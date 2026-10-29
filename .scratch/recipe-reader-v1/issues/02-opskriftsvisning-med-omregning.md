# 02: Opskriftsvisning med omregning af portioner

**What to build:** Brugeren åbner en opskrift fra biblioteket og ser hele opskriften på én side i kogebogsopsætningen, uden faner. Brugeren kan regne mængderne op og ned i portioner og åbne originalbillederne i stor visning.

Design: `prototype/design/index.html?variant=B&screen=opskrift&id=boller-i-karry` og `&id=mormors-aeblekage` (uden tid og portioner) på branchen `prototype/design`.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] API'et returnerer en enkelt opskrift med alle felter og strukturerede ingredienser (gruppe, mængde, enhed, navn).
- [ ] Visningen har:
  - "← Biblioteket"
  - tags som lille etiket
  - stor titel
  - byline "Fra *kilde* · tilføjet <dato>"
  - stjerner, som endnu ikke kan klikkes
- [ ] Retbilledet vises i fuld bredde. Uden retbillede vises det første originalbillede med teksten "Intet retbillede endnu", og der er altid et link "Se originalbilleder (n)".
- [ ] Originalbilleder kan åbnes i stor visning, hvor man kan bladre mellem dem.
- [ ] Faktalinjen viser Portioner, Forberedelse og I alt. En manglende værdi vises som "—".
- [ ] Ingredienser og trin står i to kolonner på desktop og under hinanden på telefonen. Ingrediensgrupper har små overskrifter i accentfarven. Trin har store numre. Noter vises som en håndskrevet note (Caveat).
- [ ] Omregning: − og + ved Portioner regner mængderne om som mængde × (valgte portioner / opskriftens portioner). Der kan ikke vælges under 1. Omregningen ændrer ikke filen.
- [ ] Mængder vises som brøkerne ¼, ⅓, ½, ⅔ og ¾ (fx "1½"), ellers med én decimal og komma. Fra 20 og opefter vises heltal. Ingredienser uden mængde står uændret.
- [ ] Når portioner ikke er angivet, er der ingen −/+, og mængderne står som i originalen.
- [ ] Tests: API'et returnerer opskriften med grupper, tomme felter og mængder uden enhed, og et ukendt id giver 404. Omregningen testes ikke automatisk, jf. specen.
