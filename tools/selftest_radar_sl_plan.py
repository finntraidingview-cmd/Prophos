#!/usr/bin/env python3
"""Selbsttest RADAR-SPANNE: SL/TP AUS DEM PLAN (21.10.2026, Master 04:35 Dubai, Radar Topstep 150k BUY 2 NQ, master_tp 2.419 /
master_sl 1.746: „hat der Plan ein master_sl (Topstep-Kette, Orbit mit SL), zeigt die Spanne ‚SL −1.746 $' rot links statt Liq,
TP = master_tp; Liq nur, wenn kein SL gesetzt ist; Tooltip nennt zusätzlich MLL/DLL des Kontos. Keine Regelprüfung, nur Anzeige.").
Aufruf:  python3 tools/selftest_radar_sl_plan.py
Prueft wdlSpanne (echt per osascript/JXA, aus prophos.html geschnitten): Beträge an den Enden = master_sl/master_tp statt gerundetes
Level × Punktwert; SL-Level notfalls aus master_sl gerechnet; Winning Days (sl_art 'liquidation') bleiben Liq; Apex-Tageslimit
unverändert; Echo unverändert; Tooltip-Texte in Radar- und Live-Trades-Zeile. Ohne Netz, Platzhalter-Werte."""
import json
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    m = re.search(r"  function " + name + r"\(t\)\{\n.*?\n  \}", HTML, re.S)
    return m.group(0) if m else None


SP, SLE = fn("wdlSpanne"), fn("wdlSlEcht")
check(bool(SP) and bool(SLE), "wdlSpanne + wdlSlEcht gefunden")
# Zeilen wie aus /admin/live-trades (Felder wie _lt_zeile), Platzhalter-Konten
TSX = {"route": "tsv2", "plattform": "orbit", "richtung": "buy", "kt": 2, "symbol_root": "NQ", "punktwert": 20, "einstieg_nq": 29757,
       "tp_level_nq": 29817.5, "sl_level_nq": 29713.25, "sl_art": "bracket", "master_tp": 2419, "master_sl": 1746,
       "liq_level_nq": 29592.89, "liq_regel_level_nq": 29682, "liq_regel_soft": True, "liq_gilt": "regel",
       "liq_regel_text": "Daily Loss 3.000 $ ab Tagesstart 156.564,58 $", "liq_boden_text": "MLL TopstepX 150.000,00 $",
       "liq_vergleich_text": "MLL TopstepX 150.000,00 $ → −6.565 $ · Regel: Daily Loss 3.000 $ ab Tagesstart 156.564,58 $ → −3.000 $ ✓ gilt"}
