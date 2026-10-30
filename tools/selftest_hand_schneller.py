#!/usr/bin/env python3
"""Selbsttest HAND-SCHNELLER + MASTER-EXIT BEI GEKÜRZTEM KONTO (30.10.2026, Chris pc-c19p2l, Orbit f35ba6ae Apex …0005: Reader sah den
Master zu 04:38:10,923 UTC, Schließbefehl 04:38:11,934, Copier 04:38:12,434 „Position war schon zu (hand)" — Finn war ~1 s schneller;
master_exit fehlte, weil der Exit-Fill nur bei vollem Kontotext ('ja') zählte). Prüft über JavaScriptCore:
  hedgeHandSchneller / hedgeGrundText / swAuswertung (Weg „Userscript (Hand schneller)", kein Overshoot) und hedgeExitFillWahl mit 'kurz'.
Aufruf:  python3 tools/selftest_hand_schneller.py"""
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


UMGEBUNG = r"""
const window = {}, KONTO_KURZ_MIN = 12
function hedgeKontoPasst(t, id){ return String(t).split(/[^A-Z0-9]+/).includes(id) }
function tvSymbolWurzel(s){ return /^MNQ/.test(String(s)) ? 'MNQ' : /^NQ/.test(String(s)) ? 'NQ' : '' }
"""
code = "\n".join([UMGEBUNG, js_funktion("kontoTextBezug"), js_funktion("hedgeHandSchneller"), js_funktion("hedgeGrundText"),
                  zeile("  const SW_WEGE ="), zeile("  const SW_WEG_TXT ="), zeile("  const SW_WEG_VON ="), js_funktion("swAuswertung"),
                  js_funktion("hedgeExitFillWahl")])
# echter Hedge f35ba6ae (gekürzt auf die Felder der Rechnung)
CHRIS = {"status": "geschlossen", "grund": "hand", "grund_copier": "hand", "schon_zu": True, "richtung": "sell", "sl": 28888.2, "tp": 28668.92,
         "fill_close": 28862.49, "lots": 7.41, "wert_pro_punkt": 0.89288, "eur": 932.99, "close_at": "2026-10-30T04:38:11.934Z",
         "closed_at": "2026-10-30T04:38:12.434Z", "master_weg_at": "2026-10-30T04:38:10.923Z", "master_weg_quelle": "reader",
         "opened_at": "2026-10-30T03:19:13.433Z", "reader_kurz": {"exit": 29006.1}}
