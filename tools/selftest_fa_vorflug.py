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
jetzt_s = 8 * 3600   # 08:00
check(ob.journal_letzte_ablehnung([f1], L, "NAS100", jetzt_s) is not None, "b9 Ablehnung 07:58, jetzt 08:00, gleiches Symbol → Treffer")
check(ob.journal_letzte_ablehnung([f1], L, "NAS100", 12 * 3600) is None, "b10 Prüfer S2: Ablehnung älter als 3 h → kein Befund")
check(ob.journal_letzte_ablehnung([f1], L, "US30", jetzt_s) is None, "b11 Prüfer S2: Ablehnung eines anderen Symbols → kein Befund")
check(not ob.vorflug_urteil(z(symbol_modus=1), "")["rot"] and ob.vorflug_urteil(z(symbol_modus=1), "sell")["rot"],
      "b12 Prüfer S3: ohne gültige Richtung keine Seitenprüfung, mit Verkauf bei LONGONLY rot")

# c) Bot
msrc = inspect.getsource(ob.main)
check(0 < msrc.find('sys.argv[1] == "vorflug"') < msrc.find("fehlerfoto_huelle_einbauen("), "c1 vorflug läuft vor der Fehlerfoto-Hülle")
check("vorflug" in ob.FEHLERFOTO_OHNE, "c2 kein Fehlerfoto im Vorflug")
vsrc = inspect.getsource(ob.modus_vorflug)
check("symbol_select" not in vsrc.replace("kein symbol_select", "") and "_feld_tippen" not in vsrc and "click" not in vsrc
      and "_mt5_login_bestaetigen" not in vsrc and "order_send" not in vsrc, "c3 modus_vorflug liest nur (kein symbol_select/Klick/Login-Dialog)")
check("mt5.shutdown()" in vsrc, "c4 Verbindung wird wieder gelöst")

# d) Panel
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel as pn_vf  # noqa: E402
with open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8") as f:
    p = f.read()
i = p.find('if path == "/api/vorflug":')
blk = p[i:p.find('if path == "/api/haupt-tab":', i)]
check(i > 0 and "provision.terminal_pids(" in blk and "lock.acquire(blocking=False)" in blk and "409" in blk and "VORFLUG_LESEN.add(" in blk
      and "VORFLUG_LESEN.discard(" in blk and "lock.release()" in blk and '"vorflug"' in blk, "d1 /api/vorflug wie /api/deals (laufendes Terminal, Lock, 409, aufräumen)")
g1 = blk[blk.find("with MASTER_ORDER_GUARD:"):blk.find("if not frei:")]
check("lock.acquire(blocking=False)" in g1 and "VORFLUG_LESEN.add(" in g1 and "vorflug_darf(" in g1,
      "d1b Hinweis S1: Lock + Markierung in EINEM Schritt unter MASTER_ORDER_GUARD, angemeldete Order hat Vorrang")
g2 = blk[blk.rfind("finally:"):]
check(g2.find("with MASTER_ORDER_GUARD:") < g2.find("lock.release()") < g2.find("VORFLUG_LESEN.discard("), "d1c erst Lock frei, dann Markierung weg (unter dem Guard)")
check(pn_vf.vorflug_darf("a.json", {"a.json": 1000.0}, 1030.0) is False and pn_vf.vorflug_darf("a.json", {"a.json": 1000.0}, 1061.0) is True
      and pn_vf.vorflug_darf("b.json", {"a.json": 1000.0}, 1001.0) is True, "d1d angemeldete Order sperrt den Vorflug derselben Instanz 60 s")
check("ORDER_ANGEMELDET[inst[\"config_file\"]] = time.time()" in p, "d1e Order/Close melden sich nach dem Vorab-Warten an")
check("_instanz_heilt(inst)" in blk, "d2 nicht während einer EA-Heilung")
check("_hat = lock.acquire(timeout=" not in p and p.count("_vorflug_abwarten(inst[\"config_file\"])") == 1,
      "d3 Prüfer M1: kein Warten am Lock mehr — EIN Vorab-Warten vor allen Riegeln beider Routen")
