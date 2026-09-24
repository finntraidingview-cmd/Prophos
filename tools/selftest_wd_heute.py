#!/usr/bin/env python3
"""Selbsttest fuer /admin/wd-heute (app.py) — nur die rein rechnenden Teile, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_wd_heute.py
Laedt die Funktionen per Quelltext aus app.py (app.py selbst zieht beim Import Flask und
Umgebungsvariablen — das braucht kein Rechen-Test). Prueft: CME-Handelstag, Level aus
$-Distanz (BUY und SELL, NQ und MNQ, ohne Einstieg = null), Kontogroesse, Zeilenaufbau aus
mt5_baseline (Hedge, Rundgang-P&L, Ende-Differenz) und die Sortierung open → planned → Rest."""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}

    def block(name):
        i = src.index(f"def {name}(")
        j = src.find("\n\n\n", i)
        return src[i:j]

    def const(name):
        m = re.search(rf"^{name} = .*$", src, re.M)
        return m.group(0)

    code = "\n".join([const("WD_HEUTE_PPL"), block("_wd_num"), block("_symbol_wurzel"), block("_cme_handelstag"),
                      block("_wd_level"), block("_wd_konto_groesse"), block("_wd_heute_zeile"),
                      block("_wd_heute_sortkey"), block("_wd_heute_sortieren"), block("_wd_ohne_master_sl")])
    exec(code, ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    # CME-Handelstag: 16:59 CT 24.09. → 24.09.; 17:01 CT 24.09. (= 22:01 UTC) → 25.09.; Unix-Sekunden; Unsinn → None
    check(a["_cme_handelstag"]("2026-09-24T21:59:00+00:00") == "2026-09-24"
          and a["_cme_handelstag"]("2026-09-24T22:01:00Z") == "2026-09-25"
          and a["_cme_handelstag"](1790268262) == "2026-09-24"
          and a["_cme_handelstag"]("quatsch") is None and isinstance(a["_cme_handelstag"](None), str),
          "CME-Handelstag: Session ab 17:00 Chicago traegt das Folgedatum (ISO, Z, Unix, None)")

    lvl = a["_wd_level"]
    check(lvl(30000, "buy", 280, 2, 1, True) == 30140.0 and lvl(30000, "buy", 100, 2, 1, False) == 29950.0,
          "Level BUY MNQ 1 Kt: TP $280 → +140 Pkt, SL $100 → −50 Pkt")
    check(lvl(30000, "sell", 280, 2, 1, True) == 29860.0 and lvl(30000, "sell", 100, 2, 1, False) == 30050.0,
          "Level SELL MNQ: TP unter, SL ueber dem Einstieg")
    check(lvl(30000, "buy", 400, 20, 2, True) == 30010.0 and lvl(30000, "sell", 400, 20, 2, False) == 30010.0,
          "Level NQ 2 Kt: $400 = 10 Pkt")
    check(lvl(None, "buy", 280, 2, 1, True) is None and lvl(30000, "buy", None, 2, 1, True) is None
          and lvl(30000, "", 280, 2, 1, True) is None and lvl(30000, "buy", 280, None, 1, True) is None and lvl("x", "buy", 1, 2, 1, True) is None,
          "Level: ohne Einstieg/Betrag/Richtung/Punktwert/Unsinn → None")

    check(a["_wd_konto_groesse"]({"starting_balance": 100000}) == 100000 and a["_wd_konto_groesse"]({"name": "150k Apex PAAPEX…"}) == 150000
          and a["_wd_konto_groesse"]({"name": "Konto ohne Groesse"}) is None and a["_wd_konto_groesse"](None) is None,
          "Kontogroesse: starting_balance, sonst '150k' aus dem Namen, sonst None")

    disp = {"u1": "Moritz"}
    p = {"id": "p1", "user_id": "u1", "master_account_id": "a1", "route": "tvv2", "notes": "Winning-Day-Farmer", "status": "open",
         "richtung": "buy", "master_contracts": "1", "master_symbol": "MNQZ6", "master_symbol_root": None, "master_tp": "280", "master_sl": None,
         "master_pl": None, "hedge_eur": "70", "hedge_faktor": None, "start_um": None, "start_um_gestartet_at": "2026-09-24T10:00:00Z",
         "started_at": "2026-09-24T10:00:30Z", "ended_at": None, "completed_at": None, "planned_for": "2026-09-24", "created_at": "2026-09-24T09:00:00Z",
         "mt5_baseline": {"tv": {"today_pnl_start": 10.0, "datum_start": "2026-09-24"}, "live": {"pnl": -12.5, "offen": True, "at": "2026-09-24T11:00:00Z"},
                          "hedge": {"status": "offen", "richtung": "sell", "lots": 0.59, "fill": 20000.5, "sl": 20143.0, "tp": 0, "einstieg_nq": 30000.25, "pc": "pc-x"}}}
    z = a["_wd_heute_zeile"](p, {"name": "150k Apex", "firm": "Apex Trader", "starting_balance": None, "external_id": "APEX6416990000025"}, disp)
    check(z["person"] == "Moritz" and z["symbol_root"] == "MNQ" and z["kontrakte"] == 1.0 and z["einstieg_nq"] == 30000.25
          and z["tp_level_nq"] == 30140.25 and z["sl_level_nq"] is None and z["master_pl"] == {"wert": -12.5, "at": "2026-09-24T11:00:00Z", "quelle": "rundgang"}
          and z["hedge"]["lots"] == 0.59 and z["hedge"]["pc"] == "pc-x" and z["quelle"] == "farmer" and z["verknuepft"] is True
          and z["konto"]["groesse"] == 150000 and z["konto"]["kontonr_ende"] == "0025" and z["farbe_key"] == "u1"
          and z["id"] == "p1" and z["kt"] == 1.0 and z["handelstag"] == "2026-09-24" and z["grund"] is None,
          "Zeile: Wurzel aus master_symbol, Level aus hedge.einstieg_nq, Rundgang-P&L, Hedge komplett, kontonr_ende, farbe_key, farmer, verknuepft")
    p2 = dict(p, id="p2", notes=None, hedge_eur=None, status="review", master_sl="100", started_at="2026-09-24T22:30:00Z", ended_at="2026-09-24T23:00:00Z",
              mt5_baseline={"tv": {"today_pnl_start": 10.0, "datum_start": "2026-09-25"}, "final": {"today_pnl": 40.0, "datum": "2026-09-25", "at": "x"}})
    z2 = a["_wd_heute_zeile"](p2, None, {})
    check(z2["einstieg_nq"] is None and z2["tp_level_nq"] is None and z2["master_pl"] == {"wert": 30.0, "at": "x", "quelle": "final"}
          and z2["hedge"] is None and z2["quelle"] == "manuell" and z2["person"] == "u1" and z2["handelstag"] == "2026-09-25" and z2["konto"]["name"] == ""
          and z2["grund"] == "rundgang" and z2["farbe_key"] == "u1" and z2["konto"]["kontonr_ende"] == "",
          "Zeile: ohne Hedge keine Level, Ende-Differenz final − Start am selben Tag, manuell, Handelstag = Folgetag nach 17:00 CT")
    p4 = dict(p2, id="p4", mt5_baseline={"tv": {"today_pnl_start": 10.0, "datum_start": "2026-09-25", "einstieg_nq": "30000.5"}})
    z4 = a["_wd_heute_zeile"](p4, None, {})
    check(z4["einstieg_nq"] == 30000.5 and z4["einstieg_quelle"] == "tv" and z4["tp_level_nq"] == 30140.5 and z4["sl_level_nq"] == 29950.5 and z4["hedge"] is None,
          "Zeile ohne Hedge: Einstieg aus der tv-Baseline, Level gerechnet, Quelle 'tv'")
    check(z["einstieg_quelle"] == "hedge" and z2["einstieg_quelle"] is None, "einstieg_quelle: hedge / null")
    # Chart-Linie = Wächter-Level (25.09.2026): eingefrorene Level am Hedge schlagen die Rechnung aus einem nachgetragenen Einstieg
    ph = dict(p, id="ph", master_contracts="1", master_symbol="MNQZ6", master_tp="280", master_sl=None,
              mt5_baseline=dict(p["mt5_baseline"], hedge=dict(p["mt5_baseline"]["hedge"], einstieg_nq=30618.0, einstieg_quelle="puls avg_fill (nachgetragen)",
                                                              tp_level_nq=30752.1, schliesst_bei_nq=30754.1, sl_level_nq=None)))
    zh = a["_wd_heute_zeile"](ph, None, {})
    check(zh["tp_level_nq"] == 30752.1 and zh["schliesst_bei_nq"] == 30754.1 and zh["level_quelle"] == "hedge" and zh["sl_level_nq"] is None
          and zh["einstieg_nq"] == 30618.0, "wd-heute: TP-Linie = hedge.tp_level_nq (nicht Fill + Distanz), schliesst_bei_nq durchgereicht, ohne Master-SL kein SL")
    check(z["level_quelle"] == "einstieg" and z["schliesst_bei_nq"] is None and z4["level_quelle"] == "einstieg" and z2["level_quelle"] is None,
          "wd-heute: ohne Level am Hedge gerechnet (level_quelle einstieg), ohne Einstieg null")
    # Winning Days ohne Master-SL (Finn 25.09.2026): POST/PATCH schreiben master_sl immer null, wd-heute rechnet dann kein SL-Level
    osl = a["_wd_ohne_master_sl"]
    d1, v1 = osl({"master_sl": 250, "master_tp": 280, "master_risk": 250})
    d2, v2 = osl({"master_sl": None}); d3, v3 = osl({"master_sl": ""}); d4, v4 = osl({"master_tp": 1})
    check(d1 == {"master_sl": None, "master_tp": 280, "master_risk": 250} and v1 is True and d2["master_sl"] is None and v2 is False
          and v3 is False and d4 == {"master_tp": 1, "master_sl": None} and v4 is False and osl(None) == (None, False),
          "ohne Master-SL: Wert → null (verworfen gemeldet), null/leer bleibt null, master_risk unangetastet")
    for leer in (None, "", "0", 0):
        zl = a["_wd_heute_zeile"](dict(p4, master_sl=leer), None, {})
        check(zl["sl_level_nq"] is None and zl["tp_level_nq"] == 30140.5, f"wd-heute: master_sl {leer!r} → sl_level_nq null, TP-Level bleibt")
    p3 = dict(p2, id="p3", master_pl="55.5", completed_at="2026-09-25T01:00:00Z", status="completed")
    check(a["_wd_heute_zeile"](p3, None, {})["master_pl"]["quelle"] == "plan", "Zeile: fertiger master_pl schlaegt alles")

    zeilen = [{"status": "completed", "ended_at": "2026-09-24T05:00:00Z"}, {"status": "planned", "start_um": "2026-09-24T12:00:00Z"},
              {"status": "open", "started_at": "2026-09-24T09:00:00Z"}, {"status": "review", "ended_at": "2026-09-24T07:00:00Z"},
              {"status": "planned", "start_um": "2026-09-24T10:00:00Z"}, {"status": "open", "started_at": "2026-09-24T08:00:00Z"}]
    s = a["_wd_heute_sortieren"](zeilen)
    check([x["status"] for x in s] == ["open", "open", "planned", "planned", "review", "completed"]
          and s[0]["started_at"] < s[1]["started_at"] and s[2]["start_um"] < s[3]["start_um"] and s[4]["ended_at"] > s[5]["ended_at"],
          "Sortierung: open (started_at auf) → planned (start_um auf) → Rest (ended_at ab)")

    print("\n" + ("alle Tests bestanden" if ok else "FEHLER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
