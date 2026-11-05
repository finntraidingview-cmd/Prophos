#!/usr/bin/env python3
"""Selbsttest SA3 (05.11.2026, NK1 #8 Rest von MO1b): (a) Delta-Anzeige wiegt ein Unternehmen mit seiner Waage-Liste/seinen Modellen,
(b) Lucid-Reset auf derselben Konto-Zeile: EOD-Hochs zählen erst ab dem Reset — nur neue External ID oder Buchung „Reset von …" (konto-reset-Weg). Ohne Netz.
Aufruf: python3 tools/selftest_sa3.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


EXT = "LFE20251104000002"
Z = [  # Verlauf eines Lucid-Kontos: zwei Trades vor dem Reset (alte Nummer im Namen bzw. vor dem Kauf), einer danach
    {"id": "a", "master_account_id": "k1", "konto_typ": "challenge", "started_at": "2026-11-01T14:00:00+00:00", "ended_at": "2026-11-01T15:00:00+00:00",
     "bal_end": 52800, "master_name": "50k LFE20251001000001 → Challenge"},
    {"id": "b", "master_account_id": "k1", "konto_typ": "challenge", "started_at": "2026-11-02T14:00:00+00:00", "ended_at": "2026-11-02T15:00:00+00:00",
     "bal_end": 52500, "master_name": f"50k {EXT} → Challenge"},
    {"id": "c", "master_account_id": "k1", "konto_typ": "challenge", "started_at": "2026-11-04T14:00:00+00:00", "ended_at": "2026-11-04T15:00:00+00:00",
     "bal_end": 50600, "master_name": f"50k {EXT} → Challenge"},
]
f = app.liq_verlauf_nach_reset

# ── (b) rein rechnend ──
ok([z["id"] for z in f(Z)] == ["a", "b", "c"], "(b) ohne Reset-Info: alles bleibt (wie bisher)")
ok([z["id"] for z in f(Z, None, EXT)] == ["b", "c"], "(b) neue External ID: Plan mit ANDERER Nummer derselben Form (LFE…) fällt weg")
ok([z["id"] for z in f(Z, "2026-11-03T08:00:00+00:00", EXT)] == ["c"], "(b) Reset-Buchung 03.11.: nur Trades danach")
ok([z["id"] for z in f(Z, "2026-11-03T08:00:00+00:00", None)] == ["c"], "(b) nur Reset-Buchung (ohne External ID) genügt")
ohne_nr = [dict(Z[0], master_name="Lucid 50k")]
ok([z["id"] for z in f(ohne_nr, None, EXT)] == ["a"], "(b) Name ohne Nummer: bleibt (im Zweifel zählt das alte Hoch)")
beide = [dict(Z[0], master_name=f"50k LFE20251001000001 → {EXT}")]
ok([z["id"] for z in f(beide, None, EXT)] == ["a"], "(b) Name nennt auch die aktuelle Nummer: bleibt")
ts = [{"id": "t", "started_at": "2026-11-01T14:00:00+00:00", "master_name": "150KTC-V2-111-222333"}]
ok([z["id"] for z in f(ts, None, "150KTC-V2-444-555666")] == ["t"], "(b) Topstep-Form ohne Buchstaben-Präfix: nie per Name gefiltert")
ok([z["id"] for z in f([dict(Z[2], started_at=None)], "2026-11-03T08:00:00+00:00", EXT)] == ["c"], "(b) ohne Start zählt das Ende")

# EOD-Hoch: vorher 52.800 (vor dem Reset), nachher nur 50.600
acc = {"id": "k1", "account_type": "challenge"}
p = {"id": "neu", "master_account_id": "k1", "started_at": "2026-11-05T14:00:00+00:00"}
vor = app.liq_peak(p, acc, 50600, Z, eod=True)
nach = app.liq_peak(p, acc, 50600, f(Z, "2026-11-03T08:00:00+00:00", EXT), eod=True)
ok(vor == 52800 and nach == 50600, f"(b) EOD-Hoch: alt {vor} → ab dem Reset {nach}")

# ── (b) Lader: Reset-Infos aus accounts + transactions, Lesefehler → ohne Filter ──
alt_all, alt_sel = app._sb_all, app.sb_select
FEHL = {"tx": False}


def sb_all(t, params):
    if t == "trade_plans":
        return [dict(z) for z in Z]
    if t == "transactions":
        if FEHL["tx"]:
            raise RuntimeError("weg")
        return [{"account_id": "k1", "occurred_at": "2026-10-20T10:00:00+00:00", "kind": "account_purchase", "notes": ""},
                {"account_id": "k1", "occurred_at": "2026-11-03T08:00:00+00:00", "kind": "account_purchase", "notes": "Reset von LFE20251001000001 (auto)"},
                {"account_id": "k1", "occurred_at": "2026-11-04T20:00:00+00:00", "kind": "account_purchase", "notes": "Add-on 1 % Rule"}]   # nach dem Reset: kein Reset
    return []


app._sb_all = sb_all
app.sb_select = lambda t, params: [{"id": "k1", "external_id": EXT}] if t == "accounts" else []
app._liq_verlauf_cache.clear()
ok([z["id"] for z in app._liq_verlauf_laden(["k1"])] == ["c"], "(b) Lader: Reset-Buchung (Notiz) + External ID → nur Zeilen nach dem Reset; späteres Add-on verschiebt nichts")
# Master/S4 05.11.2026: ein Add-on-/Gebühren-Kauf auf derselben Zeile ist KEIN Reset → die alten Hochs bleiben (vorsichtig)
NUR_ADDON = [{"account_id": "k1", "occurred_at": "2026-11-03T08:00:00+00:00", "kind": "account_purchase", "notes": "Add-on On Demand"},
             {"account_id": "k1", "occurred_at": "2026-11-03T09:00:00+00:00", "kind": "account_purchase", "notes": None}]
Z_GLEICH = [dict(z, master_name=f"50k {EXT} → Challenge") for z in Z]   # alle Trades unter derselben Nummer (kein ID-Wechsel)
app._sb_all = lambda tb, params: NUR_ADDON if tb == "transactions" else ([dict(z) for z in Z_GLEICH] if tb == "trade_plans" else [])
app._liq_verlauf_cache.clear()
ok([z["id"] for z in app._liq_verlauf_laden(["k1"])] == ["a", "b", "c"], "(b) nur Add-on-/Gebühren-Käufe, gleiche External ID → kein Reset, alte Hochs bleiben")
pk = app.liq_peak({"id": "neu", "master_account_id": "k1", "started_at": "2026-11-05T14:00:00+00:00"}, {"id": "k1", "account_type": "challenge"},
                  50600, app._liq_verlauf_laden(["k1"]), eod=True)
ok(pk == 52800, f"(b) Add-on auf derselben Zeile: EOD-Hoch bleibt 52.800 (vorsichtig) ({pk})")
app._sb_all = sb_all
app.sb_select = lambda tb, params: [{"id": "k1", "external_id": EXT}] if tb == "accounts" else []
ok(app.liq_reset_buchung({"kind": "account_purchase", "notes": "Reset von TDFYSL150219964586 (auto)"}) and app.liq_reset_buchung({"notes": "  reset von LFE1 "})
   and not app.liq_reset_buchung({"kind": "account_purchase", "notes": "Add-on 1 % Rule"}) and not app.liq_reset_buchung({"notes": "Presetkauf"})
   and not app.liq_reset_buchung({"notes": "Reset"}) and not app.liq_reset_buchung({"notes": "Kauf nach Reset"})
   and not app.liq_reset_buchung({"kind": "payout", "notes": "Reset von X"}) and not app.liq_reset_buchung({}),
   "(b) liq_reset_buchung: nur die Notiz „Reset von …“ eines Kaufs (konto-reset-Weg), nichts anderes mit „Reset“")

# ── (b) die vier Fälle des Masters (05.11.2026), Lader wie live: accounts + transactions + trade_plans ──
EOD_P = {"id": "neu", "master_account_id": "k2", "started_at": "2026-11-05T14:00:00+00:00"}
EXT2 = "LFE20251101000009"
VERL = [{"id": "x1", "master_account_id": "k2", "konto_typ": "challenge", "started_at": "2026-11-01T14:00:00+00:00", "ended_at": "2026-11-01T15:00:00+00:00",
         "bal_end": 51800, "master_name": f"50k {EXT2} → Challenge"},
        {"id": "x2", "master_account_id": "k2", "konto_typ": "challenge", "started_at": "2026-11-04T14:00:00+00:00", "ended_at": "2026-11-04T15:00:00+00:00",
         "bal_end": 50200, "master_name": f"50k {EXT2} → Challenge"}]


def fall(tx, ext=EXT2, verl=VERL):
    app._sb_all = lambda tb, params: tx if tb == "transactions" else ([dict(z) for z in verl] if tb == "trade_plans" else [])
    app.sb_select = lambda tb, params: [{"id": "k2", "external_id": ext}] if tb == "accounts" else []
    app._liq_verlauf_cache.clear()
    v = app._liq_verlauf_laden(["k2"])
    return app.liq_peak(EOD_P, {"id": "k2", "account_type": "challenge"}, 50200, v, eod=True)


k = lambda at, notes: {"account_id": "k2", "occurred_at": at, "kind": "account_purchase", "notes": notes}   # noqa: E731
ok(fall([k("2026-11-04T00:00:00+00:00", "")]) == 51800, "(b) Probe S6: Hoch 51.800 am 01.11., einzige Kaufbuchung 04.11. → Hoch bleibt")
ok(fall([k("2026-10-20T00:00:00+00:00", ""), k("2026-11-03T00:00:00+00:00", "Add-on On Demand")]) == 51800, "(b) Add-on-Kauf auf derselben Zeile → Hoch bleibt")
ok(fall([k("2026-11-04T09:00:00+00:00", "Account-Kauf (nachgetragen)")]) == 51800, "(b) nachgetragener Erstkauf → Hoch bleibt")
ok(fall([k("2026-10-20T00:00:00+00:00", ""), k("2026-11-02T00:00:00+00:00", "Reset von LFE20251001000001 (auto)")]) == 50200,
   "(b) echter konto-reset („Reset von …“) → nur Hochs danach (50.200)")
ok(fall([], ext=EXT2, verl=[dict(VERL[0], master_name="50k LFE20251001000001 → Challenge"), VERL[1]]) == 50200,
   "(b) neue External ID (alter Plan nennt die alte Nummer) → alter Plan zählt nicht")
app._sb_all = sb_all                                                          # Stub für die Fälle unten wieder herstellen
app.sb_select = lambda tb, params: [{"id": "k1", "external_id": EXT}] if tb == "accounts" else []
app._liq_verlauf_cache.clear()
ok("master_name" in str(app.__dict__.get("_liq_verlauf_laden").__code__.co_consts), "(b) Lader liest master_name mit")
FEHL["tx"] = True
app._liq_verlauf_cache.clear()
ok([z["id"] for z in app._liq_verlauf_laden(["k1"], streng=True)] == ["a", "b", "c"], "(b) Reset-Infos nicht lesbar → ohne Filter, streng scheitert nicht")
app._sb_all, app.sb_select = alt_all, alt_sel
app._liq_verlauf_cache.clear()

# ── (a) Delta-Route: Unternehmens-Stand wiegt mit seiner Liste/seinen Modellen ──
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
r = SRC[SRC.index('def admin_auto_plan_delta():'):]
r = r[:r.index("ap_tages_saldo(stand)")]
ok('if _hb_u != "ht":' in r and "ap_waage_param_gruppe(stand.get(\"param\")" in r and "ap_gruppen_modelle()" in r,
   "(a) Delta: Stand eines Unternehmens bekommt ap_waage_param_gruppe mit den Modellen seiner IDs")
ok(r.index('if _hb_u != "ht":') > r.index('_hb_u = "ht"'), "(a) erst nach dem Laden des Stands, HT-Zweig unverändert")
F = [{"name": "Apex", "namen": ["apex"]}, {"name": "Lucid", "namen": ["lucidtrading"]}]
pg = app.ap_waage_param_gruppe({"waage_ohne": ["apex"]}, {}, F, {"lucidtrading": "orbit_prio2"})
ok(any("lucid" in k for k in pg["waage_ohne"]) and "apex" in pg["waage_ohne"], f"(a) Gruppe mit Lucid auf Prio 2: Lucid raus aus ihrer Waage ({pg['waage_ohne']})")
pg2 = app.ap_waage_param_gruppe({"waage_ohne": ["apex", "lucidtrading"]}, {"waage_ohne_modell": ["lucidtrading"]}, F, {})
ok(pg2["waage_ohne"] == ["apex"], f"(a) HT-Prio-2-Eintrag gilt der Gruppe nicht ({pg2['waage_ohne']})")

print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
