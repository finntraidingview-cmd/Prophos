#!/usr/bin/env python3
"""Selbsttest FIRMEN-ABSTAND (app.py + sql/2026-10-08_firmen_abstand_riegel.sql, 08.10.2026, Slave-Terminal 3 — Finn zu The5%ers
Finn + Pascal 04:24, Jacob 04:23 Dubai: „dass bei zwei verschiedenen IDs zur selben Uhrzeit bei derselben Prop-Firm zwei Trades
aufgehen. Das ist mies auffällig. Immer mindestens 5 Minuten Abstand … Korrelation").

Aufruf:  python3 tools/selftest_auto_firmen_abstand.py
Ohne Netz, Platzhalter-IDs. Geprüft: (1) ap_zeiten_verteilen — Starts verschiedener IDs bei derselben Firma ≥ AP_FIRMA_ABSTAND_MIN,
auch gegen schon geplante/gestartete (bestehend[fkey]), gleiche ID oder andere Firma frei, Abstände gestreut statt starr 5:00,
enges Fenster ohne Fehler; (2) Bot-Verteilung — The5%ers 04:23/04:24/04:24 über mehrere Läufe repariert, nur nach hinten, eine
Gruppe je Lauf, Richtung nie, gegen gestartete und Hand-Pläne; (3) SQL-Riegel — prophos_firma_key liefert für alle Schreibweisen
dasselbe wie app.py _firm_norm (Bedingungen direkt aus dem SQL-Text ausgewertet), Trigger sitzt auf dem Claim und gibt NULL zurück."""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

SQL = os.path.join(HIER, "..", "sql", "2026-10-08_firmen_abstand_riegel.sql")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def sql_firma_key(sql_text):
    """prophos_firma_key aus dem SQL-Text als Python-Funktion: jede Zeile `if <Bedingung> then return '<X>'; end if;` in Reihenfolge."""
    rumpf = sql_text[sql_text.index("function public.prophos_firma_key"):]
    rumpf = rumpf[rumpf.index("begin"):rumpf.index("return btrim")]
    rumpf = re.sub(r"--[^\n]*", "", rumpf)
    regeln = []
    for bed, wert in re.findall(r"if (.+?) then return '([^']*)'; end if;", rumpf, re.S):
        py = re.sub(r"strpos\(f, '([^']*)'\) > 0", lambda m: repr(m.group(1)) + " in f", " ".join(bed.split()))
        py = py.replace("f = ''", "f == ''")
        regeln.append((compile(py, "sql", "eval"), wert))

    def key(name):
        f = (name or "").strip().lower()
        for c, w in regeln:
            if eval(c, {}, {"f": f}):        # noqa: S307 — nur der eigene SQL-Text
                return w
        return (name or "").strip()
    return key, len(regeln)


