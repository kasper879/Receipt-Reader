# 11: Retbillede

**What to build:** Brugeren vælger et retbillede til en opskrift ved at tage et billede eller vælge et fra galleriet, så biblioteket og opskriftsvisningen viser den færdige ret. Retbilledet kan skiftes og fjernes. Der laves ingen automatisk beskæring.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Opskriftsvisningen har en handling til at tage eller vælge et retbillede. Når der allerede er et retbillede, kan det skiftes eller fjernes.
- [ ] Retbilledet gemmes ved siden af filen med opskriftens slug som præfiks, og `retbillede` sættes i frontmatter. Ved skift fjernes det gamle billede. Ved fjern fjernes både billedet og feltet.
- [ ] Billedet skaleres ned til en fornuftig størrelse og får EXIF-rotation på serveren, så store billeder fra telefonen ikke gør biblioteket tungt.
- [ ] Biblioteket og visningen viser retbilledet. Uden retbillede falder de tilbage til originalbilledet, som i ticket 01 og 02.
- [ ] En fil med advarsel kan ikke få et retbillede.
- [ ] Tests via API'et:
  - upload, og billedet og feltet findes
  - skift, og det gamle billede er væk
  - fjern, og listen og visningen falder tilbage til originalbilledet
