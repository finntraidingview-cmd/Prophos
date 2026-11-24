#!/usr/bin/env python3
"""Selbsttest MI1 (25.11.2026): MT5-Login für Zugangsdaten mit Sonderzeichen/Umlauten über die MetaTrader5-Python-API statt der
Start-ini (die nur ASCII trägt). Anlass: Amir · Blue Guardian 100k …1977/…1978 · Emin — „Zugangsdaten enthalten Sonderzeichen/Umlaute
— die MT5-Start-ini kann nur ASCII“. Prüft (echter Quelltext aus panel.py/provision.py, alles Fremde nachgebaut):
  A mi1_api_login_moeglich / build_experts_ini
  B _mi1_api_login allein: Erfolg, falsches Konto, Fehlschlag, Lock belegt, Terminal fehlt, Ausnahme — NIE das Passwort in der Ausgabe
  C ZUSAMMENSPIEL (Prüfer-Stopp 25.11.2026): start_terminal → Login-Thread → Heilung erst NACH dem Login (kein HEAL_ACTIVE vorher) →
    Snapshot fließt nicht → Heil-Neustart → wieder API-Login (aus_heilung, trotz eigenem HEAL_ACTIVE) statt nackt; ein zweiter
    Start/Heilung während eines MI1-Logins heilt nicht dazwischen; ASCII-Weg startet wie bisher Heilung + Login-Wache sofort
  D ASCII-Zwangs-Login-Zweig Zeichen für Zeichen wie auf origin/main
Aufruf:  python3 mt5-copier/selftest_mi1_api_login.py   (ohne Netz, ohne Windows)"""
import importlib.machinery
import io
import os
import re
import subprocess
import sys
import tempfile
import threading
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


class Uhr:
    """Nachgebaute Zeit: sleep rückt die Uhr vor, nichts wartet echt."""
    def __init__(self):
        self.t = 1_800_000_000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += max(float(s), 0.01)


class Faden:
    """Nachgebauter Thread: merkt sich, was gestartet würde; ausgeführt wird von Hand (Reihenfolge wie im Leben)."""
    gestartet = []

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target, self.args, self.kwargs = target, tuple(args), dict(kwargs or {})

    def start(self):
        Faden.gestartet.append(self)

    def lauf(self):
        return self.target(*self.args, **self.kwargs)


class FakeMt5(types.ModuleType):
    def __init__(self, konto_nach_login=None, init_ok=True, beim_init=None):
        super().__init__("MetaTrader5")
        self.__spec__ = importlib.machinery.ModuleSpec("MetaTrader5", None)
        self.konto_nach_login, self.init_ok, self.aufrufe, self.shutdowns, self.beim_init = konto_nach_login, init_ok, [], 0, beim_init

    def initialize(self, **kw):
        self.aufrufe.append(dict(kw))
        if self.beim_init:
            self.beim_init()
        return self.init_ok

    def account_info(self):
        return None if self.konto_nach_login is None else types.SimpleNamespace(login=self.konto_nach_login)

    def last_error(self):
        return (-6, "Terminal: Authorization failed")

    def shutdown(self):
        self.shutdowns += 1


# ── Lader: echte Funktionen + Nachbauten ──
TMP = tempfile.mkdtemp(prefix="mi1-")
INST = os.path.join(TMP, "MT5-Master")
DATA = os.path.join(TMP, "data")
os.makedirs(INST)
os.makedirs(os.path.join(DATA, "MQL5", "Experts"))
open(os.path.join(INST, "terminal64.exe"), "w").close()
open(os.path.join(DATA, "MQL5", "Experts", "ProphosHedgeReader.ex5"), "w").close()
EXE = os.path.join(INST, "terminal64.exe")

uhr = Uhr()
POPEN, KILLS = [], []
ZUSTAND = {"pids": [4711]}
prov = types.SimpleNamespace(
    INI_ENCODING="ascii", SET_ENCODING="ascii", EA_NAME="ProphosHedgeReader",
    terminal_pids=lambda d: list(ZUSTAND["pids"]),
    _taskkill=lambda pid, grace_s=15: KILLS.append(pid),
    data_dir_for=lambda d: DATA,
    build_startup_ini=lambda **kw: "[StartUp]\nExpert=ProphosHedgeReader\n",
    build_preset=lambda snap: "InpFileName=" + snap + "\n")
