#!/usr/bin/env python3
"""Selbsttest E2 — Einstellungen Funded Planer → Futures (Finn 04.11.2026 ~17:30 Dubai: „Alle Inputs … unten visuell und änderbar").
app.py fdp_regeln_anzeige / fdp_regeln_aendern (rein rechnend, mit den echten Funktionen aus app.py), Route-Verdrahtung und prophos.html-Teile
als Text. Der Planer selbst bleibt unverändert: gleiche Regel-Zeile → gleiche Rechnung (fdp_konto_rechnen vorher = nachher geprüft).
Ohne Netz. Aufruf: python3 tools/selftest_e2_fdp_einstellungen.py"""
import copy
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


HILFEN = ("_wd_num", "_liq_de", "_cme_handelstag", "ist_topstep_express", "liq_konto_boden", "liq_stufe", "_ap_norm", "ap_regel_finden", "_wd_konto_groesse", "liq_regel_waehlen", "_ap_tz")
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "time": time, "GP_SLAVE_PPL": 0.85,
      "_firm_norm": lambda x: str(x or ""), "hashlib": __import__("hashlib")}
i, j = SRC.index("FDP_TAKT_S = 300"), SRC.index('@app.route("/admin/funded-plan"')
k0, k1 = SRC.index("FDP_FEST = ["), SRC.index('@app.route("/admin/funded-plan/regeln"')
exec("\n".join(block(n) for n in HILFEN) + "\n" + SRC[i:j] + "\n" + SRC[k0:k1], ns)
anz, aend = ns["fdp_regeln_anzeige"], ns["fdp_regeln_aendern"]

REG = {"aktiv": True, "auto_bestaetigen": False, "updated_at": "2026-11-03T22:10:00.123+00:00", "user_ids": ["u1"],
       "zeiten": {"max_je_id_tag": 2, "firma_abstand_min": 15, "abstand_id_min": 90, "vorlauf_min": 15},
       "firmen": copy.deepcopy(ns["FDP_FIRMEN_STANDARD"])}
REG["firmen"][0]["je_groesse"]["150000"]["kontrakte"] = {"2": 0.9, "3": 0.1}
REG["firmen"][-1] = {"name": "FTMO Futures", "namen": ["ftmofutures"], "an": True, "symbol": "NQ", "lock_usd": 0, "tp_modus": "rest",
                     "je_groesse": {"50000": {"ziel_gewinn": [4750, 5000], "sl": [750, 850], "kontrakte": {"1": 1}, "dd": 3000, "daily_usd": 1000,
                                              "hedge_eur": 450, "kosten_eur": 120}}}
ALT = copy.deepcopy(REG)

# ── Anzeige
a = anz(REG)
check(a["quelle"] == "db" and a["aktiv"] is True and a["auto_bestaetigen"] is False and a["updated_at"] == REG["updated_at"], "Anzeige: Schalter + updated_at aus der Zeile")
check(a["zeiten"]["abstand_id_min"] == 90 and a["zeiten"]["tz"] == "Asia/Dubai", "Anzeige: zeiten = Standard überlagert mit der Zeile")
ap = next(f for f in a["firmen"] if f["name"] == "Apex Trader")
check(ap["an"] and ap["je_groesse"]["150000"]["kontrakte"] == {"2": 0.9, "3": 0.1} and ap["tp_modus"] == "normal", "Anzeige: Apex je Größe vollständig, Modus normal")
check(next(f for f in a["firmen"] if f["name"] == "FTMO Futures")["tp_modus"] == "rest", "Anzeige: FTMO Futures Modus rest")
fest = {x["key"]: x for x in a["fest"]}
check(fest["breakeven_tol"]["wert"] == 500 and fest["sl_min"]["wert"] == 100 and fest["firma_abstand"]["wo"] == "db" and fest["takt"]["wert"] == 5,
      "Anzeige: Konstanten aus dem Code (500 $, 100 $, Firmen-Abstand DB, Takt 5 min)")
check(anz(None)["quelle"] == "standard" and anz(None)["firmen"][0]["name"] == "Apex Trader", "ohne Zeile: Standard-Regeln, Quelle standard")
check(REG == ALT, "Anzeige ändert die Zeile nicht")

