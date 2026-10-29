# 04: Filer er sandheden – ændringer uden for appen og ulæselige filer

**What to build:** Biblioteket følger altid filerne i biblioteksmappen, jf. ADR-0001. Filer, der tilføjes, rettes eller slettes via Samba, ses i appen uden genstart. En fil, der ikke kan læses korrekt, vises med en advarsel i stedet for at blive sprunget over. Søgeindekset kan altid bygges op igen ud fra filerne.

Design: `prototype/design/index.html?variant=B&screen=opskrift&id=pasta-med-pesto` på branchen `prototype/design`.

**Blocked by:** 02, 03

**Status:** ready-for-agent

- [ ] Ændringer i biblioteksmappen opdages med en filovervågning. Hvis overvågning ikke er tilgængelig, tjekkes ændringstiden, når biblioteket hentes. Næste kald til API'et afspejler ændringen.
- [ ] En fil, der ikke kan tolkes, giver en opskrift med advarsel (grund og filens rå indhold) i stedet for en fejl. Den indgår i listen og i søgningen på det, der kunne læses, fx titlen eller filnavnet.
- [ ] Forsiden viser en opskrift med advarsel med ⚠ og "Filen kunne ikke læses korrekt".
- [ ] Opskriftsvisningen viser en boks med kant i accentfarven, "Denne fil kunne ikke læses korrekt.", grunden og filens rå indhold.
- [ ] Biblioteket overskriver aldrig en fil med advarsel. Alle ændringer via API'et afvises, og filen er uændret.
- [ ] Hvis indeksfilen slettes eller er ødelagt, bygges den op igen ved opstart og giver samme bibliotek.
- [ ] Skjulte undermapper (til udkast, ventende aflæsninger og papirkurv) ignoreres af indekset.
- [ ] Tests via API'et og direkte filoperationer i den midlertidige mappe:
  - tilføj, ret og slet en fil
  - en ulæselig fil vises i listen og i visningen med grund og rå indhold
  - opdatering af en ulæselig fil afvises, og filen er uændret
  - slet indekset, genstart, og biblioteket er det samme
