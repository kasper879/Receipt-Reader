"""Billeder fra telefonen: drejes efter EXIF og skaleres ned, så biblioteket ikke bliver tungt."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

DISH_PHOTO_SIZE = 1600
"""Længste side på et retbillede i pixels."""

ORIGINAL_IMAGE_SIZE = 2400
"""Længste side på et originalbillede. Større, så små og håndskrevne detaljer kan læses."""


class InvalidImage(Exception):
    """Filen er ikke et billede, der kan læses."""


def crop(data: bytes, box: tuple[float, float, float, float], longest_side: int) -> bytes:
    """Et udsnit af billedet som JPEG. `box` er venstre, top, højre og bund som brøkdele af bredde og højde."""
    try:
        with Image.open(io.BytesIO(data)) as original:
            image = ImageOps.exif_transpose(original)
            left, top, right, bottom = box
            width, height = image.size
            cropped = image.crop((round(left * width), round(top * height), round(right * width), round(bottom * height)))
            cropped.thumbnail((longest_side, longest_side))
            out = io.BytesIO()
            cropped.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImage("Billedet kunne ikke beskæres.") from error
    return out.getvalue()


def prepare(data: bytes, longest_side: int) -> bytes:
    """Et billede som JPEG, drejet efter EXIF og med den længste side højst `longest_side`."""
    try:
        with Image.open(io.BytesIO(data)) as original:
            image = ImageOps.exif_transpose(original)
            image.thumbnail((longest_side, longest_side))
            out = io.BytesIO()
            image.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImage("Billedet kunne ikke læses. Brug et JPEG- eller PNG-billede.") from error
    return out.getvalue()
