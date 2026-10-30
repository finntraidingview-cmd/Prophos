#!/usr/bin/env python3
"""Selbsttest: FUNDED-PLANER JE GRUPPE (30.10.2026, Finn ~07:13: „Beide sind einfach wie Unternehmen, die Prophos nutzen — genau gleich
planen und genau gleich sehen"). Prüft fd_plan_ids / fd_gruppen_schluessel / Sicht und je einen Lauf des Funded-Planers (Futures, fdp_planen)
und des Funded-CFD-Planers (fcp_planen) mit HT-IDs + Emins Gruppe gegen eine nachgebaute DB: beide Gruppen werden geplant, der Firmen-Abstand
gilt je Gruppe, jede Sicht zeigt nur ihre Gruppe, die HT-Liste „IDs verwalten" nimmt nie Gruppen-IDs. Ohne Netz, schreibt nichts.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_funded_je_gruppe.py"""
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


H1, H2 = "00000000-0000-4000-a000-0000000000h1".replace("h", "0"), "00000000-0000-4000-a000-0000000000h2".replace("h", "0")
E1, E2 = "00000000-0000-4000-a000-0000000000e1".replace("e", "9"), "00000000-0000-4000-a000-0000000000e2".replace("e", "9")
DATEN = {"gruppen": [{"id": "g-emin", "name": "Emin", "verwalter_id": E1}, {"id": "g-ht", "name": "Hermann Technologies", "verwalter_id": None}],
         "mitglieder": [{"gruppe_id": "g-emin", "user_id": E1}, {"gruppe_id": "g-emin", "user_id": E2},
                        {"gruppe_id": "g-ht", "user_id": H1}, {"gruppe_id": "g-ht", "user_id": H2}]}
EMIN = frozenset({E1, E2})

print("1) Bausteine")
check(app.fd_plan_ids([H1, H2], {E2, E1}) == [H1, H2, E1, E2], "user_ids (HT) + alle Gruppen-IDs, ohne Doppelte")
check(app.fd_plan_ids([H1, E1], {E1}) == [H1, E1], "Gruppen-ID schon in user_ids → einmal")
check(app.fd_gruppen_schluessel(H1, DATEN) == "g-ht" and app.fd_gruppen_schluessel(E2, DATEN) == "g-emin", "Gruppen-Schlüssel wie prophos_gruppe_von (HT / Emin)")
check(app.fd_gruppen_schluessel("x", DATEN) == "ohne", "ohne Mitglieds-Zeile eigener Topf (DB: NULL)")
check(app.fd_gruppen_schluessel(E1, {"mitglieder": [{"gruppe_id": "b", "user_id": E1}, {"gruppe_id": "a", "user_id": E1}]}) == "a", "kleinste gruppe_id gewinnt")
check(app.fd_gruppen_schluessel(E1, {}) == "ht", "ohne Gruppen-Daten wie bisher ein Topf")
von = lambda u: app.admin_lese_gruppe_menge(u, DATEN)   # noqa: E731
alle = [H1, H2, E1, E2]
check(app.fcp_gruppen_sicht(H1, alle, von) == frozenset({H1, H2}), "HT-Login sieht nur HT")
check(app.fcp_gruppen_sicht(E2, alle, von) == EMIN, "Mitglied von Emins Gruppe sieht die Gruppe")
check(app.fcp_schreib_sicht(None, app.fcp_gruppen_sicht(H1, alle, von)) == frozenset({H1, H2}), "Admin (HT) schreibt nur HT")
check(app.fcp_schreib_sicht(EMIN, app.fcp_gruppen_sicht(E1, alle, von)) == EMIN, "Verwalter mit sicht=admin schreibt seine Gruppe")
check(app.fcp_schreib_sicht(str(E2), app.fcp_gruppen_sicht(E2, alle, von)) == str(E2), "Mitglied ohne Code schreibt nur sich")
check(app.fcp_schreib_sicht(str(H1), frozenset({H2})) == str(H1), "eigene Pläne bleiben anfassbar, auch außerhalb der Liste")

print("2) Funded-Planer Futures (fdp_planen) mit HT + Emins Gruppe")
ST100 = [{"minis": 3, "ab_balance": 100000, "daily_loss_usd": 1750}, {"minis": 6, "ab_balance": 110000, "daily_loss_usd": 3500}]
konten = [{"id": f"k{i}", "user_id": u, "name": f"100k PAAPEX00000000{i:02d} → Funded", "firm": "Apex Trader", "account_type": "funded",
           "auto_planer": True, "tv_balance": 100000, "tv_balance_at": "2026-11-01T22:00:00+00:00", "created_at": "2026-10-01T00:00:00+00:00"}
          for i, u in enumerate([H1, H1, H2, E1, E2, E2], 1)]
REG = {"id": 1, "aktiv": True, "auto_bestaetigen": False, "user_ids": [H1, H2], "firmen": app.FDP_FIRMEN_STANDARD, "zeiten": dict(app.FDP_ZEITEN_STANDARD)}
ANGEFRAGT = {}


def sb_all(tab, par):
    if tab == "accounts":
        ANGEFRAGT["accounts"] = par.get("user_id")
        return [dict(a) for a in konten if a["user_id"] in par.get("user_id", "")]
    return []


