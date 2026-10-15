# 🦟 Mosquito Breeding Risk Detection System (IoT Monitoring Dashboard)

An engineering IoT surveillance system and monitoring dashboard connected to a **two-board hardware system**: an **Arduino** sensor node that reads all sensors, and an **ESP8266 / NodeMCU** that handles Wi-Fi and telemetry. The application monitors environmental micro-climatic parameters—specifically **air temperature**, **humidity**, **water temperature**, and **stagnant standing water presence**—to calculate real-time vector infestation risk indices for Aedes aegypti (dengue vector) and Culex mosquito species.

---

## 🌟 Key Features

1. **Real-Time Main Dashboard**
   - **Animated Circular Risk Gauge:** SVG circular progress meter displaying risk score (0-100%) and dynamic risk level (`LOW`, `MODERATE`, `HIGH`).
   - **Color-Coded Statuses:** Green for LOW risk, Amber for MODERATE risk, and Crimson Red for HIGH risk.
   - **Diagnostic Reasoning:** Explains exact biological reasons for the current risk level (e.g., *Optimal incubation temp 28°C + Humidity 78% + Stagnant water present*).
   - **Live Sensors & Clock:** Real-time air temperature (°C), relative humidity (%), DS18B20 water temperature (°C), stagnant water detection status with ripple effect, and live system date/time.
   - **Weather Forecast & Breeding Outlook:** Live local weather (Open-Meteo) with a computed breeding-risk outlook for the coming days.
   - **Toast Notifications:** Slide-in notifications on every new sensor reading and on HIGH-risk conditions.
   - **Simulation Control Suite:** One-click simulation buttons (`High Risk`, `Moderate`, `Safe / Low`, `Random Pulse`) for engineering demonstrations.

2. **Telemetry Ingestion API**
   - Microcontroller REST API endpoint (`POST /api/sensor`) accepting JSON payloads:
     ```json
     {
       "temperature": 28.5,
       "humidity": 78.0,
       "water_detected": true,
       "water_temperature": 27.5,
       "timestamp": "2026-10-15 19:30:00"
     }
     ```
   - Auto-stores sensor telemetry into SQLite database and recalculates vector breeding risk indices.
   - **DS3231 RTC device time** (`timestamp`) is stored as the authoritative measurement time when supplied, so offline/batched uploads keep their real timestamp; otherwise the server clock is used.

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
     - Live Node Comparison (Temperature / Humidity / Risk bar chart)

6. **Prominent Alerting System**
   - Animated warning notification banner pops up when stagnant water is detected or risk becomes HIGH.

7. **Multi-Factor Vector Pipeline Diagram**
   - Animated visual relationship flowchart:
     $$\text{Micro-Climate} \longrightarrow \text{Arduino Sensors} \longrightarrow \text{ESP8266 Gateway} \longrightarrow \text{Flask Risk Engine} \longrightarrow \text{Breeding Risk Index}$$

8. **Project Documentation & Firmware Code**
   - Complete project overview page detailing Problem Statement, Objectives, Working Principle, Hardware Specs, Software Architecture, Applications, and Future Scope.
   - Ready-to-flash **Arduino + ESP8266 C++ firmware sketches** (`firmware/arduino_sensor_node.ino` and `firmware/esp8266_gateway.ino`).

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

## 📡 Arduino + ESP8266 Hardware Integration

The hardware uses a **two-board** design:

- **Arduino Uno / Nano — sensor node:** reads every sensor (no Wi-Fi).
- **ESP8266 / NodeMCU — Wi-Fi gateway:** receives the readings over a serial link and POSTs them to the API (no sensors).

1. **Arduino (sensor) wiring:**
   - **DHT22** (air temp + humidity) → Pin `D2`
   - **DS18B20** waterproof water temperature probe → Pin `D3` (with a 4.7kΩ pull-up to 5V)
   - **Water Droplet/Rain Sensor** → Analog Pin `A0`
   - **DS3231 RTC** → `A4` (SDA) / `A5` (SCL), powered from `3.3V`
2. **Serial link between the boards:** Arduino `TX` (D1) → ESP8266 `D5` (through a 5V→3.3V divider), Arduino `RX` (D0) → ESP8266 `D6`, plus a common `GND`. Both sides use `9600` baud.
3. Flash `firmware/arduino_sensor_node.ino` to the **Arduino** (Arduino IDE). It emits one line per sample, e.g. `T=29.1,H=70.0,W=1,WT=28.0,RT=2026-10-15 19:30:00`.
4. Flash `firmware/esp8266_gateway.ino` to the **ESP8266** — set `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_URL` (`http://<YOUR_COMPUTER_IP>:5000/api/sensor`). It parses the Arduino line into JSON and performs the HTTP POST.
5. Disconnect the Arduino TX line while flashing the ESP8266. The system streams a new reading every 5 seconds.

---

## 📁 Directory Structure

```
d:\vsc  programs\stagnant water\
├── app.py                   # Flask Application Controller & REST API routes
├── database.py              # SQLite connection, risk logic, CRUD & sample data seeding
├── test_app.py              # Automated unit tests for API endpoints & logic
├── requirements.txt         # Python dependencies (Flask, Flask-CORS)
├── README.md                # Project documentation
├── firmware/
│   ├── arduino_sensor_node.ino  # Arduino sensor node (DHT22 + DS18B20 + water probe + DS3231)
│   └── esp8266_gateway.ino      # ESP8266 Wi-Fi gateway (serial -> JSON -> HTTP POST)
├── static/
│   ├── css/
│   │   └── style.css        # Custom Glassmorphism design system & animations
│   └── js/
│       ├── main.js          # Core UI controller, polling, gauge animation & tab logic
│       └── charts.js        # Chart.js analytics charts setup & updates
└── templates/
    └── index.html           # Main web application dashboard single-page view
```
