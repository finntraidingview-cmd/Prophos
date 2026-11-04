#!/usr/bin/env python3
"""Selbsttest EINSTELLUNGEN CHALLENGE-PLANER (04.11.2026, Auftrag E3): GET /admin/auto-plan/einstellungen (nur lesen) und POST
/admin/auto-plan/kernwert (nur vorhandene Felder, gleicher Typ, Grenzen, Admin). app.py importiert, DB ersetzt. Ohne Netz.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_einstellungen_challenge.py"""
import json
import os
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


FIRMEN = [
    {"namen": ["the5ers"], "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [100000, 200000], "kauf_eur": {"100000": 146, "200000": 226},
     "ziel_pct": {"phase1": 8, "phase2": 5}, "skaliert": True,
     "phasen": {"phase1": {"sl": [1800, 2160], "tp": [5400, 6300], "menge": [20, 30], "ziel_pct": 8, "menge_schritt": 1}},
     "je_groesse": {"200000": {"phasen": {"phase1": {"tp": [10800, 12600], "menge": [50, 60]}}}}},
    {"namen": ["topstep"], "route": "tsv2", "dd_usd": 4500, "planen": True, "kauf_eur": 237, "tp_max": 4500,
     "kette": {"t1_bis": "11:00", "t1_sl": [1250, 1750], "tagesziel_usd": 4500}, "phasen": {"challenge": {"sl": None, "tp": [4350, 4450]}}},
]
REG = {"id": 1, "aktiv": True, "updated_at": "2026-11-02T00:15:55+00:00",
       "zeiten": {"nachtlauf": {"tz": "Asia/Dubai", "uhr": "01:30"}, "cfd_ab": {"tz": "Asia/Dubai", "uhr": "02:15"}},
       "regeln": {"firmen": FIRMEN, "auto_bestaetigen": "cfd", "echo_hedge": {"an": True}, "apex_hedge": {"an": True},
                  "tradeify_final_hedge": {"an": False}, "ausgleich": {"aktiv": True, "takt_min": 3}}}

print("1) ap_einst_wert / ap_einst_anwenden (rein rechnend)")
W = app.ap_einst_wert
check(W(146, 150, "kauf_eur") == (150, None) and isinstance(W(146, 150, "kauf_eur")[0], int), "Zahl: ganze Zahl bleibt ganz")
check(W(0.1, 0.05, "menge_schritt") == (0.05, None), "Lot-Schritt 0,05")
check(W([5400, 6300], [5000, 6000], "tp") == ([5000, 6000], None), "Spanne [von, bis]")
check(W([5400, 6300], [7000, 6000], "tp")[0] is None, "von > bis → nie")
check(W([5400, 6300], 6000, "tp")[0] is None and W(146, [1, 2], "kauf_eur")[0] is None, "anderer Typ (Zahl ↔ Spanne) → nie")
check(W(8, 80, "ziel_pct")[0] is None and W(8, -1, "ziel_pct")[0] is None, "Ziel % außerhalb 0,1–50 → nie")
check(W(None, 5, "sl")[0] is None, "bisher null (kein SL) → nicht änderbar")
check(W(True, False, "planen") == (False, None) and W(True, 0, "planen")[0] is None, "Schalter nur true/false")
check(W("statisch", "nachziehend", "boden")[0] is None and W(1, 2, "irgendwas")[0] is None, "unbekanntes Feld → nie")
check(W(146, True, "kauf_eur")[0] is None, "true ist keine Zahl")
A = app.ap_einst_anwenden
neu, g = A(FIRMEN, "the5ers", [{"pfad": ["je_groesse", "200000", "phasen", "phase1", "tp"], "wert": [11000, 12000]}])
check(g is None and neu[0]["je_groesse"]["200000"]["phasen"]["phase1"]["tp"] == [11000, 12000] and FIRMEN[0]["je_groesse"]["200000"]["phasen"]["phase1"]["tp"] == [10800, 12600],
      "tiefer Pfad je Größe geändert, Original unberührt")