def main():
    a = sd.lade()
    src = open(sd.APP, encoding="utf-8").read()
    exec("\n".join([re.search(r"^_FIRM_RULES = \[.*?^\]", src, re.M | re.S).group(0),
                    src[src.index("\ndef _firm_norm(") + 1:src.find("\n\n\n", src.index("\ndef _firm_norm("))]]), a)
    GFA = a["AP_FIRMA_ABSTAND_MIN"]
    verteilen = a["ap_zeiten_verteilen"]
    Z = {"fenster": [["00:00", "16:30", 1]], "start_bis": "16:30"}

    # ── 1 Planer ────────────────────────────────────────────────────────────────────────────────────────────────────────────
    eng = {"fenster": [["02:00", "02:40", 1]], "start_bis": "16:30"}
    tr = [{"key": f"u{i}|the5ers", "user": f"u{i}", "gruppe": f"u{i}|the5ers", "fkey": "the5ers", "dauer_min": 2} for i in range(5)]
    tr += [{"key": "u0|apex", "user": "u0", "gruppe": "u0|apex", "fkey": "apex", "dauer_min": 2},
           {"key": "u9|apex", "user": "u9", "gruppe": "u9|apex", "fkey": "apex", "dauer_min": 2}]
    verstoss, fehlt, abstaende = 0, 0, []
    for seed in range(200):
        m = verteilen(tr, eng, random.Random(seed))
        fehlt += sum(1 for t in tr if t["key"] not in m)
        for x in tr:
            for y in tr:
                if x["key"] < y["key"] and x["key"] in m and y["key"] in m and x["fkey"] == y["fkey"] and x["user"] != y["user"]:
                    d = abs(m[x["key"]] - m[y["key"]])
                    verstoss += d < GFA
                    abstaende.append(d)
    check(fehlt == 0, f"enges Fenster (40 min, 5 IDs bei The5%ers + 2 bei Apex): alle gesetzt (fehlend {fehlt})")
    check(verstoss == 0, f"verschiedene IDs bei derselben Firma ≥ {GFA:g} min (200 Seeds, Verstöße {verstoss})")
    nah = sorted(d for d in abstaende if d < 2 * GFA)
    check(len(set(nah)) > 2, f"Abstände gestreut, nicht starr {GFA:g}:00 ({sorted(set(nah))[:6]} …)")
    best = [{"user": "jacob", "start": 143, "dauer_min": 2, "gruppe": "jacob|the5ers", "fkey": "the5ers"}]
    v = 0
    for seed in range(100):
        m = verteilen([dict(tr[0], key="finn|the5ers", user="finn", gruppe="finn|the5ers")],
                      {"fenster": [["02:20", "02:35", 1]], "start_bis": "16:30"}, random.Random(seed), bestehend=best)
        v += sum(1 for s in m.values() if abs(s - 143) < GFA)
    check(v == 0, "auch gegen einen schon geplanten/gestarteten Plan einer anderen ID (bestehend[fkey])")
    gleich = verteilen([{"key": "a", "user": "u1", "gruppe": "u1|x", "fkey": "x", "dauer_min": 2}],
                       {"fenster": [["02:00", "02:12", 1]], "start_bis": "16:30"}, random.Random(1),
                       bestehend=[{"user": "u1", "start": 121, "dauer_min": 2, "gruppe": "u1|y", "fkey": "x"}])
    check("a" in gleich, "gleiche ID: der Firmen-Abstand gilt nur zwischen VERSCHIEDENEN IDs (PC-Regel bleibt)")

    # ── 2 Bot-Verteilung: The5%ers Finn + Pascal 04:24, Jacob 04:23 Dubai (dt = Dubai − 120) ──────────────────────────────────
    U = a["ap_umplanen"]

    def plan(pid, uid, firma, start, richtung="buy", **kw):
        return dict({"plan_id": pid, "user_id": uid, "user": uid.capitalize(), "firma": firma, "firma_name": "The5%ers", "richtung": richtung,
                     "start_min": float(start), "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "fest_durch": None,
                     "auto_plan": True, "bestaetigt": True, "route": "tvv2"}, **kw)
    d = lambda h, m: h * 60 + m - 120     # noqa: E731
    pl = [plan("jacob", "jacob", "the5ers", d(4, 23), "sell"), plan("finn", "finn", "the5ers", d(4, 24)),
          plan("pascal", "pascal", "the5ers", d(4, 24), "sell")]
    start0 = {p["plan_id"]: p["start_min"] for p in pl}
    jm, zuletzt, alle, je_lauf = d(4, 5), {}, [], []
    for lauf in range(5):
        erg = U(pl, 0.0, 0.0, jm, Z, 100, random.Random(lauf), zuletzt=zuletzt, dubai_min=120)
        v_ = [x for x in erg["aenderungen"] if x["art"] == "start"]
        je_lauf.append({x["user_id"] for x in v_})
        alle += erg["aenderungen"]
        neu = {x["plan_id"]: x["nach_start_min"] for x in v_}
        pl = [dict(p, start_min=neu.get(p["plan_id"], p["start_min"])) for p in pl]
        for x in v_:
            zuletzt[x["plan_id"]] = jm
        jm += 3
    st = {p["plan_id"]: p["start_min"] for p in pl}
    s = sorted(st.values())
    check(min(b - a_ for a_, b in zip(s, s[1:])) >= GFA, f"The5%ers 04:23/04:24/04:24 → alle ≥ {GFA:g} min auseinander "
          f"({['%02d:%02d' % divmod(int(x + 120), 60) for x in s]} Dubai)")
    check(st["jacob"] == start0["jacob"], "der früheste (Jacob 04:23) bleibt stehen")
    check(all(st[i] >= start0[i] for i in st) and all(x["nach_richtung"] == x["von_richtung"] for x in alle),
          "nur nach hinten, Richtung nie geändert")
    check(all(len(g) <= 1 for g in je_lauf), "höchstens eine Gruppe je Bot-Lauf")
    # Finn (Buy) hält seit 08.10.2026 AP_GEGEN_FIRMA_MIN (30) zu den Shorts von Jacob/Pascal — Gegenhedge über IDs gesperrt
    check(all(st[i] - start0[i] <= 45 for i in st), f"nur so weit wie nötig + Streuung (≤ 45 min: {[round(st[i] - start0[i]) for i in st]})")
    check(all(abs(st["finn"] - st[k]) > a["AP_GEGEN_FIRMA_MIN"] for k in ("jacob", "pascal")),
          "Finn (Buy) > 30 min zu den Shorts der anderen IDs derselben Firma — kein Gegenhedge über IDs")
    g_ = next((x["grund"] for x in alle), "")
    check(g_.startswith("Verteilung: "), f"Protokoll-Grund ({g_[:80]})")
    # gegen einen schon GESTARTETEN Plan einer anderen ID
    e = U([plan("finn", "finn", "the5ers", d(4, 24))], 0.0, 0.0, d(4, 5), Z, 100, random.Random(1),
          gestartet=[{"user_id": "jacob", "firma": "the5ers", "start": float(d(4, 23)), "richtung": "sell"}])
    n_ = next((x["nach_start_min"] for x in e["aenderungen"] if x["plan_id"] == "finn"), None)
    check(n_ is not None and n_ - d(4, 23) >= GFA, "gegen einen schon gestarteten Trade einer anderen ID: Plan rückt nach hinten")
    # Handplan der anderen ID steht fest → der änderbare weicht
    e = U([plan("finn", "finn", "the5ers", d(4, 24), auto_plan=False, aenderbar=False, fest_durch="Handplan"),
           plan("pascal", "pascal", "the5ers", d(4, 24))], 0.0, 0.0, d(4, 5), Z, 100, random.Random(1))
    ids = {x["plan_id"] for x in e["aenderungen"]}
    check(ids == {"pascal"}, f"Handplan bleibt, der Auto-Plan der anderen ID weicht ({sorted(ids)})")
    # andere Firma oder gleiche ID: nichts zu tun
    e = U([plan("finn", "finn", "the5ers", d(4, 24)), plan("pascal", "pascal", "apex", d(4, 24))], 0.0, 0.0, d(4, 5), Z, 100, random.Random(1))
    check(not e["aenderungen"], "andere Firma zur selben Minute: kein Eingriff")

    # ── 2b GEGENHEDGE ÜBER IDs (08.10.2026: Trockenlauf zog Chris FundedNext BUY auf 05:57, während Jacob FundedNext SELL lief) ──────
    EKg = {"basis": -800.0, "brutto": 800.0, "gross_ab": 100000.0, "laufzeit": 60}
    pg = [plan("chris_fn", "chris", "fundednext", d(10, 38), "buy"), plan("emin_tf", "emin", "tradeify", d(11, 0), "buy")]
    lauf_g = [{"user_id": "jacob", "firma": "fundednext", "richtung": "sell", "start": None}]
    eg = U(pg, 0.0, 0.0, d(5, 50), Z, 25, random.Random(1), einsatz=EKg, laufend=lauf_g, dubai_min=120)
    vg = [x["plan_id"] for x in eg["aenderungen"] if x["art"] == "start"]
    check("chris_fn" not in vg and vg == ["emin_tf"],
          f"Vorziehen: Chris FundedNext BUY nicht neben Jacobs laufenden FundedNext SELL — stattdessen ein anderer Long ({vg})")
    sperre = a["_ap_gegen_firma"]
    check(sperre(200, "chris", "fundednext", "buy", [], lauf_g, 190, 60) and not sperre(200, "chris", "tradeify", "buy", [], lauf_g, 190, 60)
          and not sperre(200, "jacob", "fundednext", "buy", [], lauf_g, 190, 60) and not sperre(200, "chris", "fundednext", "sell", [], lauf_g, 190, 60),
          "_ap_gegen_firma: nur andere ID + gleiche Firma + Gegenrichtung sperrt")
    check(sperre(200, "chris", "fundednext", "buy", [(225, "sell", "jacob", "fundednext")], [], 100, 60)
          and not sperre(200, "chris", "fundednext", "buy", [(235, "sell", "jacob", "fundednext")], [], 100, 60),
          "geplante Gegenrichtung einer anderen ID: ≤ 30 min gesperrt, 35 min frei")

    # ── 2b' BAND-SCHRITT (Prüfer Slave 2 zu 3d43e4e): weder Drehen noch Verschieben neben eine Gegenrichtung einer anderen ID je Firma ──
    Zb = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
    pb = [dict(plan("a_ap", "u-a", "apex", d(9, 0), "buy"), delta_abs=5.0, einsatz_abs=0.0, bestaetigt=False)]
    frei_b = U(pb, 6.0, 6.0, d(8, 30), Zb, 15, random.Random(1))
    dreh_frei = [x for x in frei_b["aenderungen"] if x["art"] == "richtung"]
    lauf_b = [{"user_id": "u-b", "firma": "apex", "richtung": "buy", "start": None}]
    mit_b = U(pb, 6.0, 6.0, d(8, 30), Zb, 15, random.Random(1), laufend=lauf_b)
    dreh_mit = [x for x in mit_b["aenderungen"] if x["art"] == "richtung"]
    check(dreh_frei and not dreh_mit,
          f"Band-Schritt dreht A Apex buy → sell nur ohne laufenden Apex-Buy einer anderen ID ({len(dreh_frei)} → {len(dreh_mit)})")
    verstoss_b = 0
    plan_b = [dict(plan("a_ap", "u-a", "apex", d(10, 0), "buy"), delta_abs=5.0, einsatz_abs=0.0, bestaetigt=False),
              dict(plan("b_ap", "u-b", "apex", d(9, 0), "sell"), delta_abs=1.0, einsatz_abs=0.0, aenderbar=False, fest_durch="Handplan")]
    lauf_s = [{"user_id": "u-c", "firma": "apex", "richtung": "sell", "start": None}]
    for seed in range(40):
        eb = U(plan_b, 6.0, 6.0, d(8, 30), Zb, 15, random.Random(seed), laufend=lauf_s, id_fest={"u-a|apex": {"richtung": "buy"}})
        for x in eb["aenderungen"]:
            if x["art"] == "start" and x["plan_id"] == "a_ap":
                t_ = x["nach_start_min"]
                if a["_ap_gegen_firma"](t_, "u-a", "apex", "buy", [(d(9, 0), "sell", "u-b", "apex")], lauf_s, d(8, 30), None):
                    verstoss_b += 1
    check(verstoss_b == 0, f"Band-Schritt verschiebt (40 Seeds) nie neben laufende/≤ 30 min nahe Gegenrichtung einer anderen ID (Verstöße {verstoss_b})")

    # ── 2c ABSTAND JE ID ÜBER FIRMEN (Slave 4: Chris FundedNext 18:06 + Topstep 18:13 = 7 min) ───────────────────────────────────────
    pk = [plan("c_fn", "chris", "fundednext", d(18, 6), "buy"), plan("c_ts", "chris", "topstep", d(18, 13), "sell")]
    ek0 = {"basis": 0.0, "brutto": 0.0, "gross_ab": 100000.0, "laufzeit": 60}
    Zl = {"fenster": [["00:00", "14:30", 50], ["14:30", "18:00", 50]], "start_bis": "18:00", "abstand_id_min": 3}
    ek = U(pk, 0.0, 0.0, d(9, 0), Zl, 100, random.Random(1), einsatz=ek0, dubai_min=120)
    nk = {x["plan_id"]: x["nach_start_min"] for x in ek["aenderungen"] if x["art"] == "start"}
    sk = {p["plan_id"]: nk.get(p["plan_id"], p["start_min"]) for p in pk}
    check("c_ts" in nk and sk["c_ts"] - sk["c_fn"] >= a["AP_ABSTAND_ID_MIN"] * 0.5 and nk["c_ts"] - d(18, 13) >= 5,
          f"Chris FundedNext 18:06 + Topstep 18:13: Topstep rückt nach hinten, ≥ 5 min, Abstand {sk['c_ts'] - sk['c_fn']:g} min")

    # ── 3 SQL-Riegel ──────────────────────────────────────────────────────────────────────────────────────────────────────
    sql = open(SQL, encoding="utf-8").read()
    key, n = sql_firma_key(sql)
    namen = ["The5%ers", "The 5%ers", "the5ers", "Five Percent Online", "FundedNext", "FundedNext Futures", "Funded Next Futures",
             "MyFundedFutures", "MyFoundedFutures", "Apex", "Apex Trader", "Tradeify", "FundingPips", "Funding Pips", "Topstep",
             "TopstepX", "FTMO", "Alpha Futures", "Fusion Markets", "Lucid Trading", "Blue Guardian", "", "  Blue Guardian  "]
    abw = [(x, key(x), a["_firm_norm"](x)) for x in namen if key(x) != a["_firm_norm"](x)]
    check(n >= 12 and not abw, f"prophos_firma_key = app.py _firm_norm für {len(namen)} Schreibweisen ({n} Regeln; Abweichungen {abw})")
    rules = re.search(r"^_FIRM_RULES = \[.*?^\]", src, re.M | re.S).group(0)
    nadeln = re.findall(r'\("([^"]+)",', rules)
    check(all(f"'{x}'" in sql for x in nadeln), "jede Nadel aus _FIRM_RULES steht im SQL")
    check(re.search(r"before update of start_um_gestartet_at on public\.trade_plans", sql) is not None
          and "when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)" in sql,
          "Trigger sitzt genau auf dem Claim (start_um_gestartet_at NULL → gesetzt)")
    rumpf = sql[sql.index("function public.trade_plans_firmen_abstand"):]
    check("return null;" in rumpf and "pg_advisory_xact_lock" in rumpf and "interval '5 minutes'" in rumpf
          and "p.user_id is distinct from new.user_id" in rumpf,
          "Riegel: andere ID, 5 min, Lock je Firma, Claim nicht schreiben (NULL → Tab startet nicht)")
    check("'start'" in rumpf and "auto_plan_umplanung" in rumpf, "Protokoll in auto_plan_umplanung (quelle 'start', erlaubt seit 2026-10-07)")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
