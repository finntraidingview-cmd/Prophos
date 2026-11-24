#!/usr/bin/env python3
"""Selbsttest Tradeify „Zyklus im Plus“ (Finn 03.11.2026 ~04:30 Dubai; Jacob Tradeify 150k …6016: 5/5 WD, Zyklus −1.853,17 $). Rechnet app.py
tradeify_zyklus_konto mit Jacobs echten Zahlen, ohne Netz und ohne DB.

Aufruf:  python3 tools/selftest_tradeify_zyklus.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(40):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("TRADEIFY_ZYKLUS_MIN_USD", "TRADEIFY_ZYKLUS_PUFFER", "TRADEIFY_AUSGLEICH_BESTAETIGEN", "_wd_iso_ts", "WD_ZYKLUS_STAFFEL_VON", "WD_ZYKLUS_STAFFEL_STD", "WD_GOOD_DAY_MIN", "tradeify_zyklus_konto", "tradeify_zyklus_start_bal", "wd_zyklus_stand"):
    lade(n)

JACOB = {"id": "934afbbc", "name": "150k FTDFYSLX150212276016 → Winning Days", "firm": "Tradeify", "user_id": "368076fd", "max_drawdown": 4500}
FRISCH = "2026-11-02T13:38:19+00:00"   # tv_balance_at nach dem Ende des letzten Trades (02.11. 12:53)
PAY = [{"requested_at": "2026-10-22", "status": "received"}]
T = [("2026-10-22T08:23:00+00:00", 270.2, 166047.92), ("2026-10-23T13:32:00+00:00", 263.2, 161818.12), ("2026-10-26T06:35:00+00:00", -1440.8, 162081.32),
     ("2026-10-27T06:41:00+00:00", -1400, 160640.52), ("2026-10-28T12:00:00+00:00", 279.3, 158862.72), ("2026-10-29T09:44:00+00:00", 277.8, 159142.02),
     ("2026-10-30T04:19:00+00:00", 274.8, 159419.82), ("2026-11-02T12:53:00+00:00", 270.33, 159694.62)]
PL = [{"status": "completed", "started_at": s, "ended_at": s, "master_pl": pl, "tv": {"balance_start": bs}} for s, pl, bs in T]
ns["wd_plan_pnl"] = lambda p: p.get("master_pl")


def ag2_stimmig(plaene, live):
    """AG2 (24.11.2026): Fehlbetrag = Trade-Summe, Balance nur Gegenprobe (> 50 $ daneben → kein Ausgleich). Die Fixtures dieses Tests variieren nur die
    Live-Balance; damit Trades und Balance zusammenpassen wie am echten Konto, ist der P&L jedes Trades die Differenz zum nächsten balance_start, der letzte
    die Differenz zur Live-Balance. Eine Payout-Abbuchung vor dem ersten Trade des Zyklus fällt in den alten Zyklus (wie am Konto)."""
    m = [dict(p) for p in (plaene or ())]
    seq = sorted([p for p in m if str(p.get("status") or "") in ("completed", "review") and isinstance(p.get("tv"), dict)
                  and p["tv"].get("balance_start") is not None], key=lambda p: str(p.get("started_at") or ""))
    for a, b in zip(seq, seq[1:]):
        a["master_pl"] = round(float(b["tv"]["balance_start"]) - float(a["tv"]["balance_start"]), 2)
    if seq and isinstance(live, (int, float)):
        seq[-1]["master_pl"] = round(float(live) - float(seq[-1]["tv"]["balance_start"]), 2)
    return m


def ag2_wrap(fn):
    def w(konto, plaene, payouts, wd_stand, wd_ziel, vorplan, live, *a, **k):
        return fn(konto, ag2_stimmig(plaene, live), payouts, wd_stand, wd_ziel, vorplan, live, *a, **k)
    return w


ns["tzk_roh"] = ns["tradeify_zyklus_konto"]   # PO2b-Fälle unten: Balance bewusst unbrauchbar, Trades unverändert
ns["tradeify_zyklus_konto"] = ag2_wrap(ns["tradeify_zyklus_konto"])
VP = {"regeln": {"fu": {"tradeify": [270, 290]}, "staffel": [50, 60, 70, 80, 90]}}

check(ruf("tradeify_zyklus_start_bal", PL, "2026-10-22") == 161818.12, "Zyklus-Start = Balance des ersten Trades nach der Anfrage (23.10.: 161.818,12 $)")
z = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH)
check(z["nr"] == 2 and z["gewinn"] == -1853.17 and z["gesperrt"], f"Jacob: Zyklus 2, −1.853,17 $ wie Tradeify, Payout gesperrt ({z['gewinn']})")
check(z["aktiv"] and 1884 <= z["ziel"] <= 1915 and 30 <= z["puffer"] <= 60 and z["satz"] > 0 and abs(z["hedge_eur"] - z["ziel"] * z["satz"] / 1000) < 0.01,
      f"5/5 im Minus: sofort Ausgleichs-Trade, TP = 1.853,17 + 1 + Puffer 30–60 (gewürfelt) → {z['ziel']} $, Hedge im normalen €/$-Satz {z['hedge_eur']} €")
zw = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH)
check(zw["ziel"] == z["ziel"], "Puffer stabil für denselben Trade (Saat Konto + Handelstag), kein Nachziehen bei jedem Abruf")
andere = {ruf("tradeify_zyklus_konto", dict(JACOB, id=f"k{i}"), PL, PAY, 5, 5, VP, 159964.95, FRISCH)["puffer"] for i in range(12)}
check(len(andere) > 1 and all(30 <= x <= 60 for x in andere), f"Puffer je Konto/Trade verschieden gewürfelt in 30–60 ({sorted(andere)})")
z4 = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 4, 5, VP, 159964.95, FRISCH)
z3 = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 3, 5, VP, 159964.95, FRISCH)
check(z4["aktiv"] and not z3["aktiv"] and z3["gesperrt"] and z3["ziel"] is None, "4/5: der Trade zum letzten WD ist der Ausgleich; 3/5: normale WD, Payout trotzdem gesperrt")
zk = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 161830.0, FRISCH)
check(not zk["aktiv"] and not zk["gesperrt"] and zk["gewinn"] == 11.88, "Zyklus ≥ +1 $: nicht gesperrt, kein Ausgleich (Payout bereit wie heute)")
klein = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 161810.0, FRISCH)
check(klein["aktiv"] and klein["ziel"] == 280, f"kleiner Fehlbetrag: TP = max(normaler WD-TP 280, 8,12 + 1 + 20) = 280 ({klein['ziel']})")
z1 = ruf("tradeify_zyklus_konto", JACOB, PL, [], 5, 5, VP, 159964.95, FRISCH)
check(z1["nr"] == 1 and not z1["gesperrt"] and not z1["aktiv"], "1. Zyklus (noch kein Payout): Regel gilt nicht")
check(ruf("tradeify_zyklus_konto", JACOB, [], PAY, 5, 5, VP, 159964.95, FRISCH)["grund_code"] == "unbekannt", "kein Trade seit der Anfrage: Stand unbekannt (PO2b: Trade-Summe 0 $ < 1 $ → gesperrt)")
# Stopp S9 zu 7388c5f4 (a) Deckel, (b) Frische
za = ruf("tzk_roh", JACOB, PL, PAY, 5, 5, VP, 150000.0, FRISCH)
# PO2b (11.11.2026): „unbekannt“ urteilt über die Trade-Summe seit der Anfrage wie die Kachel — Jacobs Trades seit dem 22.10.: −1.475,37 $ → gesperrt, nie ein Ausgleich
check(za["grund_code"] == "unbekannt" and not za["aktiv"] and za["gesperrt"] and za["gewinn_quelle"] == "trades" and za["gewinn"] == -1475.37,
      f"(a) Fehlbetrag über Max DD (−11.818 $ bei 4.500 $) → unbekannt: kein Ausgleich, Sperre aus der Trade-Summe ({za.get('gewinn')})")
za2 = ruf("tzk_roh", JACOB, PL, PAY, 5, 5, VP, 180000.0, FRISCH)
check(za2["grund_code"] == "unbekannt" and za2["gesperrt"] and not za2["aktiv"], "(a) Plus über 3 × Max DD unplausibel → unbekannt, Urteil aus der Trade-Summe (PO2b)")
check(ruf("tradeify_zyklus_konto", dict(JACOB, max_drawdown=None), PL, PAY, 5, 5, VP, 159964.95, FRISCH)["grund_code"] == "unbekannt", "(a) ohne Max DD am Konto → unbekannt")
zb = ruf("tzk_roh", JACOB, PL, PAY, 5, 5, VP, 159964.95, "2026-11-02T10:00:00+00:00")
check(zb["grund_code"] == "unbekannt" and not zb["aktiv"] and zb["gesperrt"] and zb["fehl"] == 1475.37,
      "(b) Balance vor dem Ende des letzten Trades gelesen → unbekannt, kein Ausgleich, Sperre aus der Trade-Summe (PO2b)")
# PO2b: Trade-Summe im Plus → bei unbekannt nicht gesperrt
_plus = [dict(x, master_pl=abs(x["master_pl"])) for x in PL]
zbp = ruf("tzk_roh", JACOB, _plus, PAY, 5, 5, VP, 159964.95, "2026-11-02T10:00:00+00:00")
check(zbp["grund_code"] == "unbekannt" and not zbp["gesperrt"] and zbp["gewinn"] > 0, "PO2b: unbekannt + Trade-Summe im Plus → nicht gesperrt")
# PO2b Moritz (Befund PO2 §2): WD-Liq fest bei Größe + 100 → Puffer 11.344 $ statt Max DD 4.500 $ — Start 161.444, Balance 156.028 → −5.416 $ gesperrt
MORITZ = {"id": "mz", "name": "150k Tradeify WD", "firm": "Tradeify", "user_id": "u", "max_drawdown": 4500, "account_type": "winning_days"}
PLM = [{"status": "completed", "started_at": "2026-11-06T08:00:00+00:00", "ended_at": "2026-11-06T09:00:00+00:00", "master_pl": -5416.0, "tv": {"balance_start": 161444.0}}]
PAYM = [{"requested_at": "2026-11-05", "status": "received"}]
zm = ruf("tradeify_zyklus_konto", MORITZ, PLM, PAYM, 3, 5, VP, 156028.0, "2026-11-06T10:00:00+00:00", wd_lock=100)
check(zm["grund_code"] == "minus" and zm["gesperrt"] and zm["gewinn"] == -5416.0 and zm["fehl"] == 5416.0,
      f"PO2b Moritz: 161.444 → 156.028 bei Max DD 4.500 + WD-Lock 100 = gesperrt, Fehlbetrag 5.416 ({zm.get('grund_code')}, {zm.get('fehl')})")
zm0 = ruf("tradeify_zyklus_konto", MORITZ, PLM, PAYM, 3, 5, VP, 156028.0, "2026-11-06T10:00:00+00:00")
check(zm0["grund_code"] == "unbekannt" and zm0["gesperrt"] and zm0["gewinn"] == -5416.0, "PO2b Moritz ohne Lock (liq_regeln nicht lesbar): unbekannt, trotzdem gesperrt über die Trade-Summe")
zmf = ruf("tradeify_zyklus_konto", dict(MORITZ, account_type="funded"), PLM, PAYM, 3, 5, VP, 156028.0, "2026-11-06T10:00:00+00:00", wd_lock=100)
check(zmf["grund_code"] == "unbekannt", "PO2b: Tradeify Funded nutzt den WD-Lock nicht (Deckel bleibt Max DD)")
# Prüfer PO2b MUSS b: Fehlbetrag über Max DD → gesperrt, aber nie ein automatischer Ausgleichs-Trade (TP ohne SL), auch nicht bei 4/5 WD
zm4 = ruf("tradeify_zyklus_konto", MORITZ, PLM, PAYM, 4, 5, VP, 156028.0, "2026-11-06T10:00:00+00:00", wd_lock=100)
check(zm4["gesperrt"] and not zm4["aktiv"] and zm4.get("ausgleich_hand") and zm4["ziel"] is None, "PO2b: −5.416 $ > Max DD bei 4/5 → gesperrt, kein Auto-Ausgleich (von Hand)")
PLF = [dict(PLM[0], tv={"balance_start": 170000.0}, master_pl=-14000.0)]
zf = ruf("tradeify_zyklus_konto", MORITZ, PLF, PAYM, 5, 5, VP, 156000.0, "2026-11-06T10:00:00+00:00", wd_lock=100)
check(zf["gesperrt"] and not zf["aktiv"] and zf["ziel"] is None, "PO2b: falscher Zyklus-Start 170.000 → kein Ausgleich mit TP 14.037 $ ohne SL")
check(klein["aktiv"], "kleiner Fehlbetrag (≤ Max DD) bleibt automatischer Ausgleich")
# Prüfer PO2b MUSS a: Lucid Zyklus 1 (ohne Anfrage) + unbekannt → kein Urteil aus der (leeren) Trade-Summe
LUC = {"id": "lu", "name": "150k Lucid WD", "firm": "Lucid Trading", "user_id": "u", "max_drawdown": 4500, "account_type": "winning_days"}
zl = ruf("tradeify_zyklus_konto", LUC, PLM, [], 3, 5, VP, 151200.0, "2026-11-06T08:30:00+00:00", regel={"an": True, "usd": 1, "ab_zyklus": 1})
check(zl["grund_code"] == "unbekannt" and not zl["gesperrt"] and zl["gewinn"] is None, f"PO2b: Lucid Zyklus 1 + Balance nicht frisch → keine Sperre ({zl.get('grund')})")
# Prüfer PO2b SOLLTE: Trade im Zyklus ohne P&L → kein Urteil
PLN = PLM + [{"status": "review", "started_at": "2026-11-07T08:00:00+00:00", "ended_at": "2026-11-07T09:00:00+00:00", "master_pl": None, "tv": {}}]
zn = ruf("tradeify_zyklus_konto", MORITZ, PLN, PAYM, 3, 5, VP, 156028.0, "2026-11-06T10:00:00+00:00")
check(zn["grund_code"] == "unbekannt" and not zn["gesperrt"], "PO2b: P&L eines Trades fehlt noch → kein Urteil aus der Trade-Summe")
zmb = ruf("tradeify_zyklus_konto", MORITZ, PLM, PAYM, 3, 5, VP, 150050.0, "2026-11-06T10:00:00+00:00", wd_lock=100)
check(zmb["grund_code"] == "unbekannt", "PO2b: Verlust über den echten Puffer (unter 150.100) bleibt unplausibel → unbekannt")
check(ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, None)["grund_code"] == "unbekannt", "(b) ohne Lesezeit → unbekannt")
ohne_bs = [dict(PL[1], tv={})] + PL[2:]
check(ruf("tradeify_zyklus_start_bal", ohne_bs, "2026-10-22") is None, "erster Trade nach der Anfrage ohne balance_start → Start unbekannt (kein späterer Trade als Ersatz)")
check('trotzdem = b.get("trotzdem") is True and _planer_admin_auth()[1] is None' in app and "admAnfrageSpeichern(true)" in html, "(c) Notausgang: trotzdem nur für Admin, Knopf im Admin-Payout-Popup")
# RC4 (Finn 12.11.2026 „Nein, automatisch.“): die Bestätigungspflicht des Ausgleichs ist weg — die Prüfungen unten drehen sich entsprechend (bis RC4: „yes“ vom 03.11.)
check(z["bestaetigen"] is False and "TRADEIFY_AUSGLEICH_BESTAETIGEN = False" in app, "(d) RC4: Ausgleichs-Trade ohne Bestätigung (zyklus.bestaetigen false)")
for n2 in ("hf_ist_wd", "hf_basis"):
    lade(n2)
ns["HEDGE_ARTEN"] = ("apex", "tradeify_final")
wt = {"winning_day": True, "notes": "Winning-Day-Farmer", "master_firm": "Tradeify"}
check(not ruf("hf_ist_wd", dict(wt, aus="true"), ["apex"]) and not ruf("hf_ist_wd", wt, ["apex"]), "Liste „Zu bestätigen“: weder Tradeify-Ausgleich (RC4) noch normaler Tradeify-WD")
check("wd_ausgleich" not in ruf("hf_basis", [])["or"] and "wd_ausgleich" not in ruf("hf_basis", ["apex"])["or"], "Abfrage holt keine Ausgleichs-Trades mehr (RC4)")
check('if (r or {}).get("wd_ausgleich") is True:\n' in app and "if(ausgleich) pr.wd_ausgleich = true" in html
      and "if(ausgleichA) row.mt5_baseline = Object.assign({}, row.mt5_baseline || {}, { wd_ausgleich: true })" in html, "Marke wd_ausgleich an beiden Anlage-Wegen (Mac über Railway, Tab direkt)")
check("alt.zyArt === 'tradeify' ? { wd_ausgleich: true, wd_sl: wdSlOhneWuerfel('Ausgleich — kein Würfel') }" in html and ".update(Object.assign({}, alt.upd, { mt5_baseline: blNeu }))" in html, "Nachziehen auf den Ausgleich: erst die Marke, sonst kein großer TP")
check("if((p.mt5Baseline && p.mt5Baseline.wd_ausgleich === true) || (typeof planIstRecoverer === 'function'" in html, "PC-Tab: markierter Ausgleich (und Recoverer) wartet nie auf eine Bestätigung (RC4)")
lade("hf_zeile_fuer"); lade("hf_wd_sichtbar")
emin, ht = {"user_id": "emin-mitglied", "aus": "true", "winning_day": True, "notes": "Winning-Day-Farmer", "master_firm": "Tradeify"}, {"user_id": "ht-id", "aus": None, "winning_day": True, "notes": "Winning-Day-Farmer", "master_firm": "Tradeify"}
check(not ruf("hf_zeile_fuer", emin, None, {"emin-mitglied"}, ["apex"], {"emin-mitglied"}), "Admin: Ausgleich aus einer Gruppe mit Verwalter nicht mehr in der Liste (RC4)")
check(not ruf("hf_zeile_fuer", emin, frozenset({"emin-mitglied"}), set(), ["apex"], set()), "Verwalter: Ausgleich seiner Gruppe nicht mehr in der Liste (RC4)")
check(not ruf("hf_zeile_fuer", ht, frozenset({"ht-id"}), set(), ["apex"], set()), "Verwalter sieht keine anderen Freigaben (Hedge-Arten, Apex-WD, normale WD)")
check(not ruf("hf_zeile_fuer", dict(emin, art="tradeify_final"), frozenset({"emin-mitglied"}), set(), ["apex"], set())
      and not ruf("hf_zeile_fuer", dict(emin, winning_day=False), frozenset({"emin-mitglied"}), set(), ["apex"], set()),
      "Verwalter: Winning-Day-Ausgleiche (hf_ist_wd) — keine andere Hedge-Art, kein Nicht-WD trotz Marke (S9 zu bda93043)")
# ORBIT PRIO 2 (MO1, 05.11.2026, Master: „bei Emins Gruppe bestätigt Emin selbst“): Orbit-Prio-2-Hedge (art 'apex') der eigenen Gruppe ja, fremder nie
_op = {"user_id": "emin-mitglied", "art": "apex", "winning_day": False, "notes": "Auto-Planer", "master_firm": "Lucid Trading"}
check(ruf("hf_zeile_fuer", _op, frozenset({"emin-mitglied"}), set(), ["apex"], set()) and not ruf("hf_zeile_fuer", dict(_op, user_id="ht-id"), frozenset({"emin-mitglied"}), set(), ["apex"], set()),
      "Verwalter bestätigt Orbit Prio 2 nur seiner Gruppe (MO1)")
sqlg = open(os.path.join(W, "sql", "2026-11-03_tradeify_ausgleich_gruppen.sql"), encoding="utf-8").read()
check("coalesce(new.mt5_baseline->>'wd_ausgleich', '') = 'true' and coalesce(new.winning_day, false))) then" in sqlg and "verwalter_user_id" not in sqlg.split("TRADEIFY-AUSGLEICH (03.11.2026)")[1].split("then")[0],
      "DB-Netz: Ausgleich ohne Gruppen-Ausnahme (neue SQL-Datei)")
check("'/hedge-freigabe?ansicht=admin'" in html and "String(z.aus || '').toLowerCase() === 'true')" not in html, "Liste mit ansicht=admin (Verwalter); Ausgleich nicht mehr in „Zu bestätigen“ (RC4)")
sql = open(os.path.join(W, "sql", "2026-11-03_tradeify_ausgleich_bestaetigen.sql"), encoding="utf-8").read()
check("coalesce(new.mt5_baseline->>'wd_ausgleich', '') = 'true'" in sql, "Alt-Datei 03.11.: DB-Netz hielt den Ausgleich (Geschichte)")
sql4 = open(os.path.join(W, "sql", "2026-11-12_rc4_ausgleich_automatisch.sql"), encoding="utf-8").read()
check("and coalesce(new.mt5_baseline->>'wd_ausgleich', '') <> 'true'" in sql4, "RC4-Datei: DB-Netz hält den Ausgleich nicht mehr")
check("if(ziel && ziel.done && !wdAusgleichFaellig(k.acc.id))" in html and "if(ziel && ziel.done && !wdAusgleichFaellig(acc.id))" in html, "Ziel voll + Zyklus im Minus: Konto bleibt im Farmer (Ausgleich wird angelegt)")
check("Math.max(Number(zy.ziel), tpVor || 0)" in html, "TP-Vorgabe am Konto schlägt den Ausgleich nicht (max)")
check("document.addEventListener('click', e => {\n    const el = e.target && e.target.closest && e.target.closest('.acc-rec-chip" not in html and "window._recoveryChipKlick" in html, "kein Sammel-Klick-Handler, Klick nur am Chip")
check('if _zp and str(konto.get("account_type") or "") in _zp_typen and not trotzdem:' in app   # LZ1: Tradeify funded + WD, Lucid nur WD
      and "Payout erst ab +{_m_txt} $ — nichts angelegt" in app, "Payout-Anfrage über Railway wird bei Zyklus < Mindest-Gewinn (Standard +1 $) abgelehnt (409)")
# nachgezogen 11.11.2026 (ST1, Slave 2): cc413c54 PO2 bringt gewollt eine dritte Stelle (Railway „unbekannt“ → Urteil aus /konto-ziele) mit demselben Text;
# die beiden alten Stellen (Anfragbar-Zelle, Finanzen-Payout) werden weiter einzeln geprüft
_po_txt = "Payout erst ab +${(zyT.min_usd != null ? Number(zyT.min_usd) : 1).toLocaleString('de-DE'"
check("zyT.art === 'tradeify' && zyT.gesperrt" in html and html.count(_po_txt) == 3
      and ("sub: `Zyklus ${zyklusTxt(zyT.gewinn)} $ · " + _po_txt) in html and ("msgEl.textContent = `Zyklus ${zyklusTxt(zyT.gewinn)} $ · " + _po_txt) in html
      and ("sub: `Zyklus ${mn.zg || '—'} · " + _po_txt) in html,
      "Frontend: Anfragbar-Zelle und Finanzen-Payout zeigen „Zyklus −X $ · Payout erst ab +<Mindest-Gewinn> $“ (Standard 1 $, E4)")
check("(/tradeify/i.test(String(a.firm || '')) && !istTradeifyCfd(a.firm))" in html, "Zyklus-Stand lädt auch für Tradeify-WD-Konten (nie Tradeify CFD)")
check(html.count("window._kontoRecoveryChipHtml?.(t.konto_id") == 2 and "function kontoRecoveryChipHtml(kid, name)" in html and ">Recovery</span>" in html,
      "Chip „Recovery“ in Konto-Zeile, Planer/WD-Karte (planRecovererChipHtml) und Radar")
check("[`Fehlt bis +${(z.min_usd != null ? Number(z.min_usd) : 1)" in html and "['Nächster Trade', z.aktiv ? `Ausgleich · TP" in html, "Popup: Zyklus, Fehlbetrag bis Mindest-Gewinn, WD-Stand, nächster Trade mit TP")

# ── E4 (05.11.2026): Mindest-Gewinn je Zyklus als Parameter (wd_farmer_regeln.firmen_regeln) — Standard = Verhalten von vorher ──
lade("wd_firmen_regel")
std = ruf("wd_firmen_regel", {}, "tradeify")
check(std == {"konsistenz": {"an": False, "pct": None}, "min_netto": {"an": True, "usd": 1.0, "ab_zyklus": 2}}, f"Standard Tradeify: Mindest-Gewinn 1 $ ab Zyklus 2, keine Consistency ({std})")
z_std = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH, regel=std["min_netto"])
check({k: z_std[k] for k in ("gesperrt", "aktiv", "ziel", "fehl", "grund_code")} == {k: z[k] for k in ("gesperrt", "aktiv", "ziel", "fehl", "grund_code")},
      "Standard-Regel ausdrücklich = ohne Regel: gleicher Ausgleich, gleicher TP (Verhalten unverändert)")
z_aus = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH, regel={"an": False, "usd": 1, "ab_zyklus": 2})
check(not z_aus["gesperrt"] and not z_aus["aktiv"] and z_aus["grund_code"] == "regel_aus", "Regel aus: keine Payout-Sperre, kein Ausgleichs-Trade")
z_ab3 = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH, regel={"an": True, "usd": 1, "ab_zyklus": 3})
check(z_ab3["grund_code"] == "zyklus_1" and not z_ab3["gesperrt"] and "ab Zyklus 3" in z_ab3["grund"], "ab Zyklus 3: Zyklus 2 noch frei")
z_100 = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH, regel={"an": True, "usd": 100, "ab_zyklus": 2})
check(z_100["gesperrt"] and z_100["aktiv"] and z_100["min_usd"] == 100 and z_100["ziel"] >= 1853.17 + 100 + 30 and "ab +100 $" not in z_100["grund"],
      f"100 $ Mindest-Gewinn: Ausgleichs-TP reicht bis Fehlbetrag + 100 $ + Puffer ({z_100['ziel']} $)")
PLUS = [dict(p) for p in PL]
z_p = ruf("tradeify_zyklus_konto", JACOB, PLUS, PAY, 3, 5, VP, 161868.12, FRISCH, regel={"an": True, "usd": 100, "ab_zyklus": 2})
check(z_p["gewinn"] == 50.0 and z_p["gesperrt"] and z_p["grund_code"] == "minus" and "ab +100 $" in z_p["grund"], f"+50 $ bei 100 $ Mindest-Gewinn: gesperrt ({z_p['grund']})")
z_p1 = ruf("tradeify_zyklus_konto", JACOB, PLUS, PAY, 3, 5, VP, 161868.12, FRISCH)
check(not z_p1["gesperrt"] and z_p1["grund_code"] == "plus", "+50 $ beim Standard (1 $): frei wie bisher")
kaputt = ruf("wd_firmen_regel", {"tradeify": {"min_netto": {"an": "ja", "usd": -5, "ab_zyklus": 0}}, "apex": {"konsistenz": {"pct": 150}}}, "tradeify")
check(kaputt["min_netto"] == {"an": True, "usd": 1.0, "ab_zyklus": 2}, "Ungültiges fällt feldweise auf den Standard zurück")
check(ruf("wd_firmen_regel", {"apex": {"konsistenz": {"pct": 150}}}, "apex")["konsistenz"] == {"an": True, "pct": 50}, "Apex-Consistency 150 % ungültig → 50 %")
check(ruf("wd_firmen_regel", None, "gibtsnicht") == ruf("wd_firmen_regel", None, "sonst"), "unbekannte Firma = sonst")
# Frontend-Standard gleich dem Backend
m = re.search(r"const E4_WD_FIRMEN_STD = \{(.*?)\} \}\n", html, re.S)
check(bool(m), "Frontend: E4_WD_FIRMEN_STD vorhanden")
if m:
    import json as _j
    roh = "{" + m.group(1) + "} }"
    js = re.sub(r"(\w+):", r'"\1":', roh).replace("true", "true").replace("null", "null")
    fe = _j.loads(js)
    be = ns["WD_FIRMEN_REGELN_STD"]
    check({k: {t: {f: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for f, v in d.items()} for t, d in x.items()} for k, x in fe.items()}
          == {k: {t: {f: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for f, v in d.items()} for t, d in x.items()} for k, x in be.items()},
          "Frontend-Standard = app.py WD_FIRMEN_REGELN_STD (alle Firmen)")
# LF1 (16.11.2026): die 50k-Zeilen (lucid50/fnfutures50) zeigen die Regeln ihrer Firma — wdBasisKey(k), sonst k unverändert
check(("${e4RegelnHtml(k)}" in html or "${e4RegelnHtml(wdBasisKey(k))}" in html or "e4RegelnHtml(wdBasisKey(k))}" in html) and "firmen_regeln: neu" in html and "await wdNurGruppe()" in html.split("async function e4Speichern")[1][:200],
      "Einstellungen → Firmen: Payout-Regeln je Firma, Speichern in firmen_regeln, nur HT-weit (wdNurGruppe)")
check("_tradeify_zyklus_anhaengen(apex, plaene, pay, vorplan, _wd_firmen_regeln_lesen())" in app and "regel=mn_je.get(zyklus_plus_key(k) or \"tradeify\"), wd_lock=_lock(k)," in app,   # LZ1 (10.11.2026): Regel je Firma (Tradeify/Lucid); PO2b: WD-Lock; RC3: danach rc_regel
      "Railway liest firmen_regeln (Rückfall Standard) und gibt die Regel an tradeify_zyklus_konto")

# ── LZ1 (Finn 10.11.2026): Lucid „Zyklus im Plus“ in jedem Payout-Zyklus, auch im 1. — derselbe Weg (art 'tradeify', firma_key 'lucid') ──
print("\nLZ1 · Lucid")
lade("WD_FIRMEN_REGELN_STD"); lade("wd_firmen_regel")
for n in ("zyklus_plus_key", "tradeify_zyklus_firma", "_wd_konto_groesse"):
    try:
        lade(n)
    except Exception:
        pass
ns.setdefault("_ist_tradeify_cfd", lambda f: "cfd" in str(f or "").lower())
ML = ruf("wd_firmen_regel", {}, "lucid")["min_netto"]
check(ML == {"an": True, "usd": 1.0, "ab_zyklus": 1}, f"Standard Lucid: min_netto an, +1 $, ab Zyklus 1 ({ML})")
check(ruf("wd_firmen_regel", {}, "tradeify")["min_netto"] == {"an": True, "usd": 1.0, "ab_zyklus": 2}, "Tradeify unverändert: ab Zyklus 2")
check(ruf("tradeify_zyklus_firma", {"firm": "Lucid Trading"}) and ruf("zyklus_plus_key", {"firm": "Lucid Trading"}) == "lucid"
      and ruf("zyklus_plus_key", {"firm": "Tradeify"}) == "tradeify" and not ruf("tradeify_zyklus_firma", {"firm": "Tradeify CFD"})
      and not ruf("tradeify_zyklus_firma", {"firm": "Apex Trader"}), "Firmen: Tradeify (ohne CFD) und Lucid, sonst keine")
# Finns Konto Lucid 150k LFF…0001 (952df577): Payouts 28.10./04.11. → Zyklus 3 ab 05.11., Start 158.987,50, Live 157.096,50 (10.11. 07:37 Dubai) = −1.891 $
FINN = {"id": "952df577", "name": "150k LFF15084019460001 → Winning Days", "firm": "Lucid Trading", "user_id": "48f272b4", "max_drawdown": 4500}
PAYL = [{"requested_at": "2026-10-28", "status": "received"}, {"requested_at": "2026-11-04", "status": "received"}]
TL = [("2026-11-05T01:25:00+00:00", 264, 158987.5), ("2026-11-06T00:43:00+00:00", 281, 159251.5), ("2026-11-09T02:52:00+00:00", -2712, 159532.5),
      ("2026-11-10T01:49:00+00:00", 276, 156820.5)]
PLL = [{"status": "completed", "started_at": s_, "ended_at": s_, "master_pl": pl, "tv": {"balance_start": bs}} for s_, pl, bs in TL]
FR = "2026-11-10T03:37:36+00:00"
zl = ruf("tradeify_zyklus_konto", FINN, PLL, PAYL, 3, 5, VP, 157096.5, FR, regel=ML)
check(zl["art"] == "tradeify" and zl["firma_key"] == "lucid" and zl["nr"] == 3 and zl["gewinn"] == -1891.0 and zl["gesperrt"] and not zl["aktiv"]
      and zl["grund_code"] == "minus", f"Finn Lucid: Zyklus 3, −1.891 $, Payout gesperrt, 3/5 → noch normaler WD ({zl['grund']})")
zl4 = ruf("tradeify_zyklus_konto", FINN, PLL, PAYL, 4, 5, VP, 157096.5, FR, regel=ML)
check(zl4["aktiv"] and 1922 <= zl4["ziel"] <= 1952 and zl4["bestaetigen"] is False and zl4["hedge_eur"] > 0,
      f"4/5 im Minus: Ausgleichs-Trade TP = 1.891 + 1 + 30–60 → {zl4['ziel']} $, ohne Bestätigung (RC4), Hedge {zl4['hedge_eur']} €")
# 1. Zyklus (noch keine Anfrage): Start = Start-Balance bzw. Kontogröße
NEU = dict(FINN, id="lneu", name="150k LFF999 → Winning Days")
z1p = ruf("tradeify_zyklus_konto", NEU, [], [], 2, 5, VP, 151200.0, None, regel=ML)
z1m = ruf("tradeify_zyklus_konto", NEU, [], [], 4, 5, VP, 149500.0, None, regel=ML)
check(z1p["nr"] == 1 and z1p["start_bal"] == 150000.0 and z1p["gewinn"] == 1200.0 and not z1p["gesperrt"] and z1p["grund_code"] == "plus",
      f"Lucid Zyklus 1 im Plus: Start = Kontogröße 150.000, +1.200 $ ({z1p['grund']})")
check(z1m["nr"] == 1 and z1m["gesperrt"] and z1m["aktiv"] and z1m["fehl"] == 500.0, f"Lucid Zyklus 1 im Minus (−500 $, 4/5): gesperrt, Ausgleich ({z1m['grund']})")
zt1 = ruf("tradeify_zyklus_konto", dict(JACOB, id="tneu"), [], [], 4, 5, VP, 149500.0, None)
check(zt1["grund_code"] == "zyklus_1" and not zt1["gesperrt"] and zt1["firma_key"] == "tradeify", "Tradeify Zyklus 1: unverändert ohne Regel")
check(ruf("tradeify_zyklus_konto", FINN, PLL, PAYL, 3, 5, VP, 157096.5, FR, regel={"an": False, "usd": None, "ab_zyklus": 1})["grund_code"] == "regel_aus",
      "Lucid-Regel in den Einstellungen aus → nie gesperrt")
check('"or": "(firm.ilike.*apex*,firm.ilike.*tradeify*,firm.ilike.*lucid*)"' in app and "|| /lucid/i.test(String(a.firm || ''))" in html,
      "/wd-zyklus und der eigene Tab laden Lucid-WD-Konten mit")
# Nachzug Gegenprüfung: Größe aus dem Namen vor starting_balance; großes Plus im 1. Zyklus nicht „unplausibel“; Frische im 1. Zyklus; Lucid Funded ohne Payout-Sperre
z1s = ruf("tradeify_zyklus_konto", dict(NEU, starting_balance=100000), [], [], 2, 5, VP, 151200.0, None, regel=ML)
check(z1s["start_bal"] == 150000.0, f"Zyklus 1: Größe aus dem Namen (150k) vor einer abweichenden starting_balance ({z1s['start_bal']})")
z1g = ruf("tradeify_zyklus_konto", NEU, [], [], 2, 5, VP, 163609.5, None, regel=ML)
check(z1g["grund_code"] == "plus" and z1g["gewinn"] == 13609.5, f"Zyklus 1 mit Big-Trade-Plus +13.609,50 $ (> 3 × DD): echt, nicht unplausibel ({z1g['grund']})")
z1v = ruf("tradeify_zyklus_konto", NEU, [], [], 2, 5, VP, 140000.0, None, regel=ML)
check(z1v["grund_code"] == "unbekannt", "Zyklus 1 Verlust über Max DD: weiter unplausibel/unbekannt (keine Sperre, kein Riesen-TP)")
PL1 = [{"status": "completed", "started_at": "2026-11-09T02:00:00+00:00", "ended_at": "2026-11-09T03:00:00+00:00", "master_pl": -500, "tv": {"balance_start": 150000}}]
z1f = ruf("tradeify_zyklus_konto", NEU, PL1, [], 4, 5, VP, 149500.0, "2026-11-09T02:30:00+00:00", regel=ML)
check(z1f["grund_code"] == "unbekannt" and not z1f["aktiv"], "Zyklus 1: Balance vor dem Ende des letzten Trades gelesen → unbekannt, kein Ausgleich")
zt_vorher = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH)
check({k: v for k, v in zt_vorher.items() if k != "firma_key"} == {k: v for k, v in z.items() if k != "firma_key"} and zt_vorher["firma_key"] == "tradeify",
      "Tradeify: Ergebnis bis auf das neue Feld firma_key gleich dem Lauf oben (Jacob)")
check('_zp_typen = ("winning_days",) if _zp == "lucid" else ("funded", "winning_days")' in app,
      "Payout-Anfrage: Lucid nur bei Winning Days gesperrt, Tradeify wie bisher Funded + WD")
check("E4_WIRKT = { tradeify: { min_netto: true }, lucid: { min_netto: true } }" in html and "z.firma_key === 'lucid' ? 'Lucid' : 'Tradeify'" in html,
      "Frontend: Lucid-Regel wirkt, Texte nennen Lucid")

print("— AG2 (24.11.2026): Fehlbetrag = Trade-Summe, Balance nur Gegenprobe —")
for n in ("AG2_GEGENPROBE_USD",):
    lade(n)
# Mike Tradeify 150k …5297 (echte Zahlen): Antrag 12.11., Tradeify buchte 4.500 $ erst NACH dem ersten Trade des Zyklus ab (17.11. → 18.11.)
MIKE = {"id": "43f9cd07", "name": "150k FTDFYSLX150482435297 → Funded", "firm": "Tradeify", "user_id": "32b854d1", "max_drawdown": 4500}
PAYK = [{"requested_at": "2026-11-12", "status": "received"}]
TK = [("2026-11-11T09:00:00+00:00", 280.86, 161715.74), ("2026-11-17T00:48:00+00:00", 276.74, 161996.6), ("2026-11-18T05:15:00+00:00", 269.36, 157773.34),
      ("2026-11-19T10:26:00+00:00", 276.24, 158042.7), ("2026-11-23T06:52:00+00:00", 273.36, 158318.94)]
PLK = [{"status": "completed", "started_at": s, "ended_at": s, "master_pl": pl, "tv": {"balance_start": bs}} for s, pl, bs in TK]
zk = ruf("tzk_roh", MIKE, PLK, PAYK, 4, 5, VP, 158592.3, "2026-11-23T08:00:00+00:00")
check(zk["grund_code"] == "unbekannt" and not zk["aktiv"] and not zk.get("ziel") and zk["gesperrt"] and zk["gewinn"] == -3404.3 and zk["gewinn_quelle"] == "min"
      and zk["gegenprobe_abw"] == -4500.0 and zk["gewinn_balance"] == -3404.3 and zk["profit_trades"] == 1095.7 and "Payout gesperrt" in zk["grund"],
      f"Mike …5297: Balance −3.404 ≠ Trades +1.096 → kein Ausgleichs-Trade (vorher TP 3.462 $); Payout vorsichtig gesperrt (eine Quelle im Minus), ⚪ ({zk.get('grund')})")
# Mike heute nach dem Ausgleich (Balance 162.026,56): beide Quellen im Plus → nicht gesperrt, trotz Abweichung kein Ausgleich
zk2 = ruf("tzk_roh", MIKE, PLK + [{"status": "completed", "started_at": "2026-11-24T07:20:00+00:00", "ended_at": "2026-11-24T07:40:00+00:00", "master_pl": 3434.26,
                                    "tv": {"balance_start": 158592.3}}], PAYK, 5, 5, VP, 162026.56, "2026-11-24T09:00:00+00:00")
check(not zk2["gesperrt"] and not zk2["aktiv"] and zk2["gewinn"] == 29.96 and zk2["gegenprobe_abw"] == -4500.0, "Mike …5297 heute: +29,96 / +4.529,96 → nicht gesperrt, kein Ausgleich")
# Finn + Pascal Lucid …0001 (echte Zahlen, BS1): TV las −180,50 $, die Balance fiel 2.768 $ → Trade-Summe +907,50, Balance −1.680 → gesperrt, kein Ausgleich
LU1 = {"id": "lu0001", "name": "150k LFE150100019460001 → Winning Days", "firm": "Lucid Trading", "user_id": "fp", "max_drawdown": 4500}
TL = [("2026-11-17T02:10:00+00:00", 265.0, 156032.0), ("2026-11-18T06:10:00+00:00", 269.5, 156297.0), ("2026-11-20T03:42:00+00:00", 277.5, 156566.5),
      ("2026-11-23T06:37:00+00:00", -180.5, 156844.0), ("2026-11-24T08:56:00+00:00", 276.0, 154076.0)]
PLL = [{"status": "completed", "started_at": s, "ended_at": s, "master_pl": pl, "tv": {"balance_start": bs}} for s, pl, bs in TL]
zl = ruf("tzk_roh", LU1, PLL, PAYK, 4, 5, VP, 154352.0, "2026-11-24T10:00:00+00:00")
check(zl["gesperrt"] and not zl["aktiv"] and zl["gewinn"] == -1680.0 and zl["profit_trades"] == 907.5,
      f"Lucid …0001: falscher Trade-P&L (−180,50 statt −2.768) gibt den Payout NICHT frei (Balance −1.680 → gesperrt), kein Ausgleich ({zl.get('grund')})")
# Marco Tradeify 150k …2833 (echte Zahlen): Abbuchung VOR dem ersten Trade des Zyklus → Balance = Trades, Ausgleich wie bisher
MARCO = {"id": "10739e92", "name": "150k FTDFYSLX150306272833 → Winning Days", "firm": "Tradeify", "user_id": "1c96cf0f", "max_drawdown": 4500}
PAYO = [{"requested_at": "2026-11-10", "status": "received"}]
TO = [("2026-11-10T07:00:00+00:00", 267.36, 156882.78), ("2026-11-11T09:21:00+00:00", 271.24, 157150.14), ("2026-11-12T07:06:00+00:00", 272.24, 157421.38),
      ("2026-11-16T03:02:00+00:00", -2987.76, 157693.62), ("2026-11-17T05:44:00+00:00", -786.76, 154705.86), ("2026-11-18T07:25:00+00:00", 268.24, 153919.1)]
PLO2 = [{"status": "completed", "started_at": s, "ended_at": s, "master_pl": pl, "tv": {"balance_start": bs}} for s, pl, bs in TO]
zo = ruf("tzk_roh", MARCO, PLO2, PAYO, 4, 5, VP, 154187.34, "2026-11-18T09:00:00+00:00")
check(zo["grund_code"] == "ausgleich" and zo["aktiv"] and zo["fehl"] == 2962.8 and 2993 <= zo["ziel"] <= 3024 and "gegenprobe_abw" not in zo,
      f"Marco …2833: Balance = Trades (−2.962,80) → Ausgleich wie bisher, TP {zo.get('ziel')} $ (war 3.008)")
# Grenze: P&L 50 $ daneben → noch Ausgleich (Fehlbetrag aus den Trades), 50,01 $ → kein Ausgleich
_d = lambda delta: [dict(x, master_pl=round(x["master_pl"] + delta, 2)) if x["started_at"].startswith("2026-11-17") else x for x in PLO2]   # noqa: E731
z50 = ruf("tzk_roh", MARCO, _d(-50.0), PAYO, 4, 5, VP, 154187.34, "2026-11-18T09:00:00+00:00")
z51 = ruf("tzk_roh", MARCO, _d(-50.01), PAYO, 4, 5, VP, 154187.34, "2026-11-18T09:00:00+00:00")
check(z50["aktiv"] and z50["fehl"] == 3012.8 and z50["gewinn"] == -3012.8, f"Abweichung genau 50 $: Ausgleich, Fehlbetrag aus der Trade-Summe ({z50.get('fehl')})")
check(not z51["aktiv"] and z51["grund_code"] == "unbekannt" and z51["gesperrt"] and z51["gegenprobe_abw"] == 50.01,
      "Abweichung 50,01 $: kein Ausgleich, Sperre aus der Trade-Summe (im Minus)")
# Trade ohne P&L im Zyklus (completed, Altlast): keine Gegenprobe → kein Ausgleich, Sperre wie bisher aus der Balance
zn = ruf("tzk_roh", MARCO, [dict(x, master_pl=None) if x["started_at"].startswith("2026-11-12") else x for x in PLO2], PAYO, 4, 5, VP, 154187.34,
         "2026-11-18T09:00:00+00:00")
check(not zn["aktiv"] and zn["grund_code"] == "unbekannt" and zn["gesperrt"] and zn["gewinn"] == -2962.8 and zn["gewinn_quelle"] == "balance"
      and zn.get("gegenprobe_fehlt") is True,
      "completed ohne P&L im Zyklus: kein Ausgleich, Payout-Sperre aus der Balance (nie lockerer als vorher), Marke für ⚪")
# Prüfer AG2 (2): review ohne P&L bleibt bei RC5 („Ausgleich wartet“), wie vor AG2
zr = ruf("tzk_roh", MARCO, [dict(x, status="review", master_pl=None) if x["started_at"].startswith("2026-11-18") else x for x in PLO2], PAYO, 4, 5, VP,
         154187.34, "2026-11-18T09:00:00+00:00")
check(zr["grund_code"] == "laeuft" and not zr["aktiv"] and zr["gesperrt"], f"review ohne P&L: RC5 „Ausgleich wartet“ wie vorher ({zr.get('grund')})")
# Prüfer AG2 (1): stimmig, aber Trades 50 $ BESSER als die Balance → Fehlbetrag/Sperre aus der Balance (die schlechtere Quelle)
zp = ruf("tzk_roh", MARCO, _d(+50.0), PAYO, 4, 5, VP, 154187.34, "2026-11-18T09:00:00+00:00")
check(zp["aktiv"] and zp["fehl"] == 2962.8, f"Trades +50 $ über der Balance: Fehlbetrag aus der Balance 2.962,80 (nie zu kurz) ({zp.get('fehl')})")
_p30 = [dict(x, master_pl=round(x["master_pl"] + 2992.8, 2)) if x["started_at"].startswith("2026-11-11") else x for x in PLO2]   # Trade-Summe +30,00
zp2 = ruf("tzk_roh", MARCO, _p30, PAYO, 2, 5, VP, 157150.14 - 20.0, "2026-11-18T09:00:00+00:00")
check(zp2["gesperrt"] and zp2["gewinn"] == -20.0 and "gegenprobe_abw" not in zp2,
      f"Balance −20 $, Trades +30 $ (stimmig, 50 $ daneben): Payout bleibt gesperrt — nie lockerer als vorher ({zp2.get('gewinn')})")
# Zyklus 1 ohne Anfrage (Lucid): keine Gegenprobe, Verhalten unverändert
check("if st[\"start\"] and not _of:\n        _ag2_im" in app, "Gegenprobe nur mit Payout-Anfrage (Zyklus 1 unverändert) und ohne RC5-Wartegrund")
# ⚪-Meldung: nur wenn die Balance allein einen Ausgleich ausgelöst hätte, je Konto × Tag, nur HT-IDs
check("_ag2_melden(k, stand, a.get(\"goal_target\") or 5)" in app and "key = f\"ag2_gegenprobe|{k.get('id')}|{_berlin_heute()}\"" in app
      and "alarm_senden(3, \"ag2_gegenprobe\"" in app and "_alarm_fremd_verwaltet(owner)" in app,
      "⚪ an die Master-IDs je Konto × Berlin-Tag (alarm_senden prio 3, gedrosselt), Emin-Gruppe ausgenommen")
_gesendet, _frei = [], set()
ns.update({"_ap_namen": lambda: ({"32b854d1": "Mike"}, set()), "_alarm_fremd_verwaltet": lambda u: u == "emin0001", "_berlin_heute": lambda: "2026-11-24",
           "_tm_melde_frei": lambda key: (key not in _frei) and not _frei.add(key), "alarm_senden": lambda *a, **k: _gesendet.append((a, k))})
lade("_ag2_melden")
km = dict(MIKE, zyklus=zk)
ruf("_ag2_melden", km, 4, 5)
ruf("_ag2_melden", km, 4, 5)
check(len(_gesendet) == 1 and _gesendet[0][0][0] == 3 and "Mike" in _gesendet[0][0][3] and "−4.500" not in _gesendet[0][0][3] and "-4.500 $" in _gesendet[0][0][3],
      f"Mike …5297 bei WD 4/5: genau eine ⚪-Meldung je Tag ({_gesendet[0][0][3] if _gesendet else '—'})")
_gesendet.clear()
ruf("_ag2_melden", dict(MIKE, id="x2", zyklus=zk), 2, 5)                       # WD 2/5: Balance hätte noch keinen Ausgleich ausgelöst
ruf("_ag2_melden", dict(MIKE, id="x3", user_id="emin0001", zyklus=zk), 4, 5)   # Emin-Gruppe
ruf("_ag2_melden", dict(MIKE, id="x4", zyklus=zo), 4, 5)                       # keine Abweichung
ruf("_ag2_melden", dict(MIKE, id="x5", zyklus=zk2), 5, 5)                      # beide Quellen im Plus: nicht gesperrt, kein Ausgleich fällig
ruf("_ag2_melden", dict(MIKE, id="x7", zyklus=zr), 4, 5)                       # review ohne P&L (RC5 „wartet“): keine AG2-Meldung
check(not _gesendet, "keine Meldung bei WD < Ziel − 1, Emin-Gruppe, ohne Abweichung, ohne Sperre oder bei RC5 „wartet“")
ruf("_ag2_melden", dict(MIKE, id="x8", zyklus=zn), 4, 5)                       # completed ohne P&L: ⚪ mit eigenem Text
check(len(_gesendet) == 1 and "keinen P&L" in _gesendet[0][0][3], f"completed ohne P&L: ⚪ „keine Gegenprobe“ ({_gesendet[0][0][3] if _gesendet else '—'})")
_gesendet.clear()
ns["alarm_senden"] = lambda *a, **k: 1 / 0
ruf("_ag2_melden", dict(MIKE, id="x6", zyklus=zk), 4, 5)                       # Fehler beim Senden: wirft nie
check(not _gesendet, "keine Meldung bei WD < Ziel − 1, Emin-Gruppe, ohne Abweichung oder ohne Sperre; Sende-Fehler wirft nie")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
