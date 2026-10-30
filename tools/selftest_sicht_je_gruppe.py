#!/usr/bin/env python3
"""Selbsttest SICHT JE GRUPPE (app.py/prophos.html, 30.10.2026, Finn 05:08: „Eine ID von Hermann Technologies soll im Radar nur alle Trades
von Hermann Technologies sehen, auch im Planer. Eine ID von Emin soll im Radar nur alle Trades von Emins IDs sehen, im Planer genau das
Gleiche."). Ohne Netz: admin_lese_gruppe_menge rein; Quelltext-Verträge für Radar (live-trades, handarbeit), Planer-Lese-Routen,
Übersicht, Frontend — und dass KEIN Schreibweg die Lese-Gruppe benutzt (Mitglied ändert weiter nur eigene Pläne).
Aufruf: python3 tools/selftest_sicht_je_gruppe.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def ok(bed, txt):
    print(("  ok   " if bed else "  FEHL ") + txt)
    if not bed:
        FEHLER.append(txt)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


def fn_text(name):
    i = SRC.index(f"\ndef {name}(") + 1
    m = re.search(r"\n(def |@app\.route|# ══)", SRC[i:])
    return SRC[i:i + m.start()] if m else SRC[i:]


ns = {}
exec(block("admin_lese_gruppe_menge"), ns)
L = ns["admin_lese_gruppe_menge"]
D = {"gruppen": [{"id": "g-emin", "verwalter_id": "u-emin"}, {"id": "g-ht", "verwalter_id": None}],
     "mitglieder": [{"user_id": "u-ahmad", "gruppe_id": "g-emin"}, {"user_id": "u-julian", "gruppe_id": "g-emin"},
                    {"user_id": "u-finn", "gruppe_id": "g-ht"}]}
print("admin_lese_gruppe_menge")
ok(L("u-emin", D) == frozenset({"u-emin", "u-ahmad", "u-julian"}), "Verwalter → ganze Gruppe")
ok(L("u-julian", D) == frozenset({"u-emin", "u-ahmad", "u-julian"}), "Mitglied → ganze Gruppe (nicht nur er)")
ok(L("u-finn", D) is None, "HT-Mitglied → None")
ok(L("u-neu", D) is None and L("u-x", None) is None, "unbekannt / ohne Daten → None")

print("Radar")
lt = fn_text("admin_live_trades")
ok('request.args.get("radar")' not in lt, "?radar=1 aus a3bbfba9 zurückgenommen (HT sieht Emins Gruppe nicht mehr)")
ok("admin_radar_lese_sicht(me)" in lt and "excluded = set(disp) - set(lese)" in lt, "live-trades: Gruppe MIT Verwalter liest ihre ganze Gruppe")
ok("None if nur_eigene else admin_radar_lese_sicht(me)" in lt, "PC-Tab-Takt (nur_eigene=1) bleibt bei der eigenen ID")
rl = fn_text("admin_radar_lese_sicht")
ok("_admin_eingeschraenkt() is None or not _admin_ansicht()" in rl, "Lese-Gruppe nur für eingeschränkte Logins in der Admin-Ansicht (HT unverändert)")
ha = fn_text("admin_handarbeit")
ok("lese_g = admin_radar_lese_sicht(me)" in ha and "ausgeblendet = set(namen) - set(lese_g)" in ha, "handarbeit (Manuell/Bestanden): Mitglied sieht die Gruppe")
ok("&radar=1" not in HTML, "Frontend fragt den Radar ohne ?radar=1")

print("Planer (nur lesen)")
ok("gruppe = ap_lese_gruppe(uid)" in fn_text("_ap_sicht_aus_anfrage"), "_ap_sicht_aus_anfrage: Mitglied liest die Gruppe")
ok("ap_lese_gruppe(uid)" in fn_text("_ap_zugang") and "ap_lese_gruppe(uid)" in fn_text("admin_auto_plan"), "Lese-Gates: Mitglied wie Verwalter")
ids = fn_text("admin_auto_plan_ids")
ok('request.method == "GET" and _admin_ansicht()' in ids and 'if gruppe and request.method == "POST":' in ids,
   "/ids: Mitglied liest nur per GET, POST (Planer-Haken) bleibt gesperrt")
ok('gruppen_info["lese_gruppe"]' in fn_text("admin_build_overview") if "def admin_build_overview(" in SRC else 'gruppen_info["lese_gruppe"]' in SRC,
   "Übersicht meldet lese_gruppe ans Frontend")
ok("if(name === 'planer' && admData && admData.lese_gruppe) return true" in HTML, "Frontend: Challenge-Planer-Reiter für Mitglieder")

print("Keine Schreibrechte erweitert")
for n in ("ap_eingriff_sicht", "ap_eingriff_admin_reiter", "_ap_gruppe_lesen", "_admin_darf_uid", "admin_sicht_menge"):
    ok("ap_lese_gruppe" not in fn_text(n) and "admin_lese_gruppe_menge" not in fn_text(n), f"{n} kennt die Lese-Gruppe nicht")
for route in ("/admin/auto-plan/bestaetigen", "/admin/auto-plan/plan"):
    i = SRC.find(f'@app.route("{route}"')
    if i < 0:
        continue
    j = SRC.find("\n@app.route", i + 10)
    t = SRC[i:j]
    ok("ap_lese_gruppe" not in t.replace("_ap_zugang(admin_reiter=True)", ""), f"{route}: Eingriffe ohne Lese-Gruppe")

print("\nALLES OK" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
