#!/usr/bin/env python3
"""Selbsttest E1 (10.11.2026, Master nach FS1): NA1-Takt (app.py kk_tick) kennt drei weitere feste Konto-Zustände — MT5 „Authorization failed“, Server
„Only position closing is allowed“, Tradovate „Nach dem Login zeigt TradingView kein Konto“. Prüft: Muster eng (nur die Schlüssel-Texte), Schwellen je Regel
(„kein Konto“ 3 Treffer über ≥ 60 min — der echte vorübergehende Fall vom 02.11. sperrt nicht), ⚪ mit Beleg, „Authorization failed“ auf der Liste „Nur du“
(Konten-Pflege), NA1 bitgleich 🟠, eine Sperre je Konto und Lauf, nach Reaktivieren aus jeder Regel nur neue Treffer, fremde Gruppe nie;
Prüfer-MUSS: derselbe Text an mehreren Konten einer Firma / eines PCs binnen 2 h → nichts sperren, ⚪ „breit“; Deckel je Lauf. Ohne Netz, DB nachgebaut.
Aufruf: python3 tools/selftest_e1_konto_zustaende.py"""
import os
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


AUTH = ("Geclaimt vor 5 min, danach still — letzte Order-Antwort: Terminal-Verbindung fehlgeschlagen: (-6, 'Terminal: Authorization failed') — Terminal "
        "läuft und reagiert unter Windows (Fenster '1000 - Firma: Demokonto - Netting -', PID 1), antwortet aber nicht über die Schnittstelle")
NURZU = ("Geclaimt vor 5 min, Plan nicht offen — letzte Order-Antwort: KEINE Bestaetigung binnen 12 s — Grund: Server antwortete „Only position closing is "
         "allowed“ — Kontostand 90 553.06 (Journal) → Antwort im Journal prüfen.")
KEINK = ("Nichts platziert · Tradovate-Login 'LOGIN1' nicht geschafft (verbunden): Nach dem Login zeigt TradingView kein Konto (40 s) — Puls-Chrome ansehen.")
NA1 = ("Nichts platziert · Tradovate-Login 'TDFYU000' nicht geschafft (abgebrochen): TradingView bricht den Login dreimal ab ('Error! Failed to login: "
       "No active accounts found for this environment.')")

print("1) Regeln")
R = {r["art"]: r for r in app.KK_ARTEN}
check(app.KK_ART_NAMEN[0] == "keine_konten" and set(R) == {"keine_konten", "auth_failed", "nur_schliessen", "login_ohne_konto"},
      "vier Regeln, NA1 zuerst")
check(R["keine_konten"]["re"] is app.KK_RE and R["keine_konten"]["prio"] == 2 and R["keine_konten"]["min_n"] == 2, "NA1 unverändert (🟠, 2 Treffer)")
check(R["auth_failed"]["re"].search(AUTH) and not R["auth_failed"]["re"].search("Authorization failed") and not R["auth_failed"]["re"].search(NURZU),
      "Auth nur als Terminal-Verbindungsfehler (kein loses „Authorization failed“)")
check(R["nur_schliessen"]["re"].search(NURZU) and not R["nur_schliessen"]["re"].search(AUTH), "Only position closing erkannt")
check(R["login_ohne_konto"]["re"].search(KEINK) and not R["login_ohne_konto"]["re"].search(NA1), "„kein Konto nach Login“ erkannt, NA1-Text nicht")
check(all(R[a]["prio"] == 3 for a in ("auth_failed", "nur_schliessen", "login_ohne_konto")), "neue Regeln melden ⚪")
check(R["auth_failed"].get("liste") == "nur_du" and R["auth_failed"].get("fuer") == "konten"
      and not R["nur_schliessen"].get("liste") and not R["login_ohne_konto"].get("liste"), "nur „Authorization failed“ auf die Liste „Nur du“ (Konten-Pflege)")
check(R["auth_failed"]["ohne"].search("Terminal wird gerade geheilt (terminal_heilt)") and R["auth_failed"]["breit"] == ("firma", "pc")
      and R["nur_schliessen"]["breit"] == ("firma",) and R["login_ohne_konto"]["breit"] == ("firma", "pc") and not R["keine_konten"].get("breit"),
      "Breiten-Wache für die neuen Regeln, NA1 ohne; Auth-Treffer während der Selbstheilung zählen nicht")

print("2) Schwellen (Simulation 30 Tage)")
U = app.kk_urteil
T0 = datetime(2026, 11, 2, 0, 9, tzinfo=timezone.utc)
lk = R["login_ohne_konto"]
fall_02 = [T0, T0 + timedelta(minutes=20), T0 + timedelta(minutes=40)]          # 3× in 40 min, lief 20 min später
check(U(fall_02, jetzt=T0 + timedelta(minutes=45), min_n=lk["min_n"], min_abstand_s=lk["min_abstand_s"])[0] is False,
      "„kein Konto“ 3× in 40 min (vorübergehend, 02.11.) → nicht gesperrt")
