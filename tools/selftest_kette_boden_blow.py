#!/usr/bin/env python3
"""Selbsttest GEBLOWT AM TAGESENDE DER TAGESTEILUNG (19.11.2026, Slave Terminal 29 — Finn per Screenshot Radar → Erledigt: „es soll ja eine eigene
Spalte geben mit geblowten Accounts … der war bei Abhaken Challenges, nicht bei geblowt"). Fall Simon FundedNext 100k …1696, Plan 5bb7caa4: Echo mit
Fusion-Hedge, Tagesteilung (kette von 2, nr 1), Tagesende „Balance auf/unter dem Boden — geblowt?", kette_tag.blown false, Balance 89.932,96 $ bei
Boden 90.000 $. Ursache: an Zeilen mit kette_tag entschied allein kette_tag.blown, das app.py tt_tick nur für Topstep (tsv2) rechnet.

Ohne Netz und ohne Node: wdlKetteBodenBlow, wdlBlowStand, wdlGeblowtUrteil per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten. Geprüft:
1. Simons Zeile (echte Werte) → geblowt (Gruppe „Geblowt · archivieren", Vorbelegung, Ergebnis-Wort über wdlBlowStand)
2. Grenzen: knapp über dem Boden → nicht; ohne Boden → nicht (nicht raten); Balance 0 → nicht
3. Topstep-Kette (tsv2) und Orbit-Tagesteilung (tvv2, nachziehender Boden): weiter nur kette_tag.blown — auch unter dem Boden nicht geblowt
4. BITGLEICH: eine Matrix aus Zeilen OHNE kette_tag (Tradeify Liq-Regel, Echo am Boden, Tageslimit, Konto weg, TP + weg = bestanden, Topstep-
   Schätzung, abgehakt geblowt …) und Topstep-Ketten liefert mit dem alten Stand (git origin/main) dasselbe Urteil und denselben wdlBlowStand.
Alle Kennungen außer Simons Werten erfunden. Aufruf: python3 tools/selftest_kette_boden_blow.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
HTML = os.path.join(WURZEL, "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_abhaken_geblowt_vorbelegen.py)."""
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


def schneiden(html):
    teile = [re.search(r"^\s*const TV_LIQ_WEG_MIN = .*$", html, re.M).group(0), js_funktion(html, "wdlTpUndWeg"),
             re.search(r"^\s*const wdlKontoWeg = .*$", html, re.M).group(0),
             re.search(r"^\s*const WDL_TSX_SCHAETZ_TIP = .*$", html, re.M).group(0), js_funktion(html, "wdlTsxBlowSchaetzung")]
    if "function wdlKetteBodenBlow(" in html:
        teile.append(js_funktion(html, "wdlKetteBodenBlow"))
    return "\n".join(teile + [js_funktion(html, "wdlBlowStand"), js_funktion(html, "wdlGeblowtUrteil")])


JS_TEST = r"""
function tvV2KontoWeg(e){ return !!(e && e.konto_weg) }
function tvV2KontoVermutetOffen(e){ return false }
const F = %s
print(JSON.stringify(F.map(z => { const b = wdlBlowStand(z); return { u: wdlGeblowtUrteil(z), b: b ? { bal: b.bal, quelle: b.quelle, liq: b.liq, tagLiq: b.tagLiq, geblowt: b.geblowt, vonBoden: b.vonBoden, softBreach: b.softBreach, geschaetzt: !!b.geschaetzt } : null } })))
"""


def laufen(html, zeilen):
    js = schneiden(html) + JS_TEST % json.dumps(zeilen)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    if r.returncode != 0:
        print("✗ jsc:", (r.stdout + r.stderr)[-800:])
        sys.exit(1)
    return json.loads(r.stdout.strip().splitlines()[-1])


# Simons Zeile, wie /admin/live-trades sie liefert (Supabase 19.11.2026: final.master_balance, mt5_baseline.master_balance, kette.tagesende)
SIMON_KT = {"at": "2026-11-19T06:33:07.457609Z", "blown": False, "t1_pl": -3055.8, "t2_pl": None, "tag_pl": -3055.8, "trades": 1,
            "balance": 89932.96, "ende_text": "Balance auf/unter dem Boden — geblowt?", "ende_grund": "verlust", "fusion_sum": 253.54,
            "teile": [{"nr": 1, "pl": -3055.8, "rolle": "haupt", "fusion": 253.54, "richtung": "sell"}]}
