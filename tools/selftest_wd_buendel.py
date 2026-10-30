#!/usr/bin/env python3
"""Selbsttest WINNING-DAYS-FARMER BÜNDEL JE ID (prophos.html wdBuendelWuerfeln, wdBuendelAnKonten, wdKontoZeiten, wdKontoRichtung,
wdWuerfeln + app.py ap_wd_block_starts/wd_konto_gruppe, 28.10.2026 — Finn per Sprachnachricht: „an manchen Tagen alle auf einmal, an
anderen nicht — z. B. zwei Longs um 16 Uhr und schon um 7 Uhr morgens ein Short, an einem anderen Tag alle drei zu verschiedenen
Uhrzeiten"). Ist bis hier: eine ID = ein Block, alle Konten Blockstart + 80 s je Konto, eine Richtung (wd_tagesplan 26.–28.10.).

Aufruf:  python3 tools/selftest_wd_buendel.py
Ohne Netz und ohne Node: schneidet den WD-Block aus prophos.html und führt ihn mit macOS-JavaScriptCore (jsc) aus; die Python-Seite
per exec aus app.py. Platzhalter-IDs. Geprüft über 2.000 gewürfelte Tage (7 IDs, 1–4 Konten): (1) Bündel-Arten kommen alle vor, je
grob 1/3 (2 Konten je 1/2), 1 Konto immer „alle"; (2) jede Konto-Startzeit im Fenster 05:00–18:00 Dubai, Gruppen-Starts verschiedener
Gruppen/IDs ≥ Block-Abstand auseinander, Konten einer Gruppe 80 s versetzt; (3) Richtung je Gruppe: Gegenrichtung innerhalb einer ID
kommt vor (Finns Beispiel), Gruppe 1 = Richtung der Zeile; (4) übernommene Richtung (laufender Trade) → alle Gruppen dieselbe; (5)
gleicher Seed = gleiches Ergebnis (zwei Tabs würfeln gleich); (6) Konten ohne Gruppe → Zeiten exakt wie bis 28.10. (Blockstart + 80 s ×
Nummer); (7) Python ap_wd_block_starts rechnet dieselben Minuten und Richtungen wie JS; (8) jedes aktive Konto steckt in genau einer
Gruppe, inaktive nie."""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
APP = os.path.join(HIER, "..", "app.py")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def schnitt(zeilen, anfang, ende, ende_mit=True):
    a = next(i for i, z in enumerate(zeilen) if anfang in z)
    b = next(i for i, z in enumerate(zeilen) if i > a and ende in z)
    return "".join(zeilen[a:b + 1 if ende_mit else b])


