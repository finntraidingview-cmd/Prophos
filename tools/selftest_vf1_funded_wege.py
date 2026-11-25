#!/usr/bin/env python3
"""Selbsttest VF1 (Master 26.11.2026, Befund Slave 1): Lucid, FundedNext Futures und FTMO Futures standen in JEDEM Vorrat-Lauf für alle 16 IDs auf
„daten_fehlen“ („Deckel 10 Käufe erreicht — auch damit unter 25 % Sicherheit“, chance_neu 0) — VORRAT2_STD.funded_wege kennt nur Tradeify/Topstep/Apex,
ohne Funded-Weg ist die Kette Challenge → Funded → Winning Days 0. Fix: fehlende Wege aus Finns Funded-Planer (funded_plan_regeln je Größe: dd,
ziel_gewinn) — Tradeify/Topstep/Apex bleiben bitgleich. Echte Funktionen (Lader aus selftest_vorrat_stufe2), Kernwerte wie live 26.11.
Aufruf: python3 tools/selftest_vf1_funded_wege.py"""
import importlib.util
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(HIER)
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


spec = importlib.util.spec_from_file_location("s2", os.path.join(HIER, "selftest_vorrat_stufe2.py"))
s2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s2)
ns = s2.lade()
i = SRC.index("def vorrat_funded_wege_aus_planer(")
exec(SRC[i:SRC.find("\n\n\n", i)], ns)
aus_planer, stufen_aus, kette, STD = ns["vorrat_funded_wege_aus_planer"], ns["vorrat_stufen_aus_kernwerten"], ns["vorrat_chance_kette"], ns["VORRAT2_STD"]

# funded_plan_regeln.firmen wie live 26.11.2026 (gekürzt auf die gelesenen Felder)
FPR = [
    {"an": False, "name": "Apex Trader", "namen": ["apextrader", "apex"], "je_groesse": {"100000": {"dd": 3000, "ziel_gewinn": 12000}}},
    {"an": True, "name": "Tradeify", "namen": ["tradeify"], "je_groesse": {"150000": {"dd": 4500, "ziel_gewinn": [13000, 19000]}}},
    {"an": False, "name": "Topstep", "namen": ["topstep"], "je_groesse": {"150000": {"dd": 4500, "ziel_gewinn": [13000, 19000]}}},
    {"an": True, "name": "Lucid Trading", "namen": ["lucidtrading", "lucid"], "je_groesse": {
        "50000": {"an": True, "dd": 2000, "ziel_gewinn": [6000, 8000]}, "150000": {"an": True, "dd": 4500, "ziel_gewinn": [12500, 14000]}}},
    {"an": True, "name": "FundedNext Futures", "namen": ["fundednextfutures"], "je_groesse": {"50000": {"an": True, "dd": 1500, "ziel_gewinn": [6000, 8000]}}},
    {"an": True, "name": "FTMO Futures", "namen": ["ftmofutures"], "je_groesse": {"50000": {"dd": 3000, "ziel_gewinn": [4000, 4500]}}},
    {"an": True, "name": "Kaputt", "namen": ["kaputt"], "je_groesse": {"50000": {"dd": 0, "ziel_gewinn": [1, 2]}, "x": "nein"}},
]
fw = aus_planer(FPR)
check(set(fw) == {"tradeify", "lucidtrading", "fundednextfutures", "ftmofutures"}, f"Wege aus dem Planer: eingeschaltete Firmen mit dd + Ziel ({sorted(fw)})")
check(fw["lucidtrading"]["je_groesse"] == {"50000": {"risiko_usd": 2000.0, "tps_usd": [7000.0]}, "150000": {"risiko_usd": 4500.0, "tps_usd": [13250.0]}}
      and fw["lucidtrading"]["tps_usd"] == [13250.0], "Lucid: 50k 2.000 → 7.000, 150k 4.500 → 13.250 (Mitte der Ziel-Spanne)")
check(fw["ftmofutures"]["je_groesse"]["50000"] == {"risiko_usd": 3000.0, "tps_usd": [4250.0]}, "FTMO Futures 50k: 3.000 → 4.250")
check(aus_planer([{"an": True, "namen": ["x"], "je_groesse": {"50000": {"an": False, "dd": 1, "ziel_gewinn": 5}}}]) == {}, "Größe aus → kein Weg")

