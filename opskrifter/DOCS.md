# Opskrifter

Husstandens opskriftsbibliotek. Hver opskrift er én Markdown-fil i biblioteksmappen, så den kan læses og rettes direkte via Samba og kommer med i HA's fulde backups.

## Indstillinger

- `biblioteksmappe`: Mappen med opskrifterne. Standard er `/share/opskrifter`.

## Udvikling

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r opskrifter/requirements-dev.txt
cd opskrifter
../.venv/Scripts/python -m pytest
../.venv/Scripts/python -m mypy
```

Kør lokalt mod en mappe med `RECIPE_LIBRARY_DIR=<mappe> RECIPE_INDEX_PATH=<fil> python -m recipe_reader` og åbn http://localhost:8099/.
