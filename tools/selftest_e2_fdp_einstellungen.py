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


HILFEN = ("_ist_tradeify_cfd", "wd_min_gewinn", "wd_firmen_regel", "_wd_num", "_liq_de", "_cme_handelstag", "ist_topstep_express", "liq_konto_boden", "liq_stufe", "_ap_norm", "ap_regel_finden", "_wd_konto_groesse", "liq_regel_waehlen", "_ap_tz")
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "time": time, "GP_SLAVE_PPL": 0.85,
      "_firm_norm": lambda x: str(x or ""), "hashlib": __import__("hashlib")}
i, j = SRC.index("FDP_TAKT_S = 300"), SRC.index('@app.route("/admin/funded-plan"')
k0, k1 = SRC.index("FDP_FEST = ["), SRC.index('@app.route("/admin/funded-plan/regeln"')
# Konstanten des WD-Farmers (E2b): dieselben Zeilen wie in app.py
_konst = "\n".join(z for z in SRC.splitlines() if z.startswith(("WD_GOOD_DAY_MIN = ", "WD_ZYKLUS_KT, WD_ZYKLUS_INSTR = ", "TRADEIFY_ZYKLUS_MIN_USD = ", "TRADEIFY_ZYKLUS_PUFFER = ", "TRADEIFY_AUSGLEICH_BESTAETIGEN = ")))
_vorg = SRC[SRC.index("WD_ZYKLUS_VORGABE = {"):SRC.index("WD_ZYKLUS_KT, WD_ZYKLUS_INSTR")]
_e4 = SRC[SRC.index("WD_FIRMEN_REGELN_STD = {"):SRC.index("\n\n\ndef wd_firmen_regel(")]   # E4: Standard der WD-Firmen-Regeln (Mindest-Gewinn je Zyklus)
exec(_konst + "\n" + _vorg + "\n" + _e4, ns)
b0, b1 = SRC.index("def fdp_start_bestaetigt("), SRC.index("def _fdp_login(")   # Bestätigen-Zeiten + FDP_KONST/fdp_konst (E2b-Nachtrag)
exec("\n".join(block(n) for n in HILFEN) + "\n" + SRC[i:j] + "\n" + SRC[b0:b1] + "\n" + SRC[k0:k1], ns)
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
check(a["konst"]["breakeven_tol"] == 500 and a["konst"]["sl_min"] == 100 and fest["firma_abstand"]["wo"] == "db" and fest["takt"]["wert"] == 5,
      "Anzeige: Grenzen mit Rückfall (500 $, 100 $), Firmen-Abstand DB-Riegel, Takt 5 min")
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

# ── E2b: Winning Day je Firma (fdp_wd_anzeige) — Werte aus denselben Funktionen/Konstanten wie der Farmer
W0 = ns["fdp_wd_anzeige"]


def W(*a):
    """fdp_wd_anzeige + besonders als Textzeilen (Name Wert Info) für die Prüfungen"""
    r = W0(*a)
    r["_dicts"] = r["besonders"]
    r["besonders"] = [f"{b['name']} {b['wert']} | {b.get('info', '')}" for b in r["besonders"]]
    return r
