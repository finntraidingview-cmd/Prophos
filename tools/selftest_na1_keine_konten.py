#!/usr/bin/env python3
"""Selbsttest NA1 (10.11.2026, Master; Fehler-Muster FA1-2a): Tradovate-Login ohne Konten („No active accounts found for this environment" / „No trading accounts
available"). Prüft (1) Puls (mt5-copier/order_bot.py): Text sicher erkannt, kein zweiter/dritter Connect, kein frischer Tab, andere Abbrüche unverändert;
(2) Railway (app.py kk_urteil / kk_satz / kk_tick): Konto erst nach zwei Startversuchen ≥ 10 min deaktiviert, nie nach einem Start, nie Emins Gruppe, nach
Reaktivieren nur neue Treffer, Pläne markiert, 🟠 einmal je Konto, Lesefehler = nichts. Ohne Netz, DB nachgebaut.
Aufruf: python3 tools/selftest_na1_keine_konten.py"""
import inspect
import os
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


ALT = ("Nichts platziert · Tradovate-Login 'TDFYU000' nicht geschafft (abgebrochen): TradingView bricht den Login dreimal ab ('nd accept all risks.Error! "
       "Failed to login: No active accounts found for this environment.') — Tradovate ist NICHT verbunden. (auch nach frisch geöffnetem TradingView-Tab)")

print("1) Puls (order_bot)")
check(ob.tv_login_keine_konten(ALT) == "Failed to login: No active accounts found for this environment"
      and ob.tv_login_keine_konten("Error! Failed to login: No trading accounts available") == "Failed to login: No trading accounts available",
      "beide Texte erkannt (Tradeify Live-Rahmen, Apex ohne Konten)")
check(not ob.tv_login_keine_konten("Error! The login operation has been canceled") and not ob.tv_login_keine_konten("An error has occurred while logging in")
      and not ob.tv_login_keine_konten(""), "andere Login-Abbrüche bleiben beim alten Weg (Connect bis 3×)")
src = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
i = src.index('        if ort == "abgebrochen":\n            code = "abgebrochen"\n            kk = tv_login_keine_konten(text)')
j = src.index("        if versuch < 3:", i)
check("return \"abgebrochen\", (f\"Tradovate meldet für diesen Login keine Konten ('{kk}')" in src[i:j],
      "Login-Schleife: bei „keine Konten“ sofort zurück, vor dem zweiten/dritten Connect; Code bleibt 'abgebrochen' (Aufrufer bitgleich)")
fr = inspect.getsource(ob._cdp_konto_mit_login_frisch)
check(fr.index("tv_login_keine_konten(erg[2])") < fr.index("cdp_tab_frisch_noetig("), "kein frischer TradingView-Tab bei „keine Konten“")

print("2) Railway: Urteil")
U = app.kk_urteil
T0 = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
check(U([T0, T0 + timedelta(minutes=50)])[0] is True, "zwei Versuche 50 min auseinander → bestätigt")
check(U([T0, T0 + timedelta(seconds=1)])[0] is False and U([T0])[0] is False, "ein Versuch (zwei Zeilen in 1 s) bzw. ein Treffer → nicht")
check(U([T0, T0 + timedelta(hours=1)], start_nach=T0 + timedelta(minutes=5))[0] is False, "Konto lief seit dem ersten Treffer → nicht (vorübergehend)")
check(U([T0, T0 + timedelta(hours=1)], seit=T0 + timedelta(minutes=30))[0] is False
      and U([T0, T0 + timedelta(hours=1), T0 + timedelta(hours=2)], seit=T0 + timedelta(minutes=30))[0] is True,
      "nach eigener Sperre (Finn hat reaktiviert) zählen nur neuere Treffer")
check(U([T0, T0 + timedelta(minutes=50)], jetzt=T0 + timedelta(minutes=80))[0] is True
      and U([T0, T0 + timedelta(minutes=50)], jetzt=T0 + timedelta(hours=3))[0] is False,
      "Prüfer S2 (MUSS d): letzter Treffer muss frisch sein (≤ 60 min) — alte Treffer allein sperren nie wieder")
