#!/usr/bin/env python3
"""Selbsttest HT ECHO-HEDGE B2 (app.py, 29.10.2026): eh_param, eh_hedge, eh_marge rein rechnend, dazu eh_tick / eh_zurueck mit
nachgebauter Datenbank (kein Netz). Geprüft:
- B2-Größe q = Satz ÷ 0,89, derselbe Multiplikator wie gp_multiplikator / tpMultiplierAusRisiko
- Rundung und Mindest-Lot
- 60-Lot-Grenze inkl. vorgemerkter Hedges, Marge nur über den Zuwachs des größeren Schenkels
- Takt: nur HT, nur CFD-Challenges auf mt5v2 im Fenster, Guard am Update, Gründe ohne Hedge einmal mit ⚪-Meldung,
  Schalter aus → zurück auf Echo V2
Aufruf: python3 tools/selftest_echo_hedge.py"""
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def ok(bed, txt):
    print(("  ok   " if bed else "  FEHL ") + txt)
    if not bed:
        FEHLER.append(txt)


def _wd_num(v):
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def lade(extra=None):
    src = open(APP, encoding="utf-8").read()
    i = src.index("\nEH_STANDARD = ")
    j = src.index("\n# ════", i)
    k = src.index("\ndef gp_multiplikator(") + 1
    gp = src[k:src.find("\n\n\n", k)]
    ns = {"_wd_num": _wd_num, "time": time, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "re": re}
    ns.update(extra or {})
    exec(gp + "\n" + src[i:j], ns)
    return ns


def rein():
    ns = lade()
    print("eh_param")
    p = ns["eh_param"]({})
    ok(p["an"] is False and p["netto_faktor"] == 0.89 and p["max_lots"] == 60.0 and p["min_lot"] == 0.01, "Standard aus, 0,89, 60 Lot, 0,01")
    p = ns["eh_param"]({"echo_hedge": {"an": True, "netto_faktor": 0.9, "max_lots": "x", "vorlauf_min": 2, "min_lot": True}})
    ok(p["an"] is True and p["netto_faktor"] == 0.9 and p["max_lots"] == 60.0 and p["vorlauf_min"] == 20.0 and p["min_lot"] == 0.01,
       "an + gültiger Faktor; Ungültiges einzeln auf Standard")
    ok(ns["eh_param"]({"echo_hedge": {"an": "true"}})["an"] is False, "an nur mit echtem true")

    print("eh_hedge (B2)")
    h, g = ns["eh_hedge"](0.0446, 20, 1.0, 0.85, 1000, 0.89, 0.01)
    ok(g is None and h["lots"] == 1.18 and abs(h["q"] - 0.05011) < 1e-5, f"FTMO 100k P1 frisch: Satz 0,0446, 20 Lot → 1,18 Lot Fusion ({h})")
    ok(h["slave_risk"] == round(h["q"] * 1000, 2), "slave_risk = q × master_risk")
    gm = ns["gp_multiplikator"](1000, 20, h["q"] * 1000, 1.0, 0.85)
    ok(abs(gm - h["multiplier"]) < 1e-4, f"gleicher Multiplikator wie gp_multiplikator / Popup ({gm:.5f} ≈ {h['multiplier']})")
    h2, _ = ns["eh_hedge"](0.0464, 2.5, 20.0, 0.85, 1500, 0.89, 0.01)
    ok(h2["lots"] == round(0.0464 / 0.89 * 20 / 0.85 * 2.5, 2), f"FundingPips NDX 20 $/Pkt, 2,5 Lot → {h2['lots']} Lot")
    ok(ns["eh_hedge"](0.0446, 0.18, 1.0, 0.85, 100)[0]["lots"] == 0.01, "Klein-Trade 0,18 Lot → 0,0106 gerundet 0,01 Lot (wie gp_hedge)")
    ok(ns["eh_hedge"](0.0446, 0.05, 1.0, 0.85, 100)[0] is None, "0,05 Lot → 0,003 Lot unter 0,01, ohne Hedge")
    ok("unter 0,01 Lot" in ns["eh_hedge"](0.0446, 0.05, 1.0, 0.85, 100)[1], "Grund nennt die Grenze")
    ok(ns["eh_hedge"](None, 20, 1, 0.85, 1)[0] is None and ns["eh_hedge"](0.04, 20, None, 0.85, 1)[0] is None
       and ns["eh_hedge"](0.04, 0, 1, 0.85, 1)[0] is None, "ohne Satz / Punktwert / Lots → Grund")
    ok(ns["eh_hedge"](0.0446, 20, 1.0, 0.85, None)[0]["slave_risk"] is None, "ohne master_risk: Multiplikator trotzdem, slave_risk leer")

    print("eh_marge")
    les = {"frei": 15900.0, "je_lot": 265.0, "offen": {"buy": 8.61, "sell": 2.1}, "w": "EUR"}
    ok(ns["eh_marge"](les, 1.18, "buy", 0.0, 60)[0] is True, "Lesung 29.10.: 10,7 offen + 1,18 → passt")
    r = ns["eh_marge"](les, 1.18, "buy", 49.0, 60)
    ok(r[0] is False and "60 Lot" in r[1], f"10,71 + 49 vorgemerkt + 1,18 > 60 → ohne Hedge ({r[1]})")
    r = ns["eh_marge"](dict(les, frei=300.0), 2.0, "buy", 0.0, 60)
    ok(r[0] is True, "Master buy → Hedge sell: Ausgleich gegen den Long-Überhang, kein Zuwachs → braucht keine Marge")
    r = ns["eh_marge"](dict(les, frei=300.0), 2.0, "sell", 0.0, 60)
    ok(r[0] is False and "Marge knapp" in r[1] and "EUR, nötig" in r[1], f"Master sell → Hedge buy auf den größeren Schenkel: 2 × 265 > 300 × 0,8 ({r[1]})")
    ok(ns["eh_marge"](dict(les, offen=None), 1, "buy", 0, 60)[0] is False, "ohne offen-Lesung → ohne Hedge")


