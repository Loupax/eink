# Project Log — eink static image display

Waveshare 7.5" e-Paper (800x480, B&W) + Waveshare ESP32 Driver Board, Arduino IDE.

## 2026-08-01

- Set up project: generated `images/testcard.png` test pattern, `tools/img_to_header.py`
  converter, `firmware/eink_static_image/` sketch (GxEPD2-based, draws static image once
  then sleeps). Pins assume Waveshare ESP32 Driver Board fixed header (CS15/DC27/RST26/BUSY25).
- Checked USB: board detected as `/dev/ttyACM0` (CH340-family USB-serial, vendor 1a86).
- Found serial port owned by group `uucp`, user not in it. Ran `sudo usermod -aG uucp $USER`
  (user's own terminal, needed password). User logged out/in to pick up group membership.
- User installing Arduino IDE.
- Board selection: **ESP32 Dev Module** (esp32 boards package by Espressif Systems).
- 12:35 — User installing esp32 board package in Arduino IDE. Next: install GxEPD2 library,
  open sketch, select port `/dev/ttyACM0`, upload.
- First upload succeeded. Screen stayed blank. Ruled out, in order: FPC ribbon
  orientation/seating, panel power switch, A/B switch position, USB cable/port
  (board was fully power-cycling under load — turned out to just be manual EN
  presses, not a real brownout loop), the extra "e-Paper Adapter" + extension
  cable (bypassed by plugging panel directly into driver board), and controller
  variant (tried both `GxEPD2_750` and `GxEPD2_750_T7`; panel's back sticker
  confirmed "V2" = T7 is correct). Nothing changed - screen never flickered even
  once across every attempt.
- Root cause found by diffing against Waveshare's own official example repo
  (github.com/jasompi/waveshare-epaper-esp32, mirrored to
  ~/src/waveshare-epaper-esp32): their `DEV_Config.h` wires SPI clock/data to
  GPIO13/14, non-default pins. GxEPD2's constructor only takes CS/DC/RST/BUSY -
  it never gets told about SCK/MOSI, so it silently uses the ESP32's default
  VSPI pins (18/23), which aren't connected to anything on this board. CS, DC,
  RST, BUSY are explicit digitalWrite/digitalRead pins so they always "worked"
  (explains why every test ran to completion with no hang) - but actual pixel
  data never physically reached the panel. Every hardware check that day was a
  reasonable one to rule out first, but the bug was software the whole time.
- Fix: `SPI.end(); SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS);` before
  `display.init()`, using SCK=13, MOSI=14. Applied to both
  `eink_black_test.ino` and `eink_static_image.ino`. Also switched both
  sketches to the `GxEPD2_750_T7` (V2) controller class per the panel's sticker.
- 20:23 — Fix applied, not yet retested on hardware. Next: re-upload
  `eink_black_test.ino`, confirm the panel actually flashes black/white.
- Confirmed fixed: black-fill test now flashes black then white on the panel.
  SPI pin remap was the actual root cause. Screen confirmed working with
  testcard.png.
- Moved reference clone of Waveshare's official example repo to
  ~/src/waveshare-epaper-esp32 (was in /tmp).
- Upgraded `tools/img_to_header.py`: proper aspect-preserving crop
  (ImageOps.fit, no more stretch-to-fit distortion), autocontrast, and real
  Floyd-Steinberg dithering (previous version pre-thresholded before
  convert("1"), which defeated dithering entirely). Added `--zoom` (values
  <1.0 letterbox on white instead of cropping tight) and `--contrast` flags.
- Picked a personal photo (~/Downloads/BuH9Ud87.jpg, most recent file in
  Downloads at the time), iterated on crop/contrast with the user via preview
  PNGs (xdg-open) rather than flashing blind each time. Settled on
  `--zoom=0.7 --contrast=1.2`. Written into
  firmware/eink_static_image/image_data.h. Reflashed and confirmed working
  on hardware - "hello world" phase complete.

## Phase 2: LAN-driven display, button-triggered refresh

- Goal: ESP32 connects to WiFi, fetches an image from a file on the LAN, and
  redraws the panel on BOOT-button press. Local python http.server for now;
  proper service later.
- Decisions: pre-converted raw 1bpp bitmap over HTTP (not on-device JPEG
  decode) for simplicity; BOOT button (GPIO0) as trigger, no extra wiring.
- Refactored image conversion into `tools/eink_convert.py` (shared by
  `img_to_header.py` and new `img_to_bin.py`, which emits a raw .bin instead
  of a C header, meant to be served directly over HTTP).
- New sketch: `firmware/eink_lan_display/`. `config.h` holds WIFI_SSID,
  WIFI_PASSWORD, IMAGE_URL (pulled WiFi password from `nmcli -s -g
  802-11-wireless-security.psk connection show <SSID>` on this machine).
  Server IP corrected from user's initial guess (192.168.1.50, wrong subnet)
  to this machine's actual LAN IP (192.168.2.38).
- `server/screen.bin` generated from the same BuH9Ud87.jpg photo
  (--zoom=0.7 --contrast=1.2). `python3 -m http.server 8000` running in
  `server/` (background), verified reachable at
  http://192.168.2.38:8000/screen.bin (200, 48000 bytes).
- Flashed and confirmed working: server log showed a real GET from the
  ESP32's own IP (192.168.2.147) after a BOOT press, distinct from manual
  curl checks from this machine. Phase 2 complete.
- Swapped both `server/screen.bin` and `firmware/eink_static_image/image_data.h`
  back to the "EINK OK" test card (were showing a personal photo) - user
  wanted the repo's example artifacts to not carry personal photos.
- Added `.gitignore` ahead of ever running `git init`: excludes
  `firmware/*/config.h` (has the WiFi password in plaintext), python/Arduino
  build junk.

## Phase 3: weather report instead of a static image

- Considered existing prior art first: esp32-weather-epd (mature, on-device
  rendering, no server, but OpenWeatherMap not Open-Meteo) and TRMNL/BYOS
  (matches our server-renders/device-fetches architecture closely, but a
  whole platform). User chose to keep building our own minimal version.
- Location: Berlin, postal code 13125 -> geocoded via api.zippopotam.us to
  lat 52.5167 / lon 13.4 (server/weather_config.py). Refresh: manual for now,
  no cron/timer.
- Weather data: Open-Meteo (api.open-meteo.com), no API key needed.
- Rendering approach: HTML+CSS -> headless Chromium screenshot (Playwright)
  -> same 1-bit dither/pack pipeline as photos -> server/screen.bin. Confirmed
  with the user that the ESP32 itself cannot render HTML (nowhere near enough
  RAM/flash for a browser engine) - it only ever fetches/blits raw pixel
  bytes, same as before.
- Set up `.venv` at repo root (Playwright not available system-wide; Arch is
  an unsupported OS for Playwright's dep installer, so used
  `playwright install chromium` without `--with-deps` - worked fine without
  needing sudo/system packages). Added Pillow to the venv too.
- User wants to hand-edit the HTML later, so the report layout lives in a
  real standalone file, `server/weather_template.html` (plain HTML/CSS, no
  Python string-escaping headaches), with `{{TOKEN}}` placeholders filled by
  simple string replacement in `tools/render_weather.py` (avoided
  str.format() deliberately - CSS's `{ }` would collide with format-string
  syntax).
- `tools/render_weather.py`: fetches Open-Meteo current + 5-day forecast,
  fills the template, screenshots at 800x480 via Playwright, dithers, writes
  server/screen.bin. Ran successfully end to end - real data (19C, clear sky,
  4-day forecast) confirmed via preview PNG. Server already serving the new
  file (confirmed via curl). Not yet reflashed/viewed on the physical panel
  since this doesn't require a firmware change - eink_lan_display.ino is
  unchanged, it just fetches whatever's at screen.bin.
- To regenerate: `source .venv/bin/activate && python3 tools/render_weather.py`,
  then press BOOT on the device.
- Confirmed working on hardware: real ESP32 GET logged, screen updated.

## Phase 4: render on-demand instead of a pre-generated file

- User asked if the server could render fresh on every request rather than
  needing the script run manually beforehand. Chose "always render fresh"
  over a TTL cache (simpler; a couple seconds of latency per button press is
  fine for a single-user local setup).
- Refactored `tools/render_weather.py`: pulled the fetch/render/convert
  sequence into a `render() -> bytes` function (still writes screen.bin as a
  side-effect/fallback cache), `main()` is now a thin CLI wrapper around it.
- New `server/app.py`: stdlib `http.server` (no Flask needed) that calls
  `render_weather.render()` on every GET /screen.bin and streams the bytes
  back; falls back to the last cached screen.bin on render failure (e.g.
  Open-Meteo hiccup) rather than erroring out to a blank display.
- Gotcha hit: killed the old static server with `pkill -f "http.server 8000"`
  chained in the *same* background command as starting the new server - the
  pattern matched the launching shell's own command-line text (which
  contained that string as part of the pkill invocation itself) and killed
  it immediately, no error output. Fixed by running the kill and the new
  server start as fully separate commands.
