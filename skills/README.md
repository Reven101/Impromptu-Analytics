# Claude Skills for kulturdata-arbeidet

Seks skills laget 2026-07-04, én mappe per skill. Hver mappe zippes for seg og lastes
opp i claude.ai → Customize > Skills (SKILL.md må ligge i rot av zip-en sammen med
eventuelle referansefiler).

| Skill | Verifiseringsstatus |
|---|---|
| `impromptu-dataengine` | Fullt verifisert mot kildekode (main, ikke egen branch) |
| `tilskuddskompasset` | Fullt verifisert mot kildekode og generert datafil (307 ordninger) |
| `norsk-monitor-kulturdata` | SSB-delen verifisert mot pipeline; Norsk Monitor-delen krever kodebok |
| `kulturstatistikk-formidling` | Formidlingsdelen verifisert; statsregnskap-fallgruvene er brukerens oppgitte lærdommer |
| `habilitet-klagesaker` | IKKE verifisert — pipeline ikke funnet i repoene; skillen krever steg 0 |
| `nytt-datasett-onboarding` | Prosedyre rekonstruert fra verifisert praksis i kodebasene |

Hver SKILL.md har en egen «Verifiseringsstatus»-seksjon som skiller verifisert fra antatt.
Zip-kommando: `cd skills && for d in */; do (cd "$d" && zip -r "../${d%/}.zip" .); done`
