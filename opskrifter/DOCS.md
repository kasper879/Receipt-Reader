# Opskrifter

Husstandens opskriftsbibliotek. Hver opskrift er én Markdown-fil i biblioteksmappen, så den kan læses og rettes direkte via Samba og kommer med i HA's fulde backups.

## Indstillinger

- `biblioteksmappe`: Mappen med opskrifterne. Standard er `/share/opskrifter`.
- `api_noegle`: API-nøglen til Claude API'et (Anthropic), som aflæser de fotograferede opskrifter. Den gemmes som en hemmelighed og logges aldrig. Uden nøgle gemmes billederne som en ventende aflæsning, indtil nøglen er sat.
- `model`: Claude-modellen, der aflæser billederne. Standard er `claude-opus-5-5`.

Aflæsningen er det eneste, appen henter fra internettet. Fejler den af tekniske årsager, fx fordi der ikke er forbindelse, venter billederne og prøves igen automatisk.

Undermapperne `.aflaesninger` (ventende aflæsninger og udkast, der ikke er gennemset) og `.papirkurv` er skjulte. De kommer med i backup, men er ikke en del af biblioteket.

## Udvikling

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r opskrifter/requirements-dev.txt
cd opskrifter
../.venv/Scripts/python -m pytest
../.venv/Scripts/python -m mypy
```

Kør lokalt mod en mappe med `RECIPE_LIBRARY_DIR=<mappe> RECIPE_INDEX_PATH=<fil> RECIPE_API_KEY=<nøgle> python -m recipe_reader` og åbn http://localhost:8099/.
