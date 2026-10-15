import sqlite3
import os
from datetime import datetime, timedelta
import random

DB_PATH = os.environ.get(
    'MOSQUITO_DB_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mosquito_monitoring.db')
)

DEFAULT_CONFIG = {
    'temp_opt_min': '25.0',
    'temp_opt_max': '32.0',
    'temp_sub_min': '20.0',
    'temp_sub_max': '36.0',
    'humidity_opt': '65.0',
    'thresh_high': '70',
    'thresh_mod': '35',
    'water_weight': '45',
    'temp_weight': '35',
    'humidity_weight': '20'
}

SPECIES_PROFILES = {
    'aedes': {
        'name': 'Aedes aegypti (Dengue / Chikungunya / Zika)',
        'temp_opt_min': 25.0,
        'temp_opt_max': 32.0,
        'humidity_opt': 65.0,
        'hatching_base_days': 7.0
    },
    'culex': {
        'name': 'Culex quinquefasciatus (Filariasis / West Nile)',
        'temp_opt_min': 23.0,
        'temp_opt_max': 30.0,
        'humidity_opt': 60.0,
        'hatching_base_days': 9.0
    },
    'anopheles': {
        'name': 'Anopheles stephensi (Malaria)',
        'temp_opt_min': 26.0,
        'temp_opt_max': 34.0,
        'humidity_opt': 70.0,
        'hatching_base_days': 10.0
    }
}

NODES_LIST = [
    {"node_id": "NODE-01", "name": "Current Site", "lat": 12.9716, "lng": 77.5946, "location": "Current site"}
]
LEGACY_NODE_IDS = {"NODE-02", "NODE-03", "NODE-04"}


def cleanup_legacy_sample_nodes(conn):
    """Remove stale demo nodes left behind from earlier project data sets."""
    cursor = conn.cursor()
    for table in ("sensor_readings", "alert_events", "inspections", "calibrations"):
        if table == "sensor_readings":
            cursor.execute(f"DELETE FROM {table} WHERE node_id IN ({', '.join('?' for _ in sorted(LEGACY_NODE_IDS))})", sorted(LEGACY_NODE_IDS))
        else:
            cursor.execute(f"DELETE FROM {table} WHERE node_id IN ({', '.join('?' for _ in sorted(LEGACY_NODE_IDS))})", sorted(LEGACY_NODE_IDS))
    conn.commit()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create sensor readings table with extended hardware diagnostic fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT DEFAULT 'NODE-01',
            timestamp TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            water_detected INTEGER NOT NULL,
            water_temperature REAL,
            risk_level TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_reason TEXT NOT NULL,
            rssi INTEGER DEFAULT -65,
            battery_level INTEGER DEFAULT 88,
            species TEXT DEFAULT 'aedes',
            data_source TEXT NOT NULL DEFAULT 'unverified'
        )
    ''')

    columns = {row['name'] for row in cursor.execute('PRAGMA table_info(sensor_readings)')}
    if 'data_source' not in columns:
        cursor.execute("ALTER TABLE sensor_readings ADD COLUMN data_source TEXT NOT NULL DEFAULT 'unverified'")
    if 'water_temperature' not in columns:
        cursor.execute("ALTER TABLE sensor_readings ADD COLUMN water_temperature REAL")
    
    # System config table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reading_id INTEGER,
            node_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            acknowledged INTEGER NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            site_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            notes TEXT NOT NULL DEFAULT '',
            photo_path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calibrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            sensor_name TEXT NOT NULL,
            offset_value REAL NOT NULL DEFAULT 0,
            calibrated_at TEXT NOT NULL,
            next_due TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT ''
        )
    ''')
    
    for key, value in DEFAULT_CONFIG.items():
        cursor.execute('INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)', (key, value))

    cleanup_legacy_sample_nodes(conn)
    conn.commit()
    
    conn.commit()
        
    conn.close()

def get_config():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM system_config')
    rows = cursor.fetchall()
    conn.close()
    
    config = DEFAULT_CONFIG.copy()
    for row in rows:
        config[row['key']] = row['value']
    return config