neu, g = A(FIRMEN, "the5ers", [{"pfad": ["kauf_eur", "200000"], "wert": 230}, {"pfad": ["phasen", "phase1", "tp"], "wert": [1, "x"]}])
check(neu is None and "phase1/tp" in g, f"alles oder nichts: ein Fehler → nichts geändert ({g})")
check(A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase2", "tp"], "wert": [1, 2]}])[0] is None, "Pfad, den es nicht gibt → nie (keine neuen Schlüssel)")
check(A(FIRMEN, "the5ers", [{"pfad": ["route"], "wert": "tvv2"}])[0] is None and A(FIRMEN, "the5ers", [{"pfad": ["namen"], "wert": ["x"]}])[0] is None,
      "route / namen nie änderbar")
check(A(FIRMEN, "ftmo", [{"pfad": ["kauf_eur"], "wert": 1}])[0] is None, "unbekannte Firma → nie")
check(A(FIRMEN, "topstep", [{"pfad": ["kette", "t1_sl"], "wert": [1300, 1700]}])[0][1]["kette"]["t1_sl"] == [1300, 1700], "Topstep-Kette änderbar")
check(A(FIRMEN, "topstep", [{"pfad": ["kette", "t1_bis"], "wert": "10:30"}])[0][1]["kette"]["t1_bis"] == "10:30", "E3b: Uhrzeit der Kette änderbar (HH:MM)")
check(A(FIRMEN, "topstep", [{"pfad": ["kette", "t1_bis"], "wert": "25:00"}])[0] is None and A(FIRMEN, "topstep", [{"pfad": ["kette", "t1_bis"], "wert": 11}])[0] is None,
      "E3b: Kette-Uhrzeit nur gültiges HH:MM")
neu, g = A(FIRMEN, "the5ers", [{"pfad": ["ziel_pct", "phase1"], "wert": 9}])
check(g is None and neu[0]["ziel_pct"]["phase1"] == 9, f"Ziel % je Phase (Zuordnung) speicherbar — S6-Review Befund 1 ({g})")
check(A(FIRMEN, "the5ers", [{"pfad": ["ziel_pct", "phase1"], "wert": 80}])[0] is None, "Ziel % je Phase mit Grenze 0,1–50")
check(A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase1", "menge"], "wert": [20.5, 30]}])[0] is None
      and A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase1", "menge"], "wert": [21, 31]}])[1] is None, "ganze Lots/Kontrakte bleiben ganz (20,5 nie, 21 ja)")
check(A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase1", "menge_schritt"], "wert": 0.5}])[0] is None, "Schritt 1 bleibt ganz")
check(W([2.1, 3.2], [2.2, 3.3], "menge")[1] is None, "Kommazahlen-Lots (CFD) bleiben frei")
check(W([5400, 6300], [0, 6300], "tp")[0] is None and W(4500, 0, "dd_usd")[0] is None, "TP / Drawdown nie 0")
check(A(FIRMEN, "the5ers", [])[0] is None and A(FIRMEN, "the5ers", [{"pfad": "kauf_eur", "wert": 1}])[0] is None, "leere Liste / Pfad kein Array → nie")

FIRMEN[1]["kette"].update({"t2_ab": "11:00", "t2_bis": "19:30"})
check(A(FIRMEN, "topstep", [{"pfad": ["kette", "t1_bis"], "wert": "20:00"}])[0] is None, "E3b: Kette Trade 1 bis ≤ Trade 2 ab < Trade 2 bis")
FIRMEN[1]["phasen"]["challenge"]["puffer_je_menge"] = {"1": [10, 15], "2": [15, 25]}
FIRMEN[1]["phasen"]["challenge"]["menge_gewichte"] = {"1": 20, "2": 80}
neu, g = A(FIRMEN, "topstep", [{"pfad": ["phasen", "challenge", "puffer_je_menge", "2"], "wert": [16, 26]},
                                {"pfad": ["phasen", "challenge", "menge_gewichte", "1"], "wert": 30}])
check(g is None and neu[1]["phasen"]["challenge"]["puffer_je_menge"]["2"] == [16, 26] and neu[1]["phasen"]["challenge"]["menge_gewichte"]["1"] == 30,
      f"E3b: Puffer je Kontrakt-Zahl und Gewichte änderbar ({g})")
check(A(FIRMEN, "topstep", [{"pfad": ["phasen", "challenge", "menge_gewichte", "1"], "wert": 130}])[0] is None, "E3b: Gewicht höchstens 100")

print("1b) Zeiten / Zufall / Bestätigen (E3b)")
Z = app.ap_einst_zeiten_anwenden
ZT = REG["zeiten"] | {"fenster": [["02:00", "20:00", 100]], "start_bis": "20:00", "abstand_id_min": 3, "abstand_konto_s": [60, 120], "pause_firma_min": [25, 45],
                      "cfd_bis": {"tz": "Asia/Dubai", "uhr": "18:00"}}
neu, g = Z(ZT, [{"pfad": ["nachtlauf", "uhr"], "wert": "1:45"}, {"pfad": ["fenster", "0", "1"], "wert": "19:00"}, {"pfad": ["abstand_konto_s"], "wert": [45, 90]}])
check(g is None and neu["nachtlauf"] == {"tz": "Asia/Dubai", "uhr": "01:45"} and neu["fenster"][0] == ["02:00", "19:00", 100] and neu["abstand_konto_s"] == [45, 90]
      and ZT["fenster"][0][1] == "20:00", f"Uhr, Fenster-Ende, Spanne geändert, Original unberührt ({g})")
check(Z(ZT, [{"pfad": ["fenster", "0", "0"], "wert": "21:00"}])[0] is None, "Fenster von < bis")
check(Z(ZT, [{"pfad": ["cfd_ab", "uhr"], "wert": "18:30"}])[0] is None, "CFD ab < CFD bis")
check(Z(ZT, [{"pfad": ["tz"], "wert": "x"}])[0] is None and Z(ZT, [{"pfad": ["fenster", "3", "0"], "wert": "03:00"}])[0] is None, "andere Pfade / fehlendes Fenster → nie")
check(Z(ZT, [{"pfad": ["abstand_konto_s"], "wert": [120, 60]}])[0] is None and Z(ZT, [{"pfad": ["abstand_id_min"], "wert": 99}])[0] is None, "Spanne von ≤ bis, Grenzen")
check(Z(ZT, [{"pfad": ["abstand_id_min"], "wert": 0}])[0] is None and Z(ZT, [{"pfad": ["pause_firma_min"], "wert": [20, 40]}])[0] is None,
      "Review: Abstand je ID ab 1 (Leser: or 3), Pause je Firma (liest keiner) nicht änderbar")
neu, g = Z(dict(ZT, cfd_ab="00:20"), [{"pfad": ["cfd_ab", "uhr"], "wert": "00:30"}])
check(g is None and neu["cfd_ab"] == "00:30", "Review: alte Text-Form cfd_ab über [cfd_ab, uhr] bleibt Text")
check(Z(dict(ZT, abstand_konto_s=5), [{"pfad": ["abstand_konto_s"], "wert": [1, 2]}])[0] is None, "Review: Spanne auf Nicht-Liste → 400 statt 500")
neu, g = Z(ZT, [{"pfad": ["neu_bis", "uhr"], "wert": "15:00"}])
check(g is None and neu["neu_bis"] == {"tz": "Asia/Dubai", "uhr": "15:00"}, "Neue Konten bis: legt neu_bis mit Dubai an")
R = app.ap_einst_regeln_anwenden
neu, g = R(REG["regeln"], {"paar_intern_min": [3, 20], "fenster_wuerfe": 10}, "aus")
check(g is None and neu["zufall"] == {"paar_intern_min": [3, 20], "fenster_wuerfe": 10} and neu["auto_bestaetigen"] is False and REG["regeln"].get("zufall") is None,
      f"Zufall angelegt, Bestätigen aus, Original unberührt ({g})")
check(R(REG["regeln"], {"fenster_wuerfe": 2.5})[0] is None and R(REG["regeln"], {"paar_intern_min": [30, 2]})[0] is None and R(REG["regeln"], {"x": 1})[0] is None,
      "Zufall: ganze Würfe, von ≤ bis, nur bekannte Schlüssel")
check(R(REG["regeln"], None, "vielleicht")[0] is None and R(REG["regeln"], None, "alle")[0]["auto_bestaetigen"] is True, "Bestätigen nur aus | cfd | alle")
neu, g = R(REG["regeln"], bloecke={"echo_hedge": {"vorlauf_min": 25, "max_lots": 80}, "ausgleich": {"takt_min": 5, "waage_max_abstand": 3}},
          schalter=[{"pfad": ["abhaken_auto_normal"], "wert": True}, {"pfad": ["ausgleich", "waage_deckel_an"], "wert": False}])
check(g is None and neu["echo_hedge"] == {"an": True, "vorlauf_min": 25, "max_lots": 80} and neu["ausgleich"]["takt_min"] == 5 and neu["ausgleich"]["waage_max_abstand"] == 3
      and neu["ausgleich"]["aktiv"] is True and neu["abhaken_auto_normal"] is True and neu["ausgleich"]["waage_deckel_an"] is False and REG["regeln"]["echo_hedge"] == {"an": True},
      f"Nachtrag 2: Hedge-/Ausgleich-Zahlen und Regel-Schalter, Rest bleibt ({g})")
check(R(REG["regeln"], bloecke={"echo_hedge": {"an": False}})[0] is None and R(REG["regeln"], bloecke={"ausgleich": {"takt_min": 2.5}})[0] is None
      and R(REG["regeln"], bloecke={"echo_hedge": {"vorlauf_min": 999}})[0] is None and R(REG["regeln"], bloecke={"firmen": {"x": 1}})[0] is None,
      "Blöcke: kein an/aus (bleibt /ausgleich-einstellung), ganze Takte, Grenzen, nur bekannte Blöcke")
check(R(REG["regeln"], bloecke={"echo_hedge": {"netto_faktor": 1.2}})[0] is None and R(REG["regeln"], bloecke={"echo_hedge": {"vorlauf_min": 2}})[0] is None
      and R(REG["regeln"], bloecke={"apex_hedge": {"nachlauf_min": 90}})[0] is None and R(REG["regeln"], bloecke={"echo_hedge": {"min_lot": 2}})[0] is None,
      "Review: Hedge-Grenzen wie eh_param/ah_param (Netto 0,5–1, Vorlauf ≥ 3, Nachlauf ≤ 60, Mindest-Lot ≤ 1)")
check(R(REG["regeln"], {"paar_intern_min": [2, 45]})[0] is None and R(REG["regeln"], {"paar_rs_min": 20})[0] is None and R(REG["regeln"], {"paar_pc_min": 2})[0] is None
      and R(REG["regeln"], {"gegen_wuerfe": 40})[0] is None, "Review: Zufall-Grenzen wie die Start-Wächter (Paar ≤ 30, RS ≥ 30, PC ≥ 3), Würfe ≤ 30")
check(R(REG["regeln"], schalter=[{"pfad": ["aktiv"], "wert": False}])[0] is None and R(REG["regeln"], schalter=[{"pfad": ["abhaken_auto_blow"], "wert": 1}])[0] is None,
      "Regel-Schalter: nur die Liste, nur true/false")
check(app.ap_einst_fest()["beide"]["nachplan_takt_min"] == app.AP_NACHPLAN_TAKT_S / 60, "Nachplan-Takt im Fest-Block")
zf = app.ap_zufall({"zufall": {"paar_intern_min": [3, 20], "fenster_wuerfe": 2.5, "x": 1}})
check(zf["paar_intern_min"] == [3, 20] and zf["fenster_wuerfe"] == app.AP_FENSTER_WUERFE and "x" not in zf, "ap_zufall: gültiges gilt, Ungültiges fällt auf den Code zurück")
check(app.ap_zeiten_mit_zufall({"zeiten": {"a": 1}, "regeln": {}}) == {"a": 1, "_zufall": app.ap_zufall_code()}, "ap_zeiten_mit_zufall: Kopie + _zufall")

print("1c) Gleiche Werte → gleiche Pläne (Code-Werte = SQL-Werte = ohne regeln.zufall)")
import random  # noqa: E402
SQL = {"paar_extern_min": [2, 5], "paar_intern_min": [2, 30], "paar_pc_min": 3, "paar_rs_min": 30, "verteil_jitter_min": 8, "fenster_wuerfe": 20, "gegen_wuerfe": 16}
check(app.ap_zufall({"zufall": SQL}) == app.ap_zufall_code() and set(SQL) == set(app.AP_ZUFALL_FELDER), "SQL-Datei trägt genau die Code-Werte ein")
sql_txt = open(os.path.join(os.path.dirname(HIER), "sql", "2026-11-05_ap_zufall_parameter.sql"), encoding="utf-8").read()
import re  # noqa: E402
sql_json = json.loads(re.search(r"'(\{\"paar_extern_min\".*?\})'::jsonb", sql_txt, re.S).group(1))
check(sql_json == SQL, f"SQL-Datei: dieselben Zahlen wie im Test ({sql_json})")
TI = lambda u, fk="tradeify": {"user": u, "fkey": fk, "route": "tvv2"}   # noqa: E731
tr = {"k1": TI("mike"), "k2": TI("marc"), "k3": TI("moritz", "topstep"), "k4": TI("aurel"), "k5": TI("ina", "lucidtrading"), "k6": TI("chris")}
mi = {"k1": 316.0, "k2": 325.0, "k3": 362.0, "k4": 455.0, "k5": 500.0, "k6": 610.0}
ri = {"k1": "sell", "k2": "sell", "k3": "buy", "k4": "buy", "k5": "sell", "k6": "buy"}
fest = [{"user_id": "jacob", "firma": "tradeify", "richtung": "buy", "start": 300.0, "route": "tvv2"}]
gleich = True
for seed in range(25):
    a = app.ap_paare_legen(mi, ri, tr, [], fest, random.Random(seed), ohne=("apex",))
    b = app.ap_paare_legen(mi, ri, tr, [], fest, random.Random(seed), ohne=("apex",), zufall=app.ap_zufall({}))
    c = app.ap_paare_legen(mi, ri, tr, [], fest, random.Random(seed), ohne=("apex",), zufall=app.ap_zufall({"zufall": SQL}))
    gleich = gleich and a == b == c
check(gleich, "ap_paare_legen: 25 Seeds — ohne / Code / SQL-Werte identisch")
eng = app.ap_paare_legen(mi, ri, tr, [], fest, random.Random(3), ohne=("apex",), zufall=app.ap_zufall({"zufall": {"paar_intern_min": [10, 12], "paar_extern_min": [10, 12]}}))
check(eng[1] and all(10.0 <= i["nach"] - i["anker"] <= 12.0 for i in eng[1]), f"geänderter Wert wirkt: Paare 10–12 min ({[(i['art'], round(i['nach'] - i['anker'], 1)) for i in eng[1]]})")
MIXV = [("u1", "FundingPips"), ("u1", "The5%ers"), ("u2", "Tradeify"), ("u2", "Tradeify"), ("u3", "FundedNext"), ("u3", "FTMO"), ("u4", "Apex Trader"), ("u4", "Topstep")] * 3
ZV = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3, "cfd_ab": "00:20"}
def tranchen():
    n = {}
    out = []
    for u, f in MIXV:
        i = n[(u, f)] = n.get((u, f), -1) + 1
        out.append({"key": f"{u}|{f}#{i}", "user": u, "gruppe": f"{u}|{f}", "fkey": f, "dauer_min": 2, "ab_min": 0})
    return out
gleich = True
for seed in range(10):
    a = app.ap_zeiten_verteilen(tranchen(), ZV, random.Random(seed))
    b = app.ap_zeiten_verteilen(tranchen(), dict(ZV, _zufall=app.ap_zufall({"zufall": SQL})), random.Random(seed))
    gleich = gleich and a == b and len(a) == len(MIXV)
check(gleich, "ap_zeiten_verteilen: 10 Seeds — ohne / SQL-Werte identisch")
w1 = app.ap_zeiten_verteilen(tranchen(), dict(ZV, _zufall={"fenster_wuerfe": 1}), random.Random(4))
check(len(w1) == len(MIXV), "Würfe = 1 läuft (ein Wurf)")

print("1d) Zusatz 4: Firma an/aus, Kontoliste (Ziel + Consistency)")
neu, g = A(FIRMEN, "the5ers", [{"pfad": ["planen"], "wert": False}])
check(g is None and neu[0]["planen"] is False and "planen" not in FIRMEN[0], f"Firma an/aus legt planen an, wenn es fehlt ({g})")
check(A(FIRMEN, "the5ers", [{"pfad": ["planen"], "wert": "nein"}])[0] is None, "planen nur true/false")
TS = {"namen": ["tradeify"], "route": "tvv2", "groessen": [150000], "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"tp": [3450, 3550], "tp_max": 3600, "ziel_pct": 6}}}
K = {"id": "k", "account_type": "challenge", "firm": "Tradeify", "consistency_pct": None}
z = app.ap_konten_stand_zeile(K, TS, 153000.0, {"2026-11-01": 1500.0, "2026-11-02": 3420.0, "2026-11-03": -200.0})
check(z["groesse"] == 150000 and z["ziel"] == 159000 and z["ziel_usd"] == 9000 and z["gewinn"] == 3000 and abs(z["fortschritt"] - 0.3333) < 1e-3,
      f"Ziel 159.000, Gewinn 3.000 → 33 % ({z})")
check(z["cons_pct"] == 40.0 and z["cons_quelle"] == "firma" and z["groesster_tag"] == 3420.0 and abs(z["cons_anteil"] - 0.38) < 1e-3,
      "Consistency aus dem Firmen-Deckel 3.600 ÷ 9.000 = 40 %, größter Tag 3.420 = 38 %")
z5 = app.ap_konten_stand_zeile(dict(K, consistency_pct=50), TS, 153000.0, {})
check(z5["cons_pct"] == 50.0 and z5["cons_quelle"] == "konto" and z5["groesster_tag"] is None, "Konto-Wert 50 % geht vor (ap_regel_konto), ohne Tage kein Balken")
FNF = {"namen": ["fundednextfutures"], "route": "tvv2", "groessen": [50000, 150000], "ziel_pct": {"challenge": 5.3333}, "phasen": {"challenge": {"tp_max": 3200}},
       "je_groesse": {"50000": {"ziel_pct": {"challenge": 5}, "phasen": {"challenge": {"tp_max": 1000}}}}}
zj = app.ap_konten_stand_zeile(dict(K, consistency_pct=50), FNF, 51000.0, {})
check(zj["cons_pct"] == 40.0 and zj["cons_quelle"] == "firma" and zj["cons_waehlbar"] is False,
      f"Review: Größe mit eigenen Phasen — Konto-Wert greift nicht (ap_konto_rechnen), Anzeige 40 % aus dem Größen-Block, nicht wählbar ({zj['cons_pct']})")
check(z["cons_waehlbar"] is True and z["cons_firma"] == 40.0, "Tradeify Standard: wählbar, Firmen-Wert 40 %")
check(app.ap_konten_stand_zeile(K, TS, None, {})["ziel"] is None and app.ap_konten_stand_zeile(K, None, 153000.0, {})["ziel"] is None, "ohne Balance/Regel: nur Bekanntes")
zc = app.ap_konten_stand_zeile(dict(K, account_type="phase1", firm="The5ers"), FIRMEN[0], 101000.0, {"x": 500.0})
check(zc["ziel"] == 108000 and zc["cons_pct"] is None, "CFD ohne tp_max: keine Consistency")

# Größter Tag = Berlin-Tag des Trade-Endes (Prüfer E3c): 23:15 UTC und 23:30 UTC am 04.11. sind beide der 05.11. in Berlin → ein Tag
_alt = (app._ap_konten_laden, app._ap_archiviert_gemerkt, app._ap_balance_karten, app._ap_namen, app._sb_all)
app._ap_konten_laden = lambda p: [{"id": "kb", "user_id": "u1", "firm": "Tradeify", "account_type": "challenge", "tv_balance": 153000, "tv_balance_at": "2026-11-05T08:00:00+00:00"}]
app._ap_archiviert_gemerkt = lambda: set(); app._ap_balance_karten = lambda: ({}, {}); app._ap_namen = lambda: ({"u1": "ID 1"}, set())
app._sb_all = lambda t, p: [{"master_account_id": "kb", "status": "completed", "started_at": "2026-11-04T20:00:00+00:00", "ended_at": "2026-11-04T23:15:00+00:00", "master_pl": 1500},
                            {"master_account_id": "kb", "status": "completed", "started_at": "2026-11-04T21:00:00+00:00", "ended_at": "2026-11-04T23:30:00+00:00", "master_pl": 1200},
                            {"master_account_id": "kb", "status": "completed", "started_at": "2026-11-03T10:00:00+00:00", "ended_at": "2026-11-03T11:00:00+00:00", "master_pl": 2000}] if t == "trade_plans" else []
ks = app.ap_konten_stand({"user_ids": ["u1"], "regeln": {"firmen": [TS]}})
check(len(ks) == 1 and ks[0]["groesster_tag"] == 2700.0 and ks[0]["user_id"] == "u1", f"größter Tag als Berlin-Tag des Endes: 1.500 + 1.200 am 05.11. ({ks[0]['groesster_tag'] if ks else None})")
app._ap_konten_laden, app._ap_archiviert_gemerkt, app._ap_balance_karten, app._ap_namen, app._sb_all = _alt

print("2) GET /admin/auto-plan/einstellungen")
app._ap_zugang = lambda admin_reiter=False: (True, "u", json.loads(json.dumps(REG)), None)
c = app.app.test_client()
r = c.get("/admin/auto-plan/einstellungen")
d = r.get_json()
check(r.status_code == 200 and d["ok"] and d["admin"] is True and len(d["firmen"]) == 2, "Antwort mit Firmen")
check(d["zeiten"]["nachtlauf"] == {"uhr": "01:30", "tz": "Asia/Dubai"} and d["zeiten"]["neu_bis"]["uhr"] == "16:00", "Nachtlauf aus der DB, Neue-Konten-Standard 16:00")
check(d["schalter"]["auto_bestaetigen"] == "cfd" and d["echo_hedge"]["an"] is True and d["tradeify_final_hedge"]["an"] is False, "Schalter + Hedge-Wege")
check(d["fest"]["futures"]["paar_extern_min"] == [2.0, 5.0] and d["fest"]["cfd"]["rest_min_usd"] == app.AP_REST_MIN_CFD, "Code-Konstanten wie im Planer")
check(r.headers.get("Cache-Control") == "no-store", "no-store")
check(d["zufall"] == app.ap_zufall_code() and d["zufall_db"] == [] and d["zeiten_db"] == REG["zeiten"], "E3b: Zufall (Code), zufall_db leer, zeiten_db roh")
ri_ = d["regel_info"]
check(isinstance(ri_, dict) and ri_.get("topstep", {}).get("id") == "topstep" and any(a["gruppe"] == "Drawdown" for a in ri_["topstep"]["abschnitte"])
      and "the5ers" in ri_ and "blueguardian" not in ri_, "E3b: Regeln der Firma aus firm_rules.json (Topstep mit Drawdown, Blue Guardian ohne Eintrag)")

print("3) POST /admin/auto-plan/kernwert")
gespeichert = []
app._planer_schreib_gate = lambda: None
app.sb_update = lambda t, f, b: gespeichert.append(b)
app._ap_kw_cache["x"] = (9e18, {})
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["phasen", "phase1", "tp"], "wert": [5500, 6400]}]})
check(r.status_code == 200 and gespeichert and gespeichert[-1]["regeln"]["firmen"][0]["phasen"]["phase1"]["tp"] == [5500, 6400]
      and gespeichert[-1]["regeln"]["auto_bestaetigen"] == "cfd" and not app._ap_kw_cache, "gespeichert, Rest der Regeln unverändert, Kernwert-Cache geleert")