pns = {}
exec(fn(PROV, "build_login_ini"), pns)
exec(fn(PROV, "build_experts_ini"), pns)
prov.build_login_ini, prov.build_experts_ini = pns["build_login_ini"], pns["build_experts_ini"]

ns = {"os": os, "re": re, "time": uhr, "random": types.SimpleNamespace(uniform=lambda a, b: 0.0),
      "threading": types.SimpleNamespace(Thread=Faden, Lock=threading.Lock), "provision": prov,
      "subprocess": types.SimpleNamespace(Popen=lambda args, cwd=None: POPEN.append(list(args))),
      "HERE": TMP, "datetime": __import__("datetime").datetime,
      "HEAL_LOCK": threading.Lock(), "HEAL_ACTIVE": set(), "UPDATE_LAEUFT": set(), "_MT5_INPROC_LOCK": threading.Lock()}
for z in ("MI1_BOOT_WARTE_S", "MI1_BOOT_RUHE_S", "MI1_INIT_TIMEOUT_MS", "MI1_VERSUCHE"):
    exec(re.search(r"^" + z + r" = [^\n#]*", SRC, re.M).group(0), ns)
exec(re.search(r"^_MI1_LAEUFT = [^\n#]*", SRC, re.M).group(0), ns)
exec(re.search(r"^_MI1_NULLBREITE = [^\n]*", SRC, re.M).group(0), ns)
for name in ("mi1_feld_norm", "mi1_api_login_moeglich", "_mi1_api_login", "_mi1_reservieren", "_mi1_thread", "_mi1_nach_heil_start",
             "_mi1_api_login_inner", "_heal_ea", "_heal_ea_inner", "start_terminal", "_instanz_heilt"):
    exec(fn(SRC, name), ns)
CFG = {"master_terminal_path": EXE, "master_expected_login": 631977, "snapshot_file": "prophos_master.csv",
       "common_files_dir": os.path.join(TMP, "common"), "master_server": "BlueGuardian-Server"}
ns.update(
    EA_FROST_HAELT=set(),
    read_json=lambda p, d=None: dict(CFG),
    _drop_snapshot=lambda cfg: None, _fenster_nach_vorn=lambda pid: True, _ensure_ea_compiled=lambda f, d: None,
    _update_vor_start_noetig=lambda d: None, _update_abwarten=lambda d: None, _vor_kaltstart=lambda f, d: None,
    _inject_ea_into_profile=lambda f, c, d: True, _startup_attach_part=lambda f, c, d: "", _remove_later=lambda p, delay_s=90: None,
    _ok_dialog_watcher=lambda d: None, _login_ok_wache=lambda f, e, d: None, _front_when_up=lambda d: None,
    _update_dann_start=lambda *a: None, _update_einspielen=lambda f, a: None)
def _ok_dialog_watcher(d):
    return None


def _login_ok_wache(f, e, d):
    return None


ns.update(_ok_dialog_watcher=_ok_dialog_watcher, _login_ok_wache=_login_ok_wache)   # mit Namen, damit die Thread-Ziele lesbar sind
ASCII = {"login": "631977", "password": "Abc123xyz", "server": "BlueGuardian-Server"}
UNI = {"login": "631977", "password": PW, "server": "BlueGuardian-Server"}


def mit_mt5(m):
    sys.modules["MetaTrader5"] = m
    return m


def ausgabe(f, *a, **kw):
    out = io.StringIO()
    with redirect_stdout(out):
        r = f(*a, **kw)
    return r, out.getvalue()


def ziel(t):
    return getattr(t.target, "__name__", "?")


