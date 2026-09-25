"""Udir Statistikkbanken — skolestatistikk per skole, kommune og fylke.

Utdanningsdirektoratets statistikksystem (USS) har to veier inn, begge uten
nøkkel:

A) Det dokumenterte eksport-API-et (v2). Bare åtte tabeller er åpnet, og alle
   er Elevundersøkelsen (trivsel, mobbing, motivasjon, deltakelse).

B) Rapport-endepunktene (v1) som nettsidene til statistikkbanken selv kaller.
   Her ligger nasjonale prøver, grunnskolepoeng, karakterer og resten. Funnet
   ved å lese nettsidens JS (sept. 2026) — udokumentert og skjørere enn A.

Udir skriver selv i swaggeren at API-et «ikke er ment for ekstern bruk i dag,
og vil endres uten varsel». Kjør røyktesten før du bygger på det, og lagre
snapshot av det du henter.

Kjøring:  python3 api-atlas/eksempler/hent_udir_statistikkbank.py
Nøkkel:   ingen
Lisens:   NLOD 2.0 — oppgi «Kilde: Utdanningsdirektoratet»
Dok:      https://statistikkportalen.udir.no/api/rapportering/swagger

A) Eksport-API-et (base https://api.statistikkbanken.udir.no/api/rest/v2):
  GET /Eksport                       liste over åpne tabeller (EksportID)
  GET /Eksport/{id}/filterSpec       hvilke filtre tabellen har
  GET /Eksport/{id}/filterVerdier    alle gyldige verdier, med hierarki
  GET /Eksport/{id}/sideData?filter= antall rader og sider — sjekk FØR data
  GET /Eksport/{id}/data?filter=     dataene (JSON; &format=4 gir CSV,
                                     &sideNummer=n for side n)

Tabeller: 148 EUG-Indikator, 149 EUG-Tema, 150 EUG-Mobbing, 151 EUG-Deltakelse
(grunnskole); 152/154/153/243 tilsvarende for videregående (EUV).
OBS: I tabellista er beskrivelsene av 153 og 154 byttet om. 154 har
mobbetallene (felt AndelMobbet), 153 har temaspørsmålene (felt TemaID).
Velg tabell på feltnavn, ikke på Beskrivelse. EUV har ikke «alle trinn»;
Vg1 er det obligatoriske trinnet.

Filtersyntaks: Filter(verdi)_Filter(verdi1_verdi2)
  TidID(202412)_EnhetID(-76)_TrinnID(8)_SpoersmaalID(436)_KjoennID(-10)
  Flere verdier skilles med _, også inni parentesen. TidID er obligatorisk.
  Swaggeren sier komma mellom verdier — det gir 400 «Feil format på
  filtrene!» (målt sept. 2026). Understrek er det som virker.

Feller (målt):
  - Filterverdiene bruker intern `id`, ikke `kode`. TrinnID(8) er 9. trinn,
    Oslo kommune er EnhetID(-76), ikke 0301. Slå alltid opp i filterVerdier.
  - -10 betyr «alle». Utelater du KjoennID/EierformID, får du ALLE
    kombinasjoner (alle/gutt/jente × alle/offentlig/privat) i samme svar, og
    summerer du dem, teller du elevene flere ganger.
  - Tallene er tekst med norsk format: "4,1", "5 943", "  116" (desimalkomma,
    mellomrom som tusenskille, ledende mellomrom). Bruk tall() under.
  - Skoler i hierarkiet: kommunenoden har `barn` = indekser (ikke id) inn i
    EnhetID-lista. Organisasjonsnummer er skolens nøkkel for kobling;
    på kommunenivå står kommunenummeret i samme felt.
  - Skolenavn kan ha etterfølgende mellomrom ("Ammerud skole ") — strip().
  - Skoler uten det valgte trinnet, eller med for få svar (prikket),
    forsvinner bare stille fra svaret.
  - Uten EnhetID-filter kan ett år bli over 1 million rader (1,5 GB JSON).

B) Rapport-endepunktene (base https://statistikkportalen.udir.no/api/rapportering/):
  GET rest/v1/Rapportside/{kode}?versjon=n   rapportdefinisjon: gyldige filtre,
                                             standardverdier, dataEndepunkt
  GET {dataEndepunkt minus /data}/filterVerdier
  GET {dataEndepunkt}?filter=...&radSti=...   pivottabell som JSON

  Rapportkoden står i nettsidens <script src="...pagebuild...?rapportsideKode=">:
    GSK_NP_Geografisk  v1  nasjonale prøver 8. og 9. trinn
                           → rest/v1/Statistikk/GSK/NasjonaleProever/1/1/data
    GSK_GSPoeng        v2  grunnskolepoeng, 2011-12 →
                           → rest/v1/Statistikk/GSK/ResultatG/1/1/data
    GSK_GSKarakterer   v2  grunnskolekarakterer per fag

  Videregående, ned på SKOLE (kartlagt sept. 2026):
    VGO_VGOkarakterer            standpunkt, skriftlig og muntlig eksamen per fag,
                                 2007-08 → (radhierarki Fag.Nasjonalt.Fylke.Enhet)
    VGO_fravaer                  median fraværsdager/-timer, 2013-14 →
    VGO_slutta                   andel sluttet i løpet av året, 2011-12 →
    VGO_Elev_UtdprogTrinn        elevtall per programområde, 2012-13 →
    VGO_OvergangerV_UtdprogTrinn overganger (bestått, videre, ute), 2013 →
    VGO_Skolebidrag_Del_Bes      skolebidrag årsbestått — bare 2015-16–2019-20
  Radene i de tre siste er programområder, ikke skoler: filtrer EnhetID på én
  skole om gangen. Vgs-hierarkiet har ikke kommunenivå: Nasjonalt.Fylke.Skole,
  og Oslo er fylket (EnhetID -17). EUV (eksport 152–154, 243) har samme
  EnhetID-er (Akademiet Oslo AS = 6119 i begge).
  Bare fylke/fag: VGO_IV, VGO_ResultatIV_*, VGO_Elev_fag, VGO_UUUV,
  VGO_Voksne_*, VGO_Finntak_*, VGO_Soeker_UtdprogAar, OT_Statusgruppe,
  VGO_PrivEks. VGO_Gjennomfoering_* stopper på 2019 og fylke — bruk SSB.

  Feller (målt):
  - Samme filtersyntaks som A, men filternavnene varierer mellom rapporter
    (SkoleAarID(20242025) for prøvene, TidID(202506) for grunnskolepoeng).
    Ta utgangspunkt i rapportens filterDefaultVerdier og bytt ut det du vil.
  - Uten radSti får du bare toppraden. radSti=** gir hele landet (~1500
    rader); radSti=1.3.42.* gir bare skolene i Oslo. Stien er hierarkiet
    Nasjonalt.Fylke.Kommune.Skole — les den fra en radSti=** -kjøring.
  - Svaret er pivotert: metadata.columns er kolonnehodet i flere nivåer
    (år × prøve × trinn × … × mål), og rows[i].data er en flat liste i samme
    rekkefølge. Bygg kolonnenavn ved å gå nederst i hodet og telle
    columnCount oppover.
  - Ingen org.nr i svaret. Siste ledd i rad-id-en er EnhetID, som slås opp i
    filterVerdier (`kode` = org.nr). EnhetID-ene er DE SAMME som i
    Elevundersøkelsen (Abildsø skole = 6047 i begge), så tabellene kan kobles.
  - Prikking: "*" = skjermet, "" og "0" elever = ingen deltakelse. Rader med
    bare noen prøver prikket finnes (Linderud 2024-25: bare regning vist).
  - Nasjonale prøver finnes bare fra 2022-23 i denne rapporten (ny skala og
    brudd i tidsrekken 2022). Skalapoeng har snitt 50 nasjonalt det året
    skalaen ble satt.

Gull å grave i:
  - Trivsel og mobbing per skole i Oslo, østkant mot vestkant over tid
  - Nasjonale prøver + grunnskolepoeng + Elevundersøkelsen koblet på EnhetID:
    henger læringsmiljø sammen med resultater? — «NYC school scores» på norsk
  - Forskjell mellom offentlige og private skoler i samme kommune
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Udir Statistikkbanken"
DOK = "https://statistikkportalen.udir.no/api/rapportering/swagger"
API = "https://api.statistikkbanken.udir.no/api/rest/v2/Eksport"
RAPPORT = "https://statistikkportalen.udir.no/api/rapportering/"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"

EUG_INDIKATOR = 148
ALLE = -10


def hent_json(url: str, timeout: int = 120):
    req = urllib.request.Request(
        url, headers={"User-Agent": BRUKERAGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def tall(tekst: str | None) -> float | None:
    """'5 943' → 5943.0, '4,1' → 4.1, '' / None → None."""
    if tekst is None:
        return None
    renset = tekst.replace(" ", "").replace(" ", "").replace(",", ".")
    return float(renset) if renset else None


def filterverdier(eksport_id: int) -> dict[str, list[dict]]:
    return hent_json(f"{API}/{eksport_id}/filterVerdier")


def skoler_i_kommune(enheter: list[dict], kommunenr: str) -> list[dict]:
    """Skolene under en kommune. `barn` peker på indekser i lista, ikke id-er."""
    kommune = next(e for e in enheter if e["nivaa"] == 3 and e["kode"] == kommunenr)
    return [enheter[i] for i in kommune.get("barn", [])]


def hent_data(eksport_id: int, filtre: dict[str, int | list[int]]) -> list[dict]:
    """Hent alle sider for et filter. filtre = {"TidID": 202412, "EnhetID": [..]}."""
    deler = []
    for navn, verdi in filtre.items():
        verdier = verdi if isinstance(verdi, list) else [verdi]
        deler.append(f"{navn}({'_'.join(str(v) for v in verdier)})")
    filterstreng = "_".join(deler)

    info = hent_json(f"{API}/{eksport_id}/sideData?" + urllib.parse.urlencode({"filter": filterstreng}))
    sider = info[0]["JSONSider"] if info else 0
    rader: list[dict] = []
    for side in range(1, sider + 1):
        params = urllib.parse.urlencode({"filter": filterstreng, "sideNummer": side})
        rader.extend(hent_json(f"{API}/{eksport_id}/data?{params}"))
    return rader


def rapportside(kode: str, versjon: int) -> dict:
    """Rapportdefinisjonen: filtre, standardverdier og dataEndepunkt (vei B)."""
    return hent_json(f"{RAPPORT}rest/v1/Rapportside/{kode}?versjon={versjon}")["rappside"]


def hent_rapport(kode: str, versjon: int, radsti: str, **endringer: list[int]) -> dict:
    """Hent en rapport-pivot med rapportens standardfiltre, overstyrt av `endringer`.

    Returnerer {"kolonner": [...], "rader": [(rad_id, navn, [verdier])]} der
    kolonnenavnene er leddene i kolonnehodet skjøtt sammen med « | ».
    """
    side = rapportside(kode, versjon)
    filtre = {**side["filterDefaultVerdier"], **endringer}
    filterstreng = "_".join(f"{k}({'_'.join(str(v) for v in verdier)})" for k, verdier in filtre.items())
    endepunkt = side["rapportElementer"][0]["dataEndepunkt"]
    params = urllib.parse.urlencode({"filter": filterstreng, "radSti": radsti})
    svar = hent_json(f"{RAPPORT}{endepunkt}?{params}")

    # Kolonnehodet er nivåer av grupper med columnCount; fold hvert nivå ut
    # til like mange ledd som nederste nivå, og les dem på tvers.
    nivaaer = svar["metadata"]["columns"]
    utfoldet = [[c["name"] for c in nivaa for _ in range(c["columnCount"])] for nivaa in nivaaer]
    kolonner = [" | ".join(deler) for deler in zip(*utfoldet)]
    rader = [(r["id"], r["navn"].strip(), r["data"]) for r in svar["rows"]]
    return {"kolonner": kolonner, "rader": rader}


def nasjonale_prover_oslo(skoleaar: int = 20242025) -> dict:
    """Nasjonale prøver 8. trinn for skolene i Oslo (radsti 1.3.42.*)."""
    return hent_rapport("GSK_NP_Geografisk", 1, "1.3.42.*",
                        SkoleAarID=[skoleaar], TrinnID=[7], EnhetID=[-76])


def trivsel_oslo(skoleaar: int = 202412, antall_skoler: int = 5) -> list[tuple[str, str, float, float]]:
    """«Trives du på skolen?», 9. trinn, noen Oslo-skoler: [(navn, orgnr, snitt, n)]."""
    fv = filterverdier(EUG_INDIKATOR)
    skoler = skoler_i_kommune(fv["EnhetID"], "0301")[:antall_skoler]
    trinn9 = next(t["id"] for t in fv["TrinnID"] if t["kode"] == "9")
    trives = next(s["id"] for s in fv["SpoersmaalID"] if s["navn"] == "Trives du på skolen?")

    rader = hent_data(EUG_INDIKATOR, {
        "TidID": skoleaar,
        "EnhetID": [s["id"] for s in skoler],
        "TrinnID": trinn9,
        "SpoersmaalID": trives,
        "KjoennID": ALLE,
        "EierformID": ALLE,
    })
    return [
        (r["EnhetNavn"].strip(), r["Organisasjonsnummer"], tall(r["Score"]), tall(r["AntallBesvart"]))
        for r in rader
    ]


def smoke() -> str:
    tabeller = hent_json(API)
    if not any(t["EksportID"] == EUG_INDIKATOR for t in tabeller):
        raise ValueError(f"eksport {EUG_INDIKATOR} (EUG-Indikator) er borte fra lista")
    rader = trivsel_oslo(antall_skoler=10)
    if not rader:
        raise ValueError("ingen rader for Oslo-skoler — har filtersyntaksen endret seg?")
    navn, _, snitt, n = rader[0]
    if snitt is None or not 1 <= snitt <= 5:
        raise ValueError(f"trivselssnitt {snitt} utenfor skalaen 1–5 — feil parsing?")

    np = nasjonale_prover_oslo()
    if not any("Skalapoeng" in k for k in np["kolonner"]) or len(np["rader"]) < 30:
        raise ValueError(f"nasjonale prøver: {len(np['rader'])} Oslo-rader, kolonner "
                         f"{np['kolonner'][:3]} — har rapport-endepunktet endret seg?")
    return (f"{len(tabeller)} åpne tabeller; {navn}: trivsel {snitt} (n={n:.0f}); "
            f"nasjonale prøver: {len(np['rader'])} Oslo-skoler")


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Åpne tabeller:")
    for t in hent_json(API):
        print(f"  {t['EksportID']:>4}  {t['Beskrivelse']}")
    print("\n«Trives du på skolen?», 9. trinn 2024-25, fem Oslo-skoler:")
    for navn, orgnr, snitt, n in trivsel_oslo():
        print(f"  {navn:<40} {orgnr}  {snitt}  (n={n:.0f})")
    print("\nNasjonale prøver 8. trinn 2024-25, Oslo (rapport-endepunkt, vei B):")
    np = nasjonale_prover_oslo()
    print("  kolonner: " + "; ".join(np["kolonner"][:3]))
    for rad_id, navn, verdier in np["rader"][:5]:
        print(f"  {navn:<40} EnhetID {rad_id.split('.')[-1]:>6}  {verdier[:3]}")
    print(f"\n✓ {smoke()}")
    return 0


if __name__ == "__main__":
    for _strom in (sys.stdout, sys.stderr):
        if hasattr(_strom, "reconfigure"):
            _strom.reconfigure(encoding="utf-8")
    sys.exit(main())