apex = W(REG["firmen"][0], {}, {"aktiv": True, "stuetz": [{"v": 2000, "ziel": 750, "satz": 400}, {"v": 4000, "ziel": 1500, "satz": 300}], "firmen": ["apex", "apex100"], "ab_zyklus": 2}, ["apex"])
g = {z["groesse"]: z for z in apex["groessen"]}
check(g["100000"]["min_usd"] == 300 and g["150000"]["min_usd"] == 350, "Apex: WD ab 300 $ (100k) / 350 $ (150k) — wd_min_gewinn")
check(g["100000"]["tp"] == [320, 340] and g["150000"]["tp"] == [370, 390] and g["150000"]["tp_quelle"] == "standard", "Apex: TP-Spanne Standard des Farmers je Größe")
check(apex["bestaetigen"] is True and any(b.startswith("Recoverer an · ab Zyklus 2") for b in apex["besonders"]) and any(b.startswith("bei −2.000 $ Verlust 750 $ / 400 €") for b in apex["besonders"]) and any(b.startswith("bei −4.000 $ Verlust 1.500 $ / 300 €") for b in apex["besonders"]), "Apex: Bestätigen + Recoverer aus der DB-Regel")
check(any(b.startswith("Recoverer nicht eingerichtet") for b in W(REG["firmen"][0], {}, None, [])["besonders"]), "ohne zyklus_regel: Recoverer nicht eingerichtet (wie wd_zyklus_konto keine_regel)")
check(any(b.startswith("Recoverer aus") for b in W(REG["firmen"][0], {}, {"aktiv": None}, [])["besonders"]), "zyklus_regel.aktiv null → aus wie im Farmer")
check(any(b.startswith("Recoverer an (150k)") for b in W(REG["firmen"][0], {}, {"aktiv": True, "firmen": ["apex"]}, [])["besonders"]), "firmen nur apex → gilt nur 150k")
_kt = lambda k, std=1: W({"name": "Tradeify", "je_groesse": {}}, {"kt": std, "regeln": {"kt": {"tradeify": k}}}, None, [])["groessen"][0]["kt"]
check(_kt([3, None]) == [3, 3] and _kt([3]) == [3, 3] and _kt([2, 1]) == [2, 2] and _kt([1.5, 2.5]) == [2, 3] and _kt(None, 2.5) == [3, 3], "Kontrakte wie wdKtSpanne (bis ≥ von, gerundet)")
vp = {"instr": "nq", "kt": 1, "regeln": {"fu": {"tradeify": [260, 280], "apex": [380, 400]}, "kt": {"tradeify": [1, 2]}}}
apex2 = W(REG["firmen"][0], vp, {"aktiv": False, "ab_zyklus": 3, "stuetz": [{"v": 1000, "ziel": 500, "satz": 450}]}, [])
g2 = {z["groesse"]: z for z in apex2["groessen"]}
check(g2["150000"]["tp"] == [380, 400] and g2["150000"]["tp_quelle"] == "wd-farmer" and g2["100000"]["tp_quelle"] == "standard", "TP aus wd_farmer_regeln.vorplan.regeln.fu, fehlender Schlüssel = Standard")
check(apex2["bestaetigen"] is False and any(b.startswith("Recoverer aus") for b in apex2["besonders"]) and not any(b.startswith("bei −") for b in apex2["besonders"]), "Recoverer aus der DB-Regel (zyklus_regel)")
tr = W({"name": "Tradeify", "je_groesse": {}}, vp, None, [])
check(tr["groessen"][0]["min_usd"] == 250 and tr["groessen"][0]["tp"] == [260, 280] and tr["groessen"][0]["kt"] == [1, 2] and tr["groessen"][0]["instr"] == "NQ", "Tradeify: 250 $, TP/Kontrakte aus dem Farmer")
check(any(b.startswith("Payout ab Zyklus 2 +1 $") for b in tr["besonders"]) and any(b.startswith("Ausgleichs-Trade Fehlbetrag + 30–60 $") for b in tr["besonders"]), "Tradeify: Zyklus im Plus")
lu = W({"name": "Lucid Trading", "je_groesse": {}}, vp, None, [])
check(lu["groessen"][0]["min_usd"] == 250 and lu["groessen"][0]["tp"] == [260, 280] and not any(b.startswith("Payout ab Zyklus") for b in lu["besonders"]) and any(b.startswith("Regeln wie Tradeify") for b in lu["besonders"]), "Lucid: 250 $, Tradeify-Werte, keine Zyklus-Regel")
check(W({"name": "Topstep", "je_groesse": {}}, {}, None, [])["groessen"][0]["min_usd"] == 150, "Topstep: 150 $")
check(W({"name": "FundedNext Futures", "je_groesse": {}}, {}, None, [])["groessen"][0]["min_usd"] == 250, "FundedNext Futures: 250 $")
ft = W(REG["firmen"][-1], {}, None, [])
check(ft["fehlt"] is True and ft["groessen"][0]["min_usd"] is None and ft["groessen"][0]["schluessel"] == "sonst", "FTMO Futures: noch nicht hinterlegt (kein Raten)")
check(W({"name": "Tradeify CFD", "je_groesse": {}}, {}, None, [])["groessen"][0]["min_usd"] is None, "Tradeify CFD zählt nie als Tradeify-WD")
gt2 = SRC[SRC.index("def admin_funded_plan():"):SRC.index("def fdp_vorschlaege_aufraeumen(")]
check('_f["wd"] = fdp_wd_anzeige(_f, _vp, _zr, _best, _fr)' in gt2 and "_fr = _wd_firmen_regeln_lesen()" in gt2 and "_wd_zyklus_regelzeile()" in gt2, "GET hängt WD je Firma an (Farmer-Zeile + Bestätigen-Firmen)")
check("const wdGruppe = !wd ? ''" in HTML and "${hedgeT}${wdGruppe}" in HTML and "data-e2-wd-link" in HTML and "noch nicht hinterlegt" in HTML, "Kachel Winning Day rechts (Planer & Hedge), Link zur Quelle, „noch nicht hinterlegt“")
check("e2In(" not in HTML.split("const wdGruppe")[1].split("detailK = `")[0], "WD-Kachel ohne Eingabefelder (keine zweite Schreibstelle)")
check(all(isinstance(b, dict) and b.get("name") and b.get("wert") for x in (apex, tr, lu) for b in x["_dicts"]), "Besonderheiten als Parameter {name, wert, info}")
check('class="e2-kchip e2-knur"' in HTML and "nur ansehen — ändern als „Finn + Pascal“ / „Pascal“" in HTML and "const e2I = t =>" in HTML, "Nur-ansehen-Chip in der Regel-Zeile (Grund im Tooltip), Erklärungen hinter ⓘ")