# ── A ──
mit_mt5(FakeMt5())
M = ns["mi1_api_login_moeglich"]
check(M("631977") is True, "A1 Konto-Nummer + Paket → API-Login möglich")
check(M("abc") is False and M("") is False and M(None) is False, "A2 ohne Konto-Nummer → nicht möglich (alte Ansage)")
del sys.modules["MetaTrader5"]
_alt = sys.meta_path[:]
sys.meta_path[:] = []
try:
    check(M("631977") is False, "A3 ohne MetaTrader5-Paket → nicht möglich")
finally:
    sys.meta_path[:] = _alt
e = prov.build_experts_ini()
check(e.isascii() and "[Experts]" in e and "Password" not in e and "[Common]" not in e, "A4 Experts-ini: ASCII, keine Zugangsdaten")
check('"[Experts]\\nEnabled=1\\nAllowLiveTrading=1\\n"' in fn(PROV, "build_login_ini"), "A5 build_login_ini unverändert")

# ── B: _mi1_api_login allein ──
L = ns["_mi1_api_login"]
m = mit_mt5(FakeMt5(konto_nach_login=631977))
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
a = m.aufrufe[0] if m.aufrufe else {}
check(r is True and len(m.aufrufe) == 1 and m.shutdowns == 1, "B1 Erfolg im ersten Versuch, danach shutdown")
check(a.get("login") == 631977 and a.get("password") == PW and a.get("server") == "BlueGuardian-Server" and a.get("timeout") == 30000,
      "B2 initialize mit login(int)/Unicode-Passwort/server/30 s")
check(PW not in out and "eingeloggt" in out, "B3 Ausgabe ohne Passwort")
m = mit_mt5(FakeMt5(konto_nach_login=999999))
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
check(r is False and len(m.aufrufe) == 2 and PW not in out and "anderes Konto" in out, "B4 falsches Konto → 2 Versuche, kein Passwort")
m = mit_mt5(FakeMt5(init_ok=False))
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
check(r is False and len(m.aufrufe) == 2 and PW not in out and "Authorization failed" in out, "B5 Fehlschlag: last_error, kein Passwort")
m = mit_mt5(FakeMt5(konto_nach_login=631977))
ZUSTAND["pids"] = []
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
ZUSTAND["pids"] = [4711]
check(r is False and not m.aufrufe and "kam nicht hoch" in out, "B6 Terminal-Prozess fehlt → nichts versucht")
ns["HEAL_ACTIVE"].add(INST)
m = mit_mt5(FakeMt5(konto_nach_login=631977))
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
check(r is False and not m.aufrufe and "heilt gerade" in out, "B7 fremde Heilung läuft → kein Anschluss")
m = mit_mt5(FakeMt5(konto_nach_login=631977))
r, out = ausgabe(L, "c.json", EXE, INST, UNI, aus_heilung=True)
ns["HEAL_ACTIVE"].clear()
check(r is True and len(m.aufrufe) == 1, "B8 aus der Heilung selbst (aus_heilung) → trotz HEAL_ACTIVE eingeloggt")
_lock = ns["_MT5_INPROC_LOCK"]
ns["_MT5_INPROC_LOCK"] = types.SimpleNamespace(acquire=lambda timeout=None: False, release=lambda: None)
m = mit_mt5(FakeMt5(konto_nach_login=631977))
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
ns["_MT5_INPROC_LOCK"] = _lock
check(r is False and not m.aufrufe and "belegt" in out, "B9 In-Prozess-Lock belegt → kein initialize")


class Kaputt(FakeMt5):
    def initialize(self, **kw):
        raise RuntimeError("Password=" + kw.get("password", ""))


mit_mt5(Kaputt())
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
check(r is False and PW not in out and "RuntimeError" in out, "B10 Ausnahme mit Passwort im Text → nur der Typ im Log")
ns["_MI1_LAEUFT"].add(INST)
m = mit_mt5(FakeMt5(konto_nach_login=631977))
r, out = ausgabe(L, "c.json", EXE, INST, UNI)
ns["_MI1_LAEUFT"].clear()
check(r is False and not m.aufrufe and "läuft schon" in out, "B11 zweiter MI1-Login derselben Instanz → keiner")
check(not ns["_MI1_LAEUFT"] and not ns["HEAL_ACTIVE"], "B12 Merker nach jedem Lauf leer")