- Verified: GET /screen.bin now takes ~1.4s (real render happening each
  time, not a static file - would be milliseconds otherwise) and returns
  fresh 48000 bytes. `server/app.py` running in background on :8000.

## Phase 5 (paused, pending measurement): deep sleep for battery life

- Goal: board mostly "off", wakes 4x/day on a timer + on button press,
  refreshes, sleeps again. User wants to confirm actual sleep current draw
  first, before adding that complexity - board-level quiescent current
  (USB-serial chip, power LED, etc.) can dominate over the bare ESP32's
  deep-sleep spec, so worth measuring rather than assuming.
- Wrote `firmware/eink_deep_sleep_test/` - minimal sketch, does nothing but
  esp_deep_sleep_start() immediately, wakes every 60s (repeatable
  measurement without hitting reset) and on BOOT press. User to flash this
  and measure current in series with USB VBUS using a multimeter.
- Not yet implemented: the actual scheduled-wake + button-wake production
  firmware. Waiting on the measurement result before deciding if it's worth it.

## Phase 6: production deployment, to-do list, always-on refresh (2026-08-02)

- User doesn't want to run the server on their laptop long-term - has a mini
  PC (`brick.local`, Arch + systemd + nginx, ssh reachable) already hosting
  a couple other self-hosted things (`ollama.local`, `excalidraw.local` via
  an existing `avahi-alias@.service` systemd template). Followed that same
  convention: `weather.local` via `avahi-alias@weather.service`, nginx
  reverse-proxying to `app.py` on :8000, `eink-weather.service` running as
  the `loupax` user (not root - matches the existing native-service
  pattern, Docker-based services on that box use root instead).