faelle = {
    "chris_alt": CHRIS,
    "mit_grund_tab": dict(CHRIS, grund_tab="sl_feed"),
    "grund_tab_hand": dict(CHRIS, grund_tab="hand"),
    "ohne_close_at": {k: v for k, v in CHRIS.items() if k != "close_at"},
    "nicht_schon_zu": dict(CHRIS, schon_zu=False),
    "ohne_master_weg": {k: v for k, v in CHRIS.items() if k not in ("master_weg_at", "master_weg_quelle")},
    "anderer_grund": dict(CHRIS, grund="level_tp"),
    "zu_vor_befehl": dict(CHRIS, closed_at="2026-10-30T04:38:11.000Z"),
    "level_mt5": dict(CHRIS, grund_tab="level_mt5"),
    "master_ende": dict(CHRIS, grund_tab="master_ende"),
    "bestaetigt_spaet": dict(CHRIS, closed_at="2026-10-30T04:38:30.000Z"),
    "alt_ohne_reader": dict(CHRIS, master_weg_quelle="feed"),
}
FILLS = [{"at": 1793335090500, "seite": "sell", "menge": 2, "preis": 29006.25, "symbol": "NQZ6", "konto": "PAAPEX668794000000"}]
lauf = "const out = {}\n" + "".join(
    f"{{ const h = {json.dumps(v)}; out[{json.dumps(k)}] = {{ hs: hedgeHandSchneller(h), text: hedgeGrundText(h.grund, h), s: swAuswertung({{ hedge: h }}) }} }}\n"
    for k, v in faelle.items()) + f"""
const F = {json.dumps(FILLS)}, ende = Date.parse('2026-10-30T04:38:10.923Z'), start = Date.parse('2026-10-30T03:19:11Z')
const o = {{ ext: 'PAAPEX6687940000005', seite: 'sell', menge: 2, wurzel: 'NQ', startMs: start, endeMs: ende }}
out.exit_ohne_kurzOk = hedgeExitFillWahl(F, o)
out.exit_kurz_preis = hedgeExitFillWahl(F, Object.assign({{}}, o, {{ kurzOk: x => Math.abs(x.preis - 29006.1) <= 3 }}))
out.exit_kurz_falsch = hedgeExitFillWahl(F, Object.assign({{}}, o, {{ kurzOk: x => Math.abs(x.preis - 28950) <= 3 }}))
out.exit_voll = hedgeExitFillWahl([Object.assign({{}}, F[0], {{ konto: 'PAAPEX6687940000005' }})], o)
out.exit_fremd = hedgeExitFillWahl([Object.assign({{}}, F[0], {{ konto: 'TDFYSL150463012290' }})], Object.assign({{}}, o, {{ kurzOk: () => true }}))
print(JSON.stringify(out))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(code + "\n" + lauf)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
os.unlink(pfad)
try:
    e = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout, r.stderr)
    sys.exit(1)

c = e["chris_alt"]
soll("Chris (Altdaten, ohne grund_tab): Hand schneller → Weg userscript", c["hs"] == "userscript" and c["s"]["weg"] == "userscript")
soll("Chris: Weg-Text „Userscript (Hand schneller)“", c["s"]["wegTxt"] == "Userscript (Hand schneller)" and c["s"]["handSchneller"] is True)
soll("Chris: kein Overshoot (Hand-Schluss liegt nicht am Level)", c["s"]["overPkt"] is None and c["s"]["overEur"] is None)
soll("Chris: Grund-Text nennt Reader + Hand schneller", "Reader" in c["text"] and "Hand schneller" in c["text"])
soll("grund_tab sl_feed → Weg radar", e["mit_grund_tab"]["s"]["weg"] == "radar" and "Radar" in e["mit_grund_tab"]["text"])
for k, txt in (("grund_tab_hand", "Tab selbst meldete hand"), ("ohne_close_at", "kein Schließbefehl"), ("nicht_schon_zu", "nicht schon zu"),
               ("ohne_master_weg", "kein Erkennungs-Stempel (Altdaten)"), ("level_mt5", "level_mt5 (Ticket weg = auch Hand)"),
               ("master_ende", "master_ende (jedes Plan-Ende)"), ("bestaetigt_spaet", "Bestätigung > 10 s nach dem Befehl"),
               ("alt_ohne_reader", "Altdaten ohne Reader-Erkennung"), ("anderer_grund", "Copier-Grund nicht hand"), ("zu_vor_befehl", "zu vor dem Befehl")):
    soll(f"kein Hand-schneller: {txt}", e[k]["hs"] == "")
soll("echte Hand-Schlüsse bleiben „von Hand“", e["grund_tab_hand"]["s"]["weg"] == "hand" and e["ohne_close_at"]["s"]["wegTxt"] == "von Hand")
soll("master_exit: gekürzter Text ohne kurzOk → kein Treffer (wie bisher)", e["exit_ohne_kurzOk"] is None)
soll("master_exit: gekürzter Text + Preis = Ausstieg aus dem Balance-Beweis → Treffer", (e["exit_kurz_preis"] or {}).get("preis") == 29006.25)
soll("master_exit: gekürzter Text, Preis passt nicht → kein Treffer", e["exit_kurz_falsch"] is None)
soll("master_exit: voller Text wie bisher", (e["exit_voll"] or {}).get("preis") == 29006.25)
soll("master_exit: fremdes Konto nie, auch mit kurzOk", e["exit_fremd"] is None)
soll("Close-Pfad schreibt grund_tab", "grund_copier: res.grund || null, grund_tab: grund || null," in HTML)

print(f"\n{'ALLES OK' if not fehler else f'{fehler} FEHLER'}")
sys.exit(1 if fehler else 0)
