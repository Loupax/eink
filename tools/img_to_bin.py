#!/usr/bin/env python3
"""Convert an image to a raw 1-bit packed bitmap file (800x480, 48000 bytes),
for serving over HTTP and rendering directly on the ESP32.

Usage: img_to_bin.py <input_image> <output.bin> [--zoom=1.0] [--contrast=1.0]
Same cropping/contrast/dithering behavior as img_to_header.py.
"""
import sys
from eink_convert import convert_to_1bit, pack_1bit, parse_common_args


def main():
    args, zoom, contrast = parse_common_args(sys.argv[1:])
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    src_path = args[0]
    out_path = args[1]

    img = convert_to_1bit(src_path, zoom=zoom, contrast=contrast)
    data = pack_1bit(img)

    with open(out_path, "wb") as f:
        f.write(data)

    print(f"wrote {out_path}: {len(data)} bytes")

if __name__ == "__main__":
    main()
