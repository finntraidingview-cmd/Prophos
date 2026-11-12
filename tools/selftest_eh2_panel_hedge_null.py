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
check('"hedge_sym": hedge_sym_specs(m.symbol_map)' in COP and "def hedge_sym_specs(symbol_map):" in COP, "Copier schreibt hedge_sym (Lot-Schritt, Mindest-Lot, Kontraktgröße der Hedge-Ziele) in den Status")
check("const hedgeNull = !!(r && !r.ok && r.code === 'hedge_null' && r.gesendet === false" in HTML and "unklar: !(retryOk || sicherAbgelehnt || hedgeNull)" in HTML
      and "(retryOk || echoAus || hedgeNull)) await fensterWeg()" in HTML, "PC-Tab: hedge_null = nichts gesendet (nicht UNKLAR), Fenster zurück")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en)")
    sys.exit(1)
print("GRÜN: EH2 Panel-Riegel Hedge wäre 0 Lot")
