// Measures baseline deep-sleep current draw of the whole board (not just
// the bare ESP32 chip - the driver board's other components, e.g. the
// USB-serial chip and power LED, can dominate actual sleep current).
//
// Does nothing but immediately go to deep sleep. Wakes every 60s (so you
// can take repeated multimeter readings without needing to hit reset) and
// also wakes on a BOOT button press. Panel is left alone entirely - it's
// already in hibernate from whatever sketch ran last.
//
// Measure current with your multimeter in series with USB VBUS *after* the
// board has settled into sleep (give it a couple seconds past boot).

#include <esp_sleep.h>

#define BUTTON_PIN GPIO_NUM_0  // BOOT button, active LOW
#define SLEEP_SECONDS 60

void setup() {
  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_SECONDS * 1000000ULL);
  esp_sleep_enable_ext0_wakeup(BUTTON_PIN, 0 /* wake on LOW */);
  esp_deep_sleep_start();
}

void loop() {}
