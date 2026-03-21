#include <WiFi.h>
#include <HTTPClient.h>

// ========== CHANGE THESE ==========
const char* WIFI_SSID     = "KK947";
const char* WIFI_PASSWORD = "karthiking@947";
const char* BUS_NUMBER    = "7";
const char* STOP_NAME     = "Stop B";
// ===================================

// Server URL
const char* SERVER_URL = "https://web-production-e7155.up.railway.app/bus-signal";

// Pin Configuration
#define BUTTON_PIN  18   // GPIO 18 - Connect button here
#define BUZZER_PIN  5    // GPIO 5 - Connect buzzer here
#define LED_PIN     2    // Built-in LED (blue)
#define BATTERY_PIN 34   // GPIO 34 - Analog pin for Battery Voltage Divider

// Debounce
unsigned long lastButtonPress = 0;
const int DEBOUNCE_DELAY = 2000;

void setup() {
  Serial.begin(115200);
  Serial.println("\n=============================");
  Serial.println("  InstiTrack MVP Phase 1a");
  Serial.println("  Features: Audio Feedback & Battery");
  Serial.println("=============================");

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  // ADC pins don't need pinMode(), but good practice:
  pinMode(BATTERY_PIN, INPUT);

  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  // 1. Check Battery Level & Beep
  checkBatteryLevel();

  // 2. Connect Wi-Fi with Connecting Beeps
  connectWiFi();

  Serial.println("\n✅ InstiTrack Ready!");
  Serial.print("Bus: ");
  Serial.println(BUS_NUMBER);
  Serial.print("Stop: ");
  Serial.println(STOP_NAME);
  Serial.println("Press the button to send signal.");
  Serial.println("=============================\n");
}

void loop() {
  if (digitalRead(BUTTON_PIN) == LOW) {
    unsigned long currentTime = millis();

    if (currentTime - lastButtonPress > DEBOUNCE_DELAY) {
      lastButtonPress = currentTime;

      Serial.println("\n🔘 Button Pressed!");
      Serial.print("Confirming: ");
      Serial.println(STOP_NAME);

      bool success = sendBusSignal();

      if (success) {
        Serial.println("✅ Stop confirmed!");
        beep(500); // 1 long beep = success
      } else {
        Serial.println("❌ Failed to send signal!");
        beep(100); delay(100); beep(100); delay(100); beep(100); // 3 short beeps = fail
      }
    }
  }
}

// 🔋 Battery Check Function
void checkBatteryLevel() {
  Serial.println("🔋 Checking Battery Level...");
  
  // NOTE: This assumes a voltage divider connected to GPIO 34
  // If no wire is connected to GPIO 34, this will just read floating noise (random values)
  int rawADC = analogRead(BATTERY_PIN);
  
  Serial.print("Raw ADC Value: ");
  Serial.println(rawADC);

  // Example thresholds (0 - 4095 range for ESP32 ADC)
  // These values will need testing once you solder the resistors
  if (rawADC > 2800) { 
    Serial.println("Status: HIGH Charge (70-100%)");
    // 3 short beeps
    beep(100); delay(100); beep(100); delay(100); beep(100);
  } 
  else if (rawADC > 2000) { 
    Serial.println("Status: MEDIUM Charge (30-70%)");
    // 2 short beeps
    beep(100); delay(100); beep(100);
  } 
  else { 
    Serial.println("Status: LOW Charge (<30%) - NEEDS CHARGING!");
    // 1 long beep
    beep(1000);
  }
  
  delay(500); // Small pause before doing WiFi
}

// 📶 Wi-Fi Function with Audio Feedback
void connectWiFi() {
  Serial.print("📶 Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    beep(50); // Short "tick" sound while connecting
    delay(450);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ Wi-Fi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    // Happy double-beep for success
    beep(150); delay(100); beep(150); delay(100); beep(300);
  } else {
    Serial.println("\n❌ Wi-Fi Failed! Check SSID and password.");
    // 3 long, sad beeps for failure
    beep(800); delay(100); beep(800); delay(100); beep(800);
  }
}

bool sendBusSignal() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ Wi-Fi disconnected! Reconnecting...");
    connectWiFi();
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{\"bus_number\":\"" + String(BUS_NUMBER) +
                   "\",\"location\":\"" + String(STOP_NAME) + "\"}";

  Serial.println("📡 Sending: " + payload);

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.println("📨 Response (" + String(httpCode) + "): " + response);
    http.end();
    return (httpCode == 200);
  } else {
    Serial.println("❌ HTTP Error: " + http.errorToString(httpCode));
    http.end();
    return false;
  }
}

void beep(int duration) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(duration);
  digitalWrite(BUZZER_PIN, LOW);
}
