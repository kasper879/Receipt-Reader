# Recipe Reader

Et personligt opskriftsbibliotek, der kører på Home Assistant. Opskrifter fotograferes med telefonen, læses automatisk og gemmes lokalt i et fast format, hvor de kan søges frem igen.

## Language

### Opskrifter

**Opskrift**:
Én ret med ingredienser, fremgangsmåde og metadata, gemt som én fil i biblioteket.
_Avoid_: Recipe, receipt, kvittering, dokument

**Bibliotek**:
Samlingen af alle gemte opskrifter på det lokale drev.
_Avoid_: Database, arkiv, samling

**Kilde**:
Hvor en opskrift oprindeligt kommer fra, fx en kogebog, en person eller en hjemmeside.
_Avoid_: Ophav, reference

**Portioner**:
Antallet af personer, som opskriftens mængder er beregnet til. Mængderne kan omregnes til et andet antal portioner.
_Avoid_: Personer, servings, antal

**Vurdering**:
Antal stjerner (1–5), som opskriften har fået. Der er én fælles vurdering for hele husstanden.
_Avoid_: Rating, score, karakter

**Retbillede**:
Et billede af den færdige ret, som brugeren selv har valgt til opskriften. Det er ikke det samme som et originalbillede.
_Avoid_: Forsidebillede, thumbnail, foto

**Papirkurv**:
Stedet, hvor slettede opskrifter ligger, indtil de enten hentes tilbage eller slettes endeligt.
_Avoid_: Arkiv, skraldespand

**Tag**:
En fri etiket på en opskrift (fx "aftensmad", "vegetar", "kage"), der bruges til at filtrere.
_Avoid_: Kategori, label

### Indlæsning

**Originalbillede**:
Et foto, som brugeren har taget af en opskrift. En opskrift kan have flere originalbilleder, fx når den strækker sig over flere sider.
_Avoid_: Scan, upload, foto

**Aflæsning**:
At omdanne et eller flere originalbilleder til et struktureret udkast til en opskrift. Udkastet er altid på dansk og med metriske enheder, uanset originalens sprog.
_Avoid_: OCR, scanning, parsing

**Udkast**:
Resultatet af en aflæsning, før brugeren har godkendt det. En aflæsning kan give flere udkast, hvis originalbillederne indeholder flere opskrifter. Et udkast er endnu ikke en del af biblioteket.
_Avoid_: Kladde, draft

**Ventende aflæsning**:
Originalbilleder, der er gemt, men endnu ikke aflæst, fordi aflæsningen fejlede af tekniske årsager (fx intet internet). De aflæses igen senere.
_Avoid_: Kø, pending, fejlet upload

**Gennemsyn**:
Trinnet, hvor brugeren ser udkastet ved siden af originalbillederne, retter det og gemmer det som en opskrift.
_Avoid_: Review, godkendelse
