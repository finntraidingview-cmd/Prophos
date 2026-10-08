#!/usr/bin/env python3
"""Selbsttest TOPSTEP-KETTE (app.py ap_kette_*, ap_konto_rechnen, ap_zeiten_verteilen, 08.10.2026, Slave-Terminal 3 — Finn: je Konto und
Tag am Ende nur „+4.500 $" oder geblowt, aber in ZWEI Trades; Konzept als Baum bestätigt).

Aufruf:  python3 tools/selftest_auto_topstep_kette.py
Ohne Netz, Platzhalter-IDs. Geprüft: Trade 1 (00:00–11:00 dt, SL/TP 1.950–2.650 $, 3–4 NQ, Tagesziel 4.500, Verlustgrenze 4.700);
Trade 1 2–3 NQ, Trade 2 3–4 NQ; Finns Beispiele für Trade 2 (−2.500 → TP 7.000 / SL 2.200; +2.500 → TP 2.000 / SL 7.200); zweiter Tag (154.500, Rest 4.500 + Puffer);
Blow / Tagesziel schon erreicht → kein Trade 2; nur genaue Puls-Nachlesung in TopstepX zählt; ap_kette_tick legt Trade 2 an (Start ≥ Ende
+ 5 min und ≥ 11:00, ≤ 19:30 dt, Bestätigung geerbt, nie doppelt, ohne Nachlesung nichts), Richtung ohne Gegenhedge über IDs; Trade 1
nur bis 11:00 in ap_zeiten_verteilen; Firmen ohne Kette unverändert."""
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


