#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order-Bot — platziert die MASTER-Order per SICHTBARER Maus-/Tastatur-Steuerung
(15.08.2026, Finns Ansage: die Order muss serverseitig wie ein Handklick
aussehen — eine API-Order traegt die Expert-Markierung, ein echter Klick nicht).

Choreografie (sichtbar, wie mit Finn geuebt):
  1. Maus faehrt in die Taskleiste und klickt den Terminal-Tab
  2. Fenster-Guard: Titelzeile MUSS die Kontonummer tragen, sonst Abbruch
  3. F9 -> Order-Dialog, Symbol waehlen, Volumen ECHT eintippen (Tastatur-
     Events, kein set_text — s. _feld_tippen) und zuruecklesen
  4. Maus faehrt auf den Buy/Sell-Knopf und klickt — der einzige unumkehrbare Schritt
  5. Bestaetigung NICHT der UI glauben: Positionsliste des Kontos (nur LESEND
     ueber die MetaTrader5-API — Lesen traegt keine Order-Markierung)
  6. SL/TP vom ECHTEN Einstiegskurs rechnen und PER KLICK im Aendern-Dialog
     der Position eintragen (18.08.2026, Finns Ansage: auch die SL/TP-Aenderung
     muss wie Handarbeit aussehen — der fruehere TRADE_ACTION_SLTP-Weg lief
     ueber denselben API-Kanal wie ein EA, unnoetiges Restrisiko). Bestaetigt
     wird auch das nur LESEND am Positionsstand.

Die API wird ausschliesslich LESEND benutzt: aktueller Kurs fuer die
$->Preis-Umrechnung, Positionsstand vorher/nachher, SL/TP-Kontrolle.
mt5.order_send existiert in dieser Datei bewusst NICHT.

Aufruf (vom Panel als kurzlebiger Subprozess):
  python order_bot.py <config-datei.json> "<befehl-json>"
  python order_bot.py inspect <config-datei.json>     (Dialog-Dump, platziert nichts)
  python order_bot.py tvorder "<befehl-json>"         (Orbit: Order auf TradingView)
Befehl:  {"symbol": "NDX100", "richtung": "buy", "volumen": 0.2,
          "sl_usd": 100, "tp_usd": 300}
Antwort: EINE JSON-Zeile auf stdout.

retry_ok-Regel: True nur, solange sicher NICHTS gesendet wurde (jeder Abbruch
VOR dem Buy/Sell-Klick). Nach dem Klick ist jede Unsicherheit retry_ok=False —
'erst im Terminal nachsehen, nie blind wiederholen'.
"""

import json
import math
import os
import random
import re
import sys
import time


# ---------------------------------------------------------------------------
# REIN RECHNENDE Funktionen — ohne Windows/MetaTrader testbar (selftest.py)
# ---------------------------------------------------------------------------

def pruefe_befehl(cmd):
    """Liste von Fehlertexten; leer = Befehl ok."""
    fehler = []
    if not isinstance(cmd, dict):
        return ["Befehl ist kein JSON-Objekt."]
    if str(cmd.get("aktion") or "").lower() == "close":
        # Close-Befehl (28.08.2026, Remote-Close): braucht NUR Ticket + Symbol —
        # Richtung/Volumen/SL/TP gehoeren zur Eroeffnung. Eigener Zweig, damit
        # ein Close nie durch die Order-Pflichtfelder rutscht (und umgekehrt
        # ein alter Bot-Build den unbekannten Befehl an genau diesen Feldern
        # sauber ablehnt, statt etwas zu raten).
        try:
            if int(cmd.get("ticket") or 0) <= 0:
                fehler.append("ticket fehlt oder <= 0")
        except (TypeError, ValueError):
            fehler.append("ticket ist keine Zahl")
        if not str(cmd.get("symbol") or "").strip():
            fehler.append("symbol fehlt")
        return fehler
    if not str(cmd.get("symbol") or "").strip():
        fehler.append("symbol fehlt")
    if str(cmd.get("richtung") or "").lower() not in ("buy", "sell"):
        fehler.append("richtung muss buy oder sell sein")
    try:
        v = float(cmd.get("volumen") or 0)
        # isfinite deckt NaN und Infinity ab ('nan <= 0' waere still False)
        if not math.isfinite(v) or v <= 0:
            fehler.append("volumen fehlt oder <= 0")
    except (TypeError, ValueError):
        fehler.append("volumen ist keine Zahl")
    # SL/TP sind OPTIONAL (18.08.2026, Schalter im Order-Popup): beide gesetzt
    # -> Bot traegt sie nach dem Fill per Klick ein; beide leer -> Order pur,
    # SL/TP macht Finn von Hand. NUR EINES gesetzt ist ein Fehler.
    gesetzt = {}
    for k in ("sl_usd", "tp_usd"):
        roh = cmd.get(k)
        if roh in (None, "", 0, "0"):
            gesetzt[k] = False
            continue
        gesetzt[k] = True
        try:
            v = float(roh)
            if not math.isfinite(v) or v <= 0:
                fehler.append(f"{k} <= 0 oder keine Zahl")
        except (TypeError, ValueError):
            fehler.append(f"{k} ist keine Zahl")
    if gesetzt.get("sl_usd") != gesetzt.get("tp_usd"):
        fehler.append("sl_usd und tp_usd nur ZUSAMMEN setzen (oder beide weglassen)")
    return fehler


def fmt_preis(x, digits):
    """Preis mit PUNKT als Dezimaltrenner — MT5-Eingabefelder erwarten den Punkt
    unabhaengig von der Windows-Sprache."""
    return f"{float(x):.{int(digits)}f}"


def berechne_sl_tp(richtung, ref_preis, volumen, contract_size, sl_usd, tp_usd, digits=2):
    """$-Betraege -> absolute Preise. 1.0 Preis-Einheit ist volumen*contract_size
    wert (Index-CFD in USD) — dieselbe Basis wie die Exposure-Formel im Copier."""
    ref = float(ref_preis)
    je_einheit = float(volumen) * float(contract_size)
    if je_einheit <= 0:
        raise ValueError("volumen*contract_size muss > 0 sein")
    kauf = str(richtung).lower() == "buy"
    d_sl = float(sl_usd) / je_einheit
    d_tp = float(tp_usd) / je_einheit
    sl = round(ref - d_sl if kauf else ref + d_sl, int(digits))
    tp = round(ref + d_tp if kauf else ref - d_tp, int(digits))
    return sl, tp


def finde_neue_position(vorher_tickets, positionen, symbol, richtung, volumen, tol=0.005):
    """Die frisch platzierte Position wiederfinden: neues Ticket, richtiges
    Symbol, richtige Richtung, Volumen im Toleranzfenster (Lot-Raster)."""
    will_typ = 0 if str(richtung).lower() == "buy" else 1
    for p in positionen:
        if p["ticket"] in vorher_tickets:
            continue
        if p["symbol"] != symbol or p["typ"] != will_typ:
            continue
        if abs(p["volumen"] - float(volumen)) <= tol:
            return p
    return None


def ist_aendern_knopf(text):
    """Erkennt den Aendern-Knopf des Positions-Dialogs an der Beschriftung —
    und schliesst alles aus, was loeschen/schliessen/abbrechen koennte. Reine
    Textlogik, damit der Mac-Selbsttest sie abdeckt."""
    t = (text or "").strip().lower()
    if not t:
        return False
    for verboten in ("abbre", "cancel", "schlie", "close", "delet", "loesch", "lösch"):
        if verboten in t:
            return False
    return any(k in t for k in ("ändern", "aendern", "modify", "change"))


def ist_bestaetigen_knopf(text):
    """Der LANGE Bestaetigen-Knopf des Aendern-Dialogs — NICHT der 'Position
    aendern'-Reiter links (Fund 18.08.2026: ist_aendern_knopf traf im UI-Baum
    zuerst den Reiter, der Bot drueckte bei jedem Lauf brav den Reiter statt
    zu bestaetigen — Dialog blieb wirkungslos offen und wurde verworfen).
    Der Bestaetigen-Knopf traegt die Order-Daten in der Beschriftung:
    '#<Ticket> buy 1 NAS100 ... sl: ... tp: ... aendern'."""
    t = (text or "").strip().lower()
    if not ist_aendern_knopf(t):
        return False
    if t in ("position ändern", "position aendern", "modify position"):
        return False
    return ("#" in t or "sl:" in t or "tp:" in t
            or bool(re.search(r"(?<!\d)\d{7,}(?!\d)", t)))


def sltp_bestaetigt(pos_sl, pos_tp, sl, tp, digits):
    """Traegt die Position die gewuenschten SL/TP? Toleranz: 1.5 Einheiten der
    letzten Kursstelle (Server normalisieren minimal). 0.0 heisst 'nicht
    gesetzt' und faellt damit automatisch durch."""
    tol = 1.5 * (10 ** -int(digits))
    return (abs(float(pos_sl) - float(sl)) <= tol
            and abs(float(pos_tp) - float(tp)) <= tol)


def zahl_gleich(text, wert, tol=1e-9):
    """Zeigt der ZURUECKGELESENE Feldtext wirklich den getippten Wert? Vergleich
    als Zahl, nicht als String — MT5 formatiert um ('2' -> '2.00') und kann je
    nach Windows-Locale Komma/Leerzeichen einstreuen."""
    try:
        a = float(str(text).strip().replace(" ", "").replace(",", "."))
        b = float(str(wert).strip().replace(",", "."))
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= tol * max(1.0, abs(b)) + 1e-12


def zeile_nennt_ticket(text, ticket):
    """Steht die Ticket-Nummer als eigenstaendige Zahl im Element-Text? So wird
    die Zeile der Position in der Handel-Liste erkannt, ohne dass 9123456789
    faelschlich auf 123456789 passt."""
    return bool(re.search(r"(?<!\d)" + re.escape(str(int(ticket))) + r"(?!\d)",
                          text or ""))


def ist_handelszeile(text, symbol):
    """Sieht der UIA-Text wie eine Zeile der HANDEL-Liste aus? Symbol UND
    buy/sell muessen drinstehen. Fund 18.08.2026: der .54-Filter (Symbol plus
    Mindestlaenge) traf auch den Chart-Titel ('NAS100,M1: US Tech 100 Index')
    und den Navigator-Eintrag ('ProphosHedgeReader - NAS100,M1') — der
    Doppelklick darauf oeffnete den EA-Eigenschaften-Dialog. Beide tragen
    nie buy/sell."""
    t = (text or "").lower()
    return bool(symbol) and symbol.lower() in t and ("buy" in t or "sell" in t)


