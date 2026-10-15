/*
 * ============================================================================
 *  Mosquito Breeding Risk Detection System — ARDUINO SENSOR NODE
 * ----------------------------------------------------------------------------
 *  Board: Arduino Uno (or Nano — identical pins for this wiring).
 *
 *  ROLE: read every sensor and stream the values to the ESP8266 gateway.
 *        This board has NO Wi-Fi; it only does sensor acquisition.
 *
 *  Sensors:
 *    - DHT22       : Air temperature + relative humidity   -> D2   (digital)
 *    - DS18B20     : Waterproof water temperature (1-Wire)  -> D3   (digital)
 *    - Water probe : Stagnant-water presence (analog)       -> A0   (analog)
 *    - DS3231 RTC  : Accurate timestamps (I2C)              -> A4 SDA / A5 SCL
 *
 *  Link to ESP8266 gateway (UART):
 *    - Arduino TX (D1)  ->  ESP8266 RX   (through a 5V->3.3V divider!)
 *    - Arduino RX (D0)  <-  ESP8266 TX
 *    - Common GND.
 *
 *  Serial line protocol (9600 baud, one line per sample):
 *    T=29.1,H=70.0,W=1,WT=28.0,RT=2026-10-15 19:30:00
 *      T  = air temperature  (°C)          [required]
 *      H  = relative humidity (%)          [required]
 *      W  = water detected (1/0)           [required]
 *      WT = water temperature (°C)         [optional, DS18B20]
 *      RT = DS3231 RTC device time         [optional, YYYY-MM-DD HH:MM:SS]
 *
 *  Required libraries (Arduino IDE Library Manager):
 *    - "DHT sensor library"      by Adafruit
 *    - "Adafruit Unified Sensor" by Adafruit
 *    - "OneWire"                 by Paul Stoffregen
 *    - "DallasTemperature"       by Miles Burton
 *    - "RTClib"                  by Adafruit  (for the DS3231 RTC)
 *
 *  Wiring notes:
 *    - 4.7k pull-up between DHT22 DATA (D2) and 5V.
 *    - 4.7k pull-up between DS18B20 DQ (D3) and 5V (1-Wire bus).
 *    - DS3231 VCC -> 3.3V (NOT 5V), GND -> GND, SDA -> A4, SCL -> A5.
 *    - Water probe VCC -> 5V, GND -> GND, AO -> A0.
 *    - Arduino TX -> ESP8266 RX needs a 5V->3.3V level divider (1k/2k).
 * ============================================================================
 */

#include <Wire.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <RTClib.h>

// ----------------------------------------------------------------------------
//  PIN DEFINITIONS (Arduino Uno / Nano)
// ----------------------------------------------------------------------------
#define DHT_PIN           2      // DHT22 data
#define DHT_TYPE          DHT22
#define ONE_WIRE_BUS      3      // DS18B20 data (1-Wire)
#define WATER_SENSOR_PIN  A0     // analog water presence probe
#define WATER_THRESHOLD   500    // ADC reading above this => stagnant water present
#define SAMPLE_INTERVAL_MS 5000  // 5 second sampling interval

// ----------------------------------------------------------------------------
//  SENSOR OBJECTS
// ----------------------------------------------------------------------------
DHT dht(DHT_PIN, DHT_TYPE);
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature waterTempSensor(&oneWire);
RTC_DS3231 rtc;
bool rtcReady = false;

unsigned long lastSample = 0;

// ----------------------------------------------------------------------------
void setup() {
  Serial.begin(9600);          // link to the ESP8266 gateway
  dht.begin();
  waterTempSensor.begin();

  // DS3231 RTC on the I2C bus (Uno defaults: SDA = A4, SCL = A5)
  Wire.begin();
  rtcReady = rtc.begin();
  if (rtcReady && rtc.lostPower()) {
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
}

// ----------------------------------------------------------------------------
//  Read the DS18B20 water temperature. Returns NAN on failure.
// ----------------------------------------------------------------------------
float readWaterTemperature() {
  waterTempSensor.requestTemperatures();
  float t = waterTempSensor.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C) return NAN;
  return t;
}

// ----------------------------------------------------------------------------
//  Read all sensors and emit one line to the ESP8266 gateway.
// ----------------------------------------------------------------------------
void emitReading() {
  float humidity    = dht.readHumidity();
  float temperature = dht.readTemperature();   // Celsius

  if (isnan(humidity) || isnan(temperature)) {
    return;                                    // bad DHT cycle - skip it
  }

  int   waterRaw      = analogRead(WATER_SENSOR_PIN);
  bool  waterDetected = (waterRaw > WATER_THRESHOLD);
  float waterTemperature = readWaterTemperature();

  Serial.print(F("T="));  Serial.print(temperature, 1);
  Serial.print(F(",H=")); Serial.print(humidity, 1);
  Serial.print(F(",W=")); Serial.print(waterDetected ? 1 : 0);

  if (!isnan(waterTemperature)) {
    Serial.print(F(",WT=")); Serial.print(waterTemperature, 1);
  }

  if (rtcReady) {
    DateTime now = rtc.now();
    char ts[20];
    snprintf(ts, sizeof(ts), "%04d-%02d-%02d %02d:%02d:%02d",
             now.year(), now.month(), now.day(),
             now.hour(), now.minute(), now.second());
    Serial.print(F(",RT=")); Serial.print(ts);
  }

  Serial.println();
}

// ----------------------------------------------------------------------------
void loop() {
  if (millis() - lastSample >= SAMPLE_INTERVAL_MS) {
    lastSample = millis();
    emitReading();
  }
}
