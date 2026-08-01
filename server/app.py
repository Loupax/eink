#!/usr/bin/env python3
"""Serves a freshly-rendered weather bitmap on every request to /screen.bin.

Run from repo root with the venv active:
    source .venv/bin/activate && python3 server/app.py

On render failure, falls back to the last successfully-written server/screen.bin
(from render_weather.render()'s side-effect write) rather than erroring out,
so a transient Open-Meteo/network hiccup doesn't leave the display blank.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import render_weather

PORT = 8000
FALLBACK_BIN = os.path.join(os.path.dirname(__file__), "screen.bin")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/screen.bin":
            self.send_response(404)
            self.end_headers()
            return

        try:
            print("rendering fresh weather report...")
            data = render_weather.render()
        except Exception as e:
            print(f"render failed ({e}), falling back to cached screen.bin")
            if not os.path.exists(FALLBACK_BIN):
                self.send_response(500)
                self.end_headers()
                return
            with open(FALLBACK_BIN, "rb") as f:
                data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}")


if __name__ == "__main__":
    print(f"serving on :{PORT}, rendering fresh on every GET /screen.bin")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
