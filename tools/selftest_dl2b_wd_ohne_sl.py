#!/usr/bin/env python3
"""Selbsttest DL2b (Master 11.11.2026 nach S2/KK1b, Finns Linie seit Emin …0887): Firmen MIT Tageslimit (Lucid 2.700, FTMO Futures 1.000) bekommen nie einen
WD-Plan ohne SL — scheitert der SL-Kontext, wirft wd_sl_fuer_plan oder reicht der Puffer nicht, wird der Plan NICHT angelegt (Grund, nächster Lauf).
Firmen ohne Tageslimit (Tradeify: „nie ein Daily Loss Limit“, Apex mit Stufen-Regel) bleiben wie heute. Die ECHTEN Funktionen aus app.py (wd_sl_dll_firma über
liq_regel_waehlen/_wd_konto_groesse) mit dem Live-Stand von liq_regeln (11.11.2026), dazu Lage und Bedingungen des Riegels im POST /admin/wd-plaene.
Ohne Netz. Aufruf: python3 tools/selftest_dl2b_wd_ohne_sl.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_wd_sl_wuerfel as ws1  # noqa: E402

APP = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


ns = ws1.lade()
i = APP.index("\ndef wd_sl_dll_firma(") + 1
exec(APP[i:APP.index("\n\n\n", i)], ns)
D = ns["wd_sl_dll_firma"]

# liq_regeln wie live (11.11.2026)
REGELN = [
    {"id": 4, "firma": "Apex Trader", "kontotyp": "funded", "groesse": 150000, "art": "stufen", "stufen": [{"ab_balance": 150000, "daily_loss_usd": 2500}]},
    {"id": 6, "firma": None, "kontotyp": "winning_days", "groesse": None, "art": None, "wie_kontotyp": "funded"},
    {"id": 7, "firma": "Tradeify", "kontotyp": "winning_days", "groesse": None, "art": "boden", "lock_ueber_start_usd": 100},
    {"id": 2, "firma": "Tradeify", "kontotyp": "funded", "groesse": None, "art": "fest", "betrag_usd": 4500},
    {"id": 14, "firma": "Lucid Trading", "kontotyp": "winning_days", "groesse": None, "art": "boden", "lock_ueber_start_usd": 100},
    {"id": 17, "firma": "Lucid Trading", "kontotyp": "funded", "groesse": 150000, "art": "tagesstart", "betrag_usd": 2700},
    {"id": 18, "firma": "Lucid Trading", "kontotyp": "winning_days", "groesse": 150000, "art": "tagesstart", "betrag_usd": 2700},
    {"id": 19, "firma": "FTMO Futures", "kontotyp": "winning_days", "groesse": 50000, "art": "tagesstart", "betrag_usd": 1000},
]
konto = lambda firm, name, **k: dict({"id": "k", "firm": firm, "name": name, "account_type": "winning_days"}, **k)
check(D(REGELN, konto("Lucid Trading", "150k LFF0000000001 → Winning Days")) is True, "Lucid 150k WD → Tageslimit (id 18 tagesstart)")
check(D([r for r in REGELN if r["id"] != 18], konto("Lucid Trading", "150k LFF0000000001 → Winning Days")) is True,
      "Lucid 150k WD ohne id 18 → über die Funded-Zeile id 17 (wie hedgeLiqDll)")
check(D(REGELN, konto("Lucid Trading", "50k LFF0000000002 → Winning Days")) is False, "Lucid 50k WD: weder WD- noch Funded-Zeile mit Tageslimit → wie heute")
check(D(REGELN, konto("FTMO Futures", "50k FTMOF0000001 → Winning Days")) is True, "FTMO Futures 50k WD → Tageslimit 1.000")
check(D(REGELN, konto("Tradeify", "150k FTDFYSLX150000000000887 → Winning Days")) is False, "Tradeify → NIE Tageslimit (WD boden, Funded fest) — wie heute")
check(D(REGELN, konto("Apex Trader", "150k PAAPEX0000000000001 → Funded")) is False, "Apex (Stufen-Regel) → zählt hier nicht — wie heute")
check(D(REGELN, konto("Tradeify", "150k X", dll_usd=1750)) is True and D(REGELN, konto("Lucid Trading", "150k Y", dll_usd=0)) is False,
      "Konto-Feld dll_usd gewinnt (> 0 ja, 0 nein)")
check(D([], konto("Lucid Trading", "150k Z")) is None and D(REGELN, None) is None, "Regeln oder Konto fehlen → unbekannt (None, Aufrufer sperrt)")

# Riegel im POST /admin/wd-plaene
i = APP.index("\ndef admin_wd_plaene(")
post = APP[i:APP.index("\n\n\n", APP.index("return jsonify({\"angelegt\": angelegt", i))]
k_riegel = post.index("if not body.get(\"master_sl\") and (sl_regel or sl_kontext_fehler)")
k_insert = post.index("angelegt.append(sb_insert(\"trade_plans\", body))")
k_wuerfel = post.index("wd_sl = wd_sl_fuer_plan(sl_regel, body, sl_konten.get(mid), sl_liq, sl_frueher)")
check(k_wuerfel < k_riegel < k_insert, "Riegel liegt nach dem Würfel, direkt vor dem Anlegen")
blk = post[k_riegel:k_insert]
check("not wd_ist_recoverer_plan(body)" in blk and '(r or {}).get("wd_ausgleich") is not True' in blk, "Recoverer/Tradeify-Ausgleich (würfeln bewusst nicht) ausgenommen")
check("wd_sl_dll_firma(sl_liq or _liq_regeln_laden(), sl_konten.get(mid) or acc[0])" in blk and "if _dll is not False:" in blk,
      "Firma mit Tageslimit ODER unbekannt (fail-closed) → kein Plan; False (Tradeify/Apex) → wie heute")
check("uebersprungen.append(" in blk and "continue" in blk and "WD_GRUND_DLL_OHNE_SL" in blk, "kein Plan + Grund (Übersprungen-Liste), kein Insert")
check("sl_kontext_fehler = sl_fest_fehler" in post and post.index("sl_kontext_fehler = sl_fest_fehler") < k_riegel,
      "Kontext-Fehler (Würfel in diesem Lauf aus) zählt — Würfel absichtlich aus (sl_regel None ohne Fehler) bleibt wie heute")
check('alarm_senden(2, "wd_dll_ohne_sl"' in post and "if _n_dll and sl_kontext_fehler:" in post, "🟠 nur bei gescheitertem Kontext, höchstens stündlich")
# Ablauf ohne Netz: simuliert, welche Pläne angelegt würden
def anlegen(master_sl, sl_regel, kontext_fehler, dll, recoverer=False, ausgleich=False):
    if not master_sl and (sl_regel or kontext_fehler) and not recoverer and not ausgleich:
        if dll is not False:
            return "kein Plan"
    return "Plan"
check(anlegen(None, {"an": True}, None, True) == "kein Plan", "Lucid, Würfel an, kein SL (z. B. Rechenfehler) → kein Plan")
check(anlegen(None, None, "Kontext nicht lesbar (HTTPError)", True) == "kein Plan", "Lucid, Kontext gescheitert → kein Plan")
check(anlegen(1650, {"an": True}, None, True) == "Plan", "Lucid mit SL (DL2-Pflicht-SL) → Plan")
check(anlegen(None, {"an": True}, None, False) == "Plan", "Tradeify ohne SL → wie heute Plan")
check(anlegen(None, None, None, True) == "Plan", "Würfel absichtlich aus → wie heute")
check(anlegen(None, {"an": True}, None, True, recoverer=True) == "Plan", "Recoverer → wie heute")
print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: " + "; ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
