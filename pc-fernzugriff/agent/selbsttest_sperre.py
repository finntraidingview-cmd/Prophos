# -*- coding: utf-8 -*-
"""Selbsttest Lotse-Sperre (Finn 02.11.2026 05:55: „In TradingView darfst du klicken. In TopstepX nichts klicken, nur Fotos und zugucken.“).
Läuft ohne Windows: Die Fenster-Abfragen sind Attrappen, _senden und maus zeichnen nur auf. Bei jedem gesperrten Fall darf KEIN Eingabe-Ereignis entstehen.
Was nur echtes Windows zeigt (SendInput, echte Fenstertitel gegen die CDP-Liste), steht in README.md. Aufruf: python3 pc-fernzugriff/agent/selbsttest_sperre.py"""
import base64
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


CHROME, KL, MT5K = "chrome.exe", "Chrome_WidgetWin_1", "MetaQuotes::MetaTrader::5.00"
TAB_TSX = {"type": "page", "title": "NQZ26 $28,677.00 ▲ +0.50%", "url": "https://topstepx.com/trade?token=geheim", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/AB-1"}
TAB_TV = {"type": "page", "title": "NQ1! 28,683.25 … Unnamed", "url": "https://de.tradingview.com/chart/", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/CD-2"}
TAB_PRO = {"type": "page", "title": "Prophos", "url": "http://localhost:5000/", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/EF-3"}
TAB_ANMELD = {"type": "page", "title": "Sign in", "url": "https://topstepx.com/login", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/GH-4"}
TABS = [TAB_TSX, TAB_TV, TAB_PRO, TAB_ANMELD]

# ── Titel und Fenster ──
for name, t, k, e in (("TopstepX-Kursitel", "NQZ26 $28,677.00 ▲ +0.50% - Google Chrome", KL, CHROME), ("TopstepX ohne Pfeil", "MNQZ26 $28,677.00", KL, CHROME), ("Wort TopstepX", "TopstepX - Google Chrome", KL, CHROME),
                      ("Wort Topstep im Edge", "Topstep Dashboard - Microsoft Edge", KL, "msedge.exe"), ("Desktop-App", "TopstepX", "App", "topstepx.exe"), ("mit Zähler", "(2) NQZ26 $28,677.00", KL, CHROME),
                      ("Konsole des Panels", "Copier-Panel", "ConsoleWindowClass", "cmd.exe"), ("Konsole des Copiers", "MT5-Hedge-Copier (alle Master)", "ConsoleWindowClass", "cmd.exe"),
                      ("Konsole mit Python", "python", "ConsoleWindowClass", "python.exe")):
    pruefe("gesperrt: " + name, a.freigabe(t, k, e, 111, 222, {})[0] is None)
for name, t, k, e, soll in (("TradingView", "NQ1! 28,683.25 … Unnamed - Google Chrome", KL, CHROME, "browser"), ("TradingView mit Prozent", "NQZ2026 30,787.00 ▲ +0.01% Unnamed - Google Chrome", KL, CHROME, "browser"),
                            ("MT5", "14348534 - FundedNext-Server 2 - Hedge - FundedNext Ltd", MT5K, "terminal64.exe", "frei"), ("MT5-Dialog", "Anmeldung", "#32770", "terminal64.exe", "frei"),
                            ("Prophos", "Prophos - Google Chrome", KL, CHROME, "browser"), ("Apex-Seite", "Apex Trader Funding - Google Chrome", KL, CHROME, "browser"), ("Explorer", "mt5-copier", "CabinetWClass", "explorer.exe", "frei"),
                            ("Taskleiste", "", "Shell_TrayWnd", "explorer.exe", "frei"), ("Chrome-Menü", "", "Chrome_WidgetWin_2", CHROME, "frei"), ("PowerShell", "Windows PowerShell", "ConsoleWindowClass", "powershell.exe", "konsole"),
                            ("Terminal", "Administrator: Windows PowerShell", "CASCADIA_HOSTING_WINDOW_CLASS", "windowsterminal.exe", "konsole"), ("Einstellungen", "Einstellungen", "ApplicationFrameWindow", "applicationframehost.exe", "frei")):
    art, grund = a.freigabe(t, k, e, 111, 222, {})
    pruefe("erlaubt: " + name, art == soll, (art, grund))
pruefe("netstat lief nicht: Browser gesperrt", a.freigabe("Prophos - Google Chrome", KL, CHROME, 700, 9, {}, None, False)[0] is None)

# ── Puls-Chrome: aktiver Tab ──
for name, titel, tabs, soll in (("TradingView", "NQ1! 28,683.25 … Unnamed - Google Chrome", TABS, "frei"), ("Prophos", "Prophos - Google Chrome", TABS, "frei"), ("mit Profil", "Prophos - Google Chrome - Puls", TABS, "frei"),
                                ("mit Audio", "Prophos - Audio wird wiedergegeben - Google Chrome", TABS, "frei"), ("TopstepX nur an der Adresse", "Sign in - Google Chrome", TABS, "topstepx"),
                                ("Titel in keinem Tab", "Hallo - Google Chrome", TABS, "unklar"), ("CDP nicht lesbar", "Prophos - Google Chrome", None, "unklar"), ("leerer Titel", "", TABS, "unklar"), ("Liste leer", "Prophos - Google Chrome", [], "unklar"),
                                ("gleicher Titel, einer TopstepX", "Sign in - Google Chrome", [dict(TAB_ANMELD, url="https://x.example/"), TAB_ANMELD], "topstepx")):
    pruefe("Tab-Stand %s" % name, a.puls_tab_stand(titel, tabs) == soll, a.puls_tab_stand(titel, tabs))
TVT = "NQ1! 28,683.25 … Unnamed - Google Chrome"
pruefe("Puls-Chrome TradingView frei", a.freigabe(TVT, KL, CHROME, 500, 9, {"pid": 500}, None, True, TABS)[0] == "puls_chrome")
pruefe("Puls-Chrome per Port erkannt, Merkdatei alt", a.freigabe(TVT, KL, CHROME, 700, 9, {"pid": 500}, 700, True, TABS)[0] == "puls_chrome")
pruefe("Puls-Chrome per hwnd erkannt", a.freigabe(TVT, KL, CHROME, 7, 900, {"hwnd": 900}, None, True, TABS)[0] == "puls_chrome")
pruefe("Puls-Chrome Adresse TopstepX gesperrt", a.freigabe("Sign in - Google Chrome", KL, CHROME, 500, 9, {"pid": 500}, None, True, TABS)[0] is None)
pruefe("Puls-Chrome CDP weg gesperrt", a.freigabe(TVT, KL, CHROME, 500, 9, {"pid": 500}, None, True, None)[0] is None)
pruefe("Puls-Chrome Menü fällt auf den Vordergrund zurück", a.freigabe("", "Chrome_WidgetWin_2", CHROME, 500, 9, {"pid": 500}, 500, True, TABS)[0] == "frei")
pruefe("anderes Chrome bleibt browser", a.freigabe(TVT, KL, CHROME, 700, 9, {"pid": 500}, 800, True, None)[0] == "browser")
NETSTAT = "  TCP    0.0.0.0:135   0.0.0.0:0   ABHÖREN   1096\n  TCP    127.0.0.1:9333   0.0.0.0:0   ABHÖREN   6144\n  TCP    127.0.0.1:9333   127.0.0.1:50000   HERGESTELLT   6144\n  TCP    127.0.0.1:19333   0.0.0.0:0   ABHÖREN   9\n"
pruefe("netstat: Port 9333", a.netstat_lauscher_pid(NETSTAT, 9333) == 6144)
pruefe("Browser-Kopf", a.im_browser_kopf(129, 0) and not a.im_browser_kopf(130, 0) and a.im_browser_kopf(100, -8) and a.im_browser_kopf(190, 0, 144))

# ── Tasten, start, Punkte, Felder ──
for k, art in (("ctrl+w", "browser"), ("w+strg", "puls_chrome"), ("alt+f4", "browser"), ("ctrl+shift+w", "puls_chrome"), ("f4+ctrl", "browser")):
    try:
        a.kombi_pruefen(k, art)
        pruefe("Kombi gesperrt: %s in %s" % (k, art), False)
    except RuntimeError:
        pruefe("Kombi gesperrt: %s in %s" % (k, art), True)
for k, art in (("enter", "puls_chrome"), ("ctrl+a", "browser"), ("alt+tab", "frei"), ("win+r", "frei"), ("alt+f4", "frei"), ("ctrl+c", "konsole"), ("ctrl+tab", "browser")):
    pruefe("Kombi frei: %s in %s" % (k, art), bool(a.kombi_pruefen(k, art)))
for prog, ziel in (("chrome.exe", None), ("msedge.exe", "https://x"), ("terminal64.exe", None), ("https://topstepx.com", None), ("C:\\boese\\cmd.exe", None), ("explorer.exe", "https://topstepx.com"), ("explorer.exe", "C:\\x\\chrome.exe")):
    try:
        a.start_pruefen(prog, ziel, lambda z: False)
        pruefe("start gesperrt: %s %s" % (prog, ziel), False)
    except (RuntimeError, ValueError):
        pruefe("start gesperrt: %s %s" % (prog, ziel), True)
pruefe("start frei", a.start_pruefen("cmd.exe", None) == "cmd.exe" and a.start_pruefen("explorer.exe", "C:\\mt5-copier", lambda z: True) == "explorer.exe")
R = (0, 0, 1920, 1080)
pruefe("Punkt ok", a.punkt_lesen({"x": 300, "y": 400}, R) == (300, 400))
for name, x, y in (("Überlauf", 300, 4294967346), ("negativ", -5, 10), ("Text", "300", 10), ("bool", True, 10)):
    try:
        a.punkt_lesen({"x": x, "y": y}, R)
        pruefe("Punkt abgelehnt: " + name, False)
    except ValueError:
        pruefe("Punkt abgelehnt: " + name, True)
pruefe("Panel-Antwort", a.panel_auswerten('{"frei":true}')[0] is True and a.panel_auswerten('{"frei":false,"gruende":["Polar-Lauf"]}') == (False, ["Polar-Lauf"]) and a.panel_auswerten("<html>")[0] is False)
pruefe("Tab-Liste ohne Token", "geheim" not in json.dumps(a.tab_kurz(TAB_TSX)))
pruefe("Tab-Wahl", a.tab_waehlen(TABS, "topstepx.com/trade")[1].endswith("AB-1"))

# ── Ablauf mit Attrappen ──
WELT = SimpleNamespace(vorne=1, unter=1, fenster={}, oben=0, gesendet=[], bewegt=[], gestartet=[], lauf=None, panel="frei", cdp_rufe=[], wm=[], tabs=TABS)
a.vorne_hwnd = lambda: WELT.vorne
a.fenster_unter = lambda x, y: WELT.unter
a.fenster_info = lambda h: WELT.fenster[h][:3]
a.exe_name = lambda pid: next((f[3] for f in WELT.fenster.values() if f[2] == pid), "")
a.puls_stand = lambda: (500, True, WELT.tabs)
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
a.fenster_finden = lambda t: next(({"hwnd": h, "titel": f[0], "klasse": f[1], "pid": f[2], "vorne": h == WELT.vorne, "minimiert": False, "w": 10, "h": 10} for h, f in WELT.fenster.items() if str(t).lower() in f[0].lower()), None)
a.u32 = lambda: SimpleNamespace(PostMessageW=lambda h, m, w, l: WELT.wm.append(h))
a.os.startfile = lambda p: WELT.gestartet.append(p)
a.cdp_json = lambda p, basis=None, timeout=2.0: TABS
a.cdp_seite_rufen = lambda ws, m, p, timeout=10.0: WELT.cdp_rufe.append(m) or {"data": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + (900).to_bytes(4, "big") + (600).to_bytes(4, "big")).decode()}
a.ERGEBNISSE = tempfile.mkdtemp(prefix="lotse-test-")
EXPL, PTV, PTSX, PANM, NTSX, MT5, BOT, PROPH = 1, 2, 3, 4, 5, 6, 7, 8
WELT.fenster = {EXPL: ("mt5-copier - Datei-Explorer", "CabinetWClass", 11, "explorer.exe"), PTV: (TVT, KL, 500, CHROME), PTSX: ("NQZ26 $28,677.00 ▲ +0.50% - Google Chrome", KL, 500, CHROME),
                PANM: ("Sign in - Google Chrome", KL, 500, CHROME), NTSX: ("TopstepX - Google Chrome", KL, 12, CHROME), MT5: ("14348534 - FundedNext-Server 2 - Hedge - FundedNext Ltd", MT5K, 14, "terminal64.exe"),
                BOT: ("Copier-Panel", "ConsoleWindowClass", 15, "cmd.exe"), PROPH: ("Prophos - Google Chrome", KL, 16, CHROME)}


def lauf(aktionen, vorne=EXPL, unter=None, **feld):
    WELT.vorne, WELT.unter = vorne, (vorne if unter is None else unter)
    WELT.gesendet, WELT.bewegt, WELT.gestartet, WELT.cdp_rufe, WELT.wm = [], [], [], [], []
    return a.auftrag_ausfuehren(dict({"id": "t", "aktionen": aktionen}, **feld))


KLICK = {"aktion": "klick", "x": 300, "y": 400}
MAUSARTEN = [("klick", KLICK), ("doppelklick", dict(KLICK, art="doppelt")), ("rechtsklick", dict(KLICK, art="rechts")), ("scroll", {"aktion": "scroll", "x": 300, "y": 400}), ("maus", {"aktion": "maus", "x": 300, "y": 400})]
for hw, wort in ((PTSX, "NQZ26"), (PANM, "Sign in"), (NTSX, "TopstepX"), (BOT, "Copier-Panel")):
    for name, ak in MAUSARTEN + [("text", {"aktion": "tasten", "fenster": wort, "text": "x"}), ("kombi", {"aktion": "tasten", "fenster": wort, "kombi": "enter"})]:
        e = lauf([ak], vorne=hw)
        pruefe("Vordergrund %s: %s kein Ereignis" % (wort, name), e["ok"] is False and not WELT.gesendet and not WELT.bewegt, e)
    for name, ak in MAUSARTEN:
        e = lauf([ak], vorne=EXPL, unter=hw)
        pruefe("unter dem Zeiger %s: %s kein Ereignis" % (wort, name), e["ok"] is False and not WELT.gesendet and not WELT.bewegt, e)
    pruefe("schliessen %s verweigert" % wort, lauf([{"aktion": "schliessen", "fenster": wort}], vorne=EXPL)["ok"] is False and not WELT.wm)

# Jetzt erlaubt: TradingView im Puls-Chrome, MT5, Prophos, Rechtsklick
for hw, wort in ((PTV, "TradingView im Puls-Chrome"), (MT5, "MT5"), (PROPH, "Prophos"), (EXPL, "Explorer")):
    pruefe("Klick in %s" % wort, lauf([KLICK], vorne=hw)["ok"] and WELT.gesendet == [3])
    pruefe("Rechtsklick in %s" % wort, lauf([dict(KLICK, art="rechts")], vorne=hw)["ok"] and WELT.gesendet == [3])
    pruefe("Doppelklick in %s" % wort, lauf([dict(KLICK, art="doppelt")], vorne=hw)["ok"] and WELT.gesendet == [5])
pruefe("Text in TradingView", lauf([{"aktion": "tasten", "fenster": "NQ1!", "text": "ab"}], vorne=PTV)["ok"] and WELT.gesendet)
pruefe("tasten nur bei passendem Vordergrund", lauf([{"aktion": "tasten", "fenster": "Explorer", "text": "ab"}], vorne=PTV)["ok"] is False and not WELT.gesendet)
pruefe("tasten ohne fenster abgelehnt", lauf([{"aktion": "tasten", "text": "ab"}], vorne=PTV)["ok"] is False and not WELT.gesendet)
pruefe("Klick Art Unsinn abgelehnt", lauf([dict(KLICK, art="mitte")])["ok"] is False and not WELT.gesendet)
pruefe("y-Überlauf gesperrt", lauf([{"aktion": "klick", "x": 300, "y": 4294967346}], vorne=PTV)["ok"] is False and not WELT.bewegt)
e = lauf([{"aktion": "klick", "x": 300, "y": 40}], vorne=PTV)
pruefe("Tab-Leiste des Puls-Chrome gesperrt", e["ok"] is False and not WELT.gesendet, e)
pruefe("Tab-Leiste eines anderen Chrome frei", lauf([{"aktion": "klick", "x": 300, "y": 40}], vorne=PROPH)["ok"])
pruefe("schliessen Browser nie", lauf([{"aktion": "schliessen", "fenster": "Prophos"}], vorne=PROPH)["ok"] is False and not WELT.wm)
pruefe("ctrl+w im Puls-Chrome gesperrt", lauf([{"aktion": "tasten", "fenster": "NQ1!", "kombi": "ctrl+w"}], vorne=PTV)["ok"] is False and not WELT.gesendet)
pruefe("schliessen Explorer geht", lauf([{"aktion": "schliessen", "fenster": "Explorer"}])["ok"] and WELT.wm == [EXPL])

# CDP fällt aus: Puls-Chrome gesperrt, der Rest nicht
WELT.tabs = None
e = lauf([KLICK], vorne=PTV)
pruefe("CDP aus: Puls-Chrome gesperrt", e["ok"] is False and not WELT.gesendet, e)
pruefe("CDP aus: Explorer geht", lauf([KLICK])["ok"])
WELT.tabs = TABS

# Tab wechselt auf TopstepX, nachdem die Tabliste gelesen wurde: Fenstertitel frisch, TopstepX-Titel gewinnt
_maus = a.maus


def maus_dann_wechsel(x, y):
    _maus(x, y)
    WELT.vorne = WELT.unter = PTSX


a.maus = maus_dann_wechsel
e = lauf([KLICK], vorne=PTV)
pruefe("Puls wechselt nach dem Bewegen auf TopstepX: kein Klick", e["ok"] is False and not WELT.gesendet, e)
a.maus = _maus
_s = a._senden


def senden_dann_wechsel(ev):
    _s(ev)
    WELT.vorne = PTSX


a._senden = senden_dann_wechsel
e = lauf([{"aktion": "tasten", "fenster": "Google Chrome", "text": "x" * 60}], vorne=PTV)
pruefe("TopstepX mitten im Text: Rest ungetippt", e["ok"] is False and len(WELT.gesendet) == 1, e)
a._senden = _s
a.zeiger_lesen, _z = (lambda: (0, 0)), a.zeiger_lesen
pruefe("Zeiger geklemmt: kein Klick", lauf([KLICK])["ok"] is False and not WELT.gesendet)
a.zeiger_lesen = _z

# Puls läuft: nur foto, tabs, fenster, warte
a.foto_modul = lambda: SimpleNamespace(bildschirm=lambda: (b"", 1, 1), bgra_zu_rgb=lambda b, w, h: b"", png_bauen=lambda r, w, h: b"PNG")
a.AKTIONEN["fenster"] = lambda *_: {"fenster": []}
WELT.lauf = "Panel belegt: TV_ORDER_LOCK"
pruefe("Lauf: Foto geht", lauf([{"aktion": "foto"}, {"aktion": "warte", "ms": 1}, {"aktion": "fenster"}], vorne=PTSX)["ok"])
for name, ak in (("klick", KLICK), ("start", {"aktion": "start", "programm": "cmd.exe"}), ("tasten", {"aktion": "tasten", "fenster": "Explorer", "text": "x"}), ("schliessen", {"aktion": "schliessen", "fenster": "Explorer"})):
    pruefe("Lauf: %s gesperrt, auch im Explorer" % name, lauf([ak])["ok"] is False and not WELT.gesendet and not WELT.gestartet and not WELT.wm)
e = lauf([{"aktion": "foto", "tab": "topstepx.com/trade"}], vorne=PTV)
pruefe("Lauf: Tab-Foto verweigert", e["ok"] is False and not WELT.cdp_rufe, e)
WELT.lauf = None
e = lauf([{"aktion": "foto", "tab": "topstepx.com/trade"}], vorne=PTV)
pruefe("Tab-Foto TopstepX ohne Klick", e["ok"] and WELT.cdp_rufe == ["Page.captureScreenshot"] and not WELT.gesendet, e)
pruefe("Foto bei TopstepX vorn", lauf([{"aktion": "foto"}], vorne=PTSX)["ok"] and not WELT.gesendet)

# Ausnahme-Felder bleiben verboten
for feld in ({"puls_ok": True}, {"puls_ok": False}, {"browser_ok": True}):
    e = lauf([KLICK], **feld)
    pruefe("Auftrag mit %s abgelehnt" % feld, e["ok"] is False and e["aktionen"] == [] and not WELT.gesendet, e)
pruefe("puls_ok in der Aktion abgelehnt", lauf([dict(KLICK, puls_ok=True)])["ok"] is False and not WELT.gesendet)
pruefe("unbekannte Aktion", lauf([{"aktion": "ziehen", "x": 1, "y": 1}])["ok"] is False and not WELT.gesendet)
pruefe("Ergebnis trägt den Stand", lauf([{"aktion": "warte", "ms": 1}])["stand"] == a.STAND)

# vorholen: TopstepX nie, TradingView ja
VORN = []
a.fenster_liste = lambda: [{"hwnd": h, "titel": f[0], "klasse": f[1], "pid": f[2], "minimiert": False, "vorne": h == WELT.vorne} for h, f in WELT.fenster.items()]


def _setzen(h):
    VORN.append(h)
    WELT.vorne = h


a.u32 = lambda: SimpleNamespace(SetForegroundWindow=_setzen, ShowWindow=lambda h, c: None)
pruefe("vorholen TradingView", lauf([{"aktion": "vorholen", "fenster": "NQ1!"}])["ok"] and VORN == [PTV])
VORN.clear()
pruefe("vorholen TopstepX gesperrt", lauf([{"aktion": "vorholen", "fenster": "NQZ26"}])["ok"] is False and not VORN)

# Echtes lauf_grund: Lock und Panel
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
with tempfile.NamedTemporaryFile(delete=False) as f:
    b.PULS_LOCK = f.name
pruefe("frischer Lock sperrt", "Handlauf" in (b.lauf_grund() or ""))
os.utime(b.PULS_LOCK, (1, 1))
b.panel_stand = lambda: "frei"
pruefe("alter Lock sperrt nicht", b.lauf_grund() is None)
b.panel_stand = lambda: "Panel antwortet nicht (timeout)"
pruefe("Panel schweigt: gesperrt", b.lauf_grund() is not None)
os.remove(b.PULS_LOCK)

print("\n%s" % ("ALLES GRÜN" if not FEHLER else "%d ROT: %s" % (len(FEHLER), "; ".join(FEHLER))))
sys.exit(1 if FEHLER else 0)
