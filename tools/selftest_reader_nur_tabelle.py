#!/usr/bin/env python3
"""Selbsttest Userscript 0.10.9 NUR DIE POSITIONS-TABELLE (02.11.2026, Finn-Test Simon 69900aaa: Schluss 37 s zu spät, Lotse-Spur mit Orders-Zeilen im selben Dokument).
lesePositionen liest im Puls-Chrome nur Zeilen aus SEL_POS_TABELLE bei aktivem Reiter Positions; außerhalb des Puls-Chrome wie bisher das ganze Dokument. Der Takt läuft im
Puls-Chrome nur auf /chart/-Seiten. Ohne Netz, jsc. Aufruf: python3 tools/selftest_reader_nur_tabelle.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
US = open(os.path.join(W, "tv-reader", "tv-reader.user.js"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    t = 0
    for k in range(j, len(src)):
        t += {"{": 1, "}": -1}.get(src[k], 0)
        if t == 0:
            return src[i:k + 1]
    raise ValueError(name)


JS = "\n".join([
    "const SEL_POS_TABELLE = 'table[data-name$=\"positions-table\"]'",
    "let PULS_CHROME = true, spaltenGesehen = [], spracheFremd = false, leseBefund = null",
    "const tabelleDa = () => true",
    "const positionenAusZeilen = (z) => ({ positionen: z, unklar: 0, unklarFest: 0, pnlSpalte: true })",
    fn(US, "zellText"), fn(US, "lesePositionen"), r"""
// kleines DOM: Zeilen sind {tr, label, text}; eine Tabelle sammelt ihre td, das Dokument alle
const td = (tr, label, text) => ({ tr, getAttribute: () => label, textContent: text, closest: () => tr })
const tabelle = (tds) => ({ querySelectorAll: () => tds })
function welt(o){
  const p1 = {}, o1 = {}, o2 = {}
  const pos = o.position ? [td(p1, 'Symbol', 'MNQZ6'), td(p1, 'Side', 'Sell'), td(p1, 'Qty', '1'), td(p1, 'Profit', '')] : []
  const ord = [td(o1, 'Symbol', 'MNQZ6'), td(o1, 'Status', 'filled'), td(o2, 'Symbol', 'MNQZ6'), td(o2, 'Status', 'working')]
  const posTab = o.tabelle === false ? null : tabelle(pos)
  globalThis.document = {
    getElementById: id => id === 'positions' ? { getAttribute: () => (o.reiter === false ? 'false' : 'true') } : null,
    querySelector: s => s === SEL_POS_TABELLE ? posTab : null,
    querySelectorAll: () => pos.concat(ord),
  }
}
const lauf = (o) => { PULS_CHROME = o.puls !== false; welt(o); const p = lesePositionen(); return { n: p.length, zeilen: leseBefund.zeilen } }
const o = {
  flach_mit_orders: lauf({}), position: lauf({ position: true }), reiter_aus: lauf({ position: true, reiter: false }),
  ohne_tabelle: lauf({ tabelle: false }), ausserhalb_puls: lauf({ puls: false }),
}
print(JSON.stringify(o))
"""])
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1])
check(o["flach_mit_orders"] == {"n": 0, "zeilen": 0}, "Simon nach dem Schluss: leere Positions-Tabelle, Orders-Zeilen daneben → 0 Zeilen, Tabelle kann als flach gelten")
check(o["position"] == {"n": 1, "zeilen": 1}, "offene Position in der Tabelle wird gelesen (auch mit leerem Profit)")
check(o["reiter_aus"] == {"n": 0, "zeilen": 0}, "Reiter Positions nicht aktiv → keine Zeile; blindGrund meldet den Reiter, nie flach")
check(o["ohne_tabelle"] == {"n": 0, "zeilen": 0}, "keine Positions-Tabelle → keine Zeile")
check(o["ausserhalb_puls"]["zeilen"] == 2, "außerhalb des Puls-Chrome wie bisher das ganze Dokument")
check("if (PULS_CHROME && !/^\\/chart(\\/|$)/.test(location.pathname))" in US and US.index("keine Chart-Seite, Reader aus") < US.index("if ((tickNr % BF_JEDER) === 0) liesKonto();"),
      "Puls-Chrome: Takt nur auf /chart/-Seiten, vor dem Lesen und Senden")
check("tabelleOk = reiterAn && tabelleFlach(leseBefund, document.querySelector(SEL_POS_TABELLE))" in US, "Flach-Beweis unverändert: Reiter + leere Tabelle, jetzt ohne fremde Zeilen")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
