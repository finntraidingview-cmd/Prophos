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

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
