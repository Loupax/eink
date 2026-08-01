// Minimal hardware test: fills the whole 7.5" panel black, then white.
// No image data involved - isolates wiring/panel from image conversion bugs.
// Same pins as eink_static_image sketch (Waveshare ESP32 Driver Board).

#include <SPI.h>
#include <GxEPD2_BW.h>

#define EPD_CS   15
#define EPD_DC   27
#define EPD_RST  26
#define EPD_BUSY 25

// Waveshare ESP32 Driver Board wires SPI clock/data to non-default pins.
// GxEPD2 doesn't take these in its constructor - the ESP32 SPI peripheral
// must be told explicitly, or it silently uses the default VSPI pins
// (18/23), which aren't connected to anything on this board.
#define EPD_SCK  13
#define EPD_MOSI 14

// Trying the V2 controller variant (GDEW075T7) since the V1 variant
// (GxEPD2_750) produced zero visible change across multiple tests.
GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(
    GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

void setup() {
  Serial.begin(115200);

  SPI.end();
  SPI.begin(EPD_SCK, -1 /* MISO unused */, EPD_MOSI, EPD_CS);
  display.init(115200);

  display.setRotation(0);
  display.setFullWindow();

  Serial.println("filling black...");
  display.firstPage();
  do {
    display.fillScreen(GxEPD_BLACK);
  } while (display.nextPage());
  Serial.println("black done");

  delay(3000);

  Serial.println("filling white...");
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
  } while (display.nextPage());
  Serial.println("white done");

  display.hibernate();
  Serial.println("test complete");
}

void loop() {}
