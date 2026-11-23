#!/usr/bin/env python3
"""Selbsttest MG3 (23.11.2026, Finn nach VF2/MG2: „Ja, dann pass es an.“): der CFD-Planer (Challenge-Planer ap_planen, alter Gruppen-Planer
gp_planen, Funded-CFD-Planer) deckelt die Lots auf 0,9 × freie Marge ÷ Marge je Lot. Die Marge je Lot lernt er JE KONTO aus dessen Vorprüfung
(„(Vorprüfung: nötig X, frei Y)“ ÷ Plan-Lots); ein Konto ohne eigenen Wert nimmt den höchsten Wert derselben Firma im SELBEN Unternehmen. TP/SL-$
bleiben, die Mengen-Wache dreht gedeckelte Pläne nie zurück. Ohne Lernwert: unverändert. Echte Funktionen per AST aus app.py (ohne Flask/DB).
Aufruf: python3 tools/selftest_mg3_lots_marge_deckel.py   Kennungen erfunden."""
import ast
import os
import re
import sys
from datetime import datetime, timedelta, timezone

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
try:
    compile(src, "app.py", "exec")
    syntax = True
except SyntaxError as e:
    syntax = False
    print(e)
check(syntax, "app.py übersetzt fehlerfrei")
baum = ast.parse(src)
NAMEN = {"_wd_num", "_ap_norm", "_ap_de", "_mg3_zahl", "mg3_marge_je_lot", "mg3_marge_tabelle", "mg3_marge_fuer", "mg3_lots_max", "mg3_deckel",
         "mg3_schritt", "mg3_ist_cfd", "mg3_marge_laden", "ap_menge_fix", "mg3_sicherung_zeilen",
         "_mg3_zeit", "mg3_frisch", "mg3_vergleich_art", "mg3_vergleich_groesse", "_wd_konto_groesse"}
KONST = {"_MG3_UUID", "MG3_MARGE_ANTEIL", "MG3_LERN_TAGE", "MG3_SETTINGS_KEY", "MG3_GRUND", "_MG3_RE", "AP_CFD_ROUTEN", "FCP_LOT_SCHRITT"}
teile = []
for n in baum.body:
    if isinstance(n, ast.FunctionDef) and n.name in NAMEN:
        teile.append(ast.get_source_segment(src, n))
    elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in KONST for t in n.targets):
        teile.append(ast.get_source_segment(src, n))
SB = {}


def _sb_all(table, params):
    SB.setdefault(table, []).append(params)
    if SB.get("fehler"):
        raise OSError("Netz weg")
    return SB.get("antwort_" + table, [])


POSTS = []


def _sb_anfrage(methode, url, **kw):
    POSTS.append((methode, url, kw.get("json"), (kw.get("headers") or {}).get("Prefer")))
    return "antwort"


ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "_firm_norm": lambda n: (n or "").strip(), "_sb_all": _sb_all,
      "_sb_anfrage": _sb_anfrage, "_sb_pruefen": lambda r: None, "_sb_headers": lambda prefer=None: {"Prefer": prefer}, "SUPABASE_URL": "https://x"}
exec(compile("\n\n".join(teile), "app_mg3", "exec"), ns)
check(all(k in ns for k in NAMEN | KONST), f"alle MG3-Teile in app.py gefunden ({sorted((NAMEN | KONST) - set(ns))})")

# ── Lernwert aus der Vorprüfung ─────────────────────────────────────────────────────────────────────────────────────────────────
J = ("Geclaimt vor 4 min, danach still — letzte Order-Antwort: Vorprüfung vor F9: zu wenig freie Marge für dieses Volumen (Vorprüfung: nötig "
     "108 140.09, frei 100 000.00) — Kontostand 100 000.00 — nichts gesendet. → Volumen senken oder Marge prüfen [0.0s·Hand: Tempo 1.29]")
ML = ns["mg3_marge_je_lot"]
check(abs(ML(J, "4.200") - 25747.64) < 0.01, f"Julian: 108.140,09 ÷ 4,2 Lots = 25.747,64 $/Lot ({ML(J, '4.200')})")
check(abs(ML(J.replace("108 140.09", "108 140.09"), 4.2) - 25747.64) < 0.01, "schmale/geschützte Leerzeichen in der Zahl")
check(ML("KEINE Bestaetigung — Grund: zu wenig freie Marge (API: nötig 5 000.00, frei 3 000.00)", 1.0) is None and ML(J, None) is None and ML(J, 0) is None
      and ML("", 1) is None, "API-Rechengrund nach dem Klick / ohne Lots / leer → kein Lernwert")
