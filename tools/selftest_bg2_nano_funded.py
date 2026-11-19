#!/usr/bin/env python3
"""Selbsttest BG2 (Finn 19.11.2026): Blue Guardian 2 Step NANO FUNDED im Funded-CFD-Planer — Variante je Konto (app.py fcp_regel_konto, Kennung
accounts.max_drawdown ≥ flex.ab_dd_pct %) mit den Werten aus sql/2026-11-19_bg2_blue_guardian_nano_funded.sql.

Aufruf:  python3 tools/selftest_bg2_nano_funded.py      (ohne Netz, Platzhalter-Konten)
Geprüft: Erkennung (10.000 Nano / 8.000 und leer Standard / ohne Größe Standard); Nano: Ziel 800–1.200, keine Gewinntage, Consistency 50 % über den
vorhandenen Weg (TP ≤ 50 % × Summe × 0,95, „Ziel erreicht“ erst mit größtem Tag ≤ 50 %), SL 1.250–1.700, Lots 1–1,75, Hedge 0,05 €/$; Standard-Konto
bitgleich mit und ohne flex (gleicher Zufall); Radar-Ziel/Boden Nano 100.800 / 90.000; alle Leser der Funded-Regel gehen durch fcp_regel_konto."""
import copy
import os
import random
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


# blueguardian-Eintrag in funded_cfd_plan_regeln wie live (19.11.2026) + flex wie in der SQL-Datei
BG = {"an": True, "name": "Blue Guardian", "namen": ["blueguardian", "bluegardian"], "erster_payout": False,
      "je_groesse": {"100000": {"dd": 8000, "sl": [1250, 1600], "lots": [1, 1.75], "ziel": [1000, 2000], "hedge_eur": 1000,
                                "gewinntage": {"tp": [550, 650], "min": 500, "anzahl": 3}}}}
FLEX = {"name": "Nano", "ab_dd_pct": 10, "consistency_pct": 50,
        "je_groesse": {"100000": {"ziel": [800, 1200], "sl": [1250, 1700], "lots": [1, 1.75], "hedge_eur": 500, "dd": 10000}}}
BGN = dict(copy.deepcopy(BG), flex=copy.deepcopy(FLEX))
MPPL, SPPL = 10.0, 0.9


def konto(dd, name="100k 700100 → Funded", **kw):
    return dict({"id": "00000000-0000-0000-0000-0000000000c1", "firm": "Blue Guardian", "account_type": "funded_cfd", "name": name,
                 "max_drawdown": dd}, **kw)


def rechne(regel, k, bal, seed=7, tage=None, gewinntage=None, zyklus=2):
    r = app.fcp_regel_konto(regel, k)
    g = app._wd_konto_groesse(k)
    return app.fcp_konto_rechnen(app.fcp_je_groesse(r, g), bal, g, zyklus, False, MPPL, SPPL, random.Random(seed), r,
                                 tage=tage, gewinntage=gewinntage)


def tw(w=0.0, b=0.0, serie=0.0, serie_n=0, heute=0.0):
    return {"w": w, "b": b, "serie": serie, "serie_n": serie_n, "heute": heute}