- Wrote `server/deploy/deploy.sh`: rsyncs `tools/` + `server/` to
  `~/src/eink-weather` on brick, rebuilds the venv, and reports whether a
  service restart is needed based on whether any `.py` file actually
  changed (HTML/txt files are read fresh from disk every request, no
  restart needed for those) - never runs the restart itself, since sudo
  needs a real TTY for the password prompt and this session has none.
  Neither this machine nor brick had `rsync` installed; both needed
  `pacman -S rsync`.
- Mid-session, a routine `sudo pacman -Syu` on brick (to install `rsync`)
  broke `sudo` itself - `pam_unix` started reporting "could not identify
  password" for every attempt, `su -` with the *root* password still
  worked. Root cause: `/etc/shadow`'s mtime lined up to the same second the
  `shadow` package's upgrade hook ran, strongly suggesting that hook
  rewrote it. Fixed via `su -` + `passwd loupax`. Lesson: a big rolling-release
  upgrade can silently break auth; if sudo starts rejecting a correct
  password right after one, suspect the upgrade before the user's typing.
- Added `server/app.py` `/screen.png` endpoint (same render as PNG, for
  previewing template changes in a browser instead of flashing the
  physical device each time) and `tools/render_weather.py` writes
  `server/screen.png` alongside `screen.bin`.
- Added a to-do list next to the temperature. Iterated the layout live
  against a local server + browser preview loop rather than guessing:
  - First cut used `display:flex` for the temp/todo row - a long item
    wrapping to multiple lines pushed the whole rest of the page (including
    the day forecast) down, off the bottom of the fixed 800x480 canvas
    entirely (screenshot is a fixed viewport, not a scrollable page - it just
    silently disappears). Fixed by taking the to-do box out of document flow
    (`position: absolute`, fixed `max-height` + `overflow: hidden`) so it can
    never push siblings around, and clamping each item to 2 lines
    (`-webkit-line-clamp`) with an ellipsis instead of wrapping indefinitely.
  - `position: absolute`'s containing block is the nearest positioned
    ancestor's *padding* box, which ignores that ancestor's own padding -
    `top`/`right` had to restate `.wrap`'s 30px/40px padding explicitly to
    actually line up with the rest of the content instead of sitting flush
    against the canvas edge.
  - Item count that fits varies (2-line items cost more space than 1-line
    ones), so truncation is budgeted by *estimated rendered line count*
    (`TODO_LINE_BUDGET`, `TODO_CHARS_PER_LINE` in `render_weather.py`), not a
    fixed item cap - swaps whatever doesn't fit for a trailing "More..." line
    rather than ever letting `overflow: hidden` silently eat a real item.
  - Data source: discussed Google Tasks (rejected - OAuth-only, tokens expire
    hourly, no simple static-token option) vs. Todoist (real static API
    token) vs. a published-to-web Google Sheet vs. a local file. User picked
    the local file for now (`server/todo.txt`, gitignored, `.dist` template
    committed) - one item per line, `[x] `/`[ ] ` prefix for checked state,
    `#` comments. Deliberately excluded from `deploy.sh`'s rsync (unlike
    `weather_config.py`) since it's edited far more often and directly on
    whichever machine is running the server, not pushed from the laptop.
  - Done items render with `text-decoration: line-through` (`.todo-done`).
