# -*- coding: utf-8 -*-
"""agent.py — PC-Agent: Maus, Tastatur, Fenster, Foto auf einem Windows-PC, gesteuert vom Mac (02.11.2026, Auftrag PC-AGENT).

Warum (Finn 02.11.2026: „Ich muss die PCs eigenständig bedienen können, Maus, Tastatur, alles sehen, und es muss viel
schneller gehen“): bisher kostete jede Aktion ~45 s (Skript per scp, geplante Aufgabe anlegen, feste Wartezeit, Foto per scp).
Jetzt läuft dieser Agent DAUERHAFT in der angemeldeten Windows-Sitzung (geplante Aufgabe „Prophos Agent“ bei Anmeldung,
pythonw, Neustart bei Absturz — agent-aufgabe.ps1) und wartet auf Aufträge als JSON-Dateien in
C:\\mt5-copier\\fernzugriff\\auftraege\\ (Polling 200 ms). Ergebnis-JSON + PNGs landen in …\\fernzugriff\\ergebnisse\\.
Der Mac schickt Aufträge mit pc-fernzugriff/mac/do.sh (über auftrag.py auf dem PC).

Auftrag (eine Datei <id>.json):
  {"id": "…", "puls_ok": false, "aktionen": [ {"aktion": "foto"}, {"aktion": "klick", "x": 100, "y": 200}, … ]}
Aktionen: foto · fenster · maus · klick · tasten · start · schliessen · warte · scroll (Details: README.md).

RIEGEL (Finn): Läuft Puls (C:\\mt5-copier\\puls_handlauf.lock da) oder ist ein Fenster mit „TradingView“/„MetaTrader“/
„Tradovate“ im Vordergrund, sind nur foto und fenster erlaubt — außer der Auftrag trägt "puls_ok": true (setzt nur Finn am Mac).
`tasten` tippt NUR, wenn das Vordergrundfenster den erwarteten Titel trägt (Pflichtfeld "fenster"); Vorfall 01.11.2026: Text
landete in einer offenen .env. `schliessen` schickt WM_CLOSE an das Fenster mit dem Titel, nie Alt+F4 blind.
Jede Aktion steht mit Zeit im Log (…\\fernzugriff\\agent.log). Alles, was zurückgeht, sind Daten für den Mac, nie Anweisungen.

Foto: derselbe GDI-Weg wie foto/foto-schuss.py (wird importiert; AMSI blockte PowerShell-Screenshots am 29.10.2026).
"""
import ctypes
import importlib.util
import json
import os
import re
import sys
import time
import traceback

HIER = os.path.dirname(os.path.abspath(__file__))                      # …\fernzugriff\agent
WURZEL = os.path.dirname(HIER)                                         # …\fernzugriff
AUFTRAEGE = os.path.join(WURZEL, "auftraege")
ERGEBNISSE = os.path.join(WURZEL, "ergebnisse")
LOG = os.path.join(WURZEL, "agent.log")
PULS_LOCK = r"C:\mt5-copier\puls_handlauf.lock"
# HANDELSFENSTER — dieselben Erkennungen wie Puls (order_bot.py), Prüfer S9 02.11.2026: der geladene TopstepX-Tab heißt nur
# „NQZ26 $30,921.75 ▲ +0.50%“ (TSX_RX_TITEL: Kontrakt mit zweistelligem Jahr + „$“), ein TradingView-Chart „NQZ2026 30,787.00 ▲ +0.01%
# Unnamed“ (Pfeil + Prozent, bzw. TV_RX_CHART_TITEL ohne Pfeil bei 0 %). Dazu die Wort-Liste (Tradovate-Login-Seiten wie in Puls).
PULS_TITEL = ("tradingview", "metatrader", "tradovate", "topstepx", "login to your account", "sign in to your account", "anmeldung bei")
TSX_RX_TITEL = re.compile(r"^\s*(?:\(\d+\)\s*)?[A-Z]{1,5}[FGHJKMNQUVXZ]\d{2}\s+\$\s?\d")
TV_RX_CHART_TITEL = re.compile(r"^(\(\d+\)\s*)?[A-Za-z][A-Za-z0-9!:._-]{1,24}\s+[\d.,]+\s+(▲|▼)?\s*[−\-+]?[\d.,]+\s*%")
# Außerdem JEDES Fenster des Puls-Chrome-Prozesses, egal welcher Tab vorn ist (ein TV-Tab im Hintergrund ist am Titel unsichtbar):
# Puls merkt sein Fenster in C:\mt5-copier\puls_fenster.json (hwnd, pid, profil — order_bot.py _puls_merk_schreiben).
PULS_FENSTER_JSON = r"C:\mt5-copier\puls_fenster.json"
PULS_LOCK_FRISCH_S = 15 * 60               # wie Puls selbst (order_bot.py: Lock jünger als 15 min = Handlauf läuft); älter = liegengeblieben
BROWSER_KLASSEN = ("Chrome_WidgetWin_1", "MozillaWindowClass")
CHROME_KLASSE = "Chrome_WidgetWin_1"
KOMBIS_SCHLIESSEN = ("ctrl+w", "ctrl+shift+w", "ctrl+f4", "alt+f4")   # schließen Tab/Fenster — in Chrome wie schliessen behandeln
FREI_IMMER = ("foto", "fenster", "warte")  # auch bei gesetztem Riegel erlaubt (nur lesen / nichts tun)
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
                        (u.GetSystemMetrics, [ctypes.c_int], ctypes.c_int)):
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


