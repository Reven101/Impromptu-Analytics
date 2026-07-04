# Claude Skills for kulturdata-arbeidet

Skills laget/oppdatert 2026-07-04, én mappe per skill. Hver mappe zippes for seg og
lastes opp i claude.ai → Customize > Skills (SKILL.md i rot av zip-en). **NB:** endringer
her oppdaterer ikke opplastede skills automatisk — last opp ny zip ved endring.

| Skill | Verifiseringsstatus |
|---|---|
| `impromptu-dataengine` | Fullt verifisert mot kildekode (main, ikke egen branch) |
| `tilskuddskompasset` | Fullt verifisert mot kildekode og generert datafil (307 ordninger) |
| `impromptu-designsystem` | Fullt verifisert mot tokens.css, komponenter.js og publiserte tekster |
| `norsk-monitor-kulturdata` | SSB-delen verifisert mot pipeline; Norsk Monitor-delen krever kodebok |
| `kulturstatistikk-formidling` | Formidlingsdelen verifisert; statsregnskap-fallgruvene er brukerens oppgitte lærdommer |
| `habilitet-klagesaker` | IKKE verifisert — pipeline ikke funnet i repoene; skillen krever steg 0 |
| `nytt-datasett-onboarding` | Prosedyre verifisert mot praksis i kodebasene; kobles til profilskillen `data-analyse-metodikk` |
| `kultursektor-datakilder` | Kilderegister; 5 av 6 kilder verifisert mot kjørende hentescripts (statsregnskapet.no gjenstår) |
| `arkitektur-husregler` | Fullt verifisert mot alle seks repoer; per-repo detaljer ligger i CLAUDE.md i hvert repo |

Skillene forutsetter/refererer disse profilskillene (ligger ikke her):
`data-analyse-metodikk` (generelt analyserammeverk — Frenzel/Strategic Analytics),
`first-principles`, `ytringsrom-kunstnere`, `trav-analyse`.

Arbeidsdeling å huske: norsk-monitor-kulturdata = HVEM deltar (personer/andeler);
kulturstatistikk-formidling = PENGENE (kroner/budsjettandeler); impromptu-dataengine =
produksjon/kode; impromptu-designsystem = utseende/stemme.

Hver SKILL.md har en egen «Verifiseringsstatus»-seksjon som skiller verifisert fra antatt.
Zip-kommando: `cd skills && for d in */; do (cd "$d" && zip -r "../${d%/}.zip" .); done`
