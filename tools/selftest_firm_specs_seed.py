"""Selbsttest FS1 (05.11.2026, Befund S2 HX1): der Tab-Seed DEFAULT_FIRM_SPECS legt bei neuen Logins firm_specs an. FTMO stand dort noch auf
ppl 0,85 → seit 08.10. sieben IDs mit FTMO 0,85 (Railway-Anzeigen × 0,85 zu klein). Richtig 1,00 (MT5 US100.cash, 1 $ je Punkt und Lot,
sql/2026-10-08_ftmo_kernwerte.sql). Prüft: FTMO-Seed = 1,00, die übrigen Seed-Werte = Stand der Kernwert-/Firmen-SQLs (Wache gegen
Rückfälle), und sql/2026-11-05_ftmo_ppl_seed_fix.sql trifft nur FTMO + NAS100 + 0,85. Nur lesen. Aufruf: python3 tools/selftest_firm_specs_seed.py"""
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
fehler = 0


def check(ok, name):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    if not ok:
        fehler += 1


a = HTML.index("  const DEFAULT_FIRM_SPECS = [")
blk = HTML[a:HTML.index("\n  ]\n", a)]
seed = {}
for m in re.finditer(r"\{ name:'([^']+)',\s*symbol:'([^']*)',\s*unit:'([^']+)',\s*ppl:([\d.]+),\s*currency:'([^']+)'", blk):
    seed[m.group(1)] = (m.group(2), m.group(3), float(m.group(4)), m.group(5))

check(seed.get("FTMO") == ("NAS100", "Lots", 1.0, "$"), f"Seed FTMO NAS100 Lots 1,00 $ ({seed.get('FTMO')})")

# Stand laut Kernwert-/Firmen-SQLs (und DB-Mehrheit 05.11.2026) — (unit, ppl, currency)
SOLL = {"Alpha Future": ("Kontrakte", 2.0, "$"), "Apex Trader": ("Kontrakte", 2.0, "$"), "FTMO": ("Lots", 1.0, "$"),
        "FTMO Futures": ("Kontrakte", 2.0, "$"), "FundedNext": ("Lots", 10.0, "$"), "FundedNext Futures": ("Kontrakte", 2.0, "$"),
        "FundingPips": ("Lots", 20.0, "$"), "Fusion Markets": ("Lots", 0.85, "€"), "Lucid Trading": ("Kontrakte", 2.0, "$"),
        "MyFundedFutures": ("Kontrakte", 2.0, "$"), "The5%ers": ("Lots", 1.0, "$"), "Tradeify": ("Kontrakte", 2.0, "$"),
        "Tradeify CFD": ("Lots", 10.0, "$")}
for name, (unit, ppl, cur) in SOLL.items():
    s = seed.get(name)
    check(s is not None and (s[1], s[2], s[3]) == (unit, ppl, cur), f"Seed {name}: {unit} {ppl} {cur} ({s})")

SQL = open(os.path.join(WURZEL, "sql", "2026-11-05_ftmo_ppl_seed_fix.sql"), encoding="utf-8").read()
check("set ppl = 1.0\n where name = 'FTMO' and symbol = 'NAS100' and ppl = 0.85;" in SQL, "SQL: nur FTMO + NAS100 + 0,85 → 1,0 (idempotent)")
check("-- update public.firm_specs set ppl = 0.85" in SQL and "-- Kontrolle" in SQL, "SQL: Rückbau und Kontroll-Abfrage als Kommentar")

print("ALLES GRÜN" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
