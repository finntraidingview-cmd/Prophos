#!/usr/bin/env python3
"""Selbsttest SB1 STARTWERT FÜR ALLE PLANER (17.11.2026, Slave-Terminal 10 — Finn ~04:05 Dubai: „Bei einem neuen Account oder Nachfolger ist die
Balance klar: Ein 50k-Nachfolger hat 50k, ein 150k-Nachfolger 150k … Dann kann der Trade-Planer gleich planen").
Geprüft: (1) ap_startwerte_laden — dieselbe Kette wie ap_planen (Kandidat → Trade-Verlauf → Login-Zwillinge → ap_startwert_frisch), Echo-Karten nur
bei Kandidaten, Lesefehler → {}; (2) Funded Futures fdp_planen: frischer 50k-/150k-Nachfolger → Plan mit 50.000/150.000, Notiz-Zusatz, nichts als
„gelesen" geschrieben; Hand-Trade, Login-Zwilling, Lesung → wie bisher; (3) Funded CFD fcp_planen: frischer 50k-/100k-/200k-Nachfolger → Plan mit
der Größe; Echo-Lesung schlägt den Startwert; (4) Challenge-Planer ap_planen hat den Startwert schon (selftest_startwert_frisch);
(5) BITGLEICH gegen den Stand VOR SB1 (4c6eda8e~1, fest — origin/main enthält SB1 seit dem Push): Konten MIT Lesung ergeben in fdp_planen und fcp_planen genau dieselben Pläne/Zeilen wie vorher; dazu vorher/nachher
für die frischen Konten. (6) Balance-Wache: Startwert-Pläne ohne Lesung fasst sie nicht an, eine abweichende echte Lesung wie bisher.
Platzhalter-IDs, keine echten Konten. Ohne Netz. Aufruf: python3 tools/selftest_sb1_startwert_alle_planer.py"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def modul(pfad, name):
    spec = importlib.util.spec_from_file_location(name, pfad)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


NEU = modul(os.path.join(WURZEL, "app" + ".py"), "app_neu")
_alt_dir = tempfile.mkdtemp(prefix="sb1_alt_")
# SB1c (Prüfer S2, 17.11.2026): fester Vorgänger statt origin/main — seit SB1 (4c6eda8e) auf main liegt, plante „vorher“ auch und Teil 5 war immer rot
BASIS = "4c6eda8e~1"
_alt_src = subprocess.run(["git", "-C", WURZEL, "show", BASIS + ":app" + ".py"], capture_output=True, text=True, check=True).stdout
with open(os.path.join(_alt_dir, "app_alt.py"), "w", encoding="utf-8") as f:
    f.write(_alt_src)
ALT = modul(os.path.join(_alt_dir, "app_alt.py"), "app_alt")

# ── nachgebaute DB ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
U = {n: f"00000000-0000-4000-a000-0000000000{i:02d}" for i, n in enumerate("ABCDEFGH", 1)}
FREMD = []          # fremd_positionen (Hand-Trade ohne Plan)
ALT_EINTRAG = []    # ältere Konto-Einträge desselben Logins (Zwilling)
ABFRAGEN = []


def fut(i, u, name, **x):
    return dict({"id": f"f0000000-0000-4000-a000-0000000000{i:02d}", "user_id": U[u], "name": name, "firm": "Apex Trader", "account_type": "funded",
                 "external_id": f"PAAPEX-0000{i:02d}", "auto_planer": True, "tv_balance": None, "tv_balance_at": None,
                 "created_at": "2026-10-27T18:00:00+00:00"}, **x)


def cfd(i, u, name, firma, **x):
    return dict({"id": f"c0000000-0000-4000-a000-0000000000{i:02d}", "user_id": U[u], "name": name, "firm": firma, "account_type": "funded_cfd",
                 "external_id": f"9000{i:02d}", "auto_planer": True, "tv_balance": None, "tv_balance_at": None,
                 "created_at": "2026-11-01T18:00:00+00:00"}, **x)


# Funded Futures (Apex-Regel + 50k-Zeile nur für den Test)
F150 = fut(1, "A", "150k PAAPEX000000000001 → Funded")
F50 = fut(2, "B", "50k PAAPEX000000000002 → Funded")
F_HAND = fut(3, "C", "150k PAAPEX000000000003 → Funded")                       # Hand-Trade (fremd_positionen) → nicht frisch
F_ZW = fut(4, "D", "100k PAAPEX000000000004 → Funded", external_id="PAAPEX-ALT04")   # Login hängt an einem älteren Eintrag
F_LES = fut(5, "E", "150k PAAPEX000000000005 → Funded", tv_balance=151234.5, tv_balance_at="2026-10-27T19:00:00+00:00")
F_LES2 = fut(6, "F", "100k PAAPEX000000000006 → Funded", tv_balance=101500, tv_balance_at="2026-10-27T19:00:00+00:00")
F_OHNE_EXT = fut(7, "G", "150k PAAPEX000000000007 → Funded", external_id="")   # Gegenprüfung: tvv2 ohne Login startet rot → kein Startwert
F_AUS = fut(8, "H", "150k PAAPEX000000000008 → Funded", auto_planer=False)      # Dauer-Auslasser → keine Verlaufs-Abfrage
# Funded CFD
C100 = cfd(1, "A", "100k 900001 → Funded", "FundedNext")
C50 = cfd(2, "B", "50k 900002 → Funded", "FundingPips", max_risiko_trade=None)
C200 = cfd(3, "C", "200k 900003 → Funded", "The5%ers")
C_LES = cfd(4, "D", "100k 900004 → Funded", "FundedNext")                      # Echo kennt den Login: 100.500
C_HAND = cfd(5, "E", "100k 900005 → Funded", "FundedNext")                     # Hand-Trade → nicht frisch
C_LES2 = cfd(6, "F", "200k 900006 → Funded", "The5%ers")                       # Echo 201.000
ECHO = {"900004": (100500.0, "USD", "2026-11-02T03:30:00+00:00"), "900006": (201000.0, "USD", "2026-11-02T03:30:00+00:00")}

FDP_FIRMEN = copy.deepcopy(NEU.FDP_FIRMEN_STANDARD)
FDP_FIRMEN[0]["je_groesse"]["50000"] = {"ziel_gewinn": 6000, "max_trade": 3000, "kosten_eur": 200, "dd": 2500, "kontrakte": {"2": 1.0}}
ST = {150000: [{"minis": 4, "ab_balance": 150000, "daily_loss_usd": 2500}], 100000: [{"minis": 3, "ab_balance": 100000, "daily_loss_usd": 1750}],
      50000: [{"minis": 2, "ab_balance": 50000, "daily_loss_usd": 1000}]}


def cfd_firmen():
    import re
    sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
    return json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))


FCP_FIRMEN = cfd_firmen()
PPL = {"the5ers": 1.0, "fundednext": 10.0, "fundingpips": 20.0, "tradeifycfd": 10.0}
FUS = {u: f"e0000000-0000-4000-a000-0000000000{i:02d}" for i, u in enumerate(U.values(), 1)}


def stubs(app, konten, art, geschrieben):
    """Setzt die DB-Stubs am Modul. konten = Liste dicts; art 'funded' | 'funded_cfd'."""
    alle = {str(k["id"]): k for k in konten}

    def sb_select(t, p):
        if t == "funded_plan_regeln":
            return [{"id": 1, "aktiv": False, "auto_bestaetigen": False, "user_ids": list(U.values()), "firmen": FDP_FIRMEN,
                     "zeiten": dict(app.FDP_ZEITEN_STANDARD)}]
        if t == "funded_cfd_plan_regeln":
            return [{"id": 1, "aktiv": False, "auto_bestaetigen": False, "ziel_auto_wartet": False, "user_ids": list(U.values()), "firmen": FCP_FIRMEN,
                     "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}]
        if t == "auto_plan_regeln":
            return [{"zeiten": {"tz": "Europe/Berlin", "fenster": [["04:00", "20:00", 100]], "fenster_tz": "Asia/Dubai", "start_bis": "20:00"}}]
        return []

    def sb_all(t, p):
        sel = str(p.get("select") or "")
        if t == "accounts" and p.get("account_type") == f"eq.{art}":
            return [dict(k) for k in konten]
        if t == "accounts" and "external_id" in p and sel == "id,external_id,created_at":   # _ap_login_zwillinge
            ABFRAGEN.append(("zwillinge", p["external_id"]))
            logins = p["external_id"][4:-1].replace('"', "").split(",")
            out = [{"id": k["id"], "external_id": k["external_id"], "created_at": k["created_at"]} for k in konten if k.get("external_id") in logins]
            return out + [dict(z) for z in ALT_EINTRAG if z["external_id"] in logins]
        if t == "accounts":   # Fusion-Hedge-Konten (Funded CFD)
            return [{"id": v, "user_id": u, "external_id": "8" + v[-6:], "name": "Fusion " + v[-4:], "firm": "Fusion Markets"} for u, v in FUS.items()]
        if t == "trade_plans" and sel.endswith(",status,started_at,ended_at,orbit_gesendet_at"):   # _ap_konten_mit_trade
            ABFRAGEN.append(("verlauf", sel.split(",")[0]))
            return []
        if t == "fremd_positionen":
            return [{"konto_id": k} for k in FREMD]
        if t == "user_settings":
            return [{"user_id": u, "value": {"accountId": f}} for u, f in FUS.items()]
        if t == "firm_specs":
            return [{"user_id": u, "name": n, "ppl": PPL[app._ap_norm(n)], "unit": "Lots"} for u in U.values() for n in ("FundedNext", "The5%ers", "FundingPips")]
        if t == "id_gruppe_mitglied":
            return [{"user_id": u, "gruppe_id": "ht"} for u in U.values()]
        return []
    app.sb_select, app._sb_all = sb_select, sb_all
    app.sb_insert = lambda t, z: geschrieben.append(("insert", t, z))
    app.sb_update = lambda t, p, b: geschrieben.append(("update", t, p, b)) or [{}]
    app._ap_archiviert = lambda streng=False: set()
    app._ap_namen = lambda: ({u: n for n, u in U.items()}, set())
    app._liq_verlauf_laden = lambda ids: []
    app._liq_regeln_laden = lambda: [{"firma": "Apex Trader", "kontotyp": "funded", "groesse": g, "art": "stufen", "stufen": s} for g, s in ST.items()]
    app.admin_gruppen_daten = lambda: {"gruppen": [], "mitglieder": []}
    app.ap_planer_gruppen_ids = lambda: set()
    app._ap_balance_karten = lambda: (dict(ECHO), {})
    app.fusion_sppl = lambda *a, **k: 0.85
    app.tw_pause_grund = lambda *a, **k: None          # Handels-Würfel aus: der Test prüft die Balance, nicht den Pause-Tag
    return alle


JETZT_F = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)    # 01:00 Dubai → plant den Handelstag 28.10.
JETZT_C = datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc)      # Montag 08:00 Dubai


def lauf_f(app, konten, scharf=False):
    g = []
    stubs(app, konten, "funded", g)
    e = app.fdp_planen(trocken=not scharf, jetzt=JETZT_F, seed=27)
    return e, g


def lauf_c(app, konten, scharf=False):
    g = []
    stubs(app, konten, "funded_cfd", g)
    e = app.fcp_planen(trocken=not scharf, jetzt=JETZT_C, seed=42)
    return e, g


def je_konto(e):
    gp = {z.get("konto_id"): z for z in e.get("geplant") or []}
    aus = {z.get("konto_id"): z.get("grund") for z in e.get("ausgelassen") or []}
    return gp, aus


def kern(e, g):
    """Vergleichbarer Kern eines Laufs (ohne Zeitstempel des Laufs selbst)."""
    e = {k: v for k, v in e.items() if k not in ("at",)}
    return json.dumps({"erg": e, "geschrieben": g}, sort_keys=True, default=str)


def main():
    S = NEU.ap_startwerte_laden
    print("1) ap_startwerte_laden — dieselbe Kette wie ap_planen")
    FREMD[:] = [F_HAND["id"]]
    ALT_EINTRAG[:] = [{"id": "f0000000-0000-4000-a000-0000000000a4", "external_id": "PAAPEX-ALT04", "created_at": "2026-09-01T00:00:00+00:00"}]
    stubs(NEU, [F150, F50, F_HAND, F_ZW, F_LES], "funded", [])
    karten_geladen = []
    NEU._ap_balance_karten = lambda: karten_geladen.append(1) or ({}, {})
    ABFRAGEN.clear()
    sw = S([F150, F50, F_HAND, F_ZW, F_LES])
    check(sw == {F150["id"]: 150000.0, F50["id"]: 50000.0}, f"frischer 150k- und 50k-Nachfolger → 150.000 / 50.000, Hand-Trade/Zwilling/Lesung nicht ({sw})")
    check(karten_geladen == [1], "Echo-/Duplikum-Karten genau einmal geladen (es gab Kandidaten)")
    karten_geladen.clear()
    ABFRAGEN.clear()
    check(S([F_LES, F_LES2]) == {} and not karten_geladen and not ABFRAGEN, "nur Konten mit Lesung → keine Abfrage, kein Startwert")
    check(S([F150], {"PAAPEX-000001": (150010.0, "USD", "x")}, {}) == {}, "Echo kennt den Login (liefert Balance) → kein Startwert")
    check(S([F150], {"PAAPEX-000001": (0, "USD", "x")}, {}) == {}, "Echo kennt den Login, aber 0 → gilt als gelesen, kein Startwert")
    xfa = fut(9, "H", "50k EXPRESS-V2-000000-00000000", firm="Topstep", external_id="EXPRESS-V2-000000-00000000")
    check(S([xfa], {}, {}) == {}, "Topstep Express (0-basiert) nie")
    check(S([dict(F150, meta_api_last_check="2026-10-01T00:00:00+00:00")], {}, {}) == {}, "frühere Lesung (meta_api_last_check) → nicht frisch")
    alt_all = NEU._sb_all
    NEU._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("503")) if t == "trade_plans" else alt_all(t, p)
    check(S([F150], {}, {}) == {}, "Trade-Verlauf nicht lesbar → kein Startwert (wie ap_planen)")
    NEU._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("503")) if t == "accounts" and "external_id" in p else alt_all(t, p)
    check(S([F150], {}, {}) == {}, "Login-Zwillinge nicht lesbar → kein Startwert")
    NEU._sb_all = alt_all

    print("2) Funded Futures (fdp_planen)")
    konten = [F150, F50, F_HAND, F_ZW, F_LES, F_OHNE_EXT, F_AUS]
    ABFRAGEN.clear()
    e, g = lauf_f(NEU, konten)
    gp, aus = je_konto(e)
    gefragt = " ".join(str(x[1]) for x in ABFRAGEN)
    check(F_OHNE_EXT["id"] not in gp and aus.get(F_OHNE_EXT["id"]) == "Balance nicht live — ↻ Balance lesen",
          f"frisch, aber ohne External ID (tvv2) → kein Startwert, wie bisher ausgelassen ({aus.get(F_OHNE_EXT['id'])})")
    check(any(x[0] == "zwillinge" for x in ABFRAGEN) and "PAAPEX-000008" not in gefragt and "PAAPEX-000007" not in gefragt,
          "Haken aus / ohne External ID: nicht im Vorfilter, keine Abfrage für sie")
    for k in konten:
        z = gp.get(k["id"])
        print(f"     {k['name']:34} → " + (f"PLAN Balance {z.get('balance')} ({z.get('balance_quelle') or 'TV'}) · {z.get('kontrakte')} NQ · TP {z.get('tp')}" if z else f"AUS {aus.get(k['id'])}"))
    check(gp.get(F150["id"], {}).get("balance") == 150000 and gp[F150["id"]].get("startwert") and gp[F150["id"]].get("balance_quelle") == NEU.AP_STARTWERT_QUELLE,
          "frischer 150k-Funded-Nachfolger → Plan mit 150.000 (Startwert)")
    check(gp.get(F50["id"], {}).get("balance") == 50000 and gp[F50["id"]].get("startwert"), "frischer 50k-Funded-Nachfolger → Plan mit 50.000 (Startwert)")
    check(F_HAND["id"] not in gp and aus.get(F_HAND["id"]) == "Balance nicht live — ↻ Balance lesen", "Hand-Trade ohne Lesung → wie bisher ausgelassen")
    check(F_ZW["id"] not in gp and aus.get(F_ZW["id"]) == "Balance nicht live — ↻ Balance lesen", "Login eines älteren Eintrags (Zwilling) → wie bisher ausgelassen")
    check(gp.get(F_LES["id"], {}).get("balance") == 151234.5 and not gp[F_LES["id"]].get("startwert"), "echte Lesung 151.234,50 schlägt den Startwert")
    e2, g2 = lauf_f(NEU, konten, scharf=True)
    zeilen = {z["master_account_id"]: z for (_a, t, z, *_r) in [x for x in g2 if x[0] == "insert"] if t == "trade_plans"}
    check(NEU.AP_STARTWERT_TEXT in (zeilen.get(F150["id"]) or {}).get("notes", "") and NEU.AP_STARTWERT_TEXT not in (zeilen.get(F_LES["id"]) or {}).get("notes", "x"),
          "scharf: Notiz „Balance aus Startwert …“ nur am Startwert-Plan")
    check(not any(x[0] == "update" and x[1] == "accounts" and any(f in x[3] for f in ("tv_balance", "tv_balance_at")) for x in g2),
          "scharf: nichts als „gelesen“ in accounts geschrieben")
    check(not NEU._AP_BAL_PLAN.search(NEU.AP_STARTWERT_TEXT), "Notiz-Zusatz trifft das Muster der Balance-Wache nicht")

    print("3) Funded CFD (fcp_planen)")
    FREMD[:] = [C_HAND["id"]]
    konten_c = [C100, C50, C200, C_LES, C_HAND]
    e, g = lauf_c(NEU, konten_c)
    gp, aus = je_konto(e)
    for k in konten_c:
        z = gp.get(k["id"])
        print(f"     {k['name']:24} {k['firm']:11} → " + (f"PLAN Balance-Quelle {z.get('bal_quelle')} · Gewinn {z.get('gewinn')} · TP {z.get('tp')} · {z.get('lots')} Lot" if z else f"AUS {aus.get(k['id'])}"))
    for k, gr in ((C100, 100000), (C50, 50000), (C200, 200000)):
        z = gp.get(k["id"]) or {}
        check(z.get("bal_quelle") == NEU.AP_STARTWERT_QUELLE and z.get("startwert") and z.get("gewinn") == 0,
              f"frischer {gr // 1000}k-Nachfolger {k['firm']} → Plan mit Startwert {gr:,} (Gewinn 0) ({z.get('bal_quelle')}, {aus.get(k['id'])})".replace(",", "."))
    z = gp.get(C_LES["id"]) or next((x for x in e.get("ziel") or [] if x.get("konto_id") == C_LES["id"]), {})   # 100.500 = Ziel bei FundedNext
    check(z.get("bal_quelle") == "Echo" and z.get("gewinn") == 500 and not z.get("startwert"),
          f"Echo-Lesung 100.500 schlägt den Startwert ({z.get('bal_quelle')}, Gewinn {z.get('gewinn')}, {z.get('grund') or 'Plan'})")
    check(C_HAND["id"] not in gp and aus.get(C_HAND["id"]) == "keine Balance — ↻ Balance lesen", f"Hand-Trade ohne Lesung → wie bisher „keine Balance“ ({aus.get(C_HAND['id'])})")
    e2, g2 = lauf_c(NEU, konten_c, scharf=True)
    zeilen = {z["master_account_id"]: z for (_a, t, z, *_r) in [x for x in g2 if x[0] == "insert"] if t == "trade_plans"}
    check(NEU.AP_STARTWERT_TEXT in (zeilen.get(C100["id"]) or {}).get("notes", "") and NEU.AP_STARTWERT_TEXT not in (zeilen.get(C_LES["id"]) or {}).get("notes", "x"),
          "scharf: Notiz „Balance aus Startwert …“ nur am Startwert-Plan")
    check(not any(x[0] == "update" and x[1] == "accounts" and any(f in x[3] for f in ("tv_balance", "tv_balance_at")) for x in g2),
          "scharf: nichts als „gelesen“ in accounts geschrieben")

    print("4) Challenge-Planer / Gruppen-Planer: Startwert schon da (selftest_startwert_frisch prüft ap_planen)")
    src = open(os.path.join(WURZEL, "app" + ".py"), encoding="utf-8").read()
    for fn in ("ap_planen", "gp_planen"):
        i = src.index(f"\ndef {fn}(")
        seg = src[i:src.index("\n\n\n", i)]
        check("sw = ap_startwert_frisch(a, _ht, gelesen=_gel)" in seg, f"{fn}: ap_startwert_frisch im Weg (unverändert)")

    print(f"5) BITGLEICH gegen den Stand vor SB1 ({BASIS}, Konten mit Lesung)")
    FREMD[:] = []
    ALT_EINTRAG[:] = []
    for scharf in (False, True):
        a, b = kern(*lauf_f(ALT, [F_LES, F_LES2], scharf)), kern(*lauf_f(NEU, [F_LES, F_LES2], scharf))
        check(a == b, f"Funded Futures {'scharf (Zeilen + Lauf)' if scharf else 'Trockenlauf'}: bitgleich ({len(a)} Zeichen)")
        a, b = kern(*lauf_c(ALT, [C_LES, C_LES2], scharf)), kern(*lauf_c(NEU, [C_LES, C_LES2], scharf))
        b = b.replace(', "min_je_100k": 2000.0', '')   # FZ2 (24.11.2026): On-Demand-Regel trägt das Firmen-Minimum — gewollt neu, sonst bitgleich
        check(a == b, f"Funded CFD {'scharf (Zeilen + Lauf)' if scharf else 'Trockenlauf'}: bitgleich ({len(a)} Zeichen)")
    print(f"   vorher ({BASIS}) → nachher, frische Konten:")
    for name, lf, ks in (("Futures", lauf_f, [F150, F50]), ("CFD", lauf_c, [C100, C50, C200])):
        (ea, _x), (en, _y) = lf(ALT, ks), lf(NEU, ks)
        ga, aa = je_konto(ea)
        gn, an = je_konto(en)
        for k in ks:
            print(f"     {name:7} {k['name']:34} {'PLAN' if k['id'] in ga else 'AUS „' + str(aa.get(k['id'])) + '“'} → {'PLAN' if k['id'] in gn else 'AUS ' + str(an.get(k['id']))}")
        check(not any(k["id"] in ga for k in ks) and all(k["id"] in gn for k in ks), f"{name}: vorher ausgelassen, jetzt geplant")

    print("6) Balance-Wache")
    p = {"notes": "Auto-Planer · Etappe · Rest 9.000 $ bis Ziel · Balance 150.000 (Startwert (frisches Konto))"}
    a0 = {"id": "x", "name": "150k Test → Challenge", "firm": "Lucid Trading", "account_type": "challenge", "external_id": "LFE-0"}
    check(NEU.ap_plan_bal_abweichung(p, a0, {}, {}, None) is None, "Startwert-Plan ohne Lesung → Wache greift nicht")
    check(NEU.ap_plan_bal_abweichung(p, dict(a0, tv_balance=150000, tv_balance_at="2026-11-17T00:09:00+00:00"), {}, {}, None) is None,
          "Lesung 150.000 = Startwert → Wache greift nicht")
    check(NEU.ap_plan_bal_abweichung(p, dict(a0, tv_balance=147000, tv_balance_at="2026-11-17T00:09:00+00:00"), {}, {}, None) == (150000.0, 147000.0),
          "spätere echte Lesung 147.000 weicht ab → Wache wie bisher")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
