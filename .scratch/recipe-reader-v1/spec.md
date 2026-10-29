# Spec: Recipe Reader v1

Status: ready-for-agent

## Problem Statement

Husstandens opskrifter ligger spredt: i kogebøger, på håndskrevne kort fra familien, i udklip og på hjemmesider. Når vi skal finde en opskrift, kan vi ikke søge i den, og vi skal huske, hvor den står. Håndskrevne kort kan slides op eller blive væk. Det tager for lang tid at skrive opskrifterne af i hånden, og eksisterende opskriftsapps gemmer dem i en sky eller i en database, som vi ikke selv ejer, og som forsvinder, hvis appen gør.

## Solution

Recipe Reader er et personligt **bibliotek** af opskrifter, der kører som add-on på husstandens Home Assistant og vises som en side i HA-sidebaren. Den bruges primært på telefonen via HA companion-appen, også ude af huset.

Man fotograferer en opskrift med telefonen. Billederne bliver **originalbilleder**, og en **aflæsning** laver dem om til et eller flere **udkast** på dansk og med metriske enheder. I **gennemsynet** ser man udkastet ved siden af originalbillederne, retter det og gemmer det som en **opskrift**. Hver opskrift gemmes som én Markdown-fil på HA-maskinen, så man kan læse og rette den direkte via Samba. Den kommer også med i HA's backups.

Biblioteket kan søges, sorteres og filtreres på **tags**. En opskrift vises i en redaktionel kogebogsopsætning. Opsætningen er valgt i en designprototype, retning B "Kogebog", på branchen `prototype/design`. Opsætningen har omregning af **portioner**, en **vurdering** med stjerner, et **retbillede** og adgang til originalbillederne.

## User Stories

### Forside og bibliotek

1. Som bruger vil jeg se hele biblioteket på forsiden, når jeg åbner Opskrifter i HA, så jeg hurtigt kan finde noget at lave.
2. Som bruger vil jeg have et søgefelt øverst på forsiden, så jeg kan finde en opskrift uden at bladre.
3. Som bruger vil jeg kunne søge på titel, ingredienser, tags, kilde og noter, så jeg også kan finde "den med kokosmælk".
4. Som bruger vil jeg se søgeresultaterne, mens jeg skriver, så jeg ikke skal trykke på en knap.
5. Som bruger vil jeg se biblioteket med de nyeste opskrifter først som standard, så det, jeg lige har tilføjet, står øverst.
6. Som bruger vil jeg kunne sortere biblioteket efter vurdering, så jeg kan finde husstandens favoritter.
7. Som bruger vil jeg kunne sortere biblioteket alfabetisk, så jeg kan finde en opskrift, når jeg kender navnet.
8. Som bruger vil jeg se listen delt op med overskrifter, der følger sorteringen (måned, forbogstav eller antal stjerner), så den er let at overskue.
9. Som bruger vil jeg kunne filtrere biblioteket på et tag, så jeg fx kun ser "aftensmad" eller "kage".
10. Som bruger vil jeg kunne fjerne tagfilteret igen med ét tryk, så jeg kommer tilbage til hele biblioteket.
11. Som bruger vil jeg, at søgning og tagfilter virker sammen, så jeg kan finde en vegetarisk suppe.
12. Som bruger vil jeg se et lille billede for hver opskrift i listen, så jeg kan genkende retten.
13. Som bruger vil jeg se originalbilledet i listen, når en opskrift ikke har et retbillede, så rækken aldrig er tom.
14. Som bruger vil jeg se titel, kilde, samlet tid, tags og vurdering for hver opskrift i listen, så jeg kan vælge uden at åbne den.
15. Som bruger vil jeg, at manglende tid eller vurdering bare udelades i listen, så der ikke står tomme pladsholdere.
16. Som bruger vil jeg få en tydelig besked, når søgningen ikke finder noget, så jeg ved, at listen ikke bare er langsom.
17. Som bruger vil jeg have en stor "Ny opskrift"-knap på forsiden, så det er nemt at tilføje en opskrift med telefonen i hånden.

### Ny opskrift og aflæsning

