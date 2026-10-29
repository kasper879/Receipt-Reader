# Ændringer

## 0.3.0

- **Aflæsningen kører i baggrunden.** Upload svarer med det samme, og skærmen viser, hvor mange sekunder aflæsningen har kørt. Du kan forlade siden, så kommer resultatet som en note på forsiden, og noten opdaterer sig selv.
- **Kortere ventetid:** Hvert forsøg hos aflæsningstjenesten må højst tage 2 minutter, og der prøves én gang til. Derefter bliver aflæsningen ventende og prøves igen senere.
- **Logning af aflæsninger** i add-on'ens log: start, antal billeder, model, varighed, tokens brugt og resultatet eller fejlen med næste forsøg. API-nøglen logges aldrig.
- **Kameraet har sin egen knap**, når du tilføjer billeder, fordi nogle telefoner kun viser galleriet i filvælgeren.
- Tags gemmes altid med små bogstaver.

## 0.2.0

- **Ny opskrift:** Fotografér en opskrift med kameraet, eller vælg billeder fra galleriet. Aflæsningen laver dem om til et udkast på dansk med metriske enheder. Kræver en API-nøgle til Claude i indstillingen `api_noegle`.
- **Gennemsyn:** Ret udkastet direkte i opskriftsopsætningen med originalbilledet ved siden af, og gem det i biblioteket. Du advares, hvis titlen ligner en opskrift, der allerede findes. Finder aflæsningen flere opskrifter på billederne, gennemser du dem én ad gangen.
- **Automatisk retbillede:** Et foto af retten på originalbillederne, fx fra en hjemmeside, bliver opskriftens retbillede.
- **Ventende aflæsning:** Fejler aflæsningen, fx uden internet, gemmes billederne og aflæses igen automatisk.
- **Opskriftsvisning:** Hele opskriften på én side med omregning af portioner, vurdering med stjerner, retbillede og originalbilleder i stor visning.
- **Redigering:** Ret en gemt opskrift, og tilføj flere originalbilleder.
- **Biblioteket:** Søg, mens du skriver, sortér efter nyeste, vurdering eller alfabetisk, og filtrér på tags.
- **Papirkurv:** Slettede opskrifter kan hentes tilbage eller slettes endeligt.
- **Filer er sandheden:** Filer, der rettes via Samba, ses i appen med det samme. En fil, der ikke kan læses, vises med en advarsel og overskrives aldrig.

## 0.1.0

- Første version: biblioteket vises som "Opskrifter" i HA-sidebaren.
