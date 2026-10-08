#!/usr/bin/env python3
"""Selbsttest FIRMEN-MISCHUNG + GEGENRICHTUNG ÜBER IDs (app.py, 08.10.2026 ~17:00 Dubai, Finn: „Ich glaube, im Bot ist eine falsche
Regel drin. Heute war kein einziger Tradeify-Short bei 10–15 Trades — Fehler. Wenn eine ID Tradeify long geht, kann natürlich eine
ANDERE ID Tradeify short gehen zum Ausgleichen. Es darf sich nur nicht die GLEICHE ID gegenhedgen. Ich will auch nicht, dass an einem
Tag eine Prop-Firm nur in einer Richtung getradet wird, weil das genauso auffällig ist." — Befund Master: Tradeify 17× buy über 6 IDs).

Aufruf:  python3 tools/selftest_auto_firma_misch.py
Ohne Netz, Platzhalter-IDs, nachgebaute DB (Lader/Stubs aus selftest_auto_delta). Geprüft:
(A) ap_firma_misch rein rechnend — Mindestzahl der selteneren Richtung (3 → 1, 4 → 1, 6 → 2, 10 → 3), erst ab 3 Trades über ≥ 2 IDs,
    feste Trades des Tages zählen mit, Folgetag nicht; AP_GEGEN_FIRMA_MIN = AP_GEGEN_DICHT_MIN = 3.
(A2) MISCHUNG JE ZEITFENSTER (08.10.2026 abends, Finn: „Heute vormittag Tradeify 7 Accounts long, nachmittags 4 short — es war nie
    gemischt … nicht ganze Gruppen gleichzeitig in eine Richtung kippen"): ap_klasse (CFD/Futures nach Weg bzw. Firma), ap_misch_lage
    je Fenster × Firma, × Klasse, gesamt, Kippen CFD gegen Futures, Starts außerhalb der Fenster nur am Tag, ap_misch_text.
(B) Planer-Trockenlauf (ap_planen trocken, echter Weg Nachtlauf): Beispiel-Tag mit 9 Tradeify-Konten über 6 IDs (+ ein heute
    gestarteter Winning-Days-Long einer 7. ID morgens, + ein Handplan-Short im Opening), FundedNext 4 IDs, The5%ers 3, Apex 2,
    Zeitfenster wie live (Morgen 00:00–14:30 / Opening 14:30–16:30 dt, je 50 %): jede Firma mit ≥ 3 Trades über ≥ 2 IDs hat beide
    Richtungen — am Tag UND je Fenster, jede Klasse je Fenster ebenso, kein Fenster kippt (CFD gegen Futures, alles eine Richtung);
    gleiche ID × Firma darf gegenläufig sein (seit 09.10.2026, Finn: nur nie gleichzeitig — sichert der Start-Wächter), keine zwei gegenläufigen Starts
    derselben Firma binnen 3 min, über die Seeds kein starres Muster (mal long-, mal short-lastig).
(C) Ausgleichs-Bot (ap_umplanen): Mischungs-Drehung dreht bei einseitiger Firma die ganze ID × Firma einer anderen ID gegenläufig
    („Firmen-Mischung"), nie eine ID mit laufendem Trade dort (Richtungsschutz); Band-Drehung macht eine gemischte Firma nie einseitig
    (Fall 08.10.2026 10:22 Dubai: Tradeify short → long, danach 100 % long) und kein gemischtes Fenster einseitig; Tradeify morgens 3×
    long / Opening 3× short → nach zwei Läufen je Fenster beide Richtungen; Gegenrichtung über IDs nur nicht ±3 min am Start."""
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
    """Beispiel-Tag: 9 Tradeify-Konten über 6 IDs (+ 1 Konto mit schon geplantem Handplan), FundedNext 4, The5%ers 3, Apex 2."""
    konten, bal = [], {}

    def k(kid, uid, firm, typ, b):
        konten.append({"id": kid, "user_id": uid, "name": kid.upper(), "firm": firm, "account_type": typ, "external_id": f"EXT-{kid}"})
        bal[kid] = b
    for n, (uid, anz) in enumerate([(U[0], 2), (U[1], 2), (U[2], 1), (U[3], 1), (U[4], 2), (U[5], 1)]):
        for j in range(anz):
            k(f"tf-{n + 1}{j + 1}", uid, "Tradeify", "challenge", 150000)
    k("tf-hand", U[0], "Tradeify", "challenge", 150000)                          # hat schon einen Handplan (sell) am Tag
    for n in range(4):
        k(f"fn-{n + 1}", U[n], "FundedNext", "phase1", 100000)
    k("ap-4", U[3], "Apex Trader", "challenge", 150000)
    k("ap-5", U[4], "Apex Trader", "challenge", 150000)
    k("t5-2", U[1], "The5%ers", "phase1", 100000)
    k("t5-3", U[2], "The5%ers", "phase1", 100000)
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

    # ── A2 Mischung je Zeitfenster (rein rechnend) ──────────────────────────────────────────────────────────────────────────
    K = a["ap_klasse"]
    check(K("mt5v2", "tradeify") == "cfd" and K("tvv2", "fundednext") == "futures" and K("tsv2") == "futures"
          and K(None, "tradeify") == "futures" and K(None, "apextrader") == "futures" and K(None, "topstep") == "futures"
          and K(None, "fundednextfutures") == "futures" and K(None, "myfundedfutures") == "futures" and K(None, "lucidtrading") == "futures"
          and K(None, "fundednext") == "cfd" and K(None, "the5ers") == "cfd" and K(None, "fundingpips") == "cfd"
          and K(None, "blueguardian") == "cfd" and K(None, "ftmo") == "cfd",
          "ap_klasse: Weg zuerst (mt5/mt5v2 = CFD, tv…/ts… = Futures), sonst Firma wie balance_lese_weg (FundedNext Futures = Futures)")
    L = a["ap_misch_lage"]
    MO, OP = 300, 900                                   # 05:00 dt (Morgen) / 15:00 dt (Opening)

    def lage(trades, fest=()):
        z, tr = {}, {}
        for n, (uid, firma, r, start, route) in enumerate(trades):
            z[f"k{n}"] = r
            tr[f"k{n}"] = {"user": uid, "firma": firma, "start": start, "route": route}
        return L(z, tr, fest, ZEITEN_LIVE)

    def zellen(lg, ebene):
        return {(c["fenster"], c["name"]): c for c in lg[1]["zellen"] if c["ebene"] == ebene}
    # Finns Tag: Tradeify morgens 3× long, nachmittags 3× short — am Tag 3/3 gemischt, je Fenster nicht
    tf = [(f"u{i}", "tradeify", "buy", MO + 10 * i, "tvv2") for i in range(3)] + \
         [(f"u{i}", "tradeify", "sell", OP + 10 * i, "tvv2") for i in range(3, 6)]
    st_t, _ = a["ap_firma_misch"]({f"k{n}": t[2] for n, t in enumerate(tf)},
                                  {f"k{n}": {"user": t[0], "firma": t[1], "start": t[3]} for n, t in enumerate(tf)})
    lg = lage(tf)
    ff = zellen(lg, "fenster_firma")
    check(st_t == 0 and lg[0] > 0 and all(c["strafe"] > 0 for c in ff.values()) and len(ff) == 2,
          f"Tradeify morgens 3× long, nachmittags 3× short: am Tag gemischt (ohne zeiten 0), je Fenster einseitig → Strafe ({lg[0]})")
    tf2 = [tf[0], tf[1], (tf[2][0], "tradeify", "sell", tf[2][3], "tvv2"), (tf[3][0], "tradeify", "buy", tf[3][3], "tvv2"), tf[4], tf[5]]
    check(lage(tf2)[0] == 0, "je Fenster eine Gegenrichtung → Strafe 0")
    # Klassen: morgens CFD nur short, Futures nur long (je 3 über 3 IDs) — Klasse + Kippen
    kl = [(f"c{i}", "fundednext", "sell", MO + 5 * i, "mt5v2") for i in range(3)] + \
         [(f"f{i}", ["tradeify", "apextrader", "topstep"][i], "buy", MO + 2 + 5 * i, "tvv2") for i in range(3)]
    lk = lage(kl)
    kz = zellen(lk, "fenster_klasse")
    kp = [c for c in lk[1]["zellen"] if c["ebene"] == "kipp"]
    gz = zellen(lk, "fenster_gesamt")
    check(all(c["strafe"] > 0 for c in kz.values()) and len(kz) == 2 and kp and all(c["strafe"] == 0 for c in gz.values()),
          f"morgens CFD 3× short, Futures 3× long: beide Klassen einseitig + gekippt, insgesamt 3/3 ({[(c['name'], c['strafe']) for c in kp]})")
    kl2 = list(kl)
    kl2[0] = (kl[0][0], "fundednext", "buy", kl[0][3], "mt5v2")
    kl2[3] = (kl[3][0], "tradeify", "sell", kl[3][3], "tvv2")
    check(lage(kl2)[0] == 0, "je Klasse eine Gegenrichtung → Strafe 0, kein Kippen")
    kipp = [("c0", "fundednext", "sell", MO, "mt5v2"), ("c1", "the5ers", "sell", MO + 3, "mt5v2"),
            ("f0", "tradeify", "buy", MO + 5, "tvv2"), ("f1", "apextrader", "buy", MO + 9, "tvv2")]
    lkp = lage(kipp)
    check(lkp[0] == 25 and [c["ebene"] for c in lkp[1]["zellen"] if c["strafe"]] == ["kipp"],
          f"CFD 2× short gegen Futures 2× long: Klassen zu klein für die Regel, aber gekippt → Strafe 25 ({lkp[0]})")
    check(lage(kipp[:1] + kipp[2:])[0] == 0, "CFD 1× short neben Futures 2× long: ein einzelner Trade kippt nicht (AP_KIPP_JE_KLASSE = 2)")
    alle_long = [("a", "fundednext", "buy", MO, "mt5v2"), ("b", "tradeify", "buy", MO + 5, "tvv2"), ("c", "the5ers", "buy", MO + 9, "mt5v2")]
    lal = lage(alle_long)
    check(lal[0] > 0 and any(c["ebene"] == "fenster_gesamt" and c["strafe"] for c in lal[1]["zellen"]),
          "drei Firmen im Fenster alle long: Fenster insgesamt einseitig → Strafe (kein Ausweichen auf „alles eine Richtung“)")
    aussen = [(f"u{i}", "tradeify", "buy", 1000 + i, "tvv2") for i in range(3)]          # nach start_bis 16:30 dt
    la = lage(aussen)
    check(la[0] == 33 and not [c for c in la[1]["zellen"] if c["ebene"] != "tag_firma"],
          "Starts außerhalb der Fenster zählen nur am Tag")
    fe = [{"user_id": "w", "firma": "tradeify", "richtung": "buy", "start": MO + 30}]
    lf = lage([("a", "tradeify", "buy", MO, "tvv2"), ("b", "tradeify", "buy", MO + 9, "tvv2")], fe)
    check(lf[0] > 0 and zellen(lf, "fenster_firma")[("00:00–14:30 dt", "tradeify")]["n"] == 3,
          "fester Trade (heute gestartet, Firma → Futures) zählt im Fenster mit")
    # ap_misch_bewerter (schnell, im Optimierer) = ap_misch_lage auf 300 Zufalls-Zuteilungen (Firmen, Klassen, Fenster, fest, Folgetag)
    rz = random.Random(5)
    firmen_ = [("tradeify", "tvv2"), ("apextrader", "tvv2"), ("fundednext", "mt5v2"), ("the5ers", "mt5v2"), ("topstep", None)]
    abw = 0
    for _ in range(300):
        tr_ = {}
        for n in range(rz.randint(2, 14)):
            f_, r_ = rz.choice(firmen_)
            tr_[f"t{n}"] = {"user": f"u{rz.randint(1, 5)}", "firma": f_, "route": r_, "start": rz.choice([None, 100, 500, 880, 950, 1000]),
                            "n_plaene": rz.randint(1, 2), "folgetag": rz.random() < 0.05}
        fe_ = [{"user_id": f"u{rz.randint(1, 6)}", "firma": rz.choice(firmen_)[0], "richtung": rz.choice(["buy", "sell"]),
                "start": rz.choice([None, 200, 900, 1500])} for _ in range(rz.randint(0, 4))]
        bw = a["ap_misch_bewerter"](tr_, fe_, ZEITEN_LIVE)
        for _k in range(5):
            z_ = {k: rz.choice(["buy", "sell"]) for k in tr_}
            abw += bw(z_) != L(z_, tr_, fe_, ZEITEN_LIVE)[0]
    check(abw == 0, f"ap_misch_bewerter rechnet wie ap_misch_lage (1.500 Zufalls-Zuteilungen, Abweichungen {abw})")
    # SCHRANKE im Optimierer (08.10.2026 abends, Master: Planer-Lauf blockierte ~5–7 s CPU): mit und ohne Schranke dasselbe Ergebnis
    # (Zuteilung, Netto, Wert-Tupel) — 40 Zufalls-Fälle, mit und ohne Einsatz-Kontext, bis 18 Tranchen (> 12 = Würfe + Einzeltausch)
    RD = a["ap_richtungen_delta"]
    rs_ = random.Random(23)
    abw_s = 0
    for _ in range(40):
        tr_, fe_ = {}, []
        for n in range(rs_.randint(2, 18)):
            f_, r_ = rs_.choice(firmen_)
            u_ = f"u{rs_.randint(1, 7)}"
            tr_[f"{u_}|{f_}#{n}"] = {"fest": rs_.choice([None] * 6 + ["buy", "sell"]), "user": u_, "firma": f_, "route": r_,
                                     "start": rs_.randint(0, 985), "delta_abs": rs_.random() * 5, "einsatz_abs": rs_.random() * 900,
                                     "gruppe": f"{u_}|{f_}", "n_plaene": rs_.randint(1, 2)}
        for _k in range(rs_.randint(0, 4)):
            fe_.append({"user_id": f"u{rs_.randint(1, 8)}", "firma": rs_.choice(firmen_)[0], "richtung": rs_.choice(["buy", "sell"]),
                        "start": rs_.randint(0, 985)})
        ek_ = rs_.choice([None, {"basis": rs_.uniform(-500, 500), "brutto": 800.0, "fest_ev": [], "gross_ab": 300.0, "laufzeit": 180}])
        sd_ = rs_.randint(1, 10 ** 6)
        mit = RD(tr_, 0.0, 10.0, random.Random(sd_), 25, (), fe_, versuche=512, einsatz=ek_, mit_wert=True, firma_fest=fe_,
                 zeiten=ZEITEN_LIVE)
        ohne = RD(tr_, 0.0, 10.0, random.Random(sd_), 25, (), fe_, versuche=512, einsatz=ek_, mit_wert=True, firma_fest=fe_,
                  zeiten=ZEITEN_LIVE, ohne_schranke=True)
        abw_s += mit != ohne
    check(abw_s == 0, f"Schranke im Optimierer ändert nie das Ergebnis (40 Zufalls-Fälle, Abweichungen {abw_s})")
    txt = a["ap_misch_text"](lage(tf)[1], lage(tf2)[1], {"tradeify": "Tradeify"})
    check(txt.startswith("Tradeify im Fenster ") and "long/short" in txt, f"ap_misch_text nennt die Zelle mit dem größten Gewinn ({txt})")

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
    verstoss_fenster, fenster_ges = [], {}
    KL = {"Tradeify": "Futures", "Apex Trader": "Futures", "FundedNext": "CFD", "The5%ers": "CFD"}

    def fenster_von(m):
        return "Morgen" if m < 870 else "Opening" if m < 990 else None
    beispiel = None
    seeds = range(10)
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
        # FENSTER (unabhängig nachgerechnet): je Fenster × Firma / × Klasse / gesamt, feste Trades dazu (WD-Long 03:00 dt Morgen,
        # Handplan-Short 15:40 dt Opening)
        zl = {}
        eintr = [(int(g["start"][:2]) * 60 + int(g["start"][3:]), g["firma"], g["richtung"], g["user_id"]) for g in erg["geplant"]]
        eintr += [(180, "Tradeify", "buy", U[6]), (940, "Tradeify", "sell", U[0])]
        for m, f, r, uid in eintr:
            fn = fenster_von(m)
            if not fn:
                continue
            for key in ((fn, f), (fn, KL[f]), (fn, "alle")):
                e = zl.setdefault(key, {"buy": 0, "sell": 0, "gr": set()})
                e[r] += 1
                e["gr"].add(uid + f)
        for key, e in zl.items():
            n = e["buy"] + e["sell"]
            soll = max(1, round(0.3 * n)) if n >= 3 and len(e["gr"]) >= 2 else 0
            if min(e["buy"], e["sell"]) < soll:
                verstoss_fenster.append((seed, key, e["buy"], e["sell"]))
            fg = fenster_ges.setdefault(key, [0, 0])
            fg[0] += e["buy"]
            fg[1] += e["sell"]
        for fn in ("Morgen", "Opening"):
            c, fu = zl.get((fn, "CFD")), zl.get((fn, "Futures"))
            if c and fu and (c["buy"] == 0 or c["sell"] == 0) and (fu["buy"] == 0 or fu["sell"] == 0) \
                    and (c["buy"] > 0) != (fu["buy"] > 0) and c["buy"] + c["sell"] + fu["buy"] + fu["sell"] >= 3:
                verstoss_fenster.append((seed, (fn, "gekippt"), c["buy"], fu["buy"]))
        if beispiel is None:
            beispiel_fenster = {k: (e["buy"], e["sell"]) for k, e in zl.items()}
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
        # Seit 09.10.2026 ~03:45 (Finn: „Mach diese 90-Minuten-Regel weg … nur nie gleichzeitig"): gleiche ID × Firma darf beliebig
        # gegenläufig geplant sein — gezählt wird, ob die Mischung ID × Firma mit ≥ 2 Teilen auch wirklich mischt
        for (uid, f) in {(g["user_id"], g["firma"]) for g in erg["geplant"]}:
            rs = [g["richtung"] for g in erg["geplant"] if g["user_id"] == uid and g["firma"] == f]
            if len(rs) >= 2:
                verstoss_id.append(len(set(rs)) == 2)
        if beispiel is None:
            beispiel = (seed, {f: (e["buy"], e["sell"]) for f, e in je_f.items()}, erg.get("firma_misch"))
    n_tf = sum(gesamt.get("Tradeify", [0, 0]))
    check(n_tf > 0 and not verstoss_misch, f"{len(seeds)} Probeläufe: jede Firma mit ≥ 3 Trades über ≥ 2 IDs hat beide Richtungen "
          f"(seltenere ≥ Soll) — Verstöße {verstoss_misch[:4]}")
    check(verstoss_id and sum(verstoss_id) >= len(verstoss_id) / 2,
          f"ID × Firma mit ≥ 2 Teilen meist gemischt (Strafe „ganz einseitig\", Richtung je Trade frei): {sum(verstoss_id)}/{len(verstoss_id)}")
    check(not verstoss_dicht, f"keine zwei gegenläufigen Starts derselben Firma binnen 3 min — Verstöße {verstoss_dicht[:4]}")
    check(not verstoss_fenster, f"{len(seeds)} Probeläufe: je Fenster × Firma, × Klasse und insgesamt beide Richtungen, kein Kippen "
          f"CFD gegen Futures — Verstöße {verstoss_fenster[:4]}")
    fmf = erg.get("misch_fenster") or []
    check(fmf and any(c["ebene"] == "fenster_klasse" for c in fmf) and all(c.get("strafe", 0) == 0 for c in fmf),
          f"Antwort trägt misch_fenster (Fenster × Firma/Klasse/gesamt), alle ohne Strafe ({len(fmf)} Zellen)")
    check(zaehl["long_mehr"] > 0 and zaehl["short_mehr"] > 0,
          f"kein starres Muster: Tradeify mal long-, mal short-lastig über die Seeds ({zaehl})")
    fm = {x["firma"]: x for x in (beispiel[2] or [])} if beispiel else {}
    check(fm.get("tradeify", {}).get("regel") and fm["tradeify"]["n"] >= 10 and fm["tradeify"]["anteil"] >= 0.3 - 1e-9,
          f"Antwort trägt firma_misch je Firma (Tradeify {fm.get('tradeify')})")
    print("   Beispiel-Tag (seed", beispiel[0], ") long/short je Firma inkl. fester Trades:",
          ", ".join(f"{f} {b}/{s}" for f, (b, s) in sorted(beispiel[1].items())))
    print("   über", len(seeds), "Seeds long/short gesamt:", ", ".join(f"{f} {b}/{s} ({s / (b + s):.0%} short)" for f, (b, s) in sorted(gesamt.items())))
    print("   Beispiel-Tag je Fenster:", ", ".join(f"{fn} {w} {b}/{s}" for (fn, w), (b, s) in sorted(beispiel_fenster.items())))
    print("   über", len(seeds), "Seeds je Fenster:", ", ".join(f"{fn} {w} {b}/{s} ({s / (b + s):.0%} short)"
                                                         for (fn, w), (b, s) in sorted(fenster_ges.items())))

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
    # C5 Finns Abend-Befund (08.10.2026): Tradeify morgens 3× long, im Opening 3× short (je andere IDs) — am Tag 3/3, je Fenster einseitig
    #    → der Bot dreht je Lauf eine ID × Firma, nach zwei Läufen ist jedes Fenster gemischt
    tag6 = [plan(f"m{i}", U[i], "tradeify", 400 + 20 * i, "buy") for i in range(3)] + \
           [plan(f"o{i}", U[3 + i], "tradeify", 900 + 20 * i, "sell") for i in range(3)]
    stand6, gr6 = [dict(p) for p in tag6], []
    for lauf in range(2):
        e6 = Ub(stand6, 0.0, 0.0, jm, Z, 25, random.Random(lauf), einsatz=EK0)
        d6 = {x["plan_id"]: x["nach_richtung"] for x in e6["aenderungen"] if x["art"] == "richtung"}
        gr6 += [x["grund"] for x in e6["aenderungen"] if x["art"] == "richtung"]
        stand6 = [dict(p, richtung=d6.get(p["plan_id"], p["richtung"])) for p in stand6]
    fen6 = {w: {p["richtung"] for p in stand6 if (p["start_min"] < 870) == (w == "Morgen")} for w in ("Morgen", "Opening")}
    check(all(len(v) == 2 for v in fen6.values()) and len(gr6) == 2 and all("im Fenster" in g for g in gr6),
          f"Bot: Tradeify morgens 3× long / Opening 3× short → nach 2 Läufen je Fenster beide Richtungen ({gr6[:1]})")
    # C4 Fall 08.10.2026 10:22 Dubai: Tradeify gemischt (2 gestartete Longs anderer IDs, 1 geplanter Short) und das Buch
    # stark short → die Band-Drehung short → long machte Tradeify 100 % long. Jetzt: nie — auch nicht, wenn die Longs bei Apex liegen
    # (seit 08.10.2026 abends: Futures im selben Fenster sonst 3/0); Kontrolle ohne weitere Trades im Fenster: gedreht
    EKs = {"basis": -1500.0, "brutto": 1500.0, "gross_ab": 100000.0, "laufzeit": 180}
    short1 = [plan("au", U[2], "tradeify", jm + 20, "sell", einsatz_abs=300.0)]

    def gest(firma):
        return [{"user_id": U[0], "firma": firma, "start": jm - 100, "richtung": "buy"},
                {"user_id": U[1], "firma": firma, "start": jm - 90, "richtung": "buy"}]
    dreh_tf = dreh_ap = dreh_leer = 0
    for seed in range(6):
        e4 = Ub(short1, 0.0, 0.0, jm, Z, 25, random.Random(seed), einsatz=EKs, gestartet=gest("tradeify"))
        e4a = Ub(short1, 0.0, 0.0, jm, Z, 25, random.Random(seed), einsatz=EKs, gestartet=gest("apex"))
        e4k = Ub(short1, 0.0, 0.0, jm, Z, 25, random.Random(seed), einsatz=EKs)
        dreh_tf += sum(1 for x in e4["aenderungen"] if x["art"] == "richtung")
        dreh_ap += sum(1 for x in e4a["aenderungen"] if x["art"] == "richtung")
        dreh_leer += sum(1 for x in e4k["aenderungen"] if x["art"] == "richtung")
    check(dreh_leer > 0 and dreh_tf == 0 and dreh_ap == 0,
          f"Band-Drehung macht eine gemischte Firma / ein gemischtes Fenster nie einseitig (Tradeify 2 long + 1 short: {dreh_tf}, "
          f"Apex 2 long + Tradeify short im selben Fenster: {dreh_ap} Drehungen; Kontrolle ohne weitere Trades: {dreh_leer})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