18. Som bruger vil jeg kunne tage et eller flere billeder med telefonens kamera fra "Ny opskrift", så jeg kan fotografere en opskrift, der fylder flere sider.
19. Som bruger vil jeg også kunne vælge billeder fra telefonens billedgalleri, så jeg kan bruge et billede, jeg allerede har taget.
20. Som bruger vil jeg kunne se og fjerne billeder, inden jeg sender dem til aflæsning, så et mislykket billede ikke kommer med.
21. Som bruger vil jeg, at aflæsningen giver et udkast på dansk med metriske enheder, også når originalen er på et andet sprog eller bruger cups og ounces, så biblioteket er ensartet.
22. Som bruger vil jeg, at aflæsningen giver et udkast for hver opskrift, når billederne indeholder flere opskrifter, så to opskrifter på samme side ikke bliver blandet sammen.
23. Som bruger vil jeg, at aflæsningen lader felter stå tomme, når originalen ikke angiver dem (fx tid eller portioner), så jeg ikke får gætte-værdier i biblioteket.
24. Som bruger vil jeg, at aflæsningen bevarer ingrediensgrupper som "Til sovsen", så opskriften er opbygget som originalen.
25. Som bruger vil jeg kunne se, at aflæsningen er i gang, så jeg ved, at appen arbejder.

### Ventende aflæsning

26. Som bruger vil jeg, at mine billeder bliver gemt, selv om aflæsningen fejler af tekniske årsager (fx intet internet), så jeg ikke skal fotografere opskriften igen.
27. Som bruger vil jeg se en ventende aflæsning på forsiden med antal billeder og tidspunkt, så jeg ved, at der ligger noget og venter.
28. Som bruger vil jeg, at en ventende aflæsning automatisk aflæses igen senere, så jeg ikke selv skal huske det.
29. Som bruger vil jeg kunne prøve en ventende aflæsning igen med det samme, så jeg ikke skal vente, når forbindelsen er tilbage.
30. Som bruger vil jeg komme til gennemsynet, når en ventende aflæsning lykkes, så jeg kan gemme opskriften.
31. Som bruger vil jeg kunne kassere en ventende aflæsning, så billeder, jeg ikke vil bruge alligevel, ikke ligger og venter for evigt.
32. Som bruger vil jeg, at ventende aflæsninger overlever en genstart af add-on'en eller HA, så intet går tabt.

### Gennemsyn

33. Som bruger vil jeg se udkastet og originalbillederne samtidig, så jeg kan sammenligne dem og rette fejl.
34. Som bruger vil jeg på telefonen se originalbilledet fastgjort øverst, mens udkastet ruller nedenunder, så jeg altid kan se originalen.
35. Som bruger vil jeg på desktop se originalbilledet i en kolonne ved siden af udkastet, så jeg kan bruge den ekstra plads.
36. Som bruger vil jeg kunne skifte mellem originalbillederne, når der er flere, så jeg kan kontrollere hver side.
37. Som bruger vil jeg kunne åbne et originalbillede i stor visning, så jeg kan læse små eller håndskrevne detaljer.
38. Som bruger vil jeg se udkastet i samme opsætning som en færdig opskrift og kunne rette direkte i teksten, så jeg kan se, hvordan opskriften kommer til at se ud.
39. Som bruger vil jeg kunne rette titel, portioner, forberedelsestid, samlet tid, ingredienser (med grupper), trin, noter, tags og kilde, så opskriften bliver rigtig.
40. Som bruger vil jeg kunne tilføje og fjerne ingredienser, ingrediensgrupper og trin, så jeg kan rette det, aflæsningen har overset.
41. Som bruger vil jeg se tomme felter som en tydelig pladsholder ("Tilføj"), så jeg kan se, hvad der mangler, og udfylde det, hvis jeg vil.
42. Som bruger vil jeg kunne gemme et udkast med tomme felter, så jeg ikke er tvunget til at opfinde værdier.
43. Som bruger vil jeg få en advarsel, mens jeg skriver, hvis titlen ligner titlen på en opskrift i biblioteket, så jeg ikke gemmer den samme opskrift to gange.
44. Som bruger vil jeg kunne vælge "Gem alligevel" ved advarslen, så jeg kan gemme to forskellige opskrifter med næsten samme navn.
45. Som bruger vil jeg kunne vælge "Annullér" ved advarslen og komme tilbage til titlen, så jeg kan rette den.
46. Som bruger vil jeg se alle udkast fra en aflæsning som en liste og kunne skifte mellem dem, så jeg kan gennemse dem et ad gangen.
47. Som bruger vil jeg, at mine rettelser i et udkast bevares, når jeg skifter til et andet udkast, så jeg ikke mister arbejde.
48. Som bruger vil jeg kunne kassere et enkelt udkast, så en opskrift, jeg ikke vil have, ikke kommer i biblioteket.
49. Som bruger vil jeg, at originalbillederne gemmes sammen med opskriften, så jeg altid kan se originalen senere.
50. Som bruger vil jeg komme videre til næste udkast, når jeg har gemt et, og til forsiden, når der ikke er flere, så forløbet føles færdigt.
51. Som bruger vil jeg ikke miste udkast, hvis jeg lukker appen midt i gennemsynet, så jeg kan fortsætte senere.

