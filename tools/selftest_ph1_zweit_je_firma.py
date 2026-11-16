#!/usr/bin/env python3
"""Selbsttest PH1 (16.11.2026, Finn: „Der Zweit-Start-Abstand soll je Firma gelten“): puls_heim_zweit_firma + puls_heim_zweit_pruefen mit
firmen[<_ap_norm>].zweit_usd des LAUFENDEN Trades. app.py importiert, _sb_all / _puls_heim_regel / _puls_heim_naehe ersetzt (die Nähe rechnet der
Ersatz aus den Schwellen, die puls_heim_zweit_pruefen übergibt — so wird geprüft, WELCHE Spanne ankommt). Ohne Netz.
Diff-Test: ohne Firmen-Eintrag (oder nur für andere Firmen) ist die Antwort bitgleich zu „immer globaler zweit_usd“ (alter Weg).
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_ph1_zweit_je_firma.py"""
import copy
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


U = "11111111-1111-1111-1111-111111111111"
NEU = {"id": "n1", "user_id": U, "status": "planned", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400, "master_firm": "Tradeify"}
REGEL = {"aktiv": True, "tp_usd": 2000, "liq_usd": 2000, "big_max_je_id": 2, "zweit_usd": 2500}
ZEILEN = []
REST = {}            # plan-id → (rest_tp_usd, rest_liq_usd) des laufenden Trades
ACC_FIRMA = {}       # plan-id → Konto-Firma (accounts.firm), sonst None
GESEHEN = {}         # plan-id → Schwellen, die puls_heim_zweit_pruefen übergab


def sb_all(t, p):
    return [dict(z) for z in ZEILEN]


def naehe(plaene, schw):
    out = []
    for p in plaene:
        acc = {"firm": ACC_FIRMA[p["id"]]} if ACC_FIRMA.get(p["id"]) else None
        s_tp, s_liq = schw(acc, p)
        GESEHEN[p["id"]] = (s_tp, s_liq)
        tp, liq = REST[p["id"]]
        nah = tp <= s_tp or liq <= s_liq
        grund = (f"{format(int(tp), ',').replace(',', '.')} $ vor dem TP" if tp <= s_tp else f"{format(int(liq), ',').replace(',', '.')} $ vor der Liq") if nah else ""
        out.append((p, {"nah": nah, "grund": grund, "rest_tp_usd": tp, "rest_liq_usd": liq, "tp_level": 1, "liq_level": 1},
                    {"plan": p["id"], "rest_tp_usd": tp, "rest_liq_usd": liq}, f"{p.get('master_firm')} …{p['id']}", "SELL 3 MNQ"))
    return out


app._sb_all = sb_all
app._puls_heim_regel = lambda: REGEL
app._puls_heim_naehe = naehe
app.puls_heim_markt_oeffnung = lambda jetzt=None: None   # Markteröffnung hier nicht Thema (eigener Test selftest_zwei_orbit)


def laufend(pid, firma, route="tvv2", acc_firma=None):
    ACC_FIRMA[pid] = acc_firma
    return {"id": pid, "user_id": U, "status": "open", "route": route, "orbit_v3": True, "hedge_eur": 400, "master_firm": firma,
            "master_name": f"50k {pid} → Funded"}


print("1) puls_heim_zweit_firma (rein)")
F = {"firmen": {"lucidtrading": {"tp_usd": 1000, "liq_usd": 500, "zweit_usd": 1000}, "fundednextfutures": {"zweit_usd": 1000},
                "apextrader": {"tp_usd": 900}, "kaputt": {"zweit_usd": -5}, "text": {"zweit_usd": "abc"}, "null": {"zweit_usd": None},
                "nullwert": {"zweit_usd": 0}}}
check(app.puls_heim_zweit_firma(F, "Lucid Trading", 2500.0) == 1000.0, "Lucid Trading → 1.000 (Schlüssel _ap_norm)")
check(app.puls_heim_zweit_firma(F, "FundedNext Futures", 2500.0) == 1000.0, "FundedNext Futures → 1.000")
check(app.puls_heim_zweit_firma(F, "LUCID trading", 2500.0) == 1000.0, "Schreibweise egal")
check(app.puls_heim_zweit_firma(F, "Apex Trader", 2500.0) == 2500.0, "Eintrag ohne zweit_usd → global")
check(app.puls_heim_zweit_firma(F, "Tradeify", 2500.0) == 2500.0, "keine Zeile für die Firma → global")
check(app.puls_heim_zweit_firma(F, "kaputt", 2500.0) == 2500.0, "negativ → global")
check(app.puls_heim_zweit_firma(F, "text", 2500.0) == 2500.0, "keine Zahl → global")
check(app.puls_heim_zweit_firma(F, "null", 2500.0) == 2500.0, "None → global")
check(app.puls_heim_zweit_firma(F, "nullwert", 2500.0) == 0.0, "0 ist ein gültiger Wert (wie der globale ≥ 0)")
check(app.puls_heim_zweit_firma(F, None, 2500.0) == 2500.0 and app.puls_heim_zweit_firma(F, "", 1234.0) == 1234.0, "ohne Firma → global")
check(app.puls_heim_zweit_firma(None, "Lucid Trading", 2500.0) == 2500.0, "Regel None → global")
check(app.puls_heim_zweit_firma({"firmen": "x"}, "Lucid Trading", 2500.0) == 2500.0, "firmen kein Objekt → global")
check(app.puls_heim_zweit_firma({}, "Lucid Trading", 2500.0) == 2500.0, "ohne firmen → global")