check(abs(ML("Vorprüfung vor F9: zu wenig freie Marge (Vorprüfung: nötig 30 000.00, frei -1 250.00) — nichts gesendet", 1.2) - 25000.0) < 0.01,
      "negatives „frei“ (Konto im Minus) → Lernwert trotzdem")

# ── Deckel ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
D = ns["mg3_deckel"]
mpl = ML(J, 4.2)
neu, txt = D(4.2, 100000.0, mpl, 0.1, "eigene Vorprüfung")
check(neu == 3.4 and txt and "Lots nach Marge gedeckelt: 4,2 → 3,4" in txt and "eigene Vorprüfung" in txt,
      f"Julians Fall: 4,2 Lots → 3,4 (0,9 × 100.000 ÷ 25.748 = 3,49, abgerundet) ({neu}, {txt})")
check(D(5.2, 100000.0, mpl, 0.1)[0] == 3.4 and D(3.4, 100000.0, mpl, 0.1) == (3.4, None) and D(1.5, 100000.0, mpl, 0.1) == (1.5, None),
      "5,2 → 3,4; schon unter dem Deckel → unverändert, kein Text")
check(D(4.2, 100000.0, None, 0.1) == (4.2, None) and D(4.2, None, mpl, 0.1) == (4.2, None), "ohne Lernwert / ohne Balance → unverändert (MG1 fängt es ab)")
check(D(4.2, 2000.0, mpl, 0.1)[0] == 0 and D(4.2, 2000.0, mpl, 0.1)[1], "Marge reicht für keinen Schritt → 0 + Text (Aufrufer plant nicht)")
check(D(1.37, 30000.0, 25747.64, 0.01)[0] == 1.04, "Funded-Schritt 0,01: 0,9 × 30.000 ÷ 25.748 = 1,0486 → 1,04 (nie aufgerundet)")

# ── Lernen je Konto, Rückfall nur im selben Unternehmen ────────────────────────────────────────────────────────────────────────
GR = {"u-g1": "G", "u-g2": "G", "u-ht1": "", "u-ht2": ""}
gv = lambda u: GR.get(u, "")   # noqa: E731
JETZT = datetime.now(timezone.utc)
iso = lambda **d: (JETZT - timedelta(**d)).isoformat().replace("+00:00", "Z")   # noqa: E731 — Zeiten relativ zu jetzt (Test altert nicht)
pl = [{"user_id": "u-g1", "master_account_id": "kA", "master_firm": "Blue Guardian", "master_contracts": "4.200",
       "start_fehler": {"msg": J, "at": iso(hours=1)}},
      {"user_id": "u-ht2", "master_account_id": "kE", "master_firm": "Blue Guardian", "master_contracts": "2.000",
       "mt5_baseline": {"start_fehler": {"msg": J.replace("108 140.09", "120 000.00"), "at": iso(days=3)}}}]
gs = [{"user_id": "u-g2", "value": {"kB": {"mpl": 25737.0, "firma": "Blue Guardian", "at": iso(minutes=30)},
                                    "kALT": {"mpl": 50000.0, "firma": "Blue Guardian", "at": iso(days=40)}}},
      {"user_id": "u-g1", "value": {"kA": {"mpl": 99999.0, "firma": "Blue Guardian", "at": iso(days=22)}}}]
P1 = {"account_type": "phase1", "account_size": "100000.00"}
KN = {"kA": P1, "kB": P1, "kE": dict(P1, account_size=None, starting_balance="100000.00"), "kALT": P1}
tab = ns["mg3_marge_tabelle"](pl, gs, gv, KN)
F = ns["mg3_marge_fuer"]
check(abs(F(tab, "kA", "u-g1", "Blue Guardian", gv)[0] - 25747.64) < 0.01 and F(tab, "kA", "u-g1", "Blue Guardian", gv)[1] == "eigene Vorprüfung",
      "eigenes Konto: jüngster Wert (Plan von heute schlägt Sicherung von vor 22 Tagen)")
