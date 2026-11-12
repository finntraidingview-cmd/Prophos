#!/usr/bin/env python3
"""
Echo-Panel (Prophos) — kleines Web-Frontend für den lokalen MT5-Copier auf DIESEM PC.

Zweck: Multiplikator und Symbol-Mapping im Browser setzen statt in der
Textdatei — für mehrere Master/Prop-Firmen gleichzeitig. Zeigt außerdem live, was der
Copier pro Master gerade macht (Konten, offene Hedges, Log), und kann das jeweilige
Master-Terminal starten (MT5 merkt sich den Login pro Ordner — hier werden KEINE
Zugangsdaten gespeichert).

Bewusst eigenständig: Prophos (app.py / prophos.html) wird NICHT angefasst.

Technik:
  · Nur Python-Standardbibliothek — kein pip install, keine Cloud, keine Schlüssel.
  · Bindet ausschließlich an 127.0.0.1 — aus dem Netz nicht erreichbar.
  · Jede config*.json im Ordner ist ein Master (config.json, config-master2.json, …).
    Seit 13.08.2026 bedient EIN copier.py-Prozess alle Configs zugleich; der Status
    je Master liegt in der passenden status*.json.

Start:  python panel.py     →  http://127.0.0.1:8770
"""

import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

# ── DN1 DNS-RÜCKFALL (10.11.2026, Master; Fehler-Muster FA1/RD1: „getaddrinfo failed“ am PC von Marco pc-t8wg97 — der Router beantwortet DNS zeitweise
# nicht, Riegel- und andere Railway-Aufrufe scheitern; Windows-Einstellungen (DNS am Adapter, hosts) werden bewusst nicht geändert). Scheitert die
# System-Namensauflösung (socket.gaierror) für einen UNSERER Hosts, fragt der Prozess DNS-over-HTTPS direkt per IP (1.1.1.1, dann 8.8.8.8 — dafür
# braucht es kein DNS) und verbindet mit der gefundenen IPv4. TLS bleibt unverändert: urllib/http.client prüfen Zertifikat und SNI am HOSTNAMEN, nicht
# an der IP; die DoH-Server selbst werden über ihr IP-Zertifikat geprüft (nie verify aus). Antwort kurz gecacht (TTL 30–300 s, gescheitert 60 s,
# letzte gute bis 1 h als Notnagel). Der Normalweg ist bitgleich: zuerst immer die System-Auflösung, ihr Ergebnis/ihre anderen Fehler unverändert.
# Zeitdeckel (Gegenprüfung 10.11.2026): je DoH-Server 2 s, zusammen höchstens DNS_RUECKFALL_FRIST_S; läuft schon eine Abfrage für den Host, wartet
# kein zweiter Thread (Notnagel oder sofort der alte Fehler) — der Rückfall verzögert kritische Pfade (Riegel, Panel) nie um mehr als ~3,5 s.
# Gleicher Block in panel.py, order_bot.py, copier.py (jede Datei kommt über einen eigenen Update-Weg auf den PC; tools/selftest_dn1_dns_rueckfall.py
# prüft, dass alle drei gleich sind). Log nur auf stderr (order_bot spricht über stdout JSON mit dem Panel).
DNS_RUECKFALL_HOSTS = ("web-production-bec81.up.railway.app", "gxhkannmzpyuepxlepta.supabase.co")
DNS_RUECKFALL_DOH = ("https://1.1.1.1/dns-query?name={}&type=A", "https://8.8.8.8/resolve?name={}&type=A")
DNS_RUECKFALL_FRIST_S = 3.5
_DNS_RUECK = {"cache": {}, "fehl": {}, "log": {}, "laeuft": {}}


def dns_doh_ips(d):
    """REIN (testbar): DoH-JSON (application/dns-json, Cloudflare/Google gleich) → (IPv4-Liste, TTL s) | ([], 0). Nur Status 0, nur A-Sätze (type 1)."""
    import ipaddress
    if not isinstance(d, dict) or d.get("Status") != 0:
        return [], 0
    ips, ttl = [], None
    for a in d.get("Answer") or ():
        if not isinstance(a, dict) or a.get("type") != 1:
            continue
        try:
            ip = str(ipaddress.IPv4Address(str(a.get("data") or "").strip()))
        except ValueError:
            continue
        if ip not in ips:
            ips.append(ip)
        try:
            t = int(a.get("TTL"))
            ttl = t if ttl is None else min(ttl, t)
        except (TypeError, ValueError):
            pass
    return ips, (max(30, min(300, ttl)) if ttl is not None else 60) if ips else 0


def dns_rueckfall_eintraege(ips, port, family=0, typ=0, proto=0):
    """REIN (testbar): getaddrinfo-Einträge für die IPv4-Liste → [(AF_INET, typ, proto, '', (ip, port))]; leer, wenn nur IPv6 verlangt ist."""
    import socket
    if family not in (0, socket.AF_UNSPEC, socket.AF_INET):
        return []
    if port is None:
        p = 0
    elif isinstance(port, int):
        p = port
    else:
        s = port.decode() if isinstance(port, bytes) else str(port)
        p = int(s) if s.isdigit() else {"https": 443, "http": 80}.get(s.lower(), 0)
    t = typ or socket.SOCK_STREAM
    pr = proto or (socket.IPPROTO_TCP if t == socket.SOCK_STREAM else 0)
    return [(socket.AF_INET, t, pr, "", (ip, p)) for ip in ips]


def _dns_doh_holen(host, timeout=2.0):
    """DoH per IP nacheinander (1.1.1.1, 8.8.8.8) → (ips, ttl), zusammen höchstens DNS_RUECKFALL_FRIST_S. Zertifikat wird geprüft (Standard-Kontext),
    kein DNS nötig."""
    import urllib.parse
    import urllib.request
    ende = time.time() + DNS_RUECKFALL_FRIST_S
    for vorlage in DNS_RUECKFALL_DOH:
        rest = ende - time.time()
        if rest < 0.5:
            break
        try:
            req = urllib.request.Request(vorlage.format(urllib.parse.quote(host)),
                                         headers={"Accept": "application/dns-json", "User-Agent": "prophos-dns"})
            with urllib.request.urlopen(req, timeout=min(timeout, rest)) as r:
                ips, ttl = dns_doh_ips(json.loads(r.read().decode("utf-8") or "{}"))
            if ips:
                return ips, ttl
        except Exception:
            continue
    return [], 0


def dns_rueckfall_ips(host, jetzt=None, holen=None):
    """Gecachte bzw. frisch per DoH geholte IPv4 für einen unserer Hosts → Liste (leer = keine). holen nur für den Selbsttest."""
    jetzt = time.time() if jetzt is None else jetzt
    c = _DNS_RUECK["cache"].get(host)
    if c and c[1] > jetzt:
        return list(c[0])
    notnagel = list(c[0]) if c and jetzt - c[1] < 3600 else []    # letzte gute Antwort bis 1 h nach Ablauf
    if _DNS_RUECK["fehl"].get(host, 0) > jetzt:                  # DoH gerade gescheitert: 60 s nicht erneut
        return notnagel
    marke = object()
    if _DNS_RUECK["laeuft"].setdefault(host, marke) is not marke:   # nur eine Abfrage je Host (setdefault ist unter der GIL atomar)
        return notnagel
    try:
        ips, ttl = (holen or _dns_doh_holen)(host)
    finally:
        _DNS_RUECK["laeuft"].pop(host, None)
    if ips:
        _DNS_RUECK["cache"][host] = (tuple(ips), jetzt + ttl)
        _DNS_RUECK["fehl"].pop(host, None)
        return list(ips)
    _DNS_RUECK["fehl"][host] = jetzt + 60
    return notnagel


def dns_rueckfall_einbauen():
    """socket.getaddrinfo einmal je Prozess umhüllen (Merker am Wrapper) — Normalweg zuerst und unverändert."""
    import socket
    if getattr(socket.getaddrinfo, "_prophos_dns_rueckfall", False):
        return False
    orig = socket.getaddrinfo

    def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        try:
            return orig(host, port, family, type, proto, flags)
        except socket.gaierror:
            try:
                h = (host.decode() if isinstance(host, bytes) else str(host or "")).strip().lower().rstrip(".")
                if h not in DNS_RUECKFALL_HOSTS or (flags & socket.AI_NUMERICHOST):
                    raise LookupError
                eintraege = dns_rueckfall_eintraege(dns_rueckfall_ips(h), port, family, type, proto)
            except Exception:
                eintraege = []
            if not eintraege:
                raise
            try:
                if _DNS_RUECK["log"].get(h, 0) < time.time():
                    _DNS_RUECK["log"][h] = time.time() + 600
                    sys.stderr.write(f"[dns] System-DNS ohne Antwort für {h} — DNS-over-HTTPS: {eintraege[0][4][0]}\n")
            except Exception:
                pass
            return eintraege
    getaddrinfo._prophos_dns_rueckfall = True
    getaddrinfo._prophos_orig = orig
    socket.getaddrinfo = getaddrinfo
    return True


dns_rueckfall_einbauen()
# ── Ende DN1 DNS-RÜCKFALL ──

import provision

try:
    import polar_panel          # Polar (13.10.2026): eigenes Modul; fehlt es auf einem alten PC-Stand, bleibt alles wie bisher
except Exception:
    polar_panel = None

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PANEL_PORT", "8770"))


# ══ LAUFENDER CODE (Betrieb 1 03.11.2026 nach .2012: pc-l5o8bv lief seit 06:53 dt mit altem Panel, mt5_live meldete copier_version .2012 — der
# Neustart-Check verglich den neuen Stand mit der DATEI auf der Platte; war die schon erneuert (Download einer zweiten .bat-Schleife, panel_frisch.py
# eines zweiten Panels, Datei von Hand/per Lotse kopiert), galt der Code als „unverändert“ und nur die VERSION wurde nachgezogen → nie neu gestartet).
# Jetzt: Abbild des Quelltexts BEIM LADEN im Speicher; der Neustart-Check vergleicht damit, und der Herzschlag meldet es (panel_lauf). ══
def _code_glatt(b):
    return (b or b"").replace(b"\r\n", b"\n").lstrip(b"\xef\xbb\xbf").strip()


def _datei_bytes(pfad):
    try:
        with open(pfad, "rb") as f:
            return f.read()
    except OSError:
        return None


_GELADEN = {"panel": _datei_bytes(os.path.abspath(__file__)),
            "provision": _datei_bytes(os.path.abspath(getattr(provision, "__file__", "") or os.path.join(HERE, "provision.py"))),
            "datei": os.path.basename(os.path.abspath(__file__)), "start": time.time(), "pid": os.getpid(), "version": None}
try:
    with open(os.path.join(HERE, "VERSION"), "r", encoding="utf-8") as _vf:
        _GELADEN["version"] = _vf.read().strip() or None
except OSError:
    pass


_ABBILD_FEHLT_GEMELDET = set()


def panel_code_weicht_ab(neu, name="panel"):
    """REIN RECHNEND (testbar): weicht der Quelltext `neu` vom BEIM LADEN gemerkten Abbild ab? Neuer Stand nicht geholt → True (lieber neu starten).
    Kein Abbild (Datei beim Laden nicht lesbar) → False + einmal Log (S9 zu ae4b57db: sonst Neustart-Schleife, das Abbild fehlte nach jedem Start wieder)."""
    alt = _GELADEN.get(name)
    if neu is None:
        return True
    if alt is None:
        if name not in _ABBILD_FEHLT_GEMELDET:
            _ABBILD_FEHLT_GEMELDET.add(name)
            print(f"[panel] Abbild von {name}.py beim Laden nicht lesbar — Update-Vergleich für diese Datei aus (kein Neustart deswegen).", flush=True)
        return False
    return _code_glatt(neu) != _code_glatt(alt)


# ══ LAST DES PCs MESSEN (SW1, Finn 05.11.2026: „Ich denke nicht, dass es daran liegt, dass die PCs überlastet sind … vielleicht ist eher der Fehler, wie die
# Software die Hardware belastet“). Anlass ES4: PC von Marco (pc-t8wg97) und PC von Emin (pc-onkrbk) seit 02.11. täglich langsamer (Login 37 → 97 s, jeder
# UI-Schritt 2–6× langsamer, auch Puls in Chrome), Task-Manager-Fotos 05.11.: CPU 55–86 % im Leerlauf, ein Großteil in Hintergrundprozessen — aber KEIN PC
# meldete RAM, CPU oder Prozesse, die Ursache war aus der Ferne nicht belegbar. Jetzt misst das Panel alle ~5 min (gestreut, Jitter-Regel): RAM gesamt/belegt,
# CPU des ganzen PCs, Windows-Betriebszeit und je Prozessname (chrome, terminal64, python, MsMpEng …) Anzahl, Arbeitsspeicher und CPU-Anteil; dazu jede
# python.exe einzeln mit Rolle (panel / copier aus status-*.json / Kind des Panels = Order-Bot / sonst ?), Elternprozess und Laufzeit — so fallen doppelte
# oder wachsende Prozesse auf. Nur lesend (Toolhelp + OpenProcess nur mit Mindestrecht 0x1000, wie provision.prozess_pfad), keine Unterprozesse, ein paar ms je Runde.
# Reist ohne Frontend-Änderung über panel_lauf.last nach mt5_live.status (der Tab reicht panel_lauf unverändert durch). ══
# Takt 5 min (CPU als Mittel über die 5 min): der Tab kopiert panel_lauf in JEDE mt5_live-Zeile des PCs und pusht bei jeder Änderung (Fingerabdruck) — so kommt
# höchstens 1 zusätzlicher Upsert je 5 min dazu (Supabase-Diät 01.10.2026), Listen kurz (~1 KB je Zeile).
PC_LAST_TAKT_S = 300.0
PC_LAST_TOP_N = 5
PC_LAST_PY_MAX = 8
_PC_LAST = None          # letzte Messung, als Ganzes ersetzt (nie Teil-Stand, kein clear/update-Fenster) → panel_lauf_info()["last"]
_PC_LAST_VORHER = {}     # {"pids": {pid: (name, cpu_100ns)}, "t": monotonic, "sys": (idle, kernel, user)}
_PC_LAST_W32 = {}        # ctypes-Strukturen einmal angelegt (nicht je Runde neue Klassen)


def pc_last_auswerten(prozesse, vorher_pids, dt_s, ncpu, rollen=None, panel_pid=None, top_n=PC_LAST_TOP_N):
    """REIN RECHNEND (testbar). prozesse = [{pid, ppid, name, cpu (100-ns-Einheiten Kernel+User) | None, ws, priv (Bytes) | None, start_s (Unix) | None}],
    vorher_pids = {pid: (name, cpu)} der letzten Runde, dt_s = Wandzeit dazwischen, ncpu = logische Kerne, rollen = {pid: 'copier' …}.
    CPU-% immer als Anteil des GANZEN PCs (100 % = alle Kerne voll), nur für Prozesse, die in beiden Runden mit gleichem Namen da waren.
    → (namen: Top-Liste je Prozessname, python: jede python(w).exe einzeln, neu_vorher)."""
    rollen = rollen or {}
    jetzt = time.time()
    je_name, py, neu = {}, [], {}
    nenner = (float(dt_s) * 1e7 * max(1, int(ncpu or 1))) if dt_s and dt_s > 0 else None
    for p in prozesse or []:
        try:
            pid, name = int(p.get("pid")), str(p.get("name") or "?").lower()
        except (TypeError, ValueError):
            continue
        cpu = p.get("cpu")
        if cpu is not None:
            neu[pid] = (name, cpu)
        pct = None
        alt = vorher_pids.get(pid) if vorher_pids else None
        if nenner and cpu is not None and alt and alt[0] == name and cpu >= alt[1]:
            pct = 100.0 * (cpu - alt[1]) / nenner
        g = je_name.setdefault(name, {"name": name, "n": 0, "ws_mb": 0.0, "priv_mb": 0.0, "cpu_pct": 0.0, "_cpu_da": False})
        g["n"] += 1
        g["ws_mb"] += (p.get("ws") or 0) / 1048576.0
        g["priv_mb"] += (p.get("priv") or 0) / 1048576.0
        if pct is not None:
            g["cpu_pct"] += pct
            g["_cpu_da"] = True
        if name in ("python.exe", "pythonw.exe"):
            ppid = p.get("ppid")
            rolle = ("panel" if panel_pid and pid == panel_pid else rollen.get(pid)
                     or ("panel-kind" if panel_pid and ppid == panel_pid else "?"))
            st = p.get("start_s")
            py.append({"pid": pid, "ppid": ppid, "rolle": rolle,
                       "ws_mb": round((p.get("ws") or 0) / 1048576.0), "priv_mb": round((p.get("priv") or 0) / 1048576.0),
                       "cpu_pct": round(pct, 1) if pct is not None else None,
                       "alter_h": round((jetzt - st) / 3600.0, 1) if st else None})
    alle = list(je_name.values())   # erst ungerundet sortieren, dann runden (gerundete Gleichstände verdrehten die Reihenfolge)
    nach_cpu = sorted(alle, key=lambda g: -g["cpu_pct"])[:top_n]
    nach_ram = sorted(alle, key=lambda g: -g["priv_mb"])[:top_n]
    namen = sorted({g["name"]: g for g in nach_cpu + nach_ram}.values(), key=lambda g: (-g["cpu_pct"], -g["priv_mb"]))
    for g in namen:
        g["ws_mb"], g["priv_mb"] = round(g["ws_mb"]), round(g["priv_mb"])
        g["cpu_pct"] = round(g["cpu_pct"], 1) if g.pop("_cpu_da") else None
    py.sort(key=lambda x: (-(x["cpu_pct"] or 0), -x["ws_mb"]))
    return namen, py[:PC_LAST_PY_MAX], neu


def _pc_w32():
    """ctypes-Typen für die Messung, einmal je Prozess angelegt. Nur Windows."""
    if _PC_LAST_W32:
        return _PC_LAST_W32
    import ctypes
    import ctypes.wintypes as wt

    class PE32(ctypes.Structure):
        _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                    ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    class PMC(ctypes.Structure):   # PROCESS_MEMORY_COUNTERS_EX
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]

    class MSEX(ctypes.Structure):  # MEMORYSTATUSEX
        _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(wt.FILETIME)] * 4
    k32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
    k32.GetSystemTimes.argtypes = [ctypes.POINTER(wt.FILETIME)] * 3
    k32.GetTickCount64.restype = ctypes.c_ulonglong
    _PC_LAST_W32.update(ctypes=ctypes, wt=wt, k32=k32, PE32=PE32, PMC=PMC, MSEX=MSEX)
    return _PC_LAST_W32


def _ft(f):
    return (int(f.dwHighDateTime) << 32) | int(f.dwLowDateTime)


def _pc_prozesse_lesen():
    """Alle Prozesse: pid, ppid, name, CPU-Zeit, Arbeitsspeicher, privater Speicher, Startzeit. Prozesse ohne Zugriff (geschützte) nur mit Name/pid."""
    w = _pc_w32()
    ctypes, wt, k32 = w["ctypes"], w["wt"], w["k32"]
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)        # TH32CS_SNAPPROCESS
    if snap == ctypes.c_void_p(-1).value or not snap:
        return None
    roh = []
    try:
        pe = w["PE32"]()
        pe.dwSize = ctypes.sizeof(pe)
        ok = k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            roh.append((int(pe.th32ProcessID), int(pe.th32ParentProcessID), str(pe.szExeFile)))
            ok = k32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    out = []
    pmc = w["PMC"]()
    c_, e_, kz, uz = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    for pid, ppid, name in roh:
        d = {"pid": pid, "ppid": ppid, "name": name, "cpu": None, "ws": None, "priv": None, "start_s": None}
        if pid:
            # NUR das Mindestrecht 0x1000 (PROCESS_QUERY_LIMITED_INFORMATION, wie provision/order_bot): reicht ab Windows 8.1 für Zeiten UND Speicher. Kein VM_READ —
            # sonst öffnete die Wache alle 5 min auch lsass.exe mit Leserecht, was Defender-ASR/EDR als Zugriffsversuch melden kann (S9-Gegenprüfung SW1)
            h = k32.OpenProcess(0x1000, False, pid)
            if h:
                try:
                    if k32.GetProcessTimes(h, ctypes.byref(c_), ctypes.byref(e_), ctypes.byref(kz), ctypes.byref(uz)):
                        d["cpu"] = _ft(kz) + _ft(uz)
                        d["start_s"] = (_ft(c_) - 116444736000000000) / 1e7 if _ft(c_) else None
                    pmc.cb = ctypes.sizeof(pmc)
                    if k32.K32GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                        d["ws"], d["priv"] = int(pmc.WorkingSetSize), int(pmc.PrivateUsage)
                finally:
                    k32.CloseHandle(h)
        out.append(d)
    return out


def pc_last_system(ms_load, ram_gesamt, ram_frei, sys_jetzt, sys_vorher, uptime_ms):
    """REIN RECHNEND (testbar): System-Zeile. sys_* = (idle, kernel, user) in 100 ns (kernel enthält idle) → CPU-% des PCs seit der letzten Runde."""
    cpu = None
    if sys_jetzt and sys_vorher:
        di, dk, du = (sys_jetzt[0] - sys_vorher[0]), (sys_jetzt[1] - sys_vorher[1]), (sys_jetzt[2] - sys_vorher[2])
        if dk + du > 0:
            cpu = round(100.0 * (dk + du - di) / (dk + du), 1)
    return {"ram_gesamt_gb": round(ram_gesamt / 1073741824.0, 1) if ram_gesamt else None,
            "ram_frei_gb": round(ram_frei / 1073741824.0, 1) if ram_frei is not None else None,
            "ram_belegt_pct": ms_load, "cpu_pct": cpu,
            "betrieb_h": round(uptime_ms / 3600000.0, 1) if uptime_ms else None}


def _pc_last_runde():
    w = _pc_w32()
    ctypes, wt, k32 = w["ctypes"], w["wt"], w["k32"]
    ms = w["MSEX"]()
    ms.dwLength = ctypes.sizeof(ms)
    k32.GlobalMemoryStatusEx(ctypes.byref(ms))
    i_, k_, u_ = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    sys_jetzt = (_ft(i_), _ft(k_), _ft(u_)) if k32.GetSystemTimes(ctypes.byref(i_), ctypes.byref(k_), ctypes.byref(u_)) else None
    t = time.monotonic()
    prozesse = _pc_prozesse_lesen() or []
    rollen = {}
    for inst in instances():   # Copier-PID steht in jeder status-*.json (Instanz-Sperre des Copiers)
        try:
            pid_c = int((read_json(os.path.join(HERE, inst["status_file"]), {}) or {}).get("pid") or 0)
        except (TypeError, ValueError):
            pid_c = 0
        if pid_c:
            rollen[pid_c] = "copier"
    dt = (t - _PC_LAST_VORHER["t"]) if _PC_LAST_VORHER.get("t") else None
    namen, py, neu = pc_last_auswerten(prozesse, _PC_LAST_VORHER.get("pids"), dt, os.cpu_count() or 1, rollen, os.getpid())
    sysz = pc_last_system(int(ms.dwMemoryLoad), int(ms.ullTotalPhys), int(ms.ullAvailPhys), sys_jetzt, _PC_LAST_VORHER.get("sys"),
                          int(k32.GetTickCount64()))
    _PC_LAST_VORHER.update(pids=neu, t=t, sys=sys_jetzt)
    erg = dict(sysz, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), kerne=os.cpu_count(), prozesse=len(prozesse),
               python_n=sum(1 for p in prozesse if str(p.get("name") or "").lower() in ("python.exe", "pythonw.exe")),
               namen=namen if dt else None, python=py)
    global _PC_LAST
    _PC_LAST = erg


def _pc_last_waechter():
    """Thread: alle ~5 min eine Messung (erste CPU-Werte ab der zweiten Runde, ~60 s nach der ersten). Wirft nie; ohne Windows nichts."""
    global _PC_LAST
    if os.name != "nt":
        return
    time.sleep(20 + random.uniform(0, 20))
    runde = 0
    while True:
        runde += 1
        try:
            _pc_last_runde()
        except Exception as e:
            _PC_LAST = {"fehler": f"{type(e).__name__}: {e}"[:160], "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        # erste Runde liefert nur Vorwerte → zweite schon nach ~60 s, danach im 5-min-Takt
        time.sleep((60.0 if runde == 1 else PC_LAST_TAKT_S) + random.uniform(0, 15))


# ── WINDOWS-ABFRAGE MELDEN (UA1, 06.11.2026 — Finn: „Wenn die Windows-Abfrage kommt, kannst du mir kurz Bescheid geben, dann kann ich es
# kurz hinklicken."). Anlass F9A: MT5-Build 6230 wollte erhöht eingespielt werden, consent.exe stand auf pc-c19p2l stundenlang offen und
# blockierte jedes F9 des PCs. Alle UAC_ALARM_TAKT_S eine reine Namensliste (ein Toolhelp-Snapshot, kein Unterprozess, kein Öffnen fremder
# Prozesse); nur wenn consent.exe darin steht, Startzeit der Abfrage und der Pfad laufender terminal64.exe (liveupdate = MT5-Update →
# origin.txt nennt die Installation). Railway (POST /pc/uac-spur) alarmiert 🔴 an die Master-IDs, nach 30 min erneut, ✅ wenn weg.
# Gesendet wird bei jeder Änderung und solange offen alle UAC_ALARM_HALTEN_S. Wegklicken kann kein Programm (sicherer Desktop) — nur melden.
UAC_ALARM_TAKT_S, UAC_ALARM_HALTEN_S, UAC_ALARM_FEHL_S = 30.0, 300.0, 300.0
UAC_ALARM = {"gemeldet": None, "gesendet_at": 0.0, "erst_gesehen": {}, "fehl_bis": 0.0}
# Gemeldeter Stand übersteht einen Panel-Neustart (Gegenprüfung UA1): sonst ginge ein „weg" zwischen Neustart und nächster Runde verloren (kein ✅)
UAC_ALARM_DATEI = os.path.join(HERE, "uac_alarm.json")


def uac_alarm_senden_noetig(vorher, jetzt, zuletzt_s, now, halten_s=UAC_ALARM_HALTEN_S):
    """REIN RECHNEND (testbar): POST an Railway nötig? vorher/jetzt = Schlüssel der offenen Abfragen. Änderung (neu oder weg) sofort,
    solange etwas offen ist zusätzlich alle halten_s (Railway alarmiert nach 30 min erneut). Nichts offen und nichts weg → nie."""
    return set(vorher) != set(jetzt) or (bool(jetzt) and now - float(zuletzt_s or 0) >= halten_s)


def uac_ausloeser_waehlen(consent_seit, updater):
    """REIN RECHNEND (testbar): welcher MT5-Updater gehört zu dieser Abfrage? updater = [(start_s|None, installation)]. Der, der ≤ 20 s vor
    der Abfrage startete (MT5 startet den Updater, 1 s danach kommt consent.exe — F9A); sonst genau einer → der; sonst ''."""
    nah = [i for s, i in updater if s and consent_seit and -20 <= consent_seit - s <= 5]
    if nah:
        return nah[-1]
    # MU1 (10.11.2026): mehrere Updater-Prozesse derselben Installation (/update startet sich erhöht neu) sind EIN Auslöser
    return updater[0][1] if len({i for _s, i in updater}) == 1 else ""


def update_wartet_text(wartend):
    """REIN (testbar): [(Installation, Build)] mit wartendem neuerem Paket → Auslöser-Text für die Handy-Meldung, '' wenn keine."""
    w = sorted({(str(i), int(b)) for i, b in (wartend or []) if i and b})
    if not w:
        return ""
    namen = ", ".join(i for i, _b in w[:2]) + (f" (+{len(w) - 2})" if len(w) > 2 else "")
    return f"vermutlich MT5-Update (Build {max(b for _i, b in w)} wartet) für {namen}"


def _uac_update_wartet_text():
    """Installationen, deren liveupdate-Ordner ein Paket mit höherem Build als installiert hat (MT5 will beim Start erhöht einspielen).
    Nur listdir + Versionslesen, nur wenn consent.exe offen ist. Wirft nie."""
    try:
        wartend = []
        for _k, (pfad, dd, v, _art) in _build_installationen().items():
            if not (dd and v):
                continue
            try:
                for f in os.listdir(os.path.join(dd, "liveupdate")):
                    m = _PAKET_RE.match(f)
                    if m and int(m.group(1)) > v[3]:
                        wartend.append((pfad, int(m.group(1))))
                        break
            except OSError:
                pass
        return update_wartet_text(wartend)
    except Exception:
        return ""


def _uac_abfragen_lesen():
    """[{pid, seit, ausloeser}] der offenen Windows-Abfragen, [] wenn keine, None ohne lesbare Liste. Wirft nie."""
    if os.name != "nt":
        return None
    try:
        w = _pc_w32()
        ctypes, wt, k32 = w["ctypes"], w["wt"], w["k32"]
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        if snap == ctypes.c_void_p(-1).value or not snap:
            return None
        roh = []
        try:
            pe = w["PE32"]()
            pe.dwSize = ctypes.sizeof(pe)
            ok = k32.Process32FirstW(snap, ctypes.byref(pe))
            while ok:
                n = str(pe.szExeFile).lower()
                if n in ("consent.exe", "terminal64.exe"):
                    roh.append((int(pe.th32ProcessID), n))
                ok = k32.Process32NextW(snap, ctypes.byref(pe))
        finally:
            k32.CloseHandle(snap)
        if not any(n == "consent.exe" for _, n in roh):
            return []

        def start_und_pfad(pid, pfad_auch):
            # nur PROCESS_QUERY_LIMITED_INFORMATION (wie _pc_prozesse_lesen); consent.exe (SYSTEM) kann verweigern → None
            h = k32.OpenProcess(0x1000, False, pid)
            if not h:
                return None, ""
            try:
                c_, e_, kz, uz = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
                s = (_ft(c_) - 116444736000000000) / 1e7 if k32.GetProcessTimes(h, ctypes.byref(c_), ctypes.byref(e_), ctypes.byref(kz),
                                                                               ctypes.byref(uz)) and _ft(c_) else None
                p = ""
                if pfad_auch:
                    buf, ln = ctypes.create_unicode_buffer(1024), wt.DWORD(1024)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(ln)):
                        p = buf.value
                return s, p
            finally:
                k32.CloseHandle(h)

        updater = []
        for pid, n in roh:
            if n != "terminal64.exe":
                continue
            s, p = start_und_pfad(pid, True)
            if "\\liveupdate\\" in os.path.normcase(p or "").replace("/", "\\"):
                inst = ""
                try:   # <Datenordner>\liveupdate\terminal64.exe → <Datenordner>\origin.txt = Installation (wie das Update-Skript)
                    # MU1 (10.11.2026): origin.txt ist UTF-16 — als utf-8 gelesen kamen „��C:\MT5-…“ in Finns Handy-Meldung; read_origin kann beides
                    inst = str(provision.read_origin(os.path.dirname(os.path.dirname(p))) or "").strip()[:80]
                except Exception:
                    pass
                updater.append((s, inst or "unbekannte Installation"))
        updater.sort(key=lambda x: x[0] or 0)
        jetzt, out = time.time(), []
        for pid, n in roh:
            if n != "consent.exe":
                continue
            s, _p = start_und_pfad(pid, False)
            # seit = echte Startzeit oder 0 (consent.exe läuft als SYSTEM, ohne Adminrechte oft nicht lesbar) — gehört in den Schlüssel bei Railway;
            # gesehen = erstes Sehen dieses Panels, nur für die Anzeige (ändert sich bei einem Panel-Neustart, darf den Schlüssel also nicht bilden)
            gesehen = UAC_ALARM["erst_gesehen"].setdefault(pid, s or jetzt)
            inst = uac_ausloeser_waehlen(s, updater)
            # MU1 (10.11.2026): Updater oft schon weg, wenn consent.exe gelesen wird („Auslöser: unbekannt“, Chris 10.11. 06:05/06:08 Dubai —
            # Journal belegt liveupdate /update) → Installationen mit wartendem neuerem Build-Paket nennen
            ausl = f"MT5-Update terminal64.exe für {inst}" if inst else _uac_update_wartet_text()
            out.append({"pid": pid, "seit": int(s or 0), "gesehen": int(gesehen), "ausloeser": ausl[:160]})
        for pid in [p for p in UAC_ALARM["erst_gesehen"] if p not in {e["pid"] for e in out}]:
            UAC_ALARM["erst_gesehen"].pop(pid, None)
        return out
    except Exception as e:
        print(f"[uac-alarm] Lesen: {type(e).__name__}: {e}", flush=True)
        return None


def _uac_spur_melden(offen, weg):
    """POST /pc/uac-spur (X-Code-Token, wie /pc/tab-heil-spur). → True wenn angekommen. Wirft nie, blockiert höchstens 5 s."""
    import urllib.request
    tok = code_token()
    if not tok:
        return False
    try:
        body = json.dumps({"offen": offen, "weg": weg}).encode("utf-8")
        req = urllib.request.Request(CODE_QUELLE + "/pc/uac-spur", data=body, method="POST",
                                     headers={"X-Code-Token": tok, "Content-Type": "application/json", "User-Agent": "prophos-panel"})
        urllib.request.urlopen(req, timeout=5).read()
        return True
    except Exception as e:
        print(f"[uac-alarm] nicht gemeldet ({type(e).__name__})", flush=True)
        return False


def _uac_alarm_waechter():
    """Thread: alle ~30 s offene Windows-Abfragen lesen und Änderungen an Railway melden. Wirft nie; ohne Windows nichts."""
    if os.name != "nt":
        return
    time.sleep(30 + random.uniform(0, 30))
    if UAC_ALARM["gemeldet"] is None:
        g = read_json(UAC_ALARM_DATEI, {})
        UAC_ALARM["gemeldet"] = {str(k): v for k, v in g.items() if isinstance(v, dict)} if isinstance(g, dict) else {}
    while True:
        try:
            offen = _uac_abfragen_lesen()
            if offen is not None and time.time() >= UAC_ALARM["fehl_bis"]:
                jetzt = {f"{e['pid']}|{e['seit']}": e for e in offen}
                vorher = UAC_ALARM["gemeldet"]
                if uac_alarm_senden_noetig(vorher, jetzt, UAC_ALARM["gesendet_at"], time.time()):
                    weg = [vorher[k] for k in vorher if k not in jetzt]
                    if _uac_spur_melden(list(jetzt.values()), weg):   # nicht angekommen → nach UAC_ALARM_FEHL_S nochmal (weg bleibt im Merker)
                        UAC_ALARM.update(gemeldet=jetzt, gesendet_at=time.time())
                        try:
                            tmp = UAC_ALARM_DATEI + ".tmp"
                            with open(tmp, "w", encoding="utf-8") as f:
                                json.dump(jetzt, f)
                            os.replace(tmp, UAC_ALARM_DATEI)
                        except OSError:
                            pass
                    else:
                        UAC_ALARM["fehl_bis"] = time.time() + UAC_ALARM_FEHL_S   # Railway weg/403: nicht alle 30 s, sondern alle 5 min
        except Exception as e:
            print(f"[uac-alarm] {type(e).__name__}: {e}", flush=True)
        time.sleep(UAC_ALARM_TAKT_S + random.uniform(-5, 5))


def panel_lauf_info():
    """Was dieser Panel-Prozess WIRKLICH fährt (für mt5_live.status.panel_lauf über den Prophos-Tab): Version, deren Code nachweislich läuft (Start bzw.
    nachgezogen nach Vergleich mit dem Abbild), Startzeit, PID, Datei (panel.py / panel_frisch.py), sha12 des geladenen Quelltexts."""
    import hashlib
    b, pv = _GELADEN.get("panel"), _GELADEN.get("provision")
    ma = read_json(os.path.join(HERE, "panel_mutex_aufgabe.json"), None)
    return {"version": _GELADEN.get("version"), "start_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_GELADEN["start"])),
            "pid": _GELADEN.get("pid"), "datei": _GELADEN.get("datei"),
            "sha12": hashlib.sha256(_code_glatt(b)).hexdigest()[:12] if b else None,
            # S9 zu ae4b57db: Abbild von provision.py sichtbar (None = beim Laden nicht lesbar, Vergleich dafür aus)
            "provision_sha12": hashlib.sha256(_code_glatt(pv)).hexdigest()[:12] if pv else None,
            # S9: neue Panels, die wegen des Mutex aufgaben (Zähler, erste/letzte Zeit, PID) — steigt er, hält evtl. ein hängendes Panel den Mutex
            "mutex_aufgaben": ma if isinstance(ma, dict) else None,
            # SW1 (05.11.2026): Last des PCs (RAM/CPU/Betriebszeit, je Prozessname, jede python.exe), s. LAST DES PCs MESSEN — None bis zur ersten Messung
            "last": _PC_LAST,
            "tages_neustart": tages_neustart_info()}   # DR1 (05.11.2026): letzter täglicher Neustart + RAM vorher/nachher

# Nur diese Felder darf das Panel schreiben. Terminal-Pfade, magic und die erwarteten
# Kontonummern bleiben tabu — das sind die Sicherheitsanker des Copiers.
# max_lots_per_hedge abgeschafft (15.08.2026, Finn: "komplett weg") — Alt-Clients,
# die es noch schicken, werden vom Save still ignoriert (k not in WRITABLE).
# mode genauso abgeschafft (25.08.2026, Finn: nur noch live, Modus-Klicks weg) —
# der Copier sendet immer echt, das Feld in Alt-Configs ist bedeutungslos.
# notfall_faktor/notfall_puffer_min_punkte (27.08.2026): Notfall-SL/TP auf dem
# Hedge. BEWUSST writable, aber OHNE Eingabefeld im Panel (Finns Ansage 'mach
# eins fuer alle'): der Wert ist eine globale Flotten-Policy — gestellt wird er
# ueber den 🛡-Chip in Prophos (Supabase echo_notfall), und echoNotfallGuard
# verteilt ihn per save?file= in jede Config. Ein Panel-Feld wuerde binnen
# einer Minute zurueckgeheilt und nur verwirren.
WRITABLE = {"multiplier", "symbol_map", "notfall_faktor", "notfall_puffer_min_punkte"}
# Dieselbe strenge Namensregel wie in copier.py — Explorer-Kopien wie
# "config - Kopie.json" oder "config (2).json" sind KEINE Instanz (Audit 13.08.2026:
# solche Karten sahen echt aus, steuerten aber nichts).
CONFIG_RE = re.compile(r"config(?:[-_][A-Za-z0-9]{1,24})?\.json", re.I)
TEMPLATES = ("config.example.json", "config.fusion-test.json")
SYMBOL_RE = re.compile(r"[A-Za-z0-9._#!&\-]{1,32}")


def base_config():
    """Basis fuer die Provisionierung (Hedge-Felder + Vorlage-Terminal).
    Reihenfolge (15.08.2026, Finns Von-Null-Test: er hat ALLE Accounts inkl.
    config.json geloescht — die war bis dahin heimlich auch die Vorlage):
    1. config.json (erster Master, klassisch)
    2. config.vorlage.json — reine Vorlage, ist KEIN Account (CONFIG_RE matcht
       den Punkt nicht), taucht also nie in der Liste auf. Echtes 'von 0'."""
    cfg = read_json(os.path.join(HERE, "config.json"), None)
    if isinstance(cfg, dict) and cfg:
        return cfg
    cfg = read_json(os.path.join(HERE, "config.vorlage.json"), None)
    return cfg if isinstance(cfg, dict) else {}


def ensure_vorlage():
    """Von-Null-Selbstheilung (15.08.2026): fehlt JEDE Basis (config.json UND
    config.vorlage.json), holt das Panel die Standard-Vorlage einmalig aus dem
    Repo — gleiche vertrauenswuerdige Quelle wie das Selbst-Update. Bestehende
    Dateien werden NIE ueberschrieben (hedge_expected_login & Pfade gehoeren
    dem PC). Anlass: der manuelle irm-Download ist beim Von-Null-Test zweimal
    untergegangen — ein Pflichtschritt, den man vergessen kann, ist ein Bug."""
    if base_config():
        return
    try:
        data = repo_datei("mt5-copier/config.vorlage.json")
        if len(data) > 200 and isinstance(json.loads(data.decode("utf-8")), dict):
            tmp = os.path.join(HERE, "config.vorlage.json.tmp")
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, os.path.join(HERE, "config.vorlage.json"))
            print("[panel] config.vorlage.json fehlte — Standard-Vorlage aus dem Repo geholt.", flush=True)
    except Exception as e:
        print(f"[panel] Vorlage-Download fehlgeschlagen ({type(e).__name__}) — "
              f"Hinzufuegen meldet das klar, sobald es gebraucht wird.", flush=True)


def ensure_ea_source():
    """EA-Quelltext aus dem Repo aktuell halten (15.08.2026, Finns Live-Symmetrie):
    der Snapshot-Header v3 (balance/equity) lag laengst im Repo, aber auf den PCs
    lief die alte kompilierte .ex5 — Master-P&L blieb deshalb leer. Das Panel
    laedt die .mq5 beim Start in seinen Ordner; kompiliert wird pro Terminal beim
    Kalt-Start (_ensure_ea_compiled). Best effort wie ensure_vorlage."""
    dst = os.path.join(HERE, provision.EA_NAME + ".mq5")
    try:
        data = repo_datei("mt5-copier/" + provision.EA_NAME + ".mq5")
        if len(data) < 500 or b"OnInit" not in data:
            return
        old = b""
        if os.path.exists(dst):
            with open(dst, "rb") as f:
                old = f.read()
        if data != old:
            tmp = dst + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dst)
            print(f"[panel] {provision.EA_NAME}.mq5 aus dem Repo aktualisiert "
                  f"({len(data)} Bytes) — Terminals kompilieren beim naechsten Kalt-Start.", flush=True)
    except Exception as e:
        print(f"[panel] EA-Quelltext-Download fehlgeschlagen ({type(e).__name__}) — "
              f"kompiliert wird dann mit dem vorhandenen Stand.", flush=True)


def ensure_starter_source():
    """start-alles.bat aus dem Repo aktuell halten (01.09.2026, Finns neuer PC).

    Die .py-Dateien ziehen sich seit jeher selbst nach — die .bat NIE. Auf jedem
    PC lief deshalb der Starter vom Tag der Einrichtung weiter, und eine
    Verbesserung am Start-Weg erreichte genau die Rechner nicht, auf denen der
    Start klemmt. Finn am neuen PC: "ich will einfach eine Datei oeffnen und
    das Backend faehrt hoch, SO WIE ES IMMER WAR" — das stimmte auch, solange
    die Voraussetzungen da waren; fehlte eine, tat der Starter stillschweigend
    nichts.

    VERZOEGERT um drei Minuten, und das ist der ganze Trick an dieser Funktion:
    das Panel wird VON start-alles.bat gestartet, und die Batchdatei laeuft in
    den ersten ~90 Sekunden noch (sie wartet auf den Backend-Port). Eine
    laufende .bat zu ueberschreiben ist unter Windows undefiniert — cmd liest
    sie zeilenweise per Dateiposition weiter. Nach drei Minuten ist sie sicher
    durch, und gebraucht wird die neue Fassung ohnehin erst beim naechsten
    Start."""
    def _spaeter():
        time.sleep(180)
        dst = os.path.join(HERE, "start-alles.bat")
        try:
            data = repo_datei("mt5-copier/start-alles.bat")
            # Positiv-Signatur statt blossem Groessencheck: eine halb geladene
            # oder falsche Datei darf den einzigen Startweg nicht ersetzen.
            if len(data) < 800 or b"start-prophos.bat" not in data:
                return
            old = b""
            if os.path.exists(dst):
                with open(dst, "rb") as f:
                    old = f.read()
            if data == old:
                return
            if old:
                with open(dst + ".prev", "wb") as f:
                    f.write(old)
            tmp = dst + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dst)
            print(f"[panel] start-alles.bat aus dem Repo aktualisiert "
                  f"({len(data)} Bytes) — wirkt ab dem naechsten Start.", flush=True)
        except Exception as e:
            print(f"[panel] start-alles.bat-Download fehlgeschlagen "
                  f"({type(e).__name__}) — der vorhandene Starter bleibt.", flush=True)

    threading.Thread(target=_spaeter, daemon=True).start()


# ── SCHNELLES UPDATE (22.09.2026, Finn: "warum dauert das Selbst-Update immer so
# lange … ich warte immer 2-5 min") ────────────────────────────────────────────
# BEFUND: raw.githubusercontent.com liefert JEDE Datei mit 'cache-control:
# max-age=300' — bis zu fuenf Minuten alter Stand, pro Datei mit EIGENER Uhr.
# Dazu kam die Pruefung nur einmal pro Minute. Und schlimmer als das Warten:
# ensure_bot_source lud order_bot.py beim Panel-Start genau EINMAL von 'main'.
# War die VERSION-Datei schon frisch, order_bot.py aber noch im Zwischenspeicher,
# lief der ALTE Bot unter der NEUEN Versionsnummer — bis zum naechsten Neustart,
# und von aussen nicht zu erkennen.
# LOESUNG: den neuesten Stand (Commit-Kennung) ueber GitHubs Git-Schnittstelle
# fragen — dieselbe Abfrage wie 'git ls-remote', ohne Zwischenspeicher, ohne
# API-Kontingent, ~0,3 s. Dateien werden dann ueber die Adresse MIT dieser
# Kennung geladen: deren Inhalt kann sich nie aendern, ein Zwischenspeicher
# kann also nichts Falsches liefern.
_REPO = "finntraidingview-cmd/Prophos"
# geholt_sha: order_bot.py liegt nachweislich in diesem Stand vor; kaputt_sha: Inhalt dieses Stands unbrauchbar (Größe/run/compile) —
# der Inhalt zu einem sha ist unveränderlich, Wiederholen hilft dort nie (Prüfer T3 09.10.2026)
BOT_STAND = {"sha": None, "version": None, "geholt_sha": None, "kaputt_sha": None}


# ── CODE-QUELLE RAILWAY (07.10.2026, Repo privat — Finn: „Code-Auslieferung über Railway mit PC-Schlüssel bauen"). Zuerst
# Railway (/code/stand, /code/datei/…) mit dem PC-Schlüssel aus code_token.txt (legt der eingeloggte Prophos-Tab über
# POST /api/code-token ab), GitHub nur noch als Rückfall. Railway deployt jeden Push — Kennung + Dateien passen zusammen.
CODE_QUELLE = "https://web-production-bec81.up.railway.app"
CODE_TOKEN_DATEI = os.path.join(HERE, "code_token.txt")
CODE_TOKEN_MUSTER = re.compile(r"^[0-9a-f-]{36}\.(pc-[a-z0-9]{4,12}|host-[a-z0-9-]{1,30})\.[0-9a-f]{40}$")


def code_token():
    try:
        with open(CODE_TOKEN_DATEI, "r", encoding="utf-8") as f:
            t = f.read().strip()
        return t if CODE_TOKEN_MUSTER.fullmatch(t) else None
    except OSError:
        return None


def code_holen(pfad_url, timeout=15):
    """GET CODE_QUELLE + pfad_url mit X-Code-Token → Bytes (nur bei 200) oder None."""
    import urllib.request
    tok = code_token()
    if not tok:
        return None
    try:
        req = urllib.request.Request(CODE_QUELLE + pfad_url, headers={"X-Code-Token": tok, "User-Agent": "prophos-panel"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def tab_wache_antwort(pid, pong, ping, jetzt):
    """REIN RECHNEND (testbar): /api/puls-klick → ({tab_wache, ping?}, Antwort-Zeile für tab_pong.json | None). Nur die Marke DIESES Plans, nur jünger als 5 min."""
    felder, zeile = {"tab_wache": 1}, None
    try:
        frisch = isinstance(ping, dict) and pid and str(ping.get("plan_id") or "") == pid and jetzt - float(ping.get("at") or 0) <= 300
    except (TypeError, ValueError):
        frisch = False
    if frisch and ping.get("marke"):
        felder["ping"] = str(ping["marke"])
        if pong and pong == felder["ping"]:
            zeile = {"plan_id": pid, "marke": pong, "at": jetzt}
    return felder, zeile


# RD1 (10.11.2026, Master; Standing Order Fehler-Muster, FA1): „Riegel-Prüfung (Gegenrichtung) nicht erreichbar: <urlopen error [Errno 11001] getaddrinfo
# failed>" 20× in 7 Tagen auf einem PC — der Router (DNS) antwortet dort zeitweise nicht, zwei sofortige Versuche fielen beide in dieselbe Lücke. Nur bei einem
# NETZfehler (DNS, Zeitlimit, Verbindung) jetzt bis zu RIEGEL_NETZ_WIEDERHOLEN weitere Versuche nach gestreuter Pause (Jitter-Regel). HTTP-Fehler (4xx/5xx),
# unklare Antworten und echte Sperren (gegenrichtung, big_trade_*) bleiben genau wie bisher. Fail-closed bleibt: ohne Antwort nie frei.
RIEGEL_NETZ_WIEDERHOLEN = 2
RIEGEL_NETZ_PAUSE_S = ((1.0, 2.5), (2.5, 5.0))


def riegel_netzfehler(e):
    """REIN (testbar): ist die Ausnahme ein Netzfehler (DNS/Zeitlimit/Verbindung) und kein HTTP-Status? -> bool. HTTPError (Railway hat geantwortet) nie."""
    import socket
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        return False
    if isinstance(e, (socket.gaierror, socket.timeout, TimeoutError, ConnectionError)):
        return True
    if isinstance(e, urllib.error.URLError):
        r = getattr(e, "reason", None)
        return isinstance(r, (socket.gaierror, socket.timeout, TimeoutError, ConnectionError, OSError)) or "getaddrinfo" in str(r)
    return False


def richtung_frei(plan_id, richtung, timeout=6, zweit_aus=None, netz_wiederholen=True):
    """HARTE LINIE VOR JEDEM SCHARFEN KLICK (13.10.2026, Finn: „wenn der Wächter ausfällt … dass da nie was passieren kann"):
    fragt Railway POST /richtung/frei (X-Code-Token wie /code/stand; dort service role -> DB-Funktion prophos_gegenrichtung_frei):
    läuft bei derselben ID × Firma auf einem anderen Konto ein Trade in Gegenrichtung? Seit 19.10.2026 auch: ist ein Big Trade
    DIESES PCs nah am TP/an der Liq (puls_heim_pruefen, code big_trade_nah/big_trade_unklar)? -> (frei, msg, code).
    FAIL-CLOSED: kein Token, kein Netz, 5xx, unklare Antwort = NICHT frei (code riegel_unerreichbar) — der Bot wird dann nicht
    gestartet, es ist beweisbar nichts gesendet, der Tab versucht es später erneut. Ohne Plan-UUID/Richtung (Probe, Konto-Check)
    gibt es nichts zu prüfen -> frei.
    zweit_aus (dict, optional): bekommt {zweit: True, zweit_art?} bei einer Zweit-Sperre (ZWEI ORBIT, 03.11.2026, Z4 — Lücke 2 der Prüfung S3:
    Railway meldet „zweiter Start wartet“ als big_trade_nah mit zweit: true, das Panel gab nur code weiter; der PC-Tab unterscheidet jetzt am Flag
    statt am Text und fragt dann alle 20–40 s /admin/zweit-frei statt 15 min zu warten).
    netz_wiederholen (RD1b, 10.11.2026, Prüfer zu RD1 081fd667): False = genau das alte Verhalten vor RD1 — zwei sofortige Versuche, keine Pause,
    dann nicht frei. Für polar-start: der Slave wird unabhängig ausgelöst, ein bis ~25 s späterer Master hieße Slave offen ohne Master."""
    import urllib.request
    pid = str(plan_id or "").strip().lower()
    r = str(richtung or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f-]{36}", pid) or r not in ("buy", "sell"):
        return True, "", ""
    tok = code_token()
    if not tok:
        return False, ("Riegel-Prüfung (Gegenrichtung) nicht möglich: code_token.txt fehlt — den Prophos-Tab an diesem PC einmal "
                       "neu laden (legt den Schlüssel ab). Nichts gesendet."), "riegel_unerreichbar"
    fehler = ""
    netz_n = sonst_n = 0
    while True:
        netz = False
        try:
            req = urllib.request.Request(CODE_QUELLE + "/richtung/frei",
                                         data=json.dumps({"plan_id": pid, "richtung": r}).encode("utf-8"),
                                         headers={"X-Code-Token": tok, "User-Agent": "prophos-panel", "Content-Type": "application/json"},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.loads(resp.read().decode("utf-8") or "{}")
            if isinstance(d, dict) and d.get("ok") is True:
                if d.get("frei") is True:
                    return True, "", ""
                # PULS BLEIBT ZU HAUSE (19.10.2026, Finn): Railway sagt zusaetzlich, ob ein Big Trade DIESES PCs nah am TP/an der Liq ist
                # (code big_trade_nah / big_trade_unklar, Grund schon vollstaendig) — dann kein Kontowechsel. Ohne code: Gegenrichtung wie bisher.
                code = str(d.get("code") or "gegenrichtung")
                if code != "gegenrichtung":
                    if isinstance(zweit_aus, dict) and d.get("zweit") is True:
                        zweit_aus["zweit"] = True
                        for k, n in (("zweit_art", 20), ("zweit_code", 20), ("bis", 40), ("firma", 60)):   # zweit_code/bis/firma: S6 (Z5)
                            if d.get(k):
                                zweit_aus[k] = str(d.get(k))[:n]
                    return False, str(d.get("grund") or "Big Trade auf diesem PC nah am TP/an der Liq — Puls bleibt im Konto"), code
                return False, "Gegenrichtung gesperrt: " + str(d.get("grund") or "bei dieser ID läuft dort ein Trade in Gegenrichtung"), "gegenrichtung"
            fehler = str((d or {}).get("msg") or "unklare Antwort")[:160]
        except Exception as e:
            fehler = str(e)[:160]
            netz = riegel_netzfehler(e)
        if netz and netz_wiederholen and netz_n < RIEGEL_NETZ_WIEDERHOLEN:
            pause = random.uniform(*RIEGEL_NETZ_PAUSE_S[min(netz_n, len(RIEGEL_NETZ_PAUSE_S) - 1)])
            netz_n += 1
            print(f"[riegel] Netzfehler ({fehler[:80]}) — Versuch {netz_n + 1} in {pause:.1f} s", flush=True)
            time.sleep(pause)
            continue
        if (not netz or not netz_wiederholen) and sonst_n < 1:
            sonst_n += 1                                 # wie bisher: ein sofortiger zweiter Versuch bei HTTP-Fehler/unklarer Antwort (RD1b: ohne netz_wiederholen auch bei Netzfehler)
            continue
        break
    if netz_n:
        fehler = f"{fehler} (nach {netz_n + 1} Versuchen mit Pause)"
    return False, f"Riegel-Prüfung (Gegenrichtung) nicht erreichbar: {fehler} — nichts gesendet, der Start wird später erneut versucht.", "riegel_unerreichbar"


def riegel_pflicht_fehlt(plan_id, richtung):
    """FAIL-CLOSED VOR DEM SCHARFEN KLICK (30.10.2026, ORBIT-RICHTUNG-RIEGEL, Befund S5: Orbit schickte die Richtung nur als Marke
    @richtung= — richtung_frei bekam '' und gab frei, 0 Riegel-Fehlstarts bei tvv2). richtung_frei laesst Proben ohne Plan/Richtung
    durch; bei einer Order-Aktion (scharf) darf das nicht sein. -> Fehlermeldung (str) oder '' wenn beides da ist."""
    pid = str(plan_id or "").strip().lower()
    r = str(richtung or "").strip().lower()
    if re.fullmatch(r"[0-9a-f-]{36}", pid) and r in ("buy", "sell"):
        return ""
    fehlt = " und ".join(x for x, ok in (("Plan-ID", re.fullmatch(r"[0-9a-f-]{36}", pid)), ("Richtung", r in ("buy", "sell"))) if not ok)
    return (f"Richtungs-Riegel nicht pruefbar: die Order kam ohne {fehlt} (alter Prophos-Tab?) — den Prophos-Tab an diesem PC neu "
            "laden. Nichts gesendet.")


def repo_sha(timeout=8):
    """Kennung des neuesten Commits auf main — oder None (kein Netz o.ae.). Zuerst Railway, sonst GitHub."""
    roh = code_holen("/code/stand", timeout)
    try:
        sha = (json.loads(roh.decode("utf-8")) or {}).get("sha") if roh else None
        if sha and re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
    except Exception:
        pass
    import urllib.request
    try:
        req = urllib.request.Request(
            f"https://github.com/{_REPO}.git/info/refs?service=git-upload-pack",
            headers={"User-Agent": "git/2.40"})
        roh = urllib.request.urlopen(req, timeout=timeout).read()
        m = re.search(rb"([0-9a-f]{40}) refs/heads/main", roh)
        return m.group(1).decode("ascii") if m else None
    except Exception:
        return None


def repo_datei(pfad, sha=None, timeout=15):
    """Datei aus dem Repo — mit sha aus genau diesem Stand, sonst von main. Zuerst Railway, sonst GitHub."""
    data = code_holen(f"/code/datei/{pfad}" + (f"?sha={sha}" if sha else ""), timeout)
    if data is not None:
        return data
    import urllib.request
    url = f"https://raw.githubusercontent.com/{_REPO}/{sha or 'main'}/{pfad}"
    return urllib.request.urlopen(url, timeout=timeout).read()


def ensure_bot_source(sha=None):
    """order_bot.py aus dem Repo holen/aktuell halten (15.08.2026, erster
    Bot-Test: 'keine Antwort vom Bot' — die Datei lag gar nicht auf dem PC).
    Seit 22.09.2026 an den NEUESTEN STAND gebunden statt an 'main' (siehe
    oben) und nur ersetzt, wenn der neue Inhalt fehlerfrei uebersetzt — der
    Bot wird bei jedem Aufruf frisch gestartet, ein Austausch wirkt also
    sofort, OHNE Panel-Neustart. -> True, wenn ersetzt wurde."""
    dst = os.path.join(HERE, "order_bot.py")
    try:
        sha = sha or repo_sha()
        data = repo_datei("mt5-copier/order_bot.py", sha)
        try:
            if len(data) < 500 or b"def run(" not in data:
                raise ValueError(f"nur {len(data)} Bytes bzw. ohne run()")
            compile(data, "order_bot.py", "exec")      # kaputte Datei ersetzt nie eine laufende
        except (ValueError, SyntaxError) as e_:
            if sha and BOT_STAND.get("kaputt_sha") != sha:
                print(f"[panel] order_bot.py im Stand {sha[:7]} unbrauchbar ({type(e_).__name__}: {str(e_)[:80]}) — alter Bot bleibt, "
                      "kein neuer Versuch für diesen Stand.", flush=True)
            BOT_STAND["kaputt_sha"] = sha
            return False
        old = b""
        if os.path.exists(dst):
            with open(dst, "rb") as f:
                old = f.read()
        if sha:
            BOT_STAND["sha"] = sha
            try:
                BOT_STAND["version"] = repo_datei("mt5-copier/VERSION", sha, 10).decode("utf-8", "replace").strip()[:30]
            except Exception:
                pass
        if data != old:
            tmp = dst + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dst)
            BOT_STAND["geholt_sha"] = sha
            print(f"[panel] order_bot.py aktualisiert ({len(data)} Bytes, Stand "
                  f"{(sha or 'main')[:7]}, {BOT_STAND.get('version') or '?'}).", flush=True)
            return True
        BOT_STAND["geholt_sha"] = sha                  # Inhalt schon gleich — auch das ist „liegt vor"
    except Exception as e:
        print(f"[panel] order_bot.py-Download fehlgeschlagen ({type(e).__name__}) — "
              f"Order-Schritt meldet das klar, wenn er gebraucht wird.", flush=True)
    return False


# BOT VORKOMPILIERT STARTEN (SW1b, 05.11.2026, Befund SW1: jede Bot-Aktion — tvlesen, tvkonto, Endlesung, loginok, augen … — ist ein neuer
# python-Prozess, der order_bot.py (~29.500 Zeilen) jedes Mal neu übersetzt, ~1 s CPU je Start auf den PCs). Jetzt startet ein kleiner -c-Starter
# den Bot als IMPORTIERTES Modul mit .pyc im __pycache__ neben der Datei (derselbe Ordner, den die `python -c "import order_bot …"`-Aufrufe des
# Panels schon seit Wochen benutzen — vom Virenscanner nachweislich nicht geblockt). Kein veraltetes .pyc: das .pyc ist „checked-hash" — Python
# vergleicht bei JEDEM Start den Inhalt (Hash) von order_bot.py mit dem .pyc und übersetzt neu, sobald die Datei anders ist (Update per
# ensure_bot_source, egal wie Zeitstempel/Größe stehen); ein .pyc ohne Hash-Prüfung (vom -c-Import) wird beim ersten Start ersetzt.
# Ablauf, Takte und Wege des Bots bleiben gleich: sys.argv wie beim Skriptstart ([bot, modus, …]), sys.path[0] = Bot-Ordner, __main__.__file__ =
# order_bot.py (fehlerfoto_huelle_einbauen erkennt den Bot-Prozess daran), Rückgabewert = main(). RÜCKFALL: scheitert Übersetzen/Laden VOR main()
# (kein Schreibrecht, Importfehler …), läuft der alte Weg runpy.run_path(…, "__main__") = genau `python order_bot.py` und das .pyc wird gelöscht (ein
# kaputtes .pyc heilt sich so beim nächsten Start; die Modul-Ebene von order_bot.py hat keine Seiteneffekte); ein Fehler IN main() wird nie
# wiederholt (keine zweite Order). Ganz abschalten: Datei bot_ohne_cache.flag neben dem Bot → wieder [python, order_bot.py].
# DIESELBE Zeichenkette steht in order_bot.py (BOT_STARTER_CODE, Selbststarts augen/fehlerfoto/tsxbleiben) — Selbsttest prüft Gleichheit.
BOT_STARTER_CODE = (
    "import sys, os\n"
    "bot = os.path.abspath(sys.argv[1])\n"
    "sys.argv = [bot] + sys.argv[2:]\n"
    "if sys.path and sys.path[0] == '':\n"
    "    sys.path[0] = os.path.dirname(bot)\n"
    "else:\n"
    "    sys.path.insert(0, os.path.dirname(bot))\n"
    "__file__ = bot\n"
    "try:\n"
    "    import importlib.util, py_compile\n"
    "    pyc = importlib.util.cache_from_source(bot)\n"
    "    try:\n"
    "        with open(pyc, 'rb') as f:\n"
    "            kopf = f.read(16)\n"
    "    except OSError:\n"
    "        kopf = b''\n"
    "    if len(kopf) < 16 or int.from_bytes(kopf[4:8], 'little') != 3:\n"
    "        py_compile.compile(bot, cfile=pyc, doraise=True, invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)\n"
    "except Exception:\n"
    "    pass\n"
    "try:\n"
    "    import importlib\n"
    "    _ob = importlib.import_module(os.path.splitext(os.path.basename(bot))[0])\n"
    "except Exception:\n"
    "    _ob = None\n"
    "if _ob is None:\n"
    "    try:\n"
    "        os.remove(importlib.util.cache_from_source(bot))\n"
    "    except Exception:\n"
    "        pass\n"
    "    import runpy\n"
    "    runpy.run_path(bot, run_name='__main__')\n"
    "    sys.exit(0)\n"
    "sys.exit(_ob.main())\n"
)


def bot_argv(bot):
    """Aufruf des Order-Bots ohne die Argumente danach (SW1b): [python, -c, Starter, bot] — mit bot_ohne_cache.flag neben dem Bot der alte Weg
    [python, bot]. Die Argumente (modus, Befehl …) folgen wie bisher."""
    try:
        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(bot)), "bot_ohne_cache.flag")):
            return [sys.executable, bot]
    except Exception:
        return [sys.executable, bot]
    return [sys.executable, "-c", BOT_STARTER_CODE, bot]


def ensure_pywinauto():
    """Klick-Bot-Abhaengigkeit selbst installieren (15.08.2026, Finns Ansage:
    die Order muss per SICHTBAREM Mausklick laufen — pywinauto steuert Maus und
    Dialog). Best effort beim Panel-Start, damit kein Handgriff noetig ist."""
    if os.name != "nt":
        return
    try:
        import pywinauto  # noqa: F401
        return
    except ImportError:
        pass
    print("[panel] pywinauto fehlt — installiere einmalig (pip, kann ~1 min dauern)...", flush=True)
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "pywinauto"],
                           capture_output=True, text=True, errors="replace", timeout=300)
        print("[panel] pywinauto installiert." if r.returncode == 0 else
              f"[panel] pywinauto-Installation fehlgeschlagen — von Hand: pip install pywinauto "
              f"({(r.stderr or '').strip()[-160:]})", flush=True)
    except Exception as e:
        print(f"[panel] pywinauto-Installation fehlgeschlagen ({type(e).__name__}) — "
              f"von Hand: pip install pywinauto", flush=True)


# METATRADER5-PAKET (08.10.2026, Jacob The5%ers 72c2a073 rot: „MetaTrader5-Paket fehlt" im Order-Bot auf einem PC, der morgens noch
# platziert hatte; die Copier dort liefen mit dem Paket weiter). Der Bot läuft je Order als eigener Prozess mit dem Python des Panels
# (sys.executable) — das Panel selbst braucht nur die Standardbibliothek und merkte nichts. Jetzt prüft das Panel beim Start und alle
# 30 min GENAU so (eigener Prozess, gleiches Python, gleicher Ordner), installiert NUR, wenn pip das Paket nicht kennt (wie
# ensure_pywinauto, höchstens einmal je Stunde, ohne --upgrade — Prüfer Slave 2: laufen die Copier mit demselben Python, sind ihre
# .pyd/.dll gesperrt und ein Upgrade ließe ein halb gelöschtes Paket zurück; ist es installiert und der Import bricht trotzdem, hilft
# pip nicht → nur melden) und meldet den Stand: Konsole + Snapshot mt5_update.paket → Prophos (mt5_live.status, Admin → PC-Tabs).
MT5_PAKET = {"ok": None, "version": None, "fehler": None, "python": sys.executable, "at": None, "installiert_at": None, "pip_kennt": None,
             "app_sperre": False}


def _app_steuerung_sperre(text):
    """Windows' Intelligente App-Steuerung / WDAC blockt eine DLL (Jacobs PC 08.10.2026: „Eine Anwendungssteuerungsrichtlinie hat diese
    Datei blockiert", WinError 4551) — dann hilft pip nie; laufende Prozesse haben die DLL schon, jeder neue scheitert."""
    t = str(text or "").lower()
    return "anwendungssteuerungsrichtlinie" in t or "application control policy" in t or "winerror 4551" in t


def _mt5_paket_pruefen():
    try:
        r = subprocess.run([sys.executable, "-c", "import MetaTrader5 as m; print(m.__version__)"], cwd=HERE,
                           capture_output=True, text=True, errors="replace", timeout=90)
        if r.returncode == 0:
            return True, (r.stdout or "").strip()[-40:], None
        zeilen = [z for z in (r.stderr or "").strip().splitlines() if z.strip()]
        return False, None, (zeilen[-1] if zeilen else f"Exit {r.returncode}")[:200]
    except Exception as e:
        return False, None, f"{type(e).__name__}: {e}"[:200]


def ensure_metatrader5():
    """Einmal prüfen (+ bei Bedarf installieren) — siehe MT5_PAKET. Läuft im Hintergrund-Thread, blockiert den Start nie."""
    if os.name != "nt":
        return
    ok, ver, fehler = _mt5_paket_pruefen()
    kennt = None
    sperre = (not ok) and _app_steuerung_sperre(fehler)
    MT5_PAKET["app_sperre"] = sperre
    if not ok and not sperre:
        try:
            kennt = subprocess.run([sys.executable, "-m", "pip", "show", "MetaTrader5"], capture_output=True, text=True,
                                   errors="replace", timeout=60).returncode == 0
        except Exception:
            kennt = None                                   # pip nicht prüfbar → lieber nicht installieren
    MT5_PAKET["pip_kennt"] = kennt
    if not ok and kennt is False and time.time() - (MT5_PAKET.get("_inst_t") or 0) > 3600:
        MT5_PAKET["_inst_t"] = time.time()
        print(f"[panel] MetaTrader5-Paket fehlt im Panel-Python ({fehler}) — installiere (pip, kann ~1 min dauern) ...", flush=True)
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "MetaTrader5"],
                               capture_output=True, text=True, errors="replace", timeout=300)
            if r.returncode == 0:
                MT5_PAKET["installiert_at"] = datetime.now().astimezone().isoformat()
            else:
                print(f"[panel] pip install MetaTrader5 fehlgeschlagen ({(r.stderr or '').strip()[-160:]})", flush=True)
        except Exception as e:
            print(f"[panel] pip install MetaTrader5 fehlgeschlagen ({type(e).__name__})", flush=True)
        ok, ver, fehler = _mt5_paket_pruefen()
    war = MT5_PAKET.get("ok")
    MT5_PAKET.update(ok=ok, version=ver, fehler=fehler, at=datetime.now().astimezone().isoformat())
    if sperre:
        print(f"[panel] ⚠ Windows blockiert MetaTrader5 (Intelligente App-Steuerung): {fehler} — Echo-Starts scheitern, laufende "
              f"Copier laufen weiter, starten aber nach einem Neustart nicht mehr. Am PC: Windows-Sicherheit → App- & Browsersteuerung → "
              f"Intelligente App-Steuerung. NICHT neu installieren.", flush=True)
    elif not ok and kennt:
        print(f"[panel] ⚠ MetaTrader5 ist im Panel-Python {sys.executable} installiert, der Import bricht aber: {fehler} — "
              f"Echo-Starts scheitern; NICHT neu installieren, Fehler melden", flush=True)
    elif not ok:
        print(f"[panel] ⚠ MetaTrader5-Paket fehlt im Panel-Python {sys.executable}: {fehler} — Echo-Starts scheitern, "
              f"von Hand: \"{sys.executable}\" -m pip install MetaTrader5", flush=True)
    elif war is False:
        print(f"[panel] MetaTrader5-Paket wieder da ({ver}).", flush=True)


def _mt5_paket_waechter():
    while True:
        try:
            ensure_metatrader5()
        except Exception as e:
            print(f"[panel] MetaTrader5-Prüfung: {type(e).__name__}", flush=True)
        time.sleep(1800)


def _ensure_ea_compiled(fname, install_dir):
    """EA pro Terminal automatisch kompilieren (15.08.2026): MetaEditor liegt
    neben jeder terminal64.exe und kann per Kommandozeile kompilieren — der
    F4→F7-Handgriff entfaellt damit fuer immer, und EA-Updates aus dem Repo
    erreichen die ganze Flotte von selbst. Laeuft nur beim Kalt-Start (Terminal
    aus); kompiliert wird, wenn die .ex5 fehlt oder die .mq5 neuer ist."""
    data_dir = provision.data_dir_for(install_dir)
    if not data_dir:
        return
    experts = os.path.join(data_dir, "MQL5", "Experts")
    src_repo = os.path.join(HERE, provision.EA_NAME + ".mq5")
    src = os.path.join(experts, provision.EA_NAME + ".mq5")
    ex5 = os.path.join(experts, provision.EA_NAME + ".ex5")
    try:
        # Repo-Quelle in den Datenordner spiegeln, wenn sie sich unterscheidet
        if os.path.exists(src_repo):
            new = open(src_repo, "rb").read()
            old = open(src, "rb").read() if os.path.exists(src) else b""
            if new != old:
                os.makedirs(experts, exist_ok=True)
                with open(src, "wb") as f:
                    f.write(new)
        if not os.path.exists(src):
            return
        if os.path.exists(ex5) and os.path.getmtime(ex5) >= os.path.getmtime(src):
            return  # aktuell — nichts zu tun
        me = os.path.join(install_dir, "metaeditor64.exe")
        if not os.path.exists(me):
            print(f"[panel] {fname}: metaeditor64.exe fehlt in {install_dir} — "
                  f"EA einmal von Hand kompilieren (F4 -> F7).", flush=True)
            return
        logf = src + ".log"
        subprocess.run([me, f"/compile:{src}", f"/log:{logf}"],
                       capture_output=True, timeout=90)
        if os.path.exists(ex5) and os.path.getmtime(ex5) >= os.path.getmtime(src):
            print(f"[panel] {fname}: {provision.EA_NAME} kompiliert (v-aktuell).", flush=True)
        else:
            tail = ""
            try:
                # MetaEditor-Logs sind UTF-16
                with open(logf, "rb") as f:
                    raw = f.read()
                tail = raw.decode("utf-16" if raw[:2] == b"\xff\xfe" else "utf-8",
                                  errors="replace")[-400:]
            except OSError:
                pass
            print(f"[panel] {fname}: EA-Kompilierung NICHT bestaetigt — von Hand pruefen "
                  f"(F4 -> F7). Log-Ende: {tail}", flush=True)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[panel] {fname}: EA-Kompilierung fehlgeschlagen ({type(e).__name__}).", flush=True)


def _pid_alive(pid):
    """Lebt der Prozess? Fuer den Loesch-Riegel (b2): stale Status heisst nicht
    toter Copier (Terminal-Ausfall schreibt gar nichts mehr). ACHTUNG Windows:
    os.kill(pid, 0) wuerde dort den Prozess BEENDEN (TerminateProcess) — deshalb
    tasklist. Im Zweifel (Fehler) gilt der Prozess als lebend ('unbekannt != leer')."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                                 capture_output=True, text=True, errors="replace", timeout=5).stdout
            return str(pid) in (out or "")
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def instances():
    """Alle Master-Configs -> [{name, config_file, status_file}]. Schlüssel für alle
    API-Aufrufe ist config_file — der abgeleitete Name ist reine Anzeige (Audit-Fund:
    config-master2.json und config_master2.json ergaben denselben Namen, und der
    Save traf die falsche Datei)."""
    out = []
    for fn in sorted(os.listdir(HERE)):
        if fn in TEMPLATES or not CONFIG_RE.fullmatch(fn):
            continue
        name = fn[len("config"):-len(".json")].lstrip("-_") or "standard"
        out.append({"name": name, "config_file": fn,
                    "status_file": re.sub(r"^config", "status", fn, count=1, flags=re.I)})
    return out


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def snapshot():
    data, conflicts = [], []
    seen_magic, seen_snap = {}, {}
    for inst in instances():
        cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
        age = None
        if st.get("updated_at"):
            try:
                age = round((datetime.now() - datetime.fromisoformat(st["updated_at"])).total_seconds())
            except Exception:
                age = None
        magic = cfg.get("magic", 770001)
        snapf = str(cfg.get("snapshot_file", "prophos_master.csv")).lower()
        seen_magic.setdefault(magic, []).append(inst["config_file"])
        seen_snap.setdefault(snapf, []).append(inst["config_file"])
        alive = bool(st.get("running")) and age is not None and age <= 15
        # Lese-Instanz (25.09.2026, Finn: „Warum sehe ich bei ID A nicht den Live-P&L, wenn es doch über
        # Echo V2 gemacht wurde?"): Echo V2 läuft absichtlich OHNE Copier — dann schrieb niemand
        # master_balance/-equity/-positionen, Baseline und Live-P&L blieben leer. Läuft der Copier nicht,
        # liest das Panel die Snapshot-Datei des Lese-EAs selbst (nur Datei, keine Terminal-Verbindung,
        # kein Hedge). alive bleibt dabei FALSCH — alive heißt „Copier hedgt", darauf verlassen sich die
        # Echo-Prüfungen mit Hedge; die Lese-Daten tragen nur das eigene Merkmal lesen.
        lesen = False
        if not alive:
            ls = lese_status(cfg)
            if ls:
                st = dict(st, **ls)
                lesen = True
        data.append({
            "name": inst["name"],
            "file": inst["config_file"],
            "multiplier": cfg.get("multiplier"),
            "symbol_map": cfg.get("symbol_map") or {},
            # Notfall-SL/TP-Einstellungen (27.08.2026) — fehlen sie in
            # Alt-Configs, zeigt die UI die Copier-Defaults 110 / 100.
            "notfall_faktor": cfg.get("notfall_faktor"),
            "notfall_puffer_min_punkte": cfg.get("notfall_puffer_min_punkte"),
            "magic": magic,
            "snapshot_file": cfg.get("snapshot_file"),
            "master_expected": cfg.get("master_expected_login"),
            "hedge_expected": cfg.get("hedge_expected_login"),
            "master_server": cfg.get("master_server"),
            "has_terminal": bool(cfg.get("master_terminal_path")),
            # Besitzer-Stempel (Paket E, 15.08.2026): Prophos blendet Instanzen
            # fremder User aus; ohne Stempel (Bestand) sieht sie jeder auf dem PC.
            "owner": cfg.get("prophos_owner"),
            "display_name": cfg.get("display_name"),
            "status": st,
            "age": age,
            # "lebt" = Statusdatei ist frisch. Der Copier schreibt alle ~3s.
            "alive": alive,
            # Master-Stand frisch aus der Snapshot-Datei, OHNE Copier (nur Echo V2 wertet das aus)
            "lesen": lesen,
        })
    # Konflikte, die der Copier beim Start mit Abbruch quittieren wuerde — hier
    # schon anzeigen, BEVOR jemand den Neustart auslöst.
    for magic, fs in seen_magic.items():
        if len(fs) > 1:
            conflicts.append(f"magic {magic} doppelt: {', '.join(fs)} — der Copier startet so nicht.")
    for snapf, fs in seen_snap.items():
        if len(fs) > 1:
            conflicts.append(f"snapshot_file '{snapf}' doppelt: {', '.join(fs)} — der Copier startet so nicht.")
    job = None
    if PROV_JOB:
        job = {"name": PROV_JOB["name"], "done": PROV_JOB["done"], "error": PROV_JOB["error"],
               "steps": [{"key": k, **PROV_JOB["steps"][k]} for k in PROV_STEPS]}
    # Copier-Log-Spiegel (26.08.2026, Finns Wunsch: CMD-Meldungen in Prophos
    # lesen) — lebt auch, wenn der Copier beim Start abbricht und deshalb
    # keine status-*.json schreibt.
    clog = read_json(os.path.join(HERE, "copier-log.json"), {}) or {}
    return {"instances": data, "conflicts": conflicts, "job": job,
            "plans": advance_plans(data), "version": _local_version(),
            # LAUFENDER CODE (03.11.2026): „version“ ist nur die Datei — panel_lauf sagt, was dieser Prozess fährt (Start, PID, sha12)
            "panel_lauf": panel_lauf_info(),
            # Stand des Bots (kann dem Panel voraus sein — er wird ohne Neustart getauscht)
            "bot_version": BOT_STAND.get("version"),
            # FÄHIGKEITEN (ES2d, 05.11.2026, Prüfer S2): was dieses Panel durchreicht UND das order_bot.py kann, das es gleich startet — der Tab
            # lässt sein eigenes Warten auf „scharf“ nur mit 'scharf_pflicht' hier weg (eine Versionsnummer allein beweist das nicht)
            "bot_faehig": bot_faehig(),
            "copier_log": clog.get("lines") or [],
            "copier_log_at": clog.get("updated_at"),
            # Echo-Not-Aus (28.08.2026): Zustand fuers Pause/Start-Chip in Prophos
            "paused": os.path.exists(os.path.join(HERE, "echo_pause.flag")),
            # Stilles MT5-Update (08.10.2026): Aufgabe da? Builds ausstehend? → Prophos schreibt es nach mt5_live (Ferndiagnose UAC)
            "mt5_update": _mt5_update_stand(),
            # Knopf „MT5-Updates ohne Nachfrage einrichten" (08.10.2026): Stand des letzten Klicks fürs Panel
            "mt5_update_job": dict(MT5_UPD_JOB)}


def patch_config(fname, patch):
    """Nur erlaubte Felder schreiben, Datei atomar ersetzen."""
    path = os.path.join(HERE, fname)
    cfg = read_json(path)
    if cfg is None:
        return False, f"{fname} nicht lesbar"
    changed = []
    for k, v in patch.items():
        if k not in WRITABLE:
            continue
        if k == "multiplier":
            try:
                v = float(v)
            except (TypeError, ValueError):
                return False, f"{k}: '{v}' ist keine Zahl"
            if v <= 0:
                return False, f"{k} muss groesser als 0 sein"
        if k == "notfall_faktor":
            try:
                v = float(v)
            except (TypeError, ValueError):
                return False, f"{k}: '{v}' ist keine Zahl"
            # Unter 100% laege der Notfall-Level VOR dem Master-Level und
            # wuerde den Hedge schliessen, bevor der Master ausgestoppt ist.
            if not (100 <= v <= 1000):
                return False, "Notfall-Faktor muss zwischen 100 und 1000 (%) liegen"
        if k == "notfall_puffer_min_punkte":
            try:
                v = float(v)
            except (TypeError, ValueError):
                return False, f"{k}: '{v}' ist keine Zahl"
            if v < 0:
                return False, "Mindest-Puffer darf nicht negativ sein"
        if k == "symbol_map":
            if not isinstance(v, dict):
                return False, "symbol_map muss Text→Text sein"
            for a, b in v.items():
                if not isinstance(a, str) or not isinstance(b, str) \
                        or not SYMBOL_RE.fullmatch(a) or not SYMBOL_RE.fullmatch(b):
                    # Verengt auf Symbolzeichen — haelt auch Anfuehrungszeichen aus dem
                    # HTML fern (Audit-Fund: ein " im Symbolfeld verdrehte die Karte).
                    return False, f"Symbol ungueltig: '{a}' → '{b}'"
        if cfg.get(k) != v:
            cfg[k] = v
            changed.append(k)
    if not changed:
        return True, "keine Aenderung"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return True, "gespeichert: " + ", ".join(changed)


# ── Trade-Plaene: geplant -> laufend -> beendet (15.08.2026, Prophos-Logik) ────
# Ein Plan entsteht beim "Trade starten" (geplant), wechselt AUTOMATISCH auf
# "laufend", sobald der Master wirklich eine Position oeffnet, und auf
# "beendet", wenn sie wieder zu ist — getrieben vom Positionsstand aus den
# status*.json, nicht von Klicks. Ein aktiver Plan (geplant/laufend) pro
# Account; ein erneuter Start aktualisiert ihn nur.
PLANS_FILE = os.path.join(HERE, "plans.json")
PLANS_LOCK = threading.Lock()


def _load_plans():
    return read_json(PLANS_FILE, []) or []


def _save_plans(plans):
    tmp = PLANS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plans, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PLANS_FILE)


def upsert_plan(file, name, multiplier):
    with PLANS_LOCK:
        plans = _load_plans()
        now = datetime.now().isoformat(timespec="seconds")
        for p in plans:
            if p["file"] == file and p["status"] in ("geplant", "laufend"):
                p.update({"multiplier": multiplier, "armed_at": now})
                _save_plans(plans)
                return p
        pid = max([p["id"] for p in plans], default=0) + 1
        p = {"id": pid, "file": file, "name": name, "multiplier": multiplier,
             "created_at": now,
             "armed_at": now, "started_at": None, "ended_at": None,
             "status": "geplant"}
        plans.append(p)
        _save_plans(plans)
        return p


def _echo_fenster_offen(file):
    """Echo V2 (23.09.2026): hat diese Instanz ein offenes Trade-Fenster im Sinne des Copiers
    (copier.plan_armed_files: 'laufend' immer, 'geplant' 6 h ab armed_at)? Liefert den Plan-Namen,
    sonst None. Dieselbe Regel wie im Copier — bewusst hier nachgebaut statt importiert (copier.py
    haengt an MetaTrader5 und laeuft als eigener Prozess)."""
    now = datetime.now()
    with PLANS_LOCK:
        plans = _load_plans()
    for p in plans:
        if p.get("file") != file:
            continue
        st = p.get("status")
        if st == "laufend":
            return p.get("name") or "laufend"
        if st == "geplant":
            try:
                age = (now - datetime.fromisoformat(str(p.get("armed_at") or ""))).total_seconds()
            except (TypeError, ValueError):
                continue
            if age <= 6 * 3600:
                return p.get("name") or "geplant"
    return None


def delete_plan(pid):
    with PLANS_LOCK:
        plans = _load_plans()
        keep = [p for p in plans if p["id"] != pid]
        if len(keep) == len(plans):
            return False
        _save_plans(keep)
        return True


def _instances_snapshot():
    """Nur die Instanz-Daten (ohne den ganzen API-Payload) — fuer den
    Plan-Ticker, der die Zustandsmaschine unabhaengig vom Browser treibt."""
    out = []
    for inst in instances():
        st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
        age = None
        if st.get("updated_at"):
            try:
                age = round((datetime.now() - datetime.fromisoformat(st["updated_at"])).total_seconds())
            except Exception:
                age = None
        out.append({"file": inst["config_file"], "status": st, "age": age,
                    "alive": bool(st.get("running")) and age is not None and age <= 15})
    return out


def _plan_ticker():
    while True:
        time.sleep(5)
        try:
            advance_plans(_instances_snapshot())
        except Exception as e:
            print(f"[panel] plan-ticker: {type(e).__name__}: {e}", flush=True)


def advance_plans(instances_data):
    """Zustandsmaschine, bei jedem Status-Abruf ausgefuehrt (idempotent).
    Uebergaenge nur bei frischem, warnungsfreiem Master-Status — ein
    eingefrorener Snapshot darf keinen Plan faelschlich beenden."""
    ende_files = []
    with PLANS_LOCK:
        plans = _load_plans()
        by_file = {d["file"]: d for d in instances_data}
        now = datetime.now().isoformat(timespec="seconds")
        changed = False
        for p in plans:
            d = by_file.get(p["file"])
            if not d or not d.get("alive") or (d.get("status") or {}).get("note"):
                continue
            pos = len((d.get("status") or {}).get("master_positions") or [])
            if p["status"] == "geplant" and pos > 0:
                p["status"] = "laufend"
                p["started_at"] = now
                changed = True
            elif p["status"] == "laufend" and pos == 0:
                p["status"] = "beendet"
                p["ended_at"] = now
                # Auftrag AUF PLATTE vermerken (21.09.2026): der Zu-Worker lebt
                # nur im Speicher, und jeder VERSION-Bump beendet das Panel per
                # os._exit — der wartende Auftrag war dann weg und das Terminal
                # blieb offen (Finn: 'das hat nicht funktioniert'). Mit dem
                # Vermerk holt der naechste Panel-Start ihn nach.
                p["terminal_zu"] = "offen"
                changed = True
                # Trade-Ende = Terminal-Zu anstossen (03.09.2026, Finns Wunsch).
                # Erst NACH dem Lock — der Worker liest plans.json selbst.
                ende_files.append(p["file"])
        # Historie begrenzen: die letzten 50 beendeten reichen
        done = [p for p in plans if p["status"] == "beendet"]
        if len(done) > 50:
            drop = {p["id"] for p in done[:len(done) - 50]}
            plans = [p for p in plans if p["id"] not in drop]
            changed = True
        if changed:
            _save_plans(plans)
    for f in ende_files:
        _terminal_zu_starten(f, "Trade-Ende")
    return plans


# ── Master-Terminal zu, wenn kein Trade aktiv (03.09.2026, Finns Wunsch) ───────
# Die Master-Terminals sind laut Doktrin (25.08.2026, standby) absichtlich ZU
# und oeffnen erst beim Trade-Start — praktisch blieb aber jedes Terminal nach
# dem Trade offen, weil niemand es von Hand schliesst: die Flotte lief faktisch
# 24/7 wie ein VPS. Zwei Wege dagegen: (1) endet ein Trade-Plan (laufend →
# beendet), schliesst ein Worker das Master-Terminal der Instanz von selbst;
# (2) der Prophos-Knopf „Terminals ohne Trade schliessen" raeumt per
# /api/close-idle-terminals alles auf, was ohne Position/Hedge offen ist.
# Geschlossen wird NUR mit frischem, warnungsfreiem Copier-Status als Beweis —
# und nie, solange der Copier noch einen Hedge abzubauen hat (der Copier haengt
# am Hedge-Terminal, aber der finale 0-Positionen-Snapshot des Masters muss
# geschrieben und verarbeitet sein, bevor das Terminal verschwinden darf).
# Das Slave-/Hedge-Terminal bleibt immer offen: dort haengt der Copier, und es
# ist Finns eigenes Broker-Konto, keine Prop-Firm.
_TERMINAL_ZU_LOCK = threading.Lock()
_TERMINAL_ZU_AKTIV = set()   # config_files mit laufendem Zu-Worker


def terminal_schliessbar(cfg, st, age, plan_status=None, lese=None):
    """Reine Entscheidung (testbar, ohne I/O): darf das MASTER-Terminal dieser
    Instanz jetzt geschlossen werden? → (ja/nein, grund). Dieselbe strenge
    Beweis-Doktrin wie der Loesch-Riegel: ohne frischen Status keine Aktion.
    lese = lese_status(cfg) (Echo V2 ohne Copier): frischer Snapshot des Lese-EAs
    zählt als Beweis, wenn der Copier-Status nicht frisch ist (30.09.2026)."""
    mpath = str(cfg.get("master_terminal_path") or "").strip()
    if not mpath:
        return False, "kein Master-Terminal (Orbit/TV-Instanz oder Pfad fehlt)"
    # NIE die HEDGE-Installation (22.09.2026, Finn: "auf einmal oeffnet sich das
    # Slave-Hedge-Terminal von selbst"): zeigt master_terminal_path faelschlich in
    # denselben Ordner wie hedge_terminal_path, wuerde jeder Zu-Weg (Trade-Ende,
    # Leerlauf-Waechter, Knopf) das Hedge-Terminal killen — und der Copier startet
    # es Sekunden spaeter wieder. Derselbe Riegel wie in loesch_terminal_dir.
    hpath = str(cfg.get("hedge_terminal_path") or "").strip()
    if hpath:
        # Ordner beider Pfade — Trenner bewusst BEIDE (\ und /), damit der Vergleich
        # auch ausserhalb von Windows stimmt (Selftest laeuft auf dem Mac) und ein
        # leeres Ergebnis nie als "gleich" durchgeht.
        def _d(pfad):
            teil = re.split(r"[\\/]", str(pfad).strip().rstrip("\\/"))[:-1]
            return os.path.normcase("/".join(teil))
        if _d(mpath) and _d(mpath) == _d(hpath):
            return False, "Master- und Hedge-Terminal im selben Ordner — das Hedge-Terminal wird nie geschlossen"
    if plan_status:
        return False, f"Trade-Plan ist '{plan_status}'"
    frisch = bool(st.get("running")) and age is not None and age <= 15
    if not frisch:
        # Echo V2 läuft absichtlich OHNE Copier (25.09.2026) — dann war der Copier-Status nie frisch und
        # KEIN Terminal ging mehr zu (30.09.2026, ID A pc-aaaaaa: alle 7 Instanzen alive=false, 5–7
        # Terminals stundenlang offen). Beweis dann über den frischen Snapshot des Lese-EAs (≤ 15 s).
        # Meldet der letzte (alte) Copier-Stand noch einen Hedge, bleibt es beim Nein.
        if isinstance(lese, dict) and lese.get("lesen"):
            if any(hs for hs in (st.get("hedges") or {}).values()):
                return False, "letzter Copier-Stand meldet noch einen Hedge"
            lpos = len(lese.get("master_positions") or [])
            if lpos:
                return False, f"{lpos} offene Master-Position(en) (Lese-EA)"
            return True, "kein Trade aktiv (Lese-EA, Echo V2 ohne Copier)"
        return False, "Copier-Status nicht frisch — ob ein Trade laeuft, ist nicht beweisbar"
    if st.get("note"):
        return False, f"Status-Warnung: {st.get('note')}"
    pos = len(st.get("master_positions") or [])
    if pos:
        return False, f"{pos} offene Master-Position(en)"
    hed = sum(1 for hs in (st.get("hedges") or {}).values() if hs)
    if hed:
        return False, f"{hed} offene(r) Hedge(s) — Copier baut erst ab"
    return True, "kein Trade aktiv"


# ══ PL1 TERMINAL-ZU NIE WÄHREND EINES BOT-LAUFS (11.11.2026, Master nach Hinweis S2 aus VF3): terminal_schliessbar sah nur den Panel-Plan-Status — ein
# Start, eine Deal-Lesung oder ein Konto-Vorflug derselben Instanz hielt den Zu-Worker nicht auf (Plan noch nicht „geplant/laufend“ im Panel, Echo V2
# ohne Panel-Plan, Fern-Start). Jetzt schließen alle drei Zu-Wege (Trade-Ende-Worker, Leerlauf-Wächter, Knopf „Terminals ohne Trade schliessen“) nur
# über _terminal_kill_riegel: kein Kill, solange der MASTER_ORDER_LOCK der Instanz gehalten wird, DEALS_LESEN/VORFLUG_LESEN sie führt oder eine
# Order/ein Close angemeldet ist (ORDER_ANGEMELDET < ORDER_ANGEMELDET_S). Der Lock wird nur OHNE Warten genommen (blocking=False, sonst nächster Takt)
# und während des Schließens gehalten — eine Order, die genau dann kommt, bekommt 409 retry_ok (grund terminal_zu, nichts gesendet) statt eines
# Klicks in ein sterbendes Terminal. ══
TERMINAL_ZU_HAELT = set()   # config_files, deren MASTER_ORDER_LOCK gerade ein Terminal-Zu hält (Sekunden, nichts gesendet)


def terminal_zu_order_riegel(fname, locks, angemeldet, lesen, jetzt, angemeldet_s=60.0):
    """REIN RECHNEND (testbar, PL1): '' = kein Bot-Lauf auf dieser Instanz, sonst der Grund, warum das Master-Terminal jetzt nicht zugeht.
    locks = MASTER_ORDER_LOCKS, angemeldet = ORDER_ANGEMELDET, lesen = DEALS_LESEN | VORFLUG_LESEN."""
    if fname in (lesen or ()):
        return "Lese-Lauf (Deal-Historie/Konto-Vorflug) auf dieser Instanz"
    lk = (locks or {}).get(fname)
    if lk is not None and lk.locked():
        return "Order/Close läuft (MASTER_ORDER_LOCK der Instanz gehalten)"
    try:
        an = float((angemeldet or {}).get(fname) or 0.0)
    except (TypeError, ValueError):
        an = 0.0
    if an and jetzt - an < float(angemeldet_s):
        return f"Order/Close angemeldet (vor {max(0, int(jetzt - an))} s)"
    return ""


def _terminal_kill_riegel(fname, install_dir):
    """PL1 → (geschlossen: bool, pids: int, grund): Master-Terminal der Instanz schließen, nur ohne Bot-Lauf (terminal_zu_order_riegel) und unter dem
    eigenen MASTER_ORDER_LOCK (ohne Warten). pids 0 + geschlossen True = war schon zu. Wirft nicht für die Riegel; Kill-Fehler gehen an den Aufrufer."""
    grund = terminal_zu_order_riegel(fname, MASTER_ORDER_LOCKS, ORDER_ANGEMELDET, DEALS_LESEN | VORFLUG_LESEN, time.time(), ORDER_ANGEMELDET_S)
    if grund:
        return False, 0, grund
    # Merker VOR dem acquire setzen und NACH dem release entfernen (Prüfer PL1 SOLLTE, wie EA_FROST_HAELT): eine Order, deren acquire genau dazwischen
    # scheitert, sähe sonst keinen Merker und bekäme „läuft schon eine Order“ (retry_ok False) statt terminal_zu
    with MASTER_ORDER_GUARD:
        lock = MASTER_ORDER_LOCKS.setdefault(fname, threading.Lock())
        TERMINAL_ZU_HAELT.add(fname)
        if not lock.acquire(blocking=False):
            TERMINAL_ZU_HAELT.discard(fname)
            return False, 0, "MASTER_ORDER_LOCK der Instanz gerade belegt"
    try:
        # zwischen Prüfung und acquire angemeldet? (die Route meldet vor ihrem acquire an) — dann nicht schließen
        grund = terminal_zu_order_riegel(fname, {}, ORDER_ANGEMELDET, DEALS_LESEN | VORFLUG_LESEN, time.time(), ORDER_ANGEMELDET_S)
        if grund:
            return False, 0, grund
        pids = provision.terminal_pids(install_dir)
        for pid in pids:
            provision._taskkill(pid, grace_s=5)
        return True, len(pids), ""
    finally:
        lock.release()
        TERMINAL_ZU_HAELT.discard(fname)


def loesch_terminal_dir(cfg, andere_cfgs):
    """Reine Entscheidung (testbar, ohne I/O): welcher Master-Terminal-Ordner
    darf nach dem Loeschen DIESER Config mit geschlossen werden? None = keiner.
    (07.09.2026, Archiv-Loeschauftrag: Finn will beim Archivieren das Terminal
    des Accounts loswerden — ohne diesen Schritt liefe die terminal64.exe nach
    der Config-Loeschung kopflos weiter, denn der Terminal-Zu-Worker bricht
    bei geloeschter Config bewusst ab.)
    Die Beweis-Last (flach, kein Hedge, kein laufender Plan) tragen die
    Loesch-Riegel des Aufrufers — hier geht es nur darum, NIE ein Terminal zu
    schiessen, das jemand anders braucht: das Hedge-/Slave-Terminal (dort
    haengt der Copier, und es ist Finns eigenes Broker-Konto) oder die
    Installation einer ANDEREN Instanz (sollte es per Provisionierung nie
    geben — Klon pro Account — aber 'sollte nie' ist kein Riegel)."""
    def _dir(p):
        p = str(p or "").strip()
        return os.path.normcase(os.path.dirname(os.path.abspath(p))) if p else None
    d = _dir((cfg or {}).get("master_terminal_path"))
    if not d:
        return None  # Orbit/TV-Instanz oder Pfad fehlt
    if d == _dir((cfg or {}).get("hedge_terminal_path")):
        return None  # Master- und Hedge-Pfad im selben Ordner (Fehlkonfiguration)
    for c in (andere_cfgs or []):
        for key in ("master_terminal_path", "hedge_terminal_path"):
            if d == _dir((c or {}).get(key)):
                return None  # Ordner wird von einer anderen Config genutzt
    return d


def _terminal_zu_starten(fname, ausloeser):
    """Startet den Zu-Worker fuer eine Instanz — hoechstens einen zur Zeit."""
    cfg = read_json(os.path.join(HERE, fname), {}) or {}
    if not str(cfg.get("master_terminal_path") or "").strip():
        # Orbit/TV-Instanzen: der Master ist ein Browser, kein Terminal
        _terminal_zu_erledigt(fname)
        return
    with _TERMINAL_ZU_LOCK:
        if fname in _TERMINAL_ZU_AKTIV:
            return
        _TERMINAL_ZU_AKTIV.add(fname)
    threading.Thread(target=_terminal_zu_worker, args=(fname, ausloeser), daemon=True).start()


def _zufalls_verzoegerung():
    """Zufaellige Wartezeit vor dem Auto-Zu: 1 bis 2 Minuten, pro Trade neu
    gewuerfelt (21.09.2026, Finn: 'wenn der Trade in Take Profit oder Stop Loss
    ist, nach ein, zwei Minuten einfach das Terminal schliessen' — die offenen
    Terminals ziehen Leistung vom PC). Vorher 1-60 min (04.09.2026): so lange
    ueberlebte der Auftrag praktisch nie, weil jeder VERSION-Bump das Panel
    neu startet. Gewuerfelt bleibt es — ein Terminal, das nach JEDEM Trade im
    immer gleichen Sekunden-Abstand zugeht, waere selbst ein Muster (dieselbe
    Jitter-Doktrin wie bei allen Puls-Wartezeiten)."""
    return random.uniform(60, 120)


def _terminal_zu_erledigt(fname):
    """Loescht den 'offen'-Vermerk aller beendeten Plaene dieser Instanz — egal
    wie der Worker endete (zu, schon zu, abgebrochen, aufgegeben): ein zweiter
    Anlauf nach dem naechsten Panel-Start wuerde sonst ein Terminal schliessen,
    das Finn inzwischen bewusst von Hand geoeffnet hat."""
    with PLANS_LOCK:
        plans = _load_plans()
        treffer = [p for p in plans if p.get("file") == fname and p.get("terminal_zu")]
        for p in treffer:
            p.pop("terminal_zu", None)
        if treffer:
            _save_plans(plans)


def terminal_zu_nachholen():
    """Beim Panel-Start: Zu-Auftraege nachholen, die ein Neustart (Selbst-Update,
    Absturz, PC-Reboot) mitten in der Wartezeit abgeschnitten hat. Der Worker
    prueft alles selbst neu — neuer Plan, offene Position, frischer Status."""
    for fname in sorted({p["file"] for p in _load_plans()
                         if p.get("status") == "beendet" and p.get("terminal_zu") == "offen"}):
        _terminal_zu_starten(fname, "Trade-Ende, nachgeholt nach Panel-Neustart")


def _terminal_zu_worker(fname, ausloeser):
    """Wuerfelt erst eine Zufalls-Verzoegerung (s. _zufalls_verzoegerung), wartet
    dann (bis 3 min), bis die Instanz beweisbar flach ist — der Copier braucht
    nach dem Master-Close ein paar Sekunden, um den Hedge abzubauen — und
    schliesst dann das Master-Terminal. Bricht ab, sobald ein neuer Plan scharf
    wird oder wieder Positionen auftauchen (naechster Trade laeuft an; dessen
    eigenes Trade-Ende startet einen frischen Worker)."""
    grund = "?"
    try:
        status_fn = re.sub(r"^config", "status", fname, count=1, flags=re.I)
        warte_s = _zufalls_verzoegerung()
        print(f"[panel] {fname}: Terminal-Zu in ~{max(1, round(warte_s / 60))} min "
              f"geplant ({ausloeser} + Zufalls-Streuung).", flush=True)
        frei_ab = time.time() + warte_s
        deadline = frei_ab + 180
        while time.time() < deadline:
            cfg = read_json(os.path.join(HERE, fname), {}) or {}
            if not cfg:
                # Config weg = Instanz geloescht (Archiv-Loeschauftrag 07.09.2026).
                # Die Loeschung schliesst das Terminal selbst (terminal_zu) — bis
                # dahin lief dieser Worker ins Leere ('kein Master-Terminal') und
                # gab erst an der Deadline auf. Ehrlich benennen und sofort raus.
                print(f"[panel] {fname}: Terminal-Zu abgebrochen — Config geloescht.",
                      flush=True)
                return
            st = read_json(os.path.join(HERE, status_fn), {}) or {}
            age = None
            try:
                age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
            except (ValueError, TypeError):
                pass
            plan_status = next((p["status"] for p in _load_plans()
                                if p["file"] == fname and p["status"] in ("geplant", "laufend")), None)
            if plan_status:
                print(f"[panel] {fname}: Terminal-Zu abgebrochen — neuer Trade-Plan ist "
                      f"'{plan_status}'.", flush=True)
                return
            frisch = bool(st.get("running")) and age is not None and age <= 15
            lese = None if frisch else lese_status(cfg)
            if (frisch and not st.get("note") and (st.get("master_positions") or [])) or \
                    (lese and (lese.get("master_positions") or [])):
                print(f"[panel] {fname}: Terminal-Zu abgebrochen — Master hat wieder "
                      f"Positionen.", flush=True)
                return
            # Zufalls-Streuung noch nicht um: nur die Abbruch-Wachen laufen,
            # geschlossen wird erst nach Ablauf der gewuerfelten Wartezeit.
            if time.time() < frei_ab:
                time.sleep(5)
                continue
            ok, grund = terminal_schliessbar(cfg, st, age, plan_status, lese)
            if ok:
                install_dir = os.path.dirname(os.path.abspath(str(cfg["master_terminal_path"])))
                # PL1: nie während eines Bot-Laufs dieser Instanz (Lock ohne Warten, sonst nächster Takt)
                zu, n, grund_r = _terminal_kill_riegel(fname, install_dir)
                if zu:
                    print(f"[panel] {fname}: " + (f"Master-Terminal geschlossen ({ausloeser})." if n else f"Terminal war schon zu ({ausloeser})."),
                          flush=True)
                    return
                grund = grund_r
            time.sleep(5)
        # Ehrlich benennen statt still aufgeben (Muster TronGrid-429, 25.08.2026)
        print(f"[panel] {fname}: Terminal-Zu nach {ausloeser} aufgegeben — zuletzt: {grund}.",
              flush=True)
    except Exception as e:
        print(f"[panel] {fname}: Terminal-Zu-Fehler: {type(e).__name__}: {e}", flush=True)
    finally:
        with _TERMINAL_ZU_LOCK:
            _TERMINAL_ZU_AKTIV.discard(fname)
        try:
            _terminal_zu_erledigt(fname)
        except Exception as e:
            print(f"[panel] {fname}: Terminal-Zu-Vermerk nicht loeschbar: "
                  f"{type(e).__name__}: {e}", flush=True)


# ── Leerlauf-Waechter: Terminal ohne Trade geht nach 15 min von selbst zu ─────
# (22.09.2026, Finn: "so oft sehe ich unter Accounts Terminals, die seit Stunden
# oder Tagen offen sind, wo kein Trade laeuft — wenn kein Trade auf dem Terminal
# laeuft, soll es einfach automatisch geschlossen werden"). Der Trade-Ende-
# Worker oben haengt an einem Plan-Ereignis und wird von jedem Panel-Neustart
# gekappt; Trades ohne Panel-Plan sieht er gar nicht. Dieser Waechter braucht
# kein Ereignis: er prueft alle 60 s jede Echo-Instanz mit terminal_schliessbar
# (frischer, warnungsfreier Status, keine Position, kein Hedge, kein Plan
# geplant/laufend) und schliesst, wenn das nachweislich seit LEERLAUF_MIN Minuten
# ununterbrochen so ist — ein Terminal, das Finn gerade fuer den naechsten Trade
# oeffnet, ist dann laengst per Plan 'geplant' und bleibt. Zufalls-Streuung auf
# die Schwelle (Jitter-Doktrin), damit kein festes Muster entsteht.
LEERLAUF_MIN = 15.0
_LEERLAUF_SEIT = {}     # config_file -> Zeitpunkt, seit dem die Instanz beweisbar leer laeuft
_LEERLAUF_SCHWELLE = {} # config_file -> gewuerfelte Schwelle in Sekunden


def leerlauf_entscheidung(schliessbar, seit, jetzt, schwelle_s):
    """Reine Entscheidung (testbar): (neues 'seit', jetzt schliessen?).
    schliessbar False -> Zaehler zurueck (None). True -> Zaehler laeuft ab dem
    ersten leeren Blick; schliessen, sobald jetzt - seit >= schwelle_s."""
    if not schliessbar:
        return None, False
    if seit is None:
        return jetzt, False
    return seit, (jetzt - seit) >= schwelle_s


# ── Nach dem PC-Start: Master-Terminals mit laufendem Trade wieder oeffnen (01.10.2026) ─────
# Finn: „wenn ich starte, soll alles hochfahren, was ich irgendwie brauche". Master-Terminals oeffnen sonst nur beim
# Trade-Start — lief beim Ausschalten ein Echo-Trade, blieb sein Terminal nach dem Neustart zu und der Copier sah den Master
# nicht mehr. Die Status-Datei der Instanz ueberlebt den Neustart: stand dort zuletzt eine Master-Position oder ein Hedge,
# wird das Terminal (ohne Login-Zwang, MT5 nimmt das Konto des Ordners) einmal gestartet. NUR kurz nach dem Hochfahren
# (Windows-Laufzeit < BOOT_FENSTER_S) — ein Panel-Neustart durch ein Update oeffnet nichts. Ohne Trade schliesst der
# Leerlauf-Waechter es wie gewohnt wieder.
BOOT_FENSTER_S = 15 * 60


def boot_terminal_noetig(st):
    """REIN RECHNEND (testbar): hatte die Instanz beim letzten Status eine Master-Position oder einen Hedge?"""
    if not isinstance(st, dict):
        return False
    hd = st.get("hedges")
    if isinstance(hd, dict) and any(hd.values()):
        return True
    return bool(st.get("master_positions"))


def _windows_laufzeit_s(k32=None):
    """Windows-Betriebszeit in Sekunden oder None (kein Windows / Fehler). k32 = kernel32 (Test-Haken, sonst ctypes.windll.kernel32).
    ÜBERLAUF (PU1, 05.11.2026): GetTickCount64 lief ohne restype — ctypes nimmt dann c_int (32 Bit mit Vorzeichen), ab 2^31 ms (≈ 24,8 Tage
    Betriebszeit) kam eine negative bzw. falsche Zahl, und _boot_terminals hielt einen Panel-Neustart für „frisch gebootet" (öffnete alle
    Master-Terminals). Jetzt restype c_ulonglong; Rückfall nur ohne GetTickCount64 (Windows vor Vista): GetTickCount mit c_uint32 (läuft nach
    ≈ 49,7 Tagen über — dann ist ein kleiner Wert möglich, aber nie negativ)."""
    try:
        import ctypes
        if k32 is None:
            k32 = ctypes.windll.kernel32
        f = getattr(k32, "GetTickCount64", None)
        if f is not None:
            f.restype = ctypes.c_ulonglong
            f.argtypes = []
            return int(f()) / 1000.0
        f = k32.GetTickCount
        f.restype = ctypes.c_uint32
        f.argtypes = []
        return int(f()) / 1000.0
    except Exception:
        return None


def _boot_terminals():
    try:
        lz = _windows_laufzeit_s()
        if lz is None or lz > BOOT_FENSTER_S:
            return
        time.sleep(20 + random.uniform(0, 10))   # Copier/Hedge-Terminal zuerst hochkommen lassen
        for i in instances():
            fname = i["config_file"]
            cfg = read_json(os.path.join(HERE, fname), {}) or {}
            pfad = str(cfg.get("master_terminal_path") or "").strip()
            if not pfad:
                continue
            if provision.terminal_pids(os.path.dirname(os.path.abspath(pfad))):
                continue
            if not boot_terminal_noetig(read_json(os.path.join(HERE, i["status_file"]), {}) or {}):
                continue
            ok, msg = start_terminal(fname)
            print(f"[panel] {fname}: Master-Terminal nach PC-Start geoeffnet (lief ein Trade) -> {msg}", flush=True)
            time.sleep(5 + random.uniform(0, 3))
    except Exception as e:
        print(f"[panel] Boot-Terminals: {type(e).__name__}: {e}", flush=True)


def _leerlauf_waechter():
    while True:
        try:
            time.sleep(60)
            plans_akt = {}
            with PLANS_LOCK:
                for p in _load_plans():
                    if p["status"] in ("geplant", "laufend"):
                        plans_akt[p["file"]] = p["status"]
            for i in instances():
                fname = i["config_file"]
                cfg = read_json(os.path.join(HERE, fname), {}) or {}
                if not str(cfg.get("master_terminal_path") or "").strip():
                    continue  # Orbit/TV-Instanzen: kein Master-Terminal
                install_dir = os.path.dirname(os.path.abspath(str(cfg["master_terminal_path"])))
                if not provision.terminal_pids(install_dir):
                    _LEERLAUF_SEIT.pop(fname, None)
                    continue
                st = read_json(os.path.join(HERE, i["status_file"]), {}) or {}
                age = None
                try:
                    age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
                except (ValueError, TypeError):
                    pass
                frisch = bool(st.get("running")) and age is not None and age <= 15
                ok, grund = terminal_schliessbar(cfg, st, age, plans_akt.get(fname),
                                                 None if frisch else lese_status(cfg))
                schwelle = _LEERLAUF_SCHWELLE.setdefault(fname, LEERLAUF_MIN * 60 + random.uniform(0, 240))
                seit, zu = leerlauf_entscheidung(ok, _LEERLAUF_SEIT.get(fname), time.time(), schwelle)
                if seit is None:
                    _LEERLAUF_SEIT.pop(fname, None)
                else:
                    _LEERLAUF_SEIT[fname] = seit
                if not zu:
                    continue
                if fname in _TERMINAL_ZU_AKTIV:
                    continue  # der Trade-Ende-Worker ist schon dran
                anzeige = cfg.get("display_name") or i["name"]
                zu_ok, _n, grund_r = _terminal_kill_riegel(fname, install_dir)   # PL1: nie während eines Bot-Laufs, sonst nächster Takt (Zähler bleibt)
                if not zu_ok:
                    print(f"[panel] {fname}: Leerlauf-Waechter wartet — {grund_r}.", flush=True)
                    continue
                print(f"[panel] {fname}: Master-Terminal geschlossen (Leerlauf-Waechter: {anzeige}, "
                      f"seit {round((time.time() - seit) / 60)} min kein Trade — {grund}).", flush=True)
                _LEERLAUF_SEIT.pop(fname, None)
                _LEERLAUF_SCHWELLE.pop(fname, None)
        except Exception as e:
            print(f"[panel] Leerlauf-Waechter: {type(e).__name__}: {e}", flush=True)


# MT5-Update ohne UAC-Abfrage (01.10.2026, Finn: "Client Terminal AVX2 …
# /updateadmin" kam wieder) — Begruendung und Schutz in provision.py beim
# Block "MT5-Update still". Der Waechter richtet die geplante Aufgabe einmal
# ein (die letzte Ja-Abfrage, "Windows PowerShell") und spielt danach neue
# Builds NUR im Leerlauf ein: kein Plan geplant/laufend, Terminal zu. Nein
# geklickt -> erst nach 24 h wieder fragen, bis dahin bleibt alles wie bisher.
# getattr-Riegel: provision.py kommt ueber die Copier-Schleife, ein frisches
# Panel auf altem provision-Stand darf nicht sterben.
UPDATE_ABGELEHNT = os.path.join(HERE, ".mt5-update-abgelehnt")


def _update_abwarten(install_dir):
    getattr(provision, "update_abwarten", lambda d: None)(install_dir)


# UPDATE VOR JEDEM KALTSTART (08.10.2026, Finn bei Chris' Echo-Test: wieder UAC „Client Terminal AVX2" mit
# liveupdate\terminal64.exe /updateadmin /path:C:\MT5-100kpips21002811 — „ich will die jetzt so fixen, dass die nie wieder
# kommt"). Die stille Aufgabe (.930) erfasst jeden Instanz-Ordner dynamisch, aber _mt5_update_waechter spielt nur alle
# 10–15 min ein (der erste Lauf 90–150 s nach dem Panel-Start) und nur bei geschlossenem Terminal. MetaQuotes legt den neuen
# Build ab, WÄHREND das Terminal läuft; startet Echo (oder ein Klick) das Terminal wieder, bevor der Wächter dran war — nach
# einem PC-Neustart fast immer —, ruft MT5 selbst /updateadmin auf = UAC. Jetzt prüft jeder Kaltstart zuerst: liegt für GENAU
# diese Installation ein neuerer Build im liveupdate-Ordner und ist die Aufgabe da, wird er still eingespielt und erst danach
# gestartet. Windows-Einstellungen bleiben unberührt (UAC an).
UPDATE_LAEUFT = set()   # install_dir, solange vor dem Start still eingespielt wird (unter HEAL_LOCK)


def _update_vor_start_noetig(install_dir):
    """[(inst, alt, neu)] für DIESE Installation, wenn ein neuerer Build wartet UND die stille Aufgabe steht — sonst None."""
    try:
        if not getattr(provision, "update_aufgabe_ok", lambda: False)():
            return None
        n = os.path.normcase(os.path.abspath(install_dir))
        aus = [x for x in provision.update_ausstehend() if os.path.normcase(os.path.abspath(x[0])) == n]
        return aus or None
    except Exception as e:
        print(f"[mt5-update] Prüfung vor dem Start: {type(e).__name__}: {e}", flush=True)
        return None


# WINDOWS-ABFRAGE GAR NICHT ERST ENTSTEHEN LASSEN (Master 23.10.2026, Finn: „die zwei Fehler, die bei dir liegen — echt versuchen zu
# eliminieren"; Mike pc-l5o8bv: Windows fragte, ob die Datei geöffnet werden soll — .1722 fand weder Admin-Häkchen noch liveupdate-Build).
# Dritter Auslöser neben Häkchen und Update: die Download-Kennung (Alternate Data Stream „Zone.Identifier", den Browser an heruntergeladene
# Dateien hängen) an terminal64.exe & Co. Sie zu löschen braucht keine Adminrechte. Vor jedem Kaltstart (start_terminal, Heil-Neustart)
# für GENAU diese Installation und beim Panel-Start für ALLE: Kennung weg, HKCU-Häkchen weg (provision.uac_haken_entfernen). Was ohne
# Admin nicht geht, meldet der Status (mt5_update.windows): Installationen unter „Programme" (dort greift die stille Update-Aufgabe nicht,
# sie kennt nur X:\MT5-…) und HKLM-Häkchen. _MT5_UPDATE_PS bleibt unberührt (jede Änderung = neue Ja-Abfrage auf jedem PC).
ZONE_ENDUNGEN = (".exe", ".dll")
WIN_ABFRAGE = {}   # Stand für den Status: at, zone_entfernt, programme, hklm_haken


def zone_kandidat(name):
    """REIN: trägt diese Datei eine Download-Kennung, die beim Start eine Windows-Frage auslösen kann? Nur Programme/Bibliotheken."""
    return str(name or "").lower().endswith(ZONE_ENDUNGEN)


def unter_programme(install_dir, programme_dirs):
    """REIN: liegt die Installation unter „Programme" (ProgramFiles/ProgramFiles(x86))? Vergleich ohne Groß/klein, nur ganze Ordner."""
    d = os.path.normcase(os.path.normpath(str(install_dir or ""))).replace("/", "\\").rstrip("\\") + "\\"
    for p in programme_dirs or ():
        if p and d.startswith(os.path.normcase(os.path.normpath(str(p))).replace("/", "\\").rstrip("\\") + "\\"):
            return True
    return False


def zone_kennung_entfernen(install_dir):
    """Download-Kennung an *.exe/*.dll im Installationsordner (mit Unterordnern) löschen → Anzahl. Ohne Windows 0; wirft nie.
    Nur der Datenstrom „:Zone.Identifier" wird gelöscht, die Datei selbst bleibt unberührt."""
    if os.name != "nt" or not install_dir or not os.path.isdir(install_dir):
        return 0
    n = 0
    try:
        for wurzel, _ordner, dateien in os.walk(install_dir):
            for f in dateien:
                if not zone_kandidat(f):
                    continue
                try:
                    os.remove(os.path.join(wurzel, f) + ":Zone.Identifier")
                    n += 1
                except OSError:
                    pass   # keine Kennung (der Normalfall) oder gesperrt — nie den Start aufhalten
    except Exception:
        pass
    return n


def _hklm_admin_haken():
    """Nur lesen: terminal64.exe-Einträge mit „Als Administrator ausführen" in HKLM (ohne Adminrechte nicht löschbar)."""
    if os.name != "nt":
        return []
    out = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers") as k:
            i = 0
            while True:
                try:
                    name, wert, typ = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                if typ == winreg.REG_SZ and str(name).lower().endswith("terminal64.exe") \
                        and {t.upper() for t in str(wert).split()} & {"RUNASADMIN", "ELEVATECREATEPROCESS"}:
                    out.append(str(name))
    except Exception:
        pass
    return out


def _vor_kaltstart(fname, install_dir):
    """Vor jedem Kaltstart: Download-Kennung dieser Installation + HKCU-Häkchen weg. Darf einen Start nie verhindern."""
    try:
        n = zone_kennung_entfernen(install_dir)
        if n:
            print(f"[windows] {fname}: Download-Kennung an {n} Datei(en) entfernt — Windows fragt beim Start nicht mehr „Datei öffnen?“",
                  flush=True)
        getattr(provision, "uac_haken_entfernen", lambda: None)()
    except Exception as e:
        print(f"[windows] {fname}: Vorbeugen übersprungen ({type(e).__name__}: {e})", flush=True)
    # MU1 (10.11.2026): älteren MT5-Build dieser Installation still auf den neuesten Build des PCs heben, bevor MT5 selbst per UAC
    # einspielen will — eigener try, wirft nie, verhindert nie einen Start
    try:
        st, txt = build_angleichen(install_dir, schnell=True)
        if st in ("angeglichen", "fehler"):
            print(f"[mt5-build] {fname}: {txt}", flush=True)
    except Exception as e:
        print(f"[mt5-build] {fname}: übersprungen ({type(e).__name__}: {e})", flush=True)


# ── MT5-BUILD ANGLEICHEN OHNE ADMINRECHTE (MU1, 10.11.2026 — Master: Handy-Meldung „Windows-Abfrage offen … bitte per Parsec mit Ja
# bestätigen“ 42× in 7 Tagen, Finn musste jedes Mal per Parsec „Ja“ klicken; „an der Ursache beheben“). Befund per Lotse (nur lesend):
#  1. MetaQuotes legt einen neuen Build NICHT als neuere liveupdate\terminal64.exe ab, sondern als Pakete <Datenordner>\liveupdate\
#     mt5clw64.<build> (+ mt5clwide64/mt5clwtst64/mt5onnx64). liveupdate\terminal64.exe ist die ALTE Exe als Updater; MT5 startet sie beim
#     nächsten Kaltstart mit /update /path:X:\MT5-… und sie fordert Adminrechte an = Windows-Abfrage (Chris pc-c19p2l, MT5-100k117783Phase1:
#     Installation 6191, Updater 6191, Pakete .6230). update_ausstehend()/das Aufgaben-Skript vergleichen genau diese Exe mit der Installation
#     → immer „nichts zu tun“ (zudem liefert map_installs normcase-Pfade „c:\mt5-…“, die ist_mt5_ordner nie trifft): auf KEINEM der 12 PCs
#     gibt es ein mt5-update.log, die stille Aufgabe hat nie etwas eingespielt.
#  2. Die Vorlage C:\MT5-Master bleibt auf dem alten Build (läuft nie mit Netz) — jeder neue Klon startet alt, lädt den neuen Build und fragt.
#     Genau die 5 PCs mit gemischten Builds und alter Vorlage alarmierten (2zc2we 23, c19p2l 26, usq1i6 8, l5o8bv 10, pw1put 7), die 6 PCs
#     mit einheitlichem Build nie.
#  3. Zwischen zwei Builds unterscheiden sich nur terminal64.exe, MetaEditor64.exe und metatester64.exe (6140→6230 und 6191→6230 belegt,
#     alle übrigen 41 Dateien byte-gleich), alle MetaQuotes-signiert; X:\MT5-… ist für „Authentifizierte Benutzer“ beschreibbar.
# Fix: Liegt auf DIESEM PC eine X:\MT5-…-Installation mit neuerem Build, kopiert Echo deren drei Programmdateien (Signatur MetaQuotes geprüft)
# in jede ältere, NICHT laufende X:\MT5-…-Installation — vor jedem Kaltstart (_vor_kaltstart: start_terminal + Heil-Neustart, Hedge-Start)
# und im Hintergrund alle 2–3 min (auch die Vorlage → neue Klone starten aktuell). Danach im Datenordner die veralteten liveupdate-Pakete
# (Build ≤ installiert) und den alten Updater löschen, damit MT5 beim Start nichts mehr einspielen will. Ohne Adminrechte, keine
# Windows-Einstellung, UAC bleibt an; _MT5_UPDATE_PS und provision.py unverändert (keine neue Ja-Abfrage, kein Copier-Neustart).
# Bleibt: ein WIRKLICH neuer MetaQuotes-Build fragt höchstens einmal je PC (die erste Instanz) — danach gleichen sich alle anderen still an.
BUILD_DATEIEN = ("metatester64.exe", "MetaEditor64.exe", "terminal64.exe")   # terminal64.exe zuletzt: bricht vorher etwas ab, bleibt sie alt
BUILD_LOCK = threading.Lock()
BUILD_ANGLEICH = {}            # Stand für mt5_live.status.mt5_update.build_angleich
BUILD_TAKT_S = (120.0, 180.0)
_BUILD_SIG_OK = {}             # (pfad, größe, mtime) → True: Signatur je Datei-Stand nur einmal prüfen (PowerShell ~1–2 s)
_MT5_ORDNER_I = re.compile(r'^[A-Za-z]:\\MT5-[^\\/:*?"<>|]+$', re.I)   # wie provision._MT5_ORDNER_RE, aber auch für normcase-Pfade
_PAKET_RE = re.compile(r"^[a-z0-9_]+\.(\d{3,6})$", re.I)                # liveupdate\mt5clw64.6230 usw.


def build_angleich_plan(stand, art=None):
    """REIN (testbar): stand = {Installation: Versions-Tupel|None}, art = {Installation: Kennung der übrigen Programmdateien} →
    {ältere Installation: Quelle}. Nur X:\\MT5-…-Ordner; Quelle = höchster Build DERSELBEN Art und Hauptversion (pc-2zc2we: zwei
    MT5-Grid-Installationen 6231 mit anderer uninstall.exe = andere Ausgabe → nie Quelle für die übrigen). art fehlt/None → nie dabei,
    außer art wird gar nicht übergeben (dann eine Art für alle). Gleichstand → nichts."""
    g = {i: tuple(v) for i, v in (stand or {}).items() if v and len(tuple(v)) == 4 and _MT5_ORDNER_I.match(str(i or ""))}
    if art is not None:
        g = {i: v for i, v in g.items() if art.get(i) is not None}
    a = (lambda i: art.get(i)) if art is not None else (lambda i: 0)
    out = {}
    for i, v in g.items():
        q = max((j for j in g if a(j) == a(i) and g[j][0] == v[0]), key=lambda j: (g[j], str(j)))
        if g[q] > v:
            out[i] = q
    return out


def paket_veraltet(name, build):
    """REIN (testbar): ist diese liveupdate-Datei ein Build-Paket (mt5clw64.6230) mit Build ≤ build? Alles andere → False."""
    m = _PAKET_RE.match(str(name or ""))
    return bool(m and build and int(m.group(1)) <= int(build))


def liveupdate_aufraeumen(data_dir, version, ver=None):
    """Veraltete Pakete (Build ≤ installiert) und den alten Updater (liveupdate\\terminal64.exe, Version ≤ installiert) im Datenordner
    löschen → [gelöschte Namen]. Nur bei NICHT laufendem Terminal aufrufen. Neuere Pakete bleiben (echter neuer Build). Wirft nie."""
    ver = ver or getattr(provision, "_datei_version", lambda p: None)
    lu = os.path.join(data_dir or "", "liveupdate")
    weg = []
    if not data_dir or not version or not os.path.isdir(lu):
        return weg
    try:
        namen = os.listdir(lu)
        # Gegenprüfung MU1: wartet ein NEUERES Paket (echter neuer Build), braucht MT5 den Updater — dann bleibt er liegen
        neuer_wartet = any((m := _PAKET_RE.match(f)) and int(m.group(1)) > version[3] for f in namen)
        for f in namen:
            p = os.path.join(lu, f)
            if not os.path.isfile(p):
                continue
            try:   # je Datei: eine unlesbare Datei hält das Aufräumen der übrigen nicht auf
                if f.lower() == "terminal64.exe":
                    v = ver(p)
                    alt = bool(v and tuple(v) <= tuple(version)) and not neuer_wartet
                else:
                    alt = paket_veraltet(f, version[3])
                if alt:
                    os.remove(p)
                    weg.append(f)
            except Exception:
                pass
    except Exception:
        pass
    return weg


def _liveupdate_rest(data_dir, version):
    """Liegt im liveupdate-Ordner etwas, das liveupdate_aufraeumen löschen würde (Paket ≤ Build oder ein Updater)? Nur listdir. Wirft nie."""
    try:
        namen = os.listdir(os.path.join(data_dir, "liveupdate"))
        neuer = any((m := _PAKET_RE.match(f)) and int(m.group(1)) > version[3] for f in namen)
        return any((f.lower() == "terminal64.exe" and not neuer) or paket_veraltet(f, version[3]) for f in namen)
    except Exception:
        return False


def _build_installationen():
    """{normcase(Installation): (Installation, Datenordner|None, Versions-Tupel|None, Art|None)} — Datenordner per origin.txt, dazu die
    Terminal-Pfade aller Instanz-Configs (Master + Hedge) und der Vorlage. Nur X:\\MT5-…; ohne Windows {}. Wirft nie."""
    if os.name != "nt":
        return {}
    ver = getattr(provision, "_datei_version", lambda p: None)
    out = {}

    def dazu(inst, data_dir=None):
        inst = os.path.normpath(str(inst or "").strip())
        if not _MT5_ORDNER_I.match(inst):
            return
        k = os.path.normcase(inst)
        alt = out.get(k)
        if alt and (alt[1] or not data_dir):
            return
        pr = programm_rest(inst)
        out[k] = (inst, data_dir or (alt[1] if alt else None), ver(os.path.join(inst, "terminal64.exe")),
                  tuple(sorted(pr.items())) if pr is not None else None)

    try:
        root = provision.terminals_root()
        for e in (os.listdir(root) if root and os.path.isdir(root) else []):
            dd = os.path.join(root, e)
            if e.lower() != "common" and os.path.isdir(dd):
                origin = provision.read_origin(dd)
                if origin:
                    dazu(origin, dd)
    except Exception:
        pass
    try:
        cfgs = [read_json(os.path.join(HERE, i["config_file"]), {}) or {} for i in instances()]
        cfgs.append(read_json(os.path.join(HERE, "config.vorlage.json"), {}) or {})
        for c in cfgs:
            for k in ("master_terminal_path", "hedge_terminal_path"):
                p = str(c.get(k) or "").strip()
                if p:
                    dazu(os.path.dirname(os.path.abspath(p)))
    except Exception:
        pass
    return out


BUILD_PROZESSE = {n.lower() for n in BUILD_DATEIEN}


def ordner_pids(ordner):
    """PIDs von terminal64/MetaEditor64/metatester64, deren Programm in GENAU einem dieser Ordner liegt (Installation, aber auch
    <Datenordner>\\liveupdate = MetaQuotes-Updater läuft). Gegenprüfung MU1: nicht nur terminal64.exe — ein laufender MetaEditor
    (EA-Kompilieren) oder Updater darf nie unter dem Kopieren/Aufräumen liegen. Unlesbar → [-1] (gilt als „läuft“). Ohne Windows []."""
    if os.name != "nt":
        return []
    try:
        w = _pc_w32()
        ctypes, k32 = w["ctypes"], w["k32"]
        ziele = {os.path.normcase(os.path.normpath(o)) for o in ordner if o}
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        if snap == ctypes.c_void_p(-1).value or not snap:
            return [-1]
        out = []
        try:
            pe = w["PE32"]()
            pe.dwSize = ctypes.sizeof(pe)
            ok = k32.Process32FirstW(snap, ctypes.byref(pe))
            while ok:
                if str(pe.szExeFile).lower() in BUILD_PROZESSE:
                    pfad = provision.prozess_pfad(int(pe.th32ProcessID))
                    if not pfad:
                        out.append(-1)   # Pfad unlesbar → vorsichtshalber „läuft“
                    elif os.path.normcase(os.path.dirname(os.path.normpath(pfad))) in ziele:
                        out.append(int(pe.th32ProcessID))
                ok = k32.Process32NextW(snap, ctypes.byref(pe))
        finally:
            k32.CloseHandle(snap)
        return out
    except Exception:
        return [-1]


def _signatur_metaquotes(pfade, nur_gemerkt=False):
    """Alle Dateien gültig von MetaQuotes signiert? Ein PowerShell-Aufruf (Get-AuthenticodeSignature, wie das Aufgaben-Skript), Ergebnis
    je Datei-Stand gemerkt. Fehler/kein Windows → False (dann wird nichts kopiert). nur_gemerkt: kein PowerShell (Startweg, ≤ 20 s)."""
    if os.name != "nt":
        return False
    try:
        offen = []
        for p in pfade:
            s = os.stat(p)
            if not _BUILD_SIG_OK.get((os.path.normcase(p), s.st_size, int(s.st_mtime))):
                offen.append((p, (os.path.normcase(p), s.st_size, int(s.st_mtime))))
        if not offen:
            return True
        if nur_gemerkt:
            return False
        liste = ",".join("'" + p.replace("'", "''") + "'" for p, _ in offen)
        ps = ("$ok=$true; foreach($p in @(" + liste + ")){ $s=Get-AuthenticodeSignature -LiteralPath $p; "
              "if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'O=MetaQuotes'){ $ok=$false } }; if($ok){exit 0}else{exit 3}")
        import base64
        enc = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
        # Bytes statt Text: PowerShell schreibt Fortschritt mit Umlauten in OEM-Codepage nach stderr — text=True warf im Lesethread
        # UnicodeDecodeError (Trockenlauf pc-c19p2l 10.11.2026). Gebraucht wird nur der Exit-Code.
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                           capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return False
        for _p, k in offen:
            _BUILD_SIG_OK[k] = True
        return True
    except Exception:
        return False


def programm_rest(ordner):
    """{name: größe} der übrigen .exe/.dll direkt im Installationsordner (ohne die drei Build-Programme). Unlesbar → None."""
    try:
        return {f.lower(): os.path.getsize(os.path.join(ordner, f)) for f in os.listdir(ordner)
                if f.lower().endswith((".exe", ".dll")) and f.lower() not in BUILD_PROZESSE and os.path.isfile(os.path.join(ordner, f))}
    except OSError:
        return None


def temp_reste_weg(ordner):
    """Liegengebliebene *.prophos-neu (Panel starb mitten im Kopieren) löschen → Anzahl. Nur bei nicht laufender Installation."""
    n = 0
    try:
        for f in os.listdir(ordner):
            if f.endswith(".prophos-neu"):
                try:
                    os.remove(os.path.join(ordner, f))
                    n += 1
                except OSError:
                    pass
    except OSError:
        pass
    return n


def build_kopieren(quelle, ziel, q_ver, *, ver, pids, sig_ok):
    """Die drei Programmdateien von quelle nach ziel (beide X:\\MT5-…, ziel läuft nicht) → (status, text). Erst alle in Temp-Dateien
    neben dem Ziel kopieren und Größe prüfen, dann je Datei atomar ersetzen (terminal64.exe zuletzt). Funktionen injiziert (testbar)."""
    src = [os.path.join(quelle, n) for n in BUILD_DATEIEN]
    for p in src:
        if tuple(ver(p) or ()) != tuple(q_ver):
            return "fehler", f"Quelle {quelle}: {os.path.basename(p)} hat nicht Build {'.'.join(map(str, q_ver))} — nichts kopiert"
    if not os.path.isfile(os.path.join(ziel, "terminal64.exe")):
        return "fehler", f"{ziel}: terminal64.exe fehlt — nichts kopiert"
    if programm_rest(quelle) != programm_rest(ziel):
        # Gegenprüfung MU1: ändert ein künftiger Build mehr als die drei Programme (neue/andere .exe/.dll), lieber gar nicht als halb
        return "fehler", f"{ziel}: weitere Programmdateien weichen von {quelle} ab — nichts kopiert (MT5 spielt selbst ein)"
    if pids(ziel):
        return "laeuft", f"{ziel} läuft — beim nächsten Leerlauf/Kaltstart"
    if not sig_ok(src):
        return "fehler", f"Quelle {quelle}: Signatur nicht MetaQuotes/ungültig — nichts kopiert"
    import shutil
    tmp = []
    try:
        for p in src:
            t = os.path.join(ziel, os.path.basename(p) + ".prophos-neu")
            shutil.copy2(p, t)
            tmp.append(t)
            if os.path.getsize(t) != os.path.getsize(p):
                return "fehler", f"{os.path.basename(t)}: Größe weicht ab — nichts ersetzt"
        if pids(ziel):   # während des Kopierens gestartet (z. B. Provisionierung) → nichts ersetzen
            return "laeuft", f"{ziel} wurde gestartet — nichts ersetzt"
        for t in tmp:
            os.replace(t, t[:-len(".prophos-neu")])
        tmp = []
    except OSError as e:
        return "fehler", f"{ziel}: Kopieren gescheitert ({type(e).__name__}: {e})"[:200]
    finally:
        for t in tmp:
            try:
                os.remove(t)
            except OSError:
                pass
    neu = tuple(ver(os.path.join(ziel, "terminal64.exe")) or ())
    if neu != tuple(q_ver):
        return "fehler", f"{ziel}: nach dem Kopieren Build {neu or '?'} statt {'.'.join(map(str, q_ver))}"
    return "angeglichen", f"{ziel} auf Build {q_ver[3]} gehoben (aus {quelle}, ohne Windows-Abfrage)"


def _build_merken(status, text, ziel, version=None):
    BUILD_ANGLEICH["at"] = datetime.now().isoformat(timespec="seconds")
    if status == "angeglichen":
        BUILD_ANGLEICH["angeglichen"] = BUILD_ANGLEICH.get("angeglichen", 0) + 1
        BUILD_ANGLEICH["letzte"] = ([f"{os.path.basename(ziel)}→{version[3]}"] + list(BUILD_ANGLEICH.get("letzte") or []))[:10]
    elif status == "fehler":
        BUILD_ANGLEICH["fehler"] = text[:200]


def _stilles_update_dran(install_dir):
    """Läuft für diese Installation gerade das alte stille Update (UPDATE_LAEUFT, normcase-Vergleich) oder liegt sein frischer Merker
    prophos-update.lock (< 10 min, wie update_abwarten)? Dann nichts anfassen (Gegenprüfung MU1)."""
    k = os.path.normcase(os.path.normpath(os.path.abspath(install_dir)))
    if any(os.path.normcase(os.path.normpath(os.path.abspath(u))) == k for u in list(UPDATE_LAEUFT)):
        return True
    try:
        return time.time() - os.path.getmtime(os.path.join(install_dir, getattr(provision, "UPDATE_LOCK", "prophos-update.lock"))) < 600
    except OSError:
        return False


def build_angleichen(install_dir, schnell=False):
    """Diese Installation still auf den neuesten Build des PCs heben (s. Block oben) → (status, text). status: aus | aktuell | laeuft |
    belegt | angeglichen | fehler. Auch wenn aktuell: veraltete liveupdate-Pakete weg. Darf einen Start nie verhindern, wirft nie.
    schnell (synchrone Startwege, PC-Tab bricht nach 20 s ab — Gegenprüfung MU1): Sperre nicht abwarten, Signatur nur aus dem Merker
    (fehlt sie → „belegt“, der Wächter erledigt es); kopiert wird dann nur, was in wenigen Sekunden geht."""
    if os.name != "nt" or not install_dir:
        return "aus", ""
    try:
        ziel_k = os.path.normcase(os.path.normpath(os.path.abspath(install_dir)))
        if not _MT5_ORDNER_I.match(ziel_k) or _stilles_update_dran(install_dir):
            return "aus", ""
        if not BUILD_LOCK.acquire(blocking=not schnell):
            return "belegt", ""
        try:
            inst = _build_installationen()
            plan = build_angleich_plan({k: v[2] for k, v in inst.items()}, {k: v[3] for k, v in inst.items()})
            eintrag = inst.get(ziel_k)
            if not eintrag:
                return "aus", ""
            lu = os.path.join(eintrag[1], "liveupdate") if eintrag[1] else ""
            belegt = lambda d: ordner_pids([d, lu])   # Installation (alle drei Programme) + MetaQuotes-Updater
            st, txt = "aktuell", ""
            if ziel_k in plan:
                quelle = plan[ziel_k]
                q_ver = inst[quelle][2]
                st, txt = build_kopieren(inst[quelle][0], eintrag[0], q_ver, ver=provision._datei_version, pids=belegt,
                                         sig_ok=lambda ps: _signatur_metaquotes(ps, nur_gemerkt=schnell))
                if schnell and st == "fehler" and "Signatur" in txt:
                    st, txt = "belegt", ""   # Signatur noch nicht gemerkt → Wächter prüft (PowerShell ~1–2 s, im Startweg zu riskant)
                else:
                    _build_merken(st, txt, eintrag[0], q_ver)
            if st == "aktuell" and not belegt(eintrag[0]):
                temp_reste_weg(eintrag[0])   # sonst erbt ein Klon der Vorlage die Reste
            if st in ("aktuell", "angeglichen") and eintrag[1] and not belegt(eintrag[0]):
                v = provision._datei_version(os.path.join(eintrag[0], "terminal64.exe"))
                weg = liveupdate_aufraeumen(eintrag[1], v)
                if weg:
                    txt = (txt + "; " if txt else "") + f"liveupdate: {', '.join(weg)} gelöscht"
                    if st == "aktuell":
                        print(f"[mt5-build] {eintrag[0]}: veraltete liveupdate-Dateien gelöscht ({', '.join(weg)})", flush=True)
            return st, txt
        finally:
            BUILD_LOCK.release()
    except Exception as e:
        return "fehler", f"{type(e).__name__}: {e}"[:200]


def _build_angleich_waechter():
    """Thread: alle 2–3 min jede ältere, nicht laufende X:\\MT5-…-Installation (auch die Vorlage) angleichen und veraltete
    liveupdate-Pakete löschen. Pausiert, solange ein Puls/Order-/Polar-Lauf auf diesem PC läuft (kein Plattendruck mitten im Klick)."""
    if os.name != "nt":
        return
    time.sleep(60 + random.uniform(0, 60))
    while True:
        try:
            # Provisionierung läuft → Vorlage/Klon nicht anfassen (copytree könnte eine halbe .prophos-neu mitnehmen)
            if not _bot_lauf_aktiv() and not (PROV_JOB and not PROV_JOB.get("done")):
                with BUILD_LOCK:
                    inst = _build_installationen()
                ziele = build_angleich_plan({k: v[2] for k, v in inst.items()}, {k: v[3] for k, v in inst.items()})
                offen = []
                for k, (pfad, dd, v, _art) in inst.items():
                    if k in ziele or (v and _liveupdate_rest(dd, v)):
                        # Gegenprüfung MU1: je Ziel neu — ein Lauf/eine Provisionierung kann mitten in der Runde beginnen
                        if _bot_lauf_aktiv() or (PROV_JOB and not PROV_JOB.get("done")):
                            break
                        st, txt = build_angleichen(pfad)
                        if st in ("angeglichen", "fehler"):
                            print(f"[mt5-build] {txt}", flush=True)
                        if st in ("laeuft", "fehler"):
                            offen.append(os.path.basename(pfad))
                builds = sorted({v[2][3] for v in inst.values() if v[2]})
                BUILD_ANGLEICH.update(at=datetime.now().isoformat(timespec="seconds"), installationen=len(inst), builds=builds[-4:],
                                      offen=offen[:20])
        except Exception as e:
            print(f"[mt5-build] {type(e).__name__}: {e}", flush=True)
        time.sleep(random.uniform(*BUILD_TAKT_S))


def _windows_abfrage_vorbeugen():
    """Einmal beim Panel-Start für ALLE MT5-Installationen (Datenordner-Zuordnung + Instanz-Configs): Kennung weg, Stand für den Status."""
    if os.name != "nt":
        return
    try:
        dirs = {}
        try:
            for inst in provision.map_installs(provision.terminals_root()):
                dirs[os.path.normcase(os.path.normpath(inst))] = inst
        except Exception:
            pass
        for i in instances():
            pfad = str((read_json(os.path.join(HERE, i["config_file"]), {}) or {}).get("master_terminal_path") or "").strip()
            if pfad:
                d = os.path.dirname(os.path.abspath(pfad))
                dirs.setdefault(os.path.normcase(os.path.normpath(d)), d)
        n = sum(zone_kennung_entfernen(d) for d in dirs.values())
        programme = [os.environ.get("ProgramFiles") or "", os.environ.get("ProgramFiles(x86)") or ""]
        WIN_ABFRAGE.update(at=datetime.now().isoformat(timespec="seconds"), installationen=len(dirs), zone_entfernt=n,
                           programme=sorted(d for d in dirs.values() if unter_programme(d, programme))[:20],
                           hklm_haken=_hklm_admin_haken()[:20])
        print(f"[windows] {len(dirs)} MT5-Installation(en): Download-Kennung an {n} Datei(en) entfernt"
              + (f"; unter Programme (ohne stille Updates): {', '.join(WIN_ABFRAGE['programme'])}" if WIN_ABFRAGE["programme"] else "")
              + (f"; HKLM-Häkchen (braucht Admin): {', '.join(WIN_ABFRAGE['hklm_haken'])}" if WIN_ABFRAGE["hklm_haken"] else ""), flush=True)
    except Exception as e:
        WIN_ABFRAGE.update(fehler=f"{type(e).__name__}: {e}"[:120])


def _update_einspielen(fname, aus):
    try:
        for zeile in provision.mt5_updates_einspielen(aus, max_s=300):
            print(f"[mt5-update] {fname}: {zeile}", flush=True)
    except Exception as e:
        print(f"[mt5-update] {fname}: {type(e).__name__}: {e}", flush=True)


def _update_dann_start(fname, install_dir, aus, creds):
    """Hintergrund: still einspielen (die Instanz gilt so lange als „heilt" — master-order antwortet retry_ok/terminal_heilt,
    der Echo-V2-Check wartet bis 180 s), danach normal kalt starten — ohne erneute Update-Prüfung (kein Kreislauf)."""
    try:
        _update_einspielen(fname, aus)
    finally:
        with HEAL_LOCK:
            UPDATE_LAEUFT.discard(install_dir)
            HEAL_ACTIVE.discard(install_dir)
    ok, msg = start_terminal(fname, creds, ohne_update=True)
    print(f"[mt5-update] {fname}: Terminal nach dem Update {'gestartet' if ok else 'NICHT gestartet'} — {msg}", flush=True)


_MT5_UPD_STAND = {"t": 0.0, "wert": None}


def _mt5_update_stand():
    """Für Prophos (mt5_live): steht die stille Aufgabe, wie viele Builds warten? Höchstens alle 5 min neu ermittelt."""
    if os.name != "nt":
        return None
    if time.time() - _MT5_UPD_STAND["t"] < 300 and _MT5_UPD_STAND["wert"] is not None:
        return dict(_MT5_UPD_STAND["wert"], paket={k: v for k, v in MT5_PAKET.items() if not k.startswith("_")},
                    windows=dict(WIN_ABFRAGE) or None)
    try:
        aus = provision.update_ausstehend()
        w = {"aufgabe_ok": bool(provision.update_aufgabe_ok()), "ausstehend": len(aus),
             "ordner": [os.path.basename(x[0]) for x in aus][:20], "abgelehnt": os.path.exists(UPDATE_ABGELEHNT),
             "laeuft": len(UPDATE_LAEUFT), "build_angleich": dict(BUILD_ANGLEICH) or None}   # MU1 (10.11.2026)
    except Exception as e:
        w = {"fehler": f"{type(e).__name__}: {e}"[:120]}
    _MT5_UPD_STAND.update(t=time.time(), wert=w)
    # MetaTrader5-Paket des Panel-Pythons (08.10.2026) mitliefern — kommt so ohne Backend-Änderung bis Admin → PC-Tabs
    # windows (23.10.2026): Download-Kennung/Programme/HKLM-Häkchen aus _windows_abfrage_vorbeugen, auf demselben Weg
    return dict(w, paket={k: v for k, v in MT5_PAKET.items() if not k.startswith("_")}, windows=dict(WIN_ABFRAGE) or None)


# MT5-UPDATE PER KLICK EINRICHTEN (08.10.2026, Finn: „Kannst du das vorher bei der Einrichtung einbauen?"): der Wächter fragt
# aus dem Hintergrund per runas — an Aurels und EzPokers PC zeigte Windows dafür weder Dialog noch Taskleisten-Symbol, Finn musste
# den 10.796 Zeichen langen Einrichtungsbefehl von Hand in PowerShell einfügen. Jetzt: Kasten im Panel, solange die Aufgabe fehlt;
# der Klick holt das Panel-Fenster kurz nach vorn (Windows gibt den Vordergrund sonst nicht an einen Hintergrundprozess) und startet
# dasselbe provision.setup_ps() per runas MIT diesem Fenster als Eltern → die Ja-Abfrage kommt im Vordergrund. UAC bleibt an,
# keine Windows-Einstellung wird geändert. provision.py bleibt unverändert (Neustart des Copiers vermeiden).
MT5_UPD_JOB = {"laeuft": False, "ok": None, "msg": "", "t": 0.0}


def _konsole_nach_vorn():
    """Panel-Konsolenfenster in den Vordergrund (Muster copier._vordergrund_geben: AttachThreadInput, Rückfall Alt). → hwnd | 0"""
    import ctypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = int(k32.GetConsoleWindow() or 0)
    if not hwnd:
        return 0
    try:
        u32.ShowWindow(ctypes.c_void_p(hwnd), 9)   # SW_RESTORE — auch wenn minimiert
        vorn = u32.GetForegroundWindow()
        mein = k32.GetCurrentThreadId()
        fremd = u32.GetWindowThreadProcessId(vorn, None) if vorn else 0
        angehaengt = bool(fremd and fremd != mein and u32.AttachThreadInput(fremd, mein, True))
        try:
            u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        finally:
            if angehaengt:
                u32.AttachThreadInput(fremd, mein, False)
        if int(u32.GetForegroundWindow() or 0) != hwnd:
            u32.keybd_event(0x12, 0, 0, 0); u32.keybd_event(0x12, 0, 2, 0)   # Alt gibt den Foreground-Lock frei
            u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    except Exception as e:
        print(f"[mt5-update] Fenster nach vorn: {type(e).__name__}: {e}", flush=True)
    return hwnd


def _mt5_update_klick_worker():
    try:
        import base64
        import ctypes
        hwnd = _konsole_nach_vorn()
        enc = base64.b64encode(provision.setup_ps().encode("utf-16-le")).decode("ascii")
        print("[mt5-update] Einrichtung per Klick — jetzt am PC einmal 'Ja' klicken (Windows PowerShell).", flush=True)
        rc = ctypes.windll.shell32.ShellExecuteW(
            ctypes.c_void_p(hwnd) if hwnd else None, "runas", "powershell.exe",
            f"-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand {enc}", None, 0)
        if int(rc or 0) <= 32:
            MT5_UPD_JOB.update(laeuft=False, ok=False, msg="Nicht eingerichtet — „Nein“ geklickt oder Abfrage abgebrochen.", t=time.time())
            return
        ende = time.time() + 150
        while time.time() < ende:
            if provision.update_aufgabe_ok():
                try:
                    os.remove(UPDATE_ABGELEHNT)
                except OSError:
                    pass
                MT5_UPD_JOB.update(laeuft=False, ok=True, msg="Eingerichtet — MT5-Updates laufen ab jetzt ohne Nachfrage.", t=time.time())
                print("[mt5-update] Aufgabe eingerichtet (Klick im Panel).", flush=True)
                return
            time.sleep(3)
        MT5_UPD_JOB.update(laeuft=False, ok=False, msg="Keine Bestätigung innerhalb von 2,5 min — nochmal versuchen.", t=time.time())
    except Exception as e:
        MT5_UPD_JOB.update(laeuft=False, ok=False, msg=f"Fehler: {type(e).__name__}: {e}"[:160], t=time.time())
    finally:
        _MT5_UPD_STAND["t"] = 0.0   # Kasten/Prophos-Status sofort neu ermitteln


def _bot_lauf_aktiv():
    """Läuft gerade ein Puls/Order-Lauf über dieses Panel? (Prüfer zu .1346-Entwurf: Fenster-nach-vorn + Alt-Tipp könnten einen
    TradingView- oder MT5-Klick mitten im Ticket stören) — TV-Weg-Lock, MT5-Order-Locks, K3-Handlauf-Sperre jünger als 15 min."""
    try:
        if polar_panel and polar_panel.aktiv():      # Polar hält die Maus (13.10.2026)
            return True
        if polar_panel and getattr(polar_panel, "test_aktiv", lambda: False)():   # Maus-Test × parkt die Maus 10 s (20.10.2026, S1-Prüfung)
            return True
        if TV_ORDER_LOCK.locked() or mt5_order_belegt():   # reine Deal-/Vorflug-Lesungen zählen nicht (S1, RA2 F1)
            return True
        return time.time() - os.path.getmtime(os.path.join(HERE, "puls_handlauf.lock")) < 900
    except OSError:
        return False
    except Exception:
        return False


def mt5_update_klick():
    if os.name != "nt":
        return False, "nur unter Windows"
    if _bot_lauf_aktiv():
        return False, "Gerade läuft ein Puls/Order-Lauf auf diesem PC — in ein paar Minuten nochmal klicken (das Fenster nach vorn würde den Lauf stören)."
    if MT5_UPD_JOB.get("laeuft"):
        return False, "läuft schon — bitte die Windows-Abfrage bestätigen"
    if provision.update_aufgabe_ok():
        _MT5_UPD_STAND["t"] = 0.0
        return True, "schon eingerichtet"
    MT5_UPD_JOB.update(laeuft=True, ok=None, msg="Windows fragt gleich — bitte „Ja“ klicken.", t=time.time())
    threading.Thread(target=_mt5_update_klick_worker, daemon=True).start()
    return True, "gestartet"


def _mt5_update_waechter():
    if os.name != "nt":
        return
    time.sleep(90 + random.uniform(0, 60))
    while True:
        try:
            einspielen = getattr(provision, "mt5_updates_einspielen", None)
            if einspielen and not provision.update_aufgabe_ok():
                try:
                    abgelehnt = time.time() - os.path.getmtime(UPDATE_ABGELEHNT) < 86400
                except OSError:
                    abgelehnt = False
                if not abgelehnt:
                    print("[mt5-update] Richte die stille MT5-Update-Aufgabe ein — am PC einmal "
                          "'Ja' klicken (Windows PowerShell). Danach kommt die "
                          "MT5-Update-Abfrage nicht mehr.", flush=True)
                    if provision.update_aufgabe_einrichten():
                        print("[mt5-update] Aufgabe eingerichtet.", flush=True)
                    else:
                        with open(UPDATE_ABGELEHNT, "w") as f:
                            f.write(datetime.now().isoformat())
                        print("[mt5-update] Nicht eingerichtet (Nein oder Zeitablauf) — "
                              "neuer Versuch in 24 h.", flush=True)
            if einspielen and provision.update_aufgabe_ok():
                with PLANS_LOCK:
                    aktiv = any(p["status"] in ("geplant", "laufend") for p in _load_plans())
                if not aktiv:
                    for zeile in einspielen():
                        print(f"[mt5-update] {zeile}", flush=True)
        except Exception as e:
            print(f"[mt5-update] {type(e).__name__}: {e}", flush=True)
        time.sleep(600 + random.uniform(0, 300))


# ── Provisionierung: "Account hinzufuegen" ─────────────────────────────────────
# Ein Job zur Zeit. Das Passwort liegt NUR im Speicher des Worker-Threads und in
# der transienten Startdatei, die provision.py garantiert loescht — im Job-Status
# (den der Browser pollt) taucht es nie auf.
PROV_STEPS = ("pruefen", "klonen", "login", "ea", "neustart", "config")
PROV_LOCK = threading.Lock()
PROV_JOB = None  # {"name", "steps": {key: {"state", "note"}}, "error", "done"}


def prov_start(name, login, password, server, owner=None, display=None):
    global PROV_JOB
    with PROV_LOCK:
        if PROV_JOB and not PROV_JOB.get("done"):
            return False, "Es laeuft schon eine Provisionierung — erst fertig laufen lassen."
        cfg = base_config()
        template = cfg.get("master_terminal_path") or ""
        # magic_base pro PC (27.08.2026): teilen sich mehrere PCs dasselbe
        # Hedge-Konto, vergibt jeder in seinem eigenen 1000er-Block. Fehlt der
        # Wert, gilt der Default 770000 (Bestands-PC bleibt wie bisher).
        try:
            magic_base = int(cfg.get("magic_base") or provision.MAGIC_BASE)
        except (TypeError, ValueError):
            magic_base = provision.MAGIC_BASE
        job = {"name": name, "error": None, "done": False,
               "steps": {k: {"state": "pending", "note": None} for k in PROV_STEPS}}
        PROV_JOB = job

    def report(step, state, note=None):
        st = job["steps"].get(step)
        if st:
            st["state"] = state
            if note:
                st["note"] = note

    def worker():
        try:
            # Vorlage-EA sicherstellen (28.08.2026, frischer-PC-Provisionierung):
            # auf einem neu aufgesetzten PC ist das Lese-EA in der Master-Vorlage
            # noch nie kompiliert — run_provision braeche sonst am ex5-Check ab
            # ('Kompiliertes EA fehlt'). _ensure_ea_compiled spiegelt die .mq5 in
            # den Vorlage-Datenordner und kompiliert sie per metaeditor64.exe;
            # damit entfaellt der MetaEditor-Handgriff auch fuer die Vorlage.
            # Schlaegt es fehl (kein MetaEditor), meldet run_provision weiterhin
            # klar 'von Hand kompilieren' — reiner Best-Effort-Vorlauf.
            if template:
                try:
                    _ensure_ea_compiled("vorlage", os.path.dirname(os.path.abspath(template)))
                except Exception as e:
                    print(f"[prov] Vorlage-EA-Vorlauf uebersprungen ({type(e).__name__}: {e})", flush=True)
            if template:   # MU1 (10.11.2026): Vorlage auf den neuesten Build des PCs heben → der Klon startet ohne MT5-Update/UAC
                try:
                    _st, _txt = build_angleichen(os.path.dirname(os.path.abspath(template)))
                    if _st in ("angeglichen", "fehler"):
                        print(f"[mt5-build] Vorlage: {_txt}", flush=True)
                except Exception:
                    pass
            provision.run_provision(name=name, login=login, password=password,
                                    server=server, template_exe=template,
                                    folder=HERE, report=report, owner=owner, display=display,
                                    magic_base=magic_base)
        except provision.ProvisionError as e:
            job["error"] = str(e)
            for st in job["steps"].values():
                if st["state"] == "running":
                    st["state"] = "error"
        except Exception as e:  # unerwartet — trotzdem lesbar anzeigen
            job["error"] = f"{type(e).__name__}: {e}"
            for st in job["steps"].values():
                if st["state"] == "running":
                    st["state"] = "error"
        finally:
            job["done"] = True

    threading.Thread(target=worker, daemon=True).start()
    return True, "gestartet"


# Laufende Heilungen pro Installation — verhindert, dass mehrfaches Klicken
# mehrere Kill/Restart-Zyklen uebereinanderlegt.
HEAL_ACTIVE = set()
HEAL_LOCK = threading.Lock()

# Ein Order-Bot pro Instanz zur Zeit (Review-Fund 15.08.2026): der
# ThreadingHTTPServer bedient POSTs parallel — zwei gleichzeitige
# master-order-Aufrufe wuerden sonst zwei Orders platzieren.
MASTER_ORDER_LOCKS = {}
MASTER_ORDER_GUARD = threading.Lock()
DEALS_LESEN = set()   # N2 (04.11.2026): Instanzen, deren MASTER_ORDER_LOCK gerade eine Deal-Lesung (/api/deals, nur lesen) hält
VORFLUG_LESEN = set()   # F-A (11.11.2026): Instanzen, deren MASTER_ORDER_LOCK gerade ein Konto-Vorflug (/api/vorflug, nur lesen) hält
VORFLUG_WARTE_S = 25.0  # eine Order/ein Close wartet so lange VOR allen Riegeln auf einen laufenden Vorflug (Lese-Deckel 20 s) statt 409 = Fehlstart
VORFLUG_DECKEL_S = 20   # Deckel des Bot-Laufs „vorflug“ (Prüfer S1: 25 + 300 s Bot bleibt unter dem Proxy-Deckel 310 s / mtcApi 320 s)


ORDER_ANGEMELDET = {}   # F-A (Hinweis S1): config_file → Zeitpunkt, zu dem eine Order/ein Close in die Route kam (nach dem Vorab-Warten)
ORDER_ANGEMELDET_S = 60.0   # so lange startet auf dieser Instanz kein Vorflug (deckt die Riegel bis zum acquire; danach hält die Order den Lock)


def vorflug_darf(fname, angemeldet, jetzt):
    """REIN RECHNEND (testbar): darf ein Vorflug auf dieser Instanz jetzt den Lock nehmen? Nein, solange eine Order/ein Close angemeldet ist."""
    return jetzt - float((angemeldet or {}).get(fname) or 0.0) >= ORDER_ANGEMELDET_S


def _vorflug_abwarten(fname):
    """F-A (Prüfer M1): läuft auf DIESER Instanz gerade ein Konto-Vorflug (nur lesen), gestreut warten, bis er fertig ist — VOR allen Riegeln (Richtung,
    Echo-Fenster, Copier-Frische, Heilung), damit sie beim Senden frisch sind. Danach unverändert acquire(blocking=False): ein zweiter Auftrag bekommt
    wie bisher sofort 409. → gewartete Sekunden."""
    t0 = time.time()
    while fname in VORFLUG_LESEN and time.time() - t0 < VORFLUG_WARTE_S:
        time.sleep(0.5 + random.random() * 0.5)
    return time.time() - t0


def mt5_order_belegt(locks=None, lesen=None):
    """REIN (testbar, Hinweis S1 zu RA2 F1, 11.11.2026): hält eine Instanz ihren MASTER_ORDER_LOCK für eine ORDER bzw. einen Close? Reine Lesungen
    (/api/deals, /api/vorflug — DEALS_LESEN/VORFLUG_LESEN) fassen weder Fenster noch Maus an: sie zählen für die PC-weiten Belegt-Prüfungen
    (Tab-Heilung/Fenster nach vorn, Panel-Neustart) nicht mit — sonst wartete dort alles bis zu 90 s auf die Deal-Lesung einer ANDEREN Instanz.
    Der Lock je Instanz selbst bleibt unverändert (Order gegen Lesung derselben Instanz)."""
    locks = MASTER_ORDER_LOCKS if locks is None else locks
    lesen = (DEALS_LESEN | VORFLUG_LESEN) if lesen is None else lesen
    return any(l.locked() and f not in lesen for f, l in list(locks.items()))

# Orbit-Puls (30.08.2026): EIN Lock fuer den ganzen TradingView-Weg, nicht pro
# Instanz. Der MT5-Bot bedient je ein eigenes Terminal, der TV-Bot bedient
# Browser und Maus — davon gibt es genau eines. Zwei parallele Laeufe wuerden
# sich die Klicks gegenseitig wegziehen, mitten im Order-Ticket.
TV_ORDER_LOCK = threading.Lock()
def hedge_solo_zeiten(erg, proxy_ms, t_ein, t_aus):
    """REIN RECHNEND (HEDGE-ZU-7S, 02.11.2026, Plan e67ec7b9: Close hing 7,17 s zwischen Tab und Panel): erg mit Stempeln in zeiten_ms —
    proxy_ein (Eingang app.py /copier), panel_ein (Eingang do_POST), panel_aus (Quittung geht raus), alle in ms. Nur Messung: Fehlt ein Wert
    oder ist er unlesbar, bleibt das Feld weg; erg sonst unverändert."""
    if not isinstance(erg, dict):
        return erg
    z = dict(erg.get("zeiten_ms")) if isinstance(erg.get("zeiten_ms"), dict) else {}
    try:
        z["proxy_ein"] = int(str(proxy_ms))
    except (TypeError, ValueError):
        pass
    if t_ein:
        z["panel_ein"] = round(t_ein * 1000)
    if t_aus:
        z["panel_aus"] = round(t_aus * 1000)
    return dict(erg, zeiten_ms=z)


# Solo-Hedge-Auftragsdatei (24.09.2026): zwei gleichzeitige /api/hedge-solo duerfen sich
# die Liste nicht gegenseitig ueberschreiben (Auto-Close schliesst mehrere Plaene in einem Tick).
HEDGE_SOLO_LOCK = threading.Lock()


# PC-Kennung im Panel (25.09.2026, Koordinations-Session): Finn nutzt auf pc-cccccc zwei Chrome-Profile (Puls +
# Feed). Prophos erzeugte die Kennung je Profil aus localStorage → zwei Kennungen am selben PC (pc-cccccc +
# pc-dddddd), und hedge.pc band Wächter/Schließen an EIN Profil. Jetzt verwahrt das Panel die Kennung für alle
# Profile des PCs. Keine Erfindung, keine Überschreibung: das erste Profil, das POST /api/pc-id schickt, trägt
# seine bestehende Kennung ein (so bleiben pc-cccccc … erhalten), jedes weitere bekommt diese zurück.
PC_ID_DATEI = os.path.join(HERE, "pc_id.json")
PC_ID_RE = re.compile(r"^pc-[a-z0-9]{4,12}$")
PC_ID_LOCK = threading.Lock()


def pc_id_lesen(pfad=None):
    """Gespeicherte PC-Kennung oder None (Datei fehlt, kaputt oder Format ungültig — nie raten)."""
    d = read_json(pfad or PC_ID_DATEI, None)
    v = d.get("pc_id") if isinstance(d, dict) else None
    return v if isinstance(v, str) and PC_ID_RE.fullmatch(v) else None


def pc_id_setzen(neu, pfad=None):
    """Setzt die Kennung NUR, wenn noch keine gültige gespeichert ist (atomar über .tmp + os.replace).
    -> (gueltige_kennung, neu_gesetzt: bool). Ungültiges Format → ValueError (Panel antwortet 400)."""
    neu = str(neu or "").strip()
    if not PC_ID_RE.fullmatch(neu):
        raise ValueError("pc_id muss dem Muster pc-[a-z0-9]{4,12} entsprechen")
    pfad = pfad or PC_ID_DATEI
    with PC_ID_LOCK:
        alt = pc_id_lesen(pfad)
        if alt:
            return alt, False
        tmp = pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"pc_id": neu, "gesetzt_at": datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
        os.replace(tmp, pfad)
        return neu, True


# ══ TAB SELBST NEU LADEN (Finn 16.10.2026: „Wenn man den Tab neu laden muss, mach das als Bot — wie beim Balancelesen. Nie mehr
# Hand-F5.") Anlass: Chris · pc-c19p2l hing mit tab_bw „Popup offen" auf .1565, Copier/Bot schon .1582 — der Tab startete Pläne mit
# altem Code (ohne 1-s-Doppelsperre), F5 von Hand war nötig. Der Neulade-Wächter IM Tab kann einen Tab mit altem oder hängendem Code
# nicht retten; das Panel ist per Code-Sync immer aktuell. Es fragt je Minute Railway GET /code/tab-stand/<pc_id> (Tab-Build aus
# mt5_live + Server-Riegel) und lädt den VORHANDENEN Tab neu: Chrome-Fenster mit Titel „Prophos …" nach vorn, Strg+F5, das vorige
# Fenster zurück (minimiert bleibt minimiert). Kein neuer Tab und kein neues Fenster (zwei Tabs mit derselben pc_id claimen beide).
# Nur wenn: Tab ≥ TAB_NL_HINTER_S hinter origin (nicht inhaltsgleich) oder ≥ TAB_NL_STUMM_S stumm; kein Server-Riegel (Signal läuft,
# Start geclaimt/≤ 5 min, Hedge öffnet/schließt); Puls hält nicht TV_ORDER_LOCK; ≥ TAB_NL_IDLE_S keine Eingabe am PC; höchstens
# 1 Versuch je TAB_NL_ABSTAND_S. Jeder Schritt mit genauem Grund ins Panel-Log und als ?panel= in die Railway-Spur. Aus mit
# „tab_neuladen": false in der Basis-Config. Nur Windows. ══
TAB_NL_TAKT_S = 60
TAB_NL_ANLAUF_S = 180
TAB_NL_HINTER_S = 20 * 60
TAB_NL_HINTER_BG_S = 3 * 60     # 30.10.2026: verdeckter Tab lädt nicht selbst (tab_bw „Tab im Hintergrund") → das Panel schon nach 3 min
TAB_NL_STUMM_S = 10 * 60
TAB_NL_IDLE_S = 120
TAB_NL_ABSTAND_S = 15 * 60
TAB_NL = {"grund": "", "at": 0.0, "letzter_versuch": 0.0, "hinter_seit": None, "ergebnis": ""}
# TAB ÖFFNEN, WENN GAR KEINER LÄUFT (Master 16.10.2026, aus „Braucht dich, Teil 1" 4b367e2 vom 13.10. — der kam nie auf main): der
# Prophos-Tab fragt das Panel alle 5 s über das lokale app.py (/api/instances, User-Agent python-requests; die Panel-Seite im Browser
# zählt nicht). Bleibt das TAB_OEFFNEN_FEHLT_S aus UND gibt es kein Chrome-Fenster mit aktivem Prophos-Tab, öffnet das Panel den Tab
# im Puls-Profil (order_bot.puls_start_profil — nie im Reader-Profil; Profil unklar → nicht öffnen). Nie ein zweiter Tab: steht ein
# Prophos-Fenster da, lädt der Neulade-Weg oben es neu statt zu öffnen.
TAB_OEFFNEN_FEHLT_S = 5 * 60
TAB_OEFFNEN_ANLAUF_S = 5 * 60
TAB_OEFFNEN_ABSTAND_S = 20 * 60
TAB_OEFFNEN_MAX_TAG = 8
TAB_URL = "http://localhost:5000/"
_TAB_OEFFNEN = {"zuletzt": 0.0, "start": time.time(), "geoeffnet": [], "tag": "", "url": "", "login": None, "tid": "", "geoeffnet_at": 0.0}
TAB_URL_RE = re.compile(r"^http://(localhost|127\.0\.0\.1):\d{2,5}/[A-Za-z0-9._/-]*$")
TAB_URL_V_RE = re.compile(r"^http://(localhost|127\.0\.0\.1):\d{2,5}/\?v=[0-9A-Za-z._-]{1,40}$")   # nur fürs Öffnen mit Build (Puls-Wache 02.11.2026)


# ══ HAUPT-TAB (30.10.2026, Master nach Befund C: Ina pc-xc5c52 — Prophos lag nicht im Puls-Chrome, F1 fand ihn per CDP nicht; die Tabs
# schlossen sich bis heute gar nicht aus, das Panel merkte sich nur die zuletzt fragende Kennung). Jeder Tab meldet seine Kennung (tid); das
# Panel führt GENAU EINEN Haupt-Tab: angemeldet vor nicht angemeldet, im Puls-Chrome vor einem anderen Chrome, bei gleichem Rang bleibt der
# bisherige (kein Flattern). Nur der Haupt-Tab zählt als Herzschlag (Öffnen/Neuladen/Heilung) — ein zweiter Tab bekommt haupt_tab:false und
# schaltet sich auf „nur ansehen" (prophos.html ?neben=1: ohne PC-Rollen, kein mt5_live, keine Claims). Geschlossen wird er nie. Ob eine
# Kennung im Puls-Chrome liegt, liest das Panel per CDP (window._tabHerzId der Prophos-Seiten, nur lesen). ══
TAB_HAUPT_FRISCH_S = 5 * 60   # Hysterese (S2 30.10.2026): Chrome drosselt verdeckte Tabs auf ~1 Abfrage/min oder friert sie kurz ein
TAB_PULS_PRUEF_S = 5 * 60
TAB_HAUPT_SICHER_S = 60   # kein anderer Tab fragte so lange → der fragende wird sofort Haupt-Tab (Master 30.10.2026)
TAB_ZAEHL_FRISCH_S = 90   # Doppel-Tab-Zählung: nur Kennungen, die eben noch gefragt haben (Spur Chris: alte Kennungen zählten 5 min mit)
_TABS = {}   # tid → {"at", "login", "url", "puls": True/False/None}
_TAB_HAUPT = {"tid": "", "puls_at": 0.0, "meldung": ""}


def haupt_tab_waehlen(tabs, jetzt, bisher="", ich=""):
    """REIN RECHNEND (testbar): Kennung des Haupt-Tabs ('' = keiner lebt). Lebend = Abfrage ≤ TAB_HAUPT_FRISCH_S her. Rang: angemeldet,
    dann im Puls-Chrome (puls True); bei gleichem Rang bleibt der bisherige, sonst der zuletzt fragende.
    SICHERUNG (Master 30.10.2026, nie eine Phase ohne Haupt-Tab): fragt gerade der Tab „ich" und hat KEIN anderer Tab in den letzten
    TAB_HAUPT_SICHER_S gefragt, wird „ich" sofort Haupt-Tab — die 5-min-Hysterese gilt nur, wenn ein anderer Tab nachweislich lebt
    (z. B. nach einem Deploy: alte, stille Kennungen halten den frisch geladenen Tab nie im „nur ansehen")."""
    if ich and ich in (tabs or {}) and not any(t != ich and jetzt - float(z.get("at") or 0) <= TAB_HAUPT_SICHER_S for t, z in tabs.items()):
        return ich
    lebend = {t: z for t, z in (tabs or {}).items() if jetzt - float(z.get("at") or 0) <= TAB_HAUPT_FRISCH_S}
    if not lebend:
        return ""
    rang = lambda z: (bool(z.get("login")), z.get("puls") is True)   # noqa: E731
    best = max(rang(z) for z in lebend.values())
    if bisher in lebend and rang(lebend[bisher]) == best:
        return bisher
    return max((t for t, z in lebend.items() if rang(z) == best), key=lambda t: float(lebend[t].get("at") or 0))


def tab_gesehen(user_agent, query=None):
    """Aufruf von /api/instances über das lokale app.py (= Prophos-Tab) → Herzschlag merken. Seit 16.10.2026 meldet der Tab dabei
    login (1/0), url (origin + pathname), build, tid (Kennung je Tab) — ältere Tabs ohne diese Angaben zählen nur als Herzschlag.
    → True = dieser Tab ist der Haupt-Tab (bzw. alter Tab ohne Kennung), False = zweiter Tab (haupt_tab:false)."""
    if not str(user_agent or "").lower().startswith("python-requests"):
        return True
    q = query or {}
    w = lambda k: str((q.get(k) or [""])[0]).strip()   # noqa: E731 — parse_qs-Form
    tid = w("tid")[:16] if w("tab") == "1" else ""
    if tid:
        jetzt = time.time()
        alt = _TABS.get(tid) or {}
        _TABS[tid] = {"at": jetzt, "login": w("login") == "1", "url": w("url"), "puls": alt.get("puls"), "neben_at": alt.get("neben_at")}
        for t in [t for t, z in _TABS.items() if jetzt - max(float(z.get("at") or 0), float(z.get("neben_at") or 0)) > 3600]:
            _TABS.pop(t, None)
        _TAB_HAUPT["tid"] = haupt_tab_waehlen(_TABS, jetzt, _TAB_HAUPT["tid"], tid)
        if _TAB_HAUPT["tid"] != tid:
            return False
    _TAB_OEFFNEN["zuletzt"] = time.time()
    if w("tab") == "1":
        if TAB_URL_RE.fullmatch(w("url")):
            _TAB_OEFFNEN["url"] = w("url")
        _TAB_OEFFNEN["login"] = w("login") == "1"
        _TAB_OEFFNEN["tid"] = w("tid")[:16]
        # 30.10.2026 (Stufen-Heilung): Sekunden seit dem letzten Supabase-Schreiben / ohne Realtime — leer = unbekannt (alter Tab)
        for k, feld in (("sb", "sb_s"), ("rt", "rt_aus_s")):
            try:
                _TAB_OEFFNEN[feld] = int(w(k)) if w(k) != "" else None
            except ValueError:
                _TAB_OEFFNEN[feld] = None
        # FS1 (10.11.2026): Sichtbarkeit (v/h) und Ladezeit (Unix-s) des Tabs — für den Tab-Zustand in der Spur (/api/tab-zustand); leer = alter Tab
        _TAB_OEFFNEN["vis"] = w("vis") if w("vis") in ("v", "h") else ""
        # F-B (11.11.2026): Antwort auf die Vorflug-Marke (nur der Haupt-Tab; ein Tab ohne dieses Feld bleibt „kann_pong“ False)
        # Prüfer S4: „kann_pong“ gilt nur für DIESEN Tab und nur, solange er vpong schickt (≤ TAB_VF_PONG_FRISCH_S) — ein späterer Haupt-Tab ohne
        # vpong wird wieder nur an den Lebenszeichen gemessen. Der Tab schickt vpong=<Marke> bzw. vpong=- ohne Marke.
        if w("vpong"):
            TAB_VORFLUG.update(vpong_tid=w("tid")[:16], vpong_at=time.time())
            if TAB_VORFLUG.get("marke") and w("vpong") == TAB_VORFLUG["marke"]:
                TAB_VORFLUG["pong_at"] = time.time()
        try:
            _TAB_OEFFNEN["geladen"] = int(w("geladen")) if w("geladen") else None
        except ValueError:
            _TAB_OEFFNEN["geladen"] = None
    return True


def neben_tab_frei(tabs, tid, login, jetzt, haupt):
    """REIN RECHNEND (testbar, /api/haupt-tab): darf ein Tab im „nur ansehen"-Modus wieder Haupt-Tab werden? Ja, wenn kein Haupt-Tab mehr
    lebt oder er selbst den höheren Rang hätte (angemeldet / im Puls-Chrome)."""
    z = (tabs or {}).get(haupt) if haupt else None
    if not z or jetzt - float(z.get("at") or 0) > TAB_HAUPT_FRISCH_S:
        return True
    ich = (bool(login), ((tabs or {}).get(tid) or {}).get("puls") is True)
    return ich > (bool(z.get("login")), z.get("puls") is True)


def tab_oeffnen_entscheiden(jetzt, zuletzt, start, fenster_da, letzter_versuch, n_heute, lock_frei, idle_s, chrome_offen=False, puls_hat=True):
    """REIN RECHNEND (testbar): (öffnen: bool, grund: str). '' = Tab lebt, nichts zu tun. chrome_offen = irgendein Chrome-Hauptfenster
    läuft: früher dann NIE öffnen (Prüfer S2 16.10.2026: ein eingefrorener/verworfener Prophos-Tab im Hintergrund fragt nicht mehr; ein
    neuer Tab gäbe beim nächsten Anklicken zwei Tabs mit derselben pc_id — Fleet-Push, Hedge-Wächter und Signale doppelt). Seit der
    Haupt-Tab-Wahl (30.10.2026) wird ein wieder erwachter alter Tab zum „nur ansehen"-Tab — gesperrt bleibt das Öffnen nur noch, wenn im
    Puls-Chrome schon ein Prophos-Tab steht (puls_hat; den heilt die Stufen-Heilung). Geöffnet wird nur noch im Puls-Chrome."""
    if jetzt - start < TAB_OEFFNEN_ANLAUF_S:
        return False, ""
    still_s = jetzt - max(zuletzt, start)
    if still_s < TAB_OEFFNEN_FEHLT_S:
        return False, ""
    warum = f"kein Prophos-Tab: seit {int(still_s // 60)} min keine Abfrage vom Tab"
    if fenster_da:
        return False, f"{warum}, aber ein Prophos-Fenster ist da — kein zweiter Tab (Neulade-Weg)"
    if chrome_offen and puls_hat:
        return False, (f"{warum} — Chrome läuft, aber ohne aktiven Prophos-Tab: Prophos-Tab im Hintergrund oder von Chrome verworfen → "
                       "am PC den Prophos-Tab anklicken (kein zweiter Tab)")
    if n_heute >= TAB_OEFFNEN_MAX_TAG:
        return False, f"{warum} — heute schon {n_heute}× geöffnet (Deckel {TAB_OEFFNEN_MAX_TAG})"
    if letzter_versuch and jetzt - letzter_versuch < TAB_OEFFNEN_ABSTAND_S:
        return False, f"{warum} — zuletzt vor {int((jetzt - letzter_versuch) // 60)} min geöffnet (höchstens 1 je {TAB_OEFFNEN_ABSTAND_S // 60} min)"
    if not lock_frei:
        return False, f"{warum} — wartet: Puls/MT5-Order läuft"
    if idle_s is not None and idle_s < TAB_NL_IDLE_S:
        return False, f"{warum} — wartet: am PC wird gerade gearbeitet (letzte Eingabe vor {int(idle_s)} s)"
    return True, warum


def _build_nr(v):
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.(\d+)", str(v or "").strip())
    return (m.group(1), int(m.group(2))) if m else None


# ══ PROPHOS-TAB IM PULS-CHROME FEHLT → SOFORT NEU (Finn 02.11.2026 ~18:40 Dubai „Ja, einbauen“; Simon pc-pmqd8g 18:31:06: der TopstepX-Lauf bekam im
# 1. Versuch einen ConnectionError, der PULS-CHROME-NEUSTART (order_bot _puls_chrome_neustart, Browser.close) startete das Puls-Chrome nur mit topstepx.com
# neu — der Prophos-Tab war weg, während Finns Big Trade 88b28130 mit offenem Fusion-Hedge lief, bis Finn localhost:5000 von Hand öffnete). Der bisherige Weg
# (tab_oeffnen_entscheiden) wartet 5 min Stille und 120 s ohne Eingabe, puls_tab_entscheiden zusätzlich auf Server-Riegel — beides hält bei offenem Trade.
# Diese Wache: steht im Puls-Chrome (CDP erreichbar) PULS_WACHE_FEHLT_S lang keine Seite auf localhost:5000/127.0.0.1:5000, öffnet das Panel eine — auch bei
# offenem Trade (Finn ausdrücklich), aber nie während Puls/Polar/MT5-Order (dann nach dem Lauf), höchstens 1× je PULS_WACHE_ABSTAND_S. Nur öffnen: kein Tab
# zu, kein Klick, kein Login (lädt die Seite, tippt nichts), neues Fenster im Hintergrund (Target.createTarget background, wie _tab_oeffnen). Läuft das
# Puls-Chrome nicht, startet es diese Wache nicht. ══
PULS_WACHE_FEHLT_S = 60
PULS_WACHE_ABSTAND_S = 5 * 60
PULS_WACHE_IDLE_S = 25   # S9 02.11.2026: ob ein neues Fenster im Hintergrund den Fokus nimmt, ist unbelegt — nie, während jemand tippt (kurz, nicht 120 s)
_PULS_WACHE = {"fehlt_seit": None, "letzter": 0.0, "grund": ""}


def puls_wache_entscheiden(jetzt, erreichbar, n_prophos, fehlt_seit, letzter, lock_frei, idle_s=None):
    """REIN RECHNEND (testbar): (öffnen, grund, fehlt_seit_neu). erreichbar = CDP-Liste des Puls-Chrome lesbar, n_prophos = Seiten auf :5000,
    idle_s = Sekunden ohne Eingabe am PC (None = unbekannt)."""
    if not erreichbar or n_prophos > 0:
        return False, "", None
    fehlt_seit = fehlt_seit or jetzt
    warum = f"kein Prophos-Tab im Puls-Chrome seit {int(jetzt - fehlt_seit)} s"
    if jetzt - fehlt_seit < PULS_WACHE_FEHLT_S:
        return False, "", fehlt_seit
    if letzter and jetzt - letzter < PULS_WACHE_ABSTAND_S:
        return False, f"{warum} — zuletzt vor {int(jetzt - letzter)} s geöffnet (höchstens 1 je {PULS_WACHE_ABSTAND_S // 60} min)", fehlt_seit
    if not lock_frei:
        return False, f"{warum} — wartet: Puls/Polar/MT5-Order läuft, öffnet danach", fehlt_seit
    if idle_s is not None and idle_s < PULS_WACHE_IDLE_S:
        return False, f"{warum} — wartet: am PC wird gerade eingegeben (vor {int(idle_s)} s), öffnet nach {PULS_WACHE_IDLE_S} s Ruhe", fehlt_seit
    return True, warum, fehlt_seit


def _puls_wache_url():
    """Adresse des letzten Tabs (localhost ≠ 127.0.0.1 = getrennte Logins, S9 02.11.2026 — sonst öffnete die Wache einen nicht angemeldeten Tab) mit
    ?v=<Build> wie die Neulade-Wege des Tabs (frischer Tab-Stand von Railway, sonst OS_TAB_BUILD der lokalen prophos.html)."""
    m = re.match(r"^(http://(?:localhost|127\.0\.0\.1):\d{2,5})/", str(_TAB_OEFFNEN.get("url") or ""))
    basis = (m.group(1) + "/") if m else TAB_URL
    b = str(((TAB_NL.get("stand") or {}) if time.time() - float(TAB_NL.get("stand_at") or 0) < 600 else {}).get("origin") or "")
    if not re.fullmatch(r"[0-9A-Za-z._-]{1,40}", b):
        try:
            with open(os.path.join(os.path.dirname(HERE), "prophos.html"), encoding="utf-8") as f:
                m = re.search(r"const OS_TAB_BUILD = '([0-9A-Za-z._-]{1,40})'", f.read())
            b = m.group(1) if m else ""
        except OSError:
            b = ""
    return basis + (f"?v={b}" if b else f"?v={int(time.time())}")


def _puls_wache_schritt(pc):
    """Eine Runde der Puls-Wache (im Tab-Wächter, vor allem anderen nach dem Fern-Auftrag). Wirft nie."""
    try:
        try:
            liste = _cdp_get("/json/list")
            erreichbar = isinstance(liste, list)
        except Exception:
            liste, erreichbar = [], False
        n = sum(1 for t in (liste or []) if isinstance(t, dict) and t.get("type") == "page" and _PROPHOS_URL_RE.match(str(t.get("url") or "")))
        jetzt = time.time()
        auf, grund, _PULS_WACHE["fehlt_seit"] = puls_wache_entscheiden(jetzt, erreichbar, n, _PULS_WACHE["fehlt_seit"], _PULS_WACHE["letzter"],
                                                                      _browser_und_mt5_frei(), _win_leerlauf_s())
        if auf:
            ok, msg = _tab_oeffnen(_puls_wache_url())
            if ok or "lokales Backend" not in str(msg):    # Backend gerade im Neustart → nächste Runde neu, sonst zählt der Versuch
                _PULS_WACHE["letzter"] = jetzt
            if ok:
                _TAB_OEFFNEN["geoeffnet"].append(datetime.now().isoformat(timespec="seconds"))
                _TAB_OEFFNEN["geoeffnet_at"] = jetzt
            grund = f"{grund} → {'geöffnet' if ok else 'NICHT geöffnet'}: {msg}"
        if grund and grund != _PULS_WACHE["grund"]:
            _PULS_WACHE["grund"] = grund
            print(f"[puls-wache] {grund}", flush=True)
            if pc and auf:
                _tab_stand_holen(pc, f"Puls-Wache: {grund}"[:200])   # Spur an Railway ([tab-stand] im Log)
    except Exception as e:
        print(f"[puls-wache] Fehler: {type(e).__name__}: {e}", flush=True)


def tab_neuladen_entscheiden(stand, jetzt, hinter_seit, letzter_versuch, idle_s, lock_frei, lokal_still_s=None):
    """REIN RECHNEND (testbar): (laden: bool, grund: str, hinter_seit_neu). stand = Antwort von /code/tab-stand (oder None),
    jetzt in s (epoch), hinter_seit = seit wann das Panel den Tab hinter origin sieht (s, oder None), letzter_versuch in s,
    idle_s = Sekunden ohne Eingabe am PC (None = unbekannt), lock_frei = TV_ORDER_LOCK frei. lokal_still_s = Sekunden ohne Abfrage des
    Tabs beim Panel (/api/instances) — zählt wie „stumm" (auch auf PCs ohne mt5_live-Zeile), None = Panel läuft erst kurz."""
    if not isinstance(stand, dict) or stand.get("ok") is not True:
        return False, "Tab-Stand von Railway nicht lesbar", hinter_seit
    o, t = _build_nr(stand.get("origin")), _build_nr(stand.get("tab_build"))
    gleich = _build_nr(stand.get("tab_gleich"))
    tab_at = None
    try:
        tab_at = datetime.fromisoformat(str(stand.get("tab_at")).replace("Z", "+00:00")).timestamp() if stand.get("tab_at") else None
    except ValueError:
        tab_at = None
    stumm_s = (jetzt - tab_at) if tab_at else None
    hinter = bool(o and t and t < o and not (gleich and gleich >= o))
    if hinter:
        hinter_seit = hinter_seit or jetzt
        bw = stand.get("tab_bw") if isinstance(stand.get("tab_bw"), dict) else {}
        try:                                         # „hinter seit" des Tab-Wächters (ms) — älter als das eigene Erkennen zählt
            hs = float(bw.get("hinter_seit")) / 1000.0
            if 0 < hs < hinter_seit:
                hinter_seit = hs
        except (TypeError, ValueError):
            pass
    else:
        hinter_seit = None
    if lokal_still_s is not None and lokal_still_s >= TAB_NL_STUMM_S:
        warum = f"Tab stumm seit {int(lokal_still_s // 60)} min (keine Abfrage beim Panel)"
    elif stumm_s is not None and stumm_s >= TAB_NL_STUMM_S:
        warum = f"Tab stumm seit {int(stumm_s // 60)} min (letztes Lebenszeichen in mt5_live)"
    elif hinter and jetzt - hinter_seit >= TAB_NL_HINTER_S:
        warum = f"Tab {stand.get('tab_build')} seit {int((jetzt - hinter_seit) // 60)} min hinter {stand.get('origin')}"
    elif hinter and jetzt - hinter_seit >= TAB_NL_HINTER_BG_S and "Hintergrund" in str((bw or {}).get("grund") or ""):
        # der verdeckte Tab lädt nicht selbst (prophos.html bwGrund) — das Panel übernimmt früher
        warum = f"Tab {stand.get('tab_build')} seit {int((jetzt - hinter_seit) // 60)} min hinter {stand.get('origin')} (Tab im Hintergrund)"
    elif hinter:
        return False, f"Tab {stand.get('tab_build')} hinter {stand.get('origin')} seit {int((jetzt - hinter_seit) // 60)} min — " \
                      f"der Tab-Wächter hat bis {TAB_NL_HINTER_S // 60} min Zeit", hinter_seit
    else:
        return False, "", hinter_seit                # Tab aktuell (oder inhaltsgleich) und lebt — nichts zu tun
    riegel = str(stand.get("riegel") or "").strip()
    if riegel:
        return False, f"{warum} — wartet: {riegel}", hinter_seit
    if not lock_frei:
        return False, f"{warum} — wartet: Puls/MT5-Order läuft (Browser oder MT5 belegt)", hinter_seit
    if idle_s is not None and idle_s < TAB_NL_IDLE_S:
        return False, f"{warum} — wartet: am PC wird gerade gearbeitet (letzte Eingabe vor {int(idle_s)} s)", hinter_seit
    if letzter_versuch and jetzt - letzter_versuch < TAB_NL_ABSTAND_S:
        return False, f"{warum} — wartet: letzter Neulade-Versuch vor {int((jetzt - letzter_versuch) // 60)} min (höchstens 1 je " \
                      f"{TAB_NL_ABSTAND_S // 60} min)", hinter_seit
    return True, warum, hinter_seit


def tab_neulade_weg(stand, haupt_puls, pro0):
    """REIN RECHNEND (testbar): 'cdp' | 'fenster'. VERDECKTER HAUPT-TAB ZUERST PER CDP (Betrieb 1 03.11.2026, 16:54 Dubai: 7 PC-Tabs hingen auf .2004–.2013,
    alle mit tab_bw „Tab im Hintergrund — Panel lädt neu“, pc-2zc2we seit 02:36Z). Der alte Weg drückte zuerst Strg+F5 in JEDEM sichtbaren Chrome-Fenster mit
    aktivem Prophos-Tab und galt dann als erledigt — steht neben dem verdeckten Haupt-Tab im Puls-Chrome ein sichtbarer „nur ansehen“-Tab, lud er alle 15 min
    den falschen Tab, der Haupt-Tab (der mt5_live schreibt) blieb alt. Jetzt: pro0 = vorderste Prophos-Seite im Puls-Chrome (cdp_prophos_ziele, Haupt-Tab
    zuerst) oder None. CDP nur, wenn pro0 KEIN „nur ansehen“-Tab (?neben=1) ist UND der Haupt-Tab nachweislich im Puls-Chrome liegt (haupt_puls True) oder —
    Kennung unbekannt, etwa bei nur einem Tab — er „Hintergrund“ meldet (S2-Stopp 03.11.2026: „verdeckt“ allein reicht nicht, nie den ?neben=1-Tab laden und den
    Haupt-Tab alt lassen; liegt der Haupt-Tab woanders, haupt_puls False → Fenster). Sonst wie bisher Fenster, CDP als Rückfall."""
    if not isinstance(pro0, dict) or "neben=1" in str(pro0.get("url") or "") or haupt_puls is False:
        return "fenster"
    bw = (stand or {}).get("tab_bw") if isinstance(stand, dict) and isinstance(stand.get("tab_bw"), dict) else {}
    verdeckt = "Hintergrund" in str((bw or {}).get("grund") or "")
    return "cdp" if haupt_puls is True or verdeckt else "fenster"


def cdp_vorn_erlaubt(stand, scharf_ids):
    """REIN RECHNEND (testbar): darf das CDP-Neuladen den Prophos-Tab per /json/activate nach vorn holen? (alter S9-Stopp zu ed4f8de4, S2-Stopp 03.11.2026:
    activate verdeckte TradingView/TopstepX 6–19 s.) Nur wenn der PC stumm ist: Tab-Stand lesbar, plaene_offen_tv == 0 (kein offener TV-/TSX-Plan; None =
    IDs unbekannt → nein), kein Server-Riegel, kein offener scharfer TV-Trade mit Hedge. Sonst nur Page.reload im Hintergrund. Den TV_ORDER_LOCK und
    _browser_und_mt5_frei prüft _prophos_tab_neuladen_cdp selbst."""
    if not isinstance(stand, dict) or stand.get("ok") is not True or scharf_ids:
        return False
    if str(stand.get("riegel") or "").strip() or str(stand.get("riegel_tv") or "").strip():
        return False
    n = stand.get("plaene_offen_tv")
    return isinstance(n, int) and not isinstance(n, bool) and n == 0


def cdp_rueckweg_seiten(liste, pro_id, max_n=8):
    """REIN RECHNEND (testbar): CDP-Seitenliste (/json/list, nach letzter Sichtbarkeit sortiert, jüngste zuerst) → die Seiten VOR dem Prophos-Tab, jüngste
    zuerst, höchstens max_n. Für den Rückweg nach einem activate (S2-Stopp 03.11.2026: nicht immer TradingView nach vorn, sondern das, was vorher vorn war —
    auch TopstepX). Der Rückweg aktiviert sie in umgekehrter Reihenfolge (älteste zuerst): So landet in JEDEM Chrome-Fenster zuletzt die Seite vorn, die dort
    zuletzt sichtbar war, auch wenn TradingView und TopstepX in getrennten Fenstern liegen (Gegenprüfung 03.11.2026: die Liste kennt keine Fenster).
    Prophos nicht in der Liste → nur die vorderste Seite."""
    seiten = [t for t in liste or () if isinstance(t, dict) and t.get("type") == "page" and t.get("id")]
    vor = []
    for t in seiten:
        if t.get("id") == pro_id:
            return vor[:max_n]
        vor.append(t)
    return seiten[:1] if seiten and seiten[0].get("id") != pro_id else []


def _win_leerlauf_s():
    """Sekunden seit der letzten Maus-/Tastatureingabe am PC (GetLastInputInfo) oder None."""
    try:
        import ctypes

        class _LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = _LII()
        lii.cbSize = ctypes.sizeof(_LII)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        return max(0.0, ((ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0)
    except Exception:
        return None


def _prophos_fenster():
    """Sichtbare Chrome-Fenster, deren aktiver Tab Prophos ist (Titel „Prophos … - Google Chrome") → [(hwnd, titel)]."""
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    gefunden = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _je(hwnd, _l):
        try:
            if not u32.IsWindowVisible(hwnd):
                return True
            kb = ctypes.create_unicode_buffer(128)
            u32.GetClassNameW(hwnd, kb, 128)
            if kb.value != "Chrome_WidgetWin_1":
                return True
            n = u32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            t = buf.value or ""
            if re.match(r"^Prophos\b", t) and t.endswith("Google Chrome"):
                gefunden.append((int(hwnd), t))
        except Exception:
            pass
        return True
    u32.EnumWindows(_je, 0)
    return gefunden


def _chrome_hauptfenster_da():
    """Läuft irgendein sichtbares Chrome-Hauptfenster („… - Google Chrome", Klasse Chrome_WidgetWin_1)? Fehler → True (nie raten)."""
    try:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        da = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def _je(hwnd, _l):
            if u32.IsWindowVisible(hwnd):
                kb = ctypes.create_unicode_buffer(128)
                u32.GetClassNameW(hwnd, kb, 128)
                if kb.value == "Chrome_WidgetWin_1":
                    n = u32.GetWindowTextLengthW(hwnd)
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u32.GetWindowTextW(hwnd, buf, n + 1)
                    if (buf.value or "").endswith("Google Chrome"):
                        da.append(int(hwnd))
                        return False
            return True
        u32.EnumWindows(_je, 0)
        return bool(da)
    except Exception:
        return True


def _fenster_vorn(hwnd):
    """Fenster nach vorn (AttachThreadInput, Rückfall Alt — wie _konsole_nach_vorn) → True, wenn es danach vorn steht."""
    import ctypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    vorn = u32.GetForegroundWindow()
    mein = k32.GetCurrentThreadId()
    fremd = u32.GetWindowThreadProcessId(vorn, None) if vorn else 0
    angehaengt = bool(fremd and fremd != mein and u32.AttachThreadInput(fremd, mein, True))
    try:
        u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    finally:
        if angehaengt:
            u32.AttachThreadInput(fremd, mein, False)
    if int(u32.GetForegroundWindow() or 0) != hwnd:
        u32.keybd_event(0x12, 0, 0, 0); u32.keybd_event(0x12, 0, 2, 0)
        u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    return int(u32.GetForegroundWindow() or 0) == hwnd


def _prophos_tab_neu_laden():
    """Strg+F5 im Prophos-Fenster (unter TV_ORDER_LOCK) → (ok, Klartext). Fenster-Treue: kein neues Fenster/kein neuer Tab, nur
    Tasten im Prophos-Fenster und nur, wenn es nachweislich vorn steht; danach das vorige Fenster zurück, minimiert bleibt minimiert."""
    import ctypes
    u32 = ctypes.windll.user32
    fenster = _prophos_fenster()
    if not fenster:
        return False, ("kein Chrome-Fenster mit aktivem Prophos-Tab gefunden (Prophos-Tab zu oder nicht vorn in seinem Fenster) — "
                       "am PC Prophos öffnen bzw. den Tab anklicken")
    if not TV_ORDER_LOCK.acquire(blocking=False):
        return False, "Puls läuft gerade im Browser — nächster Versuch später"
    try:
        if not _browser_und_mt5_frei(tv_eigen=True):
            return False, "MT5-Order läuft gerade (Echo/Master-Order) — nächster Versuch später"
        vorher = int(u32.GetForegroundWindow() or 0)
        erg = []
        for hwnd, titel in fenster:
            mini = bool(u32.IsIconic(hwnd))
            if mini:
                u32.ShowWindow(ctypes.c_void_p(hwnd), 9)         # SW_RESTORE
                time.sleep(0.3 + random.random() * 0.2)
            if not _fenster_vorn(hwnd):
                erg.append(f"„{titel[:40]}“ kam nicht nach vorn — nichts gedrückt")
                if mini:
                    u32.ShowWindow(ctypes.c_void_p(hwnd), 6)     # SW_MINIMIZE
                continue
            time.sleep(0.25 + random.random() * 0.25)            # Jitter wie Puls
            if int(u32.GetForegroundWindow() or 0) != hwnd:      # Beweis direkt vor dem Druck
                erg.append(f"„{titel[:40]}“ verlor den Vordergrund — nichts gedrückt")
                continue
            u32.keybd_event(0x11, 0, 0, 0)                        # Strg
            time.sleep(0.04 + random.random() * 0.04)
            u32.keybd_event(0x74, 0, 0, 0); u32.keybd_event(0x74, 0, 2, 0)   # F5
            time.sleep(0.04 + random.random() * 0.04)
            u32.keybd_event(0x11, 0, 2, 0)
            erg.append(f"Strg+F5 in „{titel[:40]}“")
            time.sleep(1.0 + random.random() * 0.5)
            if mini:
                u32.ShowWindow(ctypes.c_void_p(hwnd), 6)
        if vorher and vorher not in [h for h, _t in fenster]:
            try:
                _fenster_vorn(vorher)
            except Exception:
                pass
        ok = any(e.startswith("Strg+F5") for e in erg)
        return ok, "; ".join(erg)
    except Exception as e:
        return False, f"Neuladen fehlgeschlagen: {type(e).__name__}: {e}"
    finally:
        TV_ORDER_LOCK.release()


# ══ NL2 TABSTREIFEN-WEG (11.11.2026, Master nach NL1/S2: Jona pc-b97zc7 + Ahaj pc-na1q6b hingen seit 19:12 Dubai auf .2181, Julian pc-6qnjpu seit
# 20:05 auf .2187 — alle 15 min „→ NICHT neu geladen: kein Chrome-Fenster mit aktivem Prophos-Tab gefunden“, der CDP-Rückfall fand nichts, die Puls-Wache
# meldete nie: auf diesen Echo-PCs läuft kein Puls-Chrome (:9333 zu), Prophos liegt im NORMALEN Chrome hinter einem anderen Tab, und ein verdeckter Tab
# lädt bewusst nicht selbst (prophos.html bwGrund „Tab im Hintergrund — Panel lädt neu“). Jetzt, NUR wenn Fenster-Weg UND CDP leer sind und :9333 nicht
# erreichbar ist: das Panel liest per UIA die Tabstreifen der Chrome-Fenster (Webinhalt wird nie betreten), wählt GENAU EINEN Tab „Prophos …“ per
# SelectionItem (Rückfall Invoke) — keine Maus —, prüft, dass das Fenster vorn steht und sein Titel jetzt „Prophos …“ ist, drückt Strg+F5, wartet wie der
# CDP-Weg auf die erste Abfrage des Tabs und wählt danach den vorher aktiven Tab wieder (minimiert bleibt minimiert, voriges Fenster zurück). Riegel wie
# beim Fenster-Weg (Server-Riegel Start ≤ 5 min/Signal/Hedge, keine Eingabe ≥ 120 s, 1 Versuch je 15 min — tab_neuladen_entscheiden) plus TV_ORDER_LOCK,
# keine MT5-Order/Polar und die PC-Tipp-Sperre der Echo-Läufe (Mutex, ohne Warten). Zwei oder mehr Prophos-Tabs, kein eindeutig aktiver Tab, Tabstreifen
# geändert → nichts gedrückt, Grund in die Spur. Kein CDP, kein zweites Chrome, kein neuer Tab. Aus mit „tab_streifen“: false in der Basis-Config. ══
ECHO_TIPP_MUTEX_PANEL = "Local\\ProphosEchoTipp"   # derselbe Name wie order_bot.ECHO_TIPP_MUTEX (PC-Tipp-Sperre um jeden Echo-Lauf)


# Walker als EINE Quelle für Panel und UIA-Prozess (nicht inspect.getsource: nach einem Code-Sync läse das die neue Datei an alten Zeilen)
_TAB_STREIFEN_WALKER = r'''
_PROPHOS_TAB_MUSTER = r"^Prophos\b(?!-Backend)"   # wie order_bot.prophos_tab_wahl: die Backend-Konsole „Prophos-Backend“ zählt nie

def tabstreifen_tabs(wurzel, max_tiefe=14, max_knoten=900):
    """REIN (testbar; läuft auch im UIA-Prozess, _TAB_STREIFEN_WALKER): TabItem-Elemente unter wurzel (Objekte mit .children() und
    .control_type, z. B. pywinauto UIAElementInfo), Breitensuche in Tabstreifen-Reihenfolge. Webinhalt (control_type Document) wird nie betreten,
    höchstens max_knoten Elemente — Chrome baut sonst den ganzen Barrierefreiheits-Baum der Seite."""
    out, q, n = [], [(wurzel, 0)], 0
    while q and n < max_knoten:
        el, d = q.pop(0)
        n += 1
        try:
            kinder = list(el.children())
        except Exception:
            continue
        for k in kinder:
            try:
                ct = str(k.control_type or "")
            except Exception:
                continue
            if ct == "TabItem":
                out.append(k)
            elif ct != "Document" and d + 1 < max_tiefe:
                q.append((k, d + 1))
    return out
'''
exec(_TAB_STREIFEN_WALKER, globals())   # definiert _PROPHOS_TAB_MUSTER + tabstreifen_tabs
_PROPHOS_TAB_RE = re.compile(_PROPHOS_TAB_MUSTER)


def tabstreifen_ziel(fenster):
    """REIN RECHNEND (testbar): UIA-Lesung [{hwnd, titel, klasse, tabs: [{name, sel}]}] → (ziel | None, grund). Nur sichtbare Chrome-Hauptfenster
    (Klasse Chrome_WidgetWin_1, Titel „… - Google Chrome“). Ziel nur bei GENAU EINEM Tab „Prophos …“ über alle Fenster, der NICHT vorn ist, und genau
    einem sicher aktiven Tab (sel True) in seinem Fenster: {hwnd, idx, name, vorher_idx, vorher_name}."""
    chrome = [f for f in (fenster or []) if isinstance(f, dict) and f.get("klasse") == "Chrome_WidgetWin_1"
              and str(f.get("titel") or "").endswith("Google Chrome")]
    if not chrome:
        return None, "kein Chrome-Fenster im UIA-Baum"
    treffer = []
    for f in chrome:
        tabs = [t for t in (f.get("tabs") or []) if isinstance(t, dict)]
        for i, t in enumerate(tabs):
            if _PROPHOS_TAB_RE.match(str(t.get("name") or "")):
                treffer.append((f, i, tabs))
    if not treffer:
        return None, "kein Tab „Prophos …“ im Tabstreifen eines Chrome-Fensters (Prophos-Tab zu?)"
    if len(treffer) > 1:
        return None, f"{len(treffer)} Tabs „Prophos …“ in den Tabstreifen — welcher der Haupt-Tab ist, ist per UIA nicht sicher, nichts gedrückt"
    f, i, tabs = treffer[0]
    if f.get("gesperrt") is None or str(f.get("gesperrt")):
        # Prüfer NL2 (SOLLTE): Reader-Profil und Puls-Chrome fasst das Panel nie an (order_bot._fenster_gesperrt); nicht lesbar → auch nicht
        return None, f"Prophos-Tab liegt in einem gesperrten Fenster ({str(f.get('gesperrt') or 'Sperre nicht lesbar')[:40]}) — nichts gedrückt"
    if tabs[i].get("sel") is True:
        return None, "Prophos-Tab ist in seinem Fenster schon vorn — das ist der Fenster-Weg, nichts gedrückt"
    sel = [j for j, t in enumerate(tabs) if t.get("sel") is True]
    if len(sel) != 1:
        return None, "aktiver Tab im Prophos-Fenster nicht eindeutig lesbar — nichts gedrückt"
    try:
        hwnd = int(f.get("hwnd"))
    except (TypeError, ValueError):
        hwnd = 0
    if hwnd <= 0:
        return None, "Fenster-Kennung fehlt — nichts gedrückt"
    return {"hwnd": hwnd, "idx": i, "name": str(tabs[i].get("name") or ""), "vorher_idx": sel[0],
            "vorher_name": str(tabs[sel[0]].get("name") or ""), "anzahl": len(tabs)}, ""


def streifen_weg_noetig(msg_fenster, cdp_erreichbar, pro, schalter=None):
    """REIN RECHNEND (testbar): Tabstreifen-Weg nur, wenn der Fenster-Weg kein Fenster mit aktivem Prophos-Tab fand, :9333 NICHT erreichbar ist (mit
    Puls-Chrome zuständig: CDP-Rückfall bzw. Puls-Wache) und kein Prophos per CDP da ist. schalter = base_config „tab_streifen“ (False = aus)."""
    if schalter is False:
        return False
    return "kein Chrome-Fenster mit aktivem Prophos-Tab" in str(msg_fenster or "") and cdp_erreichbar is False and not pro


_TAB_STREIFEN_HAUPT = r'''
import sys, json, re
def _gesperrt(hwnd):
    try:
        import order_bot
        return str(order_bot._fenster_gesperrt(hwnd) or "")
    except Exception:
        return None
def _sichtbar(hwnd):
    try:
        import ctypes
        return bool(ctypes.windll.user32.IsWindowVisible(int(hwnd)))
    except Exception:
        return True
def _main():
    from pywinauto import Desktop
    from pywinauto.uia_element_info import UIAElementInfo
    from pywinauto.controls.uiawrapper import UIAWrapper
    modus = sys.argv[1]
    if modus == "lesen":
        out = []
        # visible_only=False (Prüfer NL2): sonst fehlen minimierte Fenster (UIA offscreen) — sichtbar prüft IsWindowVisible
        for w in Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1", visible_only=False):
            try:
                info = w.element_info
                titel = str(info.name or "")
                if not titel.endswith("Google Chrome") or not _sichtbar(info.handle):
                    continue
                tabs = []
                for t in tabstreifen_tabs(info):
                    try:
                        sel = bool(UIAWrapper(t).is_selected())
                    except Exception:
                        sel = None
                    tabs.append({"name": str(t.name or "")[:120], "sel": sel})
                out.append({"hwnd": int(info.handle or 0), "titel": titel[:160], "klasse": str(info.class_name or ""), "tabs": tabs,
                            "gesperrt": _gesperrt(info.handle) if any(re.match(_PROPHOS_TAB_MUSTER, x["name"]) for x in tabs) else ""})
            except Exception:
                continue
        print(json.dumps(out))
        return
    if modus in ("waehlen", "zurueck"):
        hwnd, idx = int(sys.argv[2]), int(sys.argv[3])
        tabs = tabstreifen_tabs(UIAElementInfo(hwnd))
        if modus == "waehlen" and (idx >= len(tabs) or str(tabs[idx].name or "")[:120] != sys.argv[4]):
            print(json.dumps({"ok": False, "msg": "Tabstreifen hat sich geändert — nichts gewählt"}))
            return
        # zurueck (Prüfer NL2 MUSS): Titel wie TradingView („MNQ1! 21 034 ▲ …“) wechseln laufend — gleiche Tab-Zahl + derselbe Platz, kein Prophos-Tab
        if modus == "zurueck" and (len(tabs) != int(sys.argv[4]) or idx >= len(tabs) or re.match(_PROPHOS_TAB_MUSTER, str(tabs[idx].name or ""))):
            print(json.dumps({"ok": False, "msg": "Tabstreifen hat sich geändert (Tab-Zahl/Platz) — nichts gewählt"}))
            return
        w = UIAWrapper(tabs[idx])
        try:
            w.select()
            weg = "SelectionItem"
        except Exception:
            try:
                w.invoke()
                weg = "Invoke"
            except Exception as e:
                print(json.dumps({"ok": False, "msg": "Tab nicht wählbar (weder SelectionItem noch Invoke: %s)" % type(e).__name__}))
                return
        print(json.dumps({"ok": True, "weg": weg}))
_main()
'''


def _streifen_lauf(*args, timeout=20):
    """UIA-Teil in einem frischen Prozess (pywinauto/COM nie im Panel-Thread) → letzte JSON-Zeile oder None. Wirft bei Zeitlimit/Startfehler."""
    code = _TAB_STREIFEN_WALKER + _TAB_STREIFEN_HAUPT
    r = subprocess.run([sys.executable, "-c", code, *[str(a) for a in args]], cwd=HERE, capture_output=True, text=True, timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    zeilen = (r.stdout or "").strip().splitlines()
    try:
        return json.loads(zeilen[-1]) if zeilen else None
    except ValueError:
        return None


def _fenster_titel(hwnd):
    import ctypes
    u32 = ctypes.windll.user32
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value or ""


def _tipp_sperre_versuchen():
    """PC-Tipp-Sperre der Echo-Läufe OHNE Warten → ('frei', handle) | ('belegt', None) | ('unbekannt', None). Wirft nie."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.CreateMutexW(None, False, ECHO_TIPP_MUTEX_PANEL)
        if not h:
            return "unbekannt", None
        rc = k32.WaitForSingleObject(h, 0)
        if rc in (0, 0x80):                       # frei bzw. Vorbesitzer tot
            return "frei", h
        k32.CloseHandle(h)
        return ("belegt", None) if rc == 0x102 else ("unbekannt", None)
    except Exception:
        return "unbekannt", None


def _tipp_sperre_frei(h):
    if not h:
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.ReleaseMutex(h)
        k32.CloseHandle(h)
    except Exception:
        pass


def _prophos_tab_neuladen_streifen():
    """NL2 → (ok, Klartext): Prophos-Tab im Tabstreifen des normalen Chrome per UIA wählen, Strg+F5, auf die erste Abfrage warten, vorherigen Tab
    zurück (Block oben). Nur Tasten ins nachweislich vordere Fenster mit Titel „Prophos …“, keine Maus."""
    import ctypes
    u32 = ctypes.windll.user32
    # Prüfer NL2 (SOLLTE): ein einzelnes /json/list mit 2 s ist kein Beweis — antwortet :9333 doch (ausgelastetes Puls-Chrome), ist es zuständig
    try:
        _cdp_get("/json/version", timeout=5.0)
        return False, "Puls-Chrome (:9333) antwortet doch — dort zuständig (CDP/Puls-Wache), nichts gedrückt"
    except Exception:
        pass
    # Lesen VOR den Sperren (Prüfer NL2 KANN: Haltezeit) — gewählt wird unten nur, wenn Name und Platz noch stimmen
    try:
        fenster = _streifen_lauf("lesen")
    except Exception as e:
        return False, f"Tabstreifen per UIA nicht lesbar ({type(e).__name__})"
    if not isinstance(fenster, list):
        return False, "Tabstreifen per UIA nicht lesbar (keine Antwort — pywinauto da?)"
    ziel, grund = tabstreifen_ziel(fenster)
    if not ziel:
        return False, grund
    if not TV_ORDER_LOCK.acquire(blocking=False):
        return False, "Puls läuft gerade im Browser — nächster Versuch später"
    tipp = None
    try:
        if not _browser_und_mt5_frei(tv_eigen=True):
            return False, "MT5-Order/Polar läuft gerade — nächster Versuch später"
        art, tipp = _tipp_sperre_versuchen()
        if art != "frei":   # Prüfer NL2 (KANN): ein Weg, der Tasten drückt, rät nie — „unbekannt“ bricht auch ab
            return False, ("PC-Tipp-Sperre belegt (ein Echo-Lauf tippt gerade)" if art == "belegt" else "PC-Tipp-Sperre nicht lesbar") + \
                " — nichts gedrückt, nächster Versuch später"
        hwnd = ziel["hwnd"]
        vorher_fg = int(u32.GetForegroundWindow() or 0)
        mini = bool(u32.IsIconic(hwnd))
        gewaehlt, ergebnis, zurueck = False, (False, "nichts gedrückt"), ""
        try:
            if mini:
                u32.ShowWindow(ctypes.c_void_p(hwnd), 9)               # SW_RESTORE
                time.sleep(0.3 + random.random() * 0.2)
            if not _fenster_vorn(hwnd):
                ergebnis = (False, "Chrome-Fenster mit dem Prophos-Tab kam nicht nach vorn — nichts gewählt, nichts gedrückt")
            else:
                w1 = _streifen_lauf("waehlen", hwnd, ziel["idx"], ziel["name"])
                if not (isinstance(w1, dict) and w1.get("ok")):
                    ergebnis = (False, str((w1 or {}).get("msg") or "Prophos-Tab nicht gewählt (keine Antwort)") + " — nichts gedrückt")
                else:
                    gewaehlt = True
                    time.sleep(0.4 + random.random() * 0.4)            # Jitter wie Puls
                    titel = _fenster_titel(hwnd)
                    if not _PROPHOS_TAB_RE.match(titel):
                        ergebnis = (False, f"nach dem Wählen steht „{titel[:40]}“ im Fenster statt Prophos — nichts gedrückt")
                    elif int(u32.GetForegroundWindow() or 0) != hwnd and not _fenster_vorn(hwnd):
                        ergebnis = (False, "Fenster verlor den Vordergrund — nichts gedrückt")
                    elif int(u32.GetForegroundWindow() or 0) != hwnd:   # Beweis direkt vor dem Druck
                        ergebnis = (False, "Fenster verlor den Vordergrund — nichts gedrückt")
                    else:
                        u32.keybd_event(0x11, 0, 0, 0)                    # Strg
                        time.sleep(0.04 + random.random() * 0.04)
                        u32.keybd_event(0x74, 0, 0, 0); u32.keybd_event(0x74, 0, 2, 0)   # F5
                        time.sleep(0.04 + random.random() * 0.04)
                        u32.keybd_event(0x11, 0, 2, 0)
                        t0 = time.time()
                        # wie der CDP-Weg: Tab vorn lassen, bis er wieder beim Panel fragt (Beweis), dann erst zurück
                        time.sleep(6 + random.random() * 4)
                        if _TAB_OEFFNEN["zuletzt"] < t0:
                            time.sleep(5 + random.random() * 4)
                        wach = _TAB_OEFFNEN["zuletzt"] >= t0
                        ergebnis = (wach, f"Strg+F5 im Prophos-Tab (per {w1.get('weg') or 'UIA'}), "
                                          f"{'fragt wieder' if wach else 'fragt noch nicht'} ({time.time() - t0:.0f} s)")
        finally:
            if gewaehlt:
                try:
                    w2 = _streifen_lauf("zurueck", hwnd, ziel["vorher_idx"], ziel["anzahl"])
                    zurueck = (f", „{ziel['vorher_name'][:30]}“ wieder vorn" if isinstance(w2, dict) and w2.get("ok")
                               else f", vorheriger Tab NICHT zurück ({str((w2 or {}).get('msg') or 'keine Antwort')[:60]})")
                except Exception as e:
                    zurueck = f", vorheriger Tab NICHT zurück ({type(e).__name__})"
            if mini:
                u32.ShowWindow(ctypes.c_void_p(hwnd), 6)               # SW_MINIMIZE
            if vorher_fg and vorher_fg != hwnd:
                try:
                    _fenster_vorn(vorher_fg)
                except Exception:
                    pass
        return ergebnis[0], ergebnis[1] + zurueck
    except Exception as e:
        return False, f"Tabstreifen-Weg fehlgeschlagen: {type(e).__name__}: {e}"
    finally:
        _tipp_sperre_frei(tipp)
        TV_ORDER_LOCK.release()


def _tab_oeffnen(url=TAB_URL, lock_gehalten=False):
    """Öffnet den Prophos-Tab IM PULS-CHROME (Port 9333) in einem eigenen Fenster, unter der Adresse, die der Tab zuletzt selbst gemeldet
    hat (localhost ≠ 127.0.0.1 = eigener Login), sonst TAB_URL → (ok, Klartext). lock_gehalten = der Aufrufer hält TV_ORDER_LOCK schon.
    PULS-CHROME STATT „chrome.exe --profile-directory" (30.10.2026, Befund C: Ina pc-xc5c52 — der alte Weg öffnete im normalen Chrome des
    Nutzers; auch Stufe 3 der Tab-Heilung schloss den Tab im Puls-Chrome und öffnete ihn dort, wo F1 ihn danach nicht mehr fand). Läuft das
    Puls-Chrome nicht, startet es order_bot._puls_chrome_sicher (minimiert, nie ein zweiter Start). Steht schon ein Prophos-Tab im
    Puls-Chrome, wird keiner geöffnet."""
    import urllib.request
    url = url if (TAB_URL_RE.fullmatch(str(url or "")) or TAB_URL_V_RE.fullmatch(str(url or ""))) else TAB_URL
    try:
        urllib.request.urlopen(url, timeout=5).close()
    except Exception as e:
        return False, f"lokales Backend (localhost:5000) antwortet nicht ({type(e).__name__}) — start-alles.bat"
    if not lock_gehalten and not TV_ORDER_LOCK.acquire(blocking=False):
        return False, "Puls läuft gerade im Browser — nächster Versuch später"
    try:
        if not _browser_und_mt5_frei(tv_eigen=True):
            return False, "MT5-Order läuft gerade — nächster Versuch später"
        # EIGENES FENSTER (30.10.2026, Befund ECHO-AUSSETZER: Prophos als Tab hinter TradingView wurde von Chrome eingefroren/verworfen —
        # der aktive Tab eines eigenen Fensters wird nicht verworfen). Target.createTarget newWindow im Browser-Kanal des Puls-Chrome.
        r = subprocess.run([sys.executable, "-c", _TAB_PULS_OEFFNEN_CODE, url], cwd=HERE, capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            ok, msg = json.loads((r.stdout or "").strip().splitlines()[-1])
        except Exception:
            return False, f"Öffnen im Puls-Chrome ohne Antwort ({(r.stderr or '').strip()[-120:]})"
        if not ok:
            return False, str(msg)
        time.sleep(4 + random.random())   # Lock kurz halten: die neue Seite lädt
        return True, f"{msg} → {url}"
    except Exception as e:
        return False, f"Öffnen fehlgeschlagen: {type(e).__name__}: {e}"
    finally:
        if not lock_gehalten:
            TV_ORDER_LOCK.release()



# ══ SCHLIESSEN AUF DEM PC (Finn 02.11.2026 ~19:10 „Zurück zu den Basics“, /goal: Master-Exit → Fusion zu ≤ 1 s auf allen PCs, egal ob der Prophos-Tab lädt,
# fehlt oder gedrosselt ist; „Puls weiß, in welches Konto er klickt; sobald die Position weg ist, ist Fusion zu“). Vorfall Simon 88b28130: der Puls-Chrome-
# Neustart im TopstepX-Lauf schloss den Prophos-Tab (18:31), der neue Tab kannte die Position nicht → 30-s-Rückfall → 34,5 s.
# SCHARF SCHALTEN: öffnet der Tab einen Fusion-Hedge für einen TradingView-Trade (/api/hedge-solo open mit Feld scharf {ext_id, wurzel, nachbarn}), merkt das
# Panel nach der Quittung {plan_id, ticket, ext_id, wurzel, nachbarn} in hedge_scharf.json (überlebt Tab- und Panel-Neustart).
# SCHLIESS-WACHE (Thread, 0,1 s): liest den Reader-Stand (127.0.0.1:8790, dieselbe Quelle wie der Tab). Im scharfen Konto (voller Text = External ID, oder
# gekürzt/angeklebt und unter den Konten der ID eindeutig — sonst nie) Position der Wurzel gesehen → danach flach + Exit-Fill der Gegenseite (seit 03.11.2026,
# Vorfall Marc e72df7a0: nur mit Fill, flach allein nie) → close-Auftrag an den Copier (hedge_solo_auftrag.json, wie /api/hedge-solo). Fail-safe: Konto nicht sicher, Stand blind/alt, Userscript < 0.10.8
# oder Position nie gesehen → nichts, der bestehende Weg im Tab greift. Der Tab bucht weiter und darf selbst schließen (doppelt: Copier antwortet schon_zu).
# Gelöst wird ein Eintrag beim Close des Tabs (/api/hedge-solo close mit dem Ticket), nach dem eigenen Close (ok/schon_zu) oder nach 12 h.
# Ort Panel statt reader-server: das Panel läuft dauerhaft, schreibt ohnehin die Copier-Aufträge und hält die Puls-Locks. ══
SCHARF_PFAD = os.path.join(HERE, "hedge_scharf.json")
SCHARF_LOCK = threading.Lock()
SCHARF_TAKT_S = 0.1          # Grundtakt bei offenem scharfem Eintrag
SCHARF_TAKT_FLACH_S = 0.05   # Eingang 02.11.2026 (Jacob 98c946a0 ≈ 1,0 s; S9-Hinweis Last): 0,05 s nur ab der ersten flachen Lesung bis zur Entscheidung
SCHARF_FILL_FRISCH_S = 3.0   # Exit-Fill zählt, wenn er höchstens so alt ist
SCHARF_FLACH_S = 0.3
SCHARF_FLACH_LESUNGEN = 2
SCHARF_OFFEN_MIN_S = 3.0
SCHARF_STAND_MAX_S = 1.0
SCHARF_MAX_S = 3 * 3600   # S9: 2–4 h statt 12 h — ein liegengebliebener Eintrag hält sonst „kein Neustart“ den halben Tag
# BIG TRADES ÜBER 3 H (Eingang 03.11.2026, Belege Finn + Pascal b167a248 Tradeify …3495 pc-2zc2we 5,5 h, Ina 8e1a558f …8820 pc-xc5c52 4,2 h, dazu 1f30fe17/
# 18253d21/4a2532e2/726c6895 3,6–4,5 h: alle schloss der Tab nach seiner 1-s-Regel, 2–3 s ab Toast, 726c6895 32 s; alle Hedges unter 3 h schloss das Panel, 0,84–0,87 s):
# nach SCHARF_MAX_S fiel der Eintrag als „abgelaufen“ weg, obwohl der Hedge offen war. Jetzt gilt SCHARF_MAX_S nur, solange der Copier das Ticket nicht frisch als
# offen meldet; mit Copier-Beleg (≤ SCHARF_COPIER_BELEG_S alt) bleibt der Eintrag bis SCHARF_MAX_HART_S (eine Futures-Session). Liegengebliebene Einträge räumt
# weiter „im Copier nicht mehr offen“ ab; ohne Copier-Beleg (Copier aus) bleibt es bei 3 h — „kein Neustart“ hängt so nie länger an einem toten Eintrag.
SCHARF_MAX_HART_S = 23 * 3600
SCHARF_COPIER_BELEG_S = 120.0
SCHARF_COPIER_BELEG_NEU_S = 60.0   # Beleg höchstens 1×/min in die Datei schreiben (kein Schreiben je Takt)
SCHARF_COPIER_KARENZ_S = 30   # so lange nach dem Open zählt ein fehlendes Ticket in der Copier-Liste noch nicht (Status-Takt)
SCHARF_CLOSE_WIEDER_S = 2.0
SCHARF_KONTO_KURZ_MIN = 12
SCHARF_NACHBARN_MAX = 500
SCHARF_MIN_VERSION = (0, 10, 8)
READER_STAND_URL = "http://127.0.0.1:8790/"
# SPUR AUF PLATTE (Eingang 02.11.2026, Test Chris a6f5c630: die Panel-Konsole ist fernab nicht lesbar): jede Entscheidung der Schließ-Wache als Zeile in
# scharf_spur.log (Datum Dubai-Zeit, Ticket, Ereignis, Grund) — Setzen, Lösen, Close, und jeder Wechsel des Entscheidungs-Grunds je Ticket (kein Takt-Spam).
# Höchstens SCHARF_SPUR_MAX Zeilen, ältere fallen vorne weg.
SCHARF_SPUR_PFAD = os.path.join(HERE, "scharf_spur.log")
SCHARF_SPUR_MAX = 2000
SCHARF_SPUR_KUERZEN_JE = 200       # nur alle N Zeilen auf SCHARF_SPUR_MAX kürzen (S9 02.11.2026: vorher ganze Datei je Zeile, bis 10 Rewrites/s)
SCHARF_SPUR_LAGE_MIN_S = 1.0       # Lage-Zeile je Ticket höchstens 1×/s, auch wenn der Grund flackert
SCHARF_SPUR_LOCK = threading.Lock()   # Handler-Thread (/api/hedge-solo, /api/hedge-scharf) und Wache schreiben in dieselbe Datei
_SCHARF_SPUR_LETZT = {}   # ticket → (letzter Grund, Zeit)
_SCHARF_SPUR_N = [0]


def scharf_spur(ticket, ereignis, grund="", nur_bei_wechsel=False):
    """Eine Zeile an scharf_spur.log anhängen; nur_bei_wechsel: nur bei neuem Grund für dieses Ticket und höchstens 1×/s. Wirft nie."""
    try:
        with SCHARF_SPUR_LOCK:
            if nur_bei_wechsel:
                alt = _SCHARF_SPUR_LETZT.get(ticket)
                jetzt = time.time()
                if alt and (alt[0] == grund or jetzt - alt[1] < SCHARF_SPUR_LAGE_MIN_S):
                    return
                _SCHARF_SPUR_LETZT[ticket] = (grund, jetzt)
            zeit = datetime.utcfromtimestamp(time.time() + 4 * 3600).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with open(SCHARF_SPUR_PFAD, "a", encoding="utf-8") as f:
                f.write(f"{zeit} Dubai · Ticket {ticket} · {ereignis}" + (f" · {grund}" if grund else "") + "\n")
            _SCHARF_SPUR_N[0] += 1
            if _SCHARF_SPUR_N[0] % SCHARF_SPUR_KUERZEN_JE == 0:
                with open(SCHARF_SPUR_PFAD, "r", encoding="utf-8", errors="replace") as f:
                    zeilen = f.read().splitlines()
                if len(zeilen) > SCHARF_SPUR_MAX:
                    with open(SCHARF_SPUR_PFAD + ".tmp", "w", encoding="utf-8") as f:
                        f.write("\n".join(zeilen[-SCHARF_SPUR_MAX:]) + "\n")
                    os.replace(SCHARF_SPUR_PFAD + ".tmp", SCHARF_SPUR_PFAD)
    except Exception:
        pass


def scharf_konto_bezug(text, ext):
    """REIN RECHNEND (testbar, wie kontoTextBezug im Tab): 'ja' | 'kurz' | 'klebt' | ''."""
    eid = str(ext or "").strip().upper()
    t = str(text or "").strip().upper()
    if not eid or not t:
        return ""
    if t == eid or eid in re.split(r"[^A-Z0-9]+", t):
        return "ja"
    w = (re.split(r"[^A-Z0-9]+", t) or [""])[0]
    if len(w) >= SCHARF_KONTO_KURZ_MIN and len(w) < len(eid) and eid.startswith(w):
        return "kurz"
    if len(w) > len(eid) and w.startswith(eid) and re.fullmatch(r"\d{1,3}", w[len(eid):]):
        return "klebt"
    return ""


# PULS-BELEG (02.11.2026, Chris pc-c19p2l a6f5c630 Apex …0007: Reader „PAAPEX668794000000“ passt auf alle 7 Apex-Konten der ID — das Panel war scharf, traute
# dem gekürzten Text aber nie, der Tab schloss nach 31 s): „Puls weiß, in welches Konto er klickt“ (Finn). Jeder TradingView-Lauf von Puls (tv-konto, tv-lesen,
# tv-close, tv-konten-liste, tv-order) setzt den Beleg neu — volle Kennung aus res.konto_aktiv (order_bot meldet sie nur nach bewiesenem Listen-Klick, .1752),
# sonst leer. Ein gekürzter, mehrdeutiger Text gilt als das scharfe Konto nur, wenn der LETZTE Puls-Lauf genau dieses Konto bewiesen hat.
_PULS_BELEG = {"text": "", "at": 0.0}


def puls_beleg_merken(res):
    """Nach jedem TradingView-Lauf von Puls: Beleg = volle Kennung des bewiesen gewählten Kontos, sonst leer (der Lauf kann gewechselt haben)."""
    k = str((res or {}).get("konto_aktiv") or "").strip() if isinstance(res, dict) and res.get("ok") else ""
    _PULS_BELEG.update(text=k if (k and "…" not in k and len(re.sub(r"[^A-Za-z0-9]", "", k)) >= 10) else "", at=time.time())
    if scharf_laden():
        scharf_spur("-", "Puls-Beleg", _PULS_BELEG["text"] or "leer (Konto des Laufs nicht bewiesen)")


def puls_beleg_gueltig(beleg_at, jetzt, idle_s):
    """REIN RECHNEND (testbar, S9 02.11.2026): gilt der Puls-Beleg noch? Nur, wenn seit dem Beleg keine Eingabe am PC war (Puls' eigene Klicks liegen
    vor dem Merken) — jede Hand-/Parsec-Eingabe danach kann ins Geschwister-Konto gewechselt haben, dann schließt nur der Tab. idle_s None → ungültig."""
    if not beleg_at or idle_s is None:
        return False
    return float(idle_s) >= float(jetzt) - float(beleg_at)


def scharf_konto_kern(text, ext=None):
    """REIN RECHNEND (S9 zu 9e4f53e8, 03.11.2026): Kennung des Reader-Kontotexts ohne Balance/Zusatz — erstes Wort aus A–Z/0–9, groß.
    KLEBENDE BALANCE (03.11.2026, Lotse L1: Finn+Pascal 43c68171 Tradeify …1362, Reader „FTDFYSLX150889401362162“ → „…166“ binnen 40 s, Panel meldete
    „Reader-Konto gewechselt“, der Tab schloss nach 3,2 s): das Userscript (kontoNummerAmSchalter) nimmt alle Leerzeichen raus, „…1362 162,431.20 USD“
    wird „…1362162“ — die erste Tausendergruppe der Balance klebt an der Kennung. Klebt sie an ext (scharf_konto_bezug „klebt“, 1–3 Ziffern), ist der
    Kern ext selbst; ein echter Kontowechsel bleibt ein anderer Kern."""
    k = (re.split(r"[^A-Z0-9]+", str(text or "").strip().upper()) or [""])[0]
    eid = str(ext or "").strip().upper()
    return eid if (eid and scharf_konto_bezug(k, eid) == "klebt") else k


def scharf_fill_konto_ok(text, ext, nachbarn, gekappt=False):
    """REIN RECHNEND (testbar, 03.11.2026, Lotse L1: alle 5 Big Trades 17:26–17:30 Dubai, Fill „FTDFYSLX150306272833161“ gegen ext „FTDFYSLX150306272833“
    → „klebt“, seit .2013 verworfen, geschlossen hat jedes Mal der Tab): zählt das Konto eines Exit-Fills für GENAU dieses Konto? Voller Text („ja“) oder
    angeklebte Balance („klebt“: ext + 1–3 Ziffern, s. scharf_konto_kern) — und kein anderes Konto der ID (nachbarn) passt auf denselben Text, weder voll
    noch angeklebt noch gekürzt (z. B. kürzeres Nachbarkonto + Balance-Ziffern = derselbe Text). „klebt“ nur mit bekannten Nachbarn. Gekürzt oder per
    Puls-Beleg nie (S9 zu 9e4f53e8: fill.konto ist das vorgewählte Konto, im Marc-Fenster sähe sonst eine Gegen-Order des Nachbarn wie der Exit aus).
    Nachbarn ohne Trennzeichen verglichen (TradingView zeigt die Kennung ohne „-“/Leerzeichen); gekappte Nachbarliste → „klebt“ nie."""
    b = scharf_konto_bezug(text, ext)
    if b not in ("ja", "klebt"):
        return False
    eid = str(ext or "").strip().upper()
    andere = [k for k in (re.sub(r"[^A-Z0-9]", "", str(n or "").upper()) for n in (nachbarn or ())) if k not in ("", eid)]
    if b == "klebt" and (not andere or gekappt):
        return False
    return not any(scharf_konto_bezug(text, n) for n in andere)


def scharf_konto_sicher(text, ext, nachbarn, beleg=None):
    """REIN RECHNEND (testbar): steht der Reader sicher im scharfen Konto? Voller Text immer; gekürzt/angeklebt, wenn kein anderes Konto der ID
    (nachbarn = External IDs) im selben Bezug steht, oder — Apex-Falle, alle beginnen gleich — wenn der letzte Puls-Lauf genau dieses Konto bewiesen gewählt
    hat (beleg = volle Kennung aus PULS-BELEG). Sonst nie (dann schließt nur der Tab)."""
    b = scharf_konto_bezug(text, ext)
    if b == "ja":
        return True
    if not b:
        return False
    eid = str(ext or "").strip().upper()
    if not any(scharf_konto_bezug(text, n) for n in (nachbarn or ()) if str(n or "").strip().upper() not in ("", eid)):
        return True
    return bool(beleg) and scharf_konto_bezug(beleg, ext) == "ja"


def _scharf_version_ok(st):
    v = str((st or {}).get("script_version") or (st or {}).get("version") or "")
    try:
        return tuple(int(x) for x in v.split(".")[:3]) >= SCHARF_MIN_VERSION
    except ValueError:
        return False


def _scharf_wurzel_da(st, wurzel):
    w = str(wurzel or "").upper()
    for x in (st or {}).get("positionen") or ():
        if not isinstance(x, dict):
            continue
        xw = str(x.get("wurzel") or "").upper()
        if not xw:
            sym = str(x.get("symbol") or "").upper()
            xw = "MNQ" if sym.startswith("MNQ") else "NQ" if sym.startswith("NQ") else ""
        if xw == w:
            return True
    return False


def scharf_exit_fill(e, st, jetzt, beleg=None):
    """REIN RECHNEND (testbar, Eingang 02.11.2026 „Nachschärfen“): ein Exit-Fill im Reader-Stand (fills, Userscript ≥ 0.10.2 im Puls-Chrome) für diesen
    Eintrag? Gegenseite der Plan-Richtung, volle Plan-Menge, Wurzel passt (wenn die Meldung ein Symbol trägt), Konto des Fills genau das des Plans
    (scharf_fill_konto_ok: voll oder angeklebte Balance, eindeutig unter den Konten der ID, nie per Beleg), frisch (≤ SCHARF_FILL_FRISCH_S) und nach dem Open. Ohne richtung/menge am Eintrag (alter Tab) → nie. → Fill | None"""
    r, menge = str(e.get("richtung") or ""), e.get("menge")
    if r not in ("buy", "sell") or not isinstance(menge, (int, float)) or menge <= 0:
        return None
    gegen = "sell" if r == "buy" else "buy"
    for f in reversed((st or {}).get("fills") or []):
        if not isinstance(f, dict) or f.get("seite") != gegen:
            continue
        try:
            at_s = float(f.get("at")) / 1000.0
            mf = float(f.get("menge"))
        except (TypeError, ValueError):
            continue
        if abs(mf - float(menge)) > 1e-9 or not (jetzt - SCHARF_FILL_FRISCH_S <= at_s <= jetzt + 1.0) or at_s <= float(e.get("at") or 0):
            continue
        sym = str(f.get("symbol") or "").upper()
        if sym:
            fw = "MNQ" if sym.startswith("MNQ") else "NQ" if sym.startswith("NQ") else ""
            if fw != str(e.get("wurzel") or "").upper():
                continue
        if not str(f.get("tab_id") or "").startswith("puls-"):
            continue
        # S9 zu 9e4f53e8 (03.11.2026): fill.konto ist das vorgewählte Konto (kontoMerk), nicht das aus der Meldung — nur der VOLLE Kontotext zählt,
        # gekürzt oder per Puls-Beleg nie (sonst sähe im Marc-Fenster eine volle Gegen-Order eines Nachbarkontos wie der Exit aus). Seit Lotse L1 (03.11.2026)
        # zählt auch die angeklebte Balance, aber nur eindeutig unter den Konten der ID (scharf_fill_konto_ok)
        if not scharf_fill_konto_ok(f.get("konto"), e.get("ext_id"), e.get("nachbarn"), e.get("nachbarn_gekappt") is True):
            continue
        return f
    return None


def scharf_entscheid(e, st, jetzt, beleg=None):
    """REIN RECHNEND (testbar): ein scharfer Eintrag + Reader-Stand → (zu: bool, e_neu, grund). e: {at, ext_id, wurzel, nachbarn, gesehen,
    flach_seit, flach_ts[]}. Jede unsichere Lesung setzt die Flach-Strecke zurück, ein Kontowechsel auch „gesehen“ (muss im Konto neu gesehen werden)."""
    e = dict(e)
    st = st if isinstance(st, dict) else {}
    konto_ok = scharf_konto_sicher(st.get("konto"), e.get("ext_id"), e.get("nachbarn"), beleg)
    alter = st.get("alter_s")
    # S9 02.11.2026: nur der Positions-Tab im Puls-Chrome zählt (ein TradingView im normalen Chrome mit demselben Konto nie)
    frisch = (st.get("an") is not False and st.get("positionen_ok") is True and not st.get("blind") and isinstance(alter, (int, float))
              and alter <= SCHARF_STAND_MAX_S and isinstance(st.get("positionen"), list) and _scharf_version_ok(st)
              and str(st.get("positionen_tab") or "").startswith("puls-"))
    if not konto_ok:
        e.update(gesehen=False, flach_seit=None, flach_ts=[])
        return False, e, "Konto nicht sicher"
    if not frisch:
        e.update(flach_seit=None, flach_ts=[])
        return False, e, "Stand nicht frisch"
    if _scharf_wurzel_da(st, e.get("wurzel")):
        e.update(gesehen=True, flach_seit=None, flach_ts=[], konto_gesehen=scharf_konto_kern(st.get("konto"), e.get("ext_id")))
        return False, e, "Position da"
    if not e.get("gesehen"):
        return False, e, "Position im Konto nie gesehen"
    # S9 zu 9e4f53e8 (03.11.2026): nur POSITIVER Leer-Beweis zählt (True), fehlend/unbekannt wie False — sonst entscheidet der Tab
    if st.get("leer_beweis") is not True:
        e.update(flach_seit=None, flach_ts=[])
        return False, e, "flach ohne Leer-Beweis"
    # S9 zu 9e4f53e8: Reader-Konto seit der letzten „Position da“-Lesung unverändert (Kennung ohne Balance); ein Wechsel dazwischen → nie
    if e.get("konto_gesehen") is not None and scharf_konto_kern(st.get("konto"), e.get("ext_id")) != e.get("konto_gesehen"):
        e.update(gesehen=False, flach_seit=None, flach_ts=[])
        return False, e, "Reader-Konto seit „Position da“ gewechselt"
    ts = st.get("positionen_ts") or st.get("ts")
    lesungen = list(e.get("flach_ts") or [])
    if ts not in lesungen:
        lesungen.append(ts)
    e.update(flach_seit=e.get("flach_seit") or jetzt, flach_ts=lesungen[-5:])
    if jetzt - float(e.get("at") or 0) < SCHARF_OFFEN_MIN_S:
        return False, e, "Hedge jünger als 3 s"
    # EXIT-FILL (Eingang 02.11.2026): passender Toast der Gegenseite im sicheren Konto → schon bei der ERSTEN flachen Lesung (spart 0,3–0,35 s)
    fill = scharf_exit_fill(e, st, jetzt, beleg)
    if fill:
        return True, e, (f"Master weg im Konto {e.get('ext_id')} (erste flache Lesung + Exit-Fill {fill.get('seite')} {fill.get('menge')} @ {fill.get('preis')}, "
                         f"{jetzt - float(fill.get('at')) / 1000.0:.2f} s alt)")
    # NUR MIT BEWEIS (Eingang 03.11.2026, Vorfall Marc e72df7a0 Tradeify 150k …5998 pc-7ftp5l: SELL 3 NQ ab 28.252,75, TP 27.997,75, kein SL; Fusion-Ticket
    # 244489604 um 10:11:27Z per Copier-Auftrag „PXsoloc“ zu, ohne Tab-Close (close_at leer, kein master_exit), Kurs 28.246,75 weit vor dem TP — der Master lief
    # ~2 h ohne Hedge, bis „Buy 3 at 28,158.00“). Seit .2011 bleibt der Eintrag über 3 h scharf (Hedge war 10,75 h offen); flache Lesungen allein (Konto-/
    # Login-Wechsel, Tradovate-Abriss: Tabelle leer, Kontotext noch der alte) reichten für den Close. Ab jetzt schließt das Panel NUR mit dem Exit-Fill der
    # Gegenseite in voller Menge im sicheren Konto (oben); flach ohne Fill → nichts, der Tab entscheidet mit seinen Regeln (Wächter, Level, 1-s/30-s).
    if len(lesungen) >= SCHARF_FLACH_LESUNGEN and jetzt - e["flach_seit"] >= SCHARF_FLACH_S:
        return False, e, "flach ohne Exit-Fill — kein Beweis, der Tab entscheidet"
    return False, e, "flach, noch nicht bestätigt"



# ══ ZWEITER SCHLIESSWEG FÜR TOPSTEP / NOVA (NV3, Finn 10.11.2026: „Das Auge erkennt es ja. Sobald das Auge erkennt, direkt schließen.“; Master: „Den zweiten Weg
# über Railway/Panel als Netz baust du trotzdem“). Zwei Fälle auf dem PC von Marco (pc-t8wg97): 937e9256 (Fusion blieb bis zum Hand-Ende offen) und 3d0c3e06 (Fusion
# 71,9 s nach dem Flach des Auges) — beide Male sah das TopstepX-Auge den Master flach, nur der Tab schloss nicht. Der Tab meldet seinen tsv2-Hedge jetzt wie Orbit
# scharf (quelle „tsx“), und diese Wache liest das Auge direkt aus dem Speicher des Panels (tsx_stand_ausgabe, ohne HTTP, gleiche PC-Uhr wie st.ts). Sie ist das
# Netz hinter dem Tab (der schließt nach ~0,25 s), deshalb etwas strenger: Auge ≥ 0.3.1, genau ein TopstepX-Tab, Stand ≤ 3 s, Messung ≤ 2,5 s, nicht ausgeloggt,
# Kontoliste zu, genau das Plan-Konto (tsxKontoPasst des Tabs), Master im Plan-Konto gesehen (Panel selbst oder Tab: Sichtung/Fill-Beleg), danach flach_folge ≥ 3,
# flach seit ≥ 2 s, ≥ 3 eigene flache Messungen, Hedge ≥ 3 s offen. Kein Exit-Fill nötig (anders als TradingView, Vorfall e72df7a0): Finns Vorgabe „Auge flach =
# zu“, das Auge meldet flach nur mit Beweis im gezeigten Konto. Kein Puls-Riegel. Schließen, Wiederholen und Lösen wie bei Orbit (Ticket einmal, cmd_id).
SCHARF_TSX_STAND_MAX_S = 3.0
SCHARF_TSX_MESSUNG_MAX_S = 2.5
SCHARF_TSX_FLACH_S = 2.0
SCHARF_TSX_FLACH_FOLGE = 3
SCHARF_TSX_LESUNGEN = 3
SCHARF_TSX_MIN_SCRIPT = (0, 3, 1)
SCHARF_TSX_SICHT_NEU_S = 5.0   # Sichtungszeit (gesehen_ts) höchstens so oft neu → Datei höchstens alle 5 s geschrieben, solange der Master steht


def _tsx_norm(s):
    return re.sub(r"[^A-Za-z0-9]", "", str(s or "")).upper()


def scharf_tsx_konto_passt(k, ext, ext_ids):
    """REIN RECHNEND (testbar) — wie tsxKontoPasst im Tab: volle, nicht gekürzte Kennung gleich der External ID, sonst die Kopf-Endung (…1234), wenn genau ein
    TopstepX-Konto der ID so endet und es das Plan-Konto ist. Offene Kontoliste nie."""
    if not isinstance(k, dict) or k.get("liste_offen") or not _tsx_norm(ext):
        return False
    if k.get("kontonr"):
        return k.get("abgekuerzt") is False and _tsx_norm(k.get("kontonr")) == _tsx_norm(ext)
    e = str(k.get("endung") or "")
    if not re.fullmatch(r"\d{4}", e):
        m = re.search(r"\(\s*(?:\.{3}|…)\s*(\d{4})\s*\)", str(k.get("aktiv") or ""))
        e = m.group(1) if m else ""
    if not e:
        return False
    treffer = {_tsx_norm(x) for x in (ext_ids or []) if _tsx_norm(x).endswith(e)}
    return len(treffer) == 1 and next(iter(treffer)) == _tsx_norm(ext)


def _tsx_wurzel(sym):
    """REIN RECHNEND — wie tvSymbolWurzel im Tab (MNQZ6 → MNQ, CME_MINI:NQZ2026 → NQ, MNQ1! → MNQ)."""
    s = str(sym or "").upper().strip()
    s = s[s.rfind(":") + 1:].lstrip("/")
    m = re.match(r"[A-Z]+", s)
    if not m:
        return ""
    w, rest = m.group(0), s[len(m.group(0)):]
    if re.match(r"\d+!", rest):
        return w
    if re.match(r"\d", rest) and len(w) > 1 and w[-1] in "FGHJKMNQUVXZ":
        w = w[:-1]
    return w


def _tsx_position_da(st, wurzel, richtung):
    for x in (st.get("positionen") or []) if isinstance(st, dict) else []:
        if not isinstance(x, dict) or not x.get("symbol") or not isinstance(x.get("menge"), (int, float)) or not abs(x.get("menge")):
            continue
        seite = x.get("seite") if x.get("seite") in ("buy", "sell") else None
        if _tsx_wurzel(x.get("symbol")) == wurzel and (not richtung or not seite or seite == richtung):
            return True
    return False


def _tsx_script_ok(v):
    try:
        return tuple(int(x) for x in str(v or "").split(".")[:3]) >= SCHARF_TSX_MIN_SCRIPT
    except ValueError:
        return False


def scharf_entscheid_tsx(e, aus, jetzt):
    """REIN RECHNEND (testbar): scharfer Topstep-Eintrag + tsx_stand_ausgabe() → (zu, e_neu, grund). e: {at, ext_id, wurzel, richtung, nachbarn, gesehen,
    gesehen_ts, flach_ts[]}. Jede unsichere Lesung setzt die eigenen flachen Messungen zurück; die Sichtung bleibt (Schutz 2 wie im Tab)."""
    e = dict(e)
    aus = aus if isinstance(aus, dict) else {}
    st = aus.get("stand") if isinstance(aus.get("stand"), dict) else None

    def nein(grund, **neu):
        e.update(flach_ts=[], **neu)
        return False, e, grund
    if not aus.get("ok") or st is None:
        return nein("kein Stand vom TopstepX-Auge")
    alter = aus.get("alter_s")
    if not isinstance(alter, (int, float)) or alter > SCHARF_TSX_STAND_MAX_S:
        return nein("Auge-Stand zu alt")
    if int(aus.get("tabs") or 0) != 1:
        return nein("mehrere TopstepX-Tabs melden")
    if not _tsx_script_ok(aus.get("script")):
        return nein("Auge älter als 0.3.1 (keine Flach-Folge)")
    if st.get("ausgeloggt") is True:
        return nein("TopstepX ausgeloggt")
    if not scharf_tsx_konto_passt(st.get("konto"), e.get("ext_id"), e.get("nachbarn")):
        return nein("Auge zeigt nicht das Plan-Konto")
    ts = st.get("ts")
    if not isinstance(ts, (int, float)) or jetzt * 1000.0 - ts > SCHARF_TSX_MESSUNG_MAX_S * 1000.0:
        return nein("Messung des Auges nicht frisch")
    if _tsx_position_da(st, e.get("wurzel"), e.get("richtung")):
        # Sichtungszeit höchstens alle SCHARF_TSX_SICHT_NEU_S neu (Prüfer SOLLTE 1: sonst schreibt die Wache hedge_scharf.json bei jeder Messung, die ganze Nova lang)
        g0 = e.get("gesehen_ts")
        if e.get("gesehen") and isinstance(g0, (int, float)) and 0 <= ts - g0 < SCHARF_TSX_SICHT_NEU_S * 1000.0 and not e.get("flach_ts"):
            return False, e, "Position da"
        return nein("Position da", gesehen=True, gesehen_ts=ts)
    if st.get("flach") is not True:
        return nein("keine flach-Aussage")
    if not e.get("gesehen"):
        return nein("Master im Plan-Konto nie gesehen und kein Fill-Beleg")
    fs, folge = st.get("flach_seit"), st.get("flach_folge")
    # die Flach-Serie muss NACH der letzten Sichtung beginnen (bzw. nach dem Hedge-Open − 5 s, wenn nur der Tab den Master sah) — nie ein alter Flach-Stand
    grenze = float(e.get("gesehen_ts")) if isinstance(e.get("gesehen_ts"), (int, float)) else (float(e.get("at") or 0) - 5.0) * 1000.0
    if not isinstance(fs, (int, float)) or fs <= grenze:
        return nein("Flach-Serie älter als die Sichtung")
    lesungen = list(e.get("flach_ts") or [])
    if ts not in lesungen:
        lesungen.append(ts)
    e.update(flach_ts=lesungen[-5:])
    if not isinstance(folge, (int, float)) or folge < SCHARF_TSX_FLACH_FOLGE:
        return False, e, "flach, Folge zu kurz"
    if jetzt * 1000.0 - fs < SCHARF_TSX_FLACH_S * 1000.0:
        return False, e, "flach, noch keine 2 s"
    if len(lesungen) < SCHARF_TSX_LESUNGEN:
        return False, e, "flach, zu wenige eigene Messungen"
    if jetzt - float(e.get("at") or 0) < SCHARF_OFFEN_MIN_S:
        return False, e, "Hedge jünger als 3 s"
    return True, e, (f"Master weg laut TopstepX-Auge im Konto {e.get('ext_id')} (flach seit {(jetzt * 1000.0 - fs) / 1000.0:.1f} s, Folge {int(folge)}, "
                     f"{len(lesungen)} eigene Messungen)")


def scharf_laden():
    l = read_json(SCHARF_PFAD, []) or []
    return [x for x in l if isinstance(x, dict) and x.get("ticket")] if isinstance(l, list) else []


def scharf_speichern(liste):
    tmp = SCHARF_PFAD + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SCHARF_PFAD)


def scharf_puls_reader_ok(st):
    """REIN RECHNEND (testbar, S9 02.11.2026): meldet ein Reader-Tab im Puls-Chrome (tab_id „puls-…“) Userscript ≥ 0.10.8? Sonst wäre der Eintrag nutzlos."""
    for t in ((st or {}).get("tabs") or ()):
        if isinstance(t, dict) and str(t.get("tab_id") or "").startswith("puls-") and _scharf_version_ok({"version": t.get("version")}):
            return True
    return False


def scharf_setzen(sch, plan_id, ticket, reader_stand=None):
    """Nach der Open-Quittung: Eintrag anlegen (gleiches Ticket ersetzt). sch = body.scharf vom Tab. → True, wenn gemerkt."""
    if not isinstance(sch, dict):
        return False
    tsx = sch.get("quelle") == "tsx"   # NV3: Topstep — die Wache liest das TopstepX-Auge im Panel-Speicher, kein TradingView-Reader nötig
    if not tsx and not scharf_puls_reader_ok(reader_stand):
        print(f"[scharf] nicht gemerkt (Ticket {ticket}): kein Puls-Chrome-Reader ≥ 0.10.8", flush=True)
        scharf_spur(ticket, "NICHT gemerkt", "kein Puls-Chrome-Reader ≥ 0.10.8")
        return False
    ext = str(sch.get("ext_id") or "").strip()[:60]
    wurzel = str(sch.get("wurzel") or "").strip().upper()
    if len(re.sub(r"[^A-Za-z0-9]", "", ext)) < 5 or wurzel not in ("NQ", "MNQ") or not int(ticket or 0) > 0:
        scharf_spur(ticket, "NICHT gemerkt", f"Daten unvollständig (Konto {ext or '?'}, Wurzel {wurzel or '?'})")
        return False
    nb = sch.get("nachbarn")
    r = str(sch.get("richtung") or "").strip().lower()
    try:
        menge = float(sch.get("menge")) if sch.get("menge") is not None else None
    except (TypeError, ValueError):
        menge = None
    e = {"plan_id": str(plan_id or "")[:64], "ticket": int(ticket), "ext_id": ext, "wurzel": wurzel,
         "richtung": r if r in ("buy", "sell") else None, "menge": menge if (menge and menge > 0) else None,
         # S6-Gegenprüfung X1 (03.11.2026): vorher [:80] — Pascal/Finn+Pascal standen genau auf „80 Konten der ID“ (gekappt, Tradeify-Resets wachsen);
         # für die angeklebte Balance muss die Liste vollständig sein → höher kappen und Kappung merken (dann zählt nur der volle Text)
         "nachbarn": [str(x).strip()[:60] for x in nb][:SCHARF_NACHBARN_MAX] if isinstance(nb, list) else [],
         "nachbarn_gekappt": isinstance(nb, list) and len(nb) > SCHARF_NACHBARN_MAX, "at": time.time(),
         "gesehen": bool(tsx and sch.get("gesehen") is True), "flach_seit": None, "flach_ts": [], "status": "offen"}
    if tsx:
        e["quelle"] = "tsx"
    with SCHARF_LOCK:
        liste = [x for x in scharf_laden() if int(x.get("ticket") or 0) != int(ticket)]
        liste.append(e)
        scharf_speichern(liste)
    print(f"[scharf] gemerkt: Plan {e['plan_id'][:8]} Ticket {ticket} Konto {ext} {wurzel}{' (TopstepX-Auge)' if tsx else ''}", flush=True)
    scharf_spur(ticket, "gemerkt", f"Plan {e['plan_id'][:8]} · Konto {ext} · {wurzel} · {len(e['nachbarn'])} Konten der ID")
    return True


def scharf_loesen(ticket, grund):
    with SCHARF_LOCK:
        liste = scharf_laden()
        neu = [x for x in liste if int(x.get("ticket") or 0) != int(ticket or 0)]
        if len(neu) != len(liste):
            scharf_speichern(neu)
            print(f"[scharf] gelöst: Ticket {ticket} ({grund})", flush=True)
            scharf_spur(ticket, "gelöst", grund)


def scharf_lebt(e, jetzt):
    """REIN RECHNEND (testbar, 03.11.2026 Big Trades > 3 h): gilt der Eintrag noch? Unter SCHARF_MAX_S immer; danach nur mit frischem Copier-Beleg
    (copier_offen_at ≤ SCHARF_COPIER_BELEG_S alt) und unter SCHARF_MAX_HART_S."""
    alter = jetzt - float(e.get("at") or 0)
    if alter < SCHARF_MAX_S:
        return True
    try:
        beleg = float(e.get("copier_offen_at") or 0)
    except (TypeError, ValueError):
        beleg = 0.0
    return alter < SCHARF_MAX_HART_S and beleg > 0 and jetzt - beleg <= SCHARF_COPIER_BELEG_S


def scharf_konto_fest():
    """Offene scharfe Einträge → [ext_id] (für „kein Puls-Chrome-Neustart bei offenem TV-Trade mit Hedge“)."""
    jetzt = time.time()
    return [str(x.get("ext_id")) for x in scharf_laden() if scharf_lebt(x, jetzt) and x.get("quelle") != "tsx"]   # NV3: Topstep-Einträge ändern hier nichts


def _scharf_close_senden(e):
    auftrag = {"cmd_id": f"{int(time.time())}-{random.randrange(10**6):06d}", "at": time.time(), "aktion": "close",
               "ticket": int(e["ticket"]), "grund": "master_ende_panel"}
    pfad = os.path.join(HERE, "hedge_solo_auftrag.json")
    with HEDGE_SOLO_LOCK:
        liste = read_json(pfad, []) or []
        liste = [a for a in liste if isinstance(a, dict) and (time.time() - float(a.get("at") or 0)) < 300] if isinstance(liste, list) else []
        liste.append(auftrag)
        tmp = pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(liste, f, ensure_ascii=False, indent=1)
        os.replace(tmp, pfad)
    return auftrag["cmd_id"]


def scharf_copier_solo():
    """Offene Solo-Hedges aus den frischen Copier-Status-Dateien → {ticket: plan8 | ''} | None (nicht prüfbar). plan8 aus dem Kommentar bzw. plan_id[:8]."""
    out, geprueft = {}, False
    for inst in instances():
        st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
        try:
            age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
        except (ValueError, TypeError):
            continue
        if not st.get("running") or age > 15 or not isinstance(st.get("hedge_solo"), list):
            continue
        geprueft = True
        for x in st["hedge_solo"]:
            if isinstance(x, dict) and x.get("ticket"):
                out[int(x["ticket"])] = str(x.get("plan8") or str(x.get("plan_id") or "")[:8] or "")
    return out if geprueft else None


# SCHLIESS-WACHE OHNE DAUER-LESEN (SW1, 05.11.2026, Anlass ES4/SW1: PCs seit 02.11. täglich langsamer): die Wache läuft mit offenem Eintrag 10–20×/s und las
# dabei JEDES Mal alle status-*.json (15–35 Dateien à ~9 KB = bis 300 KB JSON je Runde, bis 6 MB/s Parsen + Datei-Öffnen unter dem Virenscanner) — der Copier
# schreibt sie aber nur 1×/s (write_status, m.last_status > 1.0). Jetzt höchstens alle SCHARF_COPIER_CACHE_S neu gelesen, dazwischen derselbe Stand: der Inhalt
# ist ohnehin bis 1 s alt, die Leser brauchen ihn nur für den Copier-Beleg (1×/min) und „im Copier nicht mehr offen“ (erst nach 30 s Karenz). Der Close-Weg selbst
# (Reader-Stand je Runde, Takt 0,1/0,05 s) bleibt unverändert. Fehler werden nicht gemerkt (nächste Runde liest neu).
SCHARF_COPIER_CACHE_S = 0.5
_SCHARF_COPIER_CACHE = {"t": None, "wert": None}


def scharf_copier_tickets(jetzt=None, lesen=None):
    """Offene Solo-Hedge-Tickets aus den frischen Copier-Status-Dateien (status.hedge_solo) → set | None (nicht prüfbar). Höchstens alle
    SCHARF_COPIER_CACHE_S neu gelesen (s. Block oben); jetzt/lesen nur für den Selbsttest."""
    jetzt = time.monotonic() if jetzt is None else jetzt
    c = _SCHARF_COPIER_CACHE
    if c["t"] is not None and 0 <= jetzt - c["t"] < SCHARF_COPIER_CACHE_S:
        solo = c["wert"]
    else:
        solo = (lesen or scharf_copier_solo)()
        c["t"], c["wert"] = jetzt, solo
    return set(solo) if solo is not None else None


def _scharf_stand_lesen():
    import urllib.request
    with urllib.request.urlopen(READER_STAND_URL, timeout=0.5) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _scharf_runde(st, jetzt, offene_tickets=None, tsx=None):
    """Eine Runde der Schließ-Wache (testbar mit Attrappen): Einträge laden, je Eintrag entscheiden, Close senden bzw. Quittung prüfen, zurückschreiben.
    st = Reader-Stand oder None (nicht lesbar); tsx = tsx_stand_ausgabe() für Topstep-Einträge (quelle „tsx“, NV3) oder None. → Anzahl gesendeter Close-Aufträge."""
    liste = scharf_laden()
    if not liste:
        return 0
    erg_alle = read_json(os.path.join(HERE, "hedge_solo_ergebnis.json"), {}) or {}
    geaendert, n = False, 0
    for i, e in enumerate(list(liste)):
        # Copier meldet das Ticket offen → Beleg merken (höchstens 1×/min geschrieben), damit ein Big Trade über 3 h scharf bleibt (03.11.2026)
        if offene_tickets is not None and int(e.get("ticket") or 0) in offene_tickets and jetzt - float(e.get("copier_offen_at") or 0) >= SCHARF_COPIER_BELEG_NEU_S:
            e = dict(e, copier_offen_at=jetzt)
            liste[i], geaendert = e, True
        if not scharf_lebt(e, jetzt):
            scharf_loesen(e.get("ticket"), "abgelaufen" + (" (kein frischer Copier-Beleg)" if jetzt - float(e.get("at") or 0) < SCHARF_MAX_HART_S else ""))
            continue
        # S9: anders zugegangen (Level im Terminal, Hand in MT5, Tab bucht über die Copier-Liste) → Ticket nicht mehr offen → lösen
        if offene_tickets is not None and int(e.get("ticket") or 0) not in offene_tickets and jetzt - float(e.get("at") or 0) >= SCHARF_COPIER_KARENZ_S:
            scharf_loesen(e.get("ticket"), "im Copier nicht mehr offen")
            continue
        if e.get("status") == "schliesst":
            q = erg_alle.get(e.get("cmd_id")) if isinstance(erg_alle, dict) else None
            if isinstance(q, dict) and q.get("ok"):
                print(f"[scharf] Fusion zu: Ticket {e['ticket']} ({'schon zu' if q.get('schon_zu') else 'geschlossen'}), "
                      f"{jetzt - float(e.get('zu_at') or jetzt):.2f} s nach dem Auftrag", flush=True)
                scharf_spur(e["ticket"], "Fusion zu", f"{'schon zu' if q.get('schon_zu') else 'geschlossen'} · {jetzt - float(e.get('zu_at') or jetzt):.2f} s nach dem Auftrag")
                scharf_loesen(e.get("ticket"), "Panel-Close ok")
            elif jetzt - float(e.get("zu_at") or 0) >= SCHARF_CLOSE_WIEDER_S:   # keine Quittung → erneut (Copier antwortet schon_zu, wenn zu)
                e = dict(e, cmd_id=_scharf_close_senden(e), zu_at=jetzt)
                liste[i], geaendert, n = e, True, n + 1
            continue
        if e.get("quelle") == "tsx":   # NV3: Topstep — das TopstepX-Auge entscheidet (scharf_entscheid_tsx), kein Puls-Beleg
            if tsx is None:
                continue
            zu, e2, grund = scharf_entscheid_tsx(e, tsx, jetzt)
            if zu:
                e2.update(status="schliesst", cmd_id=_scharf_close_senden(e2), zu_at=jetzt, grund_zu=grund)
                n += 1
                print(f"[scharf] {grund} → close Ticket {e2['ticket']}", flush=True)
                scharf_spur(e2["ticket"], "CLOSE gesendet", f"{grund} · cmd {e2['cmd_id']}")
            _k = (tsx.get("stand") or {}).get("konto") if isinstance(tsx.get("stand"), dict) else None
            _k = _k if isinstance(_k, dict) else {}
            scharf_spur(e.get("ticket"), "Lage", f"{grund} · Auge-Konto {str(_k.get('kontonr') or _k.get('endung') or '-')[:40]} · Auge {str(tsx.get('script') or '-')[:12]}", nur_bei_wechsel=True)
            if e2 != e:
                liste[i], geaendert = e2, True
            continue
        if st is None:
            continue
        try:
            _idle = _win_leerlauf_s()
        except Exception:
            _idle = None
        beleg = (_PULS_BELEG.get("text") or None) if puls_beleg_gueltig(_PULS_BELEG.get("at"), jetzt, _idle) else None
        zu, e2, grund = scharf_entscheid(e, st, jetzt, beleg)
        if zu:
            e2.update(status="schliesst", cmd_id=_scharf_close_senden(e2), zu_at=jetzt, grund_zu=grund)
            n += 1
            print(f"[scharf] {grund} → close Ticket {e2['ticket']}", flush=True)
            scharf_spur(e2["ticket"], "CLOSE gesendet", f"{grund} · cmd {e2['cmd_id']}")
        # Lage-Zeile erst NACH dem Close (S9 02.11.2026): hält Windows die Spur-Datei kurz fest, wartet der Close nicht mit
        scharf_spur(e.get("ticket"), "Lage", f"{grund} · Reader-Konto {str(st.get('konto') or '-')[:40]} · Tab {str(st.get('positionen_tab') or '-')[:24]}"
                    f" · Beleg {beleg or ('-' if not _PULS_BELEG.get('text') else 'ungültig (Eingabe am PC seit dem Beleg)')}", nur_bei_wechsel=True)
        if e2 != e:
            liste[i], geaendert = e2, True
    if geaendert:
        with SCHARF_LOCK:
            frisch = {int(x.get("ticket") or 0): x for x in scharf_laden()}
            for e in liste:
                t = int(e.get("ticket") or 0)
                if t in frisch:                       # inzwischen gelöste Einträge nicht zurückschreiben
                    if e.get("quelle") == "tsx" and frisch[t].get("gesehen") is True and not e.get("gesehen"):
                        e = dict(e, gesehen=True)      # NV3: Sichtung, die der Tab in derselben Runde nachgetragen hat (/api/hedge-scharf), nicht überschreiben
                    frisch[t] = e
            scharf_speichern(list(frisch.values()))
    return n


def scharf_takt(liste):
    """Takt der nächsten Runde: 0,05 s, solange ein offener Eintrag eine Flach-Strecke hat (erste flache Lesung bis Entscheidung), sonst 0,1 s.
    Eingang 03.11.2026 (S9-Hinweis Last): davor kostet der langsamere Takt höchstens ~0,05 s bei der ersten flachen Lesung."""
    for e in liste or []:
        if isinstance(e, dict) and e.get("status") == "offen" and e.get("flach_seit"):
            return SCHARF_TAKT_FLACH_S
    return SCHARF_TAKT_S


def _scharf_wache():
    """Thread: die Schließ-Wache (s. Block-Kopf). Wirft nie. Ohne scharfen Eintrag nur 1× je Sekunde ein Blick in die Datei."""
    while True:
        try:
            _l = scharf_laden()
            if not _l:
                time.sleep(1.0)
                continue
            st = None
            if any(x.get("quelle") != "tsx" for x in _l):   # NV3: nur Topstep-Einträge → kein HTTP zum TradingView-Reader
                try:
                    st = _scharf_stand_lesen()
                except Exception:
                    st = None
            try:
                tsx = tsx_stand_ausgabe() if any(x.get("quelle") == "tsx" for x in _l) else None
            except Exception:
                tsx = None
            try:
                tickets = scharf_copier_tickets()
            except Exception:
                tickets = None
            _scharf_runde(st, time.time(), tickets, tsx)
        except Exception as ex:
            print(f"[scharf] Fehler: {type(ex).__name__}: {ex}", flush=True)
            time.sleep(1.0)
        try:
            takt = scharf_takt(scharf_laden())
        except Exception:
            takt = SCHARF_TAKT_S
        time.sleep(takt)


# ══ LESE-SPERRE UM DAS MARKET OPENING (Finn 02.11.2026, Korrektur über den Eingang: kein „Konto fest bei offenem Trade“ — die Heim-Wache-Regel bleibt, Puls
# bleibt zu Hause, wenn der Trade ≤ 2.000 $ vor TP/Liq steht): 18:30–18:40 Asia/Dubai keine Lesungen und keine Kontowechsel in TradingView. tv-lesen und
# tv-konten-liste antworten in dem Fenster puls_beschaeftigt (retry_ok, der Aufrufer wartet wie bei einem laufenden Lauf). Trade-Starts (tv-konto) und
# tv-close sind nie betroffen (Finn: „ein Trade hat die oberste Priorität“, Schließen ist die sichere Richtung). Dazu bleibt: bei offenem TradingView-Trade mit Fusion-Hedge (scharfer Eintrag) kein Puls-Chrome-Neustart (Simon 18:31, s. tv-konto/tsx-*). ══
LESE_SPERRE_VON = (18, 30)
LESE_SPERRE_BIS = (18, 40)
DUBAI_UTC_OFFSET_S = 4 * 3600   # Dubai ohne Sommerzeit


def lese_sperre_markt(jetzt_ts):
    """REIN RECHNEND (testbar): (gesperrt, msg) — 18:30 ≤ Dubai-Uhrzeit < 18:40."""
    sek = int(jetzt_ts + DUBAI_UTC_OFFSET_S) % 86400
    von, bis = LESE_SPERRE_VON[0] * 3600 + LESE_SPERRE_VON[1] * 60, LESE_SPERRE_BIS[0] * 3600 + LESE_SPERRE_BIS[1] * 60
    if von <= sek < bis:
        return True, (f"Market Opening: {LESE_SPERRE_VON[0]}:{LESE_SPERRE_VON[1]:02d}–{LESE_SPERRE_BIS[0]}:{LESE_SPERRE_BIS[1]:02d} Dubai keine Lesungen "
                      f"und keine Kontowechsel in TradingView — wartet noch {int((bis - sek) // 60) + 1} min")
    return False, ""


def _lese_sperre_antwort(konto, pfad):
    gesperrt, msg = lese_sperre_markt(time.time())
    # Heimweg frei (S9 02.11.2026): ins Konto eines offenen TV-Trades mit Hedge darf Puls auch 18:30–18:40 (bigTradeHeimPlanen → tvV2Lesen) — sonst bliebe er
    # im Opening bis 10 min im falschen Konto, der Reader sähe den Trade nicht und die Schließ-Wache könnte nicht schließen
    if gesperrt and str(konto or "").strip().upper() in [str(x).strip().upper() for x in scharf_konto_fest()]:
        gesperrt = False
    if gesperrt:
        print(f"[lese-sperre] {pfad} @{konto}: wartet (Market Opening)", flush=True)
        return json.dumps({"ok": False, "code": "puls_beschaeftigt", "lese_sperre": True, "retry_ok": True, "gesendet": False, "msg": msg},
                          ensure_ascii=False)
    return None


_TAB_PULS_OEFFNEN_CODE = (
    "import sys, json, order_bot\n"
    "t = []\n"
    "if not order_bot._puls_chrome_sicher(t):\n"
    "    print(json.dumps([False, ' / '.join(t)[-200:] or 'Puls-Chrome nicht erreichbar'])); sys.exit(0)\n"
    "l = order_bot._cdp_http('/json/list') or []\n"
    "if any(isinstance(x, dict) and x.get('type') == 'page' and str(x.get('url') or '').startswith(('http://localhost:5000', 'http://127.0.0.1:5000')) for x in l):\n"
    "    print(json.dumps([False, 'im Puls-Chrome steht schon ein Prophos-Tab — kein zweiter'])); sys.exit(0)\n"
    "v = order_bot._cdp_http('/json/version') or {}\n"
    "c = order_bot._CdpVerbindung(v.get('webSocketDebuggerUrl') or '')\n"
    "r = c.rufe('Target.createTarget', {'url': sys.argv[1], 'newWindow': True, 'background': True}, timeout=8); c.zu()\n"
    "print(json.dumps([bool((r or {}).get('targetId')), 'Puls-Chrome (Port 9333), eigenes Fenster']))\n")
_TAB_PULS_LESEN_CODE = (
    "import sys, json, order_bot\n"
    "out = []\n"
    "for u in sys.argv[1:]:\n"
    "    try:\n"
    "        c = order_bot._CdpVerbindung(u)\n"
    "        r = c.rufe('Runtime.evaluate', {'expression': 'String(window._tabHerzId || \"\")', 'returnByValue': True}, timeout=5); c.zu()\n"
    "        out.append(str(((r or {}).get('result') or {}).get('value') or ''))\n"
    "    except Exception:\n"
    "        pass\n"
    "print(json.dumps(out))\n")


# ══ PROPHOS IM PULS-CHROME HALTEN (30.10.2026, Master nach Befund C, Ina pc-xc5c52: „Das Panel stellt dauerhaft sicher, dass genau EIN
# Prophos-Tab im Puls-Chrome (im eigenen Fenster) läuft. Fehlt er dort, öffnet das Panel ihn selbst, gestreut und mit allen Riegeln.") Je
# Runde liest der Tab-Wächter die CDP-Liste des Puls-Chrome. Fehlt dort ein Prophos-Tab, während ein Tab woanders lebt, öffnet er ihn —
# höchstens TAB_OEFFNEN_MAX_TAG am Tag, 1 je TAB_OEFFNEN_ABSTAND_S, gestreut 0–30 s, nur ohne Server-Riegel (Signal/Start/Hedge), ohne
# Puls/Polar/MT5-Order und 120 s ohne Eingabe. Läuft das Puls-Chrome nicht, startet es dafür niemand (das macht Puls beim nächsten Lauf);
# fragt gar kein Tab mehr, öffnet der bisherige Weg (tab_oeffnen_entscheiden) — jetzt ebenfalls im Puls-Chrome. Der alte Tab bleibt offen
# und wird über die Haupt-Tab-Wahl zum „nur ansehen"-Tab. ══
def puls_tab_entscheiden(jetzt, start, erreichbar, n_prophos, haupt_lebt, letzter_versuch, n_heute, riegel, lock_frei, idle_s):
    """REIN RECHNEND (testbar): (öffnen: bool, grund: str). '' = nichts zu sagen."""
    if jetzt - start < TAB_OEFFNEN_ANLAUF_S or not erreichbar or not haupt_lebt:
        return False, ""
    if n_prophos >= 2:
        return False, f"{n_prophos} Prophos-Tabs im Puls-Chrome — einer ist Haupt-Tab, die anderen nur ansehen (keiner geschlossen)"
    if n_prophos == 1:
        return False, ""
    warum = "kein Prophos-Tab im Puls-Chrome (Haupt-Tab liegt in einem anderen Chrome)"
    if n_heute >= TAB_OEFFNEN_MAX_TAG:
        return False, f"{warum} — heute schon {n_heute}× geöffnet (Deckel {TAB_OEFFNEN_MAX_TAG})"
    if letzter_versuch and jetzt - letzter_versuch < TAB_OEFFNEN_ABSTAND_S:
        return False, f"{warum} — zuletzt vor {int((jetzt - letzter_versuch) // 60)} min geöffnet (höchstens 1 je {TAB_OEFFNEN_ABSTAND_S // 60} min)"
    if riegel:
        return False, f"{warum} — wartet: {riegel}"
    if not lock_frei:
        return False, f"{warum} — wartet: Puls/MT5-Order läuft"
    if idle_s is not None and idle_s < TAB_NL_IDLE_S:
        return False, f"{warum} — wartet: am PC wird gerade gearbeitet (letzte Eingabe vor {int(idle_s)} s)"
    return True, warum


def puls_prophos_lage():
    """CDP-Liste des Puls-Chrome → (erreichbar, Zahl der Prophos-Seiten, Liste). Nur lesen."""
    try:
        liste = _cdp_get("/json/list")
    except Exception:
        return False, 0, []
    liste = liste if isinstance(liste, list) else []
    n = sum(1 for t in liste if isinstance(t, dict) and t.get("type") == "page" and _PROPHOS_URL_RE.match(str(t.get("url") or "")))
    return True, n, liste


def _tabs_puls_lesen(liste):
    """Kennungen (window._tabHerzId) der Prophos-Seiten im Puls-Chrome per CDP Runtime.evaluate — nur lesen, frischer Prozess. → set | None."""
    urls = [str(t.get("webSocketDebuggerUrl")) for t in liste or [] if isinstance(t, dict) and t.get("type") == "page"
            and _PROPHOS_URL_RE.match(str(t.get("url") or "")) and t.get("webSocketDebuggerUrl")]
    if not urls:
        return set()
    try:
        r = subprocess.run([sys.executable, "-c", _TAB_PULS_LESEN_CODE] + urls[:6], cwd=HERE, capture_output=True, text=True, timeout=45,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {t for t in json.loads((r.stdout or "").strip().splitlines()[-1]) if t}
    except Exception:
        return None


def _haupt_tab_runde(pc, liste, jetzt):
    """Puls-Kennzeichen der lebenden Tabs nachziehen (nur bei ≥ 2 lebenden Tabs, höchstens je TAB_PULS_PRUEF_S, sonst sobald eine Kennung
    noch unbekannt ist) und zweite Tabs einmal in Log/Spur melden."""
    # für Zählung/Meldung nur FRISCHE Kennungen (Haupt-Tab fragt alle 5–30 s, „nur ansehen" alle 50–70 s) — die Hysterese der Wahl bleibt 5 min
    lebend = [t for t, z in _TABS.items() if jetzt - float(z.get("at") or 0) <= TAB_ZAEHL_FRISCH_S
              or jetzt - float(z.get("neben_at") or 0) <= TAB_ZAEHL_FRISCH_S + 60]
    if len(lebend) >= 2 and (any(_TABS[t].get("puls") is None for t in lebend) or jetzt - _TAB_HAUPT["puls_at"] >= TAB_PULS_PRUEF_S):
        tids = _tabs_puls_lesen(liste)
        _TAB_HAUPT["puls_at"] = jetzt
        if tids is not None:
            for t in _TABS:
                _TABS[t]["puls"] = t in tids
            _TAB_HAUPT["tid"] = haupt_tab_waehlen(_TABS, jetzt, _TAB_HAUPT["tid"])
    meldung = ""
    if len(lebend) >= 2:
        h = _TABS.get(_TAB_HAUPT["tid"]) or {}
        meldung = (f"{len(lebend)} Prophos-Tabs an diesem PC — Haupt-Tab {'im Puls-Chrome' if h.get('puls') else 'in einem anderen Chrome'}"
                   f"{'' if h.get('login') else ' (nicht angemeldet)'}, die anderen nur ansehen")
        if any(_TABS[t].get("puls") is True and not _TABS[t].get("login") for t in lebend):
            meldung += " — der Prophos-Tab im Puls-Chrome ist nicht angemeldet: am PC dort einmal in Prophos einloggen, dann wird er Haupt-Tab"
            if not _TAB_HAUPT.get("login_gemeldet"):
                # ⚪ einmal je PC (Master 30.10.2026): statt den „nur ansehen"-Tab zu heilen → melden (Railway drosselt je PC auf 1× je Tag)
                _TAB_HAUPT["login_gemeldet"] = True
                _tab_heil_melden("Prophos im Puls-Chrome nicht angemeldet — einmal einloggen", "puls_login")
    if meldung != _TAB_HAUPT["meldung"]:
        _TAB_HAUPT["meldung"] = meldung
        if meldung:
            print(f"[haupt-tab] {meldung}", flush=True)
            if pc:
                _tab_stand_holen(pc, meldung)


# ══ FERN-AUFTRAG „PROPHOS IM PULS-CHROME ÖFFNEN" (30.10.2026, Finn: „Mach diesen Tab nochmal überall auf."): Railway legt den Auftrag in die
# Antwort von /code/tab-stand (auftrag {id, at}, verfällt nach 10 min). Das Panel öffnet localhost:5000 im Puls-Chrome im eigenen Fenster
# (_tab_oeffnen) bzw. holt den vorhandenen Prophos-Tab nach vorn (/json/activate) — nie doppelt. Unter TV_ORDER_LOCK, ohne Puls/Polar/MT5-Lauf,
# ohne Server-Riegel und TAB_AUFTRAG_IDLE_S ohne Eingabe (kürzer als sonst: der Auftrag kommt bewusst, während jemand am PC ist); sonst
# „verschoben" mit Grund und nächste Runde erneut. Quittung an Railway POST /pc/tab-auftrag-quittung. Kein Login, kein Klick. ══
TAB_AUFTRAG_IDLE_S = 20
TAB_AUFTRAG_MAX_VERSUCHE = 4
_TAB_AUFTRAG = {"erledigt": set(), "versuche": {}, "gemeldet": {}}


def tab_auftrag_entscheiden(auftrag, erledigt, versuche, riegel, lock_frei, idle_s):
    """REIN RECHNEND (testbar): ('' | 'tun' | 'verschoben' | 'aufgeben', grund)."""
    aid = str((auftrag or {}).get("id") or "") if isinstance(auftrag, dict) else ""
    if not aid or aid in erledigt:
        return "", ""
    if versuche >= TAB_AUFTRAG_MAX_VERSUCHE:
        return "aufgeben", f"{versuche} Versuche ohne Erfolg — am PC ansehen"
    if riegel:
        return "verschoben", f"wartet: {riegel}"
    if not lock_frei:
        return "verschoben", "wartet: Puls/Polar/MT5-Order läuft — danach"
    if idle_s is not None and idle_s < TAB_AUFTRAG_IDLE_S:
        return "verschoben", f"wartet: am PC wird gerade gearbeitet (letzte Eingabe vor {int(idle_s)} s)"
    return "tun", ""


def _prophos_puls_vorn():
    """→ (ok, ergebnis 'geoeffnet'|'vorn'|'verschoben'|'fehler', Klartext). Unter TV_ORDER_LOCK; öffnet nur, wenn im Puls-Chrome kein Prophos-Tab steht."""
    if not TV_ORDER_LOCK.acquire(blocking=False):
        return False, "verschoben", "Puls läuft gerade im Browser — danach"
    try:
        if not _browser_und_mt5_frei(tv_eigen=True):
            return False, "verschoben", "MT5-Order/Polar läuft gerade — danach"
        url_merk = _TAB_OEFFNEN.get("url") or ""
        da, n, liste = puls_prophos_lage()
        erg = "vorn"
        if not da or n == 0:
            ok, msg = _tab_oeffnen(url_merk or TAB_URL, lock_gehalten=True)
            if not ok:
                return False, "fehler", msg
            erg = "geoeffnet"
            da, n, liste = puls_prophos_lage()
        pro, tv = cdp_prophos_ziele(liste, url_merk)
        if not pro:
            return False, "fehler", "Prophos-Tab im Puls-Chrome nach dem Öffnen nicht gefunden"
        time.sleep(0.4 + random.random() * 0.6)
        _cdp_get(f"/json/activate/{pro['id']}")
        zurueck = ""
        # TRADINGVIEW ZURÜCK (S2 30.10.2026): liegen Prophos und TradingView im SELBEN Fenster, wäre das Userscript jetzt ein Hintergrund-Tab
        # (gedrosselt) → nach 4–7 s (gestreut) TradingView wieder aktivieren, wie _prophos_tab_wecken. Eigene Fenster bleiben, wie sie sind.
        if tv and tv.get("id") != pro.get("id") and _cdp_selbes_fenster(pro["id"], tv["id"]) is not False:
            time.sleep(4 + random.random() * 3)
            try:
                _cdp_get(f"/json/activate/{tv['id']}")
                zurueck = ", TradingView danach wieder vorn (selbes Fenster)"
            except Exception as e:
                zurueck = f", TradingView NICHT zurück ({type(e).__name__})"
        return True, erg, ("im Puls-Chrome im eigenen Fenster geöffnet und nach vorn geholt" if erg == "geoeffnet"
                           else "Prophos-Tab im Puls-Chrome nach vorn geholt (war schon offen, nicht doppelt geöffnet)") + zurueck
    except Exception as e:
        return False, "fehler", f"{type(e).__name__}: {e}"
    finally:
        TV_ORDER_LOCK.release()


_TAB_FENSTER_CODE = (
    "import sys, json, order_bot\n"
    "v = order_bot._cdp_http('/json/version') or {}\n"
    "c = order_bot._CdpVerbindung(v.get('webSocketDebuggerUrl') or '')\n"
    "w = [c.rufe('Browser.getWindowForTarget', {'targetId': t}, timeout=5).get('windowId') for t in sys.argv[1:3]]; c.zu()\n"
    "print(json.dumps(w))\n")


def _cdp_selbes_fenster(a, b):
    """Liegen zwei Seiten des Puls-Chrome im selben Fenster? → True/False, None = unklar (nur lesen, Browser.getWindowForTarget)."""
    try:
        r = subprocess.run([sys.executable, "-c", _TAB_FENSTER_CODE, str(a), str(b)], cwd=HERE, capture_output=True, text=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        w = json.loads((r.stdout or "").strip().splitlines()[-1])
        return None if None in w else w[0] == w[1]
    except Exception:
        return None


def _tab_auftrag_quittung(aid, ergebnis, grund):
    """POST /pc/tab-auftrag-quittung (X-Code-Token). Wirft nie."""
    import urllib.request
    tok = code_token()
    if not tok:
        return
    try:
        body = json.dumps({"id": aid, "ergebnis": ergebnis, "grund": str(grund)[:200]}).encode("utf-8")
        req = urllib.request.Request(CODE_QUELLE + "/pc/tab-auftrag-quittung", data=body, method="POST",
                                     headers={"X-Code-Token": tok, "Content-Type": "application/json", "User-Agent": "prophos-panel"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print(f"[tab-auftrag] Quittung nicht gesendet ({type(e).__name__})", flush=True)


def _tab_auftrag_schritt():
    """Eine Runde: offenen Auftrag aus dem letzten Tab-Stand (≤ 150 s alt) ausführen bzw. verschieben und quittieren."""
    st = TAB_NL.get("stand") if time.time() - float(TAB_NL.get("stand_at") or 0) < 150 else None
    a = st.get("auftrag") if isinstance(st, dict) else None
    aid = str((a or {}).get("id") or "") if isinstance(a, dict) else ""
    riegel = str((st or {}).get("riegel") or "").strip() if isinstance(st, dict) else ""
    aktion, grund = tab_auftrag_entscheiden(a, _TAB_AUFTRAG["erledigt"], _TAB_AUFTRAG["versuche"].get(aid, 0), riegel,
                                            _browser_und_mt5_frei(), _win_leerlauf_s())
    if not aktion:
        return
    erg = "verschoben"
    if aktion == "aufgeben":
        _TAB_AUFTRAG["erledigt"].add(aid)
        erg = "fehler"
    elif aktion == "tun":
        time.sleep(random.random() * 4)                 # gestreut
        _TAB_AUFTRAG["versuche"][aid] = _TAB_AUFTRAG["versuche"].get(aid, 0) + 1
        ok, erg, grund = _prophos_puls_vorn()
        if ok:
            _TAB_AUFTRAG["erledigt"].add(aid)
            _TAB_HAUPT["puls_at"] = 0.0                 # Kennungen bald neu lesen
        elif erg == "verschoben":
            _TAB_AUFTRAG["versuche"][aid] -= 1          # nur echte Fehlversuche zählen
    if _TAB_AUFTRAG["gemeldet"].get(aid) != (erg, grund):
        _TAB_AUFTRAG["gemeldet"][aid] = (erg, grund)
        print(f"[tab-auftrag] {erg}: {grund}", flush=True)
        _tab_auftrag_quittung(aid, erg, grund)


# ══ UPDATE-SCHUTZ (29.10.2026, Master nach dem Befund „Deploy-Welle": fünf Abrisse in zwei Stunden, jeder 1–2 min nach einem Push mit
# app.py/panel.py — der Neustart riss laufende Puls-/Order-Aufrufe ab, „Ergebnis UNKLAR"). Das Panel sagt per GET /api/beschaeftigt, ob ein
# Lauf es hält; das lokale app.py (Proxy aller Tab-Aufrufe) und der Versions-Wächter hier starten nur neu, wenn es „frei" ist — gestreut
# 0–60 s je PC (Jitter-Regel), höchstens UPDATE_DECKEL_S lang vertagt, danach trotzdem (Spur + ⚪ an die Master-IDs über Railway).
UPDATE_DECKEL_S = 15 * 60
UPDATE_STREU_S = 60.0
UPDATE_LEERLAUF_S = 320.0       # Deckel erreicht: zu und höchstens so lange leerlaufen lassen (längster Lauf ~310 s), dann beenden
# Laufende POST-Aufrufe (Prüfer 29.10.2026: manche Wege tun vor dem Lock Sekunden lang etwas — richtung_frei, tv-fokus, mouse-test …);
# zu = kurz vor dem Beenden neue POSTs mit 503 „nichts gesendet" ablehnen (wie der Proxy im lokalen app.py). tsx-stand zählt nie.
_PANEL_POST = {"n": 0, "zu": False}
_PANEL_POST_LOCK = threading.Lock()


def panel_beschaeftigt_gruende():
    """Was hält das Panel gerade? -> Liste kurzer Gründe ([] = frei). Nur lesen; wirft nie (Fehler = 'unbekannt', also belegt)."""
    try:
        g = []
        if _PANEL_POST["n"] > 0:
            g.append(f"{_PANEL_POST['n']} laufende(r) Panel-Aufruf(e)")
        if TV_ORDER_LOCK.locked():
            g.append("TradingView-/TopstepX-Lauf (TV_ORDER_LOCK)")
        for f, l in list(MASTER_ORDER_LOCKS.items()):
            # LK1 (Master 11.11.2026 nach RA2): eine reine Deal-/Vorflug-Lesung klickt nichts und bewegt keine Maus → kein Grund, den Neustart zu vertagen
            if l.locked() and f not in (DEALS_LESEN | VORFLUG_LESEN):
                g.append(f"MT5-Order {str(f)[:40]}")
        if polar_panel and polar_panel.aktiv():
            g.append("Polar-Lauf")
        if polar_panel and getattr(polar_panel, "test_aktiv", lambda: False)():
            g.append("Polar-Maus-Test")
        if PROV_JOB and not PROV_JOB.get("done"):
            g.append("Provisionierung")
        try:
            if time.time() - os.path.getmtime(os.path.join(HERE, "puls_handlauf.lock")) < 900:
                g.append("K3-Handlauf")
        except OSError:
            pass
        return g
    except Exception as e:
        return [f"unbekannt ({type(e).__name__})"]


def update_neustart_entscheiden(gruende, wartet_seit, jetzt, streu_bis, deckel_s=UPDATE_DECKEL_S):
    """REIN RECHNEND (testbar): darf der Neustart jetzt? -> ('warten' | 'jetzt' | 'erzwingen', grund).
    Erst nach der Streuzeit (streu_bis), dann nur ohne Gründe; belegt länger als deckel_s seit wartet_seit → 'erzwingen'."""
    if jetzt < streu_bis:
        return "warten", f"Streuung noch {int(streu_bis - jetzt)} s"
    if not gruende:
        return "jetzt", ""
    # POLAR NIE ERZWINGEN (S2/Master 29.10.2026, alte Regel „nie mitten im Polar-Trade"): solange Polar läuft, unbegrenzt vertagen
    if any(str(x).startswith("Polar") for x in gruende):
        return "warten", "Polar läuft — Neustart nie erzwungen: " + ", ".join(gruende)[:200]
    if wartet_seit is not None and jetzt - wartet_seit >= deckel_s:
        return "erzwingen", "seit " + str(int((jetzt - wartet_seit) // 60)) + " min belegt: " + ", ".join(gruende)[:200]
    return "warten", "belegt: " + ", ".join(gruende)[:200]


def panel_lauf_gruende(gruende):
    """Teilmenge der Gründe, die ein Neustart des LOKALEN app.py (Proxy) betrifft: laufende Panel-Aufrufe und Order-Sperren. Polar,
    K3-Handlauf und Provisionierung laufen ohne Proxy weiter (Prüfer 29.10.2026: sonst wartet app.py bei jedem Polar-Trade 15 min)."""
    return [x for x in (gruende or []) if "Panel-Aufruf" in x or "TV_ORDER_LOCK" in x or x.startswith("MT5-Order") or x.startswith("unbekannt")]


def _panel_zu_und_leeren(erzwingen):
    """Neue POSTs ablehnen, dann prüfen: läuft noch etwas? -> True = darf beenden. Ohne Deckel: läuft etwas → wieder auf, False.
    Mit Deckel: bis UPDATE_LEERLAUF_S auf das Ende warten (0,5-s-Takt), dann True."""
    with _PANEL_POST_LOCK:
        _PANEL_POST["zu"] = True
    ende = time.time() + (UPDATE_LEERLAUF_S if erzwingen else 0.0)
    while True:
        g = panel_beschaeftigt_gruende()          # ALLE Gründe (S2 29.10.2026) — nicht nur die, die das lokale app.py betreffen
        if not g:
            return True
        polar = any(str(x).startswith("Polar") for x in g)
        if time.time() >= ende or polar:          # Polar: nie erzwingen, sofort wieder auf und weiter vertagen
            if erzwingen and not polar:
                return True
            with _PANEL_POST_LOCK:
                _PANEL_POST["zu"] = False
            return False
        time.sleep(0.5)


def update_spur_melden(wer, von, auf, grund, wartete_s):
    """Erzwungener Neustart → Railway POST /pc/update-spur (⚪ an die Master-IDs). Wirft nie, blockiert höchstens 5 s."""
    import urllib.request
    tok = code_token()
    if not tok:
        return
    try:
        body = json.dumps({"pc": pc_id_lesen() or "", "wer": wer, "von": str(von)[:30], "auf": str(auf)[:30], "grund": str(grund)[:240],
                           "wartete_s": int(wartete_s or 0)}).encode("utf-8")
        req = urllib.request.Request(CODE_QUELLE + "/pc/update-spur", data=body, method="POST",
                                     headers={"X-Code-Token": tok, "Content-Type": "application/json", "User-Agent": "prophos-panel"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print(f"[panel] Update-Spur nicht gemeldet ({type(e).__name__})", flush=True)


def _browser_und_mt5_frei(tv_eigen=False):
    """Kein Puls im Browser (TV_ORDER_LOCK) und keine MT5-Order (MASTER_ORDER_LOCKS: Echo-V2 /api/master-order klickt im MT5-Fenster
    F9/Felder/Knopf — Prüfer S2 16.10.2026: holt der Wächter dann Chrome nach vorn, landet der Vordergrund mitten im Order-Dialog).
    tv_eigen=True: TV_ORDER_LOCK hält der Aufrufer selbst."""
    try:
        if polar_panel and polar_panel.aktiv():   # POLAR-VORRANG (20.10.2026): nie Strg+F5/Tab öffnen, solange Polar den PC hält
            return False
        if polar_panel and getattr(polar_panel, "test_aktiv", lambda: False)():   # Maus-Test × (20.10.2026): nicht in die geparkte Maus fahren
            return False
        if not tv_eigen and TV_ORDER_LOCK.locked():
            return False
        return not mt5_order_belegt()   # reine Deal-/Vorflug-Lesungen zählen nicht (S1, RA2 F1)
    except Exception:
        return False


def _tab_stand_holen(pc, spur):
    from urllib.parse import urlencode
    # NEULADE-GRUND JE PC (02.11.2026, Prüfauftrag Betrieb 1: [tab-neuladen] steht nur in der Konsole): letztes Ergebnis mitschicken, Railway zeigt es in /admin/pc-stand.
    # Über das Panel, nicht über den Tab: Ein hängender alter Tab schreibt kein neues Feld, gerade den will man sehen.
    q = {}
    if spur:
        q["panel"] = spur[:200]
    if TAB_NL.get("ergebnis"):
        q.update(ergebnis=str(TAB_NL["ergebnis"])[:300], ergebnis_at=int(TAB_NL.get("ergebnis_at") or 0))
    roh = code_holen(f"/code/tab-stand/{pc}" + ("?" + urlencode(q) if q else ""), timeout=10)
    try:
        return json.loads(roh.decode("utf-8")) if roh else None
    except Exception:
        return None


def _tab_neulade_waechter():
    if os.name != "nt":
        return
    time.sleep(TAB_NL_ANLAUF_S)
    while True:
        try:
            if (base_config() or {}).get("tab_neuladen") is False:
                time.sleep(TAB_NL_TAKT_S * 5)
                continue
            pc = pc_id_lesen()
            # FERN-AUFTRAG (30.10.2026): „Prophos im Puls-Chrome öffnen" aus dem letzten Tab-Stand — vor allem anderen, eigene Riegel
            try:
                _tab_auftrag_schritt()
            except Exception as e:
                print(f"[tab-auftrag] Fehler: {type(e).__name__}: {e}", flush=True)
            _puls_wache_schritt(pc)   # PULS-WACHE (02.11.2026): fehlender Prophos-Tab im Puls-Chrome → nach 60 s neu, auch bei offenem Trade
            try:
                _tab_vorflug_schritt(pc)   # F-B (11.11.2026): 2–3 min vor einem Start Lebenszeichen prüfen, bei rot Stufen-Heilung sofort
            except Exception as e:
                print(f"[tab-vorflug] Fehler: {type(e).__name__}: {e}", flush=True)
            jetzt0 = time.time()
            tag = datetime.now().strftime("%Y-%m-%d")
            if _TAB_OEFFNEN["tag"] != tag:
                _TAB_OEFFNEN.update(tag=tag, geoeffnet=[])
            still0 = jetzt0 - max(_TAB_OEFFNEN["zuletzt"], _TAB_OEFFNEN["start"])
            # STUFEN-HEILUNG (30.10.2026): Prophos-Tab im Puls-Chrome still bzw. ohne Verbindung → wecken / neu laden / neu öffnen / melden
            if jetzt0 - _TAB_OEFFNEN["start"] >= TAB_OEFFNEN_ANLAUF_S and _tab_heil_schritt(pc, still0):
                time.sleep(20 + random.random() * 15)       # während einer Folge enger takten (Stufe 2 nach 60 s)
                continue
            # PULS-CHROME-LAGE + HAUPT-TAB (30.10.2026): Prophos-Seiten im Puls-Chrome zählen, Puls-Kennzeichen der Tabs nachziehen
            puls_da, puls_n, puls_liste = puls_prophos_lage()
            if puls_da:
                _haupt_tab_runde(pc, puls_liste, jetzt0)
            fenster_da = bool(_prophos_fenster())
            chrome_offen = (not fenster_da) and still0 >= TAB_OEFFNEN_FEHLT_S and _chrome_hauptfenster_da()
            auf, grund_auf = tab_oeffnen_entscheiden(jetzt0, _TAB_OEFFNEN["zuletzt"], _TAB_OEFFNEN["start"], fenster_da,
                                                     TAB_NL["letzter_versuch"], len(_TAB_OEFFNEN["geoeffnet"]),
                                                     _browser_und_mt5_frei(), _win_leerlauf_s(), chrome_offen, puls_da and puls_n > 0)
            if auf:
                TAB_NL["letzter_versuch"] = jetzt0
                ok, msg = _tab_oeffnen(_TAB_OEFFNEN["url"] or TAB_URL)
                if ok:
                    _TAB_OEFFNEN["geoeffnet"].append(datetime.now().isoformat(timespec="seconds"))
                    _TAB_OEFFNEN["geoeffnet_at"] = jetzt0
                grund_auf = f"{grund_auf} → {'geöffnet' if ok else 'NICHT geöffnet'}: {msg}"
            # LOGIN-BEWEIS (Master 16.10.2026): nach dem Öffnen muss sich der Tab innerhalb von 3 min melden, und zwar angemeldet —
            # sonst claimt er nichts. Ergebnis einmal in Log/Spur.
            ga = _TAB_OEFFNEN["geoeffnet_at"]
            if ga and not auf and jetzt0 - ga >= 180:
                _TAB_OEFFNEN["geoeffnet_at"] = 0.0
                if _TAB_OEFFNEN["zuletzt"] < ga:
                    grund_auf = "Tab geöffnet, meldet sich aber nicht (3 min nach dem Öffnen keine Abfrage) — am PC Chrome/Prophos ansehen"
                elif _TAB_OEFFNEN["login"] is False:
                    grund_auf = "Tab offen, aber nicht angemeldet — am PC in Prophos einloggen (sonst claimt der Tab keine Starts)"
                else:
                    grund_auf = "Tab geöffnet und meldet sich" + (" angemeldet" if _TAB_OEFFNEN["login"] else " (alter Tab-Stand, Login unbekannt)")
                print(f"[tab-neuladen] {grund_auf}", flush=True)
                if pc:
                    _tab_stand_holen(pc, grund_auf)
            if grund_auf and not fenster_da:
                if grund_auf != TAB_NL["grund"]:
                    print(f"[tab-neuladen] {grund_auf}", flush=True)
                    TAB_NL.update(grund=grund_auf, at=jetzt0)
                stand0 = _tab_stand_holen(pc, grund_auf) if pc else None          # nur die Spur an Railway
                if isinstance(stand0, dict) and stand0.get("ok"):
                    TAB_NL.update(stand=stand0, stand_at=time.time())
                time.sleep(TAB_NL_TAKT_S + random.random() * 10)
                continue
            if pc:
                stand = _tab_stand_holen(pc, TAB_NL["grund"])
                if isinstance(stand, dict) and stand.get("ok"):
                    TAB_NL.update(stand=stand, stand_at=time.time())   # echo_logins für die EA-Selbstheilung (F2)
                jetzt = time.time()
                frei = _browser_und_mt5_frei()
                still = jetzt - max(_TAB_OEFFNEN["zuletzt"], _TAB_OEFFNEN["start"]) if jetzt - _TAB_OEFFNEN["start"] >= TAB_OEFFNEN_ANLAUF_S else None
                laden, grund, TAB_NL["hinter_seit"] = tab_neuladen_entscheiden(stand, jetzt, TAB_NL["hinter_seit"],
                                                                               TAB_NL["letzter_versuch"], _win_leerlauf_s(), frei, still)
                if laden:
                    TAB_NL["letzter_versuch"] = jetzt
                    try:
                        pro0 = cdp_prophos_ziele(puls_liste or [], _TAB_OEFFNEN.get("url") or "")[0] if puls_da else None
                    except Exception:
                        pro0 = None
                    weg = tab_neulade_weg(stand, (_TABS.get(_TAB_HAUPT.get("tid")) or {}).get("puls"), pro0)
                    if weg == "cdp":   # 03.11.2026: verdeckter Haupt-Tab im Puls-Chrome → genau den, nicht ein sichtbares Neben-Fenster
                        time.sleep(random.random() * 10)            # gestreut
                        ok, msg = _prophos_tab_neuladen_cdp(stand)
                        msg = f"per CDP im Puls-Chrome (Haupt-Tab {'im Puls-Chrome' if (_TABS.get(_TAB_HAUPT.get('tid')) or {}).get('puls') is True else 'verdeckt'}): {msg}"
                    else:
                        ok, msg = _prophos_tab_neu_laden()
                    if weg != "cdp" and not ok and "kein Chrome-Fenster mit aktivem Prophos-Tab" in str(msg):
                        # kein eigenes Prophos-Fenster (Tab liegt im Puls-Chrome hinter TradingView, 30.10.2026) → per CDP neu laden;
                        # nicht im Puls-Chrome → bleibt beim bisherigen Hinweis
                        cdp_da = True
                        try:
                            liste_c = _cdp_get("/json/list")        # antwortet :9333 überhaupt, ist das Puls-Chrome zuständig (Puls-Wache)
                            pro = cdp_prophos_ziele(liste_c if isinstance(liste_c, list) else [], _TAB_OEFFNEN.get("url") or "")[0]
                        except Exception:
                            pro, cdp_da = None, False
                        if pro:
                            time.sleep(random.random() * 10)        # gestreut
                            ok, msg = _prophos_tab_neuladen_cdp(stand)
                            msg = f"per CDP im Puls-Chrome: {msg}"
                        elif streifen_weg_noetig(msg, cdp_da, pro, (base_config() or {}).get("tab_streifen")):
                            # NL2 (11.11.2026): kein Puls-Chrome (:9333 zu), Prophos verdeckt im normalen Chrome → Tabstreifen per UIA
                            time.sleep(random.random() * 10)        # gestreut
                            ok, msg = _prophos_tab_neuladen_streifen()
                            msg = f"per Tabstreifen im normalen Chrome (kein Puls-Chrome): {msg}"
                    grund = f"{grund} → {'neu geladen' if ok else 'NICHT neu geladen'}: {msg}"
                    TAB_NL.update(ergebnis=grund, ergebnis_at=jetzt)
                elif puls_da:
                    # PROPHOS IM PULS-CHROME HALTEN (30.10.2026): lebt der Haupt-Tab woanders und fehlt er im Puls-Chrome → dort öffnen
                    riegel = str((stand or {}).get("riegel") or "").strip() if isinstance(stand, dict) and stand.get("ok") else "Tab-Stand von Railway nicht lesbar"
                    auf2, g2 = puls_tab_entscheiden(jetzt, _TAB_OEFFNEN["start"], puls_da, puls_n, still is not None and still < TAB_OEFFNEN_FEHLT_S,
                                                    TAB_NL["letzter_versuch"], len(_TAB_OEFFNEN["geoeffnet"]), riegel, frei, _win_leerlauf_s())
                    if auf2:
                        TAB_NL["letzter_versuch"] = jetzt
                        time.sleep(random.random() * 30)            # gestreut
                        ok, msg = _tab_oeffnen(_TAB_OEFFNEN["url"] or TAB_URL)
                        if ok:
                            _TAB_OEFFNEN["geoeffnet"].append(datetime.now().isoformat(timespec="seconds"))
                            _TAB_HAUPT["puls_at"] = 0.0             # Kennungen bald neu lesen → Haupt-Tab wechselt ins Puls-Chrome
                        g2 = f"{g2} → {'geöffnet' if ok else 'NICHT geöffnet'}: {msg}"
                    grund = grund or g2
                if grund != TAB_NL["grund"]:
                    if grund:
                        print(f"[tab-neuladen] {grund}", flush=True)
                    TAB_NL.update(grund=grund, at=jetzt)
        except Exception as e:
            print(f"[tab-neuladen] Fehler: {type(e).__name__}: {e}", flush=True)
        time.sleep(TAB_NL_TAKT_S + random.random() * 10)


# ══ TAB WECKEN (F1, 30.10.2026, Befund ECHO-AUSSETZER: Chris pc-c19p2l 16:57–19:03 Dubai „kein Prophos-Tab … Chrome läuft, aber ohne
# aktiven Prophos-Tab", 29.10. elf solche Episoden auf vier PCs, seit 27./28.10. gehäuft — der Prophos-Tab liegt im Puls-Chrome hinter
# TradingView, Chrome friert/verwirft ihn; Neuladen per Fenstertitel findet ihn nicht, ein zweiter Tab ist verboten). Master: „Prophos-Tab
# im Puls-Chrome per /json/activate wecken, danach TradingView gestreut zurück nach vorn. Gleiche Riegel wie TAB_NL". Weg: CDP-Liste des
# Puls-Chrome (127.0.0.1:9333) → Seite mit localhost:5000 → /json/activate (holt sie nach vorn; ein verworfener Tab lädt dabei neu) → 4–7 s
# (gestreut) auf die erste Abfrage beim Panel warten, sonst noch einmal 5–8 s → den zuvor vordersten TradingView-Tab wieder aktivieren.
# Unter TV_ORDER_LOCK (Puls kann nicht dazwischen). Kein Klick, keine Taste. Scheitert es: Spur + Fehlerfoto (Bildschirm). Seit Finns
# Ergänzung (30.10.2026) ist Wecken Stufe 1 der Stufen-Heilung unten (tab_heil_stufe). ══
TAB_WECK_CDP = "http://127.0.0.1:9333"
_PROPHOS_URL_RE = re.compile(r"^http://(localhost|127\.0\.0\.1):5000(/|$)")
# STUFEN (Master 30.10.2026 nach Finn: „Oft verliert der Prophos-Tab die Verbindung und wird als inaktiv angezeigt. Dann muss ich in den PC
# rein und einmal neu laden, meistens reicht das."): Problem = Tab fragt ≥ 3 min nicht ODER (angemeldet) seit ≥ 3 min kein Supabase-
# Schreiben ODER Realtime ≥ 5 min getrennt. Stufe 1 wecken (/json/activate), 2 nach 60 s weiter Problem → Page.reload per CDP, 3 nach
# weiteren 3 min → Tab schließen und frisch im EIGENEN Fenster öffnen, 4 nach weiteren 3 min → Spur + ⚪ an die Master-IDs (Railway
# /pc/tab-heil-spur). Jede Stufe nur mit den Riegeln (Server-Riegel: Signal/Start ≤ 5 min/Hedge-Lauf; Puls/MT5-Order; 120 s ohne Eingabe),
# sonst wartet sie; eine neue Folge höchstens je TAB_HEIL_ABSTAND_S. Ein laufender Trade bleibt unberührt — nur der Tab lädt neu.
TAB_HEIL_START_S = 3 * 60
TAB_HEIL_SB_S = 3 * 60
TAB_HEIL_RT_S = 5 * 60
TAB_HEIL_NEULADEN_NACH_S = 60
TAB_HEIL_OEFFNEN_NACH_S = 3 * 60
TAB_HEIL_MELDEN_NACH_S = 3 * 60
TAB_HEIL_ABSTAND_S = 10 * 60
TAB_HEIL = {"ep": None, "letzte": 0.0, "grund": ""}
# ══ FS1 TAB ANTWORTET BEIM START NICHT (10.11.2026, Master nach FS1: „Prophos-Tab antwortet nicht / Tab neu geladen“ 27 Pläne auf 10 PCs in 7 Handelstagen,
# von keinem Fix erfasst, Ursache nicht belegt). (a) Puls fragt bei tab_nicht_erreichbar GET /api/tab-zustand und schreibt den Zustand in Spur und Meldung
# (letzte Abfrage, sichtbar/Hintergrund, Ladezeit, letzte Puls-Abfrage, Heil-Stufe, letztes Neuladen). (b) Dieselbe Abfrage mit anlass=tab_nicht_erreichbar
# startet die VORHANDENE Stufen-Heilung sofort (TAB_HEIL: wecken → nach 60 s neu laden → neu öffnen → melden), auch wenn der Tab noch fragt (dann greift die
# 3-min-Schwelle nie) und ohne den 10-min-Abstand vor Stufe 1. Neu laden/öffnen in diesem Weg NUR ohne offenen Trade der IDs dieses PCs (Railway offen_n,
# fehlt = nicht) — wecken (Tab kurz nach vorn, TradingView zurück) darf immer, mit den bisherigen Riegeln. Fertig, sobald eine Stufe gelingt, spätestens
# TAB_HEIL_SOFORT_S. Den einen schnellen Neustart des Plans macht der Tab (prophos.html sfBehoben, tab_n).
TAB_HEIL_SOFORT_S = 10 * 60
TAB_HEIL_SOFORT = {"at": 0.0, "plan": "", "erledigt": False, "geheilt": False}   # geheilt = eine Stufe gelang (nicht: nur gemeldet)


def tab_heil_sofort_lage(sofort, jetzt):
    """REIN RECHNEND (testbar): (Dauer in s | None, Klartext) des Sofort-Auslösers aus Puls (tab_nicht_erreichbar)."""
    at = float((sofort or {}).get("at") or 0.0)
    if not at or (sofort or {}).get("erledigt") or jetzt - at > TAB_HEIL_SOFORT_S or jetzt < at:
        return None, ""
    if (sofort or {}).get("bis") and jetzt > float(sofort["bis"]):   # F-B: Vorflug-Befund nur bis zum Start
        return None, ""
    pl = str((sofort or {}).get("plan") or "")[:8]
    if (sofort or {}).get("grund"):   # F-B (11.11.2026): Tab-Vorflug vor dem Start nennt seinen eigenen Befund
        return jetzt - at, str(sofort["grund"])[:200]
    return jetzt - at, f"Prophos-Tab antwortete beim Puls-Start nicht{' (Plan ' + pl + ')' if pl else ''}"


# ══ F-B TAB-VORFLUG (11.11.2026, Master nach FS2; K4 „Prophos-Tab antwortet nicht“ 27 Pläne/7 Tage auf 10 PCs) ══
# Heute merkt erst der Puls-Lauf selbst (order_bot _tab_wache_pruefen „vor dem Lauf“), dass der Tab schläft — dann ist der Start verloren und kommt frühestens
# 2–4 min später (FS1 sfBehoben). Jetzt prüft das Panel 2–3 min (gewürfelt) VOR jedem Start der IDs dieses PCs die Lebenszeichen des Tabs mit strengeren
# Schwellen als die Stufen-Heilung (still ≥ 30 s statt 3 min, ohne Login, Supabase ≥ 90 s, Realtime ≥ 2 min) und startet bei rot die VORHANDENE Heilung
# sofort (TAB_HEIL_SOFORT, Riegel wie FS1: wecken immer, neu laden/öffnen nur ohne offenen Trade). Startzeiten: Railway /code/tab-stand „next_start_um“
# (ISO oder Liste); fehlt das Feld (Railway noch ohne), passiert nichts. ECHTER PING: /api/instances gibt „vorflug_ping“ mit; schickt der Tab die Marke als
# vpong zurück, verlangt der Vorflug sie binnen TAB_VF_PONG_S. Ein Tab, der das (noch) nicht kann, wird nur an den Lebenszeichen gemessen.
TAB_VF_FENSTER_S = (120.0, 180.0)   # Ziel-Abstand vor dem Start, je Start gewürfelt (Jitter-Regel)
TAB_VF_ZU_SPAET_S = 45.0            # näher am Start nie mehr (der Puls-Lauf beginnt gleich)
TAB_VF_STILL_S = 30.0               # der Tab fragt sonst alle ~5 s
TAB_VF_SB_S = 90
TAB_VF_RT_S = 120
TAB_VF_PONG_S = 20.0
TAB_VF_PONG_FRISCH_S = 60.0
TAB_VORFLUG = {"ziel": {}, "erledigt": {}, "marke": None, "marke_at": 0.0, "pong_at": 0.0, "vpong_tid": "", "vpong_at": 0.0}


def tab_kann_pong(vf, haupt_tid, jetzt):
    """REIN RECHNEND (testbar, Prüfer S4): schickt der AKTUELLE Haupt-Tab vpong (zuletzt ≤ TAB_VF_PONG_FRISCH_S)?"""
    return bool(haupt_tid) and str((vf or {}).get("vpong_tid") or "") == str(haupt_tid) and jetzt - float((vf or {}).get("vpong_at") or 0) <= TAB_VF_PONG_FRISCH_S


def tab_vorflug_riegel(riegel, sofort, stufe_jetzt):
    """REIN RECHNEND (testbar, F-B Prüfer M2): Railway meldet ±5 min um jeden Start „Start in ≤ 5 min“ — damit hätte der Vorflug (T−2…3 min) nie geweckt.
    Nur im Vorflug-Sofort-Weg und nur für Stufe 1 (wecken: Tab kurz nach vorn, kein Neuladen) fällt GENAU dieser Riegel weg; jeder andere Riegel
    (Puls/Signal läuft, Hedge, Claim …) und alle weiteren Stufen bleiben gesperrt."""
    r = str(riegel or "").strip()
    if r == "Start in ≤ 5 min" and int(stufe_jetzt or 0) == 0 and str((sofort or {}).get("grund") or "").startswith("Vorflug:"):
        return ""
    return r


def tab_vorflug_starts(stand):
    """REIN RECHNEND (testbar): /code/tab-stand → Startzeiten (Unix-s) aus „next_start_um“ (ISO-Text oder Liste); ungültig/fehlend → []."""
    roh = (stand or {}).get("next_start_um") if isinstance(stand, dict) else None
    liste = roh if isinstance(roh, list) else [roh] if roh else []
    out = []
    for x in liste[:20]:
        try:
            t = re.sub(r"(\.\d{1,6})\d*", lambda m: m.group(1).ljust(7, "0"), str(x).strip().replace("Z", "+00:00"))   # Prüfer H8: Bruchteile 1–6 Stellen
            d = datetime.fromisoformat(t)
            out.append((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp())   # ohne Zone = UTC (Railway)
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def tab_vorflug_faellig(starts, jetzt, erledigt, ziele):
    """REIN RECHNEND (testbar): der erste Start, dessen Vorflug JETZT dran ist → Startzeit | None. Dran: noch nicht erledigt, Abstand ≤ gewürfeltes Ziel
    (ziele[start], sonst Fenster-Mitte) und ≥ TAB_VF_ZU_SPAET_S."""
    for st in starts or ():
        d = float(st) - float(jetzt)
        ziel = float((ziele or {}).get(st) or sum(TAB_VF_FENSTER_S) / 2)
        if st not in (erledigt or {}) and TAB_VF_ZU_SPAET_S <= d <= ziel:
            return st
    return None


def tab_vorflug_urteil(still_s, login, sb_s, rt_aus_s, pong):
    """REIN RECHNEND (testbar): Lebenszeichen des Haupt-Tabs → (rot, Klartext). pong: True/False = Vorflug-Marke beantwortet/nicht, None = Tab kann es nicht."""
    if still_s is None:
        return True, "kein Prophos-Tab hat sich beim Panel gemeldet"
    if still_s >= TAB_VF_STILL_S:
        return True, f"Prophos-Tab fragt seit {int(still_s)} s nicht (sonst alle ~5 s)"
    if login is False:
        return True, "Prophos-Tab nicht angemeldet (claimt keine Starts)"
    if login and sb_s is not None and sb_s >= TAB_VF_SB_S:
        return True, f"Prophos-Tab ohne Supabase-Verbindung seit {int(sb_s)} s"
    if login and rt_aus_s is not None and rt_aus_s >= TAB_VF_RT_S:
        return True, f"Prophos-Tab ohne Realtime seit {int(rt_aus_s)} s"
    if pong is False:
        return True, f"Prophos-Tab beantwortet die Vorflug-Marke nicht binnen {int(TAB_VF_PONG_S)} s"
    return False, "Prophos-Tab antwortet" + (" (Vorflug-Marke beantwortet)" if pong else "")


def _tab_vorflug_schritt(pc):
    """F-B: eine Runde im Tab-Wächter. Nie werfen; ohne frischen Tab-Stand oder ohne Startzeiten nichts."""
    stand, at = TAB_NL.get("stand"), float(TAB_NL.get("stand_at") or 0.0)
    jetzt = time.time()
    if not isinstance(stand, dict) or jetzt - at > 180:
        return
    starts = tab_vorflug_starts(stand)
    for k in [k for k in list(TAB_VORFLUG["ziel"]) if k < jetzt - 3600]:
        TAB_VORFLUG["ziel"].pop(k, None)
        TAB_VORFLUG["erledigt"].pop(k, None)
    for st in starts:
        TAB_VORFLUG["ziel"].setdefault(st, random.uniform(*TAB_VF_FENSTER_S))
    st = tab_vorflug_faellig(starts, jetzt, TAB_VORFLUG["erledigt"], TAB_VORFLUG["ziel"])
    if st is None or not _browser_und_mt5_frei():   # nie während eines Puls-Laufs / einer MT5-Order — dann die nächste Runde
        return
    TAB_VORFLUG["erledigt"][st] = jetzt
    pong = None
    if tab_kann_pong(TAB_VORFLUG, _TAB_OEFFNEN.get("tid"), jetzt):
        TAB_VORFLUG.update(marke=f"{int(jetzt * 1000):x}-{random.randint(0, 1 << 30):x}", marke_at=jetzt, pong_at=0.0)
        while time.time() - jetzt < TAB_VF_PONG_S and TAB_VORFLUG["pong_at"] < TAB_VORFLUG["marke_at"]:
            time.sleep(0.8 + random.random() * 0.6)
        pong = TAB_VORFLUG["pong_at"] >= TAB_VORFLUG["marke_at"]
        TAB_VORFLUG["marke"] = None
    still = time.time() - max(float(_TAB_OEFFNEN.get("zuletzt") or 0.0), float(_TAB_OEFFNEN.get("start") or 0.0))   # wie der Wächter (still0)
    rot, grund = tab_vorflug_urteil(still, _TAB_OEFFNEN.get("login"), _TAB_OEFFNEN.get("sb_s"), _TAB_OEFFNEN.get("rt_aus_s"), pong)
    txt = f"Vorflug Tab (Start in {int(st - time.time())} s): {grund}"
    print(f"[tab-vorflug] {txt}", flush=True)
    if rot:
        # Prüfer H7: „nicht angemeldet“ heilt kein Wecken/Neuladen → nur melden. Prüfer H6: einen offenen FS1-Eintrag nie überschreiben.
        # bis = Startzeit: nach dem Start gilt der Vorflug-Befund nicht mehr (dann übernimmt FS1, falls der Tab beim Start nicht antwortet).
        if _TAB_OEFFNEN.get("login") is not False and tab_heil_sofort_lage(TAB_HEIL_SOFORT, time.time())[0] is None:
            TAB_HEIL_SOFORT.update(at=time.time(), plan="", erledigt=False, geheilt=False, grund=f"Vorflug: {grund}", bis=float(st))
        if pc:
            _tab_stand_holen(pc, txt[:200])


def tab_heil_sofort_riegel(stufe_jetzt, stand):
    """REIN RECHNEND (testbar): zusätzlicher Riegel im Sofort-Weg. Stufe 1 (wecken) frei; ab Stufe 2 (neu laden/öffnen) nur, wenn Railway für die IDs dieses
    PCs offen_n == 0 meldet. Fehlt die Zahl (alter Railway-Stand, nicht lesbar) → gesperrt (fail-closed)."""
    if int(stufe_jetzt or 0) < 1:
        return ""
    n = (stand or {}).get("offen_n") if isinstance(stand, dict) else None
    if not isinstance(n, int) or isinstance(n, bool):
        return "offene Trades nicht lesbar — kein Neuladen (nur wecken)"
    return f"Trade offen ({n}) — kein Neuladen (nur wecken)" if n > 0 else ""


def tab_zustand_ausgabe(jetzt, oeffnen, heil, sofort, nl, klick_at):
    """REIN RECHNEND (testbar): Tab-Zustand für die Puls-Spur (GET /api/tab-zustand). Nur Zahlen/Wörter, keine Kennungen."""
    o = oeffnen or {}
    z = float(o.get("zuletzt") or 0.0)
    ep = (heil or {}).get("ep") or {}
    ka = float(klick_at or 0.0)
    gel = o.get("geladen")
    return {"ok": True, "still_s": round(jetzt - z, 1) if z else None, "login": o.get("login"), "sb_s": o.get("sb_s"), "rt_aus_s": o.get("rt_aus_s"),
            "vis": o.get("vis") or "", "geladen_vor_s": int(jetzt - gel) if isinstance(gel, int) and 0 < gel <= jetzt else None,
            "puls_abfrage_vor_s": round(jetzt - ka, 1) if ka else None, "heil_stufe": int(ep.get("stufe") or 0) if ep else 0,
            "heil_grund": str((heil or {}).get("grund") or "")[:160],
            "neuladen": str((nl or {}).get("ergebnis") or "")[:120],
            "neuladen_vor_s": int(jetzt - float((nl or {}).get("ergebnis_at") or 0)) if (nl or {}).get("ergebnis_at") else None,
            "sofort_vor_s": int(jetzt - float((sofort or {}).get("at") or 0)) if (sofort or {}).get("at") else None,
            # Prüfer FS1 Runde 2 (S2): nur eine GELUNGENE Stufe der jüngsten Folge (≤ TAB_HEIL_SOFORT_S alt), nie „nur gemeldet“
            "sofort_geheilt": bool((sofort or {}).get("at") and (sofort or {}).get("geheilt") and 0 <= jetzt - float((sofort or {}).get("at") or 0) <= TAB_HEIL_SOFORT_S)}


def tab_heil_lage(still_s, login, sb_s, rt_aus_s):
    """REIN RECHNEND (testbar): (Dauer des Problems in s | None, Klartext). still_s = Sekunden ohne Abfrage beim Panel."""
    if still_s is not None and still_s >= TAB_HEIL_START_S:
        return still_s, f"Prophos-Tab fragt seit {int(still_s // 60)} min nicht (eingefroren/verworfen)"
    if login and sb_s is not None and sb_s >= TAB_HEIL_SB_S:
        return sb_s, f"Prophos-Tab ohne Supabase-Verbindung seit {int(sb_s // 60)} min (kein Schreiben)"
    if login and rt_aus_s is not None and rt_aus_s >= TAB_HEIL_RT_S:   # ohne Login baut der Tab keinen Realtime-Kanal auf (S2)
        return rt_aus_s, f"Prophos-Tab ohne Realtime seit {int(rt_aus_s // 60)} min"
    return None, ""


def tab_heil_stufe(ep, problem_s, problem, jetzt, riegel, lock_frei, idle_s, letzte):
    """REIN RECHNEND (testbar): (aktion, grund, ep_neu). aktion ∈ '' | 'wecken' | 'neuladen' | 'neu_oeffnen' | 'melden'.
    ep = {stufe, at, start} der laufenden Folge oder None; problem_s None = Tab gesund → Folge vorbei (ep None)."""
    if problem_s is None:
        return "", "", None
    stufe, at = int((ep or {}).get("stufe") or 0), float((ep or {}).get("at") or 0.0)
    if stufe == 0:
        if letzte and jetzt - letzte < TAB_HEIL_ABSTAND_S:
            return "", f"{problem} — wartet: letzte Heil-Folge vor {int((jetzt - letzte) // 60)} min (höchstens 1 je {TAB_HEIL_ABSTAND_S // 60} min)", ep
        naechste, text = "wecken", "Tab wecken"
    elif stufe == 1:
        if jetzt - at < TAB_HEIL_NEULADEN_NACH_S:
            return "", "", ep
        naechste, text = "neuladen", "Tab neu laden"
    elif stufe == 2:
        if jetzt - at < TAB_HEIL_OEFFNEN_NACH_S:
            return "", "", ep
        naechste, text = "neu_oeffnen", "Tab schließen und im eigenen Fenster neu öffnen"
    elif stufe == 3:
        if jetzt - at < TAB_HEIL_MELDEN_NACH_S:
            return "", "", ep
        return "melden", f"{problem} — Stufen 1–3 ohne Erfolg → Meldung an die Master-IDs", dict(ep, stufe=4, at=jetzt)
    else:
        return "", f"{problem} — Stufen 1–3 ohne Erfolg, gemeldet", ep
    if riegel:
        return "", f"{problem} — Stufe {stufe + 1} wartet: {riegel}", ep
    if not lock_frei:
        return "", f"{problem} — Stufe {stufe + 1} wartet: Puls/MT5-Order läuft", ep
    if idle_s is not None and idle_s < TAB_NL_IDLE_S:
        return "", f"{problem} — Stufe {stufe + 1} wartet: am PC wird gerade gearbeitet (letzte Eingabe vor {int(idle_s)} s)", ep
    start = float((ep or {}).get("start") or jetzt)
    return naechste, f"{problem} → Stufe {stufe + 1}: {text}", {"stufe": stufe + 1, "at": jetzt, "start": start}


def cdp_prophos_ziele(liste, url_merk=""):
    """REIN RECHNEND (testbar): CDP-Seitenliste (/json/list, vorderste zuerst) → (Prophos-Seite | None, TradingView-Seite | None).
    Prophos = Seite auf localhost:5000 (die zuletzt gemeldete Adresse zuerst); TradingView = die vorderste TradingView-Seite."""
    seiten = [t for t in (liste or []) if isinstance(t, dict) and t.get("type") == "page" and t.get("id")]
    pro = [t for t in seiten if _PROPHOS_URL_RE.match(str(t.get("url") or ""))]
    # Tabs im „nur ansehen"-Modus (?neben=1, HAUPT-TAB 30.10.2026) zuletzt — gemeint ist immer der Haupt-Tab
    pro.sort(key=lambda t: (1 if "neben=1" in str(t.get("url") or "") else 0, 0 if url_merk and str(t.get("url") or "").startswith(url_merk) else 1))
    tv = [t for t in seiten if "tradingview.com" in str(t.get("url") or "")]
    return (pro[0] if pro else None), (tv[0] if tv else None)


def _cdp_get(pfad, timeout=2.0):
    import urllib.request
    with urllib.request.urlopen(TAB_WECK_CDP + pfad, timeout=timeout) as r:
        roh = r.read().decode("utf-8", "replace")
    try:
        return json.loads(roh)
    except ValueError:
        return roh


def _panel_fehlerfoto(weg, code):
    """Fehlerfoto über den Bot (order_bot.fehlerfoto_anstossen, entkoppelt, eigener Deckel) — frischer Prozess. → Text für die Spur."""
    code_py = ("import json, order_bot; b, g = order_bot.fehlerfoto_anstossen(%r, False, %r); print(json.dumps([b, g]))" % (weg, code))
    try:
        r = subprocess.run([sys.executable, "-c", code_py], cwd=HERE, capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        b, g = json.loads((r.stdout or "").strip().splitlines()[-1])
        return f"Fehlerfoto {b}" if b else f"kein Fehlerfoto: {g}"
    except Exception as e:
        return f"kein Fehlerfoto ({type(e).__name__})"


def _prophos_tab_wecken():
    """Stufe 1 → (ok, Klartext). Siehe Block-Kopf."""
    if not TV_ORDER_LOCK.acquire(blocking=False):
        return False, "Puls läuft gerade im Browser — nächster Versuch später"
    try:
        if not _browser_und_mt5_frei(tv_eigen=True):
            return False, "MT5-Order/Polar läuft gerade — nächster Versuch später"
        try:
            liste = _cdp_get("/json/list")
        except Exception as e:
            return False, f"Puls-Chrome per CDP nicht erreichbar ({type(e).__name__}) — Prophos-Tab liegt wohl in einem anderen Chrome: am PC anklicken"
        pro, tv = cdp_prophos_ziele(liste if isinstance(liste, list) else [], _TAB_OEFFNEN.get("url") or "")
        if not pro:
            return False, "kein Prophos-Tab im Puls-Chrome (CDP) — am PC den Prophos-Tab anklicken"
        t0 = time.time()
        _cdp_get(f"/json/activate/{pro['id']}")
        time.sleep(4 + random.random() * 3)
        if _TAB_OEFFNEN["zuletzt"] < t0:
            time.sleep(5 + random.random() * 3)
        wach = _TAB_OEFFNEN["zuletzt"] >= t0
        zurueck = ""
        if tv and tv.get("id") != pro.get("id"):
            try:
                _cdp_get(f"/json/activate/{tv['id']}")
                zurueck = ", TradingView wieder vorn"
            except Exception as e:
                zurueck = f", TradingView NICHT zurück ({type(e).__name__})"
        if wach:
            return True, f"Prophos-Tab geweckt (fragt wieder nach {time.time() - t0:.0f} s){zurueck}"
        return False, f"Prophos-Tab aktiviert, fragt aber nicht ({time.time() - t0:.0f} s){zurueck}"
    except Exception as e:
        return False, f"Wecken fehlgeschlagen: {type(e).__name__}: {e}"
    finally:
        TV_ORDER_LOCK.release()


def _prophos_tab_neuladen_cdp(stand=None):
    """Stufe 2 → (ok, Klartext): Prophos-Seite im Puls-Chrome per CDP Page.reload (ignoreCache) — über order_bot._CdpVerbindung in einem
    frischen Prozess (nur 127.0.0.1:9333), danach gestreut auf die erste Abfrage warten. stand = Tab-Stand von Railway: nur wenn der PC stumm ist
    (cdp_vorn_erlaubt) holt er den Tab vorher per activate nach vorn und danach die Seite zurück, die vorher vorn war; sonst lädt er im Hintergrund
    (S2-Stopp 03.11.2026: TradingView/TopstepX blieb bei offenem Plan 6–19 s verdeckt). Nie einen „nur ansehen“-Tab (?neben=1)."""
    if not TV_ORDER_LOCK.acquire(blocking=False):
        return False, "Puls läuft gerade im Browser — nächster Versuch später"
    gehalten = True
    try:
        if not _browser_und_mt5_frei(tv_eigen=True):
            return False, "MT5-Order/Polar läuft gerade — nächster Versuch später"
        liste = _cdp_get("/json/list")
        liste = liste if isinstance(liste, list) else []
        pro, _tv = cdp_prophos_ziele(liste, _TAB_OEFFNEN.get("url") or "")
        if not pro or not pro.get("webSocketDebuggerUrl"):
            return False, "Prophos-Tab im Puls-Chrome (CDP) nicht verbindbar"
        if "neben=1" in str(pro.get("url") or ""):
            # S2-Stopp 03.11.2026: im Puls-Chrome liegt nur ein „nur ansehen“-Tab — der Haupt-Tab ist woanders und bliebe alt
            return False, "im Puls-Chrome nur ein „nur ansehen“-Tab (?neben=1) — Haupt-Tab liegt woanders, nicht per CDP geladen"
        vorn = cdp_vorn_erlaubt(stand, scharf_konto_fest())
        vorher = cdp_rueckweg_seiten(liste, pro.get("id")) if vorn else []
        t0 = time.time()
        fehler = ""
        try:
            if vorn:
                _cdp_get(f"/json/activate/{pro['id']}")
            code = ("import sys, order_bot; c = order_bot._CdpVerbindung(sys.argv[1]); "
                    "c.rufe('Page.reload', {'ignoreCache': True}, timeout=8); c.zu(); print('ok')")
            r = subprocess.run([sys.executable, "-c", code, pro["webSocketDebuggerUrl"]], cwd=HERE, capture_output=True, text=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if "ok" not in (r.stdout or ""):
                fehler = f"Page.reload ohne Antwort ({(r.stderr or '').strip()[-120:]})"
            if not vorn:
                # im Hintergrund geladen: der Browser bleibt, wie er war — Puls nicht während des Wartens auf die erste Abfrage sperren
                TV_ORDER_LOCK.release()
                gehalten = False
            if not fehler:
                time.sleep(6 + random.random() * 4)
                if _TAB_OEFFNEN["zuletzt"] < t0:
                    time.sleep(5 + random.random() * 4)
        finally:
            zurueck = "" if vorn else ", im Hintergrund (offener Plan oder Riegel — nicht nach vorn geholt)"
            if vorher:
                # Rückweg auch nach einem Fehler: die Seiten, die vorher vorn waren (TradingView, TopstepX …), älteste zuerst — nicht pauschal TradingView
                name = "TradingView" if "tradingview.com" in str(vorher[0].get("url") or "") else (str(vorher[0].get("title") or "")[:30] or "vorige Seite")
                try:
                    for t in reversed(vorher):
                        _cdp_get(f"/json/activate/{t['id']}")
                    zurueck = f", {name} wieder vorn"
                except Exception as e:
                    zurueck = f", {name} NICHT zurück ({type(e).__name__})"
        if fehler:
            return False, fehler + zurueck
        wach = _TAB_OEFFNEN["zuletzt"] >= t0
        return wach, f"Prophos-Tab neu geladen, {'fragt wieder' if wach else 'fragt noch nicht'} ({time.time() - t0:.0f} s){zurueck}"
    except Exception as e:
        return False, f"Neu laden fehlgeschlagen: {type(e).__name__}: {e}"
    finally:
        if gehalten:
            TV_ORDER_LOCK.release()


def _prophos_tab_neu_oeffnen(still_s=None):
    """Stufe 3 → (ok, Klartext): unter TV_ORDER_LOCK den alten Prophos-Tab im Puls-Chrome schließen (/json/close) und erst, wenn er
    nachweislich aus der CDP-Liste verschwunden ist, frisch im EIGENEN Fenster öffnen (Prüfer S2: nie zwei Prophos-Tabs). Ist kein alter
    Tab im Puls-Chrome zu finden, nur dann öffnen, wenn auch kein Tab mehr beim Panel fragt (still_s ≥ TAB_HEIL_START_S)."""
    if not TV_ORDER_LOCK.acquire(blocking=False):
        return False, "Puls läuft gerade im Browser — nächster Versuch später"
    try:
        if not _browser_und_mt5_frei(tv_eigen=True):
            return False, "MT5-Order/Polar läuft gerade — nächster Versuch später"
        liste = _cdp_get("/json/list")
        pro, _tv = cdp_prophos_ziele(liste if isinstance(liste, list) else [], _TAB_OEFFNEN.get("url") or "")
        if pro:
            _cdp_get(f"/json/close/{pro['id']}")
            weg = False
            for _ in range(6):
                time.sleep(0.8 + random.random() * 0.6)
                l2 = _cdp_get("/json/list")
                if not any(isinstance(t, dict) and t.get("id") == pro["id"] for t in (l2 if isinstance(l2, list) else [])):
                    weg = True
                    break
            if not weg:
                return False, "alter Prophos-Tab ließ sich nicht schließen — kein zweiter Tab geöffnet"
        elif still_s is None or still_s < TAB_HEIL_START_S:
            return False, "kein alter Prophos-Tab im Puls-Chrome, aber ein Tab fragt noch beim Panel — kein zweiter Tab geöffnet"
        ok, msg = _tab_oeffnen(_TAB_OEFFNEN.get("url") or TAB_URL, lock_gehalten=True)
        if ok:
            _TAB_OEFFNEN["geoeffnet"].append(datetime.now().isoformat(timespec="seconds"))
            _TAB_OEFFNEN["geoeffnet_at"] = time.time()
        return ok, ("alter Tab geschlossen, " if pro else "") + msg
    except Exception as e:
        return False, f"Neu öffnen fehlgeschlagen: {type(e).__name__}: {e}"
    finally:
        TV_ORDER_LOCK.release()


def _tab_heil_melden(grund, art=""):
    """Stufe 4: ⚪ an die Master-IDs über Railway POST /pc/tab-heil-spur (X-Code-Token). art 'puls_login' = Prophos im Puls-Chrome nicht
    angemeldet (Railway: einmal je PC). Wirft nie."""
    import urllib.request
    tok = code_token()
    if not tok:
        return
    try:
        body = json.dumps({"grund": str(grund)[:240], "art": str(art or "")[:20]}).encode("utf-8")
        req = urllib.request.Request(CODE_QUELLE + "/pc/tab-heil-spur", data=body, method="POST",
                                     headers={"X-Code-Token": tok, "Content-Type": "application/json", "User-Agent": "prophos-panel"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print(f"[tab-heilen] Meldung nicht gesendet ({type(e).__name__})", flush=True)


def _tab_heil_schritt(pc, still0):
    """Eine Runde der Stufen-Heilung. → True = diese Runde behandelt (der übrige Wächter-Lauf entfällt), False = nichts zu tun bzw. kein
    Prophos-Tab im Puls-Chrome (dann der bisherige Weg: Fenster-Neuladen / Öffnen / „anklicken")."""
    jetzt = time.time()
    dauer, problem = tab_heil_lage(still0, _TAB_OEFFNEN.get("login"), _TAB_OEFFNEN.get("sb_s"), _TAB_OEFFNEN.get("rt_aus_s"))
    sofort = False
    if dauer is None:
        dauer, problem = tab_heil_sofort_lage(TAB_HEIL_SOFORT, jetzt)      # FS1: Puls meldete tab_nicht_erreichbar
        sofort = dauer is not None
    if dauer is None:
        if TAB_HEIL["ep"]:
            g = "Prophos-Tab wieder gesund" + (f" (nach Stufe {TAB_HEIL['ep'].get('stufe')})" if TAB_HEIL["ep"].get("stufe") else "")
            print(f"[tab-heilen] {g}", flush=True)
            if pc:
                _tab_stand_holen(pc, g)
        TAB_HEIL["ep"] = None
        return False
    if not TAB_HEIL["ep"]:
        try:
            liste = _cdp_get("/json/list")
        except Exception:
            return False
        pro0 = cdp_prophos_ziele(liste if isinstance(liste, list) else [])[0]
        # nur den HAUPT-Tab heilen (S2 30.10.2026): liegt im Puls-Chrome nur ein „nur ansehen"-Tab (z. B. dort nicht angemeldet) bzw. liegt
        # der Haupt-Tab nachweislich woanders → bisheriger Weg, nie den falschen Tab wecken/neu laden/schließen
        if not pro0 or "neben=1" in str(pro0.get("url") or "") or (_TABS.get(_TAB_HAUPT["tid"]) or {}).get("puls") is False:
            return False                     # Prophos-Tab nicht im Puls-Chrome: bisheriger Weg
    stand = _tab_stand_holen(pc, TAB_HEIL["grund"]) if pc else None
    if isinstance(stand, dict) and stand.get("ok"):
        TAB_NL.update(stand=stand, stand_at=time.time())
    riegel = str((stand or {}).get("riegel") or "").strip() if isinstance(stand, dict) else "Tab-Stand von Railway nicht lesbar"
    if sofort:
        riegel = tab_vorflug_riegel(riegel, TAB_HEIL_SOFORT, int((TAB_HEIL["ep"] or {}).get("stufe") or 0))   # F-B (Prüfer M2)
    if sofort and not riegel:
        riegel = tab_heil_sofort_riegel(int((TAB_HEIL["ep"] or {}).get("stufe") or 0), stand)
    aktion, grund, ep_neu = tab_heil_stufe(TAB_HEIL["ep"], dauer, problem, jetzt, riegel, _browser_und_mt5_frei(), _win_leerlauf_s(),
                                           0.0 if sofort and int((TAB_HEIL["ep"] or {}).get("stufe") or 0) == 0 else TAB_HEIL["letzte"])
    if aktion == "wecken":
        TAB_HEIL["letzte"] = jetzt
    TAB_HEIL["ep"] = ep_neu or {"stufe": 0, "at": 0.0, "start": jetzt}
    if sofort and not aktion:
        # Prüfer FS1 (SOLLTE 4): wartet der Sofort-Weg (Riegel, Lock, Eingabe, Stufen-Takt), läuft der übrige Wächter weiter (Haupt-Tab, Öffnen, Build-Neuladen)
        if grund and grund != TAB_HEIL["grund"]:
            print(f"[tab-heilen] {grund}", flush=True)
            TAB_HEIL["grund"] = grund
        return False
    if aktion:
        tun = {"wecken": _prophos_tab_wecken, "neuladen": lambda: _prophos_tab_neuladen_cdp(stand),
               "neu_oeffnen": lambda: _prophos_tab_neu_oeffnen(still0)}.get(aktion)
        if tun:
            ok, msg = tun()
            grund = f"{grund} → {'ok' if ok else 'NICHT ok'}: {msg}"
            if not ok:
                grund += " — " + _panel_fehlerfoto(f"panel_tab_{aktion}", "tab_heilen")
            elif sofort:
                TAB_HEIL_SOFORT.update(erledigt=True, geheilt=True)   # FS1: eine Stufe gelang — der Tab startet den Plan selbst einmal neu
        else:
            _tab_heil_melden(grund)
            if sofort:
                TAB_HEIL_SOFORT["erledigt"] = True
    if grund and grund != TAB_HEIL["grund"]:
        print(f"[tab-heilen] {grund}", flush=True)
        TAB_HEIL["grund"] = grund
        if pc:
            _tab_stand_holen(pc, grund)
    return True


# ══ EA-SELBSTHEILUNG OHNE KNOPF (F2, 30.10.2026, Befund ECHO-AUSSETZER: Jacob pc-auzre5 …2655, Echo MIT Fusion-Hedge offen, Lese-EA
# eingefroren → Copier ohne Master-Position, kein Hedge; _heal_ea lief nur nach „Terminal starten"). Master: „Panel ruft _heal_ea selbst,
# wenn der Snapshot einer gebrauchten Instanz > 60 s eingefroren ist (offene Positionen/Hedges oder offener Echo-Plan). Höchstens 1× je
# 15 min je Instanz, gestreut, nie während eines Puls-Laufs oder einer offenen MT5-Order." Eingefroren = Snapshot-Datei des Lese-EA älter
# als EA_FROST_S (wie copier.master_status, dort 15 s). Gebraucht = Positionen/Hedges im letzten Copier-Stand ODER Master-Login unter den
# offenen Echo-Plänen dieses PCs (Railway /code/tab-stand echo_logins, Stand ≤ 5 min aus dem Tab-Wächter). Die Heilung selbst ist
# _heal_ea (Terminal beenden, EA per Profil/StartUp aufziehen, neu starten — Positionen liegen beim Broker); die MT5-Order-Sperre der
# Instanz bleibt dabei gehalten. 5 min danach noch eingefroren → Spur + Fehlerfoto. Railway meldet 🔴 erst nach ECHO_FROST_KARENZ_S. ══
EA_FROST_S = 60
EA_FROST_TAKT_S = 30
EA_FROST_ABSTAND_S = 15 * 60
EA_FROST_NACH_S = 5 * 60
EA_FROST_MAX_S = 12 * 3600      # länger still = die Instanz läuft auf diesem PC gar nicht (Login auf zwei PCs eingetragen) → nie heilen
EA_STATUS_FRISCH_S = 60         # Positionen/Hedges zählen nur aus einem frischen Copier-Stand (alte Statusdatei = kein Beleg)
EA_FROST = {}   # config_file → {"letzter": ts, "geprueft": bool, "grund": str}
EA_FROST_HAELT = set()   # config_files, deren Order-Sperre die EA-Heilung gerade hält (Order/Close antworten dann „gleich erneut")


def _instanz_heilt(inst):
    """True = für diese Instanz läuft gerade eine EA-Heilung (eigene Sperre der Heilung oder HEAL_ACTIVE des Terminals) — Order/Close
    antworten dann 409 retry_ok:true statt „unklar" (Prüfer S2 30.10.2026 zu 21c004d7: master-close route mt5 lief sonst in retry_ok:false)."""
    if inst["config_file"] in EA_FROST_HAELT:
        return True
    cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
    tpath = str(cfg.get("master_terminal_path") or "").strip()
    d = os.path.dirname(os.path.abspath(tpath)) if tpath else ""
    with HEAL_LOCK:
        return bool(d) and d in HEAL_ACTIVE


def ea_frost_entscheiden(snap_alter_s, gebraucht, letzter, jetzt, puls_frei, order_frei, terminal_da, hedges_offen=False):
    """REIN RECHNEND (testbar): (heilen: bool, grund). gebraucht = Grund, warum die Instanz gebraucht wird ('' = nicht).
    hedges_offen (Prüfer S2 30.10.2026): der erste frische Snapshot nach dem Neustart kann vor dem Server-Sync 0 Positionen zeigen, und der
    Copier schlösse daraufhin die Hedges (copier.py Master-zu-Weg) — bei offenen Hedges deshalb NIE heilen, nur melden."""
    if snap_alter_s is None or snap_alter_s <= EA_FROST_S or not gebraucht:
        return False, ""
    warum = f"Snapshot seit {int(snap_alter_s)} s eingefroren ({gebraucht})"
    if snap_alter_s > EA_FROST_MAX_S:
        return False, f"{warum} — über {EA_FROST_MAX_S // 3600} h still: Instanz läuft auf diesem PC wohl nicht, keine Heilung (zweites Terminal?)"
    if hedges_offen:
        return False, f"{warum} — offene Hedges: keine automatische Heilung (Neustart könnte sie schließen), Lese-EA am PC von Hand prüfen"
    if not terminal_da:
        return False, f"{warum} — kein master_terminal_path in der Config, Heilung nicht möglich"
    if not puls_frei:
        return False, f"{warum} — wartet: Puls/Polar läuft"
    if not order_frei:
        return False, f"{warum} — wartet: MT5-Order dieser Instanz läuft"
    if letzter and jetzt - letzter < EA_FROST_ABSTAND_S:
        return False, f"{warum} — wartet: zuletzt geheilt vor {int((jetzt - letzter) // 60)} min (höchstens 1 je {EA_FROST_ABSTAND_S // 60} min)"
    return True, warum


def ea_gebraucht(st, login, echo_logins, status_alter_s=None):
    """REIN RECHNEND (testbar): warum die Instanz gebraucht wird, sonst ''. st = Copier-Status; Positionen/Hedges zählen nur, wenn er
    frisch ist (status_alter_s ≤ EA_STATUS_FRISCH_S — der Copier schreibt alle ~3 s, auch bei eingefrorenem Snapshot)."""
    st = st if isinstance(st, dict) and status_alter_s is not None and status_alter_s <= EA_STATUS_FRISCH_S else {}
    if st.get("master_positions"):
        return "Master-Positionen im letzten Stand"
    if any(v for v in (st.get("hedges") or {}).values()) if isinstance(st.get("hedges"), dict) else bool(st.get("hedges")):
        return "offene Hedges"
    if login and str(login).strip() in {str(x).strip() for x in (echo_logins or [])}:
        return "offener Echo-Plan"
    return ""


def _ea_frost_waechter():
    if os.name != "nt":
        return
    time.sleep(TAB_NL_ANLAUF_S + random.random() * 30)
    while True:
        try:
            jetzt = time.time()
            stand = TAB_NL.get("stand") if jetzt - TAB_NL.get("stand_at", 0.0) <= 300 else None
            echo_logins = (stand or {}).get("echo_logins") or []
            for inst in instances():
                fname = inst["config_file"]
                cfg = read_json(os.path.join(HERE, fname), {}) or {}
                st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
                sp = _snapshot_path(cfg)
                try:
                    alter = jetzt - os.path.getmtime(sp) if sp else None
                except OSError:
                    alter = None
                m = EA_FROST.setdefault(fname, {"letzter": 0.0, "geprueft": True, "grund": ""})
                try:
                    st_alter = (datetime.now() - datetime.fromisoformat(st["updated_at"])).total_seconds() if st.get("updated_at") else None
                except Exception:
                    st_alter = None
                login = str(cfg.get("master_expected_login") or st.get("master_login") or "").strip()
                # Nachkontrolle EA_FROST_NACH_S nach der Heilung (einmal)
                if not m["geprueft"] and jetzt - m["letzter"] >= EA_FROST_NACH_S:
                    m["geprueft"] = True
                    if alter is not None and alter > EA_FROST_S:
                        foto = _panel_fehlerfoto("panel_ea_heilung", "ea_eingefroren")
                        g = f"EA-Heilung {fname}: {EA_FROST_NACH_S // 60} min danach weiter eingefroren ({int(alter)} s) — {foto}"
                    else:
                        g = f"EA-Heilung {fname}: Snapshot fließt wieder"
                    print(f"[ea-frost] {g}", flush=True)
                    pc = pc_id_lesen()
                    if pc:
                        _tab_stand_holen(pc, g)
                lock = MASTER_ORDER_LOCKS.setdefault(fname, threading.Lock())
                path = str(cfg.get("master_terminal_path") or "").strip()
                gebraucht = ea_gebraucht(st, login, echo_logins, st_alter)
                # offene Hedges laut frischem Copier-Stand (auch wenn „gebraucht" schon aus den Master-Positionen kommt)
                hedges_offen = ea_gebraucht({"hedges": st.get("hedges")}, "", [], st_alter) == "offene Hedges"
                ja, grund = ea_frost_entscheiden(alter, gebraucht, m["letzter"], jetzt,
                                                 not TV_ORDER_LOCK.locked() and _browser_und_mt5_frei(tv_eigen=True),
                                                 not lock.locked(), path.lower().endswith("terminal64.exe"), hedges_offen)
                if grund and grund != m["grund"]:
                    print(f"[ea-frost] {fname}: {grund}", flush=True)
                    m["grund"] = grund
                    if "offene Hedges" in grund and pc_id_lesen():
                        _tab_stand_holen(pc_id_lesen(), f"EA {fname}: {grund}")   # Spur an Railway (🔴 echo_blind folgt nach der Karenz)
                if not ja:
                    continue
                time.sleep(random.random() * 15)                    # gestreut (Jitter-Regel)
                # Merkliste VOR der Sperre (Prüfer S2 30.10.2026): eine Order/ein Close genau zwischen Sperre und Merkliste sähe sonst nur
                # „belegt" (retry_ok:false) statt „terminal_heilt"; jede Ausnahme bis zum Thread-Start gibt Sperre und Merkliste wieder frei
                EA_FROST_HAELT.add(fname)
                if not lock.acquire(blocking=False):
                    EA_FROST_HAELT.discard(fname)
                    continue
                gestartet = False
                try:
                    # Puls/Polar kam in der Streuzeit dazu? (nicht _browser_und_mt5_frei — das zählte jetzt die eigene, gerade gehaltene Sperre)
                    if TV_ORDER_LOCK.locked() or (polar_panel and (polar_panel.aktiv() or getattr(polar_panel, "test_aktiv", lambda: False)())):
                        continue
                    m.update(letzter=time.time(), geprueft=False)
                    g = f"EA-Heilung {fname}: {grund} → Terminal neu + EA aufziehen"
                    print(f"[ea-frost] {g}", flush=True)

                    def _heilen(fname=fname, cfg=cfg, path=path, lock=lock):
                        try:
                            _heal_ea(fname, cfg, os.path.dirname(os.path.abspath(path)), time.time(), 15)
                        finally:
                            EA_FROST_HAELT.discard(fname)
                            lock.release()
                    threading.Thread(target=_heilen, daemon=True).start()
                    gestartet = True
                except Exception as e:
                    f = f"EA-Heilung {fname}: Start fehlgeschlagen ({type(e).__name__}: {str(e)[:80]}) — Sperre freigegeben"
                    print(f"[ea-frost] {f}", flush=True)
                    if pc_id_lesen():
                        _tab_stand_holen(pc_id_lesen(), f)
                    continue
                finally:
                    if not gestartet:
                        EA_FROST_HAELT.discard(fname)
                        lock.release()
                pc = pc_id_lesen()
                if pc:
                    _tab_stand_holen(pc, g)
        except Exception as e:
            print(f"[ea-frost] Fehler: {type(e).__name__}: {e}", flush=True)
        time.sleep(EA_FROST_TAKT_S + random.random() * 15)


def _heal_ea(fname, cfg, install_dir, started_ts, wait_s=45, schnell_wenn_nie_da=False):
    """Hintergrund-Selbstheilung (15.08.2026): Nach einem Terminal-Start pruefen,
    ob der Snapshot wieder fliesst. Tut er es nicht, fehlt das Lese-EA auf dem
    Chart (passiert nach unsauberem Beenden — Chart-Stand verloren). Dann:
    Terminal beenden und mit [StartUp]-Startdatei neu starten, die das EA samt
    richtigem InpFileName automatisch aufzieht — derselbe Mechanismus wie bei
    der Provisionierung. Seit dem Abend auch fuer BEREITS LAUFENDE Terminals
    mit eingefrorenem Snapshot (Fund: Terminal lief noch vom vorigen Versuch,
    der Start-Knopf holte es nur nach vorn und uebersprang die Heilung — ein
    Terminal, das nichts liefert, ist zum Kopieren nutzlos, und die Positionen
    liegen beim Broker, ueberleben den Neustart also)."""
    with HEAL_LOCK:
        if install_dir in HEAL_ACTIVE:
            return
        HEAL_ACTIVE.add(install_dir)
    try:
        _heal_ea_inner(fname, cfg, install_dir, started_ts, wait_s, schnell_wenn_nie_da)
    finally:
        with HEAL_LOCK:
            HEAL_ACTIVE.discard(install_dir)


def _heal_ea_inner(fname, cfg, install_dir, started_ts, wait_s, schnell_wenn_nie_da=False):
    snap = str(cfg.get("snapshot_file") or "prophos_master.csv")
    common = cfg.get("common_files_dir") or os.path.join(
        os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")
    snap_path = os.path.join(common, snap)
    # POLLEN statt Ein-Schuss-Check (Fund 15.08.2026, gwgdwd-Trade-Test): der
    # Zwangs-Start loescht den Alt-Snapshot (_drop_snapshot), und ein Terminal,
    # das langsamer bootet als die Frist (FundedNext > 45s), sah im Ein-Schuss-
    # Check aus wie 'Datei fehlt' — die Heilung killte das GESUNDE, noch
    # bootende Terminal und startete es ohne Login-Zwang neu. Jetzt: bis
    # Frist + 90s Boot-Puffer alle 5s nachsehen; EIN frischer Schreibvorgang
    # beendet die Heilung sofort. Gekillt wird nur ein Terminal, das das ganze
    # Fenster ueber nichts geliefert hat.
    # Schnell-Pfad (18.08.2026, The5ers-Fund: frisches Konto, EA nie
    # eingerichtet — die Snapshot-Datei hat NIE existiert, trotzdem wartete
    # die Heilung die vollen wait_s+90s Boot-Puffer, waehrend Finn vor dem
    # Zaehler sass). Hat die Datei nie existiert und der Aufrufer erlaubt es
    # (nur ohne Login-Zwang — der Zwangs-Start loescht die Datei bewusst und
    # braucht den langen Puffer fuer langsame Boots), wird schon nach wait_s
    # geheilt: eine Datei, die nie da war, kommt auch nicht von selbst.
    nie_da = not os.path.exists(snap_path)
    kurz = time.time() + wait_s
    deadline = time.time() + wait_s + 90
    while time.time() < deadline:
        time.sleep(5)
        try:
            if os.path.getmtime(snap_path) > started_ts:
                return  # Snapshot fliesst — EA laeuft, nichts zu tun
            nie_da = False  # Datei existiert (nur alt) — normaler langer Pfad
        except OSError:
            pass  # Datei (noch) nicht da -> weiter warten
        if schnell_wenn_nie_da and nie_da and time.time() >= kurz:
            break
    data_dir = provision.data_dir_for(install_dir)
    if not data_dir:
        print(f"[panel] {fname}: Selbstheilung — Datenordner nicht gefunden.", flush=True)
        return
    ex5 = os.path.join(data_dir, "MQL5", "Experts", provision.EA_NAME + ".ex5")
    if not os.path.exists(ex5):
        # Fehlt das EA komplett (frisches/nicht provisioniertes Terminal —
        # 18.08.2026, Finns neue FivePercentOnline-Konten), kann
        # _ensure_ea_compiled es SELBST installieren: .mq5 aus dem Repo in den
        # Datenordner spiegeln + per MetaEditor kompilieren. Vorher gab die
        # Heilung hier grundlos auf ('von Hand kompilieren').
        _ensure_ea_compiled(fname, install_dir)
    if not os.path.exists(ex5):
        print(f"[panel] {fname}: Selbstheilung — {provision.EA_NAME}.ex5 fehlt im "
              f"Datenordner und liess sich nicht bauen (metaeditor64.exe da?) — "
              f"einmal im Terminal kompilieren (F4 -> F7).", flush=True)
        return
    print(f"[panel] {fname}: Snapshot fliesst nicht — EA fehlt wohl. Starte Terminal "
          f"neu und ziehe {provision.EA_NAME} automatisch auf (InpFileName={snap}).", flush=True)
    for pid in provision.terminal_pids(install_dir):
        provision._taskkill(pid)
    # Terminal ist jetzt aus — EA vor dem Neustart aktuell kompilieren, sonst
    # zieht die Heilung ein veraltetes EA ohne Balance-Header auf (15.08.2026)
    _ensure_ea_compiled(fname, install_dir)
    # ZUERST fest ins Profil schreiben (25.08.2026, Finns Live-Fund: das
    # [StartUp]-Chart wird vom gespeicherten Profil ersetzt — das EA lebte nur
    # bis zum naechsten Boot, jeder Trade-Start zahlte die volle Heilung
    # erneut). Terminal ist aus, die .chr liegen still. Klappt die Injektion,
    # reicht der nackte Start; [StartUp] bleibt nur als Fallback (z.B. frische
    # Installation ohne Profil-Ordner).
    aus = _update_vor_start_noetig(install_dir)   # neuer Build? erst still einspielen (08.10.2026)
    if aus:
        _update_einspielen(fname, aus)
    _update_abwarten(install_dir)  # stilles MT5-Update gerade dran? (01.10.2026)
    _vor_kaltstart(fname, install_dir)   # Download-Kennung + HKCU-Häkchen weg (23.10.2026)
    # Login-Wache auch nach dem Heil-Neustart (23.10.2026): hier startet Echo ebenso kalt — bisher ohne Wache
    exp_heil = int(cfg.get("master_expected_login") or 0)
    if _inject_ea_into_profile(fname, cfg, install_dir):
        subprocess.Popen([os.path.join(install_dir, "terminal64.exe")], cwd=install_dir)
        if exp_heil:
            threading.Thread(target=_login_ok_wache, args=(fname, exp_heil, install_dir), daemon=True).start()
        return
    name = os.path.splitext(fname)[0].replace("config", "", 1).strip("-_") or "standard"
    preset = f"prophos-heal-{name}.set"
    os.makedirs(os.path.join(data_dir, "MQL5", "Presets"), exist_ok=True)
    with open(os.path.join(data_dir, "MQL5", "Presets", preset), "w",
              encoding=provision.SET_ENCODING) as f:
        f.write(provision.build_preset(snap))
    ini = os.path.join(install_dir, "prophos-heal.ini")
    with open(ini, "w", encoding=provision.INI_ENCODING) as f:
        f.write(provision.build_startup_ini(preset=preset))
    try:
        subprocess.Popen([os.path.join(install_dir, "terminal64.exe"),
                          f"/config:{ini}"], cwd=install_dir)
        if exp_heil:
            threading.Thread(target=_login_ok_wache, args=(fname, exp_heil, install_dir), daemon=True).start()
    finally:
        # ini nach dem Start wegraeumen (ein weiterer Start damit haengte das EA
        # auf einen ZWEITEN Chart)
        time.sleep(30)
        try:
            os.remove(ini)
        except OSError:
            pass


def _remove_later(path, delay_s=90):
    """Passwort-fuehrende Login-ini nach dem Start wegraeumen. 90 s statt 25
    (Review-Fund 15.08.2026): ein langsamer Terminal-Boot (Defender, VPS) darf
    die /config-ini nicht verpassen — die Provisionierung haelt ihre ini sogar
    bis zur Login-Bestaetigung. Mit Retry gegen transiente Windows-Locks; den
    Prozess-Exit (os._exit des Version-Watchers) ueberlebt der Thread NICHT —
    dafuer raeumt main() beim naechsten Panel-Start liegengebliebene inis auf."""
    def worker():
        time.sleep(delay_s)
        for _ in range(4):
            try:
                os.remove(path)
                return
            except FileNotFoundError:
                return
            except OSError:
                time.sleep(10)
    threading.Thread(target=worker, daemon=True).start()


def _fenster_nach_vorn(pid):
    """Terminal-Fenster WIRKLICH nach vorn holen (25.08.2026, Finns Live-Test:
    das Terminal stand nur in der Taskleiste, 'man kommt visuell nicht rein').
    Zwei Fallen des alten nackten AppActivate:
      1. Ein frischer MT5-Prozess hat sekundenlang noch KEIN Fenster — der
         eine Versuch lief ins Leere.
      2. Windows' Foreground-Lock: ein Hintergrundprozess darf den Vordergrund
         nicht klauen — AppActivate liess die Taskleiste nur blinken.
    Fix: erst pruefen, ob ueberhaupt ein Hauptfenster existiert (das bleibt
    der Zombie-Beweis), dann Alt-Tastendruck (SendKeys '%' — gibt den
    Foreground-Wechsel frei), dann aktivieren. Nur einfache Quotes im
    PowerShell-Skript — doppelte zerlegt die Windows-Arg-Quotierung."""
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"$p=Get-Process -Id {int(pid)};"
        "if($p -and $p.MainWindowHandle -ne 0){"
        "$ws=New-Object -ComObject WScript.Shell;"
        "$ws.SendKeys('%');"
        f"[void]$ws.AppActivate({int(pid)});"
        "'True'}else{'False'}"
    )
    try:
        pr = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, errors="replace", timeout=15)
        return "True" in (pr.stdout or "")
    except Exception:
        return False


def _front_when_up(install_dir):
    """Frisch gestartetes Terminal nach vorn holen (Finns Ansage 15.08.2026:
    'das Terminal-Fenster soll auch aufgehen'). Gepollt wird jetzt bis das
    FENSTER da ist, nicht nur der Prozess (25.08.2026): vorher feuerte der
    einzige Versuch, sobald die PID existierte — Sekunden bevor MT5 sein
    Fenster hatte — und kehrte unverrichtet zurueck."""
    def worker():
        for _ in range(30):
            time.sleep(2)
            pids = provision.terminal_pids(install_dir)
            if pids and _fenster_nach_vorn(pids[0]):
                return
    threading.Thread(target=worker, daemon=True).start()


def _snapshot_path(cfg):
    """Pfad der Snapshot-CSV — Aufloesung identisch zu copier.py."""
    snapf = str(cfg.get("snapshot_file") or "").strip()
    if not snapf:
        return None
    common = str(cfg.get("common_files_dir") or "").strip() or os.path.join(
        os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")
    return os.path.join(common, snapf)


LESE_FRISCH_S = 15   # wie alive beim Copier: das EA schreibt alle 200 ms, älter heißt Terminal/EA weg


def snapshot_lesen(path, expect_login=None):
    """Snapshot-CSV des Lese-EAs parsen — dieselben Regeln wie copier.read_snapshot (Kopf PROPHOS1,
    Fremd-Login verworfen, END-Zeile mit passender seq/Anzahl, fehlende Werte None statt 0). Bewusst
    nachgebaut statt importiert, wie _echo_fenster_offen: copier.py hängt an MetaTrader5."""
    try:
        with open(path, "r", encoding="ascii", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]
    except OSError:
        return None
    if not lines or not lines[0].startswith("PROPHOS1;"):
        return None
    head = lines[0].split(";")
    try:
        seq = int(head[1]); login = int(head[3]); server = head[4]; count = int(head[6])
    except (IndexError, ValueError):
        return None
    balance = equity = currency = None
    try:
        if len(head) >= 9:
            balance = float(head[7]); equity = float(head[8])
        if len(head) >= 10 and head[9]:
            currency = head[9]
    except (IndexError, ValueError):
        balance = equity = currency = None
    try:
        if expect_login and int(expect_login) != login:
            return None
    except (TypeError, ValueError):
        return None
    positions, footer_ok = [], False
    for l in lines[1:]:
        f_ = l.split(";")
        if l.startswith("P;"):
            try:
                pos = {"ident": int(f_[1]), "symbol": f_[2], "type": int(f_[3]),
                       "volume": float(f_[4]), "contract_size": float(f_[5])}
            except (IndexError, ValueError):
                return None
            pos["price_open"] = pos["sl"] = pos["tp"] = None
            try:
                if len(f_) >= 9:
                    pos["price_open"] = float(f_[6]); pos["sl"] = float(f_[7]); pos["tp"] = float(f_[8])
            except (IndexError, ValueError):
                pos["price_open"] = pos["sl"] = pos["tp"] = None
            positions.append(pos)
        elif l.startswith("END;"):
            try:
                footer_ok = int(f_[1]) == seq and int(f_[2]) == len(positions)
            except (IndexError, ValueError):
                return None
    if not footer_ok or len(positions) != count:
        return None   # halb geschrieben → nächster Abruf
    return {"seq": seq, "login": login, "server": server, "positions": positions,
            "balance": balance, "equity": equity, "currency": currency}


def lese_status(cfg, jetzt=None):
    """Master-Stand OHNE Copier (Echo V2, 25.09.2026): frische Snapshot-Datei → Status-Felder in der Form
    von copier.master_status (nur die Master-Seite), sonst None. Frisch = Datei ≤ 15 s alt; eine Datei
    von gestern ist kein Live-Stand („Beweis oder leer"). Kein Hedge-Feld, running bleibt beim Copier."""
    p = _snapshot_path(cfg)
    if not p:
        return None
    try:
        mtime = os.path.getmtime(p)
    except OSError:
        return None
    alter = (time.time() if jetzt is None else jetzt) - mtime
    if alter > LESE_FRISCH_S or alter < -5:
        return None
    snap = snapshot_lesen(p, cfg.get("master_expected_login"))
    if not snap:
        return None
    return {
        "lesen": True, "lese_alter_s": round(max(alter, 0), 1),
        "note": None, "standby": False,
        "master_login": snap["login"], "master_server": snap["server"],
        "master_positions": snap["positions"],
        "master_balance": snap["balance"], "master_equity": snap["equity"],
        "master_currency": snap["currency"],
    }


def _drop_snapshot(cfg):
    """Alt-Snapshot des Masters entwerten (Review-Fund 15.08.2026, Stale-Beweis-
    Livelock): die Snapshot-CSV ueberlebt Terminal-Kill und Kontowechsel, und der
    Copier wuerde daraus weiter 'FALSCHES Konto' stempeln — waehrend das frisch
    gezwungene Terminal noch bootet. Datei weg → ehrliches 'warte auf Snapshot'."""
    p = _snapshot_path(cfg)
    if not p:
        return
    try:
        os.remove(p)
    except OSError:
        pass


def _inject_ea_into_profile(fname, cfg, install_dir):
    """Lese-EA FEST ins Chart-Profil schreiben (15.08.2026, Experten-Log-Beweis:
    'ProphosHedgeReader beendet, reason=4' = Chart geschlossen). Das /config-
    [StartUp]-Chart wird beim Fertigladen des gespeicherten Profils ERSETZT —
    das EA lebte deshalb nur die ersten ~30-90s jedes Starts, dann Freeze.
    Fix: der <expert>-Block wandert direkt in die chartNN.chr des Profils
    (Terminal ist beim Kalt-Start aus, die Datei liegt still) — damit ist das
    EA Profil-Bestandteil und ueberlebt jeden Boot. Backup .prophos-bak,
    idempotent (Marker-Check), pro Profil genau ein Chart."""
    data_dir = provision.data_dir_for(install_dir)
    if not data_dir:
        return False
    if not os.path.exists(os.path.join(data_dir, "MQL5", "Experts", provision.EA_NAME + ".ex5")):
        return False
    snapf = str(cfg.get("snapshot_file") or "prophos_master.csv")
    charts_root = os.path.join(data_dir, "MQL5", "Profiles", "Charts")
    if not os.path.isdir(charts_root):
        return False
    block = ("<expert>\r\n"
             f"name={provision.EA_NAME}\r\n"
             f"path=Experts\\{provision.EA_NAME}.ex5\r\n"
             "expertmode=0\r\n"
             "<inputs>\r\n"
             f"InpFileName={snapf}\r\n"
             "InpTimerMs=200\r\n"
             "</inputs>\r\n"
             "</expert>\r\n")
    injected = False
    for prof in sorted(os.listdir(charts_root)):
        pdir = os.path.join(charts_root, prof)
        if not os.path.isdir(pdir):
            continue
        for fn in sorted(f for f in os.listdir(pdir) if f.lower().endswith(".chr")):
            p = os.path.join(pdir, fn)
            try:
                with open(p, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
            try:
                txt = raw.decode(enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
            if provision.EA_NAME in txt:
                injected = True   # Profil traegt das EA schon — nichts zu tun
                break
            if "<expert>" in txt:
                continue          # Chart hat schon ein anderes EA — naechstes
            idx = txt.rfind("</chart>")
            if idx < 0:
                continue
            try:
                with open(p + ".prophos-bak", "wb") as f:
                    f.write(raw)
                with open(p, "wb") as f:
                    f.write((txt[:idx] + block + txt[idx:]).encode(enc))
            except OSError:
                continue
            print(f"[panel] {fname}: Lese-EA fest ins Profil geschrieben ({prof}/{fn}, "
                  f"InpFileName={snapf}).", flush=True)
            injected = True
            break
    return injected


def _startup_attach_part(fname, cfg, install_dir):
    """[StartUp]-Teil fuer die Start-ini: zieht das Lese-EA direkt beim Boot auf
    (15.08.2026, gwgdwd-Test #2: das Chart-Profil der Instanz hatte sein EA-Chart
    verloren — Terminal lief, lieferte aber NIE einen Snapshot, und erst die
    Heilung nach >2 Minuten haette es gefixt). Login + EA-Aufzug in EINER ini,
    exakt der Provisionierungs-Weg. Preis: pro Kalt-Start kommt ein weiteres
    EA-Chart ins Profil — bewusst in Kauf genommen, Daten schlagen Optik.
    Rueckgabe: ini-Teil oder '' (ex5 fehlt/Datenordner unbekannt)."""
    data_dir = provision.data_dir_for(install_dir)
    if not data_dir:
        print(f"[panel] {fname}: EA-Aufzug uebersprungen — Datenordner nicht gefunden.", flush=True)
        return ""
    if not os.path.exists(os.path.join(data_dir, "MQL5", "Experts", provision.EA_NAME + ".ex5")):
        print(f"[panel] {fname}: {provision.EA_NAME}.ex5 fehlt im Datenordner — bitte einmal "
              f"im Terminal kompilieren (F4 → MetaEditor → F7), dann Trade neu starten.", flush=True)
        return ""
    snapf = str(cfg.get("snapshot_file") or "prophos_master.csv")
    name = os.path.splitext(fname)[0].replace("config", "", 1).strip("-_") or "standard"
    preset = f"prophos-heal-{name}.set"
    os.makedirs(os.path.join(data_dir, "MQL5", "Presets"), exist_ok=True)
    with open(os.path.join(data_dir, "MQL5", "Presets", preset), "w",
              encoding=provision.SET_ENCODING) as f:
        f.write(provision.build_preset(snapf))
    return "\n" + provision.build_startup_ini(preset=preset)


def hedge_null_urteil(volumen, multiplier, m_cs, hs):
    """REIN RECHNEND (testbar, EH2 12.11.2026, Befund S2): würde der Copier zu dieser Master-Order einen Hedge von 0 Lot rechnen? Dieselbe Formel wie
    copier.plan_actions + norm_vol: v = volumen × multiplier × m_cs ÷ h_cs, auf volume_step gerundet, unter volume_min → 0.
    hs = {volume_step, volume_min, trade_contract_size} des Hedge-Ziels (Copier-Status hedge_sym). → (gesperrt, text, v) | (None, grund, None) = nicht prüfbar
    (fehlende Angabe → wie bisher kein Riegel, nur Log)."""
    try:
        vol, mult = float(volumen), float(multiplier)
        mcs = float(m_cs)
        step = float((hs or {}).get("volume_step") or 0)
        vmin = float((hs or {}).get("volume_min") or 0)
        hcs = float((hs or {}).get("trade_contract_size") or 0)
    except (TypeError, ValueError):
        return None, "Angabe nicht lesbar", None
    if not (vol > 0 and mult > 0 and mcs > 0 and step > 0 and vmin > 0 and hcs > 0):
        return None, "Angabe fehlt (Volumen/Multiplikator/Kontraktgrößen/Lot-Schritt)", None
    roh = vol * mult * (mcs / hcs)
    v = round(round(roh / step) * step, 8)
    if v < vmin - 1e-6:
        return True, (f"Hedge wäre 0 Lot — Kontraktgrößen Master/Fusion prüfen (gerechnet {roh:.4f} Lot = {vol:g} × {mult:.4f} × {mcs:g} ÷ {hcs:g}, "
                      f"Mindest-Lot {vmin:g}). Nichts gesendet."), 0.0
    return False, "", v


_MCS_CACHE = {}          # EH2: (Terminal-Pfad, Login, Symbol) → (Zeit, Kontraktgröße) — die Kontraktgröße eines Symbols ändert sich praktisch nie
_MCS_CACHE_S = 6 * 3600


def _master_contract_size_live(cfg, symbol):
    """EH2: Kontraktgröße des Master-Symbols LIVE am Master-Terminal, NUR LESEND (wie _master_positionen_live: initialize → symbol_info → shutdown,
    Login-Guard). → float | None (nicht lesbar — Aufrufer prüft dann nicht, nur Log).
    Prüfer EH2 (SOLLTE): nur ein Terminal lesen, das schon läuft (provision.terminal_pids wie der Deals-Weg — initialize startete sonst ein
    geschlossenes Terminal ohne die Start-Parameter), initialize mit kurzem timeout (5 s statt 60 s Standard: ein hängendes Terminal bzw. ein offener
    Login-Dialog darf die Zeit bis zum Klick nicht aufzehren), ohne master_expected_login nie (sonst läse es ein fremdes Konto). Ergebnis 6 h gemerkt."""
    path = str(cfg.get("master_terminal_path") or "").strip()
    try:
        exp = int(cfg.get("master_expected_login") or 0)
    except (TypeError, ValueError):
        exp = 0
    if not path or not os.path.exists(path) or not symbol or not exp:
        return None
    key = (os.path.abspath(path), exp, str(symbol))
    c = _MCS_CACHE.get(key)
    if c and time.time() - c[0] < _MCS_CACHE_S:
        return c[1]
    try:
        if not provision.terminal_pids(os.path.dirname(os.path.abspath(path))):
            return None
    except Exception:
        return None
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    try:
        if not mt5.initialize(path=path, timeout=5000):
            return None
        try:
            ai = mt5.account_info()
            if ai is None or int(ai.login) != exp:
                return None
            si = mt5.symbol_info(symbol)
            cs = float(getattr(si, "trade_contract_size", 0) or 0) if si is not None else 0.0
            if cs > 0:
                _MCS_CACHE[key] = (time.time(), cs)
                return cs
            return None
        finally:
            mt5.shutdown()
    except Exception:
        return None


def _master_positionen_live(cfg):
    """LIVE am Master-Terminal nachsehen, NUR LESEND (19.08.2026, Finns Fund:
    der Loesch-Riegel glaubte der Positionsliste aus dem EINGEFRORENEN
    Snapshot — '1 Position' von gestern blockierte das Loeschen, waehrend das
    Terminal live 0 zeigte). Rueckgabe: Anzahl offener Positionen oder None
    (nicht pruefbar — falsches Konto, Terminal nicht erreichbar, Paket fehlt)."""
    path = str(cfg.get("master_terminal_path") or "").strip()
    if not path or not os.path.exists(path):
        return None
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    try:
        if not mt5.initialize(path=path):
            return None
        try:
            ai = mt5.account_info()
            exp = int(cfg.get("master_expected_login") or 0)
            if ai is None or (exp and int(ai.login) != exp):
                return None
            return len(mt5.positions_get() or ())
        finally:
            mt5.shutdown()
    except Exception:
        return None


def _ok_dialog_watcher(install_dir, dauer_s=75):
    """Start-Dialoge automatisch bestaetigen (18.08.2026, Finns The5ers-Fund:
    das Terminal oeffnete mit einem Login-/OK-Dialog, niemand drueckte OK,
    alles hing). 75s lang nach Standard-Dialogen (#32770) des Terminal-
    Prozesses suchen und NUR einen OK/Ja/Anmelden-Knopf druecken — nie
    Abbrechen, kein blindes Enter ans Terminal. Standard-Windows-Dialoge
    reagieren auf .click(); max. 2 Bestaetigungen pro Start."""
    try:
        from pywinauto import Desktop
    except ImportError:
        return
    ende = time.time() + dauer_s
    gedrueckt = 0
    while time.time() < ende and gedrueckt < 2:
        time.sleep(2.0)
        try:
            pids = set(provision.terminal_pids(install_dir))
            if not pids:
                continue
            for w in Desktop(backend="win32").windows():
                try:
                    if w.process_id() not in pids:
                        continue
                    if w.element_info.class_name != "#32770":
                        continue
                    for b in w.descendants(class_name="Button"):
                        t = (b.window_text() or "").replace("&", "").strip().lower()
                        if t in ("ok", "ja", "yes", "anmelden", "login"):
                            b.click()
                            gedrueckt += 1
                            print(f"[panel] {os.path.basename(install_dir)}: Start-Dialog "
                                  f"('{t}') automatisch bestaetigt.", flush=True)
                            break
                except Exception:
                    continue
        except Exception:
            pass


# LOGIN-WACHE DAUERHAFT (Master 23.10.2026, Finn: „die zwei Fehler, die bei dir liegen — echt versuchen zu eliminieren"): Chris
# FundingPips 03:33 + 05:09 — consent.exe hielt den Kaltstart stundenlang fest; als Finn die Abfrage weggeklickt hatte, stand der
# MT5-Dialog „Einloggen" (Konto, Server, Passwort gespeichert) offen und niemand drückte OK. Die Wache lief nur 90 s nach dem Start.
# Jetzt: in Runden (LOGIN_WACHE_RUNDE_S je Bot-Aufruf), bis das Konto verbunden ist (Copier-Status frisch, connected, master_login =
# erwartetes Konto, LOGIN_WACHE_STABIL_S am Stück) oder LOGIN_WACHE_MAX_S vorbei sind — Zeit, in der eine Windows-Abfrage offen war oder
# MT5 ein Update einspielte, zählt nicht mit (bis LOGIN_WACHE_HART_S). Terminal aus = Ende. Je Installation höchstens EINE Wache.
def consent_offen():
    """True/False: läuft consent.exe (Windows-Sicherheitsabfrage auf dem sicheren Desktop)? None ohne Windows oder ohne lesbare Liste.
    Nur der Name aus tasklist — consent.exe läuft als SYSTEM, sein Pfad ist für uns nicht lesbar (wie order_bot._verbindung_lage)."""
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq consent.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             timeout=8, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout or ""
        return '"consent.exe"' in out.lower()
    except Exception:
        return None


LOGIN_WACHE_MAX_S, LOGIN_WACHE_STABIL_S, LOGIN_WACHE_RUNDE_S, LOGIN_WACHE_HART_S = 1800, 120, 120, 12 * 3600
LOGIN_WACHE = set()   # install_dir mit laufender Wache (unter HEAL_LOCK)
# Höchstens so viele Bestätigungen je Wache (Prüf-Agent 23.10.2026): kommt der Dialog nach einem gescheiterten Login immer wieder, wären es
# sonst 30 min lang Login-Versuche beim Broker. Nach jeder Bestätigung gestreut LOGIN_WACHE_NACH_OK_S Pause.
LOGIN_WACHE_MAX_OK, LOGIN_WACHE_NACH_OK_S = 3, (20.0, 20.0)


def login_wache_weiter(start, jetzt, warten_s, verbunden_seit, ende_bot=None, bestaetigt_n=0):
    """REIN RECHNEND (testbar): (weiter, grund). warten_s = Summe der Abfrage-/Update-Wartezeit, verbunden_seit = Zeitpunkt, seit dem
    das Konto am Stück verbunden ist (None = nicht verbunden), ende_bot = 'terminal_aus' beendet sofort, bestaetigt_n = Bestätigungen."""
    if ende_bot == "terminal_aus":
        return False, "Terminal aus"
    if bestaetigt_n >= LOGIN_WACHE_MAX_OK:
        return False, f"Login-Dialog {bestaetigt_n}× bestätigt, kommt wieder — Login am PC prüfen (Passwort/Server)"
    if verbunden_seit is not None and jetzt - verbunden_seit >= LOGIN_WACHE_STABIL_S:
        return False, "Konto verbunden"
    if jetzt - start >= LOGIN_WACHE_HART_S:
        return False, f"{LOGIN_WACHE_HART_S // 3600} h vorbei"
    if jetzt - start - max(0.0, float(warten_s or 0)) >= LOGIN_WACHE_MAX_S:
        return False, f"{LOGIN_WACHE_MAX_S // 60} min ohne Verbindung"
    return True, ""


def _konto_verbunden(fname, expected):
    """Copier-Status dieser Instanz: frisch (≤ 15 s), Snapshot fließt (connected) und kommt aus GENAU diesem Konto."""
    st = read_json(os.path.join(HERE, re.sub(r"^config", "status", fname, count=1, flags=re.I)), {}) or {}
    try:
        alter = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
    except (ValueError, TypeError):
        return False
    return (bool(st.get("running")) and alter <= 15 and bool(st.get("connected")) and not st.get("wrong_login")
            and str(st.get("master_login") or "") == str(int(expected)))


# LOGIN-WACHE AUCH OHNE KALTSTART (Finn 29.10.2026 07:35 Dubai, Mikes PC pc-l5o8bv: der Dialog „Einloggen" stand nach 04:13 Dubai bis
# Finn ihn um 07:20 wegdrueckte — die Wache lief nur nach einem Kaltstart DURCH das Panel; meldete MT5 sich selbst ab oder startete ohne
# Panel, schaute niemand nach). Jetzt prueft _login_dialog_waechter jede Minute (gestreut), ob im Prozess eines laufenden Master-Terminals
# ein Login-Fenster steht (Titel „Einloggen"/„Login …", win32-Fensterliste — billig, kein UIA-Baum). Steht es LOGIN_DIALOG_STEHT_S
# (+ 0–60 s) am Stück, startet dieselbe _login_ok_wache wie nach einem Kaltstart. Bewusst NICHT der Copier-Status: Puls-/Echo-V2-Instanzen
# laufen ohne Copier und waeren sonst immer „nicht verbunden" (Review 29.10.2026). Last-Deckel: hoechstens LOGIN_WACHE_GLEICHZEITIG
# Wachen auf dem PC (in einer Runde mitgezaehlt), je Instanz frühestens LOGIN_WACHE_PAUSE_S nach dem Ende der letzten Wache (auch der
# Kaltstart-Wache). Die Wache bestaetigt weiter nur den Dialog GENAU dieses Kontos per invoke (keine Maus).
LOGIN_DIALOG_STEHT_S, LOGIN_WACHE_PAUSE_S, LOGIN_WACHE_GLEICHZEITIG = 120, 3600, 2
LOGIN_FENSTER_TITEL = ("einloggen", "login", "anmelden", "anmeldung")   # wie order_bot.MT5_LOGIN_TITEL
_DIALOG_SEIT, _LOGIN_WACHE_ZULETZT, _LOGIN_WACHE_SCHWELLE = {}, {}, {}


def login_fenster_titel(titel):
    """REIN RECHNEND (testbar): Titel eines MT5-Login-Fensters? Exakt oder als Anfang (wie order_bot.ist_mt5_login_titel)."""
    t = (titel or "").strip().lower()
    return bool(t) and any(t == x or t.startswith(x + " ") or t.startswith(x + ":") for x in LOGIN_FENSTER_TITEL)


def _login_dialog_steht(install_dir):
    """True, wenn ein sichtbares Login-Fenster zu einem terminal64.exe-Prozess dieser Installation gehoert; None ohne Windows/pywinauto."""
    try:
        from pywinauto import Desktop
    except ImportError:
        return None
    try:
        pids = set(provision.terminal_pids(install_dir))
        if not pids:
            return False
        for w in Desktop(backend="win32").windows():
            try:
                if w.process_id() in pids and w.is_visible() and login_fenster_titel(w.window_text()):
                    return True
            except Exception:
                continue
    except Exception:
        return None
    return False


def login_wache_faellig(laeuft, dialog, seit, jetzt, schwelle, zuletzt, aktiv, laufende):
    """REIN RECHNEND (testbar): (faellig, seit). laeuft = Master-Terminal der Instanz laeuft, dialog = Login-Fenster steht, seit = erster
    Zeitpunkt mit stehendem Dialog (None = bisher keiner), zuletzt = Ende der letzten Wache dieser Instanz, aktiv = Wache laeuft schon,
    laufende = Wachen auf dem PC insgesamt. Terminal aus oder kein Dialog → (False, None)."""
    if not laeuft or not dialog:
        return False, None
    seit = jetzt if seit is None else seit
    if aktiv or laufende >= LOGIN_WACHE_GLEICHZEITIG:
        return False, seit
    if zuletzt is not None and jetzt - zuletzt < LOGIN_WACHE_PAUSE_S:
        return False, seit
    return jetzt - seit >= schwelle, seit


def _login_dialog_waechter():
    time.sleep(90 + random.uniform(0, 60))   # Panel-Start: Terminals/Kaltstart-Wachen erst hochkommen lassen
    while True:
        try:
            neu = 0   # in dieser Runde gestartete Wachen (tragen sich erst in ihrem Thread in LOGIN_WACHE ein)
            for i in instances():
                fname = i["config_file"]
                cfg = read_json(os.path.join(HERE, fname), {}) or {}
                pfad = str(cfg.get("master_terminal_path") or "").strip()
                try:
                    expected = int(cfg.get("master_expected_login") or 0)
                except (TypeError, ValueError):
                    expected = 0
                if not pfad or not expected:
                    continue   # Orbit/TV-Instanzen oder Konto unbekannt
                install_dir = os.path.dirname(os.path.abspath(pfad))
                laeuft = bool(provision.terminal_pids(install_dir))
                dialog = laeuft and bool(_login_dialog_steht(install_dir))
                with HEAL_LOCK:
                    aktiv, laufende = install_dir in LOGIN_WACHE, len(LOGIN_WACHE) + neu
                schwelle = _LOGIN_WACHE_SCHWELLE.setdefault(fname, LOGIN_DIALOG_STEHT_S + random.uniform(0, 60))
                faellig, seit = login_wache_faellig(laeuft, dialog, _DIALOG_SEIT.get(fname), time.time(), schwelle,
                                                    _LOGIN_WACHE_ZULETZT.get(fname), aktiv, laufende)
                if seit is None:
                    _DIALOG_SEIT.pop(fname, None)
                else:
                    _DIALOG_SEIT[fname] = seit
                if not faellig:
                    continue
                if _bot_lauf_aktiv():
                    continue   # Prüfer zu .1842: mitten im Puls-/Order-Lauf nicht dazwischen (der Lauf bestätigt seine Dialoge selbst); Uhr bleibt, nächste Runde
                neu += 1
                _DIALOG_SEIT.pop(fname, None)
                _LOGIN_WACHE_SCHWELLE.pop(fname, None)
                print(f"[panel] {fname}: Login-Fenster steht seit {round(time.time() - seit)} s, Terminal läuft — "
                      f"Login-Wache für {expected} startet (ohne Kaltstart)", flush=True)
                threading.Thread(target=_login_ok_wache, args=(fname, expected, install_dir), daemon=True).start()
                time.sleep(2 + random.uniform(0, 3))
        except Exception as e:
            print(f"[panel] Login-Dialog-Waechter: {type(e).__name__}: {e}", flush=True)
        time.sleep(60 + random.uniform(0, 30))


def _login_ok_wache(fname, expected, install_dir=None):
    """Nach einem Kaltstart (08.10.2026, Master — Moritz 8a05ebaa: das MT5-Einloggen-Fenster blockierte Snapshot und API ~4 min, der
    _ok_dialog_watcher erkennt es nicht, nur der Bot — und der erst mitten im Order-Lauf): der Bot sucht NUR das Einloggen-Fenster für
    GENAU dieses Konto (ist_mt5_login_dialog) und bestätigt es nur per invoke() — keine Maus, kein Tippen, nie ein fremder Dialog.
    Läuft als eigener Prozess wie /api/mouse-test; Fehler bleiben still (der Order-Weg prüft selbst nach). Seit 23.10.2026 dauerhaft
    bis zur Verbindung (s. LOGIN_WACHE_MAX_S)."""
    cfg = read_json(os.path.join(HERE, fname), {}) or {}
    pfad = str(cfg.get("master_terminal_path") or "").strip()
    install_dir = install_dir or (os.path.dirname(os.path.abspath(pfad)) if pfad else "")
    if not install_dir or not pfad:
        return
    with HEAL_LOCK:
        if install_dir in LOGIN_WACHE:
            return
        LOGIN_WACHE.add(install_dir)
    try:
        start, warten_s, verbunden_seit, ok_n = time.time(), 0.0, None, 0
        while True:
            bot = os.path.join(HERE, "order_bot.py")
            if not os.path.exists(bot):
                ensure_bot_source()
            res = {}
            try:
                p = subprocess.run([*bot_argv(bot), "loginok", str(int(expected)), str(LOGIN_WACHE_RUNDE_S), pfad],
                                   capture_output=True, text=True, errors="replace", timeout=LOGIN_WACHE_RUNDE_S + 60,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                zeilen = (p.stdout or "").strip().splitlines()
                res = json.loads(zeilen[-1]) if zeilen else {}
            except Exception as e:
                print(f"[panel] {fname}: Login-OK-Wache {type(e).__name__}: {e}", flush=True)
            if not isinstance(res, dict) or not res.get("ende"):
                # leere/kaputte Antwort (order_bot.py fehlt, Import-Tod, MemoryError — Prüf-Agent 23.10.2026): nie ohne Pause neu starten
                res = {}
                time.sleep(LOGIN_WACHE_RUNDE_S / 4 + random.uniform(0, 10))
            if res.get("ende") == "bestaetigt":
                ok_n += 1
                print(f"[panel] {fname}: {res.get('msg')} ({ok_n}/{LOGIN_WACHE_MAX_OK})", flush=True)
                time.sleep(LOGIN_WACHE_NACH_OK_S[0] + random.uniform(0, LOGIN_WACHE_NACH_OK_S[1]))
            warten_s += float(res.get("warten_s") or 0)
            jetzt = time.time()
            verbunden_seit = (verbunden_seit or jetzt) if _konto_verbunden(fname, expected) else None
            weiter, grund = login_wache_weiter(start, jetzt, warten_s, verbunden_seit, res.get("ende"), ok_n)
            if not weiter:
                print(f"[panel] {fname}: Login-OK-Wache beendet — {grund} ({round((jetzt - start) / 60)} min"
                      + (f", davon {round(warten_s / 60)} min Windows-Abfrage/Update" if warten_s >= 60 else "") + ")", flush=True)
                return
    finally:
        with HEAL_LOCK:
            LOGIN_WACHE.discard(install_dir)
        _LOGIN_WACHE_ZULETZT[fname] = time.time()   # Pause des Dialog-Waechters zaehlt ab dem Ende jeder Wache (29.10.2026)


def start_terminal(fname, creds=None, ohne_update=False):
    """Startet das Master-Terminal der Instanz — oder holt das LAUFENDE Fenster
    nach vorn. Ein zweiter Start derselben Installation wuerde ein frisches
    Fenster ohne die laufende Sitzung oeffnen, das nach dem Login fragt
    (Fund 14.08.2026: genau daher kam der stoerende OK-Dialog). Pfad kommt
    AUSSCHLIESSLICH aus der Config (nicht ueber die API setzbar).

    creds = {login, password, server} (optional, aus Prophos/Supabase): damit
    wird der Login beim Start ERZWUNGEN — per transienter /config-ini mit
    KeepPrivate=1, exakt der Provisionierungs-Weg. Ohne Zwang schlaegt MT5 das
    zuletzt benutzte Konto des Ordners vor (15.08.2026, erster Trade-Test: das
    Terminal oeffnete mit 400005 statt 400006 und der Trade lief ins Leere)."""
    cfg = read_json(os.path.join(HERE, fname), {}) or {}
    path = str(cfg.get("master_terminal_path") or "").strip()
    if not path:
        return False, "master_terminal_path ist in der Config nicht gesetzt"
    if os.path.basename(path).lower() != "terminal64.exe":
        return False, "master_terminal_path muss auf eine terminal64.exe zeigen"
    if not os.path.exists(path):
        return False, f"nicht gefunden: {path}"
    expected = int(cfg.get("master_expected_login") or 0)
    if creds and expected and str(creds.get("login")) != str(expected):
        # Zugangsdaten fuer ein ANDERES Konto erzwingen waere garantiert falsch —
        # lieber laut scheitern als leise ins falsche Konto einloggen.
        return False, (f"Zugangsdaten gehoeren zu Konto {creds.get('login')}, die Instanz "
                       f"erwartet {expected} — Verlinkung in Prophos pruefen.")
    if creds and not (creds.get("server") or cfg.get("master_server")):
        # Ohne Servernamen kein Zwang (leere Server=-Zeile in der ini waere
        # unberechenbar) — dann lieber der bisherige nackte Start.
        creds = None
    if creds and not all(str(creds.get(k) or "").isascii() for k in ("login", "password", "server")):
        # VOR jedem Kill pruefen (Review-Fund 15.08.2026): die Start-ini ist
        # zwingend ASCII (UTF-16 ignoriert MT5), und ein UnicodeEncodeError nach
        # dem Kill liesse das Terminal tot zurueck. Klare Ansage statt Crash.
        return False, ("Zugangsdaten enthalten Sonderzeichen/Umlaute — die MT5-Start-ini "
                       "kann nur ASCII. Login einmal von Hand im Terminal machen "
                       "(Datei → Bei Handelskonto anmelden).")
    install_dir = os.path.dirname(os.path.abspath(path))
    pids = provision.terminal_pids(install_dir)
    wrong = None
    if pids:
        # Steht das laufende Terminal nachweislich im FALSCHEN Konto (Snapshot-
        # Beweis aus dem Copier-Status), hilft Fenster-nach-vorn nicht — nur ein
        # Neustart mit erzwungenem Login. Nur mit frischem Status-Beweis killen.
        status_fn = re.sub(r"^config", "status", fname, count=1, flags=re.I)
        st = read_json(os.path.join(HERE, status_fn), {}) or {}
        age = None
        try:
            age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
        except (ValueError, TypeError):
            pass
        if st.get("running") and age is not None and age <= 15:
            wrong = st.get("wrong_login")
        if wrong and creds:
            print(f"[panel] {fname}: Terminal im falschen Konto ({wrong}) — Neustart mit "
                  f"erzwungenem Login {creds.get('login')}.", flush=True)
            # Kurze Grace statt der 15 s von _kill_terminal_at: ab 2 PIDs risse
            # der synchrone Kill sonst den 25-s-Proxy-Timeout von app.py.
            for pid in provision.terminal_pids(install_dir):
                provision._taskkill(pid, grace_s=5)
            # Alt-Snapshot SOFORT entwerten — sonst stempelt der Copier daraus
            # weiter 'FALSCHES Konto', waehrend das neue Terminal bootet.
            _drop_snapshot(cfg)
            pids = []
    if pids:
        # Fenster-Beweis (18.08.2026, The5ers-Fund: nach einem Haenger blieb
        # ein Terminal-Prozess OHNE Fenster zurueck — der zweite Start-Klick
        # meldete 'laeuft', aber nichts oeffnete sich). AppActivate liefert
        # False, wenn der Prozess kein aktivierbares Fenster hat: dann Zombie
        # killen und unten regulaer kalt starten.
        # Fenster-Beweis + Nach-vorn-holen in einem (25.08.2026): der robuste
        # Helfer prueft MainWindowHandle (Zombie-Semantik unveraendert) und
        # ueberwindet den Foreground-Lock per Alt-Tastendruck.
        vorn = _fenster_nach_vorn(pids[0])
        if not vorn:
            print(f"[panel] {fname}: Terminal-Prozess ohne Fenster (Zombie) — "
                  f"beende und starte kalt neu.", flush=True)
            for pid in provision.terminal_pids(install_dir):
                provision._taskkill(pid, grace_s=5)
            pids = []
    if pids:
        # Laeuft schon: Fenster ist vorn — ABER auch hier die Selbstheilung
        # anstossen: liefert das laufende Terminal keinen frischen Snapshot
        # (EA fehlt), wird es neu gestartet und das EA automatisch aufgezogen.
        # EA auch im WARM-Pfad aktuell kompilieren (15.08.2026, Zwei-Plan-Test:
        # das warm gebliebene test321323-Terminal behielt das alte EA ohne
        # Balance-Header — Master-P&L fehlte nur dort). MT5 laedt ein neu
        # kompiliertes EA am laufenden Chart von selbst neu, kein Neustart noetig.
        _ensure_ea_compiled(fname, install_dir)
        threading.Thread(target=_heal_ea,
                         args=(fname, cfg, install_dir, time.time(), 8, True),
                         daemon=True).start()
        if wrong and not creds:
            return True, (f"Terminal läuft, aber im FALSCHEN Konto ({wrong} statt {expected or '?'}) — "
                          f"im Terminal Datei → „Bei Handelskonto anmelden“ auf das richtige Konto wechseln.")
        return True, "Terminal läuft — EA wird geprüft und notfalls automatisch aufgezogen"
    # Neuer MT5-Build wartet? Erst still einspielen, dann starten — sonst fragt MT5 selbst per UAC (08.10.2026, s. _update_vor_start_noetig)
    aus = None if ohne_update else _update_vor_start_noetig(install_dir)
    if aus:
        with HEAL_LOCK:
            schon = install_dir in UPDATE_LAEUFT
            if not schon:
                UPDATE_LAEUFT.add(install_dir)
                HEAL_ACTIVE.add(install_dir)
        if not schon:
            print(f"[mt5-update] {fname}: neuer Build {'.'.join(map(str, aus[0][2]))} wartet — still einspielen, dann starten.", flush=True)
            threading.Thread(target=_update_dann_start, args=(fname, install_dir, aus, creds), daemon=True).start()
        return True, "Neuer MT5-Build wird still eingespielt (ohne Windows-Abfrage) — das Terminal startet gleich danach"
    _update_abwarten(install_dir)  # stilles MT5-Update gerade dran? (01.10.2026)
    _vor_kaltstart(fname, install_dir)   # Download-Kennung + HKCU-Häkchen weg (23.10.2026)
    try:
        if creds:
            # Login-Zwang: [Common]-only-ini (KEIN [StartUp] — das wuerde bei jedem
            # Start einen weiteren EA-Chart aufziehen; das EA haengt am Profil und
            # die Selbstheilung unten faengt den Fehlfall). ASCII ist Pflicht,
            # UTF-16-inis ignoriert MT5 stillschweigend (Fund 14.08.2026).
            _drop_snapshot(cfg)  # Alt-Beweis eines frueheren (Falsch-)Logins entwerten
            # EA aktuell kompilieren, solange das Terminal aus ist (Master-P&L
            # braucht den v3-Header — die .ex5 auf den PCs war aelter als die .mq5)
            _ensure_ea_compiled(fname, install_dir)
            # EA-Sicherstellung, Rangfolge (15.08.2026, reason=4-Fund): ZUERST fest
            # ins Chart-Profil schreiben — nur das ueberlebt das Profil-Laden.
            # Klappt das nicht (frische Installation ohne Profil), klassischer
            # [StartUp]-Aufzug als Fallback — der traegt dort, weil es kein
            # gespeichertes Profil gibt, das sein Chart ersetzen koennte.
            startup = ""
            if not _inject_ea_into_profile(fname, cfg, install_dir):
                startup = _startup_attach_part(fname, cfg, install_dir)
            ini = os.path.join(install_dir, "prophos-login.ini")
            try:
                with open(ini, "w", encoding=provision.INI_ENCODING) as f:
                    f.write(provision.build_login_ini(creds["login"], creds["password"],
                                                      creds.get("server") or cfg.get("master_server") or "")
                            + startup)
                subprocess.Popen([path, f"/config:{ini}"], cwd=install_dir)
            finally:
                # Auch bei Write-/Start-Fehlern aufraeumen — nie eine Passwort-ini
                # ungeplant liegen lassen.
                _remove_later(ini)
            msg = ("Terminal gestartet — Login wird erzwungen"
                   + (", Lese-EA wird direkt aufgezogen" if startup else "")
                   + "; Selbstheilung wacht im Hintergrund")
        else:
            # Auch OHNE hinterlegte Zugangsdaten das EA fest ins Profil schreiben
            # (25.08.2026, Finns Live-Fund: dieser Zweig startete nackt, die
            # Heilung hing das EA nur ans temporaere [StartUp]-Chart — das
            # gespeicherte Profil ersetzte es beim naechsten Boot, jeder
            # Trade-Start zahlte die volle Heilung erneut und der Bot kam
            # 'gar nicht oder viel zu spaet'). Terminal ist hier aus, die
            # .chr-Dateien liegen still — Injektion ist sicher.
            _ensure_ea_compiled(fname, install_dir)
            _inject_ea_into_profile(fname, cfg, install_dir)
            subprocess.Popen([path], cwd=install_dir)
            msg = "Terminal gestartet — Login automatisch; EA wird geprüft und notfalls selbst aufgezogen"
        # Selbstheilung im Hintergrund: fliesst der Snapshot in 45 s nicht,
        # wird das EA automatisch per [StartUp] nachgezogen. Schnell-Pfad nur
        # OHNE Login-Zwang (der Zwangs-Start loescht die Datei bewusst).
        threading.Thread(target=_heal_ea,
                         args=(fname, cfg, install_dir, time.time(), 45, not creds),
                         daemon=True).start()
        # Start-Dialoge (Login/OK) automatisch bestaetigen — s. _ok_dialog_watcher
        threading.Thread(target=_ok_dialog_watcher, args=(install_dir,),
                         daemon=True).start()
        # MT5-Einloggen-Fenster dieses Kontos (08.10.2026, s. _login_ok_wache; seit 23.10.2026 bis zur Verbindung) — nur mit bekanntem Konto
        if expected:
            threading.Thread(target=_login_ok_wache, args=(fname, expected, install_dir), daemon=True).start()
        # Fenster nach vorn, sobald es da ist (sonst startet MT5 hinter dem Browser)
        _front_when_up(install_dir)
        return True, msg
    except (OSError, ValueError) as e:
        # ValueError deckt UnicodeEncodeError ab (Review-Fund 15.08.2026) —
        # der ASCII-Wachter oben faengt das normal vorher, aber ein Handler-
        # Crash ohne JSON-Antwort darf daraus nie wieder werden.
        return False, f"Start fehlgeschlagen: {e}"


PAGE = r"""<!doctype html><html lang=de><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Echo-Panel</title><style>
/* Design-Tokens aus prophos.html uebernommen (14.08.2026) — gleiche Sprache wie Prophos */
:root{
  --violet:#5447CE;--violet-dark:#4539b8;--violet-tint:rgba(84,71,206,.08);
  --ink:#101828;--ink-2:#1D2939;--sub:#667085;--sub-2:#98A2B3;
  --border:#E5E7EB;--border-soft:#EEF2F6;--surface:#FFFFFF;--surface-tint:#F2F4F7;--bg:#FAFBFC;
  --good:#12B76A;--warn:#F79009;--danger:#F04438;
  --r-sm:8px;--r-md:12px;--r-lg:16px;
  --shadow-card:0 1px 2px rgba(16,24,40,.04);
  --shadow-card-hover:0 4px 12px rgba(16,24,40,.06);
  --shadow-input-focus:0 0 0 4px rgba(84,71,206,.12);
  --ease:cubic-bezier(.4,0,.2,1);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:'Inter','Segoe UI',system-ui,sans-serif;line-height:1.5;
  -webkit-font-smoothing:antialiased}
.mono{font-family:'JetBrains Mono','Consolas',monospace;font-variant-numeric:tabular-nums}
.tnum{font-variant-numeric:tabular-nums}
button{font-family:inherit;cursor:pointer}

/* Topbar */
.topbar{background:var(--surface);border-bottom:1px solid var(--border);
  padding:14px 28px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:20}
.topbar h1{font-size:16px;font-weight:600;margin:0;letter-spacing:-.01em}
.topbar .sub{font-size:12.5px;color:var(--sub)}
.copier-chip{margin-left:auto;display:inline-flex;align-items:center;gap:7px;
  font-size:12.5px;font-weight:500;color:var(--sub);
  background:var(--surface-tint);border:1px solid var(--border);border-radius:20px;padding:5px 12px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.dot.on{background:var(--good);box-shadow:0 0 0 3px rgba(18,183,106,.15)}
.dot.off{background:var(--danger);box-shadow:0 0 0 3px rgba(240,68,56,.12)}
.dot.idle{background:#98A2B3;box-shadow:0 0 0 3px rgba(152,162,179,.15)}

.wrap{max-width:1340px;margin:0 auto;padding:22px 28px 60px}
.view-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:16px;flex-wrap:wrap}
.view-title{font-size:22px;font-weight:600;letter-spacing:-.02em;margin:0}
.view-sub{font-size:13.5px;color:var(--sub);margin:2px 0 0}

/* Buttons — wie Prophos */
.btn{display:inline-flex;align-items:center;gap:7px;padding:8px 14px;border-radius:8px;
  font-size:13px;font-weight:500;transition:all .15s var(--ease);border:1px solid transparent}
.btn-primary{background:var(--violet);color:#fff;
  box-shadow:0 1px 2px rgba(16,24,40,.06),0 2px 6px rgba(84,71,206,.22)}
.btn-primary:hover{background:var(--violet-dark);transform:translateY(-1px)}
.btn-primary:disabled{opacity:.55;transform:none;cursor:default}
.btn-ghost{background:var(--surface);border-color:var(--border);color:var(--ink)}
.btn-ghost:hover{background:var(--surface-tint)}
.btn-sm{padding:6px 11px;font-size:12px}

/* Banner */
.banner{background:rgba(240,68,56,.08);border:1px solid rgba(240,68,56,.35);color:#c03128;
  padding:11px 14px;border-radius:var(--r-md);font-size:13px;margin-bottom:14px;white-space:pre-line}
.jobbar{background:var(--violet-tint);border:1px solid rgba(84,71,206,.25);color:var(--violet-dark);
  padding:10px 14px;border-radius:var(--r-md);font-size:13px;margin-bottom:14px;cursor:pointer;
  display:flex;align-items:center;gap:10px}
.jobbar .spin{width:14px;height:14px;border:2.5px solid rgba(84,71,206,.25);border-top-color:var(--violet);
  border-radius:50%;animation:spin .7s linear infinite;flex-shrink:0}
.jobbar.err{background:rgba(240,68,56,.08);border-color:rgba(240,68,56,.35);color:#c03128}
.mt5upd{background:rgba(247,144,9,.08);border:1px solid rgba(247,144,9,.4);color:var(--ink);padding:12px 14px;
  border-radius:var(--r-md);font-size:13px;margin-bottom:14px;display:flex;align-items:center;gap:14px;justify-content:space-between;flex-wrap:wrap}
.mt5upd-sub{color:var(--sub);font-size:12.5px;margin-top:3px;max-width:640px}
.mt5upd-msg{color:var(--ink);font-weight:500;margin-top:4px}
@keyframes spin{to{transform:rotate(360deg)}}

/* Account-Grid */
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr))}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:16px;box-shadow:var(--shadow-card);transition:box-shadow .15s var(--ease)}
.card:hover{box-shadow:var(--shadow-card-hover)}
.acc-top{display:flex;align-items:center;gap:8px}
.acc-name{font-size:15px;font-weight:600;letter-spacing:-.01em}
.acc-state{margin-left:auto;font-size:12px;color:var(--sub);display:inline-flex;align-items:center;gap:6px}
.acc-broker{font-size:12.5px;color:var(--sub);margin-top:3px}
.acc-broker b{color:var(--ink);font-weight:600}
.acc-route{font-size:12px;color:var(--sub-2);margin-top:1px}
.acc-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.stat{background:var(--surface-tint);border-radius:var(--r-sm);padding:7px 4px;text-align:center}
.stat b{display:block;font-size:15px;font-weight:600;font-variant-numeric:tabular-nums}
.stat span{font-size:10.5px;color:var(--sub)}
.stat.hot b{color:var(--violet)}
.acc-acts{display:flex;gap:8px;margin-top:13px;align-items:center;flex-wrap:wrap}
.warnbox{background:rgba(247,144,9,.1);border:1px solid rgba(247,144,9,.35);color:#b45309;
  padding:8px 10px;border-radius:var(--r-sm);font-size:12px;margin-top:10px}
.standbybox{color:var(--sub);font-size:12px;margin-top:10px}

/* Details (aufklappbar) */
.details{display:none;border-top:1px solid var(--border-soft);margin-top:14px;padding-top:13px}
.card.open .details{display:block}
label{display:block;font-size:11px;font-weight:600;color:var(--sub);margin:10px 0 4px;
  text-transform:uppercase;letter-spacing:.05em}
input,select{width:100%;background:var(--surface);border:1px solid var(--border);color:var(--ink);
  border-radius:var(--r-sm);padding:8px 10px;font:13px inherit;font-family:inherit;
  transition:border-color .12s,box-shadow .12s}
input:focus,select:focus{outline:0;border-color:var(--violet);box-shadow:var(--shadow-input-focus)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.map{display:grid;grid-template-columns:1fr auto 1fr auto;gap:6px;align-items:center;margin-top:5px}
.map span{color:var(--sub-2);font-size:12px}
.x{background:none;border:0;color:var(--sub-2);font-size:15px;padding:0 4px}
.x:hover{color:var(--danger)}
.msg{font-size:12px;font-family:'JetBrains Mono','Consolas',monospace;color:#058a50;min-height:16px;flex:1}
.msg.err{color:#c03128}
.dirty-hint{font-size:11px;color:#b45309;display:none}
.card[data-dirty] .dirty-hint{display:inline}
pre.log{background:var(--surface-tint);border:1px solid var(--border-soft);border-radius:var(--r-sm);
  padding:9px;margin:10px 0 0;font-size:11px;line-height:1.55;
  font-family:'JetBrains Mono','Consolas',monospace;
  max-height:150px;overflow:auto;color:var(--sub);white-space:pre-wrap}
.empty{color:var(--sub);padding:40px 20px;text-align:center}

/* Modals — wie Prophos */
.modal-bg{position:fixed;inset:0;background:rgba(16,24,40,.5);
  backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);
  display:none;align-items:center;justify-content:center;z-index:200;padding:20px}
.modal-bg.open{display:flex;animation:fadeIn .15s var(--ease)}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);
  padding:24px 26px;width:100%;max-width:460px;max-height:90vh;overflow-y:auto;
  box-shadow:0 20px 60px -10px rgba(16,24,40,.25);animation:modalIn .2s var(--ease)}
@keyframes modalIn{from{opacity:0;transform:translateY(8px) scale(.98)}to{opacity:1;transform:none}}
.modal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px}
.modal-head h3{margin:0;font-size:18px;font-weight:600;letter-spacing:-.01em}
.modal-x{width:32px;height:32px;padding:0;display:inline-flex;align-items:center;justify-content:center;
  background:transparent;border:1px solid transparent;border-radius:8px;color:var(--sub);font-size:16px}
.modal-x:hover{background:rgba(16,24,40,.06);color:var(--ink);border-color:var(--border)}
.modal-sub{font-size:13px;color:var(--sub);margin:0 0 16px}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:20px;align-items:center}
.modal input.big{font-size:24px;font-weight:600;padding:10px 12px;text-align:center;
  font-variant-numeric:tabular-nums}
.rule{color:var(--sub-2);font-size:11.5px;margin-top:10px;line-height:1.45}

/* Provisionierungs-Schritte */
/* Trade-Plaene: drei Spalten geplant / laufend / beendet */
.plans-grid{display:grid;gap:14px;grid-template-columns:repeat(3,1fr);margin-top:14px}
@media (max-width:1000px){.plans-grid{grid-template-columns:1fr}}
.plan-col h4{margin:0 0 8px;font-size:12px;font-weight:600;color:var(--sub);
  text-transform:uppercase;letter-spacing:.06em;display:flex;align-items:center;gap:7px}
.plan-col h4 .cnt{background:var(--surface-tint);border:1px solid var(--border);
  border-radius:12px;padding:0 7px;font-size:11px;color:var(--sub)}
.plan{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:11px 13px;box-shadow:var(--shadow-card);margin-bottom:10px;font-size:13px}
.plan.laufend{border-color:rgba(18,183,106,.45)}
.plan-top{display:flex;align-items:center;gap:8px}
.plan-top b{font-size:13.5px}
.plan-top .x{margin-left:auto}
.plan-meta{color:var(--sub);font-size:12px;margin-top:3px}
.plan-live{color:#0d9668;font-size:12px;margin-top:4px;font-variant-numeric:tabular-nums}
.plan-empty{color:var(--sub-2);font-size:12.5px;padding:12px 4px}
.steps{margin-top:14px;display:grid;gap:6px;font-size:13px}
.step{display:flex;gap:9px;align-items:baseline;color:var(--sub-2)}
.step .st{width:16px;text-align:center;flex-shrink:0;font-weight:700}
.step.done{color:#0d9668}.step.running{color:#b45309}.step.error{color:#c03128}
.step .note{color:var(--sub-2);font-size:11px}
</style></head><body>

<div class=topbar>
  <h1>Echo-Panel</h1>
  <span class=sub>lokal auf diesem PC · Prophos bleibt unangetastet</span>
  <span class=sub id=version-chip title="Version — aktualisiert sich selbst von GitHub"></span>
  <span class=copier-chip id=copier-chip><span class="dot off"></span>Copier</span>
</div>

<div class=wrap>
  <div class=view-head>
    <div>
      <h2 class=view-title>Accounts</h2>
      <p class=view-sub id=count-sub>–</p>
    </div>
    <button class="btn btn-primary" id=add-open>＋ Account hinzufügen</button>
  </div>
  <div id=notice></div>
  <div class=grid id=app><div class=empty>lade…</div></div>

  <div class=view-head style="margin-top:30px">
    <div>
      <h2 class=view-title style="font-size:19px">Trade-Pläne</h2>
      <p class=view-sub>geplant → laufend → beendet — wandert automatisch mit deinen Positionen</p>
    </div>
  </div>
  <div class=plans-grid id=plans></div>
</div>

<!-- Trade-Plan-Modal — dedizierte Verdrahtung (Projektregel: kein Sammel-Handler) -->
<div class=modal-bg id=plan-bg>
 <div class=modal>
  <div class=modal-head><h3 id=plan-title>Trade planen</h3>
    <button class=modal-x id=plan-x>✕</button></div>
  <p class=modal-sub id=plan-sub></p>
  <label>Multiplikator</label>
  <input class=big id=plan-mult type=number step=0.001 min=0>
  <div class=modal-actions>
    <span class=msg id=plan-msg></span>
    <button class="btn btn-ghost" id=plan-cancel>Abbrechen</button>
    <button class="btn btn-primary" id=plan-start>Trade starten</button>
  </div>
 </div>
</div>

<!-- Account-hinzufuegen-Modal — dedizierte Verdrahtung -->
<div class=modal-bg id=add-bg>
 <div class=modal>
  <div class=modal-head><h3>Account hinzufügen</h3>
    <button class=modal-x id=add-x>✕</button></div>
  <p class=modal-sub>klont das Master-Vorlage-Terminal, loggt ein, legt EA + Config an — alles automatisch</p>
  <div class=row>
    <div><label>Name (kurz, nur Buchstaben/Zahlen)</label><input data-p=name placeholder="z.B. ftmo1"></div>
    <div><label>Login (Kontonummer)</label><input data-p=login placeholder="z.B. 12345678"></div>
  </div>
  <div class=row style="margin-top:2px">
    <div><label>Passwort (sichtbar — auf Wunsch)</label><input data-p=password autocomplete=off spellcheck=false></div>
    <div><label>Server</label><input data-p=server placeholder="z.B. FusionMarkets-Demo"></div>
  </div>
  <div id=add-steps></div>
  <div class=modal-actions>
    <span class=msg id=add-msg></span>
    <button class="btn btn-primary" id=add-start>Fertig — automatisch einrichten</button>
  </div>
 </div>
</div>

<script>
const state={}, openSet=new Set();
let lastJob=null;
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function mapRows(map){
  const e=Object.entries(map);
  return e.map(([k,v])=>`<div class=map>
    <input value="${esc(k)}" data-mk placeholder="Master-Symbol">
    <span>→</span>
    <input value="${esc(v)}" data-mv placeholder="Hedge-Symbol">
    <button class=x data-del title="Zeile entfernen">×</button></div>`).join('')
   +`<div class=map><input data-mk placeholder="neues Master-Symbol">
     <span>→</span><input data-mv placeholder="Hedge-Symbol"><span></span></div>`;
}
function card(d){
  const s=d.status||{}, live=d.alive;
  // Standby statt Dauer-Warnung (25.08.2026, wie in prophos.html): Terminal
  // absichtlich zu + nichts im Spiel -> ruhiger Chip, keine orange Box.
  const standby=live&&!!s.standby;
  const pos=(s.master_positions||[]).length, hed=Object.keys(s.hedges||{}).length;
  const broker=s.master_server||d.master_server||'Broker unbekannt';
  const isOpen=openSet.has(d.file);
  return `<div class="card${isOpen?' open':''}" data-file="${esc(d.file)}">
   <div class=acc-top><span class=acc-name>${esc(d.name)}</span>
     <span class=acc-state><span class="dot ${live?(standby?'idle':'on'):'off'}"></span>${live?(standby?'Standby':(s.note?'läuft':'aktiv')):'gestoppt'}</span></div>
   <div class=acc-broker><b>${esc(broker)}</b></div>
   <div class=acc-route><span class=mono>${esc(s.master_login||d.master_expected||'—')}</span> → Hedge <span class=mono>${esc(s.hedge_login||d.hedge_expected||'—')}</span></div>
   ${s.note&&!standby?`<div class=warnbox>${esc(s.note)}</div>`:''}
   ${standby?`<div class=standbybox>Master-Terminal zu — Karte wird aktiv, sobald der Trade-Start es öffnet</div>`:''}
   ${(s.blocked||[]).length?`<div class=warnbox>Keine neuen Hedges für Master-Pos: ${esc((s.blocked||[]).join(', '))} (Mehrfach-Hedge-Schutz oder Hand-Close)</div>`:''}
   <div class=acc-stats>
     <div class="stat${pos?' hot':''}"><b>${pos}</b><span>Positionen</span></div>
     <div class="stat${hed?' hot':''}"><b>${hed}</b><span>Hedges</span></div>
     <div class=stat><b>×${esc(d.multiplier??'–')}</b><span>Multi</span></div>
   </div>
   <div class=acc-acts>
     <button class="btn btn-primary btn-sm" data-plan>Trade planen</button>
     <button class="btn btn-ghost btn-sm" data-toggle>${isOpen?'Details ▴':'Details ▾'}</button>
     <span class=dirty-hint>ungespeicherte Änderung</span>
     <span class=msg></span>
   </div>
   <div class=details>
     <div class=row>
       <div><label>Multiplikator</label><input type=number step=0.001 min=0 value="${esc(d.multiplier??'')}" data-f=multiplier></div>
     </div>
     <label>Symbol-Mapping (Master → Hedge)</label>
     <div data-maps>${mapRows(d.symbol_map||{})}</div>
     <div class=acc-acts>
       <button class="btn btn-primary btn-sm" data-save>Speichern &amp; pushen</button>
       ${d.has_terminal?`<button class="btn btn-ghost btn-sm" data-term>Terminal öffnen</button>`:''}
     </div>
     <div style="font-size:11px;color:var(--sub-2);margin-top:8px">${esc(d.file)} · magic ${esc(d.magic)} · ${esc(d.snapshot_file||'')}</div>
     <pre class=log>${esc((s.log||[]).slice(-14).join('\n')||'noch keine Log-Zeilen')}</pre>
   </div>
  </div>`;
}
function jobSteps(job){
  const mark=s=>s.state==='done'?'✓':s.state==='running'?'…':s.state==='error'?'✗':'·';
  const labels={pruefen:'Prüfen & Kennwerte vergeben',klonen:'Terminal-Ordner klonen',
    login:'Erststart — Datenordner anlegen',
    ea:'Server-Liste + Lese-EA + Preset einlegen',
    neustart:'Start mit Login + EA (Zugangsdaten-Datei wird danach gelöscht)',config:'Config anlegen'};
  let h=`<div class=steps>${job.steps.map(s=>`<div class="step ${s.state}"><span class=st>${mark(s)}</span><span>${labels[s.key]||s.key}${s.note?` <span class=note>${esc(s.note)}</span>`:''}</span></div>`).join('')}`;
  if(job.error)h+=`<div class="step error" style="margin-top:6px"><span class=st>✗</span><span>${esc(job.error)}</span></div>`;
  else if(job.done)h+=`<div class="step done"><span class=st>✓</span><span>fertig — Karte „${esc(job.name)}" erscheint gleich</span></div>`;
  return h+'</div>';
}
async function load(){
  const r=await fetch('/api/instances'); const d=await r.json();
  lastJob=d.job;
  const app=document.getElementById('app');
  d.instances.forEach(x=>state[x.file]=x);
  // Kopf: Copier-Status + Zaehler
  const anyAlive=d.instances.some(x=>x.alive);
  document.getElementById('copier-chip').innerHTML=`<span class="dot ${anyAlive?'on':'off'}"></span>Copier ${anyAlive?'läuft':'gestoppt'}`;
  document.getElementById('version-chip').textContent=d.version?('v'+d.version):'';
  const brokers=new Set(d.instances.map(x=>(x.status||{}).master_server||x.master_server).filter(Boolean));
  document.getElementById('count-sub').textContent=`${d.instances.length} Accounts · ${brokers.size} Broker · ein Copier-Prozess`;
  // Hinweise: Konflikte + laufende Provisionierung
  let n='';
  if(d.conflicts.length)n+=`<div class=banner>⛔ ${d.conflicts.map(esc).join('\n⛔ ')}</div>`;
  if(d.job&&!d.job.done&&document.getElementById('add-bg').style.display!=='flex'){
    const cur=d.job.steps.find(s=>s.state==='running');
    n+=`<div class=jobbar id=jobbar><span class=spin></span>Account „${esc(d.job.name)}" wird eingerichtet — ${esc(cur?cur.key:'…')} … (klicken für Details)</div>`;
  }else if(d.job&&d.job.done&&d.job.error&&document.getElementById('add-bg').style.display!=='flex'){
    n+=`<div class="jobbar err" id=jobbar>✗ Account „${esc(d.job.name)}": ${esc(d.job.error.slice(0,140))}… (klicken für Details)</div>`;
  }
  // MT5-Updates ohne Nachfrage (08.10.2026): Kasten, solange die stille Aufgabe fehlt — Klick → Windows-Abfrage im Vordergrund
  const mu=d.mt5_update, mj=d.mt5_update_job||{};
  if((mu&&mu.aufgabe_ok===false)||mj.laeuft||(mj.msg&&Date.now()/1000-(mj.t||0)<120)){
    const fertig=mu&&mu.aufgabe_ok;
    n+=`<div class=mt5upd><div><b>${fertig?'✓ MT5-Updates laufen ohne Nachfrage':'MT5-Updates ohne Nachfrage einrichten'}</b>`
      +`<div class=mt5upd-sub>${fertig?'':'Einmal je PC: Windows fragt „Windows PowerShell – Änderungen zulassen?" — „Ja" klicken. Danach spielt Echo neue MetaTrader-Versionen still ein, die Update-Abfrage kommt nicht mehr.'}${mj.msg?`<div class=mt5upd-msg>${esc(mj.msg)}</div>`:''}</div></div>`
      +(fertig?'':`<button class="btn btn-primary" id=mt5upd-btn ${mj.laeuft?'disabled':''}>${mj.laeuft?'wartet auf „Ja" …':'Jetzt einrichten'}</button>`)+`</div>`;
  }
  document.getElementById('notice').innerHTML=n;
  const jb=document.getElementById('jobbar'); if(jb)jb.addEventListener('click',openAdd);
  const mb=document.getElementById('mt5upd-btn');
  if(mb)mb.addEventListener('click',async()=>{mb.disabled=true;mb.textContent='wartet auf „Ja" …';
    try{const r=await fetch('/api/mt5-update-einrichten',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const j=await r.json();
      if(!j.ok){mb.disabled=false;mb.textContent='Jetzt einrichten';alert(j.msg||'Nicht gestartet');return}}catch(e){}
    setTimeout(load,800)});
  // Karten
  if(!d.instances.length){app.innerHTML='<div class=empty>Keine Accounts. Oben rechts „＋ Account hinzufügen".</div>';}
  else{
    const empty=app.querySelector('.empty'); if(empty)empty.remove();
    const files=new Set(d.instances.map(x=>x.file));
    app.querySelectorAll('.card').forEach(c=>{if(!files.has(c.getAttribute('data-file')))c.remove()});
    for(const x of d.instances){
      const cur=app.querySelector(`.card[data-file="${CSS.escape(x.file)}"]`);
      // Karten mit ungespeicherten Eingaben oder Fokus NICHT überschreiben (3s-Reload)
      if(cur&&(cur.hasAttribute('data-dirty')||cur.contains(document.activeElement)))continue;
      const html=card(x);
      if(cur)cur.outerHTML=html; else app.insertAdjacentHTML('beforeend',html);
    }
  }
  // Trade-Plaene rendern (keine Eingabefelder darin -> immer neu zeichnen ok)
  renderPlans(d.plans||[]);
  // Add-Modal-Schritte live aktualisieren, wenn offen
  if(document.getElementById('add-bg').classList.contains('open'))renderAddJob();
}
function fmtT(iso){if(!iso)return'';const d=new Date(iso);return d.toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'})+' '+d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}
function dur(a,b){if(!a||!b)return'';const m=Math.round((new Date(b)-new Date(a))/60000);return m<60?`${m} min`:`${Math.floor(m/60)} h ${m%60} min`}
function planCard(p){
  const d=state[p.file]||{}, s=d.status||{};
  const pos=(s.master_positions||[]).length, hed=Object.keys(s.hedges||{}).length;
  let meta='', live='';
  if(p.status==='geplant')meta=`geplant ${fmtT(p.armed_at||p.created_at)}`;
  if(p.status==='laufend'){meta=`läuft seit ${fmtT(p.started_at)}`;
    live=`<div class=plan-live>● ${pos} Position(en) · ${hed} Hedge(s) bewacht</div>`}
  if(p.status==='beendet')meta=`${fmtT(p.started_at)} → ${fmtT(p.ended_at)} · ${dur(p.started_at,p.ended_at)}`;
  return `<div class="plan ${p.status}">
    <div class=plan-top><b>${esc(d.name||p.name)}</b>
      <button class=x data-plandel="${p.id}" data-planstatus="${p.status}" title="Plan löschen">×</button></div>
    <div class=plan-meta>×${esc(p.multiplier)} · ${esc((s.master_server||d.master_server||''))}</div>
    <div class=plan-meta>${esc(meta)}</div>
    ${live}
  </div>`;
}
function renderPlans(plans){
  const cols=[['geplant','Geplant'],['laufend','Laufend'],['beendet','Beendet']];
  document.getElementById('plans').innerHTML=cols.map(([k,label])=>{
    let list=plans.filter(p=>p.status===k);
    if(k==='beendet')list=list.slice().reverse();
    return `<div class=plan-col><h4>${label}<span class=cnt>${list.length}</span></h4>
      ${list.map(planCard).join('')||`<div class=plan-empty>${k==='geplant'?'Kein Plan — „Trade planen" auf einer Karte.':k==='laufend'?'Nichts im Markt.':'Noch keine abgeschlossenen Trades.'}</div>`}
    </div>`;
  }).join('');
}
document.getElementById('plans').addEventListener('click',async e=>{
  const pid=e.target.getAttribute&&e.target.getAttribute('data-plandel');
  if(!pid)return;
  if(e.target.getAttribute('data-planstatus')==='laufend'&&!confirm('Dieser Plan LÄUFT gerade (Position offen). Wirklich nur den Plan-Eintrag löschen? Die Position und der Hedge bleiben unberührt.'))return;
  await fetch('/api/plan-delete?id='+encodeURIComponent(pid),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  load();
});
document.getElementById('app').addEventListener('input',e=>{
  const c=e.target.closest('.card'); if(c)c.setAttribute('data-dirty','1');
});
document.getElementById('app').addEventListener('change',e=>{
  const c=e.target.closest('.card'); if(c)c.setAttribute('data-dirty','1');
});

// ── Trade-Plan-Modal ────────────────────────────────────────────────────────
const planBg=document.getElementById('plan-bg');
function openPlan(file){
  const d=state[file]; if(!d)return;
  planBg.dataset.file=file;
  const s=d.status||{};
  document.getElementById('plan-title').textContent='Trade planen — '+d.name;
  document.getElementById('plan-sub').textContent=`${s.master_server||d.master_server||''} · Master ${d.master_expected||'—'} → Hedge ${d.hedge_expected||'—'}`;
  document.getElementById('plan-mult').value=d.multiplier??'';
  const m=document.getElementById('plan-msg'); m.className='msg'; m.textContent='';
  planBg.classList.add('open'); planBg.style.display='flex';
  document.getElementById('plan-mult').focus();
}
function closePlan(){planBg.classList.remove('open');planBg.style.display='none'}
document.getElementById('plan-cancel').addEventListener('click',closePlan);
document.getElementById('plan-x').addEventListener('click',closePlan);
document.getElementById('plan-start').addEventListener('click',async()=>{
  const file=planBg.dataset.file, d=state[file]||{};
  const msg=document.getElementById('plan-msg');
  // Haerteste Falle zuerst: ohne laufenden Copier wird NICHTS gehedgt.
  if(!d.alive){
    if(!confirm(`Der Copier ist GESTOPPT — deine Trades würden NICHT gehedgt!\n\nErst start-copier.bat starten, dann hier erneut auf „Trade starten".\n\nTrotzdem fortfahren (nur Werte pushen + Terminal öffnen)?`)){
      msg.className='msg err';msg.textContent='Abgebrochen — erst den Copier starten.';return}
  }
  // Liefert der Master gerade nichts (Terminal zu / EA fehlt), ist das KEIN
  // Abbruchgrund mehr: Terminal-Start + EA-Selbstheilung erledigen das, und
  // die Bereitschafts-Anzeige unten sagt, wann wirklich getradet werden darf.
  const patch={multiplier:document.getElementById('plan-mult').value};
  if(!patch.multiplier){
    msg.className='msg err';msg.textContent='Multiplikator ausfüllen.';return}
  msg.className='msg';msg.textContent='pushe…';
  const r=await fetch('/api/save?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  const s=await r.json();
  if(!s.ok){msg.className='msg err';msg.textContent='Fehler: '+s.msg;return}
  // Trade-Plan anlegen/aktualisieren: startet als "geplant" und wandert von
  // selbst nach "laufend"/"beendet", sobald die Position auf-/zugeht.
  try{await fetch('/api/plan?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({multiplier:patch.multiplier})});}catch(e){}
  msg.textContent='gepusht — öffne Terminal…';
  const t=await fetch('/api/start-terminal?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const ts=await t.json();
  if(!ts.ok){msg.className='msg err';msg.textContent='Multiplikator gepusht, aber Terminal: '+ts.msg;return}
  // Bereitschafts-Ueberwachung: der Dialog bleibt offen und meldet live, wann
  // der Snapshot wirklich fliesst — erst DANN traden. Die EA-Selbstheilung im
  // Hintergrund braucht im Reparaturfall bis ~1,5 Minuten.
  const t0=Date.now();
  msg.className='msg';msg.textContent=`⏳ ×${patch.multiplier} gepusht · Terminal startet, Login automatisch…`;
  const timer=setInterval(async()=>{
    let inst=null;
    try{const rr=await fetch('/api/instances');const dd=await rr.json();inst=dd.instances.find(x=>x.file===file);}catch(e){}
    const sec=Math.round((Date.now()-t0)/1000);
    if(inst&&inst.alive&&!(inst.status||{}).note){
      clearInterval(timer);
      msg.className='msg';
      msg.textContent=`✓ Bereit — ×${patch.multiplier} aktiv, Hedge bewacht. Jetzt im Terminal traden.`;
      setTimeout(load,1000);
      return;
    }
    if(sec>170){
      clearInterval(timer);
      msg.className='msg err';
      msg.textContent='Terminal liefert nach 3 Minuten nichts — Details-Log der Karte prüfen.';
      return;
    }
    msg.textContent=sec>50
      ?`⏳ EA wird geprüft und notfalls automatisch aufgezogen… (${sec}s)`
      :`⏳ Terminal startet, Login automatisch… (${sec}s)`;
  },3000);
});

// ── Account-hinzufuegen-Modal ───────────────────────────────────────────────
const addBg=document.getElementById('add-bg');
function renderAddJob(){
  document.getElementById('add-steps').innerHTML=lastJob?jobSteps(lastJob):'';
  const busy=lastJob&&!lastJob.done;
  document.getElementById('add-start').disabled=!!busy;
  addBg.querySelectorAll('[data-p]').forEach(i=>i.disabled=!!busy);
}
function openAdd(){addBg.classList.add('open');addBg.style.display='flex';renderAddJob()}
function closeAdd(){addBg.classList.remove('open');addBg.style.display='none';load()}
document.getElementById('add-open').addEventListener('click',openAdd);
document.getElementById('add-x').addEventListener('click',closeAdd);
document.getElementById('add-start').addEventListener('click',async()=>{
  const get=k=>(addBg.querySelector(`[data-p=${k}]`)||{}).value?.trim()||'';
  const body={name:get('name'),login:get('login'),password:(addBg.querySelector('[data-p=password]')||{}).value||'',server:get('server')};
  const msg=document.getElementById('add-msg');
  if(!body.name||!body.login||!body.password||!body.server){
    msg.className='msg err';msg.textContent='Alle vier Felder ausfüllen.';return}
  if(!/^[A-Za-z0-9]{1,24}$/.test(body.name)){
    msg.className='msg err';msg.textContent='Name: nur Buchstaben/Zahlen, ohne Leer-/Bindezeichen.';return}
  msg.className='msg';msg.textContent='starte…';
  const r=await fetch('/api/provision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  const pw=addBg.querySelector('[data-p=password]'); if(pw)pw.value='';
  msg.className='msg'+(d.ok?'':' err');
  msg.textContent=d.ok?'läuft — Fortschritt unten':('Fehler: '+d.msg);
  if(d.ok)setTimeout(load,1000);
});

// ── Karten-Aktionen (delegiert) ─────────────────────────────────────────────
document.getElementById('app').addEventListener('click',async e=>{
  const cardEl=e.target.closest('.card'); if(!cardEl)return;
  const file=cardEl.getAttribute('data-file');
  const msg=cardEl.querySelector('.msg');
  if(e.target.hasAttribute('data-plan')){openPlan(file);return}
  if(e.target.hasAttribute('data-toggle')){
    if(openSet.has(file))openSet.delete(file); else openSet.add(file);
    cardEl.classList.toggle('open');
    e.target.textContent=cardEl.classList.contains('open')?'Details ▴':'Details ▾';
    return;
  }
  if(e.target.hasAttribute('data-del')){
    e.target.closest('.map').remove();
    cardEl.setAttribute('data-dirty','1');
    return;
  }
  if(e.target.hasAttribute('data-term')){
    msg.className='msg'; msg.textContent='öffne Terminal…';
    const r=await fetch('/api/start-terminal?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    msg.className='msg'+(d.ok?'':' err'); msg.textContent=d.ok?d.msg:('Fehler: '+d.msg);
    return;
  }
  if(!e.target.hasAttribute('data-save'))return;
  const patch={};
  cardEl.querySelectorAll('[data-f]').forEach(el=>patch[el.getAttribute('data-f')]=el.value);
  const map={}; let bad=null, dup=null;
  cardEl.querySelectorAll('[data-maps] .map').forEach(row=>{
    const a=(row.querySelector('[data-mk]')||{}).value?.trim()||'';
    const b=(row.querySelector('[data-mv]')||{}).value?.trim()||'';
    if(!a&&!b)return;
    if(!a||!b){bad=a||b;return}
    if(map[a]!==undefined)dup=a;
    map[a]=b;
  });
  if(bad){msg.className='msg err';msg.textContent=`Mapping-Zeile '${bad}' ist nur halb ausgefüllt`;return}
  if(dup){msg.className='msg err';msg.textContent=`Master-Symbol '${dup}' doppelt im Mapping`;return}
  patch.symbol_map=map;
  msg.className='msg';msg.textContent='speichere…';
  const r=await fetch('/api/save?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  const d=await r.json();
  msg.className='msg'+(d.ok?'':' err');
  msg.textContent=d.ok?(d.msg+' — der Copier übernimmt es in ~2s'+(d.restart?' (Neustart läuft automatisch)':'')):('Fehler: '+d.msg);
  if(d.ok)cardEl.removeAttribute('data-dirty');
  setTimeout(load,2500);
});
load(); setInterval(load,3000);
</script></body></html>"""


# ══ TOPSTEPX-AUGE (27.10.2026, Finn: „In erster Instanz ein Tampermonkey-Script im TopstepX-Tab … sobald der Trade in TopstepX
# geschlossen wird, sieht das Auge des Scripts das und schließt den Hedge direkt — gleiche Prio wie ein Orbit Big Trade"). Das Userscript
# tv-reader/tsx-auge.user.js (Puls-Chrome, topstepx.com) meldet alle 0,25 s seinen Stand (augen_tsx.js stand(): Konto, Positionen,
# Flach-Beweis, Reiter) per POST /api/tsx-stand; der Prophos-Tab dieses PCs fragt GET /api/tsx-stand alle 0,05 s, solange ein Topstep-
# Hedge offen ist (prophos.html hedgeTsxSchnellTick). Eigener Kanal statt reader-server (8790): der kennt nur EINEN Stand (TradingView),
# ein zweiter Tab dort würde den Orbit-Schließer stören, und er kommt erst mit start-alles.bat auf die PCs. Nur im Speicher, je Tab der
# jüngste Stand; nichts wird geschrieben, nichts geklickt.
TSX_STAND_MAX = 60_000          # Bytes je Meldung (stand() bleibt laut augen_tsx.js unter STAND_MAX)
TSX_STAND_TABS = 4              # mehr Tabs merkt sich das Panel nicht (Puls-Chrome hat einen TopstepX-Tab)
TSX_STAND_ALT_S = 30.0          # ältere Tab-Stände fallen weg
_tsx_stand = {}                 # tab → {"ts": Panel-Zeit, "stand": dict}
_tsx_stand_lock = threading.Lock()


def tsx_stand_herkunft_ok(origin):
    """REIN RECHNEND (testbar): darf diese Origin den TopstepX-Stand melden? Tampermonkeys GM_xmlhttpRequest kommt je nach Version ohne
    Origin, mit der Seite (https://topstepx.com) oder mit der Erweiterung (chrome-extension://…). Andere Webseiten nie — sonst könnte
    jede Seite im Browser „flach" melden und den Fusion-Hedge schließen lassen."""
    if not origin:
        return True
    o = urlparse(str(origin))
    host = (o.hostname or "").lower()
    if o.scheme == "chrome-extension":
        return True
    if o.scheme == "https" and (host == "topstepx.com" or host.endswith(".topstepx.com")):
        return True
    return o.scheme in ("http", "https") and host in ("127.0.0.1", "localhost")


# ══ TOPSTEPX-AUGE: LADER (29.10.2026, Finn 10:20: „Ich will, dass sich das Auge automatisch aktualisiert … Ich will nicht jedes Script von
# Hand aktualisieren"). Das Auge ab 0.3.0 ist Lader + eingebauter Kern (wie tv-reader.user.js 0.10.x). Das Panel liefert hier — es ist auf
# jedem PC da und per Code-Sync aktuell — aus dem deployten Repo-Stand (Railway /code/datei, X-Code-Token dieses PCs, beide Dateien vom
# SELBEN Commit): /userscript/tsx-kern.json = {version, sha, kern}, kern = aktuelle augen_tsx.js + das Stück zwischen KERN-START/KERN-ENDE
# (in einer new Function: PROPHOS_AUGEN_TSX ist dort lokal, die nachgeladene Fassung liest also mit der augen_tsx.js IHRES Stands), sha =
# SHA-256 über kern; dazu die ganze .user.js/.meta.js für Tampermonkeys @updateURL/@downloadURL (Puls klickt einmal je PC „Aktualisieren").
# Nur lesen, 60 s gemerkt; Herkunft wie tsx-stand (Tampermonkey, topstepx.com, lokal).
TSX_KERN_MERK = {"s": 0.0, "wert": None, "datei": None}


def tsx_kern_aus(userscript, augen):
    """REIN RECHNEND (testbar): tsx-auge.user.js + augen_tsx.js → {ok, version, sha, kern} oder None (Marker fehlen/doppelt, keine
    Version, augen_tsx.js leer oder ohne PROPHOS_AUGEN_TSX)."""
    import hashlib
    t = userscript.decode("utf-8") if isinstance(userscript, (bytes, bytearray)) else str(userscript or "")
    a = augen.decode("utf-8") if isinstance(augen, (bytes, bytearray)) else str(augen or "")
    k0, k1 = "// ==KERN-START==\n", "// ==KERN-ENDE=="
    if t.count(k0) != 1 or t.count(k1) != 1 or t.index(k0) > t.index(k1) or "var PROPHOS_AUGEN_TSX" not in a:
        return None
    teil = t[t.index(k0) + len(k0):t.index(k1)]
    m = re.search(r"var SCRIPT = '([0-9][0-9.]{2,20})'", teil)
    if not m:
        return None
    kern = a.rstrip() + "\n;\n" + teil
    return {"ok": True, "version": m.group(1), "sha": hashlib.sha256(kern.encode("utf-8")).hexdigest(), "kern": kern}


def tsx_dateien_holen(jetzt=None):
    """(userscript_bytes, augen_bytes) vom deployten Stand (beide mit demselben ?sha=), 60 s gemerkt — (None, None) ohne Netz/Schlüssel."""
    jetzt = time.time() if jetzt is None else jetzt
    if TSX_KERN_MERK["datei"] is not None and jetzt - TSX_KERN_MERK["s"] < 60:
        return TSX_KERN_MERK["datei"]
    sha = None
    try:
        roh = code_holen("/code/stand", timeout=8)
        sha = (json.loads(roh.decode("utf-8")) or {}).get("sha") if roh else None
    except Exception:
        sha = None
    if not (sha and re.fullmatch(r"[0-9a-f]{40}", str(sha))):
        return None, None
    us = code_holen(f"/code/datei/tv-reader/tsx-auge.user.js?sha={sha}")
    au = code_holen(f"/code/datei/mt5-copier/augen_tsx.js?sha={sha}")
    if us and au:
        TSX_KERN_MERK.update(s=jetzt, datei=(us, au), wert=tsx_kern_aus(us, au))
        return us, au
    return None, None


# AUGE JE GESEHEN (30.10.2026, PC von Mike ohne TopstepX-Auge: 14× Reparaturlauf ohne Chance): wann kam seit dem Panel-Start überhaupt je
# ein Stand an? Der PC-Tab trennt damit „Auge nie da" (nicht installiert → keine Reparatur) von „war da, jetzt blind". Stände selbst fallen
# nach TSX_STAND_ALT_S weg, dieser Zeitpunkt nicht.
_tsx_jemals = {"ts": None}
_TSX_PANEL_START = time.time()


def tsx_stand_merken(daten, jetzt=None):
    """REIN RECHNEND bis auf den Speicher: Meldung des Userscripts ablegen. → (ok, grund)."""
    if not isinstance(daten, dict) or not isinstance(daten.get("stand"), dict):
        return False, "stand fehlt"
    tab = re.sub(r"[^A-Za-z0-9_.-]", "", str(daten.get("tab") or ""))[:48]
    if not tab:
        return False, "tab fehlt"
    jetzt = time.time() if jetzt is None else jetzt
    with _tsx_stand_lock:
        _tsx_jemals["ts"] = jetzt
        _tsx_stand[tab] = {"ts": jetzt, "stand": daten["stand"], "script": str(daten.get("script") or "")[:24],
                           "lader": tsx_lader_kurz(daten.get("lader")) if isinstance(daten.get("lader"), dict) else None}   # 0.3.0
        for t in [t for t, v in _tsx_stand.items() if jetzt - v["ts"] > TSX_STAND_ALT_S]:
            _tsx_stand.pop(t, None)
        while len(_tsx_stand) > TSX_STAND_TABS:
            _tsx_stand.pop(min(_tsx_stand, key=lambda t: _tsx_stand[t]["ts"]), None)
    return True, ""


def tsx_lader_kurz(l):
    """REIN RECHNEND: Lader-Status des Auges auf sechs kurze Felder stutzen (wie lader_kurz im reader-server)."""
    out = {}
    for k in ("v", "eval", "laeuft", "quelle", "bereit", "fehler"):
        x = l.get(k) if isinstance(l, dict) else None
        out[k] = x if (x is None or isinstance(x, (bool, int, float))) else str(x)[:80]
    return out


def tsx_stand_ausgabe(jetzt=None):
    """Jüngster Stand aller Tabs mit Alter in Sekunden (Panel-Uhr) — {ok:false}, solange keiner meldet. Immer dabei (30.10.2026):
    jemals_s = Sekunden seit dem letzten Stand überhaupt seit dem Panel-Start (None = nie), panel_s = Laufzeit des Panels."""
    jetzt = time.time() if jetzt is None else jetzt
    with _tsx_stand_lock:
        je = {"jemals_s": None if _tsx_jemals["ts"] is None else round(jetzt - _tsx_jemals["ts"], 1), "panel_s": round(jetzt - _TSX_PANEL_START)}
        if not _tsx_stand:
            return dict({"ok": False, "grund": "kein TopstepX-Auge meldet"}, **je)
        tab = max(_tsx_stand, key=lambda t: _tsx_stand[t]["ts"])
        v = _tsx_stand[tab]
        return dict({"ok": True, "tab": tab, "tabs": len(_tsx_stand), "alter_s": round(jetzt - v["ts"], 3), "script": v["script"],
                     "stand": v["stand"], "lader": v.get("lader")}, **je)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _local_ok(self):
        """Host/Origin auf 127.0.0.1|localhost festnageln — schuetzt gegen
        DNS-Rebinding und Requests fremder Seiten aus dem Browser heraus."""
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            return False
        origin = self.headers.get("Origin")
        if origin:
            o = urlparse(origin)
            if (o.hostname or "").lower() not in ("127.0.0.1", "localhost"):
                return False
        return True

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/userscript/tsx-kern.json", "/userscript/tsx-auge.user.js", "/userscript/tsx-auge.meta.js"):
            # TopstepX-Auge-Lader (29.10.2026, s. tsx_kern_aus): Herkunft wie tsx-stand (Tampermonkey/topstepx.com/lokal), Host lokal
            host = (self.headers.get("Host") or "").split(":")[0].lower()
            if host not in ("127.0.0.1", "localhost") or not tsx_stand_herkunft_ok(self.headers.get("Origin")):
                return self._send(403, json.dumps({"ok": False, "msg": "nur lokal"}))
            us, au = tsx_dateien_holen()
            if path.endswith(".json"):
                w = TSX_KERN_MERK["wert"] if us else None
                if not w:
                    return self._send(502, json.dumps({"ok": False, "msg": "Auge nicht ladbar (kein Schlüssel / Railway / Marker)"}))
                return self._send(200, json.dumps(w, ensure_ascii=False))
            if not us:
                return self._send(502, json.dumps({"ok": False, "msg": "Auge nicht ladbar (kein Schlüssel / Railway nicht erreichbar)"}))
            return self._send(200, us, "text/javascript; charset=utf-8")
        if not self._local_ok():
            return self._send(403, json.dumps({"error": "nur lokal"}))
        if path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if polar_panel and path == "/api/polar-stand":   # POLAR (13.10.2026): Zustand des Polar-Prozesses dieses PCs
            code, antwort = polar_panel.behandle_get(path, parse_qs(urlparse(self.path).query))
            return self._send(code, json.dumps(antwort, ensure_ascii=False, default=str))
        if path == "/api/instances":
            haupt = tab_gesehen(self.headers.get("User-Agent"), parse_qs(urlparse(self.path).query))   # Tab öffnen, wenn gar keiner läuft (16.10.2026)
            return self._send(200, json.dumps(dict(snapshot(), haupt_tab=haupt, **({"vorflug_ping": TAB_VORFLUG["marke"]} if TAB_VORFLUG.get("marke") else {})),
                                              ensure_ascii=False))
        if path == "/api/deals":
            # ENDLESUNG UNKLARER ECHO-PLÄNE (N2, Finn 04.11.2026 ~04:15 Dubai: „der P&L wird nie angezeigt"): Deal-Historie + Balance des Master-Logins
            # über order_bot.py „deals" — nur lesen, nie ein Klick. Nur wenn auf dieser Instanz gerade keine Order läuft (MASTER_ORDER_LOCKS): ein
            # zweiter MetaTrader5-Anschluss mitten in einem Order-Lauf bliebe sonst nicht folgenlos. Besetzt → 409, der Tab fragt später wieder.
            q = parse_qs(urlparse(self.path).query)
            fname = (q.get("file") or [""])[0]
            inst = next((i for i in instances() if i["config_file"] == fname), None)
            if not inst:
                return self._send(404, json.dumps({"ok": False, "lesbar": False, "grund": "Instanz unbekannt"}, ensure_ascii=False))
            # Gegenprüfung N2: nur ein Terminal lesen, das schon läuft — MetaTrader5.initialize startet ein geschlossenes (Standby, Login-Dialog) und
            # direkt nach dem Start sind Positionen/Historie evtl. noch leer → „nicht gelaufen" wäre geraten
            _cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
            _pfad = str(_cfg.get("master_terminal_path") or "").strip()
            if not _pfad or not provision.terminal_pids(os.path.dirname(os.path.abspath(_pfad))):
                return self._send(200, json.dumps({"ok": False, "lesbar": False, "grund": "Master-Terminal läuft nicht — nicht gelesen (wird nicht gestartet)"}, ensure_ascii=False))
            with MASTER_ORDER_GUARD:
                lock = MASTER_ORDER_LOCKS.setdefault(inst["config_file"], threading.Lock())
            if not lock.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "lesbar": False, "grund": "auf dieser Instanz läuft gerade eine Order"}, ensure_ascii=False))
            DEALS_LESEN.add(inst["config_file"])
            try:
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                auftrag = {"cfg": os.path.join(HERE, inst["config_file"]), "von": (q.get("von") or [""])[0], "bis": (q.get("bis") or [""])[0],
                           "symbol": (q.get("symbol") or [""])[0], "richtung": (q.get("richtung") or [""])[0], "lots": (q.get("lots") or [""])[0],
                           "ohne": (q.get("ohne") or [""])[0]}
                try:
                    p = subprocess.run([*bot_argv(bot), "deals", json.dumps(auftrag)], capture_output=True, text=True, errors="replace",
                                       timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    zeilen = (p.stdout or "").strip().splitlines()
                    res = json.loads(zeilen[-1]) if zeilen else {"ok": False, "lesbar": False, "grund": "keine Antwort vom Bot"}
                except Exception as e:
                    res = {"ok": False, "lesbar": False, "grund": f"Bot-Lauf {type(e).__name__}"}
            finally:
                DEALS_LESEN.discard(inst["config_file"])
                lock.release()
            return self._send(200, json.dumps(res, ensure_ascii=False))
        if path == "/api/vorflug":
            # F-A KONTO-VORFLUG (11.11.2026, Master nach FS2): Zustand des Master-Logins 10–15 min vor dem Start — über order_bot.py „vorflug“, nur lesen
            # (kein Fenster, kein Login-Dialog, kein Klick). Wie /api/deals: nur ein schon laufendes Terminal, nur ohne laufende Order (MASTER_ORDER_LOCKS,
            # besetzt → 409, der Tab fragt später). Eine Order, die während der Lesung kommt, wartet bis VORFLUG_WARTE_S (s. master-order).
            q = parse_qs(urlparse(self.path).query)
            fname = (q.get("file") or [""])[0]
            inst = next((i for i in instances() if i["config_file"] == fname), None)
            if not inst:
                return self._send(404, json.dumps({"ok": False, "lesbar": False, "grund": "Instanz unbekannt"}, ensure_ascii=False))
            _cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
            _pfad = str(_cfg.get("master_terminal_path") or "").strip()
            if not _pfad or not provision.terminal_pids(os.path.dirname(os.path.abspath(_pfad))):
                return self._send(200, json.dumps({"ok": False, "lesbar": False, "grund": "Master-Terminal läuft nicht — nicht gelesen (wird nicht gestartet)"}, ensure_ascii=False))
            if _instanz_heilt(inst):
                return self._send(409, json.dumps({"ok": False, "lesbar": False, "grund": "Terminal wird gerade geheilt — später"}, ensure_ascii=False))
            # Hinweis S1: Lock nehmen und als Lesung markieren in EINEM Schritt unter MASTER_ORDER_GUARD (kein Fenster „Lock gehalten, nicht markiert“);
            # eine angemeldete Order/ein Close (ORDER_ANGEMELDET) hat Vorrang
            with MASTER_ORDER_GUARD:
                lock = MASTER_ORDER_LOCKS.setdefault(inst["config_file"], threading.Lock())
                frei = vorflug_darf(inst["config_file"], ORDER_ANGEMELDET, time.time()) and lock.acquire(blocking=False)
                if frei:
                    VORFLUG_LESEN.add(inst["config_file"])
            if not frei:
                return self._send(409, json.dumps({"ok": False, "lesbar": False, "grund": "auf dieser Instanz läuft gerade eine Order oder Lesung"}, ensure_ascii=False))
            try:
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                _ri = (q.get("richtung") or [""])[0].strip().lower()
                auftrag = {"cfg": os.path.join(HERE, inst["config_file"]), "symbol": (q.get("symbol") or [""])[0][:32],
                           "richtung": _ri if _ri in ("buy", "sell") else ""}   # Prüfer S3: unbekannt = ohne Seitenprüfung
                try:
                    p = subprocess.run([*bot_argv(bot), "vorflug", json.dumps(auftrag)], capture_output=True, text=True, errors="replace",
                                       timeout=VORFLUG_DECKEL_S, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    zeilen = (p.stdout or "").strip().splitlines()
                    res = json.loads(zeilen[-1]) if zeilen else {"ok": False, "lesbar": False, "grund": "keine Antwort vom Bot"}
                except Exception as e:
                    res = {"ok": False, "lesbar": False, "grund": f"Bot-Lauf {type(e).__name__}"}
            finally:
                with MASTER_ORDER_GUARD:   # erst den Lock frei, dann die Markierung weg: wer die Markierung nicht mehr sieht, bekommt den Lock
                    lock.release()
                    VORFLUG_LESEN.discard(inst["config_file"])
            if isinstance(res, dict) and res.get("rot"):
                print(f"[vorflug] {fname}: {res.get('art')} — {str(res.get('grund') or '')[:160]}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))
        if path == "/api/haupt-tab":
            # Tab im „nur ansehen"-Modus (30.10.2026, HAUPT-TAB): darf er wieder Haupt-Tab werden? Nur lesen, zählt nie als Herzschlag
            q = parse_qs(urlparse(self.path).query)
            tid = str((q.get("tid") or [""])[0]).strip()[:16]
            login = str((q.get("login") or [""])[0]) == "1"
            if tid:   # merken (für die Doppel-Tab-Meldung), aber nie als Haupt-Herzschlag ("at" bleibt)
                _TABS.setdefault(tid, {"at": 0.0, "puls": None}).update(login=login, neben_at=time.time())
            frei = neben_tab_frei(_TABS, tid, login, time.time(), _TAB_HAUPT["tid"])
            return self._send(200, json.dumps({"ok": True, "frei": frei}))
        if path == "/api/tab-zustand":
            # FS1 (10.11.2026): Tab-Zustand für die Puls-Spur; anlass=tab_nicht_erreichbar startet die Stufen-Heilung sofort (s. TAB_HEIL_SOFORT). Nur lokal.
            q = parse_qs(urlparse(self.path).query)
            if (q.get("anlass") or [""])[0] == "tab_nicht_erreichbar":
                TAB_HEIL_SOFORT.update(at=time.time(), plan=re.sub(r"[^0-9a-f-]", "", (q.get("plan_id") or [""])[0])[:36], erledigt=False, geheilt=False, grund="", bis=None)
                print(f"[tab-heilen] Puls: Tab antwortete beim Start nicht — Stufen-Heilung sofort", flush=True)
            return self._send(200, json.dumps(tab_zustand_ausgabe(time.time(), _TAB_OEFFNEN, TAB_HEIL, TAB_HEIL_SOFORT,
                                                                  {"ergebnis": TAB_NL.get("ergebnis"), "ergebnis_at": TAB_NL.get("ergebnis_at")},
                                                                  _TAB_OEFFNEN.get("klick_at")), ensure_ascii=False, default=str))
        if path == "/api/tsx-stand":
            # TopstepX-Auge (27.10.2026, s. tsx_stand_merken): jüngster Stand des Userscripts im Puls-Chrome — nur lesen
            return self._send(200, json.dumps(tsx_stand_ausgabe(), ensure_ascii=False, default=str))
        if path == "/api/puls-klick":
            # Klick-/Fill-Meldung von Puls LOKAL (01.10.2026, Finn: „Fusion sofort beim Knopfdruck, an Supabase vorbei"): order_bot.py
            # legt jede Order-Meldung zusätzlich als puls_ergebnisse/letzt_order.json ab (überschrieben). Der Prophos-Tab dieses PCs fragt
            # während eines Laufs alle 0,1 s hier statt alle 0,6 s in Supabase (puls_ergebnisse via Railway) — nur lesen, nie schreiben.
            q = parse_qs(urlparse(self.path).query)
            pid = (q.get("plan_id") or [""])[0].strip()
            _TAB_OEFFNEN["klick_at"] = time.time()      # FS1 (10.11.2026): letzte Puls-Abfrage des Tabs (Tab-Zustand in der Spur)
            d = read_json(os.path.join(HERE, "puls_ergebnisse", "letzt_order.json"), None)
            # TAB-WÄCHTER (30.10.2026, order_bot tab_wache_warten): Marke des Bots mitgeben, Antwort des Tabs für den Bot ablegen; tab_wache:1 = dieses Panel kann es
            wache, pong = tab_wache_antwort(pid, (q.get("pong") or [""])[0].strip(), read_json(os.path.join(HERE, "puls_ergebnisse", "tab_ping.json"), None), time.time())
            if pong:
                try:
                    ziel = os.path.join(HERE, "puls_ergebnisse", "tab_pong.json")
                    with open(ziel + ".tmp", "w", encoding="utf-8") as f:
                        json.dump(pong, f)
                    os.replace(ziel + ".tmp", ziel)
                except OSError as e:
                    print(f"[panel] tab_pong nicht geschrieben: {e}", flush=True)   # der Bot sieht dann keine Antwort und sendet nicht
            if not pid or not isinstance(d, dict) or str(d.get("plan_id") or "") != pid:
                return self._send(200, json.dumps(dict({"ok": False, "plan_id": pid or None}, **wache)))
            return self._send(200, json.dumps(dict({"ok": True, "paket": d}, **wache), ensure_ascii=False, default=str))
        if path == "/api/pc-id":
            # PC-Kennung für alle Browser-Profile dieses PCs (25.09.2026) — null, solange keine eingetragen ist
            import socket
            return self._send(200, json.dumps({"ok": True, "pc_id": pc_id_lesen(), "host": socket.gethostname()}, ensure_ascii=False))
        if path == "/api/windows-abfrage":
            # Steht eine Windows-Sicherheitsabfrage offen? (23.10.2026, Master: ein Start, der daran scheitert, ist kein Fehlversuch —
            # sfTick im Prophos-Tab plant neu ein, sobald consent.exe weg ist). Nur lesen; ohne Windows/lesbare Liste consent None.
            return self._send(200, json.dumps({"ok": True, "consent": consent_offen()}))
        if path == "/api/beschaeftigt":
            # UPDATE-SCHUTZ (29.10.2026): hält ein Lauf das Panel? Fragt das lokale app.py vor seinem Selbst-Neustart. Nur lesen.
            g = panel_beschaeftigt_gruende()
            return self._send(200, json.dumps({"ok": True, "frei": not g, "gruende": g, "lauf": panel_lauf_gruende(g)}, ensure_ascii=False))
        if path == "/api/code-token":
            # Liegt der PC-Schlüssel für die Code-Quelle schon da? (07.10.2026) — nur ja/nein, nie der Schlüssel selbst
            return self._send(200, json.dumps({"ok": True, "da": bool(code_token())}))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        self._t_ein = time.time()    # HEDGE-ZU-7S (02.11.2026): Eingang im Panel, nur Messung (hedge_solo_zeiten)
        # UPDATE-SCHUTZ (29.10.2026): jeden POST außer tsx-stand zählen; kurz vor dem Neustart (zu) sofort 503 „nichts gesendet"
        if urlparse(self.path).path == "/api/tsx-stand":
            return self._do_post_innen()
        with _PANEL_POST_LOCK:
            if _PANEL_POST["zu"]:
                return self._send(503, json.dumps({"ok": False, "code": "backend_neustart", "retry_ok": True, "_nichtGesendet": True,
                    "_httpFail": True, "copier_offline": True,
                    "msg": "Panel startet gerade neu (Update) — nichts gesendet, gleich erneut."}, ensure_ascii=False))
            _PANEL_POST["n"] += 1
        try:
            return self._do_post_innen()
        finally:
            with _PANEL_POST_LOCK:
                _PANEL_POST["n"] -= 1

    def _do_post_innen(self):
        u = urlparse(self.path)
        if u.path == "/api/tsx-stand":
            # TopstepX-Auge (27.10.2026): eigene Herkunfts-Regel (tsx_stand_herkunft_ok — Tampermonkey kommt nicht als localhost), Host
            # bleibt 127.0.0.1/localhost; vor der Polar-Sperre, denn das Melden ist kein Puls-Weg und muss auch während Polar laufen
            host = (self.headers.get("Host") or "").split(":")[0].lower()
            if host not in ("127.0.0.1", "localhost") or not tsx_stand_herkunft_ok(self.headers.get("Origin")):
                return self._send(403, json.dumps({"ok": False, "msg": "nur lokal"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > TSX_STAND_MAX:
                    return self._send(413, json.dumps({"ok": False, "msg": "zu groß"}))
                ok, grund = tsx_stand_merken(json.loads(self.rfile.read(n) or b"{}") if n else {})
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {type(e).__name__}"}))
            return self._send(200 if ok else 400, json.dumps({"ok": ok, "msg": grund}))
        if not self._local_ok():
            return self._send(403, json.dumps({"ok": False, "msg": "nur lokal"}))
        ctype = (self.headers.get("Content-Type") or "")
        if "application/json" not in ctype:
            return self._send(400, json.dumps({"ok": False, "msg": "Content-Type muss application/json sein"}))
        # POLAR (13.10.2026, Finn: „Priorität 1 — kein anderer Puls-Bot darf diesen PC bedienen"): läuft Polar, bekommt jeder andere
        # Puls-/Maus-Weg 409 puls_beschaeftigt (der Tab wartet wie bei einem laufenden Rundgang). Die Polar-Routen gehen ans Modul.
        # POLAR-VORRANG (20.10.2026, Finn: „wenn Polar läuft, darf gar kein einziger Trade mehr gestartet werden"): alle POST-Routen außer
        # polar_panel.FREI_PFADE → 409 polar_aktiv mit lauf_id (sperre_antwort); alter Modul-Stand ohne sperre_antwort → wie bisher.
        if polar_panel and hasattr(polar_panel, "sperre_antwort"):
            _ps = polar_panel.sperre_antwort(u.path)
            if _ps:
                return self._send(_ps[0], json.dumps(_ps[1], ensure_ascii=False, default=str))
        elif polar_panel and polar_panel.gesperrt(u.path):
            return self._send(409, json.dumps({"ok": False, "retry_ok": True, "code": "puls_beschaeftigt", "gesendet": False,
                                               "msg": "Polar läuft auf diesem PC — kein anderer Puls-Weg, bis der Polar-Trade zu ist."}, ensure_ascii=False))
        if polar_panel and u.path in ("/api/polar-start", "/api/polar-abbruch", "/api/polar-test-x"):   # polar-test-x: Maus-Test × (20.10.2026)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            # POLAR-MASTER AM PANEL (30.10.2026, Master nach Crosscheck S5: Railway prüft beim /polar/start, das Panel bisher nicht): vor dem
            # Start des Master-Prozesses derselbe Riegel wie bei tv-konto — Plan-UUID + buy/sell Pflicht, richtung_frei fail-closed. Nur die
            # Master-Seite: das Slave-Signal trägt zwar dieselbe plan_id, die gehört aber der Master-ID (falsche ID × Firma) — der Slave braucht
            # den Konto-Modus an /richtung/frei (S4). polar_bot und sein Feuer-Timing bleiben unberührt (Prüfung VOR dem Popen).
            if u.path == "/api/polar-start" and str(body.get("seite") or "") == "master":
                _pid = str(body.get("plan_id") or "").strip()
                _ri = str(body.get("richtung") or "").strip().lower()
                _fehlt = riegel_pflicht_fehlt(_pid, _ri)
                # RD1b (10.11.2026): ohne Netz-Pausen — der Slave feuert unabhängig, der Master darf nie bis ~25 s später starten
                _frei, _msg, _code = (False, _fehlt, "riegel_unerreichbar") if _fehlt else richtung_frei(_pid, _ri, netz_wiederholen=False)
                if not _frei:
                    print(f"[panel] polar-start master RIEGEL {_code} {_ri}: {_msg[:160]}", flush=True)
                    return self._send(200, json.dumps({"ok": False, "code": _code, "retry_ok": True, "gesendet": False, "msg": _msg},
                                                      ensure_ascii=False))
            code, antwort = polar_panel.behandle_post(u.path, body, beschaeftigt=_bot_lauf_aktiv())
            return self._send(code, json.dumps(antwort, ensure_ascii=False, default=str))
        if u.path == "/api/provision":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            name = str(body.get("name") or "").strip()
            login = str(body.get("login") or "").strip()
            password = str(body.get("password") or "")
            server = str(body.get("server") or "").strip()
            # Besitzer-Stempel (Paket E, 15.08.2026): optionale Prophos-User-ID.
            # Nur UUID-artige Zeichen, sonst verwerfen — landet als prophos_owner
            # in der Config (Identitaetsfeld, nicht in WRITABLE).
            owner = str(body.get("owner") or "").strip()[:64]
            if owner and not re.fullmatch(r"[A-Za-z0-9-]{1,64}", owner):
                owner = None
            # Anzeigename mit Leerzeichen (Finn, 15.08.2026): intern bleibt der
            # Slug (Dateinamen/Ordner/Regexe), angezeigt wird display_name.
            display = str(body.get("display") or "").strip()[:40]
            if display and not re.fullmatch(r"[A-Za-z0-9 ._\-]{1,40}", display):
                display = None
            if not (name and login and password and server):
                return self._send(400, json.dumps({"ok": False, "msg": "Name, Login, Passwort und Server sind Pflicht."}))
            # Selbst-Spiegel-Sperre (15.08.2026, Finns 'Fusion SLAVE TEST'-Fall):
            # das Hedge-Konto als Master einzurichten hiesse, es auf sich selbst
            # zu spiegeln — jede Position wuerde ihren eigenen Hedge ausloesen
            # (Teufelskreis). Wird hier hart verweigert.
            _hedge_login = str(base_config().get("hedge_expected_login") or "")
            if _hedge_login and str(login) == _hedge_login:
                return self._send(400, json.dumps({"ok": False, "msg":
                    f"Login {login} IST das Hedge-Konto dieses PCs — es wird nicht "
                    f"als Master eingerichtet (wuerde auf sich selbst spiegeln)."},
                    ensure_ascii=False))
            if not base_config():
                # Von-Null-Fall (15.08.2026): ohne Basis weiss die Einrichtung weder
                # Hedge-Konto noch Vorlage-Terminal — klare Ansage statt Folgefehler.
                return self._send(400, json.dumps({"ok": False, "msg":
                    "Keine Vorlage auf diesem PC: config.vorlage.json fehlt (traegt "
                    "Hedge-Konto + Vorlage-Terminal). Einmalig anlegen/herunterladen, "
                    "dann klappt jedes Hinzufuegen."}, ensure_ascii=False))
            probs = provision.plan_checks(HERE, name, login, server,
                                          base_config().get("master_terminal_path"))
            if probs:
                return self._send(400, json.dumps({"ok": False, "msg": " · ".join(probs)}, ensure_ascii=False))
            ok, msg = prov_start(name, login, password, server, owner=owner, display=display)
            print(f"[panel] provision '{name}': {msg}", flush=True)  # bewusst ohne Zugangsdaten
            return self._send(200 if ok else 409, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))

        if u.path == "/api/mt5-update-einrichten":
            ok, msg = mt5_update_klick()
            return self._send(200, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))
        if u.path == "/api/plan-delete":
            # braucht keinen file-Parameter — Plan-ID reicht
            try:
                pid = int((parse_qs(u.query).get("id") or ["0"])[0])
            except ValueError:
                pid = 0
            ok = delete_plan(pid)
            return self._send(200, json.dumps({"ok": ok, "msg": "geloescht" if ok else "unbekannt"}))

        if u.path == "/api/set-hedge":
            # Hedge-Konto dieses PCs zentral umstellen (25.08.2026, Finns Wunsch
            # nach dem 400002/400004-Hänger: die ID soll in Prophos eingebbar
            # sein statt per Hand in jeder config*.json). Schreibt
            # hedge_expected_login in ALLE Instanz-Configs — check_fleet
            # verlangt ohnehin, dass sie identisch sind. Der Copier merkt die
            # Aenderung binnen 2 s (nicht in HOT) und startet sich selbst neu,
            # damit alle Startpruefungen gegen das neue Konto laufen.
            # Localhost-only wie alles hier; die Master-Kontonummern bleiben tabu.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            login_raw = str(body.get("login") or "").strip()
            if not re.fullmatch(r"\d{1,12}", login_raw):
                return self._send(400, json.dumps({"ok": False, "msg":
                    "Hedge-Kontonummer muss eine Zahl sein (z.B. 12345678)."}, ensure_ascii=False))
            new_login = int(login_raw)
            insts = instances()
            if not insts:
                return self._send(400, json.dumps({"ok": False, "msg":
                    "Keine Instanz-Configs auf diesem PC."}, ensure_ascii=False))
            # Selbst-Spiegel-Sperre, andersherum (Muster /api/provision): das neue
            # Hedge-Konto darf kein Master dieses PCs sein.
            for inst in insts:
                cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
                if int(cfg.get("master_expected_login") or 0) == new_login:
                    return self._send(400, json.dumps({"ok": False, "msg":
                        f"{new_login} ist der Master von '{inst['name']}' — ein Master kann "
                        f"nicht das Hedge-Konto sein (wuerde auf sich selbst spiegeln)."},
                        ensure_ascii=False))
            # Riegel: bewiesene offene Hedges auf dem ALTEN Konto → erst schliessen.
            # Nur FRISCHER Status zaehlt als Beweis (Doktrin 'unbekannt ≠ leer' gilt
            # fuers Loeschen — hier blockt nur ein positiver Beweis, sonst kaeme man
            # aus einem crashenden Copier nie heraus).
            for inst in insts:
                st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
                try:
                    age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
                except (TypeError, ValueError):
                    age = None
                if st.get("running") and age is not None and age <= 15 \
                        and any((st.get("hedges") or {}).values()):
                    return self._send(409, json.dumps({"ok": False, "msg":
                        f"'{inst['name']}' hat gerade offene Hedges — erst schliessen, "
                        f"dann das Hedge-Konto wechseln."}, ensure_ascii=False))
            changed = []
            # Die VORLAGE mit umstellen (25.08.2026, Finns Live-Fund: die
            # Provisionierung von '100kThe5ers00000000' erbte das alte
            # Hedge-Konto aus config.vorlage.json — die Flotten-Pruefung brach
            # in der Schleife ab, weil die neue Config vom Rest abwich. Der
            # Chip ist die eine Stelle, die das Hedge-Konto dieses PCs pflegt —
            # also gehoert die Vorlage als Erb-Quelle kuenftiger Accounts dazu.)
            vor_path = os.path.join(HERE, "config.vorlage.json")
            vor = read_json(vor_path)
            if vor is not None and int(vor.get("hedge_expected_login") or 0) != new_login:
                vor["hedge_expected_login"] = new_login
                tmp = vor_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(vor, f, ensure_ascii=False, indent=2)
                os.replace(tmp, vor_path)
                changed.append("config.vorlage.json")
            for inst in insts:
                path = os.path.join(HERE, inst["config_file"])
                cfg = read_json(path)
                if cfg is None:
                    return self._send(500, json.dumps({"ok": False, "msg":
                        f"{inst['config_file']} nicht lesbar — nichts geaendert."}, ensure_ascii=False))
                if int(cfg.get("hedge_expected_login") or 0) == new_login:
                    continue
                cfg["hedge_expected_login"] = new_login
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
                os.replace(tmp, path)
                changed.append(inst["config_file"])
            print(f"[panel] set-hedge: hedge_expected_login -> {new_login} "
                  f"({', '.join(changed) or 'keine Aenderung'})", flush=True)
            return self._send(200, json.dumps({"ok": True, "changed": changed, "msg":
                (f"Hedge-Konto auf {new_login} gestellt ({len(changed)} Config(s)) — der Copier "
                 f"startet sich in ~10 s neu und prueft gegen das neue Konto. Wichtig: das "
                 f"Hedge-Terminal muss in genau diesem Konto eingeloggt sein.")
                if changed else f"Alle Configs standen schon auf {new_login}."}, ensure_ascii=False))

        if u.path == "/api/pause":
            # Echo-Not-Aus (28.08.2026, Finns Wunsch nach dem rumklickenden Bot):
            # ein Klick in Prophos legt/entfernt echo_pause.flag. Existiert sie,
            # stoppen Copier UND Order-Bot NUR NEUE Aktionen (keine neuen Hedges,
            # keine SL/TP-Klicks); Closes und die Absicherung laufender Hedges
            # laufen weiter. Kein Bestaetigen — bewusst ein einziger Klick.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            flag = os.path.join(HERE, "echo_pause.flag")
            an = bool(body.get("on"))
            try:
                if an:
                    with open(flag, "w", encoding="utf-8") as f:
                        f.write(datetime.now().isoformat(timespec="seconds"))
                else:
                    if os.path.exists(flag):
                        os.remove(flag)
            except OSError as e:
                return self._send(500, json.dumps({"ok": False, "msg": f"Flag-Datei: {e}"}))
            print(f"[panel] Echo {'PAUSIERT' if an else 'fortgesetzt'} "
                  f"(echo_pause.flag {'gelegt' if an else 'entfernt'})", flush=True)
            return self._send(200, json.dumps({"ok": True, "paused": an, "msg":
                ("Echo pausiert — keine neuen Hedges/Orders/SL-TP-Klicks. Laufende Hedges "
                 "bleiben offen, Closes laufen weiter.") if an
                else "Echo fortgesetzt — Copier und Bot arbeiten wieder normal."},
                ensure_ascii=False))

        if u.path == "/api/mouse-test":
            # Isolierter Maus-/Tastatur-Test (15.08.2026, Finns Wunsch): klaert
            # getrennt von MT5, ob der Bot auf diesem PC den Cursor bewegen und
            # tippen kann. Braucht keine Instanz.
            bot = os.path.join(HERE, "order_bot.py")
            if not os.path.exists(bot):
                ensure_bot_source()
            try:
                p = subprocess.run([*bot_argv(bot), "mousetest"],
                                   capture_output=True, text=True, errors="replace", timeout=60)
                line = (p.stdout or "").strip().splitlines()
                res = json.loads(line[-1]) if line else {
                    "ok": False, "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "msg": "Maus-Test Timeout (60s)."}
            except (OSError, ValueError) as e:
                res = {"ok": False, "msg": f"Maus-Test-Start fehlgeschlagen: {e}"}
            print(f"[panel] Maus-Test → {res.get('msg')}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/tv-fokus":
            # Orbit-Puls Schritt 1 (28.08.2026, Finns Etappe 3): der Bot holt
            # NUR den TradingView-Tab nach vorn — kein Klick in die Seite,
            # keine Order. Bewusst OHNE Instanz-Bezug (wie mouse-test): fuer
            # den Fokuswechsel braucht es keine Config, der Schritt laeuft so
            # auch auf PCs, deren tvplus-Config noch fehlt. Ein alter Bot ohne
            # tvfokus-Modus antwortet harmlos mit seiner Aufruf-Hilfe (ok:false).
            bot = os.path.join(HERE, "order_bot.py")
            if not os.path.exists(bot):
                ensure_bot_source()
            try:
                p = subprocess.run([*bot_argv(bot), "tvfokus"],
                                   capture_output=True, text=True, errors="replace", timeout=60)
                line = (p.stdout or "").strip().splitlines()
                res = json.loads(line[-1]) if line else {
                    "ok": False, "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "msg": "TV-Fokus Timeout (60s)."}
            except (OSError, ValueError) as e:
                res = {"ok": False, "msg": f"TV-Fokus-Start fehlgeschlagen: {e}"}
            print(f"[panel] TV-Fokus -> {res.get('ok')} ({res.get('msg')})", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/tv-start":
            # Futures-Puls Neuaufbau Schritt 1 (21.09.2026, Finn: "als Erstes
            # soll gecheckt werden, ob TradingView offen ist. Wenn nicht, soll
            # TradingView gestartet werden"). Instanzlos wie /api/tv-fokus —
            # TradingView ist eine Pro-PC-Sache. URL, Browser-Pfad und Chrome-
            # Profil kommen AUSSCHLIESSLICH aus der Config (Muster
            # start-hedge-terminal: nichts davon ist ueber die API setzbar —
            # dieser Aufruf startet ein Programm). Alle drei sind optional,
            # ohne sie gilt: Chrome am Standard-Ort, tradingview.com/chart/.
            # Bewusst KEIN Echo-Pause-Riegel: hier wird keine Order angefasst.
            bc = base_config()
            tvcfg = {k: str(bc.get(k) or "").strip()
                     for k in ("tv_url", "tv_browser_path", "tv_chrome_profil")}
            bot = os.path.join(HERE, "order_bot.py")
            if not os.path.exists(bot):
                ensure_bot_source()
            try:
                # 24s: der Proxy in app.py gibt dieser Route 25 s. Der Bot
                # wartet hoechstens 12 s auf den Beweis (plus Fenster-Scans) und meldet sonst
                # ehrlich "laedt noch" — der Start selbst ist dann schon passiert.
                p = subprocess.run([*bot_argv(bot), "tvstart", json.dumps(tvcfg)],
                                   capture_output=True, text=True, errors="replace", timeout=24)
                line = (p.stdout or "").strip().splitlines()
                res = json.loads(line[-1]) if line else {
                    "ok": False, "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "msg": "TV-Start Timeout (24s) — nachsehen, ob TradingView aufgegangen ist."}
            except (OSError, ValueError) as e:
                res = {"ok": False, "msg": f"TV-Start fehlgeschlagen: {e}"}
            print(f"[panel] TV-Start -> {res.get('ok')} ({res.get('msg')}) {res.get('trail') or ''}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/tv-konto":
            # Futures-Puls Neuaufbau Schritt 2a (21.09.2026): TradingView
            # sicherstellen und pruefen, ob das Tradovate-Konto des Plans aktiv
            # ist. Der Aufruf bringt NUR Username + External ID mit (nie ein
            # Passwort — das liegt in Chromes Passwort-Manager); URL/Browser/
            # Profil kommen wie bei tv-start ausschliesslich aus der Config.
            # Unter dem TV-Lock: es gibt einen Browser und eine Maus, und ein
            # paralleler tv-order-Lauf duerfte hier nicht dazwischenfunken.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            bc = base_config()
            cmd = {k: str(bc.get(k) or "").strip()
                   for k in ("tv_url", "tv_browser_path", "tv_chrome_profil")}
            cmd["ext_id"] = str(body.get("ext_id") or "").strip()
            cmd["tv_username"] = str(body.get("tv_username") or "").strip()
            cmd["firma"] = str(body.get("firma") or "").strip()[:60]
            # Warteschlangen-Schalter (Finns Notiz 22.09.2026): true = als Naechstes
            # kommt ein Trade DERSELBEN Firma -> "Don't remember me" NICHT setzen.
            cmd["sitzung_merken"] = bool(body.get("sitzung_merken"))
            # Schritt 3 (22.09.2026): Symbol des Plans -> Watchlist-Klick. Dieselbe
            # Zeichenpruefung wie bei tv-order; ohne Symbol bleibt es bei Schritt 1+2.
            sym = str(body.get("symbol") or "").strip()
            if sym and not SYMBOL_RE.fullmatch(sym):
                return self._send(400, json.dumps({"ok": False, "msg": "Symbol ungueltig"}))
            cmd["symbol"] = sym
            # Felder fuer Schritt 4 (Order) schon JETZT durchreichen, damit der naechste
            # Bau-Schritt keinen Panel-Neustart mehr braucht (der ist der langsame Teil).
            cmd["richtung"] = str(body.get("richtung") or "").strip().lower()[:8]
            for _f in ("volumen", "tp_usd", "sl_usd"):
                cmd[_f] = body.get(_f) if isinstance(body.get(_f), (int, float, str)) else None
            cmd["probe"] = bool(body.get("probe"))
            # Schritt 4b (22.09.2026): NUR mit dieser Marke klickt der Bot den Kauf-Knopf.
            # Ein altes Panel kennt sie nicht — dann reist sie ueber die Bruecke (@scharf=1).
            cmd["scharf"] = body.get("scharf") is True
            if scharf_konto_fest():   # 02.11.2026: kein Puls-Chrome-Neustart bei offenem TV-Trade mit Hedge (Simon 18:31); der Start selbst läuft wie immer
                cmd["kein_neustart"] = True
            # Geschwister = External IDs der anderen aktiven Konten DERSELBEN
            # Firma (aus Prophos). Steht eines davon im Panel, ist es derselbe
            # Tradovate-Login und der Bot wechselt nur im Dropdown.
            g = body.get("geschwister")
            cmd["geschwister"] = [str(x).strip()[:60] for x in g][:60] if isinstance(g, list) else []
            # HARTE LINIE (13.10.2026): nur beim scharfen Klick (scharf oder Bruecken-Marke @scharf=1) — Plan-ID kommt als
            # Marke @plan_id= mit. Nicht frei / nicht pruefbar -> kein Bot-Start, beweisbar nichts gesendet (richtung_frei).
            if cmd["scharf"] or "@scharf=1" in cmd["geschwister"]:
                _pid = next((x[9:] for x in cmd["geschwister"] if x.startswith("@plan_id=")), body.get("plan_id"))
                # Richtung: echtes Feld, sonst die Bruecken-Marke @richtung= (so schickte der Orbit-Tab bis 30.10.2026); fehlt beides
                # oder die Plan-ID -> gesperrt statt frei (riegel_pflicht_fehlt). Der Bot bekommt dieselbe Richtung wie der Riegel.
                if not cmd["richtung"]:
                    cmd["richtung"] = next((x[10:] for x in cmd["geschwister"] if x.startswith("@richtung=")), "").strip().lower()[:8]
                _fehlt = riegel_pflicht_fehlt(_pid, cmd["richtung"])
                if _fehlt:
                    print(f"[panel] tv-konto RIEGEL ohne plan_id/richtung @{cmd['ext_id']} -> gesperrt", flush=True)
                    return self._send(200, json.dumps({"ok": False, "code": "riegel_unerreichbar", "retry_ok": True, "gesendet": False,
                                                       "msg": _fehlt}, ensure_ascii=False))
                _zweit = {}
                _frei, _msg, _code = richtung_frei(_pid, cmd["richtung"], zweit_aus=_zweit)
                if not _frei:
                    print(f"[panel] tv-konto RIEGEL {_code} @{cmd['ext_id']} {cmd['richtung']}: {_msg[:160]}", flush=True)
                    return self._send(200, json.dumps({"ok": False, "code": _code, "retry_ok": True, "gesendet": False, "msg": _msg, **_zweit}, ensure_ascii=False))
            if not TV_ORDER_LOCK.acquire(blocking=False):
                # code + retry_ok (Cross-Check 24.09.2026): der Orbit-Start im Frontend wartet bei
                # puls_beschaeftigt (Rundgang/tv-close halten den Lock minutenlang) statt abzubrechen —
                # dafuer braucht er denselben Code wie tv-lesen/tv-close. Hier ist noch nichts gesendet.
                return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True, "msg":
                    "Es laeuft schon ein TradingView-Lauf — kurz warten."}, ensure_ascii=False))
            try:
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                # 260s (seit 2b, 21.09.2026 nachts): Start-Beweis (45) + Broker
                # lesen (40) + abmelden (20) + verbinden (25) + Tradovate-Fenster
                # und Autofill (50) + Fenster zu (35) + neu lesen (45) — im
                # Normalfall ist nach wenigen Sekunden Schluss, die Zahl ist die
                # Obergrenze des laengsten Wegs.
                p = subprocess.run([*bot_argv(bot), "tvkonto", json.dumps(cmd)],
                                   capture_output=True, text=True, errors="replace", timeout=260)
                line = (p.stdout or "").strip().splitlines()
                res = json.loads(line[-1]) if line else {
                    "ok": False, "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "msg": "TV-Konto-Pruefung Timeout (260s) — in TradingView nachsehen, wie weit er kam."}
                if cmd.get("scharf"):
                    # 4b: der Kauf-Klick KANN schon raus sein — nie blind wiederholen.
                    res["retry_ok"] = False
            except (OSError, ValueError) as e:
                res = {"ok": False, "msg": f"TV-Konto-Pruefung fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            puls_beleg_merken(res)   # PULS-BELEG (02.11.2026): welches Konto Puls zuletzt bewiesen gewählt hat (Schließ-Wache, gekürzte Apex-Texte)
            print(f"[panel] TV-Konto {cmd['firma']} @{cmd['ext_id']} -> {res.get('ok')} "
                  f"[{res.get('zustand')}] ({res.get('msg')}) {res.get('trail') or ''}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/tsx-konto":
            # Puls für Topstep, Etappe 2 (27.09.2026, Plan B26, vom Master freigegeben): Order in TopstepX per UIA.
            # scharf:false = PROBE bis vor den Order-Knopf (Brackets/Contract/Menge werden wirklich gesetzt, kein Klick auf
            # BUY/SELL); scharf nur bei echtem true (Finns Schalter „scharf"). Antwort wie /api/tv-konto.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "retry_ok": True, "msg": f"ungueltige Daten: {e}"}))
            felder = ("ext_id", "firma", "symbol", "richtung", "volumen", "tp_usd", "sl_usd", "plan_id")
            cmd = {k: body.get(k) for k in felder}
            cmd["scharf"] = body.get("scharf") is True
            if scharf_konto_fest():   # 02.11.2026: bei offenem TV-Trade mit Hedge nie das Puls-Chrome neu starten (Simon 18:31)
                cmd["kein_neustart"] = True
            # HARTE LINIE (13.10.2026, Anlass Mike: Topstep-Short laeuft, zwei Longs geplant): vor dem scharfen Klick fragt das Panel
            # Railway/DB selbst (richtung_frei) — unabhaengig vom Waechter im Tab. Nicht frei / nicht pruefbar -> nichts gesendet.
            if cmd["scharf"]:
                _fehlt = riegel_pflicht_fehlt(cmd.get("plan_id"), cmd.get("richtung"))   # 30.10.2026: ohne Plan/Richtung gesperrt
                if _fehlt:
                    print(f"[panel] tsxorder RIEGEL ohne plan_id/richtung @{cmd.get('ext_id')} -> gesperrt", flush=True)
                    return self._send(200, json.dumps({"ok": False, "code": "riegel_unerreichbar", "retry_ok": True, "gesendet": False,
                                                       "msg": _fehlt}, ensure_ascii=False))
                _zweit = {}
                _frei, _msg, _code = richtung_frei(cmd.get("plan_id"), cmd.get("richtung"), zweit_aus=_zweit)
                if not _frei:
                    print(f"[panel] tsxorder RIEGEL {_code} @{cmd.get('ext_id')} {cmd.get('richtung')}: {_msg[:160]}", flush=True)
                    return self._send(200, json.dumps({"ok": False, "code": _code, "retry_ok": True, "gesendet": False, "msg": _msg, **_zweit}, ensure_ascii=False))
            if len(re.sub(r"[^A-Za-z0-9]", "", str(cmd.get("ext_id") or ""))) < 5:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "retry_ok": True, "gesendet": False,
                    "msg": "Feld 'ext_id' (External ID) fehlt oder ist zu kurz"}, ensure_ascii=False))
            if not TV_ORDER_LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True, "gesendet": False,
                    "msg": "Es laeuft schon ein Browser-Lauf (Order/Konto/Lesen) — spaeter erneut."}, ensure_ascii=False))
            to = 170                                    # Bot-Wachhund steht auf 150 s — das Panel wartet länger
            try:
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                if not os.path.exists(bot):
                    res = {"ok": False, "code": "bot_fehlt", "retry_ok": True, "gesendet": False, "msg": "order_bot.py fehlt auf diesem PC."}
                else:
                    p = subprocess.run([*bot_argv(bot), "tsxorder", json.dumps(cmd)],
                                       capture_output=True, text=True, errors="replace", timeout=to,
                                       env=dict(os.environ, PULS_BOT_STAND=f"{BOT_STAND.get('version') or '?'} {str(BOT_STAND.get('sha') or '')[:7]}"))
                    line = (p.stdout or "").strip().splitlines()
                    res = json.loads(line[-1]) if line else {
                        "ok": False, "code": "bot_stumm", "retry_ok": not cmd["scharf"],
                        "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                # scharf: der Klick KANN schon raus sein — nie blind wiederholen
                res = {"ok": False, "code": "timeout", "retry_ok": not cmd["scharf"],
                       "msg": f"TopstepX-Order Timeout ({to}s) — in TopstepX nachsehen, wie weit er kam."}
            except (OSError, ValueError) as e:
                res = {"ok": False, "code": "bot_fehlt", "retry_ok": not cmd["scharf"], "msg": f"TopstepX-Order fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            print(f"[panel] tsxorder {'SCHARF' if cmd['scharf'] else 'probe'} @{cmd.get('ext_id')}: "
                  f"{'ok' if res.get('ok') else res.get('code')} [{res.get('schritt')}] · {str(res.get('msg') or '')[:120]} "
                  f"{res.get('trail') or ''}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))
        if u.path in ("/api/tsx-lesen", "/api/tsx-inventar"):
            # Puls für Topstep, Etappe 1 (27.09.2026, Auftrag Koordination B16): TopstepX-Web-App per UIA — NUR LESEN,
            # keine Order. tsx-lesen = Konto wählen + BAL/MLL/RP&L/UP&L + „No Active Position" (Vertrag wie tv-lesen:
            # summary/konto_aktiv/positionen); tsx-inventar = UIA-Inventar Grundzustand/Konto-Dropdown/Bracket-Dialog.
            # Unter dem TV-Lock wie jeder Browser-Lauf (ein Chrome, eine Maus).
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": f"ungueltige Daten: {e}"}))
            modus = "tsxlesen" if u.path == "/api/tsx-lesen" else "tsxinventar"
            konto = str(body.get("konto") or body.get("ext_id") or "").strip()[:60]
            if modus == "tsxlesen" and len(re.sub(r"[^A-Za-z0-9]", "", konto)) < 5:
                return self._send(400, json.dumps({"ok": False, "code": "befehl",
                    "msg": "Feld 'konto' (External ID) fehlt oder ist zu kurz"}, ensure_ascii=False))
            cmd = {"konto": konto, "firma": str(body.get("firma") or "").strip()[:60]}
            if scharf_konto_fest():   # 02.11.2026: kein Puls-Chrome-Neustart bei offenem TV-Trade mit Hedge (Simon 18:31)
                cmd["kein_neustart"] = True
            if modus == "tsxlesen" and body.get("auge_reparieren") is True:
                cmd["auge_reparieren"] = True   # 29.10.2026: Heimweg „TopstepX-Auge blind" — Bot lädt neu / öffnet den Tab neu (order_bot._tsx_auge_reparieren)
            if not TV_ORDER_LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True,
                    "msg": "Es laeuft schon ein Browser-Lauf (Order/Konto/Lesen) — spaeter erneut."}, ensure_ascii=False))
            to = 150 + (110 if cmd.get("auge_reparieren") else 0)   # Auge-Reparatur: Bot-Wachhund +100 s (29.10.2026, 240 s < 260 s)
            try:
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                if not os.path.exists(bot):
                    res = {"ok": False, "code": "bot_fehlt", "retry_ok": True, "msg": "order_bot.py fehlt auf diesem PC."}
                else:
                    p = subprocess.run([*bot_argv(bot), modus, json.dumps(cmd)],
                                       capture_output=True, text=True, errors="replace", timeout=to,
                                       env=dict(os.environ, PULS_BOT_STAND=f"{BOT_STAND.get('version') or '?'} {str(BOT_STAND.get('sha') or '')[:7]}"))
                    line = (p.stdout or "").strip().splitlines()
                    res = json.loads(line[-1]) if line else {
                        "ok": False, "code": "bot_stumm",
                        "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "code": "timeout", "retry_ok": True,
                       "msg": f"TopstepX-Lauf Timeout ({to}s) — in TopstepX nachsehen, wie weit er kam."}
            except (OSError, ValueError) as e:
                res = {"ok": False, "code": "bot_fehlt", "msg": f"TopstepX-Lauf fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            print(f"[panel] {modus}: {'ok' if res.get('ok') else res.get('code')} · {str(res.get('msg') or '')[:120]}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))
        if u.path == "/api/tv-lesen":
            # Orbit-V2-Rundgang (24.09.2026 nachts, Finn: "Der Bot geht sich in
            # einem gewissen Intervall automatisch in das Konto bei Tradovate auf
            # TradingView, genauso wie man einen Trade startet. Er liest, ob die
            # Position noch offen ist oder schon beendet. Ist sie beendet, kann
            # man bei Today's P&L sehen, wie viel sich bewegt hat"). Duplikum ist
            # weg — Orbit V2 (tvv2) bekommt Ende + P&L jetzt ueber diesen Weg.
            # Gleiche Bauart wie /api/tv-konto: Config-Felder aus der Basis-Config,
            # Bot-Aufruf, UNTER dem TV-Lock (ein Browser, eine Maus — nie in einen
            # laufenden Order-/Konto-Lauf hineinklicken). Bewusst OHNE Copier-
            # Frische-Riegel (V2 hat keinen Copier) und ohne Echo-Pause-Riegel
            # (hier wird nur gelesen).
            # Vertrag: 200 ok · 409 puls_beschaeftigt / konto_nicht_erreicht ·
            # sonst 200 mit ok:false + code. Seit 24.09.2026 (Finn: „alles ohne
            # Tampermonkey-Script, wenn es geht") kein 503 reader_fehlt mehr: der
            # Bot liest ohne Reader per UIA; die Antwort traegt 'quelle'
            # ('reader' | 'uia'), das Log nennt sie.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": f"ungueltige Daten: {e}"}))
            konto = str(body.get("konto") or body.get("ext_id") or "").strip()[:60]
            _kf = _lese_sperre_antwort(konto, u.path)   # LESE-SPERRE (02.11.2026): 18:30–18:40 Dubai keine Lesung/kein Kontowechsel in TradingView
            if _kf:
                return self._send(409, _kf)
            if len(re.sub(r"[^A-Za-z0-9]", "", konto)) < 3:
                return self._send(400, json.dumps({"ok": False, "code": "befehl",
                    "msg": "Feld 'konto' (External ID) fehlt oder ist kuerzer als 3 Zeichen"}, ensure_ascii=False))
            try:
                timeout_s = max(10.0, min(180.0, float(body.get("timeout_s") or 45)))
            except (TypeError, ValueError):
                timeout_s = 45.0
            bc = base_config()
            cmd = {k: str(bc.get(k) or "").strip()
                   for k in ("tv_url", "tv_browser_path", "tv_chrome_profil")}
            cmd["konto"] = konto
            cmd["timeout_s"] = timeout_s
            # Optional, wie bei tv-konto: Username/Firma/Geschwister erlauben dem
            # Konto-Schritt den Login-Wechsel bzw. den Dropdown-Weg. Ohne sie
            # bleibt es beim Lesen + Dropdown im aktuellen Login.
            cmd["tv_username"] = str(body.get("tv_username") or "").strip()
            cmd["firma"] = str(body.get("firma") or "").strip()[:60]
            cmd["sitzung_merken"] = bool(body.get("sitzung_merken"))
            g = body.get("geschwister")
            cmd["geschwister"] = [str(x).strip()[:60] for x in g][:60] if isinstance(g, list) else []
            # Endlesung (25.09.2026): Ende-Modus des Bots — Befund bei Fehlschlag, Rueckfall Handelspanel,
            # Exit-Fill aus der Order-Historie. Ohne 'ende' liest der Bot genau wie bisher (Rundgang, Start).
            cmd["ende"] = bool(body.get("ende"))
            cmd["symbol"] = str(body.get("symbol") or "").strip()[:30]
            _ri = str(body.get("richtung") or "").strip().lower()
            cmd["richtung"] = _ri if _ri in ("buy", "sell") else ""
            if not TV_ORDER_LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True,
                    "msg": "Es laeuft schon ein TradingView-Lauf (Order/Konto/Lesen) — spaeter erneut."},
                    ensure_ascii=False))
            try:
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                if not os.path.exists(bot):
                    res = {"ok": False, "code": "bot_fehlt", "retry_ok": True, "msg":
                           "order_bot.py fehlt auf diesem PC und Download schlug fehl — "
                           "einmal 'Alles neu starten' klicken, dann erneut."}
                else:
                    # Konto-Schritt (bis 45 s TV-Start + Lesen + Dropdown) + Lesephase
                    # (timeout_s) + Puffer; ist ein Login-Wechsel moeglich (Username
                    # dabei), gilt die 260-s-Obergrenze von tv-konto.
                    # +110 statt +90 (Cross-Check 24.09.2026): der Konto-Schritt allein kann ohne Login-
                    # Wechsel ~105 s brauchen (TV-Start 45 + Lesen 40 + Dropdown), plus Lesephase — sonst
                    # killt das Panel den Bot kurz vor dem Stand. Deckel 300 < Proxy 310 (app.py).
                    to = min(300, int(timeout_s) + 110 + (25 if cmd["ende"] else 0))   # Ende-Modus: Historie + Befund
                    if cmd["tv_username"]:
                        to = max(to, 260)
                    p = subprocess.run([*bot_argv(bot), "tvlesen", json.dumps(cmd)],
                                       capture_output=True, text=True, errors="replace", timeout=to)
                    line = (p.stdout or "").strip().splitlines()
                    res = json.loads(line[-1]) if line else {
                        "ok": False, "code": "bot_stumm",
                        "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "code": "timeout", "retry_ok": True,
                       "msg": f"TV-Lesen Timeout ({to}s) — in TradingView nachsehen, wie weit er kam."}
            except (OSError, ValueError) as e:
                res = {"ok": False, "code": "bot_fehlt", "msg": f"TV-Lesen fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            puls_beleg_merken(res)   # PULS-BELEG (02.11.2026): welches Konto Puls zuletzt bewiesen gewählt hat (Schließ-Wache, gekürzte Apex-Texte)
            http = 200
            if not res.get("ok"):
                http = {"konto_nicht_erreicht": 409}.get(str(res.get("code") or ""), 200)
            # Kurze Zeile je Lesung (24.09.2026, Rundgang alle 50–80 s — das Log soll
            # lesbar bleiben): Erfolg = Konto, Positionen, Today, Klicks im Konto-Schritt,
            # Quelle (reader/uia); Fehler = Code + Meldung. Die Spur gibt es weiter in der Antwort.
            if res.get("ok"):
                _t = res.get("today_pnl")
                print(f"[panel] tv-lesen {konto}: {len(res.get('positionen') or [])} Pos, today "
                      f"{('%+.2f' % _t) if isinstance(_t, (int, float)) else '?'}"
                      f" · {res.get('konto_klicks', '?')} Klick(s) · Quelle {res.get('quelle') or '?'}", flush=True)
            else:
                print(f"[panel] tv-lesen {konto}: FEHLER {res.get('code') or '?'} (Quelle {res.get('quelle') or '?'}) — "
                      f"{str(res.get('msg') or '')[:160]}", flush=True)
            return self._send(http, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/tv-konten-liste":
            # TV-Konten lesen (29.10.2026, Finn: „im Zufallsintervall nach der Kauf-Mail kurz einloggen und alle neuen externen IDs lesen"):
            # Bot-Modus tvkontenliste — Seite neu laden, ggf. Login der Firma (dabei wird das mitgegebene bekannte Konto gewählt, wie bei jeder
            # Balance-Lesung), Konto-Liste lesen, Esc; im Lese-Schritt nie ein Listeneintrag, nie Order.
            # Unter dem TV-Lock wie tv-lesen (ein Browser, eine Maus). Vertrag: 200 {ok, konten, liste_n, login_gewechselt, trail} · 409 belegt.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": f"ungueltige Daten: {e}"}))
            konto = str(body.get("konto") or "").strip()[:60]
            _kf = _lese_sperre_antwort(konto, u.path)   # LESE-SPERRE (02.11.2026): 18:30–18:40 Dubai keine Lesung/kein Kontowechsel in TradingView
            if _kf:
                return self._send(409, _kf)
            if len(re.sub(r"[^A-Za-z0-9]", "", konto)) < 3:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "Feld 'konto' fehlt"}, ensure_ascii=False))
            bc = base_config()
            cmd = {k: str(bc.get(k) or "").strip() for k in ("tv_url", "tv_browser_path", "tv_chrome_profil")}
            cmd["konto"] = konto
            cmd["tv_username"] = str(body.get("tv_username") or "").strip()
            cmd["firma"] = str(body.get("firma") or "").strip()[:60]
            g = body.get("geschwister")
            cmd["geschwister"] = [str(x).strip()[:60] for x in g][:60] if isinstance(g, list) else []
            if not TV_ORDER_LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True,
                    "msg": "Es laeuft schon ein TradingView-Lauf — spaeter erneut."}, ensure_ascii=False))
            to = 260   # Login-Weg mit Wiederholung im frischen Tab kann auch ohne Username lang werden (Prüfer 29.10.2026)
            try:
                # MT5 FREI (Master 29.10.2026): offene Echo-/Echo-V2-Pläne sperren das Lesen im PC-Tab nicht mehr (tvkFrei zählt nur tvv2/tsv2) —
                # dafür hier: keine MT5-Order/Polar gerade (_browser_und_mt5_frei) und ≥ TAB_NL_IDLE_S keine Eingabe am PC; sonst 409 belegt
                idle = _win_leerlauf_s()
                if not _browser_und_mt5_frei(tv_eigen=True) or (idle is not None and idle < TAB_NL_IDLE_S):
                    grund = "MT5-Order/Polar läuft" if not _browser_und_mt5_frei(tv_eigen=True) else f"am PC wird gearbeitet (letzte Eingabe vor {int(idle)} s)"
                    print(f"[panel] tv-konten-liste {konto}: belegt — {grund}", flush=True)
                    return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True,
                        "msg": f"TV-Konten lesen vertagt: {grund}", "trail": f"Panel: {grund} — nichts geklickt"}, ensure_ascii=False))
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                if not os.path.exists(bot):
                    res = {"ok": False, "code": "bot_fehlt", "msg": "order_bot.py fehlt auf diesem PC"}
                else:
                    p = subprocess.run([*bot_argv(bot), "tvkontenliste", json.dumps(cmd)],
                                       capture_output=True, text=True, errors="replace", timeout=to)
                    line = (p.stdout or "").strip().splitlines()
                    res = json.loads(line[-1]) if line else {"ok": False, "code": "bot_stumm",
                        "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "code": "timeout", "msg": f"TV-Konten lesen Timeout ({to}s)"}
            except (OSError, ValueError) as e:
                res = {"ok": False, "code": "bot_fehlt", "msg": f"TV-Konten lesen fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            puls_beleg_merken(res)   # PULS-BELEG (02.11.2026): welches Konto Puls zuletzt bewiesen gewählt hat (Schließ-Wache, gekürzte Apex-Texte)
            print(f"[panel] tv-konten-liste {konto}: " + (f"{len(res.get('konten') or [])} Name(n)" if res.get("ok")
                  else f"FEHLER {res.get('code') or '?'} — {str(res.get('msg') or '')[:140]}"), flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path in ("/api/tv-neuladen", "/api/tv-tm-update"):
            # Userscript-Update (29.10.2026): tv-neuladen = TradingView-Tab im Puls-Chrome neu laden, damit der Lader die bereitliegende
            # neuere Fassung startet (nur Page.reload); tv-tm-update = einmal je PC in Tampermonkey „Aktualisieren" (nur auf dessen Seite,
            # danach Neuladen). Beide unter dem TV-Lock (nie in einen laufenden Order-/Lese-Lauf), 409 = belegt.
            tm = u.path == "/api/tv-tm-update"
            modus, frist = ("tvtmupdate", 150) if tm else ("tvneuladen", 90)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": f"ungueltige Daten: {e}"}))
            bc = base_config()
            cmd = {k: str(bc.get(k) or "").strip() for k in ("tv_url", "tv_browser_path", "tv_chrome_profil")}
            cmd["grund"] = str(body.get("grund") or "").strip()[:80]
            if str(body.get("tab") or "") == "tsx":           # Auge-Lader (29.10.2026): TopstepX-Tab bzw. TopstepX-Auge statt TV-Reader
                cmd["tab"] = cmd["art"] = "tsx"
            if not TV_ORDER_LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True,
                    "msg": "Es laeuft schon ein TradingView-Lauf — spaeter erneut."}, ensure_ascii=False))
            try:
                # Prüfer 29.10.2026: auch keine MT5-Order (Echo V2 hängt nicht am TV-Lock), kein Polar, niemand tippt gerade am PC
                idle = _win_leerlauf_s()
                if not _browser_und_mt5_frei(tv_eigen=True) or (idle is not None and idle < TAB_NL_IDLE_S):
                    return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True,
                        "msg": "MT5-Order/Polar laeuft oder am PC wird gerade gearbeitet — spaeter erneut."}, ensure_ascii=False))
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                p = subprocess.run([*bot_argv(bot), modus, json.dumps(cmd)],
                                   capture_output=True, text=True, errors="replace", timeout=frist)
                line = (p.stdout or "").strip().splitlines()
                res = json.loads(line[-1]) if line else {"ok": False, "code": "bot_stumm", "msg": (p.stderr or "").strip()[-200:] or "keine Antwort"}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "code": "timeout", "msg": f"{modus} Timeout ({frist} s)"}
            except (OSError, ValueError) as e:
                res = {"ok": False, "code": "bot_fehlt", "msg": f"{modus} fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            print(f"[panel] {modus}: {'ok' if res.get('ok') else 'FEHLER ' + str(res.get('code') or '?')} — {str(res.get('msg') or '')[:140]}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/tv-close":
            # Orbit V2 schliessen (24.09.2026, Vollumstieg 'Ohne Hedge'; Finns
            # Auto-Close-Regel 23:45–00:00 Dubai, bisher 'Orbit-Schliessen in TV
            # offen'): der Bot faehrt das Konto an wie bei tv-lesen und flattet
            # die Position der Symbol-Wurzel ueber TradingViews eigenen
            # Schliessen-Knopf in der Positions-Tabelle (+ Rueckfrage). Beweis:
            # Reader-Stand juenger als der Klick, ohne die Position, zweimal —
            # ohne Reader (seit 24.09.2026) die UIA-Tabelle zweimal ohne die Zeile.
            # Gleiche Bauart wie /api/tv-lesen: Config-Felder aus der Basis-Config,
            # UNTER dem TV-Lock. Kein Echo-Pause-Riegel (Schliessen ist die sichere
            # Richtung; die Pause gilt dem MT5-Echo), kein Copier-Riegel (V2 hat
            # keinen Copier).
            # Vertrag: 200 ok (code '' = geschlossen, 'schon_flach' = war nichts
            # offen) · 409 puls_beschaeftigt / konto_nicht_erreicht · sonst 200 mit
            # ok:false + code (close_knopf_unklar, bestaetigung_unklar, ende_unklar,
            # fenster, tabelle_unklar, bot_fehlt, tv_fehlt, befehl, timeout, absturz).
            # Seit 24.09.2026 kein 503 reader_fehlt und keine reader_*-Codes mehr:
            # ohne Reader laeuft der Bot per UIA, die Antwort traegt 'quelle'.
            # retry_ok:false, sobald ein Klick raus war (geklickt:true).
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": f"ungueltige Daten: {e}"}))
            konto = str(body.get("konto") or body.get("ext_id") or "").strip()[:60]
            if len(re.sub(r"[^A-Za-z0-9]", "", konto)) < 3:
                return self._send(400, json.dumps({"ok": False, "code": "befehl",
                    "msg": "Feld 'konto' (External ID) fehlt oder ist kuerzer als 3 Zeichen"}, ensure_ascii=False))
            symbol = str(body.get("symbol") or "").strip()
            if not SYMBOL_RE.fullmatch(symbol or ""):
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "Symbol ungueltig"}))
            richtung = str(body.get("richtung") or "").strip().lower()
            if richtung and richtung not in ("buy", "sell"):
                return self._send(400, json.dumps({"ok": False, "code": "befehl",
                    "msg": "richtung muss buy/sell sein (oder fehlen)"}, ensure_ascii=False))
            try:
                timeout_s = max(10.0, min(180.0, float(body.get("timeout_s") or 45)))
            except (TypeError, ValueError):
                timeout_s = 45.0
            bc = base_config()
            cmd = {k: str(bc.get(k) or "").strip()
                   for k in ("tv_url", "tv_browser_path", "tv_chrome_profil")}
            cmd["konto"] = konto
            cmd["symbol"] = symbol
            cmd["richtung"] = richtung
            cmd["timeout_s"] = timeout_s
            cmd["tv_username"] = str(body.get("tv_username") or "").strip()
            cmd["firma"] = str(body.get("firma") or "").strip()[:60]
            cmd["sitzung_merken"] = bool(body.get("sitzung_merken"))
            g = body.get("geschwister")
            cmd["geschwister"] = [str(x).strip()[:60] for x in g][:60] if isinstance(g, list) else []
            if not TV_ORDER_LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "code": "puls_beschaeftigt", "retry_ok": True,
                    "msg": "Es laeuft schon ein TradingView-Lauf (Order/Konto/Lesen/Schliessen) — spaeter erneut."},
                    ensure_ascii=False))
            # +150 statt +120 (Cross-Check 24.09.2026): laengste Kette = Konto-Schritt ~105 + Vorher-Stand 30
            # + Fenster 8 + Knopf 10 + Rueckfrage 8 + Beweis timeout_s + Today 7 — mit den 90 s des Frontends
            # waren 210 s zu knapp; ein Timeout HIER ist der teuerste Ausgang (Klick evtl. raus, retry_ok
            # False). Deckel 300 < Proxy 310 (app.py).
            to = min(300, int(timeout_s) + 150)
            try:
                bot = os.path.join(HERE, "order_bot.py")
                if not os.path.exists(bot):
                    ensure_bot_source()
                if not os.path.exists(bot):
                    res = {"ok": False, "code": "bot_fehlt", "retry_ok": True, "msg":
                           "order_bot.py fehlt auf diesem PC und Download schlug fehl — "
                           "einmal 'Alles neu starten' klicken, dann erneut."}
                else:
                    # Konto-Schritt (bis 45 s) + Vorher-Stand (bis 30 s) + Knopf (10 s) +
                    # Rueckfrage (8 s) + Beweis (timeout_s) + Puffer; mit Login-Wechsel
                    # die 260-s-Obergrenze von tv-konto.
                    if cmd["tv_username"]:
                        to = max(to, 260)
                    p = subprocess.run([*bot_argv(bot), "tvclose", json.dumps(cmd)],
                                       capture_output=True, text=True, errors="replace", timeout=to)
                    line = (p.stdout or "").strip().splitlines()
                    res = json.loads(line[-1]) if line else {
                        "ok": False, "code": "bot_stumm", "retry_ok": False,
                        "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                # retry_ok=False: der Klick KANN raus sein — nie blind wiederholen.
                res = {"ok": False, "code": "timeout", "retry_ok": False,
                       "msg": f"TV-Schliessen Timeout ({to}s) — in TradingView nachsehen, ob die Position noch offen ist."}
            except (OSError, ValueError) as e:
                res = {"ok": False, "code": "bot_fehlt", "retry_ok": True, "msg": f"TV-Schliessen fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            puls_beleg_merken(res)   # PULS-BELEG (02.11.2026): welches Konto Puls zuletzt bewiesen gewählt hat (Schließ-Wache, gekürzte Apex-Texte)
            http = 200
            if not res.get("ok"):
                http = {"konto_nicht_erreicht": 409}.get(str(res.get("code") or ""), 200)
            _t = res.get("today_pnl")
            print(f"[panel] tv-close {konto} {symbol}{(' ' + richtung) if richtung else ''}: "
                  f"{'OK' if res.get('ok') else 'FEHLER'} [{res.get('code') or 'geschlossen'}]"
                  f" geklickt={res.get('geklickt')} · {len(res.get('positionen_danach') or [])} Pos danach"
                  f" · today {('%+.2f' % _t) if isinstance(_t, (int, float)) else '?'}"
                  f" · Quelle {res.get('quelle') or '?'}"
                  + ("" if res.get("ok") else f" — {str(res.get('msg') or '')[:160]}"), flush=True)
            if res.get("trail"):
                print(f"[panel] tv-close Spur: {str(res['trail'])[:900]}", flush=True)
            return self._send(http, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/tv-order":
            # Orbit-Puls Schritt 2 (30.08.2026, Finns Ablauf 1-5): der Bot faehrt
            # die ganze Kette in TradingView — Tab nach vorn, Unterkonto per
            # External ID, Symbol, Order-Ticket ausfuellen, platzieren. Gleiche
            # Bauart wie /api/tv-fokus (OHNE Instanz-Bezug im Aufruf, der Weg
            # fuehrt durch den Browser statt durch ein MT5-Terminal), aber mit
            # den Riegeln von /api/master-order — hier wird echtes Geld bewegt.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            if os.path.exists(os.path.join(HERE, "echo_pause.flag")):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                    "grund": "echo_pausiert", "msg":
                    "Echo ist pausiert — es wird keine neue Order platziert. Erst oben "
                    "auf Fortsetzen klicken."}, ensure_ascii=False))
            cmd = {"ext_id": str(body.get("ext_id") or "").strip(),
                   "symbol": str(body.get("symbol") or "").strip(),
                   "richtung": str(body.get("richtung") or "").lower(),
                   "volumen": body.get("volumen"),
                   "sl_usd": body.get("sl_usd"), "tp_usd": body.get("tp_usd"),
                   # Probelauf (30.08.2026): faehrt die ganze Kette, klickt den
                   # Senden-Knopf aber nicht. Gedacht fuer den ersten Lauf auf
                   # einem PC — und fuer geschlossene Maerkte, wo ein echter
                   # Versuch nur eine unklare Lage erzeugen wuerde.
                   "probe": bool(body.get("probe"))}
            if not SYMBOL_RE.fullmatch(cmd["symbol"] or ""):
                return self._send(400, json.dumps({"ok": False, "msg": "Symbol ungueltig"}))
            # HARTE LINIE AUCH HIER (30.10.2026, ORBIT-RICHTUNG-RIEGEL, Gegenpruefung): der alte Orbit-Weg platziert echt, ruft prophos.html
            # nicht mehr auf, ist aber ueber Panel/Railway-Proxy erreichbar und hatte keinen Gegenrichtungs-Riegel. Ohne Plan-UUID/Richtung
            # oder nicht frei -> gesperrt, beweisbar nichts gesendet. Probe (klickt nie) bleibt frei.
            if not cmd["probe"]:
                _pid = str(body.get("plan_id") or "").strip()
                _fehlt = riegel_pflicht_fehlt(_pid, cmd["richtung"])
                _zweit = {}   # ZWEI ORBIT (03.11.2026, Z4): zweit/zweit_art von Railway an den Tab
                _frei, _msg, _code = (False, _fehlt, "riegel_unerreichbar") if _fehlt else richtung_frei(_pid, cmd["richtung"], zweit_aus=_zweit)
                if not _frei:
                    print(f"[panel] tv-order RIEGEL {_code} @{cmd['ext_id']} {cmd['richtung']}: {_msg[:160]}", flush=True)
                    return self._send(200, json.dumps({"ok": False, "code": _code, "grund": _code, "retry_ok": True, "gesendet": False,
                                                       "msg": _msg, **_zweit}, ensure_ascii=False))
            # Neustart-Sperre (25.09.2026): nach einem echten Puls-Start folgt der Hedge-Open —
            # 3 min kein Copier-Update-Neustart, damit er einen frischen Copier vorfindet
            if not cmd["probe"]:
                hedge_bereit_setzen(180, f"tv-order {cmd['symbol']}")

            # Hedge-Riegel, das Gegenstueck zum Frische-Check von master-order:
            # ohne laufende Orbit-Copier-Instanz bliebe die Futures-Position
            # UNGEHEDGET. Die Orbit-Instanz erkennt man daran, dass sie KEIN
            # Master-Terminal hat (der TV-Verbinder speist das Snapshot-CSV) und
            # immer scharf ist. Genau EINE muss es sein — mehrere waeren der
            # Mehrkonten-Fall, und der ist bewusst noch nicht gebaut (Finns
            # Vorgabe 30.08.2026: "erstmal nur 1 tap nur 1 acc").
            orbit = []
            for i in instances():
                c = read_json(os.path.join(HERE, i["config_file"]), {}) or {}
                if not str(c.get("master_terminal_path") or "").strip() and c.get("snapshot_file"):
                    orbit.append(i)
            if len(orbit) != 1:
                return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                    "grund": "keine_orbit_instanz", "msg":
                    (f"{len(orbit)} Orbit-Copier-Instanzen auf diesem PC gefunden — "
                     "erwartet wird genau eine. Ohne sie bliebe die Order UNGEHEDGET."
                     if orbit else
                     "Keine Orbit-Copier-Instanz auf diesem PC (config-tvplus.json) — "
                     "die Order bliebe UNGEHEDGET. Erst den Orbit-Stack einrichten.")},
                    ensure_ascii=False))
            st = read_json(os.path.join(HERE, orbit[0]["status_file"]), {}) or {}
            age = None
            try:
                age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
            except (ValueError, TypeError):
                pass
            if not (st.get("running") and age is not None and age <= 15):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                    "grund": "copier_alt", "msg":
                    "Orbit-Copier liefert keine frischen Daten — die Order wuerde "
                    "UNGEHEDGET bleiben. Erst den Stack gruen bekommen."}, ensure_ascii=False))

            # EIN Lock fuer den ganzen TV-Weg (nicht pro Instanz wie bei
            # master-order): es gibt genau einen Browser und genau eine Maus —
            # zwei gleichzeitige Laeufe wuerden sich gegenseitig die Klicks
            # wegziehen, und das mitten in einem Order-Ticket.
            if not TV_ORDER_LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"ok": False, "retry_ok": False, "msg":
                    "Es laeuft schon ein TradingView-Order-Lauf — warten, dann in "
                    "TradingView nachsehen."}, ensure_ascii=False))
            bot = os.path.join(HERE, "order_bot.py")
            if not os.path.exists(bot):
                ensure_bot_source()
            if not os.path.exists(bot):
                TV_ORDER_LOCK.release()
                return self._send(200, json.dumps({"ok": False, "retry_ok": True, "msg":
                    "order_bot.py fehlt auf diesem PC und Download schlug fehl — "
                    "einmal 'Alles neu starten' klicken, dann erneut."}, ensure_ascii=False))
            try:
                # 180s: die Kette hat vier Warte-Etappen (Tab, Konto, Symbol,
                # Ticket) plus 25s Bestaetigungsfenster; der Rest ist Puffer.
                # Kuerzer waere die Fehlerklasse von 18.08.2026 — ein Abbruch
                # mitten im Ablauf, bei dem niemand weiss, wie weit er kam.
                p = subprocess.run([*bot_argv(bot), "tvorder", json.dumps(cmd)],
                                   capture_output=True, text=True, errors="replace", timeout=180)
                line = (p.stdout or "").strip().splitlines()
                res = json.loads(line[-1]) if line else {
                    "ok": False, "retry_ok": False,
                    "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "retry_ok": False,
                       "msg": "TV-Order Timeout (180s) — in TradingView pruefen, ob die "
                              "Order liegt, bevor irgendetwas wiederholt wird!"}
            except (OSError, ValueError) as e:
                res = {"ok": False, "retry_ok": False, "msg": f"TV-Order-Start fehlgeschlagen: {e}"}
            finally:
                TV_ORDER_LOCK.release()
            puls_beleg_merken(res)   # PULS-BELEG (02.11.2026): welches Konto Puls zuletzt bewiesen gewählt hat (Schließ-Wache, gekürzte Apex-Texte)
            print(f"[panel] TV-Order {cmd['richtung']} {cmd['volumen']} {cmd['symbol']} "
                  f"@{cmd['ext_id']} -> {res.get('ok')} ({res.get('schritt')}: {res.get('msg')})",
                  flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/pc-id":
            # Kennung eintragen, falls noch keine da ist; sonst die gespeicherte zurück (nie überschreiben)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            try:
                pid, neu = pc_id_setzen((body or {}).get("pc_id"))
            except ValueError as e:
                return self._send(400, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))
            except OSError as e:
                return self._send(500, json.dumps({"ok": False, "msg": f"pc_id.json nicht schreibbar: {e}"}, ensure_ascii=False))
            if neu:
                print(f"[panel] PC-Kennung eingetragen: {pid}", flush=True)
            return self._send(200, json.dumps({"ok": True, "pc_id": pid, "neu": neu}, ensure_ascii=False))
        if u.path == "/api/code-token":
            # PC-Schlüssel für die Code-Quelle (07.10.2026, Repo privat): der eingeloggte Prophos-Tab holt ihn bei Railway
            # (/reader-feed-token) und legt ihn hier ab. Nur das bekannte Format, atomar geschrieben.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            tok = str((body or {}).get("token") or "").strip()
            if not CODE_TOKEN_MUSTER.fullmatch(tok):
                return self._send(400, json.dumps({"ok": False, "msg": "Schluessel-Format ungueltig"}))
            try:
                with open(CODE_TOKEN_DATEI + ".tmp", "w", encoding="utf-8") as f:
                    f.write(tok + "\n")
                os.replace(CODE_TOKEN_DATEI + ".tmp", CODE_TOKEN_DATEI)
            except OSError as e:
                return self._send(500, json.dumps({"ok": False, "msg": f"code_token.txt nicht schreibbar: {e}"}))
            print("[panel] PC-Schluessel fuer die Code-Quelle abgelegt.", flush=True)
            return self._send(200, json.dumps({"ok": True}))
        if u.path == "/api/hedge-scharf":
            # SCHARF NACHHOLEN (02.11.2026, Eingang: Hedge offen, aber nie scharf — Tab beim Open noch auf altem Build, Panel neu gestartet …): der PC-Tab
            # meldet je offenem TV-Hedge dieses PCs einmal {plan_id, ticket, scharf}. Nur wenn das Ticket im Copier offen ist; schon scharf → nichts.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
                ticket = int(body.get("ticket") or 0)
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": f"ungueltige Daten: {e}"}))
            _sch = body.get("scharf") if isinstance(body.get("scharf"), dict) else {}
            if any(int(x.get("ticket") or 0) == ticket for x in scharf_laden()):
                # NV3: Topstep — der Tab sah den Master (oder Fill-Beleg) erst nach dem Open → Sichtung am Eintrag nachtragen (nur dasselbe Ticket, nur true)
                if _sch.get("quelle") == "tsx" and _sch.get("gesehen") is True:
                    with SCHARF_LOCK:
                        _l = scharf_laden()
                        for x in _l:
                            if int(x.get("ticket") or 0) == ticket and x.get("quelle") == "tsx" and not x.get("gesehen"):
                                x["gesehen"] = True
                                scharf_speichern(_l)
                                scharf_spur(ticket, "Sichtung vom Tab", "Master im Plan-Konto gesehen bzw. Fill-Beleg")
                                break
                return self._send(200, json.dumps({"ok": True, "schon": True}))
            offen = scharf_copier_solo()
            if offen is None or ticket not in offen:
                return self._send(200, json.dumps({"ok": False, "code": "nicht_offen" if offen is not None else "copier_alt",
                                                   "msg": "Ticket im Copier nicht offen" if offen is not None else "Copier-Liste nicht lesbar"}))
            # S9 02.11.2026: nur der Hedge DIESES Plans — der Copier kennt je Solo-Ticket plan8/plan_id; fehlt sie oder passt sie nicht → fremd, nichts setzen
            if not offen[ticket] or offen[ticket] != str(body.get("plan_id") or "")[:8]:
                scharf_spur(ticket, "NICHT gemerkt (Nachholen)", f"Ticket gehört laut Copier zu {offen[ticket] or '?'}, nicht zu {str(body.get('plan_id') or '')[:8]}")
                return self._send(200, json.dumps({"ok": False, "code": "fremd", "msg": "Ticket gehört laut Copier zu einem anderen Plan"}))
            try:
                rs = _scharf_stand_lesen() if _sch.get("quelle") != "tsx" else None
            except Exception:
                rs = None
            ok = scharf_setzen(body.get("scharf"), str(body.get("plan_id") or "")[:64], ticket, rs)
            return self._send(200, json.dumps({"ok": bool(ok), "code": "" if ok else "nicht_scharf"}))

        if u.path == "/api/hedge-solo":
            # Solo-Hedge auf dem Fusion-Hedge-Terminal (24.09.2026 abends, Winning Days
            # gegenhedgen ohne Duplikum — Finn: „direkt nach der Puls-Order auf Fusion
            # die Gegen-Order im Verhaeltnis, und sobald NQ den TP erreicht, schliessen").
            # Das Panel sendet NICHT selbst an MetaTrader (zweiter Prozess am Terminal,
            # README.md) — es schreibt einen Auftrag in hedge_solo_auftrag.json, der
            # laufende Copier fuehrt ihn im naechsten Tick aus (copier.solo_abarbeiten)
            # und quittiert in hedge_solo_ergebnis.json. Hier wird bis ~14 s gewartet.
            # Body: {aktion:'open', richtung:'buy'|'sell' (Richtung der HEDGE-Order),
            #        eur, punkte, symbol?, lots?}  |  {aktion:'close', ticket, grund?}
            # Antwort: Ergebnis des Copiers (ok, ticket, lots, fill, sl, pl …) oder
            # 409 copier_alt (kein frischer Status → kein Auftrag, damit nichts liegen
            # bleibt) / 200 copier_stumm (Auftrag liegt, keine Quittung in der Zeit —
            # bei open retry_ok:false, die Order KANN raus sein; das Frontend fragt
            # dann mit derselben cmd_id nach: {aktion:'ergebnis', cmd_id}).
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": f"ungueltige Daten: {e}"}))
            aktion = str(body.get("aktion") or "").strip().lower()
            erg_pfad = os.path.join(HERE, "hedge_solo_ergebnis.json")
            if aktion == "ergebnis":
                cid = str(body.get("cmd_id") or "")[:64]
                alle = read_json(erg_pfad, {}) or {}
                e = alle.get(cid) if cid else None
                return self._send(200, json.dumps(e or {"ok": False, "code": "offen", "retry_ok": False,
                    "msg": "noch keine Quittung vom Copier"}, ensure_ascii=False))
            if aktion == "bereit":
                # Start steht bevor (z. B. geplanter Winning Day in den naechsten Minuten): Copier-Update-
                # Neustart so lange vertagen. {aktion:'bereit', sekunden (Standard 180, max. 900), grund?}
                bis = hedge_bereit_setzen(body.get("sekunden") if body.get("sekunden") is not None else 180,
                                          str(body.get("grund") or "frontend")[:60])
                return self._send(200, json.dumps({"ok": True, "bis": bis, "rest_s": round(bis - time.time(), 1)}))
            if aktion not in ("open", "close", "level"):
                return self._send(400, json.dumps({"ok": False, "code": "befehl",
                    "msg": "aktion muss open/close/level/ergebnis/bereit sein"}, ensure_ascii=False))
            auftrag = {"cmd_id": f"{int(time.time())}-{random.randrange(10**6):06d}", "at": time.time(), "aktion": aktion}
            if aktion == "open":
                richtung = str(body.get("richtung") or "").strip().lower()
                if richtung not in ("buy", "sell"):
                    return self._send(400, json.dumps({"ok": False, "code": "befehl",
                        "msg": "richtung muss buy/sell sein (Richtung der Hedge-Order)"}, ensure_ascii=False))
                symbol = str(body.get("symbol") or "NAS100").strip()
                if not SYMBOL_RE.fullmatch(symbol):
                    return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "Symbol ungueltig"}))
                try:
                    eur = float(body.get("eur") or 0)
                    # tp_punkte = Distanz Master-TP (Pflicht), sl_punkte = Distanz Master-SL (optional);
                    # 'punkte' bleibt als alter Name fuer tp_punkte (Frontend-Stand .469)
                    punkte = float(body.get("tp_punkte") or body.get("punkte") or 0)
                    sl_punkte = float(body.get("sl_punkte") or 0)
                    lots = float(body.get("lots") or 0)
                except (TypeError, ValueError):
                    return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "eur/tp_punkte/sl_punkte/lots keine Zahlen"}))
                if not (lots > 0 or (eur > 0 and punkte > 0)):
                    return self._send(400, json.dumps({"ok": False, "code": "befehl",
                        "msg": "eur + tp_punkte (oder lots) muessen > 0 sein"}, ensure_ascii=False))
                if sl_punkte < 0:
                    return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "sl_punkte darf nicht negativ sein"}))
                if lots > 50:
                    return self._send(400, json.dumps({"ok": False, "code": "befehl",
                        "msg": f"lots {lots} ueber dem Riegel 50 — Rechenfehler?"}, ensure_ascii=False))
                try:
                    puffer = max(0.0, min(100.0, float(body.get("puffer") if body.get("puffer") is not None else 3)))
                except (TypeError, ValueError):
                    puffer = 3.0
                # Notfall-Faktor (25.09.2026, Finn: „im Notfall ein Stop-Loss bei 110 % vom Master-Take-Profit"):
                # SL am Hedge = fill ± tp_punkte × faktor; erlaubt 1,0–2,0, Standard 1,10, sonst 400
                try:
                    notfall_faktor = float(body.get("notfall_faktor") if body.get("notfall_faktor") is not None else 1.10)
                except (TypeError, ValueError):
                    return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "notfall_faktor keine Zahl"}))
                if not (1.0 <= notfall_faktor <= 2.0):
                    return self._send(400, json.dumps({"ok": False, "code": "befehl",
                        "msg": f"notfall_faktor {notfall_faktor} ausserhalb 1.0–2.0"}, ensure_ascii=False))
                auftrag.update({"richtung": richtung, "symbol": symbol, "eur": eur, "punkte": punkte, "tp_punkte": punkte,
                                "sl_punkte": sl_punkte, "puffer": puffer, "notfall_faktor": notfall_faktor, "lots": lots,
                                "plan_id": str(body.get("plan_id") or "")[:64]})
            elif aktion == "level":
                # Level am offenen Solo-Hedge neu setzen (01.10.2026): absolute NAS100-Preise vom PC-Tab, gerechnet ab dem
                # echten TradingView-Fill/TP-Limit statt ab dem Fusion-Fill. {aktion:'level', ticket, sl (>0), tp (0 = keins)}
                try:
                    ticket = int(body.get("ticket") or 0)
                    sl = float(body.get("sl") or 0)
                    tp = float(body.get("tp") or 0)
                except (TypeError, ValueError):
                    return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "ticket/sl/tp keine Zahlen"}))
                if ticket <= 0 or not sl > 0 or tp < 0:
                    return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "ticket und sl > 0 noetig"}))
                auftrag.update({"ticket": ticket, "sl": sl, "tp": tp})
            else:
                try:
                    ticket = int(body.get("ticket") or 0)
                except (TypeError, ValueError):
                    ticket = 0
                if ticket <= 0:
                    return self._send(400, json.dumps({"ok": False, "code": "befehl", "msg": "ticket fehlt"}))
                auftrag.update({"ticket": ticket, "grund": str(body.get("grund") or "")[:40]})
            # Riegel: laeuft ein Copier mit frischem Status? Sonst bliebe der Auftrag liegen
            # (und wuerde nach 40 s verfallen) — lieber sofort ehrlich absagen.
            frisch = False
            for inst in instances():
                st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
                try:
                    age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
                except (ValueError, TypeError):
                    age = None
                if st.get("running") and age is not None and age <= 15:
                    frisch = True
                    break
            if not frisch:
                return self._send(409, json.dumps({"ok": False, "code": "copier_alt", "retry_ok": True,
                    "msg": "Der Copier auf diesem PC liefert keinen frischen Status — ohne laufenden Copier "
                           "kann nichts auf Fusion gesendet werden (Copier-Karte pruefen)."}, ensure_ascii=False))
            pfad = os.path.join(HERE, "hedge_solo_auftrag.json")
            with HEDGE_SOLO_LOCK:
                liste = read_json(pfad, []) or []
                if not isinstance(liste, list):
                    liste = []
                # alte Auftraege (> 5 min) aus der Datei raeumen, sonst waechst sie ewig
                liste = [a for a in liste if isinstance(a, dict) and (time.time() - float(a.get("at") or 0)) < 300]
                liste.append(auftrag)
                tmp = pfad + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(liste, f, ensure_ascii=False, indent=1)
                os.replace(tmp, pfad)
            print(f"[panel] hedge-solo {aktion} {auftrag['cmd_id']}: "
                  + (f"{auftrag.get('richtung')} {auftrag.get('eur')} € / {auftrag.get('punkte')} Pkt {auftrag.get('symbol')}"
                     if aktion == "open" else f"Ticket {auftrag.get('ticket')} ({auftrag.get('grund')})"), flush=True)
            ende = time.time() + 14.0
            erg = None
            while time.time() < ende:
                time.sleep(0.05)   # 01.10.2026: 0,3 → 0,05 s — die Quittung des Copiers (Ticket, Fill) kommt so ~0,25 s früher beim Tab an
                alle = read_json(erg_pfad, {}) or {}
                if isinstance(alle, dict) and auftrag["cmd_id"] in alle:
                    erg = alle[auftrag["cmd_id"]]
                    break
            if erg is None:
                erg = {"ok": False, "code": "copier_stumm", "cmd_id": auftrag["cmd_id"],
                       "retry_ok": aktion == "close",
                       "msg": "Auftrag liegt, aber der Copier hat in 14 s nicht quittiert — "
                              + ("die Order KANN raus sein: mit cmd_id nachfragen, nie blind wiederholen." if aktion == "open"
                                 else "spaeter erneut schliessen.")}
            print(f"[panel] hedge-solo {aktion} {auftrag['cmd_id']} -> {'OK' if erg.get('ok') else 'FEHLER'} "
                  f"[{erg.get('code') or ''}] {str(erg.get('msg') or '')[:160]}", flush=True)
            erg = hedge_solo_zeiten(erg, self.headers.get("X-Prophos-Proxy-Ms"), getattr(self, "_t_ein", None), time.time())
            try:   # SCHARF SCHALTEN / LÖSEN (02.11.2026, s. SCHLIESSEN AUF DEM PC)
                if aktion == "open" and erg.get("ok") and erg.get("ticket"):
                    try:
                        _rs = _scharf_stand_lesen() if (isinstance(body.get("scharf"), dict) and body["scharf"].get("quelle") != "tsx") else None
                    except Exception:
                        _rs = None
                    erg["scharf"] = scharf_setzen(body.get("scharf"), auftrag.get("plan_id"), erg.get("ticket"), _rs)
                elif aktion == "close" and (erg.get("ok") or erg.get("schon_zu")):
                    scharf_loesen(auftrag.get("ticket"), f"Close vom Tab ({auftrag.get('grund') or '-'})")
            except Exception as e:
                print(f"[scharf] {aktion}: {type(e).__name__}: {e}", flush=True)
            return self._send(200, json.dumps(erg, ensure_ascii=False))

        if u.path == "/api/start-hedge-terminal":
            # Slave-/Hedge-Terminal per Knopf starten (01.09.2026, Finns Wunsch:
            # "falls ich es mal aus Versehen schliesse"). Braucht keinen file-
            # Parameter — das Hedge-Terminal ist eine Pro-PC-Sache, check_fleet
            # erzwingt ohnehin denselben Pfad in allen Configs. Pfad kommt
            # AUSSCHLIESSLICH aus der Config (nicht ueber die API setzbar).
            # Kein Login-Zwang wie bei start_terminal: der Login ist im Hedge-
            # Terminal gespeichert (derselbe Weg wie der Copier-Autostart), und
            # der Copier prueft hedge_expected_login beim Verbinden selbst hart.
            hpath = str(base_config().get("hedge_terminal_path") or "").strip()
            if not hpath:
                return self._send(200, json.dumps({"ok": False, "msg":
                    "hedge_terminal_path ist in der Config nicht gesetzt"}, ensure_ascii=False))
            if os.path.basename(hpath).lower() != "terminal64.exe":
                return self._send(200, json.dumps({"ok": False, "msg":
                    "hedge_terminal_path muss auf eine terminal64.exe zeigen"}, ensure_ascii=False))
            if not os.path.exists(hpath):
                return self._send(200, json.dumps({"ok": False, "msg":
                    f"nicht gefunden: {hpath}"}, ensure_ascii=False))
            install_dir = os.path.dirname(os.path.abspath(hpath))
            pids = provision.terminal_pids(install_dir)
            if pids:
                # Zweiter Start derselben Installation waere ein frisches Fenster
                # mit Login-Dialog (Fund 14.08.2026) — laeuft es, nur nach vorn
                # holen. Prozess OHNE Fenster ist ein Zombie (Muster
                # start_terminal, 18.08.2026): beenden und unten kalt starten.
                if _fenster_nach_vorn(pids[0]):
                    print(f"[panel] Hedge-Terminal laeuft (PID {pids[0]}) — Fenster nach vorn.", flush=True)
                    return self._send(200, json.dumps({"ok": True, "msg":
                        "Slave-Terminal läuft schon — Fenster ist vorn"}, ensure_ascii=False))
                print("[panel] Hedge-Terminal-Prozess ohne Fenster (Zombie) — beende und starte kalt neu.", flush=True)
                for pid in provision.terminal_pids(install_dir):
                    provision._taskkill(pid, grace_s=5)
            _update_abwarten(install_dir)  # stilles MT5-Update gerade dran? (01.10.2026)
            try:   # MU1 (10.11.2026): älteren Build still angleichen, bevor MT5 per UAC einspielen will — verhindert den Start nie
                _st, _txt = build_angleichen(install_dir, schnell=True)   # synchroner HTTP-Weg (20 s) → nie warten
                if _st in ("angeglichen", "fehler"):
                    print(f"[mt5-build] Hedge: {_txt}", flush=True)
            except Exception:
                pass
            subprocess.Popen([hpath], cwd=install_dir)
            _front_when_up(install_dir)
            print(f"[panel] Hedge-Terminal gestartet: {hpath}", flush=True)
            return self._send(200, json.dumps({"ok": True, "msg":
                "Slave-Terminal gestartet — Login ist gespeichert, das Fenster kommt gleich nach vorn"},
                ensure_ascii=False))

        if u.path == "/api/close-idle-terminals":
            # „Terminals ohne Trade schliessen" (03.09.2026, Finns Wunsch: die
            # Master-Terminals laufen sonst 24/7 weiter, obwohl die Doktrin seit
            # 25.08. 'Terminal nur im Trade offen' heisst). Flotten-Endpoint ohne
            # file-Parameter — geprueft wird jede Instanz einzeln, geschlossen
            # nur mit frischem Status-Beweis (terminal_schliessbar). Die Kills
            # laufen im Hintergrund: bei mehreren Terminals wuerde das hoefliche
            # WM_CLOSE (5 s Grace je PID) sonst den 25-s-Proxy-Timeout von
            # app.py reissen. Die Antwort nennt die ENTSCHEIDUNG je Instanz;
            # das tatsaechliche Zu folgt binnen Sekunden (naechster Poll zeigt's).
            plans_akt = {}
            with PLANS_LOCK:
                for p in _load_plans():
                    if p["status"] in ("geplant", "laufend"):
                        plans_akt[p["file"]] = p["status"]
            geschlossen, uebersprungen, bereits_zu, zu_killen = [], [], [], []
            for i in instances():
                cfg = read_json(os.path.join(HERE, i["config_file"]), {}) or {}
                if not str(cfg.get("master_terminal_path") or "").strip():
                    continue  # Orbit/TV-Instanzen: kein Master-Terminal
                anzeige = cfg.get("display_name") or i["name"]
                install_dir = os.path.dirname(os.path.abspath(str(cfg["master_terminal_path"])))
                if not provision.terminal_pids(install_dir):
                    bereits_zu.append(anzeige)
                    continue
                st = read_json(os.path.join(HERE, i["status_file"]), {}) or {}
                age = None
                try:
                    age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
                except (ValueError, TypeError):
                    pass
                ok, grund = terminal_schliessbar(cfg, st, age, plans_akt.get(i["config_file"]))
                if ok:   # PL1: läuft gerade ein Bot-Lauf, gleich hier als übersprungen melden (der Killer prüft beim Schließen noch einmal)
                    _r = terminal_zu_order_riegel(i["config_file"], MASTER_ORDER_LOCKS, ORDER_ANGEMELDET, DEALS_LESEN | VORFLUG_LESEN,
                                                  time.time(), ORDER_ANGEMELDET_S)
                    if _r:
                        ok, grund = False, _r
                if ok:
                    geschlossen.append(anzeige)
                    zu_killen.append((i["config_file"], install_dir))
                else:
                    uebersprungen.append({"name": anzeige, "grund": grund})
            if zu_killen:
                def _killer(kandidaten=zu_killen):
                    for kf, kdir in kandidaten:
                        try:
                            zu_ok, _n, grund_r = _terminal_kill_riegel(kf, kdir)   # PL1
                            print(f"[panel] {kf}: " + ("Master-Terminal geschlossen (Knopf)." if zu_ok else f"Terminal bleibt offen (Knopf) — {grund_r}."),
                                  flush=True)
                        except Exception as e:
                            print(f"[panel] {kf}: Terminal-Zu-Fehler: {type(e).__name__}: {e}", flush=True)
                threading.Thread(target=_killer, daemon=True).start()
            print(f"[panel] Terminals ohne Trade schliessen: {len(geschlossen)} zu, "
                  f"{len(uebersprungen)} uebersprungen, {len(bereits_zu)} schon zu.", flush=True)
            return self._send(200, json.dumps({"ok": True, "geschlossen": geschlossen,
                "bereits_zu": bereits_zu, "uebersprungen": uebersprungen}, ensure_ascii=False))

        fname = (parse_qs(u.query).get("file") or [""])[0]
        inst = next((i for i in instances() if i["config_file"] == fname), None)
        if not inst:
            return self._send(404, json.dumps({"ok": False, "msg": f"Instanz '{fname}' unbekannt"}))

        if u.path in ("/api/master-order", "/api/master-close") and inst:
            if inst["config_file"] in VORFLUG_LESEN:
                _vorflug_abwarten(inst["config_file"])   # F-A (Prüfer M1): vor allen Riegeln beider Routen auf einen laufenden Vorflug warten
            with MASTER_ORDER_GUARD:   # Hinweis S1: anmelden — ein Vorflug, der jetzt käme, nähme sonst den Lock zwischen Riegeln und acquire (→ 409)
                ORDER_ANGEMELDET[inst["config_file"]] = time.time()
        if u.path == "/api/master-order":
            # Order-Bot (15.08.2026, Finns Ansage): platziert die Master-Order als
            # kurzlebiger Subprozess. WICHTIG (Korrektur 28.08.2026, Detection-
            # Audit): der Bot handelt AUSSCHLIESSLICH ueber die Terminal-UI
            # (F9-Dialog, echte Tastatur-/SendInput-Events) — die MetaTrader5-API
            # wird nur LESEND benutzt, ein order_send Richtung Master existiert im
            # Bot NICHT (order_bot.py Docstring Z. 24, TRADE_ACTION_SLTP am 18.08.
            # geloescht). Dadurch kommt die Order beim Broker mit Reason=CLIENT an,
            # wie von Hand. Kommt NUR nach gruenem Trade-Start-Check aus dem
            # Preflight — hier trotzdem eigene Riegel: Copier muss frische Daten
            # liefern (sonst bliebe die Order UNGEHEDGET), und der Bot selbst
            # prueft den Login nochmal vor dem Klick.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            # Echo pausiert? (28.08.2026, Not-Aus) — gar keinen neuen Bot starten.
            # retry_ok=True und ein maschinenlesbares 'grund' (30.08.2026, Finns
            # Fund am PC): hier ist BEWEISBAR nichts gesendet worden, der Aufruf
            # endet vor dem Bot-Start. Ohne retry_ok las das Frontend die Absage
            # als "unklar" und warnte "erst im Master-Terminal pruefen, ob die
            # Order liegt" — eine Falschaussage, die genau die Vorsicht abstumpft,
            # die sie erzeugen soll. 'grund' gibt es, damit das Frontend den Fall
            # nicht am Meldungstext erkennen muss (Textvergleiche brechen still,
            # sobald jemand die Formulierung anfasst).
            if os.path.exists(os.path.join(HERE, "echo_pause.flag")):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                    "grund": "echo_pausiert", "msg":
                    "Echo ist pausiert — es wird keine neue Order platziert. Erst oben "
                    "auf Fortsetzen klicken."}, ensure_ascii=False))
            cmd = {"symbol": str(body.get("symbol") or "").strip(),
                   "richtung": str(body.get("richtung") or "").lower(),
                   "volumen": body.get("volumen"),
                   "sl_usd": body.get("sl_usd"), "tp_usd": body.get("tp_usd")}
            if not SYMBOL_RE.fullmatch(cmd["symbol"] or ""):
                return self._send(400, json.dumps({"ok": False, "msg": "Symbol ungueltig"}))
            # HARTE LINIE AUCH FUER ECHO (30.10.2026, Finn: „auf gar keinen Fall ein interner Hedge"; Audit Slave 1: Echo von Hand am PC
            # hatte keine DB-Linie, nur die Pruefung im Tab): vor JEDEM Bot-Start fragt das Panel Railway/DB selbst (richtung_frei ->
            # prophos_gegenrichtung_frei), wie /api/tv-konto. FAIL-CLOSED: ohne Plan-UUID (alter Tab), ohne Richtung, ohne Token, ohne
            # Netz oder bei unklarer Antwort = gesperrt, beweisbar nichts gesendet (retry_ok=True). big_trade_nah/_unklar sind die
            # Heim-Regel des Puls-Chrome (TradingView/TopstepX) — Railway prueft sie erst, wenn die Gegenrichtung frei ist; fuer eine
            # MT5-Order gelten sie nicht.
            _pid = str(body.get("plan_id") or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f-]{36}", _pid) or cmd["richtung"] not in ("buy", "sell"):
                print(f"[panel] {fname}: master-order RIEGEL ohne plan_id/richtung -> gesperrt", flush=True)
                return self._send(200, json.dumps({"ok": False, "retry_ok": True, "gesendet": False, "grund": "riegel_unerreichbar",
                    "code": "riegel_unerreichbar", "msg": "Richtungs-Riegel nicht pruefbar: die Order kam ohne Plan-ID/Richtung (alter Prophos-"
                    "Tab?) — den Prophos-Tab an diesem PC neu laden. Nichts gesendet."}, ensure_ascii=False))
            _frei, _msg, _code = richtung_frei(_pid, cmd["richtung"])
            if not _frei and _code in ("gegenrichtung", "riegel_unerreichbar"):
                print(f"[panel] {fname}: master-order RIEGEL {_code} {cmd['richtung']}: {_msg[:160]}", flush=True)
                return self._send(200, json.dumps({"ok": False, "retry_ok": True, "gesendet": False, "grund": _code, "code": _code,
                                                   "msg": _msg + ("" if "Nichts gesendet" in _msg or "nichts gesendet" in _msg else " Nichts gesendet.")},
                                                  ensure_ascii=False))
            # ECHO V2 (23.09.2026, Finn: "nichts gegengehedgt, kein Multiplikator, gar nichts"): ohne_hedge
            # heisst, der Copier SOLL nicht mitlaufen — der Frische-Riegel unten (schuetzt die Order vor einem
            # ungehedgten Markt) ist hier verkehrt. Stattdessen zwei eigene Riegel, beide beweisbar VOR dem
            # Bot-Start (retry_ok=True): (1) kein offenes Echo-Fenster dieser Instanz (plans.json 'laufend'
            # bzw. 'geplant' < 6 h — sonst wuerde ein laufender Copier die Order doch kopieren), (2) keine
            # laufende EA-Selbstheilung fuer dieses Terminal (die killt und startet das Terminal neu — mitten
            # im Order-Dialog waere das ein UNKLAR). Der Bot selbst bleibt unveraendert (Login-Guard, Klick).
            ohne_hedge = bool(body.get("ohne_hedge"))
            # an den Bot (21.10.2026): nur ein FINALER Trade zieht nach dem Fill exakt nach (order_bot nachzieh_seiten; Echo mit Hedge seit JU1 nur TP) —
            # final = 'pass' | 'blow' | 'beide' | 'gewinntag' | None aus dem PC-Tab (echoV2Final), final_grund nur für die Spur.
            # JU1 (Finn 05.11.2026, Weg A): Echo mit Hedge bekommt nur die TP-Seite (pass/beide/gewinntag, der Bot macht daraus nachzieh_cmd),
            # nie 'blow' und nie die Tagesgrenze (31.10.2026 unverändert)
            cmd["ohne_hedge"] = ohne_hedge
            _fin = str(body.get("final") or "").strip().lower()
            cmd["final"] = _fin if _fin in (("pass", "blow", "beide", "gewinntag") if ohne_hedge else ("pass", "beide", "gewinntag")) else None
            cmd["final_grund"] = str(body.get("final_grund") or "").strip()[:160] if (ohne_hedge or cmd["final"]) else ""
            # SCHARF-BEWEIS IM BOT (ES2/ES3-Zusatz 05.11.2026, order_bot echo_scharf_urteil): nur Echo mit Hedge; true nur ausdrücklich (bool),
            # scharf_max_s kappt der Bot selbst (5–60 s). Ohne Feld (alter Tab) prüft wie bisher der Tab vor dem Senden.
            if not ohne_hedge and body.get("scharf_pflicht") is True:
                # FÄHIGKEIT BEIM SENDEN (ES2d-Gegenprüfung 05.11.2026): der Tab hat bot_faehig beim instances-Takt gelesen — wurde order_bot.py
                # seitdem gegen einen Stand ohne Scharf-Beweis getauscht (ensure_bot_source, Rückbau auf main), ignorierte der Bot das Feld still
                # → ungehedgt. Deshalb hier noch einmal: ohne Fähigkeit nichts starten, Antwort nicht_scharf (retry_ok, nichts gesendet)
                if "scharf_pflicht" not in bot_faehig():
                    return self._send(200, json.dumps({"ok": False, "retry_ok": True, "gesendet": False, "grund": "nicht_scharf", "code": "nicht_scharf",
                                                       "msg": "Bot an diesem PC kann den Scharf-Beweis nicht (order_bot.py ohne ES3b) — nichts gesendet. "
                                                              "→ Tab neu laden lassen, dann prüft der Tab das Trade-Fenster wieder selbst."},
                                                      ensure_ascii=False))
                cmd["scharf_pflicht"] = True
                cmd["scharf_max_s"] = body.get("scharf_max_s")
            # Tagesgrenze-Rest in $ ohne Puffer (26.10.2026, Vertrag Teil B, Auto-Planer ap_tagesgrenze): nur Echo V2, Zahl ≥ 0 oder None —
            # None = keine Prüfung; der Bot zieht den SL am echten Fill nach, wenn er die Grenze reißen würde
            try:
                _tg = float(body.get("tages_grenze_usd")) if body.get("tages_grenze_usd") not in (None, "") else None
            except (TypeError, ValueError):
                _tg = None
            cmd["tages_grenze_usd"] = _tg if ohne_hedge and _tg is not None and _tg >= 0 else None
            if ohne_hedge:
                fenster = _echo_fenster_offen(inst["config_file"])
                if fenster:
                    return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                        "grund": "echo_fenster_offen", "msg":
                        f"Echo-Fenster fuer diese Instanz ist offen (Plan '{fenster}') — der Copier "
                        "wuerde die Order hedgen. Erst den Echo-Trade beenden."}, ensure_ascii=False))
                cfg_v2 = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
                tpath = str(cfg_v2.get("master_terminal_path") or "").strip()
                inst_dir = os.path.dirname(os.path.abspath(tpath)) if tpath else ""
                with HEAL_LOCK:
                    heilt = bool(inst_dir) and inst_dir in HEAL_ACTIVE
                if heilt:
                    return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                        "grund": "terminal_heilt", "msg":
                        "Terminal wird gerade geprueft (EA-Selbstheilung laeuft) — gleich erneut."},
                        ensure_ascii=False))
            st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
            age = None
            try:
                age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
            except (ValueError, TypeError):
                pass
            if not ohne_hedge and not (st.get("running") and age is not None and age <= 15):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                    "grund": "copier_alt", "msg":
                    "Copier liefert keine frischen Daten — die Order wuerde UNGEHEDGET "
                    "bleiben. Erst den Trade-Start-Check gruen bekommen."}, ensure_ascii=False))
            if _instanz_heilt(inst):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True, "grund": "terminal_heilt", "msg":
                    "Terminal wird gerade geheilt (EA-Selbstheilung, nichts gesendet) — gleich erneut."}, ensure_ascii=False))
            with MASTER_ORDER_GUARD:
                lock = MASTER_ORDER_LOCKS.setdefault(inst["config_file"], threading.Lock())
            if not lock.acquire(blocking=False):
                # N2 (04.11.2026): nur eine Deal-Lesung hält den Lock — beweisbar nichts gesendet; F-A (Prüfer S2, 11.11.2026): ebenso ein Konto-Vorflug
                if inst["config_file"] in (DEALS_LESEN | VORFLUG_LESEN):
                    return self._send(409, json.dumps({"ok": False, "retry_ok": True, "grund": "deals_lesen", "msg":
                        "Lese-Lauf (Deal-Historie) auf dieser Instanz — nichts gesendet, gleich erneut."}, ensure_ascii=False))
                if inst["config_file"] in TERMINAL_ZU_HAELT:   # PL1: Terminal-Zu hält den Lock (Sekunden) — nichts gesendet, gleich erneut
                    return self._send(409, json.dumps({"ok": False, "retry_ok": True, "grund": "terminal_zu", "msg":
                        "Master-Terminal wird gerade geschlossen (kein Trade) — nichts gesendet, gleich erneut."}, ensure_ascii=False))
                return self._send(409, json.dumps({"ok": False, "retry_ok": False, "msg":
                    "Fuer diese Instanz laeuft gerade schon eine Order — warten, "
                    "dann im Terminal pruefen."}, ensure_ascii=False))
            # HEDGE WÄRE 0 LOT (EH2 12.11.2026, Befund S2 zu EH1): nur Echo mit Hedge — rechnet der Copier für diese Order mit der Formel aus
            # plan_actions/norm_vol 0 Lot (Kontraktgröße Master ≫ Fusion-Raster, falsches Preset), bliebe die Order ungehedgt: KEIN Klick, retry_ok False.
            # Fehlt eine Angabe (Master-Kontraktgröße nicht lesbar, Copier-Status ohne hedge_sym, kein Mapping), bleibt es wie bisher — nur Log.
            if not ohne_hedge:
                try:
                    _cfg_h = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
                    _hsym = str((_cfg_h.get("symbol_map") or {}).get(cmd["symbol"]) or "")
                    _hs = ((st.get("hedge_sym") or {}) if isinstance(st.get("hedge_sym"), dict) else {}).get(_hsym) if _hsym else None
                    _mcs = _master_contract_size_live(_cfg_h, cmd["symbol"]) if _hs else None
                    _gesp, _txt, _v = hedge_null_urteil(cmd["volumen"], _cfg_h.get("multiplier"), _mcs, _hs)
                except Exception as e:
                    _gesp, _txt, _v = None, f"{type(e).__name__}: {e}", None
                if _gesp is True:
                    lock.release()
                    print(f"[panel] {fname}: master-order RIEGEL hedge_null {cmd['symbol']} {cmd['volumen']}: {_txt[:200]}", flush=True)
                    return self._send(200, json.dumps({"ok": False, "retry_ok": False, "gesendet": False, "grund": "hedge_null", "code": "hedge_null",
                                                       "msg": _txt}, ensure_ascii=False))
                if _gesp is None:
                    print(f"[panel] {fname}: master-order Hedge-0-Prüfung nicht möglich ({cmd['symbol']} → {_hsym or 'kein Mapping'}): {_txt}", flush=True)
            bot = os.path.join(HERE, "order_bot.py")
            if not os.path.exists(bot):
                # Nachladen statt raten (15.08.2026): die Datei fehlt auf PCs,
                # deren Panel vor ihr installiert wurde.
                ensure_bot_source()
            if not os.path.exists(bot):
                lock.release()
                return self._send(200, json.dumps({"ok": False, "retry_ok": True, "msg":
                    "order_bot.py fehlt auf diesem PC und Download schlug fehl — "
                    "einmal 'Alles neu starten' klicken, dann erneut."}, ensure_ascii=False))
            try:
                # 300s statt 45s (18.08.2026, Finns Lauf: der SL/TP-Zeilen-Scan
                # wurde nach 45s mitten in der Suche abgewuergt — die Position
                # lag dann OHNE Stop im Markt, ohne dass die Meldung die Werte
                # nannte). 300s deckt den schlimmsten Scan locker; die Bremse
                # bleibt, weil an diesem Aufruf das Lock fuer ALLE Trade-Starts
                # haengt — ein wirklich haengender Bot darf es nicht ewig halten.
                p = subprocess.run([*bot_argv(bot), os.path.join(HERE, inst["config_file"]),
                                    json.dumps(cmd)],
                                   capture_output=True, text=True, errors="replace", timeout=300)
                line = (p.stdout or "").strip().splitlines()
                # Stumme Bots sind Diagnose-Killer: stderr-Ende mitgeben (z.B.
                # Traceback/ImportError), sonst bleibt der Fehler anonym.
                res = json.loads(line[-1]) if line else {
                    "ok": False, "retry_ok": False,
                    "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "retry_ok": False,
                       "msg": "Order-Bot Timeout (300s) — im Terminal pruefen, ob die "
                              "Order platziert wurde und ob SL/TP an der Position "
                              "haengen (sonst von Hand nachtragen)!"}
            except (OSError, ValueError) as e:
                res = {"ok": False, "retry_ok": False, "msg": f"Order-Bot-Start fehlgeschlagen: {e}"}
            finally:
                lock.release()
            print(f"[panel] {fname}: Master-Order{' (Echo V2, ohne Hedge)' if ohne_hedge else ''} "
                  f"{cmd['richtung']} {cmd['volumen']} "
                  f"{cmd['symbol']} -> {res.get('ok')} ({res.get('msg') or res.get('retcode')})", flush=True)
            # Stempel-Spur immer ins Log (02.09.2026, Finns '10 sec pro Step'):
            # bei Erfolg steht die Spur sonst NIRGENDS — genau dann braucht
            # man sie aber, um zu sehen, welche Station die Zeit gefressen hat.
            if res.get("trail"):
                print(f"[panel] {fname}: Spur: {res['trail']}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/master-close":
            # Remote-Close (28.08.2026, Finns Feature nach dem ersten Remote-
            # Erfolg): Position per Klick schliessen — gleicher Rahmen wie
            # master-order (Pause-Riegel, Frische-Riegel, EIN Lock pro Instanz,
            # 300s), nur der Befehl traegt aktion=close + ticket. Der Frische-
            # Riegel bleibt bewusst: ohne frischen Copier wuerde der Hedge das
            # Master-Close nicht mitgehen und bliebe allein offen.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            if os.path.exists(os.path.join(HERE, "echo_pause.flag")):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                    "grund": "echo_pausiert", "msg":
                    "Echo ist pausiert — es wird nichts geschlossen. Erst oben "
                    "auf Fortsetzen klicken."}, ensure_ascii=False))
            try:
                ticket = int(body.get("ticket") or 0)
            except (TypeError, ValueError):
                ticket = 0
            symbol = str(body.get("symbol") or "").strip()
            # MT1 Punkt 4 (11.11.2026): ohne Ticket (Copier-Schnappschuss ohne die Position) mit aufloesen + Symbol + Richtung — der Bot löst das Ticket
            # LESEND über die Terminal-API auf (Login-Guard, genau EINE Position); die Frische-Riegel unten bleiben unverändert
            richtung_c = str(body.get("richtung") or "").strip().lower()
            aufloesen_c = ticket <= 0 and body.get("aufloesen") is True and richtung_c in ("buy", "sell") and bool(symbol)
            if ticket <= 0 and not aufloesen_c:
                return self._send(400, json.dumps({"ok": False, "msg": "ticket fehlt"}))
            if symbol and not SYMBOL_RE.fullmatch(symbol):
                return self._send(400, json.dumps({"ok": False, "msg": "Symbol ungueltig"}))
            # ECHO V2 (24.09.2026, Vollumstieg 'Ohne Hedge' — Auto-Close 23:45–00:00 Dubai
            # muss auch V2-Positionen schliessen): ohne_hedge:true = es gibt keinen Hedge,
            # den der Copier mitgehen muesste — der Frische-Riegel unten waere hier verkehrt
            # (der Copier laeuft bei V2 oft gar nicht, das Close muss trotzdem raus). Derselbe
            # Bypass wie bei /api/master-order: statt Copier-Frische nur der Riegel gegen die
            # laufende EA-Selbstheilung (killt das Terminal mitten im Klick = UNKLAR). Der
            # Bot selbst (run_close) braucht keinen Copier: er liest die Position ueber die
            # Terminal-API (Login-Guard, Ticket, genau EINE offene Position) und klickt.
            ohne_hedge = bool(body.get("ohne_hedge"))
            if ohne_hedge:
                cfg_v2 = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
                tpath = str(cfg_v2.get("master_terminal_path") or "").strip()
                inst_dir = os.path.dirname(os.path.abspath(tpath)) if tpath else ""
                with HEAL_LOCK:
                    heilt = bool(inst_dir) and inst_dir in HEAL_ACTIVE
                if heilt:
                    return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                        "grund": "terminal_heilt", "msg":
                        "Terminal wird gerade geprueft (EA-Selbstheilung laeuft) — gleich erneut."},
                        ensure_ascii=False))
            st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
            age = None
            try:
                age = (datetime.now() - datetime.fromisoformat(st.get("updated_at") or "")).total_seconds()
            except (ValueError, TypeError):
                pass
            if not ohne_hedge and not (st.get("running") and age is not None and age <= 15):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True,
                    "grund": "copier_alt", "msg":
                    "Copier liefert keine frischen Daten — der Hedge wuerde das Close "
                    "nicht mitgehen und bliebe allein offen. Erst Copier gruen bekommen."},
                    ensure_ascii=False))
            if _instanz_heilt(inst):
                return self._send(409, json.dumps({"ok": False, "retry_ok": True, "grund": "terminal_heilt", "msg":
                    "Terminal wird gerade geheilt (EA-Selbstheilung, nichts gesendet) — gleich erneut."}, ensure_ascii=False))
            with MASTER_ORDER_GUARD:
                lock = MASTER_ORDER_LOCKS.setdefault(inst["config_file"], threading.Lock())
            if not lock.acquire(blocking=False):
                # N2 (Prüfer 04.11.2026): nur eine Deal-Lesung — nichts geklickt, gleich erneut; F-A (Prüfer S2, 11.11.2026): ebenso ein Konto-Vorflug
                if inst["config_file"] in (DEALS_LESEN | VORFLUG_LESEN):
                    return self._send(409, json.dumps({"ok": False, "retry_ok": True, "grund": "deals_lesen", "msg":
                        "Lese-Lauf (Deal-Historie) auf dieser Instanz — nichts geklickt, gleich erneut."}, ensure_ascii=False))
                if inst["config_file"] in TERMINAL_ZU_HAELT:   # PL1: Terminal-Zu hält den Lock (Sekunden) — nichts geklickt, gleich erneut
                    return self._send(409, json.dumps({"ok": False, "retry_ok": True, "grund": "terminal_zu", "msg":
                        "Master-Terminal wird gerade geschlossen (kein Trade) — nichts geklickt, gleich erneut."}, ensure_ascii=False))
                return self._send(409, json.dumps({"ok": False, "retry_ok": False, "msg":
                    "Fuer diese Instanz laeuft gerade schon ein Bot-Lauf — warten, "
                    "dann im Terminal pruefen."}, ensure_ascii=False))
            bot = os.path.join(HERE, "order_bot.py")
            if not os.path.exists(bot):
                ensure_bot_source()
            if not os.path.exists(bot):
                lock.release()
                return self._send(200, json.dumps({"ok": False, "retry_ok": True, "msg":
                    "order_bot.py fehlt auf diesem PC und Download schlug fehl — "
                    "einmal 'Alles neu starten' klicken, dann erneut."}, ensure_ascii=False))
            cmd = {"aktion": "close", "ticket": ticket, "symbol": symbol}
            if aufloesen_c:
                cmd.update(aufloesen=True, richtung=richtung_c)   # MT1 Punkt 4
            try:
                p = subprocess.run([*bot_argv(bot), os.path.join(HERE, inst["config_file"]),
                                    json.dumps(cmd)],
                                   capture_output=True, text=True, errors="replace", timeout=300)
                line = (p.stdout or "").strip().splitlines()
                res = json.loads(line[-1]) if line else {
                    "ok": False, "retry_ok": False,
                    "msg": "keine Antwort vom Bot: " + ((p.stderr or "").strip()[-200:] or "kein stderr")}
            except subprocess.TimeoutExpired:
                res = {"ok": False, "retry_ok": False,
                       "msg": "Close-Bot Timeout (300s) — im Terminal pruefen, ob die "
                              "Position noch offen ist!"}
            except (OSError, ValueError) as e:
                res = {"ok": False, "retry_ok": False, "msg": f"Close-Bot-Start fehlgeschlagen: {e}"}
            finally:
                lock.release()
            print(f"[panel] {fname}: Master-Close{' (Echo V2, ohne Hedge)' if ohne_hedge else ''} #{ticket} {symbol} "
                  f"-> {res.get('ok')} ({res.get('msg')})", flush=True)
            if res.get("trail"):
                print(f"[panel] {fname}: Spur: {res['trail']}", flush=True)
            return self._send(200, json.dumps(res, ensure_ascii=False))

        if u.path == "/api/start-terminal":
            # Optionale Zugangsdaten im Body (aus Prophos/Supabase): erzwingen den
            # richtigen Login beim Start. Nur komplett (login+password+server bzw.
            # Server aus der Config) macht der Zwang Sinn — sonst wie bisher nackt.
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except Exception:
                body = {}
            creds = {k: str(body.get(k) or "").strip() for k in ("login", "password", "server")}
            has_creds = bool(creds["login"] and creds["password"])
            ok, msg = start_terminal(inst["config_file"], creds if has_creds else None)
            print(f"[panel] {fname}: Terminal-Start → {msg}", flush=True)  # bewusst ohne Zugangsdaten
            return self._send(200, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))

        if u.path == "/api/delete":
            # Body eigenstaendig lesen: das body aus dem start-terminal-Zweig
            # darueber existiert hier NICHT (der Zweig kehrt zurueck). Ohne
            # diese Zeilen waere force ein NameError zur Laufzeit.
            try:
                _n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(_n) or b"{}") if _n else {}
            except Exception:
                body = {}
            # Config loeschen (15.08.2026, Etappe 3). Geloescht werden AUSSCHLIESSLICH
            # die aus dem instances()-Lookup abgeleiteten Pfade — nie der rohe
            # Query-Wert. Vier Verweigerungsgruende (409), weil eine geloeschte
            # Config den GANZEN Copier-Prozess neu startet und der Neustart keine
            # offenen Positionen blind stellen darf:
            data = _instances_snapshot()
            target = next((d for d in data if d["file"] == inst["config_file"]), None)
            st = (target or {}).get("status") or {}
            fresh = bool((target or {}).get("alive"))
            # (a) Instanz frisch und mitten im Geschehen — offene Master-Positionen
            #     oder Hedges wuerden beim Neustart als Alt-Bestand uebersprungen.
            #     ABER: bei eingefrorenem Snapshot (note gesetzt) ist die
            #     master_positions-Liste ALT und kein Beweis (19.08.2026, Finns
            #     Fund: '1 Position' von gestern blockierte das Loeschen). Dann
            #     zaehlt nur der LIVE-Blick ins laufende Master-Terminal — und
            #     nur eine beweisbare 0 ohne Hedges laesst durch.
            if fresh and ((st.get("master_positions") or []) or (st.get("hedges") or {})):
                beweisbar_flach = False
                if st.get("note") and not (st.get("hedges") or {}):
                    cfg_del = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
                    mpath = str(cfg_del.get("master_terminal_path") or "").strip()
                    if mpath and provision.terminal_pids(os.path.dirname(os.path.abspath(mpath))):
                        beweisbar_flach = _master_positionen_live(cfg_del) == 0
                if not beweisbar_flach:
                    return self._send(409, json.dumps({"ok": False, "msg":
                        "Instanz hat offene Positionen oder Hedges — erst flach werden, "
                        "dann loeschen. (Snapshot eingefroren? Master-Terminal oeffnen — "
                        "dann prueft der Riegel LIVE und laesst bei 0 Positionen durch.)"},
                        ensure_ascii=False))
            # (b) Ziel-Status NICHT frisch, aber irgendein Copier-Prozess schreibt
            #     frische Status-Dateien ('unbekannt != leer': wir koennen nicht
            #     beweisen, dass niemand diese Config bedient — gleiches
            #     Frische-Muster wie der Doppelstart-Schutz in copier.py).
            if not fresh and any(d.get("alive") for d in data):
                return self._send(409, json.dumps({"ok": False, "msg":
                    "Status dieser Instanz ist nicht frisch, aber ein Copier-Prozess "
                    "laeuft — Zustand unklar, nicht geloescht ('unbekannt != leer')."},
                    ensure_ascii=False))
            # (b2) Alle Status stale, aber die PID aus einer Status-Datei lebt noch
            #      (Review-Fund 15.08.2026): bei Hedge-Terminal-Ausfall schreibt die
            #      Hauptschleife GAR keinen Status mehr (book is None -> continue),
            #      der Prozess haelt aber offene Hedges. Frische allein reicht als
            #      Beweis also nicht — die PID muss tot sein.
            if not fresh:
                for d in data:
                    pid = (d.get("status") or {}).get("pid")
                    if pid and _pid_alive(pid):
                        return self._send(409, json.dumps({"ok": False, "msg":
                            f"Copier-Prozess (PID {pid}) lebt noch, schreibt aber keinen "
                            f"frischen Status (Terminal-Ausfall/Startphase?) — Zustand "
                            f"unklar, nicht geloescht ('unbekannt != leer')."},
                            ensure_ascii=False))
            # (c) Ein LAUFENDER Plan haengt an der file.
            with PLANS_LOCK:
                plans = _load_plans()
            if any(p["file"] == inst["config_file"] and p["status"] == "laufend" for p in plans):
                return self._send(409, json.dumps({"ok": False, "msg":
                    "Auf dieser Instanz laeuft ein Trade-Plan — erst beenden, dann "
                    "loeschen."}, ensure_ascii=False))
            # (d) Irgendeine ANDERE Instanz ist busy — die Loeschung restartet den
            #     ganzen Copier-Prozess, und der Neustart darf keine fremden
            #     offenen Positionen blind stellen.
            # UEBERSTIMMBAR seit 31.08.2026 (Finns Ansage "dass ich immer den acc
            # loeschen kann"): der Riegel bleibt der Normalfall, aber er ist
            # kein Naturgesetz -- eine tote Testinstanz muss loeschbar sein,
            # auch wenn nebenan etwas offen ist. Mit force=true wird nur der
            # ZWEITE Riegel uebergangen; die drei davor (eigene Positionen,
            # unklarer Status, laufender Trade-Plan) bleiben hart, weil die die
            # zu loeschende Instanz SELBST betreffen. Das Frontend fragt vorher
            # mit der ganzen Konsequenz im Klartext nach.
            if not bool(body.get("force")):
                for d in data:
                    if d["file"] == inst["config_file"]:
                        continue
                    s2 = d.get("status") or {}
                    if d.get("alive") and ((s2.get("master_positions") or []) or (s2.get("hedges") or {})):
                        return self._send(409, json.dumps({"ok": False,
                            "erzwingbar": True,
                            "msg": f"Andere Instanz ({d['file']}) hat gerade offene "
                                   f"Positionen/Hedges — Loeschen startet den ganzen "
                                   f"Copier neu."}, ensure_ascii=False))
            # Master-Terminal-Ordner JETZT merken — nach os.remove ist die Config
            # weg (07.09.2026, Archiv-Loeschauftrag: das Terminal soll mit zu,
            # sonst laeuft die terminal64.exe nach der Loeschung kopflos weiter).
            cfg_weg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
            # Loeschen: ZUERST die Config — schlaegt das fehl (Windows: Datei
            # gerade von copier.py/instances() offen, kein FILE_SHARE_DELETE),
            # wird ABGEBROCHEN statt Erfolg zu melden (Review-Fund 15.08.2026:
            # sonst waeren Status+Sidecar weg, die Config aber wieder da).
            # Status + closed-Sidecar erst NACH erfolgreicher Config-Loeschung.
            closed_file = re.sub(r"^config", "closed", inst["config_file"], count=1, flags=re.I)
            try:
                os.remove(os.path.join(HERE, inst["config_file"]))
            except OSError as e:
                return self._send(409, json.dumps({"ok": False, "msg":
                    f"Config gerade in Benutzung ({type(e).__name__}) — kurz warten "
                    f"und nochmal versuchen."}, ensure_ascii=False))
            removed = [inst["config_file"]]
            for fn in (inst["status_file"], closed_file):
                try:
                    os.remove(os.path.join(HERE, fn))
                    removed.append(fn)
                except OSError:
                    pass
            with PLANS_LOCK:
                plans = _load_plans()
                keep = [p for p in plans
                        if not (p["file"] == inst["config_file"] and p["status"] == "geplant")]
                if len(keep) != len(plans):
                    _save_plans(keep)
            print(f"[panel] {fname}: geloescht ({', '.join(removed) or 'nichts zu entfernen'})", flush=True)
            # Auf ausdruecklichen Wunsch des Aufrufers (terminal_zu, Archiv-
            # Loeschauftrag 07.09.2026) das Master-Terminal der geloeschten
            # Instanz mit schliessen. Die Beweis-Last haben die Riegel oben
            # schon getragen (keine eigenen Positionen/Hedges, kein laufender
            # Plan); loesch_terminal_dir prueft nur noch rein, dass kein
            # ANDERER den Ordner nutzt (Hedge-Terminal, fremde Instanz).
            # Kill im Hintergrund — Muster close-idle-terminals (03.09.2026):
            # die Grace-Periode darf nicht den 25s-Proxy-Timeout von app.py
            # reissen. Der manuelle Loeschen-Knopf schickt kein terminal_zu
            # und verhaelt sich exakt wie bisher.
            zu_msg = ""
            if bool(body.get("terminal_zu")):
                andere = [read_json(os.path.join(HERE, i2["config_file"]), {}) or {}
                          for i2 in instances()]
                zu_dir = loesch_terminal_dir(cfg_weg, andere)
                if zu_dir:
                    def _nach_loeschung_zu(d=zu_dir, fn=fname):
                        try:
                            pids = provision.terminal_pids(d)
                            for pid in pids:
                                provision._taskkill(pid, grace_s=5)
                            if pids:
                                print(f"[panel] {fn}: Master-Terminal nach Loeschung "
                                      f"geschlossen.", flush=True)
                        except Exception as e:
                            print(f"[panel] {fn}: Terminal-Zu nach Loeschung: "
                                  f"{type(e).__name__}: {e}", flush=True)
                    threading.Thread(target=_nach_loeschung_zu, daemon=True).start()
                    zu_msg = " Master-Terminal wird geschlossen;"
            return self._send(200, json.dumps({"ok": True, "msg":
                "Config geloescht — der Copier startet neu." + zu_msg +
                " Der Terminal-Ordner bleibt auf der Platte."}, ensure_ascii=False))

        if u.path == "/api/plan":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            p = upsert_plan(inst["config_file"], inst["name"], body.get("multiplier"))
            return self._send(200, json.dumps({"ok": True, "plan": p}, ensure_ascii=False))


        if u.path != "/api/save":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length") or 0)
            patch = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
        ok, msg = patch_config(inst["config_file"], patch)
        # restart bleibt im Payload (immer False), damit gecachte Alt-Frontends
        # den Schluessel weiter finden — der Moduswechsel als einziger Ausloeser
        # ist mit dem Modus-Ausbau (25.08.2026) weggefallen.
        print(f"[panel] {fname}: {msg}", flush=True)
        self._send(200, json.dumps({"ok": ok, "msg": msg, "restart": False}, ensure_ascii=False))

    def log_message(self, *a):
        pass  # eigenes, ruhigeres Logging oben


# ── Neustart-Sperre „Start steht bevor" (25.09.2026, Finns Test auf pc-iiiiii: der Hedge-Open um 20:51:14
# bekam 'copier_alt', weil der Copier gerade per Selbst-Update neu startete — zwischen Puls-Start und Hedge-Open
# liegen bis zu ~1 min, und in diesem Fenster hielt nichts den Neustart auf; eine offene Solo-Position tut es
# erst NACH dem Open). Jeder echte Puls-Start (/api/tv-order ohne probe) und POST /api/hedge-solo
# {aktion:'bereit', sekunden} schreibt hedge_bereit.json {bis, grund, at}; der Copier behandelt ein
# 'bis' in der Zukunft wie einen belegten Master und vertagt den Update-Neustart. Hoechstens 15 min.
HEDGE_BEREIT = "hedge_bereit.json"


def hedge_bereit_setzen(sekunden, grund):
    """Sperre bis jetzt + sekunden setzen (nie verkuerzen, max. 900 s). -> bis (Unix-Sekunden)."""
    pfad = os.path.join(HERE, HEDGE_BEREIT)
    try:
        sek = max(0.0, min(900.0, float(sekunden)))
    except (TypeError, ValueError):
        sek = 180.0
    alt = read_json(pfad, {}) or {}
    try:
        alt_bis = float(alt.get("bis") or 0)
    except (TypeError, ValueError):
        alt_bis = 0.0
    bis = max(alt_bis, time.time() + sek)
    try:
        tmp = pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"bis": bis, "grund": str(grund or "")[:60], "at": time.time()}, f)
        os.replace(tmp, pfad)
    except OSError as e:
        print(f"[panel] {HEDGE_BEREIT} nicht geschrieben: {type(e).__name__}: {e}", flush=True)
    return bis


# ── Selbst-Update wie im Copier (15.08.2026): neue VERSION auf GitHub → Neustart
# durch die start-panel.bat-Schleife. Das Panel ist zustandslos (Configs liegen
# atomar auf Platte) — einzige Ruecksicht: nie mitten in einer Provisionierung.
UPDATE_URL = ("https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/"
              "main/mt5-copier/VERSION")


# ── BOT-FÄHIGKEITEN (ES2d, 05.11.2026, Prüfer S2 zu ES3b) ─────────────────────────────────────────────────────────────────────────────
# Der Tab darf master-order ohne eigenen Scharf-Beweis nur schicken, wenn der Bot auf DIESEM PC ihn selbst führt: ein alter Bot ignoriert
# scharf_pflicht still → Order ohne Hedge-Fenster = ungehedgt. VERSION/bot_version beweisen das nicht (order_bot.py wird ohne Panel-Neustart
# getauscht und kann der VERSION-Datei hinterherhinken, s. ensure_bot_source). Beweis: dieser Panel-Code reicht scharf_pflicht durch (sonst
# gäbe es diese Funktion nicht) UND das order_bot.py, das jede Order frisch von der Platte startet, enthält den Scharf-Beweis (ES3b) — je
# mtime einmal gelesen. Fehler beim Lesen → keine Fähigkeit (der Tab wartet dann wie bisher selbst).
_BOT_FAEHIG = {"mtime": None, "liste": []}


def bot_faehig_aus_quelle(text):
    """REIN RECHNEND (testbar): Quelltext von order_bot.py → Liste der Fähigkeiten. 'scharf_pflicht' nur mit Urteil, Warten und BEIDEN
    Prüfstellen (vor Terminal/F9 und vor dem Order-Knopf)."""
    t = str(text or "")
    out = []
    if ("def echo_scharf_urteil(" in t and "def _echo_scharf_abwarten(" in t
            and t.count('cmd.get("scharf_pflicht") is True and not cmd.get("ohne_hedge")') >= 2):
        out.append("scharf_pflicht")
    return out


def bot_faehig():
    """Fähigkeiten des order_bot.py neben dem Panel (je mtime gecacht). Wirft nie."""
    pfad = os.path.join(HERE, "order_bot.py")
    try:
        mt = os.path.getmtime(pfad)
    except OSError:
        return []
    if _BOT_FAEHIG["mtime"] != mt:
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                _BOT_FAEHIG["liste"] = bot_faehig_aus_quelle(f.read())
        except Exception:
            _BOT_FAEHIG["liste"] = []
        _BOT_FAEHIG["mtime"] = mt
    return list(_BOT_FAEHIG["liste"])


def _local_version():
    try:
        with open(os.path.join(HERE, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


# ── QuickEdit aus (25.09.2026, Live-Befund pc-cccccc: Feed stand 6 min, Finns Foto zeigte die Titelleiste
# „Auswählen Prophos TV-Reader"). Windows-Konsolen starten bei einem Klick ins Fenster eine MARKIERUNG
# (QuickEdit) — solange sie steht, blockiert Windows jede Ausgabe, der Prozess haengt beim naechsten print()
# und nimmt nichts mehr an. Beim Start abschalten; auf Mac/Linux nichts.
def _quickedit_modus(mode):
    """REIN RECHNEND (testbar): Konsolen-Modus ohne ENABLE_QUICK_EDIT_MODE (0x0040), mit ENABLE_EXTENDED_FLAGS (0x0080)."""
    return (int(mode) & ~0x0040) | 0x0080


# ══ PC WACH HALTEN (PL2, Master 05.11.2026 nach PL1: PC von Mike pc-l5o8bv schlief heute 13× ein, 6 h, Panel UND Tab still, 3 Starts 21–64 min zu
# spät). Bisher hielt nur der TV-Reader den PC wach (tv-reader/reader-server.py wach_halten, 25.09.2026) — fehlt oder hängt er, greift der
# Energiesparplan von Windows. Jetzt auch das Panel, derselbe Weg: SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) — kein
# Admin, kein UAC, keine Systemeinstellung geändert; der Bildschirm darf aus (kein ES_DISPLAY_REQUIRED). Gilt je THREAD, darum im Haupt-Thread
# vor serve_forever (lebt so lange wie das Panel); endet der Prozess, gilt wieder Windows. Fehler → nur Hinweis, nichts bricht. ══
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def pc_wach_halten(kernel32=None):
    """→ None (kein Windows), True (gesetzt), False (abgelehnt/Fehler). kernel32 = Ersatz für Tests. Wirft nie."""
    try:
        if kernel32 is None:
            if os.name != "nt":
                return None
            import ctypes
            kernel32 = ctypes.windll.kernel32
        return bool(kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED))
    except Exception:
        return False


def quickedit_aus():
    """-> None (kein Windows), True (aus bzw. war schon aus), False (keine Konsole / abgelehnt)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)            # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k32.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        neu = _quickedit_modus(mode.value)
        return True if neu == mode.value else bool(k32.SetConsoleMode(h, neu))
    except Exception:
        return False


def _panel_code_geaendert(sha):
    """Wuerde ein Neustart den LAUFENDEN Panel-Code aendern? Vergleicht panel.py und
    provision.py aus GENAU dem Stand `sha` (Commit-Kennung, nie Zwischenspeicher)
    mit dem, was hier gerade laeuft (__file__ — bei runpy-Auffrischung ist das
    panel_frisch.py, also wirklich der laufende Code). True auch bei Unsicherheit
    (kein sha, kein Netz): dann gilt der alte Weg, Neustart."""
    if not sha:
        return True
    # gegen das Abbild BEIM LADEN (03.11.2026, pc-l5o8bv), nicht gegen die Datei — die kann schon erneuert sein, während der alte Code läuft
    for name in ("panel", "provision"):
        try:
            neu = repo_datei(f"mt5-copier/{name}.py", sha, 10)
        except Exception:
            return True
        if panel_code_weicht_ab(neu, name):
            return True
    return False


VERSION_NACHZIEHEN_S = 90


def _version_uebernehmen(version):
    """VERSION-Datei nachziehen, ohne Neustart — der Chip im MT5-Tab zeigt dann die
    Wahrheit: laufender Code == neuester Code, Nummer == neueste Nummer."""
    try:
        ziel = os.path.join(HERE, "VERSION")
        with open(ziel + ".tmp", "w", encoding="utf-8") as f:
            f.write(version + "\n")
        os.replace(ziel + ".tmp", ziel)
    except OSError as e:
        print(f"[panel] VERSION nachziehen: {type(e).__name__}: {e}", flush=True)


def _version_watcher(my_version):
    """Zwei Geschwindigkeiten (22.09.2026):
    SCHNELL — alle 15 s den neuesten Stand fragen (repo_sha). Hat er sich
    geaendert, wird order_bot.py sofort aus GENAU diesem Stand getauscht. Das
    ist die Datei, an der gerade gebaut wird, und sie braucht keinen Neustart:
    Bot-Aenderungen sind damit in ~15-20 s am PC, egal ob Master flach sind.
    LANGSAM — der Panel-Neustart wie bisher, aber erst, wenn AUCH 'main' die
    neue VERSION zeigt: die start-panel.bat laedt panel.py von dort. Ein
    Neustart vorher bekaeme den alten Stand aus dem Zwischenspeicher und
    startete im Kreis, bis der abgelaufen ist."""
    letzter = BOT_STAND.get("geholt_sha")      # nicht "sha": der Start-Abruf kann gescheitert sein (09.10.2026)
    # neuester = jüngster gemeldeter Stand, unabhängig vom Bot-Abruf — NUR er geht an _panel_code_geaendert (Prüfer T3 09.10.2026: mit
    # dem alten `letzter` sah der Neustart-Check das neue panel.py nie, übernahm aber die VERSION → das Update ging still verloren)
    neuester = BOT_STAND.get("sha")
    fehl_n = 0
    runde = 0
    upd = {"auf": None, "streu_bis": 0.0, "seit": None, "gemeldet": "", "code": {}}   # UPDATE-SCHUTZ (29.10.2026)
    while True:
        time.sleep(15)
        runde += 1
        sha = repo_sha()
        if sha:
            neuester = sha
        if sha and sha != letzter:
            # ERST NACH DEM ABRUF MERKEN (09.10.2026, Push e621d2b: ein Panel bekam beim Umschalten von Railway den neuen Stand über den
            # GitHub-Rückfall, der Abruf von order_bot.py kam nie in Railway an — `letzter` stand trotzdem schon auf dem neuen Stand,
            # das Panel fragte danach 15-s-weise /code/stand und holte die Datei bis zum nächsten Push nie). Jetzt gilt ein Stand erst als
            # erledigt, wenn order_bot.py in genau diesem Stand vorliegt; sonst holt der nächste Takt nach — mit Zufalls-Versatz, damit
            # nach einer Umschaltung nicht alle Panels im selben Takt nachfragen.
            ensure_bot_source(sha)
            if polar_panel:                                 # POLAR (13.10.2026): polar_bot.py/polar_panel.py aus demselben Stand
                polar_panel.ensure_source(repo_datei, sha)
            if BOT_STAND.get("geholt_sha") == sha or BOT_STAND.get("kaputt_sha") == sha:
                letzter, fehl_n = sha, 0            # kaputter Inhalt: nie wiederholen (alter Bot bleibt, Zeile steht in der Konsole)
            else:
                fehl_n += 1                         # Netz/HTTP: nachholen, Abstand wächst (bis ~2 min), gestreut
                print(f"[panel] order_bot.py für Stand {sha[:7]} nicht geholt ({fehl_n}. Mal) — nächster Takt versucht es erneut.",
                      flush=True)
                time.sleep(random.uniform(2, 10) + min(fehl_n - 1, 6) * random.uniform(12, 18))
        if runde % 2:                 # 'main' reicht alle 30 s
            continue
        try:
            remote = repo_datei("mt5-copier/VERSION", None, 10).decode("utf-8", "replace").strip()
        except Exception:
            continue
        if remote and remote != my_version:
            if PROV_JOB and not PROV_JOB.get("done"):
                continue  # nie mitten in einer Provisionierung
            # NIE mitten in einem Bot-Lauf (22.09.2026, Finns Lauf: 'Copier-Panel auf
            # diesem PC nicht erreichbar (ConnectionError)' — mein Push hatte das Panel
            # neu gestartet, WAEHREND der Puls in TradingView klickte; die Antwort ging
            # verloren, der Bot lief verwaist weiter). Solange der TradingView-Lauf
            # oder eine Master-Order ihre Sperre haelt, wird der Neustart vertagt.
            # UPDATE-SCHUTZ (29.10.2026): die Wartezeit zählt ab dem ersten Sehen dieser VERSION (Deckel unten gilt auch hier)
            if upd["seit"] is None:       # Wartezeit ab dem ersten anstehenden Update — eine neue VERSION beim Warten setzt sie nicht zurück
                upd.update(streu_bis=time.time() + random.uniform(0, UPDATE_STREU_S), seit=time.time(), gemeldet="")
            upd["auf"] = remote
            if (TV_ORDER_LOCK.locked() or mt5_order_belegt()) and time.time() - upd["seit"] < UPDATE_DECKEL_S:   # Lesungen zählen nicht (S1, RA2 F1)
                continue
            if polar_panel and polar_panel.aktiv():   # POLAR (13.10.2026): nie mitten im Polar-Trade neu starten — auch nach dem Deckel nicht (S2 29.10.2026)
                continue
            # NUR neu starten, wenn sich das PANEL selbst geaendert hat (23.09.2026, Finns
            # Nacht: 12 Frontend-Commits in 100 min, jeder mit VERSION-Bump, jeder ein
            # Panel-Neustart — und in jedem Neustart-Fenster stand der Signal-Empfaenger
            # im Prophos-Tab auf 'copier-offline'. Finns Orbit-Start vom Mac um 03:20:53
            # fiel genau ins Fenster des Bumps von 03:17 und wurde 17 s lang nicht
            # geclaimt: "warum ist Puls so langsam"). Der Stand `neuester` (repo_sha) ist
            # der neueste Commit; ist panel.py/provision.py dort gleich dem laufenden
            # Code, bringt ein Neustart nichts — nur die VERSION-Datei nachziehen, damit
            # der Chip stimmt. order_bot.py ist ohnehin schon per Hot-Swap frisch.
            if neuester not in upd["code"]:   # je Stand nur einmal holen (Prüfer: sonst panel.py+provision.py bei jedem Warte-Takt)
                upd["code"] = {neuester: _panel_code_geaendert(neuester)}
            if not upd["code"][neuester]:
                # COPIER-UPDATE-FIX (30.10.2026): erst nach 90 s nachziehen. Copier VOR diesem Stand vergleichen noch die VERSION-Datei (Takt 60 s) und
                # uebersehen sonst einen reinen copier.py-Commit; so sehen auch sie den Unterschied. Neue Copier haengen nicht mehr an der Datei.
                # Je VERSION eigene Uhr: upd["seit"] bleibt ueber mehrere Bumps stehen und liesse den zweiten sofort durch (Gegenpruefung 30.10.2026)
                _nz = upd.get("nachziehen") or {}
                if remote not in _nz:
                    upd["nachziehen"] = _nz = {remote: time.time()}
                if time.time() - _nz[remote] < VERSION_NACHZIEHEN_S:
                    continue
                _version_uebernehmen(remote)
                print(f"[panel] Update {my_version} → {remote}: Panel-Code unveraendert — kein Neustart.", flush=True)
                my_version = remote
                _GELADEN["version"] = remote   # der laufende Code ist nachweislich der dieser Version (Abbild verglichen)
                upd.update(auf=None, seit=None, gemeldet="")
                continue
            # UPDATE-SCHUTZ (29.10.2026, Befund Deploy-Welle): zwischen der Sperrprüfung oben und hier lagen bis zu 20 s (zwei Abrufe in
            # _panel_code_geaendert) — ein Lauf, der genau dann begann, starb mit. Jetzt: gestreut 0–60 s je PC, dann DIREKT vor dem Beenden
            # noch einmal alle Gründe (panel_beschaeftigt_gruende), belegt → 30 s vertagen; nach UPDATE_DECKEL_S trotzdem (Spur + ⚪).
            entsch, grund = update_neustart_entscheiden(panel_beschaeftigt_gruende(), upd["seit"], time.time(), upd["streu_bis"])
            if entsch == "warten":
                if grund != upd["gemeldet"] and not grund.startswith("Streuung"):
                    print(f"[panel] Update {my_version} → {remote} wartet — {grund}", flush=True)
                upd["gemeldet"] = grund
                time.sleep(random.uniform(0, 15))   # mit den 15 s oben ≈ alle 15–30 s neu prüfen
                continue
            # zu (neue POSTs → 503 „nichts gesendet") und nachprüfen; mit Deckel bis UPDATE_LEERLAUF_S leerlaufen lassen statt abzureißen
            if not _panel_zu_und_leeren(entsch == "erzwingen"):
                continue
            try:
                rest = panel_beschaeftigt_gruende()
                if entsch == "erzwingen":
                    print(f"[panel] Update {my_version} → {remote}: Deckel {UPDATE_DECKEL_S // 60} min — Neustart ({grund})", flush=True)
                    if rest:   # nur wenn wirklich noch etwas lief, kann etwas abgerissen sein
                        update_spur_melden("panel", my_version, remote, ", ".join(rest)[:200], time.time() - upd["seit"])
                print(f"[panel] Update {my_version} → {remote} — Neustart durch start-panel.bat.", flush=True)
            finally:
                os._exit(0)


def _selbst_auffrischen():
    """VERALTETES PANEL ERKENNEN UND BEHEBEN (22.09.2026). Die start-panel.bat
    laedt panel.py von '…/main/…' — GitHub haelt dort JEDE Datei bis zu fuenf
    Minuten im Zwischenspeicher, jede mit eigener Uhr. Ist VERSION schon frisch,
    panel.py aber noch alt, startet das ALTE Panel unter der NEUEN Versionsnummer
    — und weil die Nummern dann uebereinstimmen, aktualisiert es sich nie mehr
    (Finns Lauf: Schritt 3 lief still nicht, das Panel reichte 'symbol' nicht
    durch). Gegenmittel: beim Start den Quelltext aus dem NEUESTEN STAND holen
    (Adresse mit Commit-Kennung — kann nie alt sein). Weicht er ab, laeuft der
    frische Code in DIESEM Prozess weiter (runpy). Bewusst kein Neustart: die
    .bat wuerde die frische Datei sofort wieder mit der alten ueberschreiben.
    Jede Stoerung fuehrt einfach zum normalen Start."""
    if os.environ.get("PROPHOS_PANEL_FRISCH") == "1":
        return
    try:
        sha = repo_sha()
        if not sha:
            return
        neu = repo_datei("mt5-copier/panel.py", sha)
        with open(os.path.abspath(__file__), "rb") as f:
            alt = f.read()
        glatt = lambda b: b.replace(b"\r\n", b"\n").lstrip(b"\xef\xbb\xbf").strip()
        if glatt(neu) == glatt(alt) or len(neu) < 10000 or b"def main():" not in neu:
            return
        compile(neu, "panel.py", "exec")
        ziel = os.path.join(HERE, "panel_frisch.py")
        with open(ziel + ".tmp", "wb") as f:
            f.write(neu)
        os.replace(ziel + ".tmp", ziel)
        os.environ["PROPHOS_PANEL_FRISCH"] = "1"
        print(f"[panel] panel.py auf der Platte ist VERALTET (Zwischenspeicher) — fahre den "
              f"frischen Stand {sha[:7]} in diesem Prozess.", flush=True)
        import runpy
        runpy.run_path(ziel, run_name="__main__")
        os._exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[panel] Selbst-Auffrischen uebersprungen ({type(e).__name__}) — normaler Start.", flush=True)


# ══ TÄGLICHER NEUSTART JE PC (DR1, Finn 05.11.2026: „Wenn man das komplette Backend und auch die Prophos-Seite daily einmal neu startet, dann
# müsste ja der RAM in der Cache gelöscht werden.“ Anlass ES4: PC von Marco pc-t8wg97 und Emin pc-onkrbk seit 02.11. täglich langsamer, Emin RAM
# 90 %). Sicherheitsnetz, die eigentliche Ursache suchen SW1/SW2. Einmal je Dubai-Tag, im Fenster aus puls_heim_regel.pc_neustart (Standard
# AUS, nur_pcs für den Testlauf), nur wenn Railway den PC ruhig meldet (Tab-Stand „tages_neustart“: kein Plan open, kein Hedge offen, kein
# Start in den nächsten 30 min, kein Signal) UND hier nichts läuft (panel_beschaeftigt_gruende, Browser/MT5 frei, kein scharfer Eintrag,
# niemand am PC). Nur BESTEHENDE Wege: Puls-Chrome per order_bot._puls_chrome_beenden zu, Prophos-Tab per _tab_oeffnen wieder auf (startet
# das Puls-Chrome selbst), Copier über copier_neustart.json (startet nur flach neu, wie das Selbst-Update), Panel zuletzt per os._exit →
# start-panel.bat. MT5-Terminals bleiben offen (Login-Kosten). Gestreut 1–20 min ab dem ersten ruhigen Moment (Jitter-Regel). Ergebnis in
# tages_neustart.json (überlebt den Exit) → panel_lauf.tages_neustart → mt5_live.status über den Prophos-Tab: at, ram_vorher/ram_nachher (%),
# copier_neu (PID gewechselt), schritte. Kein ruhiger Moment bis Fensterende → einmal Spur an Railway (/pc/update-spur), morgen neu. ══
TN_DATEI = "tages_neustart.json"
TN_TAKT_S = 60.0
TN_STREU_S = (60.0, 20 * 60.0)
TN_LEERLAUF_MIN_S = 120.0       # so lange keine Eingabe am PC (sonst sitzt jemand davor)
TN_NACHHER_S = 5 * 60.0         # RAM nach dem Neustart erst messen, wenn Tab/Puls-Chrome wieder stehen


def tages_neustart_entscheiden(sicht, tag_erledigt, jetzt, streu_bis, gruende_lokal, idle_s, verpasst_gemeldet):
    """REIN RECHNEND (testbar). sicht = Tab-Stand-Feld tages_neustart von Railway ({an, pc_frei, tag, offen, vorbei, ruhig, grund}) oder None;
    tag_erledigt = Dubai-Tag des letzten Neustarts. → ('aus' | 'warten' | 'streuen' | 'jetzt' | 'verpasst', grund)."""
    s = sicht if isinstance(sicht, dict) else None
    if not s or not s.get("an"):
        return "aus", "aus (puls_heim_regel.pc_neustart.an)" if s else "Tab-Stand ohne tages_neustart (Railway alt oder nicht lesbar)"
    if not s.get("pc_frei"):
        return "aus", "PC nicht in nur_pcs"
    tag = str(s.get("tag") or "")
    if not tag or tag == str(tag_erledigt or ""):
        return "aus", f"heute schon neu gestartet ({tag})" if tag else "Tag unbekannt"
    if s.get("vorbei"):
        return ("aus", "Fenster vorbei, schon gemeldet") if verpasst_gemeldet == tag else ("verpasst", f"kein ruhiger Moment im Fenster ({tag})")
    if not s.get("offen"):
        return "aus", "außerhalb des Fensters"
    if not s.get("ruhig"):
        return "warten", "Railway: " + str(s.get("grund") or "nicht ruhig")[:160]
    if gruende_lokal:
        return "warten", "Panel: " + ", ".join(gruende_lokal)[:160]
    if idle_s is not None and idle_s < TN_LEERLAUF_MIN_S:
        return "warten", f"jemand am PC (letzte Eingabe vor {int(idle_s)} s)"
    if streu_bis is None:
        return "streuen", "ruhig — Streuung würfeln"
    if jetzt < streu_bis:
        return "warten", f"Streuung noch {int(streu_bis - jetzt)} s"
    return "jetzt", "ruhig"


def _ram_prozent():
    """Belegter Arbeitsspeicher in % (GlobalMemoryStatusEx) oder None — nur Windows, wirft nie."""
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = _MS()
        ms.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
            return None
        return int(ms.dwMemoryLoad)
    except Exception:
        return None


def _copier_pid():
    return (read_json(os.path.join(HERE, "copier-log.json"), None) or {}).get("pid")


def tages_neustart_info():
    """Kurzfassung für panel_lauf (→ mt5_live.status über den Tab). Wirft nie."""
    try:
        d = read_json(os.path.join(HERE, TN_DATEI), None)
        if not isinstance(d, dict):
            return {"stand": TN_STAND.get("grund") or None}
        return dict({k: d.get(k) for k in ("tag", "at", "ram_vorher", "ram_nachher", "copier_neu", "backend_neu", "reader_neu", "abbruch", "schritte")},
                    stand=TN_STAND.get("grund") or None)
    except Exception:
        return None


TN_STAND = {"grund": "", "streu_bis": None, "streu_tag": "", "verpasst": ""}


def _tn_schreiben(d):
    """tages_neustart.json schreiben → True/False. Ohne geschriebenen Merker kein Neustart (Prüfer DR1: sonst wüsste das neue Panel nicht,
    dass heute schon neu gestartet wurde, und startete im Fenster wieder und wieder neu)."""
    try:
        with open(os.path.join(HERE, TN_DATEI) + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(os.path.join(HERE, TN_DATEI) + ".tmp", os.path.join(HERE, TN_DATEI))
        return True
    except OSError as e:
        print(f"[tages-neustart] Merker nicht schreibbar ({type(e).__name__}) — kein Neustart", flush=True)
        return False


def _tn_frisch_ruhig(pc):
    """Direkt vor dem Neustart den Tab-Stand FRISCH holen (Prüfer DR1: der gemerkte Stand kann 150 s alt sein) → (ruhig, grund, sicht)."""
    st = _tab_stand_holen(pc, TAB_NL.get("grund") or "") if pc else None
    s = st.get("tages_neustart") if isinstance(st, dict) and st.get("ok") else None
    if not isinstance(s, dict):
        return False, "Tab-Stand frisch nicht lesbar", {}
    if isinstance(st, dict):
        TAB_NL.update(stand=st, stand_at=time.time())
    return bool(s.get("an") and s.get("pc_frei") and s.get("offen") and s.get("ruhig")), str(s.get("grund") or ""), s


# ── DR1b (Finn/Master 05.11.2026: „das komplette Backend … daily neu starten“): lokales Backend (app.py, Port 5000) und Reader (reader-server.py,
# Port 8790) im selben ruhigen Moment. Neu starten = genau die EINE lauschende python-PID beenden — taskkill /F OHNE /T. Backend: python ist Kind
# von cmd /c start-prophos.bat (Schleife: Ende → 10 s → frische Dateien → Neustart), mit /T stürbe die Schleife mit. Reader: am Port lauscht das
# Kind der Reader-Aufsicht (reader-server.py startet es per Popen), die Aufsicht startet es nach ~5 s aus der vorhandenen Datei neu (Prüfer DR1b).
# PID über netstat wie der Reader selbst (reader-server.py netstat_lauscher); beendet wird nur, was python ist UND das Skript in der Befehlszeile
# trägt — nie ein fremdes Programm auf dem Port. Backend zusätzlich nie bei aktiver Spiegel-Sitzung (mirror_sessions: ihr Stand ist laut
# _local_version_watcher nicht wiederherstellbar; das Update wartet dort auch). Kein Popen, kein UAC (eigener Benutzer).
# (name, port, skript, frist_s, rückkehr-pfad) — Rückkehr über einen billigen Pfad (Prüfer DR1b: „/“ des Backends lädt erst 7 MB prophos.html)
TN_TEILE = (("backend", 5000, "app.py", 120.0, "/health"), ("reader", 8790, "reader-server.py", 60.0, "/"))


def netstat_lauscher(text, port):
    """REIN RECHNEND (testbar, wie reader-server.py): PIDs, die laut 'netstat -ano -p TCP' auf <port> lauschen (Gegenstelle 0.0.0.0:0)."""
    pids = set()
    for z in str(text or "").splitlines():
        t = z.split()
        if len(t) >= 5 and t[0].upper() == "TCP" and t[1].endswith(f":{port}") and t[2] in ("0.0.0.0:0", "[::]:0"):
            try:
                pids.add(int(t[-1]))
            except ValueError:
                pass
    return sorted(pids)


def tn_prozesse_parsen(roh):
    """REIN RECHNEND (testbar): JSON aus Get-CimInstance Win32_Process → {pid: {name, cmd}}."""
    try:
        d = json.loads(roh) if roh else []
    except ValueError:
        return {}
    out = {}
    for x in ([d] if isinstance(d, dict) else d if isinstance(d, list) else []):
        try:
            out[int(x.get("ProcessId"))] = {"name": str(x.get("Name") or ""), "cmd": str(x.get("CommandLine") or "")}
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def tn_port_ziel(pids, prozesse, skript):
    """REIN RECHNEND (testbar): (pid | None, grund). Genau EIN Lauscher, der python*.exe ist und skript als eigenes Wort in der Befehlszeile hat
    (…\\app.py, nicht dapp.py) — sonst None. Fremdes Programm, mehrere Lauscher oder unlesbare Befehlszeile → nie beenden."""
    if not pids:
        return None, "läuft nicht (Port frei)"
    if len(pids) > 1:
        return None, f"{len(pids)} Programme lauschen — nichts beendet"
    p = prozesse.get(pids[0])
    if not p:
        return None, f"PID {pids[0]}: Befehlszeile nicht lesbar — nichts beendet"
    name, cmd = p["name"].lower(), p["cmd"].lower()
    if not re.fullmatch(r"python[0-9.]*w?\.exe|py\.exe", name):     # auch python3.12.exe (Microsoft Store)
        return None, f"PID {pids[0]} ist {p['name'] or '?'} — fremdes Programm, nichts beendet"
    if not re.search(r"(^|[\s\\/\"'])" + re.escape(skript.lower()) + r"($|[\s\"'])", cmd):
        return None, f"PID {pids[0]}: python ohne {skript} — fremdes Programm, nichts beendet"
    return pids[0], ""


def tn_spiegel_scharf(daten):
    """REIN RECHNEND (testbar): GET /mirror/status (ohne pairId) des Backends → [pair_id] aktiver Spiegel-Sitzungen, None = nicht lesbar.
    Die Übersicht liefert weder engine noch direction — darum zählt hier jede aktive Sitzung (strenger als der Update-Weg, nie lockerer)."""
    if not isinstance(daten, dict):
        return None
    return sorted(str(k) for k, v in daten.items() if isinstance(v, dict) and v.get("active"))


def _tn_spiegel_frei():
    """→ (frei, grund). Nicht lesbar → nicht frei (kein Kill)."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/mirror/status", timeout=8) as r:
            scharf = tn_spiegel_scharf(json.loads(r.read().decode("utf-8") or "null"))
    except Exception as e:
        return False, f"Spiegel-Stand nicht lesbar ({type(e).__name__}) — Backend nicht neu"
    if scharf is None:
        return False, "Spiegel-Stand nicht lesbar — Backend nicht neu"
    return (not scharf), (f"Spiegel-Sitzung aktiv ({', '.join(scharf)[:60]}) — Backend nicht neu" if scharf else "")


def _tn_netstat():
    r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=15, errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.stdout or ""


def _tn_prozesse(pids):
    if not pids:
        return {}
    filt = " or ".join(f"ProcessId={int(p)}" for p in pids)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", f"Get-CimInstance Win32_Process -Filter \"{filt}\" "
                        "| Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"],
                       capture_output=True, text=True, timeout=25, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return tn_prozesse_parsen((r.stdout or "").strip())


def _tn_antwortet(port, pfad="/"):
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}{pfad}", timeout=4).close()
        return True
    except urllib.error.HTTPError:
        return True                        # antwortet (404 o. ä.) = läuft
    except Exception:
        return False


def _tn_teil_neu(port, skript, frist_s, pfad="/", vorab=None):
    """Ein Teil neu starten → (status, text). VOR dem Kill: 'fehlt' | 'fremd' | 'belegt' | 'uebersprungen' (Fehler beim Prüfen — nichts
    angefasst, weitermachen; Prüfer DR1b). NACH dem Kill: 'neu' | 'nicht_zurueck' | 'fehler'. vorab() → (frei, grund), z. B. Spiegel-Schutz."""
    try:
        pids = netstat_lauscher(_tn_netstat(), port)
        pid, grund = tn_port_ziel(pids, _tn_prozesse(pids), skript)
        if pid is None:
            return ("fehlt" if not pids else "fremd"), grund
        if vorab is not None:
            frei, g = vorab()
            if not frei:
                return "belegt", g
        r = subprocess.run(["taskkill", "/PID", str(int(pid)), "/F"], capture_output=True, text=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:      # z. B. „Zugriff verweigert“ (mit Adminrechten gestartet) — läuft weiter, nichts kaputt
            return "uebersprungen", f"taskkill PID {pid} abgelehnt ({(r.stdout or r.stderr or '').strip()[:80]})"
    except Exception as e:
        return "uebersprungen", f"vor dem Beenden: {type(e).__name__}: {str(e)[:80]} — nichts angefasst"
    try:
        t0 = time.time()
        while time.time() - t0 < frist_s:
            time.sleep(2 + random.random() * 2)              # gestreut
            neu = netstat_lauscher(_tn_netstat(), port)
            if neu and pid not in neu and _tn_antwortet(port, pfad):
                return "neu", f"neu (PID {pid} → {neu[0]}, {int(time.time() - t0)} s)"
        return "nicht_zurueck", f"PID {pid} beendet, nach {int(frist_s)} s nicht zurück"
    except Exception as e:
        return "fehler", f"nach dem Beenden: {type(e).__name__}: {str(e)[:80]}"


def _tages_neustart_ausfuehren(tag):
    """Die Schritte (bestehende Wege) → endet mit os._exit(0), außer es ist doch nicht ruhig/nicht schreibbar (dann False, nichts getan)."""
    ruhig, g, sicht = _tn_frisch_ruhig(pc_id_lesen())
    if not ruhig:
        TN_STAND["streu_bis"] = None
        print(f"[tages-neustart] frisch geprüft doch nicht ruhig: {g or 'aus'}", flush=True)
        return False
    ram0, pid0 = _ram_prozent(), _copier_pid()
    merk = {"tag": tag, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "at_ts": time.time(), "ram_vorher": ram0,
            "ram_nachher": None, "copier_pid_vorher": pid0, "copier_neu": None, "schritte": ["begonnen"]}
    if not _tn_schreiben(merk):            # VOR dem ersten Schritt: der Tag gilt ab hier als erledigt
        return False
    if not _panel_zu_und_leeren(False):
        _tn_schreiben(dict(merk, tag=None, schritte=["abgebrochen: Panel beim Zumachen belegt"]))
        return False
    schritte = []
    if not TV_ORDER_LOCK.acquire(blocking=False):
        with _PANEL_POST_LOCK:
            _PANEL_POST["zu"] = False
        _tn_schreiben(dict(merk, tag=None, schritte=["abgebrochen: Puls im Browser"]))
        return False
    try:
        try:
            with open(os.path.join(HERE, "copier_neustart.json"), "w", encoding="utf-8") as f:
                json.dump({"at": time.time(), "von": "tages_neustart"}, f)
            schritte.append("Copier: Neustart-Wunsch abgelegt")
        except OSError as e:
            schritte.append(f"Copier-Wunsch nicht geschrieben ({type(e).__name__})")
        # DR1b: Backend, dann Reader — VOR dem Chrome-Schritt (der neue Tab braucht das Backend, das neue Userscript trifft den frischen Reader)
        teile = sicht.get("teile") if isinstance(sicht.get("teile"), dict) else {}
        for name, port, skript, frist, pfad in TN_TEILE:
            if teile.get(name) is False:
                schritte.append(f"{name}: aus (pc_neustart.teile)")
                continue
            st, txt = _tn_teil_neu(port, skript, frist, pfad, _tn_spiegel_frei if name == "backend" else None)
            merk[f"{name}_neu"] = st == "neu"
            schritte.append(f"{name}: {txt}")
            if name == "backend" and st in ("nicht_zurueck", "fehler"):
                # ohne Backend öffnet kein Tab (_tab_oeffnen prüft localhost:5000) → vor dem Chrome-Schritt aufhören, Chrome/Tab/Panel bleiben
                with _PANEL_POST_LOCK:
                    _PANEL_POST["zu"] = False
                _tn_schreiben(dict(merk, abbruch=f"Backend kam nicht zurück: {txt}", schritte=schritte + ["abgebrochen vor dem Chrome-Schritt"]))
                _tab_heil_melden(f"täglicher Neustart abgebrochen — Backend (Port 5000) kam nicht zurück: {txt}", "tages_neustart")
                print(f"[tages-neustart] {tag}: Abbruch — Backend kam nicht zurück ({txt})", flush=True)
                return True
            if name == "reader" and st in ("nicht_zurueck", "fehler"):
                # S2 (DR1b): der Reader ist der erste Weg der Fusion-Schließkette (Schließ-Wache liest ihn) → 🟠, aber kein Abbruch (Tab-Weg bleibt)
                _tab_heil_melden(f"täglicher Neustart — Reader (Port 8790) kam nicht zurück: {txt}", "tages_neustart")
                print(f"[tages-neustart] {tag}: Reader kam nicht zurück ({txt}) — 🟠, weiter", flush=True)
        code = ("import json, order_bot\nt = []\nok, txt = order_bot._puls_chrome_beenden(t)\nprint(json.dumps([bool(ok), str(txt)[:160]]))\n")
        try:
            r = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, timeout=90,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            ok, txt = json.loads((r.stdout or "").strip().splitlines()[-1])
        except Exception as e:
            ok, txt = False, f"{type(e).__name__}"
        schritte.append(("Puls-Chrome zu: " if ok else "Puls-Chrome nicht zu: ") + str(txt))
        time.sleep(3 + random.random() * 4)
        ok2, msg2 = _tab_oeffnen(TAB_URL, lock_gehalten=True)   # startet das Puls-Chrome selbst (_puls_chrome_sicher), Prophos im eigenen Fenster
        schritte.append(("Prophos-Tab neu: " if ok2 else "Prophos-Tab NICHT neu: ") + str(msg2)[:160])
    finally:
        TV_ORDER_LOCK.release()
    time.sleep(8 + random.random() * 4)   # der neue Tab lädt, bevor das Panel kurz weg ist
    # LETZTE PRÜFUNG vor dem Exit wie beim Update-Neustart (Prüfer DR1): läuft inzwischen etwas, bis UPDATE_LEERLAUF_S auf das Ende warten
    ende = time.time() + UPDATE_LEERLAUF_S
    while panel_beschaeftigt_gruende() and time.time() < ende:
        time.sleep(0.5)
    rest = panel_beschaeftigt_gruende()
    if any(str(x).startswith("Polar") for x in rest):     # Polar nie abreißen: Panel bleibt, Chrome/Copier sind schon neu
        with _PANEL_POST_LOCK:
            _PANEL_POST["zu"] = False
        _tn_schreiben(dict(merk, schritte=schritte + ["Panel NICHT neu: Polar-Lauf"]))
        return True
    _tn_schreiben(dict(merk, schritte=schritte + ["Panel: Neustart (start-panel.bat)" + (f", lief noch: {', '.join(rest)[:80]}" if rest else "")]))
    print(f"[tages-neustart] {tag}: RAM {ram0} % · " + " · ".join(schritte) + " → Panel-Neustart", flush=True)
    os._exit(0)


def _tages_neustart_nachher():
    """Nach dem Panel-Start: war der Neustart eben erst (< 30 min) und fehlt die Messung → nach TN_NACHHER_S RAM + Copier-PID nachtragen."""
    try:
        d = read_json(os.path.join(HERE, TN_DATEI), None)
        if not isinstance(d, dict) or d.get("ram_nachher") is not None or time.time() - float(d.get("at_ts") or 0) > 1800:
            return
        time.sleep(TN_NACHHER_S)
        d["ram_nachher"] = _ram_prozent()
        pid = _copier_pid()
        d["copier_neu"] = bool(pid and pid != d.get("copier_pid_vorher"))
        with open(os.path.join(HERE, TN_DATEI), "w", encoding="utf-8") as f:
            json.dump(d, f)
        print(f"[tages-neustart] danach: RAM {d.get('ram_vorher')} → {d['ram_nachher']} % · Copier neu: {d['copier_neu']}", flush=True)
    except Exception as e:
        print(f"[tages-neustart] Nachmessung: {type(e).__name__}: {e}", flush=True)


def _tages_neustart_waechter():
    if os.name != "nt":
        return
    _tages_neustart_nachher()
    time.sleep(120 + random.random() * 60)
    while True:
        try:
            st = TAB_NL.get("stand") if time.time() - float(TAB_NL.get("stand_at") or 0) < 150 else None
            sicht = st.get("tages_neustart") if isinstance(st, dict) else None
            d = read_json(os.path.join(HERE, TN_DATEI), None)
            erledigt = d.get("tag") if isinstance(d, dict) else None
            lokal = panel_beschaeftigt_gruende()
            if not _browser_und_mt5_frei():
                lokal = lokal + ["Browser/MT5 belegt"]
            if scharf_konto_fest():
                lokal = lokal + ["offener TradingView-Trade mit Hedge (scharf)"]
            tag = str((sicht or {}).get("tag") or "")
            if TN_STAND["streu_tag"] != tag:
                TN_STAND.update(streu_bis=None, streu_tag=tag)
            entsch, grund = tages_neustart_entscheiden(sicht, erledigt, time.time(), TN_STAND["streu_bis"], lokal, _win_leerlauf_s(),
                                                       TN_STAND["verpasst"])
            if entsch == "streuen":
                TN_STAND["streu_bis"] = time.time() + random.uniform(*TN_STREU_S)
            elif entsch == "verpasst":
                TN_STAND["verpasst"] = tag
                _tab_heil_melden(f"im Fenster kein ruhiger Moment ({TN_STAND.get('grund') or 'belegt'})", "tages_neustart")   # 🟠 1× je PC und Tag
            elif entsch == "jetzt":
                if _tages_neustart_ausfuehren(tag):   # endet im Erfolgsfall mit os._exit; True = Panel blieb wegen Polar
                    grund = "Panel blieb (Polar-Lauf oder Abbruch, s. tages_neustart.json)"
                else:
                    grund = "doch nicht ruhig/belegt — nächster Takt"
            if grund != TN_STAND["grund"]:
                TN_STAND["grund"] = grund
                if entsch != "aus":
                    print(f"[tages-neustart] {entsch}: {grund}", flush=True)
        except Exception as e:
            print(f"[tages-neustart] Fehler: {type(e).__name__}: {e}", flush=True)
        time.sleep(TN_TAKT_S + random.random() * 30)


# ══ NUR EIN PANEL JE PC (Betrieb 1 03.11.2026: pc-usq1i6 hatte ZWEI panel.py-Prozesse, beide 13:19 dt — zwei start-panel.bat-Schleifen). Unter Windows
# setzt ThreadingHTTPServer SO_REUSEADDR (allow_reuse_address) — das erlaubt dort einen ZWEITEN Bind auf 127.0.0.1:8770; „Port belegt“ griff nie. Beide
# Prozesse fuhren alle Wachen (Schließ-Wache, Version-Watcher, Puls-Locks nur je Prozess). Jetzt: benannter Mutex vor allen Threads. Der Bind bleibt wie er war
# (S9-Stopp zu ae4b57db: SO_EXCLUSIVEADDRUSE scheitert, solange TIME_WAIT-Verbindungen auf 8770 stehen — das HTTP/1.0-Panel hat davon laufend viele, nach jedem
# Update-Neustart wäre es 2–4 min weg gewesen). Gibt ein neues Panel wegen des Mutex auf, steht das in panel_mutex_aufgabe.json (panel_lauf.mutex_aufgaben). ══
_EINZEL_MUTEX = []   # Handle festhalten (sonst gibt Windows den Mutex beim Aufräumen frei)
MUTEX_AUFGABE_PFAD = os.path.join(HERE, "panel_mutex_aufgabe.json")


def mutex_aufgabe_merken(jetzt):
    """S9 zu ae4b57db: ein neues Panel gibt wegen des Mutex auf → Zähler + Zeit + PID in panel_mutex_aufgabe.json (das laufende Panel meldet es im
    Herzschlag; hängt es, liest man die Datei per Lotse). Wirft nie."""
    try:
        alt = read_json(MUTEX_AUFGABE_PFAD, {}) or {}
        d = {"n": int(alt.get("n") or 0) + 1, "erst_at": alt.get("erst_at") or jetzt, "letzt_at": jetzt, "pid": os.getpid()}
        with open(MUTEX_AUFGABE_PFAD + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(MUTEX_AUFGABE_PFAD + ".tmp", MUTEX_AUFGABE_PFAD)
    except Exception as e:
        print(f"[panel] {MUTEX_AUFGABE_PFAD} nicht geschrieben: {type(e).__name__}: {e}", flush=True)


def panel_einzel_instanz():
    """→ True (dieses Panel ist das einzige / kein Windows), False (es läuft schon eins). Benannter Mutex je Port, gilt bis zum Prozessende."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.CreateMutexW(None, False, f"Local\\ProphosPanel{PORT}")
        if not h:
            return True                      # Mutex nicht anlegbar → wie bisher starten (der exklusive Bind fängt den Rest)
        if k32.GetLastError() == 183:        # ERROR_ALREADY_EXISTS
            k32.CloseHandle(h)
            return False
        _EINZEL_MUTEX.append(h)
        return True
    except Exception:
        return True


def main():
    if quickedit_aus():
        print("QuickEdit aus (Klick ins Fenster hält das Panel nicht mehr an)", flush=True)
    _wach = pc_wach_halten()   # PL2 (05.11.2026): Haupt-Thread, lebt bis serve_forever endet
    if _wach is not None:
        print("PC bleibt wach, solange das Panel läuft (Bildschirm darf aus, keine Systemeinstellung geändert)" if _wach
              else "[panel] PC wach halten abgelehnt — es gilt der Energiesparplan von Windows", flush=True)
    _selbst_auffrischen()
    # nach dem Auffrischen: läuft der frische Stand per runpy in DIESEM Prozess, legt erst dessen main() den Mutex an (sonst sähe es sich selbst)
    if not panel_einzel_instanz():
        print(f"[panel] Es läuft schon ein Panel auf Port {PORT} — dieses Fenster beendet sich (nächster Versuch der .bat in ~70 s).", flush=True)
        mutex_aufgabe_merken(time.time())   # S9: ein hängendes Panel hält den Mutex → sichtbar machen (Zähler + Zeit)
        time.sleep(60)   # die .bat-Schleife startet nach 10 s neu: so nur ~1 Versuch je 70 s statt Download-Schleife alle 10 s
        sys.exit(f"Panel läuft schon (Port {PORT})")
    print("=" * 66)
    print(" Echo-Panel (Prophos)")
    print(f" Ordner: {HERE}")
    print(f" Master: {', '.join(i['config_file'] for i in instances()) or '(keine config*.json gefunden)'}")
    ignored = [fn for fn in sorted(os.listdir(HERE))
               if fn.endswith(".json") and fn.lower().startswith("config")
               and fn not in TEMPLATES and not CONFIG_RE.fullmatch(fn)]
    if ignored:
        print(f" IGNORIERT (kein gueltiger Config-Name): {', '.join(ignored)}")
    print(f" Im Browser oeffnen:  http://127.0.0.1:{PORT}")
    print(" Nur lokal erreichbar. Prophos wird nicht angefasst.")
    v = _local_version()
    if v:
        print(f" Version {v} · Selbst-Update aktiv")
        threading.Thread(target=_version_watcher, args=(v,), daemon=True).start()
    # Plan-Zustandsmaschine unabhaengig vom Browser treiben (Review 15.08.2026):
    # advance_plans lief bisher nur bei GET /api/instances — sobald aber die
    # Prophos-View nicht offen ist, pollt niemand, und geplant→laufend→beendet
    # bliebe stehen (falsche/fehlende Zeitstempel). Ein Daemon-Tick alle 5 s
    # macht die Uebergaenge unabhaengig davon, ob ein Browser zuschaut.
    threading.Thread(target=_plan_ticker, daemon=True).start()
    # Vom Neustart abgeschnittene Terminal-Zu-Auftraege nachholen (21.09.2026)
    try:
        terminal_zu_nachholen()
    except Exception as e:
        print(f"[panel] Terminal-Zu nachholen: {type(e).__name__}: {e}", flush=True)
    # Leerlauf-Waechter (22.09.2026): Terminal ohne Trade geht nach ~15 min von selbst zu
    threading.Thread(target=_leerlauf_waechter, daemon=True).start()
    threading.Thread(target=_login_dialog_waechter, daemon=True).start()   # 29.10.2026: Login-Wache auch ohne Kaltstart
    threading.Thread(target=_boot_terminals, daemon=True).start()   # 01.10.2026: Master mit laufendem Trade nach PC-Start
    # MT5-Update ohne UAC-Abfrage (01.10.2026) — Details bei _mt5_update_waechter
    threading.Thread(target=_mt5_update_waechter, daemon=True).start()
    threading.Thread(target=_build_angleich_waechter, daemon=True).start()   # MU1 (10.11.2026): MT5-Build ohne UAC angleichen
    # Tab selbst neu laden (16.10.2026) — Details bei _tab_neulade_waechter
    threading.Thread(target=_tab_neulade_waechter, daemon=True).start()
    threading.Thread(target=_tages_neustart_waechter, daemon=True).start()   # DR1 (05.11.2026): täglicher Neustart je PC, Standard aus
    threading.Thread(target=_scharf_wache, daemon=True).start()   # Schließ-Wache (02.11.2026, s. SCHLIESSEN AUF DEM PC)
    threading.Thread(target=_ea_frost_waechter, daemon=True).start()   # F2 (30.10.2026): EA-Selbstheilung ohne Knopf
    threading.Thread(target=_pc_last_waechter, daemon=True).start()   # SW1 (05.11.2026): Last des PCs messen, s. LAST DES PCs MESSEN
    threading.Thread(target=_uac_alarm_waechter, daemon=True).start()   # UA1 (06.11.2026): offene Windows-Abfrage an Railway melden
    # UAC-Haken an allen terminal64.exe wegraeumen (09.09.2026, Finns Fund:
    # Benutzerkontensteuerung beim Terminal-Start ueber Echo — Details im
    # Docstring von provision.uac_haken_entfernen). getattr-Riegel, weil die
    # Panel-.bat-Schleife nur panel.py holt, provision.py aber nur die
    # Copier-Schleife: ein frisches Panel darf auf einem alten provision-Stand
    # nicht mit AttributeError sterben — der naechste Copier-Zyklus zieht
    # provision.py nach, dann greift der Lauf von selbst.
    getattr(provision, "uac_haken_entfernen", lambda: None)()
    # Download-Kennung an allen MT5-Installationen weg + Stand für den Status (23.10.2026, s. _windows_abfrage_vorbeugen)
    threading.Thread(target=_windows_abfrage_vorbeugen, daemon=True).start()
    # Von-Null-Selbstheilung: fehlende Vorlage einmalig aus dem Repo holen
    # (blockiert den Start nicht laenger als den Download-Timeout).
    ensure_vorlage()
    # EA-Quelltext aktuell halten — kompiliert wird pro Terminal beim Kalt-Start
    ensure_ea_source()
    # Order-Bot aktuell halten (die .bat-Loops kennen die Datei nicht)
    ensure_bot_source()
    # POLAR (13.10.2026): polar_bot.py + polar_panel.py holen; das Modul selbst greift erst nach dem nächsten Panel-Start
    try:
        if polar_panel:
            polar_panel.ensure_source(repo_datei, BOT_STAND.get("sha"))
        else:
            _d = repo_datei("mt5-copier/polar_panel.py", BOT_STAND.get("sha"))
            if _d and len(_d) > 500:
                compile(_d, "polar_panel.py", "exec")
                with open(os.path.join(HERE, "polar_panel.py"), "wb") as _f:
                    _f.write(_d)
                print("[polar] polar_panel.py geholt — aktiv ab dem nächsten Panel-Start", flush=True)
    except Exception as _e:
        print(f"[polar] Dateien nicht geholt ({type(_e).__name__})", flush=True)
    # Starter aktuell halten — verzoegert, s. Funktionskommentar
    ensure_starter_source()
    # Klick-Bot-Abhaengigkeit (Maus-Steuerung) einmalig installieren
    threading.Thread(target=ensure_pywinauto, daemon=True).start()
    # MetaTrader5 im Panel-Python (= Order-Bot) beim Start und alle 30 min prüfen, bei Bedarf installieren (08.10.2026)
    threading.Thread(target=_mt5_paket_waechter, daemon=True).start()
    # Liegengebliebene Login-inis mit Klartext-Passwort aufraeumen (Review-Fund
    # 15.08.2026): der _remove_later-Thread ueberlebt das os._exit des Version-
    # Watchers nicht — beim naechsten Start hier nachziehen.
    for inst in instances():
        _cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        _p = str(_cfg.get("master_terminal_path") or "").strip()
        if _p:
            try:
                os.remove(os.path.join(os.path.dirname(_p), "prophos-login.ini"))
            except OSError:
                pass
    print("=" * 66)
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nPanel beendet.")
    except OSError as e:
        sys.exit(f"Port {PORT} belegt oder blockiert: {e}")


if __name__ == "__main__":
    main()
