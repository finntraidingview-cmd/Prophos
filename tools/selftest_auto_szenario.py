#!/usr/bin/env python3
"""Selbsttest SZENARIO-KURVE (app.py ap_szenario_*, ap_umplanen, 08.10.2026, Slave-Terminal 3 — Finn 05:26 Dubai: „Der Bot muss neu
berechnen. Ich will, dass Long und Short im Ausgleich gleich sind und dass der P&L hypothetisch quasi immer über Null ist. Drei Apex-Konten
mit 5 NQ sind weg, wenn es 2.000 $ hochgeht … Der Bot guckt nur auf den Netto-Einsatz, der muss aber in Relation zu den Lots stehen").

Aufruf:  python3 tools/selftest_auto_szenario.py
Ohne Netz, Platzhalter-Werte. Geprüft: ein Trade linear / TP gedeckelt / SL normal / Klippe −Kontowert bei Polster bzw. Tageslimit /
gehedgt 0 / ohne Satz 0; Finns Lage (3× Apex short 5 NQ, Tageslimit 2.000 $ → Klippe bei +20 Pkt; 2× Blue Guardian long; The5%ers
short) → Kurve stürzt bei +20 senkrecht ab (Punktpaar), Steigung bei 0 negativ (netto short), schlimmster Fall rechts; der Bot zieht
den geplanten Long vor, der genau dort hilft, und nennt den schlimmsten Fall im Grund; ausgeglichenes Buch → nichts; Verteilung und
Mischung verschlechtern das Minimum nie."""
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = sd.lade()
    T, K, L = a["ap_szenario_trade"], a["ap_szenario_kurve"], a["ap_szenario_lage"]

    # ── 1 ein Trade ──────────────────────────────────────────────────────────────────────────────────────────────────────
    # Satz = Kontowert ÷ Polster (ap_kontowert): 180 € / 2.500 $ = 0,072 € je $ — das Tageslimit (2.000 $) liegt VOR dem Polster → Klippe
    S = 180.0 / 2500.0
    apex = {"richtung": "sell", "satz": S, "usd_pro_pkt": 100.0, "wert": 180.0, "polster_usd": 2500.0, "daily_usd": 2000.0,
            "tp_punkte": 40.0, "sl_punkte": None}
    check(abs(T(apex, -10) - S * 100 * 10) < 1e-6, "Short, NQ −10: linear Satz × $/Pkt × 10 = +72 €")
    check(abs(T(apex, -60) - S * 100 * 40) < 1e-6, "TP gedeckelt (40 Pkt)")
    check(abs(T(apex, 19) + S * 100 * 19) < 1e-6 and T(apex, 20) == -180.0,
          f"Klippe: Tageslimit 2.000 $ / 100 $/Pkt = 20 Pkt → −Kontowert 180 € ({T(apex, 19):.0f} → {T(apex, 20):.0f})")
    mit_sl = dict(apex, sl_punkte=10.0)
    check(abs(T(mit_sl, 15) + S * 100 * 10) < 1e-6, "SL vor der Klippe: normaler Verlust, kein Blow")
    check(T(dict(apex, gehedgt=True), 30) == 0.0 and T(dict(apex, satz=None), 30) == 0.0, "gehedgt → 0, ohne Satz → 0")
    check(abs(T(dict(apex, polster_usd=None, daily_usd=None), 30) + S * 100 * 30) < 1e-6, "ohne Polster/Tageslimit: linear, keine Klippe")

    # ── 2 Finns Lage ────────────────────────────────────────────────────────────────────────────────────────────────────────
    laufend = [dict(apex) for _ in range(3)]
    laufend += [{"richtung": "buy", "satz": 0.05, "usd_pro_pkt": 10.0, "wert": 500.0, "polster_usd": 5000.0, "daily_usd": None,
                 "tp_punkte": 120.0, "sl_punkte": None} for _ in range(2)]                               # 2× Blue Guardian long (CFD)
    laufend += [{"richtung": "sell", "satz": 0.1, "usd_pro_pkt": 5.0, "wert": 300.0, "polster_usd": 4000.0, "daily_usd": None,
                 "tp_punkte": 150.0, "sl_punkte": None}]                                                  # The5%ers short
    kurve = K(laufend)
    bei20 = [x for x in kurve if x["pkt"] == 20]
    check(len(bei20) == 2 and bei20[1]["eur"] < bei20[0]["eur"] - 100,
          f"Kurve: bei +20 Pkt zwei Punkte (senkrechter Sturz) {[x['eur'] for x in bei20]}")
    lage = L(laufend)
    check(lage["delta_eur_pkt"] < 0, f"Steigung bei 0 = {lage['delta_eur_pkt']} €/Pkt (netto short)")
    check(lage["rechts"]["eur"] < lage["links"]["eur"] and lage["rechts"]["pkt"] >= 20,
          f"schlimmster Fall rechts (steigender NQ) {lage['rechts']} vs links {lage['links']}")
    check(lage["min_eur"] < -100, f"min über ±30 Pkt = {lage['min_eur']} €")
    check(all(-100 <= x["pkt"] <= 100 for x in kurve) and [x["pkt"] for x in kurve] == sorted(x["pkt"] for x in kurve),
          "Kurve −100…+100, aufsteigend sortiert")

    # ── 3 Bot: zieht den Long vor, der bei +20 hilft ─────────────────────────────────────────────────────────────────────
    U = a["ap_umplanen"]
    Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
    jetzt = 200

    def plan(pid, uid, firma, richtung, start, **kw):
        p = {"plan_id": pid, "user_id": uid, "user": uid.capitalize(), "firma": firma, "firma_name": firma.capitalize(), "richtung": richtung,
             "start_min": float(start), "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "fest_durch": None, "auto_plan": True,
             "bestaetigt": True, "route": "tvv2", "satz_eur_je_usd": 0.08, "usd_pro_pkt": 40.0, "wert_eur": 900.0, "polster_usd": 3000.0,
             "daily_usd": None, "tp_punkte": 40.0, "sl_punkte": None}
        p.update(kw)
        return p
    plaene = [plan("tf_long", "chris", "tradeify", "buy", 420), plan("fn_short", "emin", "fundednext", "sell", 380)]
    EK = {"basis": 0.0, "brutto": 0.0, "gross_ab": 100000.0, "laufzeit": 60, "szenario_laufend": laufend}
    erg = U(plaene, 0.0, 0.0, jetzt, Z, 25, random.Random(1), einsatz=EK, dubai_min=120)
    v = [x for x in erg["aenderungen"] if x["art"] == "start"]
    check(len(v) == 1 and v[0]["plan_id"] == "tf_long" and v[0]["nach_start_min"] < 420,
          f"Bot zieht den geplanten Long vor ({[(x['plan_id'], x['nach_start_min']) for x in v]})")
    check(v and "schlimmster Fall" in v[0]["grund"], f"Grund nennt den schlimmsten Fall ({v[0]['grund'] if v else ''})")
    check(not any(x["plan_id"] == "fn_short" for x in erg["aenderungen"]), "der Short wird nicht vorgezogen")
    nach = L(laufend + [a["ap_szenario_trade_aus_zeile"](dict(plaene[0], richtung="buy"), False)])
    check(nach["min_eur"] > lage["min_eur"], f"min ±30 nach dem Zug {lage['min_eur']} → {nach['min_eur']} €")
    # ausgeglichen: Long und Short gleich groß ohne Klippe → nichts
    ruhig = [{"richtung": "sell", "satz": 0.09, "usd_pro_pkt": 100.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None},
             {"richtung": "buy", "satz": 0.09, "usd_pro_pkt": 100.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None}]
    e2 = U([dict(p) for p in plaene], 0.0, 0.0, jetzt, Z, 25, random.Random(1), einsatz=dict(EK, szenario_laufend=ruhig))
    check(not e2["aenderungen"], f"ausgeglichenes Buch (min ±30 = {L(ruhig)['min_eur']} €) → nichts")
    # Verteilung darf das Minimum nicht verschlechtern: zwei Longs derselben ID × Firma dicht, Schieben nach hinten nähme Schutz weg
    vt = [plan("l1", "chris", "tradeify", "buy", 205), plan("l2", "chris", "tradeify", "buy", 206)]
    e3 = U(vt, 0.0, 0.0, jetzt, Z, 25, random.Random(1), einsatz=EK, dubai_min=120)
    vor3 = L(laufend + [a["ap_szenario_trade_aus_zeile"](p, False) for p in vt])["min_eur"]
    neu3 = {x["plan_id"]: x["nach_start_min"] for x in e3["aenderungen"]}
    z3 = [dict(p, start_min=neu3.get(p["plan_id"], p["start_min"])) for p in vt]
    nach3 = L(laufend + [a["ap_szenario_trade_aus_zeile"](p, False) for p in z3 if p["start_min"] <= jetzt + 60])["min_eur"]
    check(nach3 >= vor3 - 1e-6, f"Verteilung verschlechtert den schlimmsten Fall nicht ({vor3} → {nach3} €, Züge {neu3})")

    # ── 4 keine Schwelle (Finn 08.10.2026): schon −30 € löst aus; ein Zug unter AP_SZENARIO_MIN_GEWINN_EUR Gewinn unterbleibt ────────
    klein = [{"richtung": "sell", "satz": 0.05, "usd_pro_pkt": 20.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None}]   # −1 €/Pkt
    e4 = U([plan("tf_long", "chris", "tradeify", "buy", 420, satz_eur_je_usd=0.05, usd_pro_pkt=20.0)], 0.0, 0.0, jetzt, Z, 25,
           random.Random(1), einsatz=dict(EK, szenario_laufend=klein), dubai_min=120)
    check(L(klein)["min_eur"] < 0 and len(e4["aenderungen"]) == 1,
          f"keine Schwelle: min ±30 = {L(klein)['min_eur']} € (über −100) löst trotzdem aus ({[x['plan_id'] for x in e4['aenderungen']]})")
    winzig = [{"richtung": "sell", "satz": 0.05, "usd_pro_pkt": 2.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None}]   # −0,1 €/Pkt
    e5 = U([plan("tf_long", "chris", "tradeify", "buy", 420, satz_eur_je_usd=0.05, usd_pro_pkt=0.2)], 0.0, 0.0, jetzt, Z, 25,
           random.Random(1), einsatz=dict(EK, szenario_laufend=winzig), dubai_min=120)
    check(not e5["aenderungen"], f"Gewinn am Minimum < {a['AP_SZENARIO_MIN_GEWINN_EUR']:g} € → kein Zug (Dämpfung, min {L(winzig)['min_eur']} €)")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