def main():
    V = app.fcp_regel_konto
    print("1 Erkennung")
    check(V(BGN, konto(10000)).get("flex_konto") is True, "Max DD 10.000 → Nano")
    check(V(BGN, konto(8000)) is BGN and V(BGN, konto(None)) is BGN, "8.000 / leer → Standard (Regel unverändert)")
    check(V(BGN, konto(10000, name="Blue Guardian Funded")) is BGN, "ohne Größe (kein „100k“, keine starting_balance) → Standard, nie raten")
    check(V(BGN, konto(10000, name="X", starting_balance=100000)).get("flex_konto") is True, "Größe aus starting_balance")
    check(V(BG, konto(10000)) is BG and V(None, konto(10000)) is None, "Firma ohne flex / ohne Regel → unverändert")
    rn = V(BGN, konto(10000))
    check(app.fcp_consistency_pct(rn) == 50.0 and app.fcp_consistency_pct(V(BGN, konto(8000))) is None, "Consistency 50 % nur für Nano")
    check("gewinntage" not in rn["je_groesse"]["100000"] and rn["je_groesse"]["100000"]["ziel"] == [800, 1200], "Nano: Ziel 800–1.200, keine Gewinntage")

    print("2 Nano-Plan (Consistency über fcp_cons_finn)")
    for seed in range(1, 31):
        w = rechne(BGN, konto(10000), 100000.0, seed, tage=tw())
        z = w.get("ziel", 0) - 100000
        ok = (w["aktion"] == "planen" and w["tp_art"] == "consistency" and 800 <= z <= 1200 and w["tp"] <= 0.5 * z * 0.95 + 1
              and 1250 <= w["sl"] <= 1700 and 1 <= w["lots"] <= 1.75 and abs(w["slave_risk"] / w["dd"] - 0.05) < 1e-6)
        if not ok or seed in (1, 2):
            check(ok, f"seed {seed}: Ziel {z:.0f}, TP {w.get('tp')} ({w.get('tp_art')}), SL {w.get('sl')}, Lots {w.get('lots')}, "
                      f"Hedge {w.get('slave_risk')} € / {w.get('dd')} $")
    w1 = rechne(BGN, konto(10000), 100475.0, 3, tage=tw(w=475, b=475, serie=475, serie_n=1))
    c1 = w1.get("consistency") or {}
    check(w1["aktion"] == "planen" and w1["tp"] <= 0.5 * c1.get("ende", 0) * 0.95 + 1 and c1.get("ende", 0) >= 475 / 0.5,
          f"2. Tag nach 475 $: Endziel {c1.get('ende')} ≥ 950 (größter Tag ≤ 50 %), TP {w1.get('tp')} ≤ Deckel {c1.get('deckel')}")
    w2 = rechne(BGN, konto(10000), 101000.0, 4, tage=tw(w=1000, b=480))
    check(w2["aktion"] == "ziel", f"1.000 $ Gewinn, größter Tag 480 → Ziel erreicht ({w2.get('grund')})")
    w3 = rechne(BGN, konto(10000), 101000.0, 4, tage=tw(w=1000, b=700))
    check(w3["aktion"] == "planen" and w3["tp_art"] == "consistency", f"1.000 $ Gewinn, größter Tag 700 (> 50 %) → weiter planen (TP {w3.get('tp')})")
    w4 = rechne(BGN, konto(10000), 100000.0, 5, tage=None)
    check(w4["aktion"] == "planen" and w4["tp"] <= 0.5 * (w4["ziel"] - 100000) * 0.95 + 1, f"Zyklus nicht lesbar → kleiner sicherer TP {w4.get('tp')}")

    print("3 Standard bitgleich mit und ohne flex")
    for bal, tage, gi in ((100000.0, tw(), (0, 3)), (100600.0, tw(600, 600), (1, 3)), (101700.0, tw(1700, 600), (3, 3)), (101000.0, None, None)):
        for seed in (1, 9):
            a1 = rechne(BG, konto(8000), bal, seed, tage=tage, gewinntage=gi)
            a2 = rechne(BGN, konto(8000), bal, seed, tage=tage, gewinntage=gi)
            check(a1 == a2, f"Standard {bal:,.0f} Gewinntage {gi} seed {seed}: gleich ({a1.get('aktion')} {a1.get('tp_art', '')})")
    a = rechne(BGN, konto(8000), 100000.0, 1, tage=tw(), gewinntage=(0, 3))
    check(a["tp_art"] == "gewinntag" and abs(a["slave_risk"] / a["dd"] - 0.125) < 1e-6, "Standard behält Gewinntage und Hedge 0,125 €/$")

    print("4 Radar-Ziel/Boden")
    zb = app.fcp_konto_ziel_boden(V(BGN, konto(10000)), 100000.0, 2, "100k 700100 → Funded")
    check(zb == (100800.0, 90000.0), f"Nano: Ziel ab 100.800, Boden 90.000 → {zb}")
    zs = app.fcp_konto_ziel_boden(V(BGN, konto(8000)), 100000.0, 2, "100k 700100 → Funded")
    check(zs == (101000.0, 92000.0), f"Standard: 101.000 / 92.000 → {zs}")

    print("5 alle Leser der Funded-Regel nehmen die Variante")
    src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
    fn = lambda n: src[src.index("\ndef " + n + "("):src.index("\ndef ", src.index("\ndef " + n + "(") + 5)]   # noqa: E731
    check("regel = fcp_regel_konto(regel, a)" in fn("fcp_planen"), "fcp_planen (Planer + Kontostand-Liste)")
    check(fn("fcp_planen").count("fcp_regel_konto(") >= 2, "fcp_planen: auch die Reiter-Zeile (dd)")
    z = fn("zw_funded_cfd")
    check(z.count("fcp_regel_konto(") == 2 and '+ ",max_drawdown"' in z, "zw_funded_cfd: Radar-Ziel + Gewinntage, liest max_drawdown")
    check("freg = fcp_regel_konto(" in fn("kz_rechnen") and "max_drawdown" in app.KZ_KONTO_SEL, "Konto-Seite kz_rechnen (KZ_KONTO_SEL hat max_drawdown)")
    check(",max_drawdown," in app.AP_KONTO_FELDER, "Planer-Konten lesen max_drawdown")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