def ist_close_menuepunkt(text):
    """Der EINE Kontextmenue-Punkt, den der Close-Weg klicken darf (28.08.2026,
    Remote-Close). Bisher war 'Position schliessen' der Eintrag, den der Bot
    NIEMALS treffen durfte (.57: blinde Pfeiltasten = genau dieses Risiko) —
    jetzt ist er das Ziel, darum besonders strikt: Praefix-Match statt
    contains, und Alle-/Massen-Varianten sind hart ausgeschlossen (ein 'Alle
    Positionen schliessen' traefe alles, was auf dem Konto liegt)."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if "alle" in t or "all p" in t or "massen" in t or "bulk" in t:
        return False
    # 'schlie' deckt schließen/schliessen samt Encoding-Varianten des ß ab
    return t.startswith(("position schlie", "close position"))


def ist_schliessen_knopf(text, ticket):
    """Der gelbe Bestaetigen-Balken im Close-Dialog ('Schliessen #123 buy 1.20
    NAS100 zum Marktpreis' bzw. 'Close #123 ... by Market'). Positiv-Signatur
    wie beim Bestaetigen-Knopf des Aendern-Dialogs (.65): das Ticket MUSS in
    der Beschriftung stehen — die Ticket-Gegenpruefung ist damit Teil der
    Erkennung selbst. Aendern-/Abbrechen-/Loeschen-Knoepfe sind nie Treffer."""
    t = (text or "").strip().lower()
    if not t or not zeile_nennt_ticket(t, ticket):
        return False
    if any(k in t for k in ("ändern", "aendern", "andern", "modify",
                            "abbrechen", "cancel", "lösch", "loesch", "delete")):
        return False
    return "schlie" in t or "close" in t


# Fensterklassen der Browser (28.08.2026): alle Chromium-Ableger (Chrome, Edge,
# Brave — auch die als App installierte PWA-Huelle) teilen sich eine Klasse,
# dazu Firefox.
BROWSER_KLASSEN = ("Chrome_WidgetWin_1", "MozillaWindowClass")


def ist_prophos_fenster(titel, klasse):
    """Ist dieses Fenster der Browser mit dem Prophos-Tab? Positiv-Signatur aus
    Titel UND Fensterklasse (Lehre vom 18.08., EA-Dialog-Fehlgriff: nie nur ein
    String-Treffer): start-prophos.bat setzt der Backend-KONSOLE selbst den
    Titel 'Prophos-Backend' — ein reiner Titel-Match holte also die Konsole
    nach vorn statt des Browsers. Der Titel beginnt stabil mit 'Prophos'
    (prophos.html setzt kein dynamisches document.title; startswith haelt
    ausserdem DevTools-Fenster fern, deren Titel die URL nur ENTHAELT)."""
    t = (titel or "").strip().lower()
    return t.startswith("prophos") and (klasse or "") in BROWSER_KLASSEN


def ist_tradingview_fenster(titel, klasse):
    """Ist dieses Fenster der Browser mit AKTIVEM TradingView-Tab? (Orbit-Puls
    Schritt 1, 28.08.2026.) Gleiche Positiv-Signatur wie ist_prophos_fenster:
    Titel UND Browser-Klasse. Der Fenstertitel ist immer der AKTIVE Tab —
    haengt TradingView als Hintergrund-Tab im Prophos-Fenster, ist es hier
    unsichtbar; das Zielbild (Vault, 28.08.2026) ist ohnehin ein EIGENES
    TV-Fenster/Profil pro Konto. 'tradingview' steht bei TV mitten im Titel
    (Chart-Titel davor, Browser-Name dahinter), deshalb contains statt
    startswith — DevTools tragen die URL im Titel und sind explizit raus."""
    t = (titel or "").strip().lower()
    if not t or (klasse or "") not in BROWSER_KLASSEN:
        return False
    if t.startswith("devtools"):
        return False
    return "tradingview" in t


# ---------------------------------------------------------------------------
# ORBIT-PULS (30.08.2026) — rein rechnender Teil, ohne Windows testbar
#
# Der Puls klickt auf TradingView mit ECHTER Maus. Das Userscript (tv-reader
# 0.3+) liefert dafuer die Rechtecke der Steuerelemente in CSS-Pixeln relativ
# zum Viewport; hier stehen die Funktionen, die daraus Bildschirm-Pixel machen
# und die entscheiden, ob Konto und Symbol ueberhaupt die richtigen sind.
# Bewusst getrennt vom Klick-Teil: genau diese Entscheidungen sind es, die
# still danebenliegen koennen — sie gehoeren in den Selftest.
# ---------------------------------------------------------------------------

# Kontrakt-Monatsbuchstaben (CME) — nur fuer die Wurzel-Erkennung
_MONATE = "FGHJKMNQUVXZ"


def tv_symbol_root(s):
    """Wurzel eines Futures-Symbols: 'CME_MINI:MNQ1!' und 'MNQZ2025' und 'MNQ'
    sind DASSELBE Instrument. TradingView schreibt je nach Stelle anders —
    Chart-Knopf zeigt den Dauerkontrakt ('MNQ1!'), die Positionstabelle den
    konkreten Monat ('MNQZ2025'), der Plan nur 'MNQ'.

    Reihenfolge ist wichtig: das '1!' des Dauerkontrakts MUSS vor der Monats-
    Regel weg, sonst frisst die Monatsregel das Q aus MNQ1! ('Q1' sieht aus wie
    Monat+Jahr) und uebrig bliebe 'MN' — ein Symbol, das es nicht gibt, und der
    Vergleich waere still falsch statt laut."""
    s = (s or "").strip().upper()
    if not s:
        return ""
    s = s.split()[0]                 # 'MNQ1! · 1m · CME' -> 'MNQ1!'
    if ":" in s:
        s = s.split(":")[-1]         # 'CME_MINI:MNQ1!' -> 'MNQ1!'
    s = re.sub(r"[^A-Z0-9!]", "", s)
    if s.endswith("!"):
        return re.sub(r"\d+!$", "", s).rstrip("!")        # MNQ1! -> MNQ
    m = re.match(r"^([A-Z]{1,4})[" + _MONATE + r"]\d{1,4}$", s)
    if m:
        return m.group(1)                                 # MNQZ2025 -> MNQ
    return re.sub(r"\d+$", "", s)                         # Rest: Ziffern weg


def tv_symbol_passt(aktiv, ziel):
    """Zeigt der Chart schon das geplante Instrument? Verglichen wird die
    Wurzel — der Kontraktmonat ist TradingViews Sache, nicht Finns."""
    a, z = tv_symbol_root(aktiv), tv_symbol_root(ziel)
    return bool(a) and bool(z) and a == z


def _nur_alnum(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").strip().lower())


def tv_konto_passt(text, ext_id):
    """Traegt dieser Konto-Eintrag die External ID des Plans? Ein Tradovate-
    Login hat bei Prop-Firmen mehrere Unterkonten; der Kontoname IST die
    External ID (Finns Ansage 30.08.2026), steht im Dropdown aber mit Beiwerk
    ('PA-1234567 · Tradeify · $50k'). Deshalb Teilstring — aber auf
    alphanumerisch normalisiert, damit Bindestriche/Punkte/Leerzeichen nicht
    entscheiden.

    Riegel: External IDs unter 3 Zeichen werden NIE gematcht. Eine '12' faende
    sonst jedes Konto, und ein Fehlgriff hier bedeutet: Order auf dem falschen
    Prop-Konto."""
    e = _nur_alnum(ext_id)
    if len(e) < 3:
        return False
    return e in _nur_alnum(text)


def tv_de_zahl(text):
    """Deutsche Zahl aus der TradingView-Oberflaeche in float ('1.234,5' ->
    1234.5). Gibt None zurueck, wenn nichts Zaehlbares drinsteht — ein
    stillschweigendes 0.0 waere hier gefaehrlich (Mengen-Vergleich)."""
    if text is None:
        return None
    s = str(text).strip()
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s or s in ("-", ",", "."):
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def tv_seite_passt(seite, richtung):
    """'Long'/'Short' aus der Positionstabelle gegen buy/sell des Befehls."""
    s = (seite or "").strip().lower()
    r = (richtung or "").strip().lower()
    if r == "buy":
        return s.startswith("long") or s.startswith("kauf")
    if r == "sell":
        return s.startswith("short") or s.startswith("verkauf")
    return False


def tv_menge_summe(positionen, symbol, richtung):
    """Summierte Kontraktzahl fuer (Symbol-Wurzel, Richtung) im Reader-Stand.

    Summiert statt 'die eine Position gesucht': Tradovate NETTET pro Symbol,
    und mehrere Monatskontrakte derselben Wurzel koennen nebeneinander liegen.
    Die Bestaetigung nach dem Klick ist deshalb ein DIFFERENZ-Vergleich
    (vorher/nachher), nicht 'gibt es eine Position' — sonst wuerde eine bereits
    offene Position eine gar nicht ausgefuehrte Order 'bestaetigen'."""
    root = tv_symbol_root(symbol)
    summe = 0.0
    for p in (positionen or []):
        if tv_symbol_root(p.get("symbol")) != root:
            continue
        if not tv_seite_passt(p.get("seite"), richtung):
            continue
        m = tv_de_zahl(p.get("menge"))
        if m is not None:
            summe += abs(m)
    return summe


def tv_bildschirm_punkt(rect, geo, klient):
    """CSS-Rechteck (Viewport) -> Bildschirm-Pixel-MITTE. (punkt, grund).

    rect   = [x, y, breite, hoehe] in CSS-Pixeln, relativ zum Viewport
    geo    = {'innerWidth','innerHeight','dpr'} vom Userscript
    klient = (left, top, breite, hoehe) des Browser-KLIENTbereichs in echten
             Pixeln, von Puls selbst per UIA gemessen

    Rechenweg: devicePixelRatio traegt in Chrome BEIDES — Windows-Skalierung
    und Seiten-Zoom —, ist also der einzige Faktor. Der Viewport klebt links am
    Klientrand (innerWidth schliesst die Scrollleiste ein) und unten am
    Klientrand; alles, was vertikal uebrig bleibt, ist Browser-Dekoration
    (Tableiste + Adressleiste) und sitzt OBEN.

    Der Breiten-Abgleich ist die Plausibilitaetsprobe: passt innerWidth*dpr
    nicht zur gemessenen Klientbreite, stimmt eine der Annahmen nicht (DevTools
    seitlich angedockt, falsches Fenster gemessen, Prozess nicht DPI-bewusst) —
    dann wird ABGEBROCHEN statt geklickt. Ein danebenliegender Klick auf einer
    Trading-Seite ist kein harmloser Fehlversuch."""
    try:
        rx, ry, rw, rh = [float(v) for v in rect[:4]]
        dpr = float(geo.get("dpr") or 1) or 1.0
        iw = float(geo.get("innerWidth") or 0)
        ih = float(geo.get("innerHeight") or 0)
        kl, kt, kb, kh = [float(v) for v in klient[:4]]
    except (TypeError, ValueError, IndexError):
        return None, "Geometrie unvollstaendig"
    if iw <= 0 or ih <= 0 or kb <= 0 or kh <= 0:
        return None, "Geometrie leer"
    if abs(kb - iw * dpr) > 40:
        return None, (f"Breiten-Abgleich schlaegt fehl: Fenster {int(kb)} px, "
                      f"Seite {int(iw * dpr)} px (DevTools seitlich angedockt?)")
    deko = kh - ih * dpr
    if deko < -4 or deko > 400:
        return None, (f"Browser-Dekoration unplausibel ({int(deko)} px) — "
                      "Vollbild/geteiltes Fenster?")
    x = kl + (rx + rw / 2.0) * dpr
    y = kt + max(0.0, deko) + (ry + rh / 2.0) * dpr
    if not (kl <= x <= kl + kb and kt <= y <= kt + kh):
        return None, "Zielpunkt liegt ausserhalb des Browser-Fensters"
    return (int(round(x)), int(round(y))), ""


def tv_einheit_ist_geld(text):
    """Steht der Einheiten-Umschalter des TP/SL-Felds auf Geld? Finn gibt TP/SL
    in $ an — steht die Einheit auf Ticks oder %, waere derselbe getippte Wert
    eine voellig andere Distanz. Deshalb wird sie gelesen und bei Zweifel
    abgebrochen, statt eine Zahl in ein Feld unbekannter Bedeutung zu tippen."""
    t = (text or "").strip().lower()
    if not t:
        return False
    return ("$" in t or "usd" in t or "geld" in t or "money" in t
            or "waehrung" in t or "währung" in t or "currency" in t)


def tv_zahl_text(x):
    """Zahl so schreiben, wie eine deutsche TradingView-Oberflaeche sie liest:
    Komma als Dezimaltrenner, ganze Zahlen ohne Nachkomma (Kontrakte sind
    ganzzahlig — '2,0' hat TV frueher schon als '20' missverstanden, gleiche
    Fehlerklasse wie Finns 22-Einwand am MT5-Volumenfeld 18.08.2026)."""
    f = float(x)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return ("%.4f" % f).rstrip("0").rstrip(".").replace(".", ",")


def pruefe_tv_befehl(cmd):
    """Liste von Fehlertexten; leer = Befehl ok. Eigene Pruefung statt
    pruefe_befehl: der Orbit-Befehl braucht die External ID (welches Unterkonto)
    und kennt keine MT5-Lots, sondern ganze Kontrakte."""
    fehler = []
    if not isinstance(cmd, dict):
        return ["Befehl ist kein JSON-Objekt."]
    if not str(cmd.get("ext_id") or "").strip():
        fehler.append("ext_id fehlt (welches Unterkonto?)")
    elif len(_nur_alnum(cmd.get("ext_id"))) < 3:
        fehler.append("ext_id zu kurz — koennte das falsche Konto treffen")
    if not str(cmd.get("symbol") or "").strip():
        fehler.append("symbol fehlt")
    if str(cmd.get("richtung") or "").lower() not in ("buy", "sell"):
        fehler.append("richtung muss buy oder sell sein")
    try:
        v = float(cmd.get("volumen") or 0)
        if not math.isfinite(v) or v <= 0:
            fehler.append("volumen fehlt oder <= 0")
        elif abs(v - round(v)) > 1e-9:
            fehler.append("volumen muss ganze Kontrakte sein")
    except (TypeError, ValueError):
        fehler.append("volumen ist keine Zahl")
    # SL/TP sind optional (Schalter im Order-Popup) — aber nur GEMEINSAM.
    # Ein einzelner Wert waere eine halbe Absicherung, und welche Haelfte
    # fehlt, sieht man am PC nicht mehr.
    hat_sl = cmd.get("sl_usd") not in (None, "", 0)
    hat_tp = cmd.get("tp_usd") not in (None, "", 0)
    if hat_sl != hat_tp:
        fehler.append("sl_usd und tp_usd nur gemeinsam (oder beide weglassen)")
    for feld in ("sl_usd", "tp_usd"):
        if cmd.get(feld) in (None, "", 0):
            continue
        try:
            f = float(cmd[feld])
            if not math.isfinite(f) or f <= 0:
                fehler.append(f"{feld} muss > 0 sein")
        except (TypeError, ValueError):
            fehler.append(f"{feld} ist keine Zahl")
    return fehler


# ---------------------------------------------------------------------------
# LESENDER API-Teil — Kurse + Positionsstand (traegt keine Order-Markierung)
# ---------------------------------------------------------------------------

def _api_lesen(path, expected, symbol=None):
    """Einmal andocken, lesen, sofort trennen. Rueckgabe:
    {"login", "positionen": [...], "ref_ask", "ref_bid", "contract_size",
     "digits"} oder {"fehler": ...}."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return {"fehler": "MetaTrader5-Paket fehlt (nur auf dem PC lauffaehig)."}
    if not mt5.initialize(path=path):
        return {"fehler": f"Terminal-Verbindung fehlgeschlagen: {mt5.last_error()}"}
    try:
        ai = mt5.account_info()
        if ai is None:
            return {"fehler": "Kein Konto verbunden (account_info leer)."}
        if expected and int(ai.login) != expected:
            return {"fehler": f"Terminal ist im FALSCHEN Konto ({ai.login} statt {expected})."}
        out = {"login": int(ai.login), "positionen": []}
        for p in (mt5.positions_get() or []):
            out["positionen"].append({"ticket": int(p.ticket), "symbol": str(p.symbol),
                                      "typ": int(p.type), "volumen": float(p.volume),
                                      "sl": float(p.sl), "tp": float(p.tp),
                                      "preis": float(p.price_open)})
        if symbol:
            # Symbol in die Marktuebersicht holen (15.08.2026, Finns Fund: nach
            # frischem Login ist NASDAQ nie da). symbol_select(..., True) ist eine
            # reine Watchlist-Aktion — KEINE Order, also keine Expert-Markierung.
            # Damit taucht das Symbol danach auch im F9-Dialog-Dropdown auf.
            if mt5.symbol_info(symbol) is None:
                # Broker kennt diese Schreibweise gar nicht — Mapping pruefen.
                return {"fehler": f"Broker kennt Symbol '{symbol}' nicht — Schreibweise im "
                                  f"Symbol-Mapping der Copier-Karte pruefen (z.B. NAS100 vs NDX100)."}
            if not mt5.symbol_select(symbol, True):
                return {"fehler": f"Symbol '{symbol}' liess sich nicht zur Marktuebersicht "
                                  f"hinzufuegen."}
            si = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            # Nach frischem Hinzufuegen kann der erste Tick kurz fehlen — bis 3s
            # nachfassen, bevor 'Markt zu' gemeldet wird.
            _t0 = time.time()
            while (tick is None or not (tick.ask and tick.bid)) and time.time() - _t0 < 3:
                _warte(0.3, 0.3)
                tick = mt5.symbol_info_tick(symbol)
            if si is None or tick is None or not (tick.ask and tick.bid):
                return {"fehler": f"Keine Kurse fuer '{symbol}' (Markt zu?)."}
            out["ref_ask"] = float(tick.ask)
            out["ref_bid"] = float(tick.bid)
            out["contract_size"] = float(getattr(si, "trade_contract_size", 0) or 0) or 1.0
            out["digits"] = int(getattr(si, "digits", 2) or 2)
        return out
    finally:
        mt5.shutdown()


# _sltp_setzen (TRADE_ACTION_SLTP) ist am 18.08.2026 bewusst GELOESCHT worden:
# die Aenderung lief ueber denselben API-Kanal wie ein EA — Finns Ansage: auch
# SL/TP wird per Klick eingetragen, die API bleibt komplett lesend.


# ---------------------------------------------------------------------------
# SICHTBARER Klick-Teil (pywinauto) — nur bei run/inspect importiert
# ---------------------------------------------------------------------------

MT5_KLASSE = "MetaQuotes::MetaTrader::5.00"

# Echo-Pause (28.08.2026, Finns Not-Aus): dieselbe Flag-Datei wie der Copier
# (echo_pause.flag im Bot-Ordner, gelegt vom Panel /api/pause). Ist sie da,
# steigt der Bot aus seiner SL/TP-Klick-Schleife aus, statt weiter am Terminal
# herumzuklicken — genau der Fall, den Finn nicht mehr per Task-Manager killen
# will. Die Order selbst ist da laengst platziert; abgebrochen werden nur die
# NEUEN Klick-Versuche.
_PAUSE_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "echo_pause.flag")


def is_paused():
    return os.path.exists(_PAUSE_FLAG)


def _warte(minimum, streuung):
    """Wartezeit mit Zufalls-Streuung: minimum + 0..streuung Sekunden.

    28.08.2026, Finns Sorge: platziert die Flotte gleichzeitig, tickte bisher
    JEDER Schritt — F9, Symbol, Volumen, Buy-Klick, SL/TP-Eintrag — auf allen
    Instanzen im exakt gleichen Sekunden-Raster (fixe sleeps). Die Streuung
    zieht die Ablaeufe pro Lauf und pro Instanz auseinander; jeder Aufruf
    wuerfelt neu, dadurch unterscheiden sich auch die Abstaende ZWISCHEN den
    Schritten eines einzelnen Laufs.

    Das Minimum bleibt unangetastet — es ist die Zeit, die die MT5-UI wirklich
    braucht (Tempo-Kalibrierung aus .73 gilt weiter), gewuerfelt wird nur
    OBENDRAUF. Bewusst OHNE Streuung bleiben die 12-ms-Animationsschritte in
    _maus_fahren (fluessige Bewegung) und die Diagnose-Modi mousetest/inspect."""
    time.sleep(minimum + random.uniform(0.0, streuung))


def _klick_absolut(x, y, taste="links", doppel=False):
    """Echter Maus-Klick als EIN atomarer SendInput-Batch mit ABSOLUT-
    Koordinaten (18.08.2026): Bewegen+Druecken+Loslassen in einem Aufruf.
    pywinautos click_input bewegt erst und klickt dann getrennt — genau in
    diese Luecke funkt Parsec mit der lokalen Mausposition (Fund 16.08.).
    Ein Batch laesst dem keinen Raum, und fuer MT5 ist das Ergebnis von
    einem Hand-Klick nicht unterscheidbar. taste='rechts' fuer Kontextmenues,
    doppel=True haengt Druecken+Loslassen als Doppelklick an."""
    import ctypes
    user32 = ctypes.windll.user32
    # Virtueller Desktop statt Primaer-Monitor (30.08.2026, SL/TP-Fehlklick-
    # Suche): MOUSEEVENTF_ABSOLUTE allein normiert auf den PRIMAER-Monitor —
    # liegt MT5 auf einem Zweitmonitor, landen alle Batch-Klicks daneben,
    # waehrend die Maus-ANIMATION (SetCursorPos, echte Koordinaten) weiter
    # stimmt und den Fehler perfekt versteckt. VIRTUALDESK + Virtual-Screen-
    # Metriken treffen jeden Monitor; mit einem einzelnen Monitor ist das
    # Ergebnis Bit fuer Bit dasselbe wie vorher.
    vx = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    vy = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
    vw = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    vh = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
    ax = int(round((int(x) - vx) * 65535 / max(1, vw - 1)))
    ay = int(round((int(y) - vy) * 65535 / max(1, vh - 1)))
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class _MI(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]

    class _INP(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("mi", _MI)]

    MOVE, ABS = 0x0001, 0x8000 | 0x4000   # ABSOLUTE + VIRTUALDESK (s.o.)
    DOWN, UP = (0x0002, 0x0004) if taste == "links" else (0x0008, 0x0010)
    folge = [MOVE | ABS, MOVE | DOWN | ABS, MOVE | UP | ABS]
    if doppel:
        folge += [MOVE | DOWN | ABS, MOVE | UP | ABS]
    batch = (_INP * len(folge))()
    for i, fl in enumerate(folge):
        batch[i].type = 0  # INPUT_MOUSE
        batch[i].mi = _MI(ax, ay, 0, fl, 0, None)
    return user32.SendInput(len(folge), batch, ctypes.sizeof(_INP)) == len(folge)


def _cursor_pos():
    import ctypes
    import ctypes.wintypes as wt
    pt = wt.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _cursor_set(x, y):
    """Cursor per tiefster Windows-API setzen (15.08.2026): SetCursorPos greift
    auch ueber Parsec zuverlaessig auf den ECHTEN Windows-Cursor — der
    pywinauto-Weg zeigte ueber Remote-Sitzungen manchmal nur den lokalen
    Parsec-Cursor, waehrend sich der echte lautlos woanders bewegte."""
    import ctypes
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def _maus_fahren(x, y, schritte=18):
    """Den ECHTEN Mauszeiger sichtbar hinfahren (nicht teleportieren) — Finns
    Ansage: man soll sehen, wie der Bot die Kontrolle uebernimmt. SetCursorPos
    statt pywinauto.mouse (Parsec-Doppelcursor, s.o.)."""
    try:
        cx, cy = _cursor_pos()
    except Exception:
        cx, cy = x, y
    for i in range(1, schritte + 1):
        try:
            _cursor_set(int(cx + (x - cx) * i / schritte),
                        int(cy + (y - cy) * i / schritte))
        except Exception:
            break
        time.sleep(0.012)


def _bildschirm_groesse():
    import ctypes
    return (ctypes.windll.user32.GetSystemMetrics(0),
            ctypes.windll.user32.GetSystemMetrics(1))