### Opskriftsvisning

52. Som bruger vil jeg se hele opskriften på én side uden faner, så jeg kan læse den som i en kogebog.
53. Som bruger vil jeg se titel, tags, kilde og oprettet-dato øverst, så jeg ved, hvad det er, og hvor det kommer fra.
54. Som bruger vil jeg se retbilledet stort øverst, så jeg kan se, hvordan retten skal se ud.
55. Som bruger vil jeg se originalbilledet i stedet, med en tekst om at der endnu ikke er et retbillede, så siden ikke er tom.
56. Som bruger vil jeg altid kunne åbne opskriftens originalbilleder, så jeg kan tjekke aflæsningen.
57. Som bruger vil jeg se portioner, forberedelsestid og samlet tid i en fast faktalinje, så jeg hurtigt kan se, om jeg har tid.
58. Som bruger vil jeg se "—" i faktalinjen, når en værdi mangler, så det er tydeligt, at den ikke er angivet.
59. Som bruger vil jeg kunne regne opskriften op og ned i portioner med − og +, så mængderne passer til antallet af gæster.
60. Som bruger vil jeg se mængderne vist pænt (fx "½", "1½", "1,5 dl"), så de er lette at læse.
61. Som bruger vil jeg, at ingredienser uden mængde (fx "salt og peber") står uændret, når jeg regner om, så de ikke får mærkelige tal.
62. Som bruger vil jeg ikke kunne regne om, når portioner ikke er angivet, og mængderne skal stå som i originalen, så jeg ikke bliver forvirret.
63. Som bruger vil jeg, at omregningen kun gælder visningen og ikke ændrer filen, så opskriften ikke ændres ved et uheld.
64. Som bruger vil jeg se ingredienserne opdelt i deres grupper, så jeg kan forberede hver del for sig.
65. Som bruger vil jeg se trinene nummererede, så jeg kan holde styr på, hvor jeg er.
66. Som bruger vil jeg se ingredienser og trin i to kolonner på desktop og under hinanden på telefonen, så opskriften udnytter skærmen.
67. Som bruger vil jeg se noter tydeligt adskilt fra trinene, så tips ikke bliver forvekslet med fremgangsmåden.
68. Som husstand vil vi give opskriften en fælles vurdering på 1–5 stjerner direkte fra visningen, så vi kan huske, hvad der var godt.
69. Som bruger vil jeg kunne ændre eller fjerne vurderingen, så den passer, hvis vi skifter mening.
70. Som bruger vil jeg kunne gå tilbage til biblioteket og finde min søgning og mit filter, som jeg forlod dem, så jeg kan fortsætte, hvor jeg slap.

### Redigering, retbillede og papirkurv

