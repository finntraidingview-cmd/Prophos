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
check(ruf("tradeify_zyklus_konto", JACOB, [], PAY, 5, 5, VP, 159964.95, FRISCH)["grund_code"] == "unbekannt", "kein Trade seit der Anfrage: Stand unbekannt, keine Sperre")
# Stopp S9 zu 7388c5f4 (a) Deckel, (b) Frische
za = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 150000.0, FRISCH)
check(za["grund_code"] == "unbekannt" and not za["aktiv"] and not za["gesperrt"], "(a) Fehlbetrag über Max DD (−11.818 $ bei 4.500 $) → unbekannt: kein Ausgleich, keine Sperre")
za2 = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 180000.0, FRISCH)
check(za2["grund_code"] == "unbekannt" and not za2["gesperrt"], "(a) Plus über 3 × Max DD unplausibel → unbekannt")
check(ruf("tradeify_zyklus_konto", dict(JACOB, max_drawdown=None), PL, PAY, 5, 5, VP, 159964.95, FRISCH)["grund_code"] == "unbekannt", "(a) ohne Max DD am Konto → unbekannt")
zb = ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, "2026-11-02T10:00:00+00:00")
check(zb["grund_code"] == "unbekannt" and not zb["aktiv"] and not zb["gesperrt"], "(b) Balance vor dem Ende des letzten Trades gelesen → unbekannt, keine Sperre")
check(ruf("tradeify_zyklus_konto", JACOB, PL, PAY, 5, 5, VP, 159964.95, None)["grund_code"] == "unbekannt", "(b) ohne Lesezeit → unbekannt")
ohne_bs = [dict(PL[1], tv={})] + PL[2:]
check(ruf("tradeify_zyklus_start_bal", ohne_bs, "2026-10-22") is None, "erster Trade nach der Anfrage ohne balance_start → Start unbekannt (kein späterer Trade als Ersatz)")
check('trotzdem = b.get("trotzdem") is True and _planer_admin_auth()[1] is None' in app and "admAnfrageSpeichern(true)" in html, "(c) Notausgang: trotzdem nur für Admin, Knopf im Admin-Payout-Popup")
check(z["bestaetigen"] is True and "TRADEIFY_AUSGLEICH_BESTAETIGEN = True" in app, "(d) Finn „yes“: Ausgleichs-Trade einzeln bestätigen (zyklus.bestaetigen)")
for n2 in ("hf_ist_wd", "hf_basis"):
    lade(n2)
ns["HEDGE_ARTEN"] = ("apex", "tradeify_final")
wt = {"winning_day": True, "notes": "Winning-Day-Farmer", "master_firm": "Tradeify"}
check(ruf("hf_ist_wd", dict(wt, aus="true"), ["apex"]) and not ruf("hf_ist_wd", wt, ["apex"]), "Liste „Zu bestätigen“: Tradeify-Ausgleich ja, normaler Tradeify-WD nie")
check("mt5_baseline->>wd_ausgleich.eq.true" in ruf("hf_basis", [])["or"] and "mt5_baseline->>wd_ausgleich.eq.true" in ruf("hf_basis", ["apex"])["or"], "Abfrage holt markierte Ausgleichs-Trades (mit und ohne Apex-Liste)")
check('if (r or {}).get("wd_ausgleich") is True and TRADEIFY_AUSGLEICH_BESTAETIGEN:' in app and "if(ausgleich) pr.wd_ausgleich = true" in html
      and "if(ausgleichA) row.mt5_baseline = Object.assign({}, row.mt5_baseline || {}, { wd_ausgleich: true })" in html, "Marke wd_ausgleich an beiden Anlage-Wegen (Mac über Railway, Tab direkt)")
