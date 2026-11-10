#!/usr/bin/env python3
"""Selbsttest: Fusion-Blindgänger-Wache (app.py fb_positionen / fb_urteil / fb_schritt / fb_texte, FW1 10.11.2026 — Finn: „Sobald eine Order
keinen Master hat … instant eine Meldung ans Handy"). Rein rechnend, ohne Netz. Zahlen frei erfunden.  Aufruf: python3 tools/selftest_fusion_blind.py"""
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_ap_tz", "_fb_ts", "_fb_plan8", "fb_positionen", "fb_urteil", "fb_schritt", "fb_texte")
KONSTANTEN = ("HEDGE_LEBT", "FB_TAKT_S", "FB_FRISCH_S", "FB_NACH_ZU_S", "FB_WEG_N", "FB_KARENZ_S")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "time": time}
    teile = []
    for k in KONSTANTEN:
        i = re.search(rf"^{k} = ", src, re.M).start()
        teile.append(src[i:src.index("\n", i)])
    i = re.search(r"^FB_TITEL = ", src, re.M).start()
    teile.append(src[i:src.index("}\n", i) + 1])
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def zeile(pc, ts, solo=(), fr=(), hd=None, pos=None, note=None, login="488579", uid="u-ht", alive=True, cfg="config-a.json"):
    return {"pc_name": pc, "config_file": cfg, "master_login": "14333187", "hedge_login": login, "alive": alive, "updated_at": iso(ts),
            "user_id": uid, "login": login, "solo": list(solo) if solo is not None else None, "fr": list(fr) if fr is not None else None,
            "hd": hd, "pos": pos, "note": note}


def solo(tk, p8, lots=3.05, richtung="sell"):
    return {"ticket": tk, "symbol": "NAS100", "type": 1 if richtung == "sell" else 0, "volume": lots, "lots": lots, "richtung": richtung,
            "comment": f"PXsolo:{p8}", "plan8": p8, "plan_id": None}


