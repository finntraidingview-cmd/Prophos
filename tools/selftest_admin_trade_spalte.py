#!/usr/bin/env python3
"""Selbsttest TRADE-SPALTE in Admin → Alle Accounts (20.10.2026, Finn 20:25 Dubai: „Kannst du hier in der Übersicht hinschreiben, ob der
Trade aktuell gerade aktiv ist, schon läuft, damit ich weiß, welchen ich noch abarbeiten muss?").
Aufruf:  python3 tools/selftest_admin_trade_spalte.py
Prueft: (1) admKontoTradeInfo (echt per osascript/JXA): laufend vor geplant vor Überprüfen, nächster geplanter Start, Echo-Lots vs.
Futures-Kontrakte, Polar auch am Slave-Konto, anderer Tag mit Datum, fremdes Konto → null; (2) Spalte im Markup rechts neben Balance,
Chip-Klassen, Klick → Radar mit ID-Filter, Lader über tplLiveLaden (keine neue Datenquelle), Mobil-Regel. Ohne Netz, Platzhalter-IDs."""
import json
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


m = re.search(r"    function admKontoTradeInfo\(accId, zeilen, jetzt\)\{\n.*?\n    \}", HTML, re.S)
check(bool(m), "admKontoTradeInfo gefunden")
JETZT = "2026-10-20T15:00:00.000Z"   # 19:00 Dubai
Z = [
    {"plan_id": "p-lauf", "konto_id": "k1", "user_id": "u1", "status": "open", "plattform": "orbit", "richtung": "buy", "kt": 2, "symbol_root": "NQ", "started_at": "2026-10-20T10:53:00Z"},
    {"plan_id": "p-plan1", "konto_id": "k1", "user_id": "u1", "status": "planned", "plattform": "orbit", "richtung": "sell", "kt": 3, "symbol_root": "NQ", "start_um": "2026-10-20T16:32:00Z"},
    {"plan_id": "p-plan-alt", "konto_id": "k2", "user_id": "u1", "status": "planned", "plattform": "orbit", "richtung": "sell", "kt": 1, "symbol_root": "MNQ", "start_um": "2026-10-20T08:00:00Z"},
    {"plan_id": "p-plan-neu", "konto_id": "k2", "user_id": "u1", "status": "planned", "plattform": "orbit", "richtung": "buy", "kt": 2, "symbol_root": "NQ", "start_um": "2026-10-20T16:10:00Z"},
    {"plan_id": "p-rev", "konto_id": "k3", "user_id": "u2", "status": "review", "plattform": "echo", "richtung": "sell", "lots": 2.5, "ended_at": "2026-10-20T12:27:00Z"},
    {"plan_id": "p-echo", "konto_id": "k4", "user_id": "u2", "status": "open", "plattform": "echo", "richtung": "buy", "lots": 1.5, "started_at": "2026-10-19T10:05:00Z"},
    {"plan_id": "p-polar", "konto_id": "k5", "slave_account_id": "k6", "user_id": "u3", "status": "open", "plattform": "polar", "richtung": "sell", "kt": 3, "symbol_root": "NQ", "slave_richtung": "buy", "slave_lots": 1.2, "started_at": "2026-10-20T11:50:00Z"},
    {"plan_id": "p-done", "konto_id": "k7", "user_id": "u2", "status": "completed", "plattform": "orbit", "richtung": "buy", "kt": 2, "ended_at": "2026-10-20T09:00:00Z"},
]
if m and shutil.which("osascript"):
    js = (m.group(0) + "\nvar Z = " + json.dumps(Z) + ";\n"
          "JSON.stringify(['k1','k2','k3','k4','k5','k6','k7','k9'].map(function(k){ var r = admKontoTradeInfo(k, Z, '" + JETZT + "'); return r ? [r.art, r.text, r.plan_id, r.uid] : null }))")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout.strip())
    except ValueError:
        v = None
    check(isinstance(v, list) and len(v) == 8, f"admKontoTradeInfo läuft ({(r.stderr or '').strip()[:120]})")
    if isinstance(v, list) and len(v) == 8:
        k1, k2, k3, k4, k5, k6, k7, k9 = v
        check(k1 and k1[0] == "lauf" and k1[1] == "läuft · BUY 2 × NQ · seit 14:53" and k1[2] == "p-lauf" and k1[3] == "u1", f"k1: laufend schlägt geplant — {k1}")
        check(k2 and k2[0] == "plan" and k2[1] == "geplant · 20:10" and k2[2] == "p-plan-neu", f"k2: nächster geplanter Start (nicht der verpasste von 12:00) — {k2}")
        check(k3 and k3[0] == "pruef" and k3[1] == "Überprüfen" and k3[2] == "p-rev", f"k3: review = Überprüfen — {k3}")
        check(k4 and k4[0] == "lauf" and k4[1] == "läuft · BUY 1,5 Lot · seit 19.10. 14:05", f"k4: Echo mit Lots, anderer Tag mit Datum — {k4}")
        check(k5 and k5[0] == "lauf" and k5[1] == "läuft · SELL 3 × NQ · seit 15:50", f"k5: Polar Master-Seite — {k5}")
        check(k6 and k6[0] == "lauf" and k6[1] == "läuft · BUY 1,2 Lot · seit 15:50" and k6[3] == "u3", f"k6: Polar Slave-Konto zählt als laufend — {k6}")
        check(k7 is None, "k7: nur completed → kein Chip („–\")")
        check(k9 is None, "k9: fremdes Konto ohne Zeilen → null")
