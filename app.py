from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
try:
    from flask_cors import CORS
except ImportError:
    # The local dashboard does not require CORS. Keep the app usable when the
    # optional development convenience package has not been installed yet.
    def CORS(app, **_kwargs):
        return app
import database
import random
import os
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
# The dashboard is served by this Flask app, so cross-origin requests are not
# needed in the local deployment. Restrict CORS to the local UI during demos.
CORS(app, resources={r"/api/*": {"origins": ["http://127.0.0.1:5000", "http://localhost:5000"]}})

# Initialize Database on launch
with app.app_context():
    database.init_db()

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.svg', mimetype='image/svg+xml')


@app.route('/')
def index():
    return render_template('index.html')

last_hardware_ping_time = None


def parse_boolean(value):
    """Accept only actual JSON booleans and common ESP8266 string forms."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1"):
            return True
        if normalized in ("false", "0"):
            return False
    raise ValueError("water_detected must be true or false")


def parse_bounded_int(raw_value, field_name, default, minimum, maximum):
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return value

@app.route('/api/sensor', methods=['POST'])
def receive_sensor_data():
    """
    API endpoint for ESP8266 / NodeMCU to post JSON sensor payload:
    {
        "temperature": 28.5,
        "humidity": 78.0,
        "water_detected": true,
        "node_id": "NODE-01",       (optional, default NODE-01)
        "rssi": -65,                 (optional, Wi-Fi signal strength dBm)
        "battery_level": 88,         (optional, battery percentage)
        "species": "aedes"           (optional, aedes/culex/anopheles)
    }
    """
    global last_hardware_ping_time
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"status": "error", "message": "Missing JSON payload"}), 400
            
        temperature = data.get('temperature')
        humidity = data.get('humidity')
        water_detected = data.get('water_detected')
        
        # Validation
        if temperature is None or humidity is None or water_detected is None:
            return jsonify({
                "status": "error", 
                "message": "Required fields: temperature, humidity, water_detected"
            }), 400
            
        # Convert types safely
        temperature = float(temperature)
        humidity = float(humidity)
        water_detected = parse_boolean(water_detected)
        if not -20.0 <= temperature <= 70.0:
            raise ValueError("temperature must be between -20 and 70°C")
        if not 0.0 <= humidity <= 100.0:
            raise ValueError("humidity must be between 0 and 100%")
        
        # Optional hardware diagnostic fields
        node_id = data.get('node_id', 'NODE-01')
        rssi = parse_bounded_int(data.get('rssi'), 'rssi', -65, -120, 0)
        battery_level = parse_bounded_int(data.get('battery_level'), 'battery_level', 88, 0, 100)
        species = str(data.get('species', 'aedes')).lower()
        if species not in database.SPECIES_PROFILES:
            raise ValueError("species must be aedes, culex, or anopheles")
        
        # Mark hardware ping timestamp
        last_hardware_ping_time = datetime.now()

        # Insert into SQLite database & calculate risk
        reading = database.insert_reading(temperature, humidity, water_detected,
                                          node_id=node_id, rssi=rssi,
                                          battery_level=battery_level, species=species,
                                          data_source='hardware')
        database.create_alert_for_reading(reading)
        
        return jsonify({
            "status": "success",
            "message": "Sensor reading recorded successfully",
            "data": reading
        }), 201
        
    except ValueError as e:
        return jsonify({"status": "error", "message": f"Invalid data format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/latest', methods=['GET'])
def get_latest():
    node_id = request.args.get('node_id')
    allow_empty = request.args.get('allow_empty', 'false').lower() in {'1', 'true', 'yes', 'y'}
    latest = database.get_latest_reading(node_id=node_id)
    if not latest:
        if allow_empty:
            return jsonify({
                "status": "success",
                "data": None,
                "message": "Waiting for sensor data",
                "is_hardware_connected": False
            })
        return jsonify({"status": "error", "message": "No sensor readings available"}), 404

    # Calculate real-time ESP8266 connection heartbeat (active if POST received within last 15s)
    is_connected = False
    if last_hardware_ping_time is not None:
        delta = (datetime.now() - last_hardware_ping_time).total_seconds()
        is_connected = (delta <= 15.0)

    return jsonify({
        "status": "success", 
        "data": latest,
        "is_hardware_connected": is_connected
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    risk_level = request.args.get('risk_level')
    try:
        limit = parse_bounded_int(request.args.get('limit'), 'limit', 100, 1, 500)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    
    records = database.get_history(start_date=start_date, end_date=end_date, risk_level=risk_level, limit=limit)
    return jsonify({"status": "success", "count": len(records), "data": records})

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    try:
        hours = parse_bounded_int(request.args.get('hours'), 'hours', 48, 1, 24 * 90)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    analytics = database.get_analytics_data(hours=hours)
    return jsonify({"status": "success", "data": analytics})

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    if request.method == 'POST':
        new_config = request.get_json(force=True)
        if not new_config:
            return jsonify({"status": "error", "message": "No config payload provided"}), 400
        try:
            database.update_config(new_config)
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
        return jsonify({"status": "success", "message": "Configuration updated successfully", "config": database.get_config()})
    else:
        return jsonify({"status": "success", "config": database.get_config()})

@app.route('/api/simulate', methods=['POST'])
def simulate_reading():
    """Generate a quick realistic simulated sensor payload for demo testing"""
    mode = request.json.get('mode', 'random') if request.is_json else 'random'
    species = request.json.get('species', 'aedes') if request.is_json else 'aedes'
    node_id = 'SIMULATION'
    
    if mode == 'high_risk':
        temp = round(random.uniform(28.0, 31.5), 1)
        hum = round(random.uniform(75.0, 88.0), 1)
        water = True
        rssi = random.randint(-80, -55)
        battery = random.randint(70, 95)
    elif mode == 'moderate_risk':
        temp = round(random.uniform(24.0, 27.0), 1)
        hum = round(random.uniform(55.0, 68.0), 1)
        water = random.choice([True, False])
        rssi = random.randint(-85, -60)
        battery = random.randint(60, 90)
    elif mode == 'low_risk':
        temp = round(random.uniform(18.0, 22.0), 1)
        hum = round(random.uniform(35.0, 48.0), 1)
        water = False
        rssi = random.randint(-90, -65)
        battery = random.randint(40, 85)
    else:
        # Default random walk around current latest
        latest = database.get_latest_reading()
        if latest:
            temp = round(max(15.0, min(42.0, latest['temperature'] + random.uniform(-1.2, 1.2))), 1)
            hum = round(max(30.0, min(95.0, latest['humidity'] + random.uniform(-3.0, 3.0))), 1)
            water = random.choice([True, False, latest['water_detected']])
        else:
            temp = 28.0
            hum = 75.0
            water = True
        rssi = random.randint(-85, -50)
        battery = random.randint(60, 100)

    reading = database.insert_reading(temp, hum, water, node_id=node_id,
                                      rssi=rssi, battery_level=battery, species=species,
                                      data_source='simulation')
    database.create_alert_for_reading(reading)
    return jsonify({"status": "success", "message": f"Simulated {mode} reading generated", "data": reading})

@app.route('/api/nodes', methods=['GET'])
def get_nodes_status():
    """Return all geographic sensor node statuses for the GIS map"""
    nodes = database.get_multi_nodes_status()
    return jsonify({"status": "success", "data": nodes})

@app.route('/api/species', methods=['GET'])
def get_species_profiles():
    """Return available mosquito species profiles"""
    return jsonify({
        "status": "success",
        "data": database.SPECIES_PROFILES
    })


@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Device inventory derived from the most recent reading at each site."""
    return jsonify({'status': 'success', 'data': database.get_multi_nodes_status()})


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    return jsonify({'status': 'success', 'data': database.get_alerts()})