# ── E2b-Nachtrag: Grenzen aus dem Code in die DB + eigenes Startfenster — gleiche Werte → gleiche Pläne
KON, FE = ns["fdp_konst"], ns["fdp_fenster_eigen"]
std = KON({})
check(std == {"breakeven_tol": 500.0, "sl_min": 100.0, "tages_puffer": 100.0, "liq_puffer": 50.0, "liq_min": 300.0, "bestaetigen_vorlauf_min": 2.0, "bestaetigen_streu_min": 10.0},
      "fdp_konst ohne Spalte/Werte = die Konstanten (500/100/100/50/300 $, 2/10 min)")
check(KON({"konst": {"sl_min": "abc", "liq_min": -5, "breakeven_tol": True, "tages_puffer": 80}}) == dict(std, tages_puffer=80.0), "ungültige DB-Werte → Konstante, gültige gelten")
FT = REG["firmen"][-1]; jft = jg(FT, 50000)
for bal, peak in ((51200.0, 51200.0), (49400.0, 50000.0), (47300.0, 50000.0)):
    for kt in (None, 1):
        a1 = R(FT, jft, [], bal, peak, 0.0, 50000, 50000, random.Random(7), None, kt, "k-ftmo")
        a2 = R(FT, jft, [], bal, peak, 0.0, 50000, 50000, random.Random(7), None, kt, "k-ftmo", konst=std)
        if a1 != a2:
            break
