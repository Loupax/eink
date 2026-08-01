// Minimal static-image render on Waveshare 7.5" e-Paper V2 (800x480, B&W)
// via Waveshare ESP32 e-Paper Driver Board, using the GxEPD2 library.
//
// Library Manager -> install "GxEPD2" by Jean-Marc Zingg.
// Board: "ESP32 Dev Module" (the Waveshare driver board uses a plain ESP32).
//
// Wiring is fixed by the Waveshare ESP32 Driver Board's onboard header —
// no jumper wires needed, just seat the panel FPC connector into the board.

#include <SPI.h>
#include <GxEPD2_BW.h>
#include "image_data.h"

// Waveshare ESP32 Driver Board pinout (from Waveshare's own DEV_Config.h)
#define EPD_CS   15
#define EPD_DC   27
#define EPD_RST  26
#define EPD_BUSY 25
#define EPD_SCK  13
#define EPD_MOSI 14

// Panel back sticker read "V2" -> GDEW075T7 controller.
GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(
    GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

void setup() {
  Serial.begin(115200);

  // GxEPD2 doesn't take SCK/MOSI in its constructor - without this the
  // ESP32 SPI peripheral silently defaults to pins 18/23, which aren't
  // wired to anything on this board.
  SPI.end();
  SPI.begin(EPD_SCK, -1 /* MISO unused */, EPD_MOSI, EPD_CS);
  display.init(115200);

  display.setRotation(0);
  display.setFullWindow();
  display.firstPage();
  do {
    display.drawInvertedBitmap(0, 0, image_data, image_data_width, image_data_height, GxEPD_BLACK);
  } while (display.nextPage());

  display.hibernate();
  Serial.println("done");
}

void loop() {
  // static image only - nothing to do
}
