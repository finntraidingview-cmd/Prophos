#!/usr/bin/env python3
"""Selbsttest: PAARE JE FUTURES-FIRMA (app.py ap_paare_legen, Finn 19.10.2026 — „Tradeify Long und Tradeify Short, zwei IDs, innerhalb
von 10 Minuten"; seit 25.10.2026 propfirm-extern zuerst 2–5 min, intern 2–30 min) — rein rechnend. Aufruf: python3 tools/selftest_auto_paare.py"""
import os, random, re, sys
HIER = os.path.dirname(os.path.abspath(__file__)); APP = os.path.join(os.path.dirname(HIER), "app.py")

def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "random": random}
    teile = []
    for k in ("WD_FUTURES_FIRMEN", "WD_BALANCE_FUTURES", "AP_CFD_ROUTEN", "AP_FIRMA_ABSTAND_MIN", "AP_PAAR_ABSTAND", "AP_PAAR_ABSTAND_EXTERN", "AP_PAAR_PC_MIN", "AP_PAAR_RS_MIN", "AP_WAAGE_OHNE_FIRMEN"):
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
    # 1) Tradeify: Mike Short 05:16, Marc Short 05:25, Moritz Long 06:02, Aurel Long 07:35 (wie 19.10.) → zwei Paare, Longs rücken auf Anker + 2–30
    tr = {"k1": TI("mike"), "k2": TI("marc"), "k3": TI("moritz"), "k4": TI("aurel")}
    minuten = {"k1": 316.0, "k2": 325.0, "k3": 362.0, "k4": 455.0}
    richtung = {"k1": "sell", "k2": "sell", "k3": "buy", "k4": "buy"}
    out, info = P(minuten, richtung, tr, [], [], random.Random(1), ohne=("apex",))
    check(len(info) == 2 and {i["key"] for i in info} == {"k3", "k4"}, f"zwei Paare, die späteren Longs rücken ({[(i['key'], round(i['nach'], 1)) for i in info]})")
    check(all(2.0 <= i["nach"] - i["anker"] <= 30.0 and i["art"] == "intern" for i in info), "nur Tradeify → intern, Abstand zum Anker 2–30 min")
    check(out["k1"] == 316.0 and out["k2"] == 325.0, "Anker (die früheren) bleiben stehen")
    check(info[0]["anker"] == 316.0 and info[1]["anker"] == 325.0, "Mike↔Moritz, Marc↔Aurel (zeitlich nächster Gegentrade)")
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
    check(len(info4) == 1 and 302.0 <= out4["k1"] <= 330.0 and info4[0]["anker_id"] == "fest:0", f"fester Anker: neuer Long rückt auf 05:02–05:30 ({out4['k1']})")
    # 5) PC belegt: Mike hat um Anker + 2–10 schon Starts → Platz suchen, sonst stehen lassen
    best = [{"user": "mike", "start": 300.0 + x, "fkey": "ftmo"} for x in range(0, 34, 1)]   # jede Minute 05:00–05:33 belegt
    out5, info5 = P({"k1": 500.0, "k2": 300.0}, {"k1": "buy", "k2": "sell"}, {"k1": TI("mike"), "k2": TI("ina")}, best, [], random.Random(5))
    check(info5 == [] and out5["k1"] == 500.0, "PC der ID in ± 3 min belegt → kein Paar, nichts bewegt")
    # 6) Fenster der Tranche: der spätere (Long 06:40, Fenster ab 05:40) dürfte nur auf 05:02–05:30 → außerhalb → nichts bewegt
    out6, info6 = P({"k1": 400.0, "k2": 300.0}, {"k1": "buy", "k2": "sell"}, {"k1": TI("mike", ab_min=340.0), "k2": TI("ina")}, [], [], random.Random(6))
    check(info6 == [] and out6["k1"] == 400.0 and out6["k2"] == 300.0, "Fenster der Tranche (ab_min) hält: kein Zug vor das Fenster")
    # 6b) der SPÄTERE rückt, nie der frühere: Long 03:20 (Anker) und Short 05:00 → Short rückt auf 03:22–03:30
    out6b, info6b = P({"k1": 200.0, "k2": 300.0}, {"k1": "buy", "k2": "sell"}, {"k1": TI("mike"), "k2": TI("ina")}, [], [], random.Random(6))
    check(out6b["k1"] == 200.0 and 202.0 <= out6b["k2"] <= 230.0 and info6b[0]["key"] == "k2", f"der spätere rückt zum früheren ({out6b['k2']})")
    # 7) schon ein Paar (Abstand 2–10) → nichts anfassen, aber beide vergeben
    out7, info7 = P({"k1": 300.0, "k2": 305.0, "k3": 420.0}, {"k1": "sell", "k2": "buy", "k3": "buy"}, {"k1": TI("mike"), "k2": TI("ina"), "k3": TI("marc")}, [], [], random.Random(7))
    check(info7 == [] and out7 == {"k1": 300.0, "k2": 305.0, "k3": 420.0}, "bestehendes Paar bleibt, dritter Long ohne Partner bleibt stehen")
    # 8) Zufall: über 30 Seeds streuen die Abstände (intern) zwischen 2 und 30
    abst = []
    for seed in range(30):
        _o, i8 = P({"k1": 316.0, "k3": 362.0}, {"k1": "sell", "k3": "buy"}, {"k1": TI("mike"), "k3": TI("moritz")}, [], [], random.Random(seed))
        abst.append(round(i8[0]["nach"] - 316.0, 2))
    check(min(abst) >= 2.0 and max(abst) <= 30.0 and len(set(abst)) >= 20 and max(abst) - min(abst) >= 15, f"Abstände gestreut {min(abst)}–{max(abst)} ({len(set(abst))} Werte)")
    # 10) ANKER NUR IN DER ZUKUNFT (19.10.2026, Aurel 19:27 Dubai = 17:27 dt, frueh = 17:42 dt = 1062): feste Tradeify-Anker 17:00 / 15:47 / 16:16 dt
    #     (Short/Long/Short) sind vorbei → kein Paar, die neuen Pläne behalten ihre Startzeit (≥ frueh); nie eine Zeit < frueh
    fest10 = [{"user_id": "mike", "firma": "tradeify", "richtung": "sell", "start": 1020.0, "route": "tvv2"},
              {"user_id": "marc", "firma": "tradeify", "richtung": "buy", "start": 947.0, "route": "tvv2"},
              {"user_id": "ina", "firma": "tradeify", "richtung": "sell", "start": 976.0, "route": "tvv2"}]
    m10 = {"a1": 1075.0, "a2": 1130.0}
    out10, info10 = P(m10, {"a1": "buy", "a2": "sell"}, {"a1": TI("aurel"), "a2": TI("aurel")}, [], fest10, random.Random(10), ohne=("apex",), frueh=1062.0)
    check(info10 == [] and out10 == m10, f"Anker in der Vergangenheit: kein Paar, Startzeiten bleiben ({out10})")
    # 10b) derselbe Lauf, aber ein ZUKÜNFTIGER fester Gegen-Trade (Moritz Short 18:40 dt = 1120) → Aurels Long rückt auf 1122–1150, nie unter frueh
    #      (Aurels eigener Short liegt hier um 22:00 dt, damit der Richtungsschutz ± 30 min nicht greift)
    out10b, info10b = P({"a1": 1075.0, "a2": 1320.0}, {"a1": "buy", "a2": "sell"}, {"a1": TI("aurel"), "a2": TI("aurel")}, [], fest10 + [{"user_id": "moritz", "firma": "tradeify", "richtung": "sell", "start": 1120.0, "route": "tvv2"}], random.Random(10), ohne=("apex",), frueh=1062.0)
    check(len(info10b) == 1 and info10b[0]["key"] == "a1" and 1122.0 <= out10b["a1"] <= 1150.0 and info10b[0]["anker_id"] == "fest:3", f"vergangene Anker übersprungen, Paar mit dem zukünftigen Short ({out10b['a1']})")
    # 10e) zukünftiger Short schon 15 min entfernt (≤ 30) → zählt als Paar, nichts rückt
    out10e, info10e = P(m10, {"a1": "buy", "a2": "sell"}, {"a1": TI("aurel"), "a2": TI("aurel")}, [], fest10 + [{"user_id": "moritz", "firma": "tradeify", "richtung": "sell", "start": 1090.0, "route": "tvv2"}], random.Random(10), ohne=("apex",), frueh=1062.0)
    check(info10e == [] and out10e == m10, "Gegen-Trade 15 min entfernt ist schon ein Paar (intern 2–30)")
    # 10c) Anker knapp vorbei (frueh − 5): nur Ziele ≥ frueh sind frei → nach rückt auf ≥ frueh, nie darunter
    treffer = [P({"a1": 1200.0}, {"a1": "buy"}, {"a1": TI("aurel")}, [], [{"user_id": "mike", "firma": "tradeify", "richtung": "sell", "start": 1057.0, "route": "tvv2"}], random.Random(s), frueh=1062.0) for s in range(20)]
    check(all((not i) or (o["a1"] >= 1062.0 and o["a1"] <= 1087.0) for o, i in treffer) and any(i for _o, i in treffer), "Anker knapp vorbei: Partner rückt nur auf ≥ frueh (jetzt + Vorlauf)")
    # 10d) ohne frueh (Nachtlauf) alles wie bisher
    out10d, info10d = P({"k1": 500.0}, {"k1": "buy"}, {"k1": TI("mike")}, [], [{"user_id": "ina", "firma": "tradeify", "richtung": "sell", "start": 300.0, "route": "tvv2"}], random.Random(4))
    check(len(info10d) == 1 and 302.0 <= out10d["k1"] <= 330.0, "ohne frueh (Nachtlauf) unverändert")
    # 11) PROPFIRM-EXTERN ZUERST (Finn 25.10.2026): Mike Tradeify Short 05:00, Marc Tradeify Long 05:20, Ina Topstep Long 06:30 →
    #     Topstep (kleiner Pool) paart extern mit Mikes Short (Ina rückt auf 05:02–05:05), Marcs Long findet intern keinen freien Short mehr
    tr11 = {"t1": TI("mike"), "t2": TI("marc"), "s1": TI("ina", "topstep", "tsv2")}
    out11, info11 = P({"t1": 300.0, "t2": 320.0, "s1": 390.0}, {"t1": "sell", "t2": "buy", "s1": "buy"}, tr11, [], [], random.Random(11), ohne=("apex",))
    check(len(info11) == 1 and info11[0]["art"] == "extern" and info11[0]["key"] == "s1" and 302.0 <= out11["s1"] <= 305.0
          and info11[0]["anker_firma"] == "tradeify", f"extern vor intern: Topstep-Long rückt 2–5 min hinter den Tradeify-Short ({out11['s1']})")
    check(out11["t2"] == 320.0, "Tradeify-Long ohne freien Partner bleibt stehen (der Short ist extern vergeben)")
    # 12) extern dieselbe ID erlaubt (Jacob Tradeify Long ↔ Jacob Topstep Short) — PC ± 3 min gilt, also 3–5 min
    tr12 = {"t1": TI("jacob"), "s1": TI("jacob", "topstep", "tsv2")}
    r12 = [P({"t1": 300.0, "s1": 450.0}, {"t1": "buy", "s1": "sell"}, tr12, [], [], random.Random(s)) for s in range(20)]
    check(all(len(i) == 1 and i[0]["art"] == "extern" and 303.0 <= o["s1"] <= 305.0 for o, i in r12), "gleiche ID über zwei Firmen ist ein Paar (3–5 min wegen PC-Abstand)")
    # 13) RICHTUNGSSCHUTZ beim Rücken: Jacob hat schon einen Topstep-Short um 05:30 geplant; sein neuer Topstep-Long (07:00) dürfte nur auf
    #     05:02–05:05 hinter Inas Tradeify-Short rücken — 25 min neben dem eigenen Topstep-Short = verboten → bleibt stehen, Richtung unverändert
    fest13 = [{"user_id": "jacob", "firma": "topstep", "richtung": "sell", "start": 330.0, "route": "tsv2"}]
    out13, info13 = P({"t1": 300.0, "s1": 420.0}, {"t1": "sell", "s1": "buy"}, {"t1": TI("ina"), "s1": TI("jacob", "topstep", "tsv2")}, [], fest13, random.Random(13))
    check(info13 == [] and out13["s1"] == 420.0, "Long nie in ± 30 min an die Gegenrichtung derselben ID × Firma gerückt")
    # 13b) dasselbe innerhalb eines Laufs (beide neu): Jacob Topstep Short 05:30 neu, Jacob Topstep Long neu → Long rückt nicht daneben
    out13b, info13b = P({"t1": 300.0, "s0": 330.0, "s1": 420.0}, {"t1": "sell", "s0": "sell", "s1": "buy"},
                        {"t1": TI("ina"), "s0": TI("jacob", "topstep", "tsv2"), "s1": TI("jacob", "topstep", "tsv2")}, [], [], random.Random(13))
    check(all(abs(out13b["s1"] - out13b["s0"]) >= 30.0 for _ in [0]), f"auch neu gegen neu: Abstand Long↔Short derselben ID × Firma ≥ 30 min ({out13b})")
    # 14) Abstände extern über 30 Seeds 2–5 min
    ab14 = []
    for seed in range(30):
        _o, i14 = P({"t1": 300.0, "s1": 500.0}, {"t1": "sell", "s1": "buy"}, {"t1": TI("mike"), "s1": TI("ina", "lucidtrading")}, [], [], random.Random(seed))
        ab14.append(round(i14[0]["nach"] - 300.0, 2))
    check(min(ab14) >= 2.0 and max(ab14) <= 5.0 and len(set(ab14)) >= 20, f"extern gestreut {min(ab14)}–{max(ab14)} ({len(set(ab14))} Werte)")
    # 15) Apex-Anker zählt nie (auch nicht extern)
    out15, info15 = P({"s1": 400.0}, {"s1": "buy"}, {"s1": TI("ina", "topstep", "tsv2")}, [],
                      [{"user_id": "mike", "firma": "apex", "richtung": "sell", "start": 300.0, "route": "tvv2"}], random.Random(15), ohne=("apex",))
    check(info15 == [] and out15["s1"] == 400.0, "fester Apex-Short ist kein Partner")
    # 16) Topstep-Fenster (bis_min = t1_bis): Partner hinter dem Anker läge nach dem Fenster → kein Zug
    out16, info16 = P({"t1": 658.0, "s1": 659.0}, {"t1": "sell", "s1": "buy"}, {"t1": TI("mike"), "s1": TI("ina", "topstep", "tsv2", bis_min=660.0)}, [], [], random.Random(16))
    check(out16["s1"] <= 660.0, f"Topstep Trade 1 bleibt im Fenster bis t1_bis ({out16['s1']})")
    # 9) gleicher rnd → gleiches Ergebnis (Probelauf = Anlegen)
    a = P(minuten, richtung, tr, [], [], random.Random(9))[0]; b = P(minuten, richtung, tr, [], [], random.Random(9))[0]
    check(a == b, "deterministisch je Seed")
    n = sum(f); print(f"\n{len(f) - n}/{len(f)} OK"); sys.exit(1 if n else 0)

if __name__ == "__main__":
    main()
