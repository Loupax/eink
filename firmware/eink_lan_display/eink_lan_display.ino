// Waveshare 7.5" e-Paper V2 (800x480, B&W) on the Waveshare ESP32 Driver
// Board. Connects to WiFi, and fetches a raw 1-bit packed bitmap from
// IMAGE_URL (see config.h) and renders it: on boot, on each press of the
// BOOT button, or on a GET request to http://eink.local/refresh (see
// handleClient()).
//
// Server-side: convert an image with tools/img_to_bin.py, then serve it
// (e.g. `cd server && python3 -m http.server 8000`).

#include <SPI.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ESPmDNS.h>
#include <GxEPD2_BW.h>
#include "config.h"

#define MDNS_NAME "eink"  // reachable at http://eink.local/refresh
#define HTTP_PORT 80

#define EPD_CS   15
#define EPD_DC   27
#define EPD_RST  26
#define EPD_BUSY 25
#define EPD_SCK  13
#define EPD_MOSI 14

#define BUTTON_PIN 0  // BOOT button, active LOW

#define IMG_W 800
#define IMG_H 480
#define IMG_BYTES ((IMG_W / 8) * IMG_H)

GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(
    GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

// Heap-allocated at runtime (not a static array) - a compile-time 48000-byte
// global overflows the ESP32's fixed DRAM .bss budget once WiFi/HTTPClient's
// own static buffers are linked in.
static uint8_t *imageBuf = nullptr;

static WiFiServer httpServer(HTTP_PORT);

void connectWiFi() {
  Serial.printf("connecting to %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nconnected, IP: %s\n", WiFi.localIP().toString().c_str());
}

bool fetchImage() {
  HTTPClient http;
  http.begin(IMAGE_URL);
  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    Serial.printf("GET failed: %d\n", code);
    http.end();
    return false;
  }

  int len = http.getSize();
  if (len != IMG_BYTES) {
    Serial.printf("unexpected size: %d (want %d)\n", len, IMG_BYTES);
    http.end();
    return false;
  }

  size_t got = http.getStream().readBytes(imageBuf, IMG_BYTES);
  http.end();

  if (got != IMG_BYTES) {
    Serial.printf("short read: %u/%d bytes\n", (unsigned)got, IMG_BYTES);
    return false;
  }
  return true;
}

void renderImage() {
  display.setRotation(0);
  display.setFullWindow();
  display.firstPage();
  do {
    display.drawInvertedBitmap(0, 0, imageBuf, IMG_W, IMG_H, GxEPD_BLACK);
  } while (display.nextPage());
}

void refresh() {
  Serial.println("fetching image...");
  if (fetchImage()) {
    Serial.println("rendering...");
    renderImage();
    Serial.println("done");
  } else {
    Serial.println("fetch failed, keeping current display");
  }
}

// Minimal hand-rolled HTTP: enough to notice a request line and reply, not a
// real web server. Only GET /refresh does anything; everything else gets a
// 404 so a browser poking at http://eink.local/ (which also fetches
// /favicon.ico) doesn't trigger two refreshes.
void handleClient() {
  WiFiClient client = httpServer.available();
  if (!client) return;

  String requestLine = client.readStringUntil('\r');
  while (client.connected() && client.available()) client.read();  // drain headers

  bool isRefresh = requestLine.startsWith("GET /refresh");
  client.println(isRefresh ? "HTTP/1.1 200 OK" : "HTTP/1.1 404 Not Found");
  client.println("Content-Type: text/plain");
  client.println("Connection: close");
  client.println();
  client.println(isRefresh ? "refreshing" : "not found");
  client.stop();

  if (isRefresh) {
    Serial.println("refresh requested over HTTP");
    refresh();
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  imageBuf = (uint8_t *)malloc(IMG_BYTES);
  if (!imageBuf) {
    Serial.println("malloc failed");
    while (true) delay(1000);
  }

  SPI.end();
  SPI.begin(EPD_SCK, -1 /* MISO unused */, EPD_MOSI, EPD_CS);
  display.init(115200);

  connectWiFi();

  if (MDNS.begin(MDNS_NAME)) {
    Serial.printf("mDNS started: http://%s.local/refresh\n", MDNS_NAME);
  } else {
    Serial.println("mDNS setup failed (refresh still works by IP)");
  }
  httpServer.begin();

  refresh();
}

void loop() {
  static bool lastPressed = false;
  static unsigned long lastTrigger = 0;

  bool pressed = (digitalRead(BUTTON_PIN) == LOW);
  unsigned long now = millis();

  if (pressed && !lastPressed && (now - lastTrigger) > 300) {
    lastTrigger = now;
    refresh();
  }
  lastPressed = pressed;

  handleClient();

  delay(20);
}
