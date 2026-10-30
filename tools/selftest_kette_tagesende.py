#!/usr/bin/env python3
"""Selbsttest TAGESENDE TOPSTEP (app.py ap_kette_abhaken, ap_kette_letzter_trade, ap_kette_tagesende, ap_planen, _ap_plan_am_tag, 30.10.2026 —
Finn 13:41: „Nach dem ersten Trade nicht, weil ja beide Trades am Tag durchlaufen müssen, aber nach dem zweiten dann, dass ich das
Endresultat vom Tag sehe und das auch noch abhaken muss.")

Aufruf:  python3 tools/selftest_kette_tagesende.py
Ohne Netz, Platzhalter-IDs. Geprüft: 1/2 bleibt automatisch (kein review), 2/2 / Reparatur-Tag / 1/2 geblowt / 1/2 am Tagesziel bleiben in
review mit Tagesergebnis; kein minütliches Neuschreiben; Regel-Lesefehler stoppt die Kette nicht; der echte Planer-Lauf plant am Folgetag
trotz offenem Haken, am selben Tag nicht, geblowt nicht; Nachplanen ebenso; ohne Tagesergebnis sperrt review weiter."""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_alle_ids as al  # noqa: E402
import selftest_kette_mll_planer as mp  # noqa: E402

FEHLER = []
U1 = "00000000-0000-0000-0000-000000000001"


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def plan(pid, kette, start, ende, **kw):
    return dict({"id": pid, "route": "tsv2", "status": "review", "user_id": U1, "master_firm": "Topstep", "updated_at": pid, "ended_at": "2026-10-30T09:00:00Z",
                 "mt5_baseline": {"kette": kette, "tv": {"balance_start": start}, "final": {"balance_end": ende, "quelle": "puls", "plattform": "tsx"}}}, **kw)


GESUND = {"tagesziel": 4500, "verlust_grenze": 2775, "daily_usd": 3000, "dll_puffer": 225, "mll": 145500.0}


def abhaken(rows, regeln_fehler=False, t2_da=True, jetzt=None, gesperrt=False, t2_lesefehler=False):
    a = al.lade()
    upds, rpcs = [], []

    class _Antwort:
        status_code = 200

    def sb_select(t, prm):
        if t == "auto_plan_regeln":
            if regeln_fehler:
                raise RuntimeError("Supabase weg (Test)")
            return [{"regeln": {"firmen": [mp.TOPSTEP]}}]
        if "mt5_baseline->kette->>vor" in prm:
            if t2_lesefehler:
                raise RuntimeError("Supabase weg (Test)")
            return [{"id": "t2"}] if t2_da else []
        return [dict(x) for x in rows] if prm.get("status") == "eq.review" else []
    a["sb_select"] = sb_select
    a["sb_update"] = lambda t, f, u: upds.append((f, u)) or [u]
    a["_sb_anfrage"] = lambda m, url, **kw: rpcs.append(kw["json"]) or _Antwort()
    a["_sb_pruefen"] = lambda r: None
    a["_sb_headers"] = lambda: {}
    a["SUPABASE_URL"] = "http://test"
    a["_ap_sperren"] = lambda: {}
    a["ap_firma_gesperrt"] = lambda k, s: gesperrt
    weg = a["ap_kette_abhaken"](jetzt or datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc))
    u = {f["id"][3:]: x for f, x in upds}
    r = {x["p_plan"]: x for x in rpcs}
    return weg, u, r


def planer(plaene, stand="2999-01-01"):
    """Echter ap_planen-Lauf (trocken) für das Topstep-Konto aus selftest_kette_mll_planer, seine Pläne kommen nur bei select mit kette_te."""
    a = al.lade()
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    reg, _g, _i = al.db_stubs(a, jetzt)
    reg["regeln"]["firmen"].append(mp.TOPSTEP)
    alt_all, alt_bal = a["_sb_all"], a["acc_balance_wahl"]

    def _sb_all(table, params):
        s = str(params.get("select", ""))
        if table == "trade_plans" and "konto_typ" in s:
            return []
        rows = alt_all(table, params)
        if table == "trade_plans" and "kette_te:mt5_baseline->kette->tagesende" in s:
            rows += [dict(p, user_id=mp.KONTO["user_id"], master_account_id=mp.KONTO["id"], master_firm="Topstep") for p in plaene(tag)]
        if table == "accounts":
            ids, uids, typen = al.in_liste(params.get("id", "")), al.in_liste(params.get("user_id", "")), params.get("account_type")
            if (ids is None or mp.KONTO["id"] in ids) and (uids is None or mp.KONTO["user_id"] in uids) and (not typen or mp.KONTO["account_type"] in typen):
                rows += [dict(mp.KONTO)]
        return rows
    a["_sb_all"] = _sb_all
    a["_liq_verlauf_cache"].clear()
    a["acc_balance_wahl"] = lambda k, e, d: ((150000.0, "USD", "TV", stand) if str((k or {}).get("id")) == mp.KONTO["id"] else alt_bal(k, e, d))
    erg = a["ap_planen"](tag.strftime("%Y-%m-%d"), trocken=True, seed=4711, ids="alle")
    aus = {z.get("konto_id"): z for z in erg.get("ausgelassen") or []}.get(mp.KONTO["id"])
    gepl = [z for z in erg.get("geplant") or [] if z.get("konto_id") == mp.KONTO["id"] or z.get("master_account_id") == mp.KONTO["id"]]
    return aus, gepl