71. Som bruger vil jeg kunne redigere en gemt opskrift i samme opsætning som gennemsynet, så jeg kan rette fejl senere.
72. Som bruger vil jeg kunne vælge et retbillede ved at tage et billede eller vælge et fra galleriet, så biblioteket viser den færdige ret.
73. Som bruger vil jeg kunne skifte eller fjerne retbilledet, så jeg kan bruge et bedre billede.
74. Som bruger vil jeg kunne tilføje flere originalbilleder til en gemt opskrift, så jeg kan gemme en side, jeg manglede.
75. Som bruger vil jeg kunne slette en opskrift, så den flyttes til papirkurven, så jeg kan fortryde.
76. Som bruger vil jeg kunne se papirkurven og hente en opskrift tilbage til biblioteket, så en fejlsletning ikke er permanent.
77. Som bruger vil jeg kunne slette en opskrift endeligt fra papirkurven, så jeg kan rydde op.
78. Som bruger vil jeg, at opskrifter i papirkurven ikke vises i biblioteket og ikke indgår i søgning, så de ikke er i vejen.

### Filer er sandheden

79. Som bruger vil jeg kunne åbne og rette en opskrift direkte i Markdown-filen via Samba, så jeg ikke er afhængig af appen.
80. Som bruger vil jeg, at ændringer i filer, der er lavet uden for appen, ses i appen uden genstart, så biblioteket altid er opdateret.
81. Som bruger vil jeg, at en ny Markdown-fil, jeg lægger i mappen, vises i biblioteket, så jeg kan tilføje opskrifter manuelt.
82. Som bruger vil jeg, at en fil, jeg sletter i mappen, forsvinder fra biblioteket, så appen og mappen er enige.
83. Som bruger vil jeg, at en fil, der ikke kan læses korrekt, vises i biblioteket med en advarsel og ikke springes over, så jeg opdager problemet.
84. Som bruger vil jeg se grunden til advarslen og filens rå indhold, når jeg åbner en opskrift med advarsel, så jeg kan rette filen.
85. Som bruger vil jeg, at appen aldrig overskriver en fil, den ikke kan læse, så jeg ikke mister indhold.
86. Som bruger vil jeg, at biblioteket kommer med i HA's fulde backups, så opskrifterne er sikre.
87. Som bruger vil jeg, at biblioteket bliver bygget op igen ud fra filerne, hvis søgeindekset bliver slettet eller ødelagt, så intet er tabt.
88. Som bruger vil jeg have læsbare filnavne ud fra titlen, så jeg kan finde rundt i mappen via Samba.

### Platform og udseende

89. Som bruger vil jeg finde appen som "Opskrifter" i HA-sidebaren, så den føles som en del af Home Assistant.
90. Som bruger vil jeg kunne bruge appen ude af huset via HA companion-appen, så jeg kan slå en opskrift op i supermarkedet.
91. Som HA-bruger vil jeg, at alle med et HA-login kan alt i appen, så der ikke skal sættes brugere op.
92. Som bruger vil jeg, at appen følger HA's lyse eller mørke tilstand, så den passer ind.
93. Som bruger vil jeg, at appen er bygget til telefonen først og også fungerer godt på desktop, så den kan bruges begge steder.
94. Som bruger vil jeg, at appen bruger kogebogsudtrykket fra den valgte designretning, så opskrifterne er rare at læse.
95. Som bruger vil jeg, at appen virker uden at hente noget fra internettet, bortset fra selve aflæsningen, så den virker, selv om nettet er nede.

## Implementation Decisions

### Arkitektur

- Leveres som en **Home Assistant-add-on** til HA OS, der kører på en Raspberry Pi (arm64), og vises i sidebaren via **Ingress** med navnet "Opskrifter". Ingress sørger for adgangskontrol, så der er ingen brugerstyring i appen.
- **Backend:** Python med FastAPI. Den samme proces serverer både API'et og den statiske frontend.
- **Frontend:** Framework er ikke valgt. Krav:
  - Alle URL'er skal være relative, fordi Ingress serverer appen under en dynamisk sti.
  - Tema, lys eller mørk, følger HA eller systemets indstilling.
  - Fontene (Fraunces, Inter og Caveat) leveres sammen med add-on'en, så der ikke laves eksterne kald, når appen vises.
