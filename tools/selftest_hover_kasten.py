#!/usr/bin/env python3
"""Selbsttest HOVER-BEWEIS NUR IM EIGENEN KNOPF (09.10.2026, Terminal 2 — Prüfer T3 zu .1442 / Routine-Commit 5a0ca2b: ein kleiner
:hover-Vorfahr des Blatts zählte als Beweis, auch wenn er ein BEHÄLTER mit eigenem Knopf darin ist — Werbe-Kachel mit X, Konto-Zeile mit ⋮,
Toast mit „Show more“; der Druck träfe den Behälter). Jetzt muss der :hover-Knoten im nächsten klickbaren Vorfahren des Blatts liegen.
Führt WIN_HOVER_ELTERN_JS per JXA (osascript) gegen ein nachgebautes DOM aus. Aufruf: python3 tools/selftest_hover_kasten.py"""
import json
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# Mini-DOM: Knoten {tag, attr, w, h, kinder}; hover = Pfad der :hover-Knoten (Wurzel → tiefster), e = Blatt am Punkt
DOM_JS = r"""
function N(tag, attr, w, h, kinder){ var n = { tagName: tag.toUpperCase(), _attr: attr || {}, _w: w, _h: h, kinder: kinder || [], parent: null, textContent: '' };
  n.kinder.forEach(function(k){ k.parent = n }); return n }
function istIn(a, b){ for(var x = b; x; x = x.parent) if(x === a) return true; return false }
function SEL(n, s){ var t = n.tagName.toLowerCase(), a = n._attr;
  return s.split(',').some(function(q){ q = q.trim();
    if(q === t) return true;
    var m = /^\[([a-z-]+)(?:=([a-z]+))?\]$/.exec(q); if(m) return m[2] ? a[m[1]] === m[2] : (m[1] in a);
    return false }) }
function bau(n){
  n.contains = function(x){ return istIn(n, x) };
  n.getAttribute = function(k){ return k in n._attr ? n._attr[k] : null };
  n.getBoundingClientRect = function(){ return { left: 0, top: 0, width: n._w, height: n._h } };
  n.closest = function(s){ for(var x = n; x; x = x.parent) if(SEL(x, s)) return x; return null };
  n.matches = function(s){ return s === ':hover' ? HOVER.indexOf(n) >= 0 : SEL(n, s) };
  n.kinder.forEach(bau) }
var HOVER = [];
var document = { querySelectorAll: function(s){ return HOVER } };
function fall(wurzel, hoverPfad, e){ bau(wurzel); HOVER = hoverPfad; return AUSDRUCK }
"""


def main():
    import order_bot as ob
    expr = ob.WIN_HOVER_ELTERN_JS
    check("e.closest('button,a,[role=button],[role=tab],[role=menuitem],[role=option],[role=row],[data-role=list-item],[tabindex]')" in expr and "[data-testid]" not in expr and "k.contains(d)" in expr,
          "Ausdruck: nächster klickbarer Vorfahr k, d muss in k liegen")
    for f in (ob.win_ziel_js(10, 10), ob.win_ziel_pruef_js(10, 10, {"rect": [0, 0, 10, 10], "text": "x"})):
        check("k.contains(d)" in f and "win_hover_eltern" not in f, "Ziel-Proben enthalten den eingeschränkten Ausdruck")

    # Fälle: (name, Aufbau-JS das wurzel/hoverPfad/e setzt, erwartet hover, erwartet eltern)
    faelle = [
        ("svg im Knopf, :hover am Knopf → Beweis (am Ziel-Kasten)",
         "var e=N('svg',{},12,12); var k=N('button',{},28,28,[e]); var w=N('div',{},300,200,[k]); var H=[w,k];", True, True),
        ("NEG span in Hülle mit data-testid (kein Klick-Merkmal), :hover an der Hülle → nie",
         "var e=N('span',{},40,14); var k=N('div',{'data-testid':'toast-wrapper'},90,30,[e]); var w=N('div',{},400,300,[k]); var H=[w,k];", False, False),
        ("Blatt selbst :hover → Beweis (ohne Vorfahr)",
         "var e=N('button',{},28,28); var w=N('div',{},300,200,[e]); var H=[w,e];", True, False),
        ("NEG Werbe-Kachel: X-svg im Knopf, :hover an der Kachel → nie",
         "var e=N('svg',{},12,12); var x=N('button',{'aria-label':'close ad'},20,20,[e]); var k=N('div',{},280,60,[x]); var w=N('div',{},800,600,[k]); var H=[w,k];", False, False),
        ("NEG Konto-Zeile: ⋮-svg im Knopf, :hover an der Zeile → nie",
         "var e=N('svg',{},10,10); var dots=N('span',{role:'button'},16,16,[e]); var z=N('div',{},260,32,[dots]); var w=N('div',{},300,400,[z]); var H=[w,z];", False, False),
        ("NEG Toast: „Show more“-span im Knopf, :hover am Toast → nie",
         "var e=N('span',{},60,14); var b=N('button',{},70,20,[e]); var t=N('div',{},320,60,[b]); var w=N('div',{},800,600,[t]); var H=[w,t];", False, False),
        ("NEG Blatt ohne klickbaren Vorfahren, :hover am kleinen Behälter → nie",
         "var e=N('span',{},40,14); var c=N('div',{},120,30,[e]); var w=N('div',{},800,600,[c]); var H=[w,c];", False, False),
        ("Konto-Zeile [role=row] als Ziel, span darin, :hover an der Zeile → Beweis",
         "var e=N('span',{},120,14); var z=N('div',{role:'row'},260,32,[e]); var w=N('div',{},300,400,[z]); var H=[w,z];", True, True),
        ("Konto-Zeile [tabindex] als Ziel, :hover an der Zeile → Beweis",
         "var e=N('span',{},120,14); var z=N('div',{tabindex:'0'},260,32,[e]); var w=N('div',{},300,400,[z]); var H=[w,z];", True, True),
        ("NEG Zeile [tabindex] mit ⋮-Knopf: svg im Knopf, :hover an der Zeile → nie",
         "var e=N('svg',{},10,10); var dots=N('button',{},16,16,[e]); var z=N('div',{tabindex:'0'},260,32,[dots]); var w=N('div',{},300,400,[z]); var H=[w,z];", False, False),
        ("NEG großer Knopf-Kasten (> 64 px hoch) → nie",
         "var e=N('svg',{},12,12); var k=N('button',{},200,120,[e]); var w=N('div',{},800,600,[k]); var H=[w,k];", False, False),
    ]
    prog = DOM_JS.replace("AUSDRUCK", expr) + "\nJSON.stringify([" + ",".join(
        "(function(){" + aufbau + "return fall(w,H,e);})()" for _n, aufbau, _h, _e in faelle) + "])"
    try:
        out = subprocess.run(["osascript", "-l", "JavaScript", "-e", prog], capture_output=True, text=True, timeout=20)
        erg = json.loads(out.stdout.strip())
    except Exception as e:
        erg = None
        check(False, f"JXA nicht ausführbar ({type(e).__name__}: {out.stderr[:200] if 'out' in dir() else ''})")
    if erg is not None:
        for (name, _a, h, el), r in zip(faelle, erg):
            check(r.get("hover") is h and r.get("eltern") is el, f"{name} ({r})")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