n = len(gespeichert)
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["phasen", "phase1", "tp"], "wert": [6400, 5500]}]})
check(r.status_code == 400 and len(gespeichert) == n, "ungültig → 400, nichts geschrieben")
app._ap_zugang = lambda admin_reiter=False: (False, "u", json.loads(json.dumps(REG)), None)
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["kauf_eur", "200000"], "wert": 230}]})
check(r.status_code == 403 and len(gespeichert) == n, "kein Admin → 403")
app._planer_schreib_gate = lambda: (app.jsonify({"ok": False}), 403)
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["kauf_eur", "200000"], "wert": 230}]})
check(r.status_code == 403, "ohne Planer-Schreibrecht → 403")

print("4) POST /admin/auto-plan/ablaufwert (E3b)")
app._ap_zugang = lambda admin_reiter=False: (True, "u", json.loads(json.dumps(REG)), None)
app._planer_schreib_gate = lambda: None
gespeichert.clear()
r = c.post("/admin/auto-plan/ablaufwert", json={"zeiten": [{"pfad": ["nachtlauf", "uhr"], "wert": "01:45"}], "zufall": {"paar_intern_min": [3, 25]}, "auto_bestaetigen": "aus"})
d = r.get_json()
check(r.status_code == 200 and gespeichert and gespeichert[-1]["zeiten"]["nachtlauf"]["uhr"] == "01:45" and gespeichert[-1]["regeln"]["zufall"] == {"paar_intern_min": [3, 25]}
      and gespeichert[-1]["regeln"]["auto_bestaetigen"] is False and gespeichert[-1]["regeln"]["firmen"] == REG["regeln"]["firmen"] and d["zufall"]["paar_intern_min"] == [3, 25],
      "Zeiten + Zufall + Bestätigen in einem Update, Firmen unverändert")