- **Lagring følger ADR-0001:**
  - Biblioteket ligger som Markdown-filer i en konfigurerbar mappe, som standard `/share/opskrifter`.
  - Søgeindekset (SQLite) er en afledt kopi og ligger i add-on'ens egen datamappe. Det kan altid slettes og bygges op igen ud fra filerne.

### Moduler (dybe moduler med små interfaces)

1. **Opskriftsformat**
   - Tolker en Markdown-fil til en opskrift og skriver en opskrift til Markdown.
   - Er rent: ingen IO.
   - En fil, der ikke kan tolkes, giver en opskrift med en advarsel (grund plus filens rå indhold) i stedet for en fejl.
   - At tolke og skrive igen må ikke ændre en gyldig fil (rundtur).
2. **Bibliotek**
   - Ejer mappen.
   - Lister, læser, opretter, opdaterer og flytter opskrifter til og fra papirkurven, og sletter endeligt.
   - Ejer filnavne: et slug ud fra titlen, og et nummer bagi, hvis det allerede findes.
   - Ejer originalbilleder og retbillede.
   - Overskriver aldrig en fil, der har en advarsel. Redigering af sådan en fil er kun mulig via Samba.
3. **Søgeindeks**
   - Synkroniseres med biblioteket, når appen starter, og når filer ændres. Ændringer opdages med en filovervågning, og hvis den ikke er tilgængelig, med et tjek af ændringstid, når biblioteket hentes.
   - Søger i titel, ingredienser, tags, kilde og noter.
   - Sorterer efter nyeste, vurdering eller alfabetisk (dansk sortering, så æ, ø og å kommer sidst).
   - Filtrerer på tags.
   - Kan altid bygges op igen ud fra filerne.
4. **Aflæser** (port mod den eksterne tjeneste)
   - Interface: originalbilleder ind, og en liste af udkast ud. Alternativt en *teknisk fejl*, som betyder, at aflæsningen skal prøves igen senere.
   - Kontrakt:
     - Alt er på dansk og med metriske enheder.
     - Felter, der ikke står i originalen, er tomme (null). De gættes ikke.
     - Ingrediensgrupper bevares.
     - Der er ét udkast pr. opskrift på billederne.
   - Hvilken tjeneste og model der bruges, er ikke en del af denne spec. Adapteren konfigureres via add-on'ens indstillinger (fx API-nøgle).
5. **Aflæsningsforløb**
   - Gemmer originalbillederne, *før* aflæsningen går i gang.
   - Kalder aflæseren.
   - Ved teknisk fejl oprettes en ventende aflæsning, som prøves igen automatisk med stigende interval og manuelt via API'et.
   - Ventende aflæsninger og udkast, der ikke er gennemset endnu, gemmes på disken i en skjult undermappe i biblioteksmappen. Det gør, at de overlever en genstart og kommer med i backup. Søgeindekset ignorerer mappen.
6. **Lighedstjek af titel**
   - Finder opskrifter i biblioteket, hvis titel ligner udkastets titel. Titler normaliseres (små bogstaver, kun bogstaver og tal), og der ses på, om de er ens, eller om den ene indeholder den anden.
   - Bruges både, mens man skriver (til advarslen), og når man gemmer.
7. **Omregning af portioner**
   - Er ren præsentationslogik i frontenden: mængde × (valgte portioner / opskriftens portioner).
   - Formatering:
     - brøker ¼, ⅓, ½, ⅔ og ¾
     - én decimal med komma
     - heltal fra 20 og opefter
   - Ingredienser uden mængde vises uændret.
   - Kan ikke bruges, når portioner ikke er angivet.

### Filformat (skema)

YAML-frontmatter med de felter, der ikke er en del af brødteksten. Derefter faste sektioner. Felter uden værdi udelades eller står tomme og tolkes som "ikke angivet".