k = p.find('if u.path in ("/api/master-order", "/api/master-close") and inst:')
check(0 < k < p.find('if u.path == "/api/master-order":') < p.find("richtung_frei(", k), "d3b Vorab-Warten steht vor den Routen (vor Richtungs-Riegel/Copier-Frische)")
check(re.search(r"VORFLUG_WARTE_S = 25\.0", p) and re.search(r"VORFLUG_DECKEL_S = 20\b", p) and "timeout=VORFLUG_DECKEL_S" in blk,
      "d4 Prüfer S1: Warten 25 s, Lese-Deckel 20 s (25 + 300 s Bot < 310 s Proxy)")
check('_ri if _ri in ("buy", "sell") else ""' in blk, "d5 Prüfer S3: Panel reicht nur buy/sell als Richtung durch")

# d6) Verhalten (Prüfer S5): Vorab-Warten + Lock — Vorflug hält den Lock, zwei Aufträge derselben Instanz → einer läuft, der zweite bekommt sofort 409
import threading  # noqa: E402
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel as pn  # noqa: E402
pn.VORFLUG_LESEN.clear()
lk = threading.Lock()
lk.acquire()
pn.VORFLUG_LESEN.add("v.json")
erg = []


def auftrag(name):
    pn._vorflug_abwarten("v.json")
    if lk.acquire(blocking=False):
        erg.append((name, "läuft"))
        time.sleep(0.3)
        lk.release()
    else:
        erg.append((name, "409"))


import time  # noqa: E402
ts = [threading.Thread(target=auftrag, args=(n,)) for n in ("A", "B")]
for t in ts:
    t.start()
time.sleep(1.2)
check(erg == [], "d6a Aufträge warten, solange der Vorflug läuft")
pn.VORFLUG_LESEN.discard("v.json")
lk.release()
for t in ts:
    t.join(5)
check(sorted(x[1] for x in erg) == ["409", "läuft"], f"d6b danach läuft genau einer, der zweite bekommt 409 wie bisher ({erg})")
t0 = time.time()
check(pn._vorflug_abwarten("andere.json") < 0.05 and time.time() - t0 < 0.1, "d6c ohne Vorflug kein Warten")

# d7) modus_vorflug mit nachgebautem MetaTrader5 (Prüfer S5)
import json as _json, tempfile, types  # noqa: E401,E402
aufr = []


class FakeMt5(types.ModuleType):
    def __init__(self, init_ok=True, ai=True):
        super().__init__("MetaTrader5")
        self.init_ok, self.ai_da = init_ok, ai

    def initialize(self, path=None, timeout=None):
        aufr.append(("initialize", timeout))
        return self.init_ok

    def last_error(self):
        return (-1, "x")

    def account_info(self):
        return types.SimpleNamespace(login=L, balance=90040.03, trade_allowed=True) if self.ai_da else None

    def terminal_info(self):
        return types.SimpleNamespace(connected=True, data_path="")

    def symbol_info(self, s):
        return types.SimpleNamespace(trade_mode=4)

    def shutdown(self):
        aufr.append(("shutdown",))


with tempfile.TemporaryDirectory() as td:
    term = os.path.join(td, "terminal64.exe")
    open(term, "w").close()
    cfgp = os.path.join(td, "c.json")
    with open(cfgp, "w") as f:
        _json.dump({"master_terminal_path": term, "master_expected_login": L}, f)
    for fake, name in ((FakeMt5(), "ok"), (FakeMt5(init_ok=False), "init"), (FakeMt5(ai=False), "ai")):
        sys.modules["MetaTrader5"] = fake
        aufr.clear()
        res = ob.modus_vorflug({"cfg": cfgp, "symbol": "NAS100", "richtung": "buy"})
        if name == "ok":
            check(res.get("lesbar") and res.get("rot") is False and ("shutdown",) in aufr and ("initialize", 10000) in aufr,
                  "d7a gesundes Konto → lesbar, nicht rot, initialize 10 s, shutdown")
        elif name == "init":
            check(res.get("lesbar") is False and ("shutdown",) not in aufr, "d7b initialize scheitert → lesbar False")
        else:
            check(res.get("lesbar") is False and ("shutdown",) in aufr, "d7c account_info leer → lesbar False, shutdown im finally")
    res = ob.modus_vorflug({"cfg": cfgp.replace("c.json", "fehlt.json")})
    check(res.get("lesbar") is False, "d7d Config fehlt → lesbar False")
    sys.modules.pop("MetaTrader5", None)

