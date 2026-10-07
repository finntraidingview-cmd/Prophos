#!/usr/bin/env python3
"""Selbsttest Satz an Live-Trades (app.py, SATZ-AN-LIVE-TRADES, 07.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_lt_satz.py
Lädt lt_satz_setzen und ap_kontowerte_gemerkt per Quelltext aus app.py (app.py zieht beim Import Flask und Threads). Prüft:
Satz je Zeile aus den Kontowerten des Master-Kontos (plan_id oder id), ohne Konto/ohne Wert None; der 60-s-Merker
rechnet einmal und teilt sich die Sicht „*" mit /admin/kontowerte; die Route setzt den Satz nur mit ?echo=1."""
import os
import sys
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def main():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    zaehler = {"n": 0}

    def admin_build_kontowerte(sicht=None):
        zaehler["n"] += 1
        return {"k-1": {"satz_eur_pro_usd": 0.05, "wert_eur": 500}, "k-2": {"satz_eur_pro_usd": None, "wert_eur": None}}

    ns = {"time": time, "_ap_kw_cache": {}, "_ap_kw_cache_lock": threading.Lock(), "AP_KW_CACHE_S": 60,
          "admin_build_kontowerte": admin_build_kontowerte}
    exec(block("lt_satz_setzen") + "\n\n" + block("ap_kontowerte_gemerkt"), ns)
    werte = ns["ap_kontowerte_gemerkt"](None)
    ns["ap_kontowerte_gemerkt"](None)
    check(zaehler["n"] == 1 and "*" in ns["_ap_kw_cache"], "Merker: zweimal gefragt, einmal gerechnet, Sicht „*“")

    trades = [{"plan_id": "p-1"}, {"id": "p-2"}, {"plan_id": "p-3"}, {"plan_id": "p-4"}]
    konto = {"p-1": "k-1", "p-2": "k-1", "p-3": "k-2", "p-4": None}
    ns["lt_satz_setzen"](trades, konto, werte)
    check(trades[0]["satz_eur_je_usd"] == 0.05, "Satz aus dem Master-Konto (plan_id)")
    check(trades[1]["satz_eur_je_usd"] == 0.05, "Rückfall auf id, wenn plan_id fehlt")
    check(trades[2]["satz_eur_je_usd"] is None, "Konto ohne Wert → None, kein Raten")
    check(trades[3]["satz_eur_je_usd"] is None, "Plan ohne Konto → None")
    ns["lt_satz_setzen"](trades, konto, None)
    check(all(t["satz_eur_je_usd"] is None for t in trades), "keine Kontowerte → alle None")

    route = block("admin_live_trades")
    i = route.find("lt_satz_setzen(")
    check(i > 0 and "if mit_echo:" in route[max(0, i - 400):i], "Route: Satz nur mit ?echo=1 (PC-Tab-Takt bleibt ohne)")

    if FEHLER:
        print(f"\n{len(FEHLER)} Fehler")
        sys.exit(1)
    print("\nalles grün")


if __name__ == "__main__":
    main()