check(a1 == a2, "FTMO Futures (Modus Rest): konst = Standard rechnet exakt wie ohne konst")
a3 = [R(ALT["firmen"][0], jg(ALT["firmen"][0], 100000), ST100, b, b, 350.0, 100000, 100000, kt_fest=2, konst=std) for b in (99600.0, 99400.0, 101000.0)]
a4 = [R(ALT["firmen"][0], jg(ALT["firmen"][0], 100000), ST100, b, b, 350.0, 100000, 100000, kt_fest=2) for b in (99600.0, 99400.0, 101000.0)]
check(a3 == a4, "Apex (Modus normal): konst = Standard rechnet exakt wie ohne konst (Break-even-Grenze, SL)")
b1 = R(ALT["firmen"][0], jg(ALT["firmen"][0], 100000), ST100, 99400.0, 99400.0, 350.0, 100000, 100000, kt_fest=2)
b2 = R(ALT["firmen"][0], jg(ALT["firmen"][0], 100000), ST100, 99400.0, 99400.0, 350.0, 100000, 100000, kt_fest=2, konst=dict(std, breakeven_tol=1000.0))
check(b1["tp_art"] == "break_even" and b2["tp_art"] == "normal", "geänderte Break-even-Grenze wirkt (99.400 $: 500 → Break-even, 1.000 → normal)")
c1 = R(FT, jft, [], 50400.0, 50400.0, 0.0, 50000, 50000, None, None, 1, "k-ftmo", konst=dict(std, liq_min=4000.0))
check(c1["aktion"] == "aus" and "4.000" in c1["grund"], "geänderter Mindestabstand zur Liq wirkt")
jetzt = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
check(ns["fdp_start_bestaetigt"](None, jetzt) == ns["fdp_start_bestaetigt"](None, jetzt, 60 * std["bestaetigen_vorlauf_min"]), "Bestätigen-Vorlauf: Standard = Konstante")
pl = [{"id": "p1", "fp_start": None, "firma": "ht|apex", "user_id": "u1"}, {"id": "p2", "fp_start": None, "firma": "ht|apex", "user_id": "u2"}]
v1 = ns["fdp_start_verteilen"](pl, [], jetzt, 900, 5400, random.Random(3))
v2 = ns["fdp_start_verteilen"](pl, [], jetzt, 900, 5400, random.Random(3), vorlauf_s=60 * std["bestaetigen_vorlauf_min"], streu_s=60 * std["bestaetigen_streu_min"])
check(v1 == v2, "Streuung beim Bestätigen: Standard = Konstante (gleiche Zeiten)")
check(FE(None) is None and FE({"von": "05:00", "bis": "18:00"}) == ("Asia/Dubai", 300, 1080) and FE({"von": "18:00", "bis": "05:00"}) is None
      and FE({"von": "5:00", "bis": "18:00"}) is None and FE({"von": "05:75", "bis": "18:00"}) is None and FE({"von": "05:00", "bis": "18:00", "tz": "UTC"}) is None, "eigenes Fenster: gültig/ungültig")
src_plan = SRC[SRC.index("def fdp_planen("):SRC.index("def fdp_tick(")]
check("fdp_fenster_eigen(zeiten.get(\"fenster_eigen\")) or fdp_fenster(ap_zeiten)" in src_plan and "konst=konst" in src_plan, "fdp_planen: eigenes Fenster vor Challenge-Planer, konst an die Rechnung")
check(SRC.count("fdp_fenster(ap_zeiten)") == 3 and "fdp_fenster_eigen" not in SRC[SRC.index("def fcp_planen("):SRC.index("def fcp_planen(") + 3000], "Funded CFD unverändert (kein eigenes Fenster, keine konst)")
# Ändern
REGK = dict(REG, konst={})
p, f = aend(REGK, {"updated_at": U, "konst": {"breakeven_tol": 750, "bestaetigen_streu_min": 5}})
check(f is None and p["konst"] == {"breakeven_tol": 750, "bestaetigen_streu_min": 5}, f"konst ändern ({f})")
nein({"updated_at": U, "konst": {"breakeven_tol": 700}}, "konst ohne Spalte (SQL fehlt)")
for body, txt in (({"sl_min": 0}, "sl_min 0"), ({"liq_puffer": 0}, "Liq-Puffer 0 (S9)"), ({"bestaetigen_streu_min": 0}, "Streuung 0 (Jitter)"), ({"liq_min": 20000}, "liq_min zu groß"), ({"takt": 5}, "Takt (Technik)"), ({"breakeven_tol": True}, "bool")):
    p, f = aend(REGK, {"updated_at": U, "konst": body}); check(p is None and bool(f), f"konst abgelehnt: {txt} ({f})")
