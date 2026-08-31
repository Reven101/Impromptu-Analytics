"""Måler hastigheten til én modell hos to leverandører, på nøyaktig samme arbeid.

Kjøring:

    python pipeline/mal_llm_hastighet.py
    python pipeline/mal_llm_hastighet.py --modell openai/gpt-oss-120b --runder 5
    python pipeline/mal_llm_hastighet.py --parallell 4

Bakgrunn: gpt-oss-20b kan kjøres både gjennom OpenRouter og direkte hos NVIDIA
(build.nvidia.com), med samme modellnavn. Spørsmålet er hvilken som er raskest —
og «raskest» er tre ulike tall som peker hver sin vei:

- **Ventetid til første token (TTFT)** avgjør hvor lenge et enkeltkall føles dødt.
  Den domineres av kø hos leverandøren, ikke av modellen.
- **Tid til første SVARtoken** er noe annet på en resonnerende modell: gpt-oss
  tenker først, og tenketokens kommer i sin egen strøm. Avstanden mellom de to
  tallene er tenketid, og den faktureres som output (CLAUDE.md).
- **Tokens per sekund** avgjør hvor lenge en bulkjobb tar når den først er i gang.

Derfor strømmes svaret (`stream: true`) i stedet for å gå gjennom
`llm_klient.kall_modell()`: uten strømming finnes ikke TTFT i det hele tatt, og
ett totaltall skjuler hvilken av delene som er treg.

Fire valg som avgjør om målingen betyr noe:

- **Første kall er oppvarming og telles ikke.** En kald kø kan bruke mange ganger
  så lang tid som det neste kallet. Tallet rapporteres for seg — det er selv en
  opplysning — men medianen tas av rundene etterpå.
- **Begge leverandørene får identisk forespørsel.** Samme prompt, samme
  `max_tokens`, samme `reasoning_effort`. Endrer du én, endrer du begge.
- **Oppstrømsleverandøren logges.** OpenRouter er en ruter: gpt-oss-20b kan
  serveres av flere maskinparker med vidt ulik hastighet, og uten navnet på hvem
  som faktisk svarte er tallet ikke reproduserbart.
- **En død leverandør stopper ikke den andre.** Feilen skrives ut, kolonnen blir
  «–», og scriptet avslutter med feilkode til slutt. Halve tabellen er mer verdt
  enn ingen tabell.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import http.client
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import kontrakt  # noqa: F401  (setter UTF-8 på stdout, se CLAUDE.md)
import llm_klient

# Standardmodellen for målingen. Uten leverandørprefiks: prefikset settes på per
# leverandør lenger nede, så samme navn treffer begge stedene.
MODELL = "openai/gpt-oss-20b"

# Leverandørene som sammenlignes, i den rekkefølgen de skrives ut.
# Nøkkelen er prefikset llm_klient._del_modell() forstår; None = OpenRouter.
LEVERANDORER = [("OpenRouter", None), ("NVIDIA", "nvidia")]


# To arbeidsmengder, fordi de måler hver sin ting. Den korte er pipelinens egen
# jobb — en klassifisering med fast kategoriliste, der svaret er ett ord per tekst
# og ventetiden er nesten hele tiden. Den lange gir nok utdatatokens til at
# tokens/s faktisk kan måles; på den korte drukner hastigheten i oppstartstiden.
SYSTEM_KORT = (
    "Du kategoriserer norske offentlige evalueringsrapporter. Svar med en JSON-liste "
    "med én kategori per tittel, i samme rekkefølge. Gyldige kategorier: "
    "arbeid_og_velferd, helse_og_omsorg, kultur_og_frivillighet, kunnskap_og_utdanning, "
    "kommunal_og_distrikt, naering_og_fiskeri, samferdsel, annet. Ingen andre ord."
)
TITLER = [
    "Evaluering av tilskuddsordningen for frivillige barne- og ungdomsorganisasjoner",
    "Følgeevaluering av forsøk med kortere ventetid i spesialisthelsetjenesten",
    "Sluttrapport: sammenslåing av fylkeskommunale vegadministrasjoner",
    "Kartlegging av kompetansebehov i havbruksnæringen 2019-2024",
    "Underveisevaluering av digitaliseringstiltak i grunnopplæringen",
]
BRUKER_KORT = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(TITLER))

SYSTEM_LANG = "Du skriver nøkternt og konkret på norsk bokmål. Ingen punktlister."
BRUKER_LANG = (
    "Skriv omtrent 250 ord om hvorfor en evaluering av en offentlig tilskuddsordning "
    "sjelden svarer på om ordningen virket etter hensikten. Ta med at målene ofte er "
    "formulert slik at de ikke kan motbevises, at datagrunnlaget som regel er "
    "rapportering fra mottakerne selv, og at det sjelden finnes en sammenlignbar gruppe "
    "som ikke fikk tilskudd."
)

ARBEID = {
    # navn: (meldinger, maks_tokens)
    #
    # maks_tokens er målt og gitt dobbel margin, ikke satt «romslig for sikkerhets
    # skyld»: taket reserverer kreditt per forespørsel i luften, og et oppblåst tak
    # ganget med --parallell gir HTTP 402 med god saldo på konto (CLAUDE.md).
    "kort": ([{"role": "system", "content": SYSTEM_KORT},
              {"role": "user", "content": BRUKER_KORT}], 800),
    "lang": ([{"role": "system", "content": SYSTEM_LANG},
              {"role": "user", "content": BRUKER_LANG}], 2000),
}


@dataclasses.dataclass
class Maaling:
    ttft: float | None = None          # første token av noe slag (tenking teller)
    ttfs: float | None = None          # første SVARtoken — tenketiden ligger imellom
    total: float = 0.0
    tokens_inn: int = 0
    tokens_ut: int = 0
    resonnering: int = 0
    kostnad: float = 0.0
    pris_oppgitt: bool = False
    biter: int = 0                     # strømmebiter med innhold, som reservetelling
    oppstroms: str = ""                # hvem OpenRouter faktisk rutet til
    avkuttet: bool = False

    @property
    def ut(self) -> int:
        """Utdatatokens, med bitetellingen som reserve når usage mangler."""
        return self.tokens_ut or self.biter

    @property
    def tokens_per_sek(self) -> float:
        """Etter første token — oppstartstiden hører til TTFT, ikke til hastigheten."""
        generering = self.total - (self.ttft or 0)
        return self.ut / generering if generering > 0 else 0.0


def _strom_kall(modell: str, meldinger: list[dict], maks_tokens: int,
                resonnering: str | None, tidsavbrudd: int) -> Maaling:
    """Ett strømmet kall. Kaster ved feil; kalleren styrer forsøkene."""
    # Ruting og nøkkeloppslag hentes fra produksjonsklienten framfor å gjentas her.
    # En kopi ville kommet i utakt første gang et endepunkt endres, og da måler vi
    # noe annet enn det pipelinen kjører.
    url, modellnavn, lev = llm_klient._del_modell(modell)
    nokkel = (llm_klient.hent_leverandornokkel(lev) if lev
              else llm_klient.hent_api_nokkel())

    kropp = {
        "model": modellnavn,
        "messages": meldinger,
        "temperature": 0.0,
        "max_tokens": maks_tokens,
        "stream": True,
    }
    if resonnering:
        kropp["reasoning_effort"] = resonnering
    # Forbruket kommer i en avsluttende bit — men de to tjenestene ber om den på
    # hver sin måte, og et ukjent felt kan bli avvist med 400. Derfor sendes bare
    # det feltet mottakeren kjenner.
    if lev:
        kropp["stream_options"] = {"include_usage": True}
    else:
        kropp["usage"] = {"include": True}

    req = urllib.request.Request(
        url,
        data=json.dumps(kropp).encode("utf-8"),
        headers={"Authorization": f"Bearer {nokkel}",
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream",
                 "X-Title": "Impromptu Analytics"},
        method="POST",
    )

    m = Maaling()
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=tidsavbrudd) as svar:
        for linje in svar:
            linje = linje.decode("utf-8", "replace").strip()
            if not linje.startswith("data:"):
                continue
            nyttelast = linje[5:].strip()
            if nyttelast == "[DONE]":
                break
            try:
                bit = json.loads(nyttelast)
            except json.JSONDecodeError:
                continue
            # OpenRouter leverer også oppstrømsfeil som HTTP 200 med error-kropp.
            if bit.get("error"):
                raise SystemExit(f"feil i strømmen: {str(bit['error'])[:300]}")
            m.oppstroms = bit.get("provider") or m.oppstroms
            for valg in bit.get("choices") or []:
                delta = valg.get("delta") or {}
                innhold = delta.get("content") or ""
                tenk = delta.get("reasoning") or delta.get("reasoning_content") or ""
                naa = time.perf_counter() - start
                if (innhold or tenk):
                    m.biter += 1
                    if m.ttft is None:
                        m.ttft = naa
                if innhold and m.ttfs is None:
                    m.ttfs = naa
                if valg.get("finish_reason") == "length":
                    m.avkuttet = True
            if bit.get("usage"):
                bruk = bit["usage"]
                m.tokens_inn = int(bruk.get("prompt_tokens") or 0)
                m.tokens_ut = int(bruk.get("completion_tokens") or 0)
                m.resonnering = int((bruk.get("completion_tokens_details") or {})
                                    .get("reasoning_tokens") or 0)
                if bruk.get("cost") is not None:
                    m.kostnad = float(bruk["cost"])
                    m.pris_oppgitt = True
    m.total = time.perf_counter() - start
    if m.ttft is None:
        raise SystemExit("strømmen inneholdt ingen tokens")
    return m


def kall(modell: str, meldinger: list[dict], maks_tokens: int, resonnering: str | None,
         tidsavbrudd: int, forsok: int) -> Maaling:
    """Som _strom_kall, men prøver igjen på det som pleier å gå over av seg selv."""
    siste = ""
    for n in range(forsok):
        try:
            return _strom_kall(modell, meldinger, maks_tokens, resonnering, tidsavbrudd)
        except urllib.error.HTTPError as e:
            siste = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
            if e.code not in llm_klient.STATUS_SOM_PROVES_IGJEN:
                raise SystemExit(f"{modell}: {siste}") from None
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError,
                TimeoutError) as e:
            siste = f"{type(e).__name__}: {e}"
        if n == forsok - 1:
            raise SystemExit(f"{modell} svarte ikke etter {forsok} forsøk ({siste})")
        ventetid = min(2 ** n, 30)
        print(f"    …{siste[:110]} — forsøk {n + 2}/{forsok} om {ventetid}s", flush=True)
        time.sleep(ventetid)
    raise AssertionError("uendelig løkke")  # uoppnåelig


def t(sekunder: float | None) -> str:
    return "–" if sekunder is None else f"{sekunder:.2f} s".replace(".", ",")


def spenn(verdier: list[float]) -> str:
    return f"[{min(verdier):.2f}–{max(verdier):.2f}]".replace(".", ",")


def mal_leverandor(navn: str, prefiks: str | None, modell: str, args) -> dict | None:
    """Kjører oppvarming + runder + eventuell parallelltest for én leverandør."""
    fullt = f"{prefiks}:{modell}" if prefiks else modell
    print(f"\n{'=' * 72}\n{navn} — {fullt}\n{'=' * 72}", flush=True)
    resultat: dict = {"navn": navn, "modell": fullt}

    for arbeid, (meldinger, maks) in ARBEID.items():
        print(f"\n  [{arbeid}] oppvarming …", flush=True)
        oppvarming = kall(fullt, meldinger, maks, args.resonnering,
                          args.tidsavbrudd, args.forsok)
        print(f"    første kall: {t(oppvarming.total)} "
              f"(TTFT {t(oppvarming.ttft)}, {oppvarming.ut} tokens ut)"
              + (f" — servert av {oppvarming.oppstroms}" if oppvarming.oppstroms else ""),
              flush=True)

        maalinger = []
        for i in range(args.runder):
            m = kall(fullt, meldinger, maks, args.resonnering,
                     args.tidsavbrudd, args.forsok)
            maalinger.append(m)
            print(f"    runde {i + 1}/{args.runder}: {t(m.total)} "
                  f"(TTFT {t(m.ttft)}, {m.ut} tokens, "
                  f"{m.tokens_per_sek:.1f} tok/s)".replace(".", ","), flush=True)
            if m.avkuttet:
                print(f"    ⚠ avkuttet på {maks} tokens — hev taket for [{arbeid}]",
                      flush=True)

        resultat[arbeid] = {
            "oppvarming": oppvarming.total,
            "ttft": statistics.median(x.ttft for x in maalinger),
            "ttft_spenn": spenn([x.ttft for x in maalinger]),
            "ttfs": (statistics.median(x.ttfs for x in maalinger)
                     if all(x.ttfs is not None for x in maalinger) else None),
            "total": statistics.median(x.total for x in maalinger),
            "total_spenn": spenn([x.total for x in maalinger]),
            "tok_s": statistics.median(x.tokens_per_sek for x in maalinger),
            "ut": round(statistics.mean(x.ut for x in maalinger)),
            "res": round(statistics.mean(x.resonnering for x in maalinger)),
            "inn": maalinger[0].tokens_inn,
            "kostnad": sum(x.kostnad for x in maalinger) / len(maalinger),
            "pris_oppgitt": all(x.pris_oppgitt for x in maalinger),
            "oppstroms": next((x.oppstroms for x in maalinger if x.oppstroms), ""),
        }

    if args.parallell > 1:
        # Bulkjobbene er det disse modellene faktisk brukes til, og der er det
        # samlet gjennomstrømning som teller — ikke hvor raskt ett kall går.
        # NVIDIAs pulje har en hard grense på samtidige forespørsler som deles med
        # alle andre brukere (CLAUDE.md), så tallet her er ikke utledbart fra
        # enkeltkallet.
        meldinger, maks = ARBEID["kort"]
        print(f"\n  [parallell] {args.parallell} samtidige kall …", flush=True)
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallell) as pool:
            futures = [pool.submit(kall, fullt, meldinger, maks, args.resonnering,
                                   args.tidsavbrudd, args.forsok)
                       for _ in range(args.parallell)]
            samtidige = [f.result() for f in futures]
        vegg = time.perf_counter() - start
        resultat["parallell"] = {
            "antall": args.parallell,
            "vegg": vegg,
            "tok_s": sum(x.ut for x in samtidige) / vegg,
            "tregeste": max(x.total for x in samtidige),
        }
        print(f"    {args.parallell} kall på {t(vegg)} — "
              f"{resultat['parallell']['tok_s']:.1f} tokens/s samlet, "
              f"tregeste enkeltkall {t(resultat['parallell']['tregeste'])}"
              .replace(".", ","), flush=True)

    return resultat


def skriv_tabell(resultater: list[dict]) -> None:
    print(f"\n{'=' * 72}\nOPPSUMMERING — median av rundene\n{'=' * 72}")
    for arbeid in ARBEID:
        print(f"\n[{arbeid}]")
        print(f"  {'':<18}" + "".join(f"{r['navn']:>22}" for r in resultater))
        rader = [
            ("oppvarming", lambda d: t(d["oppvarming"])),
            ("TTFT", lambda d: f"{t(d['ttft'])} {d['ttft_spenn']}"),
            ("første svartoken", lambda d: t(d["ttfs"])),
            ("totaltid", lambda d: f"{t(d['total'])} {d['total_spenn']}"),
            ("tokens ut", lambda d: f"{d['ut']} (herav {d['res']} res.)"),
            ("tokens/s", lambda d: f"{d['tok_s']:.1f}".replace(".", ",")),
            ("pris per kall", lambda d: (f"${d['kostnad']:.5f}" if d["pris_oppgitt"]
                                         else "ikke oppgitt")),
            ("servert av", lambda d: d["oppstroms"] or "–"),
        ]
        for etikett, hent in rader:
            felt = "".join(f"{(hent(r[arbeid]) if arbeid in r else '–'):>22}"
                           for r in resultater)
            print(f"  {etikett:<18}{felt}")

    if any("parallell" in r for r in resultater):
        print("\n[parallell]")
        print(f"  {'':<18}" + "".join(f"{r['navn']:>22}" for r in resultater))
        for etikett, hent in [
            ("veggtid", lambda p: t(p["vegg"])),
            ("tokens/s samlet", lambda p: f"{p['tok_s']:.1f}".replace(".", ",")),
            ("tregeste kall", lambda p: t(p["tregeste"])),
        ]:
            felt = "".join(f"{(hent(r['parallell']) if 'parallell' in r else '–'):>22}"
                           for r in resultater)
            print(f"  {etikett:<18}{felt}")

    # Dommen, med tall — en tabell uten konklusjon blir lest som «omtrent likt».
    if len(resultater) == 2 and all("lang" in r for r in resultater):
        a, b = resultater
        for arbeid in ARBEID:
            rask, treg = sorted((a, b), key=lambda r: r[arbeid]["total"])
            faktor = treg[arbeid]["total"] / rask[arbeid]["total"]
            print(f"\n  [{arbeid}] {rask['navn']} er {faktor:.1f}×".replace(".", ",")
                  + f" raskere enn {treg['navn']} på totaltid "
                  f"({t(rask[arbeid]['total'])} mot {t(treg[arbeid]['total'])}).")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--modell", default=MODELL,
                   help=f"modellnavn UTEN leverandørprefiks (standard: {MODELL})")
    p.add_argument("--runder", type=int, default=3,
                   help="målte runder per arbeidsmengde, etter oppvarming (standard: 3)")
    p.add_argument("--parallell", type=int, default=1,
                   help="samtidige kall i egen bulktest (1 = hopp over)")
    p.add_argument("--resonnering", default="low", choices=["low", "medium", "high"],
                   help="reasoning_effort — gpt-oss tenker som standard (standard: low)")
    p.add_argument("--tidsavbrudd", type=int, default=180)
    p.add_argument("--forsok", type=int, default=3)
    p.add_argument("--bare", choices=["openrouter", "nvidia"],
                   help="mål bare én av leverandørene")
    args = p.parse_args()

    print(f"Modell: {args.modell} — resonnering «{args.resonnering}», "
          f"{args.runder} runder + 1 oppvarming per arbeidsmengde")

    resultater, feilet = [], []
    for navn, prefiks in LEVERANDORER:
        if args.bare and args.bare != (prefiks or "openrouter"):
            continue
        try:
            resultater.append(mal_leverandor(navn, prefiks, args.modell, args))
        except SystemExit as e:
            # En død leverandør skal ikke ta den andres tall med seg. Feilen
            # skrives ut her og gjentas i feilkoden til slutt.
            print(f"\n✗ {navn} feilet: {e}", flush=True)
            feilet.append(navn)

    if resultater:
        skriv_tabell(resultater)
    if feilet:
        print(f"\n✗ Ingen tall fra: {', '.join(feilet)}")
        return 1
    print("\n✓ Målingen fullført.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