check(F(tab, "kB", "u-g2", "Blue Guardian", gv)[0] == 25737.0, "Sicherung aus user_settings (gelöschter Plan) zählt je Konto")
check("kALT" not in tab["konto"] and F(tab, "kALT", "u-g2", "Blue Guardian", gv, art="phase1", groesse=100000)[0] != 50000.0,
      "MG3b: gesicherter Lernwert älter als 30 Tage → verworfen (auch nicht im Firmen-Rückfall)")
check(abs(F(tab, "kNEU", "u-g2", "Blue Guardian", gv, art="Phase1", groesse=100000.0)[0] - 25747.64) < 0.01
      and F(tab, "kNEU", "u-g2", "Blue Guardian", gv, art="phase1", groesse=100000)[1].startswith("Wert derselben Firma/Kontoart/Größe"),
      "Konto ohne eigenen Wert, gleiche Gruppe + Firma + Kontoart + Größe → höchster Wert dieser Konten")
check(F(tab, "kNEU", "u-g2", "Blue Guardian", gv, art="phase2", groesse=100000) == (None, "")
      and F(tab, "kNEU", "u-g2", "Blue Guardian", gv, art="phase1", groesse=50000) == (None, "")
      and F(tab, "kNEU", "u-g2", "Blue Guardian", gv) == (None, "") and F(tab, "kNEU", "u-g2", "Blue Guardian", gv, art="phase1") == (None, ""),
      "MG3b: andere Kontoart / andere Größe / Zielkonto ohne Kontoart oder Größe → kein Rückfall")
tab_ohne = ns["mg3_marge_tabelle"](pl, gs, gv, {"kA": {"account_type": "phase1"}})
check(tab_ohne["firma"] == {} and abs(F(tab_ohne, "kA", "u-g1", "Blue Guardian", gv)[0] - 25747.64) < 0.01,
      "MG3b: gelerntes Konto ohne bekannte Größe → nur sein eigener Wert, kein Rückfall für andere")
tab_g = ns["mg3_marge_tabelle"](pl[:1], gs, gv, KN)      # nur die Gruppe hat Werte
check(F(tab_g, "kC", "u-ht1", "Blue Guardian", gv, art="phase1", groesse=100000) == (None, "")
      and F(tab, "kC", "u-ht1", "Blue Guardian", gv, art="phase1", groesse=100000)[0] == 60000.0,
      "HT-Konto ohne eigenen Wert → nie der Wert der Gruppe (Unternehmen getrennt), nur ein HT-Wert gleicher Firma/Art/Größe (starting_balance als Größe)")
check(F(tab, "kE", "u-ht2", "Blue Guardian", gv)[0] == 60000.0 and D(4.2, 100000.0, 60000.0, 0.1)[0] == 1.5,
      "HT-Konto mit eigener Vorprüfung → nur sein eigener Wert")
check(F(tab, "kX", "u-g1", "FundedNext", gv, art="phase1", groesse=100000) == (None, ""), "andere Firma derselben Gruppe → kein Wert")
tab_n = ns["mg3_marge_tabelle"](pl[:1], [], gv, {"kA": {"account_type": "phase1", "name": "BG 100k 1234", "starting_balance": "150000"}})
check(list(tab_n["firma"]) == [("G", "blueguardian", "phase1", 100000)], "MG3b: Größe wie _wd_konto_groesse — „100k“ im Namen schlägt eine falsche starting_balance")
FR = ns["mg3_frisch"]
check(FR(iso(days=29), JETZT) and not FR(iso(days=31), JETZT) and not FR("x", JETZT) and not FR(None, JETZT) and FR("2026-11-23T00:00:08.933Z", datetime(2026, 11, 24, tzinfo=timezone.utc)),
      "mg3_frisch: 30 Tage wie die Pläne, unlesbare Zeit → verworfen, „…Z“ mit Millisekunden lesbar")

# ── Laden: Fehler → leer, Filter auf die IDs ───────────────────────────────────────────────────────────────────────────────────
L = ns["mg3_marge_laden"]
SB.clear()
POSTS.clear()
SB["antwort_trade_plans"], SB["antwort_user_settings"] = pl[:1], gs[:1]
SB["antwort_accounts"] = [dict(P1, id="kA"), dict(P1, id="kB")]
_uuid_echt = ns["_MG3_UUID"]
check(_uuid_echt.match("766ada29-edb9-4ae6-9b11-5c37917f0f2e") and not _uuid_echt.match("kA") and not _uuid_echt.match("x); drop"),
      "MG3b: nur gültige Konto-UUIDs gehen in die accounts-Abfrage")
