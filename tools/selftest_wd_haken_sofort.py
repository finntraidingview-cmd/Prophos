#!/usr/bin/env python3
"""Selbsttest WD-HAKEN → SOFORT EINWÜRFELN (30.10.2026, Slave 7; Finn 02:07: „Wenn ich die ID anhänge, dann soll sie automatisch in den
aktuellen Tag mit eingeplant werden, ohne dass ich neu würfeln muss").
(1) Echter JS-Code aus prophos.html in JavaScriptCore: wdTagGewuerfelt, wdHakenSlot (an den Block hängen, solange er ≥ 5 min vor uns liegt,
    sonst eigener Platz über wdNdSlot — hier gespielt), plus wdNdSlot echt mit Fenster/Abstand (bis_hhmm, Firmen-Abstand, feste Blöcke bleiben).
(2) Verdrahtung: Haken (auch „alle“ und ohne Zeile) würfelt an gewürfelten Tagen über wdKontoEinwuerfeln(anBlock) ein, sonst wie bisher
    Tageslauf; kein Platz → heute aus mit Grund („Heute nicht drin“); Busy-Riegel; Gruppen-Recht über wdDarf.
Aufruf: python3 tools/selftest_wd_haken_sofort.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def bis(anfang, ende):
    i = HTML.index(anfang)
    return HTML[i:HTML.index(ende, i) + len(ende)]


def main():
    code = bis("  function wdHakenSlot(rows, x, regeln, tag, jetztMs, rnd){", "window._wdHakenSlot = wdHakenSlot; window._wdTagGewuerfelt = wdTagGewuerfelt")
    prog = """var window = {}, NDSLOT = [];
