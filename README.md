# 🦟 Mosquito Breeding Risk Detection System (IoT Monitoring Dashboard)

An engineering IoT surveillance system and monitoring dashboard connected to an **ESP8266 / NodeMCU** hardware system. The application monitors environmental micro-climatic parameters—specifically **temperature**, **humidity**, and **stagnant standing water presence**—to calculate real-time vector infestation risk indices for Aedes aegypti (dengue vector) and Culex mosquito species.

---

## 🌟 Key Features

1. **Real-Time Main Dashboard**
   - **Animated Circular Risk Gauge:** SVG circular progress meter displaying risk score (0-100%) and dynamic risk level (`LOW`, `MODERATE`, `HIGH`).
   - **Color-Coded Statuses:** Green for LOW risk, Amber for MODERATE risk, and Crimson Red for HIGH risk.
   - **Diagnostic Reasoning:** Explains exact biological reasons for the current risk level (e.g., *Optimal incubation temp 28°C + Humidity 78% + Stagnant water present*).
   - **Live Sensors & Clock:** Real-time temperature (°C), relative humidity (%), stagnant water detection status with ripple effect, and live system date/time.
   - **Simulation Control Suite:** One-click simulation buttons (`High Risk`, `Moderate`, `Safe / Low`, `Random Pulse`) for engineering demonstrations.

2. **ESP8266 Telemetry Ingestion API**
   - Microcontroller REST API endpoint (`POST /api/sensor`) accepting JSON payloads:
     ```json
     {
       "temperature": 28.5,
       "humidity": 78.0,
       "water_detected": true
     }
     ```
   - Auto-stores sensor telemetry into SQLite database and recalculates vector breeding risk indices.

3. **Configurable Risk Thresholds**
   - Threshold parameters (`temp_opt_min`, `temp_opt_max`, `humidity_opt`, `thresh_mod`, `thresh_high`) are configurable via the backend API (`GET/POST /api/config`) and interactive drawer UI modal.

4. **Sensor Logs & History Page**
   - Tabular sensor log viewer with date range filter (Start Date, End Date) and Risk Level filter (`ALL`, `LOW`, `MODERATE`, `HIGH`).
   - **CSV Export:** Download complete sensor log tables for engineering reports and analysis.

5. **Analytics & Interactive Charts**
   - Powered by Chart.js with dark glassmorphism themes:
     - Temperature trend over time (Area line chart)
     - Relative humidity trend over time (Area line chart)
     - Risk Score timeline over time (Line chart)
     - Risk Level Category Distribution (Doughnut chart)

6. **Prominent Alerting System**
   - Animated warning notification banner pops up when stagnant water is detected or risk becomes HIGH.

7. **Multi-Factor Vector Pipeline Diagram**
   - Animated visual relationship flowchart:
     $$\text{Micro-Climate} \longrightarrow \text{ESP8266 Sensors} \longrightarrow \text{Flask Risk Engine} \longrightarrow \text{Breeding Risk Index}$$

8. **Project Documentation & Firmware Code**
   - Complete project overview page detailing Problem Statement, Objectives, Working Principle, Hardware Specs, Software Architecture, Applications, and Future Scope.
   - Ready-to-flash **ESP8266 Arduino C++ firmware sketch** with copy-to-clipboard button.

---

## 🛠️ Technology Stack

- **Frontend:** HTML5, Vanilla CSS3 (Glassmorphism design system & micro-animations), JavaScript (ES6+), Chart.js
- **Backend:** Python 3, Flask, Flask-CORS
- **Database:** SQLite3 (`mosquito_monitoring.db`)

---

## 🚀 Installation & Running Locally

### 1. Prerequisites
Ensure Python 3.8+ is installed on your system.

### 2. Clone / Open Project Directory
Navigate to the project root directory:
```bash
cd "d:\vsc  programs\stagnant water"
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Automated Test Suite (Optional)
Verify database initialization, risk calculation logic, and all REST endpoints:
```bash
python test_app.py
```

### 5. Launch the Web Application
Start the Flask development server:
```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📡 ESP8266 / NodeMCU Hardware Integration

1. Connect your **DHT11/DHT22** sensor to Pin `D4` and **Water Droplet/Rain Sensor** to Analog Pin `A0`.
2. Open the **Project Docs** tab in the dashboard or copy the firmware sketch from `templates/index.html`.
3. Update `SSID`, `PASSWORD`, and `serverName` (`http://<YOUR_COMPUTER_IP>:5000/api/sensor`) in the Arduino sketch.
4. Upload the code via Arduino IDE. The hardware will start sending sensor data every 5 seconds.

---

## 📁 Directory Structure

```
d:\vsc  programs\stagnant water\
├── app.py                   # Flask Application Controller & REST API routes
├── database.py              # SQLite connection, risk logic, CRUD & sample data seeding
├── test_app.py              # Automated unit tests for API endpoints & logic
├── requirements.txt         # Python dependencies (Flask, Flask-CORS)
├── README.md                # Project documentation
├── static/
│   ├── css/
│   │   └── style.css        # Custom Glassmorphism design system & animations
│   └── js/
│       ├── main.js          # Core UI controller, polling, gauge animation & tab logic
│       └── charts.js        # Chart.js analytics charts setup & updates
└── templates/
    └── index.html           # Main web application dashboard single-page view
```
