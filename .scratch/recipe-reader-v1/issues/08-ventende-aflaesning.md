# 08: Ventende aflæsning

**What to build:** Hvis aflæsningen fejler af tekniske årsager, fx fordi der ikke er internet, gemmes originalbillederne som en ventende aflæsning. Den aflæses automatisk igen senere. Brugeren ser den på forsiden og kan prøve igen med det samme eller kassere den. Når den lykkes, kommer brugeren til gennemsynet.

Design: noten på forsiden i `prototype/design/index.html?variant=B&screen=forside`.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] Originalbillederne gemmes på disken, *før* aflæseren kaldes. En teknisk fejl fra aflæseren giver en ventende aflæsning i en skjult undermappe i biblioteksmappen.
- [ ] Brugeren får at vide, at billederne er gemt, og at de aflæses senere.
- [ ] Forsiden viser en kursiv note med streg i accentfarven: "Ventende aflæsning. N originalbilleder fra <tidspunkt> venter …", et link "prøv nu" og en mulighed for at kassere.
- [ ] Ventende aflæsninger prøves igen automatisk i baggrunden med stigende interval og et loft. De genoptages ved opstart.
- [ ] En aflæsning, der lykkes, giver udkast, som behandles som i ticket 05 og 07. Den ventende aflæsning forsvinder, og noten på forsiden peger nu på gennemsynet.
- [ ] Kassér sletter den ventende aflæsning og dens billeder.
- [ ] Tests via API'et med den falske aflæser:
  - en teknisk fejl giver en ventende aflæsning, og billederne ligger på disken
  - listen over ventende aflæsninger
  - "prøv igen" lykkes og giver udkast
  - kassér fjerner filerne
  - en ventende aflæsning findes stadig, når appen startes igen mod samme mappe
