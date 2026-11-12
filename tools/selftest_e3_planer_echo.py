#!/usr/bin/env python3
"""Selbsttest E3 (03.11.2026, Finn: „CFD-Planer only Echo, fertig."): der Challenge-Planer legt CFD-Challenges gleich als Echo mit Fusion-Hedge an
(ap_echo_hedge_zeile / ap_echo_hedge_anlegen), eh_tick rechnet nur nach und stellt nie zurück auf Echo V2, der Claim-Riegel hält Echo mit echo_hedge
„ohne". Minis „Tage sammeln" bleiben Echo V2 (E2). Ohne Netz: nutzt lade() und die nachgebaute Datenbank aus selftest_echo_hedge.py.
Aufruf: python3 tools/selftest_e3_planer_echo.py"""
import os as _os_mk, sys as _sys_mk
_sys_mk.path.insert(0, _os_mk.path.dirname(_os_mk.path.abspath(__file__)))
import modell_name_test  # noqa: F401 — MK1b 05.11.2026: MODELL_NAME aus app.py für die exec-Ausschnitte
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_echo_hedge as eh  # noqa: E402

FEHLER = []


def ok(bed, txt):
    print(("  ok   " if bed else "  FEHL ") + txt)
    if not bed:
        FEHLER.append(txt)


FIRMEN = [{"namen": ["ftmo"], "route": "mt5v2"}, {"namen": ["fundednext"], "route": "mt5v2"}, {"namen": ["fundingpips"], "route": "mt5v2"},
          {"namen": ["the5ers"], "route": "mt5v2"}, {"namen": ["tradeifycfd"], "route": "mt5v2"}, {"namen": ["blueguardian"], "route": "mt5v2"},
          {"namen": ["tradeify"], "route": "tvv2"}]
NORM = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())   # noqa: E731
STUBS = {"ap_regel_finden": lambda firmen, f: next((r for r in firmen if NORM(f) in r["namen"]), None),
         "ap_kontowert_konto": lambda a, bal, firmen, kauf=None: {"satz_eur_pro_usd": 0.0446, "wert_eur": 446.0},
         "ap_cfd_ppl": lambda ctx, a: 1.0, "_ap_norm": NORM, "_firm_norm": lambda s: s, "GP_SLAVE_PPL": 0.85,
         "_wt_now_iso": lambda: "2026-11-03T20:00:00+00:00"}


def zeile(firma, typ="phase1", route="mt5v2", **x):
    return dict({"user_id": "U1", "master_account_id": "A-" + firma, "master_name": f"100k {firma}", "master_firm": firma, "master_contracts": 20,
                 "master_risk": 1000, "master_tp": 2000, "route": route, "notes": "Auto-Planer · Etappe", "mt5_baseline": None}, **x), \
        {"id": "A-" + firma, "user_id": "U1", "firm": firma, "account_type": typ}