check(app.kk_satz(ALT) == "Failed to login: No active accounts found for this environment" and app.kk_satz("x") == "", "Satz für die Meldung")

print("3) Railway: Takt gegen eine nachgebaute DB")
JETZT = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
J, E = "11111111-1111-1111-1111-111111111111", "33333333-3333-3333-3333-333333333333"
K1, K2, K3, KE, KS = ("a0000000-0000-0000-0000-000000000001", "a0000000-0000-0000-0000-000000000002", "a0000000-0000-0000-0000-000000000003",
                      "a0000000-0000-0000-0000-00000000000e", "a0000000-0000-0000-0000-00000000000s")
KONTEN = [{"id": K1, "user_id": J, "name": "150k T1 → Winning Days", "firm": "Tradeify", "deaktiviert_at": None},
          {"id": K2, "user_id": J, "name": "150k T2 → Winning Days", "firm": "Tradeify", "deaktiviert_at": None},
          {"id": K3, "user_id": J, "name": "150k T3 → Winning Days", "firm": "Tradeify", "deaktiviert_at": "2026-11-08T00:00:00+00:00"},
          {"id": KE, "user_id": E, "name": "100k E → Funded", "firm": "Apex", "deaktiviert_at": None},
          {"id": KS, "user_id": J, "name": "100k S → Challenge", "firm": "Apex", "deaktiviert_at": None}]


def fz(konto, uid, at, plan=None):
    return {"at": at.isoformat(), "user_id": uid, "plan_id": plan, "konto": konto, "firma": "Tradeify", "msg": ALT}


DB = {"fehl": [], "upd": [], "rpc": [], "alarm": [], "log": [], "log_fehler": False, "plaene": [], "starts": [], "upd_antwort": None}


def sb_select(t, p):
    if t == "puls_fehlstarts":
        return [dict(r) for r in DB["fehl"] if (("No active" in p["msg"]) == ("No active" in r["msg"]))]
    if t == "trade_plans" and "start_um_gestartet_at" in p:
        return [{"id": "plan-offen-1"}] if p["master_account_id"] == f"eq.{K1}" else []
    if t == "trade_plans":
        return [dict(x) for x in DB["plaene"]]
    if t == "alarm_log":
        if DB["log_fehler"]:
            raise RuntimeError("weg")
        return list(DB["log"])
    return []


def sb_all(t, p):
    if t == "accounts":
        return [dict(a) for a in KONTEN]
    if t == "trade_plans":
        return list(DB["starts"])
    return []


app.sb_select, app._sb_all = sb_select, sb_all
app.sb_update = lambda t, f, u: DB["upd"].append((t, f, u)) or (DB["upd_antwort"] if DB["upd_antwort"] is not None else [dict(u)])
app._sb_anfrage = lambda *a, **k: DB["rpc"].append(k.get("json"))
app.alarm_senden = lambda *a, **k: DB["alarm"].append((a, k)) or (1, 1)
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}, {"id": "emin", "name": "Emin", "verwalter_id": E}],
                                   "mitglieder": [{"user_id": J, "gruppe_id": "ht"}, {"user_id": E, "gruppe_id": "emin"}]}
app._ap_namen = lambda: ({J: "HT-1", E: "Gruppe-E"}, set())
t1, t2 = JETZT - timedelta(hours=27), JETZT - timedelta(minutes=20)     # letzter Fehlstart frisch (KK_FRISCH_S)
DB["fehl"] = [fz("150k T1 → Winning Days", J, t1), fz("150k T1 → Winning Days", J, t2),                                    # bestätigt, Plan gelöscht → über den Namen
              fz("150k T2 → Winning Days", J, t1), fz("150k T2 → Winning Days", J, t1 + timedelta(seconds=1)),            # nur ein Versuch
              fz("150k T3 → Winning Days", J, t1), fz("150k T3 → Winning Days", J, t2),                                    # schon deaktiviert
              fz("100k E → Funded", E, t1), fz("100k E → Funded", E, t2),                                                  # Emins Gruppe
              fz("100k S → Challenge", J, t1), fz("100k S → Challenge", J, t2)]                                            # danach gestartet
