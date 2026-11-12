#!/usr/bin/env python3
"""Selbsttest MP2 (Finn 12.11.2026: Muster-Portfolio unter Admin → Alle Accounts „alles zusammen mit Total“). app.py muster_portfolio_summe ohne Netz/DB:
Ziel/Stand nur über IDs, bei denen die Firma NICHT gesperrt ist; gesichert je ID auf ihr Ziel gedeckelt; fortschritt soll-gewichtet; Zählung IDs/gesperrt;
Firma bei allen gesperrt → status gesperrt ohne Prozent. Dazu Verdrahtung ?alle=1 und Frontend-Anker.
Aufruf:  python3 tools/selftest_mp2_muster_total.py"""
import os
import re

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {}
m = re.search(r"^def muster_portfolio_summe\(.*?(?=^[A-Za-z_@#])", app, re.S | re.M)
exec(m.group(0), ns)
S = ns["muster_portfolio_summe"]


def z(firma, status, soll, ges, fp, art="plus_ueber_start", reihe=1):
    return {"firma": firma, "status": status, "art": art, "typen": ["winning_days"], "einheit": "USD", "soll": soll, "gesichert": ges,
            "gesichert_pct": round(100 * min(1, ges / soll), 1) if soll else None, "fortschritt_pct": fp, "reihe": reihe}


daten = {
    "u1": [z("Tradeify", "frei", 20000, 18200, 95), z("Topstep", "gesperrt", 20000, 0, 0, reihe=2), z("The5%ers", "frei", 3, 3, 100, art="stueck", reihe=3)],
    "u2": [z("Tradeify", "frei", 20000, 30000, 100), z("Topstep", "gesperrt", 20000, 5000, 40, reihe=2), z("The5%ers", "frei", 3, 1, 50, art="stueck", reihe=3)],
    "u3": [z("Tradeify", "gesperrt", 20000, 9000, 60), z("Topstep", "gesperrt", 20000, 0, 0, reihe=2), z("The5%ers", "frei", 3, 0, None, art="stueck", reihe=3)],
}
out = {f["firma"]: f for f in S(daten, {"u1": "Marc", "u2": "Mike", "u3": "Chris"})}
t = out["Tradeify"]
check(t["soll"] == 40000 and t["gesichert"] == 38200 and t["gesichert_roh"] == 48200, f"1 Tradeify: Ziel nur frei (2 IDs), gesichert gedeckelt 18,2k + 20k ({t['soll']}, {t['gesichert']}, {t['gesichert_roh']})")
check(t["gesichert_pct"] == 95.5 and t["fortschritt_pct"] == 97.5, f"2 Tradeify: gesichert 95,5 %, Fortschritt soll-gewichtet 97,5 % ({t['gesichert_pct']}, {t['fortschritt_pct']})")
check(t["ids_n"] == 2 and t["gesperrt_n"] == 1 and t["status"] == "frei", "3 Tradeify: 2 IDs frei, 1 gesperrt")
check([x["name"] for x in t["je_id"]] == ["Marc", "Mike", "Chris"] and t["je_id"][-1]["status"] == "gesperrt", "4 je_id: freie zuerst nach Name, gesperrte unten")
tp = out["Topstep"]
check(tp["status"] == "gesperrt" and tp["soll"] == 0 and tp["gesichert_pct"] is None and tp["fortschritt_pct"] is None and tp["gesperrt_n"] == 3, "5 Topstep bei allen gesperrt → gesperrt, ohne Prozent")
f5 = out["The5%ers"]
check(f5["soll"] == 9 and f5["gesichert"] == 4 and f5["gesichert_pct"] == 44.4 and f5["ids_n"] == 3, f"6 The5%ers Stück: 4/9 ({f5['gesichert']}/{f5['soll']}, {f5['gesichert_pct']})")
check(f5["fortschritt_pct"] >= f5["gesichert_pct"], "7 Fortschritt nie unter gesichert (ID ohne fortschritt zählt mit gesichert_pct)")
check([f["firma"] for f in S(daten)] == ["Tradeify", "Topstep", "The5%ers"], "8 Reihenfolge wie die Ziele (reihe)")
check(S({}) == [], "9 leer → []")
check('if request.args.get("alle") == "1":\n        return _mp_alle_antwort()' in app and 'erg = vorrat2_rechnen_lauf("hand")' in app, "10 ?alle=1 → ein Lauf über alle IDs der Sicht")
check('k[0] == "__alle__"' in app, "11 Sperre umschalten leert auch den Total-Merker")
check("alle=1&ansicht=admin" in html and 'id="mp-total"' in html, "12 Frontend: Total-Karte unter Admin → Alle Accounts lädt ?alle=1")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