TOPSTEP = {"namen": ["topstep"], "route": "tsv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
           "ziel_pct": {"challenge": 6}, "planen": True,
           "phasen": {"challenge": {"sl": None, "tp": [4350, 4450], "menge": [2, 3], "dd_usd": 4500, "tp_max": 4500, "ziel_pct": 6,
                                    "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}}
KETTE = dict(TOPSTEP, kette={})


def main():
    a = sd.lade()
    R = a["ap_konto_rechnen"]

    # ── 1 Trade 1 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    check(a["ap_kette_regel"](TOPSTEP) is None and a["ap_kette_regel"](KETTE)["tagesziel_usd"] == 4500, "Kette nur mit Block kette, Standardwerte")
    ohne, _ = R(TOPSTEP, "challenge", 150000.0, {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5})
    check(ohne["sl"] is None and ohne["tp"] >= 4350 and "kette" not in ohne, "ohne Kette: wie bisher ein Trade ohne SL")
    werte = [R(KETTE, "challenge", 150000.0, {"tp": u, "sl": 1 - u, "menge": u, "puffer": u})[0] for u in (0.0, 0.37, 0.81, 0.999)]
    check(all(1950 <= w["tp"] <= 2650 and 1950 <= w["sl"] <= 2650 and w["menge"] in (2, 3) for w in werte)
          and {w["menge"] for w in werte} == {2, 3},
          f"Trade 1: TP/SL je 1.950–2.650 $, 2–3 NQ ({[(w['tp'], w['sl'], w['menge']) for w in werte]})")
    w1 = werte[1]
    check(w1["kette"] == {"nr": 1, "tagesziel": 4500, "verlust_grenze": 4700} and w1["risiko"] == w1["sl"] and "Topstep-Kette 1/2" in w1["stufe"],
          f"Tag 1 (150.000): Tagesziel +4.500, Verlustgrenze 4.700 ({w1['kette']})")
    w2, _ = R(KETTE, "challenge", 154500.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5})
    check(4525 <= w2["kette"]["tagesziel"] <= 4540 and w2["kette"]["verlust_grenze"] == 4700,
          f"Tag 2 (154.500): Tagesziel = Rest 4.500 + Puffer ({w2['kette']['tagesziel']}), gleiche Verlustgrenze")
    w3, _ = R(KETTE, "challenge", 157500.0, {"tp": 0.9, "sl": 0.5, "menge": 0.0, "puffer": 0.0})
    check(w3["tp"] == w3["kette"]["tagesziel"] == 1525, f"Rest kleiner als TP von Trade 1: Trade 1 holt das Ziel allein (TP {w3['tp']})")

    # ── 2 Trade 2 aus dem Ergebnis von Trade 1 (Finns Beispiele) ──────────────────────────────────────────────────────────────
    T2 = lambda k, b0, b1: a["ap_kette_trade2"](k, b0, b1, KETTE, a["ap_kette_regel"](KETTE), 0.3)   # noqa: E731
    k1 = {"nr": 1, "tagesziel": 4500, "verlust_grenze": 4700}
    v, _ = T2(k1, 150000, 147500)
    check((v["tp"], v["sl"], v["e1"]) == (7000, 2200, -2500.0) and v["menge"] in (3, 4), f"SL −2.500 → TP 7.000 / SL 2.200, Trade 2 3–4 NQ ({v})")
    check({a["ap_kette_trade2"](k1, 150000, 147500, KETTE, a["ap_kette_regel"](KETTE), u_)[0]["menge"] for u_ in (0.0, 0.99)} == {3, 4},
          "Trade 2: 3–4 NQ (t2_menge), Trade 1 2–3 NQ (menge) — Finn 08.10.2026")
    v, _ = T2(k1, 150000, 152500)
    check((v["tp"], v["sl"]) == (2000, 7200), f"TP +2.500 → TP 2.000 / SL 7.200 ({v['tp']} / {v['sl']})")
    v, _ = T2({"nr": 1, "tagesziel": 4530, "verlust_grenze": 4700}, 154500, 152000)
    check((v["tp"], v["sl"]) == (7030, 2200), f"Tag 2: −2.500 → TP 7.030 / SL 2.200 ({v['tp']} / {v['sl']})")
    check(T2(k1, 150000, 145400)[0] is None and "geblowt" in T2(k1, 150000, 145400)[1], "Trade 1 geblowt → kein Trade 2")
    check(T2(k1, 150000, 154480)[0] is None and "Tagesziel" in T2(k1, 150000, 154480)[1], "Tagesziel schon erreicht → kein Trade 2")
    check(T2(k1, 0, 147500)[0] is None and "unplausibel" in T2(k1, 0, 147500)[1], "Start relativ, Ende absolut → unplausibel, kein Trade 2")
    fertig = a["ap_kette_t1_fertig"]
    gut = {"mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "puls", "plattform": "tsx"}}}
    check(fertig(gut) == ((150000.0, 147500.0), None), "genaue Puls-Nachlesung in TopstepX → fertig")
    check(fertig({"mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "hand"}}})[0] is None
          and fertig({"mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "puls", "plattform": "tsx",
                                                                                  "balance_quelle": "folgetrade"}}})[0] is None
          and fertig({"mt5_baseline": {"final": {"balance_end": 1, "quelle": "puls", "plattform": "tsx"}}})[0] is None,
          "Hand-Ende, Folgetrade-Wert oder ohne Start-Balance → wartet")

    # ── 3 ap_kette_tick: Trade 2 anlegen ──────────────────────────────────────────────────────────────────────────────────
    BER = ZoneInfo("Europe/Berlin")
    jetzt = datetime(2026, 10, 9, 10, 2, tzinfo=BER).astimezone(timezone.utc)          # 10:02 dt, Trade 1 endete 09:58
    mitt = datetime(2026, 10, 9, tzinfo=BER)
    U1, U2 = sd.U1, sd.U2
    t1 = {"id": "00000000-0000-0000-0000-00000000k001", "user_id": U1, "master_account_id": "k-ts", "master_firm": "Topstep",
          "master_name": "TS-000000", "master_symbol": "NQZ6", "richtung": "buy", "auto_plan": True, "auto_bestaetigt_at": "2026-10-08T22:00:00Z",
          "ended_at": (mitt + timedelta(hours=9, minutes=58)).isoformat(), "planned_for": "2026-10-09", "status": "review",
          "mt5_baseline": {"kette": k1, "tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "puls", "plattform": "tsx"}}}
    zustand = {"t1": [t1], "t2": [], "ins": []}
    andere = []

    def sb_select(table, params):
        if table == "auto_plan_regeln":
            return [{"id": 1, "zeiten": {"tz": "Europe/Berlin", "fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30"},
                     "regeln": {"firmen": [KETTE], "ausgleich": {"laufzeit_min": 180}}}]
        if table == "trade_plans" and params.get("route") == "eq.tsv2":
            return [dict(x) for x in zustand["t1"]]
        if table == "trade_plans" and "mt5_baseline->kette->>vor" in params:
            return [{"id": "x", "vor": x["mt5_baseline"]["kette"]["vor"]} for x in zustand["ins"]]
        return []

    def stand_laden(reg, j=None, *a_, **k_):
        jm = (j - mitt).total_seconds() / 60.0
        return {"mitternacht": mitt, "jetzt_min": jm, "zeiten": reg["zeiten"], "offen": [], "geplant": list(andere), "folgetag": [],
                "starts_heute": [{"user_id": U1, "firma": "topstep", "start": 400.0, "richtung": "buy"}], "id_fest": {}, "firmen": [KETTE]}
    a["sb_select"] = sb_select
    a["requests"] = __import__("requests")
    a["sb_insert"] = lambda t, z: zustand["ins"].append(z) or z
    gruende_db = []
    a["_ap_kette_grund"] = lambda t1_, g: gruende_db.append((t1_["id"], g))
    a["_ap_stand_laden"] = stand_laden
    erg = a["ap_kette_tick"](jetzt, random.Random(3))
    z = zustand["ins"][0] if zustand["ins"] else {}
    st = datetime.fromisoformat(z.get("start_um", "2000-01-01T00:00:00+00:00")).astimezone(BER) if z else None
    check(len(zustand["ins"]) == 1 and (z["master_tp"], z["master_sl"]) == (7000, 2200) and z["route"] == "tsv2"
          and z["mt5_baseline"]["kette"]["nr"] == 2 and z["mt5_baseline"]["kette"]["vor"] == t1["id"] and z["master_contracts"] in (3, 4),
          f"Trade 2 angelegt: TP 7.000 / SL 2.200, Kette 2 nach Trade 1 ({erg.get('neu')})")
    check(st is not None and st.hour * 60 + st.minute >= 11 * 60 and st.hour * 60 + st.minute < 19 * 60 + 30,
          f"Start im Fenster 11:00–19:30 dt ({st.strftime('%H:%M') if st else '—'})")
    check(bool(z.get("auto_bestaetigt_at")) and z.get("auto_plan") is True and "Topstep-Kette 2/2" in z.get("notes", ""),
          "Bestätigung von Trade 1 geerbt, Notiz „Topstep-Kette 2/2“")
    check(any("Trade 2 angelegt" in g for _i, g in gruende_db), "Ergebnis an Trade 1 sichtbar (kette.t2_grund)")
    a["ap_kette_tick"](jetzt, random.Random(4))
    check(len(zustand["ins"]) == 1, "zweiter Takt: nie doppelt")
    # Unique-Index meldet 409 (zweiter Container war schneller) → still „schon da", kein Fehler
    class _R:
        status_code = 409
    import requests as _rq
    ins_alt = a["sb_insert"]
    a["sb_insert"] = lambda t, z: (_ for _ in ()).throw(_rq.exceptions.HTTPError(response=_R()))
    zustand.update(ins=[])
    e409 = a["ap_kette_tick"](jetzt, random.Random(5))
    check(e409.get("neu") == [], "409 vom Unique-Index → kein Fehler, nichts doppelt")
    a["sb_insert"] = ins_alt
    zustand.update(ins=[z])
    # ohne genaue Nachlesung: nichts
    zustand.update(t1=[dict(t1, id="00000000-0000-0000-0000-00000000k002", mt5_baseline=dict(t1["mt5_baseline"], final={"quelle": "hand", "balance_end": 147500}))], ins=[])
    e2 = a["ap_kette_tick"](jetzt, random.Random(3))
    check(not zustand["ins"] and "Nachlesung" in " ".join((e2.get("gruende") or {}).values())
          and any("Nachlesung" in g for _i, g in gruende_db), f"ohne genaue Nachlesung kein Trade 2, Grund am Trade 1 ({e2.get('gruende')})")
    # über IDs (seit 08.10.2026 ~17:00 Dubai, Finn: „kann natürlich eine ANDERE ID … short gehen"): andere ID bei Topstep um 11:10 dt
    # SHORT geplant → Trade 2 darf LONG sein, startet aber nie ±AP_GEGEN_FIRMA_MIN (3 min) neben diesem Short
    zustand.update(t1=[t1], ins=[])
    andere[:] = [{"plan_id": "p-x", "user_id": U2, "user": "X", "firma_key": "topstep", "firma": "Topstep", "richtung": "sell", "start_min": 670.0,
                  "delta_abs": 1.0, "aenderbar": False, "fest_durch": "Handplan", "einsatz_abs": 0.0}]
    gegen_ok = True
    for seed in range(12):
        zustand["ins"] = []
        a["ap_kette_tick"](jetzt, random.Random(seed))
        for zz in zustand["ins"]:
            m = (datetime.fromisoformat(zz["start_um"]) - mitt).total_seconds() / 60.0
            if zz["richtung"] == "buy" and abs(m - 670.0) <= a["AP_GEGEN_FIRMA_MIN"]:
                gegen_ok = False
    check(gegen_ok, "Trade 2 nie ±3 min neben einem gegenläufigen Plan einer anderen ID derselben Firma (Laufzeit über IDs frei)")

    # ── 3b automatisch abhaken (Finn 08.10.2026: nach der Prüfung direkt erledigt, nicht mehr im Radar abhaken) ───────────────
    rev = [dict(t1, id="r-t1", route="tsv2", status="review", updated_at="2026-10-09T08:00:00Z", master_pl=None, konto_typ=None),
           {"id": "r-t2", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "2026-10-09T13:00:00Z", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-t1", "verlust_grenze": 4700, "balance_start_tag": 150000},
                             "tv": {"balance_start": 147500}, "final": {"balance_end": 145480, "quelle": "puls", "plattform": "tsx"}}},
           dict(t1, id="r-warte", status="review", mt5_baseline=dict(t1["mt5_baseline"], final={"quelle": "hand", "balance_end": 1})),
           {"id": "r-t2b", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "y", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x", "verlust_grenze": 4700, "tagesziel": 4500, "balance_start_tag": 150000},
                             "tv": {"balance_start": 152650}, "final": {"balance_end": 145480, "quelle": "puls", "plattform": "tsx"}}},
           dict(t1, id="r-relativ", route="tsv2", status="review", updated_at="x",
                mt5_baseline=dict(t1["mt5_baseline"], final={"quelle": "puls", "plattform": "tsx", "balance_end": 2000}))]
    upds, gruende_ab = [], []
    a["_ap_kette_grund"] = lambda t_, g: gruende_ab.append((t_["id"], g))
    a["sb_select"] = lambda t, prm: [dict(x) for x in rev] if prm.get("status") == "eq.review" else []
    a["sb_update"] = lambda t, f, u: upds.append((f, u)) or [u]
    weg = a["ap_kette_abhaken"](jetzt)
    u1 = next((u for f, u in upds if f["id"] == "eq.r-t1"), {})
    u2 = next((u for f, u in upds if f["id"] == "eq.r-t2"), {})
    check(sorted(weg) == ["r-t1", "r-t2", "r-t2b"] and u1.get("status") == "completed" and u1.get("master_pl") == -2500.0
          and u1.get("pl_quelle") == "tv" and u1.get("konto_typ") == "challenge" and not u1.get("blown")
          and all(f.get("status") == "eq.review" and f.get("updated_at") for f, _u in upds),
          f"Trade 1 nach genauer Lesung automatisch erledigt (P&L −2.500, pl_quelle tv, Sperre review/updated_at) — {weg}")
    check(u2.get("master_pl") == -2020.0 and u2.get("blown") is True,
          "Trade 2: −2.020 nach −2.500 = Tag −4.520 → blown (Tag zählt, nicht nur der eigene P&L)")
    u2b = next((u for f, u in upds if f["id"] == "eq.r-t2b"), {})
    check(u2b.get("master_pl") == -7170.0 and u2b.get("blown") is True,
          f"Trade 2 nach +2.650 blowt mit −7.170 eigenem P&L → trotzdem plausibel, abgehakt + blown ({u2b.get('master_pl')})")
    check("eq.r-warte" not in [f["id"] for f, _u in upds], "ohne genaue Puls-Lesung bleibt der Trade in Überprüfen")
    check("eq.r-relativ" not in [f["id"] for f, _u in upds] and any(i == "r-relativ" and "unplausibel" in g for i, g in gruende_ab),
          "Start absolut 150.000, Ende relativ 2.000 → nicht abgehakt, Grund „unplausibel — von Hand abhaken“ (Prüfer Slave 2)")

    # ── 4 Trade 1 nur bis 11:00 dt im Planer ──────────────────────────────────────────────────────────────────────────────
    Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30"}
    tr = [{"key": f"u{i}|topstep", "user": f"u{i}", "gruppe": f"u{i}|topstep", "fkey": "topstep", "dauer_min": 2, "bis_min": 660} for i in range(6)]
    spaet = 0
    for seed in range(50):
        for _k, mm in a["ap_zeiten_verteilen"](tr, Z, random.Random(seed)).items():
            spaet += mm >= 660
    check(spaet == 0, f"ap_zeiten_verteilen: Trade 1 nie ab 11:00 dt (50 Seeds, {spaet} zu spät)")

    # ── 5 Bot: Topstep V2 ohne Kette fest (startet nur von Hand), Kette fest (Befund Slave 4: Suche zog Topstep „über Fenster" vor) ──
    BER5 = ZoneInfo("Europe/Berlin")
    tag5 = datetime.now(timezone.utc).astimezone(BER5) + timedelta(days=1)
    mitt5 = datetime(tag5.year, tag5.month, tag5.day, tzinfo=BER5)
    jetzt5 = mitt5 + timedelta(hours=6)

    def p5(pid, start, **kw):
        return dict({"id": pid, "user_id": sd.U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "sell",
                     "master_tp": 2000, "master_sl": 2200, "master_contracts": 3, "route": "tsv2", "master_symbol": "NQZ6",
                     "start_um": (mitt5 + timedelta(hours=start)).isoformat(), "auto_plan": True, "auto_bestaetigt_at": jetzt5.isoformat(),
                     "created_at": jetzt5.isoformat()}, **kw)
    b = sd.lade()
    reg5, _g5 = sd.db_stubs(b, jetzt5, [p5("p-ts", 15), p5("p-kt", 9, kt={"nr": 1, "tagesziel": 4500}), p5("p-mt", 10, route="mt5v2")])
    st5 = {z["plan_id"]: z for z in b["_ap_stand_laden"](reg5, jetzt=jetzt5)["geplant"]}
    check(st5["p-ts"]["fest_durch"] == b["AP_FEST_TSV2"] and st5["p-kt"]["fest_durch"] == b["AP_FEST_KETTE"] and st5["p-mt"]["aenderbar"],
          f"Stand: Topstep V2 ohne Kette fest „von Hand“, Kette fest, Echo änderbar ({ {k: v['fest_durch'] for k, v in st5.items()} })")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