def update_config(new_config):
    allowed_keys = set(DEFAULT_CONFIG)
    unknown_keys = set(new_config) - allowed_keys
    if unknown_keys:
        raise ValueError(f"Unsupported configuration key(s): {', '.join(sorted(unknown_keys))}")

    numeric_config = {}
    for key, value in new_config.items():
        try:
            numeric_config[key] = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric") from exc

    merged = {key: float(value) for key, value in get_config().items()}
    merged.update(numeric_config)
    if merged['temp_opt_min'] >= merged['temp_opt_max']:
        raise ValueError("temp_opt_min must be lower than temp_opt_max")
    if not 0 <= merged['humidity_opt'] <= 100:
        raise ValueError("humidity_opt must be between 0 and 100")
    if not 0 <= merged['thresh_mod'] < merged['thresh_high'] <= 100:
        raise ValueError("thresholds must satisfy 0 ≤ thresh_mod < thresh_high ≤ 100")
    if any(merged[key] < 0 for key in ('water_weight', 'temp_weight', 'humidity_weight')):
        raise ValueError("risk weights cannot be negative")

    conn = get_db_connection()
    cursor = conn.cursor()
    integer_keys = {'thresh_high', 'thresh_mod', 'water_weight', 'temp_weight', 'humidity_weight'}
    for key, value in numeric_config.items():
        stored_value = str(int(value)) if key in integer_keys else str(value)
        cursor.execute('''
            INSERT INTO system_config (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''', (key, stored_value))
    conn.commit()
    conn.close()

def calculate_risk(temperature, humidity, water_detected, species='aedes', water_temperature=None):
    config = get_config()
    profile = SPECIES_PROFILES.get(species, SPECIES_PROFILES['aedes'])
    
    temp_opt_min = profile['temp_opt_min']
    temp_opt_max = profile['temp_opt_max']
    humidity_opt = profile['humidity_opt']
    
    thresh_high = int(config.get('thresh_high', 70))
    thresh_mod = int(config.get('thresh_mod', 35))
    
    water_weight = int(config.get('water_weight', 45))
    temp_weight = int(config.get('temp_weight', 35))
    humidity_weight = int(config.get('humidity_weight', 20))
    
    score = 0
    reasons = []
    
    # Water Evaluation
    if water_detected:
        score += water_weight
        reasons.append("Stagnant water detected (essential oviposition site)")
    else:
        reasons.append("No stagnant water detected")
    
    # Water Temperature Evaluation (DS18B20) - bonus points for warm water
    if water_temperature is not None:
        if 25.0 <= water_temperature <= 35.0:
            score += 10
            reasons.append(f"Water temperature ({water_temperature}°C) is optimal for larval development")
        elif 20.0 <= water_temperature <= 40.0:
            score += 5
            reasons.append(f"Water temperature ({water_temperature}°C) supports larval growth")
        else:
            reasons.append(f"Water temperature ({water_temperature}°C) is suboptimal for larvae")
        
    # Temperature Evaluation
    if temp_opt_min <= temperature <= temp_opt_max:
        score += temp_weight
        reasons.append(f"Air temperature ({temperature}°C) is in optimal range for {profile['name']}")
    elif 18.0 <= temperature <= 38.0:
        score += int(temp_weight * 0.55)
        reasons.append(f"Air temperature ({temperature}°C) supports moderate growth rate")
    else:
        score += int(temp_weight * 0.15)
        reasons.append(f"Air temperature ({temperature}°C) is suboptimal")
        
    # Humidity Evaluation
    if humidity >= humidity_opt:
        score += humidity_weight
        reasons.append(f"High humidity ({humidity}%) prolongs adult mosquito lifespan")
    elif humidity >= 45.0:
        score += int(humidity_weight * 0.5)
        reasons.append(f"Moderate humidity ({humidity}%) supports adult survival")
    else:
        score += int(humidity_weight * 0.2)
        reasons.append(f"Low humidity ({humidity}%) reduces adult longevity")
        
    if score >= thresh_high:
        risk_level = "HIGH"
    elif score >= thresh_mod:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"
        
    # Calculate Biological Larval Hatching Incubation Duration
    # Use water temperature if available (more accurate for aquatic larvae), else air temperature
    incubation_temp = water_temperature if water_temperature is not None else temperature
    if incubation_temp > 15.0:
        est_incubation_days = round(max(3.0, profile['hatching_base_days'] * (28.0 / max(18.0, incubation_temp))), 1)
    else:
        est_incubation_days = 14.0

    return {
        "risk_level": risk_level,
        "risk_score": min(100, score),
        "risk_reason": " | ".join(reasons),
        "incubation_days": est_incubation_days,
        "species_profile": profile['name']
    }

