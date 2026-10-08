#!/usr/bin/env python3
"""Selbsttest FIRMEN-MISCHUNG + GEGENRICHTUNG ÜBER IDs (app.py, 08.10.2026 ~17:00 Dubai, Finn: „Ich glaube, im Bot ist eine falsche
Regel drin. Heute war kein einziger Tradeify-Short bei 10–15 Trades — Fehler. Wenn eine ID Tradeify long geht, kann natürlich eine
ANDERE ID Tradeify short gehen zum Ausgleichen. Es darf sich nur nicht die GLEICHE ID gegenhedgen. Ich will auch nicht, dass an einem
Tag eine Prop-Firm nur in einer Richtung getradet wird, weil das genauso auffällig ist." — Befund Master: Tradeify 17× buy über 6 IDs).

Aufruf:  python3 tools/selftest_auto_firma_misch.py
Ohne Netz, Platzhalter-IDs, nachgebaute DB (Lader/Stubs aus selftest_auto_delta). Geprüft:
(A) ap_firma_misch rein rechnend — Mindestzahl der selteneren Richtung (3 → 1, 4 → 1, 6 → 2, 10 → 3), erst ab 3 Trades über ≥ 2 IDs,
    feste Trades des Tages zählen mit, Folgetag nicht; AP_GEGEN_FIRMA_MIN = AP_GEGEN_DICHT_MIN = 3.
(B) Planer-Trockenlauf (ap_planen trocken, echter Weg Nachtlauf): Beispiel-Tag mit 9 Tradeify-Konten über 6 IDs (+ ein heute
    gestarteter Winning-Days-Long einer 7. ID), FundedNext 3 IDs, Apex 2, The5%ers 2, Zeitfenster wie live (Opening 50 %):
    jede Firma mit ≥ 3 Trades über ≥ 2 IDs hat beide Richtungen (seltenere ≥ Soll), gleiche ID × Firma nur EINE Richtung (auch zu
    einem schon geplanten Handplan derselben ID), keine zwei gegenläufigen Starts derselben Firma binnen 3 min, über die Seeds kein
    starres Muster (mal long-, mal short-lastig).
(C) Ausgleichs-Bot (ap_umplanen): Mischungs-Drehung dreht bei einseitiger Firma die ganze ID × Firma einer anderen ID gegenläufig
    („Firmen-Mischung"), nie eine ID mit laufendem Trade dort (Richtungsschutz); Band-Drehung macht eine gemischte Firma nie einseitig
    (Fall 08.10.2026 10:22 Dubai: Tradeify short → long, danach 100 % long); Gegenrichtung über IDs nur nicht ±3 min am Start."""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


U = [f"00000000-0000-0000-0000-0000000000b{i}" for i in range(1, 8)]    # sieben Platzhalter-IDs
NAMEN = {u: f"ID{n + 1}" for n, u in enumerate(U)}
ZEITEN_LIVE = {"tz": "Europe/Berlin", "fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30",
               "abstand_id_min": 3, "abstand_konto_s": [60, 120]}


def fixture(mitternacht):
    """Beispiel-Tag: 9 Tradeify-Konten über 6 IDs (+ 1 Konto mit schon geplantem Handplan), FundedNext 3, Apex 2, The5%ers 2."""
    konten, bal = [], {}

    def k(kid, uid, firm, typ, b):
        konten.append({"id": kid, "user_id": uid, "name": kid.upper(), "firm": firm, "account_type": typ, "external_id": f"EXT-{kid}"})
        bal[kid] = b
    for n, (uid, anz) in enumerate([(U[0], 2), (U[1], 2), (U[2], 1), (U[3], 1), (U[4], 2), (U[5], 1)]):
        for j in range(anz):
            k(f"tf-{n + 1}{j + 1}", uid, "Tradeify", "challenge", 150000)
    k("tf-hand", U[0], "Tradeify", "challenge", 150000)                          # hat schon einen Handplan (sell) am Tag
    for n in range(3):
        k(f"fn-{n + 1}", U[n], "FundedNext", "phase1", 100000)
    k("ap-4", U[3], "Apex Trader", "challenge", 150000)
    k("ap-5", U[4], "Apex Trader", "challenge", 150000)
    k("t5-2", U[1], "The5%ers", "phase1", 100000)
    k("t5-6", U[5], "The5%ers", "phase1", 100000)
    k("tf-wd", U[6], "Tradeify", "winning_days", 150000)
    bal["tf-wd"] = 150000
    offen = [{"id": "p-wd", "user_id": U[6], "master_account_id": "tf-wd", "master_firm": "Tradeify", "status": "open", "richtung": "buy",
              "master_tp": 800, "master_sl": None, "master_contracts": 2, "master_symbol": "NQZ6", "route": "tvv2",
              "mt5_baseline": {"hedge": {"status": "offen", "einstieg_nq": 20000}}, "start_um": None,
              "started_at": (mitternacht + timedelta(hours=3)).astimezone(timezone.utc).isoformat()}]
    geplant = [{"id": "p-hand", "user_id": U[0], "master_account_id": "tf-hand", "master_firm": "Tradeify", "status": "planned",
                "richtung": "sell", "master_tp": 3500, "master_sl": None, "master_contracts": 3, "master_symbol": "NQZ6", "route": "tvv2",
                "auto_plan": False, "planned_for": None,
                "start_um": (mitternacht + timedelta(hours=15, minutes=40)).astimezone(timezone.utc).isoformat()}]
    return konten, bal, offen, geplant