check("altFrei = !!(await baselinePatch(plan.id, { wd_ausgleich: true }, 'planned'))" in html, "Nachziehen auf den Ausgleich: erst die Marke, sonst kein großer TP")
check("if(p.mt5Baseline && p.mt5Baseline.wd_ausgleich === true) return true" in html, "PC-Tab startet einen markierten Ausgleich erst nach der Bestätigung — auch in Gruppen (Finn: „auch bestätigen“)")
lade("hf_zeile_fuer"); lade("hf_wd_sichtbar")
emin, ht = {"user_id": "emin-mitglied", "aus": "true"}, {"user_id": "ht-id", "aus": None, "winning_day": True, "notes": "Winning-Day-Farmer", "master_firm": "Tradeify"}
check(ruf("hf_zeile_fuer", emin, None, {"emin-mitglied"}, ["apex"], {"emin-mitglied"}), "Admin sieht den Ausgleich auch aus einer Gruppe mit Verwalter")
check(ruf("hf_zeile_fuer", emin, frozenset({"emin-mitglied"}), set(), ["apex"], set()) and not ruf("hf_zeile_fuer", dict(emin, user_id="fremd"), frozenset({"emin-mitglied"}), set(), ["apex"], set()),
      "Verwalter sieht nur die Ausgleichs-Trades seiner Gruppe")
check(not ruf("hf_zeile_fuer", ht, frozenset({"ht-id"}), set(), ["apex"], set()), "Verwalter sieht keine anderen Freigaben (Hedge-Arten, Apex-WD, normale WD)")
sqlg = open(os.path.join(W, "sql", "2026-11-03_tradeify_ausgleich_gruppen.sql"), encoding="utf-8").read()
check("coalesce(new.mt5_baseline->>'wd_ausgleich', '') = 'true' and coalesce(new.winning_day, false))) then" in sqlg and "verwalter_user_id" not in sqlg.split("TRADEIFY-AUSGLEICH (03.11.2026)")[1].split("then")[0],
      "DB-Netz: Ausgleich ohne Gruppen-Ausnahme (neue SQL-Datei)")
check("'/hedge-freigabe?ansicht=admin'" in html and "String(z.aus || '').toLowerCase() === 'true')" in html, "Liste mit ansicht=admin (Verwalter), Ausgleich in „Zu bestätigen“ immer sichtbar")
sql = open(os.path.join(W, "sql", "2026-11-03_tradeify_ausgleich_bestaetigen.sql"), encoding="utf-8").read()
check("coalesce(new.mt5_baseline->>'wd_ausgleich', '') = 'true'" in sql, "DB-Netz hält einen unbestätigten Ausgleichs-Start (SQL-Datei)")
check("if(ziel && ziel.done && !wdAusgleichFaellig(k.acc.id))" in html and "if(ziel && ziel.done && !wdAusgleichFaellig(acc.id))" in html, "Ziel voll + Zyklus im Minus: Konto bleibt im Farmer (Ausgleich wird angelegt)")
check("Math.max(Number(zy.ziel), tpVor || 0)" in html, "TP-Vorgabe am Konto schlägt den Ausgleich nicht (max)")
check("document.addEventListener('click', e => {\n    const el = e.target && e.target.closest && e.target.closest('.acc-rec-chip" not in html and "window._recoveryChipKlick" in html, "kein Sammel-Klick-Handler, Klick nur am Chip")
check('if tradeify_zyklus_firma(konto) and str(konto.get("account_type") or "") in ("funded", "winning_days") and not trotzdem:' in app
      and "Payout erst ab +1 $ — nichts angelegt" in app, "Payout-Anfrage über Railway wird bei Zyklus < +1 $ abgelehnt (409)")
check("zyT.art === 'tradeify' && zyT.gesperrt" in html and "Payout erst ab +1 $" in html, "Frontend: Anfragbar-Zelle, Finanzen-Payout und WD-Karte zeigen „Zyklus −X $ · Payout erst ab +1 $“")
check("(/tradeify/i.test(String(a.firm || '')) && !istTradeifyCfd(a.firm))" in html, "Zyklus-Stand lädt auch für Tradeify-WD-Konten (nie Tradeify CFD)")
check(html.count("window._kontoRecoveryChipHtml?.(t.konto_id") == 2 and "function kontoRecoveryChipHtml(kid, name)" in html and ">Recovery</span>" in html,
      "Chip „Recovery“ in Konto-Zeile, Planer/WD-Karte (planRecovererChipHtml) und Radar")
check("['Fehlt bis +1 $'" in html and "['Nächster Trade', z.aktiv ? `Ausgleich · TP" in html, "Popup: Zyklus, Fehlbetrag bis +1 $, WD-Stand, nächster Trade mit TP")
print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
