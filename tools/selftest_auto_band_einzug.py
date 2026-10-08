#!/usr/bin/env python3
"""Selbsttest EIN ZUG JE PLAN + PC-TAB LEBT IM BAND-SCHRITT (app.py ap_umplanen, _ap_zug_nach_vorn, 08.10.2026, Slave-Terminal 3 —
Master, Befund Slave 2 zum Lauf 02:23:16 UTC: der Band-Schritt schob Mike Topstep 57b69317 im selben Lauf zweimal, 02:43 → 02:51 →
02:59 UTC, obwohl Mikes PC tot war).

Aufruf:  python3 tools/selftest_auto_band_einzug.py
Ohne Netz, Platzhalter-IDs. Geprüft: 400 Zufallslagen (Einsatz-Modus, Band offen, mit/ohne Richtungsschutz) — kein Plan erscheint in
einem Lauf zweimal in den Änderungen (Gegenprobe beim Bau: der Stand 47a7dfe drehte bzw. schob in 3 dieser Lagen denselben Plan zweimal);
Band-Schritt nimmt keine Tranche einer ID mit totem PC-Tab (pc_lebt ohne die ID → nichts, mit der ID → Drehung, None → wie bisher);
Rückfall: ein vom Band-Schritt nach VORN gelegter Plan zählt wie „vorgezogen" (_ap_zug_nach_vorn) und fällt ungeclaimt nach
AP_VORZIEHEN_RUECKFALL_MIN auf seine alte Zeit zurück; nach hinten / Verteilung zählen nicht."""
import collections
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


def plan(pid, uid, firma, start, richtung="buy", **kw):
    return dict({"plan_id": pid, "user_id": uid, "user": uid.capitalize(), "firma": firma, "firma_name": firma, "richtung": richtung,
                 "start_min": float(start), "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "fest_durch": None,
                 "auto_plan": True, "bestaetigt": True, "route": "tvv2"}, **kw)