# ── Ändern: erlaubt
U = REG["updated_at"]
p, f = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"ziel_gewinn": 12500, "kontrakte": {"2": 0.8, "3": 0.2}}}}})
check(f is None and p["firmen"][0]["je_groesse"]["100000"]["ziel_gewinn"] == 12500 and p["firmen"][0]["je_groesse"]["100000"]["kontrakte"] == {"2": 0.8, "3": 0.2},
      f"Apex 100k Ziel + Kontrakte ändern ({f})")
check(p["firmen"][0]["je_groesse"]["150000"] == ALT["firmen"][0]["je_groesse"]["150000"] and p["firmen"][1:] == ALT["firmen"][1:], "andere Größen/Firmen bleiben unverändert")
check(REG == ALT, "Prüfung ändert die Eingabe-Zeile nicht (Kopie)")
p, f = aend(REG, {"updated_at": U, "firma": {"name": "FTMO Futures", "je_groesse": {"50000": {"sl": [700, 850], "ziel_gewinn": [4800, 5000]}}}})
check(f is None and p["firmen"][-1]["je_groesse"]["50000"]["sl"] == [700, 850] and p["firmen"][-1]["je_groesse"]["50000"]["ziel_gewinn"] == [4800, 5000], "Spanne bleibt Spanne")
p, f = aend(REG, {"updated_at": U, "zeiten": {"abstand_id_min": 60}, "schalter": {"auto_bestaetigen": True}})
check(f is None and p["zeiten"] == dict(ALT["zeiten"], abstand_id_min=60) and p["auto_bestaetigen"] is True and "firmen" not in p, "zeiten + Schalter ändern, Rest der zeiten bleibt")
p, f = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "an": False, "lock_usd": 150}})
check(f is None and p["firmen"][0]["an"] is False and p["firmen"][0]["lock_usd"] == 150, "Firma aus + Lock")

# ── Ändern: abgelehnt
def nein(body, text):
    p, f = aend(REG, body)
    check(p is None and bool(f), f"abgelehnt: {text} ({f})")


nein({"updated_at": "alt", "zeiten": {"vorlauf_min": 10}}, "veraltetes updated_at")
nein({"updated_at": U, "zeiten": {"firma_abstand_min": 10}}, "firma_abstand_min (fest in der DB)")
nein({"updated_at": U, "zeiten": {"max_je_id_tag": 2.5}}, "max_je_id_tag nicht ganz")
nein({"updated_at": U, "zeiten": {"max_je_id_tag": 0}}, "max_je_id_tag 0")
nein({"updated_at": U, "zeiten": {"neu": 1}}, "unbekanntes Zeit-Feld")
nein({"updated_at": U, "schalter": {"aktiv": "ja"}}, "Schalter kein bool")
nein({"updated_at": U, "user_ids": []}, "user_ids (nur über /ids)")
nein({"updated_at": U, "firma": {"name": "Gibt es nicht", "an": True}}, "unbekannte Firma")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"50000": {"dd": 2000}}}}, "neue Größe")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"daily_usd": 1000}}}}, "neuer Schlüssel")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"ziel_gewinn": -5}}}}, "negativer Wert")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"ziel_gewinn": [1, 2]}}}}, "Zahl als Spanne")
nein({"updated_at": U, "firma": {"name": "FTMO Futures", "je_groesse": {"50000": {"sl": [900, 800]}}}}, "Spanne von > bis")
nein({"updated_at": U, "firma": {"name": "FTMO Futures", "je_groesse": {"50000": {"sl": 800}}}}, "Spanne als Zahl")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"kontrakte": {"2": 0.5, "3": 0.2}}}}}, "Kontrakte ≠ 100 %")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"kontrakte": {"20": 1}}}}}, "Kontrakte > 10")
nein({"updated_at": U, "firma": {"name": "Tradeify", "lock_usd": 100}}, "lock_usd, wo keiner hinterlegt")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "an": "true"}}, "an kein bool")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"ziel_gewinn": True}}}}, "bool als Zahl")
nein({"updated_at": U}, "nichts zu ändern")
nein({"updated_at": U, "zeiten": {"vorlauf_min": 0}}, "vorlauf_min 0 (Planer rechnet 0 als 15)")
nein({"updated_at": U, "zeiten": {"abstand_id_min": 0}}, "abstand_id_min 0 (Bestätigen rechnet 0 als 90)")
p3, f3 = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"kontrakte": {"2": 0.667, "3": 0.333}}}}})
check(f3 is None and p3["firmen"][0]["je_groesse"]["100000"]["kontrakte"] == {"2": 0.667, "3": 0.333}, "Kontrakt-Anteile auf 3 Stellen wie eingegeben")
check(aend(None, {"updated_at": U})[0] is None, "ohne Zeile: nichts")

