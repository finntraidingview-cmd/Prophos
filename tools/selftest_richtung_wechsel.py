#!/usr/bin/env python3
"""Selbsttest RICHTUNG JE ID × FIRMA GEMISCHT (app.py ap_richtung_bloecke / ap_fest_am_start / ap_id_firma_einseitig /
ap_richtungen_delta / ap_richtung_konflikte, 09.10.2026, Slave-Terminal 4 — Finn ~03:00 Dubai zu Admin → Trade-Planer: je ID × Firma
alle Trades des Tages in EINER Richtung, „Genau das will ich ja vermeiden … Der erste Tradeify geht long, ist beendet, eine Stunde
später kann z. B. einer short gehen"; ~03:45 nachgeschärft: „Mach diese 90-Minuten-Regel weg … Zufallsprinzip. Es darf halt nur
nie gleichzeitig sein"). Regel: Richtung je Trade frei (AP_RICHTUNG_WECHSEL_MIN = 0), Strafe „ID × Firma ganz einseitig" mischt; nur
laufende bzw. geclaimte Trades legen Teile in den 90 min nach ihrem Start fest; geplante nie. Platzhalter-IDs, ohne Netz. Aufruf: python3 tools/selftest_richtung_wechsel.py"""
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
    check(a["AP_RICHTUNG_WECHSEL_MIN"] == 0 and a["AP_RICHTUNG_LAUF_FEST_MIN"] == 90,
          "keine Blöcke mehr (Finn ~03:45: 90-Minuten-Regel weg), laufende/geclaimte legen 90 min fest")

    def T(start, gruppe, user="c", firma="fundednext", fest=None, delta=1.0):
        return {"fest": fest, "user": user, "firma": firma, "start": start, "delta_abs": delta, "gruppe": gruppe}

    # 1 jeder Teil eigener Block
    chris = {f"c|fn#{i + 1}": T(hm(s_), "c|fn") for i, s_ in enumerate(("07:11", "14:34", "17:55"))}
    check(len(set(B(chris).values())) == 3, "Chris FN 07:11 / 14:34 / 17:55 → drei freie Teile")
    nah = {"c|fn#1": T(hm("10:51"), "c|fn"), "c|fn#2": T(hm("10:56"), "c|fn"), "c|fn#3": T(hm("10:57"), "c|fn")}
    check(len(set(B(nah).values())) == 3, "10:51 / 10:56 / 10:57 (Finns Beispiel) → drei freie Teile")

    # 2 Zuteilung: frei je Trade, Strafe „ganz einseitig" mischt
    gem_c = gem_n = 0
    for s_ in range(12):
        r, _m, w = R(chris, 0.0, 0.0, random.Random(s_), 50, mit_wert=True)
        gem_c += len({r[k] for k in chris}) == 2
        r2, _m2 = R(nah, 0.0, 0.0, random.Random(s_), 50)
        gem_n += len({r2[k] for k in nah}) == 2
    check(gem_c == 12, f"Chris FN: jede Zuteilung hat beide Richtungen ({gem_c}/12)")
    check(gem_n == 12, f"Teile 5 min / 1 min auseinander dürfen gegenläufig geplant sein ({gem_n}/12 gemischt)")
    bl = B(chris)
    check(E({"c|fn#1": "buy", "c|fn#2": "buy", "c|fn#3": "buy"}, chris, bl) == 1
          and E({"c|fn#1": "buy", "c|fn#2": "sell", "c|fn#3": "buy"}, chris, bl) == 0
          and E({"c|fn#1": "buy"}, {"c|fn#1": chris["c|fn#1"]}, bl) == 0, "Strafe nur bei ≥ 2 Teilen ganz einseitig")

    # 3 fest: nur laufende/geclaimte, 90 min ab ihrem Start
    lauf = [(600.0, "buy", True)]
    check(F(lauf, 645) == "buy" and F(lauf, 720) is None, "läuft BUY 10:00 → Teil 10:45 BUY, Teil 12:00 frei")
    check(F([(600.0, "sell", False)], 605) is None and F([(None, "buy", False)], 900) is None,
          "geplante Pläne (auch ohne Startzeit) legen nichts fest")
    check(F([(None, "buy", True)], 10) == "buy", "laufend ohne Bezugsminute → fest")
    ref = a["_ap_fest_ref"]
    from datetime import datetime, timezone
    mn = datetime(2026, 10, 9, 0, 0, tzinfo=timezone.utc)
    jetzt = datetime(2026, 10, 9, 10, 5, tzinfo=timezone.utc)
    gc = {"status": "planned", "richtung": "sell", "start_um": "2026-10-09T10:00:00+00:00", "start_um_gestartet_at": "2026-10-09T10:00:05+00"}
    check(ref(gc, mn, jetzt) == (600.0, "sell", True), "frisch geclaimter Plan (5 min) = läuft (Bezug: sein Start)")
    # LEICHEN (Prüfer Slave 2, 09.10.2026: live 3 geclaimte Start-Fehler-Pläne, ältester vom 07.10.) — sperren nichts
    alt = dict(gc, start_um="2026-10-07T08:00:00+00:00", start_um_gestartet_at="2026-10-07T08:00:04+00")
    check(ref(alt, mn, jetzt)[2] is False and not a["ap_claim_laeuft"](alt, jetzt), "alte geclaimte Leiche (07.10.) = legt nichts fest")
    check(not a["ap_claim_laeuft"](dict(gc, start_um_gestartet_at="2026-10-09T09:45:00+00"), jetzt), "Claim 20 min alt → zählt nicht mehr (> 15 min)")
    check(not a["ap_claim_laeuft"](dict(gc, start_fehler={"status": "rot"}), jetzt)
          and not a["ap_claim_laeuft"](dict(gc, start_fehler={"status": "tagesende"}), jetzt)
          and a["ap_claim_laeuft"](dict(gc, start_fehler={"status": "behoben"}), jetzt), "frischer Claim mit offenem Start-Fehler zählt nicht, behoben schon")
    check(a["ap_claim_laeuft"]({"orbit_gesendet_at": "2026-10-09T10:01:00+00:00"}, jetzt), "gesendet (orbit_gesendet_at) frisch = läuft")
    check(ref({"status": "planned", "richtung": "sell", "start_um": "2026-10-09T10:00:00+00:00"}, mn, jetzt)[2] is False, "bloß geplant = legt nichts fest")
    # 09.10.2026 ~09:25 (Finn: „Gegenrichtung ist verboten", Topstep 333d4791 BUY gegen d369e8d5 SELL derselben ID): LÄUFT = fest ohne Fenster
    lf = ref({"status": "open", "richtung": "sell", "started_at": "2026-10-09T05:19:32+00:00"}, mn, jetzt)
    check(lf == (None, "sell", True) and F([lf], 1400) == "sell" and F([lf], 330) == "sell",
          "laufender Trade (open) legt die Richtung für den ganzen Tag fest, solange er läuft (kein 90-min-Fenster)")
    tf = dict(chris)
    tf["c|fn#1"] = dict(tf["c|fn#1"], fest="sell")
    r, _ = R(tf, 0.0, 0.0, random.Random(3), 50)
    check(r["c|fn#1"] == "sell" and len({r[k] for k in tf}) == 2, f"fester Teil bleibt, die anderen frei und gemischt ({r})")

    # 4 Bot (ap_richtung_konflikte): nur laufende/geclaimte, 90 min
    K = a["ap_richtung_konflikte"]

    def plan(pid, start, r="sell", **kw):
        return dict({"plan_id": pid, "user_id": "u1", "user": "U1", "firma": "fundednext", "firma_name": "FundedNext", "richtung": r,
                     "start_min": start, "route": "mt5v2", "gehedgt": False, "auto_plan": True, "bestaetigt": False, "aenderbar": True,
                     "fest_durch": None}, **kw)
    offen = [{"user_id": "u1", "firma": "fundednext", "richtung": "buy", "start_min": 600.0}]
    check([x["plan_id"] for x in K([plan("p1", 645)], offen, 620)["drehen"]] == ["p1"], "läuft BUY 10:00, Auto-Plan SELL 10:45 → gedreht")
    e2 = K([plan("p2", 700)], offen, 650)
    # seit 09.10.2026 ~09:25 (Finn: „Gegenrichtung ist verboten"): ein LAUFENDER Trade legt fest, solange er läuft — kein 90-min-Fenster mehr
    check([x["plan_id"] for x in e2["drehen"]] == ["p2"], "läuft BUY 10:00 (noch offen), Auto-Plan SELL 11:40 → gedreht (solange er läuft)")
    e4 = K([plan("q", 600, "buy", bestaetigt=True), plan("p4", 605)], [], 590)
    check(not e4["drehen"] and not e4["markieren"], "geplanter BUY 10:00, Auto-Plan SELL 10:05 → beide bleiben (nur nie gleichzeitig)")
    e5 = K([plan("q", 600, "buy", bestaetigt=True, fest_durch="schon gestartet"), plan("p5", 605)], [], 601)
    check([x["plan_id"] for x in e5["drehen"]] == ["p5"], "geclaimter BUY 10:00 (Start läuft), Auto-Plan SELL 10:05 → gedreht")
    e6 = K([plan("q", 600, "buy", bestaetigt=True, fest_durch="schon gestartet", start_fehler={"status": "rot"}), plan("p6", 605)], [], 601)
    check(not e6["drehen"] and not e6["markieren"], "geclaimte Start-Fehler-Leiche BUY → Auto-Plan SELL bleibt")

    # 5 Quelltext
    src = open(sd.APP, encoding="utf-8").read()
    seg = src[src.index("\ndef ap_planen("):src.index("\n\n\n", src.index("\ndef ap_planen("))]
    check('"fest": ap_fest_am_start(tr_info[key]["fest_refs"], minuten_w[key])' in seg and "wert_w[:6]" in seg,
          "ap_planen: fest je Teil am gewürfelten Start, Abbruch prüft 6 Felder (mit ID × Firma einseitig)")
    check('"start_min": z.get("start_min")' in src and 'z["start_min"] = round((_sm - mitternacht)' in src,
          "Bot bekommt die Startminute laufender Trades")

    # 6 Frontend: nur laufende/geclaimte zählen, Start-Wächter verschiebt Auto-Pläne zuerst
    html = open(os.path.join(os.path.dirname(sd.APP), "prophos.html"), encoding="utf-8").read()
    check("const RK_CLAIM_FRISCH_MS = 15 * 60000" in html
          and "Date.now() - Date.parse(geclaimt) <= RK_CLAIM_FRISCH_MS && !(sf && sf.status !== 'behoben'))" in html
          and "const zaehlt = rkZaehlt(p.status, p.geclaimt, p.sf)" in html and "if(!zaehlt && !geplantHand) continue" in html
          and "!!(o && o.geplanteHand)" in html   # 09.10.2026: geplante Hand-/WD-Pläne zählen NUR im Plan-Popup (geplanteHand)
          and "if(!rkZaehlt(p.status, rkClaimAt(p.startUmGestartetAt, p.orbitGesendetAt), p.mt5Baseline && p.mt5Baseline.start_fehler)) continue" in html
          and "else if(zaehlt && p.geclaimt) lauf[seite].push({ name: p.name, firm: p.firm, verb: 'startet gerade' })" in html
          and "select('id,status,richtung,master_firm,master_name,start_um_gestartet_at,orbit_gesendet_at,start_fehler:mt5_baseline->start_fehler'" in html,
          "Richtungs-Prüfungen: nur laufende und FRISCH geclaimte ohne Start-Fehler zählen, bloß geplante und Leichen nie (außer Plan-Popup: Hand/WD/V3 von heute)")
    check("RK_WECHSEL_MIN" not in html and "rkPlanNah" not in html, "kein 90-min-Fenster mehr im Frontend")
    vs = html[html.index("  async function rkVorStart(plan){"):html.index("  window._rk = {")]
    check("if(plan.autoPlan && k.quelle === 'lauf'){" in vs
          and vs.index("await rkVerschieben(plan, k, false, 'start')") < vs.index(".update({ richtung: ziel })")
          and "n < RK_VERSCHIEBEN_MAX" in vs and "const RK_VERSCHIEBEN_MAX = 3" in html,
          "Start-Wächter: Auto-Plan bei laufender Gegenrichtung erst bis 3× verschieben, dann drehen")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