def main():
    a = sd.lade()
    U = a["ap_umplanen"]
    Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}

    # ── 1 ein Zug je Plan und Lauf (Zufallslagen) ─────────────────────────────────────────────────────────────────────────────
    R = random.Random(7)
    doppelt, zuege, beispiel = 0, 0, None
    for _fall in range(400):
        ids, firmen = ["u-a", "u-b", "u-c", "u-d"], ["topstep", "fundednext", "tradeify", "apex"]
        pl, fest = [], {}
        for k in range(R.randint(2, 6)):
            u, f = R.choice(ids), R.choice(firmen)
            r = fest.get(f"{u}|{f}", {}).get("richtung") or R.choice(["buy", "sell"])   # eine Richtung je ID × Firma
            fest[f"{u}|{f}"] = {"richtung": r}
            pl.append(plan(f"p{k}", u, f, R.randint(25, 700), r, einsatz_abs=float(R.choice([100, 300, 500, 800]))))
        fe = fest if R.random() < 0.7 else {}
        ek = {"basis": float(R.choice([-800, -500, 500, 800])), "brutto": 1000.0, "gross_ab": 300.0, "laufzeit": 60}
        e = U(pl, 0.0, 0.0, 20, Z, 25, random.Random(R.randint(1, 10 ** 6)), id_fest=fe, einsatz=ek)
        c = collections.Counter(x["plan_id"] for x in e["aenderungen"])
        zuege += len(e["aenderungen"])
        if any(v > 1 for v in c.values()):
            doppelt += 1
            beispiel = beispiel or [(x["plan_id"], x["art"], x["von_start_min"], x["nach_start_min"]) for x in e["aenderungen"]]
    check(doppelt == 0, f"400 Zufallslagen: kein Plan zweimal im selben Lauf (doppelt {doppelt}{', z. B. ' + str(beispiel) if beispiel else ''})")
    check(zuege > 100, f"der Bot arbeitet trotzdem ({zuege} Züge in 400 Lagen)")

    # ── 2 Band-Schritt nur für IDs mit lebendem PC-Tab ────────────────────────────────────────────────────────────────────────
    d = lambda h, m: h * 60 + m - 120     # noqa: E731
    pb = [dict(plan("a_ap", "u-a", "apex", d(9, 0), "buy"), delta_abs=5.0, einsatz_abs=0.0, bestaetigt=False)]
    ohne = U(pb, 6.0, 6.0, d(8, 30), Z, 15, random.Random(1))
    tot = U(pb, 6.0, 6.0, d(8, 30), Z, 15, random.Random(1), pc_lebt={"u-x"})
    lebt = U(pb, 6.0, 6.0, d(8, 30), Z, 15, random.Random(1), pc_lebt={"u-a"})
    check(ohne["aenderungen"] and lebt["aenderungen"] and not tot["aenderungen"],
          f"PC-Tab tot → Band-Schritt lässt die Tranche stehen ({len(tot['aenderungen'])}), lebt/ohne Quelle → Zug "
          f"({len(lebt['aenderungen'])}/{len(ohne['aenderungen'])})")
    pv = [dict(plan("m_ts", "u-m", "topstep", d(8, 50), "sell"), delta_abs=5.0, einsatz_abs=0.0, bestaetigt=False)]
    fv = {"u-m|topstep": {"richtung": "sell"}}                       # Richtung fest → nur Verschieben möglich
    sv_lebt = U(pv, -6.0, 6.0, d(8, 30), Z, 15, random.Random(3), id_fest=fv, pc_lebt={"u-m"})
    sv_tot = U(pv, -6.0, 6.0, d(8, 30), Z, 15, random.Random(3), id_fest=fv, pc_lebt=set())
    check([x["art"] for x in sv_lebt["aenderungen"]] == ["start"] and not sv_tot["aenderungen"],
          f"Mikes Fall: Verschieben nur mit lebendem PC ({[x['art'] for x in sv_lebt['aenderungen']]} / {len(sv_tot['aenderungen'])})")

    # ── 3 Rückfall auch für Band-Schritt-Züge nach vorn ───────────────────────────────────────────────────────────────────────
    vorn = a["_ap_zug_nach_vorn"]
    band = "Netto-Einsatz in den nächsten 60 min bis 429 € über dem Band ±25 %: Tranche Topstep 04:51 → 04:43 im eigenen Fenster (max |Netto| …)"
    check(vorn("Ausgleich: Long vorgezogen, Moritz Tradeify 12:30 → 07:14 Dubai (…)", 510, 194), "„Ausgleich: … vorgezogen“ zählt")
    check(vorn(band, 171, 163) and not vorn(band, 163, 171), "Band-Schritt-Tranche: nach vorn zählt, nach hinten nicht")
    check(not vorn("Verteilung: Chris Topstep 18:13 → 18:29 Dubai — einzeln starten", 853, 869) and not vorn(band, None, 163),
          "Verteilung und Zeile ohne Zeiten zählen nicht")
    stand = {"jetzt_min": 170.0, "geplant": [{"plan_id": "m_ts", "start_min": 163.0, "geclaimt": False},
                                              {"plan_id": "x", "start_min": 163.0, "geclaimt": True}]}
    vp = a["_ap_verpufft"](stand, {"m_ts": (171.0, 163.0), "x": (171.0, 163.0)})
    check(vp == [{"plan_id": "m_ts", "alt_min": 171.0}], f"ungeclaimt ≥ {a['AP_VORZIEHEN_RUECKFALL_MIN']} min über der vorgelegten Zeit → Rückfall, geclaimt nicht ({vp})")
    rf = U([dict(plan("m_ts", "u-m", "topstep", 163, "sell"), delta_abs=0.0, einsatz_abs=0.0)], 0.0, 0.0, 150, Z, 15, random.Random(1),
           verpufft=[{"plan_id": "m_ts", "alt_min": 171.0}], pc_lebt=set())
    check([(x["plan_id"], x["nach_start_min"], x.get("rueckfall")) for x in rf["aenderungen"]] == [("m_ts", 171.0, True)],
          f"ap_umplanen legt ihn zurück auf die alte Zeit, auch bei totem PC, genau ein Zug ({[(x['plan_id'], x['nach_start_min']) for x in rf['aenderungen']]})")

    # ── 4 PC-Tab tot = Phantom: zählt nicht im Band/Szenario, wird nie bewegt (Master 08.10.2026, Slave 1: „429 € über dem Band", teils Phantom) ──
    EK = {"basis": 0.0, "brutto": 1000.0, "gross_ab": 100000.0, "laufzeit": 60}
    ph = [plan("m_ts", "u-m", "topstep", 40, "sell", einsatz_abs=900.0, delta_abs=5.0),
          plan("c_fn", "u-c", "fundednext", 300, "buy", einsatz_abs=100.0)]
    mit = U(ph, 0.0, 0.0, 20, Z, 25, random.Random(1), einsatz=EK, pc_lebt={"u-m", "u-c"})
    ohne_m = U(ph, 0.0, 0.0, 20, Z, 25, random.Random(1), einsatz=EK, pc_lebt={"u-c"})
    check(mit["vorher"]["ueber_band"] > 0 and mit["aenderungen"], f"PC lebt: Mikes Short zählt (über Band {mit['vorher']['ueber_band']} €), Bot greift ein")
    check(ohne_m["vorher"]["ueber_band"] == 0 and not ohne_m["aenderungen"],
          f"PC tot: Mikes Short ist Phantom — über Band {ohne_m['vorher']['ueber_band']} €, keine Züge ({len(ohne_m['aenderungen'])})")
    lauf = [{"richtung": "buy", "satz": 0.05, "usd_pro_pkt": 100.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None}]
    s_tot = U(ph, 0.0, 0.0, 20, Z, 25, random.Random(1), einsatz=dict(EK, szenario_laufend=lauf), pc_lebt={"u-c"},
              id_fest={"u-c|fundednext": {"richtung": "buy"}})
    check(not any(x["plan_id"] == "m_ts" for x in s_tot["aenderungen"]),
          f"Szenario-Modus: Mikes Plan wird bei totem PC nie bewegt ({[(x['plan_id'], x['art']) for x in s_tot['aenderungen']]})")
    bewegt, zuege_l = 0, 0
    for seed in range(30):
        e = U(ph + [plan("i_ts", "u-i", "topstep", 45, "buy", einsatz_abs=200.0)], 0.0, 0.0, 20, Z, 25, random.Random(seed),
              einsatz=dict(EK, basis=-600.0), pc_lebt={"u-c", "u-i"})
        bewegt += sum(1 for x in e["aenderungen"] if x["plan_id"] == "m_ts")
        zuege_l += len(e["aenderungen"])
    check(bewegt == 0 and zuege_l > 0, f"30 Seeds mit offenem Band: Plan der toten ID nie bewegt ({bewegt}), andere schon ({zuege_l})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
