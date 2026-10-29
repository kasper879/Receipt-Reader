# 13: Automatisk retbillede fra originalbillederne

**What to build:** Når et originalbillede indeholder et foto af den færdige ret, fx et skærmbillede fra en hjemmeside eller en kogebogsside med et billede, beskærer appen fotoet og gemmer det automatisk som opskriftens retbillede. Brugeren skal ikke selv beskære og uploade det.

Beslutning: Brugeren har valgt den automatiske løsning frem for et forslag, der skal bekræftes. Det ændrer specens *Out of Scope*, hvor automatisk beskæring var udeladt i v1.

**Blocked by:** 05, 06, 11

**Status:** ready-for-agent

- [ ] Aflæser-porten udvides: et udkast kan have et område for retbilledet, nemlig nummeret på originalbilledet og området som brøkdele af billedets bredde og højde. Er der ikke et foto af retten, er området null. Tegninger, ikoner, logoer og personer tæller ikke.
- [ ] Claude-adapteren beder om området i samme aflæsning. Et ugyldigt område, fx uden for billedet, for lille eller på et billede, der ikke findes, ignoreres og gør ikke aflæsningen ugyldig.
- [ ] Når udkastet gemmes, beskæres området fra originalbilledet, skaleres som et uploadet retbillede (ticket 11) og gemmes som `<slug>.ret.jpg` med `retbillede` i frontmatter. Uden område gemmes opskriften som før.
- [ ] Området bevares, når udkastet rettes midlertidigt under gennemsynet.
- [ ] Gennemsynet fortæller, at billedet af retten bruges som retbillede. Det kan skiftes eller fjernes bagefter som i ticket 11.
- [ ] Tests via API'et med den falske aflæser: gem med område giver retbilledet på disken med den forventede beskæring, gem uden område giver intet retbillede, området overlever en midlertidig rettelse, og et område på et billede, der ikke findes, ignoreres. Adapteren testes med en mocket HTTP-klient for et ugyldigt område.
