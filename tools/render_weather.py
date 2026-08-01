#!/usr/bin/env python3
"""Fetch weather from Open-Meteo, render it as an 800x480 HTML report via a
headless browser, convert to a 1-bit packed bitmap, and write server/screen.bin.

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

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
TEMPLATE_PATH = os.path.join(REPO_ROOT, "server", "weather_template.html")
SCREENSHOT_PATH = os.path.join(REPO_ROOT, "server", "_weather_render.png")
OUT_BIN = os.path.join(REPO_ROOT, "server", "screen.bin")


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

    return tokens


def fill_template(tokens):
    with open(TEMPLATE_PATH) as f:
        html = f.read()
    for key, value in tokens.items():
        html = html.replace("{{" + key + "}}", value)
    return html


def render_html_to_png(html, out_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
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
    img = ImageOps.autocontrast(img, cutoff=1).convert("1")
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