@app.route('/api/summary', methods=['GET'])
def get_site_summary():
    return jsonify({'status': 'success', 'data': database.get_site_summary()})


@app.route('/api/compare', methods=['GET'])
def get_compare():
    return jsonify({'status': 'success', 'data': database.get_node_comparison()})


@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    node_id = request.args.get('node_id')
    recommendations = database.get_recommendations(node_id=node_id)
    return jsonify({'status': 'success', 'data': recommendations})


@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    if not database.acknowledge_alert(alert_id):
        return jsonify({'status': 'error', 'message': 'Alert not found'}), 404
    return jsonify({'status': 'success'})


@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    try:
        hours = parse_bounded_int(request.args.get('hours'), 'hours', 24, 1, 168)
    except ValueError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 400
    return jsonify({'status': 'success', 'data': database.get_forecast(hours)})


@app.route('/api/inspections', methods=['GET', 'POST'])
def manage_inspections():
    if request.method == 'GET':
        return jsonify({'status': 'success', 'data': database.get_inspections()})

    node_id = request.form.get('node_id', 'NODE-01').strip()
    site_name = request.form.get('site_name', '').strip()
    notes = request.form.get('notes', '').strip()
    if not site_name:
        return jsonify({'status': 'error', 'message': 'site_name is required'}), 400
    photo_path = None
    photo = request.files.get('photo')
    if photo and photo.filename:
        extension = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({'status': 'error', 'message': 'Photo must be PNG, JPG, JPEG, or WEBP'}), 400
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(photo.filename)}"
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        photo_path = f"uploads/{filename}"
    inspection = database.create_inspection(node_id, site_name, notes, photo_path)
    return jsonify({'status': 'success', 'data': inspection}), 201


@app.route('/api/inspections/<int:inspection_id>', methods=['PATCH'])
def update_inspection(inspection_id):
    payload = request.get_json(silent=True) or {}
    try:
        changed = database.update_inspection_status(inspection_id, payload.get('status', ''))
    except ValueError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 400
    if not changed:
        return jsonify({'status': 'error', 'message': 'Inspection not found'}), 404
    return jsonify({'status': 'success'})


@app.route('/api/calibrations', methods=['GET', 'POST'])
def manage_calibrations():
    if request.method == 'GET':
        return jsonify({'status': 'success', 'data': database.get_calibrations()})
    payload = request.get_json(silent=True) or {}
    try:
        node_id = str(payload.get('node_id', 'NODE-01')).strip()
        sensor_name = str(payload['sensor_name']).strip()
        offset_value = float(payload.get('offset_value', 0))
        next_due = str(payload['next_due']).strip()
        if not sensor_name or not next_due:
            raise ValueError('sensor_name and next_due are required')
        datetime.strptime(next_due, '%Y-%m-%d')
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 400
    calibration = database.add_calibration(node_id, sensor_name, offset_value, next_due, str(payload.get('notes', '')))
    return jsonify({'status': 'success', 'data': calibration}), 201


if __name__ == '__main__':
    print("[MOSQUITO DETECT] Starting Mosquito Breeding Risk Detection System Server...")
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
