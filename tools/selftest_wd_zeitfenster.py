#!/usr/bin/env python3
"""Selbsttest WINNING-DAYS-FARMER ZEITFENSTER (prophos.html wdFensterMs, wdZeitenVerteilen, wdWuerfeln, wdSlotWaehlen, wdUmsortieren,
08.10.2026, Slave-Terminal 3 — Finn: „nur die Uhrzeiten anpassen: von Dubai-Zeit 5 Uhr morgens bis 18 Uhr … zufällige Zeiten in diesem
Zeitraum und auch Long/Short zufällig, wie immer"). Block-Abstand seit der Prüfung von Slave 2 mindestens das Gegenhedge-Fenster
(90 s + 40 s Jitter), sonst 1 min Firmen-Abstand hinter dem letzten Konto.

Aufruf:  python3 tools/selftest_wd_zeitfenster.py
Ohne Netz und ohne Node: schneidet den WD-Block (WD_TZ_STD … window._wdUmsortieren) und wdSlotWaehlen aus prophos.html und führt sie
mit macOS-JavaScriptCore (jsc) aus. Platzhalter-IDs. Seit Finn 08.10.2026 nur noch 1 min je Firma (keine 20/60-min-Regel): Block-Abstand
= 1 min hinter dem letzten Konto-Start (Konten 80 s versetzt). Geprüft: (1) 4 IDs × 200 Seeds — alle Starts in 05:00–18:00 Dubai, ≥ 1 min
auseinander, je Viertel des Fensters genau einer (keine Klumpen), Richtung je ID gewürfelt (beide Seiten), gleicher Seed = gleiches
Ergebnis; (2) feste Blöcke bleiben, Neue mit Abstand daneben; (3) Würfeln mitten am Tag → nichts vor jetzt + 5 min; (4) Fenster vorbei →
dahinter im alten Takt, Abstände bleiben; (5) ohne bis_hhmm → 18:00; (6) ID nachträglich (wdSlotWaehlen) im Fenster, ≥ 20 min zu
allen Blöcken; (7) Drag & Drop tauscht nur IDs, die Zeiten bleiben; (8) Blöcke mit 3 Konten: alle Konto-Starts verschiedener IDs
≥ 1 min auseinander, auch bei 12 IDs."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def schnitt(zeilen, anfang, ende):
    a = next(i for i, z in enumerate(zeilen) if anfang in z)
    b = next(i for i, z in enumerate(zeilen) if i >= a and ende in z)
    return "".join(zeilen[a:b + 1])


TEST = r"""
const DUB = 'Asia/Dubai', M = 60000
const hm = ms => wdJetzt(DUB, new Date(ms)).minuten
const R = { start_hhmm: '05:00', bis_hhmm: '18:00', tz: DUB }
const ids = n => Array.from({ length: n }, (_, i) => ({ user_id: 'u' + i, name: 'ID' + i, konten: [{ aktiv: true, firm: 'Tradeify' }], status: 'geplant', registriert_at: '2026-10-08T00:0' + i }))
const VORTAG = Date.parse('2026-10-08T20:00:00Z')   // 00:00 Dubai am 09.10.
const aus = {}
// (1) 200 Seeds
const laeufe = []
for(let s = 1; s <= 200; s++){
  const m = wdWuerfeln(ids(4), R, '2026-10-09', s, true, VORTAG, {})
  laeufe.push([...m.values()].map(v => ({ min: hm(Date.parse(v.start_um)), ms: Date.parse(v.start_um), dir: v.richtung, nr: v.reihenfolge })))
}
aus.laeufe = laeufe.map(l => l.map(x => [x.min, x.ms, x.dir, x.nr]))
aus.det = JSON.stringify([...wdWuerfeln(ids(4), R, '2026-10-09', 7, true, VORTAG, {})]) === JSON.stringify([...wdWuerfeln(ids(4), R, '2026-10-09', 7, true, VORTAG, {})])
// (2) feste Blöcke: zwei IDs schon um 10:00 und 15:00
{
  const rows = ids(5)
  rows[0].start_um = wdZeitpunkt('2026-10-09', '10:00', DUB).toISOString(); rows[0].reihenfolge = 1
  rows[1].start_um = wdZeitpunkt('2026-10-09', '15:00', DUB).toISOString(); rows[1].reihenfolge = 2
  const m = wdWuerfeln(rows, R, '2026-10-09', 3, false, VORTAG, {})
  aus.fest = { neu: [...m.entries()].map(([k, v]) => [k, Date.parse(v.start_um), v.reihenfolge]), fest: [Date.parse(rows[0].start_um), Date.parse(rows[1].start_um)] }
}
// (3) Würfeln um 12:00 Dubai am selben Tag
{
  const jetzt = wdZeitpunkt('2026-10-09', '12:00', DUB).getTime()
  aus.mittag = { jetzt, starts: [...wdWuerfeln(ids(3), R, '2026-10-09', 5, true, jetzt, {}).values()].map(v => Date.parse(v.start_um)) }
}
// (4) Fenster vorbei: 17:55 Dubai, 3 IDs
{
  const jetzt = wdZeitpunkt('2026-10-09', '17:55', DUB).getTime()
  aus.voll = { jetzt, starts: [...wdWuerfeln(ids(3), R, '2026-10-09', 9, true, jetzt, {}).values()].map(v => Date.parse(v.start_um)) }
}
// (5) ohne bis_hhmm
{
  const f = wdFensterMs({ start_hhmm: '05:00', tz: DUB }, '2026-10-09', VORTAG)
  aus.std = [hm(f.lo), hm(f.hi)]
}
// (6) ID nachträglich
{
  const rows = ids(4).map((x, i) => Object.assign(x, { start_um: wdZeitpunkt('2026-10-09', ['06:00', '09:30', '13:00', '16:40'][i], DUB).toISOString(), reihenfolge: i + 1 }))
  const neu = { user_id: 'neu', konten: [{ aktiv: true }], status: 'geplant' }
  const fest = rows.map(x => Date.parse(x.start_um)), slots = []
  for(let s = 1; s <= 200; s++) slots.push(wdSlotWaehlen(rows.concat([neu]), neu, R, '2026-10-09', VORTAG, wdMulberry(s)).start_ms)
  aus.slot = { fest, slots }
  // nach Spätestens nachgetragen → nichts einplanen, Grund
  const spaet = wdSlotWaehlen(rows.concat([neu]), neu, R, '2026-10-09', wdZeitpunkt('2026-10-09', '18:30', DUB).getTime(), wdMulberry(1))
  aus.spaet = [spaet.start_ms, spaet.grund || '']
}
// (7) Drag & Drop: u0 ans Ende
{
  const rows = ids(4).map((x, i) => Object.assign(x, { start_um: wdZeitpunkt('2026-10-09', ['06:00', '09:30', '13:00', '16:40'][i], DUB).toISOString(), reihenfolge: i + 1 }))
  const m = wdUmsortieren(rows, 'u0', null, null)
  const nachher = rows.map(x => [x.user_id, m.has(x.user_id) ? m.get(x.user_id).start_um : x.start_um])
  aus.dnd = { vorher: rows.map(x => x.start_um).sort(), nachher }
}
// (8) 12 IDs mit je 3 Konten, 100 Seeds → Konto-Starts aller Blöcke
{
  const drei = ids(12).map(x => Object.assign(x, { konten: [{ id: 'a', aktiv: true }, { id: 'b', aktiv: true }, { id: 'c', aktiv: true }] }))
  aus.drei = []
  for(let s = 1; s <= 100; s++){
    const k = []
    for(const v of wdWuerfeln(drei, R, '2026-10-09', s, true, VORTAG, {}).values()) for(let i = 0; i < 3; i++) k.push(Date.parse(v.start_um) + i * 80000)
    aus.drei.push(k.sort((a, b) => a - b))
  }
}
print(JSON.stringify(aus))
"""


def main():
    if not os.path.exists(JSC):
        print("✗ jsc fehlt (macOS JavaScriptCore) — Test nicht ausführbar")
        sys.exit(1)
    zeilen = open(HTML, encoding="utf-8").readlines()
    js = ("var window = {};\n" + schnitt(zeilen, "const WD_TZ_STD = 'Asia/Dubai'", "window._wdUmsortieren = wdUmsortieren")
          + schnitt(zeilen, "function wdSlotWaehlen(", "window._wdSlotWaehlen = wdSlotWaehlen") + TEST)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    if r.returncode != 0:
        print("✗ jsc:", (r.stdout + r.stderr)[-800:])
        sys.exit(1)
    a = json.loads(r.stdout.strip().splitlines()[-1])
    G = 130000   # Gegenhedge-Fenster 90 s + 40 s Jitter (wdBlockAbstandMs, Prüfung Slave 2)

    # (1)
    im_fenster = all(300 <= x[0] <= 1080 for l in a["laeufe"] for x in l)
    abst = min(min(y[1] - x[1] for x, y in zip(sorted(l, key=lambda q: q[1]), sorted(l, key=lambda q: q[1])[1:])) for l in a["laeufe"])
    viertel = all(sorted(int((x[0] - 300) // (780 / 4)) for x in l) == [0, 1, 2, 3] for l in a["laeufe"])
    seiten = [x[2] for l in a["laeufe"] for x in l]
    reihen = all([x[3] for x in sorted(l, key=lambda q: q[1])] == [1, 2, 3, 4] for l in a["laeufe"])
    check(im_fenster, "200 Seeds × 4 IDs: alle Starts zwischen 05:00 und 18:00 Dubai")
    check(abst >= G, f"Abstand zwischen Blöcken ≥ 130 s (kleinster {abst / 60000:.0f} min)")
    check(viertel, "gleichmäßig: in jedem Viertel des Fensters genau ein Block (keine Klumpen)")
    anteil = seiten.count("buy") / len(seiten)
    check(0.4 <= anteil <= 0.6, f"Richtung gewürfelt wie immer: {anteil:.0%} buy")
    check(reihen and a["det"], "Reihenfolge = zeitliche Folge; gleicher Seed → gleiches Ergebnis (alle Tabs würfeln gleich)")
    # (2)
    fe, neu = a["fest"]["fest"], a["fest"]["neu"]
    check(len(neu) == 3 and all(abs(t - f) >= G for _, t, _ in neu for f in fe) and all(3 <= nr <= 5 for _, _, nr in neu),
          "feste Blöcke 10:00/15:00 bleiben, 3 Neue ≥ 130 s daneben, Nummern 3–5")
    # (3)
    check(all(t >= a["mittag"]["jetzt"] + 5 * 60000 for t in a["mittag"]["starts"]), "Würfeln um 12:00 → kein Start vor 12:05")
    # (4)
    st = sorted(a["voll"]["starts"])
    check(len(st) == 3 and st[0] >= a["voll"]["jetzt"] + 5 * 60000 and all(y - x >= G for x, y in zip(st, st[1:])),
          "Fenster vorbei (17:55) → direkt dahinter, ≥ 130 s auseinander")
    # (5)
    check(a["std"] == [300, 1080], f"ohne bis_hhmm: 05:00–18:00 ({a['std']})")
    # (6)
    fe, sl = a["slot"]["fest"], a["slot"]["slots"]
    lo, hi = min(fe) - 60 * 60000, max(fe) + 80 * 60000   # 05:00 … 18:00 relativ zu 06:00 / 16:40
    check(all(lo <= t <= hi for t in sl) and all(abs(t - f) >= G - 30000 for t in sl for f in fe) and len(set(sl)) > 50,
          "ID nachträglich: im Fenster, ≥ 130 s zu allen Blöcken, Zeiten gestreut")
    check(a["spaet"][0] is None and "vorbei" in a["spaet"][1], f"ID nach Spätestens nachgetragen → nicht eingeplant („{a['spaet'][1]}“)")
    # (7)
    d = a["dnd"]
    nach = dict(d["nachher"])
    check(sorted(nach.values()) == d["vorher"] and nach["u0"] == max(d["vorher"]), "Drag & Drop: Zeiten bleiben, u0 bekommt den letzten Platz")
    # (8)
    kl = min(min(y - x for x, y in zip(k, k[1:])) for k in a["drei"])
    check(kl >= 60000, f"12 IDs × 3 Konten: Konto-Starts ≥ 1 min auseinander (kleinster Abstand {kl / 1000:.0f} s)")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
