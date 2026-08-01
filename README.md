# eink

A Waveshare 7.5" e-Paper display (V2, 800x480, black/white) driven by a
Waveshare ESP32 Driver Board. Started as a "just show a static image" test,
grew into: LAN-fetched images with a physical button to trigger a refresh,
and a server that renders a live weather report (HTML/CSS -> headless
Chromium screenshot -> 1-bit dithered bitmap) on demand.

For the blow-by-blow build history (including a full day chasing a bug that
turned out to be a non-default SPI pin mapping), see [LOG.md](LOG.md).

## Hardware

- Waveshare 7.5" e-Paper V2 panel (800x480, B/W). Check the sticker on the
  back of the panel - "V2" corresponds to the `GxEPD2_750_T7` GxEPD2 class.
- Waveshare "e-Paper ESP32 Driver Board Rev 3" (ESP32-WROOM-32 + panel
  connector + USB-serial, all on one board).

Pin mapping (fixed by the driver board's wiring, from Waveshare's own
`DEV_Config.h`):

| Signal | GPIO |
|--------|------|
| CS     | 15   |
| DC     | 27   |
| RST    | 26   |
| BUSY   | 25   |
| SCK    | 13   |
| MOSI   | 14   |
| BOOT button (used as the refresh trigger) | 0 |

**Important gotcha:** GxEPD2's constructor only takes CS/DC/RST/BUSY. It
does *not* take SCK/MOSI, so unless you explicitly call
`SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS)` before `display.init()`, the
ESP32 silently uses its default VSPI pins (18/23) instead - which aren't
wired to anything on this board. Every sketch below already does this
correctly; keep it in mind if you write a new one.

## Firmware (Arduino sketches, in `firmware/`)

All sketches: Arduino IDE, board = **ESP32 Dev Module**, library = **GxEPD2**
(by Jean-Marc Zingg, via Library Manager).

- **`eink_black_test/`** - no image, just fills the screen black then white.
  Good first upload to confirm wiring/SPI before touching anything else.
- **`eink_static_image/`** - renders `image_data.h`, a C byte array baked in
  at compile time. Regenerate that header with `tools/img_to_header.py`
  (see below) before flashing.
- **`eink_lan_display/`** - connects to WiFi, and on every BOOT-button press
  fetches a raw 1-bit bitmap over HTTP and renders it. Needs
  `config.h` (copy from `config.h.dist` and fill in your WiFi credentials
  and the image URL - `config.h` is gitignored since it holds your WiFi
  password in plaintext).
- **`eink_deep_sleep_test/`** - does nothing but immediately
  `esp_deep_sleep_start()`, waking every 60s or on BOOT press. For measuring
  the board's real sleep-current draw with a multimeter before committing to
  a full scheduled-wake architecture.

## Server / tools (Python, in `tools/` and `server/`)

One-time setup:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install Pillow playwright
playwright install chromium   # downloads its own browser, ~300MB
```

(Skip Playwright/Chromium if you only need the image-conversion tools, not
the weather renderer.)

### `tools/make_testcard.py`

Generates the 800x480 "EINK OK" test pattern used by `eink_black_test` /
`eink_static_image` by default. No arguments:

```sh
python3 tools/make_testcard.py
# -> writes images/testcard.png
```

### `tools/img_to_header.py`

Converts any image into a C byte array for `eink_static_image/image_data.h`.
Center-crops to 800x480 preserving aspect ratio, autocontrasts, and applies
Floyd-Steinberg dithering.

```sh
python3 tools/img_to_header.py <input_image> <output.h> [array_name] [--zoom=1.0] [--contrast=1.0]

# Examples:
python3 tools/img_to_header.py images/testcard.png firmware/eink_static_image/image_data.h
python3 tools/img_to_header.py photo.jpg firmware/eink_static_image/image_data.h image_data --zoom=0.7 --contrast=1.2
```

- `--zoom` < 1.0 shows more of the original image, letterboxed in white,
  instead of cropping tight to fill the frame (default `1.0` = fill edge to
  edge, cropping the rest).
- `--contrast` > 1.0 punches up contrast before dithering - useful since
  flat/soft photos can look muddy at 1-bit (default `1.0` = autocontrast only).

### `tools/img_to_bin.py`

Same conversion pipeline as `img_to_header.py`, but writes a raw 48000-byte
binary instead of a C header - meant to be served over HTTP for
`eink_lan_display` to fetch directly.

```sh
python3 tools/img_to_bin.py <input_image> <output.bin> [--zoom=1.0] [--contrast=1.0]

# Example:
python3 tools/img_to_bin.py photo.jpg server/screen.bin --zoom=0.7 --contrast=1.2
```

### `server/weather_config.py`

Copy from `weather_config.py.dist` and fill in your location (also
gitignored - it's personal-ish data, not a secret, but kept out of the repo
regardless):

```sh
cp server/weather_config.py.dist server/weather_config.py
```

Look up lat/lon for a postal code with, e.g.:

```sh
curl https://api.zippopotam.us/de/13125
```

### `tools/render_weather.py`

One-shot: fetches current weather + forecast from Open-Meteo (no API key
needed), fills `server/weather_template.html` (plain HTML/CSS - edit that
file directly to change the layout; its `{{TOKEN}}` placeholders get
substituted by simple string replacement, not a templating engine, so
regular CSS curly braces are safe to use), screenshots it at 800x480 via
headless Chromium, dithers, and writes `server/screen.bin`.

```sh
source .venv/bin/activate
python3 tools/render_weather.py
```

### `server/app.py`

Serves `/screen.bin` dynamically - renders a fresh weather report on *every*
request (not a cached/static file), falling back to the last successfully
rendered `server/screen.bin` if a render fails (e.g. a transient Open-Meteo
hiccup), so a network blip doesn't leave the display blank.

```sh
source .venv/bin/activate
python3 server/app.py
# serving on :8000, GET /screen.bin renders fresh each time (~1-2s)
```

Point `eink_lan_display`'s `config.h` `IMAGE_URL` at
`http://<this-machine's-LAN-IP>:8000/screen.bin`.

### `tools/eink_convert.py`

Shared conversion logic (crop/contrast/dither/pack) used by both
`img_to_header.py` and `img_to_bin.py`. Not a CLI - import
`convert_to_1bit()` / `pack_1bit()` if you're scripting something new.