TEST = r"""
const DUB = 'Asia/Dubai', TAG = '2026-10-29'
const R = { start_hhmm: '05:00', bis_hhmm: '18:00', tz: DUB }
const VORTAG = Date.parse('2026-10-28T20:00:00Z')   // 00:00 Dubai am 29.10.
const zeilen = s => Array.from({ length: 7 }, (_, i) => ({ user_id: 'u' + i, name: 'ID' + i, status: 'geplant', registriert_at: '2026-10-29T00:0' + i,
  konten: Array.from({ length: 1 + ((i + s) % 4) }, (_, j) => ({ id: 'u' + i + 'k' + j, aktiv: true, firm: 'Tradeify' }))
    .concat(i === 3 ? [{ id: 'u3aus', aktiv: false, firm: 'Tradeify' }] : []) }))
const aus = { tage: [] }
for(let s = 1; s <= 2000; s++){
  const rows = zeilen(s), m = wdWuerfeln(rows, R, TAG, 'buendel|' + s, true, VORTAG, {})
  const tag = []
  for(const x of rows){
    const e = m.get(x.user_id), konten = wdBuendelAnKonten(x.konten, e.buendel), z = wdKontoZeiten(konten, e.start_um, R)
    tag.push({ uid: x.user_id, n: x.konten.filter(wdAktiv).length, art: e.buendel.art, start: e.start_um, richtung: e.richtung,
      gruppen: e.buendel.gruppen.map(g => g.ids.length),
      konten: konten.map(k => ({ id: k.id, aktiv: wdAktiv(k), gruppe: k.gruppe || null, v: k.g_versatz_min == null ? null : k.g_versatz_min, gegen: !!k.g_gegen,
        t: z.has(String(k.id)) ? Date.parse(z.get(String(k.id))) : null, r: wdKontoRichtung(k, e.richtung) })) })
  }
  aus.tage.push(tag)
}
aus.det = JSON.stringify([...wdWuerfeln(zeilen(5), R, TAG, 'x', true, VORTAG, {})]) === JSON.stringify([...wdWuerfeln(zeilen(5), R, TAG, 'x', true, VORTAG, {})])
// (4) Richtung übernommen: alle Gruppen dieselbe
{
  const rows = zeilen(2), fest = {}
  for(const x of rows) fest[x.user_id + '|tradeify'] = { richtung: 'sell', durch: 'läuft gerade' }
  aus.vorgabe = []
  for(let s = 1; s <= 300; s++){
    const m = wdWuerfeln(rows, R, TAG, 'v' + s, true, VORTAG, fest)
    for(const x of rows){ const e = m.get(x.user_id); const ks = wdBuendelAnKonten(x.konten, e.buendel); aus.vorgabe.push(ks.filter(wdAktiv).map(k => wdKontoRichtung(k, e.richtung))) }
  }
}
// (6) Konten ohne Gruppe: wie bis 28.10.
{
  const t = '2026-10-29T06:00:00.000Z', ks = [{ id: 'a', aktiv: true }, { id: 'b', aktiv: false }, { id: 'c', aktiv: true }, { id: 'd' }]
  aus.alt = [...wdKontoZeiten(ks, t, R).entries()]
}
print(JSON.stringify(aus))
"""


