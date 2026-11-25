"""Selbsttest KP2 Kaufliste (25.11.2026): Deckel „max. laufend“ + FNF-Freischaltung + Apex-5er-Pack im Vorrat-Lauf, Kauflisten-Zeilen,
Finns Regel „erwarteter Stand ≥ Ziel → nichts kaufen“ mit der echten Lauf-Rechnung, Fremd-Anlegen über /admin/konto-anlegen. Ohne Netz: holt die reinen Funktionen per AST aus app.py (kompiliert dabei die ganze Datei = Syntax-Check) und
importiert kaufliste_app mit einem Stub für kapital_app.

Aufruf:  python3 tools/selftest_kp2_kaufliste.py   (Abbruch beim ersten Fehler, Exit-Code 1)
"""
import ast
import os
import sys
import types

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
ok_n = 0


def pruef(bed, text):
    global ok_n
    if not bed:
        print("✗", text)
        sys.exit(1)
    ok_n += 1
    print("✓", text)


# ── 1. app.py: ganze Datei kompilieren, reine KP2-Teile herausholen ──
quelle = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
baum = ast.parse(quelle)
compile(baum, "app.py", "exec")
pruef(True, "app.py kompiliert")
teile = []
for knoten in baum.body:
    if isinstance(knoten, ast.FunctionDef) and knoten.name == "vorrat_kauf_deckel":
        teile.append(knoten)
    if isinstance(knoten, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("VORRAT_LAUFEND_TYPEN", "VORRAT_FNF_SPERRE", "VORRAT2_STD", "VORRAT2_RECHEN_STAND")
                                              for t in knoten.targets):
        teile.append(knoten)
ns = {}
exec(compile(ast.Module(body=teile, type_ignores=[]), "app.py(kp2)", "exec"), ns)
deckel, STD = ns["vorrat_kauf_deckel"], ns["VORRAT2_STD"]
pruef(ns["VORRAT2_RECHEN_STAND"] >= 9, "RECHEN_STAND hochgezählt (GET rechnet alte Läufe einmal neu)")
ml = STD["max_laufend"]
pruef(ml["Tradeify"] == 4 and ml["Apex Trader"] == 5 and ml["FTMO"] == 2 and ml["FundedNext"] == 2 and ml["FundingPips"] == 2
      and ml["The5%ers"] == 3 and ml["Topstep"] == 3 and ml["Lucid Trading"] == 3 and ml["FTMO Futures"] == 3
      and ml["FundedNext Futures"] == 3 and ml["Tradeify CFD"] == 3 and ml["Blue Guardian"] == 3 and ml["Audacity"] == 2,
      "Finns Werte max. laufend je Firma (KP1c)")

K = lambda stufe, bestand=False: {"stufe": stufe, "im_bestand": bestand}
# neue ID, 0 Konten: Lücke 10 → genau Max
pruef(deckel(10, [], "Tradeify", STD)["n"] == 4, "Tradeify neu: min(10, 4 − 0) = 4")
pruef(deckel(10, [], "Apex Trader", STD)["n"] == 5, "Apex neu: 5")
pruef(deckel(10, [], "FTMO", STD)["n"] == 2, "FTMO neu: 2")
# laufende zählen, Funded/Bestand nicht
d = deckel(10, [K("challenge"), K("challenge"), K("funded"), K("funded_cfd", True)], "Tradeify", STD)
pruef(d["laufend"] == 2 and d["n"] == 2, "Tradeify 2 Challenges laufen, Funded zählt nicht → 2")
pruef(deckel(10, [K("phase1"), K("phase2")], "FundedNext", STD)["n"] == 0, "FundedNext 2/2 laufend → 0")
pruef(deckel(10, [K("phase1")] * 5, "FundedNext", STD)["n"] == 0, "mehr laufend als Max → nie negativ")
pruef(deckel(1, [], "Tradeify", STD)["n"] == 1, "Lücke kleiner als Max → Lücke (1)")
pruef(deckel(0, [], "Tradeify", STD)["n"] == 0, "Lücke 0 → 0")
pruef(deckel(None, [], "Tradeify", STD)["n"] is None, "n_roh None (Sperre) bleibt None")
pruef(deckel(10, [], "Unbekannt GmbH", STD)["max"] == 3, "unbekannte Firma → max_laufend_std 3")
# FNF-Freischaltung
d = deckel(10, [], "FundedNext Futures", STD, fn_payout_ok=False)
pruef(d["n"] == 0 and d["sperre"] == "ab 1. FN-Payout", "FNF ohne FN-Payout → 0 + Sperre")
d = deckel(10, [], "FundedNext Futures", STD, fn_payout_ok=True)
pruef(d["n"] == 3 and d["sperre"] is None, "FNF mit FN-Payout → 3")
pruef(deckel(10, [], "FundedNext", STD, fn_payout_ok=False)["n"] == 2, "Sperre gilt nur für FNF, nicht für FundedNext CFD")