def stubs(a, mitternacht):
    reg, _g = sd.db_stubs(a, datetime.now(timezone.utc))
    konten, bal, offen, geplant = fixture(mitternacht)
    reg.update(user_ids=U[:6], zeiten=ZEITEN_LIVE,
               regeln={"firmen": sd.FIRMEN, "ausgleich": {"aktiv": True, "takt_min": 3, "zielband_pct": 25, "auto_start": False,
                                                          "gross_ab_eur": 300, "laufzeit_min": 180}})

    def in_liste(w):
        return [x for x in w[4:-1].split(",") if x] if w and w.startswith("in.(") else None

    def _sb_all(table, params):
        uids, ids = in_liste(params.get("user_id", "")), in_liste(params.get("id", ""))
        if table == "accounts":
            typen = params.get("account_type")
            return [dict(x) for x in konten if (ids is None or x["id"] in ids) and (uids is None or x["user_id"] in uids)
                    and (not typen or x["account_type"] in typen)]
        if table == "trade_plans":
            st = params.get("status")
            rows = offen if st == "eq.open" else geplant if st == "eq.planned" else [] if st else offen + geplant
            return [dict(p) for p in rows if uids is None or p["user_id"] in uids]
        if table == "firm_specs":
            return [{"user_id": U[0], "name": "FundedNext", "ppl": "10.0000", "symbol": None, "unit": "Lots"},
                    {"user_id": U[0], "name": "The5%ers", "ppl": "1.0000", "symbol": None, "unit": "Lots"}]
        return []
    a.update({"_sb_all": _sb_all, "sb_select": lambda t, p: [reg] if t == "auto_plan_regeln" else [],
              "_ap_namen": lambda: (dict(NAMEN), set()),
              "acc_balance_wahl": lambda x, e, d: (bal.get(str((x or {}).get("id"))), "USD", "TV", "2999-01-01")})
    return konten