# ── C: Zusammenspiel start_terminal → Login → Heilung → Heil-Neustart → Login ──
ST = ns["start_terminal"]
Faden.gestartet.clear(); POPEN.clear(); KILLS.clear()
ZUSTAND["pids"] = []                                       # Terminal aus → Kaltstart
mit_mt5(FakeMt5(konto_nach_login=631977))
(ok, msg), out = ausgabe(ST, "config-x.json", UNI)
ziele = [ziel(t) for t in Faden.gestartet]
check(ok is True and "MT5-Schnittstelle" in msg and PW not in msg + out, "C1 start_terminal (Unicode): gestartet, Meldung ohne Passwort")
check(ziele.count("_mi1_api_login") == 1 and "_heal_ea" not in ziele and "_login_ok_wache" not in ziele,
      f"C2 sofort NUR Login-Thread (keine Heilung, keine OK-Wache): {ziele}")
check(not ns["HEAL_ACTIVE"], "C3 HEAL_ACTIVE nach start_terminal leer (Prüfer-Stopp: Login brach daran ab)")
check(INST in ns["_MI1_LAEUFT"], "C3b MI1-Merker steht schon VOR dem Login-Thread (keine Lücke)")
check(ns["_instanz_heilt"]({"config_file": "config-x.json"}) is True, "C3c Order/Close: Instanz gilt während des Logins als „heilt“ (409 gleich erneut)")
check(SRC.count("heilt = bool(inst_dir) and (inst_dir in HEAL_ACTIVE or inst_dir in _MI1_LAEUFT)") == 2,
      "C3d V2-Order- und V2-Close-Riegel zählen den MI1-Login mit")
check(POPEN and POPEN[-1][0] == EXE and POPEN[-1][1].startswith("/config:"), "C4 Terminal mit /config-ini gestartet")
lt = next(t for t in Faden.gestartet if ziel(t) == "_mi1_api_login")
check(lt.kwargs.get("heal_nach") is True and lt.kwargs.get("cfg") is not None and lt.kwargs.get("reserviert") is True,
      "C5 Login-Thread mit heal_nach + cfg + reserviert")
(ok2, msg2), _ = ausgabe(ST, "config-x.json", UNI)      # zweiter Klick, während der Login noch läuft (Terminal schon da → Warm-Pfad)
check(ok2 is True, "C5b zweiter Start während des Logins: kein Fehler")

ZUSTAND["pids"] = [4711]                                   # Terminal ist hochgekommen
beobachtet = {}
m = mit_mt5(FakeMt5(konto_nach_login=631977,
                    beim_init=lambda: beobachtet.update(mi1=INST in ns["_MI1_LAEUFT"], heal=INST in ns["HEAL_ACTIVE"])))
Faden.gestartet.clear()
r, out = ausgabe(lt.lauf)
check(r is True and len(m.aufrufe) == 1 and PW not in out, "C6 Login-Thread meldet an")
check(beobachtet == {"mi1": True, "heal": False}, f"C7 während des Logins: MI1-Merker an, keine Heilung ({beobachtet})")
ht = [t for t in Faden.gestartet if ziel(t) == "_heal_ea"]
check(len(ht) == 1 and ht[0].args[3] >= uhr.t - 1 and ht[0].args[4] == 45 and ht[0].kwargs.get("api_creds") == UNI,
      "C8 Heilung erst NACH dem Login, started_ts = jetzt, mit api_creds")
check(not ns["_MI1_LAEUFT"] and ns["_instanz_heilt"]({"config_file": "config-x.json"}) is False, "C8b nach dem Login: Merker weg, Instanz frei")
# gescheiterter Login (falsches Passwort) → KEINE Heilung (sonst Kill + Neustart + 2 weitere Fehl-Logins)
Faden.gestartet.clear()
mit_mt5(FakeMt5(init_ok=False))
ns["_mi1_reservieren"](INST)
r_f, out_f = ausgabe(ns["_mi1_api_login"], "config-x.json", EXE, INST, UNI, cfg=CFG, heal_nach=True, reserviert=True)
check(r_f is False and not [t for t in Faden.gestartet if ziel(t) == "_heal_ea"] and "keine Heilung" in out_f and PW not in out_f,
      "C8c Login gescheitert → keine Heilung, Hinweis ohne Passwort")