# Zusammenführen wie _vorrat2_tabellen: Code-Wege gewinnen (Tradeify/Topstep/Apex bitgleich)
param = dict(STD, funded_wege=dict(fw, **STD["funded_wege"]))
check(param["funded_wege"]["tradeify"] == STD["funded_wege"]["tradeify"] and param["funded_wege"]["apextrader"] == STD["funded_wege"]["apextrader"],
      "Tradeify/Apex: fester Weg aus dem Code bleibt (bitgleich)")
tab = SRC[SRC.index("def _vorrat2_tabellen("):SRC.index("\ndef ", SRC.index("def _vorrat2_tabellen(") + 10)]
check('param["funded_wege"] = dict(vorrat_funded_wege_aus_planer(fpr), **(param.get("funded_wege") or {}))' in tab and "except Exception as e:" in tab,
      "_vorrat2_tabellen liest funded_plan_regeln, Code/Parameter gewinnen, Lesefehler bricht den Lauf nicht ab")

# Kernwerte wie live (auto_plan_regeln.regeln.firmen[])
LUCID = {"namen": ["lucidtrading", "lucid"], "boden": "nachziehend", "dd_usd": 4500, "groessen": [50000, 150000], "ziel_pct": {"challenge": 6},
         "lock_bei_start": True, "daily_usd": 2700, "kauf_eur": {"50000": 78, "150000": 170},
         "phasen": {"challenge": {"tp": [3450, 3550], "menge": [2, 2.8], "dd_usd": 4500, "tp_max": 3600, "ziel_pct": 6}}}
FNF = {"namen": ["fundednextfutures"], "boden": "nachziehend", "dd_usd": 4000, "groessen": [50000, 150000], "ziel_pct": {"challenge": 5.333333333333334},
       "lock_bei_start": True, "kauf_eur": {"50000": 74, "150000": 245},
       "phasen": {"challenge": {"tp": [3050, 3150], "dd_usd": 4000, "tp_max": 3200, "ziel_pct": 5.333333333333334}}}
FTF = {"namen": ["ftmofutures"], "boden": "nachziehend", "dd_usd": 3000, "groessen": [50000], "ziel_pct": {"challenge": 6}, "lock_bei_start": True,
       "daily_usd": 1000, "kauf_eur": 120, "phasen": {"challenge": {"sl": [700, 800], "tp": [1475, 1500], "dd_usd": 3000, "tp_max": 1500, "ziel_pct": 6}}}

for name, regel, gr, wert in (("Lucid 150k", LUCID, 150000, 13250.0), ("Lucid 50k", LUCID, 50000, 7000.0),
                              ("FNF 50k", FNF, 50000, 7000.0), ("FTMO Futures 50k", FTF, 50000, 4250.0)):
    alt = kette(stufen_aus(regel, STD), "challenge", gr, gr, param=STD)
    neu = kette(stufen_aus(regel, param), "challenge", gr, gr, param=param)
    check(alt.get("daten_fehlen") is True or not alt.get("chance"), f"{name} vorher: Funded-Weg fehlt → keine Chance (der Befund)")
    check(not neu.get("daten_fehlen") and 0.02 < (neu.get("chance") or 0) < 0.6 and abs(float(neu.get("wert_usd") or 0) - wert) < 1,
          f"{name} jetzt: Chance bis Winning Days {round(100 * (neu.get('chance') or 0), 1)} %, Wert beim Ankommen {neu.get('wert_usd')} (soll {wert})")
tr = kette(stufen_aus({"namen": ["tradeify"], "groessen": [150000], "dd_usd": 4500, "boden": "nachziehend", "ziel_pct": {"challenge": 6},
                       "phasen": {"challenge": {"tp_max": 3600}}}, param), "challenge", 150000, 150000, param=param)
tr0 = kette(stufen_aus({"namen": ["tradeify"], "groessen": [150000], "dd_usd": 4500, "boden": "nachziehend", "ziel_pct": {"challenge": 6},
                        "phasen": {"challenge": {"tp_max": 3600}}}, STD), "challenge", 150000, 150000, param=STD)
check(tr.get("chance") == tr0.get("chance") and tr.get("wert_usd") == tr0.get("wert_usd"), "Tradeify-Kette bitgleich zu vorher")
st = ns["vorrat_chance_stufe"]
r_ohne = {"modell": "trades", "risiko_usd": 4500, "tps_usd": [14500]}
check(st(r_ohne, 150000, 150000) == st(dict(r_ohne, je_groesse={"50000": {"risiko_usd": 1, "tps_usd": [1]}}), 150000, 150000),
      "Weg ohne passende Größe: rechnet wie bisher (oberste Werte)")
check("VORRAT2_RECHEN_STAND = 12" in SRC, "Rechenstand 12: alte Läufe rechnen einmal neu")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
