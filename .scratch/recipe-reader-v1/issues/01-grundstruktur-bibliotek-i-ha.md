# 01: Grundstruktur – biblioteket vises i HA

**What to build:** Recipe Reader kan installeres som Home Assistant-add-on og vises som "Opskrifter" i HA-sidebaren via Ingress. Forsiden viser biblioteket som en tekstliste ud fra Markdown-filerne i biblioteksmappen. Billederne i listen er retbilledet, eller det første originalbillede, hvis der ikke er et retbillede. Udseendet følger designretning B "Kogebog" i lys og mørk tilstand. Ticketen lægger også fundamentet for resten: FastAPI-backend, læsning af filformatet og testopsætningen.

Spec: `.scratch/recipe-reader-v1/spec.md`. Design: branchen `prototype/design`, `prototype/design/index.html?variant=B&screen=forside`. Skal ikke merges.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Add-on'en kan bygges til arm64 og installeres på HA OS. Den vises som "Opskrifter" i sidebaren via Ingress.
- [ ] Biblioteksmappen kan konfigureres i add-on'ens indstillinger. Standard er `/share/opskrifter`.
- [ ] FastAPI serverer både API'et og den statiske frontend. Alle URL'er er relative, så appen virker under Ingress' dynamiske sti.
- [ ] Opskriftsformatet kan læses: frontmatter (titel, portioner, forberedelse, total, vurdering, tags, kilde, oprettet, retbillede, originalbilleder) og sektionerne Ingredienser (med valgfrie `###`-grupper), Fremgangsmåde og Noter. Formatet står i specen.
- [ ] En ingredienslinje tolkes som `[mængde] [enhed] navn`. Mængden kan være decimaltal med komma eller punktum, brøk eller unicode-brøk. Enheden hentes fra en fast liste. En linje uden mængde er gyldig.
- [ ] API'et returnerer biblioteket som en liste. Hvert element har id, titel, kilde, samlet tid, tags, vurdering, billede og oprettet. Billeder serveres via API'et.
- [ ] Forsiden viser:
  - en lille etiket og overskrift
  - et søgefelt, der endnu ikke virker
  - "📷 Ny opskrift" som knap i fuld bredde, der endnu ikke virker
  - biblioteket som tekstliste med små billeder, titel, kilde, tid, tags og stjerner, sorteret med nyeste først
  - manglende værdier udelades
- [ ] Tema: Fraunces, Inter og Caveat følger med add-on'en, så der ikke laves eksterne kald. Papir-, blæk- og accentfarverne fra specen bruges. Lys og mørk tilstand følger HA eller systemet. Layoutet er bygget til telefonen først.
- [ ] Testopsætning: pytest med FastAPI's TestClient. Hver test har sin egen midlertidige biblioteksmappe og sin egen indeksplacering. En falsk aflæser kan sættes ind. Der er tests af listen ud fra filer lagt i mappen, inklusive grupper, tomme felter og mængder uden enhed.
