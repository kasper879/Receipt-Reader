# 15: Ingredienser til indkøbslisten i Home Assistant

**What to build:** Fra en opskrift kan brugeren lægge ingredienserne på husstandens indkøbsliste i Home Assistant, omregnet til de valgte portioner. Listen er HA's egen todo-liste, som alle i husstanden har i companion-appen.

Beslutning: Indkøbsliste stod under specens *Out of Scope*. Brugeren har valgt at bygge den efter v1, i den samme add-on og ikke i et nyt repo. Add-on'en taler med HA via Supervisor-API'et (`homeassistant_api: true`) og tjenesten `todo.add_item`.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Add-on'en har adgang til HA's API. En indstilling `indkoebsliste` angiver todo-listen. Standard er `todo.shopping_list`.
- [ ] Opskriftsvisningen har "🛒 Til indkøbslisten", der viser ingredienserne med flueben og med mængderne omregnet til de valgte portioner. Ingredienser uden mængde, fx "salt og peber", er fravalgt fra start.
- [ ] "Læg N varer på listen" tilføjer hver valgt ingrediens som én vare, fx "600 g hakket svinekød", med "Til <titel>" som beskrivelse. Brugeren får at vide, hvor mange varer der blev lagt på listen.
- [ ] Uden HA, fx når appen køres lokalt, vises knappen ikke. Findes listen ikke, eller svarer HA med fejl, får brugeren en forståelig besked. Tokenen logges aldrig.
- [ ] En opskrift med advarsel har ikke knappen.
- [ ] Tests: klienten mod en mocket HTTP-klient (token, tjenestekald, fejl, ingen HA) og API'et med en falsk indkøbsliste.
