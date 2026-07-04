---
name: habilitet-klagesaker
description: Strukturering av habilitetsvurderinger og klagesaker fra WebSak-eksporter og møtereferater i Kulturdirektoratet — konsistent felt-/saksstruktur, forvaltningslovens habilitetsregler og personvernhensyn. Brukes når oppgaven gjelder habilitetsvurderinger, klagesaksbehandling, WebSak-data, rådsmøte-/utvalgsreferater eller inhabilitetsregistrering hos Kulturdirektoratet.
---

# Habilitet og klagesaker — strukturering av saksdata (Kulturdirektoratet)

## ⚠️ Verifiseringsstatus — LES FØRST

**IKKE verifisert mot faktisk pipeline.** Den omtalte Python-pipelinen og feltstrukturen
for websak-/møtereferatdata ble **ikke funnet** i noen av de tilgjengelige GitHub-repoene
(søkt 2026-07-04 i alle seks repoer + GitHub-kodesøk på «habilitet»/«websak»/«klagesak»),
og Google Drive var utilgjengelig i økten som laget denne skillen. Alt under er derfor
(a) generell forvaltningsrett, (b) offentlig kunnskap om Kulturdirektoratets organer, og
(c) rimelige antakelser om struktur — merket deretter.

**Obligatorisk steg 0 hver gang skillen brukes:** be brukeren peke på den faktiske
pipelinen (repo/mappe/fil) og et eksempel på faktisk feltstruktur (én anonymisert rad),
og **oppdater denne skillen** med den verifiserte strukturen før du produserer noe.
Ikke gjett feltnavn — feil feltnavn i en habilitetsrapport er verre enn ingen rapport.

## Kontekst [offentlig kunnskap + oppgitt av bruker]

Kulturdirektoratet forvalter bl.a. Norsk kulturfond. Vedtak fattes av råd/utvalg med
fagfeller fra kulturfeltet — som selv er aktive aktører. Habilitet må derfor vurderes
løpende og dokumenteres per sak, og avslag kan påklages. Kildene er typisk WebSak
(sak-/arkivsystemet, ACOS) og møtereferater fra råds-/utvalgsmøter. Brukeren er selv
ansatt i offentlig forvaltning på tilskuddsfeltet (bekreftet i om.html i
tilskuddskompasset-repoet).

## Juridisk ramme [generell forvaltningsrett — verifiser mot gjeldende lov]

Forvaltningsloven § 6 er kjernen for habilitetsvurderinger:
- **§ 6 første ledd** (automatisk inhabilitet): selv part; slektskap/ekteskap/partnerskap
  i rett opp-/nedstigende linje eller søsken; verge/fullmektig for part; ledelse/styreverv
  i selskap som er part.
- **§ 6 andre ledd** (skjønnsmessig): «andre særegne forhold … egnet til å svekke tilliten
  til hans upartiskhet» — i kulturfeltet typisk: samarbeidsrelasjoner, konkurrentforhold
  (søker selv i samme runde/ordning), økonomiske interesser, nære vennskap/konflikter.
- **Avledet inhabilitet** (§ 6 tredje ledd) og at avgjørelsen treffes av organet, ikke
  medlemmet selv, når det er tvil (§ 8).
- Klagesaker: fvl. kap. VI; for Kulturfondet er klageadgangen typisk begrenset til
  **saksbehandlingsfeil** (ikke kunstfaglig skjønn) — verifiser gjeldende regler.

## Anbefalt målstruktur [ANTAKELSE — erstatt med verifisert feltstruktur i steg 0]

Én rad per habilitetshendelse, med minst:

| Felt | Innhold |
|---|---|
| `sak_id` / `websak_ref` | Saksnummer i WebSak |
| `mote_id`, `mote_dato`, `organ` | Hvilket råd/utvalg, hvilket møte |
| `medlem` | Hvem habiliteten gjelder |
| `relasjon_type` | Kontrollert vokabular: part / slektskap / styreverv-ledelse / eget-søkerskap / samarbeid / annet-særegent |
| `hjemmel` | fvl. § 6 første ledd bokstav a–e / § 6 andre ledd / § 6 tredje ledd |
| `utfall` | inhabil-fratrådte / habil-etter-vurdering / ikke-vurdert |
| `soknad_ref`, `soker`, `ordning` | Hva saken gjaldt |
| `kilde`, `kilde_avsnitt` | Sporbarhet tilbake til referat/dokument |

Klagesaker tilsvarende: `klage_id`, `paklaget_vedtak`, `klagegrunn` (kontrollert vokabular:
saksbehandlingsfeil-typene), `utfall` (medhold/delvis/avvist/opprettholdt), `behandlingstid`.

## Fallgruver

[Generelle, men reelle for denne typen data:]
- **Personvern**: habilitetsdata er personopplysninger om navngitte personer og deres
  relasjoner. Aldri sjekk rådata inn i offentlige repoer; aggreger/anonymiser før analyse
  deles; vurder hjemmelsgrunnlag før noe publiseres.
- **Referattekst er ustrukturert og inkonsistent**: samme habilitetsfratredelse omtales
  ulikt fra referent til referent («fratrådte», «deltok ikke», «erklærte seg inhabil»).
  Bygg gjenkjenning på nøkkelordlister og logg ALLTID avsnittet som traff, for manuell
  kontroll — samme mønster som nøkkelordmatching i brukerens SSB-pipeline (verifisert
  praksis i Impromptu-Analytics).
- **Fravær av funn er ikke funn av fravær**: at et referat ikke nevner habilitet betyr ikke
  at ingen var inhabile. Skill «ingen habilitetsmerknad i kilden» fra «vurdert habil».
- **WebSak-eksporter** har erfaringsmessig duplikater ved journalposter i flere omganger og
  inkonsistente datoformater — kjør duplikat- og datovalidering før aggregering (jf.
  duplikat-/årstallshåndteringen i bygg_nkf_flb_v2.py, verifisert praksis).
- Ikke bland **vedtaksdato, møtedato og journalføringsdato** — de kan ligge uker fra hverandre.

## Arbeidsflyt

1. **Steg 0 (obligatorisk)**: innhent faktisk pipeline + feltstruktur; oppdater skillen.
2. Profiler kildefilene (se skillen `nytt-datasett-onboarding` for standardprosedyren).
3. Normaliser til målstrukturen med kontrollerte vokabularer; logg alle rader som ikke
   lot seg klassifisere i stedet for å tvinge dem.
4. Valider: hver rad sporbar til kilde; ingen personer i aggregert output med n < 5.
5. Lever både strukturert datasett og en metodedel som skiller verifisert/antatt.
