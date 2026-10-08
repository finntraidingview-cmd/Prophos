#!/usr/bin/env python3
"""Selbsttest VERTEILEN STATT DURCHRATTERN (app.py, 08.10.2026, Slave-Terminal 3 — Finn zu Ina: 3× Apex 150k um 03:56/03:57/03:58,
3× FundedNext 100k um 16:58–17:01: „Wenn bei einer ID Trades dran sind, werden alle direkt hintereinander durchgerattert. Das muss
nicht sein … über den Tag verteilen. Damit weniger Klumpenrisiko. Aber auch hier aufpassen, dass man nicht aus Versehen gegenhedged").

Aufruf:  python3 tools/selftest_auto_verteilen.py
Ohne Netz, Platzhalter-IDs. Geprüft: ap_zeiten_verteilen hält je ID × Firma ≥ AP_ABSTAND_ID_FIRMA_MIN und je ID ≥ AP_ABSTAND_ID_MIN
(Start zu Start, über viele Seeds), auch gegen schon geplante Pläne (bestehend[gruppe]); fremde IDs dürfen dicht daneben (Takt bleibt
gemischt); enges Fenster → alles gesetzt, gelockert, PC-Regel hält, kein Fehler. ap_richtungen_delta: eine Richtung je gruppe
(auch mit Richtungsschutz auf einem Teil), Apex gegen FundedNext ausgeglichen (Band hält). Große-Folge zählt Zeit-Nähe auch mit
Gegenrichtung dazwischen. _ap_tranche_frei: der Bot schiebt nicht näher zusammen. ap_planen-Rauchlauf: drei FundedNext-Konten einer
ID ≥ 60 min auseinander, eine Richtung."""
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402
import selftest_auto_alle_ids as sa  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = sa.lade()
    GF, GI = a["AP_ABSTAND_ID_FIRMA_MIN"], a["AP_ABSTAND_ID_MIN"]
    verteilen = a["ap_zeiten_verteilen"]
    ZEITEN = {"fenster": [["00:00", "16:30", 1]], "start_bis": "16:30"}

    def tr(user, firma, n, dauer=2.0):
        return [{"key": f"{user}|{firma}#{i + 1}", "user": user, "gruppe": f"{user}|{firma}", "dauer_min": dauer} for i in range(n)]

    # ── 1 Ina: 3× Apex + 3× FundedNext einer ID, dazu eine zweite ID mit 2 Konten ───────────────────────────────────────────────
    ina = tr("ina", "apex", 3) + tr("ina", "fundednext", 3)
    chris = tr("chris", "tradeify", 2)
    schlecht_f, schlecht_i, fehlt, nah_fremd, spannen = 0, 0, 0, 0, []
    for seed in range(200):
        m = verteilen(ina + chris, ZEITEN, random.Random(seed))
        fehlt += sum(1 for t in ina + chris if t["key"] not in m)
        for x in ina + chris:
            for y in ina + chris:
                if x["key"] >= y["key"] or x["key"] not in m or y["key"] not in m:
                    continue
                d = abs(m[x["key"]] - m[y["key"]])
                if x["user"] == y["user"] and x["gruppe"] == y["gruppe"] and d < GF:
                    schlecht_f += 1
                if x["user"] == y["user"] and d < GI:
                    schlecht_i += 1
                if x["user"] != y["user"] and d < GI:
                    nah_fremd += 1
        s = sorted(m[t["key"]] for t in ina if t["key"] in m)
        spannen.append(s[-1] - s[0])
    check(fehlt == 0, f"Ina-Fall: alle 8 Pläne bekommen einen Start (200 Seeds, fehlend {fehlt})")
    check(schlecht_f == 0, f"je ID × Firma ≥ {GF:g} min Start zu Start (Verstöße {schlecht_f})")
    check(schlecht_i == 0, f"je ID ≥ {GI:g} min, auch über Firmen (Verstöße {schlecht_i})")
    check(nah_fremd > 0, f"verschiedene IDs dürfen dicht beieinander starten — Takt über alle IDs gemischt ({nah_fremd}× < {GI:g} min)")
    check(min(spannen) >= 2 * GF, f"Inas Pläne über den Tag verteilt: kleinste Spanne {min(spannen):g} min (vorher 2–5 min)")

    # ── 2 schon geplanter Plan derselben ID × Firma zählt mit ────────────────────────────────────────────────────────────────
    best = [{"user": "ina", "start": 300, "dauer_min": 2, "gruppe": "ina|apex"}]
    v = 0
    for seed in range(100):
        m = verteilen(tr("ina", "apex", 2), ZEITEN, random.Random(seed), bestehend=best)
        v += sum(1 for k, s in m.items() if abs(s - 300) < GF)
    check(v == 0, f"Abstand auch zu schon geplanten Plänen derselben ID × Firma (bestehend[gruppe], Verstöße {v})")

    # ── 3 enges Fenster: so gut wie möglich, nichts fällt weg, PC-Regel hält ───────────────────────────────────────────────────
    eng = {"fenster": [["09:00", "09:40", 1]], "start_bis": "16:30"}
    ok_eng, pc_ok = True, True
    for seed in range(100):
        try:
            m = verteilen(tr("ina", "apex", 3) + tr("ina", "fundednext", 2), eng, random.Random(seed))
        except Exception as e:          # noqa: BLE001
            ok_eng = False
            print("   ", type(e).__name__, e)
            break
        ok_eng = ok_eng and len(m) == 5
        s = sorted(m.values())
        pc_ok = pc_ok and all(b - a_ >= 2 + 3 for a_, b in zip(s, s[1:]))   # Dauer 2 + abstand_id_min 3
    check(ok_eng, "enges Fenster (40 min, 5 Pläne einer ID): alle gesetzt, kein Fehler — Abstände gelockert")
    check(pc_ok, "enges Fenster: alte PC-Regel (nie zwei Starts gleichzeitig + 3 min) hält weiter")
    m = verteilen(tr("ina", "apex", 2), eng, random.Random(1))
    check(len(m) == 2 and abs(m["ina|apex#1"] - m["ina|apex#2"]) >= 10,
          f"enges Fenster, 2 Pläne: so weit wie möglich auseinander (gelockert auf ≥ {GF * 0.25:g} min → {abs(m['ina|apex#1'] - m['ina|apex#2']):g})")

    # ── 4 Richtung: eine Richtung je gruppe, Band hält ──────────────────────────────────────────────────────────────────────
    m = verteilen(ina, ZEITEN, random.Random(7))
    T = {t["key"]: {"fest": None, "user": "ina", "firma": t["gruppe"].split("|")[1], "start": m[t["key"]], "delta_abs": 1.0,
                    "gruppe": t["gruppe"]} for t in ina}
    r, netto = a["ap_richtungen_delta"](T, 0.0, 0.0, random.Random(3), 50)
    ra = {r[k] for k in T if "apex" in k}
    rf = {r[k] for k in T if "fundednext" in k}
    check(len(ra) == 1 and len(rf) == 1, f"eine Richtung je ID × Firma trotz verteilter Starts (Apex {ra}, FundedNext {rf})")
    check(ra != rf, f"Apex gegen FundedNext ausgeglichen (Band hält, |Netto| max {netto:g} statt 6)")
    T2 = dict(T)
    T2["ina|apex#2"] = dict(T["ina|apex#2"], fest="sell")
    r2, _ = a["ap_richtungen_delta"](T2, 0.0, 0.0, random.Random(3), 50)
    check({r2[k] for k in T2 if "apex" in k} == {"sell"}, "Richtungsschutz auf EINEM Teil legt die ganze ID × Firma fest (kein Gegenhedge)")

    # ── 5 Große-Folge mit Zeit-Nähe ───────────────────────────────────────────────────────────────────────────────────────
    lage = a["ap_einsatz_lage"]
    nah = lage(0, [(100, -700), (110, 200), (130, -700)], gross_ab=300)["gross_folge"]
    weit = lage(0, [(100, -700), (130, 200), (100 + a["AP_GROSS_NAH_MIN"] + 30, -700)], gross_ab=300)["gross_folge"]
    ohne = lage(0, [(100, -700), (400, -700)], gross_ab=300)["gross_folge"]
    check(nah == 1, "zwei große Shorts 30 min auseinander zählen als Folge — auch mit Gegenrichtung dazwischen")
    check(weit == 0, f"weiter als {a['AP_GROSS_NAH_MIN']:g} min mit Gegenrichtung dazwischen: keine Folge (wie bisher)")
    check(ohne == 1, "ohne Gegenrichtung dazwischen: Folge wie bisher")

    # ── 6 Bot schiebt nicht näher zusammen ─────────────────────────────────────────────────────────────────────────────────
    frei = a["_ap_tranche_frei"]
    trs = {"ina|apex#1": {"key": "ina|apex#1", "user_id": "ina", "firma": "apex", "start": 300, "ende": 300},
           "ina|fundednext": {"key": "ina|fundednext", "user_id": "ina", "firma": "fundednext", "start": 500, "ende": 500},
           "chris|tradeify": {"key": "chris|tradeify", "user_id": "chris", "firma": "tradeify", "start": 610, "ende": 610}}
    t = {"key": "ina|apex#2", "user_id": "ina", "firma": "apex", "start": 700, "ende": 700}
    check(frei(t, 330, trs, {}) is not None, "Bot: Apex-Teil nicht 30 min neben den anderen Apex-Teil derselben ID")
    check(frei(t, 510, trs, {}) is not None, "Bot: nicht 10 min neben einen anderen Plan derselben ID")
    check(frei(t, 615, trs, {}) is None, "Bot: neben einer fremden ID ist frei")

    # ── 7 Rauchlauf ap_planen: drei FundedNext-Konten einer ID ──────────────────────────────────────────────────────────────
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    tag_s = tag.strftime("%Y-%m-%d")
    reg, geschrieben, inserts = sa.db_stubs(a, jetzt)
    alt_all = a["_sb_all"]
    konten_extra = [{"id": f"k-2{i}", "user_id": sd.U1, "name": f"FN {i}", "firm": "FundedNext", "account_type": "phase1",
                     "external_id": f"00002{i}"} for i in (1, 2)]

    def _sb_all(table, params):
        rows = alt_all(table, params)
        if table == "accounts":
            ids = sa.in_liste(params.get("id", ""))
            uids = sa.in_liste(params.get("user_id", ""))
            typen = params.get("account_type")
            rows += [dict(k) for k in konten_extra if (ids is None or k["id"] in ids) and (uids is None or k["user_id"] in uids)
                     and (not typen or k["account_type"] in typen)]
        return rows
    a["_sb_all"] = _sb_all
    alt_bal = a["acc_balance_wahl"]
    a["acc_balance_wahl"] = lambda acc, e, d: alt_bal(dict(acc, id="k-2") if str((acc or {}).get("id", "")).startswith("k-2") else acc, e, d)
    erg = a["ap_planen"](tag_s, trocken=True, seed=4711)
    fn = sorted((g for g in erg.get("geplant", []) if g["user_id"] == sd.U1 and "FundedNext" in str(g.get("firma") or g.get("konto") or "")),
                key=lambda g: g["start"])
    mins = [int(g["start"][:2]) * 60 + int(g["start"][3:]) for g in fn]
    check(erg.get("ok") and len(fn) == 3, f"ap_planen: drei FundedNext-Konten der ID geplant ({len(fn)}; {erg.get('msg') or 'ok'})")
    check(all(b - a_ >= GF for a_, b in zip(mins, mins[1:])), f"ap_planen: Starts ≥ {GF:g} min auseinander ({[g['start'] for g in fn]})")
    check(len({g["richtung"] for g in fn}) == 1, f"ap_planen: eine Richtung je ID × Firma ({[g['richtung'] for g in fn]})")
    eigen = sorted(int(g["start"][:2]) * 60 + int(g["start"][3:]) for g in erg.get("geplant", []) if g["user_id"] == sd.U1)
    check(all(b - a_ >= GI for a_, b in zip(eigen, eigen[1:])), f"ap_planen: alle Pläne der ID ≥ {GI:g} min auseinander")
    check(not geschrieben["post"] and not inserts, "Probelauf schreibt nichts")

    # ── 8 Bot-Phase VERTEILUNG mit den Klumpen von heute (08.10.2026, Zeiten Dubai = dt + 120 min) ────────────────────────────
    U = a["ap_umplanen"]
    Z16 = {"fenster": [["00:00", "16:30", 1]], "start_bis": "16:30", "abstand_id_min": 3}
    DUBAI = 120

    def dt(hhmm_dubai):
        h_, m_ = map(int, hhmm_dubai.split(":"))
        return h_ * 60 + m_ - DUBAI

    def plan(pid, uid, user, firma, start, richtung="buy", **kw):
        return dict({"plan_id": pid, "user_id": uid, "user": user, "firma": firma, "firma_name": firma.capitalize(), "richtung": richtung,
                     "start_min": float(start), "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "fest_durch": None,
                     "auto_plan": True, "bestaetigt": True, "route": "tvv2"}, **kw)
    heute = [plan("mike1", "u-mike", "Mike", "fundednext", dt("09:59")), plan("mike2", "u-mike", "Mike", "fundednext", dt("10:00")),
             plan("inafn1", "u-ina", "Ina", "fundednext", dt("16:58")), plan("inafn2", "u-ina", "Ina", "fundednext", dt("16:59")),
             plan("inafn3", "u-ina", "Ina", "fundednext", dt("17:01")),
             plan("chrfp1", "u-chris", "Chris", "fundingpips", dt("17:02"), "sell"), plan("chrfp2", "u-chris", "Chris", "fundingpips", dt("17:03"), "sell"),
             plan("aff1", "u-aff", "aff98e60", "the5ers", dt("17:57")), plan("aff2", "u-aff", "aff98e60", "the5ers", dt("17:58")),
             plan("inatf1", "u-ina", "Ina", "tradeify", dt("10:54"), "sell"), plan("inatf2", "u-ina", "Ina", "tradeify", dt("11:37"), "sell")]
    start0 = {p["plan_id"]: p["start_min"] for p in heute}
    pl = [dict(p) for p in heute]
    jm, zuletzt, je_lauf, alle_aend = dt("04:40"), {}, [], []
    for _lauf in range(14):                                    # Bot-Takt alle 10 min, gut zwei Stunden
        erg = U(pl, 0.0, 0.0, jm, Z16, 100, random.Random(_lauf), zuletzt=zuletzt, dubai_min=DUBAI)
        v = [x for x in erg["aenderungen"] if x["art"] == "start"]
        je_lauf.append({f"{x['user_id']}|{x['firma']}" for x in v})
        alle_aend += erg["aenderungen"]
        neu = {x["plan_id"]: x["nach_start_min"] for x in v}
        pl = [dict(p, start_min=neu.get(p["plan_id"], p["start_min"])) for p in pl]
        for x in v:
            zuletzt[x["plan_id"]] = jm
        jm += 10
    st = {p["plan_id"]: p["start_min"] for p in pl}

    def abst(*ids):
        s = sorted(st[i] for i in ids)
        return min(b - a_ for a_, b in zip(s, s[1:]))
    check(all(len(g) <= 1 for g in je_lauf), "höchstens EINE ID × Firma je Bot-Lauf")
    check(all(x["art"] == "start" and x["nach_richtung"] == x["von_richtung"] for x in alle_aend), "nur Startzeiten — Richtung nie geändert")
    check(all(st[i] >= start0[i] for i in st), "nur nach hinten geschoben, nie nach vorn")
    check(all(x["nach_start_min"] >= dt("04:40") + a["AP_VERTEIL_VORLAUF_MIN"] for x in alle_aend), "nie vor jetzt + 10 min")
    check(all(st[i] <= 16 * 60 + 30 for i in st), "alle Starts innerhalb start_bis 16:30 dt (18:30 Dubai)")
    check(abst("mike1", "mike2") >= GF, f"Mike FundedNext 09:59/10:00 → ≥ {GF:g} min ({abst('mike1', 'mike2'):g})")
    check(abst("chrfp1", "chrfp2") >= GF, f"Chris FundingPips 17:02/17:03 → ≥ {GF:g} min ({abst('chrfp1', 'chrfp2'):g})")
    check(abst("inatf1", "inatf2") >= GF, f"Ina Tradeify 10:54/11:37 (43 min) → ≥ {GF:g} min ({abst('inatf1', 'inatf2'):g})")
    check(st["inafn1"] == start0["inafn1"] and abst("inafn1", "inafn2", "inafn3") >= GF * 0.25,
          f"Ina FundedNext 16:58/16:59/17:01: erster bleibt, Rest so weit es bis 18:30 Dubai geht (kleinster Abstand {abst('inafn1', 'inafn2', 'inafn3'):g} min statt 1)")
    check(abst("aff1", "aff2") >= GF * 0.5, f"aff98e60 The5%ers 17:57/17:58 → so weit es geht ({abst('aff1', 'aff2'):g} min, Fenster endet 18:30 Dubai)")
    ina = sorted(st[i] for i in st if i.startswith("ina"))
    check(min(b - a_ for a_, b in zip(ina, ina[1:])) >= GI * 0.25, "Ina über beide Firmen: PC-/ID-Abstand gehalten")
    g = next((x["grund"] for x in alle_aend if x["plan_id"].startswith("inafn")), "")
    check(g.startswith("Verteilung: Ina Fundednext 16:58/16:59/17:01 → 16:58/") and "Dubai" in g, f"Protokoll-Grund in Dubai-Zeit ({g[:90]})")

    # Live-Befund 00:30 UTC: Ina FundedNext hing — frühester Platz 18:06 lag auf dem FundedNext-Buy einer anderen ID (Malus)
    Z2 = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
    live = [plan("ifn1", "u-ina", "Ina", "fundednext", dt("16:58"), "sell"), plan("ifn2", "u-ina", "Ina", "fundednext", dt("16:59"), "sell"),
            plan("ifn3", "u-ina", "Ina", "fundednext", dt("17:01"), "sell"), plan("ifp", "u-ina", "Ina", "fundingpips", dt("17:46")),
            plan("x1", "u-x", "X", "fundednext", dt("16:14")), plan("x2", "u-x", "X", "fundednext", dt("18:06")),
            plan("y1", "u-y", "Y", "fundednext", dt("17:00"), "sell")]
    pl, jm, zul = [dict(p) for p in live], dt("04:45"), {}
    for _l in range(6):
        e = U(pl, 0.0, 0.0, jm, Z2, 100, random.Random(_l), zuletzt=zul, dubai_min=DUBAI)
        nv = {x["plan_id"]: x["nach_start_min"] for x in e["aenderungen"] if x["art"] == "start"}
        pl = [dict(p, start_min=nv.get(p["plan_id"], p["start_min"])) for p in pl]
        for k in nv:
            zul[k] = jm
        jm += 10
    s2 = {p["plan_id"]: p["start_min"] for p in pl}
    ifn = sorted(s2[k] for k in ("ifn1", "ifn2", "ifn3"))
    txt = ["%02d:%02d" % divmod(int(x + DUBAI), 60) for x in ifn]
    check(min(b - a_ for a_, b in zip(ifn, ifn[1:])) >= GF * 0.25, f"Live-Fall Ina FundedNext: verteilt ({txt} Dubai, vorher 16:58/16:59/17:01)")
    check(all(abs(s2[k] - s2["x2"]) >= a["AP_GEGEN_DICHT_MIN"] for k in ("ifn2", "ifn3") if s2[k] != dt("16:59") and s2[k] != dt("17:01")),
          "Live-Fall: kein Platz im Malus-Abstand zum FundedNext-Buy der anderen ID (18:06)")
    check(all(abs(s2[k] - s2["ifp"]) >= GI * 0.5 for k in ("ifn1", "ifn2", "ifn3")), "Live-Fall: ≥ 10 min zu Inas FundingPips 17:46 (ID-Abstand)")
    check(all(abs(s2[k] - s2["y1"]) >= a["AP_FIRMA_ABSTAND_MIN"] for k in ("ifn2", "ifn3") if s2[k] not in (dt("16:59"), dt("17:01"))),
          "Live-Fall: ≥ 5 min zum FundedNext-Plan der dritten ID (Firmen-Abstand)")
    check(all(s2[k] <= 16 * 60 + 30 for k in s2), "Live-Fall: alles bis 18:30 Dubai")

    # Ruhezeit: ein eben verschobener Plan ruht 30 min
    e_r = U([plan("m1", "u-m", "M", "apex", 600), plan("m2", "u-m", "M", "apex", 601)], 0.0, 0.0, 400, Z16, 100, random.Random(1),
            zuletzt={"m2": 395})
    check(not e_r["aenderungen"], "Ruhezeit: vor 5 min angefasster Plan wird nicht erneut verschoben")
    # Werte von Hand / Handplan bleiben stehen
    e_h = U([plan("h1", "u-h", "H", "apex", 600), plan("h2", "u-h", "H", "apex", 601, aenderbar=False, fest_durch=a["AP_FEST_HAND"]),
             plan("h3", "u-h", "H", "apex", 602, auto_plan=False, aenderbar=False, fest_durch="Handplan")],
            0.0, 0.0, 400, Z16, 100, random.Random(1))
    check(not any(x["plan_id"] in ("h2", "h3") for x in e_h["aenderungen"]), "Werte von Hand und Handpläne werden nie verschoben")
    # Gegenrichtung derselben ID × Firma: nie in deren Laufzeit schieben
    e_g = U([plan("g1", "u-g", "G", "apex", 600), plan("g2", "u-g", "G", "apex", 601), plan("g3", "u-g", "G", "apex", 700, "sell")],
            0.0, 0.0, 400, Z16, 100, random.Random(2))
    g2 = next((x["nach_start_min"] for x in e_g["aenderungen"] if x["plan_id"] == "g2"), 601)
    check(abs(g2 - 700) >= a["AP_VERTEIL_GEGEN_MIN"], f"nie in die Laufzeit der Gegenrichtung derselben ID × Firma (g2 → {g2:g}, Short um 700)")
    # Band: würde das Verschieben das Band der nächsten 60 min verschlechtern, bleibt es stehen
    # vorher ausgeglichen (2× Long 10 gegen Short 20 derselben Minute) — b2 nach hinten ließe den Short 60 min allein stehen
    e_b = U([plan("b1", "u-b", "B", "apex", 600, delta_abs=10.0), plan("b2", "u-b", "B", "apex", 600, delta_abs=10.0),
             plan("b3", "u-c", "C", "topstep", 600, "sell", delta_abs=20.0)], 0.0, 0.0, 590, Z16, 5, random.Random(1), hysterese=0)
    check(e_b["vorher"]["ueber_band"] == 0, f"Band-Fall: vorher im Band ({e_b['vorher']['ueber_band']})")
    check(not any(x["art"] == "start" and x["plan_id"] == "b2" for x in e_b["aenderungen"]),
          "Band: verschlechtert das Verschieben das Netto der nächsten 60 min, bleibt der Plan stehen")

    # Schreiben: nur start_um, Bestätigung bleibt (Guard lässt bestätigte nicht fällige zu)
    patch = []
    a["sb_select"] = lambda t, p: [{"id": 1}]
    a["sb_update"] = lambda t, prm, body: (patch.append((prm, body)), [{"id": prm.get("id")}])[1]
    a["sb_insert"] = lambda t, rows: rows
    stand_w = {"geplant": [{"plan_id": "mike2", "start": "2026-10-09T06:00:00+00:00", "firma": "FundedNext", "user": "Mike"}],
               "mitternacht": datetime(2026, 10, 8, 22, 0, tzinfo=timezone.utc)}
    v_m = [x for x in alle_aend if x["plan_id"] == "mike2"][:1]
    try:
        a["_ap_aenderungen_anwenden"](stand_w, v_m, "bot")
    except Exception as e:     # noqa: BLE001 — Protokoll-Schreiben im Stub darf scheitern, der PATCH ist schon erfasst
        print("   (Protokoll im Stub:", type(e).__name__, ")")
    check(patch and set(patch[0][1]) == {"start_um"} and "or" in patch[0][0] and "auto_bestaetigt_at.is.null" in patch[0][0]["or"],
          f"PATCH ändert nur start_um, bestätigte nicht fällige Pläne erlaubt ({patch[0] if patch else '—'})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