# Lauf-Verdrahtung im Quelltext: Deckel vor dem Totband, Felder an GET durchgereicht
i_dk, i_tb = quelle.find("dk = vorrat_kauf_deckel(nr"), quelle.find("tb = vorrat_totband(nr, vorher.get((uid, f))")
pruef(0 < i_dk < i_tb, "Deckel sitzt im Lauf vor vorrat_totband")
pruef("laufend_n=s.get(\"laufend_n\")" in quelle and "reserve=bool(s.get(\"reserve\"))" in quelle, "GET /admin/vorrat reicht laufend/max/sperre/reserve durch")
pruef("import kaufliste_app" in quelle and "kaufliste_app.registrieren(app, globals())" in quelle, "Modul in app.py registriert")

# Apex 5er-Pack (Finn 25.11.2026): erwartet < Ziel → genau 1 Pack (5), egal wie viele laufen; offenes Pack (laufend ohne Lesung) → 0
pruef(STD["kauf_pack"]["Apex Trader"] == 5, "Apex Kaufeinheit 5er-Pack")
KL_ = lambda stufe, gelesen=True: {"stufe": stufe, "im_bestand": False, "balance_at": "2026-11-25T10:00:00Z" if gelesen else None}
d = deckel(1, [KL_("challenge"), KL_("challenge")], "Apex Trader", STD, True, 6000, 10000)
pruef(d["n"] == 5 and d["pack"] == 5, "Apex: 2 laufen, erwartet 6k < 10k → 1 Pack = 5")
pruef(deckel(0, [], "Apex Trader", STD, True, 6000, 10000)["n"] == 5, "Apex: Lauf sagt 0 (25 %), erwartet < Ziel → trotzdem 1 Pack")
pruef(deckel(3, [], "Apex Trader", STD, True, 10500, 10000)["n"] == 0, "Apex: erwartet ≥ Ziel → 0")
pruef(deckel(3, [KL_("challenge", gelesen=False)], "Apex Trader", STD, True, 6000, 10000)["n"] == 0, "Apex: letztes Pack noch nicht gelesen → 0")
pruef(deckel(3, [], "Apex Trader", STD, True, 6000, 10000, frei=False)["n"] == 0, "Apex pausiert/gesperrt → 0")
pruef(deckel(3, [], "Apex Trader", STD)["n"] == 5, "Apex ohne erwartet/Ziel: Kaufzahl des Laufs > 0 → 1 Pack")
pruef(deckel(10, [], "Tradeify", STD)["pack"] is None, "andere Firmen: kein Pack")

# ── 2. kaufliste_app: Zeilen ──
stub = types.ModuleType("kapital_app")
stub._sb = lambda *a, **k: []
stub._gate = lambda: (None, None)
sys.modules["kapital_app"] = stub
sys.path.insert(0, WURZEL)
import kaufliste_app as KL  # noqa: E402

zellen = [
    {"user_id": "u1", "firma": "Tradeify", "status": "frei", "nachkauf": {"n": 3, "dringlichkeit": "jetzt", "einheit": "150k", "preis_eur": 213},
     "score": 90, "laufend_n": 1, "max_laufend": 4, "reserve": False},
    {"user_id": "u1", "firma": "FTMO", "status": "frei", "nachkauf": {"n": 0}},
    {"user_id": "u2", "firma": "Topstep", "status": "frei", "nachkauf": {"n": 2, "dringlichkeit": "bald"}, "score": 50, "reserve": True, "max_laufend": 3},
    {"user_id": "u2", "firma": "FTMO", "status": "frei", "nachkauf": {"n": 2, "dringlichkeit": "jetzt"}, "score": 99},
    {"user_id": "u2", "firma": "FundedNext Futures", "status": "frei", "nachkauf": {"n": 3}, "kauf_sperre": "ab 1. FN-Payout"},
    {"user_id": "u3", "firma": "FTMO", "status": "gesperrt", "nachkauf": {"n": 2}},
    {"user_id": "u3", "firma": "Apex Trader", "status": "frei", "nachkauf": {"n": None}},
]
z = KL.zeilen_aus_vorrat(zellen, None, {"u1": "Aurel", "u2": "Carsten"})
pruef([x["firma"] for x in z] == ["Tradeify", "Topstep"], "nur n > 0, frei, ohne Sperre, mit KP2-Deckel (max_laufend); jetzt vor bald")
pruef(z[0]["name"] == "Aurel" and z[0]["laufend"] == 1 and z[0]["max"] == 4 and z[0]["einheit"] == "150k", "Name + laufend/max + Einheit")
pruef(z[1]["reserve"] is True, "Reserve-Kennzeichen durchgereicht")
pruef([x["firma"] for x in KL.zeilen_aus_vorrat(zellen, "u2")] == ["Topstep"], "normale ID sieht nur eigene Zeilen")

