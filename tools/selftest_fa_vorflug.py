#!/usr/bin/env python3
"""Selbsttest F-A Konto-Vorflug (Master 11.11.2026 nach FS2): nur lesend 10–15 min vor dem Start den Zustand des Master-Logins einer Echo-Instanz urteilen.
 a) vorflug_urteil: falsches Konto, getrennt, trade_allowed aus, Symbol gesperrt/close-only/Seite → rot mit wörtlichen Grund-Texten; ok sonst; Lots spielen keine Rolle.
 b) journal_letzte_ablehnung: neueste Order-Zeile des Logins „failed … [Only position closing is allowed]“ bzw. „[Trade disabled]“ → rot; eine spätere
    erfolgreiche Order hebt sie auf; andere Gründe (Requote, Market closed), anderes Login, modify/close zählen nicht.
 c) order_bot main: „vorflug“ vor der Fehlerfoto-Hülle, nie ein Foto; modus_vorflug liest nur (kein symbol_select, kein Klick, kein Login-Dialog).
 d) panel.py /api/vorflug wie /api/deals (nur laufendes Terminal, Lock ohne Warten, 409 bei Order); master-order und Close warten auf einen Vorflug statt 409.
Platzhalter-Login. Aufruf: python3 tools/selftest_fa_vorflug.py"""
import inspect
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


BASIS = {"symbol": "NAS100", "expected": 12345678, "login": 12345678, "verbunden": True, "handel_konto": True, "symbol_modus": 4, "balance": 100044.66}


def z(**u):
    d = dict(BASIS)
    d.update(u)
    return d


# a)
check(ob.vorflug_urteil(z(), "buy") == {"rot": False, "art": "ok", "grund": ""}, "a1 alles gut → nicht rot")
u = ob.vorflug_urteil(z(login=87654321), "buy")
check(u["rot"] and u["art"] == "falsches_konto" and "FALSCHEN Konto (87654321 statt 12345678)" in u["grund"], "a2 falsches Konto → rot")
u = ob.vorflug_urteil(z(verbunden=False), "buy")
check(u["rot"] and u["art"] == "getrennt", "a3 Terminal getrennt → rot")
u = ob.vorflug_urteil(z(handel_konto=False), "buy")
check(u["rot"] and u["art"] == "konto_gesperrt" and re.search(r"trade_allowed\s*=\s*False", u["grund"]) and "Kontostand 100 044.66" in u["grund"],
      "a4 trade_allowed False → rot, Text trifft sfGesperrt/FD_REZEPTE")
u = ob.vorflug_urteil(z(symbol_modus=3), "sell")
check(u["rot"] and u["art"] == "nur_schliessen_symbol", "a5 Symbol close-only → rot")
u = ob.vorflug_urteil(z(symbol_modus=2), "buy")
check(u["rot"] and u["art"] == "symbol", "a6 Symbol nur Verkauf, Plan Kauf → rot")
check(not ob.vorflug_urteil(z(handel_konto=None, symbol_modus=None), "buy")["rot"], "a7 Felder nicht gelesen → nicht rot")
check(not ob.vorflug_urteil(z(volume_min=5.0, volume_step=1.0), "buy")["rot"], "a8 Lot-Raster spielt im Vorflug keine Rolle")

