"""Shared image -> 1-bit packed bitmap conversion for the 7.5" e-Paper panel (800x480).

GxEPD2 convention: bit=1 is white, bit=0 is black, MSB first, rows padded to a byte.
"""
from PIL import Image, ImageOps, ImageEnhance

W, H = 800, 480


def convert_to_1bit(src_path, zoom=1.0, contrast=1.0):
    img = Image.open(src_path).convert("L")
    img = ImageOps.exif_transpose(img)

    if zoom >= 1.0:
        img = ImageOps.fit(img, (W, H), method=Image.LANCZOS, centering=(0.5, 0.5))
    else:
        src_w, src_h = img.size
        scale = max(W / src_w, H / src_h) * zoom
        new_w, new_h = round(src_w * scale), round(src_h * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("L", (W, H), 255)
        canvas.paste(resized, ((W - new_w) // 2, (H - new_h) // 2))
        img = canvas

    img = ImageOps.autocontrast(img, cutoff=1)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    return img.convert("1")  # Floyd-Steinberg dithering (Pillow default)


def pack_1bit(img):
    px = img.load()
    row_bytes = (W + 7) // 8
    data = bytearray(row_bytes * H)

    for y in range(H):
        for x in range(W):
            byte_i = y * row_bytes + (x // 8)
            bit = 7 - (x % 8)
            if px[x, y] == 0:  # black pixel -> clear bit
                data[byte_i] &= ~(1 << bit) & 0xFF
            else:
                data[byte_i] |= (1 << bit)
    return bytes(data)


def parse_common_args(argv):
    opts = [a for a in argv if a.startswith("--")]
    args = [a for a in argv if not a.startswith("--")]
    zoom_args = [a for a in opts if a.startswith("--zoom")]
    zoom = float(zoom_args[0].split("=", 1)[1]) if zoom_args else 1.0
    contrast_args = [a for a in opts if a.startswith("--contrast")]
    contrast = float(contrast_args[0].split("=", 1)[1]) if contrast_args else 1.0
    return args, zoom, contrast
