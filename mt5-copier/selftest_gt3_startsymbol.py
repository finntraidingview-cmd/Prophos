#!/usr/bin/env python3
"""Selbsttest GT3 (25.11.2026, Goat Funded Trader): Start-Chart-Symbol je Firma für Echo-Einrichtung und Heilung + Retry nie ohne Passwort.
Befund GT2: das Lese-EA zog immer auf einen EURUSD-Chart; GFT hat nur Symbole mit Endung („NAS100.x“ → „EURUSD.x“) → kein Chart, kein EA, kein
Snapshot → Provisionierung killte das Terminal und startete es mit einer Retry-ini OHNE Passwort neu („loggt nach ein paar Minuten aus“), keine Config.
Prüft: symbol_endung / startup_symbole / startup_symbol_cfg (bestehende Firmen bitgleich EURUSD), build_startup_ini, run_provision-Quelltext
(Start-Symbol, Retry mit Login-ini je weiterem Symbol, startup_symbol in der Config), panel.py (API nimmt startup_symbol, prov_start reicht durch,
Heilung nutzt die Config), prophos.html mt5StartSymbol in JavaScriptCore. Ohne Windows/Netz. Aufruf: python3 mt5-copier/selftest_gt3_startsymbol.py"""
import ast
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, HIER)
import provision  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) Start-Symbole je Firma (provision.py)")
E, S, C = provision.symbol_endung, provision.startup_symbole, provision.startup_symbol_cfg
check(E("NAS100.x") == ".x" and E("US100.cash") == ".cash" and E("USTEC#") == "#" and E("NAS100_i") == "_i", "Endung: .x / .cash / # / _i")
check(E("NAS100") == "" and E("TECH100") == "" and E("MNQ") == "" and E("") == "" and E(None) == "" and E("NAS 100.x") == "",
      "ohne Endung (NAS100, TECH100, MNQ, leer, Leerzeichen) → ''")
check(S("NAS100.x") == ["EURUSD.x", "NAS100.x"], f"GFT NAS100.x → EURUSD.x, dann NAS100.x ({S('NAS100.x')})")
check(all(S(x) == ["EURUSD"] for x in (None, "", "NAS100", "TECH100", "MNQ", "NAS100;rm", "x" * 40)),
      "alle Firmen bis heute (NAS100, TECH100, MNQ, leer) und Ungültiges → [EURUSD] (bitgleich)")
check(C({"startup_symbol": "EURUSD.x"}) == "EURUSD.x" and C({}) == "EURUSD" and C(None) == "EURUSD" and C({"startup_symbol": "a\nb"}) == "EURUSD",
      "Config-Feld startup_symbol, sonst / ungültig → EURUSD")
check(provision.build_startup_ini(symbol=provision.STARTUP_SYMBOL, preset="p.set") == provision.build_startup_ini(preset="p.set")
      and "Symbol=EURUSD.x\n" in provision.build_startup_ini(symbol="EURUSD.x", preset="p.set"), "Start-ini: EURUSD bitgleich, EURUSD.x eingesetzt")

print("2) run_provision (Quelltext)")
SRC = open(os.path.join(HIER, "provision.py"), encoding="utf-8").read()
rp = SRC[SRC.index("def run_provision("):]
rp = rp[:rp.index("\ndef ", 10)] if "\ndef " in rp[10:] else rp
check("startup_symbols=None" in rp and "or [STARTUP_SYMBOL]" in rp, "neuer Parameter startup_symbols, ohne Angabe [EURUSD]")
check(rp.count("build_startup_ini(symbol=sym_liste[0], preset=preset_name)") == 2, "Start-ini und Servername-Variante mit dem ersten Start-Symbol")
ret = rp[rp.index("if not _wait_snapshot(60):"):rp.index('report("neustart", "done"')]
check("build_login_ini(login, password, server)" in ret and "build_startup_ini(symbol=sym, preset=preset_name)" in ret
      and "build_startup_ini(preset=preset_name))" not in ret, "Retry-ini MIT Login (Passwort) — nie mehr ohne")
