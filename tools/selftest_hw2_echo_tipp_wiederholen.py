#!/usr/bin/env python3
"""Selbsttest HW2 (Master 16.11.2026, Folge zu HW1): Echo mit Hedge (tpPreflightMt5) wiederholt master-order, wenn der Bot nach seiner
150-s-Wartezeit auf die PC-Tipp-Sperre {retry_ok, code puls_beschaeftigt, grund pc_tipp_sperre} antwortet — gestreut 20–40 s, bis
ECHO_TIPP_FRIST_MS (320 s), nie bei retry_ok false / gesendet true. Führt die ECHTE Regel aus prophos.html in JavaScriptCore aus und spielt
die Schleife mit Zeitstempeln nach (jeder Bot-Versuch mit belegter Sperre dauert 150 s). Aufruf: python3 tools/selftest_hw2_echo_tipp_wiederholen.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    regel = html[html.index("  const ECHO_TIPP_FRIST_MS"):html.index("  window._echoTippBelegt = echoTippBelegt")]
    t = html[html.index("async function tpPreflightMt5(plan){"):html.index("async function tpPreflightMt5(plan){") + 60000]
    o = t[t.index("if(!mt5OrderWiederholen(r, Date.now() - t0)) break"):]
    o = o[:o.index("}finally{ if(_pfV2Laeuft === String(plan.id)) _pfV2Laeuft = laufVorher }")]
    check("const _tipp = echoTippBelegt(r), _pauseMs = _tipp ? echoTippPauseMs() : 5000 + Math.random() * 2000" in o
          and "await new Promise(res => setTimeout(res, _pauseMs))" in o, "Schleife: Tipp-Sperre → echoTippPauseMs, sonst 5–7 s wie bisher")
    zu = "if(!document.getElementById('tpPreflightModal')?.classList.contains('open') || String(_pfPlanId) !== String(plan.id)){"
    check(o.count(zu) == 2 and o.index(zu, o.index("setTimeout(res, _pauseMs)")) > 0,
          "Popup-Prüfung vor UND nach der Pause (nach 20–40 s kein Auftrag mehr, wenn das Popup zu ist)")
    js = """
function echoBotNichtScharf(r){ return !!(r && r.grund === 'nicht_scharf') }
""" + regel + """
const S = 1000, tipp = { ok:false, retry_ok:true, code:'puls_beschaeftigt', grund:'pc_tipp_sperre', msg:'PC-Tipp-Sperre seit 150 s belegt' };
const ok = { ok:true, price:1, ticket:7 };
// Schleife wie tpPreflightMt5: jeder Versuch mit belegter Sperre dauert 150 s im Bot, dann Pause aus der Regel
function schleife(antworten, dauer){
  let t = 0, n = 0, r = null
  for(const a of antworten){ n++; t += dauer(a); r = a; if(!mt5OrderWiederholen(r, t)) break; t += echoTippBelegt(r) ? echoTippPauseMs() : 6000 }
  return { n, ok: !!(r && r.ok), t }
}
const d = a => a === tipp ? 150 * S : 3 * S
const pausen = []; for(let i = 0; i < 400; i++) pausen.push(echoTippPauseMs())
print(JSON.stringify({
  frist: ECHO_TIPP_FRIST_MS,
  erst: mt5OrderWiederholen(tipp, 150 * S), spaet: mt5OrderWiederholen(tipp, 321 * S),
  nurCode: mt5OrderWiederholen({ ok:false, retry_ok:true, code:'puls_beschaeftigt', gesendet:false }, 160 * S),
  gesendet: mt5OrderWiederholen(Object.assign({}, tipp, { gesendet:true }), 150 * S),
  unklar: mt5OrderWiederholen(Object.assign({}, tipp, { retry_ok:false }), 150 * S),
  scharf: mt5OrderWiederholen({ ok:false, retry_ok:true, grund:'nicht_scharf' }, 10 * S),
  heilt179: mt5OrderWiederholen({ ok:false, retry_ok:true, grund:'terminal_heilt' }, 179 * S), heilt181: mt5OrderWiederholen({ ok:false, retry_ok:true, grund:'terminal_heilt' }, 181 * S),
  verb89: mt5OrderWiederholen({ ok:false, retry_ok:true, msg:'IPC-Verbindung fehlt' }, 89 * S), verb91: mt5OrderWiederholen({ ok:false, retry_ok:true, msg:'IPC-Verbindung fehlt' }, 91 * S),
  markt: mt5OrderWiederholen({ ok:false, retry_ok:true, msg:'Markt geschlossen (10018)' }, 5 * S),
  pMin: Math.min(...pausen), pMax: Math.max(...pausen),
  frei: schleife([tipp, ok, ok], d), bleibt: schleife([tipp, tipp, tipp, tipp, tipp], d)
}))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    r = subprocess.run([JSC, f.name], capture_output=True, text=True)
    os.unlink(f.name)
    try:
        v = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        v = {}
        print("JS:", r.stdout[-600:], r.stderr[-600:])
    check(v.get("frist") == 320000, "Frist 320 s = Budget eines Echo-Starts (pfLebt 340 s, master-order bis 320 s)")
    check(v.get("erst") is True and v.get("spaet") is False, "pc_tipp_sperre nach 150 s → erneut (alte 90-s-Frist griff hier nie); nach 320 s Schluss")
    check(v.get("nurCode") is False, "puls_beschaeftigt OHNE grund pc_tipp_sperre (Polar-Sperre, panel.py) → nicht wiederholt, Polar hat Vorrang")
    check(v.get("gesendet") is False and v.get("unklar") is False, "gesendet true bzw. retry_ok false → nie wiederholt (keine Doppel-Order)")
    check(v.get("scharf") is False, "„nicht scharf“ bleibt eine Antwort (ES2d) — nicht wiederholt")
    check(v.get("heilt179") is True and v.get("heilt181") is False and v.get("verb89") is True and v.get("verb91") is False and v.get("markt") is False,
          "übrige Regeln unverändert: terminal_heilt 180 s, Verbindung 90 s, sonstige Ablehnung nie")
    check(20000 <= (v.get("pMin") or 0) and (v.get("pMax") or 0) < 40000 and (v.get("pMax") or 0) - (v.get("pMin") or 0) > 10000,
          f"Pause gestreut 20–40 s (gemessen {round((v.get('pMin') or 0) / 1000, 1)}–{round((v.get('pMax') or 0) / 1000, 1)} s)")
    fr, bl = v.get("frei") or {}, v.get("bleibt") or {}
    check(fr.get("n") == 2 and fr.get("ok") is True, f"Sperre wird frei → zweiter Auftrag platziert genau einmal ({fr.get('n')} Aufträge)")
    check(bl.get("n") == 2 and bl.get("ok") is False and (bl.get("t") or 0) <= 360000,
          f"Sperre bleibt belegt → zwei Versuche, dann Start-Fehler ({bl.get('n')} Aufträge, {round((bl.get('t') or 0) / 1000)} s)")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
