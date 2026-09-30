#!/usr/bin/env python3
"""Selbsttest fuer PATCH /admin/wd-plaene {aktion:'erledigt'} (app.py, 25.09.2026) — rein rechnend, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_wd_erledigt.py
Laedt _wd_ende_upd, _wd_erledigt_upd, _wd_hedge_konto, _wd_hedge_buchung, _wd_hedge_schluessel, _wd_zahl per
Quelltext aus app.py. Prueft: erledigt aus open und review (final nur ergaenzt, wenn keins da), Korrektur auf
completed (completed_at bleibt), 409 fuer planned/falsche Route, 404; Zielkonto nach der Regel der Koordination
(Login-Treffer live vor Demo, Rueckfall Fusion-live, sonst ohne Konto); Buchungszeile EUR, notes-Schluessel."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    exec("\n".join(['WD_HEDGE_LOGIN = "488579"', 'WD_ERLEDIGT_ROUTEN = ("tvv2", "mt5v2", "tsv2")'] + [block(n) for n in (
        "_wd_ende_upd", "_wd_hedge_schluessel", "_wd_hedge_konto", "_wd_zahl", "_wd_erledigt_upd", "_wd_hedge_buchung",
        "_wd_good_day", "_wd_good_day_konto_upd")] + ['WD_GOOD_DAY_MIN = {"tradeify": 250.0}']), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    T, D = "2026-09-25T20:30:00Z", "2026-09-25"
    hedge = {"status": "geschlossen", "pl": -4.2, "pc": "pc-usq1i6"}
    offen = {"id": "55eb8344-8f3e-48d5-a6db-69b8d22cb814", "route": "tvv2", "status": "open", "mt5_baseline": {"hedge": hedge}}
    u, e = a["_wd_erledigt_upd"](offen, 250.0, -4.2, T, D)
    check(e is None and u["status"] == "completed" and u["master_pl"] == 250.0 and u["slave_pl"] == -4.2
          and u["completed_at"] == T and u["ended_at"] == T and u["mt5_baseline"]["final"]["quelle"] == "hand"
          and u["mt5_baseline"]["final"]["grund"] == "erledigt" and u["mt5_baseline"]["hedge"] == hedge,
          "open → completed: P&L, completed_at, ended_at, final ergänzt, hedge unverändert")
    review = dict(offen, status="review", ended_at="2026-09-25T20:15:00Z",
                  mt5_baseline={"hedge": hedge, "final": {"today_pnl": None, "quelle": "hand", "at": "x"}})
    u, e = a["_wd_erledigt_upd"](review, 250.0, None, T, D)
    check(e is None and "ended_at" not in u and "mt5_baseline" not in u and u["slave_pl"] is None,
          "review → completed: ended_at und vorhandenes final bleiben, slave_pl null erlaubt")
    fertig = dict(review, status="completed", completed_at="2026-09-25T20:20:00Z")
    u, e = a["_wd_erledigt_upd"](fertig, 260.0, -5.0, T, D)
    check(e is None and "completed_at" not in u and u["master_pl"] == 260.0, "Korrektur auf completed: completed_at bleibt, Werte neu")
    check(a["_wd_erledigt_upd"](dict(offen, status="planned"), 1, 1, T, D)[1] == (409, "nicht offen")
          and a["_wd_erledigt_upd"](dict(offen, route="dup"), 1, 1, T, D)[1] == (409, "nicht offen")
          and a["_wd_erledigt_upd"](None, 1, 1, T, D)[1][0] == 404, "planned / falsche Route → 409, kein Plan → 404")
    # 30.09.2026: Echo V2 und Topstep V2 abhakbar (Radar, auch fremde IDs) — ohne Fusion-P&L, ohne Baseline-Umbau
    for rt in ("mt5v2", "tsv2"):
        u, e = a["_wd_erledigt_upd"](dict(offen, route=rt, status="review", mt5_baseline={"tv": {}}), -1692.4, None, T, D)
        check(e is None and u["status"] == "completed" and u["master_pl"] == -1692.4 and u["slave_pl"] is None and "mt5_baseline" not in u,
              f"{rt}: erledigt ohne Fusion, Baseline unberührt (Topstep-Handplan)")
        check(a["_wd_erledigt_upd"](dict(offen, route=rt), 100, -5, T, D)[1] == (400, "Fusion-P&L gibt es nur bei Orbit V2 / Winning Days"),
              f"{rt}: Fusion-P&L → 400 (keine falsche wd_hedge-Buchung)")
    # K5 (30.09.2026): Topstep V2 mit Puls (tv.puls 'tsx') wie Orbit V2 — final + live.offen false, falls noch kein final
    u, e = a["_wd_erledigt_upd"](dict(offen, route="tsv2", status="open", mt5_baseline={"tv": {"puls": "tsx"}}), -1692.4, None, T, D)
    check(e is None and u["mt5_baseline"]["final"]["grund"] == "erledigt" and u["mt5_baseline"]["tv"] == {"puls": "tsx"}
          and u["mt5_baseline"]["live"]["offen"] is False, "tsv2 mit Puls: erledigt legt final an wie Orbit V2")
    u, e = a["_wd_erledigt_upd"](dict(offen, route="tsv2", status="review",
                                      mt5_baseline={"tv": {"puls": "tsx"}, "final": {"quelle": "close", "today_pnl": -1692.4}}), -1692.4, None, T, D)
    check(e is None and "mt5_baseline" not in u, "tsv2 mit Puls und final (quelle close): Baseline unberührt")
    check(a["_wd_zahl"]("−4,20".replace("−", "-")) == -4.2 and a["_wd_zahl"](True) is None and a["_wd_zahl"]("x") is None
          and a["_wd_zahl"](250) == 250.0, "Zahl: Komma, bool/Text keine Zahl")

    konten = [{"id": "demo", "external_id": "488579", "account_type": "phase1", "firm": "Fusion Markets", "created_at": "2026-08-01"},
              {"id": "echo", "external_id": "488579", "account_type": "live", "firm": "Fusion Markets", "created_at": "2026-08-05", "name": "Echo +", "user_id": "u1"},
              {"id": "alt", "external_id": "430095", "account_type": "live", "firm": "Fusion Markets", "created_at": "2026-07-01", "name": "Fusion Live"}]
    k, q = a["_wd_hedge_konto"](konten, "488579")
    check(k["id"] == "echo" and q == "login", "Zielkonto: Login-Treffer, live vor Demo")
    k, q = a["_wd_hedge_konto"](konten, "430095")
    check(k["id"] == "alt" and q == "login", "Zielkonto: anderer Hedge-Login (Emin 430095)")
    k, q = a["_wd_hedge_konto"]([konten[2]], "488579")
    check(k["id"] == "alt" and q == "fusion_live", "Rückfall: erstes live-Konto mit Firma Fusion")
    k, q = a["_wd_hedge_konto"]([{"id": "x", "account_type": "funded", "firm": "Apex"}], "488579")
    check(k is None and q == "ohne", "kein Fusion-Konto → ohne Konto")
    # Frontend-Gleichstand (zweite Gegenprüfung 25.09.2026): Archiv-Filter + MetaApi-Login
    k, q = a["_wd_hedge_konto"](konten, "488579", {"echo"})
    check(k["id"] == "demo" and q == "login", "archiviertes live-Konto zählt nicht → nächster Login-Treffer")
    k, q = a["_wd_hedge_konto"](konten, "488579", {"echo", "demo"})
    check(k["id"] == "alt" and q == "fusion_live", "alle Login-Treffer archiviert → Rückfall Fusion live")
    ma = [{"id": "ma", "external_id": "", "meta_api_account_id": "abc", "meta_api_login": "488579", "account_type": "live", "firm": "Fusion Markets", "created_at": "2026-09-01"},
          {"id": "ohne_ma", "external_id": "", "meta_api_account_id": None, "meta_api_login": "488579", "account_type": "live", "firm": "X", "created_at": "2026-06-01"}]
    k, q = a["_wd_hedge_konto"](ma, "488579")
    check(k["id"] == "ma" and q == "login", "MetaApi-Login als Treffer (nur mit meta_api_account_id)")

    z = a["_wd_hedge_buchung"](offen["id"], "u1", konten[1], "Moritz", -4.2, D)
    check(z["kind"] == "wd_hedge" and z["currency"] == "EUR" and z["amount"] == -4.2 and z["account_id"] == "echo"
          and z["user_id"] == "u1" and z["notes"] == "Trade #55eb8344 WD-Hedge · Moritz · Echo +" and z["auto_generated"] is True
          and z["notes"].startswith(a["_wd_hedge_schluessel"](offen["id"])), "Buchung: EUR, P&L-Vorzeichen, notes mit Schlüssel")
    z = a["_wd_hedge_buchung"](offen["id"], "u1", None, "Moritz", -4.2, D)
    check(z["account_id"] is None and z["account_name"] == "Fusion (WD-Hedge)" and z["account_firm"] == "Fusion Markets",
          "Buchung ohne Konto: account_id null, 'Fusion (WD-Hedge)'")
    # Good Day (01.10.2026): Tradeify-WD über 250 $ zählt als Winning Day, einmal je Berlin-Tag
    wd = {"account_type": "winning_days", "firm": "Tradeify"}
    check(a["_wd_good_day"](wd, 250.01) and not a["_wd_good_day"](wd, 250) and not a["_wd_good_day"](wd, -400),
          "Good Day: Tradeify-WD erst über 250 $")
    check(not a["_wd_good_day"](dict(wd, firm="Apex Trader"), 900) and not a["_wd_good_day"](dict(wd, account_type="funded"), 900)
          and not a["_wd_good_day"](None, 900) and not a["_wd_good_day"](wd, None), "Good Day: andere Firma/Typ/ohne P&L nie")
    u = a["_wd_good_day_konto_upd"]({"goal_done_offset": 2, "goal_target": None, "goal_manual_last": "2026-09-30"}, "2026-10-01")
    check(u == {"goal_done_offset": 3, "goal_manual_last": "2026-10-01", "goal_kind": "winning_days", "goal_manual": True, "goal_target": 5},
          "Good Day: Konto +1, Ziel 5 wenn leer")
    check(a["_wd_good_day_konto_upd"]({"goal_done_offset": 3, "goal_manual_last": "2026-10-01"}, "2026-10-01") is None,
          "Good Day: am selben Tag nie doppelt")
    print("\n" + ("alle Tests bestanden" if ok else "FEHLER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
