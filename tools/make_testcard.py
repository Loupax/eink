#!/usr/bin/env python3
"""Generate a simple 1-bit test pattern sized for the 7.5" Waveshare panel (800x480)."""
from PIL import Image, ImageDraw, ImageFont

W, H = 800, 480

img = Image.new("1", (W, H), 1)  # 1 = white
d = ImageDraw.Draw(img)

# border
d.rectangle([0, 0, W - 1, H - 1], outline=0, width=4)

# diagonal cross to confirm orientation (top-left origin)
d.line([0, 0, W, H], fill=0, width=2)
d.line([0, H, W, 0], fill=0, width=2)

# corner markers
d.rectangle([10, 10, 60, 60], fill=0)          # top-left solid
d.ellipse([W - 60, 10, W - 10, 60], fill=0)    # top-right circle
d.rectangle([10, H - 60, 60, H - 10], outline=0, width=4)  # bottom-left ring

# center text
try:
    font = ImageFont.load_default(size=48)
except TypeError:
    font = ImageFont.load_default()
text = "EINK OK"
bbox = d.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
d.text(((W - tw) / 2, (H - th) / 2 - 10), text, fill=0, font=font)

img.save("/home/loupax/src/eink/images/testcard.png")
print("wrote images/testcard.png", img.size, img.mode)
