#!/usr/bin/env python3
"""Selbsttest MI1 (25.11.2026): MT5-Login für Zugangsdaten mit Sonderzeichen/Umlauten über die MetaTrader5-Python-API statt der
Start-ini (die nur ASCII trägt). Anlass: Amir · Blue Guardian 100k …1977/…1978 · Emin — „Zugangsdaten enthalten Sonderzeichen/Umlaute
— die MT5-Start-ini kann nur ASCII“. Prüft:
  · mi1_api_login_moeglich: nur Konto-Nummer + vorhandenes Paket
  · _mi1_api_login mit nachgebautem MetaTrader5: Erfolg, falsches Konto, Fehlschlag, Lock belegt, Terminal kommt nicht hoch —
    und NIE das Passwort in der Ausgabe
  · build_experts_ini: kein Login/Passwort, reines ASCII
  · start_terminal: Nicht-ASCII-Prüfung bleibt VOR jedem Kill, API-Zweig schreibt keine Zugangsdaten in die ini, ASCII-Zweig
    (elif creds:) ist Zeichen für Zeichen der alte Zwangs-Login-Zweig von origin/main
Aufruf:  python3 mt5-copier/selftest_mi1_api_login.py   (ohne Netz, ohne Windows)"""
import importlib.machinery
import io
import os
import random
import re
import subprocess
import sys
import threading
import time
import types
from contextlib import redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HIER, "panel.py"), encoding="utf-8").read()
PROV = open(os.path.join(HIER, "provision.py"), encoding="utf-8").read()
FEHLER = []
PW = "Pässwört§€x9"


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


# ── Lader ──
ns = {"os": os, "time": time, "random": random, "threading": threading}
for z in ("MI1_BOOT_WARTE_S", "MI1_BOOT_RUHE_S", "MI1_INIT_TIMEOUT_MS", "MI1_VERSUCHE"):
    exec(re.search(r"^" + z + r" = [^\n#]*", SRC, re.M).group(0), ns)
ns["MI1_BOOT_RUHE_S"] = (0.0, 0.0)
ns["_MT5_INPROC_LOCK"] = threading.Lock()
ns["HEAL_LOCK"], ns["HEAL_ACTIVE"] = threading.Lock(), set()
exec(fn(SRC, "mi1_api_login_moeglich"), ns)
exec(fn(SRC, "_mi1_api_login"), ns)
pns = {}
exec(fn(PROV, "build_experts_ini"), pns)
ns["time"] = types.SimpleNamespace(time=time.time, sleep=lambda s: None)   # keine echten Pausen
ns["random"] = types.SimpleNamespace(uniform=lambda a, b: 0.0)


class FakeMt5(types.ModuleType):
    def __init__(self, konto_nach_login=None, init_ok=True):
        super().__init__("MetaTrader5")
        self.__spec__ = importlib.machinery.ModuleSpec("MetaTrader5", None)
        self.konto_nach_login, self.init_ok, self.aufrufe, self.shutdowns = konto_nach_login, init_ok, [], 0

    def initialize(self, **kw):
        self.aufrufe.append(dict(kw))
        return self.init_ok

    def account_info(self):
        return None if self.konto_nach_login is None else types.SimpleNamespace(login=self.konto_nach_login)

    def last_error(self):
        return (-6, "Terminal: Authorization failed")

    def shutdown(self):
        self.shutdowns += 1


def lauf(mt5, pids=(4711,), creds=None):
    sys.modules["MetaTrader5"] = mt5
    ns["provision"] = types.SimpleNamespace(terminal_pids=lambda d: list(pids))
    out = io.StringIO()
    with redirect_stdout(out):
        r = ns["_mi1_api_login"]("config-x.json", r"C:\MT5-Master\terminal64.exe", r"C:\MT5-Master",
                                 creds or {"login": "631977", "password": PW, "server": "BlueGuardian-Server"})
    return r, out.getvalue()


