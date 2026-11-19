#!/usr/bin/env python3
"""Selbsttest WE1 (Finn 19.11.2026, Admin → Payouts „🏆 5/5 anfragbar“ am Tag des 5. Winning Days): Payouts lassen sich erst nach Ende des
Handelstags anfragen. Wurde das Ziel ERST im laufenden CME-Handelstag voll, liefert app.py wd_voll_ab das Ende dieses Tags (17:00 Chicago),
sonst ''. Das Frontend rechnet dasselbe (wdVollAbMs/wdTagEndeMs) und zeigt bis dahin „anfragbar ab HH:MM“ (Gerätezeit) statt „anfragbar“.
Ohne Netz und ohne DB.

Aufruf:  python3 tools/selftest_we1_wd_anfragbar_ab.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


try:
    compile(app, "app.py", "exec")
    check(True, "app.py kompiliert")
except SyntaxError as e:
    check(False, f"app.py kompiliert ({e})")

from datetime import datetime, timedelta, timezone  # noqa: E402
ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


for n in ("_cme_handelstag", "_cme_tag_ende", "wd_voll_ab"):
    lade(n)
ab = ns["wd_voll_ab"]

WOCHE = ["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18"]   # vier Winning Days bis gestern
HEUTE_9 = "2026-11-19T15:00:00Z"    # 09:00 Chicago (CST) = CME-Tag 19.11.
NACH = "2026-11-19T23:30:00Z"       # 17:30 Chicago → CME-Tag schon 20.11.
FAELLE = [
    ("5. WD heute → anfragbar ab Ende des Handelstags (17:00 CST = 23:00 UTC)", WOCHE + ["2026-11-19"], 5, 5, HEUTE_9, "2026-11-19T23:00:00Z"),
    ("5. WD gestern → anfragbar (leer)", ["2026-11-12"] + WOCHE, 5, 5, HEUTE_9, ""),
    ("6/5 mit heute → der 5. war gestern → anfragbar", ["2026-11-12"] + WOCHE + ["2026-11-19"], 6, 5, HEUTE_9, ""),
    ("4/5 heute → nicht am Ziel → leer", WOCHE[1:] + ["2026-11-19"], 4, 5, HEUTE_9, ""),
    ("Korrektur +1: 4 Tage inkl. heute, Stand 5 → ab Tagesende", WOCHE[1:] + ["2026-11-19"], 5, 5, HEUTE_9, "2026-11-19T23:00:00Z"),
    ("nach 17:00 Chicago: Tag vorbei → anfragbar", WOCHE + ["2026-11-19"], 5, 5, NACH, ""),
    ("Sommerzeit: 17:00 CDT = 22:00 UTC", ["2026-07-10", "2026-07-13", "2026-07-14", "2026-07-15"], 4, 4, "2026-07-15T15:00:00Z", "2026-07-15T22:00:00Z"),
    ("Ziel 0 / unlesbar → leer", WOCHE + ["2026-11-19"], 5, 0, HEUTE_9, ""),
    ("Session-Abend 18:00 Chicago (CME-Tag 20.11.) zählt zum 20.11. → Ende 20.11. 23:00 UTC", WOCHE + ["2026-11-20"], 5, 5, "2026-11-20T00:00:00Z", "2026-11-20T23:00:00Z"),
]
for text, tage, stand, ziel, jetzt, soll in FAELLE:
    ist = ab(tage, stand, ziel, jetzt)
    check(ist == soll, f"Railway: {text} → {ist!r}")

check('"voll_ab": wd_voll_ab(tage, st, zl)' in app, "wd_auto_staende liefert voll_ab")
check('"wd_ab": wd_voll_ab(wd_auto[aid]["tage"], count, target)' in app, "Admin → Payouts (payout_ready) liefert wd_ab")
check('k["wd_voll_ab"] = st["voll_ab"]' in app, "/admin/wd-plaene (ansicht=admin) liefert wd_voll_ab")
check("vollAb: mindest ? 0 : wdVollAbMs(w.tage, w.count, k.target)" in html, "zielFortschritt rechnet vollAb aus den gezählten Tagen")
check("}else if(r.wd_ready && wdAbAusIso(r.wd_ab)){" in html and "chip.textContent = 'anfragbar ' + wdAbTxt(wdAbAusIso(r.wd_ab))" in html,
      "Admin-Kasse: statt Knopf „anfragbar ab …“ (kein Klick auf die Anfrage)")
check("const faellig = tag ? tage <= 0 : !!r.wd_ready && !wdAbAusIso(r.wd_ab)" in html, "Admin-Kasse: „Fällig jetzt“ zählt das Konto erst nach Tagesende")
check("bereit: fehlt === 0 && !sperre && !ab" in html, "WD-Übersicht: KPI „Payout anfragbar“ ohne die heute vollen")
check("&& !(f.vollAb > Date.now())" in html and "r.ab = wdAbTxt(f.vollAb)" in html, "Finanzen: Payout-Status und Anfrage-Auswahl")
check("Payout anfragbar ${wdAbTxt(_ab)}" in html, "Accounts-Badge „✓ · Payout anfragbar ab …“")

if shutil.which("osascript"):
    i = html.index("  function tvV2Handelstag(d){")
    j = html.index("  window._wdVollAbMs = wdVollAbMs")
    teil = html[i:j]
    js = "function run(){ var window = {};\n" + teil + """
var P = %s, out = [];
for (var k = 0; k < P.length; k++){ var f = P[k], ms = wdVollAbMs(f[1], f[2], f[3], Date.parse(f[4])); out.push(ms ? new Date(ms).toISOString().replace('.000Z', 'Z') : '') }
var t = Date.parse('2026-11-19T23:00:00Z');
return JSON.stringify({ out: out, isoZukunft: wdAbAusIso('2026-11-19T23:00:00Z', Date.parse('2026-11-19T15:00:00Z')), isoVorbei: wdAbAusIso('2026-11-19T23:00:00Z', Date.parse('2026-11-19T23:30:00Z')),
  leer: wdAbAusIso('', 0), txtGleich: wdAbTxt(t, t - 3600000), txtMorgen: wdAbTxt(t, t - 36 * 3600000) }) }""" % json.dumps(FAELLE)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
        t.write(js)
    try:
        r = subprocess.run(["osascript", "-l", "JavaScript", t.name], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(t.name)
    check(r.returncode == 0, "Frontend-Rechnung läuft (" + r.stderr[:200] + ")")
    if r.returncode == 0:
        d = json.loads(r.stdout)
        for (text, *_rest, soll), ist in zip(FAELLE, d["out"]):
            check(ist == soll, f"Frontend wie Railway: {text} → {ist!r}")
        check(d["isoZukunft"] == 1795129200000 and d["isoVorbei"] == 0 and d["leer"] == 0, f"wdAbAusIso: künftig = ms, vorbei/leer = 0 ({d['isoZukunft']}, {d['isoVorbei']})")
        check(re.fullmatch(r"ab \d\d:\d\d", d["txtGleich"]) is not None and re.fullmatch(r"ab morgen \d\d:\d\d", d["txtMorgen"]) is not None,
              f"wdAbTxt: „{d['txtGleich']}“ (selber Gerätetag) / „{d['txtMorgen']}“ (Vortag)")
else:
    check(False, "osascript fehlt — Frontend-Teil nicht geprüft")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
