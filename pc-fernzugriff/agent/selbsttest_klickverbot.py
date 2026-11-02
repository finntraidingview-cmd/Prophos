# -*- coding: utf-8 -*-
"""Selbsttest Lotse-Klickverbot (Finn 02.11.2026: „Der Lotse darf auf TopstepX, TradingView, Prop-Firm-Seiten und Orders nichts klicken“).
Läuft ohne Windows: Die Fenster-Abfragen sind Attrappen, _senden und maus zeichnen nur auf. Geprüft wird, dass bei jedem gesperrten Fall
KEIN Eingabe-Ereignis entsteht. Was nur echtes Windows zeigt (SendInput, Klassen und Programme der echten Fenster), steht in README.md.
Aufruf: python3 pc-fernzugriff/agent/selbsttest_klickverbot.py"""
import importlib.util
import json
import os
import sys
import tempfile
from types import SimpleNamespace

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("agent", os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.py"))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

FEHLER = []


def pruefe(name, ok, info=""):
    if not ok:
        FEHLER.append(name)
    print(("ok    " if ok else "ROT   ") + name + (("  " + str(info)) if info and not ok else ""))


# Titel aus dem echten Betrieb
CHROME, KL = "chrome.exe", "Chrome_WidgetWin_1"
MT5K = "MetaQuotes::MetaTrader::5.00"
GESPERRT = [
    ("TopstepX-Tab", "NQZ26 $28,677.00 ▲ +0.50% - Google Chrome", KL, CHROME),
    ("TradingView ohne Prozent", "NQ1! 28,683.25 … Unnamed - Google Chrome", KL, CHROME),
    ("TradingView mit Prozent", "NQZ2026 30,787.00 ▲ +0.01% Unnamed - Google Chrome", KL, CHROME),
    ("MT5 FundedNext", "14348534 - FundedNext-Server 2 - Hedge - FundedNext Ltd", MT5K, "terminal64.exe"),
    ("MT5 nur am Titel", "14348534 - FundedNext-Server 2 - Hedge - FundedNext Ltd", "", ""),
    ("MT5 nur an der Klasse", "488579 - Fusion-Live", MT5K, ""),
    ("MT5-Dialog", "Anmeldung", "#32770", "terminal64.exe"),
    ("Tradovate", "Tradovate - Google Chrome", KL, CHROME),
    ("Tradovate-Login", "Login to your account - Google Chrome", KL, CHROME),
    ("TopstepX Wort", "TopstepX - Google Chrome", KL, CHROME),
    ("harmloser Tab im Browser", "Google - Google Chrome", KL, CHROME),
    ("leerer Browser-Titel", "", KL, CHROME),
    ("neuer Tab", "Neuer Tab - Google Chrome", KL, CHROME),
    ("Prophos als Teilwort", "Prophos Kurs bei Apex - Google Chrome", KL, CHROME),
    ("Prophos plus Fremdtext", "Prophos - TradingView - Google Chrome", KL, CHROME),
    ("Prophos in Firefox", "Prophos - Mozilla Firefox", "MozillaWindowClass", "firefox.exe"),
    ("Electron-App mit Prophos-Titel", "Prophos - Google Chrome", KL, "claude.exe"),
    ("Prophos ohne Programm", "Prophos - Google Chrome", KL, ""),
    ("Editor", "Unbenannt – Editor", "Notepad", "notepad.exe"),
    ("Taskleiste", "", "Shell_TrayWnd", "explorer.exe"),
    ("Desktop", "", "Progman", "explorer.exe"),
    ("Explorer-Klasse, fremdes Programm", "mt5-copier", "CabinetWClass", "evil.exe"),
    ("Konsole des Panels", "Copier-Panel", "ConsoleWindowClass", "cmd.exe"),
    ("Konsole des Copiers", "MT5-Hedge-Copier (alle Master)", "ConsoleWindowClass", "cmd.exe"),
    ("Konsole mit Python", "python", "ConsoleWindowClass", "python.exe"),
    ("App-Rahmen ohne Einstellungen", "Rechner", "ApplicationFrameWindow", "applicationframehost.exe"),
    ("alles leer", "", "", ""),
]
for firma in ("Apex Trader Funding", "Tradeify", "Lucid Trading", "FTMO", "FundedNext", "FundingPips", "The5ers", "The 5ers", "Blue Guardian", "Alpha Capital",
              "FN Futures", "Fusion Markets", "Topstep", "Tradovate", "NinjaTrader", "Rithmic"):
    GESPERRT.append(("Firma " + firma, firma + " - Dashboard - Google Chrome", KL, CHROME))
    pruefe("Handelstitel " + firma, a.ist_handelstitel(firma + " Dashboard"))
for name, t, k, e in GESPERRT:
    art, grund = a.freigabe(t, k, e, 111, 222, {})
    pruefe("gesperrt: " + name, art is None and bool(grund), art)

ERLAUBT = [
    ("Prophos-Tab", "Prophos - Google Chrome", KL, CHROME, "prophos"),
    ("Prophos mit Profil", "Prophos - Google Chrome - Finn", KL, CHROME, "prophos"),
    ("Prophos in Edge", "Prophos - Microsoft\u200b Edge", KL, "msedge.exe", "prophos"),
    ("Explorer", "mt5-copier - Datei-Explorer", "CabinetWClass", "explorer.exe", "explorer"),
    ("Ausführen", "Ausführen", "#32770", "explorer.exe", "explorer"),
    ("cmd", "Administrator: C:\\WINDOWS\\system32\\cmd.exe", "ConsoleWindowClass", "cmd.exe", "konsole"),
    ("PowerShell", "Windows PowerShell", "ConsoleWindowClass", "powershell.exe", "konsole"),
    ("Terminal", "Administrator: Windows PowerShell", "CASCADIA_HOSTING_WINDOW_CLASS", "windowsterminal.exe", "konsole"),
    ("Einstellungen", "Einstellungen", "ApplicationFrameWindow", "applicationframehost.exe", "einstellungen"),
    ("Settings", "Settings", "ApplicationFrameWindow", "applicationframehost.exe", "einstellungen"),
]
for name, t, k, e, soll in ERLAUBT:
    art, grund = a.freigabe(t, k, e, 111, 222, {})
    pruefe("erlaubt: " + name, art == soll, grund)

# Puls-Chrome ist gesperrt, auch wenn gerade der Prophos-Tab vorn ist
P = "Prophos - Google Chrome"
pruefe("Puls-Chrome per Merkdatei (pid)", a.freigabe(P, KL, CHROME, 500, 9, {"pid": 500})[0] is None)
pruefe("Puls-Chrome per Merkdatei (hwnd)", a.freigabe(P, KL, CHROME, 7, 900, {"pid": 500, "hwnd": 900})[0] is None)
pruefe("Puls-Chrome per Port 9333, Merkdatei alt", a.freigabe(P, KL, CHROME, 700, 9, {"pid": 500}, 700)[0] is None)
pruefe("netstat lief nicht: Browser gesperrt", a.freigabe(P, KL, CHROME, 700, 9, {}, None, False)[0] is None)
pruefe("anderes Chrome bleibt frei", a.freigabe(P, KL, CHROME, 700, 9, {"pid": 500}, 800)[0] == "prophos")
NETSTAT = """
Aktive Verbindungen

  Proto  Lokale Adresse         Remoteadresse          Status           PID
  TCP    0.0.0.0:135            0.0.0.0:0              ABHÖREN         1096
  TCP    127.0.0.1:9333         0.0.0.0:0              ABHÖREN         6144
  TCP    127.0.0.1:9333         127.0.0.1:50000        HERGESTELLT     6144
  TCP    127.0.0.1:19333        0.0.0.0:0              ABHÖREN         9
"""
pruefe("netstat: Port 9333 deutsch", a.netstat_lauscher_pid(NETSTAT, 9333) == 6144)
pruefe("netstat: Port 9333 fehlt", a.netstat_lauscher_pid("  TCP    127.0.0.1:19333   0.0.0.0:0   LISTENING   9", 9333) is None)

# Tab-Leiste und Adressleiste
pruefe("Browser-Kopf y=10", a.im_browser_kopf(10, 0))
pruefe("Browser-Kopf y=129", a.im_browser_kopf(129, 0))
pruefe("Seite y=130", not a.im_browser_kopf(130, 0))
pruefe("Browser-Kopf maximiert (y=-8)", a.im_browser_kopf(100, -8))
pruefe("Browser-Kopf bei 150 %", a.im_browser_kopf(190, 0, 144))

# Tasten
for k, art in (("shift+alt+tab", "konsole"), ("umschalt+alt+tab", "konsole"), ("alt+ctrl+tab", "konsole"), ("alt+tab+x", "konsole"), ("ctrl+win+1", "konsole"), ("shift+win+m", "konsole"),
               ("alt+win+1", "konsole"), ("d+win", "explorer"), ("ctrl+win+d", "explorer"), ("win+r", "explorer"), ("ctrl+shift+esc", "explorer"), ("TAB+ALT", "konsole"), ("w+strg", "prophos"),
               ("alt+tab", "konsole"), ("win+d", "explorer"), ("win+m", "explorer"), ("win+1", "konsole"), ("ctrl+esc", "explorer"), ("ctrl+w", "prophos"), ("alt+f4", "prophos"),
               ("ctrl+tab", "prophos"), ("ctrl+1", "prophos"), ("ctrl+l", "prophos"), ("ctrl+t", "prophos"), ("f6", "prophos"), ("ctrl+shift+w", "prophos"), ("ctrl+n", "prophos")):
    try:
        a.kombi_pruefen(k, art)
        pruefe("Kombi gesperrt: %s in %s" % (k, art), False)
    except RuntimeError:
        pruefe("Kombi gesperrt: %s in %s" % (k, art), True)
for k, art in (("enter", "prophos"), ("ctrl+a", "prophos"), ("strg+c", "prophos"), ("return", "prophos"), ("win+e", "konsole"), ("alt+f4", "explorer"), ("ctrl+c", "konsole"), ("f5", "prophos")):
    try:
        a.kombi_pruefen(k, art)
        pruefe("Kombi frei: %s in %s" % (k, art), True)
    except RuntimeError as ex:
        pruefe("Kombi frei: %s in %s" % (k, art), False, ex)

# start
for prog, ziel in (("chrome.exe", None), ("msedge.exe", "https://prophos.pages.dev"), ("terminal64.exe", None), ("https://tradingview.com", None), ("C:\\boese\\cmd.exe", None),
                   ("cmd.exe", "/c dir"), ("explorer.exe", "https://topstepx.com"), ("explorer.exe", "\\\\host\\freigabe"), ("tradingview:", None), ("", None),
                   ("explorer.exe", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"), ("explorer.exe", "C:\\mt5-copier\\puls-chrome-starten.bat"), ("explorer.exe", "calc.exe"),
                   ("explorer.exe", "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}"), ("explorer.exe", "/select,C:\\x"), ("explorer.exe", "C:\\ordner::x")):
    try:
        a.start_pruefen(prog, ziel, lambda z: z in ("C:\\ordner::x",))
        pruefe("start gesperrt: %s %s" % (prog, ziel), False)
    except (RuntimeError, ValueError):
        pruefe("start gesperrt: %s %s" % (prog, ziel), True)
for prog, ziel in (("explorer.exe", "C:\\mt5-copier"), ("cmd.exe", None), ("powershell.exe", None), ("ms-settings:", None), ("ms-settings:network", None)):
    pruefe("start frei: %s" % prog, a.start_pruefen(prog, ziel, lambda z: z == "C:\\mt5-copier") == prog)

# Koordinaten
R = (0, 0, 1920, 1080)
pruefe("Punkt ok", a.punkt_lesen({"x": 300, "y": 400}, R) == (300, 400))
for name, x, y in (("Überlauf y=2^32+50", 300, 4294967346), ("negativ", -5, 10), ("zu groß", 1920, 10), ("Text", "300", 10), ("bool", True, 10), ("Kommazahl", 3.0, 10), ("fehlt", None, 10)):
    try:
        a.punkt_lesen({"x": x, "y": y}, R)
        pruefe("Punkt abgelehnt: " + name, False)
    except ValueError:
        pruefe("Punkt abgelehnt: " + name, True)
pruefe("abs_koord Ecken", a.abs_koord(0, 0, R) == (0, 0) and a.abs_koord(1919, 1079, R) == (65535, 65535))
pruefe("abs_koord zweiter Monitor links", a.abs_koord(-1920, 0, (-1920, 0, 3840, 1080))[0] == 0)
pruefe("Prophos mit Audio-Zusatz", a.freigabe("Prophos - Audio wird wiedergegeben - Google Chrome", KL, CHROME, 1, 2, {})[0] == "prophos")

# Panel-Antwort
pruefe("Panel frei", a.panel_auswerten('{"ok":true,"frei":true,"gruende":[]}')[0] is True)
pruefe("Panel belegt", a.panel_auswerten('{"ok":true,"frei":false,"gruende":["Polar-Lauf"]}') == (False, ["Polar-Lauf"]))
pruefe("Panel Unsinn = belegt", a.panel_auswerten("<html>")[0] is False and a.panel_auswerten('{"frei":"true"}')[0] is False)

# Tab-Wahl
LISTE = [{"type": "page", "title": "NQZ26 $28,677.00", "url": "https://topstepx.com/trade?token=geheim", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/AB-1"},
         {"type": "page", "title": "Prophos", "url": "http://localhost:5000/", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/CD-2"},
         {"type": "iframe", "title": "topstepx", "url": "https://topstepx.com/x", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/EF-3"}]
pruefe("Tab-Wahl eindeutig", a.tab_waehlen(LISTE, "topstepx")[1].endswith("AB-1"))
pruefe("Tab-Liste ohne Token", "geheim" not in json.dumps(a.tab_kurz(LISTE[0])))
for suche, liste, name in (("o", LISTE, "mehrdeutig"), ("fehlt", LISTE, "kein Treffer"),
                           ("x", [{"type": "page", "title": "x", "url": "", "webSocketDebuggerUrl": "ws://evil.example:9333/devtools/page/A"}], "fremder Host"),
                           ("x", [{"type": "page", "title": "x", "url": "", "webSocketDebuggerUrl": ""}], "ohne Adresse")):
    try:
        a.tab_waehlen(liste, suche)
        pruefe("Tab-Wahl lehnt ab: " + name, False)
    except RuntimeError:
        pruefe("Tab-Wahl lehnt ab: " + name, True)

# ── Ablauf: Welt aus Attrappen; bei Sperre darf kein Ereignis entstehen ──
WELT = SimpleNamespace(vorne=1, unter=1, fenster={}, oben=0, gesendet=[], bewegt=[], gestartet=[], lauf=None, panel="frei", cdp_rufe=[], wm=[])
a.vorne_hwnd = lambda: WELT.vorne
a.fenster_unter = lambda x, y: WELT.unter
a.fenster_info = lambda h: WELT.fenster[h][:3]
a.exe_name = lambda pid: next((f[3] for f in WELT.fenster.values() if f[2] == pid), "")
a.puls_browser_pid = lambda: (None, True)
a.puls_fenster_merk = lambda: None
a.fenster_oben = lambda h: WELT.oben
a.fenster_dpi = lambda h: 96
a.bildschirm_rahmen = lambda: (0, 0, 1920, 1080)
a.zeiger_lesen = lambda: WELT.bewegt[-1]
a.vorne_titel = lambda: WELT.fenster.get(WELT.vorne, ("",))[0]
a._senden = lambda ev: WELT.gesendet.append(len(ev))
a.maus = lambda x, y: WELT.bewegt.append((x, y))
a.lauf_grund = lambda: WELT.lauf
a.panel_stand = lambda: WELT.panel
a.log = lambda t: None
a.time.sleep = lambda s: None
a.fenster_finden = lambda t: next(({"hwnd": h, "titel": f[0], "klasse": f[1], "pid": f[2], "vorne": h == WELT.vorne, "minimiert": False, "w": 10, "h": 10}
                                   for h, f in WELT.fenster.items() if str(t).lower() in f[0].lower()), None)
a.u32 = lambda: SimpleNamespace(PostMessageW=lambda h, m, w, l: WELT.wm.append(h))
a.os.startfile = lambda p: WELT.gestartet.append(p)
a.cdp_json = lambda p, basis=None, timeout=2.0: LISTE
a.cdp_seite_rufen = lambda ws, m, p, timeout=10.0: WELT.cdp_rufe.append(m) or {"data": __import__("base64").b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + (900).to_bytes(4, "big") + (600).to_bytes(4, "big")).decode()}
a.ERGEBNISSE = tempfile.mkdtemp(prefix="lotse-test-")
EXPL, PROPH, TV, MT5, BOT = 1, 2, 3, 4, 5
WELT.fenster = {EXPL: ("mt5-copier - Datei-Explorer", "CabinetWClass", 11, "explorer.exe"), PROPH: ("Prophos - Google Chrome", KL, 12, CHROME),
                TV: ("NQ1! 28,683.25 … Unnamed - Google Chrome", KL, 13, CHROME), MT5: ("14348534 - FundedNext-Server 2 - Hedge - FundedNext Ltd", MT5K, 14, "terminal64.exe"),
                BOT: ("Copier-Panel", "ConsoleWindowClass", 15, "cmd.exe")}


def lauf(aktionen, vorne=EXPL, unter=None, **feld):
    WELT.vorne, WELT.unter = vorne, (vorne if unter is None else unter)
    WELT.gesendet, WELT.bewegt, WELT.gestartet, WELT.cdp_rufe, WELT.wm = [], [], [], [], []
    return a.auftrag_ausfuehren(dict({"id": "t", "aktionen": aktionen}, **feld))


KLICK = {"aktion": "klick", "x": 300, "y": 400}
GESPERRTE_AKTIONEN = [("klick", KLICK), ("doppelklick", dict(KLICK, art="doppelt")), ("rechtsklick", dict(KLICK, art="rechts")), ("scroll", {"aktion": "scroll", "x": 300, "y": 400, "schritte": -3}),
                      ("maus", {"aktion": "maus", "x": 300, "y": 400}), ("text", {"aktion": "tasten", "fenster": "", "text": "x"}), ("kombi", {"aktion": "tasten", "fenster": "", "kombi": "enter"})]
for hw, wort in ((TV, "NQ1"), (MT5, "14348534"), (BOT, "Copier-Panel")):
    for name, ak in GESPERRTE_AKTIONEN:
        ak2 = dict(ak, fenster=wort) if ak["aktion"] == "tasten" else ak
        e = lauf([ak2], vorne=hw)
        pruefe("Vordergrund %s: %s kein Ereignis" % (wort, name), e["ok"] is False and not WELT.gesendet and not WELT.bewegt, e)
    for name, ak in GESPERRTE_AKTIONEN[:5]:
        e = lauf([ak], vorne=EXPL, unter=hw)
        pruefe("unter dem Zeiger %s, Explorer vorn: %s kein Ereignis" % (wort, name), e["ok"] is False and not WELT.gesendet and not WELT.bewegt, e)
    e = lauf([{"aktion": "schliessen", "fenster": wort}], vorne=EXPL)
    pruefe("schliessen %s verweigert" % wort, e["ok"] is False and not WELT.wm, e)

# Fenster wechselt NACH der ersten Prüfung: die Nachprüfung direkt vor dem Senden hält es auf
_maus = a.maus


def maus_dann_wechsel(x, y):
    _maus(x, y)
    WELT.vorne = TV


a.maus = maus_dann_wechsel
e = lauf([KLICK], vorne=EXPL)
pruefe("TradingView kommt nach dem Bewegen nach vorn: kein Klick", e["ok"] is False and not WELT.gesendet, e)
a.maus = _maus
_senden = a._senden


def senden_dann_wechsel(ev):
    _senden(ev)
    WELT.vorne = TV


a._senden = senden_dann_wechsel
e = lauf([{"aktion": "tasten", "fenster": "Explorer", "text": "x" * 60}], vorne=EXPL)
pruefe("Handelsfenster mitten im Text: Rest ungetippt", e["ok"] is False and len(WELT.gesendet) == 1, e)
a._senden = _senden

# Erlaubtes geht
pruefe("Klick in Explorer: Bewegung und Druck in einem Paket", lauf([KLICK])["ok"] and WELT.gesendet == [3])
pruefe("Doppelklick in Explorer", lauf([dict(KLICK, art="doppelt")])["ok"] and WELT.gesendet == [5])
pruefe("Rechtsklick gesperrt", lauf([dict(KLICK, art="rechts")])["ok"] is False and not WELT.gesendet)
pruefe("y-Überlauf gesperrt", lauf([{"aktion": "klick", "x": 300, "y": 4294967346}], vorne=PROPH)["ok"] is False and not WELT.gesendet and not WELT.bewegt)

# Zeiger kommt nicht an (am Monitorrand geklemmt)
_z = a.zeiger_lesen
a.zeiger_lesen = lambda: (0, 0)
e = lauf([KLICK])
pruefe("Zeiger geklemmt: kein Klick", e["ok"] is False and not WELT.gesendet, e)
a.zeiger_lesen = _z

# Fenster wechselt WÄHREND netstat: Das Fenster wird erst danach gelesen
_pp = a.puls_browser_pid


def netstat_dann_wechsel():
    WELT.vorne = TV
    return (None, True)


a.puls_browser_pid = netstat_dann_wechsel
for name, ak in (("klick", KLICK), ("kombi", {"aktion": "tasten", "fenster": "", "kombi": "enter"}), ("scroll", {"aktion": "scroll", "x": 300, "y": 400})):
    e = lauf([ak], vorne=PROPH)
    pruefe("Puls-Chrome kommt während netstat nach vorn: %s kein Ereignis" % name, e["ok"] is False and not WELT.gesendet, e)
a.puls_browser_pid = _pp

# netstat läuft einmal je Eingabe, nicht zwischen Prüfung und Senden
ZAEHL, BEIM_SENDEN = [], []
a.puls_browser_pid = lambda: ZAEHL.append(1) or (None, True)
_s = a._senden
a._senden = lambda ev: BEIM_SENDEN.append(len(ZAEHL)) or _s(ev)
lauf([KLICK], vorne=PROPH)
pruefe("netstat genau einmal vor dem Klick", BEIM_SENDEN == [1], BEIM_SENDEN)
a.puls_browser_pid, a._senden = _pp, _s

# vorholen: nur erlaubte Fenster
VORN = []
_u32 = a.u32
_liste = a.fenster_liste
a.fenster_liste = lambda: [{"hwnd": h, "titel": f[0], "klasse": f[1], "pid": f[2], "minimiert": False, "vorne": h == WELT.vorne} for h, f in WELT.fenster.items()]


def _setzen(h):
    VORN.append(h)
    WELT.vorne = h


a.u32 = lambda: SimpleNamespace(SetForegroundWindow=_setzen, ShowWindow=lambda h, c: None, PostMessageW=lambda h, m, w, l: WELT.wm.append(h))
e = lauf([{"aktion": "vorholen", "fenster": "Prophos"}], vorne=TV)
pruefe("vorholen Prophos bei TradingView vorn", e["ok"] and VORN == [PROPH], e)
VORN.clear()
for wort, name in (("NQ1", "TradingView"), ("14348534", "MT5"), ("Copier-Panel", "Betriebs-Konsole"), ("gibtsnicht", "kein Fenster")):
    e = lauf([{"aktion": "vorholen", "fenster": wort}], vorne=EXPL)
    pruefe("vorholen gesperrt: " + name, e["ok"] is False and not VORN, e)
WELT.lauf = "Panel belegt"
pruefe("vorholen im Lauf gesperrt", lauf([{"aktion": "vorholen", "fenster": "Prophos"}], vorne=EXPL)["ok"] is False and not VORN)
WELT.lauf = None
a.u32 = lambda: SimpleNamespace(SetForegroundWindow=lambda h: None, ShowWindow=lambda h, c: None)
e = lauf([{"aktion": "vorholen", "fenster": "Prophos"}], vorne=TV)
pruefe("vorholen: Windows verweigert, Fehler statt Erfolg", e["ok"] is False, e)
a.u32, a.fenster_liste = _u32, _liste

# Windows Terminal wird nicht geschlossen
WELT.fenster[6] = ("Administrator: Windows PowerShell", "CASCADIA_HOSTING_WINDOW_CLASS", 16, "windowsterminal.exe")
e = lauf([{"aktion": "schliessen", "fenster": "Administrator"}], vorne=EXPL)
pruefe("Windows Terminal nicht schliessen", e["ok"] is False and not WELT.wm, e)
del WELT.fenster[6]
pruefe("Text in Explorer", lauf([{"aktion": "tasten", "fenster": "Explorer", "text": "ab"}])["ok"] and WELT.gesendet)
pruefe("Klick in die Prophos-Seite", lauf([KLICK], vorne=PROPH)["ok"] and WELT.gesendet == [3])
e = lauf([{"aktion": "klick", "x": 300, "y": 40}], vorne=PROPH)
pruefe("Klick in die Tab-Leiste von Prophos: gesperrt", e["ok"] is False and not WELT.gesendet, e)
e = lauf([{"aktion": "scroll", "x": 300, "y": 40}], vorne=PROPH)
pruefe("Rad über der Tab-Leiste: gesperrt", e["ok"] is False and not WELT.gesendet, e)
e = lauf([{"aktion": "schliessen", "fenster": "Prophos"}], vorne=PROPH)
pruefe("Browser wird nie geschlossen", e["ok"] is False and not WELT.wm, e)
pruefe("schliessen Explorer geht", lauf([{"aktion": "schliessen", "fenster": "Explorer"}])["ok"] and WELT.wm == [EXPL])

# Ausnahme-Felder fallen ganz weg, auch mit erlaubten Aktionen
for feld in ({"puls_ok": True}, {"puls_ok": False}, {"puls_ok": "true"}, {"browser_ok": True}):
    e = lauf([KLICK, {"aktion": "warte", "ms": 1}], **feld)
    pruefe("Auftrag mit %s abgelehnt" % feld, e["ok"] is False and e["aktionen"] == [] and not WELT.gesendet and "Klickverbot" in e["fehler"], e)
e = lauf([dict(KLICK, puls_ok=True)])
pruefe("puls_ok in der Aktion abgelehnt", e["ok"] is False and e["aktionen"] == [] and not WELT.gesendet, e)
for name, ak in (("ziehen", {"aktion": "ziehen", "x": 1, "y": 1}), ("maus_runter", {"aktion": "maus_runter"})):
    pruefe("unbekannte Aktion %s" % name, lauf([ak])["ok"] is False and not WELT.gesendet)

# Foto, Liste und Warten bleiben überall erlaubt
a.foto_modul = lambda: SimpleNamespace(bildschirm=lambda: (b"", 1, 1), bgra_zu_rgb=lambda b, w, h: b"", png_bauen=lambda r, w, h: b"PNG")
a.ak_fenster = lambda *_: {"fenster": []}
a.AKTIONEN["fenster"] = a.ak_fenster
for hw, wort in ((TV, "TradingView"), (MT5, "MT5")):
    pruefe("Foto bei %s vorn" % wort, lauf([{"aktion": "foto"}], vorne=hw)["ok"] and not WELT.gesendet)
    pruefe("Fensterliste bei %s vorn" % wort, lauf([{"aktion": "fenster"}, {"aktion": "warte", "ms": 1}], vorne=hw)["ok"])
WELT.lauf = "Panel belegt: TV_ORDER_LOCK"
pruefe("Foto bleibt im Lauf", lauf([{"aktion": "foto"}])["ok"])
pruefe("Klick in Explorer im Lauf gesperrt", lauf([KLICK])["ok"] is False and not WELT.gesendet)
pruefe("start im Lauf gesperrt", lauf([{"aktion": "start", "programm": "cmd.exe"}], vorne=TV)["ok"] is False and not WELT.gestartet)

# Tab-Foto: nur captureScreenshot, kein Lauf, kein aktiviertes Fenster
e = lauf([{"aktion": "foto", "tab": "topstepx"}], vorne=TV)
pruefe("Tab-Foto im Lauf verweigert", e["ok"] is False and not WELT.cdp_rufe, e)
WELT.lauf = None
e = lauf([{"aktion": "foto", "tab": "topstepx"}], vorne=TV)
pruefe("Tab-Foto ohne Lauf, TradingView vorn", e["ok"] and e["aktionen"][0]["breite"] == 900 and e["bilder"], e)
pruefe("Tab-Foto ruft nur Page.captureScreenshot", WELT.cdp_rufe == ["Page.captureScreenshot"], WELT.cdp_rufe)
pruefe("Tab-Foto ohne Klick und Taste", not WELT.gesendet and not WELT.bewegt)
WELT.panel = "aus"
pruefe("Tab-Foto bei Panel aus verweigert", lauf([{"aktion": "foto", "tab": "topstepx"}])["ok"] is False and not WELT.cdp_rufe)
WELT.panel = "frei"
pruefe("start cmd bei TradingView vorn ohne Lauf", lauf([{"aktion": "start", "programm": "cmd.exe"}], vorne=TV)["ok"] and WELT.gestartet == ["cmd.exe"])
pruefe("Ergebnis trägt den Stand", lauf([{"aktion": "warte", "ms": 1}])["stand"] == a.STAND)

# Echtes lauf_grund: Lock und Panel (Attrappen oben ersetzt, darum frisch laden)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
with tempfile.NamedTemporaryFile(delete=False) as f:
    b.PULS_LOCK = f.name
pruefe("frischer Lock sperrt", "Handlauf" in (b.lauf_grund() or ""))
os.utime(b.PULS_LOCK, (1, 1))
b.panel_stand = lambda: "frei"
pruefe("alter Lock sperrt nicht", b.lauf_grund() is None)
b.panel_stand = lambda: "aus"
pruefe("Panel aus: kein Lauf", b.lauf_grund() is None)
b.panel_stand = lambda: "Panel antwortet nicht (timeout)"
pruefe("Panel schweigt: gesperrt", b.lauf_grund() is not None)
os.remove(b.PULS_LOCK)

print("\n%s" % ("ALLES GRÜN" if not FEHLER else "%d ROT: %s" % (len(FEHLER), "; ".join(FEHLER))))
sys.exit(1 if FEHLER else 0)