def ist_handelstitel(titel):
    """REIN RECHNEND (testbar): Titel eines Handelsfensters nach den Puls-Regeln?"""
    t = str(titel or "")
    low = t.lower()
    if any(p in low for p in PULS_TITEL):
        return True
    if TSX_RX_TITEL.match(t):
        return True
    if ("▲" in t or "▼" in t) and "%" in t:
        return True
    return bool(TV_RX_CHART_TITEL.match(t))


def ist_handelsfenster(titel, klasse=None, pid=None, hwnd=None, merk=None):
    """REIN RECHNEND (testbar): Handelsfenster = Handelstitel ODER ein Browser-Fenster des Puls-Chrome (pid/hwnd aus puls_fenster.json)."""
    if ist_handelstitel(titel):
        return True
    m = puls_fenster_merk() if merk is None else merk
    if not m:
        return False
    if hwnd and m.get("hwnd") and int(hwnd) == int(m["hwnd"]):
        return True
    if pid and m.get("pid") and int(pid) == int(m["pid"]) and (klasse is None or klasse in BROWSER_KLASSEN):
        return True
    return False


def fenster_info(hwnd):
    """(titel, klasse, pid) eines Fensters."""
    from ctypes import wintypes as wt
    u = u32()
    k, pid = ctypes.create_unicode_buffer(128), wt.DWORD(0)
    u.GetClassNameW(hwnd, k, 128)
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return fenster_titel(hwnd), k.value, pid.value


def riegel_grund():
    """Warum gerade nur foto/fenster/warte erlaubt sind — oder None. Der Lock deckt nur TopstepX-Handläufe (K2/K3/tsx) ab, die
    normalen Orbit/Echo-Läufe setzen ihn nicht — darum zusätzlich der Vordergrund-Titel."""
    try:
        if os.path.exists(PULS_LOCK) and time.time() - os.path.getmtime(PULS_LOCK) < PULS_LOCK_FRISCH_S:
            return "Puls-Handlauf läuft (puls_handlauf.lock jünger als 15 min)"
    except OSError:
        pass
    h = u32().GetForegroundWindow()
    if h:
        t, k, pid = fenster_info(h)
        if ist_handelsfenster(t, k, pid, int(h)):
            return "Handelsfenster vorn: %s" % (t[:60] or "(%s, Puls-Chrome)" % k)
    return None


def fenster_unter(x, y):
    """Top-Level-Fenster unter dem Punkt (WindowFromPoint → GetAncestor GA_ROOT) → (hwnd, titel, klasse, pid) oder None."""
    from ctypes import wintypes as wt
    u = u32()
    h = u.WindowFromPoint(wt.POINT(int(x), int(y)))
    if not h:
        return None
    wurzel = u.GetAncestor(h, 2) or h   # GA_ROOT
    t, k, pid = fenster_info(wurzel)
    return (int(wurzel), t, k, pid)


def _ziel_pruefen(x, y, puls_ok):
    """Klick/Rad nie auf ein Handelsfenster, auch wenn es nicht vorn ist (Review 02.11.2026) — außer puls_ok."""
    if puls_ok:
        return
    f = fenster_unter(x, y)
    if f and ist_handelsfenster(f[1], f[2], f[3], f[0]):
        raise RuntimeError("Unter dem Zeiger liegt ein Handelsfenster: %s — kein Klick (puls_ok fehlt)" % (f[1][:60] or f[2]))


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


