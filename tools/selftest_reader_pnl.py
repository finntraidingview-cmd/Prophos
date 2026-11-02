#!/usr/bin/env python3
"""Selbsttest READER-BLIND-PNL (02.11.2026, Plan 7bbb63d4): leerer P&L macht den Puls-Chrome nicht blind, wenn Symbol, Seite und Menge lesbar sind. Ohne Netz, jsc.
Aufruf: python3 tools/selftest_reader_pnl.py"""
import json
import os
import subprocess
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
US = open(os.path.join(WURZEL, "tv-reader", "tv-reader.user.js"), encoding="utf-8").read()
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    i = US.index(f"function {name}(")
    j = US.index("{", US.index(")", i))
    t = 0
    for k in range(j, len(US)):
        t += {"{": 1, "}": -1}.get(US[k], 0)
        if t == 0:
            return US[i:k + 1]
    raise ValueError(name)


JS = "\n".join([US[US.index("  const SPALTEN = {"):US.index("  function feld(")], US[US.index("  const ORDER_MERKMALE"):US.index("  function positionenAusZeilen(")],
                US[US.index("  const RX_KURS_SYMBOL"):].split("\n")[0]] + [fn(n) for n in ("feld", "positionenAusZeilen", "seiteNorm", "zahlAusText", "kursWurzelAusText", "unklarBlind")] + [r"""
const L = (...a) => new Set(a)
print(JSON.stringify({
  leer: positionenAusZeilen([{ Symbol: 'MNQZ6', Side: 'Buy', Qty: '2', Profit: '' }], L('Symbol', 'Side', 'Qty', 'Profit'), 1),
  ohne: positionenAusZeilen([{ Symbol: 'MNQZ6', Side: 'Buy', Qty: '2' }], L('Symbol', 'Side', 'Qty'), 1),
  seite: positionenAusZeilen([{ Symbol: 'MNQZ6', Qty: '2' }], L('Symbol', 'Qty'), 1),
  da: positionenAusZeilen([{ Symbol: 'MNQZ6', Side: 'Buy', Qty: '2', Profit: '+1,00 USD' }], L('Symbol', 'Side', 'Qty', 'Profit'), 1),
  b_reiter: unklarBlind({ unklar: 1, unklar_fest: 0 }, true),
  b_anderer: unklarBlind({ unklar: 1, unklar_fest: 0 }, false),
  b_fest: unklarBlind({ unklar: 2, unklar_fest: 1 }, true),
  b_nichts: unklarBlind({ unklar: 0, unklar_fest: 0 }, false),
  order: positionenAusZeilen([{ Symbol: 'MNQZ6', Side: 'Buy', Qty: '2', Status: 'Working' }], L('Symbol', 'Side', 'Qty', 'Status'), 1),
}))
"""])
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
e = json.loads(r.stdout.strip().splitlines()[-1])
a = e["leer"]
check(a["unklar"] == 1 and a["unklarFest"] == 0 and a["positionen"][0]["menge_zahl"] == 2 and a["positionen"][0]["wurzel"] == "MNQ" and a["positionen"][0]["pnl_unklar"], "P&L leer, Position lesbar: bleibt Position, nicht blind")
check(a["positionen"][0]["pnl_beleg"] == {"gefuellt": "Symbol|Side|Qty", "alle": "Symbol|Side|Qty|Profit"} and "_spalten" not in a["positionen"][0], "Beleg nennt gefüllte und alle Spalten")
check(e["ohne"]["unklarFest"] == 0 and e["ohne"]["positionen"][0]["pnl_beleg"]["alle"] == "Symbol|Side|Qty", "Spalte fehlt ganz: ebenso")
check(e["seite"]["unklarFest"] == 1, "Seite nicht lesbar: weiter blind")
check(e["da"]["unklar"] == 0 and "pnl_beleg" not in e["da"]["positionen"][0], "P&L da: unverändert")
check(e["order"]["positionen"] == [], "Order-Zeile fällt weiter raus")
check(e["b_reiter"] == 0 and e["b_anderer"] == 1 and e["b_fest"] == 1 and e["b_nichts"] == 0, "nicht blind nur bei Reiter Positions und lesbarer Zeile")
check("const nBlind = unklarBlind(leseBefund, reiterPos);" in US and "if (leseBefund.unklar) return leseBefund.pnl_spalte" in US, "blindGrund nutzt das; außerhalb des Puls-Chrome unverändert")
print("\nREADER-BLIND-PNL: alles grün" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