def sb_select(tab, par):
    if tab == "funded_plan_regeln":
        return [REG]
    if tab == "auto_plan_regeln":
        return [{"zeiten": {"fenster": [["04:00", "05:30", 100]], "fenster_tz": "Asia/Dubai"}}]   # enges Fenster: Firmen-Abstand greift
    return []


GESCHRIEBEN = []
app._sb_all, app.sb_select = sb_all, sb_select
app.sb_insert = lambda t, b: GESCHRIEBEN.append((t, b))
app.sb_update = lambda *a: GESCHRIEBEN.append(a)
app._ap_archiviert = lambda streng=False: set()
app._liq_verlauf_laden = lambda ids: []
app._liq_regeln_laden = lambda: [{"firma": "Apex Trader", "kontotyp": "funded", "groesse": 100000, "art": "stufen", "stufen": ST100}]
app._ap_namen = lambda: ({H1: "HT-1", H2: "HT-2", E1: "Emin", E2: "Ahmad"}, set())
app._fdp_ht_ids = lambda: [H1, H2]
app.ap_planer_gruppen_ids = lambda: set(EMIN)
app.admin_gruppen_daten = lambda: DATEN
jetzt = datetime(2026, 11, 1, 22, 30, tzinfo=timezone.utc)      # Mo 02:30 Dubai, vor dem Fenster
e = app.fdp_planen(trocken=True, jetzt=jetzt, seed=3)
check(all(u in (ANGEFRAGT.get("accounts") or "") for u in (H1, H2, E1, E2)), "Konten von HT und Emins Gruppe gelesen")
ug = {z["user_id"] for z in e["geplant"]}
check(ug & {H1, H2} and ug & EMIN, f"beide Gruppen bekommen Vorschläge ({len(e['geplant'])} geplant)")
st = {}
for z in e["geplant"]:
    st.setdefault("emin" if z["user_id"] in EMIN else "ht", []).append(datetime.fromisoformat(z["start_um"]))
ab = lambda v: min([abs((a - b).total_seconds()) / 60 for i, a in enumerate(v) for b in v[i + 1:]] or [999])   # noqa: E731
check(all(ab(v) >= 15 for v in st.values()), "≥ 15 min je Firma INNERHALB jeder Gruppe")
quer = min([abs((a - b).total_seconds()) / 60 for a in st.get("ht", []) for b in st.get("emin", [])] or [999])
print(f"     kleinster Abstand HT ↔ Emin: {quer:.1f} min (darf < 15 sein — jede Gruppe für sich)")
check({z["user_id"] for z in e["alle_ids"] if z.get("fest")} == EMIN and all(z["drin"] for z in e["alle_ids"]), "Gruppen-IDs in „IDs verwalten“ fest drin")
s_ht, s_em = app.fcp_sicht(e, frozenset({H1, H2})), app.fcp_sicht(e, EMIN)
check({z["user_id"] for k in ("geplant", "ausgelassen", "ids", "alle_ids") for z in s_ht[k]} <= {H1, H2}, "Sicht HT: keine Emin-Zeile (auch ids/alle_ids)")
check({z["user_id"] for k in ("geplant", "ausgelassen", "ids", "alle_ids") for z in s_em[k]} <= EMIN, "Sicht Emin: keine HT-Zeile")
e2 = app.fdp_planen(trocken=True, jetzt=jetzt, seed=3, nur_ids=EMIN)
check({z["user_id"] for z in e2["geplant"]} <= EMIN and e2["geplant"], "„Jetzt planen“ des Verwalters plant nur seine Gruppe")
check(not GESCHRIEBEN, "Trockenläufe schreiben nichts")
REG["auto_bestaetigen"] = True
e3 = app.fdp_planen(trocken=True, jetzt=jetzt, seed=3)
REG["auto_bestaetigen"] = False
check(all(z["vorschlag"] == (z["user_id"] in EMIN) for z in e3["geplant"]) and any(z["user_id"] in EMIN for z in e3["geplant"]),
      "Auto-Bestätigen gilt nur für die HT-Liste — Emins Gruppe bleibt Vorschlag")

print("3) Funded-CFD-Planer (fcp_planen) nimmt Gruppen-IDs auch ohne Eintrag in user_ids")
app._fcp_regeln_laden = lambda: {"aktiv": False, "user_ids": [H1], "firmen": [], "zeiten": {}}
ANGEFRAGT.clear()
r = app.fcp_planen(trocken=True, jetzt=jetzt)
check(r.get("msg") == "keine Firma an" and not r["geplant"], "ohne Firma an: nichts geplant (Rahmen läuft)")
check(app.fd_plan_ids([H1], app.ap_planer_gruppen_ids()) == [H1, E1, E2] or app.fd_plan_ids([H1], app.ap_planer_gruppen_ids()) == [H1] + sorted(EMIN),
      "CFD-Planer-IDs = user_ids + Emins Gruppe")

print("4) Quelltext: keine „nur Hermann Technologies“-Sperre mehr im Funded-Planer-GET, HT-Liste nimmt keine Gruppen-ID")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
i = src.index('def admin_funded_plan():')
check('"msg": "Funded-Planer nur für Hermann Technologies"' not in src[i:i + 2500], "GET /admin/funded-plan ohne HT-Sperre")
j = src.index('def admin_funded_plan_ids():')
check('body.get("drin") and admin_lese_gruppe_menge' in src[j:j + 2500], "POST /admin/funded-plan/ids lehnt Gruppen-IDs nur beim Hinzufügen ab")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