def lade_py():
    src = open(APP, encoding="utf-8").read()
    ns = {"datetime": datetime, "timedelta": timedelta}
    teile = [re.search(r"^WD_KONTO_ABSTAND_S = .*$", src, re.M).group(0).split("  #")[0]]
    for name in ("ap_wd_block_starts", "wd_konto_gruppe"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    ns["ap_firma_key"] = lambda firmen, f: str(f or "").lower()
    exec("\n".join(teile), ns)
    return ns


def main():
    if not os.path.exists(JSC):
        print("✗ jsc fehlt (macOS JavaScriptCore) — Test nicht ausführbar")
        sys.exit(1)
    zeilen = open(HTML, encoding="utf-8").readlines()
    js = ("var window = {};\nfunction escapeHtml(s){ return String(s) }\nconst WD_KONTO_ABSTAND_MS = 80000\n"
          + schnitt(zeilen, "const WD_TZ_STD = 'Asia/Dubai'", "window._wdUmsortieren = wdUmsortieren")
          + schnitt(zeilen, "function wdKontoZeiten(", "async function wdZeileSchreiben(", ende_mit=False) + TEST)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(f.name)
    if r.returncode != 0:
        print("✗ jsc:", (r.stdout + r.stderr)[-800:])
        sys.exit(1)
    a = json.loads(r.stdout.strip().splitlines()[-1])
    tage = a["tage"]
    G = 130000   # Block-Abstand mindestens Gegenhedge-Fenster 90 s + 40 s Jitter (wdBlockAbstandMs)
    dub = timezone(timedelta(hours=4))

    # (1) Verteilung der Bündel-Arten
    arten = {}
    for tag in tage:
        for x in tag:
            arten.setdefault(min(x["n"], 3), {}).setdefault(x["art"], 0)
            arten[min(x["n"], 3)][x["art"]] += 1
    print("  Bündel-Arten je Kontozahl (1 / 2 / ≥3):", json.dumps(arten, ensure_ascii=False))
    check(set(arten[1]) == {"alle"}, "1 Konto → immer „alle“")
    z2 = arten[2]; n2 = sum(z2.values())
    check(set(z2) == {"alle", "einzeln"} and all(0.4 < v / n2 < 0.6 for v in z2.values()), f"2 Konten → zusammen/einzeln je ~1/2 ({z2})")
    z3 = arten[3]; n3 = sum(z3.values())
    # „alle“ kann zusätzlich entstehen, wenn kein Platz im Fenster war — bei 7 IDs praktisch nie
    check(set(z3) == {"alle", "teil", "einzeln"} and all(0.25 < v / n3 < 0.42 for v in z3.values()), f"≥ 3 Konten → alle/teil/einzeln je ~1/3 ({z3})")

    # (2) Zeiten: Fenster, Abstände zwischen Gruppen, 80 s in der Gruppe; (8) Gruppen vollständig
    fenster_ok = abstand_ok = takt_ok = voll_ok = True
    kleinster = 10 ** 12
    for tag in tage:
        starts = []
        for x in tag:
            gr = {}
            for k in x["konten"]:
                if not k["aktiv"]:
                    voll_ok &= k["gruppe"] is None and k["t"] is None
                    continue
                t = datetime.fromtimestamp(k["t"] / 1000, dub)
                fenster_ok &= 5 * 60 <= t.hour * 60 + t.minute <= 18 * 60 + 3 * 80 / 60
                gr.setdefault(k["gruppe"] or 1, []).append(k["t"])
            voll_ok &= sum(len(v) for v in gr.values()) == x["n"] and sorted(len(v) for v in gr.values()) == sorted(x["gruppen"])
            for ts in gr.values():
                takt_ok &= all(b - a == 80000 for a, b in zip(ts, ts[1:]))
                starts.append(ts[0])
        starts.sort()
        d = min((b - a for a, b in zip(starts, starts[1:])), default=10 ** 12)
        kleinster = min(kleinster, d)
        abstand_ok &= d >= G
    check(fenster_ok, "alle Konto-Starts im Fenster 05:00–18:00 Dubai (letzte Gruppe + 80-s-Takt)")
    check(abstand_ok, f"Gruppen-Starts aller IDs ≥ 130 s auseinander (kleinster Abstand {kleinster // 1000} s)")
    check(takt_ok, "Konten einer Gruppe 80 s versetzt")
    check(voll_ok, "jedes aktive Konto in genau einer Gruppe, inaktive ohne Gruppe/Zeit")

    # (3) Richtung je Gruppe
    gemischt = getrennt = g1_ok = 0
    g1_ok = True
    for tag in tage:
        for x in tag:
            rs = {k["r"] for k in x["konten"] if k["aktiv"]}
            g1_ok &= all(k["r"] == x["richtung"] for k in x["konten"] if k["aktiv"] and (k["gruppe"] or 1) == 1)
            if len(x["gruppen"]) > 1:
                getrennt += 1
                gemischt += len(rs) > 1
    check(g1_ok, "Gruppe 1 fährt die Richtung der Zeile")
    check(getrennt and 0.3 < gemischt / getrennt < 0.8, f"Gegenrichtung innerhalb einer ID kommt vor ({gemischt} von {getrennt} geteilten IDs-Tagen)")
    # Finns Beispiel: 3 Konten, zwei zusammen in einer Richtung, eins einzeln früher in der anderen
    beispiel = 0
    for tag in tage:
        for x in tag:
            if x["n"] == 3 and sorted(x["gruppen"]) == [1, 2]:
                ks = [k for k in x["konten"] if k["aktiv"]]
                zwei = [k for k in ks if sum(1 for q in ks if (q["gruppe"] or 1) == (k["gruppe"] or 1)) == 2]
                eins = [k for k in ks if k not in zwei]
                if eins and zwei and eins[0]["t"] < zwei[0]["t"] and eins[0]["r"] != zwei[0]["r"]:
                    beispiel += 1
    check(beispiel > 0, f"Finns Beispiel kommt vor: einer früh in der Gegenrichtung, zwei später zusammen ({beispiel}×)")

    # (4) übernommene Richtung
    check(all(set(v) == {"sell"} for v in a["vorgabe"] if v), "Richtung übernommen (laufender Trade) → alle Gruppen dieselbe Richtung")
    # (5)
    check(a["det"], "gleicher Seed → gleiches Ergebnis (zwei Tabs würfeln gleich)")
    # (6)
    t0 = datetime(2026, 10, 29, 6, tzinfo=timezone.utc)
    soll = [["a", t0.isoformat().replace("+00:00", ".000Z")], ["c", (t0 + timedelta(seconds=80)).isoformat().replace("+00:00", ".000Z")],
            ["d", (t0 + timedelta(seconds=160)).isoformat().replace("+00:00", ".000Z")]]
    check(a["alt"] == soll, "Konten ohne Gruppe → Blockstart + 80 s × Nummer wie bis 28.10.")

    # (7) Python rechnet dasselbe
    ns = lade_py()
    mitternacht = datetime(2026, 10, 28, 20, tzinfo=timezone.utc)   # 00:00 Dubai am 29.10.
    py_ok = True
    for tag in tage[:300]:
        for x in tag:
            konten = [{"id": k["id"], "aktiv": k["aktiv"], "firm": "Tradeify", **({"gruppe": k["gruppe"], "g_versatz_min": k["v"], "g_gegen": k["gegen"]} if k["gruppe"] else {})}
                      for k in x["konten"]]
            row = {"status": "geplant", "start_um": x["start"], "richtung": x["richtung"], "user_id": x["uid"], "name": x["uid"], "konten": konten}
            py = {s["key"].split(":")[2]: s for s in ns["ap_wd_block_starts"]([row], mitternacht, {})}
            for k in x["konten"]:
                if not k["aktiv"]:
                    py_ok &= k["id"] not in py
                    continue
                m = (k["t"] / 1000 - mitternacht.timestamp()) / 60.0
                s = py.get(k["id"])
                py_ok &= bool(s) and abs(s["start"] - round(m, 2)) < 0.01 and s["richtung"] == k["r"]
    check(py_ok, "app.py ap_wd_block_starts = JS wdKontoZeiten/wdKontoRichtung (Minute + Richtung je Konto, 300 Tage)")
    v, rr = ns["wd_konto_gruppe"]({"id": "x"}, "buy")
    check((v, rr) == (0, "buy"), "Python: Konto ohne Gruppe → (0, Richtung der Zeile)")
    # RICHTUNG JE KONTO (30.10.2026, S7 366d0252): k.w_richtung überstimmt Zeile und g_gegen, Versatz bleibt
    G = ns["wd_konto_gruppe"]
    check(G({"id": "x", "w_richtung": "sell"}, "buy") == (0, "sell"), "Python: w_richtung ohne Gruppe überstimmt die Zeile")
    check(G({"id": "x", "gruppe": "a", "g_versatz_min": 7, "g_gegen": True, "w_richtung": "buy"}, "buy") == (7, "buy"),
          "Python: w_richtung überstimmt g_gegen, Versatz bleibt")
    check(G({"id": "x", "gruppe": "a", "g_versatz_min": 7, "g_gegen": True, "w_richtung": "quer"}, "buy") == (7, "sell"),
          "Python: ungültige w_richtung → wie bisher (g_gegen)")
    row = {"status": "geplant", "start_um": mitternacht.isoformat(), "richtung": "buy", "user_id": "u", "name": "u",
           "konten": [{"id": "k1", "aktiv": True, "w_richtung": "sell", "firm": "Tradeify"}, {"id": "k2", "aktiv": True, "firm": "Tradeify"}]}
    rj = {s["key"].split(":")[2]: s["richtung"] for s in ns["ap_wd_block_starts"]([row], mitternacht, {})}
    check(rj.get("k1") == "sell" and rj.get("k2") == "buy", f"ap_wd_block_starts nimmt die Konto-Richtung ({rj})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
