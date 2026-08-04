#!/usr/bin/env python3
"""Fetch weather from Open-Meteo, render it as an 800x480 HTML report via a
headless browser, convert to a 1-bit packed bitmap, and write
server/screen.bin (for the e-ink display) and server/screen.png (the same
dithered image, for previewing in a browser).

Usage: render_weather.py
Location comes from server/weather_config.py.
HTML layout comes from server/weather_template.html - edit that file's
markup/CSS freely; just keep the {{TOKEN}} placeholders intact.

Requires the venv set up at repo root: source .venv/bin/activate first
(playwright + its downloaded chromium browser, plus Pillow).
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from html import escape

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from eink_convert import W, H, pack_1bit
from PIL import Image, ImageOps
import weather_config as cfg

from playwright.sync_api import sync_playwright

WEATHER_DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Slight rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain",
    71: "Slight snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ hail",
}

DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Not interactive/scrollable (fixed 800x480 e-ink canvas), so instead of
# letting a long list silently clip under overflow:hidden, budget it by
# estimated rendered line count and swap the rest for a "More..." line.
# Measured empirically against server/weather_template.html's .todo box
# (19px items, 280px wide, top-aligned with .location, hr divider at y=285):
# ~8 lines of title+items fit without touching the divider.
TODO_LINE_BUDGET = 8
# ~30-34 chars fit per line at 19px in a 280px box (measured from the
# clamped long-item test case) - used only to guess 1 vs 2 rendered lines
# for budgeting, not for exact wrapping (the CSS clamp still caps at 2).
TODO_CHARS_PER_LINE = 32

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
TEMPLATE_PATH = os.path.join(REPO_ROOT, "server", "weather_template.html")
SCREENSHOT_PATH = os.path.join(REPO_ROOT, "server", "_weather_render.png")
OUT_BIN = os.path.join(REPO_ROOT, "server", "screen.bin")
OUT_PNG = os.path.join(REPO_ROOT, "server", "screen.png")
TODO_PATH = os.path.join(REPO_ROOT, "server", "todo.txt")


def fetch_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={cfg.LATITUDE}&longitude={cfg.LONGITUDE}"
        "&current=temperature_2m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        f"&timezone={urllib.parse.quote(cfg.TIMEZONE)}"
        "&forecast_days=5"
    )
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)


def read_todos():
    """Reads server/todo.txt: one item per line, "[x] " prefix for a
    checked/done item, "[ ] " (or no prefix at all) for unchecked. Blank
    lines and lines starting with "#" are skipped. A missing file just means
    no items - not an error, since an empty to-do list is a valid state."""
    if not os.path.exists(TODO_PATH):
        return []
    items = []
    with open(TODO_PATH) as f:
        for line in f:
            line = line.rstrip("\n").strip()
            if not line or line.startswith("#"):
                continue
            if line[:4] in ("[x] ", "[X] "):
                items.append(("☑", line[4:].strip()))
            elif line[:4] == "[ ] ":
                items.append(("☐", line[4:].strip()))
            else:
                items.append(("☐", line))
    return items


def build_todo_html(items):
    """items: list of (checkbox_glyph, text) tuples. Returns the inner HTML
    for the .todo box's item list, greedily fitting items within
    TODO_LINE_BUDGET (estimated 1 or 2 rendered lines each) and swapping
    whatever doesn't fit for a trailing "More..." line, rather than relying
    on CSS overflow to silently hide it."""
    visible = []
    lines_used = 0
    for i, (box, text) in enumerate(items):
        item_lines = 2 if len(text) > TODO_CHARS_PER_LINE else 1
        reserve_for_more = 1 if i < len(items) - 1 else 0
        if lines_used + item_lines + reserve_for_more > TODO_LINE_BUDGET:
            visible.append((None, "More…"))
            break
        visible.append((box, text))
        lines_used += item_lines

    lines = []
    for box, text in visible:
        if box is None:
            lines.append(f'<div class="todo-item todo-more">{escape(text)}</div>')
        elif box == "☑":
            lines.append(f'<div class="todo-item todo-done">{box} {escape(text)}</div>')
        else:
            lines.append(f'<div class="todo-item">{box} {escape(text)}</div>')
    return "\n      ".join(lines)


def build_tokens(data):
    current_temp = round(data["current"]["temperature_2m"])
    current_code = data["current"]["weather_code"]
    current_desc = WEATHER_DESCRIPTIONS.get(current_code, "Unknown")

    daily = data["daily"]
    tokens = {
        "LOCATION": f"{cfg.LOCATION_NAME} {cfg.POSTAL_CODE}",
        "UPDATED": datetime.now().strftime("%a %H:%M"),
        "CURRENT_TEMP": str(current_temp),
        "CURRENT_DESC": current_desc,
        "TODAY_HI": str(round(daily["temperature_2m_max"][0])),
        "TODAY_LO": str(round(daily["temperature_2m_min"][0])),
    }

    for i in range(1, 5):
        date = datetime.fromisoformat(daily["time"][i])
        tokens[f"DAY{i}_NAME"] = DAY_ABBR[date.weekday()]
        tokens[f"DAY{i}_HI"] = str(round(daily["temperature_2m_max"][i]))
        tokens[f"DAY{i}_LO"] = str(round(daily["temperature_2m_min"][i]))

    tokens["TODO_ITEMS"] = build_todo_html(read_todos())

    return tokens


def fill_template(tokens):
    with open(TEMPLATE_PATH) as f:
        html = f.read()
    for key, value in tokens.items():
        html = html.replace("{{" + key + "}}", value)
    return html


# Render at N times the target resolution, then downscale. At 1x, hard
# thresholding to 1-bit turns thin/sub-pixel-positioned letter strokes into
# a coin flip - some vanish, some survive stringy. Supersampling gives
# anti-aliasing enough room to represent partial stroke coverage as real
# gray levels, so the downscale (and later threshold) is far more
# consistent across strokes and font sizes.
SUPERSAMPLE = 3


def render_html_to_png(html, out_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": W, "height": H}, device_scale_factor=SUPERSAMPLE
        )
        page.set_content(html)
        page.screenshot(path=out_path)
        browser.close()


def render() -> bytes:
    """Fetch weather, render it, return the packed 1-bit bitmap bytes.
    Also writes them to OUT_BIN as a side effect (debugging/fallback cache)."""
    data = fetch_weather()
    tokens = build_tokens(data)
    html = fill_template(tokens)
    render_html_to_png(html, SCREENSHOT_PATH)

    img = Image.open(SCREENSHOT_PATH).convert("L")
    # Downscale the supersampled render before anything else, so the
    # resampling filter is what decides each pixel's gray level (real
    # anti-aliasing), not the browser's 1x rendering.
    img = img.resize((W, H), Image.LANCZOS)
    # No dithering: this is text/lines, not a photo, so there's no gradient
    # to approximate with a black/white speckle pattern - dithering the
    # anti-aliased edges of small text just adds noise. A hard threshold
    # reads cleaner now that the downscale has already smoothed the edges.
    # (Contrast with tools/eink_convert.py, which dithers on purpose for
    # photos.)
    img = ImageOps.autocontrast(img, cutoff=1).convert("1", dither=Image.NONE)
    img.save(OUT_PNG)
    packed = pack_1bit(img)
    with open(OUT_BIN, "wb") as f:
        f.write(packed)
    return packed


def main():
    print("fetching weather...")
    print("rendering...")
    packed = render()
    print(f"wrote {OUT_BIN}: {len(packed)} bytes")

if __name__ == "__main__":
    main()