p, f = aend(REG, {"updated_at": U, "zeiten": {"fenster_eigen": {"von": "05:00", "bis": "18:00", "tz": "Asia/Dubai"}}})
check(f is None and p["zeiten"]["fenster_eigen"] == {"von": "05:00", "bis": "18:00", "tz": "Asia/Dubai"} and p["zeiten"]["abstand_id_min"] == 90, "eigenes Fenster setzen, Rest der zeiten bleibt")
p, f = aend(dict(REG, zeiten=dict(REG["zeiten"], fenster_eigen={"von": "05:00", "bis": "18:00", "tz": "Asia/Dubai"})), {"updated_at": U, "zeiten": {"fenster_eigen": None}})
check(f is None and "fenster_eigen" not in p["zeiten"], "eigenes Fenster aus → zurück auf den Challenge-Planer")
nein({"updated_at": U, "zeiten": {"fenster_eigen": {"von": "18:00", "bis": "05:00"}}}, "Fenster von > bis")
nein({"updated_at": U, "zeiten": {"fenster_eigen": {"von": "05:00", "bis": "18:00", "x": 1}}}, "Fenster mit fremdem Feld")
an2 = anz(dict(REGK, konst={"sl_min": 150}, zeiten=dict(REG["zeiten"], fenster_eigen={"von": "05:00", "bis": "18:00", "tz": "Asia/Dubai"})))
check(an2["konst"]["sl_min"] == 150 and an2["konst"]["liq_min"] == 300 and an2["konst_spalte"] is True and an2["fenster_eigen"]["von"] == "05:00"
      and {x["key"] for x in an2["fest"]} == {"takt", "firma_abstand", "nq_ppl", "fusion_ppl"} and all(x["grund"] for x in an2["fest"]), "Anzeige: konst + Fenster, nur Technik/DB-Riegel/Kontraktwerte fest (mit Grund)")
check(anz(REG)["konst_spalte"] is False, "Anzeige erkennt fehlende Spalte konst")
check("if(karte === 'grenzen'){" in HTML and "e2In('z.fenster.von'" in HTML and "e2Sch('z.fenster.an'" in HTML and "body.konst = ko" in HTML, "Frontend: Grenzen + Fenster änderbar")

# ── E2d: Zielbild (Ablauf schlank · Firmen · Firma: Ziel/Consistency → Trade → Winning Day → Kontoliste · Sicherheit unten)
KA = ns["fdp_konto_anzeige"]
ka = KA(150000, {"ziel_gewinn": 15000}, 158000.0, {"nr": 1, "ab": None, "start": 150000.0}, ns["fdp_tage"], [], "k1")
check(ka["start"] == 150000 and ka["ziel"] == 165000 and ka["gewinn"] == 8000 and ka["max_tag"] == 0, "Kontoliste: Ziel/Gewinn wie fdp_konto_rechnen (Zyklus 1)")
ka2 = KA(150000, {"ziel_gewinn": 15000}, 158000.0, {"nr": 2, "ab": "2026-11-01", "start": None}, ns["fdp_tage"], [], "k1")
check(ka2["start"] == 158000 and ka2["ziel"] == 173000, "Kontoliste: Zyklus nach Payout ohne Trade startet bei der Balance (wie der Planer)")
r_a = R(ALT["firmen"][0], jg(ALT["firmen"][0], 150000), [{"minis": 4, "ab_balance": 150000, "daily_loss_usd": 2500}], 158000.0, 158000.0, 550.0, 150000, 150000, kt_fest=2, konto_id="k1")
check(r_a["ziel"] == ka["ziel"] and r_a["start"] == ka["start"] and r_a["gewinn"] == ka["gewinn"], "Kontoliste = Rechnung des Planers (Ziel, Start, Gewinn)")
p, f = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "consistency_pct": 40}})
check(f is None and p["firmen"][0]["consistency_pct"] == 40, "Consistency je Firma setzen (neuer Anzeige-Parameter erlaubt)")
p, f = aend(dict(REG, firmen=[dict(REG["firmen"][0], consistency_pct=50)] + REG["firmen"][1:]), {"updated_at": U, "firma": {"name": "Apex Trader", "consistency_pct": None}})
check(f is None and "consistency_pct" not in p["firmen"][0], "Consistency aus → Schlüssel weg")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "consistency_pct": 5}}, "Consistency unter 10 %")
r_c = R(dict(ALT["firmen"][0], consistency_pct=40), jg(ALT["firmen"][0], 150000), [{"minis": 4, "ab_balance": 150000, "daily_loss_usd": 2500}], 158000.0, 158000.0, 550.0, 150000, 150000, kt_fest=2, konto_id="k1")
check(r_c == r_a, "Consistency ändert die Planer-Rechnung nicht (nur Anzeige)")
src_plan2 = SRC[SRC.index("def fdp_planen("):SRC.index("def fdp_tick(")]
check('zeile["anzeige"] = fdp_konto_anzeige(' in src_plan2 and "rnd" not in SRC[SRC.index("def fdp_konto_anzeige("):SRC.index("def fdp_konto_rechnen(")], "Anzeige-Werte je Konto ohne Würfel (kein Einfluss auf die Pläne)")
check('type="range" class="e2-range"' in HTML and 'class="wd-set-grid"' in HTML and "${firmenK}${mitteK}${rechtsK}" in HTML and "const kontoZeile" not in HTML
      and "${ablauf}${hedgeT}${wdGruppe}" in HTML and '<div class="e2-block e2-global">' in HTML and "['max_trade', 'sl', 'dd', 'daily_usd'].filter" in HTML and "['kosten_eur', 'hedge_eur'].filter" in HTML,
      "Nachtrag 10: Firmen | Ziel & Trade (Ziel, Consistency, Trade, Kontrakte) | Planer & Hedge (globale Werte kompakt oben, im Planer, Kosten/Hedge/Lock, WD), keine Konten-Spalte")