def _bildschirm_mitte():
    w, h = _bildschirm_groesse()
    return (w // 2, h // 2)


def modus_mousetest():
    """Isolierter Selbsttest (15.08.2026, Finns Wunsch): bewegt den Cursor
    sichtbar ueber den Bildschirm und tippt in Notepad — beantwortet die
    Grundfrage, ob Maus/Tastatur auf diesem PC ueberhaupt steuerbar sind,
    getrennt von MT5. Liest nach JEDEM Schritt die echte Cursor-Position:
    stimmt sie mit dem Ziel, bewegt sich der OS-Cursor wirklich (auch wenn
    AnyDesk/Parsec nur den lokalen Zeiger anzeigt)."""
    res = {"ok": False, "moves": [], "notepad": None}
    time.sleep(2.0)  # Haende weg
    try:
        W, H = _bildschirm_groesse()
    except Exception as e:
        print(json.dumps({"ok": False, "msg": f"Bildschirmgroesse nicht lesbar: {e}"}))
        return
    ziele = [(W // 2, H // 2), (60, 60), (W - 60, 60),
             (W - 60, H - 60), (60, H - 60), (W // 2, H // 2)]
    for tx, ty in ziele:
        _maus_fahren(tx, ty)
        time.sleep(0.6)
        try:
            ax, ay = _cursor_pos()
        except Exception:
            ax, ay = -1, -1
        res["moves"].append({"ziel": [tx, ty], "ist": [ax, ay],
                             "ok": abs(ax - tx) < 8 and abs(ay - ty) < 8})
    res["cursor_bewegt"] = bool(res["moves"]) and all(m["ok"] for m in res["moves"])
    # Notepad: Maus hin, Fokus, Zahlen tippen
    try:
        import subprocess
        from pywinauto import Desktop
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.8)
        np = None
        for w in Desktop(backend="uia").windows():
            try:
                if "notepad" in (w.window_text() or "").lower() \
                        or w.element_info.class_name == "Notepad":
                    np = w
                    break
            except Exception:
                continue
        if np:
            np.set_focus()
            time.sleep(0.4)
            try:
                r = np.rectangle()
                _maus_fahren(r.mid_point().x, r.mid_point().y)
            except Exception:
                pass
            np.type_keys("123456 Prophos Maus-Test OK", with_spaces=True, set_foreground=True)
            res["notepad"] = "getippt: '123456 Prophos Maus-Test OK' — im Notepad sichtbar?"
        else:
            res["notepad"] = "Notepad-Fenster nicht gefunden"
    except Exception as e:
        res["notepad"] = f"Notepad-Test fehlgeschlagen: {type(e).__name__}: {e}"
    treffer = sum(1 for m in res["moves"] if m["ok"])
    res["ok"] = res["cursor_bewegt"]
    res["msg"] = (f"Cursor-Bewegung: {treffer}/{len(res['moves'])} Ziele getroffen "
                  f"({'OS-Cursor bewegt sich' if res['cursor_bewegt'] else 'OS-Cursor bewegt sich NICHT'}). "
                  f"Notepad: {res['notepad']}")
    print(json.dumps(res))


def _maus_zentrieren():
    """Anker-Punkt (Finns Wunsch 15.08.2026): der Bot faehrt die Maus SELBST
    sichtbar in die Bildschirmmitte und haelt kurz — fester Ausgangspunkt, den
    Finn nicht mehr treffen muss. Rueckgabe: (bewegt?, (x, y)) — bewegt=False
    heisst, der OS-Cursor liess sich nicht setzen (dann meldet run das klar)."""
    try:
        vor = _cursor_pos()
    except Exception:
        vor = None
    mx, my = _bildschirm_mitte()
    _maus_fahren(mx, my)
    time.sleep(1.0)  # sichtbar halten
    try:
        nach = _cursor_pos()
        bewegt = (vor is None) or (abs(nach[0] - mx) < 6 and abs(nach[1] - my) < 6)
        return bewegt, nach
    except Exception:
        return True, (mx, my)


def _fenster_betreten(w):
    """Schritt 1 der Choreografie: sichtbar INS Terminal gehen (15.08.2026,
    Finns Fix: NICHT ueber die Taskleiste — deren Tabs wandern je nach Sitzung.
    Das Terminal ist beim Trade-Start ohnehin schon geoeffnet und nach vorn
    geholt): Fenster wiederherstellen, Maus sichtbar auf die Titelzeile fahren
    und hineinklicken. Das Ziel kommt aus dem Fenster-Rechteck selbst —
    aufloesungs- und tab-unabhaengig, keine festen Pixel."""
    try:
        if w.is_minimized():
            w.restore()
            _warte(0.2, 0.25)
    except Exception:
        pass
    w.set_focus()
    _warte(0.25, 0.3)
    try:
        from pywinauto import mouse
        r = w.rectangle()
        # linkes Drittel der Titelzeile — weit weg von Minimieren/Schliessen
        x = int(r.left + (r.right - r.left) * 0.35)
        y = int(r.top + 14)
        _maus_fahren(x, y)
        mouse.click(coords=(x, y))
        _warte(0.15, 0.2)
    except Exception:
        pass  # Fokus steht schon — der Klick ist der sichtbare Uebernahme-Moment


def _finde_terminal(login):
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows():
        try:
            if w.element_info.class_name == MT5_KLASSE and str(login) in (w.window_text() or ""):
                return w
        except Exception:
            continue
    return None


def _zurueck_zu_prophos():
    """Ausgangssituation (28.08.2026, Finns Ansage nach dem ersten Remote-
    Erfolg): nach JEDEM Lauf — Erfolg, Abbruch oder SL/TP-Warnung — wechselt
    der PC zurueck in den Prophos-Tab. Je mehr remote gefahren wird, desto
    wichtiger die feste Home-Base: es steht niemand am PC, der den Fokus
    aufraeumt. Best-Effort — das Order-Ergebnis aendert sich hier NIE mehr.
    BEWUSST ohne den Titelzeilen-Klick aus _fenster_betreten: beim Browser
    sitzt dort die Tab-Leiste, ein Klick koennte den Prophos-Tab wegschalten.
    Rueckgabe: Spur-Text fuers trail-Feld (Panel-Log + ergebnis-jsonb)."""
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="uia").windows():
            try:
                if not ist_prophos_fenster(w.window_text(),
                                           w.element_info.class_name):
                    continue
                if w.is_minimized():
                    w.restore()
                    _warte(0.2, 0.25)
                w.set_focus()
                return "zurueck in Prophos"
            except Exception:
                continue
        return "Prophos-Fenster nicht gefunden"
    except Exception as e:
        return f"Rueckkehr zu Prophos fehlgeschlagen ({type(e).__name__})"


def modus_tvfokus():
    """Orbit-Puls, Etappe 3 Schritt 1 (28.08.2026, Finns Ansage 'mehr mal
    nicht, nur bis dahin'): NUR den TradingView-Tab nach vorn holen — kein
    Klick in die Seite, keine Order. Ausfuellen/Platzieren kommen als
    naechste Stufen. BEWUSST kein _zurueck_zu_prophos danach: der Sinn des
    Schritts IST der Fokuswechsel, der PC soll auf TradingView stehen."""
    res = {"ok": False, "msg": "", "trail": ""}
    try:
        from pywinauto import Desktop
    except ImportError:
        res["msg"] = "pywinauto fehlt (nur auf dem PC lauffaehig)."
        print(json.dumps(res))
        return
    _warte(0.1, 0.5)   # Start-Versatz (Jitter-Dauerregel 28.08.2026)
    try:
        for w in Desktop(backend="uia").windows():
            try:
                if not ist_tradingview_fenster(w.window_text(),
                                               w.element_info.class_name):
                    continue
                titel = (w.window_text() or "").strip()
                if w.is_minimized():
                    w.restore()
                    _warte(0.2, 0.25)
                # BEWUSST ohne den Titelzeilen-Klick aus _fenster_betreten:
                # beim Browser sitzt dort die Tab-Leiste, ein Klick koennte
                # den TV-Tab wegschalten (gleiche Lehre wie _zurueck_zu_prophos).
                w.set_focus()
                res["ok"] = True
                res["trail"] = "TradingView-Tab nach vorn"
                res["msg"] = f"TradingView ist vorn ({titel[:80]})"
                print(json.dumps(res))
                return
            except Exception:
                continue
        res["msg"] = ("Kein Browser-Fenster mit aktivem TradingView-Tab gefunden — "
                      "TradingView muss in einem eigenen Fenster offen sein und "
                      "dort der sichtbare Tab.")
        res["trail"] = "TV-Fenster gesucht, kein Treffer"
    except Exception as e:
        res["msg"] = f"TV-Fokus fehlgeschlagen: {type(e).__name__}: {e}"
    print(json.dumps(res))


# ═══════════════════════════════════════════════════════════════════════════
# ORBIT-PULS SCHRITT 2 (30.08.2026) — die Order auf TradingView platzieren
#
# Finns Ablauf (wortwoertlich, 30.08.2026): "1. Puls oeffnet im gleichen chrome
# browser den Tradingview tap  2. (wir sind in tradovate schon eingeloggt)
# 3. er oeffnet den richtigen acc (name = EXT ID)  4. er oeffnet das richtige
# asset (NQ/MNQ)  5. er oeffnet das Trade-starten-Popup, gibt Lots + TP/SL in $
# ein und oeffnet schliesslich die order."
#
# Arbeitsteilung: das Userscript sind die AUGEN (findet die Steuerelemente,
# meldet Rechtecke), der Puls sind HAENDE UND KOPF (entscheidet, klickt mit
# echter Maus). Warum nicht das Userscript klicken lassen: ein element.click()
# traegt isTrusted=false — die ganze Puls-Doktrin vom 15.08.2026 ist
# "muss wie ein Handklick aussehen".
#
# ZWEI Doktrinen aus dem MT5-Puls gelten hier unveraendert:
#  - Bestaetigung NIE aus der UI, sondern aus dem Positions-Snapshot des
#    Readers (dort, wo beim MT5-Bot der Lese-EA steht).
#  - retry_ok=True nur, solange sicher NICHTS gesendet wurde. Ab dem Klick auf
#    den Senden-Knopf ist jede Unsicherheit retry_ok=False.
#
# Der PC bleibt am Ende BEWUSST auf TradingView stehen (kein Prophos-Heimweg
# wie bei den MT5-Modi): Chrome drosselt setInterval in Hintergrund-Tabs auf
# ~1/s und friert sie nach Minuten ganz ein — der Reader ist dann blind und
# der Hedge haengt. Wer Prophos daneben braucht, gibt TradingView ein EIGENES
# Fenster (dann laufen beide sichtbar weiter).
# ═══════════════════════════════════════════════════════════════════════════

_TV_BASIS = "http://127.0.0.1:8790"


def _tv_http(pfad, daten=None, timeout=3.0):
    """Kurzer JSON-Aufruf an den lokalen Reader-Server. None = nicht erreichbar."""
    import urllib.request
    try:
        roh = json.dumps(daten).encode("utf-8") if daten is not None else None
        req = urllib.request.Request(
            _TV_BASIS + pfad, data=roh,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def _tv_bf(nach=None, timeout=8.0):
    """Bedienfeld holen — optional erst einen Stand, der NACH dem Zeitpunkt
    'nach' beim Server ankam. Das ist der Beweis-Mechanismus des ganzen Modus:
    nach jedem Klick wird nicht gehofft, dass die Seite reagiert hat, sondern
    auf einen frisch gelesenen Stand gewartet."""
    ende = time.time() + timeout
    letzt = None
    while time.time() < ende:
        d = _tv_http("/bedienfeld")
        if d and d.get("ok"):
            letzt = d
            empfangen = time.time() - float(d.get("alter_s") or 0.0)
            if nach is None or empfangen >= nach:
                return d
        time.sleep(0.15)
    return letzt if nach is None else None


def _tv_positionen(timeout=3.0):
    """(positionen, an) aus dem Reader — (None, None) wenn er nicht antwortet."""
    d = _tv_http("/positions", timeout=timeout)
    if not d:
        return None, None
    return (d.get("positionen") or []), (d.get("an") is not False)


def _klient_rechteck(hwnd):
    """(left, top, breite, hoehe) des KLIENTbereichs in echten Bildschirm-
    Pixeln. Bewusst nicht w.rectangle(): das Fenster-Rechteck enthaelt unter
    Windows 10/11 die unsichtbaren Anfass-Raender (~8 px links/rechts/unten) —
    damit waere jeder Klick um diese 8 px verschoben, und zwar lautlos."""
    import ctypes
    import ctypes.wintypes as wt
    r = wt.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wt.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return (int(pt.x), int(pt.y), int(r.right - r.left), int(r.bottom - r.top))


def _dpi_bewusst():
    """Prozess DPI-bewusst machen — NUR in diesem Modus (eigener kurzlebiger
    Subprozess, die MT5-Wege bleiben unberuehrt). Ohne das liefert Windows
    virtualisierte, also gelogene Fenster-Koordinaten, sobald die Anzeige auf
    125/150 % steht — und der Breiten-Abgleich in tv_bildschirm_punkt wuerde
    genau daran scheitern (laut, immerhin)."""
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_DPI_AWARE
        return True
    except Exception:
        pass
    try:
        return bool(ctypes.windll.user32.SetProcessDPIAware())
    except Exception:
        return False


def tv_tab_suchbegriff(titel):
    """Stabiler Suchbegriff aus dem Seitentitel, den das Userscript meldet.

    30.08.2026, Finns erster Live-Lauf: der Bot suchte den Tab am Wort
    'tradingview' und fand nichts — der Tab heisst bei ihm schlicht
    'NQU2026 29.491,75 ▼ −0,69 %'. Ein Volltext-Vergleich hilft trotzdem
    nicht: der Preis darin tickt sekuendlich. Genommen wird deshalb das
    ERSTE Wort (das Symbol), das steht still, solange der Chart steht.
    Genommen wird das erste Wort, das WIE EIN SYMBOL aussieht: mindestens
    zwei Zeichen und mindestens ein Buchstabe. Damit fallen die Zaehler-
    Praefixe weg, die Browser und TradingView voranstellen ('(1) NQU2026 …') —
    ohne diese Regel waere der Suchbegriff dort '1' und wuerde auf jeden
    beliebigen Tab passen. Ein Suchbegriff, der ueberall passt, ist
    schlimmer als keiner."""
    for teil in (titel or "").split():
        k = teil.strip("()[]{}:,;·—-")
        if len(k) >= 2 and any(c.isalpha() for c in k):
            return k
    return ""


def _tv_tab_suchen(w, begriff, gesehen):
    """Das TabItem mit TradingView in der Tableiste dieses Browser-Fensters.
    Deckt den Fall ab, den Schritt 1 (tvfokus) noch nicht konnte: TradingView
    als HINTERGRUND-Tab — der Fenstertitel zeigt immer nur den aktiven Tab.

    'begriff' ist das Symbol aus dem Seitentitel, den das Userscript meldet
    (siehe tv_tab_suchbegriff); 'tradingview' bleibt als zweiter Weg stehen,
    fuer den Fall, dass gerade kein Bedienfeld vorliegt. Jeder gesehene
    Tab-Name wandert nach 'gesehen' — ohne diese Liste sagt ein Fehlversuch
    nur 'nicht gefunden' und die Ferndiagnose faengt bei null an (Lehre aus
    dem SL/TP-Zeilen-Scan, 30.08.2026)."""
    try:
        kinder = w.descendants(control_type="TabItem", depth=12)
    except Exception:
        try:
            kinder = w.descendants(control_type="TabItem")
        except Exception:
            return None
    b = (begriff or "").strip().lower()
    treffer = []
    for it in kinder:
        try:
            n = (it.window_text() or "").strip()
        except Exception:
            continue
        if not n or n.lower().startswith("devtools"):
            continue
        if len(gesehen) < 12:
            gesehen.append(n[:60])
        if "tradingview" in n.lower() or (b and b in n.lower()):
            treffer.append(it)
    if not treffer:
        return None
    if len(treffer) > 1:
        # Mehrere Kandidaten: den mit 'tradingview' bevorzugen, sonst den
        # ersten. Anders als beim Order-Klick ist das vertretbar — ein
        # Tabwechsel ist folgenlos und sofort sichtbar.
        for it in treffer:
            try:
                if "tradingview" in (it.window_text() or "").lower():
                    return it
            except Exception:
                continue
    return treffer[0]


def _tv_fenster_holen(trail, begriff=""):
    """Browser-Fenster mit TradingView nach vorn — Titel zuerst (aktiver Tab),
    sonst ueber die Tableiste. (fenster, fehlertext)."""
    from pywinauto import Desktop
    kandidaten = []
    fenster_namen = []
    tab_namen = []
    b = (begriff or "").strip().lower()
    for w in Desktop(backend="uia").windows():
        try:
            titel = w.window_text() or ""
            klasse = w.element_info.class_name
        except Exception:
            continue
        if (klasse or "") not in BROWSER_KLASSEN:
            continue
        if len(fenster_namen) < 8:
            fenster_namen.append((titel or "?")[:60])
        # Aktiver Tab: 'tradingview' im Titel ODER das gemeldete Symbol —
        # bei Finns PC steht im Titel nur 'NQU2026 29.491,75 ...'.
        if ist_tradingview_fenster(titel, klasse) or (b and b in titel.lower()
                                                      and not titel.lower().startswith("devtools")):
            try:
                if w.is_minimized():
                    w.restore()
                    _warte(0.2, 0.25)
                w.set_focus()
            except Exception:
                pass
            trail.append(f"TradingView war schon der aktive Tab ({titel[:40]})")
            return w, ""
        kandidaten.append(w)

    for w in kandidaten:
        tab = _tv_tab_suchen(w, begriff, tab_namen)
        if not tab:
            continue
        try:
            if w.is_minimized():
                w.restore()
                _warte(0.25, 0.3)
            w.set_focus()
            _warte(0.2, 0.25)
            r = tab.rectangle()
            x = int((r.left + r.right) / 2)
            y = int((r.top + r.bottom) / 2)
            _maus_fahren(x, y)
            _klick_absolut(x, y)
            _warte(0.5, 0.4)
            trail.append(f"TradingView-Tab angeklickt ({(tab.window_text() or '')[:50]})")
            return w, ""
        except Exception as e:
            trail.append(f"Tab-Klick fehlgeschlagen ({type(e).__name__})")
            continue

    # Selbst-Diagnose statt 'nicht gefunden': WAS hat er gesehen? Daran haengt,
    # ob der Suchbegriff falsch war (Tabs sind da, passen nur nicht) oder ob
    # die Tableiste per UIA gar nicht lesbar ist (Liste leer).
    trail.append(f"Suchbegriff '{begriff or '-'}'"
                 f" · Browser-Fenster: {fenster_namen or 'keine'}"
                 f" · Tabs: {tab_namen or 'keine gelesen'}")
    return None, ("Kein Browser-Fenster mit TradingView gefunden. Gesucht wurde nach "
                  f"'{begriff or 'tradingview'}'. Gesehen: "
                  f"{len(fenster_namen)} Browser-Fenster {fenster_namen}, "
                  f"Tab-Namen {tab_namen or '(keine lesbar)'}. "
                  "Steht dort der TradingView-Tab nicht dabei, kann die Tableiste "
                  "nicht ausgelesen werden.")


def _tv_klick(rect, geo, klient, name, trail, doppel=False):
    """Ein gemeldetes Steuerelement anklicken: Punkt rechnen, Maus sichtbar
    hinfahren, EIN SendInput-Batch (Parsec-Lehre 16.08.). (ok, fehlertext)."""
    punkt, grund = tv_bildschirm_punkt(rect, geo, klient)
    if not punkt:
        trail.append(f"{name}: {grund}")
        return False, f"{name} nicht anklickbar — {grund}"
    _maus_fahren(*punkt)
    if not _klick_absolut(punkt[0], punkt[1], doppel=doppel):
        trail.append(f"{name}: SendInput abgelehnt")
        return False, f"Klick auf {name} wurde von Windows abgelehnt"
    trail.append(f"{name} geklickt @{punkt[0]},{punkt[1]}")
    return True, ""


def _tv_tippen(wert, name, trail):
    """In das zuvor angeklickte Feld tippen — echte Tastatur-Events (SendInput),
    Feld vorher garantiert leeren. Ruecklesen passiert NICHT hier, sondern eine
    Ebene hoeher am naechsten Bedienfeld-Stand: das Userscript liest den
    tatsaechlichen value aus dem DOM, was hier keine UIA-Abfrage koennte."""
    try:
        from pywinauto import keyboard
    except ImportError:
        return False, "pywinauto fehlt"
    try:
        keyboard.send_keys("^a{DELETE}")
        _warte(0.1, 0.12)
        keyboard.send_keys(str(wert), with_spaces=False)
        _warte(0.15, 0.15)
        trail.append(f"{name} getippt: {wert}")
        return True, ""
    except Exception as e:
        trail.append(f"{name} tippen fehlgeschlagen: {type(e).__name__}")
        return False, f"{name} liess sich nicht eintippen"


def _tv_element(bf, *pfad):
    """Ein Steuerelement aus dem Bedienfeld holen — nur wenn es EINDEUTIG
    gefunden wurde. Ein Treffer mit 'fehlt' (mehrdeutige Signatur) gilt
    ausdruecklich als NICHT gefunden: lieber ehrlich abbrechen als auf gut
    Glueck einen von mehreren Kandidaten anklicken."""
    d = bf or {}
    for k in pfad:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    if isinstance(d, dict) and d.get("rect") and not d.get("fehlt"):
        return d
    return None


def modus_tvorder(cmd):
    """Die Kette 1-5. Jeder Schritt beweist sich am naechsten Bedienfeld-Stand,
    bevor der naechste beginnt."""
    trail = []
    res = {"ok": False, "retry_ok": True, "msg": "", "trail": "",
           "schritt": "start"}

    def raus(msg, schritt, retry_ok=True):
        res["msg"] = msg
        res["schritt"] = schritt
        res["retry_ok"] = retry_ok
        res["trail"] = " → ".join(trail)
        # Fehlversuch = Beweise fuer die naechste Runde sammeln (gleiche Rolle
        # wie modus_inspect beim MT5-Puls, nur fuer eine Webseite): der Server
        # laesst das Userscript 60 s lang seinen Kandidaten-Dump mitschicken.
        if not res["ok"]:
            _tv_http("/dump-an", {})
        print(json.dumps(res))
        return

    fehler = pruefe_tv_befehl(cmd)
    if fehler:
        return raus("Befehl unvollstaendig: " + " · ".join(fehler), "befehl")

    if is_paused():
        return raus("Echo ist pausiert — es wird keine Order platziert.", "pause")

    try:
        from pywinauto import Desktop  # noqa: F401  (nur Verfuegbarkeits-Probe)
    except ImportError:
        return raus("pywinauto fehlt (nur auf dem PC lauffaehig).", "start")

    _dpi_bewusst()
    _warte(0.1, 0.5)   # Start-Versatz (Jitter-Dauerregel 28.08.2026)

    # --- Schritt 0: der Reader MUSS leben ---------------------------------
    # Vor dem Fensterwechsel geprueft: ohne Reader gaebe es hinterher keine
    # Bestaetigung, und eine unbestaetigte Order ist genau der Zustand, den
    # die ganze Doktrin vermeiden will.
    pos_vorher, an = _tv_positionen()
    if pos_vorher is None:
        return raus("TV-Reader antwortet nicht (127.0.0.1:8790) — erst "
                    "reader-server starten.", "reader")
    if not an:
        return raus("TV-Reader ist pausiert — er wuerde die neue Position nie "
                    "melden. Erst in der Orbit-Ansicht fortsetzen.", "reader")
    menge_vorher = tv_menge_summe(pos_vorher, cmd["symbol"], cmd["richtung"])
    trail.append(f"Reader lebt, {len(pos_vorher)} Pos, Ausgangsmenge {menge_vorher:g}")

    # --- Schritt 1: TradingView-Tab nach vorn ------------------------------
    # Erst fragen, wie die Seite gerade heisst: das Userscript sendet auch aus
    # einem Hintergrund-Tab weiter (gedrosselt, aber es sendet), also liegt
    # beim Server ein Titel vor, BEVOR ueberhaupt ein Fenster gesucht wird.
    # Ohne Bedienfeld bleibt der Begriff leer und die Suche faellt auf das
    # Wort 'tradingview' zurueck — dann sagt die Spur, dass es so war.
    bf0 = _tv_bf(timeout=4.0) or {}
    begriff = tv_tab_suchbegriff(bf0.get("titel"))
    trail.append(f"Tab-Suchbegriff: {begriff or '(kein Bedienfeld — Fallback tradingview)'}")
    w, f = _tv_fenster_holen(trail, begriff)
    if not w:
        return raus(f, "fenster")
    try:
        hwnd = w.handle
    except Exception:
        return raus("Browser-Fenster ohne Handle — Fenster neu oeffnen.", "fenster")

    def klient():
        return _klient_rechteck(hwnd)

    t0 = time.time()
    bf = _tv_bf(nach=t0, timeout=8.0)
    if not bf:
        return raus("Kein frisches Bedienfeld vom TradingView-Tab — laeuft das "
                    "Userscript in Version 0.3+? (Tampermonkey-Badge unten "
                    "rechts muss gruen sein.)", "bedienfeld")
    if not isinstance(bf.get("geo"), dict) or not bf["geo"].get("innerWidth"):
        # Das Userscript meldet bei einem internen Fehler nur {ts, fehler} —
        # ohne geo{} waere jede Koordinatenrechnung geraten. Lieber hier laut
        # abbrechen als spaeter irgendwohin klicken.
        return raus("Bedienfeld ohne Geometrie" +
                    (f" ({bf.get('fehler')})" if bf.get("fehler") else "") +
                    " — Userscript-Version pruefen (0.3+) und TradingView neu laden.",
                    "bedienfeld")
    if bf.get("sprache_fremd"):
        return raus("TradingView laeuft nicht auf Deutsch — der Reader liest "
                    "die deutschen Spalten. Profilmenue → Sprache → Deutsch, "
                    "dann F5.", "sprache")

    # --- Schritt 3: richtiges Unterkonto -----------------------------------
    ext = str(cmd["ext_id"]).strip()
    if not tv_konto_passt(bf.get("konto", {}).get("aktiv"), ext):
        schalter = _tv_element(bf, "konto", "schalter")
        if not schalter:
            return raus(f"Konto steht auf '{bf.get('konto', {}).get('aktiv') or '?'}', "
                        f"nicht auf {ext} — und der Konto-Umschalter wurde nicht "
                        "eindeutig gefunden. Konto von Hand umstellen.", "konto")
        ok, f = _tv_klick(schalter["rect"], bf["geo"], klient(), "Konto-Umschalter", trail)
        if not ok:
            return raus(f, "konto")
        _warte(0.5, 0.4)
        t1 = time.time()
        bf = _tv_bf(nach=t1, timeout=6.0) or bf
        treffer = [e for e in (bf.get("konto", {}).get("eintraege") or [])
                   if tv_konto_passt(e.get("text"), ext)]
        if len(treffer) != 1:
            return raus(f"Konto {ext} in der Liste nicht eindeutig gefunden "
                        f"({len(treffer)} Treffer bei "
                        f"{len(bf.get('konto', {}).get('eintraege') or [])} Eintraegen). "
                        "Konto von Hand waehlen.", "konto")
        ok, f = _tv_klick(treffer[0]["rect"], bf["geo"], klient(),
                          f"Konto {ext}", trail)
        if not ok:
            return raus(f, "konto")
        _warte(0.8, 0.5)
        bf = _tv_bf(nach=time.time(), timeout=8.0) or bf
        if not tv_konto_passt(bf.get("konto", {}).get("aktiv"), ext):
            return raus(f"Konto liess sich nicht auf {ext} umstellen (steht auf "
                        f"'{bf.get('konto', {}).get('aktiv') or '?'}'). Von Hand "
                        "umstellen.", "konto")
    trail.append(f"Konto steht auf {ext}")

    # --- Schritt 4: richtiges Instrument -----------------------------------
    ziel_sym = str(cmd["symbol"]).strip()
    if not tv_symbol_passt(bf.get("symbol", {}).get("aktiv"), ziel_sym):
        knopf = _tv_element(bf, "symbol", "knopf")
        if not knopf:
            return raus(f"Chart zeigt '{bf.get('symbol', {}).get('aktiv') or '?'}', "
                        f"statt {ziel_sym} — und die Symbol-Suche wurde nicht "
                        "eindeutig gefunden. Symbol von Hand wechseln.", "symbol")
        ok, f = _tv_klick(knopf["rect"], bf["geo"], klient(), "Symbol-Suche", trail)
        if not ok:
            return raus(f, "symbol")
        _warte(0.6, 0.4)
        bf = _tv_bf(nach=time.time(), timeout=6.0) or bf
        feld = _tv_element(bf, "symbol", "suchfeld")
        if feld:
            ok, f = _tv_klick(feld["rect"], bf["geo"], klient(), "Suchfeld", trail)
            if not ok:
                return raus(f, "symbol")
        # Ohne Klick ins Feld tippen ist der Normalfall: TradingView setzt den
        # Fokus beim Oeffnen der Suche selbst ins Eingabefeld.
        ok, f = _tv_tippen(ziel_sym.upper(), "Symbol", trail)
        if not ok:
            return raus(f, "symbol")
        _warte(0.8, 0.5)
        try:
            from pywinauto import keyboard
            keyboard.send_keys("{ENTER}")
        except Exception:
            return raus("Enter liess sich nicht senden — Symbol von Hand waehlen.",
                        "symbol")
        _warte(1.0, 0.6)
        bf = _tv_bf(nach=time.time(), timeout=8.0) or bf
        if not tv_symbol_passt(bf.get("symbol", {}).get("aktiv"), ziel_sym):
            return raus(f"Symbol liess sich nicht auf {ziel_sym} stellen (Chart "
                        f"zeigt '{bf.get('symbol', {}).get('aktiv') or '?'}'). "
                        "Von Hand wechseln.", "symbol")
    trail.append(f"Chart zeigt {ziel_sym}")

    # --- Schritt 5a: Order-Ticket oeffnen ----------------------------------
    richtung = str(cmd["richtung"]).lower()
    knopf = _tv_element(bf, "panel", "kaufen" if richtung == "buy" else "verkaufen")
    if not knopf:
        return raus(f"{'Kaufen' if richtung == 'buy' else 'Verkaufen'}-Knopf im "
                    "Handelspanel nicht eindeutig gefunden — Order von Hand "
                    "platzieren. (Der naechste Versuch bringt einen "
                    "Kandidaten-Dump mit.)", "ticket")
    ok, f = _tv_klick(knopf["rect"], bf["geo"], klient(),
                      "Kaufen" if richtung == "buy" else "Verkaufen", trail)
    if not ok:
        return raus(f, "ticket")
    _warte(0.9, 0.6)
    bf = _tv_bf(nach=time.time(), timeout=8.0) or bf
    if not (bf.get("ticket") or {}).get("offen"):
        return raus("Order-Ticket ging nicht auf — im TradingView nachsehen, ob "
                    "ein Dialog haengt.", "ticket")
    trail.append("Order-Ticket offen")

    # --- Schritt 5b: Menge, TP, SL -----------------------------------------
    menge_el = _tv_element(bf, "ticket", "menge")
    if not menge_el:
        return raus("Mengenfeld im Order-Ticket nicht eindeutig gefunden — "
                    "Ticket steht offen, Order NICHT platziert. Von Hand "
                    "ausfuellen oder abbrechen.", "menge")
    ok, f = _tv_klick(menge_el["rect"], bf["geo"], klient(), "Mengenfeld", trail)
    if not ok:
        return raus(f, "menge")
    ok, f = _tv_tippen(tv_zahl_text(cmd["volumen"]), "Menge", trail)
    if not ok:
        return raus(f, "menge")

    mit_sltp = cmd.get("sl_usd") not in (None, "", 0)
    if mit_sltp:
        for feld, einheit, wert, name in (
                ("sl", "sl_einheit", cmd["sl_usd"], "Stop Loss"),
                ("tp", "tp_einheit", cmd["tp_usd"], "Take Profit")):
            # Pro Feld ein FRISCHER Stand: das Ticket rendert nach jeder
            # Eingabe neu (Bracket-Zeilen klappen auf, Zahlen formatieren
            # sich), ein Rechteck von vor zwei Klicks waere dann verschoben.
            bf = _tv_bf(nach=time.time(), timeout=6.0) or bf
            el = _tv_element(bf, "ticket", feld)
            if not el:
                return raus(f"{name}-Feld im Order-Ticket nicht gefunden — Ticket "
                            "steht offen, Order NICHT platziert. Entweder von "
                            "Hand ausfuellen oder den SL/TP-Schalter im Order-"
                            "Popup ausschalten.", "sltp")
            eh = (bf.get("ticket") or {}).get(einheit) or {}
            if not tv_einheit_ist_geld(eh.get("text")):
                return raus(f"{name} steht nicht auf Geld/$ (Einheit: "
                            f"'{(eh.get('text') or '?')[:20]}') — {wert} waere "
                            "dort eine ganz andere Distanz. Einheit im Ticket "
                            "auf $ stellen, dann erneut. Order NICHT platziert.",
                            "sltp")
            ok, f = _tv_klick(el["rect"], bf["geo"], klient(), f"{name}-Feld", trail)
            if not ok:
                return raus(f, "sltp")
            ok, f = _tv_tippen(tv_zahl_text(wert), name, trail)
            if not ok:
                return raus(f, "sltp")

    # --- Schritt 5c: alles ZURUECKLESEN, bevor geklickt wird ---------------
    # Das Userscript liest den echten DOM-value. Erst wenn Menge (und ggf.
    # SL/TP) beweisbar drinstehen, faellt der unumkehrbare Klick.
    bf = _tv_bf(nach=time.time(), timeout=8.0)
    if not bf:
        return raus("Kein frischer Bedienfeld-Stand zum Ruecklesen — Order NICHT "
                    "platziert, Ticket steht offen.", "ruecklesen")
    soll = float(cmd["volumen"])
    ist = tv_de_zahl(((bf.get("ticket") or {}).get("menge") or {}).get("wert"))
    if ist is None or abs(ist - soll) > 1e-9:
        return raus(f"Menge im Ticket steht auf '{ist if ist is not None else '?'}' "
                    f"statt {tv_zahl_text(soll)} — Order NICHT platziert.",
                    "ruecklesen")
    trail.append(f"Menge zurueckgelesen: {tv_zahl_text(ist)}")
    if mit_sltp:
        for feld, wert, name in (("sl", cmd["sl_usd"], "Stop Loss"),
                                 ("tp", cmd["tp_usd"], "Take Profit")):
            ist = tv_de_zahl(((bf.get("ticket") or {}).get(feld) or {}).get("wert"))
            if ist is None or abs(ist - float(wert)) > 0.01:
                return raus(f"{name} im Ticket steht auf "
                            f"'{ist if ist is not None else '?'}' statt "
                            f"{tv_zahl_text(wert)} — Order NICHT platziert.",
                            "ruecklesen")
            trail.append(f"{name} zurueckgelesen: {tv_zahl_text(ist)}")

    senden = _tv_element(bf, "ticket", "senden")
    if not senden:
        return raus("Senden-Knopf im Order-Ticket nicht eindeutig gefunden — "
                    "alles ist ausgefuellt, der letzte Klick fehlt. Im "
                    "TradingView selbst bestaetigen.", "senden")

    # Probelauf (30.08.2026, Finns erster Test fiel auf einen geschlossenen
    # Markt): die GANZE Kette laufen lassen — Tab, Konto, Symbol, Ticket,
    # Menge, SL/TP, Ruecklesen, und sogar den Senden-Knopf suchen — nur nicht
    # klicken. Genau hier, NACH der Senden-Suche: ein Probelauf, der den
    # letzten Fund auslaesst, hat die interessanteste Frage nicht beantwortet.
    # Das Ticket bleibt danach ausgefuellt und offen; wegklicken ist Handarbeit
    # (ein Abbruch-Klick waere wieder ein geratener Klick).
    if cmd.get("probe"):
        res["ok"] = True
        res["probe"] = True
        return raus("Probelauf durch: Tab, Konto, Symbol, Ticket, Menge"
                    + (" und SL/TP" if mit_sltp else "")
                    + " sitzen — der Senden-Knopf wurde gefunden und ABSICHTLICH "
                      "nicht geklickt. Nichts platziert. Das Ticket steht "
                      "ausgefuellt offen und kann von Hand geschlossen werden.",
                    "probe", retry_ok=True)

    # ═══ AB HIER UNUMKEHRBAR ═══════════════════════════════════════════════
    ok, f = _tv_klick(senden["rect"], bf["geo"], klient(), "Order senden", trail)
    if not ok:
        # Der Klick kam nachweislich nicht raus (SendInput abgelehnt oder Punkt
        # unplausibel) — also ist nichts gesendet und retry_ok bleibt True.
        return raus(f, "senden")
    res["retry_ok"] = False
    trail.append("Senden geklickt — ab hier zaehlt nur noch der Reader")

    # --- Bestaetigung: NUR aus dem Positions-Snapshot -----------------------
    ende = time.time() + 25.0
    while time.time() < ende:
        _warte(0.4, 0.3)
        pos, an2 = _tv_positionen()
        if pos is None:
            continue
        jetzt = tv_menge_summe(pos, cmd["symbol"], cmd["richtung"])
        if jetzt - menge_vorher >= soll - 1e-9:
            res["ok"] = True
            res["menge"] = jetzt - menge_vorher
            treffer = next((p for p in pos
                            if tv_symbol_root(p.get("symbol")) == tv_symbol_root(cmd["symbol"])
                            and tv_seite_passt(p.get("seite"), cmd["richtung"])), {})
            res["einstieg"] = treffer.get("einstieg")
            res["tv_symbol"] = treffer.get("symbol")
            trail.append(f"Position bestaetigt: +{jetzt - menge_vorher:g} @ "
                         f"{treffer.get('einstieg') or '?'}")
            return raus(f"Order platziert: {richtung.upper()} "
                        f"{tv_zahl_text(soll)} {treffer.get('symbol') or ziel_sym}"
                        f" @ {treffer.get('einstieg') or '?'}"
                        + (f" · TP ${tv_zahl_text(cmd['tp_usd'])} / SL "
                           f"${tv_zahl_text(cmd['sl_usd'])}" if mit_sltp
                           else " · ohne SL/TP"),
                        "fertig", retry_ok=False)

    # Kein Positionszuwachs in 25 s. Das kann Ablehnung sein, ein zweiter
    # Bestaetigungsschritt im Ticket oder eine haengende Verbindung — welches
    # davon, kann der Bot NICHT wissen, und genau deshalb nie "nochmal".
    bf_ende = _tv_bf(timeout=3.0) or {}
    offen = (bf_ende.get("ticket") or {}).get("offen")
    return raus("Ergebnis UNKLAR: 25 s nach dem Senden meldet der Reader keine "
                "neue Position" + (" und das Order-Ticket steht noch offen "
                "(Bestaetigungsschritt?)" if offen else "") +
                ". Erst in TradingView nachsehen, ob die Order liegt — NICHT "
                "blind erneut starten.", "unklar", retry_ok=False)


def _ist_order_dialog(win):
    """Ein Fenster als Order-Dialog erkennen: Titel beginnt mit 'Order' ODER es
    traegt eine ComboBox + mind. 3 Edit-Felder (die Symbol/Volumen/SL/TP-Maske)."""
    try:
        t = (win.window_text() or "")
        if t.strip().lower().startswith("order"):
            return True
        combos = win.descendants(control_type="ComboBox")
        edits = win.descendants(control_type="Edit")
        return bool(combos) and len(edits) >= 3
    except Exception:
        return False


def _map_felder(dlg):
    """Edit-Felder nach ihrer BESCHRIFTUNG zuordnen statt nach Position (Fund
    15.08.2026: der Positions-Index passte nicht — Preis landete im Volumen-Feld,
    TP blieb leer). Sucht zu den Labels 'Volumen'/'Stop Loss'/'Take Profit' das
    naechste Edit-Feld rechts daneben in derselben Zeile. Rueckgabe-Dict; fehlt
    ein Schluessel, faellt run() fuer den auf den Index zurueck."""
    def _mitte_y(r):
        return (r.top + r.bottom) / 2
    labels = {}
    try:
        for t in dlg.descendants(control_type="Text"):
            txt = (t.window_text() or "").strip().lower().rstrip(":").replace(" ", "")
            r = t.rectangle()
            if txt in ("volumen", "volume"):
                labels["volumen"] = r
            elif txt in ("stoploss", "s/l", "sl"):
                labels["sl"] = r
            elif txt in ("takeprofit", "t/p", "tp"):
                labels["tp"] = r
    except Exception:
        pass
    edits = []
    try:
        for e in dlg.descendants(control_type="Edit"):
            try:
                edits.append((e, e.rectangle()))
            except Exception:
                continue
    except Exception:
        pass
    out = {}
    for key, lr in labels.items():
        best, bestd = None, 1e9
        for e, er in edits:
            if er.left >= lr.left - 4 and abs(_mitte_y(er) - _mitte_y(lr)) < 22:
                d = er.left - lr.left
                if d < bestd:
                    bestd, best = d, e
        if best is not None:
            out[key] = best
    return out


def _dialog_struktur(dlg):
    """Kurzer Struktur-Dump fuer die Diagnose: Labels + Edit-Werte."""
    teile = []
    try:
        for c in dlg.descendants():
            try:
                ct = c.element_info.control_type
                if ct in ("Edit", "Text", "ComboBox", "Button"):
                    teile.append(f"{ct}:{(c.window_text() or '')[:16]}")
            except Exception:
                continue
    except Exception:
        pass
    return " | ".join(teile[:40])


def _finde_order_dialog(hauptfenster, timeout=10.0):
    """Nach F9: den Order-Dialog suchen — als TOP-LEVEL-Fenster UND als
    Kind-Fenster des Terminals (Fund 15.08.2026: MT5 haengt den F9-Dialog als
    Child ans Hauptfenster, die reine Top-Level-Suche fand ihn nie, obwohl er
    sichtbar offen war). Titel 'Order…' oder die typische Feldstruktur."""
    from pywinauto import Desktop
    pid = hauptfenster.element_info.process_id
    ende = time.time() + timeout
    while time.time() < ende:
        # a) Top-Level-Fenster desselben Prozesses
        try:
            for w in Desktop(backend="uia").windows():
                try:
                    if w.element_info.process_id == pid and w.is_visible() \
                            and w.element_info.class_name != MT5_KLASSE \
                            and _ist_order_dialog(w):
                        return w
                except Exception:
                    continue
        except Exception:
            pass
        # b) Kind-/Nachkommen-Fenster des Hauptfensters
        try:
            for d in hauptfenster.descendants(control_type="Window"):
                if _ist_order_dialog(d):
                    return d
        except Exception:
            pass
        # c) Direkter Griff per Titel-Regex (owned window)
        try:
            cand = hauptfenster.child_window(title_re="(?i)^order")
            if cand.exists(timeout=0.3):
                return cand.wrapper_object()
        except Exception:
            pass
        _warte(0.3, 0.3)
    return None


def _feld_lesen(el):
    """Den INHALT eines Felds lesen — window_text() liefert bei UIA oft nur den
    NAMEN des Felds, also die Beschriftung 'Volumen:' (Fund 18.08.2026 im
    Trade-Start-Check: das Ruecklesen verglich gegen das Label und brach ab,
    obwohl das Tippen laengst funktionierte). Deshalb: ValuePattern zuerst,
    dann Legacy-Value, window_text() nur als letzter Rest."""
    try:
        v = el.get_value()
        if v is not None:
            return str(v)
    except Exception:
        pass
    try:
        v = el.iface_value.CurrentValue
        if v is not None:
            return str(v)
    except Exception:
        pass
    try:
        v = (el.legacy_properties() or {}).get("Value")
        if v is not None:
            return str(v)
    except Exception:
        pass
    try:
        return el.window_text() or ""
    except Exception:
        return ""


def _feld_tippen(el, wert, name, trail):
    """Wert per ECHTEN Tastenanschlaegen eintippen (18.08.2026, Finns Fund am
    PC: set_edit_text/set_text malt den Text nur in den Feld-Speicher — kein
    WM_CHAR-Event, MT5 parst nie und rechnet intern mit dem ALTEN Wert weiter.
    Sichtbar stand '2' im Volumen-Feld, das Label daneben rechnete 0.01).
    Deshalb: Fokus OHNE Cursor (set_focus — Fenster-/Tastaturbefehle gehen auch
    ueber Parsec durch, der Parsec-Fund 16.08. betraf nur Maus-Klicks), dann
    tippen wie ein Mensch, dann den Feldtext ZURUECKLESEN und als Zahl
    vergleichen. KEIN TAB danach (18.08.2026, .53): jedes WM_CHAR aktualisiert
    MT5s internen Wert schon live (das Label neben dem Feld rechnet beim Tippen
    mit), und TAB schob den Fokus ins naechste Feld — dort koennte eine
    spaetere Leertaste landen."""
    for _versuch in (1, 2):
        try:
            el.set_focus()
            _warte(0.1, 0.15)
            # Feld GARANTIERT leeren (18.08.2026, Finns 22-Einwand: steht vom
            # letzten Trade noch '2' drin und es kommt '2' dazu, sind es 22).
            # Strg+A UND Pos1+Shift+Ende — je nach Edit-Control greift nur
            # eines von beiden. Danach ZURUECKLESEN, ob es wirklich leer ist.
            el.type_keys("^a{DELETE}", set_foreground=False)
            el.type_keys("{HOME}+{END}{DELETE}", set_foreground=False)
            _warte(0.08, 0.1)
            rest = (_feld_lesen(el) or "").strip()
            if rest:
                # Feld fuellt sich selbst wieder (Auto-Format)? Dann alles
                # markieren und DRUEBERtippen — die Auswahl wird ersetzt, das
                # Ruecklesen unten beweist das Ergebnis.
                trail.append(f"{name}-Feld leert nicht ('{rest}') — tippe ueber die Auswahl")
                el.type_keys("^a", set_foreground=False)
                el.type_keys("{HOME}+{END}", set_foreground=False)
            el.type_keys(str(wert), with_spaces=False, set_foreground=False)
            _warte(0.12, 0.15)
            ist = _feld_lesen(el)
            if zahl_gleich(ist, wert):
                trail.append(f"{name} getippt: {wert}")
                return True
            trail.append(f"{name}-Ruecklesen zeigt '{ist.strip()}' statt {wert}")
        except Exception:
            continue
    trail.append(f"{name} NICHT uebernommen: {wert}")
    return False


def _ist_aendern_dialog(win):
    """Der Aendern-Dialog einer Position: traegt den langen Aendern-Knopf.
    Der F9-Neu-Order-Dialog hat keinen solchen Knopf — damit ist verwechseln
    ausgeschlossen (hier darf NIE ein Buy/Sell-Knopf gedrueckt werden)."""
    try:
        for b in win.descendants(control_type="Button"):
            if ist_aendern_knopf(b.window_text() or ""):
                return True
    except Exception:
        pass
    return False


def _dialog_gehoert_zu(dlg, ticket):
    """Gehoert der Aendern-Dialog wirklich zu UNSERER Position? Der lange
    Aendern-Knopf traegt die Ticket-Nummer ('#123456789 ... aendern'). Steht
    irgendwo eine ANDERE lange Nummer und unsere nirgends, ist es der Dialog
    einer fremden Position — dort darf nichts getippt werden. 7+ Stellen,
    damit Kurse (29989.33) nicht als Ticket zaehlen; zeigt der Dialog gar
    keine lange Nummer, gibt es keinen Widerspruch -> weitermachen."""
    zahlen = []
    try:
        for c in dlg.descendants():
            try:
                t = c.window_text() or ""
            except Exception:
                continue
            zahlen.extend(re.findall(r"(?<!\d)(\d{7,})(?!\d)", t))
    except Exception:
        pass
    if not zahlen:
        return True
    return str(int(ticket)) in zahlen


def _finde_aendern_dialog(hauptfenster, timeout=3.0):
    """Wie _finde_order_dialog (Top-Level UND Kind-Fenster — der F9-Fund vom
    15.08.2026 gilt fuer jeden MT5-Dialog), aber auf den Aendern-Dialog."""
    from pywinauto import Desktop
    pid = hauptfenster.element_info.process_id
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            for w in Desktop(backend="uia").windows():
                try:
                    if w.element_info.process_id == pid and w.is_visible() \
                            and w.element_info.class_name != MT5_KLASSE \
                            and _ist_aendern_dialog(w):
                        return w
                except Exception:
                    continue
        except Exception:
            pass
        try:
            for d in hauptfenster.descendants(control_type="Window"):
                if _ist_aendern_dialog(d):
                    return d
        except Exception:
            pass
        _warte(0.3, 0.3)
    return None


def _menue_offen():
    """Steht irgendwo noch ein Popup-Menue (#32768/Menu) offen? Der Beweis-
    Check fuer _menuepunkt_ausloesen: nur ein GESCHLOSSENES Menue belegt,
    dass der Punkt-Klick wirklich gezuendet hat."""
    from pywinauto import Desktop
    try:
        for m in Desktop(backend="uia").windows():
            try:
                if m.element_info.class_name == "#32768" \
                        or m.element_info.control_type == "Menu":
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _menuepunkt_ausloesen(it):
    """Einen gefundenen Menuepunkt WIRKLICH ausloesen — mit Beweis (30.08.2026,
    Finns Fund an beiden PCs: Kontextmenue offen, 'Aendern oder Loeschen'
    markiert, und nichts passiert; genau dieser eingefrorene Zustand stand auf
    seinem Screenshot). Der alte Weg meldete nach invoke() blind Erfolg, und
    der click_input-Fallback ist das getrennte Bewegen-dann-Klicken aus dem
    Parsec-Fund vom 16.08.2026 — im restlichen Bot laengst verboten, nur hier
    hatte die Lehre gefehlt. Deshalb: nach JEDEM Versuch pruefen, ob das Menue
    zu ist — nur DAS beweist den Klick. Zuendet invoke() nicht, klickt der
    Haus-Weg _klick_absolut (EIN atomarer SendInput-Batch) auf die Punkt-Mitte;
    geklickt wird dabei nur, solange das Menue nachweislich noch offen ist
    (nie ein Streuklick in den Chart darunter). click_input bleibt letzte
    Reserve. True = Menue zu, Klick bewiesen."""
    try:
        it.invoke()
    except Exception:
        pass
    _warte(0.25, 0.2)
    if not _menue_offen():
        return True
    try:
        r = it.rectangle()
        _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=3)
        _klick_absolut(r.mid_point().x, r.mid_point().y)
        _warte(0.25, 0.2)
        if not _menue_offen():
            return True
    except Exception:
        pass
    try:
        it.click_input()
        _warte(0.25, 0.2)
        return not _menue_offen()
    except Exception:
        return False


def _kontextmenue_aendern_klicken(timeout=2.0):
    """Ein offenes Kontextmenue nach 'Aendern...'/'Modify...' absuchen und den
    Punkt ausloesen. Menues sind Standard-Windows-Fenster (#32768) — die sieht
    UIA auch bei MT5. Der Punkt heisst deutsch 'Aendern oder Loeschen', darf
    also NICHT durch den Loeschen-Ausschluss von ist_aendern_knopf laufen.

    Rueckgabe seit 30.08.2026 dreiwertig statt bool — der Zeilen-Scan braucht
    den Unterschied fuer seine Selbst-Diagnose:
      'geklickt'   Punkt ausgeloest, Menue nachweislich zu
      'ausgegraut' Menue offen, aber der Punkt ist deaktiviert — der
                   Rechtsklick lag NEBEN der Positions-Zeile (leere Liste /
                   Kontostand-Zeile). Vorher hat der Bot solche Punkte blind
                   'geklickt', Erfolg gemeldet und 1,2 s auf einen Dialog
                   gewartet, der nie kommen konnte.
      'kein_menue' gar kein Menue(-Punkt) innerhalb des Timeouts gefunden,
                   ODER der Punkt liess sich trotz aller drei Klick-Wege
                   nicht ausloesen."""
    from pywinauto import Desktop
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            for m in Desktop(backend="uia").windows():
                try:
                    if m.element_info.class_name != "#32768" \
                            and m.element_info.control_type != "Menu":
                        continue
                    for it in m.descendants(control_type="MenuItem"):
                        t = (it.window_text() or "").lower()
                        if any(k in t for k in ("ändern", "aendern", "andern", "modify")):
                            try:
                                if not it.is_enabled():
                                    return "ausgegraut"
                            except Exception:
                                pass
                            return "geklickt" if _menuepunkt_ausloesen(it) else "kein_menue"
                except Exception:
                    continue
        except Exception:
            pass
        _warte(0.2, 0.25)
    return "kein_menue"


def _kontextmenue_close_klicken(timeout=2.0):
    """Gegenstueck zu _kontextmenue_aendern_klicken fuer den Close-Weg
    (28.08.2026, Remote-Close): ausgeloest wird AUSSCHLIESSLICH ein Menuepunkt,
    der ist_close_menuepunkt besteht — nie ein anderer, nie blind. Die Alle-/
    Massen-Ausschluesse stecken in der Erkennung selbst. Rueckgabe dreiwertig
    wie beim Aendern-Weg (30.08.2026): 'geklickt' | 'ausgegraut' | 'kein_menue',
    Ausloesen mit Beweis ueber _menuepunkt_ausloesen."""
    from pywinauto import Desktop
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            for m in Desktop(backend="uia").windows():
                try:
                    if m.element_info.class_name != "#32768" \
                            and m.element_info.control_type != "Menu":
                        continue
                    for it in m.descendants(control_type="MenuItem"):
                        if ist_close_menuepunkt(it.window_text()):
                            try:
                                if not it.is_enabled():
                                    return "ausgegraut"
                            except Exception:
                                pass
                            return "geklickt" if _menuepunkt_ausloesen(it) else "kein_menue"
                except Exception:
                    continue
        except Exception:
            pass
        _warte(0.2, 0.25)
    return "kein_menue"


def _finde_close_dialog(hauptfenster, ticket):
    """Close-Dialog erkennen — ueber den Knopf, der den Close-Auftrag fuer
    GENAU dieses Ticket traegt (ist_schliessen_knopf: die Ticket-Gegenpruefung
    ist Teil der Erkennung). Rueckgabe (dialog, knopf) oder (None, None).
    EIN Durchlauf — die Wiederholung taktet der Aufrufer, weil dort parallel
    lesend auf 'Position schon weg' geprueft wird (Ein-Klick-Modus)."""
    from pywinauto import Desktop
    fenster = []
    try:
        pid = hauptfenster.element_info.process_id
        for w in Desktop(backend="uia").windows():
            try:
                if w.element_info.process_id == pid and w.is_visible() \
                        and w.element_info.class_name != MT5_KLASSE:
                    fenster.append(w)
            except Exception:
                continue
    except Exception:
        pass
    try:
        fenster.extend(hauptfenster.descendants(control_type="Window"))
    except Exception:
        pass
    for w in fenster:
        try:
            for b in w.descendants(control_type="Button"):
                if ist_schliessen_knopf(b.window_text(), ticket):
                    return w, b
        except Exception:
            continue
    return None, None


def _fremde_dialoge_schliessen(hauptfenster):
    """Versehentlich geoeffnete Fenster (z.B. EA-Eigenschaften) wieder zu —
    IMMER ueber Abbrechen/ESC, NIE ueber OK (18.08.2026: der .54-Doppelklick
    traf den Navigator, der ProphosHedgeReader-Dialog ging auf, und das ESC
    ans Hauptfenster hat ihn nicht geschlossen — er blieb bei Finn stehen).
    Aendern-Dialoge werden verschont, um die kuemmert sich der Aufrufer."""
    from pywinauto import Desktop
    try:
        pid = hauptfenster.element_info.process_id
        for d in Desktop(backend="uia").windows():
            try:
                if d.element_info.process_id != pid or not d.is_visible() \
                        or d.element_info.class_name == MT5_KLASSE \
                        or _ist_aendern_dialog(d):
                    continue
                zu = False
                for b in d.descendants(control_type="Button"):
                    if (b.window_text() or "").strip().lower() in ("abbrechen", "cancel"):
                        try:
                            b.click()
                            zu = True
                        except Exception:
                            pass
                        break
                if not zu:
                    d.type_keys("{ESC}", set_foreground=False)
            except Exception:
                continue
    except Exception:
        pass


def _reihen_scan(w, ticket, trail, maus_grenze, anker_pfad=None):
    """Finns Weg als Band-Scan, OHNE jeden UIA-Anker (18.08.2026: auf diesem
    Build sind Handel-Liste, Kontostand-Zeile UND der Position-aendern-Reiter
    im frischen F9-Dialog fuer UIA unsichtbar — der .58-Lauf hat den Reiter-
    Weg widerlegt). Die Positions-Zeile liegt irgendwo im unteren Band des
    Fensters, also wird das Band abgetastet. Pro Punkt: RECHTSKLICK -> nur
    einen LESBAREN Menuepunkt 'Aendern…' klicken -> Dialog per Ticket
    gegenpruefen. Rechtsklicks sind in Liste und Chart harmlos (oeffnen nur
    Menues), geklickt wird nie blind — 'Position schliessen' kann nicht
    passieren. Zweite Runde als Doppelklick-Scan (oeffnet auf der Zeile
    denselben Dialog, sonst nichts; Tabs-/Statusleiste bleiben unterhalb des
    Bands ausgespart). x liegt bei 40 Prozent der Fensterbreite — unterhalb
    des Charts, weg von Marktuebersicht/Navigator und Ein-Klick-Panel."""
    try:
        hr = w.rectangle()
    except Exception:
        return None
    gx = hr.left + int((hr.right - hr.left) * 0.4)

    # Gemerkter Treffer zuerst (18.08.2026, Finns Kalibrier-Idee — nur dass
    # der Bot selbst mitzaehlt: die Ticket-Pruefung sagt ihm, welcher Klick
    # der richtige war, und der wird hier gespeichert und beim naechsten
    # Trade direkt angesprungen). Passt der Anker nicht mehr (Fenster anders,
    # mehr Zeilen), faellt die Pruefung durch und der Scan uebernimmt.
    punkte = []
    if anker_pfad:
        try:
            with open(anker_pfad, encoding="utf-8") as f:
                a = json.load(f)
            ax = hr.left + int((hr.right - hr.left) * float(a["x_frac"]))
            ay = hr.bottom - int(a["y_off"])
            if maus_grenze is None or ay >= maus_grenze:
                punkte.append(("Anker", ax, ay))
        except Exception:
            pass
    # Erfahrungswert zuerst (18.08.2026, Finns Treffer beim 17. Punkt =
    # -316px): die Suche startet dort, wo die Zeile bei Standard-Toolbox
    # praktisch immer liegt, und faechert von da auf — der pro PC gemerkte
    # Anker schlaegt das ohnehin. Band bis zur HALBEN Fensterhoehe statt hart
    # 400px (30.08.2026, beide PCs trafen nie): eine hoehere Toolbox/andere
    # Aufloesung darf die Zeile nicht aus dem Band schieben; nach oben
    # deckelt ohnehin maus_grenze (untere Fensterhaelfte).
    band_max = max(400, (hr.bottom - hr.top) // 2)
    offsets = sorted(range(60, band_max, 16), key=lambda o: abs(o - 316))
    for off in offsets:
        y = hr.bottom - off
        if maus_grenze is not None and y < maus_grenze:
            continue
        punkte.append((f"-{off}px", gx, y))

    grau = 0   # Punkte, deren Menue offen war, aber 'Aendern' ausgegraut = neben der Zeile
    for runde in ("Rechtsklick-Menue", "Doppelklick"):
        for pname, px_, py_ in punkte:
            if is_paused():
                trail.append("⏸ Echo pausiert — Zeilen-Scan abgebrochen")
                return None
            _maus_fahren(px_, py_, schritte=3)
            # Finns Schritt 1: Zeile markieren, dann erst oeffnen
            _klick_absolut(px_, py_)
            _warte(0.15, 0.2)
            if runde == "Rechtsklick-Menue":
                if not _klick_absolut(px_, py_, taste="rechts"):
                    continue
                _warte(0.25, 0.3)
                st_menue = _kontextmenue_aendern_klicken(timeout=0.8)
                if st_menue != "geklickt":
                    if st_menue == "ausgegraut":
                        grau += 1
                    try:
                        w.type_keys("{ESC}", set_foreground=False)
                    except Exception:
                        pass
                    continue
            else:
                if not _klick_absolut(px_, py_, doppel=True):
                    continue
            d = _finde_aendern_dialog(w, timeout=1.2)
            if d is None:
                # Menue hat geklickt, aber kein Dialog (Punkt lag neben der
                # Zeile, Eintrag ausgegraut) — Menue NICHT offen stehen
                # lassen (Fund aus Finns Screenshot 18.08.)
                try:
                    w.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                continue
            if _dialog_gehoert_zu(d, ticket):
                trail.append(f"Aendern-Dialog offen ({runde}-Scan @ {pname})")
                if anker_pfad:
                    try:
                        with open(anker_pfad, "w", encoding="utf-8") as f:
                            json.dump({"x_frac": (px_ - hr.left) / max(1, hr.right - hr.left),
                                       "y_off": hr.bottom - py_}, f)
                    except Exception:
                        pass
                return d
            try:
                d.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            _fremde_dialoge_schliessen(w)
    # Selbst-Diagnose in die Spur (30.08.2026): Geometrie + Ausgegraut-Zaehler
    # sagen beim naechsten Fehlversuch sofort, WORAN es lag — nur ausgegraute
    # Punkte = alle Klicks lagen neben der Zeile (Geometrie/Band), gar keine
    # Menues = die Rechtsklicks kommen nicht an (Klick-Weg).
    trail.append(f"Zeilen-Scan ohne Treffer (Fenster {hr.right - hr.left}x{hr.bottom - hr.top}, "
                 f"Band -60..-{band_max}px, x={gx}, {len(punkte)} Punkte, {grau}x ausgegraut)")
    return None


def _handel_tab_aktivieren(w, trail=None, maus_grenze=None):
    """Toolbox auf den 'Handel'-Tab stellen, BEVOR der Bot die Position
    anklickt (28.08.2026, Finns Live-Fund auf Moritz' PC): nach einem frischen
    Terminal-Start stand die Toolbox auf 'Posteingang' (die 'neuer Account'-
    Mail). Die Order ging ueber den F9-Dialog clean durch, aber das SL/TP-
    Aendern klickte ins Leere, weil die Positionsliste gar nicht sichtbar war —
    genau Finns Analyse: erst pruefen/auf 'Handel' gehen, dann die Zeile suchen.

    Best-Effort und idempotent: bevorzugt das UIA-Select-Pattern (KEIN
    Maus-Klick, also nie im Chart-/Ein-Klick-Panel-Bereich, wo ein Klick eine
    Order waere); der Maus-Fallback klickt nur im UNTEREN Fensterbereich, wo die
    Tabs strukturell liegen. Findet der Bot den Tab nicht, laeuft der bisherige
    Positions-Scan unveraendert weiter (nichts wird schlechter)."""
    def _passt(t):
        t = (t or "").strip()
        return t == "Handel" or t == "Trade" or t.startswith(("Handel", "Trade"))
    # Breit suchen: je nach MT5-Build ist der Toolbox-Reiter TabItem, Custom,
    # Button oder Text — notfalls der ganze Baum (None). Alle Treffer sammeln.
    treffer = []
    for ct in ("TabItem", "Custom", "Button", "Text", None):
        try:
            els = w.descendants(control_type=ct) if ct else w.descendants()
        except Exception:
            continue
        for el in els:
            try:
                if _passt(el.window_text()):
                    treffer.append(el)
            except Exception:
                continue
        if treffer:
            break
    if not treffer:
        if trail is not None:
            trail.append("Handel-Tab: kein Element gefunden — Positions-Scan wie gehabt")
        return False
    # WICHTIG (28.08.2026, Finns Fund: select() wechselte den Reiter auf seinem
    # Build NICHT, warf aber auch keinen Fehler → alter Code gab faelschlich
    # 'erledigt' zurueck): select() nur STILL mitnehmen, verlassen tun wir uns
    # auf den echten Maus-Klick auf den Reiter (der liegt strukturell unten in
    # der Toolbox, also kein Chart-/Order-Bereich).
    for el in treffer:
        try:
            el.select()
        except Exception:
            pass
        try:
            r = el.rectangle()
            unten = (maus_grenze is None) or (r.top >= maus_grenze)
            if unten and r.width() > 0 and r.height() > 0:
                cx, cy = r.mid_point().x, r.mid_point().y
                _maus_fahren(cx, cy, schritte=4)
                _klick_absolut(cx, cy)
                if trail is not None:
                    trail.append(f"Handel-Tab geklickt @({cx},{cy})")
                _warte(0.3, 0.3)
                return True
        except Exception:
            continue
    if trail is not None:
        trail.append(f"Handel-Tab: {len(treffer)} Element(e) gefunden, keins unten klickbar")
    return False


def _sltp_klicken(w, ticket, symbol, sl_text, tp_text, trail, anker_pfad=None):
    """SL/TP PER KLICK an die offene Position haengen (18.08.2026, Finns
    Ansage): Zeile der Position in der Handel-Liste finden, Aendern-Dialog
    oeffnen, die vom echten Fill gerechneten Kurse eintippen, Aendern klicken.
    Mehrere Oeffnungswege in fester Reihenfolge (cursor-unabhaengig zuerst,
    Parsec-Fund 16.08.2026); jeder Versuch wird in der Spur vermerkt. Ob es
    WIRKLICH gegriffen hat, prueft ausschliesslich der Aufrufer — lesend."""
    # 1) Kandidaten-Zeilen suchen: Ticket-Treffer zuerst; sonst Zeilen, die das
    #    Symbol PLUS weitere Daten tragen (18.08.2026, Live-Fund: der Dialog
    #    liess sich nie oeffnen — je nach MT5-Build steht das Ticket nicht im
    #    UIA-Namen der Handel-Zeile). Marktuebersicht-Zeilen (nur Symbolname)
    #    fallen durch die Laengen-Bedingung. Welche Zeile die richtige war,
    #    entscheidet am Ende IMMER der Dialog selbst (_dialog_gehoert_zu).
    try:
        haupt_r = w.rectangle()
        maus_grenze = haupt_r.top + (haupt_r.bottom - haupt_r.top) // 2
    except Exception:
        maus_grenze = None
    _fremde_dialoge_schliessen(w)
    # Toolbox zuerst auf 'Handel' — sonst ist die Positionsliste unsichtbar
    # (28.08.2026, frischer Terminal-Start stand auf 'Posteingang', s.o.).
    _handel_tab_aktivieren(w, trail, maus_grenze)

    # Echo pausiert? (28.08.2026, Not-Aus) — dann gar nicht erst anfangen zu
    # klicken. Die Order ist da laengst platziert; SL/TP traegt Finn von Hand
    # nach oder nach dem Fortsetzen ein neuer Lauf.
    if is_paused():
        trail.append("⏸ Echo pausiert — keine SL/TP-Klicks")
        return None

    # 0) Finns Weg als Band-Scan — braucht keinerlei UIA-Anker (s. _reihen_scan)
    dlg = _reihen_scan(w, ticket, trail, maus_grenze, anker_pfad=anker_pfad)

    kandidaten, ticket_da = [], False
    if dlg is None:
        try:
            for ct in ("DataItem", "ListItem", "TreeItem", "Custom", "Text", None):
                for el in (w.descendants(control_type=ct) if ct else w.descendants()):
                    try:
                        t = el.window_text() or ""
                    except Exception:
                        continue
                    if zeile_nennt_ticket(t, ticket):
                        kandidaten.insert(0, el)
                        ticket_da = True
                    elif ist_handelszeile(t, symbol) and len(kandidaten) < 3:
                        kandidaten.append(el)
                if ticket_da:
                    break
        except Exception:
            pass
        trail.append(f"Zeilen-Kandidaten: {len(kandidaten)}"
                     + (" (Ticket dabei)" if ticket_da else ""))

    # 2) Je Kandidat den Aendern-Dialog oeffnen — SendInput-Doppelklick zuerst
    #    (der Weg, den auch die Hand nimmt), dann die synthetischen Wege.
    #    JEDER geoeffnete Dialog wird per Ticket gegengeprueft, bevor getippt
    #    wird — nie die falsche Position anfassen.
    for zeile in kandidaten[:3]:
        # Zwischen den Kandidaten pruefen: hat Finn waehrenddessen pausiert,
        # sofort raus statt weiter am Terminal herumzuklicken (28.08.2026).
        if is_paused():
            trail.append("⏸ Echo pausiert — Klick-Versuche abgebrochen")
            break
        try:
            r = zeile.rectangle()
            mx, my = r.mid_point().x, r.mid_point().y
        except Exception:
            r = None
            mx = my = None
        # Maus-Klicks nur im UNTEREN Fensterbereich (Toolbox): oben liegen
        # Chart und Ein-Klick-Panel — ein Doppelklick dort waere im
        # schlimmsten Fall eine ORDER (18.08.2026, nach dem Navigator-Fund).
        maus_ok = (mx is not None and maus_grenze is not None
                   and r.top >= maus_grenze)
        if maus_ok:
            _maus_fahren(mx, my, schritte=8)
            # Finns Reihenfolge (18.08.2026, manuell vorgemacht): erst die
            # Zeile ANKLICKEN (markieren), dann oeffnen
            _klick_absolut(mx, my)
            _warte(0.2, 0.25)

        def _weg_doppel():
            if not maus_ok or not _klick_absolut(mx, my, doppel=True):
                raise RuntimeError("Maus hier nicht erlaubt/fehlgeschlagen")

        def _weg_invoke():
            zeile.invoke()

        def _weg_dodefault():
            zeile.iface_legacyiaccessible.DoDefaultAction()

        def _weg_menue():
            zeile.select()
            _warte(0.2, 0.25)
            w.type_keys("+{F10}")
            _warte(0.4, 0.35)
            if _kontextmenue_aendern_klicken() != "geklickt":
                raise RuntimeError("kein Menuepunkt")

        def _weg_rechtsklick():
            if not maus_ok or not _klick_absolut(mx, my, taste="rechts"):
                raise RuntimeError("Maus hier nicht erlaubt/fehlgeschlagen")
            _warte(0.4, 0.35)
            if _kontextmenue_aendern_klicken() != "geklickt":
                raise RuntimeError("kein Menuepunkt")

        # Reihenfolge nach Finns Hand-Weg: Rechtsklick-Menue zuerst, dann
        # Doppelklick (oeffnet denselben Dialog), dann die synthetischen Wege
        for name, weg in (("Rechtsklick-Menue", _weg_rechtsklick),
                          ("SendInput-Doppelklick", _weg_doppel),
                          ("invoke", _weg_invoke),
                          ("DoDefaultAction", _weg_dodefault),
                          ("Shift-F10-Menue", _weg_menue)):
            try:
                weg()
            except Exception:
                continue
            d = _finde_aendern_dialog(w, timeout=1.5)
            if d is not None:
                if _dialog_gehoert_zu(d, ticket):
                    dlg = d
                    trail.append(f"Aendern-Dialog offen ({name})")
                    break
                trail.append(f"Dialog einer ANDEREN Position ({name}) — geschlossen")
                try:
                    d.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
            # haengengebliebene Menues UND versehentlich geoeffnete Fenster
            # (EA-Dialog!) schliessen, bevor der naechste Weg drankommt
            try:
                w.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            _fremde_dialoge_schliessen(w)
        if dlg is not None:
            break

    if dlg is None:
        # Geometrie-Fallback (18.08.2026): sieht UIA die Handel-Zeilen nicht,
        # dient die 'Kontostand'-Zeile als Anker — die Positionen stehen im
        # Handel-Tab DIREKT darueber. Blind-Doppelklick in die Zeile(n) ueber
        # dem Anker; ob der RICHTIGE Dialog aufging, entscheidet wie immer
        # _dialog_gehoert_zu, und die Maus bleibt im unteren Fensterbereich.
        anker = None
        try:
            for ct in ("Text", None):
                for el in (w.descendants(control_type=ct) if ct else w.descendants()):
                    try:
                        if (el.window_text() or "").strip().lower().startswith("kontostand"):
                            anker = el.rectangle()
                            break
                    except Exception:
                        continue
                if anker is not None:
                    break
        except Exception:
            pass
        trail.append("Kontostand-Anker " + ("gefunden" if anker is not None else "NICHT gefunden"))
        if anker is not None and maus_grenze is not None:
            gx = anker.left + 80
            menue_notiert = False
            for i, dy in enumerate((10, 29, 48), start=1):
                gy = anker.top - dy
                if gy < maus_grenze:
                    break
                if is_paused():
                    trail.append("⏸ Echo pausiert — Geometrie-Fallback abgebrochen")
                    break
                _maus_fahren(gx, gy, schritte=6)
                # Finns Hand-Weg (18.08.2026, Schritt fuer Schritt vorgemacht):
                # Zeile ANKLICKEN (markieren) -> RECHTSKLICK -> 'Aendern oder
                # loeschen' -> Dialog. Der Menuepunkt wird NUR ueber seinen
                # UIA-Text geklickt — blind mit Pfeiltasten waere 'Position
                # schliessen' einen Fehltritt entfernt. Liest sich das Menue
                # nicht, ist der Doppelklick auf die Zeile der zweite Weg
                # (oeffnet in MT5 denselben Dialog).
                d = None
                if _klick_absolut(gx, gy):
                    _warte(0.25, 0.3)
                    if _klick_absolut(gx, gy, taste="rechts"):
                        _warte(0.4, 0.35)
                        if _kontextmenue_aendern_klicken() == "geklickt":
                            d = _finde_aendern_dialog(w, timeout=1.5)
                        else:
                            if not menue_notiert:
                                menue_notiert = True
                                trail.append("Kontextmenue per UIA nicht lesbar")
                            try:
                                w.type_keys("{ESC}", set_foreground=False)
                            except Exception:
                                pass
                if d is None:
                    if not _klick_absolut(gx, gy, doppel=True):
                        continue
                    d = _finde_aendern_dialog(w, timeout=1.5)
                if d is None:
                    continue
                if _dialog_gehoert_zu(d, ticket):
                    dlg = d
                    trail.append(f"Aendern-Dialog offen (Geometrie, Zeile -{i})")
                    break
                trail.append(f"Geometrie Zeile -{i}: fremder Dialog — geschlossen")
                try:
                    d.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                _fremde_dialoge_schliessen(w)

    if dlg is None:
        _fremde_dialoge_schliessen(w)
        return {"ok": False, "msg": "Aendern-Dialog liess sich nicht oeffnen"}

    # 3) SL/TP-Felder nach Beschriftung, sonst die ersten beiden Edits
    try:
        fmap = _map_felder(dlg)
        edits = dlg.descendants(control_type="Edit")
        sl_el = fmap.get("sl", edits[0] if len(edits) >= 2 else None)
        tp_el = fmap.get("tp", edits[1] if len(edits) >= 2 else None)
        if sl_el is None or tp_el is None:
            raise RuntimeError(f"SL/TP-Felder nicht gefunden ({len(edits)} Edits). "
                               f"Struktur: {_dialog_struktur(dlg)}")
        # ECHT tippen statt set_text (18.08.2026, gleicher Fund wie beim
        # Volumen-Feld: gemalter Text kommt bei MT5 nie an, s. _feld_tippen)
        for el, wert, name in ((sl_el, sl_text, "SL"), (tp_el, tp_text, "TP")):
            if not _feld_tippen(el, wert, name, trail):
                raise RuntimeError(f"{name}-Feld uebernimmt {wert} nicht")
        _warte(0.3, 0.3)
    except Exception as e:
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "msg": f"Felder nicht befuellbar: {e}"}

    # 4) Den BESTAETIGEN-Knopf finden — nicht den 'Position aendern'-Reiter
    # (Fund 18.08.2026, s. ist_bestaetigen_knopf). Reihenfolge: Knopf mit
    # Order-Daten in der Beschriftung; sonst der BREITESTE Aendern-Kandidat
    # (der blaue Balken spannt die Dialogmitte, der Reiter ist schmal).
    knopf = None
    kandidaten_k = []
    try:
        for b in dlg.descendants(control_type="Button"):
            t = b.window_text() or ""
            if ist_bestaetigen_knopf(t):
                knopf = b
                break
            tl = t.strip().lower()
            if ist_aendern_knopf(t) and tl not in (
                    "position ändern", "position aendern", "modify position"):
                kandidaten_k.append(b)
    except Exception:
        pass
    if knopf is None and kandidaten_k:
        def _breite(b):
            try:
                rb = b.rectangle()
                return rb.right - rb.left
            except Exception:
                return 0
        knopf = max(kandidaten_k, key=_breite)
    if knopf is None:
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "msg": "kein Bestaetigen-Knopf im Dialog"}
    try:
        trail.append(f"Bestaetigen-Knopf: '{(knopf.window_text() or '')[:40]}'")
    except Exception:
        pass
    try:
        r = knopf.rectangle()
        _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=8)
    except Exception:
        pass
    # Ausloesen mit ECHTER Eingabe zuerst (18.08.2026, Finns Fund: .click()
    # verpuffte auch HIER — die Felder waren fertig befuellt, aber der Bot
    # schloss den Dialog selbst per ESC, 'das Popup geht einfach weg', kein
    # Bestaetigungssound). Erfolgskriterium: der Dialog schliesst sich VON
    # SELBST (so wie bei Finns Hand-Test). ESC erst, wenn kein Weg wirkt.
    def _dialog_zu():
        try:
            return not dlg.is_visible()
        except Exception:
            return True

    def _k_leertaste():
        knopf.set_focus()
        _warte(0.1, 0.15)
        try:
            hat = bool(knopf.has_keyboard_focus())
        except Exception:
            hat = False
        if not hat:
            raise RuntimeError("kein Tastatur-Fokus")
        knopf.type_keys("{SPACE}", set_foreground=False)

    def _k_sendinput():
        r2 = knopf.rectangle()
        if not _klick_absolut(r2.mid_point().x, r2.mid_point().y):
            raise RuntimeError("SendInput abgelehnt")

    for name, weg in (("Fokus+Leertaste", _k_leertaste),
                      ("SendInput-Klick", _k_sendinput),
                      (".click()", lambda: knopf.click()),
                      ("click_input", lambda: knopf.click_input())):
        try:
            weg()
        except Exception:
            continue
        ende_k = time.time() + 2.5
        while time.time() < ende_k and not _dialog_zu():
            _warte(0.3, 0.3)
        if _dialog_zu():
            trail.append(f"Aendern-Knopf ausgeloest ({name}) — Dialog zu")
            return {"ok": True, "msg": "geklickt"}
        trail.append(f"Aendern-Knopf: {name} ohne Wirkung")
    try:
        dlg.type_keys("{ESC}", set_foreground=False)
    except Exception:
        pass
    return {"ok": False, "msg": "Aendern-Knopf reagiert auf keinen Weg"}


