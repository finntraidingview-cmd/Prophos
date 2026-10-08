#!/usr/bin/env python3
"""Selbsttest FENSTER-TREUE VERTEILUNG (app.py ap_zeiten_verteilen, 08.10.2026, Slave-Terminal 3 — Finn: Opening-Anteil laut
Zeitfenster; der Nachtlauf legte nur 15 von 36 statt 18 Plänen ins Opening 14:30–16:30 dt).

Aufruf:  python3 tools/selftest_auto_fenster_treu.py
Ohne Netz, Platzhalter-IDs, Planmischung wie am 08.10.2026 (36 Pläne, 7 IDs, Firmen-Mix). Geprüft über 40 Seeds: Ø Opening ≥ 17 von
18 (vorher Ø 15,7), nie unter 15; alle 36 platziert; Abstand je ID × Firma ≥ 60 min (volle Stufe) in ≥ 95 % der Paare, nie unter der
¼-Stufe; gleicher Seed → gleiches Ergebnis (Probelauf = Anlegen); info je Key gefüllt."""
import collections
import os
import random
import statistics
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


MIX = ([("u1", "Blue Guardian")] * 2 + [("u2", "FundingPips"), ("u2", "The5%ers"), ("u2", "The5%ers")] + [("u2", "Tradeify")] * 4
       + [("u1", "The5%ers"), ("u1", "FundedNext Futures"), ("u1", "FundedNext Futures")]
       + [("u3", "FundingPips")] * 4 + [("u3", "FTMO")] + [("u3", "FundedNext")] * 4
       + [("u4", "The5%ers")] * 2 + [("u4", "FundedNext")]
       + [("u5", "FundedNext"), ("u5", "Tradeify")]
       + [("u6", "Apex Trader")] * 3 + [("u6", "FundingPips")] + [("u6", "FundedNext")] * 3 + [("u6", "Tradeify")] * 2
       + [("u7", "FundedNext")])
CFD = {"FundingPips", "The5%ers", "FTMO", "FundedNext", "Blue Guardian"}
Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3, "cfd_ab": "00:20"}


def tranchen():
    n = collections.Counter()
    out = []
    for u, f in MIX:
        out.append({"key": f"{u}|{f}#{n[(u, f)]}", "user": u, "gruppe": f"{u}|{f}", "fkey": f, "dauer_min": 2, "ab_min": 20 if f in CFD else 0})
        n[(u, f)] += 1
    return out


def main():
    a = sd.lade()
    V = a["ap_zeiten_verteilen"]
    check(len(MIX) == 36, f"Planmischung 36 Pläne ({len(MIX)})")
    opening, alle, voll, paare, unter_viertel = [], [], 0, 0, 0
    for seed in range(40):
        info = {}
        m = V(tranchen(), Z, random.Random(seed), frueheste_min=0, info=info)
        opening.append(sum(1 for v in m.values() if v >= 870))
        alle.append(len(m))
        je = collections.defaultdict(list)
        for k, v in m.items():
            je[k.split("#")[0]].append(v)
        for starts in je.values():
            s = sorted(starts)
            for x, y in zip(s, s[1:]):
                paare += 1
                voll += (y - x) >= a["AP_ABSTAND_ID_FIRMA_MIN"]
                unter_viertel += (y - x) < a["AP_ABSTAND_ID_FIRMA_MIN"] * 0.25
    check(statistics.mean(opening) >= 17 and min(opening) >= 15,
          f"Opening (Soll 18 von 36): Ø {statistics.mean(opening):.2f}, min {min(opening)}, max {max(opening)} — vorher Ø 15,7")
    check(min(alle) == 36, "alle 36 platziert")
    check(voll / max(paare, 1) >= 0.95 and unter_viertel == 0,
          f"Abstand je ID × Firma: {voll}/{paare} Paare mit vollen 60 min, keins unter der ¼-Stufe")
    m1 = V(tranchen(), Z, random.Random(7), frueheste_min=0)
    m2 = V(tranchen(), Z, random.Random(7), frueheste_min=0)
    info = {}
    m3 = V(tranchen(), Z, random.Random(7), frueheste_min=0, info=info)
    check(m1 == m2 == m3 and len(info) == 36 and all("fenster" in v and "soll" in v and v.get("stufe") == 1.0 for v in info.values()),
          "gleicher Seed → gleiches Ergebnis, info je Key mit fenster/soll/stufe 1.0 (Probelauf = Anlegen)")

    # Sieger-Regel (Prüfung Slave 2): treuer, aber gelockert verliert gegen volle Abstände; mehr platziert schlägt beides
    OP, VM = [870, 990, 50], [0, 870, 50]
    wuerfe = [({"a": 900, "b": 100}, {"a": {"fenster": OP, "soll": OP, "stufe": 1.0}, "b": {"fenster": VM, "soll": OP, "stufe": 1.0}}),
              ({"a": 900, "b": 950}, {"a": {"fenster": OP, "soll": OP, "stufe": 1.0}, "b": {"fenster": OP, "soll": OP, "stufe": 0.5}}),
              ({"a": 900, "b": 940}, {"a": {"fenster": OP, "soll": OP, "stufe": 1.0}, "b": {"fenster": OP, "soll": OP, "stufe": 1.0}}),
              ({"a": 900, "b": 960}, {"a": {"fenster": OP, "soll": OP, "stufe": 1.0}, "b": {"fenster": OP, "soll": OP, "stufe": 0.0}})]
    echt = a["_ap_zeiten_verteilen_einmal"]
    for reihe, erwartet, name in (([0, 1] * 10, 100, "voll + weniger treu schlägt treu + gelockert"),
                                  ([1, 0, 2] + [0] * 17, 940, "voll + treu schlägt beide"),
                                  ([3, 0] * 10, 100, "Stufe 0.0 (nur PC-Regel) zählt als gelockert")):
        it = iter(reihe)

        def fake(tranchen, zeiten, rnd, frueheste_min=0, info=None, bestehend=None):
            m, i = wuerfe[next(it)]
            info.update(i)
            return dict(m)
        a["_ap_zeiten_verteilen_einmal"] = fake
        i_out = {}
        m = V([], Z, random.Random(1), info=i_out)
        check(m.get("b") == erwartet and i_out["b"]["stufe"] == 1.0, f"Sieger-Regel: {name} (b = {m.get('b')})")
    a["_ap_zeiten_verteilen_einmal"] = echt

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