DB["starts"] = [{"master_account_id": KS, "started_at": (t1 + timedelta(minutes=20)).isoformat()}]
e = app.kk_tick(JETZT)
upd_konten = [f["id"] for _t, f, u in DB["upd"] if "deaktiviert_at" in u]
check(upd_konten == [f"eq.{K1}"] and DB["upd"][0][1] == {"id": f"eq.{K1}", "deaktiviert_at": "is.null"} and DB["upd"][0][2]["deaktiviert_at"] == JETZT.isoformat(),
      f"nur T1 deaktiviert (Guard deaktiviert_at is null); T2 ein Versuch, T3 schon aus, Emin nie, Challenge lief danach ({upd_konten})")
check(len(DB["rpc"]) == 1 and DB["rpc"][0]["p_plan"] == "plan-offen-1" and DB["rpc"][0]["p_key"] == "keine_konten" and DB["rpc"][0]["p_status"] == "planned"
      and "Konto deaktiviert" in DB["rpc"][0]["p_patch"]["text"], "geplanter, ungeclaimter Plan bekommt mt5_baseline.keine_konten mit klarem Grund")
a_, k_ = DB["alarm"][0] if DB["alarm"] else ((None,) * 5, {})
check(len(DB["alarm"]) == 1 and a_[0] == 2 and a_[1] == "keine_konten" and k_.get("schluessel") == f"keine_konten|{K1}"
      and "HT-1: 150k T1" in a_[3] and "No active accounts found" in a_[3] and "am Stift aktivieren" in a_[3] and app.alarm_prio_aus_titel(a_[2]) == 2,
      "🟠 einmal je Konto an die Master-IDs mit Satz, Zahl und nächstem Schritt")
check(e["gesperrt"] and e["gesperrt"][0]["konto_id"] == K1 and e["geprueft"] == 4, "Ergebnis nennt das gesperrte Konto")
DB.update(upd=[], rpc=[], alarm=[], upd_antwort=[])
app.kk_tick(JETZT)
DB["upd_antwort"] = None
check(not DB["alarm"] and not DB["rpc"], "zweiter Lauf / anderer Container (Guard griff) → keine zweite Meldung")
DB.update(upd=[], rpc=[], alarm=[])
DB["log"] = [{"schluessel": f"keine_konten|{K1}", "at": (t2 + timedelta(minutes=5)).isoformat()}]
app.kk_tick(JETZT)
check(not DB["upd"], "Finn hat reaktiviert: alte Treffer vor der eigenen Sperre zählen nicht")
# Prüfer S2 (MUSS d): Finn hat reaktiviert, die eigene Sperre fehlt im alarm_log (stummer Schreibfehler) → alte Treffer allein sperren nicht wieder
DB.update(upd=[], rpc=[], alarm=[], log=[])
_fehl_alt = list(DB["fehl"])
DB["fehl"] = [dict(r, at=(JETZT - timedelta(hours=5)).isoformat()) if r["at"] == t2.isoformat() else r for r in DB["fehl"]]
app.kk_tick(JETZT)
check(not DB["upd"] and not DB["alarm"], "reaktiviert ohne alarm_log-Eintrag: letzte Treffer 5 h alt → bleibt aktiv, keine 🟠")
DB["fehl"] = _fehl_alt
DB["log"], DB["log_fehler"] = [], True
e = app.kk_tick(JETZT)
DB["log_fehler"] = False
check(not DB["upd"] and "alarm_log" in e.get("fehler", ""), "alarm_log nicht lesbar → nichts sperren (fail-closed)")
_gd = app.admin_gruppen_daten
app.admin_gruppen_daten = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
e = app.kk_tick(JETZT)
app.admin_gruppen_daten = _gd
check(not DB["upd"] and "Gruppen" in e.get("fehler", ""), "Gruppen nicht lesbar → nichts sperren")
DB["fehl"] = []
check(app.kk_tick(JETZT) == {"gesperrt": [], "geprueft": 0} and not DB["upd"], "kein Treffer → nichts")

print("4) Einbau")
asrc = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("_kk_takt()                            # NA1" in asrc and "random.uniform(*KK_TAKT_S)" in asrc, "Takt in ap_loop, gestreut 4–6 min")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