def run(cfg_path, cmd):
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        return {"ok": False, "retry_ok": True, "msg": f"Config nicht lesbar: {e}"}
    path = str(cfg.get("master_terminal_path") or "").strip()
    expected = int(cfg.get("master_expected_login") or 0)
    if not path or not os.path.exists(path):
        return {"ok": False, "retry_ok": True,
                "msg": f"master_terminal_path fehlt/nicht gefunden: {path}"}
    if not expected:
        return {"ok": False, "retry_ok": True,
                "msg": "master_expected_login fehlt in der Config — keine Order ohne Login-Guard."}

    try:
        import pywinauto  # noqa: F401
    except ImportError:
        return {"ok": False, "retry_ok": True,
                "msg": "pywinauto fehlt — einmal 'Alles neu starten' klicken "
                       "(das Panel installiert es dann selbst)."}
    # Flotte UIA-Timings (25.08.2026, Finns '3-5 s Pause zwischen den Steps'):
    # pywinautos Default wartet bei jedem ins Leere laufenden Element-Lookup
    # volle 5 s (window_find_timeout) — in einer Abfolge mit try/except-Pfaden
    # summiert sich das zu Kunstpausen. Der Dialog ist zu diesem Zeitpunkt
    # laengst da; 1 s Puffer reicht, die harten Abbruch-Checks bleiben.
    try:
        from pywinauto.timings import Timings
        Timings.window_find_timeout = 1.0
        Timings.exists_timeout = 0.3
    except Exception:
        pass

    symbol = str(cmd["symbol"]).strip()
    kauf = str(cmd["richtung"]).lower() == "buy"
    vol = float(cmd["volumen"])

    # 1) LESEND: Kurs + Positionsstand VORHER (+ Login-Kontrolle)
    lese = _api_lesen(path, expected, symbol=symbol)
    if "fehler" in lese:
        return {"ok": False, "retry_ok": True, "msg": lese["fehler"]}
    digits = lese["digits"]
    contract_size = lese["contract_size"]
    vorher_tickets = {p["ticket"] for p in lese["positionen"]}

    # Schritt-Spur (15.08.2026): jede Station vermerken — steht bei Erfolg UND
    # Fehler in der Meldung, damit Finn/ich sofort sieht, wo der Bot steht.
    trail = []

    # Start-Versatz (28.08.2026, Finns Sorge): starten mehrere Flotten-Instanzen
    # im selben Moment, blieben sie trotz gestreuter Einzelschritte anfangs eng
    # beieinander. 0-1.2 s Wuerfel VOR dem ersten sichtbaren Schritt zieht die
    # Laeufe von Beginn an auseinander.
    _warte(0.0, 1.2)

    # 2b) Ins (vom Check bereits geoeffnete) Terminal gehen -> Guard
    w = _finde_terminal(expected)
    if w is None:
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein MT5-Fenster mit Konto {expected} gefunden."}
    _fenster_betreten(w)
    if str(expected) not in (w.window_text() or ""):
        return {"ok": False, "retry_ok": True,
                "msg": "Fenster-Guard: Titelzeile passt nicht — Abbruch ohne Tastendruck."}
    trail.append("Terminal betreten")

    # 3) F9 -> Dialog -> Felder direkt setzen (cursor-unabhaengig, s.o. Parsec)
    w.type_keys("{F9}")
    _warte(0.4, 0.35)
    dlg = _finde_order_dialog(w)
    if dlg is None:
        return {"ok": False, "retry_ok": True,
                "msg": "F9-Dialog nicht gefunden — Abbruch, nichts gesendet. [" + " → ".join(trail) + "]"}
    trail.append("F9-Dialog offen")
    try:
        combos = dlg.descendants(control_type="ComboBox")
        edits = dlg.descendants(control_type="Edit")
        if not combos or len(edits) < 3:
            # Selbst-Diagnose (15.08.2026): die Struktur des Dialogs gleich
            # mitliefern — erspart den separaten inspect-Lauf am PC.
            probe = []
            try:
                for c in dlg.descendants()[:30]:
                    try:
                        probe.append(f"{c.element_info.control_type}:"
                                     f"{(c.window_text() or '')[:18]}")
                    except Exception:
                        continue
            except Exception:
                pass
            raise RuntimeError(
                f"Dialog-Felder nicht ansprechbar (ComboBoxen: {len(combos)}, "
                f"Edits: {len(edits)}). Struktur: {' | '.join(probe) or 'leer'}")
        # Symbol im Dropdown auswaehlen (per symbol_select schon in der
        # Marktuebersicht). control-basiert (select) — cursor-unabhaengig, weil
        # Parsec den Zeiger abfaengt. Maus-Animation nur noch Kosmetik.
        sym_combo = combos[0]
        try:
            r = sym_combo.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=8)
        except Exception:
            pass

        # Symbol BESTAETIGEN statt nur auswaehlen (18.08.2026, Spur-Fund:
        # select() schlug still fehl und nur der zufaellig richtige Chart
        # rettete den Lauf — ohne Bestaetigung ginge die Order aufs falsche
        # Symbol). Lesen via _feld_lesen (window_text waere nur das Label).
        def _symbol_drin():
            return symbol.lower() in (_feld_lesen(sym_combo) or "").lower()

        # IMMER aktiv auswaehlen (18.08.2026, Finns Ansage: der Bot geht
        # sichtbar ins Asset-Feld und waehlt selbst — nicht nur nachschauen,
        # was das Chart-Profil vorgibt). Bestaetigt wird trotzdem per Lesen.
        # Exakter Direkt-Select ZUERST (25.08.2026, Finns Tempo-Fund: das
        # fruehere sym_combo.texts() enumerierte IMMER die komplette
        # Marktuebersicht per UIA — bei 250 Symbolen die '5 s Pause' vor der
        # Asset-Auswahl). Die Listen-Suche ist nur noch Fallback fuer
        # Broker-Suffixe (z.B. 'NAS100.r').
        try:
            sym_combo.select(symbol)
        except Exception:
            try:
                for opt in sym_combo.texts():
                    if symbol.lower() in (opt or "").lower():
                        sym_combo.select(opt)
                        break
            except Exception:
                pass
        _warte(0.15, 0.2)
        gewaehlt = _symbol_drin()
        if not gewaehlt:
            # Combo ist editierbar: Symbol ECHT eintippen (Autovervollstaendigung),
            # TAB uebergibt die Eingabe
            try:
                sym_combo.set_focus(); _warte(0.15, 0.2)
                sym_combo.type_keys("^a{DELETE}", set_foreground=False)
                sym_combo.type_keys(symbol, with_spaces=False, set_foreground=False)
                sym_combo.type_keys("{TAB}", set_foreground=False)
                _warte(0.2, 0.25)
            except Exception:
                pass
            gewaehlt = _symbol_drin()
        trail.append(f"Symbol {'bestaetigt' if gewaehlt else 'NICHT bestaetigt'}: {symbol}")
        if not gewaehlt:
            raise RuntimeError(f"Symbol '{symbol}' steht nicht bestaetigt im Dialog "
                               f"(gelesen: '{(_feld_lesen(sym_combo) or '')[:40]}') — "
                               f"Abbruch, sonst ginge die Order aufs falsche Symbol.")
        _warte(0.1, 0.15)
        # NUR Volumen setzen — SL/TP kommen NACH dem Einstieg aus dem echten
        # Fill-Kurs (Finns Timing-Loesung). Feld nach Beschriftung, sonst
        # Index-Fallback. ECHT tippen statt set_text (18.08.2026, Finns Fund am
        # PC: gemalter Text kommt bei MT5 nie an, s. _feld_tippen) — und ohne
        # bestaetigtes Ruecklesen wird NICHT geklickt (sonst handelt der Bot
        # still den alten Feld-Wert, z.B. 0.01 statt 2).
        vol_el = _map_felder(dlg).get("volumen", edits[0])
        try:
            r = vol_el.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=6)
        except Exception:
            pass
        if not _feld_tippen(vol_el, f"{vol:g}", "Volumen", trail):
            raise RuntimeError(f"Volumen-Feld uebernimmt {vol:g} nicht — "
                               f"Abbruch VOR dem Order-Knopf.")
        _warte(0.2, 0.25)
    except Exception as e:
        return {"ok": False, "retry_ok": True,
                "msg": f"Abbruch VOR dem Order-Knopf (nichts platziert): {e} [" + " → ".join(trail) + "]"}

    # 4) Buy/Sell-Knopf — der unumkehrbare Schritt. .click() sendet die
    # Klick-Nachricht direkt ans Control (cursor-unabhaengig); click_input als
    # Fallback. Bleibt ein Terminal-UI-Klick, KEINE Expert-/API-Order.
    muster = "buy" if kauf else "sell"
    knopf = None
    try:
        for b in dlg.descendants(control_type="Button"):
            t = (b.window_text() or "").lower()
            if muster in t and "stop" not in t and "limit" not in t:
                knopf = b
                break
    except Exception:
        pass
    if knopf is None:
        inventar = []
        try:
            for b in dlg.descendants(control_type="Button"):
                inventar.append((b.window_text() or "?")[:24])
        except Exception:
            pass
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein {muster}-Knopf im Dialog gefunden — Abbruch, nichts gesendet. "
                       f"Knoepfe: {', '.join(inventar) or 'keine'} [" + " → ".join(trail) + "]"}
    try:
        r = knopf.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=6)
    except Exception:
        pass

    def _dialog_weg():
        try:
            return not dlg.is_visible()
        except Exception:
            return True

    def _schnell_bestaetigt(sekunden=4.0):
        """Kurzer LESE-Check nach jedem Ausloese-Versuch: neue Position da oder
        Dialog zu? Nur wenn BEIDES ausbleibt, darf der naechste Weg probiert
        werden — sonst feuern zwei Wege ZWEI Orders."""
        ende_s = time.time() + sekunden
        while time.time() < ende_s:
            _warte(0.35, 0.3)
            st = _api_lesen(path, expected)
            if "fehler" not in st and finde_neue_position(
                    vorher_tickets, st["positionen"], symbol, cmd["richtung"], vol):
                return True
            if _dialog_weg():
                return True
        return False

    # ECHTE Eingabe zuerst (18.08.2026, Live-Fund — dieselbe Lehre wie beim
    # set_text: MT5 reagiert auf echte Events. Das Volumen stand korrekt im
    # Dialog, der .click()-Weg verpuffte, der Dialog blieb einfach stehen).
    # BEWUSST kein pauschales {ENTER}: Enter drueckt den Default-Knopf des
    # Dialogs — und der koennte die falsche Richtung sein.
    def _weg_leertaste():
        knopf.set_focus()
        _warte(0.1, 0.15)
        try:
            hat_fokus = bool(knopf.has_keyboard_focus())
        except Exception:
            hat_fokus = False
        if not hat_fokus:
            # sonst tippte die Leertaste in das gerade fokussierte FELD
            raise RuntimeError("Knopf nimmt keinen Tastatur-Fokus an")
        knopf.type_keys("{SPACE}", set_foreground=False)

    def _weg_sendinput():
        r2 = knopf.rectangle()
        if not _klick_absolut(r2.mid_point().x, r2.mid_point().y):
            raise RuntimeError("SendInput abgelehnt")

    ausgeloest = None
    for weg, tu in (("Fokus+Leertaste", _weg_leertaste),
                    ("SendInput-Klick", _weg_sendinput),
                    (".click()", lambda: knopf.click()),
                    ("click_input", lambda: knopf.click_input())):
        try:
            tu()
        except Exception:
            continue
        trail.append(f"{muster}-Knopf: {weg}")
        ausgeloest = weg
        if _schnell_bestaetigt():
            break
    if ausgeloest is None:
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "retry_ok": True,
                "msg": "Buy/Sell-Knopf liess sich auf keinem Weg ausloesen "
                       "[" + " → ".join(trail) + "]"}

    # 5) LESEND: Bestaetigung am Positionsstand (bis 12 s), nie der UI glauben.
    ende = time.time() + 12
    while time.time() < ende:
        _warte(0.4, 0.35)
        nachher = _api_lesen(path, expected)
        if "fehler" in nachher:
            continue
        p = finde_neue_position(vorher_tickets, nachher["positionen"], symbol,
                                cmd["richtung"], vol)
        if p:
            fill = p["preis"]   # ECHTER Einstiegskurs der offenen Position
            trail.append(f"Position offen @ {fill}")
            # Schalter aus (18.08.2026): Order pur, SL/TP macht Finn von Hand —
            # Dialog zu, fertig, KEIN Scan.
            mit_sltp = False
            try:
                mit_sltp = (float(cmd.get("sl_usd") or 0) > 0
                            and float(cmd.get("tp_usd") or 0) > 0)
            except (TypeError, ValueError):
                pass
            if not mit_sltp:
                try:
                    dlg.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                trail.append("SL/TP: manuell (Schalter aus)")
                return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                        "msg": "per Klick platziert — SL/TP bewusst NICHT gesetzt "
                               "(Schalter aus), von Hand nachtragen",
                        "trail": " → ".join(trail), "symbol": symbol,
                        "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill, "ticket": p["ticket"]}
            # SL/TP vom echten Fill-Kurs rechnen — eingetragen wird PER KLICK
            # (18.08.2026, Finns Ansage: kein API-Schreibweg mehr). Vorher den
            # F9-Dialog schliessen, er laege sonst vor der Handel-Liste.
            sl, tp = berechne_sl_tp(cmd["richtung"], fill, vol, contract_size,
                                    cmd["sl_usd"], cmd["tp_usd"], digits)
            try:
                dlg.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            _warte(0.2, 0.25)
            # Anker-Datei: gemerkte Treffer-Stelle des Zeilen-Scans. BEWUSST
            # mit 'anker-'-Praefix, damit sie NIE ins config-*.json-Muster
            # des Copiers faellt.
            anker_pfad = os.path.join(os.path.dirname(os.path.abspath(cfg_path)),
                                      "anker-" + os.path.basename(cfg_path))
            k = _sltp_klicken(w, p["ticket"], symbol, fmt_preis(sl, digits),
                              fmt_preis(tp, digits), trail, anker_pfad=anker_pfad)
            # Bestaetigung NUR lesend: traegt die Position die Werte wirklich?
            bestaetigt = False
            ende2 = time.time() + 10
            while time.time() < ende2 and not bestaetigt:
                _warte(0.5, 0.4)
                st = _api_lesen(path, expected)
                if "fehler" in st:
                    continue
                for q in st["positionen"]:
                    if q["ticket"] == p["ticket"] \
                            and sltp_bestaetigt(q["sl"], q["tp"], sl, tp, digits):
                        bestaetigt = True
                        break
            if bestaetigt:
                trail.append(f"SL {fmt_preis(sl, digits)} / TP {fmt_preis(tp, digits)} "
                             f"per Klick gesetzt")
                return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                        "msg": "per Klick platziert, SL/TP per Klick am echten Einstieg gesetzt",
                        "trail": " → ".join(trail),
                        "symbol": symbol, "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill,
                        "sl": sl, "tp": tp, "ticket": p["ticket"]}
            # Position IST offen, aber SL/TP nicht bestaetigt — kritisch: klar
            # melden, NICHT erneut platzieren (retry_ok False), von Hand nachtragen.
            return {"ok": False, "retry_ok": False,
                    "msg": f"Position ist OFFEN @ {fill}, aber SL/TP-Klick nicht bestaetigt "
                           f"({k.get('msg')}) — im Terminal SL {fmt_preis(sl, digits)} / "
                           f"TP {fmt_preis(tp, digits)} SOFORT von Hand nachtragen! "
                           f"Spur: [" + " → ".join(trail) + "]",
                    "trail": " → ".join(trail), "symbol": symbol,
                    "richtung": "buy" if kauf else "sell", "volumen": p["volumen"],
                    "price": fill, "sl": sl, "tp": tp, "ticket": p["ticket"]}
    # Kein neuer Positionsstand: entweder Markt zu (Wochenende) oder der Klick
    # kam nicht an. Dialog-Text auf 'geschlossen' pruefen, sonst Struktur mitgeben.
    markt_zu = False
    try:
        for t in dlg.descendants(control_type="Text"):
            if "geschloss" in (t.window_text() or "").lower() or "closed" in (t.window_text() or "").lower():
                markt_zu = True
                break
    except Exception:
        pass
    struktur = _dialog_struktur(dlg)
    # Dialog nicht offen stehen lassen (18.08.2026, Finns Live-Fund: der Bot
    # war fertig, aber der Dialog blieb minutenlang stehen — halbkonfigurierte
    # Order, die jeder versehentlich ausloesen koennte).
    try:
        dlg.type_keys("{ESC}", set_foreground=False)
    except Exception:
        pass
    if markt_zu:
        return {"ok": False, "retry_ok": True,
                "msg": "Markt ist geschlossen (Wochenende/ausserhalb der Handelszeit) — "
                       "die Order kann jetzt nicht ausgefuehrt werden. Spur: [" + " → ".join(trail) + "]",
                "trail": " → ".join(trail)}
    return {"ok": False, "retry_ok": False,
            "msg": "KEINE Bestaetigung binnen 12 s — Position nicht am Konto, Dialog "
                   "geschlossen. Spur: [" + " → ".join(trail) + "] · Dialog: " + struktur,
            "trail": " → ".join(trail)}