check(not ns["_MI1_LAEUFT"], "C8d Merker auch nach Fehlschlag weg")
mit_mt5(FakeMt5(konto_nach_login=631977))

# Heilung: Snapshot fließt nie → Kill + Neustart → wieder API-Login (nicht nackt mit OK-Wache)
Faden.gestartet.clear(); POPEN.clear(); KILLS.clear()
r, out = ausgabe(ht[0].lauf)
neu = [ziel(t) for t in Faden.gestartet]
check(KILLS == [4711] and POPEN and POPEN[-1][0] == EXE, "C9 Heilung: Snapshot fließt nicht → Terminal neu gestartet")
check(neu == ["_mi1_api_login"] and Faden.gestartet[0].kwargs.get("aus_heilung") is True and "heal_nach" not in Faden.gestartet[0].kwargs
      and Faden.gestartet[0].kwargs.get("reserviert") is True,
      f"C10 Heil-Neustart meldet wieder per API an (aus_heilung, reserviert, keine neue Heilung danach): {neu}")
check(not ns["HEAL_ACTIVE"] and INST in ns["_MI1_LAEUFT"], "C11 Heilung fertig → HEAL_ACTIVE leer, MI1-Merker steht schon (keine Lücke)")
gerufen0 = []
_inner0 = ns["_heal_ea_inner"]
ns["_heal_ea_inner"] = lambda *a, **k: gerufen0.append(a)
ns["_heal_ea"]("config-x.json", CFG, INST, uhr.t, 15, True)     # Frost-Heilung rutscht in die Lücke
ns["_heal_ea_inner"] = _inner0
check(not gerufen0, "C11b fremde Heilung zwischen Heil-Ende und Login-Thread → heilt nicht")
ns["HEAL_ACTIVE"].add(INST)                                # Heilung im [StartUp]-Zweig schläft noch 30 s mit HEAL_ACTIVE
m = mit_mt5(FakeMt5(konto_nach_login=631977))
r, out = ausgabe(Faden.gestartet[0].lauf)
ns["HEAL_ACTIVE"].clear()
check(r is True and len(m.aufrufe) == 1, "C12 Login nach Heil-Neustart klappt trotz eigenem HEAL_ACTIVE")

# zweiter Start / fremde Heilung während eines laufenden MI1-Logins → heilt nicht dazwischen
gerufen = []
_inner = ns["_heal_ea_inner"]
ns["_heal_ea_inner"] = lambda *a, **k: gerufen.append(a)
ns["_MI1_LAEUFT"].add(INST)
ns["_heal_ea"]("config-x.json", CFG, INST, uhr.t, 8, True)
ns["_MI1_LAEUFT"].clear()
ns["_heal_ea"]("config-x.json", CFG, INST, uhr.t, 8, True)
ns["_heal_ea_inner"] = _inner
check(len(gerufen) == 1, "C13 Heilung wartet, solange ein MI1-Login läuft; danach normal")

# Warm-Pfad (Terminal läuft schon) gibt api_creds an die Heilung weiter
Faden.gestartet.clear()
ZUSTAND["pids"] = [4711]
(ok, msg), out = ausgabe(ST, "config-x.json", UNI)
wh = [t for t in Faden.gestartet if ziel(t) == "_heal_ea"]
check(ok and len(wh) == 1 and wh[0].kwargs.get("api_creds") == UNI, "C14 Warm-Pfad: Heilung mit api_creds (Neustart → API-Login)")

# ASCII-Weg: wie bisher sofort Heilung (45, False) + Login-Wache, kein MI1, Passwort nur in der Login-ini
Faden.gestartet.clear(); POPEN.clear()
ZUSTAND["pids"] = []
geschrieben = {}
_open = open