class DB:
    def __init__(self, plaene, regeln):
        self.plaene, self.regeln, self.updates, self.alarme = plaene, regeln, [], []

    def sb_select(self, t, q):
        return [{"regeln": self.regeln}] if t == "auto_plan_regeln" else []

    def _sb_all(self, t, q):
        if t == "trade_plans":
            out = []
            for p in self.plaene:
                if q.get("route") and p["route"] != q["route"][3:]:
                    continue
                st = q.get("status") or ""
                if st.startswith("eq.") and p["status"] != st[3:] or st.startswith("in.(") and p["status"] not in st[4:-1].split(","):
                    continue
                if q.get("auto_bestaetigt_at") == "not.is.null" and not p.get("auto_bestaetigt_at"):
                    continue
                if "or" in q:          # vorgemerkt: (planned, nicht geclaimt, Start ≥ von) | eben geclaimt | eben offen
                    von, frisch = re.search(r"start_um\.gte\.([^)]+)\)", q["or"]).group(1), re.search(r"start_um_gestartet_at\.gte\.([^,]+),", q["or"]).group(1)
                    if not ((p["status"] == "planned" and not p.get("start_um_gestartet_at") and p["start_um"] >= von)
                            or (p.get("start_um_gestartet_at") or "") >= frisch or (p.get("started_at") or "") >= frisch):
                        continue
                eh = (p.get("mt5_baseline") or {}).get("echo_hedge") or {}
                if "mt5_baseline->echo_hedge->>status" in q and eh.get("status") != q["mt5_baseline->echo_hedge->>status"][3:]:
                    continue
                if q.get("start_um_gestartet_at") == "is.null" and p.get("start_um_gestartet_at"):
                    continue
                if q.get("hand_werte_at") == "is.null" and p.get("hand_werte_at"):
                    continue
                if "and" in q:
                    von, bis = re.findall(r"start_um\.(?:gte|lte)\.([^,)]+)", q["and"])
                    if not (von <= p["start_um"] <= bis):
                        continue
                out.append(dict(p, echo_hedge=eh) if q.get("select", "").startswith("mt5_baseline->") else dict(p))
            return out
        if t == "accounts":
            return [{"id": "A1", "user_id": "U1", "name": "100k 511 → Phase 1", "firm": "FTMO", "account_type": "phase1", "external_id": "511"},
                    {"id": "A2", "user_id": "U1", "name": "Tradeify 150k", "firm": "Tradeify", "account_type": "challenge", "external_id": "T1"},
                    {"id": "A3", "user_id": "UE", "name": "Emin FTMO", "firm": "FTMO", "account_type": "phase1", "external_id": "E1"},
                    {"id": "A4", "user_id": "U2", "name": "FTMO ohne Hedge", "firm": "FTMO", "account_type": "phase1", "external_id": "512"},
                    {"id": "H1", "name": "Fusion Echo", "firm": "Fusion Markets", "external_id": "488579"}]
        if t == "user_settings":
            return [{"user_id": "U1", "value": {"accountId": "H1", "hedgeLogin": "488579"}}]
        return []

    def sb_update(self, t, guard, upd):
        p = next(x for x in self.plaene if "eq." + x["id"] == guard["id"])
        if p["status"] != "planned" or p.get("start_um_gestartet_at") or "eq." + p["route"] != guard["route"] \
                or ("updated_at" in guard and "eq." + p["updated_at"] != guard["updated_at"]):
            return []
        self.updates.append((p["id"], dict(upd)))
        p.update(upd)
        p["updated_at"] = p["updated_at"] + "x"
        return [p]