check("konten: [...(d.geplant || []), ...(d.ziel || []), ...(d.ausgelassen || [])]" in HTML and "start: an.start ?? (typeof z.start === 'number'" in HTML, "Kontoliste aus den Zeilen des Laufs, Anzeige-Werte vor der Uhrzeit start")
check("data-e2-mehr" in HTML and "const sicherheit = !_e2.mehr ? '' :" in HTML, "Sicherheit hinter „mehr“")
check(HTML.index("e2Oben = e2EinstHtml") < HTML.index("const listen = `<div data-apg-anker=\"offen\">"), "Block steht vor „Zu bestätigen“ (direkt am Zeitstrahl)")

# ── E2g (Finn 05.11.2026: „Bei denen noch auf ‚Plus‘ klicken und mehr hinzufügen“): Kontrakte-Zeilen frei, Planer würfelt mit den neuen Anteilen
import random as _rnd
p, f = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"150000": {"kontrakte": {"2": 0.7, "3": 0.2, "4": 0.1}}}}})
check(f is None and p["firmen"][0]["je_groesse"]["150000"]["kontrakte"] == {"2": 0.7, "3": 0.2, "4": 0.1}, "E2g: neue Zeile 4 Kontrakte angenommen (ganzes Dict ersetzt)")
pw, fw = aend(REG, {"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"150000": {"kontrakte": {"3": 1}}}}})
check(fw is None and pw["firmen"][0]["je_groesse"]["150000"]["kontrakte"] == {"3": 1}, "E2g: Zeile entfernt → Schlüssel weg (kein Zusammenführen mit dem alten Dict)")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"150000": {"kontrakte": {"2": 0.7, "3": 0.2, "4": 0.05}}}}}, "E2g: Summe 95 %")
nein({"updated_at": U, "firma": {"name": "Apex Trader", "je_groesse": {"150000": {"kontrakte": {"0": 0.5, "2": 0.5}}}}}, "E2g: 0 Kontrakte")
KT = ns["fdp_kontrakte"]
rr = _rnd.Random(7)
zz = [KT(p["firmen"][0]["je_groesse"]["150000"]["kontrakte"], 6, rr) for _ in range(4000)]
anteil = {k: zz.count(k) / len(zz) for k in (2, 3, 4)}
check(set(zz) == {2, 3, 4} and abs(anteil[2] - 0.7) < 0.03 and abs(anteil[3] - 0.2) < 0.03 and abs(anteil[4] - 0.1) < 0.03,
      f"E2g: Würfel folgt den neuen Anteilen 70/20/10 (gemessen {anteil[2]:.2f}/{anteil[3]:.2f}/{anteil[4]:.2f})")
