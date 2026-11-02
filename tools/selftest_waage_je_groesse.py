#!/usr/bin/env python3
"""Selbsttest WAAGE-DECKEL JE KONTOGRÖSSE (Finn 02.11.2026 „ok ja bau“): ein Futures-Start nur, wenn danach in SEINER Kontogröße |Long − Short| ≤ 2.
Finns Prüffälle: 150k 5 : 3 → Long gesperrt, Short frei; 100k 2 : 0 → Long gesperrt; 50k 3 : 0 → Long gesperrt. Dazu: andere Größen gleichen nicht aus,
„unbekannt“ startet nie, Größe aus Name/account_size wie die DB, Startweg Railway (ap_waage_start_lage → PC-Tab), DB-Datei (Lage + Trigger + Spur).
Ohne Netz. Aufruf: python3 tools/selftest_waage_je_groesse.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, HIER)
import selftest_zwei_waagen as zw  # noqa: E402

SQL = open(os.path.join(WURZEL, "sql", "2026-11-02_waage_deckel_je_groesse.sql"), encoding="utf-8").read()
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


ns = zw.lade()
G, D, W, S = ns["ap_waage_groesse"], ns["ap_waage_deckel"], ns["ap_klassen_waage"], ns["ap_waage_start_lage"]

# Größe wie die DB (Werte aus dem Lese-Test gegen die Live-Konten 02.11.2026)
for name, size, soll in (("150k TDFYSL150712671832 → Challenge", None, "150k"), ("150KTC-SKU-V2-679005-56869878", None, "150k"),
                         ("Apex APEX6416990000001", None, "unbekannt"), ("Apex APEX6416990000001", 100000, "100k"), ("50K FTMO xyz", None, "50k"),
                         ("1500k", None, "unbekannt"), ("300k Tradeify", None, "300k"), ("Tradeify 150k", "150000.00", "150k"), ("", 0, "unbekannt")):
    check(G(name, size) == soll, f"Größe „{name}“/{size} → {soll} ({G(name, size)})")


def w(**je):
    return {"n_long": sum(v[0] for v in je.values()), "n_short": sum(v[1] for v in je.values()),
            "je_groesse": {k.replace("g", "") + "k": {"n_long": v[0], "n_short": v[1]} for k, v in je.items()}}


# Finns Prüffälle — Lage NACH dem Start (wie ap_waage_start_lage sie übergibt): 150k 5 : 3 + Long = 6 : 3
check(D("futures", w(g150=(6, 3)), "buy", 2, "150k")[0], "150k 5 : 3 → Long gesperrt (6 : 3)")
check(not D("futures", w(g150=(5, 4)), "sell", 2, "150k")[0], "150k 5 : 3 → Short frei (5 : 4)")
check(D("futures", w(g100=(3, 0)), "buy", 2, "100k")[0], "100k 2 : 0 → Long gesperrt (3 : 0)")
check(D("futures", w(g50=(4, 0)), "buy", 2, "50k")[0], "50k 3 : 0 → Long gesperrt (4 : 0)")
check(not D("futures", w(g50=(1, 0), g150=(0, 6)), "buy", 2, "50k")[0], "50k-Long bei 150k 0 : 6 frei — der Deckel der anderen Größe zählt nicht")
check(D("futures", w(g50=(0, 3), g150=(3, 0)), "sell", 2, "50k")[0], "50k 0 : 2 + Short gesperrt, obwohl 150k 3 Longs hat (kein Ausgleich über Größen)")
s, g = D("futures", w(g150=(6, 3)), "buy", 2, "150k")
check("150k" in g and "6 Long : 3 Short" in g, f"Grund nennt Größe und Lage ({g})")
check(D("futures", w(), "buy", 2, "unbekannt")[0] and "unbekannt" in D("futures", w(), "buy", 2, "unbekannt")[1], "Kontogröße unbekannt → nie frei")
check(not D("cfd", w(g150=(9, 0)), "buy", 2, "150k")[0], "CFD hat keinen Deckel")
check(D("futures", {"n_long": 4, "n_short": 1}, "buy", 2, None)[0] and not D("futures", {"n_long": 3, "n_short": 1}, "buy", 2, None)[0],
      "ohne Größe (Zeile ohne Feld) wie vor dem 02.11. über die Klasse")

# Startweg Railway → PC-Tab: Stand mit Größen, Plan p1 ist ein 50k-Long
TF = ("Tradeify", "tradeify", "tvv2")
lauf = lambda pid, r, gk: dict(zw.lauf(pid, "u" + pid, *TF, r, 200), groesse_key=gk)   # noqa: E731
st = {"jetzt_min": 600.0, "offen": [lauf("a", "sell", "150k"), lauf("b", "sell", "150k"), lauf("c", "sell", "150k"), lauf("d", "buy", "50k"), lauf("e", "buy", "50k")],
      "geplant": [dict(zw.plan("p1", "u9", *TF, "buy", 200, 601.0), groesse_key="50k")], "id_fest": {}, "starts_heute": []}
L = S(st, "p1", "buy")
check(L["nachher"]["deckel_sperrt"] is True and "50k" in (L["nachher"]["deckel_grund"] or ""), f"Railway: 50k 2 : 0 + Long gesperrt, obwohl die Klasse 3 : 3 steht ({L['nachher']['deckel_grund']})")
check(L["gegen"]["deckel_sperrt"] is False, "Railway: derselbe Plan als Short (50k 2 : 1) frei")
wk = W(st)["futures"]
check(wk["je_groesse"] == {"150k": {"n_long": 0, "n_short": 3}, "50k": {"n_long": 3, "n_short": 0}}, f"Waage zählt je Größe (der geplante 50k-Long in ≤ 2 min zählt mit) ({wk['je_groesse']})")
st2 = dict(st, geplant=[dict(zw.plan("p1", "u9", *TF, "sell", 200, 601.0), groesse_key="150k")])
check(S(st2, "p1", "sell")["nachher"]["deckel_sperrt"] is True and S(st2, "p1", "buy")["nachher"]["deckel_sperrt"] is False,
      "150k 0 : 3: Short gesperrt (0 : 4), Long frei")
APP = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check('"groesse_key": ap_waage_groesse((a or {}).get("name"), (a or {}).get("account_size"))' in APP, "Stand-Zeile trägt die Größe aus dem Konto (wie die DB)")

# DB-Datei
check("(^|[^0-9])(\\d{2,3})\\s*k(\\M|tc)" in SQL and "account_size" in SQL and "starting_balance" not in SQL.split("create or replace function public.prophos_waage_groesse")[1].split("$$;")[0],
      "DB-Größe: Name zuerst (auch …KTC), dann account_size, nie starting_balance")
lage = SQL.split("create or replace function public.prophos_waage_deckel_lage")[1].split("$function$;")[0]
check("public.prophos_waage_groesse(a.name, a.account_size) = gr" in lage, "DB-Lage zählt nur Pläne derselben Größe")
check("'sperrt', gr = 'unbekannt' or seite - andere > max_abstand" in lage, "DB: unbekannte Größe sperrt immer, sonst Abstand > 2")
check("p.start_um_gestartet_at > now() - interval '15 minutes'" in lage and "p.status = 'open'" in lage, "DB: open und frische Claims (≤ 15 min) zählen wie bisher")
check("(p.started_at is not null and p.ended_at is null and p.started_at > now() - interval '3 days')" in lage,
      "DB robust: gestartet und nicht beendet zählt, egal welcher Status (nur Starts der letzten 3 Tage, alte completed ohne ended_at nie)")
check("and not (coalesce(p.hedge_eur, 0) > 0 and coalesce(p.mt5_baseline->'hedge'->>'status', '') in ('offen', 'oeffnet', 'schliesst'))" in lage
      and "and coalesce(p.mt5_baseline->'hedge'->>'status', '') not in" not in lage, "DB: Hedge-Ausnahme nur für echte Hedge-Pläne (hedge_eur > 0)")
# Die drei Durchrutscher vom 02.11. (Dubai) — nachgerechnet per Lese-SELECT mit genau dieser Zählung und Größe zum Claim-Zeitpunkt:
# 00001e43 15:04:18 150k 4 Long : 8 Short, 7883ce9e 15:11:02 150k 4 : 9, f9e0c9ee 15:44:54 150k 5 : 10 — jeder Short gesperrt
for name, nl, ns in (("00001e43", 4, 8), ("7883ce9e", 4, 9), ("f9e0c9ee", 5, 10)):
    check(D("futures", {"je_groesse": {"150k": {"n_long": nl, "n_short": ns}}}, "sell", 2, "150k")[0], f"{name}: 150k {nl} : {ns} → Short gesperrt")
trg = SQL.split("create or replace function public.trade_plans_waage_deckel()")[1]
check(trg.count("jsonb_build_object('waage_lage', spur)") == 3 and "'ids', lage->'ids'" in trg and "'groesse', lage->'groesse'" in trg,
      "DB-Trigger: Spur waage_lage {groesse, n_long, n_short, ids, at} beim Durchlassen und in beiden Sperr-Zweigen")
check(trg.count("return null;") == 2 and "coalesce(new.start_claim_art, '') = 'verbrauch'" in trg and "new.hand_werte_at is not null" in trg,
      "DB-Trigger: Sperren, Verbrauch und Hand-Werte wie bisher")
check("Deckel je Kontogröße (Abstand höchstens 2)" in HTML, "Anzeige „Waage jetzt“ nennt die Größen im Hinweis")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