n = len(gespeichert)
r = c.post("/admin/auto-plan/ablaufwert", json={"zeiten": [{"pfad": ["nachtlauf", "uhr"], "wert": "01:45"}], "zufall": {"fenster_wuerfe": 0}})
check(r.status_code == 400 and len(gespeichert) == n, "ein ungültiger Teil → 400, nichts geschrieben (auch die gültigen Zeiten nicht)")
check(c.post("/admin/auto-plan/ablaufwert", json={}).status_code == 400, "leer → 400")
r = c.post("/admin/auto-plan/ablaufwert", json={"bloecke": {"apex_hedge": {"vorlauf_min": 15}}, "schalter": [{"pfad": ["tradeify_final_halten"], "wert": False}]})
check(r.status_code == 200 and gespeichert[-1]["regeln"]["apex_hedge"]["vorlauf_min"] == 15 and gespeichert[-1]["regeln"]["tradeify_final_halten"] is False
      and "zeiten" not in gespeichert[-1], "Blöcke + Schalter über die Route, Zeiten unberührt")
n = len(gespeichert)
r = c.post("/admin/auto-plan/ablaufwert", json={"aktiv": False})
check(r.status_code == 200 and gespeichert[-1].get("aktiv") is False and "regeln" not in gespeichert[-1] and r.get_json()["aktiv"] is False, "Planer an/aus schreibt nur Spalte aktiv")
check(c.post("/admin/auto-plan/ablaufwert", json={"aktiv": "aus"}).status_code == 400, "aktiv nur true/false")
n = len(gespeichert)