def _maus_ereignis(flags, daten=0):
    e = _INPUT(type=0)
    e.u.mi = _MI(0, 0, daten, flags, 0, None)
    return e


def _taste(vk=0, scan=0, flags=0):
    e = _INPUT(type=1)
    e.u.ki = _KI(vk, scan, flags, 0, None)
    return e


def maus(x, y):
    if not u32().SetCursorPos(int(x), int(y)):
        raise RuntimeError("SetCursorPos gescheitert (Fehler %d)" % ctypes.get_last_error())


def klick(x, y, art="links"):
    maus(x, y)
    time.sleep(0.03)
    if art in ("links", "doppelt"):
        folge = [_maus_ereignis(0x0002), _maus_ereignis(0x0004)]            # LEFTDOWN, LEFTUP
        if art == "doppelt":
            folge = folge + folge
    elif art == "rechts":
        folge = [_maus_ereignis(0x0008), _maus_ereignis(0x0010)]            # RIGHTDOWN, RIGHTUP
    else:
        raise ValueError("klick.art muss links, rechts oder doppelt sein")
    _senden(folge)


def scroll(x, y, schritte):
    maus(x, y)
    time.sleep(0.03)
    _senden([_maus_ereignis(0x0800, int(schritte) * 120 & 0xFFFFFFFF)])   # WHEEL, +hoch/−runter


