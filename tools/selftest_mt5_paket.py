#!/usr/bin/env python3
"""Selbsttest METATRADER5-PAKET IM PANEL-PYTHON (mt5-copier/panel.py MT5_PAKET / _mt5_paket_pruefen / ensure_metatrader5,
order_bot._api_lesen, 08.10.2026, Slave-Terminal 4 — Jacob The5%ers rot: „MetaTrader5-Paket fehlt" im Order-Bot, Copier liefen weiter).
Ohne Windows: os.name und subprocess werden nachgebildet, dazu ein echter Lauf der Import-Probe (auf dem Mac fehlt MetaTrader5).
Geprüft: (1) Import ok → ok/Version, kein pip; (2) Import kaputt → pip install --upgrade MetaTrader5 mit DEM Python, danach erneut
geprüft → ok + installiert_at (nur wenn pip show es nicht kennt, ohne --upgrade); (3b) installiert, Import bricht → nie installieren;
(3) pip scheitert → ok False, Fehlertext, sichtbare Konsolen-Zeile, höchstens eine Installation je
Stunde; (4) echte Probe liefert den letzten stderr-Satz; (5) Quelltext: Wächter-Thread beim Start, Snapshot mt5_update.paket ohne
interne Schlüssel, Bot-Meldung nennt Grund + Python und beginnt weiter mit „MetaTrader5-Paket fehlt".
Aufruf: python3 tools/selftest_mt5_paket.py"""
import os
import sys
import time
import types
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HIER, "..", "mt5-copier", "panel.py")
BOT = os.path.join(HIER, "..", "mt5-copier", "order_bot.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


class Lauf:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


SAC = "ImportError: DLL load failed while importing _core: Eine Anwendungssteuerungsrichtlinie hat diese Datei blockiert."


def welt(import_ok_folge, pip_ok=True, pip_kennt=False, import_fehler=None):
    """subprocess-Nachbau: Import-Probe liefert der Reihe nach import_ok_folge, pip show je nach pip_kennt, pip install je nach pip_ok."""
    aufrufe, folge = [], list(import_ok_folge)

    def run(cmd, **kw):
        aufrufe.append(cmd)
        if cmd[1:4] == ["-m", "pip", "show"]:
            return Lauf(0 if pip_kennt else 1, "Name: MetaTrader5" if pip_kennt else "", "" if pip_kennt else "WARNING: Package(s) not found")
        if cmd[1:3] == ["-m", "pip"]:
            return Lauf(0 if pip_ok else 1, "", "" if pip_ok else "ERROR: No matching distribution")
        ok = folge.pop(0) if folge else False
        return Lauf(0, "5.0.5260\n", "") if ok else Lauf(1, "", "Traceback ...\n" + (import_fehler or "ImportError: DLL load failed while importing _core: x"))
    return types.SimpleNamespace(run=run), aufrufe


def lade(sub, ausgaben):
    src = open(PANEL, encoding="utf-8").read()
    teil = src[src.index("\nMT5_PAKET = {"):src.index("\ndef _ensure_ea_compiled(")]
    ns = {"os": types.SimpleNamespace(name="nt"), "sys": sys, "time": time, "datetime": datetime, "subprocess": sub, "HERE": HIER,
          "print": lambda *a, **k: ausgaben.append(" ".join(str(x) for x in a))}
    exec(teil, ns)
    return src, ns


def main():
    # 1 Import ok
    sub, auf = welt([True])
    out = []
    _, ns = lade(sub, out)
    ns["ensure_metatrader5"]()
    p = ns["MT5_PAKET"]
    check(p["ok"] is True and p["version"] == "5.0.5260" and p["fehler"] is None and p["at"], f"Import ok → ok/Version ({p['version']})")
    check(not any(c[1:3] == ["-m", "pip"] for c in auf) and not out, "kein pip (auch kein pip show), keine Meldung")
    check(auf[0][0] == sys.executable and auf[0][1] == "-c", "Probe als eigener Prozess mit dem Panel-Python (wie der Order-Bot)")

    # 2 Import kaputt → pip → wieder da
    sub, auf = welt([False, True])
    out = []
    _, ns = lade(sub, out)
    ns["ensure_metatrader5"]()
    p = ns["MT5_PAKET"]
    pip = [c for c in auf if c[1:4] == ["-m", "pip", "install"]]
    check(pip == [[sys.executable, "-m", "pip", "install", "MetaTrader5"]], f"fehlt laut pip show → pip install MetaTrader5 OHNE --upgrade mit DEM Python ({pip})")
    check(p["ok"] is True and p["installiert_at"], "nach der Installation erneut geprüft → ok, installiert_at gesetzt")
    check(any("installiere" in z for z in out), "Konsole meldet die Installation")

    # 3 pip scheitert → sichtbar, höchstens einmal je Stunde
    sub, auf = welt([False, False, False], pip_ok=False)
    out = []
    _, ns = lade(sub, out)
    ns["ensure_metatrader5"]()
    p = ns["MT5_PAKET"]
    check(p["ok"] is False and "DLL load failed" in (p["fehler"] or ""), f"ok False mit echtem Grund ({p['fehler']})")
    check(any("⚠ MetaTrader5-Paket fehlt" in z and "-m pip install MetaTrader5" in z for z in out), "sichtbare Konsolen-Zeile mit Befehl")
    ns["ensure_metatrader5"]()
    check(len([c for c in auf if c[1:4] == ["-m", "pip", "install"]]) == 1, "zweite Prüfung innerhalb einer Stunde installiert nicht erneut")

    # 3b installiert, Import bricht (DLL/numpy/Schatten-Datei) → NIE installieren, nur melden (Prüfer Slave 2: gesperrte Dateien der Copier)
    sub, auf = welt([False, False], pip_kennt=True)
    out = []
    _, ns = lade(sub, out)
    ns["ensure_metatrader5"]()
    p = ns["MT5_PAKET"]
    check(not [c for c in auf if c[1:4] == ["-m", "pip", "install"]] and p["ok"] is False and p["pip_kennt"] is True,
          "installiert + Import kaputt → kein pip install, pip_kennt True")
    check(any("NICHT neu installieren" in z for z in out), "Konsole: nicht neu installieren, Fehler melden")
    check(not any(k.startswith("_") for k in {k: v for k, v in p.items() if not k.startswith("_")}), "interne Schlüssel bleiben intern")

    # 3c Windows-App-Steuerung blockt die DLL (Jacobs PC 08.10.2026) → eigener Grund, weder pip show noch pip install
    sub, auf = welt([False, False], pip_kennt=True, import_fehler=SAC)
    out = []
    _, ns = lade(sub, out)
    ns["ensure_metatrader5"]()
    p = ns["MT5_PAKET"]
    check(p["ok"] is False and p["app_sperre"] is True and not [c for c in auf if c[1:3] == ["-m", "pip"]],
          "App-Steuerung blockt → app_sperre, kein pip (weder show noch install)")
    check(any("Windows blockiert MetaTrader5" in z and "Intelligente App-Steuerung" in z for z in out), "Konsole nennt Windows-Sperre + Weg")
    check(ns["_app_steuerung_sperre"]("[WinError 4551] An Application Control policy has blocked this file") and not ns["_app_steuerung_sperre"]("No module named x")
          and not ns["_app_steuerung_sperre"](r"DLL load failed: C:\MT5-4551\x.pyd"),
          "Erkennung auch englisch / [WinError 4551], nicht bei fehlendem Modul oder 4551 im Pfad")

    # 4 echte Probe (Mac ohne MetaTrader5)
    import subprocess
    _, ns = lade(subprocess, [])
    ok, ver, fehler = ns["_mt5_paket_pruefen"]()
    try:
        import MetaTrader5  # noqa: F401
        da = True
    except ImportError:
        da = False
    check(ok == da and (da or "MetaTrader5" in (fehler or "")), f"echte Probe: letzter stderr-Satz ({fehler})")

    # 5 Quelltext
    src = open(PANEL, encoding="utf-8").read()
    check("threading.Thread(target=_mt5_paket_waechter, daemon=True).start()" in src, "Wächter-Thread beim Panel-Start")
    seg = src[src.index("\ndef _mt5_update_stand("):src.index("\n\n\n", src.index("\ndef _mt5_update_stand("))]
    check(seg.count("paket={k: v for k, v in MT5_PAKET.items() if not k.startswith(\"_\")}") == 2,
          "Snapshot mt5_update.paket (auch aus dem 5-min-Zwischenspeicher)")
    bot = open(BOT, encoding="utf-8").read()
    check('return {"fehler": f"MetaTrader5-Paket fehlt (nur auf dem PC lauffaehig). {str(e)[:160]} · Python {sys.executable}"}' in bot,
          "Bot-Meldung: gleicher Anfang + echter Grund + Python")
    check("if _app_steuerung_sperre(e):" in bot and "Windows blockiert MetaTrader5 (Intelligente App-Steuerung)" in bot,
          "Bot meldet die Windows-Sperre als eigenen Grund")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
