import unittest
import json
import os
import tempfile
import shutil
from pathlib import Path

# Point database.py at a disposable SQLite file before importing the app.
TEST_DIRECTORY = tempfile.mkdtemp(
    prefix='mosquito-monitoring-tests-',
    dir=Path(__file__).resolve().parent
)
os.environ['MOSQUITO_DB_PATH'] = str(Path(TEST_DIRECTORY) / 'test.db')
from app import app
import database

class MosquitoSystemTestCase(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DIRECTORY, ignore_errors=True)

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_00_database_starts_without_sensor_values(self):
        self.assertEqual(self.app.get('/api/latest').status_code, 404)
        node = self.app.get('/api/nodes').get_json()['data'][0]
        self.assertFalse(node['has_reading'])
        self.assertIsNone(node['temperature'])
        
    def test_1_homepage(self):
        """Test main web dashboard route"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Mosquito Breeding Risk Detection', response.data)
        self.assertIn(b'MOSQUITO RISK DETECT', response.data)
        
    def test_2_receive_sensor_data(self):
        """Test API endpoint for ESP8266 sensor telemetry ingestion"""
        payload = {
            "temperature": 29.5,
            "humidity": 78.0,
            "water_detected": True
        }
        response = self.app.post('/api/sensor', 
                                 data=json.dumps(payload),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['risk_level'], 'HIGH')
        self.assertGreaterEqual(data['data']['risk_score'], 70)
        print("\n[TEST API SENSOR]: ESP8266 Payload successfully processed -> Risk:", data['data']['risk_level'], "Score:", data['data']['risk_score'])

    def test_3_get_latest(self):
        """Test fetching the latest recorded sensor reading"""
        response = self.app.get('/api/latest')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('temperature', data['data'])
        self.assertIn('risk_level', data['data'])
        print("[TEST API LATEST]: Retrieved Latest Reading -> Temp:", data['data']['temperature'], "Water:", data['data']['water_detected'])

    def test_4_get_history(self):
        """Test historical sensor log queries and filtering"""
        response = self.app.get('/api/history?risk_level=HIGH')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertGreater(data['count'], 0)
        print("[TEST API HISTORY]: Fetched", data['count'], "HIGH risk historical records")

    def test_5_analytics(self):
        """Test analytics endpoint formatted for Chart.js"""
        response = self.app.get('/api/analytics')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('temperatures', data['data'])
        self.assertIn('humidities', data['data'])
        self.assertIn('scores', data['data'])
        print("[TEST API ANALYTICS]: Analytics data successfully compiled for Chart.js")

    def test_6_config_management(self):
        """Test getting and updating configurable risk thresholds"""
        # GET Config
        res_get = self.app.get('/api/config')
        self.assertEqual(res_get.status_code, 200)
        
        # POST Config Update
        new_cfg = {"temp_opt_min": "26.0", "temp_opt_max": "33.0", "thresh_high": "75"}
        res_post = self.app.post('/api/config', data=json.dumps(new_cfg), content_type='application/json')
        self.assertEqual(res_post.status_code, 200)
        data = json.loads(res_post.data)
        self.assertEqual(data['config']['thresh_high'], '75')
        print("[TEST API CONFIG]: Threshold configurations successfully updated")

    def test_7_simulation_trigger(self):
        """Test simulator output cannot populate the live hardware node"""
        hardware_reading = self.app.get('/api/latest').get_json()['data']
        res = self.app.post('/api/simulate', data=json.dumps({"mode": "high_risk"}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['data']['risk_level'], 'HIGH')
        self.assertEqual(data['data']['node_id'], 'SIMULATION')
        self.assertEqual(data['data']['data_source'], 'simulation')
        latest = self.app.get('/api/latest').get_json()['data']
        self.assertEqual(latest['id'], hardware_reading['id'])
        print("[TEST API SIMULATE]: Simulation stayed separate from hardware readings")

    def test_8_rejects_invalid_sensor_values(self):
        response = self.app.post('/api/sensor', json={
            'temperature': 28.5, 'humidity': 101, 'water_detected': False
        })
        self.assertEqual(response.status_code, 400)

    def test_9_rejects_invalid_query_limits(self):
        self.assertEqual(self.app.get('/api/history?limit=bad').status_code, 400)
        self.assertEqual(self.app.get('/api/analytics?hours=0').status_code, 400)

    def test_10_operations_endpoints(self):
        self.assertEqual(self.app.get('/api/alerts').status_code, 200)
        self.assertEqual(self.app.get('/api/devices').status_code, 200)
        forecast = self.app.get('/api/forecast?hours=24')
        self.assertEqual(forecast.status_code, 200)
        self.assertIn('risk_score', forecast.get_json()['data'])

        inspection = self.app.post('/api/inspections', data={
            'node_id': 'NODE-01', 'site_name': 'Test drainage channel', 'notes': 'Inspection test'
        })
        self.assertEqual(inspection.status_code, 201)
        inspection_id = inspection.get_json()['data']['id']
        self.assertEqual(self.app.patch(f'/api/inspections/{inspection_id}', json={'status': 'RESOLVED'}).status_code, 200)

        calibration = self.app.post('/api/calibrations', json={
            'node_id': 'NODE-01', 'sensor_name': 'DHT22 temperature',
            'offset_value': 0.2, 'next_due': '2027-01-15', 'notes': 'Reference check'
        })
        self.assertEqual(calibration.status_code, 201)

    def test_11_top_feature_endpoints(self):
        self.app.post('/api/sensor', json={
            'temperature': 29.5, 'humidity': 80.0, 'water_detected': True
        })
        summary = self.app.get('/api/summary')
        self.assertEqual(summary.status_code, 200)
        payload = summary.get_json()
        self.assertIn('overall_risk', payload['data'])
        self.assertIn('site_health', payload['data'])

        recommendations = self.app.get('/api/recommendations?node_id=NODE-01')
        self.assertEqual(recommendations.status_code, 200)
        rec_payload = recommendations.get_json()
        self.assertGreaterEqual(len(rec_payload['data']['actions']), 1)
        self.assertIn('priority', rec_payload['data'])

    def test_12_map_current_location_control(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Use My Location', html)
        self.assertIn('Add Example Node', html)

    def test_13_node_name_uses_site_label(self):
        response = self.app.get('/api/nodes')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        names = [node['name'] for node in data['data'] if node['node_id'] == 'NODE-01']
        self.assertTrue(names)
        self.assertNotIn('My Laptop Location', names)
        self.assertIn('Current Site', names)

if __name__ == '__main__':
    unittest.main()