print("2) Zweit-Prüfung mit laufendem Lucid-50k (1.500 $ vor TP / 1.200 $ vor Liq)")
ZEILEN[:] = [laufend("a", "Lucid Trading")]
REST["a"] = (1500, 1200)
REGEL.pop("firmen", None)
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "zweit_wartet" and r["zweit_usd"] == 2500.0 and "Spanne 2.500 $" in r["grund"],
      f"ohne Firmen-Eintrag → wartet wie bisher (Spanne 2.500): {r.get('grund')}")
check(GESEHEN["a"] == (2500.0, 2500.0), "Nähe mit (2.500, 2.500) gerechnet")
REGEL["firmen"] = copy.deepcopy(F["firmen"])
r = app.puls_heim_zweit_pruefen(NEU)
check(r["frei"] is True and r["zweit_usd"] == 2500.0, f"mit lucidtrading.zweit_usd 1.000 → frei (Antwort zweit_usd bleibt global): {r}")
check(GESEHEN["a"] == (1000.0, 1000.0), "Nähe mit (1.000, 1.000) gerechnet")
check(r.get("zweit_andere") and r["zweit_andere"][0].get("rest_tp_usd") == 1500, "Abstand beim Start gemerkt (Z6) wie bisher")
REST["a"] = (800, 1200)
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "zweit_wartet" and r["zweit_usd"] == 1000.0 and "Spanne 1.000 $" in r["grund"] and r["rest_tp_usd"] == 800,
      f"800 $ vor TP < 1.000 → wartet, Spanne der Firma in Text und Feld: {r.get('grund')}")
check(r.get("big_trade") == {"plan": "a", "rest_tp_usd": 800, "rest_liq_usd": 1200}, "big_trade-Info wie bisher")
REST["a"] = (1500, 1000)
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "zweit_wartet", "genau 1.000 $ vor Liq → nah (≤ wie puls_heim_nah)")

print("3) Firma aus dem Konto (accounts.firm) vor master_firm")
ZEILEN[:] = [laufend("b", "Lucid", acc_firma="Lucid Trading")]
REST["b"] = (1500, 1500)
check(app.puls_heim_zweit_pruefen(NEU)["frei"] and GESEHEN["b"] == (1000.0, 1000.0), "master_firm „Lucid“, Konto „Lucid Trading“ → Konto-Firma zählt")
ZEILEN[:] = [laufend("c", "Lucid Trading", acc_firma="Tradeify")]
REST["c"] = (1500, 1500)
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "zweit_wartet" and GESEHEN["c"] == (2500.0, 2500.0), "Konto-Firma ohne Eintrag schlägt master_firm → global")

print("4) Spanne je laufendem Trade, nicht je neuem")
NEU_LUCID = dict(NEU, master_firm="Lucid Trading")
ZEILEN[:] = [laufend("d", "Tradeify")]
REST["d"] = (1500, 1500)
r = app.puls_heim_zweit_pruefen(NEU_LUCID)
check(not r["frei"] and r["code"] == "zweit_wartet" and GESEHEN["d"] == (2500.0, 2500.0) and "zweit_usd" in r and r["zweit_usd"] == 2500.0,
      "neuer Lucid neben laufendem Tradeify → Spanne des LAUFENDEN (global 2.500) → wartet")
REGEL["big_max_je_id"] = 3
ZEILEN[:] = [laufend("e", "Lucid Trading"), laufend("f", "FundedNext Futures")]
REST["e"], REST["f"] = (1500, 1500), (900, 3000)
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and "f" in r["grund"] and r["zweit_usd"] == 1000.0, f"zwei laufende, FNF 900 $ vor TP < 1.000 → wartet wegen FNF: {r.get('grund')}")
REST["f"] = (1100, 3000)
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "beide über ihrer eigenen Spanne → frei")
ZEILEN[:] = [laufend("k", "Lucid Trading"), laufend("l", "Apex Trader")]
REST["k"], REST["l"] = (1500, 1500), (2000, 5000)
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and "l" in r["grund"] and "Spanne 2.500 $" in r["grund"] and r["zweit_usd"] == 2500.0 and GESEHEN["k"] == (1000.0, 1000.0),
      f"wartend machender Trade ohne Firmen-Eintrag (Apex), anderer mit (Lucid) → Spanne global, Feld global: {r.get('grund')}")