```markdown
---
titel: Boller i karry
portioner: 4
forberedelse: 30        # minutter
total: 75               # minutter
vurdering: 5            # 1–5, udeladt = ingen vurdering
tags: [aftensmad, klassiker]
kilde: Mormors kogebog
oprettet: 2026-10-21
retbillede: boller-i-karry.ret.jpg
originalbilleder: [boller-i-karry.1.jpg, boller-i-karry.2.jpg]
---

## Ingredienser

### Til kødbollerne
- 500 g hakket svinekød
- 1 løg, finthakket

### Til sovsen
- 2 spsk karry
- salt og peber

## Fremgangsmåde

1. Bland kødet med …
2. …

## Noter

Mormor kom altid et revet æble i sovsen.
```

- En ingredienslinje tolkes som `[mængde] [enhed] navn`:
  - Mængden kan skrives som decimaltal med komma eller punktum, som brøk eller som unicode-brøk.
  - Enheden hentes fra en fast liste af metriske og køkkenenheder (g, kg, ml, dl, l, tsk, spsk, stk, fed, dåse, bundt, knsp …).
  - Alt andet er navnet.
  - En linje uden mængde er gyldig.
- Grupper er valgfrie. Ingredienser før den første `###` hører ikke til nogen gruppe.
- Billederne ligger i samme mappe som Markdown-filen og har opskriftens slug som præfiks.
- Papirkurven er en skjult undermappe. Filer flyttes derind med deres billeder.

### HTTP-API (kontrakt på højt niveau)

- Bibliotek:
  - Liste med søgning, sortering og tagfilter. Hvert element har: id, titel, kilde, samlet tid, tags, vurdering, billede (retbillede eller første originalbillede), oprettet og advarsel.
  - Hent en opskrift. Er filen ulæselig, returneres advarsel og rå indhold.
  - Opdatér en opskrift.
  - Sæt eller fjern vurdering.
  - Upload, skift eller fjern retbillede.
  - Tilføj originalbilleder.
  - Flyt til papirkurven.
- Papirkurv: liste, hent tilbage og slet endeligt.
- Aflæsning:
  - Upload originalbilleder og start en aflæsning. Svaret er enten en liste af udkast eller en ventende aflæsning.
  - Liste over ventende aflæsninger.
  - Prøv igen nu.
  - Kassér.
- Udkast:
  - Hent udkast, der ikke er gennemset endnu.
  - Gem udkastet midlertidigt under gennemsyn.
  - Lighedstjek af titel.
  - Gem udkastet som opskrift. Er der en lignende titel, afvises det, medmindre klienten har bekræftet "gem alligevel".
  - Kassér udkast.
- Billeder serveres via API'et, så de virker under Ingress.
- Ingredienser er strukturerede i API'et (gruppe, mængde, enhed, navn). Frontenden må gerne vise dem som tekstlinjer, men tolkningen ligger i backenden, i samme parser som filformatet bruger.

### UI (retning B "Kogebog")

Den fulde beskrivelse findes i den valgte designprototype på branchen `prototype/design` (`?variant=B`). Her er de beslutninger, der binder:

- **Forside:**
  - Søgefelt øverst.
  - "📷 Ny opskrift" som knap i fuld bredde.
  - Ventende aflæsning vises som en note.
  - Sortering og tags vises som tekstlinks.
  - Biblioteket vises som en tekstliste med små billeder, delt op med overskrifter efter sorteringen. Der er ikke et kortgitter.
- **Opskriftsvisning:** Én side uden faner. Faktalinjen viser "—" for manglende værdier. Ingredienser og trin står i to kolonner på desktop. Noter vises som en håndskrevet note.
- **Gennemsyn:**
  - Originalbilledet sidder fast: øverst på telefonen og i venstre kolonne på desktop.
  - Udkastet rettes direkte i opskriftsopsætningen.
  - Advarslen om lignende titel opdateres, mens man skriver, og erstatter gem-knappen med "Gem alligevel" og "Annullér".
- **Redigering** af en gemt opskrift bruger samme opsætning som gennemsynet.
- **Typografi og farver:**
  - Serif-skriften Fraunces til tekst. Inter til små etiketter. Caveat til noter.
  - Papirfarver: lys `#f6f0e4` / blæk `#2a2420`, mørk `#1d1a17` / `#ece4d6`.
  - Accentfarve: `#a4452c` (lys) / `#e58a69` (mørk).

## Testing Decisions

