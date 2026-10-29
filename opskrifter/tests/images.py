"""Testbilleder lavet med Pillow."""

import io

from PIL import Image


def jpeg(width: int = 40, height: int = 30, color: str = "orange", orientation: int | None = None) -> bytes:
    image = Image.new("RGB", (width, height), color)
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    out = io.BytesIO()
    image.save(out, "JPEG", exif=exif)
    return out.getvalue()


def size_of(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size
