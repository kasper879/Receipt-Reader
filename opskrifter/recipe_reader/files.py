"""Skrivning af filer i biblioteksmappen."""

import os
from pathlib import Path


def write_atomically(path: Path, data: bytes) -> None:
    """Skriver via en midlertidig fil i samme mappe, så en halv fil aldrig ligger i mappen."""
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)
