#!/usr/bin/env python3
"""Selbsttest: PAARE JE FUTURES-FIRMA (app.py ap_paare_legen, Finn 19.10.2026 — „Tradeify Long und Tradeify Short, zwei IDs, innerhalb
von 10 Minuten") — rein rechnend. Aufruf: python3 tools/selftest_auto_paare.py"""
import os, random, re, sys
HIER = os.path.dirname(os.path.abspath(__file__)); APP = os.path.join(os.path.dirname(HIER), "app.py")

def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "random": random}
    teile = []
    for k in ("WD_FUTURES_FIRMEN", "WD_BALANCE_FUTURES", "AP_CFD_ROUTEN", "AP_FIRMA_ABSTAND_MIN", "AP_PAAR_ABSTAND", "AP_PAAR_PC_MIN", "AP_WAAGE_OHNE_FIRMEN"):
        teile.append(re.search(rf"^{k} = .*$", src, re.M).group(0).split("  #")[0])
    for name in ("ap_klasse", "ap_waage_ohne", "ap_paare_legen"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    ns["ap_fest_am_start"] = lambda refs, m: None
    exec("\n".join(teile), ns)
    return ns

def main():
    ns = lade(); P = ns["ap_paare_legen"]; f = []
    def check(ok, name):
        f.append(0 if ok else 1); print(("OK  " if ok else "FEHL") + " " + name)
    TI = lambda u, fk="tradeify", route="tvv2", **kw: dict({"user": u, "fkey": fk, "route": route}, **kw)
    # 1) Tradeify: Mike Short 05:16, Marc Short 05:25, Moritz Long 06:02, Aurel Long 07:35 (wie 19.10.) → zwei Paare, Longs rücken auf Anker + 2–10
    tr = {"k1": TI("mike"), "k2": TI("marc"), "k3": TI("moritz"), "k4": TI("aurel")}
    minuten = {"k1": 316.0, "k2": 325.0, "k3": 362.0, "k4": 455.0}
    richtung = {"k1": "sell", "k2": "sell", "k3": "buy", "k4": "buy"}
    out, info = P(minuten, richtung, tr, [], [], random.Random(1), ohne=("apex",))
    check(len(info) == 2 and {i["key"] for i in info} == {"k3", "k4"}, f"zwei Paare, die späteren Longs rücken ({[(i['key'], round(i['nach'], 1)) for i in info]})")
    check(all(2.0 <= i["nach"] - i["anker"] <= 10.0 for i in info), "Abstand zum Anker 2–10 min")
    check(out["k1"] == 316.0 and out["k2"] == 325.0, "Anker (die früheren) bleiben stehen")
    check(abs(out["k3"] - 316.0) <= 10 and abs(out["k4"] - 325.0) <= 10, "Mike↔Moritz, Marc↔Aurel (zeitlich nächster Gegentrade)")
    # 2) dieselbe ID nie als Partner
    tr2 = {"k1": TI("mike"), "k2": TI("mike")}
    out2, info2 = P({"k1": 316.0, "k2": 400.0}, {"k1": "sell", "k2": "buy"}, tr2, [], [], random.Random(2))
    check(info2 == [] and out2["k2"] == 400.0, "Long und Short derselben ID bilden kein Paar")
    # 3) Apex nie, CFD nie
    tr3 = {"a1": TI("mike", "apex"), "a2": TI("marc", "apex"), "c1": TI("mike", "fundednext", "mt5v2"), "c2": TI("marc", "fundednext", "mt5v2")}
    out3, info3 = P({"a1": 300.0, "a2": 400.0, "c1": 300.0, "c2": 400.0}, {"a1": "sell", "a2": "buy", "c1": "sell", "c2": "buy"}, tr3, [], [], random.Random(3), ohne=("apex",))
    check(info3 == [] and out3["a2"] == 400.0 and out3["c2"] == 400.0, "Apex (ohne Waage) und CFD bleiben unberührt")
    # 4) fester Anker (schon geplanter Tradeify-Short von Ina 05:00) — neuer Long rückt dorthin, der feste bewegt sich nie
    tr4 = {"k1": TI("mike")}
    out4, info4 = P({"k1": 500.0}, {"k1": "buy"}, tr4, [], [{"user_id": "ina", "firma": "tradeify", "richtung": "sell", "start": 300.0, "route": "tvv2"}], random.Random(4))
    check(len(info4) == 1 and 302.0 <= out4["k1"] <= 310.0 and info4[0]["anker_id"] == "fest:0", f"fester Anker: neuer Long rückt auf 05:02–05:10 ({out4['k1']})")
    # 5) PC belegt: Mike hat um Anker + 2–10 schon Starts → Platz suchen, sonst stehen lassen
    best = [{"user": "mike", "start": 300.0 + x, "fkey": "ftmo"} for x in range(0, 14, 1)]   # jede Minute 05:00–05:13 belegt
    out5, info5 = P({"k1": 500.0, "k2": 300.0}, {"k1": "buy", "k2": "sell"}, {"k1": TI("mike"), "k2": TI("ina")}, best, [], random.Random(5))
    check(info5 == [] and out5["k1"] == 500.0, "PC der ID in ± 3 min belegt → kein Paar, nichts bewegt")
    # 6) Fenster der Tranche: der spätere (Long 06:40, Fenster ab 05:20) dürfte nur auf 05:02–05:10 → außerhalb → nichts bewegt
    out6, info6 = P({"k1": 400.0, "k2": 300.0}, {"k1": "buy", "k2": "sell"}, {"k1": TI("mike", ab_min=320.0), "k2": TI("ina")}, [], [], random.Random(6))
    check(info6 == [] and out6["k1"] == 400.0 and out6["k2"] == 300.0, "Fenster der Tranche (ab_min) hält: kein Zug vor das Fenster")
    # 6b) der SPÄTERE rückt, nie der frühere: Long 03:20 (Anker) und Short 05:00 → Short rückt auf 03:22–03:30
    out6b, info6b = P({"k1": 200.0, "k2": 300.0}, {"k1": "buy", "k2": "sell"}, {"k1": TI("mike"), "k2": TI("ina")}, [], [], random.Random(6))
    check(out6b["k1"] == 200.0 and 202.0 <= out6b["k2"] <= 210.0 and info6b[0]["key"] == "k2", f"der spätere rückt zum früheren ({out6b['k2']})")
    # 7) schon ein Paar (Abstand 2–10) → nichts anfassen, aber beide vergeben
    out7, info7 = P({"k1": 300.0, "k2": 305.0, "k3": 420.0}, {"k1": "sell", "k2": "buy", "k3": "buy"}, {"k1": TI("mike"), "k2": TI("ina"), "k3": TI("marc")}, [], [], random.Random(7))
    check(info7 == [] and out7 == {"k1": 300.0, "k2": 305.0, "k3": 420.0}, "bestehendes Paar bleibt, dritter Long ohne Partner bleibt stehen")
    # 8) Zufall: über 30 Seeds streuen die Abstände zwischen 2 und 10
    abst = []
    for seed in range(30):
        _o, i8 = P({"k1": 316.0, "k3": 362.0}, {"k1": "sell", "k3": "buy"}, {"k1": TI("mike"), "k3": TI("moritz")}, [], [], random.Random(seed))
        abst.append(round(i8[0]["nach"] - 316.0, 2))
    check(min(abst) >= 2.0 and max(abst) <= 10.0 and len(set(abst)) >= 20 and max(abst) - min(abst) >= 4, f"Abstände gestreut {min(abst)}–{max(abst)} ({len(set(abst))} Werte)")
    # 9) gleicher rnd → gleiches Ergebnis (Probelauf = Anlegen)
    a = P(minuten, richtung, tr, [], [], random.Random(9))[0]; b = P(minuten, richtung, tr, [], [], random.Random(9))[0]
    check(a == b, "deterministisch je Seed")
    n = sum(f); print(f"\n{len(f) - n}/{len(f)} OK"); sys.exit(1 if n else 0)

if __name__ == "__main__":
    main()