def _close_klicken(w, ticket, trail, anker_pfad, position_weg):
    """Position per Klick schliessen — Finns Hand-Weg als Scan (28.08.2026,
    Remote-Close): Zeile markieren -> Rechtsklick -> NUR den lesbaren Punkt
    'Position schliessen' klicken. Danach zwei legitime Ausgaenge: der
    Ein-Klick-Modus schliesst SOFORT (Position verschwindet lesend), sonst
    oeffnet der Close-Dialog und der Schliessen-Knopf (Ticket in der
    Beschriftung) wird mit der bewaehrten Kaskade gedrueckt.

    WICHTIG: der Aufrufer hat vorher lesend bewiesen, dass GENAU EINE Position
    offen ist und sie das Ziel-Ticket traegt — NUR deshalb ist der Band-Scan
    hier zulaessig. Bei mehreren Positionen koennte ein Fehltreffer auf einer
    fremden Zeile im Ein-Klick-Modus die falsche Position schliessen.

    Nach dem ERSTEN erfolgreichen Menuepunkt-Klick wird NIE weitergescannt
    (die Schliessung kann da schon unterwegs sein) — ein Versuch pro Lauf.
    Rueckgabe: 'zu' | 'knopf' | 'ohne_wirkung' | 'kein_treffer' | 'pause'."""
    try:
        hr = w.rectangle()
        maus_grenze = hr.top + (hr.bottom - hr.top) // 2
    except Exception:
        return "kein_treffer"
    gx = hr.left + int((hr.right - hr.left) * 0.4)
    _fremde_dialoge_schliessen(w)
    # Toolbox auf 'Handel' — sonst ist die Positionsliste unsichtbar (gleicher
    # Fund wie beim SL/TP-Weg: frischer Terminal-Start steht auf 'Posteingang').
    _handel_tab_aktivieren(w, trail, maus_grenze)
    if is_paused():
        trail.append("⏸ Echo pausiert — kein Close-Klick")
        return "pause"
    # Punkte wie _reihen_scan: gemerkter Anker zuerst — bewusst DIESELBE
    # anker-Datei, die Positions-Zeile ist dieselbe, die der SL/TP-Weg beim
    # Platzieren schon Ticket-geprueft getroffen hat.
    punkte = []
    if anker_pfad:
        try:
            with open(anker_pfad, encoding="utf-8") as f:
                a = json.load(f)
            ax = hr.left + int((hr.right - hr.left) * float(a["x_frac"]))
            ay = hr.bottom - int(a["y_off"])
            if ay >= maus_grenze:
                punkte.append(("Anker", ax, ay))
        except Exception:
            pass
    # Band bis zur halben Fensterhoehe statt hart 400px — gleicher Grund wie
    # im SL/TP-Scan (30.08.2026, s. _reihen_scan).
    band_max = max(400, (hr.bottom - hr.top) // 2)
    for off in sorted(range(60, band_max, 16), key=lambda o: abs(o - 316)):
        y = hr.bottom - off
        if y < maus_grenze:
            continue
        punkte.append((f"-{off}px", gx, y))

    grau = 0
    for pname, px_, py_ in punkte:
        if is_paused():
            trail.append("⏸ Echo pausiert — Close-Scan abgebrochen")
            return "pause"
        _maus_fahren(px_, py_, schritte=3)
        _klick_absolut(px_, py_)          # Finns Schritt 1: Zeile markieren
        _warte(0.15, 0.2)
        if not _klick_absolut(px_, py_, taste="rechts"):
            continue
        _warte(0.25, 0.3)
        st_menue = _kontextmenue_close_klicken(timeout=0.8)
        if st_menue != "geklickt":
            # Punkt lag neben der Zeile (Menue da, Eintrag ausgegraut) oder
            # gar kein Menue — Chart/Marktuebersicht haben den Eintrag nicht.
            # Menue zu, naechster Punkt; geklickt wird nur lesbar, nie blind.
            if st_menue == "ausgegraut":
                grau += 1
            try:
                w.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            continue
        trail.append(f"'Position schliessen' geklickt ({pname})")
        # Treffer-Stelle merken (dieselbe Datei/Form wie der SL/TP-Scan) —
        # dass der Menuepunkt existierte, beweist die Positions-Zeile.
        if anker_pfad:
            try:
                with open(anker_pfad, "w", encoding="utf-8") as f:
                    json.dump({"x_frac": (px_ - hr.left) / max(1, hr.right - hr.left),
                               "y_off": hr.bottom - py_}, f)
            except Exception:
                pass
        dlg = knopf = None
        ende = time.time() + 3.0
        while time.time() < ende:
            if position_weg():
                trail.append("Position weg (Ein-Klick-Modus)")
                return "zu"
            dlg, knopf = _finde_close_dialog(w, ticket)
            if knopf is not None:
                break
            _warte(0.25, 0.25)
        if knopf is None:
            return "ohne_wirkung"
        try:
            trail.append(f"Close-Dialog offen, Knopf: '{(knopf.window_text() or '')[:44]}'")
        except Exception:
            pass
        try:
            r = knopf.rectangle()
            _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=6)
        except Exception:
            pass

        # Kaskade wie Buy-/Aendern-Knopf (.52/.64): echte Eingabe zuerst, nach
        # jedem Weg lesend pruefen — nie zwei Wege blind hintereinander.
        def _weg_leertaste():
            knopf.set_focus()
            _warte(0.1, 0.15)
            try:
                hat_fokus = bool(knopf.has_keyboard_focus())
            except Exception:
                hat_fokus = False
            if not hat_fokus:
                raise RuntimeError("Knopf nimmt keinen Tastatur-Fokus an")
            knopf.type_keys("{SPACE}", set_foreground=False)

        def _weg_sendinput():
            r2 = knopf.rectangle()
            if not _klick_absolut(r2.mid_point().x, r2.mid_point().y):
                raise RuntimeError("SendInput abgelehnt")

        for wegname, tu in (("Fokus+Leertaste", _weg_leertaste),
                            ("SendInput-Klick", _weg_sendinput),
                            (".click()", lambda: knopf.click()),
                            ("click_input", lambda: knopf.click_input())):
            try:
                tu()
            except Exception:
                continue
            trail.append(f"Schliessen-Knopf: {wegname}")
            ende2 = time.time() + 4.0
            while time.time() < ende2:
                _warte(0.35, 0.3)
                if position_weg():
                    return "zu"
                try:
                    if not dlg.is_visible():
                        return "knopf"
                except Exception:
                    return "knopf"
        return "knopf"   # alle Wege durch — den Ausgang entscheidet der Aufrufer lesend
    trail.append(f"Zeilen-Scan ohne Treffer (Fenster {hr.right - hr.left}x{hr.bottom - hr.top}, "
                 f"Band -60..-{band_max}px, x={gx}, {len(punkte)} Punkte, {grau}x ausgegraut)")
    return "kein_treffer"