# ── Planer unverändert: dieselbe Zeile (durch Anzeige und eine Null-Änderung) rechnet gleich
R, jg = ns["fdp_konto_rechnen"], ns["fdp_je_groesse"]
ST100 = [{"minis": 3, "ab_balance": 100000, "daily_loss_usd": 1750}, {"minis": 6, "ab_balance": 105000, "daily_loss_usd": 2500}]
vor = R(ALT["firmen"][0], jg(ALT["firmen"][0], 100000), ST100, 101000.0, 101000.0, 350.0, 100000, 100000, kt_fest=2)
p, f = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"ziel_gewinn": 12000}}}})
nach = R(p["firmen"][0], jg(p["firmen"][0], 100000), ST100, 101000.0, 101000.0, 350.0, 100000, 100000, kt_fest=2)
check(f is None and vor == nach, "gleicher Wert gespeichert → gleiche Rechnung (fdp_konto_rechnen)")
p, f = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"100000": {"max_trade": 5000}}}})
nach2 = R(p["firmen"][0], jg(p["firmen"][0], 100000), ST100, 101000.0, 101000.0, 350.0, 100000, 100000, kt_fest=2)
check(nach2["tp"] == 5000 and vor["tp"] == 6000, "geänderter Wert wirkt (TP höchstens 5.000 statt 6.000)")

# ── Verdrahtung
rt = SRC[SRC.index('@app.route("/admin/funded-plan/regeln"'):SRC.index("# ══ FUNDED-CFD-PLANER")]
check("_planer_schreib_gate()" in rt and "admin_voll_uids()" in rt and "fdp_regeln_aendern(reg" in rt, "Route: Planer-Rechte + nur Admin/„Finn + Pascal“/„Pascal“ + Prüfung")
check('"updated_at": f"eq.{reg.get(\'updated_at\')}"' in rt and "409" in rt, "Route: Schreiben nur, wenn updated_at noch passt (sonst 409)")
gt = SRC[SRC.index("def admin_funded_plan():"):SRC.index("def fdp_vorschlaege_aufraeumen(")]
check('erg["regeln"] = fdp_regeln_anzeige(_fdp_regeln_laden()' in gt, "GET /admin/funded-plan hängt die Einstellungen an")
check("regeln: d.regeln || null" in HTML and "if(fd && !fc) try{ unten = e2EinstHtml(Q, x.admin) }" in HTML and "try{ e2Verdrahten(root) }" in HTML,
      "prophos.html: Q.regeln, Einstellungen unten nur bei Funded Futures, verdrahtet")
check("'[data-e2-pfad]', '[data-e2-save]'" in HTML, "Planer-Rechte-Schloss sperrt Eingaben + Speichern ohne Schreibrecht")
check("apdApi('POST', '/regeln', body, '/admin/funded-plan')" in HTML, "Speichern über die neue Route")
check('erg["regeln"]["darf"] = bool(_admin or str(_uid) in' in gt and "R.darf !== false" in HTML, "Eingaben nur offen, wenn der Server das Schreiben erlaubt (darf)")
check("updated_at: _e2.basis[karte] || R.updated_at" in HTML and "if(!(kk in _e2.basis)) _e2.basis[kk]" in HTML, "updated_at vom ersten Entwurf je Karte (kein stilles Überschreiben)")
check("fen = (Q && Q.zeiten) || {}" in HTML and "fen.von" in HTML, "Startfenster aus der Vorschau (fdp_fenster), nicht der Rückfall")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