def insert_reading(temperature, humidity, water_detected, node_id="NODE-01", rssi=-65, battery_level=88, species="aedes", timestamp=None, data_source='unverified', water_temperature=None):
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    risk = calculate_risk(temperature, humidity, water_detected, species=species, water_temperature=water_temperature)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sensor_readings 
                (node_id, timestamp, temperature, humidity, water_detected, water_temperature, risk_level, risk_score, risk_reason, rssi, battery_level, species, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (node_id, timestamp, float(temperature), float(humidity), 1 if water_detected else 0,
                    water_temperature, risk['risk_level'], risk['risk_score'], risk['risk_reason'], int(rssi), int(battery_level), species, data_source))
    
    reading_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "id": reading_id,
        "node_id": node_id,
        "timestamp": timestamp,
        "temperature": temperature,
        "humidity": humidity,
        "water_detected": bool(water_detected),
        "water_temperature": water_temperature,
        "risk_level": risk['risk_level'],
        "risk_score": risk['risk_score'],
        "risk_reason": risk['risk_reason'],
        "incubation_days": risk['incubation_days'],
        "species_profile": risk['species_profile'],
        "rssi": rssi,
        "battery_level": battery_level,
        "data_source": data_source
    }


def create_alert_for_reading(reading):
    """Record actionable conditions for the alert centre without duplicate UI logic."""
    if not (reading['water_detected'] or reading['risk_level'] == 'HIGH'):
        return None
    severity = 'HIGH' if reading['risk_level'] == 'HIGH' else 'MODERATE'
    message = (f"{reading['node_id']}: {reading['risk_level']} breeding risk "
               f"({reading['risk_score']}%). "
               f"{'Standing water detected.' if reading['water_detected'] else 'Inspect site conditions.'}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alert_events (reading_id, node_id, severity, message, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (reading['id'], reading['node_id'], severity, message, reading['timestamp']))
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alert_id


def get_alerts(limit=20):
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT alert_events.* FROM alert_events
        JOIN sensor_readings ON sensor_readings.id = alert_events.reading_id
        WHERE sensor_readings.data_source = 'hardware'
        ORDER BY alert_events.id DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(row) | {'acknowledged': bool(row['acknowledged'])} for row in rows]


def get_node_comparison():
    """Return a compact comparison of each node's health, risk, and maintenance needs."""
    nodes = [node for node in get_multi_nodes_status() if node['has_reading']]
    comparison = []
    for node in nodes:
        comparison.append({
            'node_id': node['node_id'],
            'name': node['name'],
            'location': node.get('location', 'Unknown'),
            'risk_score': node['risk_score'],
            'risk_level': node['risk_level'],
            'temperature': node['temperature'],
            'humidity': node['humidity'],
            'water_detected': node['water_detected'],
            'battery_level': node.get('battery_level', 0),
            'last_sync': node.get('last_sync', 'Unknown'),
            'priority': 'HIGH' if node['risk_level'] == 'HIGH' else 'MODERATE' if node['risk_level'] == 'MODERATE' else 'LOW'
        })
    return sorted(comparison, key=lambda item: (-item['risk_score'], item['node_id']))