check("weiter = sym_liste[1:] or [sym_liste[0]]" in ret and "symbol_ok, geschafft = sym, True" in ret, "je weiterem Start-Symbol ein Anlauf, sonst genau einer wie bisher")
check('if symbol_ok != STARTUP_SYMBOL:\n        cfg["startup_symbol"] = symbol_ok' in rp, "Config merkt startup_symbol nur, wenn ≠ EURUSD (bitgleich)")
check("for p in (start_ini, retry_ini):" in rp, "beide ini-Dateien (mit Passwort) werden im finally gelöscht")

print("3) panel.py")
PSRC = open(os.path.join(HIER, "panel.py"), encoding="utf-8").read()
check('fsym = str(body.get("startup_symbol") or "").strip()[:32]' in PSRC and "firmen_symbol=fsym or None" in PSRC, "/api/provision nimmt startup_symbol (geprüft) an")
check("def prov_start(name, login, password, server, owner=None, display=None, firmen_symbol=None):" in PSRC
      and '{"startup_symbols": provision.startup_symbole(firmen_symbol)} if firmen_symbol' in PSRC, "prov_start reicht die Kandidaten an run_provision")
check(PSRC.count("provision.build_startup_ini(symbol=_startup_symbol(cfg), preset=preset)") == 2
      and "provision.build_startup_ini(preset=preset)" not in PSRC, "beide Heil-Wege ziehen das EA auf das Start-Symbol der Config")
baum = ast.parse(PSRC)
ns = {"provision": provision}
fd = next(x for x in baum.body if isinstance(x, ast.FunctionDef) and x.name == "_startup_symbol")
exec(compile(ast.Module(body=[fd], type_ignores=[]), "panel.py", "exec"), ns)
check(ns["_startup_symbol"]({"startup_symbol": "EURUSD.x"}) == "EURUSD.x" and ns["_startup_symbol"]({}) == "EURUSD", "_startup_symbol: Config-Wert, sonst EURUSD")
ns2 = {"provision": type("P", (), {"STARTUP_SYMBOL": "EURUSD"})}
exec(compile(ast.Module(body=[fd], type_ignores=[]), "panel.py", "exec"), ns2)
check(ns2["_startup_symbol"]({"startup_symbol": "EURUSD.x"}) == "EURUSD", "älteres provision.py ohne Helfer → EURUSD (kein Absturz)")

print("4) prophos.html (JavaScriptCore)")
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
i = HTML.index("  function mt5StartSymbol(")
fn = HTML[i:HTML.index("\n  }\n", i) + 4]
js = "var window = {};\n" + fn + r"""
window._getCustomFirms = () => [{name: 'Goat Funded Trader', symbol: 'NAS100.x', server: 'GoatFunded-Server'}, {name: 'FTMO', symbol: 'NAS100', server: 'FTMO-Server'},
  {name: 'FundedNext', symbol: '', server: ''}, {name: 'Böse', symbol: 'NAS;100', server: 'X'}]
print(JSON.stringify([mt5StartSymbol('Goat Funded Trader', ''), mt5StartSymbol('', 'goatfunded-server'), mt5StartSymbol('FTMO', ''), mt5StartSymbol('FundedNext', ''),
  mt5StartSymbol('Unbekannt', 'Nix'), mt5StartSymbol('Böse', '')]))
window._getCustomFirms = undefined
print(JSON.stringify(mt5StartSymbol('Goat Funded Trader', '')))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(js)
out = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", f.name], capture_output=True, text=True)
os.unlink(f.name)
zeilen = out.stdout.strip().splitlines()
check(zeilen[:1] == ['["NAS100.x","NAS100.x","NAS100","","",""]'], f"Symbol nach Firma, sonst nach Server; leer/ungültig → '' ({zeilen[:1] or out.stderr[:120]})")
check(zeilen[1:2] == ['""'], "ohne Firmen-Liste → '' (Panel bleibt bei EURUSD)")
check("const _ss = mt5StartSymbol(acc.firm, acc.creds.server); if(_ss) body.startup_symbol = _ss" in HTML
      and "window._mt5StartSymbol?.(_pa && _pa.firm, body.server); if(_ss) body.startup_symbol = _ss" in HTML,
      "Konto anlegen / Echo-Signal (mt5CreateAccountInCopier) und „Echo hinzufügen“ von Hand schicken das Firmen-Symbol")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
