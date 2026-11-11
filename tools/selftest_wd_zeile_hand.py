#!/usr/bin/env python3
"""Selbsttest WD-Zeile von Hand (Finn 02.11.2026: Klick auf die Zeile im Winning-Day-Farmer ändert TP, Kontrakte, Risiko, Fusion €, Start, Richtung;
Rechte 19:20: „jede Admin-ID darf seine Slaves-IDs da editieren“; Apex mit Freigabe: Freigabe weg). Echte Funktionen aus app.py und prophos.html (jsc), ohne Netz.

Aufruf:  python3 tools/selftest_wd_zeile_hand.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
fehler = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        fehler.append(text)


ns = {"datetime": datetime, "timedelta": timedelta, "timezone": timezone}
exec(re.search(r"^WD_HAND_AKTIONEN = .*?(?=^PLANER_WD_AUTOMATIK)", app, re.S | re.M).group(0), ns)
DARF, UPD, KONTEN = ns["wd_hand_darf"], ns["wd_hand_upd"], ns["wd_hand_konten"]
FP, PASCAL, EMIN, MARC, JULIAN = "fp", "pascal", "emin", "marc", "julian"
GRUPPE_EMIN = {EMIN, JULIAN}
check(DARF(FP, MARC, None, True, GRUPPE_EMIN) and DARF(PASCAL, MARC, None, True, GRUPPE_EMIN), "Finn + Pascal und Pascal (volle Admins) bearbeiten HT-IDs")
check(not DARF(FP, JULIAN, None, True, GRUPPE_EMIN), "volle Admins bearbeiten keine IDs aus Emins Gruppe")
check(DARF(EMIN, JULIAN, GRUPPE_EMIN, False, GRUPPE_EMIN) and not DARF(EMIN, MARC, GRUPPE_EMIN, False, GRUPPE_EMIN), "Emin bearbeitet nur seine Gruppe")
check(DARF(MARC, MARC, None, False, GRUPPE_EMIN) and not DARF(MARC, FP, None, False, GRUPPE_EMIN), "andere IDs nur ihre eigenen Zeilen")

jetzt = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
plan = {"start_um": "2026-11-02T16:00:00+00:00", "master_firm": "Tradeify", "hedge_freigabe_at": None}
u, f = UPD({"master_tp": 300, "master_contracts": 2, "richtung": "sell", "hedge_eur": 120.5}, plan, jetzt)
check(f is None and u["master_tp"] == 300 and u["master_contracts"] == 2 and u["richtung"] == "sell" and u["hand_werte_at"] == jetzt.isoformat() and "start_um" not in u, "Werte + Hand-Marke, Start unverändert bleibt weg")
u, f = UPD({"start_um": "2026-11-02T15:01:00Z"}, plan, jetzt)
check(f and "2 min" in f, "Start unter 2 min verweigert")
u, f = UPD({"start_um": "2026-11-02T15:30:00Z"}, plan, jetzt)
check(f is None and u["start_um"].startswith("2026-11-02T15:30"), "Start in 30 min geht")
check(UPD({"master_contracts": 1.5}, plan, jetzt)[1] and UPD({"master_tp": -5}, plan, jetzt)[1] and UPD({"richtung": "x"}, plan, jetzt)[1] and UPD({}, plan, jetzt)[1], "Grenzen: halbe Kontrakte, negativer TP, falsche Richtung, nichts zu ändern")
u, f = UPD({"master_tp": 1499}, dict(plan, master_firm="Apex Trader", hedge_freigabe_at="2026-11-02T10:00:00Z"), jetzt)
check(u.get("hedge_freigabe_at", "x") is None, "Apex mit Freigabe: Freigabe gelöscht, neu bestätigen")
u, f = UPD({"master_tp": 300}, dict(plan, hedge_freigabe_at="2026-11-02T10:00:00Z"), jetzt)
check("hedge_freigabe_at" not in u, "andere Firmen: Freigabe bleibt")
u, f = UPD({"master_tp": 300, "master_contracts": 2}, plan, jetzt, True)
check(f is None and u["hand_werte_at"] is None, "Würfel-Werte: Hand-Marke weg")
k, ge = KONTEN([{"plan_id": "p1", "tp": 200, "kt": 1}, {"plan_id": "p2", "tp": 100}], "p1", {"master_tp": 300, "master_contracts": 2, "slave_risk": 90, "richtung": "sell", "hand_werte_at": "x"}, FP, "t")
check(ge and k[0]["tp"] == 300 and k[0]["kt"] == 2 and k[0]["slave"] == 90 and k[0]["w_richtung"] == "sell" and k[0]["hand"]["von"] == FP and k[1] == {"plan_id": "p2", "tp": 100}, "Tageszeile: Werte + k.hand nur am betroffenen Konto")
k, ge = KONTEN([{"plan_id": "p1", "hand": {"at": "t"}}], "p1", {"master_tp": 200, "hand_werte_at": None}, FP, "t", True)
check(ge and "hand" not in k[0], "Würfel-Werte: k.hand entfernt")

# Einbau: Gate, Sperren im Abgleich (PC + Mac), GET-Felder
check('not in PLANER_WD_AUTOMATIK + WD_HAND_AKTIONEN' in app and '"vormerken", "vormerken_weg") + WD_HAND_AKTIONEN' in app and "recht = wd_hand_darf(me, p.get(\"user_id\")" in app, "Route: eigene Rechte-Prüfung statt Planer-Gate, Gruppen-Besitz für eingeschränkte Logins")
check("if(k.hand || plan.handWerteAt) continue" in html and ".is('start_um_gestartet_at', null).is('hand_werte_at', null).select('*')" in html and "if(p.hand_werte_at || k.hand) continue" in html,
      "Abgleich (PC, auch in der DB) und Nachziehen (Mac) drehen Hand-Werte nicht zurück")
# nachgezogen 11.11.2026 (ST1, Slave 2): 543756bd WS1a-Nachtrag hängt "wd_sl:mt5_baseline->wd_sl" als nächste Zeile an die select-Liste —
# das Teilstück endet jetzt auf Komma statt Anführungszeichen; dieselben drei Felder
check(re.search(r'"hand_werte_at,master_firm,anz_frei:hedge_freigabe_at,?"', app) is not None, "GET liefert Hand-Marke, Firma, Freigabe")

js = "const window = {};\n" + html[html.index("  function wdzStartIso("):html.index("  // REIN RECHNEND (Test-Haken): Eingaben")] + """
const wdFarmHedge = (pr, risk, slave, an) => { pr.multiplier = 1.5; pr.hedge_faktor = 1.5; pr.slave_risk = slave; pr.hedge_eur = 99; pr.master_risk = risk }
""" + html[html.index("  function wdzFelder("):html.index("  window._wdz = ")] + """
const a = wdzStartIso('2026-11-02T16:00:00Z', '20:30'), b = wdzStartIso('2026-11-02T21:30:00Z', '02:10'), c = wdzStartIso('2026-11-02T16:00:00Z', '25:00')
const r = wdzFelder({ master_firm: 'Tradeify', anz_hedge_eur: 120 }, { kt: '2', tp: '300', risk: '500', slave: '90', richtung: 'sell' })
const o = wdzFelder({ master_firm: 'Topstep' }, { kt: '1', tp: '200', risk: '', slave: '' })
print(JSON.stringify({ a, b, c, r, o }))"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
rr = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
try:
    e = json.loads(rr.stdout.strip().splitlines()[-1])
except Exception:
    print(rr.stdout[-400:], rr.stderr[-400:]); e = {}
check(e.get("a") == "2026-11-02T16:30:00.000Z" and e.get("b") == "2026-11-02T22:10:00.000Z" and e.get("c") is None, "Start HH:MM Dubai → ISO am Tag des alten Starts (auch nach Mitternacht Dubai), 25:00 ungültig")
r = e.get("r") or {}
check(r.get("lots") == 3 and r["f"]["slave_risk"] == 90 and r["f"]["hedge_eur"] == 99 and r["f"]["richtung"] == "sell" and r["f"]["master_contracts"] == 2, "Fusion-Felder aus wdFarmHedge, Lots = Kontrakte × Multiplikator")
check("slave_risk" not in (e.get("o") or {}).get("f", {}) and (e.get("o") or {}).get("lots") is None, "Plan ohne Hedge: keine Fusion-Felder")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