fall_10 = [T0, T0 + timedelta(minutes=21), T0 + timedelta(minutes=43), T0 + timedelta(minutes=113)]
check(U(fall_10[:3], jetzt=T0 + timedelta(minutes=50), min_n=3, min_abstand_s=3600)[0] is False
      and U(fall_10, jetzt=T0 + timedelta(minutes=115), min_n=3, min_abstand_s=3600)[0] is True, "„kein Konto“ 4× über 113 min (echter Fall) → gesperrt")
check(U([T0, T0 + timedelta(hours=1, minutes=5)], jetzt=T0 + timedelta(hours=1, minutes=6), min_n=3, min_abstand_s=3600)[0] is False,
      "„kein Konto“ nur 2 Treffer → nicht, auch über 60 min")
check(U([T0, T0 + timedelta(minutes=24)], jetzt=T0 + timedelta(minutes=30))[0] is True and U([T0, T0 + timedelta(minutes=5)])[0] is False,
      "Auth/Only-closing: 2 Treffer ≥ 10 min (wie NA1)")

print("3) Takt gegen eine nachgebaute DB")
JETZT = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
J, E = "11111111-1111-1111-1111-111111111111", "33333333-3333-3333-3333-333333333333"
KA, KN, KK, KD, KE, KX = ("b0000000-0000-0000-0000-00000000000a", "b0000000-0000-0000-0000-00000000000b", "b0000000-0000-0000-0000-00000000000c",
                          "b0000000-0000-0000-0000-00000000000d", "b0000000-0000-0000-0000-00000000000e", "b0000000-0000-0000-0000-00000000000f")
KONTEN = [{"id": KA, "user_id": J, "name": "100k A → Phase 2", "firm": "FirmaA", "deaktiviert_at": None},
          {"id": KN, "user_id": J, "name": "100k N → Funded", "firm": "FirmaN", "deaktiviert_at": None},
          {"id": KK, "user_id": J, "name": "50k K → Challenge", "firm": "FirmaK", "deaktiviert_at": None},
          {"id": KD, "user_id": J, "name": "150k D → Winning Days", "firm": "FirmaD", "deaktiviert_at": None},
          {"id": KE, "user_id": E, "name": "100k E → Phase 1", "firm": "FirmaE", "deaktiviert_at": None},
          {"id": KX, "user_id": J, "name": "100k X → Phase 1", "firm": "FirmaX", "deaktiviert_at": None}]
DB = {"fehl": [], "upd": [], "rpc": [], "alarm": [], "log": [], "abfragen": []}


def fz(konto, uid, at, msg):
    return {"at": at.isoformat(), "user_id": uid, "plan_id": None, "konto": konto, "firma": "", "msg": msg, "pc": "pc-" + konto.split()[1].lower() * 4}


def sb_select(t, p):
    DB["abfragen"].append((t, dict(p)))
    if t == "puls_fehlstarts":
        stueck = p["msg"].replace("ilike.", "").strip("*").lower()
        return [dict(r) for r in DB["fehl"] if stueck in r["msg"].lower()]
    if t == "trade_plans" and "start_um_gestartet_at" in p:
        return [{"id": "plan-" + p["master_account_id"][-1]}]
    if t == "alarm_log":
        return list(DB["log"])
    return []


app.sb_select = sb_select
app._sb_all = lambda t, p: [dict(a) for a in KONTEN] if t == "accounts" else []
app.sb_update = lambda t, f, u: DB["upd"].append((t, f, u)) or [dict(u)]
app._sb_anfrage = lambda *a, **k: DB["rpc"].append(k.get("json"))
app.alarm_senden = lambda *a, **k: DB["alarm"].append((a, k)) or (1, 1)
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}, {"id": "fremd", "name": "Gruppe-E", "verwalter_id": E}],
                                   "mitglieder": [{"user_id": J, "gruppe_id": "ht"}, {"user_id": E, "gruppe_id": "fremd"}]}