SIMON = {"route": "mt5", "status": "review", "blown": False, "konto_typ": "phase2", "ended_at": "2026-11-19T06:32:08.299Z",
         "balance_start": 92988.76, "balance_end": 89932.96, "pl_balance": -3055.8, "boden_usd": 90000, "liq_balance": None,
         "liq_regel_balance": None, "kette_tag": SIMON_KT}


def mit(z, **kw):
    return dict(z, **kw)


def kt(**kw):
    return dict(SIMON_KT, **kw)


NEU = [  # (name, Zeile, Urteil erwartet)
    ("Simon FundedNext …1696 (Echo-Tagesteilung, 89.932,96 ≤ Boden 90.000) → geblowt", SIMON, True),
    ("gleiche Zeile, Tagesende 90.000,01 → nicht geblowt", mit(SIMON, balance_end=90000.01, kette_tag=kt(balance=90000.01)), False),
    ("genau am Boden (90.000) → geblowt (≤ wie der Boden-Rückfall)", mit(SIMON, balance_end=90000, kette_tag=kt(balance=90000)), True),
    ("ohne Boden an der Zeile → nicht geblowt (nicht raten)", mit(SIMON, boden_usd=None), False),
    ("Tagesende ohne Balance → Balance der Zeile zählt", mit(SIMON, kette_tag=kt(balance=None)), True),
    ("Zeile ohne Balance → Balance am Tagesende zählt", mit(SIMON, balance_end=None), True),
    ("Balance der Zeile vor kette_tag.balance (Zeile über dem Boden) → nicht", mit(SIMON, balance_end=90500), False),
    ("Echo V2 (mt5v2) Tagesteilung unter dem Boden → geblowt", mit(SIMON, route="mt5v2"), True),
    ("Balance 0 (nicht gelesen) → nicht geblowt", mit(SIMON, balance_end=0, kette_tag=kt(balance=0)), False),
    ("Orbit-V2-Tagesteilung (tvv2) unter dem heutigen Boden → weiter nicht (Boden zieht nach, nur kette_tag.blown)",
     mit(SIMON, route="tvv2", boden_usd=145500, balance_end=145400, kette_tag=kt(balance=145400)), False),
    ("Topstep-Kette (tsv2) unter dem Boden, Backend blown false → weiter nicht geblowt",
     mit(SIMON, route="tsv2", boden_usd=146000, liq_balance=146000, balance_end=145900, kette_tag=kt(balance=145900)), False),
    ("Topstep-Kette (tsv2) Backend blown true → geblowt",
     mit(SIMON, route="tsv2", boden_usd=146000, balance_end=145900, kette_tag=kt(balance=145900, blown=True)), True),
    ("Plan abgehakt geblowt (blown true) → geblowt", mit(SIMON, blown=True, balance_end=95000, kette_tag=kt(balance=95000)), True),
]

