# 09: Vurdering

**What to build:** Husstanden giver en opskrift en fælles vurdering på 1–5 stjerner direkte fra opskriftsvisningen. Vurderingen kan ændres og fjernes, og den gemmes i opskriftens fil.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Stjernerne i opskriftsvisningen kan klikkes og sætter vurderingen 1–5. Klikker man på den aktuelle vurdering igen, eller vælger "fjern", fjernes vurderingen.
- [ ] Vurderingen skrives til `vurdering` i filens frontmatter. Når der ikke er nogen vurdering, udelades feltet. Resten af filen er uændret.
- [ ] Biblioteket og sortering efter vurdering afspejler ændringen med det samme.
- [ ] En fil med advarsel kan ikke få en vurdering. Ticket 04 håndhæver det.
- [ ] Tests via API'et: sæt, ændr og fjern vurdering. Feltet i filen kontrolleres, og resten af filen er byte for byte uændret.
