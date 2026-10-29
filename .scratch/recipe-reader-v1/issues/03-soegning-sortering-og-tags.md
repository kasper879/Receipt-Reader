# 03: Søgning, sortering og tags

**What to build:** Brugeren finder opskrifter på forsiden ved at søge, mens der skrives, sortere biblioteket og filtrere på tags. Listen er delt op med overskrifter, der følger sorteringen. Det kræver det afledte søgeindeks (SQLite) fra ADR-0001.

Design: `prototype/design/index.html?variant=B&screen=forside`.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Søgeindekset ligger i add-on'ens datamappe, ikke i biblioteksmappen, og bygges ud fra filerne, når appen starter.
- [ ] Søgningen finder ord i titel, ingredienser, tags, kilde og noter uden at skelne mellem store og små bogstaver.
- [ ] Sortering: nyeste først (standard), højeste vurdering (opskrifter uden vurdering sidst, derefter alfabetisk) og alfabetisk med dansk sortering, så æ, ø og å kommer sidst.
- [ ] Tagfilter. Søgning og tagfilter kan kombineres.
- [ ] Forsiden:
  - søgefeltet opdaterer listen, mens man skriver
  - sortering og tags vises som tekstlinks ("Sortér: nyeste først · …", "Tags: alle · …")
  - overskrifterne følger sorteringen: måned og år, forbogstav eller antal stjerner
  - en tydelig besked vises, når intet matcher
- [ ] Søgning, sortering og filter bevares, når man går fra forsiden til en opskrift og tilbage.
- [ ] Tests via API'et: søgning i hvert af de fem felter, dansk sortering, sortering efter vurdering med opskrifter uden vurdering, tagfilter, og tagfilter kombineret med søgning.
