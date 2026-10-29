# 10: Redigér en gemt opskrift

**What to build:** Brugeren kan rette en opskrift, der allerede ligger i biblioteket. Redigeringen sker i samme opsætning som gennemsynet, med originalbillederne fastgjort ved siden af. Brugeren kan også tilføje originalbilleder til en gemt opskrift, fx en side, der manglede.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] Opskriftsvisningen har en "Redigér"-handling, der åbner opskriften i gennemsynets opsætning fra ticket 05, med originalbillederne fastgjort.
- [ ] Alle felter kan rettes som i gennemsynet. Gem opdaterer den eksisterende fil og laver ikke en ny.
- [ ] Hvis titlen ændres, så den ligner en anden opskrift, vises advarslen fra ticket 05. Filnavnet bevares, når titlen ændres, så eksterne henvisninger og Samba-stier ikke brydes.
- [ ] Originalbilleder kan tilføjes med kamera eller galleri og lægges ved siden af filen. Listen i frontmatter opdateres.
- [ ] Opskrifter med advarsel kan ikke redigeres i appen. Redigér-handlingen er skjult, og API'et afviser.
- [ ] Tests via API'et:
  - opdatering ændrer filen på stedet med samme filnavn
  - felter, der ikke er rettet, er uændrede
  - tilføjede originalbilleder ligger på disken og står i frontmatter
  - redigering af en fil med advarsel afvises