def review_am(tag, tage_davor, te=True, blown=False):
    ende = (tag - timedelta(days=tage_davor)).replace(hour=12, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    p = {"id": "p-te", "status": "review", "richtung": "buy", "master_pl": 3300.0, "blown": blown, "started_at": ende, "ended_at": ende, "created_at": ende}
    if te:
        p["kette_te"] = {"tag_pl": 4500.0, "blown": blown}
    return [p]


def main():
    k1 = dict(GESUND, nr=1)
    weg, u, r = abhaken([plan("t1", k1, 150000, 148500)])
    check(weg == ["t1"] and u["t1"].get("status") == "completed" and "t1" not in r and u["t1"].get("master_pl") == -1500.0,
          f"1/2 mit folgendem Trade 2 → automatisch erledigt, kein Tagesende, Kette läuft wie heute ({u})")

    k2 = dict(GESUND, nr=2, vor="t1", e1=1200.0, balance_start_tag=150000)
    weg, u, r = abhaken([plan("t2", k2, 151200, 154500)])
    te = (r.get("t2") or {}).get("p_patch", {}).get("tagesende", {})
    check(not weg and "status" not in u["t2"] and u["t2"]["master_pl"] == 3300.0 and u["t2"]["pl_quelle"] == "tv" and "completed_at" not in u["t2"],
          f"2/2 → bleibt in review, P&L steht ({u})")
    check(te.get("t1_pl") == 1200.0 and te.get("t2_pl") == 3300.0 and te.get("tag_pl") == 4500.0 and te.get("balance") == 154500.0 and te.get("trades") == 2 and te.get("blown") is False
          and (r.get("t2") or {}).get("p_key") == "kette" and (r.get("t2") or {}).get("p_status") is None,
          f"2/2: Tagesergebnis +1.200 + 3.300 = +4.500, Balance 154.500 ({te})")
    weg, u, r = abhaken([plan("t2", dict(GESUND, nr=2, vor="t1", balance_start_tag=150000), 151200, 148800)])
    te = r["t2"]["p_patch"]["tagesende"]
    check(te["t1_pl"] == 1200.0 and te["t2_pl"] == -2400.0 and te["tag_pl"] == -1200.0, f"2/2 ohne kette.e1: Trade 1 = Tag − Trade 2 ({te})")

    weg, u, r = abhaken([plan("rep", {"nr": 1, "reparatur": True, "ein_trade": True, "tagesziel": 3030, "verlust_grenze": 1700, "daily_usd": 3000,
                                      "mll": 145500.0, "angefressen": True, "abstand_mll": 1500.0}, 147000, 150030)])
    te = (r.get("rep") or {}).get("p_patch", {}).get("tagesende", {})
    check(not weg and "status" not in u["rep"] and te.get("trades") == 1 and te.get("t2_pl") is None and te.get("tag_pl") == 3030.0,
          f"Reparatur-Tag → review, 1 Trade, Tag +3.030 ({te})")

    weg, u, r = abhaken([plan("bl", dict(k1, verlust_grenze=3200), 150000, 145490)])
    te = (r.get("bl") or {}).get("p_patch", {}).get("tagesende", {})
    check(not weg and "status" not in u["bl"] and u["bl"].get("blown") is True and te.get("blown") is True and te.get("trades") == 1,
          f"1/2 geblowt → review, blown steht sofort am Plan ({u['bl']})")

    weg, u, r = abhaken([plan("zi", k1, 150000, 154500)])
    check(not weg and "status" not in u["zi"] and "zi" in r and not u["zi"].get("blown"), f"1/2 am Tagesziel → kein Trade 2 → review ({u['zi']})")

    p = plan("t2", k2, 151200, 154500)
    p["mt5_baseline"]["kette"] = dict(k2, tagesende={"tag_pl": 4500.0})
    weg, u, r = abhaken([p])
    check(not weg and not u and not r, "Tagesende steht schon → kein Neuschreiben im Minutentakt")

    weg, u, r = abhaken([plan("t1", k1, 150000, 148500)], regeln_fehler=True)
    check(weg == ["t1"] and u["t1"].get("status") == "completed", "Regeln nicht lesbar → 1/2 weiter automatisch, die Kette bleibt nicht stehen")

    # ── 1/2 ohne Trade 2 aus anderem Grund (S2 30.10.2026): vor dem Abhaken geprüft ──
    weg, u, r = abhaken([plan("t1", k1, 150000, 148500)], t2_da=False)
    check(not weg and "status" not in u["t1"] and u["t1"].get("master_pl") == -1500.0 and "t1" not in r,
          f"1/2, Trade 2 noch nicht angelegt, Fenster offen → wartet in review, P&L steht, kein Tagesergebnis ({u})")
    p = plan("t1", k1, 150000, 148500, master_pl=-1500.0)
    weg, u, r = abhaken([p], t2_da=False)
    check(not weg and not u and not r, "wartet schon, P&L steht → kein Neuschreiben im Minutentakt")
    spaet = datetime(2026, 10, 30, 19, 0, tzinfo=timezone.utc)   # 20:00 dt, Fenster bis 19:30 dt vorbei
    weg, u, r = abhaken([plan("t1", k1, 150000, 148500)], t2_da=False, jetzt=spaet)
    check(not weg and "status" not in u["t1"] and (r.get("t1") or {}).get("p_patch", {}).get("tagesende", {}).get("trades") == 1,
          f"kein Start bis t2_bis → review mit Tagesergebnis (1 Trade) ({r})")
    weg, u, r = abhaken([plan("t1", k1, 150000, 148500)], t2_da=False, gesperrt=True)
    check(not weg and "t1" in r, "Firma gesperrt → review mit Tagesergebnis")
    weg, u, r = abhaken([plan("t1", k1, 150000, 148500)], t2_da=False, t2_lesefehler=True)
    check(weg == ["t1"], "Trade 2 nicht lesbar → automatisch wie bisher, die Kette bleibt nicht stehen")

    w = dict(plan("w", k2, 151200, 154500))
    w["mt5_baseline"]["final"] = {"quelle": "puls"}
    weg, u, r = abhaken([w])
    check(not weg and not u and not r, "ohne genaue Lesung: weder Tagesende noch erledigt")

    # ── Planer: offenes Abhaken darf den Folgetag nicht stoppen (echter ap_planen-Lauf) ──
    aus, gepl = planer(lambda t: [])
    check(gepl and not aus, f"Gegenprobe: Konto ohne Pläne wird geplant ({aus})")
    aus, gepl = planer(lambda t: review_am(t, 1))
    check(gepl and not aus and "Topstep-Kette 1/2" in str(gepl[0].get("stufe")), f"Haken von gestern offen → Planer plant den Folgetag ({aus})")
    aus, gepl = planer(lambda t: review_am(t, 0))
    check(not gepl and aus and "letzter Trade" not in aus.get("grund", ""), f"Haken von heute offen → heute kein Trade, Grund „{(aus or {}).get('grund')}“")
    aus, gepl = planer(lambda t: review_am(t, 1, blown=True), stand="2000-01-01")
    check(not gepl and aus and "geblowt" in aus.get("grund", ""), f"geblowt offen → nicht geplant, Grund „{(aus or {}).get('grund')}“")
    aus, gepl = planer(lambda t: review_am(t, 1, te=False))
    check(not gepl and aus and "letzter Trade noch nicht erledigt" in aus.get("grund", ""),
          f"anderes Überprüfen ohne Tagesergebnis sperrt weiter wie bisher ({(aus or {}).get('grund')})")

    # ── Nachplanen (_ap_plan_am_tag, ap_nachplan_kandidaten) ──
    a = al.lade()
    tz = ZoneInfo("Europe/Berlin")
    am = a["_ap_plan_am_tag"]
    z = {"status": "review", "started_at": "2026-10-30T09:00:00+00:00", "kette_te": {"tag_pl": 4500}}
    check(am(z, "2026-10-30", tz) is True and not am(z, "2026-10-31", tz), "_ap_plan_am_tag: Tagesende belegt nur seinen eigenen Tag")
    check(am({"status": "review", "started_at": "2026-10-30T09:00:00+00:00"}, "2026-10-31", tz) is True, "_ap_plan_am_tag: anderes Überprüfen belegt weiter jeden Tag")

    # ── Anzeige: Feld kommt im Radar an ──
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
    check("dt\"\n            _ap_kette_grund(t1, gruende[pid])" in src, "kein regelkonformer Start: Grund steht sichtbar an Trade 1")
    check('z["kette_tag"]' in src, "/admin/live-trades liefert kette_tag")
    check('.get("tagesende")):\n                        blow_auto = False' in src, "Abhaken im Radar: Tagesende entscheidet über geblowt, nicht die Boden-Rechnung ab Trade 2")
    check('"konto_typ", "ended_at") if x in upd' in src, "Tagesende schreibt ended_at, falls leer (Richtungs-Riegel)")
    html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
    check(html.count("wdlKetteTagChip(t)") >= 3, "Radar-Karte zeigt das Tagesergebnis in Überprüfen und im Verlauf")
    check("t.kette_tag && typeof t.kette_tag === 'object') return t.blown === true || t.kette_tag.blown === true" in html
          and "(t.kette_tag && typeof t.kette_tag === 'object') ? t.kette_tag.blown === true :" in html,
          "Abhak-Dialog und Radar-Gruppe: mit Tagesergebnis gilt kette_tag.blown, nicht die Boden-Rechnung ab Trade 2")
    check('.get("tagesende"):\n            continue                                  # Tag ist abgeschlossen' in src, "ap_kette_tick legt nach dem Tagesende keinen Trade 2 mehr an")

    print(f"\n{'selftest_kette_tagesende: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
