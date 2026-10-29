# 12: Papirkurv

**What to build:** Når brugeren sletter en opskrift, flyttes den til papirkurven i stedet for at forsvinde. Fra papirkurven kan den hentes tilbage til biblioteket eller slettes endeligt. Opskrifter i papirkurven vises ikke i biblioteket og indgår ikke i søgningen.

**Blocked by:** 02, 03

**Status:** ready-for-agent

- [ ] Opskriftsvisningen har "Slet", som flytter Markdown-filen og alle dens billeder til en skjult papirkurv-undermappe i biblioteksmappen. Brugeren får at vide, at opskriften ligger i papirkurven.
- [ ] Opskrifter i papirkurven er ikke med i biblioteket, i søgningen eller i tagfilteret.
- [ ] Papirkurven kan nås fra forsiden, fx som et link nederst, og viser opskrifterne med titel og slettedato.
- [ ] "Hent tilbage" flytter filen og billederne tilbage. Er filnavnet blevet optaget i mellemtiden, får filen et nummer bagi.
- [ ] "Slet endeligt" fjerner filen og billederne permanent. Brugeren skal bekræfte først.
- [ ] Opskrifter med advarsel kan også slettes til papirkurven, fordi filen flyttes uændret.
- [ ] Tests via API'et:
  - slet, og opskriften er skjult fra listen og søgningen, og filerne ligger i papirkurven
  - hent tilbage med billeder, også ved en navnekonflikt
  - slet endeligt, og filerne er væk