REGEL["big_max_je_id"] = 2

print("5) Firmen-Sperre / voll / gesendet unverändert")
ZEILEN[:] = [laufend("g", "Tradeify")]
REST["g"] = (5000, 5000)
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "firma_laeuft", "gleiche Firma → firma_laeuft wie bisher")
ZEILEN[:] = [laufend("h", "Lucid Trading"), laufend("i", "Apex Trader")]
REST["h"], REST["i"] = (5000, 5000), (5000, 5000)
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "zweit_wartet", "big_max 2 und schon 2 → voll wie bisher")
ZEILEN[:] = [dict(laufend("j", "Lucid Trading"), status="planned", orbit_gesendet_at=app.datetime.now(app.timezone.utc).isoformat())]
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "zweit_wartet", "gerade gesendet → wartet wie bisher")

print("6) Diff-Test: ohne passenden Firmen-Eintrag bitgleich zum alten Weg (immer globaler zweit_usd)")
echt = app.puls_heim_zweit_firma
FIRMEN = ["Tradeify", "Apex Trader", "Lucid Trading", "FundedNext Futures", "Topstep", "Alpha Futures"]
rnd = random.Random(1611)
gleich, faelle = 0, 0
for i in range(400):
    n = rnd.randint(0, 2)
    ZEILEN[:] = []
    for k in range(n):
        pid = f"r{i}_{k}"
        ZEILEN.append(laufend(pid, rnd.choice(FIRMEN), route=rnd.choice(["tvv2", "tvv2", "tsv2"]), acc_firma=rnd.choice([None, None, rnd.choice(FIRMEN)])))
        REST[pid] = (rnd.choice([300, 900, 1000, 1500, 2400, 2500, 2600, 4000]), rnd.choice([400, 1000, 2000, 2500, 3000, 6000]))
    REGEL["big_max_je_id"] = rnd.choice([1, 2, 3])
    REGEL["zweit_usd"] = rnd.choice([2500, 1500, 3000])
    # Firmen-Einträge nur für Firmen, die in diesem Fall NICHT laufen (bzw. ohne zweit_usd) → darf nichts ändern
    laufende = {app._ap_norm((ACC_FIRMA.get(z["id"]) or z["master_firm"])) for z in ZEILEN}
    REGEL["firmen"] = {app._ap_norm(f): {"zweit_usd": 777, "tp_usd": 111} for f in FIRMEN if app._ap_norm(f) not in laufende}
    REGEL["firmen"].update({k: {"tp_usd": 999} for k in laufende})
    neu = dict(NEU, route=rnd.choice(["tvv2", "tsv2"]), master_firm=rnd.choice(FIRMEN))
    a = app.puls_heim_zweit_pruefen(neu)
    app.puls_heim_zweit_firma = lambda regel, firma, zu: zu   # alter Weg
    try:
        b = app.puls_heim_zweit_pruefen(neu)
    finally:
        app.puls_heim_zweit_firma = echt
    faelle += 1
    gleich += (a == b and list(a) == list(b))
check(gleich == faelle, f"{gleich}/{faelle} Fälle bitgleich (Inhalt und Schlüssel-Reihenfolge)")
REGEL.pop("firmen", None)
REGEL["zweit_usd"] = 2500

print("7) Urteil rein: ohne zweit_usd am Eintrag Text/Felder wie vorher")
a = {"name": "X", "art": "BUY 2 NQ", "nah": True, "grund": "1.800 $ vor dem TP", "rest_tp_usd": 1800, "rest_liq_usd": 4000}
u = app.puls_heim_zweit_urteil([a], 2, 2500.0)
check(u == {"frei": False, "code": "zweit_wartet", "rest_tp_usd": 1800, "rest_liq_usd": 4000,
            "grund": "1. Trade X (BUY 2 NQ) ist 1.800 $ vor dem TP — zweiter Start wartet (Spanne 2.500 $)"}, "ohne Feld: exakt wie bisher")
u = app.puls_heim_zweit_urteil([dict(a, zweit_usd=2500.0)], 2, 2500.0)
check("zweit_usd" not in u, "Feld = global → kein Zusatzfeld")
u = app.puls_heim_zweit_urteil([dict(a, zweit_usd=1000.0)], 2, 2500.0)
check(u.get("zweit_usd") == 1000.0 and "Spanne 1.000 $" in u["grund"], "Feld ≠ global → Spanne der Firma")

print()
print("FEHLER:" if FEHLER else "ALLES GRÜN", len(FEHLER) or "")
sys.exit(1 if FEHLER else 0)