ZU = {"status": "review", "ended_at": "2026-11-19T06:32:00Z"}
GLEICH = [  # Zeilen, deren Urteil und wdlBlowStand bitgleich zum alten Stand bleiben müssen
    dict(ZU, route="tvv2", balance_start=153462.72, balance_end=148921.2, liq_regel_balance=148962.72, liq_boden_balance=145500, boden_usd=145500, liq_gilt="regel"),
    dict(ZU, route="tvv2", balance_start=153462.72, balance_end=149162.72, liq_regel_balance=148962.72, liq_boden_balance=145500),
    dict(ZU, route="tvv2", balance_start=150000, balance_end=147981, liq_regel_balance=147981, liq_regel_soft=True, liq_regel_nur_balance=147981, liq_boden_balance=146000),
    dict(ZU, route="mt5v2", balance_end=89942, boden_usd=90000),
    dict(ZU, route="mt5", balance_start=92988.76, balance_end=89932.96, boden_usd=90000),
    dict(ZU, route="mt5", balance_start=92988.76, balance_end=95000, boden_usd=90000),
    dict(ZU, blown=True, balance_end=151000, liq_regel_balance=145500),
    dict(ZU, route="tvv2", endlesung={"konto_weg": True}, liq_regel_balance=145500),
    dict(ZU, route="tvv2", endlesung={"konto_weg": True, "tp": True}, liq_regel_balance=145500, balance_end=153000),
    {"status": "open", "balance_end": 140000, "liq_regel_balance": 145500},
    {"status": "review", "route": "tsv2", "balance_start": 151583.42, "liq_balance": 149947.32, "liq_quelle": "mll_tsx",
     "endlesung": {"grund": "tsx_geblowt", "konto_geblowt": {"art": "maximum_loss"}}},
    dict(ZU, route="tsv2", balance_start=150000, balance_end=145900, liq_balance=146000, boden_usd=146000,
         kette_tag={"blown": False, "balance": 145900, "trades": 2, "tag_pl": -4100}),
    dict(ZU, route="tsv2", balance_start=150000, balance_end=145900, liq_balance=146000,
         kette_tag={"blown": True, "balance": 145900, "trades": 2, "tag_pl": -4100}),
    dict(ZU, route="tsv2", balance_start=150000, balance_end=151000, liq_balance=146000,
         kette_tag={"blown": False, "balance": 151000, "trades": 1, "tag_pl": 1000}),
    # Tagesteilung über dem Boden (Echo/Orbit): alt wie neu nicht geblowt
    dict(SIMON, balance_end=95000, kette_tag=kt(balance=95000)),
    dict(SIMON, route="tvv2", boden_usd=145500, balance_end=148900, kette_tag=kt(balance=148900)),
    dict(SIMON, route="tvv2", boden_usd=150500, balance_end=150400, kette_tag=kt(balance=150400)),   # Orbit unter nachgezogenem Boden: bleibt wie bisher
    dict(SIMON, kette_tag=True),   # fdp_pump_tick schreibt tagesende als Boolean
]


def main():
    if not os.path.exists(JSC):
        print("✗ jsc fehlt — Frontend-Teil nicht ausführbar")
        sys.exit(1)
    html = open(HTML, encoding="utf-8").read()
    aus = laufen(html, [z for _n, z, _s in NEU])
    for (name, _z, soll), ist in zip(NEU, aus):
        check(ist["u"] is soll, f"wdlGeblowtUrteil {name}: {ist['u']}")
    check(aus[0]["b"] and aus[0]["b"]["geblowt"] is True and aus[0]["b"]["bal"] == 89932.96,
          "wdlBlowStand Simon: geblowt + Balance 89.932,96 (Ergebnis-Wort/Konto-Spalte stimmen mit der Gruppe überein)")

    try:
        alt_html = subprocess.run(["git", "-C", WURZEL, "show", "origin/main:prophos.html"], capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        print("✗ git show origin/main:prophos.html:", e.stderr[-300:])
        sys.exit(1)
    if "function wdlKetteBodenBlow(" in alt_html:
        print("· origin/main hat den Fix schon — Bitgleich-Vergleich gegen den Stand davor übersprungen (Fälle oben gelten weiter)")
    else:
        a_alt, a_neu = laufen(alt_html, GLEICH), laufen(html, GLEICH)
        for i, (x, y) in enumerate(zip(a_alt, a_neu)):
            check(x == y, f"bitgleich zum alten Stand, Zeile {i + 1} ({GLEICH[i].get('route') or '-'}{' · kette' if GLEICH[i].get('kette_tag') else ''}): {y['u']}")
        a_simon = laufen(alt_html, [SIMON])[0]
        check(a_simon["u"] is False, "Gegenprobe: der alte Stand urteilt bei Simon „nicht geblowt“ (der gemeldete Fehler)")

    check("const istGeblowt = wdlGeblowtUrteil" in html, "Radar-Gruppe „Geblowt · archivieren“ fragt weiter wdlGeblowtUrteil")
    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("ALLES GRÜN")


if __name__ == "__main__":
    main()
