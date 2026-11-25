#!/usr/bin/env python3
"""Selbsttest FN2 (Master 26.11.2026, Finn: bei „Finn + Pascal“ war FundedNext Futures im Vorrat-Lauf gesperrt — „ab 1. FN-Payout“ —, obwohl er
FundedNext längst ausgezahlt bekommt). Befund: der Check _vorrat2_fn_payout_uids zählte nur FundedNext-CFD-Payouts; „Finn + Pascal“ hat 6 erhaltene
FundedNext-FUTURES-Payouts und 0 CFD, die archivierte ID „Finn“ keinen FundedNext-Payout (nur Apex). Fix: erhaltene FNF-Payouts zählen mit.
Echte Funktion per AST aus app.py mit Stub-DB, ohne Netz. Aufruf: python3 tools/selftest_fn2_fnf_payout.py"""
import ast
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


baum = ast.parse(SRC)
compile(baum, "app.py", "exec")
teile = [x for x in baum.body if (isinstance(x, ast.FunctionDef) and x.name in ("_vorrat2_fn_payout_uids", "vorrat_kauf_deckel"))
         or (isinstance(x, ast.Assign) and any(getattr(t, "id", "") in ("VORRAT_FN_PAYOUT_FIRMEN", "VORRAT_FNF_SPERRE", "VORRAT_LAUFEND_TYPEN")
                                               for t in x.targets))]
check(len(teile) == 5, f"Funktionen + Konstanten in app.py ({len(teile)})")

DB = {}
NORM = {"fundednext": "FundedNext", "funded next": "FundedNext", "fundednext futures": "FundedNext Futures", "apex trader": "Apex Trader"}


def sb_all(tab, params):
    if DB.get("fehler"):
        raise RuntimeError("DB weg")
    return DB.get(tab, [])


ns = {"time": __import__("time"), "_vr2_fn_cache": {}, "_sb_all": sb_all, "_firm_norm": lambda f: NORM.get(str(f or "").strip().lower(), str(f or ""))}
exec(compile(ast.Module(body=teile, type_ignores=[]), "app.py", "exec"), ns)
f, deckel = ns["_vorrat2_fn_payout_uids"], ns["vorrat_kauf_deckel"]
check(ns["VORRAT_FN_PAYOUT_FIRMEN"] == ("FundedNext", "FundedNext Futures"), "FundedNext CFD UND FundedNext Futures zählen")


def lauf(tx, pp, fehler=False):
    DB.clear()
    DB.update({"transactions": tx, "pending_payouts": pp, "fehler": fehler})
    ns["_vr2_fn_cache"].clear()
    return f()


u = lauf([{"user_id": "fp", "account_firm": "FundedNext Futures"}], [])
check(u == {"fp"}, "Finn + Pascal: erhaltener FNF-Payout (transactions) → frei")
check(lauf([], [{"user_id": "fp", "account_firm": "FundedNext Futures", "status": "received"}]) == {"fp"}, "… ebenso über pending_payouts received")
check(lauf([{"user_id": "jacob", "account_firm": "FundedNext"}], []) == {"jacob"}, "CFD-Payout wie bisher → frei")
check(lauf([{"user_id": "finn_alt", "account_firm": "Apex Trader"}], []) == set(), "nur Apex-Payouts (archivierte ID „Finn“) → weiter gesperrt")
check(lauf([], [], fehler=True) is None, "DB-Fehler → None (Aufrufer sperrt, lieber zu wenig)")
lauf([{"user_id": "a", "account_firm": "FundedNext"}], [])
DB["transactions"] = []                                      # Merker 10 min: zweiter Aufruf ohne DB-Änderung liefert denselben Stand
check(f() == {"a"}, "10-min-Merker unverändert")

STD = {"max_laufend": {"FundedNext Futures": 3}}
check(deckel(10, [], "FundedNext Futures", STD, fn_payout_ok="fp" in u)["n"] == 3 and deckel(10, [], "FundedNext Futures", STD, fn_payout_ok=False)["sperre"],
      "Deckel: mit Payout 3 kaufen, ohne Sperre „ab 1. FN-Payout“ (unverändert)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