ns["_MG3_UUID"] = re.compile(r"^k")                    # Test-Kennungen kA/kB zulassen
t2 = L(["u-g1", "u-g2"], gv)
ns["_MG3_UUID"] = _uuid_echt
q = SB["trade_plans"][0]
check(SB["accounts"][0]["id"] == "in.(kA,kB)" and "account_type" in SB["accounts"][0]["select"] and "name" in SB["accounts"][0]["select"]
      and t2["firma"].get(("G", "blueguardian", "phase1", 100000)) == 25747.64,
      f"MG3b Laden: nur frische Lernwerte abfragen (kALT abgelaufen), Kontoart/Größe aus accounts → Rückfall-Schlüssel ({t2['firma']})")
check(len(POSTS) == 1 and POSTS[0][1].endswith("/rest/v1/user_settings?on_conflict=user_id,key") and "merge-duplicates" in POSTS[0][3]
      and POSTS[0][2][0]["user_id"] == "u-g1" and set(POSTS[0][2][0]["value"]) == {"kA"} and POSTS[0][2][0]["value"]["kA"]["mpl"] == 25747.64,
      f"Laden sichert einen Lernwert, der nur am Plan hängt, sofort in user_settings (Nachtlauf/„Plan löschen“ nehmen ihn sonst mit) ({POSTS})")
check(set(t2["konto"]) == {"kA", "kB"} and q["user_id"] == "in.(u-g1,u-g2)" and "Vorprüfung: nötig" in q["mt5_baseline->start_fehler->>msg"]
      and SB["user_settings"][0]["key"] == "eq.marge_je_lot", "Laden: nur diese IDs, nur Vorprüfungs-Meldungen, dazu die Sicherung")
Z = ns["mg3_sicherung_zeilen"]
gs_neu = [{"user_id": "u-g1", "value": {"kA": {"mpl": 25747.64, "firma": "Blue Guardian", "at": iso(hours=1)}, "kZ": {"mpl": 1.0, "at": iso(days=2)}}}]
check(Z(ns["mg3_marge_tabelle"](pl[:1], gs_neu), gs_neu) == [], "schon gesichert (gleicher Wert, gleich alt) → nichts schreiben")
gs_z = [{"user_id": "u-g1", "value": {"kZ": {"mpl": 1.0, "at": iso(days=2)}, "kOLD": {"mpl": 2.0, "at": iso(days=45)}}}]
z1 = Z(ns["mg3_marge_tabelle"](pl[:1], gs_z), gs_z)
check(len(z1) == 1 and set(z1[0]["value"]) == {"kA", "kZ"} and z1[0]["key"] == "marge_je_lot",
      "neuer Wert → vollständiger Wert der ID (frische Konten bleiben, abgelaufene fallen heraus — MG3b)")
SB.clear()
SB["fehler"] = True
check(L(["u-g1"]) == {"konto": {}, "firma": {}}, "Lesefehler → leer (kein Deckel, wie vor MG3)")
check(L([]) == {"konto": {}, "firma": {}}, "ohne IDs → leer, keine Abfrage")

# ── Schritt/CFD ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
S = ns["mg3_schritt"]
check(S({"phasen": {"phase1": {"menge_schritt": 0.1}}}, "phase1", 100000) == 0.1
      and S({"phasen": {"phase1": {"menge_schritt": 0.1}}, "je_groesse": {"50000": {"phasen": {"phase1": {"menge_schritt": 0.05}}}}}, "phase1", 50000) == 0.05
      and S({}, "phase1", 100000) == 1.0, "Lot-Schritt wie ap_konto_rechnen (je_groesse vor Firma, ohne Angabe 1 wie dort)")
C = ns["mg3_ist_cfd"]
check(C({"route": "mt5v2"}, "phase1") and C({}, "funded") and not C({"route": "tvv2"}, "challenge") and not C({"route": "mt5v2"}, "challenge"),
      "nur CFD (Echo mt5v2/mt5), nie Futures-Challenges")

# ── Mengen-Wache dreht gedeckelte Pläne nie zurück ───────────────────────────────────────────────────────────────────────────────
ns["ap_konto_rechnen"] = lambda *a, **k: (_ for _ in ()).throw(AssertionError("darf nicht rechnen"))
p_, g_ = ns["ap_menge_fix"]({"master_contracts": "3.4", "notes": "Auto-Planer · Etappe · " + txt}, {}, "phase1", 100000.0)
check(p_ is None and "MG3" in g_, "ap_menge_fix: Plan mit „Lots nach Marge gedeckelt“ → kein Patch auf die Regel-Spanne")