function wdNdSlot(rows, x, r, tag, jetzt, rnd){ NDSLOT.push(x.user_id); return x.user_id === 'voll' ? { grund: 'kein freier Platz mehr im Fenster 05:00–18:00 Dubai' } : { versatz_min: 37, start_ms: jetzt + 37 * 60000 } }
%s
var J = 1793300000000, M = 60000, iso = ms => new Date(ms).toISOString(), out = {}
out.tag_gew = wdTagGewuerfelt([{ tag: '2026-10-30', start_um: iso(J) }, { tag: '2026-10-30', start_um: null }], '2026-10-30')
out.tag_ungew = wdTagGewuerfelt([{ tag: '2026-10-30', start_um: null }], '2026-10-30')
out.tag_anderer = wdTagGewuerfelt([{ tag: '2026-10-29', start_um: iso(J) }], '2026-10-30')
out.tag_leer = wdTagGewuerfelt([], '2026-10-30')
var a = wdHakenSlot([], { user_id: 'marc', start_um: iso(J + 60 * M) }, {}, '2026-10-30', J)
out.anblock = a.mitBlock === true && a.anBlock === true && a.start_ms === J + 60 * M && a.versatz_min === 0 && NDSLOT.length === 0
var b = wdHakenSlot([], { user_id: 'marc', start_um: iso(J + 4 * M) }, {}, '2026-10-30', J)
out.knapp_eigener = !b.mitBlock && b.versatz_min === 37 && NDSLOT[0] === 'marc'
var c = wdHakenSlot([], { user_id: 'voll', start_um: iso(J - 30 * M) }, {}, '2026-10-30', J)
out.voll_grund = !!c.grund
print(JSON.stringify(out))
""" % code
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(prog)
        pfad = f.name
    try:
        o = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(pfad)
    t = (o.stdout or "").strip()
    r = json.loads(t) if t.startswith("{") else None
    check(r is not None, f"JS läuft in jsc{'' if r else ' (' + (t or o.stderr)[:200] + ')'}")
    if r:
        check(r["tag_gew"] and not r["tag_ungew"] and not r["tag_anderer"] and not r["tag_leer"],
              "wdTagGewuerfelt: nur wenn eine Zeile des Farmer-Tags schon eine Startzeit hat")
        check(r["anblock"], "ID mit Block ≥ 5 min voraus → an den Block hängen (Gruppe 1, kein Neu-Würfeln, wdNdSlot nicht gefragt)")
        check(r["knapp_eigener"], "Block < 5 min bzw. schon angelaufen → eigener Platz im Fenster (wdNdSlot)")
        check(r["voll_grund"], "kein Platz bis bis_hhmm → Grund statt Slot")

    # (2) Verdrahtung
    hk = HTML[HTML.index("  async function wdKontoHaken(uid, kontoId, an){"):HTML.index("  // Haken an einem gewürfelten Tag: dauerhaft setzen")]
    check("if(an && (!x.tag || x.tag === _wd.tag) && wdTagGewuerfelt(_wd.rows, _wd.tag)) return wdHakenSofort(uid, kontoId, x, k)" in hk
          and hk.index("wdHakenSofort(") < hk.index("k.naechster_lauf = true"), "wdKontoHaken: gewürfelter Tag → sofort einwürfeln, VOR der alten Tageslauf-Regel")
    check("if(!k){ if(an) return wdKontoHakenOhneZeile(kontoId, true); return }" in hk, "Konto fehlt in der Zeile (Emin): Haken wird gespeichert statt still abzubrechen")
    so = HTML[HTML.index("  async function wdHakenSofort(uid, kontoId, x, k){"):HTML.index("  /* Haken für eine ID ohne Tageszeile (26.09.2026)")]
    check("rpc('wd_konto_setzen', { p_account: kontoId, p_wd_farm: true })" in so and so.index("wd_konto_setzen") < so.index("wdKontoEinwuerfeln(")
          and "wdKontoEinwuerfeln(uid, kontoId, { anBlock: true })" in so, "wdHakenSofort: erst dauerhaft, dann derselbe Weg wie das 🎲 (anBlock)")
    check("aktiv: false, hinweis: 'heute nicht eingeplant: '" in so and "if(kn && !kn.plan_id)" in so and ".neq('status', 'laeuft')" in so,
          "nicht eingeplant → dauerhaft drin, heute aus mit Grund (Heute nicht drin), nie an einem Konto mit Plan")
    check("for(let i = 0; _wd.busy && i < 30; i++)" in so and "finally{ _wd.busy = false }" in so
          and so.index("if(_wd.busy){") < so.index("_wd.busy = true") and "wdNeuLaden()" in so[so.index("if(_wd.busy){"):so.index("_wd.busy = true")]
          and "p_wd_farm: true" in so[so.index("if(_wd.busy){"):so.index("_wd.busy = true")],
          "Busy: bis 15 s warten, sonst Haken trotzdem dauerhaft setzen + neu zeichnen (S2: Kästchen blieb optisch an)")
    oz = HTML[HTML.index("  async function wdKontoHakenOhneZeile(kontoId, an){"):][:900]
    check("if(an && uid0 && wdTagGewuerfelt(_wd.rows, _wd.tag)) return wdHakenSofort(uid0, kontoId, null, null)" in oz
          and oz.index("wdDarf(") < oz.index("wdHakenSofort("), "ID ohne Tageszeile: gewürfelter Tag → sofort (nach dem Gruppen-Recht)")
    ew = HTML[HTML.index("  async function wdKontoEinwuerfeln(uid, kontoId, opts){"):HTML.index("  async function wdNdAlle(){")]
    check("const s = opts.anBlock ? wdHakenSlot(_wd.rows || [], x, r, tag, Date.now()) : wdNdSlot(_wd.rows || [], x, r, tag, Date.now())" in ew,
          "wdKontoEinwuerfeln: anBlock nur auf dem Haken-Weg, das 🎲 würfelt weiter eine eigene Gruppe")
    check("if(s.mitBlock && andere.some(q => q.gruppe)) Object.assign(kn, { gruppe: 1, g_versatz_min: 0, g_gegen: false })" in ew,
          "mit dem Block in einem Bündel → ausdrücklich Gruppe 1")
    check("if(!(await wdDarf(uid))) return { fehler: 'nicht in deiner Gruppe' }" in ew, "Gruppen-Recht (Emin nur seine Gruppe) bleibt im gemeinsamen Weg")
    check("wdSlotEinplanen(x)" in ew and "x.start_um = startUm" in ew, "ID ohne Block → eigener Slot (wdSlotEinplanen, feste Blöcke bleiben)")
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
