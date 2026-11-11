#!/usr/bin/env python3
"""Selbsttest VF3 (Master 11.11.2026, Bericht berichte/2026-11-11_VF2_vorflug_blind.md: 98 von 102 Vorflug-Lesungen „Terminal läuft nicht“).
Reihenfolge Vorwärmen → Vorflug b → Start mit den echten Funktionen vfZiele/vfFaellig aus prophos.html (jsc, ohne Netz):
  a) Echo mit Hedge (Route mt5, Vorwärmen an): Slot b nie nach Uhr, erst VF_NACH_VW (30–60 s) nach dem Vorwärm-Versuch, nie in der letzten Minute
  b) Reihenfolge: Vorwärmen bei T−240 s → Vorflug b bei T−210…−180 s → Start; Vorwärmen erst bei T−50 s → kein Vorflug b mehr
  c) mt5v2 (kein Vorwärmen): beide Slots nach Uhr wie bisher (T−15 / T−5 ± 2 min)
  d) Verdrahtung: Slot a nur bei offenem Terminal, vfFrei sperrt während _echoVorwaermenLaeuft, Einstellung 240 s (SQL), Grenze 0–300 im Tab
Aufruf:  python3 tools/selftest_vf3_vorflug_vorwaermen.py"""
import os
import json
import subprocess
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


i = html.index("  const VF_SLOTS = [")
teil = html[i:html.index("  function vfFrei(", i)]
js = teil + r"""
const S = 1800000000000, M = 60000
let k = 0; const rnd = () => [0.5, 0.5, 0.5][k++ % 3]          // Slots genau T−15 / T−5, nachVw = 45 s
const z0 = () => vfZiele(null, S, rnd)
const r = {}
let z = z0()
r.nachVw = z.nachVw
r.a_mt5_t15 = vfFaellig(z, S - 15 * M, { an: true, at: null })                 // a nach Uhr
z.erledigt.a = 'zu'
r.b_uhr_ohne_vw = vfFaellig(z, S - 5 * M, { an: true, at: null })              // b NICHT nach Uhr
const vwAt = S - 240000
r.b_vor = vfFaellig(z, vwAt + z.nachVw - 1, { an: true, at: vwAt })            // 1 ms zu früh
r.b_dran = vfFaellig(z, vwAt + z.nachVw, { an: true, at: vwAt })                // jetzt dran
r.b_t59 = vfFaellig(z, S - 59000, { an: true, at: vwAt })                       // letzte Minute → nie
r.b_spaet_vw = vfFaellig(z, S - 50000 + 45000, { an: true, at: S - 50000 })     // Vorwärmen erst T−50 s → nichts
z = z0()
r.a_verpasst = vfFaellig(z, vwAt + z.nachVw, { an: true, at: vwAt })            // a nie gelaufen → als verpasst, b dran
z = z0()
r.v2_b = vfFaellig(z, S - 5 * M, { an: false, at: null })                       // mt5v2: b nach Uhr wie bisher
r.v2_vor = vfFaellig(z, S - 16 * M, { an: false, at: null })
r.alt_ohne_vw = vfFaellig(z0(), S - 5 * M)                                       // alter Aufruf ohne vw → wie bisher
const zz = vfZiele(null, S, Math.random); r.streu = zz.nachVw >= VF_NACH_VW.von && zz.nachVw <= VF_NACH_VW.bis
print(JSON.stringify(r))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
rr = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
e = json.loads(rr.stdout.strip().splitlines()[-1]) if rr.returncode == 0 and rr.stdout.strip() else {}
if not e:
    print(rr.stdout, rr.stderr)
check(e.get("nachVw") == 45000 and e.get("streu") is True, f"a0 nachVw je Plan gewürfelt 30–60 s ({e.get('nachVw')})")
check((e.get("a_mt5_t15") or {}).get("slot") == "a", "a1 Slot a bei T−15 (liest nur, wenn das Terminal schon offen ist)")
check(e.get("b_uhr_ohne_vw") is None, "a2 Echo mit Hedge: Slot b bei T−5 ohne Vorwärmen NICHT nach Uhr (Terminal wäre zu)")
check(e.get("b_vor") is None and (e.get("b_dran") or {}).get("slot") == "b", "a3 Slot b erst nachVw nach dem Vorwärmen")
check(e.get("b_t59") is None, "a4 nie in der letzten Minute vor dem Start")
check(e.get("b_spaet_vw") is None, "b1 Vorwärmen erst bei T−50 s → kein Vorflug b mehr (Start kommt gleich)")
check((e.get("a_verpasst") or {}).get("slot") == "b" and (e.get("a_verpasst") or {}).get("verpasst") == ["a"], "b2 Reihenfolge Vorwärmen T−240 → Vorflug b T−195 → Start; a nie gelaufen = verpasst")
check((e.get("v2_b") or {}).get("slot") == "b" and (e.get("v2_vor") or {}).get("slot") is None, "c1 mt5v2 (kein Vorwärmen): Slot b nach Uhr wie bisher")
check((e.get("alt_ohne_vw") or {}).get("slot") == "b", "c2 Aufruf ohne vw → wie vor VF3")

# Verdrahtung
check("if(!offen && f.slot === 'a'){ z.erledigt.a = 'zu'; continue }" in html and "if(!offen && vw.an){ z.bGrund = 'zu'; continue }" in html and "Master-Terminal nach dem Vorwärmen bis T−60 s nicht frisch" in html, "d1 Slot a nur bei offenem Terminal, Slot b wartet auf frischen Snapshot")
check("_suLaeuft || _pfV2Laeuft || _echoVorwaermenLaeuft || _deLaeuft" in html, "d2 vfFrei sperrt während des Vorwärmens")
check("vwAn = p.route === 'mt5' && vwS > 0 && suStartetVonSelbst(p, scharf)" in html and "_echoVorgewaermt.get(id + '|' + p.startUm)" in html,
      "d3 vorgewärmt wie echoVorwaermenTick (Route mt5, startet von selbst), Zeitpunkt aus _echoVorgewaermt")
check("setTimeout(() => { try{ vfTick().catch(() => {}) }catch(_){} }, nach + 1000 + Math.random() * 5000)" in html, "d4 gezielter Vorflug-Lauf nach dem Vorwärmen, gestreut")
check("vorwaermenS:  zahl(r.echo_vorwaermen_s, 0, 300, s.vorwaermenS)" in html, "d5 Tab klemmt Vorwärmen auf 0–300 s")
sql = open(os.path.join(W, "sql", "2026-11-11_vf3_vorwaermen_240.sql"), encoding="utf-8").read()
check("set echo_vorwaermen_s = 240 where id = 1" in sql, "d6 SQL: echo_vorwaermen_s = 240")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
