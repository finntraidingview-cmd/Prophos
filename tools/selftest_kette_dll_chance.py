#!/usr/bin/env python3
"""Selbsttest TOPSTEP-KETTE MIT DLL IN VORRAT UND KONTOWERT (app.py kette_dll_chance, vorrat_chance_stufe/-kette modell kette_dll,
vorrat_stufen_aus_kernwerten, ap_kontowert, 09.10.2026, Slave-Terminal 3 — Master: Punkt 6 aus dem DLL-Umbau; Referenz Rechnung Slave 1,
Artifact „Topstep angefressen": frisch 24,9 %, angefressen 147.000 Weg B 8,33 % (A 8,20 %), nach Gewinn 151.500 mit MLL 150.000 16,7 %).

Aufruf:  python3 tools/selftest_kette_dll_chance.py
Ohne Netz (Loader aus selftest_vorrat_stufe2). Geprüft: (1) kette_dll_chance gegen Slave 1 (±0,5 Prozentpunkte); (2) Stufe challenge wird
modell kette_dll nur mit kette.daily_usd, sonst wie bisher trades; (3) Chance je Zustand über vorrat_chance_kette (Challenge → Funded),
„eins vor" bei 154.500 (ein Gewinntag fehlt); (4) Kontowert = Kauf × Chance ÷ Chance(frisch): frisch = Kauf, 147.000 ≈ ⅓, 151.500 mit
gelocktem MLL ≈ ⅔ (alt 1,33 × Kauf), bestanden/Funded = Kauf ÷ 25 % (= alter Wert 4 × Kauf); ohne daily_usd unverändert."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_vorrat_stufe2 as v2  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


TOPSTEP = {"namen": ["topstep"], "route": "tsv2", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000], "kauf_eur": 237,
           "ziel_pct": {"challenge": 6}, "tp_max": 4500,
           "phasen": {"challenge": {"tp": [4350, 4450], "menge": [2, 3], "dd_usd": 4500, "tp_max": 4500, "ziel_pct": 6}},
           "kette": {"daily_usd": 3000, "tagesziel_usd": 4500, "t1_sl": [1250, 1750]}}
OHNE = dict(TOPSTEP, kette={"tagesziel_usd": 4500})


def main():
    ns = v2.lade()
    K = ns["kette_dll_chance"]
    T = lambda b, pk, rep=True: K(b, pk, 150000, 4500, 3000, 9000, 4500, reparatur=rep)["chance"]   # noqa: E731
    for name, ist, soll in (("frisch 150.000", T(150000, None), 0.249), ("angefressen 147.000 · Weg B", T(147000, 150000), 0.0833),
                            ("angefressen 147.000 · Weg A", T(147000, 150000, False), 0.082),
                            ("nach Gewinn 151.500, MLL 150.000", T(151500, 154500), 0.167)):
        check(abs(ist - soll) <= 0.005, f"Slave 1 {name}: {ist:.2%} (Referenz {soll:.1%})")
    k = K(147000, 150000, 150000, 4500, 3000, 9000, 4500)
    check(k["reparatur"] and k["win"] == 3000 and k["loss"] == 1500 and k["mll"] == 145500,
          f"147.000: Reparatur-Tag +3.000 / −1.500 (MLL 145.500) ({k['win']}/{k['loss']})")
    check(T(145500, 150000) == 0.0 and T(159000, 159000) == 1.0, "am MLL 0 %, am Ziel 100 %")

    st_ = ns["vorrat_stufen_aus_kernwerten"](TOPSTEP)
    so_ = ns["vorrat_stufen_aus_kernwerten"](OHNE)
    check(st_["challenge"]["modell"] == "kette_dll" and so_["challenge"]["modell"] == "trades" and st_["funded"].get("modell") == "trades",
          f"Stufe challenge: mit daily_usd kette_dll, ohne wie bisher trades; Funded unverändert ({st_['challenge']['modell']}/{so_['challenge']['modell']})")
    S = lambda b, pk=None: ns["vorrat_chance_stufe"](st_["challenge"], b, 150000, 150000, None, pk)   # noqa: E731
    check(abs(S(150000)["chance"] - 0.25) < 0.005 and abs(S(147000, 150000)["chance"] - 0.0833) < 0.005
          and abs(S(151500, 154500)["chance"] - 0.1667) < 0.005 and S(147000, 150000)["boden"] == 145500,
          f"vorrat_chance_stufe kette_dll: 25,0 / 8,3 / 16,7 % ({S(150000)['chance']:.3f} / {S(147000, 150000)['chance']:.3f} / {S(151500, 154500)['chance']:.3f})")
    e = ns["vorrat_chance_kette"](st_, "challenge", 154500, 150000, 150000, peak=154500)
    check(e["kette"][0]["modell"] == "kette_dll" and e["kette"][0]["rest_trades"] == 1 and abs(e["kette"][0]["roh"] - 0.5) < 0.005,
          f"154.500: ein Gewinntag fehlt (rest_trades 1 → eins vor), Chance 50 % ({e['kette'][0]})")
    e2 = ns["vorrat_chance_kette"](st_, "challenge", 151500, 150000, 150000, peak=None)
    check(abs(e2["kette"][0]["roh"] - S(151500)["chance"]) < 1e-9 and e2["kette"][0]["polster"] == 4500,
          f"ohne Höchststand rechnet der MLL ab der Balance (151.500 → MLL 147.000, Chance {e2['kette'][0]['roh']:.1%})")

    P = ns["ap_kw_param"]
    W = lambda typ, b, pk=None, r=TOPSTEP: ns["ap_kontowert"](typ, b, P(r), None, peak=pk)   # noqa: E731
    w0, w1, w2, wf = W("challenge", 150000), W("challenge", 147000, 150000), W("challenge", 151500, 154500), W("funded", 150000)
    check(w0["wert"] == 237 and abs(w1["wert"] - 237 / 3) <= 2 and abs(w2["wert"] - 237 * 2 / 3) <= 2 and w1["polster"] == 1500,
          f"Kontowert: frisch {w0['wert']} = Kauf, 147.000 {w1['wert']} ≈ ⅓, 151.500 (MLL 150.000) {w2['wert']} ≈ ⅔, Polster {w1['polster']}")
    alt0, alt2, altf = W("challenge", 150000, r=OHNE), W("challenge", 151500, r=OHNE), W("funded", 150000, r=OHNE)
    check(alt0["wert"] == 237 and alt2["wert"] == 316 and abs(wf["wert"] - altf["wert"]) <= 1,
          f"ohne daily_usd unverändert (151.500 alt {alt2['wert']} €); Funded-Startwert mit Kette {wf['wert']} = alt {altf['wert']} (4 × Kauf)")
    check(w0["satz"] > 0 and w0["wie"] == "Kauf 237 × Chance 25,0 % ÷ frisch 25,0 % (Topstep-Kette DLL, MLL 145.500)", f"Satz je $ aus dem Tagesausgang ({w0['satz']} €/$, {w0['wie']})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