def get_site_summary():
    """Aggregate site-level health and compare all monitored nodes."""
    nodes = [node for node in get_multi_nodes_status() if node['has_reading']]
    if not nodes:
        return {
            'overall_risk': None,
            'site_health': 'NO DATA',
            'alerts': 0,
            'nodes_with_high_risk': 0,
            'avg_temperature': None,
            'avg_humidity': None,
            'data_quality_score': None,
            'comparison': [],
            'highest_risk_node': None,
            'summary': 'No sensor readings have been recorded yet.'
        }

    avg_temp = round(sum(node['temperature'] for node in nodes) / len(nodes), 1)
    avg_humidity = round(sum(node['humidity'] for node in nodes) / len(nodes), 1)
    overall_risk = round(sum(node['risk_score'] for node in nodes) / len(nodes))
    high_risk_nodes = sum(1 for node in nodes if node['risk_level'] == 'HIGH')
    alert_count = len(get_alerts(limit=20))
    quality_issues = sum(1 for node in nodes if node.get('battery_level', 0) < 35)
    quality_score = max(0, 100 - (high_risk_nodes * 12) - (quality_issues * 8) - max(0, alert_count - 2) * 4)

    highest_risk_node = max(nodes, key=lambda item: item['risk_score']) if nodes else None
    if highest_risk_node is None:
        health = 'STABLE'
    elif overall_risk >= 75 or high_risk_nodes >= 2:
        health = 'CRITICAL'
    elif overall_risk >= 45:
        health = 'WATCH'
    else:
        health = 'STABLE'

    comparison = get_node_comparison()
    return {
        'overall_risk': overall_risk,
        'site_health': health,
        'alerts': alert_count,
        'nodes_with_high_risk': high_risk_nodes,
        'avg_temperature': avg_temp,
        'avg_humidity': avg_humidity,
        'data_quality_score': quality_score,
        'comparison': comparison,
        'highest_risk_node': highest_risk_node['node_id'] if highest_risk_node else None,
        'summary': f"{health} site conditions: {overall_risk}% average breeding risk across {len(nodes)} monitored nodes."
    }


def get_recommendations(node_id=None):
    """Return prioritized field actions to reduce mosquito-breeding risk."""
    nodes = [node for node in get_multi_nodes_status() if node['has_reading']]
    if node_id:
        nodes = [node for node in nodes if node['node_id'] == node_id]
    if not nodes:
        return {
            'priority': 'LOW',
            'summary': 'No active site data is available for recommendations.',
            'actions': []
        }

    actions = []
    for node in nodes:
        if node['water_detected']:
            actions.append({
                'node_id': node['node_id'],
                'priority': 'HIGH',
                'title': f'Drain and inspect {node["name"]}',
                'detail': 'Standing water was detected. Remove obstructions, drain the source, and clear any containers or surface pooling.',
                'category': 'Water management'
            })
        if node['risk_level'] in {'MODERATE', 'HIGH'}:
            actions.append({
                'node_id': node['node_id'],
                'priority': 'MODERATE',
                'title': f'Increase inspection frequency at {node["node_id"]}',
                'detail': 'The site is trending toward mosquito breeding conditions. Reinspect the area within 24 hours.',
                'category': 'Inspection'
            })
        if node.get('battery_level', 100) < 35:
            actions.append({
                'node_id': node['node_id'],
                'priority': 'MODERATE',
                'title': f'Replace battery for {node["node_id"]}',
                'detail': 'Battery level is low; replace or recharge the sensor to maintain continuous monitoring.',
                'category': 'Maintenance'
            })
        if node['humidity'] >= 75 and node['temperature'] >= 25:
            actions.append({
                'node_id': node['node_id'],
                'priority': 'MODERATE',
                'title': f'Prioritize larval control near {node["node_id"]}',
                'detail': 'Humidity and temperature are within the high-risk range for mosquito survival and egg development.',
                'category': 'Larval control'
            })

    if not actions:
        actions.append({
            'node_id': nodes[0]['node_id'],
            'priority': 'LOW',
            'title': 'Continue routine monitoring',
            'detail': 'Current conditions are stable; keep the regular inspection cadence and monitor for changes.',
            'category': 'Monitoring'
        })

    def priority_order(level):
        return {'HIGH': 3, 'MODERATE': 2, 'LOW': 1}.get(level, 0)

    actions.sort(key=lambda item: (-priority_order(item['priority']), item['node_id']))
    top_priority = max((item['priority'] for item in actions), key=priority_order, default='LOW')
    summary = f"{top_priority} priority response required for {len(actions)} recommended actions." if actions else 'No site actions required.'
    return {
        'priority': top_priority,
        'summary': summary,
        'actions': actions[:6]
    }