# ── mi1_api_login_moeglich ──
sys.modules["MetaTrader5"] = FakeMt5()
M = ns["mi1_api_login_moeglich"]
check(M("631977") is True, "Konto-Nummer + Paket → API-Login möglich")
check(M("abc") is False and M("") is False and M(None) is False, "ohne Konto-Nummer → nicht möglich (alte Ansage)")
del sys.modules["MetaTrader5"]
_alt_finder = sys.meta_path[:]
sys.meta_path[:] = []                       # Paket „nicht installiert“
try:
    check(M("631977") is False, "ohne MetaTrader5-Paket → nicht möglich (alte Ansage, kein Kill)")
finally:
    sys.meta_path[:] = _alt_finder

# ── _mi1_api_login ──
m = FakeMt5(konto_nach_login=631977)
r, out = lauf(m)
check(r is True and len(m.aufrufe) == 1, "Erfolg im ersten Versuch")
a = m.aufrufe[0]
check(a.get("login") == 631977 and a.get("password") == PW and a.get("server") == "BlueGuardian-Server"
      and a.get("path", "").endswith("terminal64.exe") and a.get("timeout") == 30000,
      "initialize mit path/login(int)/Unicode-Passwort/server/timeout 30 s")
check(m.shutdowns == 1, "danach shutdown (Terminal bleibt eingeloggt)")
check(PW not in out and "Pässwört" not in out and "eingeloggt" in out, "Ausgabe ohne Passwort, mit Erfolgsmeldung")

m = FakeMt5(konto_nach_login=999999)
r, out = lauf(m)
check(r is False and len(m.aufrufe) == 2 and m.shutdowns == 2, "falsches Konto → nicht ok, 2 Versuche, je shutdown")
check(PW not in out and "anderes Konto" in out, "falsches Konto: Meldung ohne Passwort")

m = FakeMt5(init_ok=False)
r, out = lauf(m)
check(r is False and len(m.aufrufe) == 2, "initialize scheitert → 2 Versuche, False")
check(PW not in out and "Authorization failed" in out, "Fehler: last_error im Log, Passwort nie")

m = FakeMt5(konto_nach_login=631977)
r, out = lauf(m, creds={"login": "631977", "password": PW, "server": ""})
check(r is True and "server" not in m.aufrufe[0], "ohne Server → initialize ohne server (Terminal nimmt seinen)")

m = FakeMt5(konto_nach_login=631977)
ns["MI1_BOOT_WARTE_S"] = 0
r, out = lauf(m, pids=())
ns["MI1_BOOT_WARTE_S"] = 90
check(r is False and not m.aufrufe and "kam nicht hoch" in out, "Terminal-Prozess fehlt → nichts versucht")

m = FakeMt5(konto_nach_login=631977)
r, out = lauf(m, creds={"login": "x1", "password": PW, "server": "S"})
check(r is False and not m.aufrufe and PW not in out, "Login ohne Nummer → nichts versucht, kein Passwort im Log")

ns["HEAL_ACTIVE"].add(r"C:\MT5-Master")
m = FakeMt5(konto_nach_login=631977)
r, out = lauf(m)
ns["HEAL_ACTIVE"].clear()
check(r is False and not m.aufrufe and "heilt gerade" in out, "Instanz heilt gerade → kein Anschluss (initialize startete sonst selbst)")

lock = ns["_MT5_INPROC_LOCK"]
lock.acquire()
_alt_acq = ns["_MT5_INPROC_LOCK"]
ns["_MT5_INPROC_LOCK"] = types.SimpleNamespace(acquire=lambda timeout=None: False, release=lambda: None)
m = FakeMt5(konto_nach_login=631977)
r, out = lauf(m)
ns["_MT5_INPROC_LOCK"] = _alt_acq
lock.release()
check(r is False and not m.aufrufe and "belegt" in out, "In-Prozess-Lock belegt → kein initialize")