else:
    print("… osascript fehlt — nur Textprüfungen")

# (2) Markup, Chip, Klick, Lader, Mobil
TH = HTML.find('— Klick öffnet den Radar mit dieser ID">Trade</th>')
check(TH > 0 and '<th>Balance</th>' in HTML[TH - 600:TH] and HTML.find('>Planer</th>', TH) - TH < 400, "Spaltenkopf „Trade\" zwischen Balance und Planer (Admin → Alle Accounts)")
check("            <td>${trade}</td>\n            <td style=\"padding-right:20px\">${planer}</td>" in HTML, "Zelle rechts neben Balance, vor Planer")
check("function admKontoTradeChipHtml(a, r){" in HTML and "const info = admKontoTradeInfo(a && a.id, [..._tpl.lt.values()], new Date().toISOString())" in HTML,
      "Chip aus _tpl.lt (Live-Trades des Planers, dieselbe Quelle wie der Radar)")
check("adm-k-trade is-${info.art}" in HTML and "#dashboard-view .adm-k-trade.is-lauf{" in HTML and ".adm-k-trade.is-pruef{" in HTML and ".adm-k-trade.is-plan{" in HTML, "Chip-Klassen läuft/geplant/Überprüfen mit CSS")
check("data-adm-k-radar=" in HTML and "function admKontoRadarOeffnen(uid){" in HTML and "wdlPersonUmschalten(uid)" in HTML and "('wdlive')" in HTML, "Klick → Radar mit ID-Filter (bestehender Weg)")
check("async function admKontenTradesLaden(){" in HTML and "await tplLiveLaden(); if(_tpl.ltHolAt !== vorher) admKontenRender()" in HTML, "Lader nutzt tplLiveLaden (kein neuer Endpunkt), zeichnet danach neu")
check("if(Date.now() - (_tpl.ltAt || 0) > 50000) admKontenTradesLaden()" in HTML, "Render stößt den Lader an, wenn die Live-Trades älter als 50 s sind")
check("@media (max-width:820px){ #dashboard-view .adm-k-trade{font-size:10.5px;padding:1px 7px} }" in HTML, "Mobil-Regel für den Chip")
check("Regel" not in (m.group(0) if m else "Regel") or "keine Regel" in HTML[HTML.find("TRADE-SPALTE (20.10.2026"):HTML.find("TRADE-SPALTE (20.10.2026") + 900], "nur Zustand, keine Regelprüfung")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
