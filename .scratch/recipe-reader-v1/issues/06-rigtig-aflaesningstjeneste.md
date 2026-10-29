# 06: Rigtig aflæsningstjeneste

**What to build:** Når en opskrift fotograferes i appen, aflæses den af en rigtig tjeneste i stedet for den falske aflæser. Udkastene er på dansk, med metriske enheder og uden gætte-værdier, og hver opskrift på billederne giver sit eget udkast.

Valg af tjeneste: Brug Claude API'et (Anthropic) med billedinput og structured output eller tool use, så resultatet passer til udkastets skema. Modellen kan konfigureres, og standard er en aktuel Claude-model med billedforståelse. Valget blev truffet, da ticketen blev skrevet, fordi specen lod det stå åbent.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] En adapter bag aflæser-porten fra ticket 05 sender originalbillederne til tjenesten og returnerer en liste af udkast.
- [ ] API-nøgle og model konfigureres i add-on'ens indstillinger. API-nøglen gemmes som en hemmelighed og logges aldrig.
- [ ] Prompten håndhæver kontrakten: Alt oversættes til dansk. Enheder omregnes til metriske (cups, oz, °F og lignende). Felter, der ikke står i originalen, er null. Ingrediensgrupper bevares. Hver opskrift på billederne giver ét udkast. Billeder, der fortsætter på hinanden, behandles som én opskrift.
- [ ] Svaret valideres mod udkastets skema. Et ugyldigt svar giver en teknisk fejl og ikke et halvt udkast.
- [ ] Netværksfejl, timeout, 5xx og rate limit giver en *teknisk fejl*, så ticket 08 kan lave en ventende aflæsning. Manglende eller ugyldig API-nøgle giver en tydelig konfigurationsfejl i UI'et.
- [ ] Adapteren testes ikke mod den rigtige tjeneste i CI. Den har tests med en mocket HTTP-klient for fejlklassificering og skemavalidering. Den testes manuelt med de kilder, specen nævner: en trykt kogebogsside, et håndskrevet kort, en engelsk opskrift med cups og en side med to opskrifter. Resultatet noteres under `## Comments` i ticketen.