pruef(not hasattr(KL, "row_pruefen") and "/admin/kaufliste/anlegen" not in open(os.path.join(WURZEL, "kaufliste_app.py"), encoding="utf-8").read(),
      "keine zweite Anlege-Route — fremde IDs über /admin/konto-anlegen")
fe = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
pruef("/admin/konto-anlegen?ansicht=admin" in fe and "bulkKlFremdAnlegen" in fe, "Frontend legt fremde IDs über /admin/konto-anlegen an (Verwalter: ansicht=admin)")

# ── 3. Finns Regel (KP2-Zusatz 25.11.2026): erreicht der ERWARTETE Stand (Bestand + Σ Chance × Ertrag) das Ziel, wird nicht nachgekauft ──
# Echte Lauf-Rechnung vorrat2_zelle (Standard-Kaufregel „sicherheit" 25 % mit 15 % Toleranz), geladen wie tools/selftest_vorrat_stufe2.py.
sys.path.insert(0, HIER)
import selftest_vorrat_stufe2 as VS2  # noqa: E402
ns2 = VS2.lade()
zelle = ns2["vorrat2_zelle"]
ZIEL_TR = {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 20000, "bis": 30000, "kauf_groesse": 150000,
           "kauf_stufe": "challenge", "kauf_einheit": "150k Select"}
wd11 = [{"account_id": "w", "typ": "winning_days", "groesse": 150000, "balance": 161000, "alter_tage": 0}]          # 11k in Winning Days
ch = lambda i: {"account_id": f"c{i}", "typ": "challenge", "groesse": 150000, "balance": 150000, "alter_tage": 0}
fu = lambda i: {"account_id": f"f{i}", "typ": "funded", "groesse": 150000, "balance": 150000, "alter_tage": 0}
# a) 11k + 4 frische Challenges: Erwartung der 4 klein (je Chance bis WD × 14.500) → erwartet < Ziel → Lauf will kaufen, Deckel 4/4 → 0
za = zelle(ZIEL_TR, VS2.TRADEIFY, wd11 + [ch(i) for i in range(4)], "frei", seed=7)
pruef(za["erwartet"] < 20000 * 0.85 and (za["nachkauf"]["n_roh"] or 0) > 0,
      f"Tradeify 11k WD + 4 frische Challenges: erwartet {round(za['erwartet'])} < 17k → Lauf will {za['nachkauf']['n_roh']} kaufen")
pruef(deckel(za["nachkauf"]["n_roh"], za["konten"], "Tradeify", STD)["n"] == 0, "… aber 4 von 4 laufen → Deckel 0")
# b) 11k + 3 Funded vor dem Big Trade (je 14.500 × 23,7 %): erwartet ≥ 20k → 0 kaufen, obwohl der Deckel Platz hätte (0 laufende Challenges)
zb = zelle(ZIEL_TR, VS2.TRADEIFY, wd11 + [fu(i) for i in range(3)], "frei", seed=7)
pruef(zb["erwartet"] >= 20000 and zb["nachkauf"]["n_roh"] == 0,
      f"Tradeify 11k WD + 3 Funded: erwartet {round(zb['erwartet'])} ≥ 20k → 0 kaufen")
pruef(deckel(10, zb["konten"], "Tradeify", STD)["n"] == 4, "… der Deckel allein hätte 4 erlaubt (Funded zählt nicht als laufend)")
# c) Toleranz: erwartet zwischen 85 % und 100 % des Ziels → ebenfalls 0 (strenger als Finns 100 %)
zc = zelle(ZIEL_TR, VS2.TRADEIFY, wd11 + [fu(i) for i in range(2)], "frei", seed=7)
pruef(17000 <= zc["erwartet"] < 20000 and zc["nachkauf"]["n_roh"] == 0,
      f"Tradeify 11k WD + 2 Funded: erwartet {round(zc['erwartet'])} (≥ 85 % von 20k) → 0 kaufen (Toleranz)")
print(f"\n{ok_n} Prüfungen grün (mit Lauf-Rechnung)")