print("4b) GET /admin/auto-plan/konten-stand")
_ks_n = []
app.ap_konten_stand = lambda reg: _ks_n.append(1) or [{"id": "k1", "firma": "tradeify", "fortschritt": 0.5}]
app._ap_ks_cache.clear()
r1 = c.get("/admin/auto-plan/konten-stand"); r2 = c.get("/admin/auto-plan/konten-stand")
check(r1.status_code == 200 and r1.get_json()["konten"][0]["id"] == "k1" and len(_ks_n) == 1 and r2.headers.get("Cache-Control") == "no-store", "Kontoliste, 60 s gemerkt, no-store")
app._ap_ks_cache.update(konten=[{"id": "a", "user_id": "u"}, {"id": "b", "user_id": "andere"}], bis=9e18)
app._ap_zugang = lambda admin_reiter=False: (False, "u", json.loads(json.dumps(REG)), None)
check([k["id"] for k in c.get("/admin/auto-plan/konten-stand").get_json()["konten"]] == ["a"], "Review: ohne Admin nur die eigenen Konten")
app._ap_zugang = lambda admin_reiter=False: (True, "u", json.loads(json.dumps(REG)), None)
check(len(c.get("/admin/auto-plan/konten-stand").get_json()["konten"]) == 2, "Admin sieht alle")