def planer():
    ns = eh.lade(STUBS)
    par = ns["eh_param"]({"echo_hedge": {"an": True, "netto_faktor": 1}})
    hedge, hedge_acc = {"U1": ("H1", "488579")}, {"H1": {"id": "H1", "name": "Fusion Echo", "firm": "Fusion Markets", "external_id": "488579"}}
    f = lambda z, a, h=hedge: ns["ap_echo_hedge_zeile"](z, a, 100000.0, h, hedge_acc, {"ppl": {}, "ppl_firma": {}}, {}, FIRMEN, par,   # noqa: E731
                                                         "2026-11-03T20:00:00+00:00")
    print("Planer-Zeile → Echo mit Hedge (alle CFD-Firmen)")
    for firma in ("FTMO", "FundedNext", "FundingPips", "The5%ers", "Tradeify CFD", "Blue Guardian"):
        z, a = zeile(firma)
        art, grund = f(z, a)
        eh_ = (z.get("mt5_baseline") or {}).get("echo_hedge") or {}
        ok(art == "echo" and z["route"] == "mt5" and z["slave_account_id"] == "H1" and z["multiplier"] > 0 and z["slave_risk"] > 0
           and eh_.get("status") == "geplant" and eh_.get("login") == "488579" and "Echo: " in z["notes"],   # MK1b: Notiz „Echo: x Lot Fusion …“
           f"{firma}: route mt5, Slave Fusion, ×{z.get('multiplier')}, echo_hedge geplant")
    z, a = zeile("FTMO", typ="phase2")
    ok(f(z, a)[0] == "echo" and z["route"] == "mt5", "Phase 2 ebenso")
    z, a = zeile("FTMO")
    f(z, a)
    ok(z["mt5_baseline"]["hedge_vorschau"]["lots"] == z["mt5_baseline"]["echo_hedge"]["lots"], "Hedge-Vorschau = Lots der Anlage (Planer-Ansicht)")
    print("bleibt, wie es ist")
    z, a = zeile("FundedNext", master_contracts=0.01, mt5_baseline={"tage_mini": {"sofort_zu": True}})
    ok(f(z, a) == (None, None) and z["route"] == "mt5v2" and "slave_account_id" not in z, "Mini „Tage sammeln“ bleibt Echo V2 (E2)")
    z, a = zeile("FTMO", typ="funded_cfd")
    ok(f(z, a) == (None, None) and z["route"] == "mt5v2", "Funded CFD: nicht vom Challenge-Planer")
    z, a = zeile("Tradeify", typ="challenge", route="tvv2")
    ok(f(z, a) == (None, None) and z["route"] == "tvv2", "Futures (Orbit V2) unberührt")
    z, a = zeile("FTMO")
    art, grund = f(z, a, h={})
    ok(art == "v2" and "kein Echo-Hedge-Konto" in grund and "slave_account_id" not in z,
       "ID ohne Fusion-Konto: nicht stellbar mit Grund (Aufrufer legt nicht an)")
    z, a = zeile("FTMO", master_contracts=0.05)
    art, grund = f(z, a)
    # EH1 (Finn 12.11.2026: „Wenn der Fusion-Hedge zu klein ist, einfach immer 0,01“): unter 0,01 Lot → Echo mit 0,01 Lot, Notiz nennt die Aufrundung
    ok(art == "echo" and grund is None and z["mt5_baseline"]["echo_hedge"]["lots"] == 0.01 and z["mt5_baseline"]["echo_hedge"].get("aufgerundet_von") is not None
       and "aufgerundet" in (z.get("notes") or ""), f"Hedge unter 0,01 Lot: auf 0,01 aufgerundet, Echo mit Hedge (EH1) ({art}, {grund})")

    print("ap_echo_hedge_anlegen (Schalter, Fehler je Zeile)")
    ns2 = eh.lade(dict(STUBS, _sb_all=lambda t, q: [], gp_hedge_settings_eigen=lambda rows: rows, ap_ppl_karte=lambda rows, norm=None: ({}, {}), ap_ppl_ctx_unternehmen=lambda rows, norm=None: {"ppl": {}, "ppl_firma": {}},
                       _ap_kauf_echt=lambda ids: {}, GP_HEDGE_KEY="echo_hedge_account"))
    z, a = zeile("FTMO")
    r = ns2["ap_echo_hedge_anlegen"]([z], {"A-FTMO": (a, 100000.0)}, {"echo_hedge": {"an": False}, "firmen": FIRMEN})
    ok(r["echo"] == 0 and len(r["weg"]) == 1 and "Schalter aus" in r["weg"][0][1], "Schalter aus: nicht anlegen (kein Echo-V2-Ersatz), Grund")
    r = ns2["ap_echo_hedge_anlegen"]([z], {"A-FTMO": (a, 100000.0)}, {"echo_hedge": {"an": True}, "firmen": FIRMEN})
    ok(len(r["weg"]) == 1 and "kein Echo-Hedge-Konto" in r["weg"][0][1], "ohne Hedge-Einstellung: nicht anlegen, Grund")
    zm, am = zeile("FundedNext", master_contracts=0.01, mt5_baseline={"tage_mini": {"sofort_zu": True}})
    r = ns2["ap_echo_hedge_anlegen"]([zm], {"A-FundedNext": (am, 100000.0)}, {"echo_hedge": {"an": False}, "firmen": FIRMEN})
    ok(r == {"echo": 0, "weg": []} and zm["route"] == "mt5v2", "Mini auch bei Schalter aus: angelegt wie immer (Echo V2)")
    src = open(eh.APP, encoding="utf-8").read()
    i_e3, i_fp = src.index("_e3 = ap_echo_hedge_anlegen(zeilen, _konten_e3,"), src.index("    fp = hashlib.sha1(json.dumps([[g[\"konto_id\"]")
    ok(i_e3 < i_fp < src.index('r = _sb_anfrage("POST", f"{SUPABASE_URL}/rest/v1/trade_plans", json=zeilen,'),
       "ap_planen: vor Fingerabdruck und Anlegen (Probelauf = Anlegen, HT und Gruppen)")
    blk = src[i_e3:i_fp]
    ok('z.setdefault(f_, None)' in blk and '"slave_account_id", "slave_name", "slave_firm", "multiplier", "slave_risk"' in blk,
       "Batch-Insert: alle Zeilen mit denselben Schlüsseln (PostgREST PGRST102)")
    i_t = src.index("def _eh_tick_lauf(")
    ok('"start_um,notes,mt5_baseline,updated_at,route"' in src[i_t:i_t + 1500], "eh_tick liest route mit (Guard je Weg, sonst 0 Zeilen bei Echo)")
    ok("zeilen = [z for z in zeilen if id(z) not in _weg_ids]" in blk and "geplant = [g for g in geplant" in blk and "ausgelassen.append(" in blk
       and "if not trocken:" in blk and "ap_echo_ohne_melden(" in blk, "nicht stellbar: nicht angelegt, aus geplant raus, ausgelassen mit Grund, ⚪ nur echt")
    ok("Echo V2" not in blk.split("except Exception as e:")[1].split("if _e3")[0], "Rechenfehler: auch dann kein Echo-V2-Ersatz")