def acknowledge_alert(alert_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE alert_events SET acknowledged = 1 WHERE id = ?', (alert_id,))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def create_inspection(node_id, site_name, notes='', photo_path=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO inspections (node_id, site_name, notes, photo_path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (node_id, site_name, notes, photo_path, now, now))
    inspection_id = cursor.lastrowid
    conn.commit()
    row = conn.execute('SELECT * FROM inspections WHERE id = ?', (inspection_id,)).fetchone()
    conn.close()
    return dict(row)


def get_inspections(limit=30):
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM inspections ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_inspection_status(inspection_id, status):
    if status not in {'OPEN', 'SCHEDULED', 'RESOLVED'}:
        raise ValueError('status must be OPEN, SCHEDULED, or RESOLVED')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE inspections SET status = ?, updated_at = ? WHERE id = ?',
                   (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inspection_id))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def add_calibration(node_id, sensor_name, offset_value, next_due, notes=''):
    calibrated_at = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO calibrations (node_id, sensor_name, offset_value, calibrated_at, next_due, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (node_id, sensor_name, offset_value, calibrated_at, next_due, notes))
    calibration_id = cursor.lastrowid
    conn.commit()
    row = conn.execute('SELECT * FROM calibrations WHERE id = ?', (calibration_id,)).fetchone()
    conn.close()
    return dict(row)


def get_calibrations():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM calibrations ORDER BY next_due ASC, id DESC').fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_forecast(hours=24):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM sensor_readings WHERE data_source = 'hardware' ORDER BY id DESC LIMIT 12").fetchall()
    conn.close()
    if not rows:
        return {'hours': hours, 'risk_level': 'UNKNOWN', 'risk_score': None, 'summary': 'Waiting for hardware readings.'}
    avg_temp = sum(row['temperature'] for row in rows) / len(rows)
    avg_humidity = sum(row['humidity'] for row in rows) / len(rows)
    water_ratio = sum(bool(row['water_detected']) for row in rows) / len(rows)
    score = calculate_risk(avg_temp, avg_humidity, water_ratio >= 0.25)['risk_score']
    score = min(100, round(score + water_ratio * 12))
    level = 'HIGH' if score >= 70 else 'MODERATE' if score >= 35 else 'LOW'
    return {
        'hours': hours, 'risk_level': level, 'risk_score': score,
        'summary': f"{level} risk expected over the next {hours} hours based on the last {len(rows)} readings.",
        'average_temperature': round(avg_temp, 1), 'average_humidity': round(avg_humidity, 1),
        'water_detection_rate': round(water_ratio * 100)
    }


def get_site_quality_summary():
    summary = get_site_summary()
    return {
        'site_health': summary['site_health'],
        'overall_risk': summary['overall_risk'],
        'data_quality_score': summary['data_quality_score'],
        'nodes_with_high_risk': summary['nodes_with_high_risk'],
        'recommendations': get_recommendations()['actions']
    }