print("5) POST /admin/auto-plan/konto-consistency (Zusatz 4)")
KID = "11111111-2222-3333-4444-555555555555"
REG["user_ids"] = ["u-ht"]
app.sb_select = lambda t, p: [{"id": KID, "user_id": "u-ht", "account_type": "challenge"}] if p.get("id") == f"eq.{KID}" else []
r = c.post("/admin/auto-plan/konto-consistency", json={"konto_id": KID, "pct": 50})
check(r.status_code == 200 and gespeichert[-1] == {"consistency_pct": 50}, "50 % gespeichert")
r = c.post("/admin/auto-plan/konto-consistency", json={"konto_id": KID, "pct": None})
check(r.status_code == 200 and gespeichert[-1] == {"consistency_pct": None}, "leer = zurück auf Firmen-Standard")
n = len(gespeichert)
check(c.post("/admin/auto-plan/konto-consistency", json={"konto_id": KID, "pct": 150}).status_code == 400
      and c.post("/admin/auto-plan/konto-consistency", json={"konto_id": "x", "pct": 50}).status_code == 400 and len(gespeichert) == n, "Grenzen 1–100, nur bekannte Konten")
app.sb_select = lambda t, p: [{"id": KID, "user_id": "fremd", "account_type": "challenge"}]
check(c.post("/admin/auto-plan/konto-consistency", json={"konto_id": KID, "pct": 50}).status_code == 400, "Konto einer ID außerhalb des Planers → 400")
app.sb_select = lambda t, p: [{"id": KID, "user_id": "u-ht", "account_type": "funded"}]
check(c.post("/admin/auto-plan/konto-consistency", json={"konto_id": KID, "pct": 50}).status_code == 400 and len(gespeichert) == n, "Funded-Konto → 400")
app._ap_zugang = lambda admin_reiter=False: (False, "u", json.loads(json.dumps(REG)), None)
check(c.post("/admin/auto-plan/ablaufwert", json={"auto_bestaetigen": "aus"}).status_code == 403 and len(gespeichert) == n, "kein Admin → 403")
check(c.post("/admin/auto-plan/konto-consistency", json={"konto_id": KID, "pct": 50}).status_code == 403 and len(gespeichert) == n, "Konto-Consistency ohne Admin → 403")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
