# Hva som aldri forlater maskinen

Pipelinen kaller en språkmodell over OpenRouter (`pipeline/llm_klient.py`). Alt som sendes
dit, forlater maskinen og går til en tredjepart. Derfor denne regelen:

**Bare genuint offentlige, publiserte datasett sendes til modellen.**

Det holder ikke at et datasett er «åpent» i dagligtale. Spørsmålet er om innholdet allerede
er publisert av kilden selv.

## Godkjent

- SSB PxWeb, Kartverket, Frost, Brønnøysundregistrene, Doffin
- tilskudd.no — publiserte tildelinger med mottakernavn og organisasjonsnummer
- Kudos (DFØ), regjeringen.no, statsregnskapet.no

## Skal aldri sendes

Ligger på samme maskin, i nabomapper under `Dataanalyse/`. Forveksling er lett, og
konsekvensen er ikke reversibel — det som er sendt, er sendt.

| Datasett | Hvorfor |
|---|---|
| `claude/habilitet_samlet_*.xlsx`, `habilitet/` | Navngitte saksbehandlere og søkere, habilitetsvurderinger |
| `klagesaker/` | Enkeltsaker under behandling |
| `soknader_esak/`, `innsyn/` | Saksdokumenter, ikke publisert |
| `claude/statens_kunstnerstipend_*.csv` | Navngitte enkeltkunstnere — publisert som liste, men personopplysninger, og ikke vårt å videreformidle til tredjepart |
| `undersokelser/`, `ki_pilot_ii/` | Respondentdata |

Aggregerte tall fra disse er greit å publisere på vanlig måte — regelen gjelder å sende
*radnivådata* til et eksternt API.

## Praktisk

`kategoriser_formaal.py` leser bare fila `TILDELINGER_CSV` peker på, og peker som standard
på tilskudd.no-eksporten i tilskuddskompasset. Endrer du den variabelen, sjekk tabellen over
først.

Påstanden om at arbeid med åpne data fritar for personvernhensyn stemmer for SSB-aggregatene
Impromptu ellers bruker. Den stemmer ikke for nabomappene.
