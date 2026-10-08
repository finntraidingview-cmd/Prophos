#!/usr/bin/env python3
"""Selbsttest GENAUER KONTOWERT-GRUND (app.py ap_kontowert_grund, ap_grund_ohne_balance, _ap_bewerten, _ap_stand_laden — 09.10.2026,
Slave-Terminal 3; Finn ~03:10 Dubai: „Bei solchen Fehlern will ich immer den genauen Grund haben, wie ich das genau fixen kann" — vorher
der Sammelgrund „kein Kontowert (Firma ohne Kernwerte, Größe passt nicht oder keine Balance)").

Aufruf:  python3 tools/selftest_kontowert_grund.py
Platzhalter-Konten nach den fünf Fällen aus „Braucht dich" (keine echten Nummern): verwaister Plan (Konto gelöscht), drei frische
Tradeify-150k ohne Lesung, ein Nachfolger ohne External ID, ein FTMO-Konto mit Lesung. Geprüft: (1) jeder Code rein gerechnet mit Text +
Fix, nie „oder"; (2) _ap_bewerten nennt „kein Kontowert — <Grund>" + Code/Fix; (3) der Stand nimmt für frische Konten den Startwert wie
der Planer → kein Hinweis mehr, der verwaiste Plan zeigt „Konto gelöscht" + „Diesen Plan löschen"; (4) ap_grund_ohne_balance je Ursache;
(5) die Delta-Antwort trägt hinweis_code/hinweis_fix."""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


FTMO = {"namen": ["ftmo"], "planen": False, "route": "mt5v2", "groessen": [100000, 200000], "kauf_eur": 446, "dd_pct": 10,
        "boden": "statisch", "ziel_pct": {"phase1": 10, "phase2": 5}}
ALT = {"namen": ["altefirma"], "groessen": [100000], "phasen": {"phase1": {"ziel_pct": 8}}}      # ohne Kernwerte
U = sd.U1
FRISCH = [{"id": f"k-2{i}", "user_id": U, "name": f"150k Tradeify T{i}", "firm": "Tradeify", "account_type": "challenge",
           "external_id": f"TDFY-00002{i}"} for i in (1, 2, 3)]
NACHF = {"id": "k-24", "user_id": U, "name": "NACHFOLGER 100k FundedNext → Phase 2", "firm": "FundedNext", "account_type": "phase2",
         "external_id": None}
FTMO_K = {"id": "k-25", "user_id": U, "name": "FTMO 100k", "firm": "FTMO", "account_type": "phase1", "external_id": "000025"}
BLOW = {"id": "k-27", "user_id": U, "name": "150k Tradeify geblowt", "firm": "Tradeify", "account_type": "challenge",
        "external_id": "TDFY-000027", "tv_balance_at": "2026-10-01T00:00:00+00:00"}   # 0-Lesung: acc_balance_wahl wirft 0 weg