def merk_open(p, mode="r", encoding=None, **kw):
    f = _open(p, mode, encoding=encoding, **kw)
    if "w" in mode:
        alt_write = f.write
        f.write = lambda s: (geschrieben.__setitem__(os.path.basename(p), s), alt_write(s))[1]
    return f


ns["open"] = merk_open
(ok, msg), out = ausgabe(ST, "config-x.json", ASCII)
ziele = [ziel(t) for t in Faden.gestartet]
heil = [t for t in Faden.gestartet if ziel(t) == "_heal_ea"]
check(ok and "Login wird erzwungen" in msg and "_mi1_api_login" not in ziele and "_login_ok_wache" in ziele,
      f"C15 ASCII: Zwangs-Login wie bisher, Login-Wache, kein MI1 ({ziele})")
check(len(heil) == 1 and heil[0].args[4:6] == (45, False) and not heil[0].kwargs, "C16 ASCII: Heilung sofort, (45, False), ohne kwargs")
check("Password=Abc123xyz" in geschrieben.get("prophos-login.ini", ""), "C17 ASCII: Login-ini trägt die Zugangsdaten (wie bisher)")
Faden.gestartet.clear()
geschrieben.clear()
(ok, msg), out = ausgabe(ST, "config-x.json", UNI)
check(PW not in geschrieben.get("prophos-login.ini", "") and "Password" not in geschrieben.get("prophos-login.ini", "x"),
      "C18 Unicode: Start-ini ohne Passwort")
del ns["open"]

# EM2b: Login mit BOM / Vollbreit-Ziffern + Server mit Null-Breite → gesäubert VOR dem Konto-Abgleich → normaler ASCII-Zwangs-Login
Faden.gestartet.clear(); POPEN.clear()
ZUSTAND["pids"] = []
geschrieben.clear()
ns["open"] = merk_open
(ok, msg), out = ausgabe(ST, "config-x.json", {"login": "﻿６３１９７７", "password": "Abc123xyz", "server": "BlueGuardian-Server​"})
del ns["open"]
check(ok is True and "gehoeren zu Konto" not in msg and "Login wird erzwungen" in msg, f"EM2b Login mit BOM/Vollbreit → kein „gehört zu Konto“ ({msg[:60]})")
ini = geschrieben.get("prophos-login.ini", "")
check("Login=631977\n" in ini and "Server=BlueGuardian-Server\n" in ini and "Password=Abc123xyz" in ini, "EM2b ini mit gesäubertem Login/Server, Passwort unverändert")
Faden.gestartet.clear()
(ok, msg), out = ausgabe(ST, "config-x.json", {"login": "﻿631999", "password": "Abc123xyz", "server": "BlueGuardian-Server"})
check(ok is False and "gehoeren zu Konto 631999" in msg, "EM2b echtes Fremdkonto (nach Säubern) → weiter laut gescheitert")

# ohne Paket bzw. ohne Konto-Nummer: alte Ansage, nichts beendet, nichts gestartet
del sys.modules["MetaTrader5"]
sys.meta_path[:] = []
try:
    POPEN.clear(); KILLS.clear(); Faden.gestartet.clear()
    ZUSTAND["pids"] = [4711]
    (ok, msg), out = ausgabe(ST, "config-x.json", UNI)
finally:
    sys.meta_path[:] = _alt
check(ok is False and "kann nur ASCII" in msg and not POPEN and not KILLS and not Faden.gestartet, "C19 ohne Paket: alte Ansage, kein Kill/Start")

# ── D: ASCII-Zweig bitgleich zu origin/main ──
st = fn(SRC, "start_terminal")
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
    check(alt_st[a0 + len("        if creds:"):a1] == st[n0 + len("        elif creds:"):n1], "D1 ASCII-Zwangs-Login-Zweig bitgleich zu origin/main")
elif alt_st:
    print("· origin/main trägt MI1 schon — Bitgleich-Vergleich gegen den Vor-MI1-Stand entfällt")
else:
    check(False, "D1 origin/main nicht lesbar — Bitgleich-Vergleich NICHT geprüft (git fetch?)")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