app._ap_namen = lambda: ({J: "HT-1", E: "Gruppe-E"}, set())
m = lambda x: JETZT - timedelta(minutes=x)   # noqa: E731
DB["fehl"] = [fz("100k A → Phase 2", J, m(50), AUTH), fz("100k A → Phase 2", J, m(25), AUTH),                       # Auth bestätigt
              fz("100k N → Funded", J, m(26 * 60), NURZU), fz("100k N → Funded", J, m(10), NURZU),                   # Only closing, Folgetag
              fz("50k K → Challenge", J, m(40), KEINK), fz("50k K → Challenge", J, m(20), KEINK), fz("50k K → Challenge", J, m(5), KEINK),   # 35 min → nicht
              fz("150k D → Winning Days", J, m(30), NA1), fz("150k D → Winning Days", J, m(15), NA1),                # NA1 …
              fz("150k D → Winning Days", J, m(28), AUTH), fz("150k D → Winning Days", J, m(12), AUTH),              # … und Auth: nur eine Sperre
              fz("100k E → Phase 1", E, m(50), AUTH), fz("100k E → Phase 1", E, m(20), AUTH),                        # fremde Gruppe
              fz("100k X → Phase 1", J, m(40), "Terminal-Verbindung fehlgeschlagen: (-1, 'Terminal: Call failed')"),
              fz("100k X → Phase 1", J, m(10), "Terminal-Verbindung fehlgeschlagen: (-1, 'Terminal: Call failed')")]  # anderer Terminal-Fehler
e = app.kk_tick(JETZT)
gesperrt = {g["konto_id"]: g["art"] for g in e["gesperrt"]}
check(gesperrt == {KA: "auth_failed", KN: "nur_schliessen", KD: "keine_konten"}, f"gesperrt: Auth, Only closing, NA1 — nicht „kein Konto“ (35 min), "
      f"nicht die fremde Gruppe, nicht der andere Terminal-Fehler ({gesperrt})")
check(sum(1 for _t, f, _u in DB["upd"] if f["id"] == f"eq.{KD}") == 1, "Konto mit NA1- und Auth-Treffern: genau eine Sperre (NA1 zuerst)")
check(all(f.get("deaktiviert_at") == "is.null" for _t, f, _u in DB["upd"]), "Guard deaktiviert_at is null wie NA1")
al = {k["schluessel"].split("|")[1]: (a, k) for a, k in DB["alarm"]}
a_, k_ = al[KA]
check(a_[0] == 3 and a_[1] == "auth_failed" and k_["schluessel"] == f"auth_failed|{KA}" and k_["daten"].get("liste") == "nur_du"
      and k_["daten"].get("fuer") == "konten" and "Authorization failed" in k_["daten"].get("beleg", "") and "Konten-Pflege" in a_[3] and "2× seit" in a_[3]
      and app.alarm_prio_aus_titel(a_[2]) == 3, "Auth: ⚪, Beleg, Liste „Nur du“ (Konten-Pflege), Zahl und nächster Schritt")
a_, k_ = al[KN]
check(a_[0] == 3 and a_[1] == "nur_schliessen" and "Only position closing" in k_["daten"]["beleg"] and not k_["daten"].get("liste"),
      "Only closing: ⚪ mit Beleg, nicht auf der Liste")
a_, k_ = al[KD]
check(a_[0] == 2 and a_[1] == "keine_konten" and a_[2] == "Konto weg? Tradovate-Login ohne Konten — deaktiviert" and "beleg" not in k_["daten"],
      "NA1-Meldung bitgleich (🟠, gleicher Titel, gleiche Daten)")
rpc = {x["p_plan"]: x for x in DB["rpc"]}
check(rpc["plan-" + KA[-1]]["p_key"] == "auth_failed" and "Authorization failed" in rpc["plan-" + KA[-1]]["p_patch"]["text"]
      and rpc["plan-" + KD[-1]]["p_key"] == "keine_konten", "geplante Pläne bekommen den Grund je Regel")
lq = [p for t, p in DB["abfragen"] if t == "alarm_log"]
check(lq and lq[0]["art"] == "in.(keine_konten,auth_failed,nur_schliessen,login_ohne_konto)", "alarm_log liest die eigenen Sperren aller Regeln")

print("4) Nach Reaktivieren")
DB.update(upd=[], rpc=[], alarm=[], abfragen=[])
DB["log"] = [{"schluessel": f"keine_konten|{KA}", "at": m(15).isoformat()}]
app.kk_tick(JETZT)
check(not any(f["id"] == f"eq.{KA}" for _t, f, _u in DB["upd"]), "eigene Sperre aus einer ANDEREN Regel nach den Treffern → alte Auth-Treffer zählen nicht")

print("5) Breiten-Wache und Deckel (Prüfer-MUSS)")
B = "c0000000-0000-0000-0000-0000000000"
KONTEN[:] = [{"id": B + f"{i:02d}", "user_id": J, "name": f"100k B{i} → Funded", "firm": "FirmaB" if i < 3 else f"Firma{i}", "deaktiviert_at": None}
             for i in range(1, 7)]
