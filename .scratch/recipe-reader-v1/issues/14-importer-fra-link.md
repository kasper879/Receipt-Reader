# 14: Importér en opskrift fra et link

**What to build:** Brugeren indsætter et link til en opskrift på en hjemmeside i stedet for at tage skærmbilleder. Appen henter siden og laver et udkast, som gennemses og gemmes som en opskrift fra billeder. Sidens billede af retten bliver retbillede, og linket gemmes, så man altid kan finde originalen.

Beslutning: Import fra hjemmesider stod under specens *Out of Scope*. Brugeren har valgt at bygge det efter v1.

**Blocked by:** 05, 06, 08, 13

**Status:** ready-for-agent

- [ ] "Ny opskrift" har et felt til et link og "Hent opskrift". Mens siden hentes og læses, vises det som ved billeder, og man kan forlade siden.
- [ ] Serveren henter kun http- og https-adresser på offentlige værter, fordi add-on'en kører på hjemmenetværket. `localhost`, private adresser og adresser på det lokale netværk afvises også efter en omdirigering. Siden må højst være 5 MB, og hentningen har en timeout.
- [ ] Fra siden udtrækkes struktureret data (schema.org `Recipe` som JSON-LD), titlen, billedet (JSON-LD `image` eller `og:image`) og den synlige tekst.
- [ ] Aflæser-porten får en metode til at læse en sides indhold. Kontrakten er den samme som for billeder: dansk, metriske enheder, null for felter, der ikke står på siden, bevarede ingrediensgrupper og ét udkast pr. opskrift.
- [ ] Sidens billede af retten hentes og bliver opskriftens retbillede, når udkastet gemmes.
- [ ] Linket gemmes i frontmatter som `link` og vises i opskriftsvisningen. Feltet bevares ved redigering.
- [ ] En side, der ikke kan hentes lige nu (netværksfejl, timeout, 5xx), giver en ventende aflæsning, som prøves igen. En side, der ikke findes, eller ikke er HTML, venter på brugeren.
- [ ] Tests: hentning med en mocket HTTP-klient (udtræk af JSON-LD, billede og tekst, afviste adresser, også efter en omdirigering, størrelse, fejlklassificering) og forløbet via API'et med en falsk henter og den falske aflæser (udkast, retbillede ved gem, `link` i filen, ventende aflæsning og "prøv igen").
