#!/usr/bin/env python3
"""Convert an image to a 1-bit packed C byte array for GxEPD2 (MSB first, 0=black).

Usage: img_to_header.py <input_image> <output.h> [array_name] [--zoom=1.0] [--contrast=1.0]
Center-crops to 800x480 (preserving aspect ratio, no stretching), boosts
contrast, applies Floyd-Steinberg dithering, writes PROGMEM byte array.
--zoom <1.0 shows more of the original image (letterboxed in white);
--zoom 1.0 (default) fills the frame edge-to-edge, cropping the rest.
--contrast >1.0 increases contrast before dithering (default 1.0 = autocontrast only).
"""
import sys
from eink_convert import W, H, convert_to_1bit, pack_1bit, parse_common_args


def main():
    args, zoom, contrast = parse_common_args(sys.argv[1:])
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    src_path = args[0]
    out_path = args[1]
    name = args[2] if len(args) > 2 else "image_data"

    img = convert_to_1bit(src_path, zoom=zoom, contrast=contrast)
    data = pack_1bit(img)

    with open(out_path, "w") as f:
        f.write(f"// Auto-generated from {src_path} ({W}x{H}, 1bpp)\n")
        f.write("#pragma once\n#include <pgmspace.h>\n\n")
        f.write(f"const uint16_t {name}_width = {W};\n")
        f.write(f"const uint16_t {name}_height = {H};\n")
        f.write(f"const uint8_t {name}[] PROGMEM = {{\n")
        row_bytes = (W + 7) // 8
        for i in range(0, len(data), row_bytes):
            row = data[i:i + row_bytes]
            f.write("  " + ",".join(f"0x{b:02X}" for b in row) + ",\n")
        f.write("};\n")

    print(f"wrote {out_path}: {len(data)} bytes ({name})")

if __name__ == "__main__":
    main()
