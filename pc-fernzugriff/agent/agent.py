# -*- coding: utf-8 -*-
"""agent.py — PC-Agent: Maus, Tastatur, Fenster, Foto auf einem Windows-PC, gesteuert vom Mac (02.11.2026, Auftrag PC-AGENT).

Warum (Finn 02.11.2026: „Ich muss die PCs eigenständig bedienen können, Maus, Tastatur, alles sehen, und es muss viel
schneller gehen“): bisher kostete jede Aktion ~45 s (Skript per scp, geplante Aufgabe anlegen, feste Wartezeit, Foto per scp).
Jetzt läuft dieser Agent DAUERHAFT in der angemeldeten Windows-Sitzung (geplante Aufgabe „Prophos Agent“ bei Anmeldung,
pythonw, Neustart bei Absturz — agent-aufgabe.ps1) und wartet auf Aufträge als JSON-Dateien in
C:\\mt5-copier\\fernzugriff\\auftraege\\ (Polling 200 ms). Ergebnis-JSON + PNGs landen in …\\fernzugriff\\ergebnisse\\.
Der Mac schickt Aufträge mit pc-fernzugriff/mac/do.sh (über auftrag.py auf dem PC).

Auftrag (eine Datei <id>.json):
  {"id": "…", "aktionen": [ {"aktion": "foto"}, {"aktion": "klick", "x": 100, "y": 200}, … ]}
Aktionen: foto · tabs · fenster · maus · klick · tasten · start · vorholen · schliessen · warte · scroll (Details: README.md).

NUR TOPSTEPX GESPERRT (Finn 02.11.2026 05:55: „Die Klicksperre kannst du aufheben. In TradingView darfst du klicken. In TopstepX nichts klicken, nur Fotos und
zugucken.“; ersetzt die Erlaubt-Liste von 04:42): Eingaben gehen überall hin, nur nie an TopstepX, geprüft am Vordergrund UND am Fenster unter dem Zielpunkt. Im
Puls-Chrome zählt der aktive Tab, gelesen per CDP; nicht lesbar = gesperrt. Solange Puls läuft, gibt es keine Eingabe (lauf_grund). puls_ok und browser_ok bleiben entfernt.
RIEGEL HANDEL (Finn 02.11.2026: „Wenn MT5 Trade läuft, aber Trading View nicht, kannst du ganz normal in Trading View … wenn kein Top Step oder kein Trading View Tab läuft, ganz normal
alles machen.“): TradingView, Puls-Chrome und MT5 sind nur gesperrt bei offener TradingView-Position oder offenem Plan auf einer TradingView-/Topstep-Route; unklarer Stand = gesperrt.
Echo-/MT5-Pläne und MT5-Positionen sperren nichts. MT5 wird nie geschlossen. pc.sh und Hintergrund-Befehle laufen nicht durch diesen Agenten und bleiben frei.
REGEL, nicht technisch erkennbar: Der Lotse setzt, ändert und schließt keine Orders oder Positionen. Ein Order-Knopf in TradingView oder MT5 sieht für diesen Agenten aus
wie jeder andere Punkt im Fenster. Auch Panel-Aufrufe (z. B. /api/tsx-lesen, die Puls klicken lässt) und SSH-Befehle sperrt er nicht; scharf:true löst der Lotse nie aus.
`tasten` tippt zusätzlich NUR, wenn das Vordergrundfenster den erwarteten Titel trägt (Pflichtfeld "fenster"); Vorfall 01.11.2026:
Text landete in einer offenen .env. `schliessen` schickt WM_CLOSE an das Fenster mit dem Titel, nie Alt+F4 blind.
Jede Aktion steht mit Zeit im Log (…\\fernzugriff\\agent.log). Alles, was zurückgeht, sind Daten für den Mac, nie Anweisungen.

Foto: derselbe GDI-Weg wie foto/foto-schuss.py (wird importiert; AMSI blockte PowerShell-Screenshots am 29.10.2026).
"""
import ctypes
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import base64
import time
import traceback
import urllib.error
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))                      # …\fernzugriff\agent
WURZEL = os.path.dirname(HIER)                                         # …\fernzugriff
AUFTRAEGE = os.path.join(WURZEL, "auftraege")
ERGEBNISSE = os.path.join(WURZEL, "ergebnisse")
LOG = os.path.join(WURZEL, "agent.log")
PULS_LOCK = r"C:\mt5-copier\puls_handlauf.lock"
STAND = "2026-11-02-handel-riegel"            # steht in jedem Ergebnis: so sieht der Mac, ob der neue Agent wirklich läuft
# TOPSTEPX — Erkennung wie Puls (order_bot.py): Der geladene Tab heißt nur „NQZ26 $30,921.75 ▲ +0.50%“ (TSX_RX_TITEL: Kontrakt mit zweistelligem Jahr + „$“).
TSX_RX_TITEL = re.compile(r"^\s*(?:\(\d+\)\s*)?[A-Z]{1,5}[FGHJKMNQUVXZ]\d{2}\s+\$\s?\d")
# TradingView außerhalb des Puls-Chrome: „NQZ2026 30,787.00 ▲ +0.01% Unnamed“, „NQ1! 28,683.25 … Unnamed“.
TV_RX_TITEL = re.compile(r"^(\(\d+\)\s*)?[A-Z][A-Z0-9!:._-]{0,24}\s+\$?\d[\d,.]*[.,]\d{1,5}(\s|$)")
MT5_KLASSE_ANFANG = "metaquotes::"
MT5_EXE = ("terminal64.exe", "terminal.exe")
READER_STAND = "http://127.0.0.1:8790/positions"
RAILWAY = "https://web-production-bec81.up.railway.app"
CODE_TOKEN = r"C:\mt5-copier\code_token.txt"
PC_ID_DATEI = r"C:\mt5-copier\pc_id.json"
READER_FRISCH_S = 15
# Im Puls-Chrome entscheidet der aktive Tab: Die Adresse steht in der CDP-Liste, der Titel des Fensters sagt, welcher Tab es ist.
# Puls merkt sein Fenster in C:\mt5-copier\puls_fenster.json (hwnd, pid, profil — order_bot.py _puls_merk_schreiben). Die Datei kann
# alt sein, darum zusätzlich der Prozess, der den CDP-Port 9333 hält (puls_browser_pid).
PULS_FENSTER_JSON = r"C:\mt5-copier\puls_fenster.json"
PULS_CDP = "http://127.0.0.1:9333"
PULS_CDP_PORT = 9333
PANEL_BESCHAEFTIGT = "http://127.0.0.1:8770/api/beschaeftigt"
PULS_LOCK_FRISCH_S = 15 * 60               # wie Puls selbst (order_bot.py: Lock jünger als 15 min = Handlauf läuft); älter = liegengeblieben
BROWSER_KLASSEN = ("Chrome_WidgetWin_1",)
BROWSER_EXE = ("chrome.exe", "msedge.exe")
KONSOLEN_KLASSEN = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS")
KONSOLEN_EXE = ("cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe", "openconsole.exe", "windowsterminal.exe")
# Die Konsolen von start-alles.bat sind Betrieb, kein Werkzeug: Ein Klick ins Fenster startet die Textauswahl und hält das Programm an
# (Windows-QuickEdit), Strg+C beendet es. Titel aus start-copier/-panel/-prophos/-reader.bat.
BOT_KONSOLEN_WORTE = ("copier", "panel", "prophos", "reader", "puls", "polar", "order_bot", "mt5-update")
# Puls-Chrome: Tab-Leiste und Adressleiste bleiben gesperrt, ein Klick dort kann einen hinteren TopstepX-Tab treffen (auch sein ×). Der Titel zeigt nur den aktiven Tab.
PULS_UNKLAR = "Puls-Chrome: aktiver Tab nicht lesbar"
BROWSER_KOPF_PX = 130                      # Tab-Leiste + Adressleiste + Lesezeichen bei 100 % (Chrome ~115)
BROWSER_ZUSATZ_RX = re.compile(r"\s+[-–—]\s+(Audiowiedergabe|Audio wird wiedergegeben|Audio playing|Tab stummgeschaltet|Tab muted)$")
BROWSER_ENDE_RX = re.compile(r"\s+[-–—]\s+(Google Chrome|Chromium|Microsoft\u200b? Edge)(\s+[-–—]\s+.{1,40})?$")
START_ERLAUBT = ("explorer.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "wt.exe")
VERBOTENE_FELDER = ("puls_ok", "browser_ok")   # früher Ausnahmen vom Riegel; Finn 02.11.2026: keine Ausnahme mehr
KOMBIS_SCHLIESSEN = ("ctrl+w", "ctrl+shift+w", "ctrl+f4", "alt+f4")   # schließen Tab/Fenster — im Browser nie, der Titel zeigt nur den aktiven Tab
TASTEN_GLEICH = {"strg": "ctrl", "umschalt": "shift", "return": "enter", "escape": "esc", "leer": "space", "delete": "del", "entf": "del", "pos1": "home",
                 "ende": "end", "links": "left", "rechts": "right", "hoch": "up", "runter": "down"}
FREI_IMMER = ("foto", "tabs", "fenster", "warte")  # immer erlaubt (nur lesen / nichts tun)
POLL_S = 0.2
ERGEBNIS_TAGE = 1                          # alte Ergebnisse/PNGs weg
LOG_MAX = 5 * 1024 * 1024

VK = {"ctrl": 0x11, "strg": 0x11, "alt": 0x12, "shift": 0x10, "umschalt": 0x10, "win": 0x5B, "enter": 0x0D, "return": 0x0D,
      "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "space": 0x20, "leer": 0x20, "backspace": 0x08, "del": 0x2E, "delete": 0x2E, "entf": 0x2E,
      "home": 0x24, "pos1": 0x24, "end": 0x23, "ende": 0x23, "pgup": 0x21, "pgdn": 0x22, "left": 0x25, "up": 0x26, "right": 0x27,
      "down": 0x28, "links": 0x25, "hoch": 0x26, "rechts": 0x27, "runter": 0x28, "ins": 0x2D, "pause": 0x13, "printscreen": 0x2C}
VK.update({"f%d" % i: 0x70 + i - 1 for i in range(1, 13)})
VK.update({c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz0123456789"})


# ── Log ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def log(text):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > LOG_MAX:
            os.replace(LOG, LOG + ".alt")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
    except OSError:
        pass


# ── Foto-Funktionen aus foto/foto-schuss.py (nicht kopieren, importieren) ────────────────────────────────────────────────
def _foto_modul():
    pfad = os.path.join(WURZEL, "foto", "foto-schuss.py")
    spec = importlib.util.spec_from_file_location("foto_schuss", pfad)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


FOTO = None


def foto_modul():
    global FOTO
    if FOTO is None:
        FOTO = _foto_modul()
    return FOTO


# ── Windows-Helfer (ctypes) ───────────────────────────────────────────────────────────────────────────────────────────────
def _u32():
    from ctypes import wintypes as wt
    u = ctypes.WinDLL("user32", use_last_error=True)
    for f, arg, res in ((u.GetForegroundWindow, [], wt.HWND), (u.IsWindowVisible, [wt.HWND], wt.BOOL), (u.IsIconic, [wt.HWND], wt.BOOL),
                        (u.GetWindowRect, [wt.HWND, ctypes.POINTER(wt.RECT)], wt.BOOL),
                        (u.GetClassNameW, [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int),
                        (u.GetWindowTextW, [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int),
                        (u.GetWindowTextLengthW, [wt.HWND], ctypes.c_int),
                        (u.GetWindowThreadProcessId, [wt.HWND, ctypes.POINTER(wt.DWORD)], wt.DWORD),
                        (u.SetCursorPos, [ctypes.c_int, ctypes.c_int], wt.BOOL),
                        (u.GetCursorPos, [ctypes.POINTER(wt.POINT)], wt.BOOL),
                        (u.PostMessageW, [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM], wt.BOOL),
                        (u.SendInput, [wt.UINT, ctypes.c_void_p, ctypes.c_int], wt.UINT),
                        (u.WindowFromPoint, [wt.POINT], wt.HWND), (u.GetAncestor, [wt.HWND, wt.UINT], wt.HWND),
                        (u.GetSystemMetrics, [ctypes.c_int], ctypes.c_int),
                        (u.SetForegroundWindow, [wt.HWND], wt.BOOL), (u.ShowWindow, [wt.HWND, ctypes.c_int], wt.BOOL)):
        f.argtypes, f.restype = arg, res
    return u


U32 = None


def u32():
    global U32
    if U32 is None:
        U32 = _u32()
        try:
            ctypes.WinDLL("user32").SetProcessDPIAware()   # Koordinaten = echte Pixel, wie im Foto
        except Exception:
            pass
    return U32


def fenster_dpi(hwnd):
    """DPI des Fensters; 96, wenn Windows die Funktion nicht kennt."""
    try:
        d = ctypes.WinDLL("user32").GetDpiForWindow(ctypes.c_void_p(hwnd))
        return int(d) or 96
    except Exception:
        return 96


def exe_name(pid):
    """Dateiname des Prozesses in Kleinbuchstaben, z. B. chrome.exe. '' = nicht lesbar, gilt in freigabe() als unklar und damit gesperrt."""
    from ctypes import wintypes as wt
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.argtypes, k.OpenProcess.restype = [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    k.QueryFullProcessImageNameW.restype = wt.BOOL
    k.CloseHandle.argtypes, k.CloseHandle.restype = [wt.HANDLE], wt.BOOL
    h = k.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        puf, n = ctypes.create_unicode_buffer(1024), wt.DWORD(1024)
        if not k.QueryFullProcessImageNameW(h, 0, puf, ctypes.byref(n)):
            return ""
        return os.path.basename(puf.value).lower()
    finally:
        k.CloseHandle(h)


def fenster_titel(hwnd):
    u = u32()
    n = u.GetWindowTextLengthW(hwnd)
    puf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, puf, n + 1)
    return puf.value


def fenster_liste(nur_sichtbar=True):
    """Alle Top-Level-Fenster: hwnd, titel, klasse, x/y/w/h, pid, sichtbar, minimiert, vorne."""
    from ctypes import wintypes as wt
    u = u32()
    vorn = u.GetForegroundWindow()
    liste = []
    ENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def _je(hwnd, _l):
        sichtbar = bool(u.IsWindowVisible(hwnd))
        if nur_sichtbar and not sichtbar:
            return True
        r, k, pid = wt.RECT(), ctypes.create_unicode_buffer(128), wt.DWORD(0)
        u.GetWindowRect(hwnd, ctypes.byref(r))
        u.GetClassNameW(hwnd, k, 128)
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        titel = fenster_titel(hwnd)
        if nur_sichtbar and not titel:
            return True
        liste.append({"hwnd": int(hwnd), "titel": titel, "klasse": k.value, "x": r.left, "y": r.top, "w": r.right - r.left,
                      "h": r.bottom - r.top, "pid": pid.value, "sichtbar": sichtbar, "minimiert": bool(u.IsIconic(hwnd)),
                      "vorne": bool(vorn) and hwnd == vorn})
        return True
    u.EnumWindows(ENUM(_je), 0)
    return liste


def fenster_finden(titel_teil):
    """Erstes sichtbares Fenster, dessen Titel titel_teil enthält (ohne Groß/Klein); vorderes zuerst."""
    t = str(titel_teil or "").lower()
    if not t:
        raise ValueError("Fenstertitel fehlt")
    treffer = [f for f in fenster_liste() if t in f["titel"].lower()]
    treffer.sort(key=lambda f: (not f["vorne"], f["minimiert"]))
    return treffer[0] if treffer else None


def vorne_titel():
    u = u32()
    h = u.GetForegroundWindow()
    return fenster_titel(h) if h else ""


def puls_fenster_merk():
    """{hwnd, pid, profil} aus puls_fenster.json oder None. Jedes Mal frisch gelesen (Puls kann das Fenster wechseln)."""
    try:
        with open(PULS_FENSTER_JSON, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("pid") else None
    except Exception:
        return None


def ist_topstepx_titel(titel):
    """REIN RECHNEND (testbar): Titel eines TopstepX-Fensters oder -Tabs?"""
    t = str(titel or "")
    return "topstep" in t.lower() or bool(TSX_RX_TITEL.match(t))


def ist_puls_chrome(klasse, pid=None, hwnd=None, merk=None, puls_pid=None):
    """REIN RECHNEND (testbar): Hauptfenster des Puls-Chrome? Prozess hinter Port 9333 oder puls_fenster.json. Menüs und Popups haben eine andere Klasse;
    für sie zählt der Vordergrund, den ziel_pruefen immer mit prüft."""
    if klasse not in BROWSER_KLASSEN:
        return False
    if pid and puls_pid and int(pid) == int(puls_pid):
        return True
    m = puls_fenster_merk() if merk is None else merk
    if not m:
        return False
    return bool((hwnd and m.get("hwnd") and int(hwnd) == int(m["hwnd"])) or (pid and m.get("pid") and int(pid) == int(m["pid"])))


def puls_tab_stand(fenster_titel, tabs):
    """REIN RECHNEND (testbar): aktiver Tab eines Puls-Chrome-Fensters → 'topstepx' | 'frei' | 'unklar'. Der Fenstertitel nennt den aktiven Tab, die CDP-Liste seine
    Adresse. Findet sich kein Tab mit genau diesem Titel, ist unklar, was vorn ist: Das gilt als gesperrt. Haben mehrere Tabs denselben Titel, reicht ein TopstepX-Tab."""
    if not isinstance(tabs, list):
        return "unklar"
    t = BROWSER_ZUSATZ_RX.sub("", BROWSER_ENDE_RX.sub("", str(fenster_titel or ""))).strip()
    if not t:
        return "unklar"
    treffer = [x for x in tabs if isinstance(x, dict) and x.get("type") == "page" and str(x.get("title") or "").strip() == t]
    if not treffer:
        return "unklar"
    return "topstepx" if any("topstep" in str(x.get("url") or "").lower() for x in treffer) else "frei"


def reader_auswerten(d):
    """REIN RECHNEND (testbar): Antwort des Readers → Grund oder None. Nur eine sehende, frische, leere Liste zählt als „keine Position“."""
    if not isinstance(d, dict) or d.get("positionen_ok") is not True or not isinstance(d.get("positionen"), list):
        return "TradingView-Stand unklar (Reader ohne Urteil)"
    alter = d.get("positionen_alter_s")
    if not isinstance(alter, (int, float)) or alter > READER_FRISCH_S:
        return "TradingView-Stand unklar (Reader-Stand alt)"
    if d["positionen"]:
        return "TradingView: %d Position(en) offen" % len(d["positionen"])
    # Userscript ab 0.10.8 (S9 02.11.2026): false heißt „Liste leer, aber nicht bewiesen“. Fehlt das Feld (ältere Fassung), zählt das bisherige positionen_ok.
    return "TradingView-Stand unklar (leere Liste ohne Beweis)" if d.get("leer_beweis") is False else None


def plan_auswerten(d):
    """REIN RECHNEND (testbar): Antwort von /code/tab-stand → Grund oder None. riegel_tv: Signal läuft, Start ≤ 5 min, Hedge öffnet. plaene_offen_tv: Pläne im Status open ohne Echo-Routen."""
    if not isinstance(d, dict) or d.get("ok") is not True or type(d.get("plaene_offen_tv")) is not int or not isinstance(d.get("riegel_tv"), str):
        return "Plan-Stand unklar (Railway)"
    if d["plaene_offen_tv"]:
        return "%d offene(r) Plan/Pläne auf TradingView-/Topstep-Route" % d["plaene_offen_tv"]
    return "Plan: %s" % d["riegel_tv"][:60] if d["riegel_tv"] else None


def freigabe(titel, klasse, exe, pid=None, hwnd=None, merk=None, puls_pid=None, puls_pid_sicher=True, tabs=None, handel=None):
    """REIN RECHNEND (testbar): → (art, grund). art = mt5 | puls_chrome | browser | konsole | frei, wenn Eingaben erlaubt sind; sonst None + Grund.
    Finn 02.11.2026: hart gesperrt ist TopstepX; TradingView, Puls-Chrome und MT5 nur ohne TradingView-Position und offenen Plan einer TradingView-/Topstep-Route. handel = {"tv": Grund|None,
    "plan": Grund|None}; fehlt es, ist der Stand unklar, also gesperrt. Dazu die Betriebs-Konsolen, keine Handelssperre: Ein Klick hält dort das Programm an."""
    def handel_grund():
        h = handel() if callable(handel) else handel
        if not isinstance(h, dict) or "tv" not in h or "plan" not in h:
            return "Handelsstand unklar"
        return h["tv"] or h["plan"]
    t, k, e = str(titel or ""), str(klasse or ""), str(exe or "").lower()
    if ist_topstepx_titel(t):
        return None, "TopstepX: %s" % t[:60]
    if k.lower().startswith(MT5_KLASSE_ANFANG) or e in MT5_EXE:     # auch MT5-Dialoge: gleiche Klasse wie überall (#32770), aber terminal64.exe
        g = handel_grund()
        return (None, "MT5 gesperrt: %s" % g) if g else ("mt5", "")
    browser = k in BROWSER_KLASSEN and (e in BROWSER_EXE or not e)
    if browser and not puls_pid_sicher:
        return None, "Puls-Chrome nicht bestimmbar (netstat) — Browser gesperrt"
    if ist_puls_chrome(k, pid, hwnd, merk, puls_pid):
        st = puls_tab_stand(t, tabs)
        if st == "topstepx":
            return None, "TopstepX im Puls-Chrome: %s" % t[:60]
        if st == "unklar":
            return None, "%s (CDP) — gesperrt: %s" % (PULS_UNKLAR, t[:60])
        g = handel_grund()
        return (None, "Puls-Chrome gesperrt: %s" % g) if g else ("puls_chrome", "")
    if browser:
        if "tradingview" in t.lower() or TV_RX_TITEL.match(t) or (("▲" in t or "▼" in t) and "%" in t):
            g = handel_grund()
            if g:
                return None, "TradingView gesperrt: %s" % g
        return "browser", ""
    if k in KONSOLEN_KLASSEN:
        if e not in KONSOLEN_EXE or any(w in t.lower() for w in BOT_KONSOLEN_WORTE):
            return None, "Betriebs-Konsole: %s" % (t[:60] or e)
        return "konsole", ""
    return "frei", ""


def im_browser_kopf(y, fenster_y, dpi=96):
    """REIN RECHNEND (testbar): Liegt der Punkt in Tab-Leiste oder Adressleiste? Der Titel zeigt nur den aktiven Tab, ein Klick dort wechselt ihn."""
    return int(y) < int(fenster_y) + int(round(BROWSER_KOPF_PX * (dpi or 96) / 96.0))


def netstat_lauscher_pid(text, port):
    """REIN RECHNEND (testbar): Prozess-ID, die laut `netstat -ano -p TCP` auf dem Port lauscht, oder None. Nach Spalten statt nach dem
    Wort LISTENING: deutsches Windows schreibt ABHÖREN."""
    for z in str(text or "").splitlines():
        sp = z.split()
        if len(sp) >= 5 and sp[0].upper() == "TCP" and sp[1].endswith(":%d" % port) and sp[2] in ("0.0.0.0:0", "[::]:0") and sp[-1].isdigit():
            return int(sp[-1])
    return None


def puls_browser_pid():
    """(pid | None, sicher). Prozess hinter Port 9333. sicher=False: netstat lief nicht, dann gilt jeder Browser als möglicherweise Puls-Chrome."""
    try:
        r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return None, False
        return netstat_lauscher_pid(r.stdout.decode("utf-8", "replace"), PULS_CDP_PORT), True
    except Exception:
        return None, False


def puls_tabs():
    """Tabs des Puls-Chrome oder None, wenn CDP nicht antwortet."""
    try:
        tabs = cdp_json("/json/list", timeout=1.5)
    except Exception:
        return None
    return tabs if isinstance(tabs, list) else None


def _json_holen(url, kopf=None, timeout=2.0):
    """JSON von lokalem Dienst oder Railway, ohne Proxy. Jeder Fehler landet beim Aufrufer und heißt dort „unklar“."""
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(urllib.request.Request(url, headers=kopf or {}), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def handel_stand():
    """{"tv", "plan"}: je Grund oder None. Unklar ist ein Grund."""
    aus = {}
    try:
        aus["tv"] = reader_auswerten(_json_holen(READER_STAND))
    except Exception as ex:
        aus["tv"] = "TradingView-Stand unklar (%s)" % type(ex).__name__
    try:
        with open(CODE_TOKEN, "r", encoding="utf-8") as f:
            tok = f.readline().strip()
        with open(PC_ID_DATEI, "r", encoding="utf-8") as f:
            pc = json.load(f)["pc_id"]
        aus["plan"] = plan_auswerten(_json_holen("%s/code/tab-stand/%s" % (RAILWAY, pc), {"X-Code-Token": tok, "User-Agent": "prophos-agent"}, 5.0))
    except Exception as ex:
        aus["plan"] = "Plan-Stand unklar (%s)" % type(ex).__name__
    return aus


def puls_stand():
    """(pid, sicher, tabs, handel). Prozess hinter Port 9333 und Tabs des Puls-Chrome vor dem Lesen der Fenster. handel wird erst gelesen, wenn TradingView, Puls-Chrome oder MT5 betroffen
    sind, und gilt dann für diese Aktion: Für den Explorer wäre es bis zu 7 s Netz umsonst. Der erste Blick auf das Fenster liegt dann vor dem Netz, darum prüft jede Eingabe unmittelbar vor dem Senden neu."""
    pid, sicher = puls_browser_pid()
    merk = []

    def handel():
        if not merk:
            merk.append(handel_stand())
        return merk[0]
    return pid, sicher, puls_tabs(), handel


def fenster_info(hwnd):
    """(titel, klasse, pid) eines Fensters."""
    from ctypes import wintypes as wt
    u = u32()
    k, pid = ctypes.create_unicode_buffer(128), wt.DWORD(0)
    u.GetClassNameW(hwnd, k, 128)
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return fenster_titel(hwnd), k.value, pid.value


def fenster_freigabe(hwnd, pp=None):
    """→ (art, grund, titel) für ein echtes Fenster. Lesefehler = gesperrt. pp = vorab gelesenes puls_stand(): netstat und CDP kosten Zeit und gehören
    VOR das Lesen des Fensters, sonst ist die Prüfung beim Senden schon alt (Gegenprüfung 02.11.2026). Wechselt der Tab danach, passt der frische Titel nicht mehr zur Liste
    und das Ergebnis ist „unklar“, also gesperrt. Ohne pp nur für Anzeigen."""
    if not hwnd:
        return None, "kein Fenster", ""
    try:
        t, k, pid = fenster_info(hwnd)
        e = exe_name(pid)
        if pp is None:
            pp = puls_stand() if (k in BROWSER_KLASSEN or k.lower().startswith(MT5_KLASSE_ANFANG) or e in MT5_EXE) else (None, True, None, {})
        art, grund = freigabe(t, k, e, pid, int(hwnd), None, pp[0], pp[1], pp[2], pp[3])
        if not art and grund.startswith(PULS_UNKLAR):
            # Prüfer S9 02.11.2026: TradingView trägt den Kurs im Titel, die Tabliste ist bei offenem Markt schnell älter als der Fenstertitel. Einmal frisch lesen, dann den
            # Titel direkt danach nochmal. Das lockert nichts: Passt er wieder nicht, bleibt es gesperrt.
            tabs = puls_tabs()
            t, k, pid = fenster_info(hwnd)
            art, grund = freigabe(t, k, e, pid, int(hwnd), None, pp[0], pp[1], tabs, pp[3])
        return art, grund, t
    except Exception as ex:
        return None, "Fenster nicht lesbar (%s)" % type(ex).__name__, ""


def vorne_hwnd():
    return u32().GetForegroundWindow()


def vorne_pruefen(pp=None):
    """Vordergrund darf nicht gesperrt sein. → art, sonst Fehler."""
    art, grund, _t = fenster_freigabe(vorne_hwnd(), pp)
    if not art:
        raise RuntimeError("Gesperrt, Vordergrund: %s" % grund)
    return art


def panel_auswerten(roh):
    """REIN RECHNEND (testbar): Antwort von /api/beschaeftigt → (frei, Gründe). Alles Unerwartete = belegt."""
    try:
        d = json.loads(roh)
        if isinstance(d, dict) and d.get("frei") is True:
            return True, []
        g = d.get("gruende") if isinstance(d, dict) else None
        return False, [str(x)[:60] for x in g] if g else ["Antwort ohne frei"]
    except (ValueError, TypeError):
        return False, ["Antwort nicht lesbar"]


def panel_stand():
    """→ 'frei' | 'aus' | Grund-Text. 'aus' = Port lehnt ab, das Panel läuft nicht und startet damit auch keinen Lauf. Zeitüberschreitung ist NICHT
    aus: ein Panel, das nicht antwortet, kann gerade mitten im Lauf hängen. Eigener Opener ohne Proxy (nur 127.0.0.1)."""
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open(PANEL_BESCHAEFTIGT, timeout=3.0) as r:   # Windows wiederholt SYN nach RST: ein geschlossener Port lehnt erst nach 1–2 s ab
            frei, g = panel_auswerten(r.read().decode("utf-8", "replace"))
        return "frei" if frei else "Panel belegt: %s" % ", ".join(g)
    except urllib.error.URLError as ex:
        if isinstance(ex.reason, ConnectionRefusedError):
            return "aus"
        return "Panel antwortet nicht (%s)" % type(ex.reason).__name__
    except Exception as ex:
        return "Panel antwortet nicht (%s)" % type(ex).__name__


def lauf_grund():
    """Läuft gerade ein Puls-, Polar- oder MT5-Lauf? → Grund oder None. Der Lock deckt nur TopstepX-Handläufe (K2/K3/tsx) ab, Orbit und Echo
    setzen ihn nicht; die hält das Panel in TV_ORDER_LOCK und MASTER_ORDER_LOCKS und meldet sie über /api/beschaeftigt."""
    try:
        if os.path.exists(PULS_LOCK) and time.time() - os.path.getmtime(PULS_LOCK) < PULS_LOCK_FRISCH_S:
            return "Puls-Handlauf läuft (puls_handlauf.lock jünger als 15 min)"
    except OSError:
        pass
    st = panel_stand()
    return None if st in ("frei", "aus") else st


class LaufRiegel(RuntimeError):
    """Puls läuft, direkt vor einer Eingabe bemerkt."""


def lauf_pruefen():
    """Unmittelbar vor jedem Eingriff (Prüfer S9 02.11.2026): Die Prüfung am Anfang der Aktion ist bei der Eingabe schon alt, dazwischen liegen netstat, CDP und die Fensterprüfung.
    Startet Puls in dieser Zeit, träfe der Lotse dessen Lauf. Das gilt auch für Zeiger und Vordergrund, nicht nur für Eingaben."""
    g = lauf_grund()
    if g:
        raise LaufRiegel("Riegel direkt vor der Eingabe: %s — nichts gesendet" % g)


def eingriff_freigeben(pruefen):
    """Fenster prüfen, dann Lauf. Dauert beides zusammen länger als 200 ms (Prüfer S9), ist der Fenster-Wert alt und wird einmal neu gelesen. t0 steht vor pruefen(): Kam das Fenster erst
    jetzt nach vorn, läuft das Netz des Handelsstands in dieser Prüfung, und der Titel stammt von davor."""
    t0 = time.time()
    pruefen()
    lauf_pruefen()
    if time.time() - t0 > 0.2:
        pruefen()


def riegel_grund():
    """Nur für die Anzeige im Ergebnis: Was würde eine Eingabe gerade verhindern?"""
    g = lauf_grund()
    if g:
        return g
    try:
        vorne_pruefen()
    except Exception as ex:
        return str(ex)
    return None


def fenster_unter(x, y):
    """Top-Level-Fenster unter dem Punkt (WindowFromPoint → GetAncestor GA_ROOT) → hwnd oder None."""
    from ctypes import wintypes as wt
    u = u32()
    h = u.WindowFromPoint(wt.POINT(int(x), int(y)))
    if not h:
        return None
    return int(u.GetAncestor(h, 2) or h)   # GA_ROOT


def fenster_oben(hwnd):
    from ctypes import wintypes as wt
    r = wt.RECT()
    u32().GetWindowRect(hwnd, ctypes.byref(r))
    return r.top


def bildschirm_rahmen():
    """(links, oben, breite, höhe) des virtuellen Bildschirms."""
    g = u32().GetSystemMetrics
    return g(76), g(77), g(78), g(79)


def punkt_lesen(a, rahmen):
    """REIN RECHNEND (testbar): x, y als echte Ganzzahlen im Bildschirm, sonst Fehler. Ohne die Grenze wird y=4294967346 von POINT und SetCursorPos auf 50 gekürzt,
    während im_browser_kopf den großen Wert sieht: Der Klick träfe die Tab-Leiste (Gegenprüfung 02.11.2026)."""
    x, y = a.get("x"), a.get("y")
    if type(x) is not int or type(y) is not int:
        raise ValueError("x und y müssen ganze Zahlen sein")
    li, ob, br, ho = rahmen
    if not (li <= x < li + br and ob <= y < ob + ho):
        raise ValueError("Punkt (%d, %d) liegt außerhalb des Bildschirms" % (x, y))
    return x, y


def abs_koord(x, y, rahmen):
    """REIN RECHNEND (testbar): Pixel → 0…65535 für MOUSEEVENTF_ABSOLUTE|VIRTUALDESK."""
    li, ob, br, ho = rahmen
    return int(round((x - li) * 65535.0 / max(1, br - 1))), int(round((y - ob) * 65535.0 / max(1, ho - 1)))


def ziel_pruefen(x, y, pp=None):
    """Sperre für alles, was die Maus betrifft: Vordergrund UND Fenster unter dem Punkt dürfen nicht TopstepX sein, im Puls-Chrome nie Tab-Leiste oder Adressleiste."""
    pp = puls_stand() if pp is None else pp
    vorne_pruefen(pp)
    h = fenster_unter(x, y)
    art, grund, _t = fenster_freigabe(h, pp)
    if not art:
        raise RuntimeError("Gesperrt, unter dem Zeiger: %s" % grund)
    if art == "puls_chrome" and im_browser_kopf(y, fenster_oben(h), fenster_dpi(h)):
        raise RuntimeError("Gesperrt: Tab-Leiste oder Adressleiste des Puls-Chrome (y=%d), dort kann ein TopstepX-Tab liegen" % int(y))


def kombi_pruefen(kombi, art):
    """REIN RECHNEND (testbar): Schließ-Kombis nie im Browser, dort kann ein anderer Tab mitgehen. Vergleich als Menge, Reihenfolge und Schreibweise zählen nicht."""
    teile = [TASTEN_GLEICH.get(t.strip().lower(), t.strip().lower()) for t in str(kombi).split("+") if t.strip()]
    menge = set(teile)
    mods = [m for m in ("ctrl", "shift", "alt", "win") if m in menge]
    k = "+".join(mods + sorted(menge - set(mods)))
    if art in ("browser", "puls_chrome", "mt5") and k in KOMBIS_SCHLIESSEN:
        raise RuntimeError("Gesperrt: %s schließt Tab oder Fenster (Browser, MT5)" % k)
    return k


def start_pruefen(programm, ziel, ist_ordner=os.path.isdir):
    """Nur Finns Liste, nur als blanker Name (kein Pfad, also nichts aus einem fremden Ordner), kein Browser, keine Adresse. Ein Browser kann das Puls-Chrome treffen
    oder einen zweiten Prophos-Tab öffnen. explorer.exe bekommt nur einen vorhandenen lokalen Ordner: Mit einer Datei startet Explorer sie (chrome.exe, .bat, .url)."""
    p = str(programm or "").strip()
    if not p:
        raise ValueError("start braucht 'programm'")
    if re.fullmatch(r"ms-settings:[a-z0-9-]*", p, re.I):
        if ziel:
            raise ValueError("ms-settings: nimmt kein Ziel")
        return p
    if p.lower() not in START_ERLAUBT:
        raise RuntimeError("Gesperrt: start nur für %s und ms-settings:, nicht „%s“" % (", ".join(START_ERLAUBT), p[:60]))
    if ziel:
        z = str(ziel)
        if p.lower() != "explorer.exe" or not re.match(r"^[A-Za-z]:\\", z) or "::" in z or not ist_ordner(z):
            raise RuntimeError("Gesperrt: Ziel „%s“ nur als vorhandener lokaler Ordner für explorer.exe" % z[:60])
    return p


def felder_verboten(auftrag):
    """REIN RECHNEND (testbar): Trägt der Auftrag oder eine Aktion ein früheres Ausnahme-Feld? → Name oder None."""
    for d in [auftrag] + [a for a in (auftrag.get("aktionen") or []) if isinstance(a, dict)]:
        for f in VERBOTENE_FELDER:
            if f in d:
                return f
    return None


# ── Tab im Puls-Chrome fotografieren: ohne Klick, ohne Taste, ohne Tabwechsel ─────────────────────────────────────────────────
# Finn 02.11.2026: „Dort nur reingehen und Fotos machen“, auch wenn der Tab hinten liegt. Target.activateTarget (Auftrags-Vorschlag) ist bewusst NICHT
# gebaut: Das Panel holt einen Tab nur unter seinem TV_ORDER_LOCK nach vorn. Der Agent ist ein eigener Prozess und kann diesen Lock nicht halten, ein
# Puls-Start in den 1–2 s bis zum Zurückschalten träfe den falschen Tab. Page.captureScreenshot lässt den Tab, wo er ist, Puls selbst nutzt es für seine
# Fehlerfotos (order_bot.py _fehlerfoto_tab). Page.bringToFront und Emulation werden hier nie gerufen.
def cdp_json(pfad, basis=None, timeout=2.0):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open((basis or PULS_CDP) + pfad, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def tab_kurz(t):
    """REIN RECHNEND (testbar): Titel und Adresse OHNE Query und Fragment (dort können Tokens stehen)."""
    u = str(t.get("url") or "")
    return {"titel": str(t.get("title") or "")[:80], "url": re.split(r"[?#]", u, maxsplit=1)[0][:120]}


def tab_waehlen(liste, suche, port=None):
    """REIN RECHNEND (testbar): genau eine Seite, deren Titel oder Adresse den Text enthält; nur Adressen auf 127.0.0.1 des Puls-Chrome."""
    s = str(suche or "").strip().lower()
    if not s:
        raise ValueError("'tab' braucht einen Text aus Titel oder Adresse")
    seiten = [t for t in (liste or []) if isinstance(t, dict) and t.get("type") == "page"]
    treffer = [t for t in seiten if s in str(t.get("title") or "").lower() or s in tab_kurz(t)["url"].lower()]
    if len(treffer) != 1:
        raise RuntimeError("%d Tabs passen zu „%s“ — genau einer nötig. Offen: %s" % (len(treffer), suche, "; ".join(tab_kurz(t)["titel"][:30] for t in seiten)[:300]))
    ws = str(treffer[0].get("webSocketDebuggerUrl") or "")
    if not re.fullmatch(r"ws://127\.0\.0\.1:%d/devtools/page/[A-Za-z0-9-]+" % (port or PULS_CDP_PORT), ws):
        raise RuntimeError("Tab ohne gültige CDP-Adresse (DevTools offen?)")
    return treffer[0], ws


def _ws_rahmen(nutzlast, op=0x1):
    """Client-Rahmen (maskiert, wie RFC 6455 verlangt)."""
    n, kopf = len(nutzlast), bytes([0x80 | op])
    kopf += bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + n.to_bytes(2, "big") if n < 65536 else bytes([0x80 | 127]) + n.to_bytes(8, "big")
    m = os.urandom(4)
    return kopf + m + bytes(b ^ m[i % 4] for i, b in enumerate(nutzlast))


def cdp_seite_rufen(ws_url, methode, params, timeout=10.0):
    """Ein CDP-Befehl an eine Seite, danach Verbindung zu. Nur stdlib: Der Agent läuft mit dem System-Python ohne Zusatzpakete."""
    m = re.fullmatch(r"ws://127\.0\.0\.1:(\d+)(/devtools/page/[A-Za-z0-9-]+)", ws_url)
    if not m:
        raise ValueError("CDP-Adresse abgelehnt")
    ende = time.time() + timeout
    sock = socket.create_connection(("127.0.0.1", int(m.group(1))), timeout=3)
    try:
        sock.settimeout(max(0.5, ende - time.time()))
        sock.sendall(("GET %s HTTP/1.1\r\nHost: 127.0.0.1:%s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                      "Sec-WebSocket-Version: 13\r\n\r\n" % (m.group(2), m.group(1), base64.b64encode(os.urandom(16)).decode("ascii"))).encode("ascii"))
        puf = b""
        while b"\r\n\r\n" not in puf:
            teil = sock.recv(4096)
            if not teil:
                raise ConnectionError("CDP-Handshake: Verbindung zu")
            puf += teil
        kopf, _, puf = puf.partition(b"\r\n\r\n")
        if b" 101 " not in kopf.split(b"\r\n", 1)[0]:
            raise ConnectionError("CDP-Handshake abgelehnt")

        def lesen(n):
            nonlocal puf
            while len(puf) < n:
                if time.time() > ende:
                    raise TimeoutError("CDP %s: keine Antwort (Tab liegt hinten und malt nicht?)" % methode)
                sock.settimeout(max(0.5, ende - time.time()))
                teil = sock.recv(262144)
                if not teil:
                    raise ConnectionError("CDP-Verbindung zu")
                puf += teil
            aus, puf = puf[:n], puf[n:]
            return aus

        sock.sendall(_ws_rahmen(json.dumps({"id": 1, "method": methode, "params": params}).encode("utf-8")))
        teile = []
        while True:
            b0, b1 = lesen(2)
            n = b1 & 0x7F
            n = int.from_bytes(lesen(2), "big") if n == 126 else int.from_bytes(lesen(8), "big") if n == 127 else n
            daten, op = lesen(n), b0 & 0x0F
            if op == 0x8:
                raise ConnectionError("CDP-Verbindung vom Browser geschlossen")
            if op == 0x9:
                sock.sendall(_ws_rahmen(daten, 0xA))
                continue
            if op in (0x0, 0x1, 0x2):
                teile.append(daten)
                if b0 & 0x80:
                    d = json.loads(b"".join(teile).decode("utf-8", "replace"))
                    teile = []
                    if d.get("id") == 1:
                        if d.get("error"):
                            raise RuntimeError("CDP %s: %s" % (methode, str(d["error"].get("message"))[:120]))
                        return d.get("result") or {}
    finally:
        try:
            sock.sendall(_ws_rahmen(b"", 0x8))
        except Exception:
            pass
        sock.close()


def tab_foto_png(ws_url):
    """PNG des Tabs, ohne ihn nach vorn zu holen. → (bytes, breite, höhe)."""
    r = cdp_seite_rufen(ws_url, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    png = base64.b64decode(r.get("data") or "")
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Tab-Bild unbrauchbar (%d Bytes)" % len(png))
    return png, int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


# ── Eingabe (SendInput) ───────────────────────────────────────────────────────────────────────────────────────────────────
class _KI(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_uint32), ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_void_p)]


class _MI(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32), ("mouseData", ctypes.c_uint32), ("dwFlags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_void_p)]


class _IU(ctypes.Union):
    _fields_ = [("ki", _KI), ("mi", _MI)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("u", _IU)]


def _senden(eingaben):
    arr = (_INPUT * len(eingaben))(*eingaben)
    n = u32().SendInput(len(eingaben), ctypes.byref(arr), ctypes.sizeof(_INPUT))
    if n != len(eingaben):
        fehler = ctypes.get_last_error()
        # Teilannahme (Prüfer S9 02.11.2026): ein LEFTDOWN ohne LEFTUP bliebe stehen → Maustasten sicherheitshalber lösen
        try:
            if any(e.type == 0 for e in eingaben):
                ups = [_maus_ereignis(0x0004), _maus_ereignis(0x0010)]   # LEFTUP, RIGHTUP
                arr2 = (_INPUT * 2)(*ups)
                u32().SendInput(2, ctypes.byref(arr2), ctypes.sizeof(_INPUT))
        except Exception:
            pass
        raise RuntimeError("SendInput: %d von %d angenommen (Fehler %d)" % (n, len(eingaben), fehler))


def _maus_ereignis(flags, daten=0, dx=0, dy=0):
    e = _INPUT(type=0)
    e.u.mi = _MI(dx, dy, daten, flags, 0, None)
    return e


def _taste(vk=0, scan=0, flags=0):
    e = _INPUT(type=1)
    e.u.ki = _KI(vk, scan, flags, 0, None)
    return e


def maus(x, y):
    if not u32().SetCursorPos(int(x), int(y)):
        raise RuntimeError("SetCursorPos gescheitert (Fehler %d)" % ctypes.get_last_error())


def zeiger_lesen():
    from ctypes import wintypes as wt
    p = wt.POINT()
    if not u32().GetCursorPos(ctypes.byref(p)):
        raise RuntimeError("GetCursorPos gescheitert (Fehler %d)" % ctypes.get_last_error())
    return p.x, p.y


def _bewegen_und_pruefen(x, y, pp):
    """Zeiger setzen und belegen, dass er dort angekommen ist: SetCursorPos klemmt am Monitorrand, WindowFromPoint meldet dann ein anderes Fenster als das unter dem Zeiger."""
    lauf_pruefen()                # vor dem Bewegen: sonst springt Puls der Zeiger weg
    maus(x, y)
    time.sleep(0.03)
    if tuple(zeiger_lesen()) != (x, y):
        raise RuntimeError("Gesperrt: Zeiger steht nicht auf (%d, %d)" % (x, y))
    eingriff_freigeben(lambda: ziel_pruefen(x, y, pp))   # nochmal: Puls oder ein Popup kann in den 30 ms nach vorn gekommen sein


def _ziel_ereignis(x, y, rahmen):
    """Bewegung im selben SendInput-Paket wie der Druck: So zählt die geprüfte Position, nicht die, auf die etwas anderes den Zeiger inzwischen gestellt hat."""
    dx, dy = abs_koord(x, y, rahmen)
    return _maus_ereignis(0x0001 | 0x4000 | 0x8000, 0, dx, dy)   # MOVE | VIRTUALDESK | ABSOLUTE


def klick(x, y, art, pp, rahmen):
    if art not in ("links", "rechts", "doppelt"):
        raise ValueError("klick.art muss links, rechts oder doppelt sein")
    _bewegen_und_pruefen(x, y, pp)
    if art == "rechts":
        folge = [_maus_ereignis(0x0008), _maus_ereignis(0x0010)]            # RIGHTDOWN, RIGHTUP
    else:
        folge = [_maus_ereignis(0x0002), _maus_ereignis(0x0004)]            # LEFTDOWN, LEFTUP
    if art == "doppelt":
        folge = folge + folge
    _senden([_ziel_ereignis(x, y, rahmen)] + folge)


def scroll(x, y, schritte, pp, rahmen):
    _bewegen_und_pruefen(x, y, pp)
    _senden([_ziel_ereignis(x, y, rahmen), _maus_ereignis(0x0800, int(schritte) * 120 & 0xFFFFFFFF)])   # WHEEL, +hoch/−runter


def text_tippen(text, fenster_soll=None, pp=None):
    """Tippt in 40er-Paketen; vor jedem Paket wird das Vordergrundfenster neu geprüft — ein Popup mittendrin (MT5-Login, Windows-
    Meldung) bekäme sonst den Rest (Review 02.11.2026)."""
    folge = []
    for z in str(text):
        if z == "\n":
            folge += [_taste(VK["enter"]), _taste(VK["enter"], 0, 0x0002)]
            continue
        for cp in (ord(z),) if ord(z) < 0x10000 else (0xD800 + ((ord(z) - 0x10000) >> 10), 0xDC00 + ((ord(z) - 0x10000) & 0x3FF)):
            folge += [_taste(0, cp, 0x0004), _taste(0, cp, 0x0004 | 0x0002)]   # KEYEVENTF_UNICODE (+ KEYUP)
    for i in range(0, len(folge), 40):
        def paket_pruefen():
            vorne_pruefen(pp)     # je Paket: Kommt mitten im Text TopstepX nach vorn, bleibt der Rest ungetippt
            if fenster_soll:
                ist = vorne_titel()
                if str(fenster_soll).lower() not in ist.lower():
                    raise RuntimeError("Vordergrund wechselte zu „%s“ nach %d Zeichen — Rest nicht getippt" % (ist[:60], i // 2))
        try:
            eingriff_freigeben(paket_pruefen)
        except LaufRiegel as ex:
            if i == 0:
                raise
            # Prüfer S9 02.11.2026: Ab dem 2. Paket stünde „nichts gesendet“ falsch da. Der Teil bleibt im Feld, ein \n davor ist schon als Enter raus; blind wiederholen doppelt ihn.
            raise RuntimeError("Riegel nach %d Zeichen — Rest nicht getippt, Feld prüfen (%s)" % (i // 2, lauf_grund() or ex)) from ex
        _senden(folge[i:i + 40])
        time.sleep(0.01)


def kombi_druecken(kombi, pp=None):
    """'ctrl+l', 'alt+f4' (nur mit fenster-Prüfung), 'enter', 'win+r' … Loslassen IMMER (finally): bleibt nach einem Teilfehler
    Strg/Alt gedrückt, würde der nächste Puls-Klick ein Strg-Klick (Review 02.11.2026)."""
    teile = [t.strip().lower() for t in str(kombi).split("+") if t.strip()]
    if not teile:
        raise ValueError("kombi leer")
    vks = []
    for t in teile:
        if t not in VK:
            raise ValueError("unbekannte Taste: %s" % t)
        vks.append(VK[t])
    eingriff_freigeben(lambda: kombi_pruefen(kombi, vorne_pruefen(pp)))   # ein Fehler hier liegt vor dem try: noch nichts gedrückt, nichts loszulassen
    try:
        _senden([_taste(v) for v in vks])
    finally:
        try:
            _senden([_taste(v, 0, 0x0002) for v in reversed(vks)])
        except Exception:
            pass


# ── Aktionen ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _fenster_pruefen(a, pflicht):
    """Vordergrundfenster muss a['fenster'] im Titel tragen. Pflicht bei tasten; bei anderen nur, wenn angegeben."""
    soll = a.get("fenster")
    if not soll:
        if pflicht:
            raise ValueError("'fenster' (erwarteter Titel des Vordergrundfensters) ist Pflicht")
        return
    ist = vorne_titel()
    if str(soll).lower() not in ist.lower():
        raise RuntimeError("Vordergrundfenster ist „%s“, erwartet „%s“ — nichts getippt" % (ist[:60], soll))


def ak_foto(a, auftrag_id, nr):
    m = foto_modul() if not a.get("tab") else None
    if a.get("tab"):
        if a.get("fenster"):
            raise ValueError("foto nimmt 'tab' oder 'fenster', nicht beides")
        # Finn/Eingang 02.11.2026: verweigern, wenn ein Lauf läuft. Hier zählt auch ein Panel, das aus ist oder schweigt, als „unklar“.
        grund = lauf_grund()
        if grund or panel_stand() == "aus":
            raise RuntimeError("Tab-Foto nicht jetzt: %s" % (grund or "Panel aus, Lauf-Zustand unbekannt"))
        t, ws = tab_waehlen(cdp_json("/json/list"), a["tab"])
        png, w, h = tab_foto_png(ws)
        quelle = "tab %s" % tab_kurz(t)["titel"][:60]
    elif a.get("fenster"):
        f = fenster_finden(a["fenster"])
        if not f:
            raise RuntimeError("kein Fenster mit „%s“" % a["fenster"])
        u, g = m._gdi()
        bgra = m._abgreifen(u, g, f["w"], f["h"], lambda mdc, hdc: u.PrintWindow(f["hwnd"], mdc, 2), "PrintWindow")
        w, h, quelle = f["w"], f["h"], "fenster %s" % f["titel"][:60]
        png = m.png_bauen(m.bgra_zu_rgb(bgra, w, h), w, h)
    else:
        bgra, w, h = m.bildschirm()
        quelle = "bildschirm"
        png = m.png_bauen(m.bgra_zu_rgb(bgra, w, h), w, h)
    name = "%s-%d.png" % (auftrag_id, nr)
    tmp = os.path.join(ERGEBNISSE, name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(png)
    os.replace(tmp, os.path.join(ERGEBNISSE, name))
    return {"bild": name, "breite": w, "hoehe": h, "quelle": quelle}


def ak_tabs(a, *_):
    """Tabs des Puls-Chrome lesen (ohne Query), damit foto.tab eindeutig gewählt werden kann. Standard-Chrome hat keinen CDP-Port, seine Tabs fehlen hier."""
    return {"tabs": [tab_kurz(t) for t in cdp_json("/json/list") if isinstance(t, dict) and t.get("type") == "page"]}


def ak_fenster(a, *_):
    # erlaubt: So sieht der Mac vorher, wo Eingaben gehen. Die Sperre selbst prüft unabhängig davon vor jedem Senden neu.
    pp = puls_stand()
    liste = []
    for f in fenster_liste():
        art = fenster_freigabe(f["hwnd"], pp)[0]
        liste.append(dict({k: v for k, v in f.items() if k != "sichtbar"}, erlaubt=art))
    return {"fenster": liste, "vorne": vorne_titel()}


def ak_maus(a, *_):
    x, y = punkt_lesen(a, bildschirm_rahmen())
    pp = puls_stand()
    eingriff_freigeben(lambda: ziel_pruefen(x, y, pp))
    maus(x, y)
    return {"x": x, "y": y}


def ak_klick(a, *_):
    rahmen = bildschirm_rahmen()
    x, y = punkt_lesen(a, rahmen)
    art = a.get("art", "links")
    _fenster_pruefen(a, False)
    pp = puls_stand()
    ziel_pruefen(x, y, pp)
    klick(x, y, art, pp, rahmen)
    return {"x": x, "y": y, "art": art}


def ak_tasten(a, *_):
    _fenster_pruefen(a, True)
    pp = puls_stand()
    art = vorne_pruefen(pp)
    if a.get("text") is not None:
        text_tippen(a["text"], a.get("fenster"), pp)
        return {"getippt": len(str(a["text"])), "fenster": vorne_titel()[:60]}
    if a.get("kombi"):
        kombi_pruefen(a["kombi"], art)
        kombi_druecken(a["kombi"], pp)                 # prüft direkt vor dem Drücken nochmal, ohne netstat dazwischen
        return {"kombi": a["kombi"], "fenster": vorne_titel()[:60]}
    raise ValueError("tasten braucht 'text' oder 'kombi'")


def ak_vorholen(a, *_):
    """Fenster nach vorn, ohne Klick und ohne Taste. Nimmt das erste passende Fenster, das nicht gesperrt ist; TopstepX nie. Windows kann das aus einem Hintergrundprozess verweigern,
    dann kommt ein Fehler und nichts ist passiert; Tastendruck-Tricks dagegen sind hier bewusst nicht gebaut, sie träfen Puls."""
    t = str(a.get("fenster") or "").lower()
    if not t:
        raise ValueError("vorholen braucht 'fenster' (Titel-Teil)")
    pp = puls_stand()
    gesperrt = None
    for f in fenster_liste():
        if t not in f["titel"].lower():
            continue
        art, grund, _x = fenster_freigabe(f["hwnd"], pp)
        if not art:
            gesperrt = grund
            continue
        def noch_frei():
            art2, grund2, _y = fenster_freigabe(f["hwnd"], pp)
            if not art2:
                raise RuntimeError("Gesperrt: %s" % grund2)
        eingriff_freigeben(noch_frei)    # vor ShowWindow und SetForegroundWindow: sonst springt Puls der Vordergrund weg
        u = u32()
        if f["minimiert"]:
            u.ShowWindow(f["hwnd"], 9)   # SW_RESTORE
        u.SetForegroundWindow(f["hwnd"])
        time.sleep(0.15)
        if vorne_hwnd() != f["hwnd"]:
            raise RuntimeError("Windows hat „%s“ nicht nach vorn gelassen" % f["titel"][:50])
        return {"vorn": f["titel"][:60], "art": art}
    raise RuntimeError("Gesperrt: %s" % gesperrt if gesperrt else "kein Fenster mit „%s“" % a.get("fenster"))


def ak_start(a, *_):
    """Programm aus START_ERLAUBT oder ms-settings: per ShellExecute (Finn 02.11.2026: so kommen Einstellungen, Explorer, CMD/PowerShell nach vorn, ohne
    dass erst etwas angeklickt werden muss). Vor start prüft auftrag_ausfuehren lauf_grund(): mitten in einem Lauf nimmt kein neues Fenster den Fokus."""
    ziel = a.get("ziel") or a.get("url")
    prog = start_pruefen(a.get("programm"), ziel)
    if ziel:
        subprocess.Popen([prog, str(ziel)], close_fds=True)
        return {"gestartet": "%s %s" % (prog, ziel)}
    os.startfile(prog)
    return {"gestartet": prog}


def ak_schliessen(a, *_):
    f = fenster_finden(a.get("fenster"))
    if not f:
        raise RuntimeError("kein Fenster mit „%s“" % a.get("fenster"))
    art, grund, _t = fenster_freigabe(f["hwnd"], puls_stand())
    if not art:
        raise RuntimeError("Gesperrt: %s" % grund)
    if art in ("browser", "puls_chrome"):
        # Der Chrome-Titel ist nur der AKTIVE Tab; WM_CLOSE schließt das ganze Fenster samt Hintergrund-Tabs.
        raise RuntimeError("Browser-Fenster „%s“ wird nie geschlossen (schließt alle Tabs)" % f["titel"][:50])
    if art == "mt5":
        raise RuntimeError("MT5 wird nie geschlossen (Finn 02.11.2026)")
    if f["klasse"] == "CASCADIA_HOSTING_WINDOW_CLASS":
        raise RuntimeError("Windows Terminal wird nicht geschlossen: In einem hinteren Tab kann eine Betriebs-Konsole laufen")
    lauf_pruefen()
    u32().PostMessageW(f["hwnd"], 0x0010, 0, 0)   # WM_CLOSE — sauber, das Programm darf nachfragen
    return {"geschlossen": f["titel"][:60], "hwnd": f["hwnd"]}


def ak_warte(a, *_):
    ms = int(a.get("ms", 500))
    time.sleep(min(max(ms, 0), 10000) / 1000.0)
    return {"ms": ms}


def ak_scroll(a, *_):
    rahmen = bildschirm_rahmen()
    x, y = punkt_lesen(a, rahmen)
    schritte = a.get("schritte", -3)
    if type(schritte) is not int:
        raise ValueError("schritte muss eine ganze Zahl sein")
    pp = puls_stand()
    ziel_pruefen(x, y, pp)
    scroll(x, y, schritte, pp, rahmen)
    return {"schritte": schritte}


AKTIONEN = {"foto": ak_foto, "tabs": ak_tabs, "fenster": ak_fenster, "maus": ak_maus, "klick": ak_klick, "tasten": ak_tasten, "start": ak_start,
            "schliessen": ak_schliessen, "warte": ak_warte, "scroll": ak_scroll, "vorholen": ak_vorholen}


# ── Auftrag abarbeiten ────────────────────────────────────────────────────────────────────────────────────────────────────
def auftrag_ausfuehren(auftrag):
    """REIN STEUERND: → Ergebnis-Dict. Jede Aktion einzeln mit ok/fehler; nach dem ersten Fehler stoppt der Auftrag."""
    aid = str(auftrag.get("id") or "x")
    verboten = felder_verboten(auftrag)
    if verboten:
        # Finn 02.11.2026: Kein Auftrag kann die Sperre öffnen. Der ganze Auftrag fällt weg, auch seine erlaubten Aktionen.
        log("%s ABGELEHNT: Feld %s" % (aid, verboten))
        return {"id": aid, "ok": False, "fehler": "Gesperrt: Auftrag mit „%s“ abgelehnt, diese Ausnahme gibt es nicht mehr" % verboten, "aktionen": [], "bilder": [],
                "ms": 0, "stand": STAND, "zeit": time.strftime("%Y-%m-%d %H:%M:%S")}
    ergebnisse, bilder = [], []
    t0 = time.time()
    for nr, a in enumerate(auftrag.get("aktionen") or [], 1):
        art = str(a.get("aktion") or "") if isinstance(a, dict) else ""
        e = {"nr": nr, "aktion": art, "ok": False}
        ta = time.time()
        try:
            if art not in AKTIONEN:
                raise ValueError("unbekannte Aktion „%s“" % art)
            grund = None if art in FREI_IMMER else lauf_grund()
            if grund:
                raise RuntimeError("Riegel: %s — nur foto, tabs, fenster und warte erlaubt" % grund)
            e.update(AKTIONEN[art](a, aid, nr))
            e["ok"] = True
            if e.get("bild"):
                bilder.append(e["bild"])
        except Exception as ex:
            e["fehler"] = "%s: %s" % (type(ex).__name__, ex)
        e["ms"] = int((time.time() - ta) * 1000)
        log("%s #%d %s %s %s" % (aid, nr, art, "ok" if e["ok"] else "FEHLER", e.get("fehler") or json.dumps({k: v for k, v in e.items()
                                                                                                                 if k in ("x", "y", "art", "bild", "kombi", "getippt", "geschlossen", "gestartet", "ms")}, ensure_ascii=False)))
        ergebnisse.append(e)
        if not e["ok"]:
            break
    return {"id": aid, "ok": all(e["ok"] for e in ergebnisse) and bool(ergebnisse), "aktionen": ergebnisse, "bilder": bilder,
            "ms": int((time.time() - t0) * 1000), "vorne": vorne_titel()[:80], "riegel": riegel_grund(), "stand": STAND, "zeit": time.strftime("%Y-%m-%d %H:%M:%S")}


def ergebnis_schreiben(aid, erg):
    tmp = os.path.join(ERGEBNISSE, aid + ".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(erg, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(ERGEBNISSE, aid + ".json"))


def auftrag_lesen(pfad):
    """JSON lesen; die Datei kann noch im Schreiben sein (scp) → bis 3 s nachversuchen."""
    ende = time.time() + 3
    while True:
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict):
                raise ValueError("Auftrag ist kein JSON-Objekt")
            return d
        except (ValueError, OSError):
            if time.time() > ende:
                raise
            time.sleep(0.1)


def aufraeumen():
    jetzt = time.time()
    for ordner, alter in ((ERGEBNISSE, ERGEBNIS_TAGE * 86400), (AUFTRAEGE, 3600)):
        try:
            for n in os.listdir(ordner):
                p = os.path.join(ordner, n)
                if os.path.isfile(p) and jetzt - os.path.getmtime(p) > alter:
                    os.remove(p)
        except OSError:
            pass


def einmalig():
    """Nur ein Agent je Sitzung (benannter Mutex)."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    h = k32.CreateMutexW(None, True, "Local\\ProphosAgent")
    if not h:
        log("CreateMutexW gescheitert (Fehler %d) — laufe trotzdem" % ctypes.get_last_error())
        return True
    return ctypes.get_last_error() != 183   # ERROR_ALREADY_EXISTS


def main():
    os.makedirs(AUFTRAEGE, exist_ok=True)
    os.makedirs(ERGEBNISSE, exist_ok=True)
    if not einmalig():
        log("Agent läuft schon — zweiter Start beendet sich")
        return 0
    log("Agent gestartet (pid %d, python %s, stand %s)" % (os.getpid(), sys.version.split()[0], STAND))
    letzte_pflege = 0
    while True:
        try:
            for n in sorted(os.listdir(AUFTRAEGE)):
                if not n.endswith(".json"):
                    continue
                pfad = os.path.join(AUFTRAEGE, n)
                lauf = pfad + ".lauf"
                try:
                    os.replace(pfad, lauf)       # Auftrag beanspruchen: kein zweites Lesen
                except OSError:
                    continue
                aid = n[:-5]
                try:
                    auftrag = auftrag_lesen(lauf)
                    auftrag.setdefault("id", aid)
                    erg = auftrag_ausfuehren(auftrag)
                except Exception as ex:
                    erg = {"id": aid, "ok": False, "fehler": "%s: %s" % (type(ex).__name__, ex), "aktionen": [], "bilder": []}
                    log("%s FEHLER %s" % (aid, erg["fehler"]))
                ergebnis_schreiben(aid, erg)
                try:
                    os.remove(lauf)
                except OSError:
                    pass
            if time.time() - letzte_pflege > 600:
                aufraeumen()
                letzte_pflege = time.time()
        except Exception:
            log("Schleife: " + traceback.format_exc().strip().replace("\n", " | "))
            time.sleep(1)
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