def main():
    a = sd.lade()
    M = a["ap_firma_misch"]

    # ── A rein rechnend ─────────────────────────────────────────────────────────────────────────────────────────────────────
    check(a["AP_GEGEN_FIRMA_MIN"] == 3 and a["AP_GEGEN_DICHT_MIN"] == 3 and a["AP_FIRMA_MISCH_AB"] == 3,
          "Gegenrichtung über IDs: nur ±3 min am Start (DB 90 s + Puffer), Mischung ab 3 Trades")

    def tag(paare):
        z, tr = {}, {}
        for n, (uid, r) in enumerate(paare):
            z[f"k{n}"] = r
            tr[f"k{n}"] = {"user": uid, "firma": "tradeify"}
        return M(z, tr)
    st, je = tag([("a", "buy"), ("b", "buy"), ("c", "buy")])
    check(st == 33 and je["tradeify"]["soll"] == 1 and je["tradeify"]["regel"], f"3 Trades / 3 IDs nur long → Strafe 33, Soll 1 ({st}, {je})")
    check(tag([("a", "buy"), ("b", "buy"), ("c", "sell")])[0] == 0, "3 Trades 2/1 → gemischt")
    check(tag([("a", "buy"), ("b", "buy"), ("c", "buy"), ("d", "sell")])[0] == 0, "4 Trades 3/1 → gemischt (grob 30 %, 25 % reicht)")
    st6, je6 = tag([("a", "buy")] * 2 + [("b", "buy")] * 3 + [("c", "sell")])
    check(st6 == 17 and je6["tradeify"]["soll"] == 2, f"6 Trades 5/1 → Soll 2, Strafe 17 ({st6})")
    st10, je10 = tag([(f"u{i}", "buy") for i in range(7)] + [("x", "sell")] * 3)
    check(st10 == 0 and je10["tradeify"]["soll"] == 3 and je10["tradeify"]["anteil"] == 0.3, "10 Trades 7/3 → Soll 3 erfüllt")
    check(tag([("a", "buy"), ("b", "buy")])[0] == 0, "2 Trades → keine Vorgabe")
    check(tag([("a", "buy")] * 5)[0] == 0, "5 Trades, nur eine ID → keine Vorgabe (eine ID = eine Richtung je Firma)")
    st_f, _ = M({"k": "buy", "j": "buy"}, {"k": {"user": "a", "firma": "tradeify"}, "j": {"user": "b", "firma": "tradeify"}},
                [{"user_id": "c", "firma": "tradeify", "richtung": "buy"}])
    st_f2, _ = M({"k": "buy", "j": "sell"}, {"k": {"user": "a", "firma": "tradeify"}, "j": {"user": "b", "firma": "tradeify"}},
                 [{"user_id": "c", "firma": "tradeify", "richtung": "buy"}])
    check(st_f == 33 and st_f2 == 0, "feste Trades des Tages (heute gestartet / schon geplant) zählen mit")
    st_n, _ = M({"k": "buy", "j": "buy", "f": "buy"}, {"k": {"user": "a", "firma": "x"}, "j": {"user": "b", "firma": "x"},
                                                       "f": {"user": "c", "firma": "x", "folgetag": True}})
    check(st_n == 0, "Pläne des Folgetags zählen nicht zum Tag")
    st_np, _ = M({"k": "buy", "j": "buy"}, {"k": {"user": "a", "firma": "x", "n_plaene": 2}, "j": {"user": "b", "firma": "x"}})
    check(st_np == 33, "n_plaene zählt je Tranche (2 + 1 Pläne = 3 Trades)")

    # ── B Planer-Trockenlauf (ap_planen trocken, Weg des Nachtlaufs) ────────────────────────────────────────────────────────
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Berlin")
    t = datetime.now(tz) + timedelta(days=1)
    while t.weekday() >= 5:
        t += timedelta(days=1)
    tag_s = t.strftime("%Y-%m-%d")
    mitt = datetime(t.year, t.month, t.day, tzinfo=tz)
    stubs(a, mitt)
    zaehl = {"long_mehr": 0, "short_mehr": 0}
    verstoss_misch, verstoss_id, verstoss_dicht, gesamt = [], [], [], {}
    beispiel = None
    seeds = range(12)
    for seed in seeds:
        erg = a["ap_planen"](tag_s, trocken=True, seed=1000 + seed)
        if not erg.get("ok"):
            check(False, f"Probelauf seed {seed}: {erg.get('msg')}")
            break
        je_f = {}
        for g in erg["geplant"]:
            e = je_f.setdefault(g["firma"], {"buy": 0, "sell": 0, "ids": set(), "starts": []})
            e[g["richtung"]] += 1
            e["ids"].add(g["user_id"])
            e["starts"].append((int(g["start"][:2]) * 60 + int(g["start"][3:]), g["richtung"], g["user_id"]))
        # fest am Tag: Handplan ID1 Tradeify sell, Winning-Days-Long ID7 Tradeify (heute gestartet)
        tf = je_f.setdefault("Tradeify", {"buy": 0, "sell": 0, "ids": set(), "starts": []})
        tf["sell"] += 1
        tf["buy"] += 1
        tf["ids"] |= {U[0], U[6]}
        for f, e in je_f.items():
            n = e["buy"] + e["sell"]
            soll = max(1, round(0.3 * n)) if n >= 3 and len(e["ids"]) >= 2 else 0
            if min(e["buy"], e["sell"]) < soll:
                verstoss_misch.append((seed, f, e["buy"], e["sell"]))
            gs = gesamt.setdefault(f, [0, 0])
            gs[0] += e["buy"]
            gs[1] += e["sell"]
            st_ = sorted(e["starts"])
            for i_, (m1, r1, u1) in enumerate(st_):
                for m2, r2, u2 in st_[i_ + 1:]:
                    if r1 != r2 and m2 - m1 < 3 and u1 != u2:
                        verstoss_dicht.append((seed, f, m1, m2))
        zaehl["long_mehr" if tf["buy"] > tf["sell"] else "short_mehr"] += 1 if tf["buy"] != tf["sell"] else 0
        for (uid, f) in {(g["user_id"], g["firma"]) for g in erg["geplant"]}:
            rs = {g["richtung"] for g in erg["geplant"] if g["user_id"] == uid and g["firma"] == f}
            if uid == U[0] and f == "Tradeify":
                rs |= {"sell"}                                   # Handplan derselben ID × Firma am Tag
            if len(rs) > 1:
                verstoss_id.append((seed, NAMEN.get(uid), f, sorted(rs)))
        if beispiel is None:
            beispiel = (seed, {f: (e["buy"], e["sell"]) for f, e in je_f.items()}, erg.get("firma_misch"))
    n_tf = sum(gesamt.get("Tradeify", [0, 0]))
    check(n_tf > 0 and not verstoss_misch, f"{len(seeds)} Probeläufe: jede Firma mit ≥ 3 Trades über ≥ 2 IDs hat beide Richtungen "
          f"(seltenere ≥ Soll) — Verstöße {verstoss_misch[:4]}")
    check(not verstoss_id, f"gleiche ID × Firma nie gegenläufig (auch nicht gegen den Handplan derselben ID) — Verstöße {verstoss_id[:4]}")
    check(not verstoss_dicht, f"keine zwei gegenläufigen Starts derselben Firma binnen 3 min — Verstöße {verstoss_dicht[:4]}")
    check(zaehl["long_mehr"] > 0 and zaehl["short_mehr"] > 0,
          f"kein starres Muster: Tradeify mal long-, mal short-lastig über die Seeds ({zaehl})")
    fm = {x["firma"]: x for x in (beispiel[2] or [])} if beispiel else {}
    check(fm.get("tradeify", {}).get("regel") and fm["tradeify"]["n"] >= 10 and fm["tradeify"]["anteil"] >= 0.3 - 1e-9,
          f"Antwort trägt firma_misch je Firma (Tradeify {fm.get('tradeify')})")
    print("   Beispiel-Tag (seed", beispiel[0], ") long/short je Firma inkl. fester Trades:",
          ", ".join(f"{f} {b}/{s}" for f, (b, s) in sorted(beispiel[1].items())))
    print("   über", len(seeds), "Seeds long/short gesamt:", ", ".join(f"{f} {b}/{s} ({s / (b + s):.0%} short)" for f, (b, s) in sorted(gesamt.items())))

    # ── C Ausgleichs-Bot ────────────────────────────────────────────────────────────────────────────────────────────────────
    Ub = a["ap_umplanen"]
    Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}

    def plan(pid, uid, firma, start, richtung="buy", **kw):
        return dict({"plan_id": pid, "user_id": uid, "user": NAMEN.get(uid, uid), "firma": firma, "firma_name": firma.capitalize(),
                     "richtung": richtung, "start_min": float(start), "delta_abs": 0.0, "einsatz_abs": 10.0, "aenderbar": True,
                     "fest_durch": None, "auto_plan": True, "bestaetigt": False, "route": "tvv2"}, **kw)
    jm = 300.0
    EK0 = {"basis": 0.0, "brutto": 0.0, "gross_ab": 100000.0, "laufzeit": 180}
    # C1 einseitige Firma: Tradeify 5× long über 4 IDs (ID1 mit 2 Konten), alles weit in der Zukunft, Band ruhig
    tf5 = [plan("t1a", U[0], "tradeify", 600), plan("t1b", U[0], "tradeify", 640), plan("t2", U[1], "tradeify", 700),
           plan("t3", U[2], "tradeify", 760), plan("t4", U[3], "tradeify", 820)]
    e1 = Ub(tf5, 0.0, 0.0, jm, Z, 25, random.Random(1), einsatz=EK0)
    dreh = [x for x in e1["aenderungen"] if x["art"] == "richtung"]
    nach = {p["plan_id"]: p["richtung"] for p in tf5}
    nach.update({x["plan_id"]: x["nach_richtung"] for x in dreh})
    check(dreh and all(x["nach_richtung"] == "sell" for x in dreh) and sum(1 for r in nach.values() if r == "sell") >= 1
          and all(x["grund"].startswith("Firmen-Mischung") for x in dreh),
          f"Bot: Tradeify 5× long über 4 IDs → eine andere ID wird gegenläufig gedreht („Firmen-Mischung“) "
          f"({[(x['plan_id'], x['grund'][:70]) for x in dreh]})")
    check(nach["t1a"] == nach["t1b"], "Bot: ID × Firma dreht nur als Ganzes (ID1 beide Tradeify gleich)")
    check(len({x["user_id"] for x in dreh}) == 1, "Bot: eine Mischungs-Drehung je Lauf")
    # C2 Richtungsschutz: läuft bei ID2/ID3/ID4 Tradeify long (id_fest), darf nur ID1 gedreht werden — sonst niemand
    fest = {f"{U[i]}|tradeify": {"richtung": "buy", "durch": "läuft gerade"} for i in (1, 2, 3)}
    e2 = Ub(tf5, 0.0, 0.0, jm, Z, 25, random.Random(1), einsatz=EK0, id_fest=fest)
    d2 = {x["user_id"] for x in e2["aenderungen"] if x["art"] == "richtung"}
    check(d2 <= {U[0]}, f"Bot: nie eine ID drehen, deren Tradeify-Trade läuft (gleiche ID nie gegenläufig) ({[NAMEN[u] for u in d2]})")
    # C3 nicht ±3 min neben einen gegenläufigen Start einer anderen ID: ID6 Tradeify-Long (Handplan) 2 min nach ID2s Long
    gegen = tf5 + [plan("b_x", U[5], "tradeify", 702, "buy", aenderbar=False, fest_durch="Handplan", auto_plan=False)]
    ok3 = True
    for seed in range(10):
        e3b = Ub(gegen, 0.0, 0.0, jm, Z, 25, random.Random(seed), einsatz=EK0)
        for x in e3b["aenderungen"]:
            if x["art"] == "richtung" and x["nach_richtung"] == "sell" and abs(x["nach_start_min"] - 702) <= 3:
                ok3 = False
    check(ok3, "Bot: gedrehter Short nie ±3 min neben dem Long einer anderen ID derselben Firma (ID2 700 ↔ ID6 702)")
    # C4 Fall 08.10.2026 10:22 Dubai: Tradeify gemischt (2 gestartete Longs anderer IDs, 1 geplanter Short) und das Buch
    # stark short → die Band-Drehung short → long machte Tradeify 100 % long. Jetzt: nie; Kontrolle mit den Longs bei Apex: gedreht
    EKs = {"basis": -1500.0, "brutto": 1500.0, "gross_ab": 100000.0, "laufzeit": 180}
    short1 = [plan("au", U[2], "tradeify", jm + 20, "sell", einsatz_abs=300.0)]

    def gest(firma):
        return [{"user_id": U[0], "firma": firma, "start": jm - 100, "richtung": "buy"},
                {"user_id": U[1], "firma": firma, "start": jm - 90, "richtung": "buy"}]
    dreh_tf = dreh_ap = 0
    for seed in range(6):
        e4 = Ub(short1, 0.0, 0.0, jm, Z, 25, random.Random(seed), einsatz=EKs, gestartet=gest("tradeify"))
        e4k = Ub(short1, 0.0, 0.0, jm, Z, 25, random.Random(seed), einsatz=EKs, gestartet=gest("apex"))
        dreh_tf += sum(1 for x in e4["aenderungen"] if x["art"] == "richtung")
        dreh_ap += sum(1 for x in e4k["aenderungen"] if x["art"] == "richtung")
    check(dreh_ap > 0 and dreh_tf == 0,
          f"Band-Drehung macht eine gemischte Firma nie einseitig (Tradeify 2 long + 1 short: {dreh_tf} Drehungen; "
          f"Kontrolle Longs bei Apex: {dreh_ap})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