def nachrechnen():
    """eh_tick mit einem Echo-Plan aus dem Planer (route mt5, echo_hedge geplant) im Fenster."""
    jetzt = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)
    iso = lambda m: (jetzt + timedelta(minutes=m)).isoformat()   # noqa: E731
    base = {"echo_hedge": {"status": "geplant", "quelle": "planer", "lots": 1.0, "login": "488579"}}
    plan = lambda pid, m, **x: dict({"id": pid, "user_id": "U1", "master_account_id": "A1", "master_name": pid, "master_firm": "FTMO",   # noqa: E731
                                     "master_contracts": 20, "master_risk": 1000, "richtung": "buy", "start_um": iso(m), "notes": "",
                                     "mt5_baseline": dict(base), "status": "planned", "route": "mt5", "slave_account_id": "H1", "multiplier": 0.05,
                                     "auto_plan": True, "auto_bestaetigt_at": "b", "updated_at": "t0"}, **x)
    plaene = [plan("E1", 10), plan("E2", 12), plan("E3", 120)]
    regeln = {"echo_hedge": {"an": True}, "firmen": [{"namen": ["ftmo"], "route": "mt5v2"}]}
    db = eh.DB(plaene, regeln)
    les = {"488579": {"frei": 15900.0, "je_lot": 265.0, "offen": {"buy": 1.0, "sell": 1.0}, "w": "EUR", "at": jetzt.timestamp() - 30}}
    ns = eh.lade(dict(STUBS, sb_select=db.sb_select, _sb_all=db._sb_all, sb_update=db.sb_update,
                      alarm_senden=lambda *a, **k: db.alarme.append((a, k)),
                      _ap_namen=lambda: ({"U1": "Mike"}, set()), gp_verwalter_karte=lambda: {}, ap_planer_gruppen_ids=lambda: set(),
                      AP_KONTO_FELDER="id", GP_HEDGE_KEY="echo_hedge_account", ap_ppl_karte=lambda rows, norm=None: ({}, {}), ap_ppl_ctx_unternehmen=lambda rows, norm=None: {"ppl": {}, "ppl_firma": {}},
                      _ap_balance_karten=lambda: ({}, {}), _ap_kauf_echt=lambda ids: {}, gp_fusion_lesungen=lambda uids, j: les,
                      acc_balance_wahl=lambda a, e, d: (100000.0, "USD", "Echo", "")))
    print("eh_tick rechnet Echo aus dem Planer nach")
    ns["eh_tick"](jetzt=jetzt, force=True)
    e1 = plaene[0]
    ok(e1["route"] == "mt5" and e1["mt5_baseline"]["echo_hedge"]["status"] == "mit" and e1["slave_account_id"] == "H1" and e1["multiplier"] > 0,
       f"E1 im Fenster: nachgerechnet → status mit, ×{e1['multiplier']}")
    ok(plaene[2]["mt5_baseline"]["echo_hedge"]["status"] == "geplant", "E3 (Start in 2 h) noch nicht angefasst")
    les["488579"]["at"] = jetzt.timestamp() - 900
    plaene.append(plan("E4", 14))
    ns["eh_tick"](jetzt=jetzt, force=True)
    e4 = plaene[-1]
    ok(e4["route"] == "mt5" and e4["mt5_baseline"]["echo_hedge"]["status"] == "ohne" and e4["mt5_baseline"]["echo_hedge"]["code"] == "lesung",
       "Fusion-Lesung alt: bleibt Echo (nie Echo V2), echo_hedge ohne/lesung → Riegel hält")
    les["488579"]["at"] = jetzt.timestamp() - 30
    ns["eh_tick"](jetzt=jetzt, force=True)
    ok(e4["mt5_baseline"]["echo_hedge"]["status"] == "mit", "Lesung wieder frisch: derselbe Plan wird nachgerechnet (ohne → mit)")
    regeln["echo_hedge"]["an"] = False
    erg = ns["eh_tick"](jetzt=jetzt, force=True)
    ok(all(p["route"] == "mt5" for p in plaene) and erg.get("zurueck") == 0, "Schalter aus: kein Plan zurück auf Echo V2")


