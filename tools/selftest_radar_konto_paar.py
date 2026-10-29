#!/usr/bin/env python3
"""Selbsttest RADAR-KONTO-PAAR (30.10.2026, Finn: „Unter Radar werden mir manchmal doppelte Trades angezeigt"): prophos.html wdlKontoPaare
(REIN, über JavaScriptCore) — dasselbe Konto mit beendetem, nicht abgehaktem Trade (review, Erledigt) und laufendem nächsten Trade (open,
Läuft) bekommt je Seite einen Chip mit Sprungziel; dazu die Verdrahtung am Quelltext (Chip in der Zeile, Klick vor dem Zeilen-Klick, CSS).
Aufruf:  python3 tools/selftest_radar_konto_paar.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def js_funktion(name):
    i = HTML.index(f"  function {name}(")
    return HTML[i:HTML.index("\n  }\n", i) + 4]


def zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


code = "\n".join([zeile("  const wdlTid = t =>"), zeile("  const wdlUid = t =>"), "function wdlIstPolar(t){ return !!t && (t.plattform === 'polar' || t.route === 'polar') }",
                  js_funktion("wdlKontoPaare")])
faelle = {
    "paar": [{"id": "alt", "status": "review", "konto_id": "k1", "ended_at": "2026-10-29T09:08:00Z"},
             {"id": "neu", "status": "open", "konto_id": "k1", "started_at": "2026-10-29T10:06:00Z"}],
    "anderes_konto": [{"id": "a", "status": "review", "konto_id": "k1"}, {"id": "b", "status": "open", "konto_id": "k2"}],
    "nur_review": [{"id": "a", "status": "review", "konto_id": "k1"}, {"id": "b", "status": "review", "konto_id": "k1"}],
    "completed": [{"id": "a", "status": "completed", "konto_id": "k1"}, {"id": "b", "status": "open", "konto_id": "k1"}],
    "polar": [{"id": "a", "status": "review", "konto_id": "k1", "route": "polar"}, {"id": "b", "status": "open", "konto_id": "k1"}],
    "ohne_konto_id": [{"id": "a", "status": "review", "user_id": "u", "konto": {"kontonr_ende": "7813"}},
                      {"id": "b", "status": "open", "user_id": "u", "konto": {"kontonr_ende": "7813"}}],
    "andere_id_gleiche_nr": [{"id": "a", "status": "review", "user_id": "u1", "konto": {"kontonr_ende": "7813"}},
                             {"id": "b", "status": "open", "user_id": "u2", "konto": {"kontonr_ende": "7813"}}],
    "zwei_alte": [{"id": "r1", "status": "review", "konto_id": "k1", "ended_at": "2026-10-29T08:00:00Z"},
                  {"id": "r2", "status": "review", "konto_id": "k1", "ended_at": "2026-10-29T09:00:00Z"},
                  {"id": "o", "status": "open", "konto_id": "k1", "started_at": "2026-10-29T10:00:00Z"}],
}
lauf = "const out = {}\n" + "".join(f"out[{json.dumps(k)}] = [...wdlKontoPaare({json.dumps(v)}).entries()]\n" for k, v in faelle.items()) + "print(JSON.stringify(out))\n"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(code + "\n" + lauf)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
os.unlink(pfad)
try:
    erg = {k: dict((a, b) for a, b in v) for k, v in json.loads(r.stdout.strip().splitlines()[-1]).items()}
except Exception:
    print(r.stdout, r.stderr)
    sys.exit(1)

soll("Paar: alter Trade (review) ⇄ nächster (open), je Seite Chip mit Ziel der anderen",
     erg["paar"] == {"neu": {"art": "voriger", "ziel": "alt"}, "alt": {"art": "naechster", "ziel": "neu"}})
soll("anderes Konto → kein Chip", erg["anderes_konto"] == {})
soll("zwei Review-Zeilen ohne laufenden Trade → kein Chip", erg["nur_review"] == {})
soll("abgehakter Trade (completed) zählt nicht", erg["completed"] == {})
soll("Polar zählt nicht", erg["polar"] == {})
soll("ohne konto_id: ID + Kontonummer-Ende", set(erg["ohne_konto_id"]) == {"a", "b"})
soll("gleiche Kontonummer, andere ID → kein Chip", erg["andere_id_gleiche_nr"] == {})
soll("zwei alte Trades: Läuft-Chip springt zum jüngsten, beide alten springen zum laufenden",
     erg["zwei_alte"]["o"]["ziel"] == "r2" and erg["zwei_alte"]["r1"] == {"art": "naechster", "ziel": "o"})

soll("Chip in der Zeile neben SL/TP-Chip", "${wdlSltpChip(t)}${wdlPaarChip(t)}" in HTML)
soll("Paare je Render aus allen sichtbaren Trades", "_wdlPaare = wdlKontoPaare(alleTrades)" in HTML)
i_pa, i_tr = HTML.index("closest('[data-wdl-paar]')"), HTML.index("closest('[data-wdl-trade]'); if(!c) return")
soll("Klick auf den Chip vor dem Zeilen-Klick (Chart-Linien), mit return", i_pa < i_tr and "wdlPaarSpringen(pa.getAttribute('data-wdl-paar')); return" in HTML)
soll("Texte wie bestellt", "'voriger Trade noch nicht abgehakt'" in HTML and "'nächster Trade läuft'" in HTML)
soll("CSS: Chip + Aufleuchten der Zielzeile", ".wdl-paar{" in HTML and ".wdl-z.is-paar-ziel{" in HTML)
print("ALLE OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
