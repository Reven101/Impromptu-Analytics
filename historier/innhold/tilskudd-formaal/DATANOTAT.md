# Datanotat: tilskudd-formaal

**Status: parkert 2026-08-26.** Valideringen fant et sammenlignbarhetsproblem i kilden som
gjør både tidslinjen og totaltallene misvisende. Historien ligger som utkast
(`meta.utkast = true`) og havner ikke på forsiden.

Planen er å hente inn egne festivaldata senere og se om grunnlaget da blir godt nok. Alt
arbeidet under er intakt: cachen (`pipeline/cache/formaal_cache.json`) inneholder 29 518
ferdig kategoriserte beskrivelser som ikke koster noe å bruke om igjen, så lenge
`PROMPTVERSJON` og modellnavnet står uendret. Endres en av dem, må kategoriseringen kjøres
på nytt.

## Hva som er gjort

Fritekstfeltene `tiltak` og `kort_beskrivelse_av_tiltak` i tilskudd.no-eksporten er
kategorisert etter formål med `anthropic/claude-haiku-4.5` (promptversjon `formaal-v2`,
kjørt 2026-08-26). 29 518 unike beskrivelser, som dekker 96,7 % av kronene med beskrivelse.
Formelstyrte ordninger (momskompensasjon, grasrotandel, partistøtte, trossamfunn) er holdt
utenfor kategoriseringen og telt for seg.

### Kvalitetsmåling

| Mål | Resultat |
|---|---|
| Treff mot ICNPO-fasit, Haiku 4.5 (n=300) | 65,7 % |
| Treff mot ICNPO-fasit, Sonnet 5 (n=300) | 71,0 % |
| — herav Idrett | 92,6 % / 95,1 % |
| — herav Kunst og kultur | 73,6 % / 84,7 % |
| Andel i «annet» (kategorilisten treffer ikke) | 1,0 % av kronene |
| Andel i «uklar_beskrivelse» (kilden sier ikke noe) | 29,2 % av kronene |

### Modellvalg (ICNPO-fasit, n=300, samme utvalg og seed for alle)

| Modell | Treff | Idrett | Kunst og kultur | $/1000 tekster |
|---|---|---|---|---|
| claude-sonnet-5 | 71,0 % | 95,1 % | 84,7 % | 0,981 |
| **gemini-3.1-flash-lite** | **68,7 %** | 91,4 % | 81,9 % | **0,066** |
| claude-haiku-4.5 | 65,7 % | 92,6 % | 73,6 % | 0,182 |
| gemini-2.5-flash-lite | 51,7 % | 91,4 % | 65,3 % | 0,022 |
| gemini-3.7-flash | ikke testet | | | 0,388 |

`gemini-3.1-flash-lite` er valgt som standardmodell: bedre enn Haiku til under en tredjedel
av prisen, og 2,3 prosentpoeng under Sonnet til en femtendedel. gemini-3.7-flash har lavere
listepris enn Haiku, men resonnerer (415 av 458 output-tokens) og blir dobbelt så dyr.

**Grunnlaget som ligger i cachen nå er kategorisert med claude-haiku-4.5.** Tas historien opp
igjen, må enten hele settet kjøres om med én modell (~$3,80), eller så må det blandede
grunnlaget opplyses om — `modellsetning()` i hent_tilskudd_formaal.py gjør det automatisk.

ICNPO-testen er en nedre grense, ikke en fasit for formålskategoriene: ICNPO klassifiserer
mottakerorganisasjonens *sektor*, ikke tiltaket. Bommene er toveis mellom bins som overlapper
i ICNPO selv (Rekreasjon ↔ Interesseorganisasjoner, Sosiale tjenester → Krisehjelp), og begge
modeller treffer samme vegg der. Forskjellen mellom modellene ligger i de veldefinerte
kategoriene. Haiku ble valgt: 5,3× billigere for 5,3 prosentpoeng.

## Hvorfor den ikke kan publiseres

Datasettet er en sammenslåing av tilskudd.no-bulk og Kulturrådets NKF/FLB-eksport, og de to
har ulik komplettbarhet per år.

**Utenriksdepartementet slutter å rapportere etter 2022:**

| År | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| UD, mkr | 2 000 | 2 163 | 0 | 0 | 0 |
| UD, rader | 82 | 65 | 0 | 0 | 0 |

Over 4 mrd kr forsvinner ut av grunnlaget. Siden UD-tildelinger er prosjektbaserte og
beskrevne, blir den formelstyrte andelen for høy: headline-tallet «minst 64 % uten oppgitt
formål» er anslagsvis 5–6 prosentpoeng for høyt.

**Kulturrådet har et hull i 2024:** 2 071 rader, 221 mkr — mot 3 658 rader og 1 023 mkr i
2023. Radene finnes, beløpene mangler. Kilden (`nkf_flb_organisasjoner_2021_2026_alle_status.csv`)
inneholder alle statuser, også ubehandlede søknader.

**Følgen for tidslinjen:** «Arrangement» faller fra 719 til 129 mkr mellom 2023 og 2024. Det
er ikke en politisk endring — Musikkfestivaler (402 mkr i 2023) og Scenekunst – arrangører
forsvinner fra grunnlaget. Kurven ville vært en ren rapporteringsartefakt.

Kategoriseringsdekningen er derimot jevn over år (96,4–97,1 %), så problemet ligger i kilden,
ikke i LLM-steget.

## Før dette kan publiseres

Universet må avgrenses til noe som faktisk er sammenlignbart. Alternativene er å låse
analysen til ett år der de store forvalterne rapporterer fullt, å utelate NKF/FLB-kilden og
kjøre på tilskudd.no-bulk alene, eller å gjøre selve rapporteringshullene til historien.
Valget er ikke tatt.

## Andre forbehold

- Beløp er nominelle kroner, ikke deflatert.
- Ingen normalisering mot befolkning — et fylkeskart ble derfor droppet, siden et kart over
  tildelte kroner i praksis blir et befolkningskart.
- `tildelinger_samlet_2021_2026.csv` har UTF-8 BOM: første kolonne heter
  `﻿tilskuddsforvalter`, og leses som tom uten at noe feiler. `les_rader()` bruker
  `utf-8-sig`. Denne feilen skjulte rapporteringshullet i første forsøk.
