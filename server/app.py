#!/usr/bin/env python3
"""Serves a freshly-rendered weather bitmap on every request to /screen.bin,
and the same image as a viewable PNG on /screen.png (for previewing template
changes in a browser during development).

Run from repo root with the venv active:
    source .venv/bin/activate && python3 server/app.py

On render failure, falls back to the last successfully-written
server/screen.bin / server/screen.png (from render_weather.render()'s
side-effect writes) rather than erroring out, so a transient
Open-Meteo/network hiccup doesn't leave the display blank.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import render_weather

PORT = 8000
FALLBACK_BIN = os.path.join(os.path.dirname(__file__), "screen.bin")
FALLBACK_PNG = os.path.join(os.path.dirname(__file__), "screen.png")

ROUTES = {
    "/screen.bin": (FALLBACK_BIN, "application/octet-stream"),
    "/screen.png": (FALLBACK_PNG, "image/png"),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = ROUTES.get(self.path)
        if route is None:
            self.send_response(404)
            self.end_headers()
            return
        fallback_path, content_type = route

        try:
            print("rendering fresh weather report...")
            render_weather.render()
        except Exception as e:
            print(f"render failed ({e}), falling back to cached {os.path.basename(fallback_path)}")

        if not os.path.exists(fallback_path):
            self.send_response(500)
            self.end_headers()
            return
        with open(fallback_path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}")


if __name__ == "__main__":
    print(f"serving on :{PORT} - /screen.bin (device) and /screen.png (browser preview), rendering fresh on every GET")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