def main():
    ns = lade()
    pos_f, urteil, schritt, texte = ns["fb_positionen"], ns["fb_urteil"], ns["fb_schritt"], ns["fb_texte"]
    f = []
    ok = lambda b, t: f.append(t) if not b else None
    T0 = 1_800_000_000.0

    def plan(pid, status, hst, ticket=None, closed=None, pc="pc-7ftp5l"):
        h = {"status": hst, "pc": pc}
        if ticket:
            h["ticket"] = ticket
        if closed:
            h["closed_at"] = iso(closed)
        return {"id": pid, "user_id": "u-ht", "status": status, "master_firm": "Tradeify", "master_name": "150k FTDFY…6154 → Funded", "hedge": h}

    P1 = "917fc42f-8ac5-4e6c-9981-1d722197fa65"

    # 1) Vereinigung über PCs am selben Konto, alte / tote / Emin-Zeilen zählen nicht
    rows = [zeile("pc-a", T0 - 3, [solo(1, "917fc42f")]), zeile("pc-b", T0 - 5, [solo(1, "917fc42f")]),
            zeile("pc-alt", T0 - 100, [solo(2, "aaaaaaaa")]), zeile("pc-tot", T0 - 2, [solo(3, "bbbbbbbb")], alive=False),
            zeile("pc-emin", T0 - 2, [solo(4, "cccccccc")], login="430095", uid="u-emin")]
    p, les = pos_f(rows, T0, {"u-emin"})
    ok(set(p) == {("488579", 1)}, f"1 Vereinigung/Filter: {set(p)}")
    ok(sorted(p[("488579", 1)]["pcs"]) == ["pc-a", "pc-b"] and p[("488579", 1)]["lesung"] == T0 - 3, "1 pcs/lesung")
    ok(les.get(("konto", "488579")) == T0 - 3, f"1 lesbar {les}")
    # Lesefehler (solo None) → Konto nicht lesbar
    p, les = pos_f([zeile("pc-a", T0 - 3, None)], T0)
    ok(not p and ("konto", "488579") not in les, "1 None = nicht lesbar")

    # 2) Urteile
    e = {"quelle": "solo", "ticket": 1, "plan8": "917fc42f", "plan_id": None}
    ok(urteil(e, {}, set())[0] == "ohne_plan", "2 ohne Plan")
    ok(urteil(e, {P1: plan(P1, "open", "offen", 1)}, set())[0] is None, "2 offener Plan, eigenes Ticket")
    ok(urteil(e, {P1: plan(P1, "open", "offen", 99)}, set())[0] == "doppelt", "2 doppelt")
    ok(urteil(e, {P1: plan(P1, "review", "offen", 1)}, set())[0] is None, "2 review + lebt → bestehender hedge_offen")
    ok(urteil(e, {P1: plan(P1, "review", "geschlossen", 1, T0 - 60)}, set())[0] == "plan_zu", "2 Hedge laut DB zu")
    ok(urteil(e, {P1: plan(P1, "open", "fehler")}, set())[0] == "ohne_ticket", "2 Öffnen scheiterte laut Tab")
    ok(urteil(e, {P1: plan(P1, "cancelled", None)}, set())[0] == "plan_zu", "2 Plan storniert")
    ok(urteil(e, {P1: plan(P1, "review", "geschlossen", 1, T0 - 60)}, {"1"})[0] is None, "2 anderer Plan führt das Ticket")
    ok(urteil({"quelle": "fremd", "ticket": 7}, {}, set())[0] == "fremd", "2 fremde magic")
    ok(urteil({"quelle": "fremd", "ticket": 7}, {}, {"7"})[0] is None, "2 fremde magic, aber Plan-Ticket")
    ok(urteil({"quelle": "echo", "ticket": 8}, {}, set())[0] == "echo_waise", "2 Echo-Waise")
    # plan8 mehrdeutig → kein Plan
    P1b = "917fc42f-0000-4000-8000-000000000001"
    ok(urteil(e, {P1: plan(P1, "open", "offen", 1), P1b: plan(P1b, "open", "offen", 2)}, set())[0] == "ohne_plan", "2 plan8 mehrdeutig")

    # 3) Karenz + genau eine Meldung + ✅
    kand, gem = {}, {}
    plaene = {}
    neu_alle = []
    for i in range(6):
        t = T0 + i * 10
        p, les = pos_f([zeile("pc-a", t - 2, [solo(1, "917fc42f")])], t)
        neu, erl = schritt(p, les, plaene, set(), kand, gem, t)
        neu_alle += [(t, n[1]) for n in neu]
    ok(len(neu_alle) == 1 and neu_alle[0] == (T0 + 20, "ohne_plan"), f"3 genau eine Meldung nach 20 s: {neu_alle}")
    # Position weg: erste neue Lesung → noch nichts, zweite → ✅
    erl_alle = []
    for i in range(6, 9):
        t = T0 + i * 10
        p, les = pos_f([zeile("pc-a", t - 2, [])], t)
        neu, erl = schritt(p, les, plaene, set(), kand, gem, t)
        erl_alle += [(t, k) for k, _ in erl]
        ok(not neu, "3 keine neue Meldung")
    ok(erl_alle == [(T0 + 70, "488579|1")] and not gem, f"3 ✅ nach 2 Lesungen: {erl_alle}")
    # gleiche Lesung zweimal (mt5_live nicht neu) zählt nur einmal
    kand, gem = {}, {}
    for t in (T0, T0 + 10, T0 + 20, T0 + 30):
        p, les = pos_f([zeile("pc-a", T0 - 1, [solo(1, "917fc42f")])], t)
        neu, _ = schritt(p, les, {}, set(), kand, gem, t)
        ok(not neu, "3 dieselbe Lesung zählt nicht doppelt")
    # ohne lesbares Konto kein ✅
    gem = {"488579|1": {"lkey": ["konto", "488579"], "weg": 0, "lesung": T0}}
    for t in (T0 + 10, T0 + 20, T0 + 30):
        neu, erl = schritt({}, {}, {}, set(), {}, gem, t)
        ok(not erl, "3 kein ✅ ohne Lesung")

    # 4) Hedge zu: Lesungen vor closed_at + 5 s zählen nicht (mt5_live-Verzug), danach normal
    kand, gem = {}, {}
    zu = T0 + 15
    plaene = {P1: plan(P1, "review", "geschlossen", 1, zu)}
    meld = []
    for i in range(8):
        t = T0 + i * 10
        p, les = pos_f([zeile("pc-a", t - 9, [solo(1, "917fc42f")])], t)
        neu, _ = schritt(p, les, plaene, set(), kand, gem, t)
        meld += [(t, n[1]) for n in neu]
    # erste zählende Lesung: t-9 ≥ 20 → t=30 (n=1, erst=30), t=40 n=2, Karenz 20 → t=50
    ok(meld == [(T0 + 50, "plan_zu")], f"4 plan_zu erst nach closed_at+5 und Karenz: {meld}")
    # Position verschwindet in der Verzugs-Zeit → nie eine Meldung
    kand, gem = {}, {}
    meld = []
    for i in range(8):
        t = T0 + i * 10
        p, les = pos_f([zeile("pc-a", t - 2, [solo(1, "917fc42f")] if t - 2 < zu + 4 else [])], t)
        neu, _ = schritt(p, les, plaene, set(), kand, gem, t)
        meld += neu
    ok(not meld, "4 normaler Schluss mit Verzug → keine Meldung")

    # 5) offener Plan → nie; Wechsel von blind zu normal setzt zurück
    kand, gem = {}, {}
    meld = []
    for i in range(10):
        t = T0 + i * 10
        pl = {P1: plan(P1, "open", "offen" if i >= 1 else "oeffnet", 1)}
        p, les = pos_f([zeile("pc-a", t - 2, [solo(1, "917fc42f")])], t)
        neu, _ = schritt(p, les, pl, set(), kand, gem, t)
        meld += neu
    ok(not meld, "5 offener Plan bleibt still")
    # ohne_ticket: Tab übernimmt nach 30 s → keine Meldung (Karenz 90 s)
    kand, gem = {}, {}
    meld = []
    for i in range(12):
        t = T0 + i * 10
        pl = {P1: plan(P1, "open", "oeffnet") if i < 3 else plan(P1, "open", "offen", 1)}
        pl[P1]["hedge"]["status"] = "fehler" if i < 3 else "offen"
        p, les = pos_f([zeile("pc-a", t - 2, [solo(1, "917fc42f")])], t)
        neu, _ = schritt(p, les, pl, set(), kand, gem, t)
        meld += neu
    ok(not meld, "5 ohne_ticket, Tab übernimmt binnen 30 s → still")

    # 6) Echo-Waise: nur bei frischem Snapshot ohne note; ✅ nur über dieselbe Zeile
    hd = {"111": [{"ticket": 5001, "volume": 1.2, "symbol": "NAS100", "type": 0}], "222": [{"ticket": 5002, "volume": 0.5, "symbol": "NAS100", "type": 1}]}
    mp = [{"ident": 222}]
    p, les = pos_f([zeile("pc-c", T0 - 2, [], hd=hd, pos=mp)], T0)
    ok(set(p) == {("488579", 5001)} and p[("488579", 5001)]["quelle"] == "echo", f"6 Waise erkannt: {set(p)}")
    ok(("row", "pc-c", "config-a.json") in les, "6 Zeile lesbar")
    p, les = pos_f([zeile("pc-c", T0 - 2, [], hd=hd, pos=[], note="Snapshot eingefroren")], T0)
    ok(not p, "6 eingefrorener Snapshot → keine Waise")
    kand, gem = {}, {}
    meld = []
    for i in range(8):
        t = T0 + i * 10
        p, les = pos_f([zeile("pc-c", t - 2, [], hd=hd, pos=mp)], t)
        neu, _ = schritt(p, les, {}, set(), kand, gem, t)
        meld += [(t, n[1]) for n in neu]
    ok(meld == [(T0 + 60, "echo_waise")], f"6 Echo-Waise nach 60 s: {meld}")
    # anderer PC lebt weiter, pc-c ist still → kein falsches ✅ für die Echo-Waise
    erl_alle = []
    for i in range(8, 12):
        t = T0 + i * 10
        p, les = pos_f([zeile("pc-a", t - 2, [])], t)
        _, erl = schritt(p, les, {}, set(), kand, gem, t)
        erl_alle += erl
    ok(not erl_alle, "6 kein ✅ ohne Lesung der Echo-Zeile")

    # 7) Texte
    namen = {"u-ht": "Mike"}
    pcn = {"pc-7ftp5l": {"name": "Mike"}, "pc-a": {"name": "Ina"}, "pc-b": {"name": "Chris"}}
    e = {"quelle": "solo", "ticket": 248133792, "login": "488579", "symbol": "NAS100", "richtung": "sell", "lots": 3.05, "plan8": "917fc42f",
         "pcs": ["pc-a", "pc-b"]}
    ti, tx = texte("plan_zu", e, plan(P1, "review", "geschlossen", 248133792, T0), T0 + 30, pcn, namen)
    ok(ti == "Fusion-Blindgänger · Hedge laut DB zu", f"7 Titel: {ti}")
    for teil in ("Fusion 488579", "SELL 3,05 Lot NAS100", "Ticket 248133792", "PC von Mike (pc-7ftp5l)", "Tradeify", "Plan 917fc42f",
                 "„geschlossen“", "Dubai", "Prophos schließt nichts"):
        ok(teil in tx, f"7 Text enthält {teil!r}: {tx}")
    ti, tx = texte("ohne_plan", e, None, T0, pcn, namen)
    ok(ti.endswith("ohne Plan"), f"7 Titel ohne Plan: {ti}")
    ok("sichtbar auf 2 PCs" in tx and "kein Plan zu Kennung 917fc42f" in tx and "zuerst gesehen" in tx, f"7 ohne Plan: {tx}")
    ti, tx = texte("fremd", {"quelle": "fremd", "ticket": 9, "login": "488579", "symbol": "NAS100", "richtung": "buy", "lots": 10.43, "pcs": ["pc-a"]},
                   None, T0, pcn, namen)
    ok(ti.endswith("fremde Magic"), f"7 Titel fremd: {ti}")
    ti, tx2 = texte("ohne_ticket", e, plan(P1, "open", "fehler"), T0, pcn, namen)
    ok("KEINEN zweiten Hedge" in tx2 and ti.endswith("Hedge laut DB fehlt"), f"7 ohne_ticket: {tx2}")
    p_, _ = pos_f([zeile("pc-x", T0 - 2, [solo(1, "917fc42f")], login=None)], T0)
    ok(not p_, "7 Zeile ohne Fusion-Login wird übersprungen")
    ok("BUY 10,43 Lot" in tx and "Duplikum" in tx and "PC von Ina (pc-a)" in tx, f"7 fremd: {tx}")

    if f:
        print("FEHLER:\n  " + "\n  ".join(f))
        sys.exit(1)
    print("OK — selftest_fusion_blind: alle Prüfungen grün")


if __name__ == "__main__":
    main()
