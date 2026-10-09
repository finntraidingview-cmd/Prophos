#!/usr/bin/env python3
"""Selbsttest TOPSTEPX POSITIONS-BEREICH ABWARTEN (09.10.2026, Terminal 2 — Ina DLL-Konto 333d4791, 08:19 Dubai: Konto + BAL korrekt,
„Positions-Bereich in TopstepX nicht sichtbar", nichts platziert). Geprüft: order_bot.py liest bei tabelle_unklar ohne Positions-Bereich
gedrosselt nach (feste Anzahl, Lesefehler → letzter Befund), schreibt sonst das Inventar (TSX_POS_INVENTAR_JS, ohne account-testids) in
ergebnis.diagnose; augen_tsx.js: RX_KEINE_POS mit Varianten (Syntax = Python re), Text-Rückfall keinePosPerText, leeres Grid + Close-Position
gesperrt = flach. Aufruf: python3 tools/selftest_tsx_pos_warten.py"""
import json
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    bot = open(os.path.join(HIER, "..", "mt5-copier", "order_bot.py"), encoding="utf-8").read()
    js = open(os.path.join(HIER, "..", "mt5-copier", "augen_tsx.js"), encoding="utf-8").read()

    i = bot.index('if code == "tabelle_unklar" and isinstance(st, dict) and st.get("positionen_sichtbar") is not True:')
    block = bot[i:i + 2200]
    check("for _n in range(8):" in block and "_warte(0.9, 0.4)" in block and "time.time()" not in block,
          "Nachlesen: feste Anzahl (8×), gedrosselt über _warte, nicht an der Uhr")
    check("except Exception:\n                    break" in block, "Lesefehler beim Nachlesen → letzter ehrlicher Befund bleibt")
    check('res["diagnose"] = {"tsx_positionen_inventar": inv}' in block and "TSX_POS_INVENTAR_JS" in block,
          "Inventar nur bei weiterem Fehlschlag, landet in ergebnis.diagnose")
    m = re.search(r'TSX_POS_INVENTAR_JS = r"""(.*?)"""', bot, re.S)
    inv = m.group(1) if m else ""
    check("/account/i.test(t)" in inv and ".click(" not in inv and ".value =" not in inv and "dispatchEvent" not in inv,
          "Inventar-JS: Konto-Auslöser ausgenommen, nur Lesen")
    check(bot.index("for _n in range(8):") < bot.index("res.update(felder)", i), "Nachlesen vor der Übernahme der Felder")

    rx = re.search(r"var RX_KEINE_POS = /(.+)/i;", js).group(1)
    r = re.compile(rx, re.I)
    for t in ("No Active Position", "No open position", "No positions", "No position", "Keine aktive Position"):
        check(bool(r.search(t)), f"RX_KEINE_POS erkennt „{t}“")
    check(not r.search("Close Position") and not r.search("Positions"), "RX_KEINE_POS: „Close Position“/„Positions“ nicht")
    check("var keine = ankerPositionen() || keinePosPerText();" in js, "positionenLesen: Text-Rückfall ohne data-testid")
    check("if (g.da && !g.zeilen.length && zuK && zustand(zuK).disabled) return { sichtbar: true, zeilen: [], flach: true };" in js,
          "leeres Positions-Grid + Close Position gesperrt = flach (zwei Belege)")
    check("catch (_) { pz = 1; }" in js and "Array.isArray(pzL) ? pzL.length : 1" in js, "positionsZeilen wirft/kein Array → pz 1 (unklar → nie flach)")
    check("keine.closest('[data-testid^=\"order-card\"]')" in js and "inKarte: inKarte" in js, "inKarte nur aus der Order-Karte, nie Seiten-Text")
    check('res["diagnose"] = {"tsx_positionen_inventar": inv}' in bot and "o.close = { quelle: kq" in bot and "o.keine_pos" in bot,
          "Inventar mit Close-Knopf-Details + „No Active Position“-Quelle")

    # flachBeweis per JXA ausführen (macOS) — Positiv- und Negativfälle
    i = js.index("  function flachBeweis(b) {")
    fsrc = js[i:js.index("\n  }\n", i) + 4]
    faelle = [
        ("Karte + Close disabled → flach", {"keine": True, "inKarte": True, "zu": {"disabled": True}}, True),
        ("Karte + Close aria-disabled → flach", {"keine": True, "inKarte": True, "zu": {"aria": True}}, True),
        ("Karte + Close pointer-events none → flach", {"keine": True, "inKarte": True, "zu": {"pe": "none"}}, True),
        ("Karte + Close Deckkraft 0,38 → flach", {"keine": True, "inKarte": True, "zu": {"opacity": 0.38}}, True),
        ("Karte + Close fehlt → flach", {"keine": True, "inKarte": True, "zu": None}, True),
        ("Seiten-Text + Grid 0 Zeilen + Close fehlt → flach (Grid-Beleg)", {"keine": True, "inKarte": False, "zu": None, "grid": {"da": True, "zeilen": 0}}, True),
        ("NEG: Karte fehlt + Seiten-Text „No positions“ + Close fehlt → NICHT flach", {"keine": True, "inKarte": False, "zu": None}, None),
        ("NEG: Close aktiv (Position offen) → nie flach", {"keine": True, "inKarte": True, "zu": {"disabled": False, "opacity": 1, "pe": "auto"}}, None),
        ("NEG: Close aktiv + Grid 0 Zeilen → nie flach", {"keine": True, "inKarte": True, "zu": {"opacity": 1}, "grid": {"da": True, "zeilen": 0}}, None),
        ("NEG: Positionszeile im Grid + Close gesperrt → nie flach", {"keine": True, "inKarte": True, "zu": {"disabled": True}, "grid": {"da": True, "zeilen": 1}}, None),
        ("NEG: ohne „No Active Position“ → nie flach", {"keine": False, "inKarte": True, "zu": {"disabled": True}}, None),
        ("NEG: Seiten-Text + opacity 0,3 + nicht in der Karte → nicht flach", {"keine": True, "inKarte": False, "zu": {"opacity": 0.3}}, None),
        ("NEG: Seiten-Text + pointer-events none + nicht in der Karte → nicht flach", {"keine": True, "inKarte": False, "zu": {"pe": "none"}}, None),
        ("NEG: positionsZeilen 1 (ohne Grid) + Close gesperrt → nie flach", {"keine": True, "inKarte": True, "posZeilen": 1, "zu": {"disabled": True}}, None),
        ("NEG: Klasse „…-disabled-false“ zählt nicht als gesperrt", {"keine": True, "inKarte": True, "zu": {"klasse": "x-btn-disabledfalse foo"}}, None),
        ("Seiten-Text + echtes disabled → flach", {"keine": True, "inKarte": False, "zu": {"disabled": True}}, True),
        ("Karte + Klasse Mui-disabled → flach", {"keine": True, "inKarte": True, "zu": {"klasse": "MuiButton-root Mui-disabled"}}, True),
    ]
    prog = fsrc + "\nJSON.stringify(" + json.dumps([f[1] for f in faelle]) + ".map(function (b) { var r = flachBeweis(b); return r === undefined ? null : r; }))"
    try:
        out = subprocess.run(["osascript", "-l", "JavaScript", "-e", prog], capture_output=True, text=True, timeout=20).stdout.strip()
        erg = json.loads(out)
    except Exception as e:
        erg = None
        check(False, f"JXA nicht ausführbar ({type(e).__name__})")
    if erg is not None:
        for (name, _b, soll), ist in zip(faelle, erg):
            check(ist == soll, f"flachBeweis: {name} ({ist})")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