DB.update(upd=[], rpc=[], alarm=[], log=[], abfragen=[])
DB["fehl"] = [fz(f"100k B{i} → Funded", J, m(x), NURZU) for i in (1, 2) for x in (40, 20)]                       # zwei Konten derselben Firma
DB["fehl"] += [fz(f"100k B{i} → Funded", J, m(x), NURZU) for i in (3, 4, 5, 6) for x in (40, 20)]                # vier Einzelfälle, je eigene Firma
e = app.kk_tick(JETZT)
gesp = sorted(g["konto_id"][-2:] for g in e["gesperrt"])
check(not any(g["konto_id"][-2:] in ("01", "02") for g in e["gesperrt"]) and len(e.get("breit", [])) == 2,
      f"Only closing an zwei Konten derselben Firma binnen 2 h → keins gesperrt ({e.get('breit')})")
ba = [a for a, k in DB["alarm"] if a[1] == "nur_schliessen_breit"]
check(len(ba) == 1 and ba[0][0] == 3 and "nichts deaktiviert" in ba[0][2] and "FirmaB" in ba[0][3], "⚪ „breit“ einmal (je Regel × Firma × Tag)")
check(gesp == ["03", "04"] and [d["konto_id"][-2:] for d in e.get("deckel", [])] == ["05", "06"], f"Deckel: höchstens 2 neue Sperren je Regel und Lauf ({gesp})")
DB.update(upd=[], rpc=[], alarm=[], abfragen=[])
app.kk_tick(JETZT)
check(not [a for a, k in DB["alarm"] if a[1] == "nur_schliessen_breit"], "zweiter Lauf: keine zweite Breit-Meldung")
# Runde 2 (S1): nach der breiten Phase (B1+B2) liefert B2 nichts mehr, B1 trifft EINMAL neu → nicht gesperrt (alte Treffer zählen nicht); zweimal neu ≥ 10 min → gesperrt
KONTEN[:] = KONTEN[:2]
J2 = JETZT + timedelta(minutes=150)
DB.update(upd=[], rpc=[], alarm=[], abfragen=[])
DB["fehl"] = [r for r in DB["fehl"] if r["konto"].startswith(("100k B1", "100k B2"))] + [fz("100k B1 → Funded", J, J2 - timedelta(minutes=2), NURZU)]
e = app.kk_tick(J2)
check(not e["gesperrt"], "nach breiter Phase: ein einziger neuer Treffer sperrt nicht")
DB["fehl"].append(fz("100k B1 → Funded", J, J2 + timedelta(minutes=10), NURZU))
DB.update(upd=[], rpc=[], alarm=[], abfragen=[])
e = app.kk_tick(J2 + timedelta(minutes=12))
check([g["konto_id"][-2:] for g in e["gesperrt"]] == ["01"], "zwei eigene neue Treffer ≥ 10 min, kein anderes Konto im Fenster → gesperrt")
KONTEN[:] = [{"id": B + "11", "user_id": J, "name": "100k P1 → Phase 1", "firm": "FirmaP", "deaktiviert_at": None},
             {"id": B + "12", "user_id": J, "name": "100k P2 → Phase 1", "firm": "FirmaQ", "deaktiviert_at": None}]
DB.update(upd=[], rpc=[], alarm=[], abfragen=[])
DB["fehl"] = [dict(fz(f"100k P{i} → Phase 1", J, m(x), AUTH), pc="pc-gleich") for i in (1, 2) for x in (40, 20)]
e = app.kk_tick(JETZT)
check(not e["gesperrt"] and {b["feld"] for b in e.get("breit", [])} == {"pc"}, "Auth an zwei Konten verschiedener Firmen auf EINEM PC → keins gesperrt (PC-weit)")
DB["fehl"] = [dict(r, at=(JETZT - timedelta(hours=5)).isoformat()) if r["konto"].startswith("100k P2") else r for r in DB["fehl"]]
app._kk_breit_seit.clear()          # eigene Lage (ohne vorherige breite Phase von P1)
DB.update(upd=[], rpc=[], alarm=[], abfragen=[])
e = app.kk_tick(JETZT)
check([g["konto_id"][-2:] for g in e["gesperrt"]] == ["11"], "anderes Konto nur vor 5 h (außerhalb ±2 h) → kein Breit, P1 gesperrt")
DB.update(upd=[], rpc=[], alarm=[], abfragen=[])
DB["fehl"] = [dict(fz("100k P1 → Phase 1", J, m(x), AUTH + " · Selbstheilung lief"), pc="pc-a") for x in (40, 20)]
e = app.kk_tick(JETZT)
check(not e["gesperrt"], "Auth-Treffer während der Selbstheilung zählen nicht")
_s = app.sb_select
app.sb_select = lambda t, p: (_ for _ in ()).throw(RuntimeError("weg")) if t == "puls_fehlstarts" and "Only position" in p.get("msg", "") else _s(t, p)
DB["fehl"] = []
e = app.kk_tick(JETZT)
app.sb_select = _s
check(e.get("fehler_regeln") == ["nur_schliessen: RuntimeError"], "Lesefehler einer neuen Regel: nur diese Regel leer, Takt läuft weiter")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
