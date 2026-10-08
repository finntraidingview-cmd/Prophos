#!/usr/bin/env python3
"""Selbsttest STARTWERT FÜR FRISCHE KONTEN (app.py ap_startwert_frisch / _ap_konten_mit_trade / ap_planen, 09.10.2026, Slave-Terminal 4 —
Finn: „Wenn ich Accounts frisch hinzufüge, soll die Balance direkt drin sein"; frische Tradeify-150k standen unter „Braucht dich" mit
„keine Balance bekannt", die Hand-Lesung ergab genau 150.000).
Geprüft: (1) rein: Größe aus Name/Kürzel/starting_balance/account_size, nie bei Trade, unklarem Verlauf, Topstep Express, ohne Größe;
(2) Verlauf: Master ODER Slave, gestartet/gesendet/beendet/Status zählt, Lesefehler → None; (3) ap_planen gegen die nachgebaute DB
(selftest_auto_delta): frisches 150k-Tradeify → Plan mit 150.000 und Quelle „Startwert", CFD FN 100k Phase 1 → 100.000, Konto mit
früherem Trade ohne Lesung → weiter „keine Balance bekannt", echte Lesung schlägt den Startwert, Verlauf nicht lesbar → kein Startwert.
Platzhalter-IDs, keine echten Konten. Aufruf: python3 tools/selftest_startwert_frisch.py"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


FRISCH = {"id": "k-90", "user_id": sd.U1, "name": "Tradeify 150k", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000090"}
CFD = {"id": "k-91", "user_id": sd.U1, "name": "FN 100k Phase 1", "firm": "FundedNext", "account_type": "phase1", "external_id": "000091"}
ALT = {"id": "k-92", "user_id": sd.U1, "name": "Tradeify 150k", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000092"}
GELESEN = {"id": "k-93", "user_id": sd.U1, "name": "Tradeify 150k", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000093"}
OHNE = {"id": "k-94", "user_id": sd.U1, "name": "Tradeify Konto", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-X"}


def main():
    a = sd.lade()
    S = a["ap_startwert_frisch"]

    # 1 rein
    check(S(FRISCH, False) == 150000.0, "frisch, „150k\" im Namen → 150.000")
    check(S(CFD, False) == 100000.0, "CFD FN 100k Phase 1 frisch → 100.000")
    check(S({"name": "x", "starting_balance": 50000}, False) == 50000.0, "ohne Größe im Namen → starting_balance")
    check(S({"name": "TDFYSL150-1", "external_id": ""}, False) == 150000.0, "Tradeify-Kürzel TDFYSL150 → 150.000 (wie liq_konto_groesse)")
    check(S({"name": "x", "account_size": 25000}, False) == 25000.0, "zuletzt account_size")
    check(S(FRISCH, True) is None and S(FRISCH, None) is None, "mit Trade oder unklarem Verlauf → kein Startwert")
    check(S(OHNE, False) is None, "ohne erkennbare Größe → kein Startwert (bleibt „Balance fehlt\")")
    check(all(S(dict(FRISCH, **{f: "2026-10-01T00:00:00+00:00"}), False) is None for f in a["AP_LESE_FELDER"]),
          "je eine frühere Lesung (tv_balance_at / topstep_last_check / meta_api_last_check, z. B. 0 $ geblowt) → nicht frisch")
    check(S(FRISCH, False, gelesen=True) is None, "Echo/Duplikum kennt den Login → nicht frisch")
    xfa = {"name": "Topstep 50k XFA", "firm": "Topstep", "account_type": "funded", "external_id": "EXPRESS-V2-1"}
    check(a["ist_topstep_express"](xfa) and S(xfa, False) is None, "Topstep Express (0-basiert) nie")
    check(S(dict(xfa, name="Topstep 50k", account_type="challenge", external_id="50KTC-1"), False) == 50000.0, "Topstep-Combine frisch → Größe")

    # 2 Verlauf
    zeilen = {"master_account_id": [{"master_account_id": "k-92", "status": "completed", "ended_at": "2026-08-01T10:00:00+00:00"},
                                    {"master_account_id": "k-90", "status": "planned"},                       # nur geplant ≠ gehandelt
                                    {"master_account_id": "k-95", "status": "deleted", "orbit_gesendet_at": "2026-08-02T10:00:00+00:00"}],
              "slave_account_id": [{"slave_account_id": "k-96", "status": "review"}],
              "fremd_positionen": [{"konto_id": "k-97"}]}
    a["_sb_all"] = lambda t, p: [dict(z) for z in zeilen["fremd_positionen" if t == "fremd_positionen" else
                                                          "master_account_id" if "master_account_id" in p else "slave_account_id"]]
    g = a["_ap_konten_mit_trade"](["k-90", "k-92", "k-95", "k-96", "k-97"])
    check(g == {"k-92", "k-95", "k-96", "k-97"}, f"gehandelt = beendet / Order gesendet / als Slave / Hand-Trade (fremd_positionen), nur geplant nicht ({sorted(g)})")
    a["_sb_all"] = lambda t, p: (_ for _ in ()).throw(RuntimeError("fremd fehlt")) if t == "fremd_positionen" else []
    check(a["_ap_konten_mit_trade"](["k-90"]) is None, "fremd_positionen nicht lesbar → None")

    def kaputt(t, p):
        raise RuntimeError("503")
    a["_sb_all"] = kaputt
    check(a["_ap_konten_mit_trade"](["k-90"]) is None, "Verlauf nicht lesbar → None")
    check(a["_ap_konten_mit_trade"]([]) == set(), "keine Konten → keine Abfrage, leer")

    # 3 ap_planen gegen die nachgebaute DB
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    tag_s = tag.strftime("%Y-%m-%d")

    def lauf(verlauf_kaputt=False):
        b = sd.lade()
        sd.db_stubs(b, jetzt)
        basis_all, basis_bal = b["_sb_all"], b["acc_balance_wahl"]
        abfragen = []

        def _sb_all(table, params):
            if table == "accounts":
                return basis_all(table, params) + [dict(k) for k in (FRISCH, CFD, ALT, GELESEN, OHNE)]
            if table == "trade_plans" and str(params.get("select") or "").endswith(",status,started_at,ended_at,orbit_gesendet_at"):   # nur _ap_konten_mit_trade
                abfragen.append(params)
                if verlauf_kaputt:
                    raise RuntimeError("503")
                if "master_account_id" in params and "k-92" in params["master_account_id"]:
                    return [{"master_account_id": "k-92", "status": "completed", "ended_at": "2026-08-01T10:00:00+00:00"}]
                return []
            return basis_all(table, params)

        def bal(acc, e, d):
            aid = str((acc or {}).get("id"))
            if aid in ("k-90", "k-91", "k-92", "k-94"):
                return None, None, None, ""
            if aid == "k-93":
                return 151234.0, "USD", "TV", "2999-01-01"
            return basis_bal(acc, e, d)
        b.update(_sb_all=_sb_all, acc_balance_wahl=bal)
        erg = b["ap_planen"](tag_s, trocken=True, seed=4711)
        gepl = {x["konto_id"]: x for x in erg.get("geplant") or []}
        aus = {x.get("konto_id"): x.get("grund") for x in erg.get("ausgelassen") or []}
        return erg, gepl, aus, abfragen

    erg, gepl, aus, abfragen = lauf()
    check(erg.get("ok"), "Lauf ok")
    f = gepl.get("k-90") or {}
    check(f.get("balance") == 150000 and f.get("bal_quelle") == a["AP_STARTWERT_QUELLE"],
          f"frisches 150k-Tradeify → Plan mit Balance 150.000, Quelle Startwert ({f.get('balance')}, {f.get('bal_quelle')}; {aus.get('k-90')})")
    c = gepl.get("k-91") or {}
    check(c.get("balance") == 100000 and c.get("bal_quelle") == a["AP_STARTWERT_QUELLE"],
          f"CFD FN 100k Phase 1 frisch → 100.000 ({c.get('balance')}; {aus.get('k-91')})")
    check("k-92" not in gepl and aus.get("k-92") == "keine Balance bekannt",
          f"Konto mit früherem Trade (vor > 30 Tagen) ohne Lesung → weiter „keine Balance bekannt\" ({aus.get('k-92')})")
    r = gepl.get("k-93") or {}
    check(r.get("balance") == 151234 and r.get("bal_quelle") == "TV", f"echte Lesung schlägt den Startwert ({r.get('balance')}, {r.get('bal_quelle')})")
    check(aus.get("k-94") == "keine Balance bekannt", f"ohne erkennbare Größe → „keine Balance bekannt\" ({aus.get('k-94')})")
    ids = " ".join(str(p.get("master_account_id") or p.get("slave_account_id")) for p in abfragen)
    check(all(k in ids for k in ("k-90", "k-91", "k-92", "k-94")) and "k-93" not in ids and "k-2," not in ids and "k-1," not in ids,
          f"Verlauf nur für Konten ohne Lesung abgefragt, Master + Slave ({len(abfragen)} Abfragen)")
    check(all(x.get("bal_quelle") != a["AP_STARTWERT_QUELLE"] for k, x in gepl.items() if k not in ("k-90", "k-91")),
          "alle anderen Konten unverändert mit ihrer gelesenen Balance")

    erg, gepl, aus, _ = lauf(verlauf_kaputt=True)
    check(aus.get("k-90") == "keine Balance bekannt" and aus.get("k-91") == "keine Balance bekannt" and erg.get("ok"),
          f"Verlauf nicht lesbar → kein Startwert, Lauf läuft weiter ({aus.get('k-90')})")

    # 4 Quelltext: Startwert nur ohne letzten Trade, nicht als „gelesen" geschrieben
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
    seg = src[src.index("\ndef ap_planen("):src.index("\n\n\n", src.index("\ndef ap_planen("))]
    check("        if not bal and not letzt:\n" in seg and "sw = ap_startwert_frisch(a, None if _gehandelt is None else aid in _gehandelt, gelesen=" in seg,
          "Planer: Startwert nur ohne Lesung und ohne Trade im 30-Tage-Fenster")
    check("tv_balance_at" not in src[src.index("\ndef ap_startwert_frisch("):src.index("\nAP_KONTO_FELDER = (")].split('"""')[2],
          "Startwert schreibt nichts (kein tv_balance_at)")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