# b) Journal
L = 12345678
f1 = f"2026.11.10 07:58:01.400 Trades '{L}': failed market sell 3 NAS100 sl: 0 tp: 0 [Only position closing is allowed]"
f2 = f"2026.11.10 07:58:01.400 Trades '{L}': failed market buy 2 NAS100 [Trade disabled]"
ok1 = f"2026.11.10 09:00:00.100 Trades '{L}': deal #998877 buy 2 NAS100 at 20000.0 done"
rq = f"2026.11.10 07:58:01.400 Trades '{L}': failed market buy 2 NAS100 [Requote]"
mod = f"2026.11.10 09:10:00.100 Trades '{L}': modify #1179274 buy 2 NAS100 sl: 1 tp: 2 done"
jt = ob.journal_letzte_ablehnung([f1], L)
check(bool(jt) and jt[0].startswith("Konto nimmt nur Schließen an") and jt[1] == "Only position closing is allowed", "b1 letzte Order „Only position closing“ → Treffer")
u = ob.vorflug_urteil(z(), "sell", jt)
check(u["rot"] and u["art"] == "nur_schliessen" and "Only position closing is allowed" in u["grund"], "b2 Urteil rot, Satz wörtlich (E1 nur_schliessen)")
jt2 = ob.journal_letzte_ablehnung([f2], L)
check(bool(jt2) and ob.vorflug_urteil(z(), "buy", jt2)["art"] == "konto_gesperrt", "b3 „Trade disabled“ → konto_gesperrt")
check(ob.journal_letzte_ablehnung([f1, ok1], L) is None, "b4 spätere erfolgreiche Order hebt die Ablehnung auf")
check(ob.journal_letzte_ablehnung([f1, mod], L) is not None, "b5 „modify #…“ danach zählt nicht als Order")
check(ob.journal_letzte_ablehnung([rq], L) is None, "b6 andere Ablehnung (Requote) → kein Konto-Befund")
check(ob.journal_letzte_ablehnung([f1.replace(str(L), "87654321")], L) is None, "b7 anderes Login → kein Treffer")
check(ob.journal_letzte_ablehnung([], L) is None, "b8 Journal leer/unlesbar → kein Treffer")

# c) Bot
msrc = inspect.getsource(ob.main)
check(0 < msrc.find('sys.argv[1] == "vorflug"') < msrc.find("fehlerfoto_huelle_einbauen("), "c1 vorflug läuft vor der Fehlerfoto-Hülle")
check("vorflug" in ob.FEHLERFOTO_OHNE, "c2 kein Fehlerfoto im Vorflug")
vsrc = inspect.getsource(ob.modus_vorflug)
check("symbol_select" not in vsrc.replace("kein symbol_select", "") and "_feld_tippen" not in vsrc and "click" not in vsrc
      and "_mt5_login_bestaetigen" not in vsrc and "order_send" not in vsrc, "c3 modus_vorflug liest nur (kein symbol_select/Klick/Login-Dialog)")
check("mt5.shutdown()" in vsrc, "c4 Verbindung wird wieder gelöst")

# d) Panel
with open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8") as f:
    p = f.read()
i = p.find('if path == "/api/vorflug":')
blk = p[i:p.find('if path == "/api/haupt-tab":', i)]
check(i > 0 and "provision.terminal_pids(" in blk and "lock.acquire(blocking=False)" in blk and "409" in blk and "VORFLUG_LESEN.add(" in blk
      and "VORFLUG_LESEN.discard(" in blk and "lock.release()" in blk and '"vorflug"' in blk, "d1 /api/vorflug wie /api/deals (laufendes Terminal, Lock, 409, aufräumen)")
check("_instanz_heilt(inst)" in blk, "d2 nicht während einer EA-Heilung")
check(p.count("_hat = lock.acquire(timeout=VORFLUG_WARTE_S)") == 2 and p.count("in VORFLUG_LESEN:") == 2,
      "d3 master-order und Close warten auf einen laufenden Vorflug (statt 409 = Fehlstart)")
check(re.search(r"VORFLUG_WARTE_S = 45\.0", p) and "timeout=40" in blk, "d4 Wartezeit der Order (45 s) > Lese-Deckel (40 s)")

# e) Hinweis S1 (RA2 F1): reine Lesungen zählen nicht als „MT5-Order läuft“ (Tab-Heilung, Polar, Panel-Neustart)
import threading  # noqa: E402
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel as pn  # noqa: E402
la, lb = threading.Lock(), threading.Lock()
la.acquire()
check(pn.mt5_order_belegt({"a.json": la, "b.json": lb}, set()) is True, "e1 Order hält den Lock → belegt")
check(pn.mt5_order_belegt({"a.json": la, "b.json": lb}, {"a.json"}) is False, "e2 nur eine Deal-/Vorflug-Lesung hält den Lock → nicht belegt")
lb.acquire()
check(pn.mt5_order_belegt({"a.json": la, "b.json": lb}, {"a.json"}) is True, "e3 Lesung auf A, Order auf B → belegt")
check("mt5_order_belegt()" in inspect.getsource(pn._browser_und_mt5_frei) and "mt5_order_belegt()" in inspect.getsource(pn._bot_lauf_aktiv),
      "e4 _browser_und_mt5_frei und _bot_lauf_aktiv (Polar, Fenster nach vorn) nutzen die neue Prüfung")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
