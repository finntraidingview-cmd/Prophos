#!/usr/bin/env python3
"""Selbsttest MG1 (23.11.2026, Master nach VF2): „Vorprüfung vor F9: zu wenig freie Marge … (Vorprüfung: nötig X, frei Y) — … nichts gesendet" zählt im
PC-Tab wie eine Sperre (sfGesperrt → Deckel sofort voll, kein Nachplanen bis SF_MAX), aber als Art 'marge' mit eigenem Text und Handgriff (Lots senken).
Der API-Rechengrund nach dem Klick („(API: nötig …)") zählt nie. Prüft die echten Funktionen aus prophos.html per JavaScriptCore (macOS) und die
Verdrahtung (Quelltext). Aufruf: python3 tools/selftest_mg1_marge_sperre.py   Kennungen erfunden."""
import json
import os
import subprocess
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
a = html.index("  const sfMargeZahl = x =>")
b = html.index("  const sfGesperrtSf = sf =>")
b = html.index("\n", b) + 1
code = html[a:b]

VORP = ("Vorprüfung vor F9: zu wenig freie Marge für dieses Volumen (Vorprüfung: nötig 108 140.09, frei 100 000.00) — Kontostand 100 000.00 — nichts gesendet. "
        "→ Volumen senken oder Marge prüfen [0.0s·Hand: Tempo 1.29 → 0.9s·Vorprüfung Marge: nötig 108140.09 / frei 100000.00]")
faelle = {
    "julian_msg": VORP,
    "julian_sf": "Geclaimt vor 4 min, danach still — letzte Order-Antwort: " + VORP,
    "schmal": VORP.replace("108 140.09", "108 140.09").replace("100 000.00)", "100 000.00)"),
    "api_nach_klick": "KEINE Bestaetigung binnen 12 s — Grund: zu wenig freie Marge für dieses Volumen (API: nötig 5 000.00, frei 3 000.00) — Kontostand 100 000.00 (API)",
    "trade_allowed": "F9-Dialog nicht gefunden — Grund: Handel am Konto gesperrt (account_info.trade_allowed = False) — Kontostand 89 987.00",
    "server": "KEINE Bestaetigung binnen 12 s — Grund: x (Server: Only position closing is allowed) → y",
    "anderes": "Vorprüfung vor F9: Lots unter dem Minimum — nichts gesendet",
}
if not os.path.exists(JSC):
    print("· JavaScriptCore fehlt — übersprungen")
    sys.exit(0)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "t.js")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(code + "\nvar F = " + json.dumps(faelle, ensure_ascii=False) + ";\nvar o = {};\nfor (var k in F) o[k] = sfGesperrt(F[k]);\n"
                 "o.sf_grund_vor_msg = sfGesperrtSf({ grund: '', msg: F.julian_sf });\no.sf_leer = sfGesperrtSf(null);\nprint(JSON.stringify(o));\n")
    r = subprocess.run([JSC, f], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {"fehler": (r.stdout + r.stderr)[-400:]}
j = o.get("julian_msg") or {}
check(j.get("art") == "marge" and abs(float(j.get("noetig") or 0) - 108140.09) < 0.01 and float(j.get("frei") or 0) == 100000.0
      and "nötig 108.140, frei 100.000" in str(j.get("quelle")), f"Julians Vorprüfungs-Meldung → art 'marge', nötig/frei gelesen ({j})")
check((o.get("julian_sf") or {}).get("art") == "marge" and (o.get("sf_grund_vor_msg") or {}).get("art") == "marge",
      "auch in start_fehler.msg („Geclaimt … letzte Order-Antwort: …“) erkannt")
check((o.get("schmal") or {}).get("art") == "marge" and abs(float((o.get("schmal") or {}).get("noetig") or 0) - 108140.09) < 0.01,
      "schmale/geschützte Leerzeichen in den Zahlen")
check(o.get("api_nach_klick") is None, "API-Rechengrund nach dem Klick → nie (Gegenprüfung N2)")
check((o.get("trade_allowed") or {}).get("art") == "sperre" and (o.get("trade_allowed") or {}).get("quelle") == "MT5: trade_allowed = False"
      and (o.get("server") or {}).get("quelle") == "Server: Only position closing is allowed", "bestehende Sperren unverändert (art 'sperre', gleiche quelle)")
check(o.get("anderes") is None and o.get("sf_leer") is None, "andere Vorprüfungs-Gründe / kein Flag → keine Sperre")

check("const sfDeckelVoll = sf => !!sf && (!!sfGesperrtSf(sf)" in html, "Deckel sofort voll über sfGesperrtSf → kein Nachplanen bis SF_MAX")
auto = html[html.index("function tplSfAuto(sf, D){"):]
auto = auto[:auto.index("\n  }\n")]
check("sfGesperrtSf(sf).art === 'marge' ? 'Kein Neuversuch — mit diesen Lots reicht die freie Marge nicht (MG1).'" in auto, "„Danach“-Text: kein Neuversuch, Grund Marge")
kn = html[html.index("if(gs && gs.art === 'marge'){"):]
kn = kn[:kn.index("if(gs) return { text:")]
check("zu wenig freie Marge für die Plan-Lots" in kn and "Lots im Plan senken" in kn and "neu: false" in kn and "Number(t && t.menge)" in kn,
      "„Braucht dich“: eigene Zeile mit Grund + Handgriff (Lots senken), kein ↻-Versprechen, Lots aus t.menge")
print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
