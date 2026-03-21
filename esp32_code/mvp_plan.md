## MVP Phase 1a (Audio Feedback & Battery prep)

This is an awesome idea. Since this device won't have a screen, using the **Buzzer as the "voice"** of the device is the perfect professional way to do it.

Yes, this is **100% possible!** Here is the logic we will apply:

### 🔊 1. Wi-Fi Connection Feedback
- **While Connecting**: The buzzer will emit a distinct "tick" sound (short blip every 500ms) so you know it's trying.
- **Success**: A happy double-beep (e.g., `beep-BEEP`) means Wi-Fi is connected!
- **Failure**: 3 long, sad beeps means it couldn't connect.

### 🔋 2. Battery / Charger Level Feedback
If the board is running on battery, the ESP32 needs to measure the battery voltage using an Analog pin (ADC).
Since we only have a buzzer, it will play a sequence of beeps to tell you the level:
- **High Charge (70-100%)**: 3 short beeps (`beep beep beep`)
- **Medium Charge (30-70%)**: 2 short beeps (`beep beep`)
- **Low Charge (<30%)**: 1 long beep (`beeeeeeep`) warning to charge.

### ⚠️ Note about the "New Type-C ESP32"
Unless your specific ESP32 board has a built-in battery charging circuit specifically designed to measure its own battery (like a WEMOS Lolin32 or TTGO T-Display), you will need to add 2 resistors (a voltage divider) between the battery and a GPIO pin (e.g., GPIO 34) to measure the voltage safely. 

I will add the battery logic in code, mapped to `BATTERY_PIN 34`. If it's not wired up yet, it'll just give a random reading.

Would you like me to write this **Phase 1a MVP Code** and update your `institrack_button.ino` file now?