- Rendering quality pass, on user's report of speckled/thin small text on
  the physical panel:
  - Pillow's `.convert("1")` dithers (Floyd-Steinberg) by default - fine for
    photos (`tools/eink_convert.py` keeps it there on purpose), wrong for
    this template's text/lines, where it just added speckle noise to
    anti-aliased font edges. Disabled with `dither=Image.NONE`.
  - That alone made small-text strokes look *thinner*, not better - a
    single-resolution (1x) render being hard-thresholded means a thin
    stroke's anti-aliased edge is essentially a coin flip. Fixed properly by
    rendering at 3x (`device_scale_factor` in Playwright) and downscaling
    with Lanczos before the threshold, so anti-aliasing has real gray levels
    to work with. Supersampling can't add resolution the final 800x480
    output doesn't have, though - the smallest text (16-18px) was still a
    genuine resolution floor, fixed by bumping those specific font-sizes and
    weights (`.updated`, `.todo-item`, `.day .dlo` to 600 weight) rather than
    chasing it further in the rendering pipeline.
  - Discussed (no action) whether a dedicated "e-ink font" exists - concluded
    no meaningful open ecosystem for that; Kindle's Bookerly/Caecilia are
    proprietary and tuned for a different pipeline (on-device hinted
    rasterization + grayscale dithering) than this project's
    browser-render-then-global-threshold approach anyway.
- Added a way to trigger a refresh without physically pressing the BOOT
  button: `eink_lan_display.ino` now runs `ESPmDNS` (`eink.local`) and a
  minimal hand-rolled `WiFiServer` HTTP listener - `GET /refresh` calls the
  same `refresh()` the button does (faster than a full restart, WiFi's
  already up). No auth - fine for a trusted home LAN, not something to
  port-forward.
- Learned the hard way that a USB power bank isn't a reliable long-term
  power source for this board: after unplugging from the laptop, the ESP32
  went unreachable a few tens of seconds in - the power bank's own
  auto-shutoff (common behavior when it sees current draw below its
  "something's still connected" threshold) had cut power. Switched to a
  plain 5V USB wall charger instead (safe even from USB-C PD/fast-charge
  bricks - they only step up voltage if the connected device negotiates for
  it, and this board doesn't).
- Added `eink-refresh.path` + `eink-refresh.service` (systemd path unit +
  oneshot service) on brick: watches `todo.txt` for changes
  (`PathChanged`), calls `http://eink.local/refresh` on every edit. Hit two
  more brick-specific gaps getting there, neither related to the ESP32
  itself:
  - brick could resolve mDNS names via `avahi-resolve` (talks to
    `avahi-daemon` directly) but *not* via `curl`/`getent` - its
    `/etc/nsswitch.conf` routed `hosts:` through `resolve`
    (systemd-resolved), which wasn't even running. Fixed by installing
    `nss-mdns` and adding `mdns4_minimal [NOTFOUND=return]` to the
    `nsswitch.conf` hosts line, so glibc's resolver talks to the
    already-running avahi-daemon instead (same backend `avahi-resolve` uses).
  - The to-do strikethrough CSS wasn't showing on the real device despite
    correct markup/CSS on disk (verified directly). Root cause was the
    *running* `eink-weather.service` process predating both this change and
    the supersampling change - Python only imports a module once at process
    start, so the deployed files were right but the live process was still
    running old code from its last actual restart. `systemctl restart`
    picked up both fixes at once. Second, unrelated gap found along the way:
    brick didn't have `ttf-liberation` installed at all, so it had been
    silently rendering the whole template in a substituted font (FreeSans)
    the entire time - every rendering-quality change this session had only
    ever been validated against the *local* dev server's font, not brick's.
    Installing `ttf-liberation` fixed that retroactively too.
- Added `eink-refresh.timer` (2026-08-04): fires the same
  `eink-refresh.service` hourly regardless of `todo.txt` edits, since
  weather changes on its own. Picked systemd timer over cron - brick's
  already all-systemd for this project (avahi-alias@, eink-weather.service,
  eink-refresh.path), and it just targets the existing `.service` by name,
  no new script needed.