# e) Hinweis S1 (RA2 F1): reine Lesungen zählen nicht als „MT5-Order läuft“ (Tab-Heilung, Polar, Panel-Neustart)
la, lb = threading.Lock(), threading.Lock()
la.acquire()
check(pn.mt5_order_belegt({"a.json": la, "b.json": lb}, set()) is True, "e1 Order hält den Lock → belegt")
check(pn.mt5_order_belegt({"a.json": la, "b.json": lb}, {"a.json"}) is False, "e2 nur eine Deal-/Vorflug-Lesung hält den Lock → nicht belegt")
lb.acquire()
check(pn.mt5_order_belegt({"a.json": la, "b.json": lb}, {"a.json"}) is True, "e3 Lesung auf A, Order auf B → belegt")
check("mt5_order_belegt()" in inspect.getsource(pn._browser_und_mt5_frei) and "mt5_order_belegt()" in inspect.getsource(pn._bot_lauf_aktiv),
      "e4 _browser_und_mt5_frei und _bot_lauf_aktiv (Polar, Fenster nach vorn) nutzen die neue Prüfung")
la.release(); lb.release()
pn.MASTER_ORDER_LOCKS.clear(); pn.DEALS_LESEN.clear(); pn.VORFLUG_LESEN.clear(); pn._PANEL_POST["n"] = 0
lx = threading.Lock(); lx.acquire()
pn.MASTER_ORDER_LOCKS["x.json"] = lx
pn.DEALS_LESEN.add("x.json")
check(not any("MT5" in g for g in pn.panel_beschaeftigt_gruende()), "e5 panel_beschaeftigt_gruende: Deal-Lesung ist kein Grund")
pn.DEALS_LESEN.clear()
check(any(g.startswith("MT5-Order") for g in pn.panel_beschaeftigt_gruende()), "e6 echte Order bleibt ein Grund")
pn.MASTER_ORDER_LOCKS.clear(); lx.release()

# f) Prüfer S2 (Master 11.11.2026): hält ein Vorflug den Lock noch (Deckel/Bot-Start bzw. Fenster vor ORDER_ANGEMELDET), antworten Order UND Close
#    409 retry_ok True „nichts gesendet“ wie bei einer Deal-Lesung — nie retry_ok False („läuft gerade schon eine Order“ = UNKLAR/Fehlstart)
hsrc = inspect.getsource(pn.Handler)
treffer = [m.start() for m in re.finditer(re.escape('if inst["config_file"] in (DEALS_LESEN | VORFLUG_LESEN):'), hsrc)]
check(len(treffer) == 2 and all('"retry_ok": True, "grund": "deals_lesen"' in hsrc[t:t + 260] for t in treffer),
      "f1 Order- und Close-Route: Lock von Vorflug oder Deal-Lesung → 409 retry_ok True")
check('if inst["config_file"] in DEALS_LESEN:' not in hsrc, "f2 kein Zweig prüft mehr nur DEALS_LESEN")
for t in treffer:
    vor = hsrc[max(0, t - 400):t]
    check("if not lock.acquire(blocking=False):" in vor, "f3 der Zweig gehört zum besetzten Lock")
pn.VORFLUG_LESEN.clear(); pn.DEALS_LESEN.clear()
pn.VORFLUG_LESEN.add("v.json")
check("v.json" in (pn.DEALS_LESEN | pn.VORFLUG_LESEN) and "w.json" not in (pn.DEALS_LESEN | pn.VORFLUG_LESEN), "f4 Mengen-Vereinigung trifft nur die lesende Instanz")
pn.VORFLUG_LESEN.clear()

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