GEHANDELT = {"id": "k-26", "user_id": U, "name": "150k Tradeify alt", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000026"}


def main():
    a = sd.lade()
    firmen = sd.FIRMEN + [FTMO, ALT]
    R = lambda firm: a["ap_regel_finden"](firmen, firm)                                        # noqa: E731
    G = lambda konto, bal: a["ap_kontowert_grund"](konto, bal, R((konto or {}).get("firm")))  # noqa: E731

    # 1 rein: jeder Code
    fall = {
        "konto_fehlt": G(None, 100000),
        "live": G({"id": "x", "firm": "Fusion", "account_type": "live"}, 5000),
        "firma_fehlt": G({"id": "x", "firm": "Lucid Trading", "account_type": "challenge"}, 50000),
        "kernwert_fehlt": G({"id": "x", "firm": "AlteFirma", "account_type": "phase1"}, 100000),
        "ext_fehlt": G(dict(NACHF), None),
        "balance_fehlt": G(dict(FTMO_K), None),
        "typ_ohne_wert": G({"id": "x", "firm": "FTMO", "account_type": "sonstwas", "external_id": "1"}, 100000),
        "ziel_erreicht": G({"id": "x", "firm": "Tradeify", "account_type": "challenge", "external_id": "1"}, 175000),
        "groesse": G({"id": "x", "firm": "FundedNext", "account_type": "phase1", "external_id": "1"}, 70000),
    }
    for code, g in fall.items():
        check(g and g["code"] == code and g["text"] and g["fix"] and " oder " not in g["text"], f"{code}: „{(g or {}).get('text')}“ → {(g or {}).get('fix')}")
    check(fall["kernwert_fehlt"]["text"] == "Firma AlteFirma: Kaufpreis, Max-Drawdown, Ziel-% je Phase fehlen in den Kernwerten"
          and "Kontogrößen" not in fall["kernwert_fehlt"]["text"], "Kernwerte: genau die fehlenden Werte beim Namen (Größen sind da)")
    g1 = G({"id": "x", "firm": "AlteFirma2", "account_type": "phase1"}, 100000)
    check(g1["code"] == "firma_fehlt", "unbekannte Firma → firma_fehlt")
    check("70.000" in fall["groesse"]["text"] and "50k / 100k" in fall["groesse"]["text"] and "±15" in fall["groesse"]["text"],
          "Größe: Balance, Größen der Kernwerte und Toleranz im Text")
    check("löschen" in fall["konto_fehlt"]["fix"], "Plan ohne Konto → Fix „Diesen Plan löschen“")
    check(G(dict(FTMO_K), 100000) is None and G(FRISCH[0], 150000) is None, "Kontowert da → kein Grund")

    # 2 _ap_bewerten
    jetzt = datetime.now(timezone.utc)
    sd.db_stubs(a, jetzt)
    ctx = {"firmen": firmen, "kauf": {}, "ppl": {}, "ppl_firma": {}}
    b = a["_ap_bewerten"](ctx, None, None, 3, "tvv2", "NQ", "buy", 3500, None)
    check(b["hinweis"] == "kein Kontowert — " + fall["konto_fehlt"]["text"] and b["hinweis_code"] == "konto_fehlt" and b["hinweis_fix"],
          f"_ap_bewerten ohne Konto → „{b['hinweis']}“")
    b = a["_ap_bewerten"](ctx, dict(FRISCH[0]), 150000.0, 3, "tvv2", "NQ", "buy", 3500, None)
    check(b["hinweis"] is None and b["hinweis_code"] is None and b["delta_eur_pkt"], "_ap_bewerten mit Balance → Delta, kein Hinweis")

    # 3 Stand: frische Konten mit Startwert, verwaister Plan, Nachfolger, FTMO
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    mitt = datetime(tag.year, tag.month, tag.day, tzinfo=ZoneInfo("Europe/Berlin"))
    t0 = max(jetzt, mitt) + timedelta(minutes=40)

    def plan(pid, konto, firm, route, minute, tp=3500, menge=3):
        return {"id": pid, "user_id": U, "master_account_id": konto, "master_firm": firm, "status": "planned", "richtung": "buy",
                "master_tp": tp, "master_sl": None, "master_contracts": menge, "master_symbol": "NQZ6" if route == "tvv2" else None,
                "route": route, "start_um": (t0 + timedelta(minutes=minute)).isoformat(), "auto_plan": True, "created_at": jetzt.isoformat()}
    # p-weg: Waise (Konto gelöscht, nie geclaimt) — seit 8a37948 (.1396, Slave 5) gar nicht im Stand, der Sweep löscht sie;
    # p-weg2: geclaimte Waise (bleibt, dort läuft vielleicht schon etwas) → genauer Grund „Konto gelöscht"
    geplant = [plan("p-weg", None, "FTMO", "mt5v2", 0, 8000, 2),
               dict(plan("p-weg2", None, "FTMO", "mt5v2", 1, 8000, 2), start_um_gestartet_at=jetzt.isoformat())] + [plan(f"p-t{i}", k["id"], "Tradeify", "tvv2", 5 * i) for i, k in enumerate(FRISCH, 1)] \
        + [plan("p-nf", NACHF["id"], "FundedNext", "mt5v2", 30, 6000, 2.5), plan("p-ftmo", FTMO_K["id"], "FTMO", "mt5v2", 35, 8000, 2),
           plan("p-alt", GEHANDELT["id"], "Tradeify", "tvv2", 40), plan("p-blow", BLOW["id"], "Tradeify", "tvv2", 45)]
    reg, _ = sd.db_stubs(a, jetzt, geplant)
    reg["regeln"]["firmen"] = firmen
    basis_all, basis_bal = a["_sb_all"], a["acc_balance_wahl"]
    neu = [dict(k) for k in FRISCH + [NACHF, FTMO_K, GEHANDELT, BLOW]]

    def _sb_all(table, params):
        rows = basis_all(table, params)
        if table == "accounts":
            ids = params.get("id", "")
            rows += [dict(k) for k in neu if k["id"] in ids]
        return rows
    verlauf = []

    def mit_trade(ids):
        verlauf.append(sorted(ids))
        return {"k-26"} & set(ids)
    a.update(_sb_all=_sb_all, _ap_konten_mit_trade=mit_trade,
             acc_balance_wahl=lambda k, e, d: ((100000.0, "USD", "Echo", "2999-01-01") if str((k or {}).get("id")) == "k-25"
                                               else (None, None, None, "") if str((k or {}).get("id")) in ("k-21", "k-22", "k-23", "k-24", "k-26", "k-27")
                                               else basis_bal(k, e, d)))
    stand = a["_ap_stand_laden"](reg, jetzt=max(jetzt, mitt + timedelta(minutes=1)), tag=tag.strftime("%Y-%m-%d"))
    dl = a["ap_delta_antwort"](stand)
    gp = {x["plan_id"]: x for x in dl["geplant"]}
    print("   Texte im Stand (wie „Braucht dich“ sie bekommt):")
    for pid in ("p-weg", "p-weg2", "p-t1", "p-t2", "p-t3", "p-nf", "p-ftmo", "p-alt"):
        z = gp.get(pid) or {}
        print(f"     {pid}: {z.get('hinweis') or '— kein Hinweis (Kontowert ' + str(z.get('wert_eur')) + ' €)'}"
              + (f" → {z.get('hinweis_fix')}" if z.get("hinweis_fix") else ""))
    check("p-weg" not in gp, "ungeclaimte Waise zählt nicht im Stand (ap_ist_waise, Sweep löscht sie)")
    w = gp.get("p-weg2") or {}
    check(w.get("hinweis_code") == "konto_fehlt" and "Konto gibt es nicht mehr" in str(w.get("hinweis")) and "löschen" in str(w.get("hinweis_fix")),
          "geclaimte Waise (Konto gelöscht) → „Plan ohne Konto …“ + „Diesen Plan löschen“")
    check(all(not (gp.get(p) or {}).get("hinweis") and (gp.get(p) or {}).get("wert_eur") for p in ("p-t1", "p-t2", "p-t3")),
          f"drei frische Tradeify-150k → Startwert wie der Planer, Kontowert da, kein Hinweis ({[(gp.get(p) or {}).get('wert_eur') for p in ('p-t1', 'p-t2', 'p-t3')]})")
    check(not (gp.get("p-nf") or {}).get("hinweis") and (gp.get("p-nf") or {}).get("wert_eur"),
          "Nachfolger ohne External ID, nie gehandelt → Startwert 100k, Kontowert da")
    check((gp.get("p-nf") or {}).get("ext_fehlt") is True and not any((gp.get(p) or {}).get("ext_fehlt") for p in ("p-t1", "p-ftmo", "p-alt", "p-weg2")),
          "Delta ext_fehlt: nur der Nachfolger ohne External ID (CFD vorab in „Braucht dich“, Master 09.10.2026)")
    ft = gp.get("p-ftmo") or {}
    check(ft.get("wert_eur") == 446 and "Kontowert" not in str(ft.get("hinweis") or ""),
          f"FTMO mit Echo-Balance 100.000 → Kontowert 446 €, kein Kontowert-Grund (Test ohne firm_specs: „{ft.get('hinweis')}“)")
    al = gp.get("p-alt") or {}
    check(al.get("hinweis_code") == "balance_fehlt" and "noch keine Balance gelesen" in str(al.get("hinweis")),
          f"schon gehandeltes Konto ohne Lesung → kein Startwert, „{al.get('hinweis')}“")
    check(verlauf and set(verlauf[0]) == {"k-21", "k-22", "k-23", "k-24", "k-26"},
          f"Trade-Verlauf nur für Startwert-Kandidaten, ein Read — geblowtes Konto mit 0-Lesung nicht abgefragt (Prüfer Slave 2) ({verlauf})")
    bl = gp.get("p-blow") or {}
    check(bl.get("hinweis_code") == "balance_fehlt" and "Lesung ohne Wert" in str(bl.get("hinweis")),
          f"geblowtes Konto mit 0-Lesung → kein Startwert, „{bl.get('hinweis')}“")
    K = a["ap_startwert_kandidat"]
    check(K(FRISCH[0], {}, {}) and not K(BLOW, {}, {}) and not K(FRISCH[0], {"TDFY-000021": 1}, {})
          and not K({"firm": "Topstep", "account_type": "funded", "external_id": "EXPRESS-1"}, {}, {}),
          "ap_startwert_kandidat: frisch ja; Lesung / Login bei Echo / Topstep Express nein")
    hw = [h for h in stand.get("hinweise") or [] if h.get("plan_id") == "p-weg2"]
    check(hw and hw[0].get("code") == "konto_fehlt" and hw[0].get("fix"), f"hinweise[] tragen code + fix ({hw})")

    # 4 ap_grund_ohne_balance
    O = a["ap_grund_ohne_balance"]
    check(O(dict(NACHF), False)["code"] == "ext_fehlt", "ohne External ID → ext_fehlt")
    check(O(dict(FRISCH[0]), None)["code"] == "verlauf_fehler", "Verlauf nicht lesbar → verlauf_fehler")
    check(O(dict(FRISCH[0]), True)["code"] == "schon_gehandelt", "schon gehandelt → schon_gehandelt")
    check(O(dict(FRISCH[0]), False, gelesen=True)["code"] == "leer_gelesen", "Echo kennt den Login ohne Balance → leer_gelesen")
    check(O(dict(FRISCH[0], tv_balance_at="2026-10-01T00:00:00+00:00"), False)["code"] == "leer_gelesen", "frühere Lesung ohne Wert → leer_gelesen")
    check(O({"id": "x", "firm": "Topstep", "account_type": "funded", "external_id": "EXPRESS-1"}, False)["code"] == "express", "Topstep Express → express")
    g = O({"id": "x", "name": "Tradeify Konto", "firm": "Tradeify", "account_type": "challenge", "external_id": "X"}, False)
    check(g["code"] == "groesse_fehlt" and g["text"].startswith("keine Balance bekannt — "), f"Größe nicht erkennbar → „{g['text']}“")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