def get_latest_reading(node_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if node_id:
        cursor.execute("SELECT * FROM sensor_readings WHERE node_id = ? AND data_source = 'hardware' ORDER BY id DESC LIMIT 1", (node_id,))
    else:
        cursor.execute("SELECT * FROM sensor_readings WHERE data_source = 'hardware' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    species = row['species'] if 'species' in row.keys() else 'aedes'
    water_temperature = row['water_temperature'] if 'water_temperature' in row.keys() else None
    risk = calculate_risk(row['temperature'], row['humidity'], bool(row['water_detected']), species=species, water_temperature=water_temperature)
    
    return {
        "id": row['id'],
        "node_id": row['node_id'] if 'node_id' in row.keys() else 'NODE-01',
        "timestamp": row['timestamp'],
        "temperature": row['temperature'],
        "humidity": row['humidity'],
        "water_detected": bool(row['water_detected']),
        "water_temperature": water_temperature,
        "risk_level": risk['risk_level'],
        "risk_score": risk['risk_score'],
        "risk_reason": risk['risk_reason'],
        "incubation_days": risk['incubation_days'],
        "species_profile": risk['species_profile'],
        "rssi": row['rssi'] if 'rssi' in row.keys() else -65,
        "battery_level": row['battery_level'] if 'battery_level' in row.keys() else 88,
        "data_source": row['data_source']
    }

def get_multi_nodes_status():
    """Return status of all geographical nodes for Leaflet GIS Map"""
    results = []
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for n in NODES_LIST:
        cursor.execute("SELECT * FROM sensor_readings WHERE node_id = ? AND data_source = 'hardware' ORDER BY id DESC LIMIT 1", (n['node_id'],))
        row = cursor.fetchone()
        if row:
            node_water_temp = row['water_temperature'] if 'water_temperature' in row.keys() else None
            risk = calculate_risk(row['temperature'], row['humidity'], bool(row['water_detected']), water_temperature=node_water_temp)
            results.append({
                **n,
                "temperature": row['temperature'],
                "humidity": row['humidity'],
                "water_detected": bool(row['water_detected']),
                "water_temperature": node_water_temp,
                "risk_level": risk['risk_level'],
                "risk_score": risk['risk_score'],
                "last_sync": row['timestamp'],
                "rssi": row['rssi'] if 'rssi' in row.keys() else -65,
                "battery_level": row['battery_level'] if 'battery_level' in row.keys() else 88,
                "has_reading": True
            })
        else:
            results.append({
                **n,
                "temperature": None,
                "humidity": None,
                "water_detected": None,
                "risk_level": "UNKNOWN",
                "risk_score": None,
                "last_sync": "Waiting for sensor data",
                "rssi": None,
                "battery_level": None,
                "has_reading": False
            })
    conn.close()
    return results

def get_history(start_date=None, end_date=None, risk_level=None, limit=100):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM sensor_readings WHERE data_source = 'hardware'"
    params = []
    
    if start_date:
        query += ' AND date(timestamp) >= date(?)'
        params.append(start_date)
    if end_date:
        query += ' AND date(timestamp) <= date(?)'
        params.append(end_date)
    if risk_level and risk_level != 'ALL':
        query += ' AND risk_level = ?'
        params.append(risk_level.upper())
        
    query += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "id": r['id'],
            "node_id": r['node_id'] if 'node_id' in r.keys() else 'NODE-01',
            "timestamp": r['timestamp'],
            "temperature": r['temperature'],
            "humidity": r['humidity'],
            "water_detected": bool(r['water_detected']),
            "risk_level": r['risk_level'],
            "risk_score": r['risk_score'],
            "risk_reason": r['risk_reason']
        })
    return results

def get_analytics_data(hours=48):
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        SELECT * FROM sensor_readings
        WHERE data_source = 'hardware' AND timestamp >= ?
        ORDER BY timestamp ASC
        LIMIT 200
    ''', (cutoff,))
    rows = cursor.fetchall()
    conn.close()
    
    timestamps = []
    temps = []
    humidities = []
    scores = []
    risk_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0}
    water_counts = {"Detected": 0, "Clear": 0}
    
    for r in rows:
        timestamps.append(r['timestamp'])
        temps.append(r['temperature'])
        humidities.append(r['humidity'])
        scores.append(r['risk_score'])
        if r['risk_level'] in risk_counts:
            risk_counts[r['risk_level']] += 1
        if r['water_detected']:
            water_counts["Detected"] += 1
        else:
            water_counts["Clear"] += 1
            
    return {
        "timestamps": timestamps,
        "temperatures": temps,
        "humidities": humidities,
        "scores": scores,
        "risk_counts": risk_counts,
        "water_counts": water_counts
    }

def seed_sample_data(conn):
    cursor = conn.cursor()
    now = datetime.now()
    
    for n in NODES_LIST:
        for i in range(24, 0, -1):
            ts = (now - timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
            
            if n['node_id'] == 'NODE-01':
                temp = round(28.5 + random.uniform(-1.0, 1.5), 1)
                hum = round(78.0 + random.uniform(-3.0, 4.0), 1)
                water = 1
                rssi = -62
                battery = 92
            else:
                continue
                
            water_temp = round(27.0 + random.uniform(-2.0, 3.0), 1)
            
            risk = calculate_risk(temp, hum, bool(water), water_temperature=water_temp)
            cursor.execute('''
                INSERT INTO sensor_readings 
                (node_id, timestamp, temperature, humidity, water_detected, water_temperature, risk_level, risk_score, risk_reason, rssi, battery_level, species)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (n['node_id'], ts, temp, hum, water, water_temp, risk['risk_level'], risk['risk_score'], risk['risk_reason'], rssi, battery, 'aedes'))
            
    conn.commit()
