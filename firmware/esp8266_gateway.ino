/*
 * ============================================================================
 *  Mosquito Breeding Risk Detection System — ESP8266 Wi-Fi GATEWAY
 * ----------------------------------------------------------------------------
 *  Board: ESP8266 / NodeMCU.
 *
 *  ROLE: Wi-Fi + telemetry transport only. It reads a sensor line from the
 *        Arduino, converts it into the JSON payload, and POSTs it to the
 *        Flask dashboard. It has NO sensors of its own.
 *
 *  Link from Arduino (UART, 9600 baud):
 *    - ESP8266 D5 (GPIO14, SoftwareSerial RX)  <-  Arduino TX (via 5V->3.3V divider)
 *    - ESP8266 D6 (GPIO12, SoftwareSerial TX)  ->  Arduino RX
 *    - Common GND.
 *
 *  Expected line from the Arduino:
 *    T=29.1,H=70.0,W=1,WT=28.0,RT=2026-10-15 19:30:00
 *
 *  Required libraries (Arduino IDE Library Manager):
 *    - "ESP8266WiFi" / "ESP8266HTTPClient" (bundled with the ESP8266 board core)
 *    - "SoftwareSerial" (bundled with the ESP8266 board core)
 *
 *  NOTE: use a 5V->3.3V divider (e.g. 1k/2k) on the Arduino TX line -
 *        the ESP8266 pins are NOT 5V tolerant.
 * ============================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <SoftwareSerial.h>

// ----------------------------------------------------------------------------
//  CONFIGURATION  (edit these for your network / server)
// ----------------------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// URL of the Flask API on the computer running the dashboard.
// NOTE: use your PC's LAN/Wi-Fi IPv4 address (this machine: 10.22.141.140).
// Find it with:  ipconfig   ->  "IPv4 Address". It may change after a reboot.
const char* SERVER_URL = "http://10.22.141.140:5000/api/sensor";

const char* NODE_ID = "NODE-01";
const char* SPECIES = "aedes";          // aedes | culex | anopheles

// ----------------------------------------------------------------------------
//  LINK PINS (NodeMCU)
// ----------------------------------------------------------------------------
#define ARDUINO_RX_PIN  D5   // ESP RX (GPIO14) <- Arduino TX (via divider)
#define ARDUINO_TX_PIN  D6   // ESP TX (GPIO12) -> Arduino RX

SoftwareSerial arduinoLink(ARDUINO_RX_PIN, ARDUINO_TX_PIN);
String lineBuf;

// ----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);        // USB debug
  arduinoLink.begin(9600);     // link from the Arduino
  connectWiFi();
}

// ----------------------------------------------------------------------------
void connectWiFi() {
  Serial.printf("Connecting to WiFi: %s ", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print(F("Connected. IP address: "));
  Serial.println(WiFi.localIP());
}

// ----------------------------------------------------------------------------
//  Parse a line like "T=29.1,H=70.0,W=1,WT=28.0,RT=2026-10-15 19:30:00"
//  into the JSON payload expected by POST /api/sensor.
//  Returns false if the required fields (T, H, W) are missing.
// ----------------------------------------------------------------------------
bool buildPayload(const String& line, String& payload) {
  float temperature = NAN, humidity = NAN, waterTemp = NAN;
  int   waterFlag = -1;
  String rtcTime = "";

  int start = 0;
  while (start <= (int)line.length()) {
    int comma = line.indexOf(',', start);
    String token = (comma == -1) ? line.substring(start) : line.substring(start, comma);

    int eq = token.indexOf('=');
    if (eq > 0) {
      String key = token.substring(0, eq);   key.trim();
      String val = token.substring(eq + 1);  val.trim();
      if      (key == "T")  temperature = val.toFloat();
      else if (key == "H")  humidity    = val.toFloat();
      else if (key == "W")  waterFlag   = val.toInt();
      else if (key == "WT") waterTemp   = val.toFloat();
      else if (key == "RT") rtcTime     = val;
    }

    if (comma == -1) break;
    start = comma + 1;
  }

  if (isnan(temperature) || isnan(humidity) || waterFlag < 0) {
    return false;
  }

  payload = "{";
  payload += "\"node_id\":\"" + String(NODE_ID) + "\",";
  payload += "\"temperature\":" + String(temperature, 1) + ",";
  payload += "\"humidity\":" + String(humidity, 1) + ",";
  payload += "\"water_detected\":" + String(waterFlag == 1 ? "true" : "false");

  if (!isnan(waterTemp)) {
    payload += ",\"water_temperature\":" + String(waterTemp, 1);
  }

  // DS3231 RTC device time (authoritative timestamp) when supplied
  if (rtcTime.length() > 0) {
    payload += ",\"timestamp\":\"" + rtcTime + "\"";
  }

  payload += ",\"rssi\":" + String(WiFi.RSSI()) + ",";
  payload += "\"battery_level\":88,";            // placeholder / optional
  payload += "\"species\":\"" + String(SPECIES) + "\"";
  payload += "}";
  return true;
}

// ----------------------------------------------------------------------------
void postPayload(const String& payload) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi lost - reconnecting..."));
    connectWiFi();
  }

  WiFiClient client;
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  Serial.print(F("POST payload: "));
  Serial.println(payload);

  int httpCode = http.POST(payload);
  if (httpCode > 0) {
    Serial.printf("HTTP %d -> %s\n", httpCode, http.getString().c_str());
  } else {
    Serial.printf("HTTP POST failed: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

// ----------------------------------------------------------------------------
void loop() {
  // Accumulate one line from the Arduino, then forward it.
  while (arduinoLink.available()) {
    char c = arduinoLink.read();
    if (c == '\n') {
      lineBuf.trim();
      String payload;
      if (lineBuf.length() > 0 && buildPayload(lineBuf, payload)) {
        postPayload(payload);
      }
      lineBuf = "";
    } else if (c != '\r') {
      lineBuf += c;
      if (lineBuf.length() > 160) lineBuf = "";   // malformed line guard
    }
  }
}