def takt():
    jetzt = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    iso = lambda m: (jetzt + timedelta(minutes=m)).isoformat()   # noqa: E731
    plan = lambda pid, acc, uid, m, **x: dict({"id": pid, "user_id": uid, "master_account_id": acc, "master_name": pid, "master_firm": "FTMO",   # noqa: E731
                                                "master_contracts": 20, "master_risk": 1000, "richtung": "buy", "start_um": iso(m),
                                                "notes": "Phase 1 · 0,18 Lots", "mt5_baseline": None, "status": "planned", "route": "mt5v2",
                                                "auto_plan": True, "auto_bestaetigt_at": "b", "updated_at": "t0"}, **x)
    plaene = [plan("P1", "A1", "U1", 10), plan("P2", "A1", "U1", 1), plan("P3", "A1", "U1", 40), plan("P4", "A2", "U1", 10),
              plan("P5", "A3", "UE", 10), plan("P6", "A4", "U2", 12), plan("P7", "A1", "U1", 11, start_um_gestartet_at="x"),
              plan("P8", "A1", "U1", 12, hand_werte_at="x"), plan("P9", "A1", "U1", 13, mt5_baseline={"tage_mini": {"tag": "x"}}),
              plan("P12", "A1", "U1", -45), plan("P13", "A1", "U1", 14, auto_bestaetigt_at=None),
              plan("P14", "A1", "U1", -120, route="mt5", mt5_baseline={"echo_hedge": {"status": "mit", "lots": 50, "login": "488579"}})]
    regeln = {"echo_hedge": {"an": True}, "firmen": [{"namen": ["ftmo"], "route": "mt5v2"}, {"namen": ["tradeify"], "route": "tvv2"}]}
    db = DB(plaene, regeln)
    les = {"488579": {"frei": 15900.0, "je_lot": 265.0, "offen": {"buy": 8.61, "sell": 2.1}, "w": "EUR", "at": jetzt.timestamp() - 30}}
    ns = lade({
        "sb_select": db.sb_select, "_sb_all": db._sb_all, "sb_update": db.sb_update,
        "alarm_senden": lambda *a, **k: db.alarme.append((a, k)), "_wt_now_iso": lambda: "2026-10-29T12:00:00+00:00",
        "_ap_namen": lambda: ({"U1": "Mike", "U2": "Ina", "UE": "Emin"}, set()), "gp_verwalter_karte": lambda: {"UE": "UE"},
        "AP_KONTO_FELDER": "id", "GP_HEDGE_KEY": "echo_hedge_account", "GP_SLAVE_PPL": 0.85,
        "ap_ppl_karte": lambda rows, norm=None: ({}, {}), "_ap_norm": lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower()),
        "_firm_norm": lambda s: s, "_ap_balance_karten": lambda: ({}, {}), "_ap_kauf_echt": lambda ids: {},
        "gp_fusion_lesungen": lambda uids, j: les,
        "ap_regel_finden": lambda firmen, f: next((r for r in firmen if re.sub(r"[^a-z0-9]", "", f.lower()) in r["namen"]), None),
        "acc_balance_wahl": lambda a, e, d: (100000.0, "USD", "Echo", ""),
        "ap_kontowert_konto": lambda a, bal, firmen, kauf=None: {"satz_eur_pro_usd": 0.0446, "wert_eur": 446.0},
        "ap_cfd_ppl": lambda ctx, a: 1.0})
    print("eh_tick an")
    erg = ns["eh_tick"](jetzt=jetzt, force=True)
    um = {pid: u for pid, u in db.updates}
    p1 = next(p for p in plaene if p["id"] == "P1")
    ok("P1" in um and p1["route"] == "mt5" and p1["slave_account_id"] == "H1" and p1["multiplier"] == 0.059 and p1["slave_risk"] == 50.11,
       f"P1 (Start +10 min) → Echo mit Hedge, Slave Fusion, ×{p1.get('multiplier')}")
    ok(p1["mt5_baseline"]["echo_hedge"]["lots"] == 1.18 and p1["mt5_baseline"]["echo_hedge"]["login"] == "488579", "Spur am Plan: 1,18 Lot, Login")
    ok("0,18 Lots" in p1["notes"] and "Echo mit Hedge: 1,18 Lot" in p1["notes"], "Notiz ergänzt, alte Notiz unverändert (0,18 Lots bleibt mit Komma)")
    ok("P2" in um, "Start in 1 min (vorgezogen) → auch umgestellt")
    ok("P3" not in um and "P12" not in um, "Start in 40 min bzw. vor 45 min → nicht angefasst (Fenster −30 … +20 min)")
    ok("P13" not in um, "unbestätigter Vorschlag → nicht angefasst")
    ok("P4" not in um, "Futures (Tradeify, tvv2-Regel) → nicht angefasst")
    ok("P5" not in um, "Verwalter-Gruppe (Emin) → nicht angefasst")
    ok("P7" not in um and "P8" not in um, "geclaimt bzw. Hand-Werte → nicht angefasst")
    p6 = next(p for p in plaene if p["id"] == "P6")
    ok(p6["route"] == "mt5v2" and p6["mt5_baseline"]["echo_hedge"]["status"] == "ohne" and "kein Echo-Hedge-Konto" in p6["notes"],
       "ID ohne Fusion-Konto → bleibt Echo V2, Grund an Plan und Notiz")
    p9 = next(p for p in plaene if p["id"] == "P9")
    ok(p9["route"] == "mt5v2" and p9["mt5_baseline"]["echo_hedge"]["grund"].startswith("Tage sammeln") and p9["mt5_baseline"]["tage_mini"],
       "Tage-Mini bleibt Echo V2, tage_mini bleibt erhalten")
    ok(not db.alarme, "P6 startet erst in 12 min → noch keine ⚪-Meldung (es kann noch klappen)")
    ok(erg.get("umgestellt") == 2, f"Ergebnis {erg} (P1, P2; P14 von vor 2 h zählt nicht als vorgemerkt)")
    n = len(db.updates)
    ns["eh_tick"](jetzt=jetzt, force=True)
    ok(len(db.updates) == n, "zweiter Takt: gleicher Grund-Code → kein neues Update")
    ns["eh_tick"](jetzt=jetzt + timedelta(minutes=10), force=True)
    ok(len(db.alarme) == 1 and db.alarme[0][0][0] == 3 and db.alarme[0][1]["plan_id"] == "P6", "P6 in 2 min → eine ⚪-Meldung, Tage-Mini still")
    ns["eh_tick"](jetzt=jetzt + timedelta(minutes=11), force=True)
    ok(len(db.alarme) == 1, "keine zweite Meldung")

    print("60-Lot-Grenze mit vorgemerkten")
    les["488579"]["offen"] = {"buy": 50.0, "sell": 7.9}
    plaene.append(plan("P10", "A1", "U1", 15))
    ns["eh_tick"](jetzt=jetzt, force=True)
    p10 = next(p for p in plaene if p["id"] == "P10")
    ok(p10["route"] == "mt5v2" and "60 Lot" in p10["mt5_baseline"]["echo_hedge"]["grund"] and p10["mt5_baseline"]["echo_hedge"]["code"] == "grenze",
       f"57,9 offen + 2,36 vorgemerkt (P1, P2) + 1,18 > 60 → ohne Hedge ({p10['mt5_baseline']['echo_hedge']['grund']})")
    print("Fusion-Lesung alt")
    les["488579"].update(offen={"buy": 1.0, "sell": 1.0}, at=jetzt.timestamp() - 600)
    plaene.append(plan("P11", "A1", "U1", 16))
    ns["eh_tick"](jetzt=jetzt, force=True)
    ok(next(p for p in plaene if p["id"] == "P11")["mt5_baseline"]["echo_hedge"]["grund"].startswith("keine frische Fusion-Lesung"),
       "Lesung 10 min alt → ohne Hedge")

    print("Schalter aus → zurück")
    regeln["echo_hedge"]["an"] = False
    erg = ns["eh_tick"](jetzt=jetzt, force=True)
    ok(p1["route"] == "mt5v2" and p1["slave_account_id"] is None and p1["multiplier"] is None and p1["mt5_baseline"]["echo_hedge"]["status"] == "zurueck",
       f"P1 zurück auf Echo V2 ohne Slave ({erg})")
    les["488579"]["at"] = jetzt.timestamp() - 30
    regeln["echo_hedge"]["an"] = True
    ns["eh_tick"](jetzt=jetzt, force=True)
    ok(p1["route"] == "mt5", "wieder an → P1 erneut umgestellt (Status zurueck zählt nicht als ohne)")
    p1["start_um_gestartet_at"] = "claim"
    regeln["echo_hedge"]["an"] = False
    ns["eh_tick"](jetzt=jetzt, force=True)
    ok(p1["route"] == "mt5", "geclaimter Plan bleibt beim Ausschalten Echo mit Hedge")


def main():
    rein()
    takt()
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