- **En god test** tester det, man kan observere udefra: HTTP-svar og filer på disken. Den tester ikke interne funktioner, klasser eller indeksets tabeller. Testene skal kunne overleve en omskrivning af modulerne indenunder.
- **Seam (afstemt med brugeren):** FastAPI's HTTP-API, kaldt via en testklient.
  - Hver test har sin egen midlertidige biblioteksmappe og en ny indeksfil.
  - **Aflæseren erstattes af en falsk aflæser**, som returnerer foruddefinerede udkast eller en teknisk fejl.
  - Testene må lægge, rette og slette Markdown-filer og billeder direkte i mappen, så ADR-0001 også testes: ændringer uden for appen, ulæselige filer, og at indekset kan bygges op igen.
- **Det skal dækkes:**
  - Rundtur:
    - et udkast gemmes og giver den forventede fil på disken
    - filen hentes via API'et og giver samme opskrift
    - grupper, tomme felter og mængder uden enhed bevares
  - Søgning (i titel, ingrediens, tag, kilde og noter), dansk sortering af æ, ø og å, tagfilter og kombinationer af dem.
  - Ekstern ændring: en fil, der rettes, tilføjes eller slettes på disken, kan ses i næste kald.
  - Ulæselig fil: den vises med en advarsel i listen, og visningen returnerer grund og rå indhold. Opdatering via API'et afvises, og filen er uændret bagefter.
  - Indekset slettes eller ødelægges, og så giver en genstart det samme bibliotek.
  - Aflæsning:
    - flere udkast fra én aflæsning
    - en teknisk fejl giver en ventende aflæsning, og billederne ligger på disken
    - "prøv igen" lykkes og giver udkast
    - "kassér"
    - ventende aflæsninger og udkast overlever, at appen startes igen mod samme mappe
  - Lighedstjek af titel: gem afvises uden bekræftelse, lykkes med bekræftelse, og der laves et unikt filnavn.
  - Papirkurv: slet, opskriften er skjult fra listen og søgningen, den kan hentes tilbage med billeder, og endelig sletning fjerner filerne.
  - Vurdering: sæt, ændr og fjern. Ændringen skrives til filen.
  - Retbillede: upload, skift og fjern. Listen falder tilbage til originalbilledet.
- **Uden for automatiske tests i v1:** frontenden, herunder omregning af portioner. Den testes manuelt mod prototypen. Den rigtige adapter mod aflæsningstjenesten testes manuelt.
- **Prior art:** Der er ingen kode eller tests i repoet endnu. Brug pytest og FastAPI's TestClient og `tmp_path`-fixtures.

## Out of Scope

- Indkøbsliste.
- Dashboard-kort i HA.
- Stemmestyring.
- Import fra hjemmesider eller andre apps.
- Automatisk beskæring af retbillede ud fra originalbilleder.
- Brugerstyring og vurdering pr. person. Vurderingen er fælles for husstanden.
- Valg af aflæsningstjeneste og prompt-design. Det besluttes, når aflæser-adapteren bygges.
- Automatiske tests af frontenden.

## Further Notes

- Domænetermer følger `CONTEXT.md`: opskrift, bibliotek, kilde, portioner, vurdering, retbillede, papirkurv, tag, originalbillede, aflæsning, udkast, ventende aflæsning og gennemsyn. "Redigering" af en gemt opskrift står ikke i ordlisten og kan blive en kandidat til `/domain-modeling`, hvis det kræver egen sprogbrug.
- Designprototypen ligger på branchen `prototype/design` (commit `68fd548`) og skal ikke merges. Når der laves tickets, skal UI-ticketen have en pointer til branchen.
- Åbent designspørgsmål: Ingredienser redigeres i prototypen som fritekst med én linje pr. ingrediens. Specen lægger tolkningen i backenden, så frontenden kan vælge mellem tekstlinjer og strukturerede felter. Det bør afgøres i UI-ticketen.
- Fortolkning af ADR-0001: Udkast, der ikke er gennemset, og ventende aflæsninger ligger i biblioteksmappen, men i en skjult undermappe, så de kommer med i backup uden at blive en del af biblioteket.