# ── Verdrahtung ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
apl = src[src.index("def ap_planen("):src.index("def ap_gruppe_ausgeblendet(") if "def ap_gruppe_ausgeblendet(" in src else None]
i_rv, i_mg, i_tt = apl.index("w = rv_tp_frei(w, tps_tranche"), apl.index("mg3_deckel(w.get(\"menge\"), k[\"bal\"]"), apl.index("_tt_p = tt_param(")
check(i_rv < i_mg < i_tt and "_mg3_tab = mg3_marge_laden(uids)" in apl and apl.index("_mg3_tab = mg3_marge_laden(uids)") < apl.index("for key, liste in tranchen.items():"),
      "ap_planen: Lernwerte einmal je Lauf, Deckel nach Würfel/RV und vor Trades pro Tag")
check("\"master_contracts\": w[\"menge\"]" in apl and "ap_notiz(w[\"stufe\"]" in apl, "ap_planen: Plan-Lots und Notiz (Grund) kommen aus w")
gpl = src[src.index("def gp_planen("):src.index("def gp_push_ereignisse(")]
check("_mg3_tab = mg3_marge_laden(uids)" in gpl and gpl.index("mg3_deckel(w.get(\"menge\"), float(bal)") < gpl.index("h, grund = gp_hedge(gp_dd(a, regel_k"),
      "gp_planen: Deckel vor dem Hedge (gp_hedge rechnet mit den gedeckelten Lots)")
fkr = src[src.index("def fcp_konto_rechnen("):src.index("def fcp_richtung(")]
check("marge_lot=None" in fkr and fkr.index("mg3_deckel(lots, balance") < fkr.index("h, grund = gp_hedge(dd,") and "tp_pkt=round(tp / (mppl * lots)" in fkr,
      "fcp_konto_rechnen: Deckel vor Hedge und Punkten, TP/SL-$ unverändert")
tth = src[src.index("def tt_planer_haken("):src.index("def tt_planer_haken(") + 6000]
check("k[\"mg3_max\"] = w[\"mg3_max\"]" in tth, "Trades pro Tag: der Deckel reist in der Kette mit (kette.mg3_max)")
ttf = src[src.index("w_h = rv_anwenden(w_h, k[\"range\"]"):]
ttf = ttf[:ttf.index("werte, g = tt_folge_rechnen(")]
check("_mg3m = _wd_num(k.get(\"mg3_max\"))" in ttf and "menge=int(_mg3m) if float(_mg3m).is_integer() else _mg3m" in ttf,
      "Folge-Haupt-Teil: neu gerechnete Lots auf kette.mg3_max gedeckelt, nach RV, vor tt_folge_rechnen (Prüfer-Befund)")
check("k2[\"mg3_max\"] = k[\"mg3_max\"]" in src[src.index("def _tt_zeile("):src.index("def _tt_zeile(") + 3000], "_tt_zeile: mg3_max geht an den nächsten Teil weiter")
check("w = dict(w, mg3_max=mg3_lots_max(k[\"bal\"], _mpl, _sch))" in apl, "ap_planen: mg3_max auch ohne Deckel heute am Beleg (späterer Haupt-Teil könnte größer würfeln)")
check("art=k[\"a\"].get(\"account_type\"), groesse=w.get(\"groesse\"))" in apl
      and "art=a.get(\"account_type\"), groesse=w.get(\"groesse\"))" in gpl
      and "art=a.get(\"account_type\"), groesse=g))" in src[src.index("def fcp_planen("):],
      "MG3b: alle drei Planer geben Kontoart + Größe des Zielkontos an mg3_marge_fuer")
fpl = src[src.index("def fcp_planen("):]
check("marge_lot=mg3_marge_fuer(_mg3_tab, aid, uid, a.get(\"firm\"), _mg3_gv, art=" in fpl and "_mg3_tab = mg3_marge_laden(uids, _mg3_gv)" in fpl
      and "f\" · {r['marge_deckel']}\" if r.get(\"marge_deckel\")" in fpl, "fcp_planen: Lernwerte je Unternehmen, Grund in der Notiz")
print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
