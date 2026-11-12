#!/usr/bin/env python3
"""Selbsttest EH2 Panel-Riegel „Hedge wäre 0 Lot“ (Master 12.11.2026, Befund S2 zu EH1): /api/master-order (Echo mit Hedge) prüft VOR dem Klick mit der
Copier-Formel (plan_actions + norm_vol: volumen × multiplier × m_cs ÷ h_cs auf volume_step, unter volume_min → 0), ob der Hedge 0 Lot würde → kein Klick,
retry_ok false, gesendet false, Meldung „Hedge wäre 0 Lot — Kontraktgrößen Master/Fusion prüfen“. Fehlt eine Angabe → wie bisher, nur Log.
Echte Funktionen aus mt5-copier/panel.py und copier.py, Anker in panel.py/copier.py/prophos.html. Ohne Netz/MT5. Aufruf: python3 tools/selftest_eh2_panel_hedge_null.py"""
import os
import random
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
COP = open(os.path.join(W, "mt5-copier", "copier.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


def quelle(src, name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", src, re.S | re.M)
    if not m:
        raise LookupError(name)
    return m.group(0)


ns, cop = {}, {"TOL": 1e-6}
exec(quelle(PANEL, "hedge_null_urteil"), ns)
exec(quelle(COP, "norm_vol"), cop)
hu = ns["hedge_null_urteil"]
FUS = {"volume_step": 0.01, "volume_min": 0.01, "trade_contract_size": 1.0}

# ── die drei Fälle aus dem Auftrag
g, t, v = hu(1.0, 0.01, 1.0, FUS)
check(g is False and v == 0.01, f"1:1 (Master-cs 1, Fusion-cs 1): 1 Lot × 0,01 → 0,01 Lot → frei ({g}, {v})")
g, t, v = hu(1.0, 0.01, 1.0, dict(FUS, trade_contract_size=10.0))
check(g is True and v == 0.0 and t.startswith("Hedge wäre 0 Lot — Kontraktgrößen Master/Fusion prüfen") and "Nichts gesendet" in t,
      f"1:10 (Fusion-cs 10): 0,01 → 0,001 → 0 Lot → gesperrt ({t[:90]})")
g, t, v = hu(1.0, 0.01, 0.1, FUS)
check(g is True and v == 0.0, "10:1 (Master-cs 0,1 gegen Fusion 1): 0,01 → 0,001 → 0 Lot → gesperrt")
g, t, v = hu(1.0, 0.01, 10.0, FUS)
check(g is False and v == 0.1, "großer Master-cs (10 gegen 1): 0,1 Lot → frei (nur 0 Lot sperrt, nie ein großer Hedge)")
check(hu(0.5, 0.0149, 1.0, FUS)[0] is False and hu(1.0, 0.0049, 1.0, FUS)[0] is True, "Schritt-Rundung wie der Copier: 0,00745 → 0,01 frei · 0,0049 → 0 gesperrt")

# ── fehlende Angaben → nicht prüfbar (kein neuer Fehlstart)
for args, name in (((1.0, 0.01, None, FUS), "Master-Kontraktgröße nicht lesbar"), ((1.0, 0.01, 1.0, None), "Copier-Status ohne hedge_sym"),
                   ((1.0, None, 1.0, FUS), "Multiplikator fehlt"), ((None, 0.01, 1.0, FUS), "Volumen fehlt"),
                   ((1.0, 0.01, 1.0, {"volume_step": 0.01}), "volume_min/Kontraktgröße fehlen"), (("x", 0.01, 1.0, FUS), "Volumen kein Zahl")):
    check(hu(*args)[0] is None, f"{name} → nicht prüfbar (None), wie bisher kein Riegel")

# ── gleiche Rechnung wie der Copier (norm_vol) über Zufallsfälle
rnd, gleich, n = random.Random(7), 0, 0
for _ in range(3000):
    vol = round(rnd.choice([0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5]) * rnd.uniform(0.5, 3), 2) or 0.01
    mult, mcs, hcs = rnd.uniform(0.0001, 3), rnd.choice([0.1, 1, 2, 5, 10, 20, 100]), rnd.choice([0.1, 1, 10])
    si = {"volume_step": 0.01, "volume_min": 0.01, "trade_contract_size": hcs}
    erw = cop["norm_vol"](dict(si, volume_max=1e9), vol * mult * (mcs / hcs)) <= 1e-6
    g, _t, _v = hu(vol, mult, mcs, si)
    n += 1
    gleich += (g is True) == erw
check(gleich == n, f"Urteil = Copier norm_vol ≤ TOL in allen {n} Zufallsfällen ({gleich})")

# ── Einbau-Anker
route = PANEL[PANEL.index('if u.path == "/api/master-order":'):PANEL.index('if u.path == "/api/master-close":')]
i_lock, i_chk, i_bot = route.index("if not lock.acquire(blocking=False):"), route.index("hedge_null_urteil("), route.index("bot_argv(bot)")
check(i_lock < i_chk < i_bot, "Riegel nach dem Instanz-Lock und VOR dem Bot-Start (kein Klick)")
blk = route[i_chk - 1400:i_chk + 1400]
check("if not ohne_hedge:" in blk and '"retry_ok": False, "gesendet": False, "grund": "hedge_null", "code": "hedge_null"' in blk and "lock.release()" in blk,
      "nur Echo mit Hedge; Antwort retry_ok false, gesendet false, Code hedge_null; Lock wird freigegeben")
check("Hedge-0-Prüfung nicht möglich" in blk and "_master_contract_size_live(_cfg_h, cmd[\"symbol\"])" in blk, "fehlende Angabe → nur Log; Master-Kontraktgröße live gelesen")
mcl = quelle(PANEL, "_master_contract_size_live")
check("mt5.symbol_info(symbol)" in mcl and "mt5.shutdown()" in mcl and "master_expected_login" in mcl and "order_send" not in mcl,
      "Master-Kontraktgröße NUR LESEND (symbol_info, Login-Guard, shutdown), kein order_send")
# Prüfer EH2 (SOLLTE): nur laufendes Terminal, kurzer timeout, nie ohne erwarteten Login, Ergebnis gemerkt
check("provision.terminal_pids(" in mcl and mcl.index("provision.terminal_pids(") < mcl.index("mt5.initialize("), "nur ein schon laufendes Terminal wird gelesen (nie gestartet)")
check("mt5.initialize(path=path, timeout=5000)" in mcl, "initialize mit 5 s timeout (nicht 60 s Standard vor dem Klick)")
check("mt5.initialize(path=path, timeout=5000)" in quelle(PANEL, "_master_positionen_live"), "EH2c: auch der Lösch-Riegel initialisiert mit 5 s timeout (hält den In-Prozess-Lock nicht 60 s)")
check("or not exp:" in mcl and "int(ai.login) != exp" in mcl, "ohne master_expected_login wird nicht gelesen; Login muss passen")
check("_MCS_CACHE[key] = (time.time(), cs)" in mcl and "_MCS_CACHE_S" in PANEL, "Kontraktgröße je Terminal × Login × Symbol gemerkt (kein Anschluss vor jeder Order)")
check('"hedge_sym": hedge_sym_specs(m.symbol_map)' in COP and "def hedge_sym_specs(symbol_map):" in COP, "Copier schreibt hedge_sym (Lot-Schritt, Mindest-Lot, Kontraktgröße der Hedge-Ziele) in den Status")
check("const hedgeNull = !!(r && !r.ok && r.code === 'hedge_null' && r.gesendet === false" in HTML and "unklar: !(retryOk || sicherAbgelehnt || hedgeNull)" in HTML
      and "(retryOk || echoAus || hedgeNull)) await fensterWeg()" in HTML, "PC-Tab: hedge_null = nichts gesendet (nicht UNKLAR), Fenster zurück")

# ── EH2b (Prüfer S2): In-Prozess-MT5-Lock — zwei Threads, zwei Terminals (gemockt) → keine Kreuz-Werte; positions_get None nie flach
import tempfile
import threading
import time
import types


class FakeMT5:
    """prozessweiter Anschluss wie MetaTrader5: initialize(path) wechselt DAS eine Terminal, Aufrufe dazwischen schlafen (Verzahnung erzwingen)"""
    def __init__(self, terminals):
        self.t, self.aktuell = terminals, None

    def initialize(self, path=None, timeout=None):
        self.aktuell = path
        time.sleep(0.01)
        return True

    def shutdown(self):
        self.aktuell = None

    def account_info(self):
        time.sleep(0.005)
        t = self.t.get(self.aktuell)
        return types.SimpleNamespace(login=t["login"]) if t else None

    def symbol_info(self, sym):
        time.sleep(0.01)
        t = self.t.get(self.aktuell)
        return types.SimpleNamespace(trade_contract_size=t["cs"]) if t else None

    def positions_get(self):
        time.sleep(0.005)
        t = self.t.get(self.aktuell)
        return t["pos"] if t else None


tmp = tempfile.mkdtemp()
pa, pb = os.path.join(tmp, "A", "terminal64.exe"), os.path.join(tmp, "B", "terminal64.exe")
for x in (pa, pb):
    os.makedirs(os.path.dirname(x), exist_ok=True)
    open(x, "w").close()
fake = FakeMT5({pa: {"login": 111, "cs": 1.0, "pos": ()}, pb: {"login": 222, "cs": 20.0, "pos": (1, 2)}})
sys.modules["MetaTrader5"] = fake
pns = {"os": os, "time": time, "threading": threading, "provision": types.SimpleNamespace(terminal_pids=lambda d: [1])}
blk = PANEL[PANEL.index("_MT5_INPROC_LOCK = threading.Lock()"):PANEL.index("def _ok_dialog_watcher(")]
exec(blk, pns)
ca, cb = {"master_terminal_path": pa, "master_expected_login": 111}, {"master_terminal_path": pb, "master_expected_login": 222}
erg = {"a": [], "b": [], "pa": [], "pb": []}


def lauf(cfg, k, kp):
    for i in range(15):
        pns["_MCS_CACHE"].clear()
        erg[k].append(pns["_master_contract_size_live"](cfg, "NAS100"))
        erg[kp].append(pns["_master_positionen_live"](cfg))


th = [threading.Thread(target=lauf, args=(ca, "a", "pa")), threading.Thread(target=lauf, args=(cb, "b", "pb"))]
for x in th:
    x.start()
for x in th:
    x.join()
check(set(v for v in erg["a"] if v is not None) <= {1.0} and set(v for v in erg["b"] if v is not None) <= {20.0} and erg["a"].count(1.0) + erg["b"].count(20.0) >= 20,
      f"zwei Threads, zwei Terminals: Kontraktgröße nie vom fremden Terminal (A {set(erg['a'])}, B {set(erg['b'])})")
check(set(v for v in erg["pa"] if v is not None) <= {0} and set(v for v in erg["pb"] if v is not None) <= {2}, f"Positionen nie vom fremden Terminal (A {set(erg['pa'])}, B {set(erg['pb'])})")
pns["_MCS_CACHE"].clear()
pns["_master_contract_size_live"](ca, "NAS100"); pns["_master_contract_size_live"](cb, "NAS100")
check(all((k[1] == 111 and v[1] == 1.0) or (k[1] == 222 and v[1] == 20.0) for k, v in pns["_MCS_CACHE"].items()) and len(pns["_MCS_CACHE"]) == 2, "Cache ohne Kreuz-Werte (Login ↔ Kontraktgröße)")
fake.t[pa]["pos"] = None
check(pns["_master_positionen_live"](ca) is None, "positions_get None → nicht prüfbar (None), nie „beweisbar flach“ (0)")
fake.t[pa]["pos"] = ()
pns["_MT5_INPROC_LOCK"].acquire()
t0 = time.time()
pns["_MT5_INPROC_WARTE_S"] = 0.2
r1, r2 = pns["_master_contract_size_live"](dict(ca, master_expected_login=111), "US500"), pns["_master_positionen_live"](ca)
pns["_MT5_INPROC_LOCK"].release()
check(r1 is None and r2 is None and time.time() - t0 < 2, "Lock besetzt → nach Wartezeit None (kein Riegel bzw. nicht flach), kein Hängen")
fake.t[pb]["login"] = 333
pns["_MCS_CACHE"].clear()
check(pns["_master_contract_size_live"](cb, "NAS100") is None and not pns["_MCS_CACHE"], "Konto passt nicht (Login-Guard) → None, nichts gemerkt")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en)")
    sys.exit(1)
print("GRÜN: EH2 Panel-Riegel Hedge wäre 0 Lot")