def riegel():
    print("Claim-Riegel (sql/2026-11-03_cfd_v2_auf_echo.sql)")
    sql = open(os.path.join(os.path.dirname(HIER), "sql", "2026-11-03_cfd_v2_auf_echo.sql"), encoding="utf-8").read()
    body = sql.split("$$")[1]
    ok("and coalesce(new.mt5_baseline->'echo_hedge'->>'status', '') not in ('ohne', 'geplant') then" in body,
       "Echo mit Slave, aber echo_hedge ohne ODER geplant (noch nicht frisch geprüft, fail-closed) → gehalten; mit / ohne Marke → läuft")
    ok(body.index("Tage sammeln%") < body.index("ss := new.mt5_baseline->'start_sperre'"), "Mini-Ausnahme (E2) unverändert vor der Halte-Logik")
    e2 = open(os.path.join(os.path.dirname(HIER), "sql", "2026-11-03_echo_riegel_mini_frei.sql"), encoding="utf-8").read().split("$$")[1]
    norm = lambda t: re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", t)).strip()   # noqa: E731
    rest = norm(body).replace("and coalesce(new.mt5_baseline->'echo_hedge'->>'status', '') not in ('ohne', 'geplant') ", "").replace("nicht stellbar:", "nicht umgestellt:")
    rest = rest.replace(" when eh->>'status' = 'geplant' then 'Echo-Hedge vor dem Start noch nicht frisch geprüft (Railway eh_tick) — startet erst danach'", "")
    ok(sorted(re.split(r" when | else ", rest)) == sorted(re.split(r" when | else ", norm(e2))),
       "sonst = E2-Funktion (eine Bedingung mehr, Text „geplant“ neu, when-Zeile „ohne“ vor „mt5“, „nicht stellbar“ statt „nicht umgestellt“)")
    t2 = sql.split("$$")[2]
    ok("p.route = 'mt5v2'" in t2 and "? 'tage_mini'" in t2 and "h.user_id = p.user_id" in t2 and "and p.start_um_gestartet_at is null" in t2
       and "verbrauch'" not in t2.split("where")[1] and "(p.start_um is null or p.start_um >= now())" in t2 and "'start_fehler'" not in t2,
       "Teil 2: nur Echo V2, nie Mini, nur eigenes Fusion-Konto, nie geclaimt (verbraucht bleibt verbraucht), nur künftige Starts, Start-Fehler bleiben")


def main():
    planer()
    nachrechnen()
    riegel()
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
