"""Starter add-on'en: API og frontend på Ingress-porten."""

import uvicorn

from .app import create_app
from .claude_reader import reader_from_settings
from .settings import Settings

INGRESS_PORT = 8099


def main() -> None:
    settings = Settings.from_environment()
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    settings.index_path.parent.mkdir(parents=True, exist_ok=True)
    uvicorn.run(create_app(settings, reader=reader_from_settings(settings)), host="0.0.0.0", port=INGRESS_PORT)


if __name__ == "__main__":
    main()
