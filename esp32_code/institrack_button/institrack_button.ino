#include <WiFi.h>
#include <HTTPClient.h>

// ========== CHANGE THESE ==========
const char* WIFI_SSID     = "KK947";
const char* WIFI_PASSWORD = "karthiking@947";
const char* BUS_NUMBER    = "7";
const char* STOP_NAME     = "Stop B";
// ===================================

// Server URL (your Railway server)
const char* SERVER_URL = "https://web-production-e7155.up.railway.app/bus-signal";

// Pin Configuration
#define BUTTON_PIN  18   // GPIO 18 - Connect button here
#define BUZZER_PIN  5    // GPIO 5 - Connect buzzer here
#define LED_PIN     2    // Built-in LED (blue)

// Debounce
unsigned long lastButtonPress = 0;
const int DEBOUNCE_DELAY = 2000;

void setup() {
  Serial.begin(115200);
  Serial.println("\n=============================");
  Serial.println("  InstiTrack Starting...");
  Serial.println("=============================");

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  connectWiFi();

  beep(100);
  delay(100);
  beep(100);

  Serial.println("\nInstiTrack Ready!");
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

      Serial.println("\nButton Pressed!");
      Serial.print("Confirming: ");
      Serial.println(STOP_NAME);

      bool success = sendBusSignal();

      if (success) {
        Serial.println("Stop confirmed!");
        beep(500); // 1 long beep = success
      } else {
        Serial.println("Failed to send signal!");
        beep(100); delay(100); beep(100); delay(100); beep(100); // 3 short beeps = fail
      }
    }
  }
}

bool sendBusSignal() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected! Reconnecting...");
    connectWiFi();
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{\"bus_number\":\"" + String(BUS_NUMBER) +
                   "\",\"location\":\"" + String(STOP_NAME) + "\"}";

  Serial.println("Sending: " + payload);

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.println("Response (" + String(httpCode) + "): " + response);
    http.end();
    return (httpCode == 200);
  } else {
    Serial.println("HTTP Error: " + http.errorToString(httpCode));
    http.end();
    return false;
  }
}

void connectWiFi() {
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWi-Fi Failed! Check SSID and password.");
  }
}

void beep(int duration) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(duration);
  digitalWrite(BUZZER_PIN, LOW);
}
