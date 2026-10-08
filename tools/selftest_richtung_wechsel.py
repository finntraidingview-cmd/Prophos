#!/usr/bin/env python3
"""Selbsttest RICHTUNG JE ID × FIRMA GEMISCHT (app.py ap_richtung_bloecke / ap_fest_am_start / ap_id_firma_einseitig /
ap_richtungen_delta / ap_richtung_konflikte, 09.10.2026, Slave-Terminal 4 — Finn ~03:00 Dubai zu Admin → Trade-Planer: je ID × Firma
alle Trades des Tages in EINER Richtung, „Genau das will ich ja vermeiden … Der erste Tradeify geht long, ist beendet, eine Stunde
später kann z. B. einer short gehen"). Regel: Teile derselben ID × Firma dürfen gegenläufig sein, wenn ihre Starts ≥ 90 min
auseinander liegen (AP_RICHTUNG_WECHSEL_MIN); dichtere Teile = ein Block = eine Richtung. Ein laufender/geplanter Trade legt nur
Teile in seiner Nähe fest. Platzhalter-IDs, ohne Netz. Aufruf: python3 tools/selftest_richtung_wechsel.py"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def hm(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def main():
    a = sd.lade()
    B, F, E, R = a["ap_richtung_bloecke"], a["ap_fest_am_start"], a["ap_id_firma_einseitig"], a["ap_richtungen_delta"]
    check(a["AP_RICHTUNG_WECHSEL_MIN"] == 90, "Wechsel-Abstand 90 min")

    def T(start, gruppe, user="c", firma="fundednext", fest=None, delta=1.0):
        return {"fest": fest, "user": user, "firma": firma, "start": start, "delta_abs": delta, "gruppe": gruppe}

    # 1 Blöcke
    chris = {f"c|fn#{i + 1}": T(hm(s), "c|fn") for i, s in enumerate(("07:11", "14:34", "17:55"))}
    bl = B(chris)
    check(len(set(bl.values())) == 3, f"Chris FN 07:11 / 14:34 / 17:55 → drei Blöcke ({sorted(set(bl.values()))})")
    dicht = {"c|fn#1": T(600, "c|fn"), "c|fn#2": T(630, "c|fn")}
    check(len(set(B(dicht).values())) == 1, "zwei Teile 30 min auseinander → ein Block")
    kette = {"k#1": T(600, "k"), "k#2": T(680, "k"), "k#3": T(760, "k")}
    check(len(set(B(kette).values())) == 1, "Kette 600/680/760 (je 80 min) → ein Block, auch wenn Anfang und Ende 160 min auseinander")
    check(len(set(B({"x#1": T(600, "x"), "x#2": T(690, "x")}).values())) == 2, "genau 90 min → zwei Blöcke")
    check(B({"a#1": T(600, "a"), "b#1": T(610, "b")})["a#1"] != B({"a#1": T(600, "a"), "b#1": T(610, "b")})["b#1"],
          "andere ID × Firma = eigener Block")

    # 2 ap_richtungen_delta: gemischt erlaubt / Block gleich
    beide, gleich = 0, True
    for s in range(12):
        r, _m, w = R(chris, 0.0, 0.0, random.Random(s), 50, mit_wert=True)
        beide += len({r[k] for k in chris}) == 2
        r2, _m2 = R(dicht, 0.0, 0.0, random.Random(s), 50)
        gleich = gleich and r2["c|fn#1"] == r2["c|fn#2"]
    check(beide == 12, f"Chris FN (≥ 90 min): jede Zuteilung hat beide Richtungen ({beide}/12)")
    check(gleich, "zwei Teile 30 min auseinander: immer gleich gerichtet")
    check(E({"c|fn#1": "buy", "c|fn#2": "buy", "c|fn#3": "buy"}, chris, bl) == 1
          and E({"c|fn#1": "buy", "c|fn#2": "sell", "c|fn#3": "buy"}, chris, bl) == 0
          and E({"c|fn#1": "buy", "c|fn#2": "buy"}, dicht, B(dicht)) == 0, "Strafe nur, wenn ≥ 2 Blöcke ganz einseitig")

    # 3 fest in der Nähe
    lauf = [(600.0, "buy", True)]
    check(F(lauf, 645) == "buy" and F(lauf, 720) is None, "läuft BUY 10:00 → Teil 10:45 BUY, Teil 12:00 frei")
    gep = [(600.0, "sell", False)]
    check(F(gep, 560) == "sell" and F(gep, 650) == "sell" and F(gep, 500) is None and F(gep, 700) is None,
          "geplanter SELL 10:00 → ±90 min fest, weiter weg frei")
    check(F([(None, "buy", False)], 1200) == "buy", "geplant ohne Startzeit → vorsichtshalber den ganzen Tag")
    check(F([(600.0, "buy", True), (700.0, "sell", False)], 690) == "sell", "zwei Bezüge → der nächste gilt")
    tf = dict(chris)
    tf["c|fn#1"] = dict(tf["c|fn#1"], fest="sell")
    nah = dict(chris, **{"c|fn#2": T(hm("08:00"), "c|fn")})          # 07:11 fest sell, 08:00 im selben Block
    for s in range(6):
        r, _ = R(tf, 0.0, 0.0, random.Random(s), 50)
        r_n, _ = R(dict(nah, **{"c|fn#1": dict(nah["c|fn#1"], fest="sell")}), 0.0, 0.0, random.Random(s), 50)
        if not (r["c|fn#1"] == "sell" and r_n["c|fn#2"] == "sell"):
            break
    else:
        r = None
    check(r is None, "fester Teil hält seinen Block (08:00 bei festem 07:11 sell), andere Blöcke frei")
    check(len({R(tf, 0.0, 0.0, random.Random(3), 50)[0][k] for k in tf}) == 2, "trotz festem SELL am Morgen: später BUY möglich")

    # 4 Bot (ap_richtung_konflikte): gleiche 90-min-Regel
    K = a["ap_richtung_konflikte"]

    def plan(pid, start, r="sell", **kw):
        return dict({"plan_id": pid, "user_id": "u1", "user": "U1", "firma": "fundednext", "firma_name": "FundedNext", "richtung": r,
                     "start_min": start, "route": "mt5v2", "gehedgt": False, "auto_plan": True, "bestaetigt": False, "aenderbar": True,
                     "fest_durch": None}, **kw)
    offen = [{"user_id": "u1", "firma": "fundednext", "richtung": "buy", "start_min": 600.0}]
    e1 = K([plan("p1", 645)], offen, 620)
    e2 = K([plan("p2", 700)], offen, 650)
    check([x["plan_id"] for x in e1["drehen"]] == ["p1"], "läuft BUY 10:00, Auto-Plan SELL 10:45 → gedreht (wie bisher)")
    check(not e2["drehen"] and not e2["markieren"], "läuft BUY 10:00, Auto-Plan SELL 11:40 → bleibt (Start-Wächter verschiebt, falls nötig)")
    e3 = K([plan("p3", 645)], [{"user_id": "u1", "firma": "fundednext", "richtung": "buy"}], 620)
    check([x["plan_id"] for x in e3["drehen"]] == ["p3"], "laufender Trade ohne Startminute → wie bisher (immer)")
    e4 = K([plan("q", 600, "buy", bestaetigt=True), plan("p4", 650)], [], 640)
    e5 = K([plan("q", 600, "buy", bestaetigt=True), plan("p5", 700)], [], 660)
    check([x["plan_id"] for x in e4["drehen"]] == ["p4"] and not e5["drehen"],
          f"vorher geplanter BUY 10:00: SELL 10:50 gedreht, SELL 11:40 bleibt ({[x['plan_id'] for x in e4['drehen'] + e5['drehen']]})")
    e6 = K([plan("q", 600, "buy", bestaetigt=True), plan("p6", 650), plan("p7", 700)], [], 645)
    check([x["plan_id"] for x in e6["drehen"]] == ["p6", "p7"], "Kette: gedrehter 10:50 hält 11:40 (50 min) im selben Block")

    # 5 Quelltext: Planer nimmt die Bezüge je Wurf, Abbruch mit dem neuen Feld
    src = open(sd.APP, encoding="utf-8").read()
    seg = src[src.index("\ndef ap_planen("):src.index("\n\n\n", src.index("\ndef ap_planen("))]
    check('"fest": ap_fest_am_start(tr_info[key]["fest_refs"], minuten_w[key])' in seg and "wert_w[:6]" in seg,
          "ap_planen: fest je Teil am gewürfelten Start, Abbruch prüft 6 Felder (mit ID × Firma einseitig)")
    check('"start_min": z.get("start_min")' in src and 'z["start_min"] = round((_sm - mitternacht)' in src,
          "Bot bekommt die Startminute laufender Trades")

    # 6 Frontend (prophos.html): geplante Pläne nur in der Nähe, Start-Wächter verschiebt Auto-Pläne zuerst
    html = open(os.path.join(os.path.dirname(sd.APP), "prophos.html"), encoding="utf-8").read()
    check("const RK_WECHSEL_MIN = 90" in html and "if(!rkPlanNah(p.status, p.start, bezug > 0 ? bezug : null)) continue" in html
          and "if(!rkPlanNah(p.status, p.startUm, bezugMs)) continue" in html, "Richtungs-Prüfungen: geplante Pläne nur ±90 min um den Bezug")
    check(html.count("frisch: true, start: Date.now() })") == 2 and html.count("firmGeplanteRichtungen(plan.masterFirm, plan.id, Date.now())") == 3,
          "harte Prüfungen vor der Order (Echo-V2-Check, Puls) mit Bezug jetzt — laufende Trades zählen weiter immer")
    vs = html[html.index("  async function rkVorStart(plan){"):html.index("  window._rk = {")]
    check("frisch: true, start: plan.startUm || Date.now() })" in vs and "if(plan.autoPlan && k.quelle === 'lauf'){" in vs
          and vs.index("await rkVerschieben(plan, k, false, 'start')") < vs.index(".update({ richtung: ziel })")
          and "n < RK_VERSCHIEBEN_MAX" in vs and "const RK_VERSCHIEBEN_MAX = 3" in html,
          "Start-Wächter: Auto-Plan bei laufender Gegenrichtung erst bis 3× verschieben, dann drehen")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
