# 16: Samlet indkøbskurv på tværs af opskrifter

**What to build:** Brugeren kan samle ingredienser fra flere opskrifter i én indkøbskurv i appen. Kurven lægger ens ingredienser sammen, fx 2 spsk + 1 spsk karry = 3 spsk karry. Brugeren fjerner det, de har i forvejen, og sender det hele til indkøbslisten i Home Assistant på én gang.

Beslutninger:
- Sammenlægningen sker i appen, før varerne sendes. Varerne på HA's liste er ren tekst, fx "400 g skyr", så appen slår ikke sammen med det, der allerede står der.
- Kurven er fælles for husstanden og gemmes på serveren, ikke i browseren. Så kan én lægge i kurven på telefonen og en anden sende den fra tabletten.
- Kurven erstatter ticket 15's direkte afsendelse. Panellet på opskriften lægger i kurven, og der sendes kun fra kurven.

**Blocked by:** 15

**Status:** ready-for-agent

- [x] Panellet under ingredienserne har "Læg N varer i kurven" i stedet for "Læg N varer på listen". Mængderne er omregnet til de valgte portioner, ligesom i dag.
- [x] Kurven har sin egen skærm, der kan nås fra forsiden og fra opskriften. Den viser, hvor mange varer der er i kurven.
- [x] Ingredienser med samme navn og samme enhed lægges sammen. Navne sammenlignes uden forskel på store og små bogstaver og ekstra mellemrum. Ingredienser med samme navn, men forskellig enhed, fx "200 g gulerod" og "2 stk gulerod", står på hver sin linje.
- [x] Ingredienser uden mængde, fx "peber", står én gang, uanset hvor mange opskrifter der bruger dem.
- [x] Hver linje viser, hvilke opskrifter den kommer fra. Linjerne har flueben, så brugeren kan fravælge det, de har i forvejen.
- [x] En opskrift kan fjernes fra kurven igen, og så trækkes dens mængder fra. Kurven kan tømmes.
- [x] "Send N varer til indkøbslisten" lægger hver valgt linje på HA's liste som én vare og tømmer kurven, når det er lykkedes. Fejler afsendelsen, bliver kurven liggende med en forståelig besked.
- [x] Beskrivelsen på varen er "Til <titel>, <titel>" med opskrifterne bag linjen, men kun når listen kan gemme beskrivelser (som i 0.5.2).
- [x] Kurven overlever, at add-on'en genstartes.
- [x] Tests: sammenlægning (samme enhed, forskellig enhed, uden mængde, brøker og omregnede portioner), at en opskrift fjernes igen, gem og indlæs efter genstart, og API'et for kurven og afsendelsen med en falsk indkøbsliste.

## Comments

- Ingredienser under gruppen "Fra eget køkken" (fx vand, olie og salt) er i dag valgt fra start i panellet. Overvej at fravælge dem fra start, når kurven bygges.
- Bygget i 0.6.0. Ingredienser under en gruppe med "eget køkken" i navnet er fravalgt fra start i panellet.
