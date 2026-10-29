# 07: Flere udkast, og udkast overlever genstart

**What to build:** Når originalbillederne indeholder flere opskrifter, giver aflæsningen flere udkast. Brugeren gennemser dem et ad gangen og kan skifte mellem dem uden at miste sine rettelser. Udkast, der ikke er gennemset endnu, gemmes på disken, så de ikke går tabt, hvis appen lukkes eller add-on'en genstartes.

Design: `prototype/design/index.html?variant=B&screen=gennemsyn` (to udkast fra de samme to originalbilleder).

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] Alle udkast fra en aflæsning vises i gennemsynet som links ("1. Boller i karry · 2. Kartoffelsalat"), og man kan skifte mellem dem.
- [ ] Rettelser gemmes midlertidigt via API'et, mens man redigerer, og bevares, når man skifter udkast.
- [ ] Udkast, der ikke er gennemset, ligger i en skjult undermappe i biblioteksmappen, så de kommer med i HA-backup. Søgeindekset ignorerer dem.
- [ ] Alle udkast fra samme aflæsning deler originalbillederne.
- [ ] Efter gem eller kassér af et udkast går man til det næste udkast. Når der ikke er flere, går man til forsiden.
- [ ] Hvis der er udkast, der ikke er gennemset, viser forsiden en note med et link til gennemsynet.
- [ ] Tests via API'et med den falske aflæser:
  - en aflæsning giver to udkast
  - en rettelse i udkast 1 bevares
  - gem udkast 1 og kassér udkast 2
  - udkast, der ikke er gennemset, findes stadig, når appen startes igen mod samme mappe
  - midlertidige filer ryddes op, når det sidste udkast er behandlet