check(max(KT({"2": 0.7, "3": 0.2, "4": 0.1}, 3, _rnd.Random(s)) for s in range(300)) == 3, "E2g: Minis der Stufe deckeln weiter (4 → 3 bei 3 Minis)")
r4 = {R(p["firmen"][0], jg(p["firmen"][0], 150000), [{"minis": 6, "ab_balance": 150000, "daily_loss_usd": 2500}], 158000.0, 158000.0, 550.0, 150000, 150000,
        konto_id="k1", rnd=_rnd.Random(s)).get("kontrakte") for s in range(400)}
check(r4 == {2, 3, 4}, f"E2g: fdp_konto_rechnen plant mit der neuen Zeile (Kontrakte {sorted(r4)})")
check("data-e2-ktadd" in HTML and "data-e2-ktx" in HTML and "data-e2-ktsel" in HTML and "ktK.length > 1" in HTML and "muss 100 % sein" in HTML
      and "if(!e2KtBeruehrt(i, g, v)) continue" in HTML and "!n || sp ? ' disabled'" in HTML and "'[data-e2-ktadd]', '[data-e2-ktx]', '[data-e2-ktsel]'" in HTML,
      "E2g Frontend: + Zeile, × (nicht bei der letzten), Anzahl wählbar, Summe ≠ 100 % sperrt Speichern, Schloss kennt die Knöpfe")

# ── Verdrahtung
rt = SRC[SRC.index('@app.route("/admin/funded-plan/regeln"'):SRC.index("# ══ FUNDED-CFD-PLANER")]
check("_planer_schreib_gate()" in rt and "admin_voll_uids()" in rt and "fdp_regeln_aendern(reg" in rt, "Route: Planer-Rechte + nur Admin/„Finn + Pascal“/„Pascal“ + Prüfung")
check('"updated_at": f"eq.{reg.get(\'updated_at\')}"' in rt and "409" in rt, "Route: Schreiben nur, wenn updated_at noch passt (sonst 409)")
gt = SRC[SRC.index("def admin_funded_plan():"):SRC.index("def fdp_vorschlaege_aufraeumen(")]
check('erg["regeln"] = fdp_regeln_anzeige(_fdp_regeln_laden()' in gt, "GET /admin/funded-plan hängt die Einstellungen an")
check("regeln: d.regeln || null" in HTML and "if(fd && !fc) try{ e2Oben = e2EinstHtml(Q, x.admin) }" in HTML and "${T.zeitstrahl}</div>` + e2Oben" in HTML and "try{ e2Verdrahten(root) }" in HTML,
      "prophos.html: Q.regeln, Einstellungen unten nur bei Funded Futures, verdrahtet")
check("'[data-e2-pfad]', '[data-e2-save]'" in HTML, "Planer-Rechte-Schloss sperrt Eingaben + Speichern ohne Schreibrecht")
check("apdApi('POST', '/regeln', body, '/admin/funded-plan')" in HTML, "Speichern über die neue Route")
check('erg["regeln"]["darf"] = bool(_admin or str(_uid) in' in gt and "R.darf !== false" in HTML, "Eingaben nur offen, wenn der Server das Schreiben erlaubt (darf)")
check("updated_at: _e2.basis[karte] || R.updated_at" in HTML and "if(!(kk in _e2.basis)) _e2.basis[kk]" in HTML, "updated_at vom ersten Entwurf je Karte (kein stilles Überschreiben)")
check("fen = (Q && Q.zeiten) || {}" in HTML and "fen.von" in HTML, "Startfenster aus der Vorschau (fdp_fenster), nicht der Rückfall")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
