#!/usr/bin/env python3
"""Selbsttest: Riegel „Puls bleibt zu Hause" (app.py puls_heim_nah / puls_heim_schwellen / puls_heim_big_trades / puls_heim_kurs_frisch,
19.10.2026 — Finn: „knapp am TP oder an der Liq darf der Puls nicht mehr raus … fest 2.000 $ vor TP und 2.000 $ vor der Liq").
Rein rechnend, ohne Netz. Zahlen frei erfunden.  Aufruf: python3 tools/selftest_puls_heim.py"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "_ap_norm", "_ap_de", "puls_heim_schwellen", "puls_heim_nah", "puls_heim_kurs_frisch", "puls_heim_big_trades")
KONSTANTEN = ("PULS_HEIM_KURS_MAX_ALTER_S", "PULS_HEIM_CODE_NAH", "PULS_HEIM_CODE_UNKLAR")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    teile = []
    for k in KONSTANTEN:
        teile.append(re.search(rf"^{k} = .*$", src, re.M).group(0))
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    nah, schw, frisch, big = ns["puls_heim_nah"], ns["puls_heim_schwellen"], ns["puls_heim_kurs_frisch"], ns["puls_heim_big_trades"]
    f = []
    ok = lambda b, t: f.append(t) if not b else None
    regel = {"aktiv": True, "tp_usd": 2000, "liq_usd": 2000, "firmen": {"apextrader": {"liq_usd": 1500}}}

    # Schwellen: Standard, Firmen-Override, aus
    ok(schw(regel, "Tradeify") == (2000.0, 2000.0), f"Standard: {schw(regel, 'Tradeify')}")
    ok(schw(regel, "Apex Trader") == (2000.0, 1500.0), f"Apex-Override: {schw(regel, 'Apex Trader')}")
    ok(schw(dict(regel, aktiv=False), "Tradeify") is None, "aktiv=false nicht None")
    ok(schw(None, "x") is None, "ohne Regel nicht None")

    # BUY 3 NQ, Einstieg 30.000, TP 30.075 (= 4.500 $), Liq 29.925 (= −4.500 $); Punktwert 20
    z = {"richtung": "buy", "punktwert": 20, "kt": 3, "tp_level_nq": 30075, "sl_level_nq": 29925, "sl_art": "liquidation",
         "liq_level_nq": None, "liq_regel_level_nq": 29930}
    r = nah(z, 30000, (2000, 2000))                  # Rest TP 75 Pkt·60 = 4.500 $, Liq engste 29.930 → 70 Pkt = 4.200 $
    ok(r["nah"] is False, f"Mitte: {r}")
    ok(r["rest_tp_usd"] == 4500 and r["rest_liq_usd"] == 4200 and r["liq_level"] == 29930, f"Reste/engste Liq: {r}")
    r = nah(z, 30045, (2000, 2000))                  # 30 Pkt vor TP = 1.800 $ → nah
    ok(r["nah"] is True and "vor dem TP" in r["grund"], f"nah am TP: {r}")
    r = nah(z, 29960, (2000, 2000))                  # 30 Pkt über engster Liq (29.930) = 1.800 $ → nah
    ok(r["nah"] is True and "vor der Liq" in r["grund"], f"nah an Liq: {r}")
    r = nah(z, 30080, (2000, 2000))                  # schon über dem TP → Rest ≤ 0 → nah
    ok(r["nah"] is True and r["rest_tp_usd"] < 0, f"über TP: {r}")
    r = nah(z, 30045, (1000, 1000))                  # strengere Schwelle: 1.800 $ > 1.000 → frei
    ok(r["nah"] is False, f"Schwelle 1.000: {r}")
    # SELL gespiegelt: Einstieg 30.000, TP 29.925, Liq 30.075
    zs = {"richtung": "sell", "punktwert": 20, "kt": 3, "tp_level_nq": 29925, "sl_level_nq": 30075, "sl_art": "bracket"}
    ok(nah(zs, 30000, (2000, 2000))["nah"] is False, "SELL Mitte")
    ok(nah(zs, 29950, (2000, 2000))["nah"] is True, "SELL nah TP")
    ok(nah(zs, 30050, (2000, 2000))["nah"] is True, "SELL nah Liq")
    # MNQ: Punktwert 2, 10 Kontrakte → 1 Pkt = 20 $; 30 Pkt vor TP = 600 $ → nah
    zm = dict(z, punktwert=2, kt=10)
    ok(nah(zm, 30045, (2000, 2000))["nah"] is True, "MNQ nah")
    ok(nah(zm, 29960, (2000, 2000))["rest_liq_usd"] == 600, f"MNQ Liq-Rest: {nah(zm, 29960, (2000, 2000))}")
    # nicht prüfbar → None
    ok(nah(z, None, (2000, 2000))["nah"] is None, "ohne Kurs nicht None")
    ok(nah(dict(z, tp_level_nq=None), 30000, (2000, 2000))["nah"] is None, "ohne TP nicht None")
    ok(nah(dict(z, sl_level_nq=None, liq_regel_level_nq=None), 30000, (2000, 2000))["nah"] is None, "ohne Liq nicht None")
    ok(nah(dict(z, kt=None), 30000, (2000, 2000))["nah"] is None, "ohne Kontrakte nicht None")
    ok(nah(dict(z, richtung=""), 30000, (2000, 2000))["nah"] is None, "ohne Richtung nicht None")

    # Kurs frisch: Minute jünger als 5 min (+60 s Toleranz) zählt, älter nicht; MNQ fällt auf NQ zurück
    jetzt = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)
    kurse = {"NQ": {"kurs": 30000, "minute": "2026-10-19T09:58:00+00:00"}}
    ok(frisch(kurse, "NQ", jetzt) == 30000, "frisch NQ")
    ok(frisch(kurse, "MNQ", jetzt) == 30000, "MNQ → NQ")
    ok(frisch({"NQ": {"kurs": 30000, "minute": "2026-10-19T09:50:00+00:00"}}, "NQ", jetzt) is None, "10 min alt nicht None")
    ok(frisch({}, "NQ", jetzt) is None, "leer nicht None")

    # Big Trades dieses PCs
    pl = [{"id": "a", "status": "open", "route": "tvv2", "hedge_eur": 800, "mt5_baseline": {"hedge": {"pc": "pc-1"}}},
          {"id": "b", "status": "open", "route": "tvv2", "orbit_v3": True, "mt5_baseline": {"hedge": {"pc": "pc-1"}}},
          {"id": "c", "status": "open", "route": "tvv2", "hedge_eur": 800, "winning_day": True, "mt5_baseline": {"hedge": {"pc": "pc-1"}}},
          {"id": "d", "status": "open", "route": "tvv2", "hedge_eur": 0, "mt5_baseline": {"hedge": {"pc": "pc-1"}}},
          {"id": "e", "status": "open", "route": "tvv2", "hedge_eur": 800, "mt5_baseline": {"hedge": {"pc": "pc-2"}}},
          {"id": "f", "status": "planned", "route": "tvv2", "hedge_eur": 800, "mt5_baseline": {"hedge": {"pc": "pc-1"}}},
          {"id": "g", "status": "open", "route": "mt5v2", "hedge_eur": 800, "mt5_baseline": {"hedge": {"pc": "pc-1"}}},
          {"id": "h", "status": "open", "route": "tsv2", "hedge_eur": 500, "mt5_baseline": {"hedge": {"pc": "pc-1"}}}]
    ids = sorted(p["id"] for p in big(pl, "pc-1"))
    ok(ids == ["a", "b", "h"], f"Big Trades pc-1: {ids}")
    ok([p["id"] for p in big(pl, "pc-1", ausser="a")] == ["b", "h"], "ausser")
    ok(big(pl, "pc-9") == [], "fremder PC")

    if f:
        print("FEHLER:\n  " + "\n  ".join(f))
        sys.exit(1)
    print("OK selftest_puls_heim: Schwellen, Nähe BUY/SELL/MNQ, nicht prüfbar, Kurs-Frische, Big Trades je PC")


if __name__ == "__main__":
    main()
