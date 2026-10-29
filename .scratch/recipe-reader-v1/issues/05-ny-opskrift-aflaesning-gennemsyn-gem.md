# 05: Ny opskrift – aflæsning, gennemsyn og gem (inkl. advarsel om lignende titel)

**What to build:** Brugeren trykker "📷 Ny opskrift" og tager eller vælger et eller flere originalbilleder. En aflæsning laver dem om til et udkast. I gennemsynet retter brugeren udkastet direkte i opskriftsopsætningen med originalbilledet fastgjort ved siden af eller over, og gemmer det som en opskrift i biblioteket. Hvis titlen ligner en eksisterende opskrift, advares brugeren, mens titlen skrives.

Ticketen bygger aflæser-porten og bruger kun den falske aflæser. Den rigtige tjeneste er ticket 06. Ticketen håndterer kun det første udkast fra en aflæsning. Flere udkast er ticket 07.

Design: `prototype/design/index.html?variant=B&screen=gennemsyn` på branchen `prototype/design`.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] "📷 Ny opskrift" åbner telefonens kamera eller billedgalleri. Man kan tage eller vælge flere billeder, se dem og fjerne enkelte, før de sendes til aflæsning. Det vises, at aflæsningen er i gang.
- [ ] Aflæser-porten: originalbilleder ind, og en liste af udkast eller en teknisk fejl ud. Kontrakten er dansk, metriske enheder, null for felter, der ikke står i originalen, bevarede ingrediensgrupper og ét udkast pr. opskrift. Hvilken aflæser der bruges, bestemmes af konfigurationen. I tests bruges den falske.
- [ ] Gennemsyn på telefonen: originalbilledet sidder fast øverst (ca. ⅓ af skærmhøjden) med knapper til at skifte side. Gennemsyn på desktop: originalbilledet står i en venstre kolonne i fuld højde. Klik åbner billedet i stor visning.
- [ ] Udkastet vises i opskriftsopsætningen fra ticket 02, og alt kan rettes direkte i teksten: titel, portioner, forberedelse, total, ingrediensgrupper og ingredienser, trin, noter, kilde og tags. Man kan tilføje og fjerne ingredienser, grupper og trin.
- [ ] Tomme felter viser en kursiv pladsholder ("Tilføj"). En hjælpetekst forklarer, at aflæsningen ikke gætter. Et udkast kan gemmes med tomme felter.
- [ ] Ticketen afgør, om ingredienser redigeres som tekstlinjer eller strukturerede felter. Uanset hvad sendes ingredienserne struktureret til API'et, og tekstlinjer tolkes i backenden med samme parser som filformatet.
- [ ] Lighedstjek af titel: Titler normaliseres (små bogstaver, kun bogstaver og tal) og sammenlignes på, om de er ens, eller om den ene indeholder den anden. API'et har et kald til tjekket. Advarslen opdateres, mens titlen skrives, og erstatter "Gem i biblioteket" med "Der findes allerede en opskrift, der hedder „…“", "Gem alligevel" og "Annullér". Annullér flytter markøren til titlen.
- [ ] Gem afvises af API'et, når titlen ligner en eksisterende, medmindre klienten har bekræftet "gem alligevel".
- [ ] Gem skriver opskriften som Markdown-fil i biblioteket med et filnavn ud fra titlen. Findes navnet, får det et nummer bagi. Originalbillederne gemmes ved siden af med opskriftens slug som præfiks, og `oprettet` sættes til dagens dato.
- [ ] "Kassér dette udkast" fjerner udkastet. Efter gem eller kassér går man til forsiden, hvor den nye opskrift står øverst.
- [ ] Tests via API'et med den falske aflæser:
  - upload, udkast, gem og den forventede fil og de forventede billeder på disken
  - filen hentes igen og giver samme opskrift (rundtur med grupper, tomme felter og mængder uden enhed)
  - en lignende titel afvises uden bekræftelse og lykkes med den, og filnavnet bliver unikt
  - tekstlinjer tolkes til strukturerede ingredienser