Z = {
    "bracket": TSX,
    "ohne_level": dict(TSX, sl_level_nq=None, sl_art=None),                       # Backend ohne SL-Level, Plan mit master_sl
    "sell_ohne_level": dict(TSX, richtung="sell", kt=3, einstieg_nq=29778.5, tp_level_nq=29735.75, sl_level_nq=None, sl_art=None, master_sl=1651, master_tp=2559),
    "wd": {"route": "tvv2", "plattform": "orbit", "richtung": "buy", "kt": 3, "symbol_root": "NQ", "einstieg_nq": 29756, "tp_level_nq": 29783.25,
           "sl_level_nq": 29600, "sl_art": "liquidation", "master_tp": 164, "master_sl": None, "liq_level_nq": 29600},
    "apex_tag": {"route": "tvv2", "plattform": "orbit", "richtung": "buy", "kt": 2, "symbol_root": "NQ", "einstieg_nq": 29700, "tp_level_nq": 29760,
                 "sl_level_nq": None, "sl_art": None, "master_tp": 2400, "master_sl": None, "liq_regel_level_nq": 29650, "liq_level_nq": 29600,
                 "liq_regel_soft": True, "liq_gilt": "regel", "liq_regel_text": "Apex Daily Loss 2.000 $"},
    "kein_einstieg": dict(TSX, einstieg_nq=None, sl_level_nq=None, sl_art=None, liq_level_nq=None, liq_regel_level_nq=None),
    "echo": {"plattform": "echo", "sl_level": 24000, "tp_level": 24100, "einstieg": 24050, "pl_bei_sl": -500, "pl_bei_tp": 500, "master_sl": 999, "master_tp": 999},
    "mnq_ohne_plan": {"route": "tvv2", "plattform": "orbit", "richtung": "buy", "kt": 5, "symbol_root": "MNQ", "einstieg_nq": 29700, "tp_level_nq": 29750,
                      "sl_level_nq": 29650, "sl_art": "master_sl", "master_tp": None, "master_sl": None},
}
if SP and SLE and shutil.which("osascript"):
    js = ("var wdlIstEcho = function(t){ return !!t && t.plattform === 'echo' };\nvar mklPpl = function(s){ return s === 'NQ' ? 20 : 2 };\n"
          "var wdlLiqIstTag = function(t){ return !!(t && t.liq_regel_soft && t.liq_gilt === 'regel') };\n" + SLE + "\n" + SP + "\nvar Z = " + json.dumps(Z, ensure_ascii=False)
          + ";\nvar out = {}; Object.keys(Z).forEach(function(k){ out[k] = wdlSpanne(Z[k]) }); JSON.stringify(out)")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout.strip())
    except ValueError:
        v = None
    check(isinstance(v, dict), f"wdlSpanne läuft ({(r.stderr or '').strip()[:160]})")
    if isinstance(v, dict):
        b = v["bracket"]
        check(b and b["art"] == "SL" and b["links"] == 29713.25 and b["rechts"] == 29817.5, f"Topstep-Bracket: SL vorn, Level unverändert — {b}")
        check(b and b["plLinks"] == -1746 and b["plRechts"] == 2419, f"Beträge vom Plan: −1.746 / +2.419 (statt −1.750 / +2.420 aus dem Level) — {b and (b['plLinks'], b['plRechts'])}")
        check(b and b["regel"].startswith("Konto: MLL TopstepX 150.000,00 $") and "Daily Loss 3.000 $" in b["regel"] and b["regelPur"] is True, f"Tooltip nennt MLL + DLL hinter dem SL — {b and b['regel']}")
        o = v["ohne_level"]
        check(o and o["art"] == "SL" and abs(o["links"] - 29713.35) < 0.01 and o["plLinks"] == -1746, f"kein SL-Level vom Backend, master_sl am Plan → Level aus master_sl gerechnet (BUY: Einstieg − 1.746/40) — {o}")
        s_ = v["sell_ohne_level"]
        check(s_ and s_["art"] == "SL" and abs(s_["links"] - (29778.5 + 1651 / 60)) < 0.01 and s_["plLinks"] == -1651 and s_["plRechts"] == 2559, f"SELL 3 NQ: SL-Level über dem Einstieg, Beträge vom Plan — {s_}")
        w = v["wd"]
        check(w and w["art"] == "Liq" and w["links"] == 29600 and w["plLinks"] == -9360 and w["plRechts"] == 164 and w["regel"] == "", f"Winning Day (sl_art liquidation, kein master_sl): bleibt Liq, Betrag aus dem Level, TP vom Plan — {w}")
        a = v["apex_tag"]
        check(a and a["art"] == "Tag" and a["links"] == 29650 and a["plLinks"] == -2000 and a["regel"] == "Apex Daily Loss 2.000 $" and a["regelPur"] is False, f'Apex-Tageslimit ohne SL: unverändert Tag mit Regel-Text — {a}')
        check(v["kein_einstieg"] is None, "ohne Einstieg und ohne Level: keine Spanne (wie bisher)")
        e = v["echo"]
        check(e and e["art"] == "SL" and e["plLinks"] == -500 and e["plRechts"] == 500, f"Echo: unverändert aus pl_bei_sl/pl_bei_tp, master_* ignoriert — {e}")
        m = v["mnq_ohne_plan"]
        check(m and m["art"] == "SL" and m["plLinks"] == -500 and m["plRechts"] == 500, f"ohne master_tp/master_sl: Beträge wie bisher aus dem Level (MNQ 2 $ × 5) — {m}")
else:
    print("… osascript fehlt — nur Textprüfungen")

# Tooltips: Radar-Zeile (zeile()) und Live-Trades-Zeile tragen den Konto-Zusatz; Kommentar nennt den Anlass + „Nur Anzeige"
check(HTML.count("${sp.regel ? (sp.regelPur ? ' · ' : ' · Regel: ') + sp.regel : ''}") == 2, "Tooltip mit sp.regel in Radar-Zeile UND Live-Trades-Zeile")
i = HTML.find("SL/TP AUS DEM PLAN (21.10.2026")
check(i > 0 and "Nur Anzeige" in HTML[i:i + 1400] and "Winning Days (sl_art 'liquidation'" in HTML[i:i + 1400], "Kommentar: Anlass, Winning Days bleiben Liq, nur Anzeige")
check("const slFb = (slE == null && slPlan != null && t.sl_art !== 'liquidation' && ein != null && kt && ppl && ri)" in HTML, "Rückfall-Level nur mit master_sl, Einstieg, Kontrakten, Punktwert, Richtung — nie bei 'liquidation'")

# ENDE AM SL (21.10.2026): der PC-Tab benennt ein Demo-Ende am echten SL als 'demo_sl' (Backend stop 'sl'), 'demo_liq' nur ohne SL
check("(dm.stop === 'sl' ? 'demo_sl' : 'demo_liq')" in HTML, "PC-Tab: Demo-Ende am SL → grund 'demo_sl', sonst 'demo_liq'")
check("const tvV2LiqUndWeg = f => !!(f && f.grund === 'demo_liq' &&" in HTML, "liquidiert + Konto weg bleibt auf 'demo_liq' (SL-Ende ist kein Blow)")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