def _deal_profit_lesen(path, expected, ticket):
    """Best-Effort, rein LESEND: realisierter P&L der eben geschlossenen
    Position aus der Konto-Historie (Ausstiegs-Deals inkl. Swap/Kommission).
    Liefert die Historie nichts, kommt None — die Meldung bleibt dann ohne
    P&L, geraten wird nie ('Beweis oder leer')."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    try:
        if not mt5.initialize(path=path):
            return None
        try:
            ai = mt5.account_info()
            if ai is None or (expected and int(ai.login) != expected):
                return None
            deals = mt5.history_deals_get(position=int(ticket)) or []
            raus = [d for d in deals if int(getattr(d, "entry", -1)) == 1]  # DEAL_ENTRY_OUT
            if not raus:
                return None
            return round(sum(float(d.profit)
                             + float(getattr(d, "swap", 0) or 0)
                             + float(getattr(d, "commission", 0) or 0) for d in raus), 2)
        finally:
            mt5.shutdown()
    except Exception:
        return None


def run_close(cfg_path, cmd):
    """Position schliessen (28.08.2026, Finns Remote-Close) — derselbe Rahmen
    wie run(), aber der unumkehrbare Schritt ist der 'Position schliessen'-
    Klick. Zwei Eigenheiten gegenueber der Eroeffnung:
    1. Close ist quasi-idempotent: die Zielposition ist entweder offen oder
       nicht, lesend pruefbar VOR jedem Klick — ein Wiederholungslauf ist
       deshalb meist ungefaehrlich (retry_ok oefter True als beim Oeffnen).
    2. Verwechslungs-Schutz: geklickt wird NUR bei lesend bewiesener GENAU
       EINER offenen Position mit dem Ziel-Ticket (s. _close_klicken)."""
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        return {"ok": False, "retry_ok": True, "msg": f"Config nicht lesbar: {e}"}
    path = str(cfg.get("master_terminal_path") or "").strip()
    expected = int(cfg.get("master_expected_login") or 0)
    if not path or not os.path.exists(path):
        return {"ok": False, "retry_ok": True,
                "msg": f"master_terminal_path fehlt/nicht gefunden: {path}"}
    if not expected:
        return {"ok": False, "retry_ok": True,
                "msg": "master_expected_login fehlt in der Config — kein Close ohne Login-Guard."}
    try:
        import pywinauto  # noqa: F401
    except ImportError:
        return {"ok": False, "retry_ok": True,
                "msg": "pywinauto fehlt — einmal 'Alles neu starten' klicken "
                       "(das Panel installiert es dann selbst)."}
    try:
        from pywinauto.timings import Timings
        Timings.window_find_timeout = 1.0
        Timings.exists_timeout = 0.3
    except Exception:
        pass

    ticket = int(cmd["ticket"])
    symbol = str(cmd.get("symbol") or "").strip()

    # 1) LESEND: gibt es die Position ueberhaupt (noch)? Login-Guard inklusive.
    lese = _api_lesen(path, expected)
    if "fehler" in lese:
        return {"ok": False, "retry_ok": True, "msg": lese["fehler"]}
    pos = next((p for p in lese["positionen"] if p["ticket"] == ticket), None)
    if pos is None:
        # Ziel-Zustand erreicht, nichts zu tun — ehrlich als eigener Fall
        # (macht auch jeden Wiederholungslauf nach Fehlschlag harmlos).
        return {"ok": True, "retry_ok": False, "schon_zu": True,
                "msg": f"Position #{ticket} ist nicht (mehr) offen — nichts zu tun."}
    if symbol and symbol.lower() not in pos["symbol"].lower():
        return {"ok": False, "retry_ok": True,
                "msg": f"Ticket #{ticket} traegt {pos['symbol']}, erwartet war {symbol} — "
                       f"falsches Signal, nichts geklickt."}
    if len(lese["positionen"]) != 1:
        andere = ", ".join(f"#{p['ticket']} {p['symbol']}"
                           for p in lese["positionen"] if p["ticket"] != ticket)
        return {"ok": False, "retry_ok": True,
                "msg": f"Verwechslungs-Schutz: {len(lese['positionen'])} Positionen offen "
                       f"(neben #{ticket} noch {andere}) — der Zeilen-Scan kann die richtige "
                       f"Zeile nicht sicher treffen, im Terminal von Hand schliessen."}

    trail = []
    _warte(0.0, 1.2)   # Start-Versatz wie run() (28.08.2026, Flotten-Streuung)

    # 2) Ins Terminal gehen -> Guard
    w = _finde_terminal(expected)
    if w is None:
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein MT5-Fenster mit Konto {expected} gefunden."}
    _fenster_betreten(w)
    if str(expected) not in (w.window_text() or ""):
        return {"ok": False, "retry_ok": True,
                "msg": "Fenster-Guard: Titelzeile passt nicht — Abbruch ohne Klick."}
    trail.append("Terminal betreten")

    def position_weg():
        st = _api_lesen(path, expected)
        return "fehler" not in st and all(p["ticket"] != ticket for p in st["positionen"])

    anker_pfad = os.path.join(os.path.dirname(os.path.abspath(cfg_path)),
                              "anker-" + os.path.basename(cfg_path))
    ausgang = _close_klicken(w, ticket, trail, anker_pfad, position_weg)

    if ausgang == "pause":
        return {"ok": False, "retry_ok": True,
                "msg": "Echo ist pausiert — nichts geklickt. Fortsetzen, dann erneut. "
                       "[" + " → ".join(trail) + "]", "trail": " → ".join(trail)}
    if ausgang == "kein_treffer":
        _fremde_dialoge_schliessen(w)
        return {"ok": False, "retry_ok": True,
                "msg": f"Positions-Zeile #{ticket} nicht gefunden (Zeilen-Scan ohne Treffer) — "
                       f"nichts geklickt. [" + " → ".join(trail) + "]",
                "trail": " → ".join(trail)}

    # 3) LESEND bestaetigen: Position weg = zu (bis 12 s, wie die Order-Seite).
    zu = (ausgang == "zu")
    ende = time.time() + 12
    while not zu and time.time() < ende:
        _warte(0.4, 0.35)
        if position_weg():
            zu = True
    # Result-/Restdialog nie stehen lassen (Abbrechen/ESC, nie OK)
    _fremde_dialoge_schliessen(w)
    if zu:
        profit = _deal_profit_lesen(path, expected, ticket)
        pl = f" · P&L {profit:+,.2f}" if profit is not None else ""
        trail.append(f"Position #{ticket} zu{pl}")
        return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                "msg": f"Position #{ticket} ({pos['symbol']}, {pos['volumen']:g} Lots) "
                       f"per Klick geschlossen{pl}",
                "trail": " → ".join(trail), "ticket": ticket, "profit": profit}
    if ausgang == "ohne_wirkung":
        return {"ok": False, "retry_ok": True,
                "msg": f"'Position schliessen' geklickt, aber Position #{ticket} liegt noch "
                       f"und kein Close-Dialog kam — im Terminal nachsehen. Wiederholen ist "
                       f"ungefaehrlich (der Bot prueft vorher lesend). [" + " → ".join(trail) + "]",
                "trail": " → ".join(trail)}
    return {"ok": False, "retry_ok": True,
            "msg": f"Close-Dialog war offen, aber Position #{ticket} ist nach 12 s weiter "
                   f"offen — im Terminal pruefen (Dialog wurde geschlossen). Wiederholen ist "
                   f"ungefaehrlich. [" + " → ".join(trail) + "]",
            "trail": " → ".join(trail)}


def modus_inspect(cfg_path):
    """Diagnose: F9-Dialog oeffnen und alle Steuerelemente dumpen — platziert
    NICHTS. Der Dump entscheidet die Feld-Zuordnung, falls run abbricht."""
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    login = int(cfg.get("master_expected_login") or 0)
    w = _finde_terminal(login)
    if not w:
        sys.exit(f"Kein MT5-Fenster mit Konto {login} gefunden (Terminal offen?).")
    print(f"Fenster: {w.window_text()!r}")
    w.set_focus()
    time.sleep(0.5)
    w.type_keys("{F9}")
    time.sleep(0.4)
    dlg = _finde_order_dialog(w)
    if not dlg:
        sys.exit("Kein Order-Dialog gefunden.")
    print(f"Dialog: {dlg.window_text()!r} — Steuerelemente:")
    dlg.print_control_identifiers(depth=4)
    print("\nDump komplett an Claude schicken — daraus wird die Feld-Zuordnung gebaut.")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "mousetest":
        modus_mousetest()
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "tvfokus":
        # Orbit Schritt 1 (28.08.2026): nur den TradingView-Tab nach vorn —
        # wie mousetest ohne Config, und ohne den Prophos-Heimweg unten.
        modus_tvfokus()
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "tvorder":
        # Orbit-Puls Schritt 2 (30.08.2026): die Order auf TradingView
        # platzieren. Wie tvfokus OHNE Config-Datei — der Weg fuehrt durch den
        # Browser, nicht durch ein MT5-Terminal; das Zielkonto steht als
        # ext_id IM BEFEHL. Und wie tvfokus ohne den Prophos-Heimweg unten:
        # der PC muss auf TradingView stehen bleiben, sonst drosselt Chrome
        # den Reader im Hintergrund-Tab und der Hedge wird blind.
        try:
            cmd = json.loads(sys.argv[2])
        except ValueError as e:
            print(json.dumps({"ok": False, "retry_ok": True,
                              "msg": f"Befehl kein gueltiges JSON: {e}"}))
            return 2
        try:
            modus_tvorder(cmd)
        except Exception as e:
            # Ein stummer Bot ist der Diagnose-Killer (Lehre 15.08.2026) — und
            # hier ist er zusaetzlich gefaehrlich: das Panel wuesste nicht, ob
            # vor oder nach dem Senden-Klick abgebrochen wurde. Deshalb ist
            # retry_ok bei einem UNERWARTETEN Fehler immer False.
            print(json.dumps({"ok": False, "retry_ok": False, "schritt": "absturz",
                              "msg": f"TV-Order abgebrochen: {type(e).__name__}: {e} — "
                                     "erst in TradingView nachsehen, ob eine Order "
                                     "liegt, bevor irgendetwas wiederholt wird."}))
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "inspect":
        modus_inspect(sys.argv[2])
        return 0
    if len(sys.argv) < 3:
        print(json.dumps({"ok": False, "retry_ok": True,
                          "msg": "Aufruf: order_bot.py <config.json> '<befehl-json>'"}))
        return 2
    try:
        cmd = json.loads(sys.argv[2])
    except ValueError as e:
        print(json.dumps({"ok": False, "retry_ok": True, "msg": f"Befehl kein gueltiges JSON: {e}"}))
        return 2
    fehler = pruefe_befehl(cmd)
    if fehler:
        print(json.dumps({"ok": False, "retry_ok": True,
                          "msg": "Befehl unvollstaendig: " + " · ".join(fehler)}))
        return 2
    # Close-Befehle (28.08.2026, Remote-Close) laufen ueber denselben Aufruf —
    # 'aktion' entscheidet den Weg, pruefe_befehl hat den Zweig schon validiert.
    if str(cmd.get("aktion") or "").lower() == "close":
        res = run_close(sys.argv[1], cmd)
    else:
        res = run(sys.argv[1], cmd)
    # Ausgangssituation (28.08.2026): nach jedem Lauf zurueck in den Prophos-
    # Tab — hier statt in run(), damit ausnahmslos JEDER Ausgang (Erfolg,
    # Abbruch, SL/TP-Warnung) denselben Heimweg nimmt. mousetest/inspect
    # bleiben bewusst aussen vor: wer diagnostiziert, will am Terminal bleiben.
    heim = _zurueck_zu_prophos()
    res["trail"] = (res["trail"] + " → " + heim) if res.get("trail") else heim
    print(json.dumps(res))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