class Kaputt(FakeMt5):
    def initialize(self, **kw):
        raise RuntimeError("Login=631977 Password=" + kw.get("password", ""))
r, out = lauf(Kaputt())
check(r is False and PW not in out and "RuntimeError" in out, "Ausnahme mit Passwort im Text → nur der Typ im Log")

# ── build_experts_ini ──
e = pns["build_experts_ini"]()
check(e.isascii() and "[Experts]" in e and "Password" not in e and "Login" not in e and "[Common]" not in e,
      "Experts-ini: reines ASCII, keine Zugangsdaten")
check(e in fn(PROV, "build_login_ini").replace('"[Experts]\\nEnabled=1\\nAllowLiveTrading=1\\n"', e),
      "Experts-Block = derselbe wie in build_login_ini")
check('"[Experts]\\nEnabled=1\\nAllowLiveTrading=1\\n"' in fn(PROV, "build_login_ini"), "build_login_ini unverändert (Experts-Block drin)")

# ── start_terminal ──
st = fn(SRC, "start_terminal")
i_pruef = st.index("api_creds = None")
i_kill = st.index("provision.terminal_pids(install_dir)")
check(i_pruef < i_kill, "Nicht-ASCII-Prüfung VOR jedem Kill")
check("mi1_api_login_moeglich(creds.get(\"login\"))" in st and "kann nur ASCII" in st, "ohne API-Möglichkeit: alte Ansage bleibt")
api = st[st.index("        if api_creds:"):st.index("        elif creds:")]
check("build_experts_ini()" in api and "build_login_ini" not in api and "password" not in api.lower().replace("api_creds", ""),
      "API-Zweig: ini ohne Zugangsdaten")
check("_mi1_api_login" in api and "_remove_later(ini)" in api and "Popen([path, f\"/config:{ini}\"]" in api,
      "API-Zweig: Start mit Experts-ini, ini wird weggeräumt, Login-Thread")
try:
    alt = subprocess.run(["git", "-C", HIER, "show", "origin/main:mt5-copier/panel.py"], capture_output=True, text=True, timeout=30).stdout
    alt_st = fn(alt, "start_terminal") if alt else ""
except Exception:
    alt_st = ""
if alt_st and "api_creds" not in alt_st:
    a0 = alt_st.index("        if creds:\n            # Login-Zwang")
    a1 = alt_st.index("        else:\n            # Auch OHNE hinterlegte Zugangsdaten")
    n0 = st.index("        elif creds:\n            # Login-Zwang")
    n1 = st.index("        else:\n            # Auch OHNE hinterlegte Zugangsdaten")
    check(alt_st[a0 + len("        if creds:"):a1] == st[n0 + len("        elif creds:"):n1], "ASCII-Zweig bitgleich zu origin/main")
    neu_rest = (st[st.index("    install_dir = os.path.dirname"):].replace(api, "").replace("        elif creds:\n            # Login-Zwang", "X")
                .replace("        if expected and not api_creds:", "        if expected:"))
    neu_rest = re.sub(r"\n        # MI1 \(Review SOLLTE 1\)[^\n]*", "", neu_rest)
    neu_rest = neu_rest.replace("— nur mit bekanntem Konto.\n", "— nur mit bekanntem Konto\n")
    check(alt_st[alt_st.index("    install_dir = os.path.dirname"):].replace("        if creds:\n            # Login-Zwang", "X") == neu_rest,
          "Rest von start_terminal ab install_dir unverändert (bis auf API-Zweig + Login-Wache nur ohne API)")
    check("if expected and not api_creds:" in st, "Login-Fenster-Wache nicht im API-Zweig")
elif alt_st:
    print("· origin/main trägt MI1 schon — Bitgleich-Vergleich gegen den Vor-MI1-Stand entfällt")
else:
    check(False, "origin/main nicht lesbar — Bitgleich-Vergleich NICHT geprüft (git fetch?)")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