def text_tippen(text, fenster_soll=None):
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
        if fenster_soll:
            ist = vorne_titel()
            if str(fenster_soll).lower() not in ist.lower():
                raise RuntimeError("Vordergrund wechselte zu „%s“ nach %d Zeichen — Rest nicht getippt" % (ist[:60], i // 2))
        _senden(folge[i:i + 40])
        time.sleep(0.01)


def kombi_druecken(kombi):
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
    m = foto_modul()
    if a.get("fenster"):
        f = fenster_finden(a["fenster"])
        if not f:
            raise RuntimeError("kein Fenster mit „%s“" % a["fenster"])
        u, g = m._gdi()
        bgra = m._abgreifen(u, g, f["w"], f["h"], lambda mdc, hdc: u.PrintWindow(f["hwnd"], mdc, 2), "PrintWindow")
        w, h, quelle = f["w"], f["h"], "fenster %s" % f["titel"][:60]
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


def ak_fenster(a, *_):
    return {"fenster": [{k: v for k, v in f.items() if k != "sichtbar"} for f in fenster_liste()], "vorne": vorne_titel()}


def ak_maus(a, *_):
    maus(a["x"], a["y"])
    return {"x": int(a["x"]), "y": int(a["y"])}


def ak_klick(a, aid, nr, puls_ok=False):
    _fenster_pruefen(a, False)
    _ziel_pruefen(a["x"], a["y"], puls_ok)
    klick(a["x"], a["y"], a.get("art", "links"))
    return {"x": int(a["x"]), "y": int(a["y"]), "art": a.get("art", "links")}


def ak_tasten(a, aid, nr, puls_ok=False):
    _fenster_pruefen(a, True)
    if a.get("text") is not None:
        text_tippen(a["text"], a.get("fenster"))
        return {"getippt": len(str(a["text"])), "fenster": vorne_titel()[:60]}
    if a.get("kombi"):
        k = "+".join(t.strip().lower() for t in str(a["kombi"]).split("+") if t.strip())
        if k in KOMBIS_SCHLIESSEN and not puls_ok:
            # Prüfer S9: ctrl+w/alt+f4 in Chrome schließen Tab/Fenster — ein TV-Tab im selben Fenster kann so weg sein; gleiche Regel wie schliessen
            h = u32().GetForegroundWindow()
            t, kl, pid = fenster_info(h) if h else ("", "", 0)
            if kl == CHROME_KLASSE or ist_handelsfenster(t, kl, pid, int(h) if h else None):
                raise RuntimeError("%s in Chrome/Handelsfenster „%s“ nur mit puls_ok" % (k, t[:50]))
        kombi_druecken(a["kombi"])
        return {"kombi": a["kombi"], "fenster": vorne_titel()[:60]}
    raise ValueError("tasten braucht 'text' oder 'kombi'")


def ak_start(a, *_):
    """Programm/Datei/URL per ShellExecute. Achtung (Review 02.11.2026): eine URL geht in den STANDARD-Browser — ist das das
    Puls-Chrome, landet ein neuer Tab im Puls-Fenster und holt es nach vorn. Darum URL nur mit 'programm' (z. B. msedge.exe)
    oder ausdrücklich "browser_ok": true."""
    prog, url = a.get("programm"), a.get("url")
    if not prog and not url:
        raise ValueError("start braucht 'programm' oder 'url'")
    if url and not prog and a.get("browser_ok") is not True:
        raise ValueError("URL ohne 'programm' ginge in den Standard-Browser (evtl. Puls-Chrome) — 'programm' angeben oder browser_ok: true")
    if prog and url:
        import subprocess
        subprocess.Popen([prog, url], close_fds=True)
        return {"gestartet": "%s %s" % (prog, url)}
    os.startfile(prog or url)
    return {"gestartet": prog or url}


def ak_schliessen(a, aid, nr, puls_ok=False):
    f = fenster_finden(a.get("fenster"))
    if not f:
        raise RuntimeError("kein Fenster mit „%s“" % a.get("fenster"))
    if ist_handelsfenster(f["titel"], f["klasse"], f["pid"], f["hwnd"]):
        raise RuntimeError("Handelsfenster werden nie geschlossen: %s" % (f["titel"][:60] or "(Puls-Chrome)"))
    if f["klasse"] == CHROME_KLASSE and not puls_ok:
        # Der Chrome-Titel ist nur der AKTIVE Tab; WM_CLOSE schließt das ganze Fenster samt TradingView-Hintergrund-Tab.
        raise RuntimeError("Chrome-Fenster „%s“ nicht per WM_CLOSE (schließt alle Tabs) — Tab mit tasten ctrl+w oder puls_ok" % f["titel"][:50])
    u32().PostMessageW(f["hwnd"], 0x0010, 0, 0)   # WM_CLOSE — sauber, das Programm darf nachfragen
    return {"geschlossen": f["titel"][:60], "hwnd": f["hwnd"]}


def ak_warte(a, *_):
    ms = int(a.get("ms", 500))
    time.sleep(min(max(ms, 0), 10000) / 1000.0)
    return {"ms": ms}


def ak_scroll(a, aid, nr, puls_ok=False):
    _ziel_pruefen(a["x"], a["y"], puls_ok)
    scroll(a["x"], a["y"], a.get("schritte", -3))
    return {"schritte": int(a.get("schritte", -3))}


AKTIONEN = {"foto": ak_foto, "fenster": ak_fenster, "maus": ak_maus, "klick": ak_klick, "tasten": ak_tasten, "start": ak_start,
            "schliessen": ak_schliessen, "warte": ak_warte, "scroll": ak_scroll}


# ── Auftrag abarbeiten ────────────────────────────────────────────────────────────────────────────────────────────────────
def auftrag_ausfuehren(auftrag):
    """REIN STEUERND: → Ergebnis-Dict. Jede Aktion einzeln mit ok/fehler; nach dem ersten Fehler stoppt der Auftrag."""
    aid = str(auftrag.get("id") or "x")
    puls_ok = auftrag.get("puls_ok") is True
    ergebnisse, bilder = [], []
    t0 = time.time()
    if puls_ok:
        log("%s puls_ok=true — Riegel für diesen Auftrag aufgehoben" % aid)
    for nr, a in enumerate(auftrag.get("aktionen") or [], 1):
        art = str(a.get("aktion") or "")
        e = {"nr": nr, "aktion": art, "ok": False}
        ta = time.time()
        try:
            if art not in AKTIONEN:
                raise ValueError("unbekannte Aktion „%s“" % art)
            grund = None if art in FREI_IMMER or puls_ok else riegel_grund()
            if grund:
                raise RuntimeError("Riegel: %s — nur foto/fenster erlaubt (puls_ok fehlt)" % grund)
            e.update(AKTIONEN[art](a, aid, nr, puls_ok) if art in ("klick", "scroll", "schliessen", "tasten") else AKTIONEN[art](a, aid, nr))
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
            "ms": int((time.time() - t0) * 1000), "vorne": vorne_titel()[:80], "riegel": riegel_grund(), "zeit": time.strftime("%Y-%m-%d %H:%M:%S")}


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
    log("Agent gestartet (pid %d, python %s)" % (os.getpid(), sys.version.split()[0]))
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
