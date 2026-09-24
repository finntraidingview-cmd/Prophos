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
  python order_bot.py tvlesen "<befehl-json>"         (Orbit V2: Konto lesen — Position offen? Today's P&L)
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


def ist_einklick_dialog(titel):
    """Der Haftungsausschluss, den MT5 vor dem ERSTEN Ein-Klick-Handel eines
    Terminals dazwischenschiebt (Finn 01.09.2026: "ich habe grad per 'Order
    schliessen' Puls die Aufgabe gegeben zu schliessen, aber hier kam dann die
    Meldung"). Er verschluckt den Close: geklickt wurde, passiert ist nichts.
    Erkennung ueber den Fenstertitel — ergaenzend zur Knopf-Signatur, die die
    eigentliche Zustimmung traegt."""
    t = (titel or "").strip().lower()
    return ("ein-klick" in t or "ein klick" in t or "einklick" in t
            or "one click" in t or "one-click" in t)


def ist_einklick_akzeptieren_knopf(text):
    """Der Zustimmen-Knopf dieses Haftungsausschlusses ('Ich akzeptiere die
    allgemeinen Geschaeftsbedingungen' / 'I accept the terms and conditions').
    Positiv-Signatur aus BEIDEN Haelften — Zustimmung UND Bedingungen —, damit
    kein beliebiger Knopf mit 'akzeptieren' im Text getroffen wird; Abbrechen
    und jede Ablehnung sind hart ausgeschlossen. Reine Textlogik, damit der
    Mac-Selbsttest sie abdeckt."""
    t = (text or "").strip().lower()
    if not t:
        return False
    for verboten in ("abbre", "cancel", "nicht", "ablehn", "decline",
                     "reject", "disagree", "do not", "don't"):
        if verboten in t:
            return False
    zustimmung = any(k in t for k in ("akzeptier", "zustimm", "einverstanden",
                                      "accept", "agree"))
    bedingungen = any(k in t for k in ("bedingung", "geschäft", "geschaeft",
                                       "terms", "conditions"))
    return zustimmung and bedingungen


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


def tv_senden_text_passt(text, richtung, menge):
    """Traegt der Senden-Knopf wirklich das, was wir gleich ausloesen?

    TradingViews Knopf beschriftet sich selbst mit Richtung, Menge, Symbol und
    Orderart -- "Kauf 3 NQU6 MARKT" (Fund im Panel-Dump 31.08.2026). Das ist
    die belastbarste Ruecklese-Probe im ganzen Ablauf: sie prueft nicht ein
    Eingabefeld, sondern das, was das Panel selbst zu tun glaubt. Deshalb faellt
    der unumkehrbare Klick erst, wenn dieser Text stimmt.

    Reihenfolge zaehlt: 'Verkauf' ENTHAELT 'kauf'. Wer auf 'kauf' prueft, ohne
    'verkauf' vorher auszuschliessen, haelt einen Verkauf fuer einen Kauf --
    das waere die Richtungsverwechslung, gegen die der ganze Rest abgesichert
    ist."""
    t = (text or "").strip().lower()
    if not t:
        return False, "Senden-Knopf ohne Beschriftung"
    if "markt" not in t and "market" not in t and not re.search(r"\bmkt\b", t):
        return False, f"Orderart steht nicht auf Markt ('{text[:40]}')"
    ist_verkauf = ("verkauf" in t) or ("sell" in t)
    ist_kauf = (not ist_verkauf) and (("kauf" in t) or ("buy" in t))
    r = (richtung or "").lower()
    if r == "buy" and not ist_kauf:
        return False, f"Knopf zeigt nicht Kauf ('{text[:40]}')"
    if r == "sell" and not ist_verkauf:
        return False, f"Knopf zeigt nicht Verkauf ('{text[:40]}')"
    # Menge als EIGENES Wort — '3' darf nicht in '30' oder im Symbol treffen.
    soll = tv_zahl_text(menge)
    if soll not in re.findall(r"[0-9][0-9.,]*", t.replace(".", "").replace(",", "")) \
       and not re.search(r"(?<![0-9])" + re.escape(soll) + r"(?![0-9])", t):
        return False, f"Menge {soll} steht nicht auf dem Knopf ('{text[:40]}')"
    return True, ""


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

# ── Terminal-Verbindung EINMAL pro Lauf (31.08.2026, Finns Tempo-Frage) ─────
# "zwischen den jeweiligen Steps ist immer so 2-3 s Pause, das ist schon lang."
# Die Pausen sind NICHT die _warte()-Wuerfel (0,2-0,5 s) — sie sind das hier:
# _api_lesen() machte bis heute bei JEDEM Aufruf mt5.initialize() … shutdown().
# Ein initialize() ist keine Funktion, sondern ein IPC-Anschluss ans laufende
# Terminal — Handshake, Konto-Sync, Abbau. Auf Finns PCs kostet das je nach
# Terminal-Last 0,5-2 s. Der Bot ruft _api_lesen im Normalfall sechsmal:
# Kurs holen, Schnell-Check nach dem Knopf, Positions-Bestaetigung, SL/TP-
# Bestaetigung — jede dieser "Pausen zwischen den Schritten" war zum groessten
# Teil ein neuer Anschluss an dasselbe Terminal.
# Jetzt: einmal andocken, fuer die Dauer des Laufs verbunden bleiben, am Ende
# trennen. Der Pfad ist pro Lauf konstant; wechselt er doch, wird sauber
# umgehaengt. Faellt die Verbindung zwischendurch weg, faellt der Leser NICHT
# auf die Nase: er trennt und versucht es genau EINMAL mit frischem
# initialize() — damit ist das Verhalten im schlechtesten Fall exakt das alte.
# An der Doktrin aendert das nichts: der API-Kanal bleibt rein LESEND, es
# wandert kein einziger Schreibaufruf hier durch (Order und SL/TP gehen
# weiterhin ausschliesslich per sichtbarem Klick).
_MT5_PFAD = None            # Terminal, an dem dieser Prozess gerade haengt
_API_STAT = {"n": 0, "ms": 0.0}   # Bilanz fuer die Spur — Beweis statt Gefuehl


def _api_verbinden(mt5, path):
    global _MT5_PFAD
    if _MT5_PFAD == path:
        return True
    _api_trennen(mt5)
    if not mt5.initialize(path=path):
        return False
    _MT5_PFAD = path
    return True


def _api_trennen(mt5=None):
    """Verbindung loesen. Am Ende jedes Laufs und bei jedem Verdacht auf eine
    tote Verbindung — danach docket der naechste Aufruf frisch an."""
    global _MT5_PFAD
    if _MT5_PFAD is None:
        return
    try:
        if mt5 is None:
            import MetaTrader5 as mt5
        mt5.shutdown()
    except Exception:
        pass
    _MT5_PFAD = None


def _api_stat_reset():
    _API_STAT["n"] = 0
    _API_STAT["ms"] = 0.0


def _spur(trail):
    """Spur als Text, mit angehaengter API-Bilanz (31.08.2026). Die Zahl
    beantwortet Finns Tempo-Frage aus einem ECHTEN Lauf statt aus meiner
    Schaetzung: steht dort '6x 0,4s', liegt die verbleibende Zeit woanders."""
    n, ms = _API_STAT["n"], _API_STAT["ms"]
    zusatz = [f"API-Lesen {n}x {ms / 1000:.1f}s"] if n else []
    return " → ".join(list(trail) + zusatz)


class _StempelSpur(list):
    """Spur-Liste, die jeden Eintrag mit der Sekunde seit Lauf-Start stempelt
    (01.09.2026, Finns Tempo-Beschwerde: 'Popup offen, dann 10 Sekunden bis
    zum naechsten Schritt'). Die API-Bilanz in _spur() beziffert nur das
    API-Lesen — WO die uebrige Zeit zwischen den Stationen blieb, war weiter
    Schaetzung. Jetzt traegt jede Station ihre Sekunde: '14.2s·Aendern-Dialog
    offen' direkt nach '3.1s·Position offen' zeigt den Fresser ohne Raten.
    Alle Helfer haengen unveraendert per append() an und bekommen den Stempel
    geschenkt; _spur() und das Panel-Log lesen die Liste wie bisher."""
    def __init__(self):
        super().__init__()
        self._t0 = time.time()

    def append(self, s):
        super().append(f"{time.time() - self._t0:.1f}s·{s}")

    def sekunden(self):
        return time.time() - self._t0


def _api_lesen(path, expected, symbol=None):
    """Lesen ueber die (offen gehaltene) Terminal-Verbindung. Rueckgabe:
    {"login", "positionen": [...], "ref_ask", "ref_bid", "contract_size",
     "digits"} oder {"fehler": ...}."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return {"fehler": "MetaTrader5-Paket fehlt (nur auf dem PC lauffaehig)."}
    _t0 = time.time()
    try:
        for versuch in (1, 2):
            if not _api_verbinden(mt5, path):
                _api_trennen(mt5)
                if versuch == 2:
                    return {"fehler": f"Terminal-Verbindung fehlgeschlagen: {mt5.last_error()}"}
                continue
            try:
                erg = _api_lesen_einmal(mt5, expected, symbol)
            except Exception as e:
                # Ausnahme heisst hier immer: Verbindung hin. Trennen und genau
                # einmal frisch andocken — das ist der alte Zustand.
                _api_trennen(mt5)
                if versuch == 2:
                    return {"fehler": f"Lesen fehlgeschlagen ({type(e).__name__}): {e}"}
                continue
            if erg is None:          # account_info leer = Verbindung tot
                _api_trennen(mt5)
                if versuch == 2:
                    return {"fehler": "Kein Konto verbunden (account_info leer)."}
                continue
            return erg
        return {"fehler": "Terminal nicht lesbar."}
    finally:
        _API_STAT["n"] += 1
        _API_STAT["ms"] += (time.time() - _t0) * 1000.0


def _api_lesen_einmal(mt5, expected, symbol=None):
    """Ein Lesedurchgang auf bestehender Verbindung. None = Verbindung tot
    (der Aufrufer haengt dann neu an); dict = Ergebnis oder Sachfehler."""
    ai = mt5.account_info()
    if ai is None:
        return None      # Verbindung tot — der Aufrufer haengt neu an
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
        # nachfassen, bevor 'Markt zu' gemeldet wird. Erst PRUEFEN, dann warten
        # (31.08.2026): der Tick ist meistens sofort da, die alte Reihenfolge
        # verschenkte trotzdem jedes Mal die volle Wartezeit.
        _t0 = time.time()
        while (tick is None or not (tick.ask and tick.bid)) and time.time() - _t0 < 3:
            _warte(0.12, 0.15)
            tick = mt5.symbol_info_tick(symbol)
        if si is None or tick is None or not (tick.ask and tick.bid):
            return {"fehler": f"Keine Kurse fuer '{symbol}' (Markt zu?)."}
        out["ref_ask"] = float(tick.ask)
        out["ref_bid"] = float(tick.bid)
        out["contract_size"] = float(getattr(si, "trade_contract_size", 0) or 0) or 1.0
        out["digits"] = int(getattr(si, "digits", 2) or 2)
    return out


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


# Hinweistext fuer den Fall "Terminal reagiert nicht" (02.09.2026, Finns
# Screenshot der Windows-Benutzerkontensteuerung: "Moechten Sie zulassen, dass
# durch diese App Aenderungen … — Client Terminal AVX2"). Diese Abfrage kommt
# vom MT5-SELBST-UPDATE, wenn ein Terminal nach laengerer Downtime startet und
# MetaQuotes einen neuen Build hat — sie steht auf dem SICHEREN DESKTOP, den
# KEIN Programm (auch der Bot nicht) per SendInput erreichen darf; das ist der
# Sinn der UAC. Der Bot kann sie also nicht wegklicken — aber er kann die Lage
# BENENNEN, statt still an einem nie erscheinenden Fenster zu scheitern. Genau
# das war Finns Wunsch: nicht auto-klicken, sondern klar melden.
_UAC_HINWEIS = ("Evtl. steht am PC eine Windows-Abfrage offen (MT5-Update / "
                "Benutzerkontensteuerung 'Client Terminal…') — einmal auf 'Ja' "
                "klicken, dann laeuft das Terminal. Das kann der Bot nicht "
                "abnehmen (Windows-Sicherheitsabfrage).")


def _ist_verbindungsfehler(txt):
    """Riecht der Lese-Fehler nach 'Terminal nicht erreichbar' (dann passt der
    UAC/Update-Hinweis) statt nach Konto-/Symbol-Sachfehler (dann waere er
    irrefuehrend)?"""
    t = (txt or "").lower()
    return any(k in t for k in ("terminal-verbindung", "kein konto verbunden",
                                "terminal nicht lesbar", "lesen fehlgeschlagen"))


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


def _ziehen_absolut(x1, y1, x2, y2, schritte=12):
    """Echtes Ziehen (Druecken - bewegen - loslassen) ueber SendInput, gleiche
    Absolut-Normierung wie _klick_absolut. Fuer die Trennleiste des Tradovate-
    Panels (22.09.2026)."""
    import ctypes
    user32 = ctypes.windll.user32
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    norm = lambda x, y: (int(round((int(x) - vx) * 65535 / max(1, vw - 1))), int(round((int(y) - vy) * 65535 / max(1, vh - 1))))
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class _MI(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]

    class _INP(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("mi", _MI)]
    MOVE, ABS, DOWN, UP = 0x0001, 0x8000 | 0x4000, 0x0002, 0x0004

    def sende(fl, x, y):
        ax, ay = norm(x, y)
        b = (_INP * 1)()
        b[0].type = 0
        b[0].mi = _MI(ax, ay, 0, fl, 0, None)
        return user32.SendInput(1, b, ctypes.sizeof(_INP)) == 1
    ok = sende(MOVE | ABS, x1, y1)
    time.sleep(0.08)
    ok = sende(MOVE | DOWN | ABS, x1, y1) and ok
    for i in range(1, schritte + 1):
        time.sleep(0.03)
        ok = sende(MOVE | ABS, x1 + (x2 - x1) * i // schritte, y1 + (y2 - y1) * i // schritte) and ok
    time.sleep(0.08)
    return sende(MOVE | UP | ABS, x2, y2) and ok


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


def _maus_fahren(x, y, schritte=8):
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


def tv_tab_rang(name, begriff, symbol):
    """Wie gut passt dieser Tab-Name? 0 = gar nicht, hoeher = besser.

    Vier Wege, absteigend nach Verlaesslichkeit (31.08.2026, nach Finns
    zweitem Fehlversuch MIT Spur):
      3  Symbol-Wurzel des Befehls steckt im Namen — der beste Treffer, weil
         der Chart dann schon auf dem geplanten Instrument steht.
      2  'tradingview' im Namen. Bei Finn trifft das nie: sein Tab heisst
         'MNQU2026 29.455,50 ▼ −0.12% Unnamed', der Produktname fehlt.
      2  Der Titel, den das Userscript meldet (0.3.1+).
      1  Der Name SIEHT AUS wie ein TradingView-Chart-Titel: Kurs-Pfeil
         (▲/▼) UND Prozentzeichen. Das ist der Weg, der Finns Fall loest.

    Warum Rang statt "erster Treffer": bis .195 war die Symbol-Wurzel die
    einzige verlaessliche Spur — damit fand der Bot den Tab NUR, wenn der
    Chart schon auf dem richtigen Instrument stand. Den Chart umzustellen ist
    aber Schritt 4 der Kette; die Suche darf ihn also nicht voraussetzen.
    Bei Finn stand der Plan auf NQ und der Chart auf MNQ, und der Bot fand
    folgerichtig gar nichts. Jetzt findet er den Chart-Tab trotzdem — und
    stellt das Symbol danach selbst um. Der Rang sorgt dabei dafuer, dass bei
    ZWEI offenen Chart-Tabs der mit dem passenden Symbol gewinnt."""
    n = (name or "").strip()
    if not n:
        return 0
    low = n.lower()
    if low.startswith("devtools"):
        return 0
    ziel = tv_symbol_root(symbol)
    if ziel:
        erst = tv_tab_suchbegriff(n)
        if erst and tv_symbol_root(erst) == ziel:
            return 3
    if "tradingview" in low:
        return 2
    b = (begriff or "").strip().lower()
    if b and b in low:
        return 2
    # Chart-Titel-Signatur: TradingView schreibt Symbol, Kurs, Richtungspfeil
    # und Prozent in den Titel. Zwei unabhaengige Merkmale zusammen (Pfeil UND
    # Prozent) — ein einzelnes waere zu weit (Prozent steht in vielen Titeln).
    if ("▲" in n or "▼" in n) and "%" in n:
        return 1
    # OHNE Pfeil (22.09.2026 02:5x, Finns Lauf: 'NQZ2026 30,784.50 0% Unnamed' —
    # bei genau 0 % Aenderung schreibt TradingView KEINEN Pfeil, der Tab galt als
    # 'nicht gefunden', obwohl er vorne stand): Symbol-Wort, dann Kurs, dann Prozent —
    # drei Merkmale in dieser Reihenfolge sind genauso eindeutig wie Pfeil + Prozent.
    if TV_RX_CHART_TITEL.match(n):
        return 1
    return 0


# '(1) ' Zaehler-Praefix vertragen; Symbol wie 'NQZ2026', 'BTC1!', 'CME_MINI:NQZ2026'
TV_RX_CHART_TITEL = re.compile(r"^(\(\d+\)\s*)?[A-Za-z][A-Za-z0-9!:._-]{1,24}\s+[\d.,]+\s+(▲|▼)?\s*[−\-+]?[\d.,]+\s*%")


def tv_tab_passt(name, begriff, symbol):
    """Ist dieser Tab-Name ueberhaupt ein Kandidat? (Duenne Huelle um den Rang.)"""
    return tv_tab_rang(name, begriff, symbol) > 0


def _tv_tab_suchen(w, begriff, symbol, gesehen):
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
    bester, bester_rang = None, 0
    for it in kinder:
        try:
            n = (it.window_text() or "").strip()
        except Exception:
            continue
        if not n or n.lower().startswith("devtools"):
            continue
        if len(gesehen) < 12:
            gesehen.append(n[:60])
        r = tv_tab_rang(n, begriff, symbol)
        if r > bester_rang:
            bester, bester_rang = it, r
    return bester


def _tv_fenster_holen(trail, begriff="", symbol=""):
    """Browser-Fenster mit TradingView nach vorn — Titel zuerst (aktiver Tab),
    sonst ueber die Tableiste. (fenster, fehlertext)."""
    from pywinauto import Desktop
    kandidaten = []
    fenster_namen = []
    tab_namen = []
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
        if ist_tradingview_fenster(titel, klasse) or tv_tab_rang(titel, begriff, symbol) > 0:
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
        tab = _tv_tab_suchen(w, begriff, symbol, tab_namen)
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
    trail.append(f"Suchbegriff '{begriff or '-'}' / Symbol-Wurzel "
                 f"'{tv_symbol_root(symbol) or '-'}'"
                 f" · Browser-Fenster: {fenster_namen or 'keine'}"
                 f" · Tabs: {tab_namen or 'keine gelesen'}")
    return None, ("Kein Browser-Fenster mit TradingView gefunden. Gesucht wurde nach "
                  f"'{begriff or 'tradingview'}' bzw. der Symbol-Wurzel "
                  f"'{tv_symbol_root(symbol) or '-'}'. Gesehen: "
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


# ═══════════════════════════════════════════════════════════════════════════
# FUTURES-PULS, NEUAUFBAU SCHRITT 1 (21.09.2026) — TradingView starten
#
# Finn 21.09.2026: der tvorder-Bau vom 30.08. "hat echt gebuggt", der neue
# Futures-Puls wird "step nach step" aufgebaut. Schritt 1, woertlich: "als
# Erstes soll gecheckt werden, ob TradingView offen ist. Wenn nicht, soll
# TradingView gestartet werden" — denn TradingView soll "nicht ohne Grund
# offen sein" (gleiche Linie wie die Master-Terminals seit 03.09.: nur im
# Trade offen, nicht 24/7).
#
# Der Modus ist bewusst EIN Baustein: der Knopf in Prophos ruft ihn direkt,
# und die spaetere Kette ruft tv_sicherstellen() als ihren ersten Schritt.
# Hier wird NICHTS in der Seite geklickt und keine Order angefasst.
# ═══════════════════════════════════════════════════════════════════════════

TV_START_URL = "https://www.tradingview.com/chart/"
_CHROME_ORTE = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
)


def tv_start_url(url):
    """Die Start-URL — nur https und nur tradingview.com. Der Wert kommt aus
    einer Config-Datei; ein Tippfehler dort soll nicht irgendeine Seite in
    einem Browser oeffnen, in dem Prop-Konten eingeloggt sind. Alles andere
    faellt still auf den Standard zurueck."""
    u = str(url or "").strip()
    low = u.lower()
    for anfang in ("https://www.tradingview.com/", "https://tradingview.com/",
                   "https://de.tradingview.com/"):
        if low.startswith(anfang) and not any(c.isspace() for c in u):
            return u
    return TV_START_URL


def tv_start_befehl(chrome, url, profil=""):
    """Aufrufzeile fuer Chrome. --new-window ist Absicht: TradingView gehoert
    in ein EIGENES Fenster — in einem verdeckten Tab drosselt Chrome das
    Userscript (Fund 30.08./01.09.2026), und der Fenstertitel ist dann
    zugleich der Tab, an dem die Erkennung haengt. Laeuft Chrome schon,
    reicht der Aufruf die URL an den laufenden Prozess weiter und endet."""
    cmd = [chrome]
    p = str(profil or "").strip()
    if p:
        cmd.append("--profile-directory=" + p)
    cmd += ["--new-window", tv_start_url(url)]
    return cmd


def _chrome_pfad(wunsch=""):
    """chrome.exe finden: Config-Wunsch, dann Registry (App Paths), dann die
    drei Standard-Orte. '' = nicht gefunden."""
    w = os.path.expandvars(str(wunsch or "").strip().strip('"'))
    if w and os.path.exists(w):
        return w
    try:
        import winreg
        for wurzel in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(wurzel, r"SOFTWARE\Microsoft\Windows\CurrentVersion"
                                            r"\App Paths\chrome.exe") as k:
                    p = str(winreg.QueryValue(k, None) or "").strip().strip('"')
                    if p and os.path.exists(p):
                        return p
            except OSError:
                continue
    except ImportError:
        pass
    for ort in _CHROME_ORTE:
        p = os.path.expandvars(ort)
        if os.path.exists(p):
            return p
    return ""


def tv_sicherstellen(trail, cfg=None, warten_s=12.0, start_url=None):
    """Ist TradingView offen? Wenn nicht: starten. -> (ok, msg, gestartet)

    Beweis 'offen' ist das Browser-Fenster selbst (Titel des aktiven Tabs,
    sonst die UIA-Tableiste) — NICHT der Reader: dessen letztes Bedienfeld
    liegt auch dann noch beim Server, wenn der Tab laengst zu ist. Der
    Seitentitel daraus dient nur als Suchbegriff.
    Nach dem Start gilt zusaetzlich ein Bedienfeld, das NACH dem Start ankam:
    das Userscript laeuft nur auf tradingview.com, ein frischer Stand heisst
    also 'Seite geladen UND Reader lebt' — mehr, als der Fenstertitel sagt."""
    cfg = cfg or {}
    bf0 = _tv_http("/bedienfeld", timeout=1.5) or {}
    begriff = tv_tab_suchbegriff(bf0.get("titel")) if bf0.get("ok") else ""
    w, _ = _tv_fenster_holen(trail, begriff, "")
    if w:
        return True, "TradingView war schon offen — Fenster ist vorn.", False

    chrome = _chrome_pfad(cfg.get("tv_browser_path"))
    if not chrome:
        return False, ("TradingView ist nicht offen, und chrome.exe wurde nicht "
                       "gefunden — Pfad als tv_browser_path in die config.json "
                       "schreiben."), False
    # start_url (22.09.2026): der Konto-Schritt startet ein noch NICHT offenes
    # TradingView gleich mit der Direkt-Adresse — dann steht der Connect-Dialog
    # sofort da (Finn: "genau wie wenn man normalerweise am Anfang startet,
    # mit dem Link"). Laeuft durch denselben Domain-Riegel wie tv_url.
    befehl = tv_start_befehl(chrome, start_url or cfg.get("tv_url"), cfg.get("tv_chrome_profil"))
    import subprocess
    # Losgeloest starten: das Panel wartet mit capture_output auf diesen Bot —
    # ein Kind, das dessen Pipes erbt, liesse den Aufruf haengen, bis Chrome
    # wieder zugeht.
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        subprocess.Popen(befehl, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    except OSError as e:
        return False, f"Chrome-Start fehlgeschlagen: {e}", False
    start = time.time()
    trail.append("TradingView nicht offen -> Chrome gestartet (" + befehl[-1] + ")")

    ende = start + float(warten_s)
    while time.time() < ende:
        _warte(0.5, 0.3)   # Jitter-Dauerregel 28.08.2026
        bf = _tv_http("/bedienfeld", timeout=1.5) or {}
        if bf.get("ok") and (time.time() - float(bf.get("alter_s") or 0.0)) >= start:
            trail.append("Reader meldet sich aus dem neuen Tab")
            return True, "TradingView gestartet — Seite ist geladen, der Reader meldet sich.", True
        probe = []
        w, _ = _tv_fenster_holen(probe, tv_tab_suchbegriff(bf.get("titel")) if bf.get("ok") else "", "")
        if w:
            trail.append("TradingView-Fenster erkannt")
            return True, "TradingView gestartet — Fenster ist vorn.", True
    # Kein Beweis ist kein Fehlschlag des Starts: Chrome IST gestartet, ein
    # kalter PC braucht nur laenger als das Zeitfenster des Knopfs (der Proxy
    # in app.py gibt 25 s, davon gehen die Fenster-Scans vorn und hinten ab —
    # deshalb 12 s Standard; die spaetere Kette darf laenger warten). Ehrlich
    # melden statt 'ok' zu behaupten.
    return False, (f"Chrome wurde gestartet, TradingView war nach {int(warten_s)} s aber "
                   "noch nicht zu erkennen — laedt vermutlich noch. Gleich noch "
                   "einmal klicken: ist es dann offen, kommt 'war schon offen'."), True


def modus_tvstart(cfg=None):
    res = {"ok": False, "msg": "", "trail": "", "gestartet": False}
    try:
        from pywinauto import Desktop  # noqa: F401  (nur Verfuegbarkeits-Probe)
    except ImportError:
        res["msg"] = "pywinauto fehlt (nur auf dem PC lauffaehig)."
        print(json.dumps(res))
        return
    _dpi_bewusst()
    _warte(0.1, 0.4)   # Start-Versatz (Jitter-Dauerregel 28.08.2026)
    trail = []
    try:
        res["ok"], res["msg"], res["gestartet"] = tv_sicherstellen(trail, cfg)
    except Exception as e:
        res["msg"] = f"TV-Start fehlgeschlagen: {type(e).__name__}: {e}"
    res["trail"] = " > ".join(trail)
    print(json.dumps(res))


# ═══════════════════════════════════════════════════════════════════════════
# FUTURES-PULS, NEUAUFBAU SCHRITT 2 (21.09.2026) — das richtige Konto
#
# Finn 21.09.2026: "jede Prop-Firm hat bei TradingView ihren eigenen Username
# … in den Einstellungen hinterlege ich den jeweiligen Username der Firma …
# der Puls weiss dann automatisch, welchen Account er auswaehlen muss. Ich muss
# hier immer nur draufdruecken: auf Login, dann einmal auf ein Feld, dann sehe
# ich die Autofill-Vorschlaege, und daneben druecke ich auf Login."
#
# TEIL 2a (dieser Stand):
#   1. TradingView sicherstellen (Schritt 1).
#   2. Aus dem Bedienfeld des Userscripts lesen, welches Konto im Broker-Panel
#      steht, und gegen die External ID des Plans pruefen (tv_konto_passt —
#      der Kontoname IST die External ID, Finns Ansage 30.08.2026).
#   3. Finns Korrektur 21.09.2026 abends: im Dropdown steht NIE der Tradovate-
#      Username, nur der Kontoname. Ob der LOGIN stimmt, beweist deshalb die
#      Datenbank: steht ein anderes Konto da, das Prophos bei DERSELBEN Firma
#      fuehrt ('geschwister'), ist es derselbe Login -> Dropdown oeffnen,
#      Zielkonto anklicken, am Panel beweisen. Nur wenn das aktive Konto
#      flach ist.
#   4. Steht ein Konto da, das Prophos bei der Firma NICHT kennt (anderer
#      Login), oder gar keins: NICHT raten, sondern den Kandidaten-Dump sichern.
#
# Warum nicht gleich ab- und anmelden: am 21.09. am echten TradingView
# nachgesehen — der Tradovate-Dialog ([data-name="broker-login-dialog"]) hat
# KEINE Username-Felder, nur Live/Demo + button[name="broker-login-submit-
# button"]. Der eigentliche Login (#name-input / #password-input, dort sitzt
# Chromes Autofill) laeuft in einem EIGENEN Tradovate-Fenster, in dem das
# Userscript nicht laeuft. Und wo im verbundenen Panel "Abmelden" sitzt, ist
# von hier aus nicht zu sehen. Am 30.08. wurden genau solche Stellen geraten —
# keiner der Selektoren existierte. Deshalb liefert der erste Lauf mit
# falschem Konto die Unterlagen, und Teil 2b klickt danach auf Bewiesenes.
#
# Das Passwort fasst der Bot in KEINEM Teil an: es liegt in Chromes Passwort-
# Manager. Uebergeben wird nur der Username.
# ═══════════════════════════════════════════════════════════════════════════

TV_KONTO_DUMP = "tv-konto-dump.json"


def pruefe_tv_konto_befehl(cmd):
    """Fehlerliste fuer den tvkonto-Befehl (leer = in Ordnung)."""
    fehler = []
    if not isinstance(cmd, dict):
        return ["Befehl ist kein Objekt"]
    if len(_nur_alnum(cmd.get("ext_id"))) < 3:
        fehler.append("External ID fehlt oder ist kuerzer als 3 Zeichen")
    # Der Username ist seit 2a-Dropdown (21.09.2026 abends) KEINE Pflicht mehr:
    # liegt das Zielkonto im selben Login, braucht es ihn nie. Gebraucht wird
    # er erst fuers Ab-/Anmelden (Teil 2b) — ist er gesetzt, muss er sauber sein.
    u = str(cmd.get("tv_username") or "").strip()
    if u and (len(u) > 80 or any(c.isspace() or ord(c) < 32 for c in u)):
        fehler.append("Tradovate-Username enthaelt Leer- oder Steuerzeichen")
    g = cmd.get("geschwister")
    if g is not None and not isinstance(g, list):
        fehler.append("geschwister muss eine Liste sein")
    return fehler


def tv_konto_wort_passt(text, ext_id):
    """Steht die External ID als GANZES WORT im Text? (21.09.2026 nachts,
    Finns Screenshot: im Panel stand 'PAAPEX6416990000008' — und darin steckt
    als Teilstring 'APEX6416990000008'. Das PA-Konto und das Eval-Konto
    desselben Apex-Users sind aber ZWEI Konten; mit dem Teilstring-Vergleich
    von tv_konto_passt haette der Bot das eine fuer das andere gehalten, und
    die Order waere spaeter auf dem falschen Konto gelandet.)
    Zerlegt wird an Leerraum und Trennzeichen, die TradingView um den Namen
    setzt ('APEX-123-01 · PA', 'APEX…024 USD', 'Name (2)'); Bindestriche und
    Unterstriche gehoeren zum Wort. Verglichen wird nur-alphanumerisch und auf
    GLEICHHEIT. Der 3-Zeichen-Riegel bleibt."""
    e = _nur_alnum(ext_id)
    if len(e) < 3:
        return False
    return any(_nur_alnum(w) == e for w in re.split(r"[\s·|,;:()\[\]/]+", str(text or "")))


def tv_konto_bestes(text, ids):
    """Welche der bekannten External IDs MEINT dieser Konto-Text? Die LAENGSTE,
    die passt — tv_konto_passt ist ein Teilstring-Vergleich, und 'APEX-123-01'
    steckt auch in 'APEX-123-011'. Ohne diese Regel wuerde das laengere
    Geschwister-Konto als das kuerzere Zielkonto durchgehen. '' = keine passt."""
    bestes = ""
    for i in ids or ():
        if tv_konto_wort_passt(text, i) and len(_nur_alnum(i)) > len(_nur_alnum(bestes)):
            bestes = str(i)
    return bestes


def _tv_rect4(e):
    r = (e or {}).get("rect")
    if isinstance(r, (list, tuple)) and len(r) == 4:
        try:
            x, y, w, h = (float(v) for v in r)
        except (TypeError, ValueError):
            return None
        return (x, y, w, h) if w >= 3 and h >= 3 else None
    return None


def _tv_rect_in(a, b):
    """Liegt Rechteck a (x,y,w,h) ganz in b? (2 px Toleranz — Rundung im Userscript)"""
    return (a[0] >= b[0] - 2 and a[1] >= b[1] - 2
            and a[0] + a[2] <= b[0] + b[2] + 2 and a[1] + a[3] <= b[1] + b[3] + 2)


def tv_konto_per_text(bf, ids, nur_ziel=None, ohne=None, ueberall=False):
    """Konto-Elemente ueber ihren TEXT finden statt ueber TradingViews Anker.

    21.09.2026, Finns erster Lauf von Schritt 2 (PC mit englischem
    TradingView): im Panel stand sichtbar 'APEX6416990000024 USD' — das
    RICHTIGE Konto —, der Bot meldete trotzdem 'kein Broker'. Beide Signaturen
    des Userscripts ([data-name="account-manager-account-select"] und
    [data-name*="account"]) hatten null Treffer: TradingView hat die Anker
    umbenannt, zum zweiten Mal (31.08.: Spaltentitel). Der Bot KENNT aber die
    External IDs — und eine 17-stellige Kontonummer im Broker-Panel ist ein
    besserer Anker als jeder data-name, weil TradingView sie nicht umbenennen
    kann. Quelle sind die Element-Listen, die das Userscript ohnehin schickt
    ('panel' immer, 'dump' auf Anforderung) — kein Userscript-Update noetig.

    Verschachtelte Treffer (Huelle + Knopf + Textspanne tragen denselben Text)
    werden auf den INNERSTEN reduziert; dessen Mitte liegt in allen Huellen,
    ein Klick dort trifft also auch den Knopf.
    nur_ziel: nur Elemente, deren beste ID diese ist. ohne: Rechteck, das
    nicht (nochmal) getroffen werden soll — der Umschalter selbst, wenn nach
    Listeneintraegen gesucht wird.
    -> Liste {rect, text, id}, innerste zuerst gefiltert, unten im Fenster."""
    geo = (bf or {}).get("geo") or {}
    try:
        hoehe = float(geo.get("innerHeight") or 0)
    except (TypeError, ValueError):
        hoehe = 0.0
    roh = []
    # 'treffer' (Userscript 0.4.2+) ist die gezielte Suche im GANZEN DOM — ist
    # sie da (auch als leere Liste!), gilt NUR sie: 'panel'/'dump' sind bei 130
    # bzw. 150 Elementen gekappt und sehen die Aufklappliste am Ende des DOM
    # nicht (Finns zweiter Lauf 21.09.2026: Dropdown offen, "0 Eintraege").
    # Fehlt das Feld (altes Userscript), bleibt der gekappte Weg als Notbehelf.
    quellen = ("treffer",) if isinstance((bf or {}).get("treffer"), list) else ("panel", "dump")
    for quelle in quellen:
        for e in ((bf or {}).get(quelle) or []):
            if not isinstance(e, dict):
                continue
            r = _tv_rect4(e)
            text = str(e.get("text") or "")
            if not r or not text:
                continue
            # Broker-Panel und seine Aufklappliste liegen in der unteren
            # Fensterhaelfte; oben stuende dieselbe Nummer hoechstens in einer
            # Chart-Beschriftung, und die ist kein Bedienelement.
            # (ueberall=True fuer die Aufklappliste: sie klappt vom unteren
            # Rand nach OBEN und kann bei vielen Konten weit hinaufreichen.)
            if not ueberall and hoehe and r[1] + r[3] / 2 < hoehe * 0.45:
                continue
            bestes = tv_konto_bestes(text, ids)
            if not bestes:
                continue
            if nur_ziel is not None and _nur_alnum(bestes) != _nur_alnum(nur_ziel):
                continue
            if ohne and (_tv_rect_in(r, ohne) or _tv_rect_in(ohne, r)):
                continue
            roh.append({"rect": [int(v) for v in r], "text": text[:80], "id": bestes, "_r": r})
    # doppelte (panel + dump liefern dasselbe Element) und Huellen raus
    innerste = []
    for a in roh:
        if any(b is not a and _tv_rect_in(b["_r"], a["_r"]) and b["_r"] != a["_r"] for b in roh):
            continue
        if any(a["_r"] == c["_r"] for c in innerste):
            continue
        innerste.append(a)
    for a in innerste:
        a.pop("_r", None)
    return innerste


def tv_uia_filtern(roh, ids, fenster=None, nur_ziel=None, ohne=None):
    """Aus (text, (l,t,r,b))-Paaren der Windows-UI-Automation die Konto-Elemente
    machen. Koordinaten sind hier ECHTE Bildschirm-Pixel — kein CSS, kein dpr,
    keine Browser-Dekoration: der Klickpunkt ist einfach die Mitte.
    fenster: (l,t,r,b) des Browser-Fensters — was ausserhalb liegt, ist nicht
    klickbar. nur_ziel/ohne wie bei tv_konto_per_text (ohne = Rechteck des
    Umschalters, damit er nicht als Listeneintrag durchgeht).
    Huellen (ListItem um seinen Text) werden auf das innerste reduziert."""
    kand = []
    for text, r in roh or ():
        try:
            l, t, rr, b = (int(v) for v in r)
        except (TypeError, ValueError):
            continue
        if rr - l < 3 or b - t < 3:
            continue
        mx, my = (l + rr) // 2, (t + b) // 2
        if fenster and not (fenster[0] <= mx <= fenster[2] and fenster[1] <= my <= fenster[3]):
            continue
        # KLEMMEN (22.09.2026 12:33, Finns PC: der Konto-Umschalter ragt unter den
        # Fensterrand, nur ein Streifen ist sichtbar; die Element-MITTE (y=2074) lag
        # in Chromes unsichtbarem Anfass-Rand am Fensterboden — der Klick traf nichts,
        # 'der Knopf wurde noch nie gedrueckt'). Der Punkt bleibt mindestens 12 px
        # ueber dem Fensterboden und im oberen Teil des Elements.
        if fenster:
            my = max(t + 3, min(my, fenster[3] - 12))
        bestes = tv_konto_bestes(text, ids)
        if not bestes:
            continue
        if nur_ziel is not None and _nur_alnum(bestes) != _nur_alnum(nur_ziel):
            continue
        if ohne and not (rr <= ohne[0] or l >= ohne[2] or b <= ohne[1] or t >= ohne[3]):
            continue          # ueberlappt den Umschalter
        kand.append({"text": str(text)[:80], "id": bestes, "r": (l, t, rr, b), "punkt": (mx, my)})
    out = []
    for a in kand:
        ar = a["r"]
        huelle = any(b is not a and b["r"] != ar
                     and b["r"][0] >= ar[0] - 2 and b["r"][1] >= ar[1] - 2
                     and b["r"][2] <= ar[2] + 2 and b["r"][3] <= ar[3] + 2 for b in kand)
        if huelle or any(c["r"] == ar for c in out):
            continue
        out.append(a)
    return out


# Reihenfolge = Wahrscheinlichkeit: Chrome legt fuer jeden sichtbaren Textknoten
# ein Text-Element an; die uebrigen Typen sind der Rueckfall, falls TradingView
# den Namen nur am Eintrag selbst traegt.
_TV_UIA_TYPEN = ("Text", "ListItem", "MenuItem", "Button", "ComboBox", "DataItem")


# ── SAMMELABFRAGE (22.09.2026, Finn nach dem ersten kompletten Live-Durchlauf:
# "es ist noch sooo langsam, gefuehlt 20 s pro Step — bekommst du das schneller,
# VIEL schneller?") ───────────────────────────────────────────────────────────
# WOHER DIE 20 s KAMEN: der bisherige Scan holte ueber pywinauto alle Elemente
# eines Typs und fragte dann JEDES EINZELN bei Chrome nach Name, Sichtbarkeit
# und Rechteck — jede Frage ein eigener Aufruf ueber die Prozessgrenze. Eine
# TradingView-Seite hat ein paar tausend Textknoten, also tausende Aufrufe pro
# Durchgang, und jede Warteschleife fuhr mehrere Durchgaenge.
# JETZT: Windows-UIA kann Eigenschaften VORAB mitliefern (CacheRequest). EIN
# Aufruf (FindAllBuildCache) bringt alle Elemente der gesuchten Typen samt
# Name, Rechteck, Sichtbarkeit und Typ; gelesen wird danach nur noch lokal.
# Geht der Weg auf einem PC nicht (Ausnahme), bleibt es beim alten Scan —
# schlimmstenfalls ist es also so schnell wie vorher.
_UIA_TYPID = {"Button": 50000, "CheckBox": 50002, "ComboBox": 50003, "Edit": 50004,
              "Hyperlink": 50005, "Image": 50006, "ListItem": 50007, "MenuItem": 50011,
              "List": 50008, "Menu": 50009, "RadioButton": 50013, "TabItem": 50019, "Text": 50020,
              "Custom": 50025, "Group": 50026, "DataItem": 50029, "Pane": 50033}
_UIA_SAMMEL = {"geht": None}      # None = noch nicht probiert, True/False = Ergebnis


def _tv_uia_sammel(w, typen):
    """Alle Elemente der Typen in EINEM Aufruf. -> [(name, (l,t,r,b)|None, typ)]
    mit rect=None fuer Unsichtbares; None, wenn der Weg nicht geht."""
    if _UIA_SAMMEL["geht"] is False:
        return None
    try:
        from pywinauto.uia_defines import IUIA
        u = IUIA()
        dll = u.UIA_dll
        anfrage = u.iuia.CreateCacheRequest()
        for pid in (dll.UIA_NamePropertyId, dll.UIA_BoundingRectanglePropertyId,
                    dll.UIA_IsOffscreenPropertyId, dll.UIA_ControlTypePropertyId):
            anfrage.AddProperty(pid)
        bed = None
        for t in typen:
            tid = _UIA_TYPID.get(t)
            if not tid:
                continue
            c = u.iuia.CreatePropertyCondition(dll.UIA_ControlTypePropertyId, tid)
            bed = c if bed is None else u.iuia.CreateOrCondition(bed, c)
        if bed is None:
            return []
        feld = w.element_info.element.FindAllBuildCache(u.tree_scope["descendants"], bed, anfrage)
        name_von = {v: k for k, v in _UIA_TYPID.items()}
        roh = []
        for i in range(feld.Length):
            e = feld.GetElement(i)
            try:
                n = str(e.CachedName or "").strip()
                if not n or len(n) > 200:
                    continue
                typ = name_von.get(e.CachedControlType, "")
                if e.CachedIsOffscreen:
                    roh.append((n, None, typ))
                    continue
                r = e.CachedBoundingRectangle
                roh.append((n, (r.left, r.top, r.right, r.bottom), typ))
            except Exception:
                continue
        _UIA_SAMMEL["geht"] = True
        return roh
    except Exception:
        _UIA_SAMMEL["geht"] = False
        return None


class _FeldSchnapp:
    """Ein Eingabefeld aus der Sammelabfrage — gleiche Schnittstelle wie der
    pywinauto-Wrapper, soweit der Puls sie braucht, aber alles schon gelesen."""
    def __init__(self, rect, wert, passwort, fokus, bedienbar):
        self._rect, self._wert = rect, wert
        self._pw, self._fokus, self._an = bool(passwort), bool(fokus), bool(bedienbar)
        self.iface_value = type("V", (), {"CurrentValue": wert})()
        self.element_info = type("I", (), {"element": type("E", (), {"CurrentIsPassword": self._pw})()})()

    def rectangle(self):
        l, t, r, b = self._rect
        return type("R", (), {"left": l, "top": t, "right": r, "bottom": b})()

    def is_visible(self):
        return True

    def is_enabled(self):
        return self._an

    def has_keyboard_focus(self):
        return self._fokus


def _tv_uia_felder(w):
    """Alle sichtbaren Eingabefelder eines Fensters in EINEM Aufruf (22.09.2026,
    Finn: 'hier ist immer noch sehr viel Leerzeit, der macht hier so 5 sec nix').
    Bisher holte pywinauto die Felder ueber einen Gang durch den ganzen Baum und
    fragte dann Wert, Passwort-Kennzeichen und Fokus einzeln ab — auf der
    Anmeldeseite mehrfach hintereinander. -> Liste von _FeldSchnapp, oder None,
    wenn der Weg nicht geht (dann faehrt der Aufrufer den alten).
    Vom Passwortfeld wird weiter nur gebraucht, DASS es gefuellt ist."""
    if _UIA_SAMMEL["geht"] is False:
        return None
    try:
        from pywinauto.uia_defines import IUIA
        u = IUIA()
        dll = u.UIA_dll
        P_OFF, P_PW = dll.UIA_IsOffscreenPropertyId, dll.UIA_IsPasswordPropertyId
        P_WERT, P_FOKUS, P_AN = dll.UIA_ValueValuePropertyId, dll.UIA_HasKeyboardFocusPropertyId, dll.UIA_IsEnabledPropertyId
        anfrage = u.iuia.CreateCacheRequest()
        for pid in (dll.UIA_BoundingRectanglePropertyId, P_OFF, P_PW, P_WERT, P_FOKUS, P_AN):
            anfrage.AddProperty(pid)
        bed = u.iuia.CreatePropertyCondition(dll.UIA_ControlTypePropertyId, _UIA_TYPID["Edit"])
        feld = w.element_info.element.FindAllBuildCache(u.tree_scope["descendants"], bed, anfrage)
        out = []
        for i in range(feld.Length):
            e = feld.GetElement(i)
            try:
                if e.GetCachedPropertyValue(P_OFF):
                    continue
                r = e.CachedBoundingRectangle
                if r.right - r.left < 3 or r.bottom - r.top < 3:
                    continue
                out.append(_FeldSchnapp((r.left, r.top, r.right, r.bottom),
                                        str(e.GetCachedPropertyValue(P_WERT) or ""),
                                        e.GetCachedPropertyValue(P_PW), e.GetCachedPropertyValue(P_FOKUS),
                                        e.GetCachedPropertyValue(P_AN)))
            except Exception:
                continue
        return out
    except Exception:
        return None


def _tv_uia_knoepfe_alle(w):
    """ALLE sichtbaren Knoepfe eines Fensters, auch UNBENANNTE, in einem UIA-Aufruf.
    -> [(name, (l,t,r,b))] oder None. (22.09.2026 12:3x, Finns PC: der ⤢-Knopf
    'Maximize panel' traegt nur einen Tooltip, keinen Accessibility-Namen — die
    Sammelabfrage laesst Namenloses weg, hier zaehlt die LAGE.)"""
    if _UIA_SAMMEL["geht"] is False:
        return None
    try:
        from pywinauto.uia_defines import IUIA
        u = IUIA()
        dll = u.UIA_dll
        anfrage = u.iuia.CreateCacheRequest()
        for pid in (dll.UIA_NamePropertyId, dll.UIA_BoundingRectanglePropertyId, dll.UIA_IsOffscreenPropertyId):
            anfrage.AddProperty(pid)
        bed = u.iuia.CreatePropertyCondition(dll.UIA_ControlTypePropertyId, _UIA_TYPID["Button"])
        feld = w.element_info.element.FindAllBuildCache(u.tree_scope["descendants"], bed, anfrage)
        out = []
        for i in range(feld.Length):
            e = feld.GetElement(i)
            try:
                if e.CachedIsOffscreen:
                    continue
                r = e.CachedBoundingRectangle
                if r.right - r.left < 6 or r.bottom - r.top < 6:
                    continue
                out.append((str(e.CachedName or "").strip(), (r.left, r.top, r.right, r.bottom)))
            except Exception:
                continue
        return out
    except Exception:
        return None


def _tv_uia_schalter(w):
    """Alle Umschalter (Toggle-Muster) eines Fensters in EINEM Aufruf (22.09.2026
    01:50, Finns Lauf: 'er platziert nur einen TP, SL vergisst er komplett' —
    Trail: 'Stop loss = 22.0 $' OHNE Tippen und OHNE 'Schalter AN'. Der alte
    Wert 22 stand noch im Feld, das Feld war laut UIA BEDIENBAR — und genau das
    galt bis dahin als 'Schalter an'. Bei TradingView ist das Feld aber auch bei
    AUS bedienbar; der Schalter selbst war aus, die Order ging ohne SL raus. Beim
    TP hatte nur das TIPPEN den Schalter angeknipst).
    -> [((l,t,r,b), an: bool|None)] oder None, wenn der Weg nicht geht."""
    if _UIA_SAMMEL["geht"] is False:
        return None
    try:
        from pywinauto.uia_defines import IUIA
        u = IUIA()
        dll = u.UIA_dll
        P_OFF, P_TOG = dll.UIA_IsOffscreenPropertyId, dll.UIA_ToggleToggleStatePropertyId
        anfrage = u.iuia.CreateCacheRequest()
        for pid in (dll.UIA_BoundingRectanglePropertyId, P_OFF, P_TOG):
            anfrage.AddProperty(pid)
        bed = u.iuia.CreatePropertyCondition(dll.UIA_IsTogglePatternAvailablePropertyId, True)
        feld = w.element_info.element.FindAllBuildCache(u.tree_scope["descendants"], bed, anfrage)
        out = []
        for i in range(feld.Length):
            e = feld.GetElement(i)
            try:
                if e.GetCachedPropertyValue(P_OFF):
                    continue
                r = e.CachedBoundingRectangle
                if r.right - r.left < 3 or r.bottom - r.top < 3:
                    continue
                z = e.GetCachedPropertyValue(P_TOG)
                out.append(((r.left, r.top, r.right, r.bottom), True if z == 1 else False if z == 0 else None))
            except Exception:
                continue
        return out
    except Exception:
        return None


def tv_schalter_zu(schalter, label_r, bereich):
    """Der Umschalter ZU einer Beschriftung: gleiche Zeile (Mitte +-14 px), rechts
    von ihr, im Panel — bei mehreren der am weitesten rechts (der Schalter sitzt
    am rechten Panelrand). -> (rect, an) oder (None, None)"""
    ly = (label_r[1] + label_r[3]) // 2
    best = None
    for r, an in schalter or ():
        my = (r[1] + r[3]) // 2
        if abs(my - ly) > 14 or r[0] <= label_r[2] or r[2] > bereich["rechts"] + 10:
            continue
        if best is None or r[0] > best[0][0]:
            best = (r, an)
    return best if best else (None, None)


TV_RX_PANEL_KOPF = re.compile(r"^(account balance|kontostand|equity|eigenkapital|profit|gewinn)$", re.I)
TV_RX_PANEL_MAX = re.compile(r"(maxim|expand|vergr|erweiter|aufklapp)", re.I)
TV_RX_PANEL_RESTORE = re.compile(r"(restore|wiederherstell)", re.I)


def tv_panel_eingeklappt(roh, fenster, knoepfe=None):
    """Ist das Tradovate-Panel unten nur als KOPFZEILE zu sehen? (22.09.2026,
    Finns PC, erster Lauf: 'unten sieht man den Accountnamen nicht — man muesste
    das Fenster an der Leiste hochziehen'; bei Moritz laedt es aufgeklappt.)
    Kopfzeile = 'Account Balance'/'Equity' im unteren Fensterbereich; ZU FLACH,
    wenn darunter bis zum Fensterrand weniger als 11 % der Fensterhoehe (mind.
    90 px) bleiben — dann passt die aufgeklappte Konto-Liste nicht hinein
    (22.09.2026 12:2x, Finns zweiter Lauf: Konto sichtbar, Dropdown geklickt,
    '0 Treffer' — die Liste wurde unten abgeschnitten). Moritz' offenes Panel
    (~17 % der Hoehe) bleibt unberuehrt.
    -> {'kopf_y': y, 'knopf': {...}|None} oder None (Kopfzeile nicht zu sehen /
    Panel offen). knopf = Maximieren-Knopf in derselben Zeile, falls benannt."""
    if not fenster:
        return None
    l, t, r, b = fenster
    h = max(1, b - t)
    kopf = [e for e in roh or () if e[1] and TV_RX_PANEL_KOPF.match(str(e[0]).strip()) and e[1][1] > t + h * 0.6]
    if not kopf:
        return None
    ky = min((e[1][1] + e[1][3]) // 2 for e in kopf)
    if b - ky > max(90, int(h * 0.11)):
        return None
    # Trennleiste = knapp ueber der obersten Zeile des Panels (Broker-Knopf 'Tradovate',
    # sonst die Kopfzeile selbst)
    oben = [e[1][1] for e in roh or () if e[1] and re.match(r"^tradovate\b", str(e[0]).strip(), re.I)
            and ky - 120 <= (e[1][1] + e[1][3]) // 2 <= ky + 10]
    leiste_y = (min(oben) - 12) if oben else (ky - 34)
    knopf = None
    for e in roh or ():
        if not e[1] or (len(e) > 2 and e[2] not in ("Button", "")):
            continue
        n = str(e[0]).strip()
        # Knopf-Zeile ('Tradovate ▾ … — ⤢') liegt bei Finn ~40 px UEBER der Kopfzeile
        if TV_RX_PANEL_MAX.search(n) and -60 <= (e[1][1] + e[1][3]) // 2 - ky <= 25:
            knopf = {"text": n[:40], "r": tuple(e[1]), "punkt": ((e[1][0] + e[1][2]) // 2, (e[1][1] + e[1][3]) // 2)}
            break
    if knopf is None and knoepfe:
        # OHNE Namen ueber die LAGE (Finns Screenshot 12:22): die Knopfzeile ist die
        # Zeile des Broker-Knopfs 'Tradovate' (ueber der Kopfzeile); 'Maximize panel'
        # ist darin der RECHTESTE Knopf, direkt links daneben 'Minimize'. Rechts
        # begrenzt die Kopfzeile selbst (rechte Kante von 'Profit'/'Equity').
        zeile = [e for e in roh or () if e[1] and re.match(r"^tradovate\b", str(e[0]).strip(), re.I)
                 and ky - 120 <= (e[1][1] + e[1][3]) // 2 <= ky + 10]
        if zeile:
            zy = (zeile[0][1][1] + zeile[0][1][3]) // 2
            rechts = max(e[1][2] for e in kopf)
            kand = [(n, r) for n, r in knoepfe if abs((r[1] + r[3]) // 2 - zy) <= 14
                    and r[2] <= rechts + 30 and r[0] >= rechts - 160 and (r[2] - r[0]) <= 60]
            if kand:
                n, r = max(kand, key=lambda x: x[1][2])
                knopf = {"text": (n or "unbenannt, rechtester Knopf der Panelzeile")[:40], "r": tuple(r),
                         "punkt": ((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)}
    return {"kopf_y": ky, "knopf": knopf, "leiste_y": leiste_y}


def tv_panel_lage(roh, knoepfe, fenster):
    """Lage des Tradovate-Panels + Klick-Kandidaten fuer seinen Maximieren-/
    Restore-Knopf (22.09.2026 13:1x, Finn: 'nur daran arbeiten, dass er dieses
    Maximieren-Feld drueckt — ueberall draufdruecken unten rechts, wo das Ding ist,
    bis das Feld weiss wird'). Rein rechnend.
    -> {'zustand': 'oben'|'unten'|None, 'kopf_y', 'kandidaten': [(x, y, wie)]}
    Kopfzeile = 'Account Balance'/'Equity'/'Profit'. 'oben' = Kopfzeile im oberen
    Drittel (Panel maximiert, Chart weiss), 'unten' = darunter. Knopfzeile = Zeile des
    Broker-Knopfs 'Tradovate' (sonst 42 px ueber der Kopfzeile). Rechte Kante = rechte
    Kante von 'Profit' (sonst 36 px links der Watchlist-Spalte 'Symbol'/'Watchlist').
    Kandidaten in dieser Reihenfolge: benannte Knoepfe, unbenannte kleine Knoepfe der
    Zeile von rechts, dann ein RASTER um die feste Lage (6-30 px links der rechten
    Kante, drei Hoehen) — der ⤢ sass in Finns Screenshot 6 px links der Kante."""
    if not fenster:
        return {"zustand": None, "kopf_y": None, "kandidaten": []}
    l, t, r, b = fenster
    h, br = max(1, b - t), max(1, r - l)
    kopf = [e for e in roh or () if e[1] and TV_RX_PANEL_KOPF.match(str(e[0]).strip())]
    # Kopfzeile = die Zeile von 'Profit' (22.09.2026 14:1x, dritter PC: ein 'Account
    # Balance' weiter oben auf der Seite (y=234) galt als Kopfzeile, waehrend 'Profit' bei
    # 622 lag — 30 Klicks in die falsche Zeile, einer traf den 'Trade'-Knopf und schloss
    # das Order-Panel). Ohne 'Profit': die Zeile, in der die meisten Labels liegen.
    if kopf:
        pz = [e for e in kopf if re.match(r"^(profit|gewinn)$", str(e[0]).strip(), re.I)]
        if pz:
            py0 = (pz[-1][1][1] + pz[-1][1][3]) // 2
        else:
            ys = [(e[1][1] + e[1][3]) // 2 for e in kopf]
            py0 = max(ys, key=lambda y: sum(1 for y2 in ys if abs(y2 - y) <= 12))
        kopf = [e for e in kopf if abs((e[1][1] + e[1][3]) // 2 - py0) <= 12]
    ky = min((e[1][1] + e[1][3]) // 2 for e in kopf) if kopf else None
    zustand = None if ky is None else ("oben" if ky < t + h * 0.34 else "unten")
    rechts = max(e[1][2] for e in kopf) if kopf else None
    if rechts is None:
        wl = [e[1][0] for e in roh or () if e[1] and re.match(r"^(watchlist|symbol)$", str(e[0]).strip(), re.I)
              and e[1][0] > l + br * 0.6]
        rechts = (min(wl) - 36) if wl else (r - int(br * 0.19))
    zeile = [e for e in roh or () if e[1] and re.match(r"^tradovate\b", str(e[0]).strip(), re.I)
             and (ky is None or ky - 120 <= (e[1][1] + e[1][3]) // 2 <= ky + 10)]
    zy = (zeile[0][1][1] + zeile[0][1][3]) // 2 if zeile else ((ky - 42) if ky is not None else (b - int(h * 0.05)))
    kand = []
    # ZUERST direkt ueber 'Profit' (Finn 22.09.2026 13:07, Screenshot mit Tooltip 'Maximize
    # panel': 'eigentlich muss er nur ueber Profit klicken' — ⤢ sitzt 5 px links der rechten
    # Kante von 'Profit', 43 px darueber; 'Restore panel' nach dem Maximieren an derselben
    # Stelle relativ zur dann oben liegenden Kopfzeile).
    profit = [e for e in kopf if re.match(r"^(profit|gewinn)$", str(e[0]).strip(), re.I)]
    if profit:
        pr = profit[0][1]
        py = (pr[1] + pr[3]) // 2
        # Finn 13:1x: "ueber dem i von Profit einfach immer nach oben gehen" — das 'i' ist
        # der vorletzte Buchstabe, ~80 % der Wortbreite; senkrecht darueber in 6-px-Schritten.
        xi = pr[0] + int((pr[2] - pr[0]) * 0.80)
        for dy in (-43, -37, -49, -31, -55, -25, -61, -67):
            kand.append((xi, py + dy, f"ueber dem i von 'Profit' ({dy:+d})"))
        for dx, dy in ((5, -43), (pr[2] - (pr[0] + pr[2]) // 2, -43), (9, -43)):
            kand.append((pr[2] - dx, py + dy, "ueber 'Profit'"))
    for e in roh or ():
        n = str(e[0]).strip()
        if e[1] and (len(e) < 3 or e[2] in ("Button", "")) and re.search(r"(maxim|expand|restore|wiederherstell|vergr)", n, re.I) \
           and abs((e[1][1] + e[1][3]) // 2 - zy) <= 25:
            kand.append(((e[1][0] + e[1][2]) // 2, (e[1][1] + e[1][3]) // 2, f"Knopf '{n[:24]}'"))
    klein = [(n, rr) for n, rr in (knoepfe or ()) if abs((rr[1] + rr[3]) // 2 - zy) <= 14
             and rr[2] <= rechts + 30 and rr[0] >= rechts - 160 and (rr[2] - rr[0]) <= 60]
    for n, rr in sorted(klein, key=lambda x: -x[1][2])[:3]:
        kand.append(((rr[0] + rr[2]) // 2, (rr[1] + rr[3]) // 2, "unbenannter Knopf der Panelzeile"))
    for dx in (6, 12, 18, 24):
        kand.append((rechts - dx, zy, f"Raster {dx} px links der Kante"))
    out = []
    for x, y, wie in kand:
        if any(abs(x - ox) <= 3 and abs(y - oy) <= 3 for ox, oy, _w in out):
            continue
        out.append((x, y, wie))
    return {"zustand": zustand, "kopf_y": ky, "kandidaten": out, "rechts": rechts, "zeile_y": zy}


def _tv_panel_umschalten(w, trail, ziel):
    """Panel per Knopf nach 'oben' (maximiert) oder 'unten' (wiederhergestellt)
    bringen — Kandidaten nacheinander klicken und nach JEDEM Klick die Lage
    zurueckerlesen, bis sie stimmt. -> True, wenn das Panel am Ende im Ziel-
    Zustand ist (auch wenn es schon dort war)."""
    fr = _tv_fenster_rect(w)
    roh0 = _tv_uia_roh(w, ("Text", "Button"))
    lage = tv_panel_lage(roh0, None, fr)
    if lage["zustand"] == ziel:
        return True
    if lage["zustand"] is not None:
        lage = tv_panel_lage(roh0, _tv_uia_knoepfe_alle(w), fr)   # Knoepfe nur, wenn geklickt werden muss
    if lage["zustand"] is None:
        # ohne Kopfzeile kein Anker -> NICHT blind klicken (22.09.2026 18:3x, Spur 16:29: vier
        # Raster-Klicks ins Leere, 5 s weg; fuer 'unten' gibt es ohnehin nichts zurueckzunehmen)
        if ziel == "oben":
            trail.append("Tradovate-Panel: keine Kopfzeile (Account Balance/Equity/Profit) zu sehen — kein Klick")
        return ziel == "unten"
    trail.append(f"Panel {lage['zustand'] or 'ohne Kopfzeile'}: Kante x={lage['rechts']}, Zeile y={lage['zeile_y']}, Fenster {fr}")
    probiert = []
    for x, y, wie in lage["kandidaten"]:
        _tv_uia_klick({"punkt": (x, y)}, f"Panel {'maximieren' if ziel == 'oben' else 'wiederherstellen'} ({wie})", trail)
        probiert.append(f"{x},{y}")
        ende = time.time() + 0.9
        while time.time() < ende:
            _warte(0.25, 0.15)
            neu = tv_panel_lage(_tv_uia_roh(w, ("Text", "Button")), None, fr)
            if neu["zustand"] == ziel:
                trail.append(f"Panel ist jetzt {ziel} (Klick {x},{y})")
                return True
    trail.append(f"Panel blieb {lage['zustand'] or 'ohne Kopfzeile'} — geklickt: " + " | ".join(probiert))
    return False


def _tv_uia_konten(w, ids, info=None, nur_ziel=None, ohne=None):
    """AUGEN OHNE USERSCRIPT (21.09.2026, Finn: 'nein, ohne Tampermonkey — das
    bekommen wir doch auch so hin'): die Kontonummern direkt aus Chromes
    Accessibility-Baum lesen, ueber dieselbe Windows-UI-Automation, mit der
    der Puls seit 30.08. die Tableiste liest. Vorteile gegenueber dem
    Userscript: nichts zu installieren oder zu aktualisieren, keine Kappung
    (die Aufklappliste am DOM-Ende ist ein ganz normaler Teil des Baums), und
    die Rechtecke sind schon Bildschirm-Pixel.
    Chrome baut den Seiten-Baum erst auf, wenn ein UIA-Client danach fragt —
    der erste Abruf kann deshalb leer sein; die Aufrufer fragen mehrfach."""
    info = info if info is not None else {}
    try:
        fr = w.rectangle()
        fenster = (fr.left, fr.top, fr.right, fr.bottom)
    except Exception:
        fenster = None
    roh, gescannt = [], 0
    # Fuer die Ferndiagnose: Namen, die WIE eine Kontonummer aussehen (>= 6
    # Ziffern am Stueck), auch wenn sie zu keiner bekannten ID passen. Zeigt im
    # Fehlfall sofort, ob der Baum die Seite ueberhaupt enthaelt und wie
    # TradingView die Nummer dort schreibt.
    aehnlich = info.setdefault("aehnlich", [])
    sammel = _tv_uia_sammel(w, ("Text", "ListItem", "MenuItem", "Button", "ComboBox"))
    if sammel is not None:
        info["weg"] = "sammel"
        info["gescannt"] = len(sammel)
        for n, r, _typ in sammel:
            if not tv_konto_bestes(n, ids):
                if len(aehnlich) < 20 and re.search(r"\d{6,}", n) and n[:50] not in aehnlich:
                    aehnlich.append(n[:50])
                continue
            if r:
                roh.append((n, r))
        info["roh"] = [(t[:40], list(r)) for t, r in roh[:12]]
        return tv_uia_filtern(roh, ids, fenster, nur_ziel=nur_ziel, ohne=ohne)
    info["weg"] = "einzeln"
    for typ in _TV_UIA_TYPEN:
        try:
            els = w.descendants(control_type=typ)
        except Exception as e:
            info["fehler"] = f"{typ}: {type(e).__name__}"
            continue
        for e in els[:6000]:
            gescannt += 1
            try:
                n = e.window_text() or ""
            except Exception:
                continue
            if not (3 <= len(n) <= 200):
                continue
            if not tv_konto_bestes(n, ids):
                if len(aehnlich) < 20 and re.search(r"\d{6,}", n) and n[:50] not in aehnlich:
                    aehnlich.append(n[:50])
                continue
            try:
                r = e.rectangle()
                if hasattr(e, "is_visible") and not e.is_visible():
                    continue
                roh.append((n, (r.left, r.top, r.right, r.bottom)))
            except Exception:
                continue
        if roh:
            break               # Text-Elemente haben geliefert -> Rueckfall-Typen sparen
    info["gescannt"] = gescannt
    info["roh"] = [(t[:40], list(r)) for t, r in roh[:12]]
    return tv_uia_filtern(roh, ids, fenster, nur_ziel=nur_ziel, ohne=ohne)


def _tv_uia_klick(el, name, trail):
    """UIA-Element anklicken — Punkt ist schon Bildschirm-Pixel. (ok, fehler)"""
    x, y = el["punkt"]
    _maus_fahren(x, y)
    if not _klick_absolut(x, y):
        trail.append(f"{name}: SendInput abgelehnt")
        return False, f"Klick auf {name} wurde von Windows abgelehnt"
    trail.append(f"{name} geklickt @{x},{y} (UIA)")
    return True, ""


# ---------------------------------------------------------------------------
# SCHRITT 2b (21.09.2026 nachts) — fremder Tradovate-Login: abmelden, Connect,
# Tradovate-Fenster, Autofill, Login. Finn: "ich lass dich mal zaubern, dann
# teste ich." Sein Handweg: "auf Login druecken, dann einmal auf ein Feld, dann
# sehe ich die Autofill-Vorschlaege, und daneben druecke ich auf Login."
#
# Alles ueber Windows-UIA (das Auge, das sich am selben Abend live bewaehrt
# hat) — das Tradovate-Fenster ist ohnehin eine eigene Seite, auf der das
# Userscript nicht laeuft. Gefunden wird ueber sichtbare NAMEN, deutsch und
# englisch, und immer nur bei GENAU EINEM Treffer.
#
# WAS BEWIESEN IST (am 21.09. am echten TradingView/Tradovate nachgesehen):
#   - Broker-Dialog: Kachel "Tradovate" -> Dialog mit Live/Demo (Radio) und
#     Knopf "Connect" (aria-label "Connect broker"); KEINE Username-Felder.
#   - Tradovate-Seite: zwei Eingabefelder (#name-input, #password-input) und
#     ein Knopf "Login"; daneben "Sign in with Google/Apple" — deshalb matcht
#     der Login-Knopf nur EXAKT.
# WAS GERATEN IST und sich im ersten Lauf beweisen muss: wo "Abmelden" sitzt
# (Annahme: Menue am Broker-Knopf "Tradovate" im unteren Panel), und wie
# Chromes Autofill-Liste in UIA heisst. Jede Stelle bricht bei 0 oder >=2
# Treffern ab und legt ein Inventar der sichtbaren Namen in die Diagnose.
#
# DAS PASSWORT fasst der Bot nie an: er waehlt den Autofill-Vorschlag bzw.
# tippt nur den USERNAMEN; vom Passwortfeld wird einzig geprueft, DASS es
# gefuellt ist (Laenge > 0) — der Wert wird weder gelesen noch geloggt.
# Vor dem Login-Klick muessen Username UND gefuelltes Passwort bewiesen sein:
# kein Fehlversuch bei Tradovate (Sperre/Captcha nach wiederholten Logins).
# ---------------------------------------------------------------------------

# 'Tradovate', aber auch 'Tradovate 4.4' (Kachel mit Bewertung im Namen) — der
# erste PC-Lauf von 2b fand mit dem exakten Muster NULL Treffer.
TV_RX_BROKER = re.compile(r"^tradovate\b", re.I)
# Finns Handweg (Screenshots 21.09.2026): Broker-Knopf -> "Connect another
# broker…" -> Kachel Tradovate. Das Menue hat genau drei Punkte: "Trading
# settings…", "Connect another broker…", "Log out".
TV_RX_ANDERER_BROKER = re.compile(r"^(connect another broker|change broker|"
                                  r"(einen )?anderen broker verbinden|broker wechseln)", re.I)
# Sieht aus wie ein Kontoname: ein Wort aus Grossbuchstaben/Ziffern mit
# mindestens 6 Ziffern, optional gefolgt von der Waehrung.
TV_RX_KONTOARTIG = re.compile(r"^(?=[A-Z0-9_-]*\d{6})[A-Z][A-Z0-9_-]{7,}(\s+[A-Z]{3})?$")
TV_RX_SPUR = re.compile(r"trad|broker|log ?out|abmeld|connect|verbind|demo|log ?in|anmeld", re.I)
TV_RX_KACHELSICHT = re.compile(r"^(paper trading|brokerage simulator)", re.I)
TV_RX_LOGOUT = re.compile(r"^(log ?out|sign ?out|abmelden|ausloggen|disconnect|"
                          r"(verbindung )?trennen)\b", re.I)
TV_RX_TRADE = re.compile(r"^(trade|handeln|traden)$", re.I)
TV_RX_DEMO = re.compile(r"^demo$", re.I)
TV_RX_CONNECT = re.compile(r"^(connect( broker)?|(broker )?verbinden)$", re.I)
TV_RX_LOGIN = re.compile(r"^(log ?in|sign ?in|anmelden|einloggen)$", re.I)

# Kappung 12000 je Typ (war 2500): TradingView haengt Dialoge und Menues ans
# ENDE des Baums, und eine Chart-Seite mit Watchlist, News und Seitenleiste hat
# mehrere tausend Textknoten — mit 2500 lag die Broker-Auswahl vermutlich
# hinter der Kappung (die Kontonummern-Suche mit 6000 fand ihre Liste).
_TV_UIA_KLICKBAR = ("Button", "MenuItem", "ListItem", "RadioButton", "Hyperlink",
                    "TabItem", "CheckBox", "ComboBox", "Text")


def tv_uia_namen_filtern(roh, muster, fenster=None, y_von=0.0, y_bis=1.0, ohne=None,
                         typ_vorrang=("Text", "Button", "MenuItem", "ListItem", "RadioButton")):
    """(name, (l,t,r,b), typ)-Tripel -> sichtbare Elemente, deren NAME auf das
    Muster passt; innerste zuerst gefiltert (Knopf + sein Text tragen denselben
    Namen -> ein Element). y_von/y_bis: Anteil der Fensterhoehe, in dem die
    Mitte liegen muss (0 = oben, 1 = unten)."""
    kand = []
    for eintrag in roh or ():
        try:
            name, r = eintrag[0], eintrag[1]
            typ = eintrag[2] if len(eintrag) > 2 else ""
            l, t, rr, b = (int(v) for v in r)
        except (TypeError, ValueError, IndexError):
            continue
        if rr - l < 3 or b - t < 3 or not muster.search(str(name or "").strip()):
            continue
        mx, my = (l + rr) // 2, (t + b) // 2
        if fenster:
            fl, ft, fr, fb = fenster
            if not (fl <= mx <= fr and ft <= my <= fb):
                continue
            h = max(1, fb - ft)
            if not (ft + h * y_von <= my <= ft + h * y_bis):
                continue
        if ohne and not (rr <= ohne[0] or l >= ohne[2] or b <= ohne[1] or t >= ohne[3]):
            continue
        kand.append({"text": str(name).strip()[:80], "typ": typ, "r": (l, t, rr, b), "punkt": (mx, my)})
    # Typ-Vorrang: traegt eine Kachel den Namen als Text UND als Bild-Alt
    # (Geschwister, nicht verschachtelt), waeren das zwei Treffer fuer EIN
    # Ding. Genommen wird nur der ranghoechste Typ, der ueberhaupt vorkommt.
    for typ in typ_vorrang or ():
        if any(k["typ"] == typ for k in kand):
            kand = [k for k in kand if k["typ"] == typ]
            break
    out = []
    for a in kand:
        ar = a["r"]
        huelle = any(b is not a and b["r"] != ar
                     and b["r"][0] >= ar[0] - 2 and b["r"][1] >= ar[1] - 2
                     and b["r"][2] <= ar[2] + 2 and b["r"][3] <= ar[3] + 2 for b in kand)
        if huelle or any(c["r"] == ar for c in out):
            continue
        out.append(a)
    return out


def tv_tasten_escape(text):
    """Text fuer pywinauto.send_keys entschaerfen: + ^ % ~ ( ) { } [ ] sind dort
    Steuerzeichen — ein Username 'max+apex' wuerde sonst als Shift-Kombination
    getippt."""
    return "".join("{" + c + "}" if c in "+^%~(){}[]" else c for c in str(text))


# DIREKT-ADRESSE ZUM BROKER-LOGIN (21.09.2026 nachts, Finns Frage: "gibt es
# irgendeinen anderen Weg … weil die Kachel immer woanders ist"). Am echten
# TradingView nachgesehen: diese Adresse laedt den Chart und oeffnet SOFORT den
# Tradovate-Dialog ([data-name="broker-login-dialog"], Live/Demo + Connect) —
# ohne Knopf "Trade", ohne Broker-Auswahl, ohne Kachel. Damit faellt die eine
# Stelle weg, deren Lage sich aendert (Favoriten, Reihenfolge, Fenstergroesse).
TV_TRADE_NOW = "?trade-now=TRADOVATE"

# "Don't remember me" im Connect-Dialog (am echten TradingView gesehen, 21.09.).
TV_RX_NICHT_MERKEN = re.compile(r"(don.?t|do not|nicht)\s+(remember|merken|speichern|erinnern)", re.I)
TV_NAMEN_NICHT_MERKEN = ("Don't remember me", "Don’t remember me", "Do not remember me",
                         "Nicht merken", "Nicht speichern")
TV_NAMEN_BROKER = ("Tradovate",)
TV_NAMEN_LOGOUT = ("Log out", "Logout", "Sign out", "Abmelden", "Ausloggen", "Disconnect", "Trennen")
TV_NAMEN_DEMO = ("Demo",)
TV_NAMEN_CONNECT = ("Connect broker", "Connect", "Broker verbinden", "Verbinden")
TV_NAMEN_LOGIN = ("Login", "Log in", "Sign in", "Anmelden", "Einloggen")

_UIA_TYPNAME = {50000: "Button", 50002: "CheckBox", 50003: "ComboBox", 50004: "Edit",
                50005: "Hyperlink", 50006: "Image", 50007: "ListItem", 50011: "MenuItem",
                50013: "RadioButton", 50019: "TabItem", 50020: "Text", 50026: "Group"}


def tv_trade_now_url(basis=""):
    """Chart-Adresse + trade-now. Die Basis kommt aus der Config (tv_url) und
    laeuft durch denselben Riegel wie beim Start: nur https + tradingview.com.
    Eine Layout-Adresse (/chart/AbC123/) bleibt erhalten, vorhandene Parameter
    fallen weg — trade-now soll der einzige sein."""
    u = tv_start_url(basis).split("?", 1)[0].split("#", 1)[0]
    if "/chart" not in u:
        u = TV_START_URL
    return u.rstrip("/") + "/" + TV_TRADE_NOW


def _tv_uia_nativ(w, namen):
    """GEZIELTE Suche: Windows selbst sucht im Baum nach Elementen mit genau
    diesen Namen (Gross/Klein egal) und liefert NUR die Treffer.
    -> [(name, rect, typ)] oder None, wenn der Weg auf diesem PC nicht geht.

    Warum (21.09.2026 nachts, Finns dritter 2b-Lauf: Menue war sichtbar offen,
    der Bot fand darin nichts): der bisherige Weg holte ALLE Elemente eines
    Typs und fragte jedes einzeln nach seinem Namen — auf einer TradingView-
    Seite mehrere tausend Aufrufe, viele Sekunden pro Durchgang. In ein
    4-Sekunden-Fenster passte genau EIN Durchgang, und der lief direkt nach dem
    Klick, bevor Chrome das neue Menue in den Baum gereicht hatte. Die gezielte
    Suche dauert Bruchteile einer Sekunde — sie kann oft genug wiederholt
    werden, bis das Menue da ist."""
    try:
        from pywinauto.uia_defines import IUIA
        u = IUIA()
        pid = u.UIA_dll.UIA_NamePropertyId
        bed = None
        for n in namen:
            # 3 = IgnoreCase + MatchSubstring: TradingView setzt um manche Namen
            # Leerraum ('Tradovate ' am Broker-Knopf — Finns Lauf 22.09.2026:
            # exakt 'Tradovate' fand NICHTS, der Bot hielt ein verbundenes
            # TradingView fuer unverbunden). Die genaue Pruefung macht danach
            # ohnehin das Muster in tv_uia_namen_filtern, auf dem gestrippten
            # Namen. Aeltere Windows kennen die Teilstring-Suche nicht -> stufen-
            # weise zurueck.
            c = None
            for flags in (3, 1):
                try:
                    c = u.iuia.CreatePropertyConditionEx(pid, n, flags)
                    break
                except Exception:
                    continue
            if c is None:
                c = u.iuia.CreatePropertyCondition(pid, n)
            bed = c if bed is None else u.iuia.CreateOrCondition(bed, c)
        feld = w.element_info.element.FindAll(u.tree_scope["descendants"], bed)
        roh = []
        for i in range(feld.Length):
            e = feld.GetElement(i)
            try:
                if e.CurrentIsOffscreen:
                    continue
                r = e.CurrentBoundingRectangle
                roh.append((str(e.CurrentName or "").strip(), (r.left, r.top, r.right, r.bottom),
                            _UIA_TYPNAME.get(e.CurrentControlType, str(e.CurrentControlType))))
            except Exception:
                continue
        return roh
    except Exception:
        return None


def _tv_adresse_oeffnen(w, url, trail):
    """Im TradingView-Tab eine Adresse oeffnen — per Tastatur (Strg+L, tippen,
    Enter), im BESTEHENDEN Tab: ein zweiter TradingView-Tab waere eine zweite
    Tradovate-Session und ein zweites Userscript. Getippt wird nur, wenn das
    TradingView-Fenster nachweislich im Vordergrund steht — Tastendruecke in
    ein fremdes Fenster sind der eine Fehler, den dieser Weg machen koennte.
    (ok, fehlertext)"""
    try:
        from pywinauto import keyboard
        import ctypes
    except ImportError:
        return False, "pywinauto fehlt"
    try:
        w.set_focus()
    except Exception:
        pass
    _warte(0.4, 0.3)
    try:
        vorn = ctypes.windll.user32.GetForegroundWindow()
        if int(vorn) != int(w.handle):
            return False, "TradingView-Fenster steht nicht im Vordergrund — Adresse wird nicht getippt."
    except Exception:
        pass                      # ohne die Probe (kein Windows) entscheidet set_focus
    try:
        keyboard.send_keys("^l")
        _warte(0.35, 0.3)
        keyboard.send_keys(tv_tasten_escape(url), with_spaces=True, pause=0.012)
        _warte(0.25, 0.2)
        # Chrome ergaenzt beim Tippen gern aus dem Verlauf (markierter Rest) —
        # Entf wirft die Ergaenzung weg, getippt bleibt genau die Adresse.
        keyboard.send_keys("{DELETE}")
        _warte(0.15, 0.15)
        keyboard.send_keys("{ENTER}")
    except Exception as e:
        return False, f"Adresse liess sich nicht tippen ({type(e).__name__})"
    trail.append("Adresse geoeffnet: …" + url[-28:])
    return True, ""


def tv_tab_schliessbar(titel, klasse, begriff=""):
    """Darf Strg+W in DIESES Fenster? Nur wenn der aktive Tab nachweislich
    TradingView ist — und nie, wenn er nach Prophos aussieht. Ein Strg+W in den
    Prophos-Tab naehme dem PC die Oberflaeche samt Reader-Bruecke weg."""
    if (klasse or "") not in BROWSER_KLASSEN or ist_prophos_fenster(titel, klasse):
        return False
    return ist_tradingview_fenster(titel, klasse) or tv_tab_rang(titel, begriff, "") > 0


TV_RX_VERLASSEN = re.compile(r"^(verlassen|leave|leave page|seite verlassen)$", re.I)


def tv_verlassen_knopf(roh):
    """Chromes Rueckfrage 'Website verlassen? — Deine Aenderungen werden eventuell
    nicht gespeichert' nach Strg+W (22.09.2026 02:05, Finns Screenshot: der Bot
    hatte den Tab richtig schnell geschlossen, blieb aber vor dem Dialog stehen;
    'kommt manchmal'). -> der Knopf 'Verlassen'/'Leave' als {text, r, punkt} oder
    None. NIE 'Abbrechen'. Rein rechnend."""
    for e in roh or ():
        n, r = str(e[0]).strip(), e[1]
        if r and TV_RX_VERLASSEN.match(n):
            return {"text": n, "r": tuple(r), "punkt": ((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)}
    return None


def _tv_tab_neu_mit_link(w, cfg, begriff, trail):
    """FINNS WEG (22.09.2026, von Hand geprueft): "das mit Log out ist dumm …
    der Tab wird geschlossen, dann oeffnet sich ein neuer Tab mit dem Link —
    dann kommt man JEDES MAL zu dem Connect." Im verbundenen Tab laedt die
    Direkt-Adresse die Seite nur neu; nach Schliessen + Neu-Oeffnen kommt der
    Tradovate-Dialog. Kein Menue, kein 'Log out', nichts zu suchen.
    Geoeffnet wird ueber denselben Chrome-Start wie in Schritt 1 (live
    bewiesen) — das deckt auch den Fall, dass der TradingView-Tab der einzige
    im Fenster war und Strg+W das ganze Fenster schliesst. (ok, fehlertext)"""
    try:
        from pywinauto import keyboard
        import subprocess
    except ImportError:
        return False, "pywinauto fehlt"
    try:
        w.set_focus()
    except Exception:
        pass
    _warte(0.15, 0.1)
    try:
        titel, klasse = w.window_text() or "", w.element_info.class_name
    except Exception:
        return False, "TradingView-Fenster nicht mehr lesbar."
    if not tv_tab_schliessbar(titel, klasse, begriff):
        return False, (f"Der aktive Tab sieht nicht nach TradingView aus ('{titel[:50]}') — "
                       "es wird nichts geschlossen.")
    # Vordergrund BEWEISEN, mit Nachdruck (22.09.2026 02:2x, Finns Lauf nach dem
    # Leerzeit-Fix: 'TradingView-Fenster steht nicht im Vordergrund' — der Fokus-
    # Wechsel von set_focus() war noch nicht durch). ZWEITER LAUF 02:4x: auch mit
    # Nachdruck 'nicht im Vordergrund', obwohl Finn TradingView vorne SAH. Deshalb
    # zaehlt jetzt der TITEL des Vordergrund-Fensters, nicht sein Handle: steht vorne
    # ein Fenster, dessen Titel nach dem TradingView-Tab aussieht, ist es das richtige
    # (Chrome kann fuer dasselbe Fenster ein anderes Handle liefern als pywinautos
    # Fund). Strg+W geht ohnehin an das Vordergrund-Fenster. Absage nennt, was vorne
    # stand.
    try:
        import ctypes
        u32 = ctypes.windll.user32

        def vorne():
            h = u32.GetForegroundWindow()
            n = u32.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(h, buf, n + 1)
            kb = ctypes.create_unicode_buffer(128)
            u32.GetClassNameW(h, kb, 128)
            return int(h), buf.value or "", kb.value or ""
        ende_v = time.time() + 2.5
        while True:
            h_v, t_v, k_v = vorne()
            if h_v == int(w.handle) or tv_tab_schliessbar(t_v, k_v, begriff):
                break
            if time.time() >= ende_v:
                return False, (f"TradingView-Fenster steht nicht im Vordergrund (vorn: '{t_v[:60] or '?'}') — "
                               "es wird nichts geschlossen.")
            try:
                w.set_focus()
            except Exception:
                pass
            try:
                u32.SetForegroundWindow(int(w.handle))
            except Exception:
                pass
            _warte(0.25, 0.15)
    except Exception:
        pass                      # ohne die Probe (kein Windows) entscheidet set_focus
    chrome = _chrome_pfad((cfg or {}).get("tv_browser_path"))
    if not chrome:
        return False, "chrome.exe nicht gefunden (tv_browser_path in der config.json setzen) — Tab bleibt offen."
    try:
        keyboard.send_keys("^w")
    except Exception as e:
        return False, f"Tab liess sich nicht schliessen ({type(e).__name__})"
    trail.append("TradingView-Tab geschlossen")
    # Chromes Rueckfrage 'Website verlassen?' (kommt nur manchmal): bis ~2,5 s nach
    # dem Knopf 'Verlassen' schauen und ihn klicken — sonst bliebe der alte Tab
    # offen und der neue kaeme daneben.
    ende_v = time.time() + 2.5
    while time.time() < ende_v:
        _warte(0.25, 0.15)
        try:
            k = tv_verlassen_knopf(_tv_uia_roh(w, ("Button",)))
        except Exception:
            k = None
        if k:
            _tv_uia_klick(k, f"'{k['text']}' (Website verlassen?)", trail)
            _warte(0.4, 0.2)
            break
    _warte(0.3, 0.2)
    befehl = tv_start_befehl(chrome, tv_trade_now_url((cfg or {}).get("tv_url")),
                             (cfg or {}).get("tv_chrome_profil"))
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        subprocess.Popen(befehl, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    except OSError as e:
        return False, f"Chrome-Start fehlgeschlagen: {e}"
    trail.append("TradingView neu mit Direkt-Adresse geoeffnet")
    return True, ""


def tv_uia_spur(roh, max_n=12):
    """Was stand an einschlaegigen Namen da? Kommt direkt in die FEHLERMELDUNG:
    Finn schickt Screenshots und den Meldungstext, nicht die Diagnose — also
    muss der Text selbst den Beweis tragen."""
    out = []
    for name, _r, typ in roh or ():
        if TV_RX_SPUR.search(name) and len(name) <= 40:
            k = f"{typ}:{name}"
            if k not in out:
                out.append(k)
        if len(out) >= max_n:
            break
    return " | ".join(out) or "nichts Einschlaegiges"


def _tv_uia_roh(w, typen=_TV_UIA_KLICKBAR, max_je_typ=12000, muster=()):
    """Benannte Elemente der genannten Typen: [(name, rect|None, typ)].
    'muster' (Regex-Tupel) ist der Vorfilter: Sichtbarkeit und Rechteck kosten
    je Element zwei weitere COM-Aufrufe, und eine TradingView-Seite hat ein
    paar tausend Textknoten — abgefragt werden sie deshalb nur fuer Namen, die
    auf eines der Muster passen. Alle anderen kommen mit rect=None zurueck
    (reichen fuers Diagnose-Inventar, fallen in den Filtern von selbst raus)."""
    sammel = _tv_uia_sammel(w, typen)
    if sammel is not None:
        # Gleiche Rueckgabe wie der Einzel-Scan: was auf kein Muster passt,
        # traegt rect=None (reicht fuers Inventar, faellt in den Filtern raus).
        return [(n, (r if (not muster or any(m.search(n) for m in muster)) else None), typ)
                for n, r, typ in sammel if len(n) <= 120]
    roh = []
    for typ in typen:
        try:
            els = w.descendants(control_type=typ)
        except Exception:
            continue
        for e in els[:max_je_typ]:
            try:
                n = (e.window_text() or "").strip()
                if not n or len(n) > 120:
                    continue
                if muster and not any(m.search(n) for m in muster):
                    roh.append((n, None, typ))
                    continue
                if hasattr(e, "is_visible") and not e.is_visible():
                    continue
                r = e.rectangle()
                roh.append((n, (r.left, r.top, r.right, r.bottom), typ))
            except Exception:
                continue
    return roh


def _tv_fenster_rect(w):
    try:
        r = w.rectangle()
        return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None


def tv_uia_inventar(roh, max_n=90):
    """Kurzliste fuer die Diagnose: was war an benannten Bedienelementen zu
    sehen? (Texte nur kurze — lange sind News/Beschreibungen.)"""
    out, gesehen = [], set()
    for name, r, typ in roh or ():
        if typ == "Text" and len(name) > 28:
            continue
        k = (name[:40], typ)
        if k in gesehen:
            continue
        gesehen.add(k)
        out.append(f"{typ}:{name[:40]}" + (f"@{r[0]},{r[1]}" if r else ""))
        if len(out) >= max_n:
            break
    return out


TV_RX_LOGIN_LABELS = re.compile(r"^(benutzername|kennwort|passwort|anmelden|username|password|log ?in|sign ?in|"
                                r"don'?t remember me|remember me|angemeldet bleiben|forgot|vergessen|tradovate|"
                                r"connect|demo|live|schliessen|close|cancel|abbrechen|ok)\b", re.I)


def tv_seite_texte(roh, max_n=6):
    """Was steht auf der Seite? (23.09.2026, Moritz-PC: 'Login geklickt, aber das
    Tradovate-Fenster ist noch offen — steht dort eine Fehlermeldung?' — die Frage
    beantwortet der Bot jetzt selbst.) Kurze, lesbare Saetze ohne die bekannten
    Feld-/Knopf-Beschriftungen; Fehler- und Rueckfragetexte kommen so in die Meldung."""
    out, gesehen = [], set()
    for name, r, typ in roh or ():
        t = " ".join(str(name or "").split())
        if not (8 <= len(t) <= 160) or not re.search(r"[A-Za-zÄÖÜäöü]{3}", t):
            continue
        if TV_RX_LOGIN_LABELS.search(t) and len(t) <= 24:
            continue
        k = t.lower()
        if k in gesehen:
            continue
        gesehen.add(k)
        out.append(t)
        if len(out) >= max_n:
            break
    return " | ".join(f"'{x}'" for x in out)


def tv_version_min(version, minimum):
    """'0.4.2' >= '0.4.2'? Unlesbare Version = False (dann lieber zum Update raten)."""
    def teile(v):
        try:
            return tuple(int(x) for x in str(v).strip().split("."))
        except ValueError:
            return None
    a, b = teile(version), teile(minimum)
    return bool(a and b and a >= b)


TV_USERSCRIPT_MIN = "0.4.2"


def tv_konto_zustand(bf, ext_id, geschwister=()):
    """Was sagt das Bedienfeld ueber das Konto? -> (zustand, aktiv_text)
       'richtig'        das angezeigte Konto IST das Zielkonto
       'gleicher_login' ein anderes Konto — aber eines, das laut Prophos zur
                        selben Firma gehoert: also derselbe Tradovate-Login,
                        ein Griff ins Dropdown genuegt
       'falsch'         ein Konto, das Prophos bei dieser Firma nicht kennt —
                        vermutlich ein anderer Tradovate-Login
       'kein_broker'    kein Konto-Umschalter gefunden — kein Broker verbunden
                        oder das Broker-Panel unten ist zugeklappt

    Finn 21.09.2026: im Dropdown steht nie der Tradovate-Username, nur der
    Kontoname (= External ID). Ob der Login stimmt, laesst sich deshalb nur
    ueber die Datenbank beweisen: "der AE-Account gehoert in der Datenbank ja
    trotzdem zu Apex" — steht AE da und AC ist gewollt, ist es der richtige
    Login und nur das falsche Unterkonto."""
    konto = (bf or {}).get("konto") or {}
    aktiv = str(konto.get("aktiv") or "").strip()
    ids = [ext_id] + list(geschwister or ())
    if not tv_konto_bestes(aktiv, ids):
        # Der Anker des Userscripts hat nichts (oder nichts Bekanntes)
        # geliefert — dann entscheidet der Text im Panel. Genau EIN Element
        # darf es sein: bei offener Aufklappliste stehen mehrere Konten da,
        # und welches davon aktiv ist, sagt der Text allein nicht.
        per_text = tv_konto_per_text(bf, ids)
        if len(per_text) == 1:
            aktiv = per_text[0]["text"]
    if not aktiv and not konto.get("schalter"):
        return "kein_broker", ""
    bestes = tv_konto_bestes(aktiv, ids)
    if bestes and _nur_alnum(bestes) == _nur_alnum(ext_id):
        return "richtig", aktiv
    if bestes:
        return "gleicher_login", aktiv
    return "falsch", aktiv


def tv_konto_eintrag(eintraege, ext_id, geschwister=()):
    """Der EINE Dropdown-Eintrag des Zielkontos — oder None. Gleiche
    Laengste-ID-Regel wie oben; bei 0 oder >=2 Treffern None (nie einer von
    mehreren Kandidaten). -> (eintrag, anzahl_treffer)"""
    ids = [ext_id] + list(geschwister or ())
    ziel = _nur_alnum(ext_id)
    treffer = [e for e in (eintraege or [])
               if isinstance(e, dict) and e.get("rect") and not e.get("fehlt")
               and _nur_alnum(tv_konto_bestes(e.get("text"), ids)) == ziel]
    return (treffer[0] if len(treffer) == 1 else None), len(treffer)


def tv_diagnose(bf):
    """Kompakte Unterlagen fuer die Ferndiagnose: was das Userscript im UNTEREN
    Fensterbereich (Broker-Panel) sieht. Geht mit der Antwort nach Prophos und
    laesst sich dort per Knopf kopieren — Finn musste am 21.09.2026 fuer die
    erste Diagnose eine Datei von einem Remote-PC holen, und hat stattdessen
    (verstaendlich) Screenshots geschickt."""
    bf = bf or {}
    geo = bf.get("geo") or {}
    try:
        hoehe = float(geo.get("innerHeight") or 0)
    except (TypeError, ValueError):
        hoehe = 0.0
    unten, gesehen = [], set()
    for quelle in ("panel", "dump"):
        for e in (bf.get(quelle) or []):
            r = _tv_rect4(e) if isinstance(e, dict) else None
            if not r or (hoehe and r[1] < hoehe * 0.45):
                continue
            k = (tuple(r), str(e.get("text") or "")[:20])
            if k in gesehen or len(unten) >= 110:
                continue
            gesehen.add(k)
            unten.append({f: e.get(f) for f in ("tag", "id", "dn", "al", "rolle", "text", "rect")
                          if e.get(f) not in (None, "")})
    return {"version": bf.get("version"), "titel": str(bf.get("titel") or "")[:60],
            "geo": {f: geo.get(f) for f in ("innerWidth", "innerHeight", "dpr")},
            "sprache_fremd": bf.get("sprache_fremd"), "konto": bf.get("konto"),
            "panel_n": len(bf.get("panel") or []), "dump_n": len(bf.get("dump") or []),
            # Text-Treffer des Userscripts 0.4.2+ (None = altes Userscript bzw.
            # nichts gesucht, [] = gesucht und nichts gefunden)
            "treffer": bf.get("treffer"),
            "unten": unten}


def _tv_dump_sichern(trail):
    """Kandidaten-Dump anfordern und neben dem Bot ablegen. -> (pfad, diagnose)"""
    _tv_http("/dump-an", {})
    ende = time.time() + 8.0
    letzt = None
    while time.time() < ende:
        bf = _tv_http("/bedienfeld") or {}
        if bf.get("ok"):
            letzt = bf
        if bf.get("ok") and bf.get("dump"):
            pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), TV_KONTO_DUMP)
            try:
                with open(pfad, "w", encoding="utf-8") as f:
                    json.dump({"zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
                               "titel": bf.get("titel"), "version": bf.get("version"),
                               "konto": bf.get("konto"), "panel": bf.get("panel"),
                               "dump": bf.get("dump")}, f, ensure_ascii=False, indent=1)
                trail.append("Dump gesichert")
                return pfad, tv_diagnose(bf)
            except OSError as e:
                trail.append(f"Dump nicht schreibbar ({e})")
                return "", tv_diagnose(bf)
        time.sleep(0.3)
    trail.append("kein Dump vom Userscript bekommen")
    return "", tv_diagnose(letzt)


TV_RX_TRADOVATE_TITEL = re.compile(r"tradovate|login to your account|anmeldung bei|sign in to your account", re.I)


def _tv_browser_fenster():
    """Alle Browser-Hauptfenster: [(handle, titel, wrapper)]"""
    from pywinauto import Desktop
    out = []
    for w in Desktop(backend="uia").windows():
        try:
            klasse = w.element_info.class_name or ""
            if klasse in BROWSER_KLASSEN or klasse.startswith("Chrome_WidgetWin"):
                out.append((w.handle, w.window_text() or "", w))
        except Exception:
            continue
    return out


def _tv_edit_wert(e):
    try:
        return str(e.iface_value.CurrentValue or "")
    except Exception:
        try:
            return str(e.get_value() or "")
        except Exception:
            return ""


def _tv_ist_passwortfeld(e):
    try:
        return bool(e.element_info.element.CurrentIsPassword)
    except Exception:
        return False


def tv_feld_darueber(felder, anker, anker_r, toleranz=40, max_abstand=260):
    """Aus Eingabefeldern das waehlen, das DIREKT UEBER dem Anker liegt: linke
    Kante gleich (± toleranz), Oberkante darueber, naechstes zuerst; weiter als
    max_abstand entfernt zaehlt nicht (Adressleiste, Suchfelder). -> Feld|None"""
    bestes, bester_abstand = None, None
    for e in felder or ():
        if e is anker:
            continue
        try:
            r = e.rectangle()
        except Exception:
            continue
        abstand = anker_r[1] - r.top
        if abs(r.left - anker_r[0]) > toleranz or abstand <= 0 or abstand > max_abstand:
            continue
        if bester_abstand is None or abstand < bester_abstand:
            bestes, bester_abstand = e, abstand
    return bestes


def _tv_autofill_vorschlag(username, ohne=None, anmelde_handle=None):
    """Chromes Autofill-Liste haengt als eigenes Popup-Fenster am Browser. Gesucht
    wird in allen Chrome-Fenstern AUSSER dem TradingView-Fenster ('ausser' =
    Handles) nach einem Nicht-Eingabe-Element, das den Username als GANZES WORT
    traegt. -> Liste (innerste), meist 0 oder 1.

    Ganzes Wort + TradingView ausgenommen, weil (Fund in der Simulation,
    21.09.2026 nachts, bevor es live passieren konnte): der Username
    'APEX_641699' steckt als Teilstring in der Kontonummer
    'PAAPEX6416990000008' — mit Teilstring-Suche haette der Bot statt des
    Vorschlags das Konto-Feld in TradingView angeklickt."""
    if len(_nur_alnum(username)) < 3:
        return []

    class _Nadel:                       # Vorfilter mit derselben Schnittstelle wie ein Regex
        @staticmethod
        def search(name):
            return tv_konto_wort_passt(name, username)
    # Die Anmeldung kann ein Tab im TradingView-FENSTER sein (Finns PC) — kein
    # Fenster wird deshalb ausgenommen; vor der Kontonummer schuetzt der
    # Ganzwort-Vergleich. Ausgenommen ist nur das Username-Feld selbst ('ohne'):
    # steht der Name schon drin, truege dessen Text denselben Namen.
    # Nur dort suchen, wo die Liste sein KANN: im Anmelde-Fenster selbst und in
    # kleinen Chrome-Popups (die Liste ist ein eigenes kleines Fenster). Das
    # grosse Prophos-Fenster u.a. abzusuchen kostete nur Zeit (22.09.2026).
    fenster = []
    for h, t, fw in _tv_browser_fenster():
        fr = _tv_fenster_rect(fw)
        klein = bool(fr) and (fr[2] - fr[0]) <= 900 and (fr[3] - fr[1]) <= 700
        if h == anmelde_handle or klein or anmelde_handle is None:
            fenster.append((h, t, fw))
    roh = []
    if _UIA_SAMMEL["geht"] is not True:             # 1) gezielt: Name == Username — nur solange
        for _h, _t, w in fenster:                   #    die Sammelabfrage (22.09.2026) nicht laeuft;
            roh += _tv_uia_nativ(w, (str(username).strip(),)) or []   # mit ihr ist Schritt 2 ohnehin ein Aufruf je Fenster
    roh = [x for x in roh if x[2] != "Edit"]
    if not roh:                                     # 2) Scan: Username als ganzes Wort im Namen
        for _h, _t, w in fenster:
            roh += [x for x in _tv_uia_roh(w, ("ListItem", "MenuItem", "Button", "DataItem", "Text"),
                                            600, muster=(_Nadel,)) if x[1]]
    return tv_uia_namen_filtern(roh, _Nadel, typ_vorrang=None, ohne=ohne)


TV_RX_KONTO_ARTIG = re.compile(r"^[A-Z]{2,}[A-Z0-9_-]*\d{5,}(\s+(USD|EUR))?$", re.I)


def tv_fremdes_konto(aehnlich, ids):
    """Steht im Panel ein Konto, das WIE eine Prop-Kontonummer aussieht (Buchstaben +
    mind. 5 Ziffern, optional ' USD'), aber zu KEINER erwarteten ID gehoert?
    -> dieser Text oder ''. Reine Ziffern (Positions-/Order-IDs) zaehlen nie.
    (22.09.2026, Finns Leerzeit-Fund: 'der erste Tab ist offen, es ist nicht der
    richtige Account drin — bis der geschlossen wird, sind es 10-15 Sekunden'. Die
    Leseschleife kannte nur ein POSITIVES Ende und lief bei einem fremden Konto
    die vollen 14 s.)"""
    soll = {_nur_alnum(i) for i in ids or () if i}
    for n in aehnlich or ():
        t = str(n).strip()
        if not TV_RX_KONTO_ARTIG.match(t):
            continue
        wort = _nur_alnum(t.split()[0])
        if wort in soll or any(w and (w in wort or wort in w) for w in soll):
            continue
        return t
    return ""


def modus_tvkonto(cmd):
    res = {"ok": False, "msg": "", "trail": "", "schritt": "start",
           "zustand": "", "konto_aktiv": "", "dump": "", "diagnose": None}
    trail = _StempelSpur()      # jeder Eintrag traegt seine Sekunde seit Lauf-Start
    fenster = [None]
    maximiert = [False]         # Panel per Knopf nach oben geholt -> am Ende wieder nach unten
    max_versucht = [False]      # einmal pro Tab probieren
    lies_diag = {"w": None, "els": None}   # was die letzte Leserunde sah (fuer die Spur)
    max_fehl = [""]             # Maximieren gescheitert -> Lauf abbrechen

    def raus(msg, schritt):
        # Panel IMMER wieder nach unten — auch bei Absage: maximiert verdeckt es den
        # Chart, und der Asset-Schritt faende Watchlist und Order-Panel nicht.
        if maximiert[0]:
            maximiert[0] = False
            try:
                if fenster[0]:
                    _tv_panel_umschalten(fenster[0], trail, "unten")
            except Exception:
                pass
        res["msg"], res["schritt"], res["trail"] = msg, schritt, " > ".join(trail)
        # Text-Suche wieder aus: sie laeuft durchs ganze DOM und soll nie im
        # Dauerbetrieb mitlaufen (der Server schaltet nach 90 s ohnehin ab).
        _tv_http("/suche", {"texte": []}, timeout=1.5)
        print(json.dumps(res))
        return "fertig"       # fuer die inneren Ablaeufe: 'es ist alles gesagt, nichts mehr tun'

    fehler = pruefe_tv_konto_befehl(cmd)
    if fehler:
        return raus("Befehl unvollstaendig: " + " / ".join(fehler), "befehl")
    try:
        from pywinauto import Desktop  # noqa: F401  (nur Verfuegbarkeits-Probe)
    except ImportError:
        return raus("pywinauto fehlt (nur auf dem PC lauffaehig).", "start")
    _dpi_bewusst()
    _warte(0.1, 0.4)   # Start-Versatz (Jitter-Dauerregel 28.08.2026)

    # --- Schritt 1: TradingView offen? sonst starten ----------------------
    start = time.time()
    # Ist TradingView noch gar nicht offen, startet es gleich MIT der Direkt-
    # Adresse: der Connect-Dialog steht dann sofort da, und es wird immer der
    # Login der Firma angemeldet — kein Raten, welcher Login sich von selbst
    # wiederverbunden haette, kein Schliessen und Neu-Oeffnen hinterher. Nur
    # mit hinterlegtem Username; ohne ihn bleibt es beim normalen Start.
    username0 = str(cmd.get("tv_username") or "").strip()
    ok, msg, gestartet = tv_sicherstellen(
        trail, cmd, warten_s=45.0,
        start_url=tv_trade_now_url(cmd.get("tv_url")) if username0 else None)
    frisch_mit_link = bool(gestartet and username0)
    if not ok:
        return raus(msg, "tradingview")

    # --- Schritt 2: welches Konto steht im Broker-Panel? ------------------
    # ZWEI AUGEN, gleichberechtigt (21.09.2026 abends, Finn: 'ohne Tampermonkey
    # bekommen wir das doch auch hin'):
    #   a) das Bedienfeld des Userscripts (wenn es laeuft),
    #   b) Chromes Accessibility-Baum ueber Windows-UIA — braucht nichts ausser
    #      dem offenen Fenster, sieht auch die Aufklappliste, liefert echte
    #      Bildschirm-Pixel.
    # Jede Aussage reicht, wenn sie eindeutig ist. Ein Stand von VOR diesem
    # Lauf zaehlt nie (er koennte aus einem geschlossenen Tab stammen).
    ext = str(cmd["ext_id"]).strip()
    geschwister = [str(x).strip() for x in (cmd.get("geschwister") or [])
                   if len(_nur_alnum(x)) >= 3][:60]
    ids = [ext] + geschwister
    _tv_http("/suche", {"texte": ids}, timeout=1.5)   # nur fuer Userscript 0.4.2+, sonst wirkungslos

    uia_info = {}

    fenster_gesehen = [""]

    def tv_fenster(versuche=1):
        """Das TradingView-Fenster. Ein Fehlversuch wird NIE gemerkt
        (22.09.2026, Finns Lauf: 'TradingView-Fenster nicht gefunden', obwohl
        der Bot es Sekunden vorher selbst geoeffnet hatte — der erste Blick
        fiel in die Ladephase, das NEIN galt danach fuer den ganzen Lauf)."""
        runde = 0
        while fenster[0] is None and runde < versuche:
            runde += 1
            bf_t = _tv_http("/bedienfeld", timeout=1.5) or {}
            spur_f = []
            w_, _f = _tv_fenster_holen(spur_f, tv_tab_suchbegriff(bf_t.get("titel")) if bf_t.get("ok") else "", "")
            if w_:
                fenster[0] = w_
            else:
                fenster_gesehen[0] = (spur_f[-1] if spur_f else "")[:300]
                if runde < versuche:
                    _warte(0.25, 0.15)
        return fenster[0]

    # Bedienfeld-Wartezeit: beim ersten Blick 2,5 s, danach nur noch kurz — meldet
    # sich kein Userscript (bei Finn seit 22.09.2026 der Normalfall: Reader aus),
    # verbrannte sonst JEDE Leserunde 2,5 s nur mit Warten auf etwas, das nie kommt.
    bf_to = [0.6]     # 2,5 -> 0,6 s (22.09.2026 18:3x, Finn: 'so viele Leerzeiten, jeder Step 10 s' — das Userscript sendet nie)

    def lies():
        """-> (zustand, aktiv_text, bf, uia_element|None)"""
        b = _tv_bf(nach=start, timeout=bf_to[0])
        if not b:
            bf_to[0] = 0.3
        z, a = tv_konto_zustand(b, ext, geschwister) if b else ("kein_broker", "")
        if z in ("richtig", "gleicher_login"):
            return z, a, b, None
        w = tv_fenster()
        lies_diag["w"] = bool(w)
        if w:
            els = _tv_uia_konten(w, ids, uia_info)
            lies_diag["els"] = [(x["text"][:30], x["r"]) for x in els[:3]]
            # NUR MAXIMIEREN, WENN NOETIG (22.09.2026 18:2x, Finn, Screenshot: Dropdown schon
            # sichtbar, Konto lesbar — der Bot klickte trotzdem in die Panel-Zeile, traf ueber
            # dem 'i' den 'Collapse'-Knopf, klappte das Panel EIN und konnte danach nichts mehr
            # lesen). Regel: ist ein Konto (bekannt oder kontoartig) zu lesen, bleibt das Panel
            # unangetastet; erst wenn NICHTS zu lesen ist, wird es nach oben geholt (hartnaeckig,
            # s. _tv_panel_umschalten) und neu gelesen — einmal pro Tab, am Ende wieder runter.
            if not els and not tv_fremdes_konto(uia_info.get("aehnlich"), ids) and not max_versucht[0]:
                max_versucht[0] = True
                try:
                    if _tv_panel_umschalten(w, trail, "oben"):
                        maximiert[0] = True
                        _warte(0.6, 0.3)
                        return lies()
                    trail.append("Panel liess sich nicht maximieren — weiter mit dem, was zu lesen ist")
                except Exception as e_:
                    trail.append(f"Panel maximieren abgebrochen: {type(e_).__name__}")
            if len(els) == 1:          # zwei sichtbare Konten = offene Liste = kein Urteil
                e = els[0]
                z2 = "richtig" if _nur_alnum(e["id"]) == _nur_alnum(ext) else "gleicher_login"
                return z2, e["text"], b, e
        return z, a, b, None

    # AUCH BEI LINK-START ZUERST LESEN (22.09.2026 14:1x, dritter PC, Spur 12:10: mit dem
    # Login-Link gestartet, Sitzung verband sich selbst mit dem RICHTIGEN Login — der Bot
    # las nicht, wartete 43 s auf den Connect-Dialog, schloss den Tab und fing von vorn an).
    # Steht nach dem Start ein bekanntes Konto im Panel, geht es direkt zum Dropdown; erst
    # wenn in 15 s nichts zu lesen ist, kommt der Dialog-Weg.
    ende = time.time() + (40.0 if (gestartet and not frisch_mit_link) else 15.0 if frisch_mit_link else 14.0)
    zustand, aktiv, bf, uia_el = "kein_broker", "", None, None
    fremd_vor = ""
    t_schleife, scan_vor, ruhig_seit = time.time(), None, None
    while True:
        zustand, aktiv, bf, uia_el = lies()
        if zustand in ("richtig", "gleicher_login") or time.time() >= ende or max_fehl[0]:
            break
        # GAR KEINE ID (22.09.2026 18:5x, Finn: 'falsche ID / gar keine ID — noch schneller?';
        # Spur 18:39: Panel nicht da, Scan 124 Elemente, die Schleife lief trotzdem 14 s):
        # ist die Seite RUHIG (zwei Blicke mit gleicher Elementzahl) und weder Konto noch
        # kontoartiger Text zu sehen, ist das 'kein Broker' — sofort Tab zu + Link.
        n_scan = uia_info.get("gescannt")
        if n_scan is not None and scan_vor is not None and abs(n_scan - scan_vor) <= 5:
            ruhig_seit = ruhig_seit or time.time()
        else:
            ruhig_seit = None
        scan_vor = n_scan
        if (ruhig_seit and time.time() - t_schleife >= 2.5 and not (gestartet and time.time() - start < 6.0)
                and not tv_fremdes_konto(uia_info.get("aehnlich"), ids)):
            trail.append(f"Seite ruhig ({n_scan} Elemente), kein Konto zu sehen -> kein Broker")
            break
        # NEGATIVES ENDE: zweimal hintereinander dasselbe FREMDE Konto im Panel (UIA)
        # -> 'falsch', sofort weiter zum Login-Wechsel statt 14 s auf ein richtiges
        # zu warten, das nie kommt. Zweimal, weil ein einzelner Blick in die
        # Ladephase fallen kann (Regel seit .327: nie aus EINEM Blick urteilen).
        fremd = tv_fremdes_konto(uia_info.get("aehnlich"), ids) if not (gestartet and time.time() - start < 6.0) else ""
        # EIN Blick reicht, wenn TradingView schon stand (22.09.2026 18:4x, Spur: 8,4 s bis
        # 'falsch' fuer zwei Leserunden); zwei Blicke nur nach frischem Start (Ladephase).
        if fremd and (fremd == fremd_vor or not gestartet):
            zustand, aktiv = "falsch", fremd
            break
        fremd_vor = fremd
        _warte(0.2, 0.15)
    if max_fehl[0]:
        return raus(max_fehl[0], "panel")
    res["zustand"], res["konto_aktiv"] = zustand, aktiv[:80]
    trail.append(f"Konto im Panel: '{aktiv[:40] or '-'}' -> {zustand}"
                 + (" (UIA)" if uia_el else "")
                 + (f" [Fenster {'ja' if lies_diag['w'] else 'NEIN: ' + fenster_gesehen[0][:120]}"
                    f" · Treffer {lies_diag['els']} · kontoartig {(uia_info.get('aehnlich') or [])[:4]}"
                    f" · Scan {uia_info.get('weg')}/{uia_info.get('gescannt')}]" if zustand not in ("richtig", "gleicher_login") else ""))

    def diagnose():
        pfad, d = _tv_dump_sichern(trail) if bf else ("", tv_diagnose(None))
        d["uia"] = uia_info
        res["dump"], res["diagnose"] = pfad, d

    if zustand == "richtig":
        res["ok"] = True
        return raus(f"Richtiges Konto ist aktiv ({aktiv[:60]}).", "konto")

    ziel = (f"Login '{cmd.get('tv_username')}', " if cmd.get("tv_username") else "") + f"Konto {ext}"

    def ab(msg, schritt="wechsel"):
        diagnose()
        # Die letzten Stationen MIT Sekunden gehoeren in den Meldungstext: Finn
        # schickt den Text, nicht die Diagnose — und 'wo blieb er haengen, wie
        # lange' war am 22.09. zweimal nur zu raten.
        return raus(msg + " | Zuletzt: " + " > ".join(list(trail)[-4:]), schritt)

    def esc():
        try:
            from pywinauto import keyboard
            keyboard.send_keys("{ESC}")
        except Exception:
            pass

    def flach_pruefen(wozu):
        """Riegel vor JEDEM Kontowechsel (Dropdown wie Ab-/Anmelden): das
        aktive Konto muss flach sein. Der Reader kennt nur "das Konto im
        Panel" — danach meldet er die Positionen des NEUEN Kontos als
        denselben Master, und der Orbit-Copier schloesse den Hedge der
        laufenden Position (Gefahren-Fund 28.08.2026). -> Fehltext oder ''"""
        pos, _an = _tv_positionen()
        if pos is None:
            return (f"Reader liefert keine Positionen — ohne den Beweis, dass das aktive "
                    f"Konto flach ist, wird nicht {wozu}.")
        if pos:
            return (f"Auf dem aktiven Konto ist noch eine Position offen ({len(pos)}). Erst "
                    f"schliessen — sonst verliert der Reader die Sicht darauf.")
        return ""

    # --- Schritt 2b: anderer Tradovate-Login -> abmelden, verbinden, anmelden --
    if zustand != "gleicher_login":
        username = str(cmd.get("tv_username") or "").strip()
        if not username:
            return ab(f"Im TradingView-Panel steht keines der Konten dieser Firma — dafuer muss "
                      f"der Tradovate-Login gewechselt werden, aber fuer die Firma ist kein "
                      "Username hinterlegt (Einstellungen > Prop Firms > Firma bearbeiten > "
                      "'Tradovate-Username fuer TradingView').", "login")
        # KEIN Positions-Riegel mehr (Finn 22.09.2026 02:2x: 'ob eine offene Position da
        # ist, ist komplett egal — es wird ueber Duplikum gehedged. Einfach direkt
        # ausloggen'). Der Riegel stammte aus der Orbit-Copier-Zeit, als der Reader die
        # Sicht auf das aktive Konto verloren haette; der Reader ist aus.
        w = tv_fenster(versuche=12)
        if not w:
            return ab("TradingView-Fenster nicht gefunden. " + fenster_gesehen[0], "login")
        inventar = uia_info.setdefault("inventar", {})

        spur = [""]

        def finde(namen, muster, y_von=0.0, y_bis=1.0, quelle=None, ohne=None):
            """Ein Durchgang: gezielt (schnell), sonst der langsame Typ-Scan.
            -> (elemente, roh)"""
            q = quelle or w
            t_scan = time.time()
            # SCHNELLSTER WEG zuerst: die Sammelabfrage sieht in EINEM Aufruf
            # alles — Treffer wie Nicht-Treffer sind damit gleich billig, und es
            # braucht keine zweite Suche als Gegenprobe.
            if _UIA_SAMMEL["geht"] is not False:
                sm = _tv_uia_sammel(q, _TV_UIA_KLICKBAR)
                if sm is not None:
                    roh = [(n, (r if muster.search(n) else None), t) for n, r, t in sm if len(n) <= 120]
                    uia_info["scan"] = {"weg": "sammel", "n": len(roh), "s": round(time.time() - t_scan, 2)}
                    return tv_uia_namen_filtern(roh, muster, _tv_fenster_rect(q), y_von, y_bis, ohne=ohne), roh
            roh = _tv_uia_nativ(q, namen)
            weg = "nativ"
            els = tv_uia_namen_filtern(roh or [], muster, _tv_fenster_rect(q), y_von, y_bis, ohne=ohne)
            if not els:
                # Kein Treffer ist beim gezielten Weg KEIN Beweis (22.09.2026: der
                # Broker-Knopf war da, die exakte Namenssuche sah ihn nicht) — der
                # langsame Scan hat genau dieses Element am 21.09. gefunden, also
                # hat er das letzte Wort. Kostet Sekunden, aber nur wenn noetig.
                roh, weg = _tv_uia_roh(q, muster=(muster,)), ("scan" if roh is None else "nativ+scan")
                els = tv_uia_namen_filtern(roh, muster, _tv_fenster_rect(q), y_von, y_bis, ohne=ohne)
            uia_info["scan"] = {"weg": weg, "n": len(roh), "s": round(time.time() - t_scan, 1)}
            return els, roh

        def warte_auf(namen, muster, sek, stelle, y_von=0.0, y_bis=1.0, quelle=None, ohne=None):
            """Pollt, bis GENAU EIN Element passt — mindestens drei Durchgaenge,
            auch wenn einer laenger dauert als das Zeitfenster (Chrome reicht
            neue Knoten verzoegert in den Baum). -> (el|None, anzahl)"""
            ende_w = time.time() + sek
            n, roh, runde = 0, [], 0
            while True:
                runde += 1
                els, roh = finde(namen, muster, y_von, y_bis, quelle, ohne)
                n = len(els)
                if n == 1:
                    return els[0], 1
                if n > 1 or (time.time() >= ende_w and runde >= 3):
                    break
                _warte(0.3, 0.25)
            inventar[stelle] = tv_uia_inventar(roh)
            if not roh:                      # gezielt nichts gefunden -> fuer die Meldung einmal breit schauen
                roh = _tv_uia_roh(quelle or w, ("Button", "MenuItem", "RadioButton", "Text"), 3000, muster=(TV_RX_SPUR,))
            spur[0] = f" Gesehen ({uia_info.get('scan', {}).get('weg')}, {len(roh)}): {tv_uia_spur(roh)}"
            return None, n

        def broker_knopf():
            # y_von 0.5 -> 0.0 (22.09.2026 13:3x): mit MAXIMIERTEM Panel sitzt der Broker-Knopf
            # 'Tradovate' oben im Fenster — die alte Einschraenkung 'untere Haelfte' haette
            # ihn (und damit 'verbunden') nicht mehr gesehen.
            els, _roh = finde(TV_NAMEN_BROKER, TV_RX_BROKER, y_von=0.0)
            return els

        def dialog_oder_verbunden(sek):
            """Was zeigt TradingView? -> ('dialog', demo_element) | ('verbunden', None)
            | ('nichts', None). Der Dialog zaehlt zuerst: steht er da, ist die
            Frage 'verbunden?' erledigt."""
            ende_d = time.time() + sek
            while True:
                els, _r = finde(TV_NAMEN_DEMO, TV_RX_DEMO)
                if len(els) == 1:
                    return "dialog", els[0]
                if broker_knopf():
                    return "verbunden", None
                # Ein Konto im Panel ist ebenfalls der Beweis 'verbunden' (22.09.2026 18:3x —
                # Spur 12:10: 46 s Warten, obwohl das Panel laengst ein Konto zeigte)
                if finde([], TV_RX_KONTOARTIG)[0]:
                    return "verbunden", None
                if time.time() >= ende_d:
                    return "nichts", None
                _warte(0.35, 0.25)

        def dropdown_pruefen(broker_el):
            """Unbekanntes Konto aktiv -> erst ins Dropdown schauen (Finns Lauf
            21.09.2026: 'PAAPEX…008' war derselbe Apex-Login). -> 'fertig' |
            'weiter' (Ziel steht nicht drin, anderer Login noetig)."""
            nonlocal start, zustand, aktiv
            broker_r = broker_el["r"]
            roh_k = _tv_uia_roh(w, ("Text",), muster=(TV_RX_KONTOARTIG,))
            # y_von 0.0 (22.09.2026, Finns Ablauf: 'wenn er das Maximieren getroffen hat, links
            # ins Dropdown druecken und anhand der External IDs pruefen, ob es der richtige
            # Login ist — falls ja switchen, falls nicht abmelden'): der Umschalter sitzt mit
            # maximiertem Panel OBEN; die Lage zum Broker-Knopf (bis 160 px darunter) reicht.
            kand = [e for e in tv_uia_namen_filtern(roh_k, TV_RX_KONTOARTIG, _tv_fenster_rect(w), y_von=0.0)
                    if 0 <= e["r"][1] - broker_r[1] <= 160 and abs(e["r"][0] - broker_r[0]) <= 200]
            # NIE STILL UEBERSPRINGEN (22.09.2026 13:4x, Finns erster kompletter Lauf auf seinem
            # PC: richtiger Login, unbekanntes Konto aktiv — der Bot meldete sich ab statt in
            # die Liste zu schauen). Mehrere Treffer (Knopf + Textkind) -> der naechste unter
            # dem Broker-Knopf; keiner -> steht in der Spur.
            if len(kand) > 1:
                kand = [min(kand, key=lambda e: e["r"][1] - broker_r[1])]
            if not kand:
                trail.append(f"kein Konto-Umschalter unter dem Broker-Knopf @{broker_r[0]},{broker_r[1]} gesehen — "
                             + tv_uia_spur([(e["text"], e["r"], "Text") for e in tv_uia_namen_filtern(roh_k, TV_RX_KONTOARTIG, _tv_fenster_rect(w), y_von=0.0)], 4))
            if len(kand) == 1:
                trail.append(f"unbekanntes Konto aktiv ('{kand[0]['text'][:30]}') -> erst Dropdown pruefen")
                ok, f = _tv_uia_klick(kand[0], "Konto-Umschalter", trail)
                if ok:
                    _warte(0.25, 0.15)
                    eintrag_x, ende_x, runde = None, time.time() + 6.0, 0
                    while not eintrag_x:
                        runde += 1
                        els = _tv_uia_konten(w, ids, uia_info, nur_ziel=ext, ohne=kand[0]["r"])
                        if len(els) == 1:
                            eintrag_x = els[0]
                        elif len(els) > 1 or (time.time() >= ende_x and runde >= 2):
                            break
                        else:
                            _warte(0.3, 0.15)
                    if eintrag_x:
                        ok, f = _tv_uia_klick(eintrag_x, f"Konto {ext}", trail)
                        if not ok:
                            return ab(f)
                        start = time.time()
                        ende_x = time.time() + 12.0
                        while time.time() < ende_x:
                            _warte(0.25, 0.15)
                            zustand, aktiv, _b, _e = lies()
                            if zustand == "richtig":
                                res["ok"], res["zustand"], res["konto_aktiv"] = True, zustand, aktiv[:80]
                                return raus(f"Konto gewechselt — aktiv ist jetzt {aktiv[:60]}. (Das "
                                            "vorher aktive Konto kennt Prophos nicht; es lag aber im "
                                            "selben Tradovate-Login.)", "wechsel")
                        return ab(f"Zielkonto in der Liste angeklickt, aber das Panel zeigt danach "
                                  f"'{aktiv[:40] or '?'}'.")
                    esc()
                    _warte(0.25, 0.15)
                    trail.append("Zielkonto nicht in der Liste -> anderer Login noetig")

            return "weiter"

        def abmelden(broker_el):
            """FINN 22.09.2026, nach dem Beweis-Lauf ('TradingView startet, Tradeify
            ist eingeloggt, nix passiert'): "dann muss sich der Puls selber
            abmelden und danach den Tab neu mit der URL oeffnen … er muss dieses
            Dropdown ueber dem, wo die Accountnamen stehen, druecken und dann auf
            Log out." TradingView MERKT sich die Broker-Sitzung: auch ein frisch
            mit dem Link gestartetes Fenster verbindet sich von selbst wieder —
            Schliessen/Neu-Oeffnen allein fuehrt nie zum Dialog. -> 'ok' | 'fertig'"""
            ok, f = _tv_uia_klick(broker_el, "Broker-Menue", trail)
            if not ok:
                trail.append("Broker-Menue nicht klickbar")
                return "nicht"
            _warte(0.6, 0.4)
            el, n = warte_auf(TV_NAMEN_LOGOUT, TV_RX_LOGOUT, 8.0, "logout_menue")
            if not el:
                # Kein Abbruch mehr (22.09.2026): seit Puls "Don't remember me"
                # setzt, genuegt Tab zu + neu mit Link. Nur die EINE noch
                # gemerkte Alt-Sitzung braucht ein Abmelden — klappt es hier
                # nicht, sagt es die Schluss-Meldung.
                esc()
                trail.append(f"'Log out' im Menue nicht gefunden ({n})" + spur[0][:160])
                return "nicht"
            ok, f = _tv_uia_klick(el, "Log out", trail)
            if not ok:
                return "nicht"
            # Fragt TradingView nach ("Wirklich abmelden?"), steht ein ZWEITER
            # Knopf mit demselben Verb da — genau einmal nachklicken.
            ende_l, nachgefragt = time.time() + 16.0, False
            while time.time() < ende_l:
                _warte(0.35, 0.25)
                if not broker_knopf():
                    trail.append("abgemeldet")
                    return "ok"
                if not nachgefragt:
                    best, _r = finde(TV_NAMEN_LOGOUT, TV_RX_LOGOUT)
                    best = [e for e in best if e["typ"] == "Button"]
                    if len(best) == 1:
                        nachgefragt = True
                        _tv_uia_klick(best[0], "Log out bestaetigen", trail)
            trail.append("'Log out' geklickt, Broker-Knopf steht aber noch da")
            return "nicht"

        def neu_mit_link():
            """TradingView-Tab schliessen, neu mit der Direkt-Adresse oeffnen, das
            neue Fenster wiederfinden. -> 'ok' | 'fertig'"""
            nonlocal w
            bf_t = _tv_http("/bedienfeld", timeout=0.4) or {}
            begriff = tv_tab_suchbegriff(bf_t.get("titel")) if bf_t.get("ok") else ""
            if not fenster[0]:
                _tv_fenster_holen([], begriff, "")   # TradingView-Tab sicher vorn (klickt ihn notfalls an)
            ok, f = _tv_tab_neu_mit_link(w, cmd, begriff, trail)
            if not ok:
                return ab(f, "login")
            w, ende_n = None, time.time() + 40.0
            while time.time() < ende_n and w is None:
                _warte(0.3, 0.15)
                fenster[0] = None
                w = tv_fenster()
            if w is None:
                return ab("TradingView wurde neu geoeffnet, das Fenster ist aber nach 40 s nicht zu "
                          "finden. " + fenster_gesehen[0], "login")
            _warte(0.6, 0.4)
            return "ok"

        def nicht_merken():
            """FINNS IDEE (22.09.2026, nach drei Laeufen, in denen das Abmelden
            nicht griff): "bei TradingView gibt's beim Connecten diesen Button
            'Konto merken oder nicht merken'" — den Haken "Don't remember me"
            bei JEDEM Verbinden setzen. Dann merkt sich TradingView die
            Tradovate-Verbindung nicht mehr (das TradingView-Konto selbst bleibt
            unberuehrt): jeder Start mit der Direkt-Adresse landet im Connect-
            Dialog — genau der Weg, der am 22.09. live durchgelaufen ist. Das
            Abmelden wird damit ueberfluessig.
            Nie ein Abbruchgrund: klappt der Haken nicht, wird trotzdem
            verbunden — dann merkt sich TradingView diese eine Sitzung eben noch.
            Der Zustand wird gelesen (kein blinder Klick, der einen gesetzten
            Haken wieder entfernt)."""
            # WARTESCHLANGE (Finns Notiz 22.09.2026, fuer spaeter): steht als
            # NAECHSTES ein Trade DERSELBEN Firma an, soll der Haken NICHT
            # gesetzt werden — dann merkt sich TradingView den Login, und der
            # naechste Start verbindet sich von selbst mit dem richtigen (nur
            # lesen + Dropdown, kein Anmelden). Kommt eine ANDERE Firma, bleibt
            # es beim Haken. Der Aufrufer sagt es ueber cmd['sitzung_merken'];
            # fehlt das Feld, gilt wie bisher: Haken setzen.
            soll_gesetzt = not bool(cmd.get("sitzung_merken"))
            kasten = None
            try:
                for cb in w.descendants(control_type="CheckBox"):
                    try:
                        if TV_RX_NICHT_MERKEN.search((cb.window_text() or "").strip()) and cb.is_visible():
                            kasten = cb
                            break
                    except Exception:
                        continue
            except Exception:
                kasten = None

            def zustand_kasten():
                try:
                    return int(kasten.get_toggle_state())      # 1 = gesetzt
                except Exception:
                    return None

            if not soll_gesetzt:
                # Sitzung SOLL gemerkt werden: nur eingreifen, wenn der Haken
                # nachweislich gesetzt ist (Standard im Dialog ist AUS).
                if kasten is not None and zustand_kasten() == 1:
                    try:
                        r = kasten.rectangle()
                        _tv_uia_klick({"punkt": ((r.left + r.right) // 2, (r.top + r.bottom) // 2)},
                                      "Don't remember me (entfernen)", trail)
                        _warte(0.3, 0.3)
                    except Exception:
                        pass
                trail.append("Sitzung wird gemerkt (naechster Trade: gleiche Firma)")
                return
            if kasten is not None:
                z = zustand_kasten()
                if z == 1:
                    trail.append("'Don't remember me' war schon gesetzt")
                    return
                try:
                    r = kasten.rectangle()
                    ziel_k = {"punkt": ((r.left + r.right) // 2, (r.top + r.bottom) // 2)}
                except Exception:
                    ziel_k = None
                if ziel_k:
                    _tv_uia_klick(ziel_k, "Don't remember me", trail)
                    _warte(0.3, 0.3)
                    z2 = zustand_kasten()
                    if z2 == 1:
                        trail.append("'Don't remember me' gesetzt (bewiesen)")
                    elif z2 == 0 and z is None:
                        # Zustand vorher unlesbar, jetzt AUS: der Klick hat einen
                        # gesetzten Haken entfernt -> einmal zurueck.
                        _tv_uia_klick(ziel_k, "Don't remember me (zurueck)", trail)
                    else:
                        trail.append("'Don't remember me' geklickt (Zustand nicht lesbar)")
                    return
            # Kein Kontrollkaestchen im Baum: die Beschriftung anklicken — sie
            # schaltet den Haken. Standard im frisch geoeffneten Dialog ist AUS.
            els, _r = finde(TV_NAMEN_NICHT_MERKEN, TV_RX_NICHT_MERKEN)
            if len(els) == 1:
                _tv_uia_klick(els[0], "Don't remember me (Beschriftung)", trail)
                _warte(0.3, 0.3)
            else:
                trail.append(f"'Don't remember me' nicht gefunden ({len(els)}) — Sitzung wird gemerkt")

        def anmelden(el):
            """Dialog steht da: Demo -> Connect -> Tradovate-Tab -> Autofill ->
            Beweis -> Anmelden -> Tab zu -> Panel neu lesen.
            -> 'fertig' | 'dropdown' (Geschwister-Konto aktiv, Schritt 3 macht weiter)"""
            nonlocal start, zustand, aktiv, bf, uia_el
            # Prop-Konten leben auf Tradovates DEMO-Umgebung (Vault 28.08.2026) —
            # ohne bewiesenen Demo-Schalter wird nicht verbunden.
            ok, f = _tv_uia_klick(el, "Demo", trail)
            if not ok:
                return ab(f, "login")
            _warte(0.25, 0.15)
            nicht_merken()
            el, n = warte_auf(TV_NAMEN_CONNECT, TV_RX_CONNECT, 6.0, "connect_knopf")
            if not el:
                esc()
                return ab(f"Der Knopf 'Connect' im Tradovate-Dialog wurde nicht eindeutig gefunden "
                          f"({n} Treffer)." + spur[0], "login")
            vorher = {h for h, _t, _w in _tv_browser_fenster()}
            ok, f = _tv_uia_klick(el, "Connect", trail)
            if not ok:
                return ab(f, "login")

            # Tradovate-Anmeldefenster (eigenes Popup — oder ein neuer Tab, dann traegt
            # das Browser-Fenster selbst den Titel).
            tw, ende_t = None, time.time() + 25.0
            while time.time() < ende_t and tw is None:
                _warte(0.35, 0.25)
                # Titel der Anmeldeseite (22.09.2026 18:4x, Finns Screenshot + Spur 'Connect → Tradovate-
                # Fenster da: 11,5 s'): der Tab heisst 'Login to your Account' — 'tradovate' steht erst
                # spaeter im Titel. Beide Schreibweisen zaehlen, deutsch wie englisch.
                kand = [(h, t, x) for h, t, x in _tv_browser_fenster() if TV_RX_TRADOVATE_TITEL.search(t)]
                neu_f = [k for k in kand if k[0] not in vorher]
                if neu_f or kand:
                    tw = (neu_f or kand)[0][2]
            if tw is None:
                return ab("Nach 'Connect' ist kein Tradovate-Anmeldefenster erschienen.", "login")
            tw_handle = tw.handle
            try:
                tw.set_focus()
            except Exception:
                pass
            trail.append("Tradovate-Fenster da")

            def felder():
                """(username_feld, passwort_feld). Finns Screenshots 21.09.2026
                22:04: die Tradovate-Anmeldung oeffnet als TAB im selben Fenster —
                damit liegt auch Chromes ADRESSLEISTE als Eingabefeld im Baum, und
                zwar VOR den Feldern der Seite. 'Das erste Feld, das kein Passwort
                ist' waere die Adressleiste gewesen: der Bot haette dort
                hineingeklickt und getippt. Deshalb ueber die Lage: Anker ist das
                Passwortfeld (IsPassword), Username ist das Feld DIREKT DARUEBER —
                gleiche linke Kante, kleinster Abstand nach oben."""
                eds = _tv_uia_felder(tw)            # EIN Aufruf; None = Weg geht nicht -> alter Weg
                if eds is None:
                    try:
                        eds = [e for e in tw.descendants(control_type="Edit")
                               if not hasattr(e, "is_visible") or e.is_visible()]
                    except Exception:
                        return None, None
                pw = next((e for e in eds if _tv_ist_passwortfeld(e)), None)
                if pw is None:
                    return None, None
                try:
                    pr = pw.rectangle()
                except Exception:
                    return None, None
                return tv_feld_darueber(eds, pw, (pr.left, pr.top, pr.right, pr.bottom)), pw

            def bewiesen():
                un, pw = felder()
                if not un or not pw:
                    return False
                return (_nur_alnum(_tv_edit_wert(un)) == _nur_alnum(username)
                        and len(_tv_edit_wert(pw)) > 0)       # nur DASS gefuellt, nie WAS

            un, pw = None, None
            ende_f = time.time() + 20.0
            while time.time() < ende_f and not (un and pw):
                un, pw = felder()
                if not (un and pw):
                    _warte(0.25, 0.15)
            if not (un and pw):
                inventar["tradovate_fenster"] = tv_uia_inventar(_tv_uia_roh(tw))
                return ab("Im Tradovate-Fenster wurden Username- und Passwortfeld nicht gefunden.", "login")

            # ERST WENN DIE SEITE RUHIG IST (22.09.2026, Finns Lauf direkt nach dem
            # Tempo-Umbau: Feld nie angeklickt, 'NICHT nachweislich drin'). Seit die
            # Suche ~1 s statt ~20 s braucht, war der Bot VOR der Seite da: Chrome
            # fuellt den zuletzt benutzten Login erst kurz nach dem Laden ein, und
            # Tradovate baut die Felder dabei neu — ein Klick davor verliert den
            # Fokus samt Vorschlagsliste, und das Tippen danach geht ins Leere. Die
            # langsame Fassung hatte genau diese Sekunden zufaellig mitgewartet.
            # Ruhig = Feldinhalte 1,2 s lang unveraendert (hoechstens 9 s warten).
            # LEERE Felder gelten erst nach 6 s als ruhig: direkt nach dem Laden
            # sind sie leer UND unveraendert — genau der Moment VOR Chromes
            # Vorbefuellen (die Simulation hat diese Luecke in der ersten Fassung
            # der Regel gefunden, bevor sie live zuschlagen konnte).
            # Steht der RICHTIGE Login samt Passwort schon drin, wird gar nicht ins
            # Feld geklickt — dann gibt es auch nichts, was ein Neuaufbau der
            # Seite verschlucken koennte: sofort weiter zu 'Anmelden' (22.09.2026,
            # Finn: '5 sec nix', obwohl TDFYU… schon vorbelegt war).
            # LEER-REGEL 6 s -> 2 s (22.09.2026 01:39, Finns Remote-Lauf, Trail:
            # 'Tradovate-Fenster da' 25,3 s -> 'Anmeldeseite ruhig' 33,0 s; Finn: 'das
            # ist meistens schon geladen, dann dauert es 5-10 s, wo nichts passiert').
            # Chrome zeigt den vorbelegten Login nur als VORSCHAU — der Feldwert bleibt
            # fuer UIA leer, bis jemand ins Feld klickt. Die Felder waren also 'leer und
            # unveraendert' und liefen in die volle 6-s-Wartezeit, obwohl die Seite
            # laengst stand. Der Klick danach ist ohnehin abgesichert (Fokus-Beweis,
            # drei Versuche, Liste per Pfeil-runter, Tipp-Rueckfall).
            schon_richtig = bewiesen()
            letzter, seit, t_r = None, time.time(), time.time()
            while not schon_richtig and time.time() - t_r < 9.0:
                u2, p2 = felder()
                jetzt = (_tv_edit_wert(u2) if u2 else None, len(_tv_edit_wert(p2)) if p2 else None)
                if jetzt != letzter:
                    letzter, seit = jetzt, time.time()
                elif time.time() - seit >= 0.6 and (jetzt[0] or time.time() - t_r >= 1.2):
                    break
                _warte(0.3, 0.2)
            trail.append("Anmeldeseite ruhig")

            def ins_feld():
                """Username-Feld anklicken, bis es den Tastaturfokus HAT. -> (ok, rect)"""
                rect = None
                for _versuch in range(3):
                    u3, _p3 = felder()
                    if not u3:
                        _warte(0.3, 0.15)
                        continue
                    try:
                        r = u3.rectangle()
                        rect = (r.left, r.top, r.right, r.bottom)
                    except Exception:
                        continue
                    ok_k, _f = _tv_uia_klick({"punkt": ((r.left + r.right) // 2, (r.top + r.bottom) // 2)},
                                             "Username-Feld", trail)
                    _warte(0.6, 0.4)
                    try:
                        if u3.has_keyboard_focus():
                            return True, rect
                    except Exception:
                        return ok_k, rect          # Fokus nicht lesbar -> dem Klick glauben
                return False, rect

            if not bewiesen():
                hat_fokus, un_r = ins_feld()
                if not hat_fokus:
                    return ab("Das Benutzername-Feld im Tradovate-Fenster nimmt den Klick nicht an "
                              "(kein Tastaturfokus nach drei Versuchen).", "login")
                vor = _tv_autofill_vorschlag(username, ohne=un_r, anmelde_handle=tw_handle)
                if len(vor) != 1:
                    # Liste nicht (mehr) offen? Pfeil-runter oeffnet sie im Feld.
                    try:
                        from pywinauto import keyboard
                        keyboard.send_keys("{DOWN}")
                        _warte(0.6, 0.3)
                    except Exception:
                        pass
                    vor = _tv_autofill_vorschlag(username, ohne=un_r, anmelde_handle=tw_handle)
                if len(vor) == 1:
                    ok, f = _tv_uia_klick(vor[0], "Autofill-Vorschlag", trail)
                    if not ok:
                        return ab(f, "login")
                else:
                    # Liste fuer UIA unsichtbar: Username tippen — Chrome filtert die
                    # Vorschlaege dann auf genau diesen — und den ersten nehmen. Nur
                    # mit bewiesenem Fokus, und erst wenn der getippte Name im Feld
                    # STEHT (sonst ginge Pfeil+Enter auf irgendeinen Vorschlag).
                    try:
                        from pywinauto import keyboard
                        keyboard.send_keys("{ESC}")           # evtl. offene Liste zu, Feld behaelt den Fokus
                    except Exception:
                        pass
                    hat_fokus, un_r = ins_feld()
                    if not hat_fokus:
                        return ab("Benutzername-Feld hat den Fokus verloren.", "login")
                    _tv_tippen(tv_tasten_escape(username), "Username", trail)
                    _warte(0.3, 0.15)
                    u4, _p4 = felder()
                    if not u4 or _nur_alnum(_tv_edit_wert(u4)) != _nur_alnum(username):
                        return ab(f"Der Username '{username}' liess sich nicht ins Feld tippen "
                                  f"(dort steht '{_tv_edit_wert(u4)[:30] if u4 else '?'}').", "login")
                    vor = _tv_autofill_vorschlag(username, ohne=un_r, anmelde_handle=tw_handle)
                    if len(vor) == 1:
                        ok, f = _tv_uia_klick(vor[0], "Autofill-Vorschlag", trail)
                        if not ok:
                            return ab(f, "login")
                    else:
                        try:
                            from pywinauto import keyboard
                            keyboard.send_keys("{DOWN}")
                            _warte(0.3, 0.2)
                            keyboard.send_keys("{ENTER}")
                            trail.append(f"Autofill per Pfeil+Enter ({len(vor)} sichtbare Vorschlaege)")
                        except Exception:
                            return ab("Autofill-Vorschlag liess sich nicht waehlen.", "login")
                ende_b = time.time() + 6.0
                while time.time() < ende_b and not bewiesen():
                    _warte(0.25, 0.15)
            if not bewiesen():
                inventar["tradovate_fenster"] = tv_uia_inventar(_tv_uia_roh(tw))
                return ab(f"Im Tradovate-Fenster stehen Username '{username}' und ein gefuelltes "
                          "Passwort NICHT nachweislich drin — es wird nicht auf Login geklickt. Ist "
                          "dieser Login in Chromes Passwortmanager fuer tradovate.com gespeichert?", "login")
            trail.append("Username + gefuelltes Passwort bewiesen")
            # Login-Klick mit NACHWEIS und zwei Rueckfaellen (23.09.2026 04:2x, Moritz-PC,
            # Finn: "der Knopf wird beim Drueberfahren ein anderes Blau, die Maus ist drauf,
            # aber es geht nicht los — irgendwas packt es"). Der atomare SendInput-Klick
            # (Bewegen+Druecken+Loslassen in einem Batch) erreicht den Knopf als Hover,
            # aber die Seite wertet ihn nicht als Klick — vermutlich schluckt Chromes noch
            # offene Autofill-Liste das Druecken. Auf Finns PC ging derselbe Klick durch.
            # Deshalb: Klick -> 4 s auf das Verschwinden des Fensters warten -> sonst Enter
            # (der Klick hat dem Knopf den Tastaturfokus gegeben) -> sonst Esc (Autofill-
            # Liste zu), ins Passwortfeld und Enter (Formular abschicken). Jeder Schritt
            # steht in der Spur; jeder wird nur gefahren, solange das Fenster wirklich noch da ist.
            def tradovate_noch_da():
                return any(h == tw_handle and TV_RX_TRADOVATE_TITEL.search(t) for h, t, _x in _tv_browser_fenster())

            def warte_weg(sek):
                ende_w = time.time() + sek
                while time.time() < ende_w:
                    _warte(0.25, 0.15)
                    if not tradovate_noch_da():
                        return True
                return False

            def taste(k):
                try:
                    from pywinauto import keyboard
                    keyboard.send_keys(k)
                    return True
                except Exception:
                    return False

            el, n = warte_auf(TV_NAMEN_LOGIN, TV_RX_LOGIN, 6.0, "login_knopf", quelle=tw)
            weg = False
            if el:
                ok, f = _tv_uia_klick(el, "Login", trail)
                if not ok:
                    return ab(f, "login")
                weg = warte_weg(4.0)
                if not weg and tradovate_noch_da():
                    trail.append("Login-Klick ohne Wirkung (Fenster unveraendert) -> Enter auf dem Knopf")
                    taste("{ENTER}")
                    weg = warte_weg(4.0)
            if not weg and tradovate_noch_da():
                # Enter im Passwortfeld schickt das Formular ab. Erlaubt, weil Username +
                # gefuelltes Passwort oben BEWIESEN sind. Erst Esc: eine offene Autofill-Liste
                # wuerde das Enter sonst als Auswahl verstehen statt als Abschicken.
                _u5, p5 = felder()
                try:
                    r = p5.rectangle()
                    taste("{ESC}")
                    _warte(0.2, 0.15)
                    _tv_uia_klick({"punkt": (r.right - 30, (r.top + r.bottom) // 2)}, "Passwortfeld", trail)
                    _warte(0.3, 0.2)
                    taste("{ESC}")
                    _warte(0.15, 0.1)
                    if not bewiesen():
                        return ab("Nach dem Esc sind Username/Passwort nicht mehr nachweislich gefuellt — "
                                  "es wird nicht abgeschickt.", "login")
                    taste("{ENTER}")
                    trail.append(("Login-Knopf" if el else f"'Anmelden' nicht eindeutig ({n})")
                                 + " -> Esc + Enter im Passwortfeld")
                except Exception:
                    if not el:
                        return ab(f"Der Knopf 'Anmelden' im Tradovate-Fenster wurde nicht eindeutig gefunden "
                                  f"({n} Treffer)." + spur[0], "login")
                    trail.append("Passwortfeld fuer den Rueckfall nicht erreichbar")

            # Das Fenster muss verschwinden (bzw. der Tab den Titel verlieren).
            ende_z = time.time() + 35.0
            noch_da = not weg
            while time.time() < ende_z and noch_da:
                _warte(0.25, 0.15)
                noch_da = tradovate_noch_da()
            if noch_da:
                roh_n = _tv_uia_roh(tw)
                inventar["tradovate_nach_login"] = tv_uia_inventar(roh_n)
                # Was auf der Seite steht, gehoert in die Meldung (23.09.2026, Moritz-PC,
                # Remote-Lauf: die Frage 'steht dort eine Fehlermeldung?' konnte vom Mac
                # aus niemand beantworten — Dump lag nur auf dem PC). Typische Faelle:
                # Tradovate verlangt bei einem NEUEN Geraet einen Bestaetigungscode per
                # E-Mail, meldet falsche Zugangsdaten oder eine bestehende Sitzung.
                seite = tv_seite_texte(roh_n)
                return ab("Login geklickt (Klick, Enter, Enter im Passwortfeld), aber das Tradovate-Fenster ist "
                          "noch offen — " + (f"dort steht: {seite}" if seite
                                              else "steht dort eine Fehlermeldung oder eine Rueckfrage?"), "login")
            trail.append("angemeldet, Tradovate-Fenster zu")

            # Zurueck zu TradingView und neu lesen: jetzt muss eines der Konten der
            # Firma dastehen.
            fenster[0] = None
            max_versucht[0] = False     # neuer Tab: Panel kann wieder flach laden
            uia_info["aehnlich"] = []   # nur, was NACH dem Login zu sehen ist (alte Konten des vorigen Logins raus)
            start = time.time()
            ende = time.time() + 45.0
            while True:
                zustand, aktiv, bf, uia_el = lies()
                if max_fehl[0]:
                    return raus(max_fehl[0], "panel")
                if zustand in ("richtig", "gleicher_login") or time.time() >= ende:
                    break
                # NACH DEM EIGENEN LOGIN ist JEDES angezeigte Konto derselbe Login (22.09.2026
                # 13:2x, Finns PC: nach dem Login mit TDFYU954156097 stand 'FTDFYSLX150141702701
                # USD' im Panel — ein Konto dieses Logins, das Prophos nicht kennt (anderes
                # Namensmuster als TDFYSL…) — und der Bot verlangte eines der BEKANNTEN Konten).
                # Steht ein kontoartiger Text da, gilt 'gleicher_login': weiter zum Dropdown.
                fremd = tv_fremdes_konto(uia_info.get("aehnlich"), ids)
                if fremd and fenster[0]:
                    els_f = _tv_uia_konten(fenster[0], [fremd.split()[0]], {})
                    if len(els_f) == 1:
                        zustand, aktiv, uia_el = "gleicher_login", fremd, els_f[0]
                        trail.append(f"nach Login: unbekanntes Konto '{fremd[:40]}' — derselbe Login (gerade angemeldet), weiter per Dropdown")
                        break
                _warte(0.2, 0.15)
            res["zustand"], res["konto_aktiv"] = zustand, aktiv[:80]
            trail.append(f"nach Login: '{aktiv[:40] or '-'}' -> {zustand}"
                         + (f" [Fenster {'ja' if lies_diag['w'] else 'NEIN: ' + fenster_gesehen[0][:120]}"
                            f" · Treffer {lies_diag['els']} · kontoartig {(uia_info.get('aehnlich') or [])[:4]}"
                            f" · Scan {uia_info.get('weg')}/{uia_info.get('gescannt')}]" if zustand not in ("richtig", "gleicher_login") else ""))
            if zustand == "richtig":
                res["ok"] = True
                return raus(f"Tradovate-Login gewechselt ({username}) — aktiv ist {aktiv[:60]}.", "login")
            if zustand != "gleicher_login":
                return ab(f"Mit '{username}' angemeldet, aber im Panel steht keines der Konten dieser "
                          f"Firma (gebraucht: {ext}). Gehoert der Username wirklich zu dieser Firma?", "login")

            return "dropdown"

        # ---- Ablauf -----------------------------------------------------------
        # Bis zu ZWEI Runden (22.09.2026, Finns Lauf: verbundenes TradingView nicht
        # erkannt -> Tab zu, neu, wieder selbst verbunden -> Ende). Steht nach dem
        # Neu-Oeffnen ein verbundener Broker da, wird er in der zweiten Runde
        # abgemeldet, statt aufzugeben.
        login_noetig = True
        if frisch_mit_link:
            trail.append("TradingView frisch mit Direkt-Adresse gestartet")
            art, el_demo = dialog_oder_verbunden(40.0)
        else:
            art, el_demo = ("verbunden" if broker_knopf() else "nichts"), None
        gelesen = not frisch_mit_link          # war TradingView schon offen, wurde oben gelesen

        for runde in (1, 2):
            if art == "dialog" or not login_noetig:
                break
            if art == "verbunden":
                if not gelesen:
                    # Gemerkte Sitzung hat sich von selbst verbunden — vielleicht ist
                    # es ja der richtige Login: erst lesen, dann handeln.
                    gelesen = True
                    trail.append("TradingView hat sich von selbst wieder verbunden (gemerkte Sitzung)")
                    ende_v = time.time() + 25.0
                    fremd_v = ""
                    while True:
                        zustand, aktiv, bf, uia_el = lies()
                        if zustand in ("richtig", "gleicher_login") or time.time() >= ende_v:
                            break
                        # Unbekanntes Konto zweimal gesehen -> nicht 25 s warten, sondern gleich
                        # zum Listen-Check (22.09.2026 13:5x, Finn: 'wenn TradingView oeffnet und ich
                        # im RICHTIGEN Tradovate schon drin bin' — erst Dropdown, dann erst abmelden).
                        f_v = tv_fremdes_konto(uia_info.get("aehnlich"), ids)
                        if f_v and f_v == fremd_v:
                            zustand, aktiv = "falsch", f_v
                            break
                        fremd_v = f_v
                        _warte(0.2, 0.15)
                    res["zustand"], res["konto_aktiv"] = zustand, aktiv[:80]
                    trail.append(f"Konto im Panel: '{aktiv[:40] or '-'}' -> {zustand}"
                                 + (f" [Fenster {'ja' if lies_diag['w'] else 'NEIN: ' + fenster_gesehen[0][:120]}"
                                    f" · Treffer {lies_diag['els']} · kontoartig {(uia_info.get('aehnlich') or [])[:4]}"
                                    f" · Scan {uia_info.get('weg')}/{uia_info.get('gescannt')}]" if zustand not in ("richtig", "gleicher_login") else ""))
                    if zustand == "richtig":
                        res["ok"] = True
                        return raus(f"Richtiges Konto ist aktiv ({aktiv[:60]}).", "konto")
                    if zustand == "gleicher_login":
                        login_noetig = False
                        break
                broker = broker_knopf()
                if len(broker) != 1:
                    return ab(f"Der Broker-Knopf 'Tradovate' im unteren Panel ist nicht eindeutig "
                              f"({len(broker)} Treffer).", "login")
                trail.append("Broker verbunden, Zielkonto nicht im Panel")
                if runde == 1 and dropdown_pruefen(broker[0]) == "fertig":
                    return
                abmelden(broker[0])          # 'nicht' ist kein Abbruch — weiter mit Tab zu + neu
            if neu_mit_link() == "fertig":
                return
            art, el_demo = dialog_oder_verbunden(40.0)

        if login_noetig:
            if art != "dialog":
                gesehen = tv_uia_spur(_tv_uia_roh(w, ("Button", "RadioButton", "Text"), 3000, muster=(TV_RX_SPUR,)))
                return ab("TradingView ist neu offen, aber der Tradovate-Dialog ist nicht erschienen"
                          + (" — es hat sich wieder von selbst mit dem alten Login verbunden (gemerkte "
                             "Sitzung). EINMAL von Hand: unten 'Tradovate' > 'Log out', dann erneut "
                             "starten. Ab dann setzt Puls bei jedem Verbinden 'Don't remember me', und "
                             "es passiert nicht wieder." if art == "verbunden" else
                             ". Ist in einem ANDEREN Chrome-Fenster noch ein TradingView-Tab offen?")
                          + f" Gesehen: {gesehen}", "login")
            if anmelden(el_demo) == "fertig":
                return

    # --- Schritt 3: gleicher Login, anderes Unterkonto -> Dropdown ---------
    # Finn 21.09.2026: "an diesem Step muessten wir einfach nur einmal auf das
    # Drop-Down draufdruecken und den Account switchen."
    # kein Positions-Riegel (s.o., Finn 22.09.2026)
    w = tv_fenster(versuche=8)
    if not w:
        return ab("TradingView-Fenster fuer den Klick nicht gefunden. " + fenster_gesehen[0])
    try:
        hwnd = w.handle
    except Exception:
        return ab("Browser-Fenster ohne Handle — Fenster neu oeffnen.")
    _warte(0.3, 0.3)

    # Umschalter anklicken — mit dem Auge, das ihn gesehen hat.
    schalter_css, schalter_uia = None, None
    if uia_el:
        schalter_uia = uia_el
        ok, f = _tv_uia_klick(uia_el, "Konto-Umschalter", trail)
    else:
        geo_ok = isinstance((bf or {}).get("geo"), dict) and bf["geo"].get("innerWidth")
        el = _tv_element(bf, "konto", "schalter") if geo_ok else None
        if not el and geo_ok:
            per_text = tv_konto_per_text(bf, ids)
            el = per_text[0] if len(per_text) == 1 else None
        if el:
            schalter_css = _tv_rect4(el)
            ok, f = _tv_klick(el["rect"], bf["geo"], _klient_rechteck(hwnd), "Konto-Umschalter", trail)
        else:
            els = _tv_uia_konten(w, ids, uia_info)
            if len(els) != 1:
                return ab(f"Konto steht auf '{aktiv[:40]}' statt {ext} — der Konto-Umschalter "
                          "wurde aber nicht eindeutig gefunden.")
            schalter_uia = els[0]
            ok, f = _tv_uia_klick(els[0], "Konto-Umschalter", trail)
    if not ok:
        return ab(f)
    _warte(0.25, 0.15)

    # Zieleintrag in der offenen Liste suchen: erst das Userscript (nur 0.4.2+
    # sieht die Liste — 'treffer'), sonst UIA. Die Liste baut sich nach dem
    # Klick erst auf und Chrome reicht neue Knoten verzoegert in den Baum,
    # deshalb mehrere Anlaeufe.
    eintrag, eintrag_uia, anzahl = None, None, 0
    ende = time.time() + 9.0
    while time.time() < ende and not (eintrag or eintrag_uia):
        b = _tv_bf(nach=time.time(), timeout=0.3)      # Userscript laeuft bei Finn nicht — nicht 1,5 s je Runde warten
        if b and isinstance(b.get("treffer"), list):
            per_text = tv_konto_per_text(b, ids, nur_ziel=ext, ohne=schalter_css, ueberall=True)
            anzahl = len(per_text)
            if anzahl == 1:
                eintrag, bf = per_text[0], b
                break
        els = _tv_uia_konten(w, ids, uia_info, nur_ziel=ext,
                             ohne=(schalter_uia or {}).get("r"))
        anzahl = max(anzahl, len(els))
        if len(els) == 1:
            eintrag_uia = els[0]
            break
        if len(els) > 1:
            break                  # mehrdeutig wird durch Warten nicht besser
        _warte(0.25, 0.2)
    if not (eintrag or eintrag_uia):
        # Dropdown wieder schliessen, sonst bleibt es ueber dem Chart haengen.
        try:
            from pywinauto import keyboard
            keyboard.send_keys("{ESC}")
        except Exception:
            pass
        # Beweise in den Meldungstext (22.09.2026 12:4x, Finns PC: dritter Lauf mit
        # '0 Treffer' — ohne die Zahlen ist nicht zu sehen, WO UIA den Umschalter sieht
        # und ob der Klick ueberhaupt im Fenster lag).
        fr_ = _tv_fenster_rect(w)
        roh_l = _tv_uia_roh(w, ("Text", "ListItem", "MenuItem", "Button"))
        konto_artig = [f"{t[:34]}@{r[0]},{r[1]}-{r[3]}" for t, r, _typ in roh_l
                       if r and TV_RX_KONTO_ARTIG.match(str(t).strip())][:8]
        return ab(f"Dropdown geoeffnet, aber Konto {ext} steht darin nicht eindeutig "
                  f"({anzahl} Treffer). Liegt es wirklich unter diesem Tradovate-Login? "
                  f"| Fenster {fr_} · Umschalter {(schalter_uia or {}).get('r')} · geklickt "
                  f"{(schalter_uia or {}).get('punkt')} · kontoartig nach dem Klick: "
                  + (" | ".join(konto_artig) or "nichts") + " · Scan " + str(uia_info.get("scan") or uia_info.get("weg")))
    if eintrag_uia:
        ok, f = _tv_uia_klick(eintrag_uia, f"Konto {ext}", trail)
    else:
        ok, f = _tv_klick(eintrag["rect"], bf["geo"], _klient_rechteck(hwnd), f"Konto {ext}", trail)
    if not ok:
        return ab(f)

    # Beweis: das Panel muss danach nachweislich das Zielkonto zeigen.
    start = time.time()            # nur Staende NACH dem Klick zaehlen
    ende = time.time() + 12.0
    while time.time() < ende:
        _warte(0.25, 0.15)
        zustand, aktiv, _b, _e = lies()
        if zustand == "richtig":
            res["ok"], res["zustand"], res["konto_aktiv"] = True, zustand, aktiv[:80]
            trail.append(f"Konto steht auf {ext}")
            return raus(f"Konto gewechselt — aktiv ist jetzt {aktiv[:60]}.", "wechsel")
    res["zustand"], res["konto_aktiv"] = zustand, aktiv[:80]
    return ab(f"Konto liess sich nicht auf {ext} umstellen — das Panel zeigt "
              f"'{aktiv[:40] or '?'}'.")


# ═══════════════════════════════════════════════════════════════════════════
# FUTURES-PULS, SCHRITT 3 (22.09.2026) — das richtige Asset ueber die Watchlist
#
# Finn 22.09.2026: "Rechts in der Favoritenleiste wird auf jeder ID immer ganz
# oben NQ sein und darunter MNQ. Je nachdem, ob ich im Trade-Plan NQ oder MNQ
# waehle, wird in der Watchlist auf NQ oder MNQ gedrueckt. Dann switcht
# automatisch der Chart dazu — plus rechts das Order-Terminal."
#
# FINDEN: Watchlist-Zeile = Textelement in der RECHTEN Fensterhaelfte, dessen
# Symbol-WURZEL (tv_symbol_root: 'NQZ6' aus Prophos == 'NQZ2026' in TradingView
# == 'NQ') die gesuchte ist. Die Wurzel trennt NQ und MNQ sauber. Dieselbe
# Schreibweise steht rechts auch im Detail-Kasten UNTER der Watchlist — genommen
# wird deshalb die OBERSTE Fundstelle; liegen zwei auf derselben Hoehe, ist es
# mehrdeutig und es wird nicht geklickt.
# BEWEIS: der Fenstertitel. TradingView schreibt das Chart-Symbol als erstes
# Wort in den Tab ('NQZ2026 30,787.00 ▲ +0.01% Unnamed') — das ist unabhaengig
# von jedem Seitenelement und liess sich schon am 30.08. sicher lesen.
# ═══════════════════════════════════════════════════════════════════════════

def tv_titel_wurzel(titel):
    """Symbol-Wurzel aus dem Fenstertitel ('NQZ2026 30,787 ▲ … - Google Chrome' -> 'NQ')."""
    return tv_symbol_root(tv_tab_suchbegriff(titel))


def tv_watchlist_zeile(roh, ziel_wurzel, fenster):
    """Aus (name, rect, typ)-Tripeln die Watchlist-Zeile des Ziel-Symbols.
    -> (element|None, anzahl_kandidaten). Siehe Kopfkommentar."""
    if not ziel_wurzel or not fenster:
        return None, 0
    fl, ft, fr, fb = fenster
    grenze_x = fl + (fr - fl) * 0.55
    kand = []
    for eintrag in roh or ():
        try:
            name, r = eintrag[0], eintrag[1]
            if not r:
                continue
            l, t, rr, b = (int(v) for v in r)
        except (TypeError, ValueError, IndexError):
            continue
        n = str(name or "").strip()
        # nur ein einzelnes Wort, das wie ein Kontrakt aussieht — keine Saetze,
        # keine Beschreibungen ('E-mini Nasdaq-100 Futures …')
        if not n or " " in n or len(n) > 24 or rr - l < 3 or b - t < 3:
            continue
        if (l + rr) // 2 < grenze_x or not (ft <= (t + b) // 2 <= fb):
            continue
        if tv_symbol_root(n) != ziel_wurzel:
            continue
        kand.append({"text": n, "r": (l, t, rr, b), "punkt": ((l + rr) // 2, (t + b) // 2)})
    if not kand:
        return None, 0
    kand.sort(key=lambda e: e["r"][1])
    oben = kand[0]
    if len(kand) > 1 and abs(kand[1]["r"][1] - oben["r"][1]) <= 10 and kand[1]["r"] != oben["r"]:
        return None, len(kand)                 # zwei auf derselben Hoehe -> mehrdeutig
    return oben, len(kand)


def tv_asset_schritt(w, symbol, trail):
    """Chart (und damit das Order-Panel) auf das Symbol des Plans stellen.
    -> (ok, msg)"""
    ziel = tv_symbol_root(symbol)
    if not ziel:
        return False, f"Symbol '{symbol}' ist nicht lesbar."

    def titel_wurzel():
        try:
            return tv_titel_wurzel(w.window_text() or "")
        except Exception:
            return ""

    if titel_wurzel() == ziel:
        trail.append(f"Chart steht schon auf {ziel}")
        return True, f"Asset {ziel} steht schon."
    el, n = None, 0
    for _runde in range(4):
        roh = _tv_uia_roh(w, ("Text", "ListItem", "DataItem", "Button"))
        el, n = tv_watchlist_zeile(roh, ziel, _tv_fenster_rect(w))
        if el or n > 1:
            break
        _warte(0.6, 0.4)
    if not el:
        gesehen = sorted({str(x[0]) for x in (roh or []) if x[1] and " " not in str(x[0])
                          and 2 <= len(str(x[0])) <= 12 and tv_symbol_root(str(x[0])) in ("NQ", "MNQ", ziel)})[:8]
        return False, (f"{ziel} in der Watchlist rechts nicht eindeutig gefunden ({n} Treffer). Ist die "
                       f"Watchlist offen und steht {ziel} drin? Gesehen: {', '.join(gesehen) or 'nichts Passendes'}")
    ok, f = _tv_uia_klick(el, f"Watchlist {el['text']}", trail)
    if not ok:
        return False, f
    ende = time.time() + 10.0
    while time.time() < ende:
        _warte(0.25, 0.15)
        if titel_wurzel() == ziel:
            trail.append(f"Chart steht auf {ziel} (Tab-Titel)")
            _warte(0.35, 0.25)      # das Order-Panel baut sich nach dem Wechsel neu auf
            return True, f"Asset {el['text']} gewaehlt."
    return False, (f"Watchlist-Zeile {el['text']} angeklickt, aber der Tab-Titel zeigt danach "
                   f"'{(w.window_text() or '')[:40]}' statt {ziel}.")


# ═══════════════════════════════════════════════════════════════════════════
# FUTURES-PULS, SCHRITT 4a (22.09.2026) — Order-Panel ausfuellen und BEWEISEN
#
# Finns Ablauf (22.09.2026): Buy oder Sell nach Plan → immer Market → Take
# Profit: Schalter an, $-Wert 1:1 wie beim Trade-Planen → Stop Loss NUR wenn
# in Prophos einer steht; sonst den SL-Schalter AUS stellen, falls er an ist
# ("mein Stop Loss ist oft die Auto-Liquidation").
#
# 4a = PROBELAUF: alles eintragen, alles zuruecklesen, den Text des Kauf-Knopfs
# pruefen — und NICHT klicken. Der scharfe Klick kommt als eigener Schritt,
# wenn Finn den Probelauf am PC gesehen hat: hier wird echtes Geld bewegt.
#
# DAS PANEL (Finns Screenshot 22.09., englische Oberflaeche): Kopf 'MNQZ6' ·
# Reiter Order/DOM · Seiten-Kasten 'Sell <Kurs> | Buy <Kurs>' · Reiter
# 'Market  Limit  Stop  Stop Limit' · 'Units' + Feld · 'Exits' mit
# 'Take profit, $' + Schalter + Wertfeld, 'Stop loss, $' + Schalter + Wertfeld ·
# unten der Knopf ('Start creating order', nach Seitenwahl 'Buy 1 MNQZ6 …').
# Links oben im CHART stehen zusaetzlich die Schnell-Knoepfe 'SELL'/'BUY' —
# die duerfen NIE getroffen werden. Deshalb wird alles am Panel VERANKERT:
# die Reiter-Zeile 'Market … Stop Limit' gibt den x-Bereich des Panels, jede
# weitere Stelle muss darin liegen.
# Felder und Schalter tragen bei TradingView keine Namen — sie werden ueber
# ihre LAGE zur Beschriftung gefunden (Wertfeld = erstes Eingabefeld direkt
# unter der Beschriftung; Schalter = selbe Zeile, rechts). Ob ein Schalter AN
# ist, zeigt das Wertfeld: aus = ausgegraut (nicht bedienbar).
# ═══════════════════════════════════════════════════════════════════════════

TV_RX_MARKET = re.compile(r"^(market|markt)$", re.I)
TV_RX_STOPLIMIT = re.compile(r"^stop[- ]?limit$", re.I)
# 25.09.2026 (Finn: 'auf Englisch geht es sofort, auf Deutsch im selben Layout nicht'): deutsche
# Varianten des neuen Tickets — und die Namen werden vor dem Vergleich NORMALISIERT (tv_name_norm:
# weiche Trennstriche, geschuetzte Leerzeichen, Pfeile/Chevrons des Aufklappmenues, Doppelabstaende).
TV_RX_UNITS = re.compile(r"^(units|einheiten|menge|kontrakte|quantity|anzahl|st(ue|ü)ck|lots?)\b", re.I)
TV_RX_TP = re.compile(r"^(take[- ]?profit|gewinn(mitnahme|ziel)|tp\b)", re.I)
TV_RX_SL = re.compile(r"^(stop+[- ]?loss|verlustbegrenzung|sl\b)", re.I)
_TV_NAME_MUELL = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff]|[\u25be\u25bc\u25b4\u25b2\u2bc5\u2bc6\u2304\u2303\u02c5\u02c4\u23f7\u23f6\u2193\u2191\u02cf]+")


def tv_name_norm(name):
    """UIA-Name fuers Muster: unsichtbare Zeichen und Menue-Pfeile raus, geschuetzte
    Leerzeichen zu Leerzeichen, Abstaende gebuendelt, Raender ab."""
    t = _TV_NAME_MUELL.sub("", str(name or ""))
    t = t.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    return re.sub(r"\s+", " ", t).strip()
# Seiten-Kasten: 'Buy' als Textknoten — oder, falls nur der Kasten selbst benannt
# ist, 'Buy 30,827.75' (Name + Kurs).
TV_RX_SEITE = {"buy": re.compile(r"^(buy|kauf|kaufen)(\s+[\d.,]+)?$", re.I),
               "sell": re.compile(r"^(sell|verkauf|verkaufen)(\s+[\d.,]+)?$", re.I)}
TV_RX_SENDEN = re.compile(r"^(buy|sell|kauf|verkauf)\w*\s+\d", re.I)


def tv_zahl_lesen(text):
    """Zahl aus einem TradingView-Feld, egal ob englisch ('1,875.00') oder
    deutsch ('1.875,00') geschrieben. None, wenn nichts Zaehlbares drinsteht."""
    t = re.sub(r"[^0-9,.\-]", "", str(text or ""))
    if not re.search(r"\d", t):
        return None
    if "," in t and "." in t:
        dez = "," if t.rfind(",") > t.rfind(".") else "."
        t = t.replace("." if dez == "," else ",", "").replace(dez, ".")
    elif re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", t):
        t = t.replace(",", "").replace(".", "")       # reine Tausender-Gruppen ('1,875' / '1.875')
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# Abstand, in dem die Feld-Beschriftungen (Units / Take profit / Stop loss) UNTER
# der Reiter-Zeile liegen muessen, damit die Reiter-Zeile als Order-Ticket gilt.
TV_PANEL_LABEL_TIEFE = 520
TV_PANEL_RAND = 30


def tv_panel_bereich(roh, fenster=None):
    """Order-Ticket per UIA finden. -> dict oder None (keine Reiter-Zeile).

    Anker (25.09.2026, Finns Test-Order: das Order-Panel war zum ersten Mal NICHT
    rechts angedockt, sondern ein frei schwebendes Popup ueber dem Chart; der Bot
    nahm die Reiter-Zeile fuer bare Muenze, arbeitete mit der Geometrie der rechten
    Spalte und klickte 'Market' @655,285 und 'BUY' @895,228 ins Leere — das Popup
    sass bei ~1000-1460 x 160-1000, 'Units' war 'nicht gefunden'):
      1. Reiter-Zeile: 'Market' und 'Stop Limit' auf EINER Zeile (beide Sprachen).
      2. Darunter, im x-Bereich der Reiter-Zeile (+/- Rand), mindestens eine
         Feld-Beschriftung aus TV_RX_UNITS / TV_RX_TP / TV_RX_SL — nur dann ist
         die Reiter-Zeile das Ticket. Die gemeinsame Bounding-Box aus Reitern und
         Beschriftungen ist der Bereich ('links'/'rechts'/'oben'/'unten'), egal ob
         angedockt oder Popup. Gibt es mehrere Reiter-Zeilen, gewinnt die mit den
         meisten Beschriftungen darunter.
      3. Reiter-Zeile ohne Beschriftungen darunter: dict mit 'ohne_felder': True —
         der Aufrufer wartet kurz (Panel im Aufbau) und bricht dann ab, statt auf
         Rueckfall-Koordinaten zu klicken.
    'modus' = 'angedockt', wenn der Bereich am rechten Fensterrand endet (fenster =
    Rechteck des TradingView-Fensters), sonst 'Popup'; 'spur' = lesbare Kurzform."""
    markt = [e for e in roh or () if e[1] and TV_RX_MARKET.search(tv_name_norm(e[0]))]
    stopl = [e for e in roh or () if e[1] and TV_RX_STOPLIMIT.search(tv_name_norm(e[0]))]
    labels = [e for e in roh or () if e[1] and (TV_RX_UNITS.search(tv_name_norm(e[0]))
                                                or TV_RX_TP.search(tv_name_norm(e[0]))
                                                or TV_RX_SL.search(tv_name_norm(e[0])))]
    bester, bester_n = None, -1
    for m in markt:
        for sl in stopl:
            if not (abs((m[1][1] + m[1][3]) - (sl[1][1] + sl[1][3])) <= 24 and sl[1][0] > m[1][0]):
                continue
            reiter_y = (m[1][1] + m[1][3]) // 2
            l0, r0 = m[1][0], sl[1][2]
            unter = []
            for e in labels:
                el, et, er, eb = e[1]
                mx, my = (el + er) // 2, (et + eb) // 2
                if l0 - TV_PANEL_RAND - 40 <= mx <= r0 + TV_PANEL_RAND + 40 and reiter_y < my <= reiter_y + TV_PANEL_LABEL_TIEFE:
                    unter.append(e)
            if len(unter) > bester_n:
                bester, bester_n = (m, sl, unter), len(unter)
    if bester is None:
        return None
    m, sl, unter = bester
    reiter_y = (m[1][1] + m[1][3]) // 2
    # Der Senden-Knopf ('Buy 5 MNQZ6 MARKET') gehoert zum Ticket und schliesst es nach unten ab —
    # sonst zaehlte er selbst als 'Element darunter' und jedes angedockte Ticket hiesse Popup.
    l0, r0 = m[1][0], sl[1][2]
    senden = [e for e in roh or () if e[1] and TV_RX_SENDEN.search(tv_name_norm(e[0]))
              and l0 - TV_PANEL_RAND - 40 <= (e[1][0] + e[1][2]) // 2 <= r0 + TV_PANEL_RAND + 40
              and reiter_y < (e[1][1] + e[1][3]) // 2 <= reiter_y + 900]
    teile = list(unter) + senden
    xs_l = [m[1][0], sl[1][0]] + [e[1][0] for e in teile]
    xs_r = [m[1][2], sl[1][2]] + [e[1][2] for e in teile]
    ys_t = [m[1][1], sl[1][1]] + [e[1][1] for e in teile]
    ys_b = [m[1][3], sl[1][3]] + [e[1][3] for e in teile]
    links, rechts = min(xs_l) - TV_PANEL_RAND, max(xs_r) + TV_PANEL_RAND
    oben, unten = min(ys_t) - 12, max(ys_b) + 12
    # angedockt vs. Popup (25.09.2026, zweite Fassung — die erste sagte 'Popup', sobald rechts neben
    # dem Ticket noch die Watchlist-Spalte lag): ein Popup schwebt UEBER der Chart-Flaeche, also liegen
    # unter seiner Box im selben x-Band weitere benannte Elemente (Zeitachse, Positions-Reiter, Konto-
    # Leiste); unter einem angedockten Ticket ist nur dessen eigene Spalte. Dazu: endet die Box am
    # rechten Fensterrand (<= 80 px), ist sie in jedem Fall angedockt.
    darunter = sum(1 for e in roh or () if e[1] and links <= (e[1][0] + e[1][2]) // 2 <= rechts
                   and (e[1][1] + e[1][3]) // 2 >= unten + 40)
    rand = (fenster[2] - rechts) if fenster else None
    modus = "angedockt" if ((rand is not None and rand <= 80) or darunter == 0) else "Popup"
    if not unter:
        modus = "Reiter ohne Felder"
    return {"links": links, "rechts": rechts, "oben": oben, "unten": unten, "reiter_y": reiter_y,
            "market": {"text": m[0], "r": tuple(m[1]), "punkt": ((m[1][0] + m[1][2]) // 2, (m[1][1] + m[1][3]) // 2)},
            "labels": len(unter), "ohne_felder": not unter, "modus": modus, "darunter": darunter, "rand_rechts": rand,
            "spur": (f"Panel: {modus} @{links},{oben} {rechts - links}x{unten - oben} ({len(unter)} Beschriftungen, "
                     f"{darunter} Elemente darunter, rechts frei {rand if rand is not None else '?'} px)")}


def tv_im_panel(roh, bereich, muster, y_von=None, y_bis=None):
    """Elemente im x-Bereich des Panels, deren Name passt; innerste, ohne Doppelte."""
    kand = []
    for e in roh or ():
        if not e[1] or not muster.search(tv_name_norm(e[0])):
            continue
        l, t, r, b = e[1]
        mx, my = (l + r) // 2, (t + b) // 2
        if not (bereich["links"] <= mx <= bereich["rechts"]):
            continue
        if (y_von is not None and my < y_von) or (y_bis is not None and my > y_bis):
            continue
        kand.append({"text": tv_name_norm(e[0])[:80], "typ": e[2] if len(e) > 2 else "", "r": (l, t, r, b), "punkt": (mx, my)})
    out = []
    for a in kand:
        ar = a["r"]
        if any(x is not a and x["r"] != ar and x["r"][0] >= ar[0] - 2 and x["r"][1] >= ar[1] - 2
               and x["r"][2] <= ar[2] + 2 and x["r"][3] <= ar[3] + 2 for x in kand):
            continue
        if not any(c["r"] == ar for c in out):
            out.append(a)
    return out


def tv_feld_unter(felder_r, label_r, bereich, max_abstand=70):
    """Index des Eingabefelds DIREKT UNTER einer Beschriftung: im Panel, Oberkante
    bis max_abstand unter der Beschriftung; bei mehreren das LINKE (rechts daneben
    steht das Umrechnungsfeld 'price'/'ticks'). -> Index oder None"""
    bestes, schluessel = None, None
    for i, r in enumerate(felder_r or ()):
        if not r:
            continue
        l, t, rr, b = r
        if not (bereich["links"] <= (l + rr) // 2 <= bereich["rechts"]):
            continue
        abstand = t - label_r[3]
        if abstand < -6 or abstand > max_abstand:
            continue
        k = (abstand // 12, l)
        if schluessel is None or k < schluessel:
            bestes, schluessel = i, k
    return bestes


def tv_label_mit_feld(labels, felder_r, bereich):
    """Aus mehreren gleichnamigen Beschriftungen die nehmen, unter der ein
    Eingabefeld sitzt — bei mehreren die oberste. -> (label, feld_index) oder (None, None)"""
    for lab in sorted(labels or (), key=lambda e: e["r"][1]):
        i = tv_feld_unter(felder_r, lab["r"], bereich)
        if i is not None:
            return lab, i
    return None, None


def tv_feld_ohne_label(felder_r, werte, bereich, y_von):
    """Rueckfall ohne Beschriftung (25.09.2026, neues TradingView-Layout: 'Einheiten' als
    Aufklappmenue): das OBERSTE (dann linkeste) Eingabefeld im Panel unterhalb der
    Markt-Reiterzeile, in dem eine Zahl steht = Units. -> Index oder None"""
    bestes, schluessel = None, None
    for i, r in enumerate(felder_r or ()):
        if not r:
            continue
        l, t, rr, b = r
        if not (bereich["links"] <= (l + rr) // 2 <= bereich["rechts"]) or t <= y_von:
            continue
        if tv_zahl_lesen(werte[i] if i < len(werte or ()) else "") is None:
            continue
        k = (t // 12, l)
        if schluessel is None or k < schluessel:
            bestes, schluessel = i, k
    return bestes


def tv_schalter_zeilen(schalter, bereich, y_von):
    """Umschalter im Panel unterhalb von y_von, von oben nach unten (Take Profit vor
    Stop Loss — so steht es im Ticket). -> [rect, ...]"""
    out = []
    for r, _an in schalter or ():
        if r[0] < bereich["links"] - 10 or r[2] > bereich["rechts"] + 10:
            continue
        if (r[1] + r[3]) // 2 <= y_von:
            continue
        out.append(tuple(r))
    return sorted(out, key=lambda r: (r[1], r[0]))


def tv_panel_inventar(roh, bereich, max_n=10):
    """Die ersten Elemente UNTER der Reiterzeile im Panel als 'Typ:Name@l,t,r,b' — kommt
    in die Fehlermeldung, damit beim naechsten Fehlschlag nicht geraten werden muss,
    wie TradingView die Beschriftungen jetzt nennt (25.09.2026)."""
    out = []
    for e in sorted((x for x in roh or () if x[1]), key=lambda x: (x[1][1], x[1][0])):
        l, t, r, b = e[1]
        if not (bereich["links"] <= (l + r) // 2 <= bereich["rechts"]) or (t + b) // 2 <= bereich["reiter_y"]:
            continue
        out.append(f"{(e[2] if len(e) > 2 else '') or '?'}:{str(e[0]).strip()[:28]}@{l},{t},{r},{b}")
        if len(out) >= max_n:
            break
    return " | ".join(out) or "nichts unter der Reiterzeile"


def tv_wert_nachlesen(lesen, soll, warten, versuche=3, toleranz=0.005):
    """Getippten Wert zuruecklesen, mit Nachlesen statt sofortigem Abbruch (25.09.2026, Finns Lauf auf
    pc-8jcrsm: 'Stop loss: im Feld steht '?' statt 250.0' — direkt nach dem Tippen baut TradingView die
    Zeile neu auf, fuer einen Moment steht unter der Beschriftung GAR KEIN Eingabefeld (das '?'); der zweite
    Versuch eine Minute spaeter lief durch). lesen() -> Zahl | None (None = Feld nicht da/Wert unlesbar),
    warten() = Pause mit Streuung (_warte). Bis zu `versuche` Lesungen, dazwischen warten.
    -> (ok, ist, n_lesungen)   ist = letzte lesbare Zahl oder None"""
    ist, n = None, 0
    for i in range(max(1, int(versuche))):
        if i:
            warten()
        n += 1
        wert = lesen()
        if wert is not None:
            ist = wert
            if abs(float(wert) - float(soll)) <= toleranz:
                return True, wert, n
    return False, ist, n


def tv_order_plan(cmd):
    """Befehl -> (plan, fehler). plan = {'richtung','menge','tp','sl'}; tp/sl None = aus."""
    r = str(cmd.get("richtung") or "").strip().lower()
    if r not in ("buy", "sell"):
        return None, "Richtung fehlt (buy/sell)"
    menge = tv_zahl_lesen(cmd.get("volumen"))
    if not menge or menge <= 0 or abs(menge - round(menge)) > 1e-9:
        return None, f"Menge '{cmd.get('volumen')}' ist keine ganze Kontraktzahl"
    tp, sl = tv_zahl_lesen(cmd.get("tp_usd")), tv_zahl_lesen(cmd.get("sl_usd"))
    return {"richtung": r, "menge": int(round(menge)),
            "tp": tp if tp and tp > 0 else None, "sl": sl if sl and sl > 0 else None}, ""


TV_RX_POS_SYMBOL = re.compile(r"^symbol$", re.I)
TV_RX_POS_SEITE = re.compile(r"^(side|seite)\b", re.I)
TV_RX_POS_MENGE = re.compile(r"^(qty|quantity|menge|anzahl)\b", re.I)
TV_RX_POS_LONGSHORT = {"buy": re.compile(r"^(long|buy|kauf)", re.I), "sell": re.compile(r"^(short|sell|verkauf)", re.I)}


# 'Positions' / 'Position' — und seit 24.09.2026 (UIA-Weg ohne Reader, Stub mit
# deutscher Oberflaeche) auch 'Positionen': Seite/Menge/Durchschn. hatten schon
# deutsche Alternativen, nur der Reiter-Anker nicht — ohne ihn gab es auf einer
# deutschen TradingView-Oberflaeche keine Positions-Tabelle, weder fuer den
# Order-Beweis noch fuer tvlesen/tvclose.
TV_RX_POS_TAB = re.compile(r"^position(s|en)?$", re.I)


def tv_positions_kopf(roh, anker=None):
    """Kopfzelle 'Symbol' der Positions-Tabelle samt 'Side'/'Qty' derselben Zeile
    — die Anker-Regel aus tv_positions_tabelle, am 24.09.2026 herausgezogen,
    weil tvclose (Orbit V2 schliessen) dieselbe Zeile braucht, ohne Mengen zu
    summieren. Regel unveraendert: 'Symbol' in der Zeile unter einem Reiter
    'Positions' (max. 120 px darueber, grob gleiche linke Kante) — oder dort,
    wo der Anker eines frueheren Blicks sass (+-20 px).
    -> (rs, rd|None, rq|None) oder None."""
    els = [(str(e[0]).strip(), e[1]) for e in roh or () if e[1]]
    mitte_y = lambda r: (r[1] + r[3]) // 2
    tabs = [r for n, r in els if TV_RX_POS_TAB.search(n)]
    for ns, rs in els:
        if not TV_RX_POS_SYMBOL.search(ns):
            continue
        # ein Positions-Reiter DARUEBER (hoechstens 120 px), grob gleiche linke Kante —
        # oder die Zelle sitzt dort, wo sie beim Vorher-Blick mit Reiter sass
        gleich = bool(anker) and abs(rs[0] - anker[0]) <= 20 and abs(rs[1] - anker[1]) <= 20
        if not gleich and not any(0 < mitte_y(rs) - mitte_y(t) <= 120 and abs(t[0] - rs[0]) <= 120 for t in tabs):
            continue
        seiten = [r for n, r in els if TV_RX_POS_SEITE.search(n) and abs(mitte_y(r) - mitte_y(rs)) <= 14 and r[0] > rs[0]]
        mengen = [r for n, r in els if TV_RX_POS_MENGE.search(n) and abs(mitte_y(r) - mitte_y(rs)) <= 14 and r[0] > rs[0]]
        rd = min(seiten, key=lambda r: r[0]) if seiten else None
        rq = min((r for r in mengen if not rd or r[0] > rd[0]), key=lambda r: r[0], default=None)
        return rs, rd, rq
    return None


def tv_positions_zeilen(roh, kopf, symbol, richtung=None):
    """Zeilen der Positions-Tabelle mit der Symbol-Wurzel (24.09.2026, fuer
    tvclose). Dieselben Regeln wie die Zeilen-Schleife in tv_positions_tabelle:
    unter der Kopfzeile, in der Symbol-Spalte, ein Wort, eine Zeile je 10 px.
    'richtung' (buy/sell) schliesst NUR Zeilen aus, deren Seiten-Spalte lesbar
    ist und BEWIESEN die Gegenseite zeigt — ohne Spalte oder mit unlesbarer
    Seite zaehlt jede Zeile der Wurzel (die Seite ist dann ehrlich unbekannt).
    -> [{'y', 'symbol', 'r', 'seite'|None}]"""
    if not kopf:
        return []
    rs, rd, rq = kopf
    els = [(str(e[0]).strip(), e[1]) for e in roh or () if e[1]]
    mitte_y = lambda r: (r[1] + r[3]) // 2
    spalten = bool(rd and rq)
    root = tv_symbol_root(symbol)
    x_bis = (rd[0] - 10) if rd else (rs[0] + 160)
    out, gesehen = [], []
    for n, r in els:
        y = mitte_y(r)
        if y <= mitte_y(rs) + 8 or not (rs[0] - 30 <= r[0] < x_bis):
            continue
        if " " in n or not root or tv_symbol_root(n) != root or any(abs(y - g) <= 10 for g in gesehen):
            continue
        seite = None
        if spalten:
            s_el = [n2 for n2, r2 in els if abs(mitte_y(r2) - y) <= 12 and rd[0] - 30 <= r2[0] < rq[0] - 10]
            seite = s_el[0][:20] if s_el else None
            gegen = tv_gegenseite(richtung)
            if gegen and any(TV_RX_POS_LONGSHORT[gegen].search(n2) for n2 in s_el):
                continue
        gesehen.append(y)
        out.append({"y": y, "symbol": n[:30], "r": tuple(r), "seite": seite})
    return out


def tv_positions_tabelle(roh, symbol, richtung, anker=None):
    """Positions-Tabelle unten im TradingView-Konto-Bereich lesen (4b, 22.09.2026,
    Finns erster scharfer Lauf: "es drueckt nicht drauf" — der Klick hing am
    Positions-Reader, und der ist bei ihm PAUSIERT, weil Duplikium kopiert. Der
    Beweis darf deshalb nicht am Reader haengen).
    ANKER (seit dem Remote-Lauf 22.09.2026 01:39: Chrome meldete den Kopf
    'Symbol' als DataItem, 'Side'/'Qty' aber unter KEINEM Namen — der Klick war
    raus, die Order lag, der Beweis sagte 'nicht lesbar'): die Zelle 'Symbol' in
    der UNTEREN Fensterhaelfte, ueber der ein Reiter 'Positions' steht. Die
    Watchlist rechts hat auch 'Symbol', aber keinen Positions-Reiter darueber.
    'Side' und 'Qty' auf derselben Zeile sind OPTIONAL: mit ihnen wird Richtung
    und Menge gelesen, ohne sie zaehlt jede Zeile mit der Symbol-Wurzel in der
    Symbol-Spalte (Tradovate nettet pro Symbol — eine NEUE Zeile ist eine neue
    Position; die Gegenrichtung auf einer bestehenden gibt keine neue Zeile und
    damit ehrlich UNKLAR).
    anker = Kopfzelle 'Symbol' aus einem FRUEHEREN Blick (22.09.2026 09:50, Finns
    Lauf: nach dem Klick decken TradingViews Meldungen die Reiter-Zeile ab —
    'kein Reiter Positions zu sehen' — obwohl die Tabelle darunter unveraendert
    steht). Steht die Symbol-Zelle noch an derselben Stelle (+-20 px), gilt sie
    ohne Reiter.
    -> {'menge': Summe, 'zeilen': n, 'spalten': bool, 'anker': rect} oder None ohne Anker."""
    els = [(str(e[0]).strip(), e[1]) for e in roh or () if e[1]]
    mitte_y = lambda r: (r[1] + r[3]) // 2
    # Kopfzeile: seit 24.09.2026 in tv_positions_kopf (tvclose braucht dieselbe
    # Anker-Regel, ohne die Mengen zu summieren) — Logik unveraendert.
    kopf = tv_positions_kopf(roh, anker)
    if not kopf:
        return None
    rs, rd, rq = kopf
    spalten = bool(rd and rq)
    root = tv_symbol_root(symbol)
    summe, zeilen, gesehen = 0.0, 0, []
    x_bis = (rd[0] - 10) if rd else (rs[0] + 160)
    for n, r in els:
        y = mitte_y(r)
        if y <= mitte_y(rs) + 8 or not (rs[0] - 30 <= r[0] < x_bis):
            continue
        if " " in n or tv_symbol_root(n) != root or any(abs(y - g) <= 10 for g in gesehen):
            continue
        if spalten and not any(TV_RX_POS_LONGSHORT[richtung].search(n2) and abs(mitte_y(r2) - y) <= 12
                               and rd[0] - 30 <= r2[0] < rq[0] - 10 for n2, r2 in els):
            continue
        gesehen.append(y)
        zeilen += 1
        if spalten:
            # Menge: der Text auf derselben Zeile, der der Qty-Spalte am naechsten steht
            kand = [(abs(r2[0] - rq[0]), tv_zahl_lesen(n2)) for n2, r2 in els
                    if abs(mitte_y(r2) - y) <= 12 and abs(r2[0] - rq[0]) <= 90 and tv_zahl_lesen(n2) is not None]
            summe += abs(min(kand)[1]) if kand else 0.0
    return {"menge": summe, "zeilen": zeilen, "spalten": spalten, "anker": tuple(rs)}


def tv_positions_zone(roh, max_n=24):
    """Fuer die Meldung: ALLE Namen im Band der Positions-Tabelle (ab dem Reiter
    'Positions' abwaerts, linke Fensterhaelfte) — damit der naechste Anker aus
    Finns Meldungstext nachgezogen werden kann, statt zu raten."""
    els = [(str(e[0]).strip(), e[1], e[2] if len(e) > 2 else "") for e in roh or () if e[1]]
    tabs = [r for n, r, _t in els if TV_RX_POS_TAB.search(n)]
    if not tabs:
        return "kein Reiter 'Positions' zu sehen"
    t = min(tabs, key=lambda r: r[1])
    out = []
    for n, r, typ in sorted(els, key=lambda e: (e[1][1], e[1][0])):
        if r[1] >= t[1] - 4 and r[0] < t[0] + 900 and len(n) <= 30:
            out.append(f"{typ}:{n}@{r[0]},{r[1]}")
        if len(out) >= max_n:
            break
    return " | ".join(out) or "nichts unter dem Reiter"


TV_RX_MELDUNG = re.compile(r"\b(order (placed|filled|executed)|position opened|filled)\b", re.I)


def tv_order_meldungen(roh, symbol):
    """TradingViews eigene Order-Meldungen (Toasts). Steht ein Symbol im Text, muss
    es die Wurzel des Plans sein; OHNE Symbol im Text zaehlt die Meldung trotzdem
    (22.09.2026 09:50, Finns Lauf: TradingView setzt den Symbol-Namen als EIGENEN
    Knoten neben 'Take Profit order placed on' — der Text selbst traegt ihn nicht;
    gegen alte Meldungen schuetzt der Vorher/Nachher-Vergleich des Aufrufers).
    -> Liste der Texte. Rein rechnend."""
    root = tv_symbol_root(symbol)
    out = []
    for e in roh or ():
        n = str(e[0]).strip()
        if not e[1] or not TV_RX_MELDUNG.search(n):
            continue
        # Symbol-artige Woerter im Text (Buchstaben, dann Ziffern: NQZ6, MNQZ2026, BTC1!) —
        # gibt es welche, muss eines die Plan-Wurzel tragen; Kurse ('30,858.25') zaehlen nicht.
        woerter = [tv_symbol_root(x) for x in re.findall(r"\b[A-Za-z]{1,6}[A-Za-z0-9]*\d[A-Za-z0-9!]*", n)]
        if root and woerter and root not in woerter:
            continue
        if n not in out:
            out.append(n)
    return out


def tv_ist_scharf(cmd):
    """Schritt 4b (22.09.2026): scharf NUR mit der ausdruecklichen Marke 'scharf'
    — und nie, wenn 'probe' gesetzt ist. Die Marke schickt erst das Frontend,
    das auch 'Order wird platziert' anzeigt: ein am PC noch altes Frontend
    (Text 'Probelauf, kein Kauf-Klick') loest so mit dem neuen Bot KEINE Order
    aus. Ueber die Bruecke kommt der Wert als Text ('1'), vom Panel als bool —
    'false'/'0'/leer zaehlen nie als ja."""
    def ja(v):
        return v is True or str(v).strip().lower() in ("1", "true", "ja")
    return ja(cmd.get("scharf")) and not ja(cmd.get("probe"))


def tv_order_schritt(w, cmd, trail, erg=None):
    """Order-Panel ausfuellen und beweisen (4a) — und NUR mit der Marke 'scharf'
    den Kauf-Knopf genau EINMAL klicken und die Position beweisen (4b).
    erg (dict) bekommt 'gesendet'/'bestaetigt'/'menge'/'einstieg'/'tv_symbol'.
    -> (ok, msg)"""
    if erg is None:
        erg = {}
    plan, fehler = tv_order_plan(cmd)
    if not plan:
        return False, fehler
    try:
        from pywinauto import keyboard
    except ImportError:
        return False, "pywinauto fehlt"
    # 25.09.2026: ComboBox/MenuItem/Group/Custom dazu — im neuen TradingView-Layout ist
    # 'Einheiten ▾' ein Aufklappmenue, 'Take Profit, $ ▾'/'Stop-Loss, $ ▾' ebenso; als reine
    # Textknoten waren sie nicht mehr zu sehen ('Beschriftung Units nicht gefunden', obwohl
    # Reiter und Seite sauber geklickt wurden).
    typen = ("Text", "Button", "TabItem", "RadioButton", "CheckBox", "ListItem", "ComboBox", "MenuItem", "Group", "Custom",
             "Hyperlink", "Menu", "List", "Pane", "Image")   # 25.09.2026 (Deutsch): alles, was einen Namen tragen kann

    fenster = _tv_fenster_rect(w)

    def blick():
        roh = _tv_uia_roh(w, typen)
        return roh, tv_panel_bereich(roh, fenster)

    # --- Panel offen? sonst Shift+T (offizieller TradingView-Hotkey, UMSCHALTER:
    # nur druecken, wenn das Panel nachweislich fehlt) ------------------------
    # UMSCHALTER-FALLE (22.09.2026, Finns Lauf + seine Diagnose: "vllt war das
    # Order-Panel schon da und er hat es dann weg gemacht" — genau so war es):
    # direkt nach dem Watchlist-Klick baut TradingView das Panel NEU auf; ein
    # einzelner Blick in diesem Moment sah keine Reiter, Shift+T hat das OFFENE
    # Panel geschlossen. Ein zweiter Start oeffnete es wieder — die Erkennung
    # selbst stimmt also. Deshalb: 'Panel fehlt' gilt erst nach VIER leeren
    # Blicken ueber mindestens 3 s, und NIE, solange irgendeine Panel-
    # Beschriftung (Take profit / Stop loss / Units) zu sehen ist.
    roh, ber = blick()
    t_leer, leer = time.time(), 0
    while not ber:
        teile = any(x[1] and (TV_RX_TP.search(tv_name_norm(x[0])) or TV_RX_SL.search(tv_name_norm(x[0])) or TV_RX_UNITS.search(tv_name_norm(x[0])))
                    for x in roh)
        leer = 0 if teile else leer + 1
        if teile and time.time() - t_leer > 10.0:
            return False, ("Vom Order-Panel sind Beschriftungen zu sehen, aber die Reiter-Zeile 'Market … Stop "
                           "Limit' nicht — es wird NICHT umgeschaltet. Gesehen: " + tv_uia_spur(roh))
        if leer >= 4 and time.time() - t_leer >= 3.0:
            break
        _warte(0.3, 0.15)
        roh, ber = blick()
    if not ber:
        fr = _tv_fenster_rect(w)
        if not fr:
            return False, "TradingView-Fenster ohne Rechteck."
        # in den Chart klicken, damit der Hotkey dort ankommt — mittig-links, weit weg
        # von den Schnell-Knoepfen SELL/BUY oben links
        _tv_uia_klick({"punkt": (fr[0] + int((fr[2] - fr[0]) * 0.35), fr[1] + int((fr[3] - fr[1]) * 0.6))},
                      "Chart (Fokus)", trail)
        _warte(0.25, 0.15)
        keyboard.send_keys("+t")
        trail.append("Order-Panel per Shift+T geoeffnet")
        ende = time.time() + 6.0
        while time.time() < ende and not ber:
            _warte(0.6, 0.3)
            roh, ber = blick()
        if not ber:
            return False, ("Das Order-Panel ist nicht zu sehen (Reiter 'Market … Stop Limit' fehlen), auch "
                           "nach Shift+T nicht. Gesehen: " + tv_uia_spur(roh))

    # --- Reiter-Zeile da, aber keine Feld-Beschriftung darunter (25.09.2026, Popup-Fall):
    # kurz warten (Panel im Aufbau), dann ABBRUCH — kein Klick auf Rueckfall-Koordinaten.
    t_felder = time.time()
    while ber.get("ohne_felder"):
        if time.time() - t_felder > 4.0:
            # Beschriftungen fehlen, aber ZAHLENFELDER unter der Reiterzeile im Reiter-Bereich? Dann ist das
            # Ticket da und TradingView nennt die Beschriftungen nur anders → weiter, feld_zu faehrt den
            # Rueckfall (oberstes Zahlenfeld = Units, Umschalter-Zeilen = TP/SL) und die Spur sagt es.
            eds_ = _tv_uia_felder(w) or []
            rs_ = []
            for e_ in eds_:
                try:
                    r_ = e_.rectangle()
                    rs_.append((r_.left, r_.top, r_.right, r_.bottom))
                except Exception:
                    rs_.append(None)
            if tv_feld_ohne_label(rs_, [_tv_edit_wert(e_) for e_ in eds_], ber, ber["reiter_y"]) is not None:
                trail.append(f"{ber.get('spur')} — keine Beschriftung lesbar, aber Zahlenfelder unter den Reitern: "
                             "weiter im Rueckfall")
                break
            return False, ("Order-Panel nicht gefunden: die Reiter-Zeile 'Market … Stop Limit' steht bei "
                           f"@{ber['links']},{ber['reiter_y']}, aber darunter ist keine Beschriftung Units/Take profit/"
                           "Stop loss zu sehen (losgeloestes Popup? in TradingView ueber das Andock-Symbol in der "
                           "Kopfzeile des Order-Tickets → Andocken). Nichts geklickt, nichts getippt. Gesehen: "
                           + tv_uia_spur(roh))
        _warte(0.4, 0.2)
        roh, ber2 = blick()
        ber = ber2 or ber
    if not ber.get("ohne_felder"):
        trail.append(ber.get("spur") or "Panel: ?")

    # --- Panel auf dem RICHTIGEN Symbol und RUHIG? (23.09.2026 03:19, Finns Lauf:
    # Watchlist NQ1! geklickt, Tab-Titel nach 0,7 s auf NQ — das Order-Panel hing aber
    # noch am alten MNQ. Units/TP/SL landeten im MNQ-Panel, erst der Knopf-Beweis
    # ganz am Ende stoppte den Lauf: "Auf dem Knopf steht nicht NQ ('Buy 2 MNQZ6
    # MARKET')". Zweiter Lauf 03:54 mit der ersten Fassung dieser Wartestelle: der
    # Senden-Knopf war VOR dem Ausfuellen 8 s lang gar nicht lesbar -> Absage, obwohl
    # das Panel da war. Finn: "mach das erst, wenn er das Panel auch so sieht".)
    # Deshalb zwei Bedingungen, keine davon eine Falle:
    #  1. RUHE: die Beschriftungen unter der Reiter-Zeile (Zahlen ausgeblendet) sind
    #     in zwei Blicken hintereinander gleich — TradingView baut das Panel nach dem
    #     Symbolwechsel verzoegert neu auf, ein halb gebautes Panel ist nie ruhig.
    #  2. SYMBOL: ist der Senden-Knopf lesbar ('Buy 1 MNQZ6 MARKET' steht schon vor
    #     dem Ausfuellen drauf), muss er die Plan-Wurzel tragen. Zeigt er 8 s lang ein
    #     anderes Symbol -> Absage ohne einen Tipp ins falsche Panel. Ist er (noch)
    #     nicht lesbar, wird NICHT abgesagt: nach 3 s Ruhe geht es weiter wie frueher,
    #     der Knopf-Beweis am Ende bleibt die letzte Sperre. Die Spur nennt, was unter
    #     den Reitern zu sehen war — damit der naechste Fall lesbar ist.
    ziel_root = tv_symbol_root(cmd.get("symbol"))

    def _panel_namen(roh_, ber_):
        out = []
        for e in roh_ or ():
            if not e[1]:
                continue
            l, t, r, b = e[1]
            if ber_["links"] <= (l + r) // 2 <= ber_["rechts"] and (t + b) // 2 >= ber_["reiter_y"]:
                out.append(re.sub(r"[\d.,]+", "#", str(e[0]).strip())[:40])
        return tuple(out)

    t_sym, letzte, knopf_falsch = time.time(), None, None
    while True:
        namen = _panel_namen(roh, ber)
        ruhig = letzte is not None and namen == letzte
        kn = tv_im_panel(roh, ber, TV_RX_SENDEN, y_von=ber["reiter_y"])
        passt = any(tv_symbol_root(wort) == ziel_root for k in kn for wort in k["text"].split()) if (kn and ziel_root) else None
        knopf_falsch = (kn[0]["text"][:40] if kn else None) if passt is False else None
        dauer = time.time() - t_sym
        if ruhig and (passt or (passt is None and dauer >= 3.0)):
            if passt is None:
                trail.append("Order-Panel ruhig, Senden-Knopf vor dem Ausfuellen nicht lesbar — weiter, Beweis am Ende "
                             f"(unter den Reitern: {', '.join(namen[:14]) or 'nichts'})")
            elif dauer > 0.5:
                trail.append(f"Order-Panel zog nach {dauer:.1f}s auf {ziel_root} nach")
            break
        if dauer > 8.0:
            if knopf_falsch:
                return False, (f"Das Order-Panel steht nicht auf {ziel_root} — der Knopf unten zeigt auch nach 8 s "
                               f"noch '{knopf_falsch}'. Nichts getippt, nichts gesendet.")
            trail.append("Order-Panel wurde 8 s nicht ruhig — weiter, Beweis am Ende "
                         f"(unter den Reitern: {', '.join(namen[:14]) or 'nichts'})")
            break
        letzte = namen
        _warte(0.4, 0.2)
        roh, ber2 = blick()
        ber = ber2 or ber

    # --- Market --------------------------------------------------------------
    ok, f = _tv_uia_klick(ber["market"], "Reiter Market", trail)
    if not ok:
        return False, f
    _warte(0.2, 0.1)      # 0,5 -> 0,2 (22.09.2026 19:0x, Finn: 'vor Buy/Sell, TP und Lots noch Leerzeit')

    # --- Seite: Buy/Sell im Seiten-Kasten UEBER der Reiter-Zeile -------------
    roh, ber2 = blick()
    ber = ber2 or ber
    seite = tv_im_panel(roh, ber, TV_RX_SEITE[plan["richtung"]], y_von=ber["reiter_y"] - 150, y_bis=ber["reiter_y"] - 12)
    if len(seite) != 1:
        return False, (f"'{plan['richtung'].upper()}' im Seiten-Kasten des Order-Panels nicht eindeutig "
                       f"({len(seite)} Treffer). Gesehen: " + tv_uia_spur(roh))
    ok, f = _tv_uia_klick(seite[0], f"Seite {plan['richtung'].upper()}", trail)
    if not ok:
        return False, f
    _warte(0.3, 0.15)

    # --- Felder ueber ihre Lage zur Beschriftung -----------------------------
    def felder():
        eds = _tv_uia_felder(w)                 # EIN Aufruf; None = Weg geht nicht -> alter Weg
        if eds is None:
            try:
                eds = [e for e in w.descendants(control_type="Edit")
                       if not hasattr(e, "is_visible") or e.is_visible()]
            except Exception:
                return [], []
        rs = []
        for e in eds:
            try:
                r = e.rectangle()
                rs.append((r.left, r.top, r.right, r.bottom))
            except Exception:
                rs.append(None)
        return eds, rs

    merk = {"units_unten": None}   # Unterkante des Units-Felds: TP/SL-Schalter liegen darunter

    def feld_zu(muster, name, lab_bekannt=None):
        # lab_bekannt (22.09.2026 19:0x): nach dem Tippen die Beschriftung nicht neu suchen —
        # sie bewegt sich nicht; nur die Felder neu lesen (ein Scan statt zwei je Feld).
        roh_ = None
        if lab_bekannt is not None:
            labels = [lab_bekannt]
        else:
            roh_, _b = blick()
            labels = tv_im_panel(roh_, ber, muster, y_von=ber["reiter_y"])
        if not labels:
            # RUECKFALL OHNE BESCHRIFTUNG (25.09.2026, Finns Lauf im neuen Layout): Units = das
            # oberste Zahlenfeld unter der Markt-Reiterzeile; Take Profit / Stop Loss = die
            # erste / zweite Umschalter-Zeile unter dem Units-Feld (Feld direkt darunter).
            # Beweis bleibt wie immer das Zuruecklesen des getippten Werts. Die Einheit ($)
            # kann so NICHT geprueft werden — das steht in der Spur.
            eds, rs = felder()
            if muster is TV_RX_UNITS:
                werte = [_tv_edit_wert(e) for e in eds]
                i = tv_feld_ohne_label(rs, werte, ber, ber["reiter_y"])
                if i is not None:
                    r = rs[i]
                    lab = {"text": "Units (ohne Beschriftung)", "typ": "?", "r": (r[0], r[1] - 22, r[2], r[1] - 2),
                           "punkt": ((r[0] + r[2]) // 2, r[1] - 12)}
                    trail.append(f"Beschriftung '{name}' nicht gefunden — Rueckfall: oberstes Zahlenfeld unter den "
                                 f"Reitern @{r[0]},{r[1]} (Wert '{werte[i]}')")
                    merk["units_unten"] = r[3]
                    return (eds[i], r), lab, ""
            else:
                sch = _tv_uia_schalter(w) or []
                zeilen = tv_schalter_zeilen(sch, ber, merk["units_unten"] or ber["reiter_y"])
                idx = 0 if muster is TV_RX_TP else 1
                if len(zeilen) > idx:
                    z = zeilen[idx]
                    lab = {"text": f"{name}, $ (ohne Beschriftung — Einheit unbestaetigt)", "typ": "?",
                           "r": (ber["links"] + 10, z[1], z[0] - 6, z[3]), "punkt": ((ber["links"] + z[0]) // 2, (z[1] + z[3]) // 2)}
                    i = tv_feld_unter(rs, lab["r"], ber)
                    if i is not None:
                        trail.append(f"Beschriftung '{name}' nicht gefunden — Rueckfall: {idx + 1}. Umschalter-Zeile unter "
                                     f"Units @{z[0]},{z[1]}, Feld darunter @{rs[i][0]},{rs[i][1]}; Einheit $ NICHT geprueft")
                        return (eds[i], rs[i]), lab, ""
            if roh_ is None:
                roh_, _b = blick()
            return None, None, (f"Beschriftung '{name}' im Order-Panel nicht gefunden (auch kein Rueckfall ueber "
                                f"Zahlenfeld/Umschalter). Unter der Reiterzeile: " + tv_panel_inventar(roh_, ber))
        eds, rs = felder()
        # MEHRERE Treffer sind normal (22.09.2026, Finns Lauf: "'Units' nicht eindeutig
        # (2 Treffer)" — TradingView fuehrt die Beschriftung als Text UND als Name des
        # Auswahlmenues daneben). Es zaehlt die Beschriftung, unter der wirklich ein
        # Eingabefeld sitzt; bei mehreren die OBERSTE.
        lab, i = tv_label_mit_feld(labels, rs, ber)
        if lab is None:
            return None, labels[0], f"Eingabefeld unter '{name}' nicht gefunden ({len(labels)} Beschriftungen)."
        return (eds[i], rs[i]), lab, ""

    def schalter(lab):
        """Echter Schalter-Zustand zur Beschriftung. -> (an|None, rect|None).
        None = kein Umschalter lesbar -> Rueckfall auf 'Feld bedienbar' (alte,
        unsichere Regel; sie wird dann in der Spur genannt)."""
        sch = _tv_uia_schalter(w)
        if sch is None:
            return None, None
        r, z = tv_schalter_zu(sch, lab["r"], ber)
        return (z, r) if r else (None, None)

    def an(feld):
        try:
            return bool(feld[0].is_enabled())
        except Exception:
            return None

    def setze_wert(feld, wert, name):
        r = feld[1]
        _tv_uia_klick({"punkt": (r[0] + max(12, (r[2] - r[0]) // 4), (r[1] + r[3]) // 2)}, f"Feld {name}", trail)
        _warte(0.15, 0.1)
        text = str(int(wert)) if abs(wert - round(wert)) < 1e-9 else ("%.2f" % wert)
        _tv_tippen(text, name, trail)
        keyboard.send_keys("{TAB}")
        _warte(0.3, 0.15)

    def pruefe_wert(muster, name, lab, soll, feld_vorher):
        """Zuruecklesen mit Nachlesen (bis 3 Lesungen, dazwischen 0,3–0,6 s) und EINEM zweiten Tippversuch,
        wenn danach ein lesbarer, aber falscher Wert steht (z. B. '25' statt '250' — abgeschnittene Eingabe).
        Steht gar kein Feld da, wird nicht erneut getippt (wohin auch). -> (ok, ist)"""
        stand = {"feld": feld_vorher}

        def lesen():
            f_, _l, _e = feld_zu(muster, name, lab_bekannt=lab)
            if f_:
                stand["feld"] = f_
            return tv_zahl_lesen(_tv_edit_wert(f_[0])) if f_ else None

        warten = lambda: _warte(0.3, 0.3)
        ok_, ist_, n_ = tv_wert_nachlesen(lesen, soll, warten)
        if ok_:
            if n_ > 1:
                trail.append(f"{name}: Wert {soll:g} erst bei Lesung {n_} bestaetigt (Feld baute sich neu auf)")
            return True, ist_
        if ist_ is not None and stand["feld"]:
            trail.append(f"{name}: '{ist_:g}' statt {soll:g} nach {n_} Lesungen — tippe einmal neu")
            setze_wert(stand["feld"], soll, name)
            ok_, ist_, n_ = tv_wert_nachlesen(lesen, soll, warten)
            if ok_:
                return True, ist_
        trail.append(f"{name}: Zuruecklesen gescheitert (letzter Wert {ist_ if ist_ is not None else 'kein Feld'})")
        return False, ist_

    # Units
    feld, _lab, f = feld_zu(TV_RX_UNITS, "Units")
    if not feld:
        return False, f
    if tv_zahl_lesen(_tv_edit_wert(feld[0])) != float(plan["menge"]):
        setze_wert(feld, float(plan["menge"]), "Units")
        ok_u, ist_u = pruefe_wert(TV_RX_UNITS, "Units", _lab, float(plan["menge"]), feld)
        if not ok_u:
            return False, f"Menge {plan['menge']} steht nicht im Feld 'Units' (dort: '{ist_u if ist_u is not None else '?'}')."
    trail.append(f"Units = {plan['menge']}")
    if feld and feld[1] and merk["units_unten"] is None:
        merk["units_unten"] = feld[1][3]

    # Take Profit / Stop Loss
    for muster, name, soll in ((TV_RX_TP, "Take profit", plan["tp"]), (TV_RX_SL, "Stop loss", plan["sl"])):
        feld, lab, f = feld_zu(muster, name)
        if not feld:
            return False, f
        if soll is not None and "$" not in lab["text"]:
            # Einheit MUSS Geld sein: '300' in Ticks oder % waere eine voellig andere Distanz
            return False, f"'{lab['text']}' steht nicht auf $ — der Wert {soll} waere dort etwas anderes. Im Panel auf $ stellen."
        will_an = soll is not None
        ist_an, sch_r = schalter(lab)
        echt = ist_an is not None
        if not echt:
            # kein Umschalter lesbar: alte Regel 'Feld bedienbar' — unsicher (bei
            # TradingView ist das Feld auch bei AUS bedienbar), wird in der Spur genannt.
            ist_an = an(feld)
            trail.append(f"Schalter {name}: kein Umschalter lesbar, Feld {'bedienbar' if ist_an else 'gesperrt'}")
            if ist_an is None:
                return False, f"Schalter-Zustand von '{name}' nicht lesbar."
        if will_an:
            # AN = ins Feld klicken + Wert tippen (Finn 22.09.2026 01:5x: 'man muss nur
            # einmal in das Input-Feld reindruecken, dann zaehlt das schon als aktiv' —
            # genau so ging der TP im Lauf davor an). Uebersprungen NUR, wenn der
            # Schalter nachweislich AN ist und der Wert schon stimmt.
            if not (echt and ist_an and tv_zahl_lesen(_tv_edit_wert(feld[0])) == float(soll)):
                setze_wert(feld, float(soll), name)
                ok_w, ist = pruefe_wert(muster, name, lab, float(soll), feld)
                if not ok_w:
                    return False, f"{name}: im Feld steht '{ist if ist is not None else '?'}' statt {soll}."
            nach, _r = schalter(lab)
            if nach is False:
                return False, f"'{name}' steht auf {soll} $, aber der Schalter ist AUS — die Order ginge ohne {name} raus."
            trail.append(f"{name} = {soll} $ (Schalter {'AN' if nach else 'unlesbar, ins Feld getippt'})")
        elif ist_an:
            # AUS: den Umschalter selbst klicken (echte Lage, sonst Schaetzung am rechten
            # Panelrand) und den Zustand zurueckerlesen.
            if sch_r:
                sx, sy = (sch_r[0] + sch_r[2]) // 2, (sch_r[1] + sch_r[3]) // 2
            else:
                sx, sy = ber["rechts"] - 52, lab["punkt"][1]
            _tv_uia_klick({"punkt": (sx, sy)}, f"Schalter {name} AUS", trail)
            _warte(0.35, 0.15)
            feld, lab, f = feld_zu(muster, name, lab_bekannt=lab)
            if not feld:
                return False, f
            nach, _r = schalter(lab)
            if nach is None:
                nach = an(feld)
            if nach:
                return False, f"Schalter '{name}' liess sich nicht AUS stellen (Klick bei {sx},{sy})."
            trail.append(f"{name} AUS (Schalter geklickt)")
        else:
            trail.append(f"{name} AUS")

    # --- 4b: Vorher-Stand der Positionen, BEVOR irgendetwas gesendet wird -----
    # Gleiche Doktrin wie im alten tvorder-Bau: ohne lebenden Reader gaebe es
    # hinterher keine Bestaetigung, und eine unbestaetigte Order ist genau der
    # Zustand, den der ganze Ablauf vermeiden will. Bestaetigt wird spaeter per
    # DIFFERENZ (vorher/nachher), nie per 'es gibt eine Position'.
    # ERSTER SCHARFER LAUF (22.09.2026 01:12, Finn: "es drueckt nicht drauf" —
    # Meldung 'TV-Reader ist pausiert … NICHT gesendet'): der Reader ist bei ihm
    # mit Absicht PAUSIERT (Duplikium kopiert; ein laufender Reader wuerde den
    # Orbit-Copier ein zweites Mal hedgen lassen). Der Klick darf also nicht am
    # Reader haengen. Beweis-Quellen, in dieser Reihenfolge: (1) Reader, wenn er
    # lebt UND an ist; (2) die Positions-Tabelle unten in TradingView, gelesen
    # mit demselben UIA-Auge wie das Panel; (3) keine → es wird TROTZDEM
    # geklickt, das Ergebnis heisst dann ehrlich 'gesendet, nicht bewiesen'.
    scharf = tv_ist_scharf(cmd)
    typen_pos = typen + ("DataItem", "HeaderItem", "Header", "Custom")
    quelle, vorher = None, None
    if scharf:
        pos_vorher, reader_an = _tv_positionen()
        if pos_vorher is not None and reader_an:
            quelle = "reader"
            vorher = {"menge": tv_menge_summe(pos_vorher, cmd.get("symbol"), plan["richtung"]), "zeilen": 0}
        else:
            roh_p = _tv_uia_roh(w, typen_pos)          # EIN Scan fuer Tabelle UND Meldungen (22.09.2026 18:4x: 2,2 s → ~1 s)
            vorher = tv_positions_tabelle(roh_p, cmd.get("symbol"), plan["richtung"])
            quelle = "tabelle" if vorher else None
        trail.append(f"Beweis-Quelle: {quelle or 'KEINE (Reader aus, Positions-Tabelle nicht zu sehen)'}"
                     + (f", vorher {vorher['menge']:g}" if vorher else ""))
        # Dritter Beweis (22.09.2026 01:50, Finns Screenshot: TradingView meldet unten
        # links selbst 'Take Profit order placed on MNQZ6 · Sell 2 at 30,858.25'; die
        # Positions-Tabelle war da hinter 'Show more' verdeckt): TradingViews EIGENE
        # Meldung nach dem Klick. Gezaehlt werden nur Meldungen, die es VOR dem Klick
        # noch nicht gab (alte bleiben minutenlang stehen).
        roh_v = roh_p if quelle != "reader" else _tv_uia_roh(w, typen)
        toasts_vorher = set(tv_order_meldungen(roh_v, cmd.get("symbol")))
        namen_vorher = {str(e[0]).strip() for e in roh_v if e[1]}

    # --- Beweis am Knopf: er sagt selbst, was er gleich tun wuerde -----------
    roh, _b = blick()
    # UNTER der Stop-Loss-Zeile suchen: der Seiten-Kasten oben heisst sonst auch
    # 'Buy 30,827.75' und saehe aus wie ein Kauf-Knopf.
    knopf = tv_im_panel(roh, ber, TV_RX_SENDEN, y_von=lab["r"][3])
    if len(knopf) != 1:
        return False, (f"Der Kauf-Knopf unten im Panel ist nicht eindeutig ({len(knopf)} Treffer). "
                       "Gesehen: " + tv_uia_spur(roh))
    ok, f = tv_senden_text_passt(knopf[0]["text"], plan["richtung"], plan["menge"])
    if not ok and f.startswith("Menge "):
        # 24.09.2026 00:0x (Finns Screenshot, Auto-Start angehalten): Units stand auf 1, der
        # Knopf sagte trotzdem 'Sell 5 NQZ6 MARKET' — TradingView hatte die Menge nach dem
        # TP/SL-Tippen wieder auf den alten Ticket-Wert gedreht. Einmal Units neu setzen und
        # den Knopf NEU lesen; bleibt es falsch, gilt der Riegel wie bisher (nie mit 5 statt 1
        # klicken). Kein Klick auf den Kauf-Knopf in diesem Zweig.
        trail.append(f"Knopf zeigt andere Menge ('{knopf[0]['text'][:40]}') — Units einmal neu setzen")
        feld_u, _lab_u, f_u = feld_zu(TV_RX_UNITS, "Units")
        if feld_u:
            setze_wert(feld_u, float(plan["menge"]), "Units")
            _warte(0.6, 0.3)
            roh, _b = blick()
            knopf = tv_im_panel(roh, ber, TV_RX_SENDEN, y_von=lab["r"][3])
            if len(knopf) == 1:
                ok, f = tv_senden_text_passt(knopf[0]["text"], plan["richtung"], plan["menge"])
            else:
                ok, f = False, f"Der Kauf-Knopf ist nach dem Menge-Neusetzen nicht eindeutig ({len(knopf)} Treffer)."
    if not ok:
        return False, f
    ziel = tv_symbol_root(cmd.get("symbol"))
    if ziel and not any(tv_symbol_root(wort) == ziel for wort in knopf[0]["text"].split()):
        return False, f"Auf dem Knopf steht nicht {ziel} ('{knopf[0]['text'][:40]}')."
    trail.append(f"Knopf: '{knopf[0]['text'][:50]}'")
    tpsl = f"TP {str(plan['tp']) + ' $' if plan['tp'] else 'aus'}, SL {str(plan['sl']) + ' $' if plan['sl'] else 'aus'}"
    if not scharf:
        return True, (f"PROBELAUF: Order-Panel steht — Knopf zeigt '{knopf[0]['text'][:50]}', {tpsl}. "
                      "NICHT gesendet.")

    # ═══ AB HIER UNUMKEHRBAR (4b, Finn 22.09.2026: "dass nachdem alles
    # eingegeben wurde, TP/SL etc., am Ende Buy/Sell gedrueckt wird") ═════════
    # Geklickt wird GENAU der Knopf, dessen Beschriftung eben bewiesen wurde —
    # derselbe Blick, kein neues Suchen dazwischen — und genau EINMAL. Nach dem
    # Klick gibt es keinen zweiten Versuch: ob die Order liegt, sagt nur der
    # Reader.
    ok, f = _tv_uia_klick(knopf[0], "Order senden", trail)
    if not ok:
        # Der Klick kam nachweislich nicht raus (SendInput abgelehnt) — nichts gesendet.
        return False, f + " — NICHT gesendet."
    erg["gesendet"] = True

    def _avg_fill_nachlauf(sekunden=3.0):
        """Avg Fill Price NACH dem Beweis nachlesen (25.09.2026, erster echter Fusion-Hedge: die
        Order war per TradingView-Meldung bewiesen, 'einstieg' blieb None, der Hedge nahm den
        Feed-Kurs statt des Fills). Quellen: Reader (wenn an), sonst die Positions-Tabelle
        (Spalte 'Avg Fill Price' / 'Durchschnittlicher Erfuellungspreis' ueber TV_RX_POS_EINSTIEG).
        -> (einstieg_text|None, tv_symbol|None, diagnose|None); nie ein Fehler, nur die Spur sagt es.
        Hoechstens `sekunden` (3 s) — jede Sekunde hier verzoegert den Hedge-Open; was hier nicht gelingt,
        holt der naechste Lesebefehl (tvlesen: avg_fill_je_wurzel) nach."""
        root = tv_symbol_root(cmd.get("symbol"))
        ende_ = time.time() + sekunden
        letzt = {"roh": None, "anker": None}
        while True:
            try:
                pos, an_ = _tv_positionen(timeout=1.0)
                if pos is not None and an_:
                    for p_ in pos:
                        if tv_symbol_root(p_.get("symbol")) == root and tv_seite_passt(p_.get("seite"), plan["richtung"]) \
                                and p_.get("einstieg") and tv_geld_lesen(p_.get("einstieg")) is not None:
                            return str(p_.get("einstieg")), p_.get("symbol"), None
                roh_f = _tv_uia_roh(w, typen_pos)
                anker_ = vorher.get("anker") if isinstance(vorher, dict) else None
                letzt.update(roh=roh_f, anker=anker_)
                for z in tv_positions_lesen(roh_f, tv_positions_kopf(roh_f, anker_)):
                    if tv_symbol_root(z.get("symbol")) == root and (not z.get("seite") or tv_seite_passt(z.get("seite"), plan["richtung"])) \
                            and z.get("einstieg") and tv_geld_lesen(z.get("einstieg")) is not None:
                        return str(z.get("einstieg")), z.get("symbol"), None
            except Exception:
                pass
            if time.time() >= ende_:
                diag = tv_tabellen_diagnose(letzt["roh"], letzt["anker"], cmd.get("symbol")) if letzt["roh"] is not None else "keine Tabellen-Lesung"
                return None, None, diag
            _warte(0.5, 0.2)
    trail.append("Senden geklickt — ab hier zaehlt nur noch der Beweis")
    ende = time.time() + 25.0
    while time.time() < ende:
        _warte(0.25, 0.15)
        roh_t = _tv_uia_roh(w, typen)
        neu_t = [t for t in tv_order_meldungen(roh_t, cmd.get("symbol")) if t not in toasts_vorher]
        if neu_t:
            trail.append(f"TradingView meldet: '{neu_t[0][:60]}'")
            einstieg_, sym_, diag_ = _avg_fill_nachlauf()
            erg.update(bestaetigt=True, menge=float(plan["menge"]), einstieg=einstieg_, tv_symbol=sym_)
            trail.append(f"Avg Fill nach der Meldung: {einstieg_ or 'nicht lesbar (3 s)'}"
                         + (f" [{diag_}]" if (diag_ and not einstieg_) else ""))
            return True, (f"Order platziert: {plan['richtung'].upper()} {plan['menge']} {sym_ or cmd.get('symbol')}"
                          + (f" @ {einstieg_}" if einstieg_ else "") + f" · {tpsl} "
                          f"(bewiesen: TradingView-Meldung '{neu_t[0][:60]}')")
        if not quelle:
            continue
        if quelle == "reader":
            pos, _an = _tv_positionen()
            if pos is None:
                continue
            jetzt = {"menge": tv_menge_summe(pos, cmd.get("symbol"), plan["richtung"]), "zeilen": 0}
            treffer = next((p for p in pos
                            if tv_symbol_root(p.get("symbol")) == tv_symbol_root(cmd.get("symbol"))
                            and tv_seite_passt(p.get("seite"), plan["richtung"])), {})
        else:
            jetzt = tv_positions_tabelle(_tv_uia_roh(w, typen_pos), cmd.get("symbol"), plan["richtung"], anker=vorher.get("anker"))
            treffer = {}
            if jetzt is None:
                continue
        # Bestaetigt wird nur der ZUWACHS: mehr Kontrakte — oder (Tabelle) eine neue Zeile.
        if vorher is not None and (jetzt["menge"] - vorher["menge"] >= plan["menge"] - 1e-9 or jetzt["zeilen"] > vorher["zeilen"]):
            zuwachs = jetzt["menge"] - vorher["menge"]
            if not treffer.get("einstieg"):
                e_, s_, d_ = _avg_fill_nachlauf(2.0)
                if e_:
                    treffer = dict(treffer, einstieg=e_, symbol=treffer.get("symbol") or s_)
                    trail.append(f"Avg Fill nachgelesen: {e_}")
                elif d_:
                    trail.append(f"Avg Fill nicht lesbar (2 s) [{d_}]")
            erg.update(bestaetigt=True, menge=zuwachs, einstieg=treffer.get("einstieg"), tv_symbol=treffer.get("symbol"))
            trail.append(f"Position bestaetigt ({quelle}): +{zuwachs:g}")
            return True, (f"Order platziert: {plan['richtung'].upper()} {plan['menge']} "
                          f"{treffer.get('symbol') or cmd.get('symbol')}"
                          + (f" @ {treffer['einstieg']}" if treffer.get("einstieg") else "")
                          + f" · {tpsl} (bewiesen: {'Reader' if quelle == 'reader' else 'Positions-Tabelle'})")
    # Kein Zuwachs in 25 s (oder gar keine Beweis-Quelle): Ablehnung, eine
    # Rueckfrage von TradingView oder eine haengende Verbindung — welches davon,
    # kann der Bot NICHT wissen. Eine Rueckfrage wird bewusst NICHT geraten
    # weggeklickt: was zu sehen ist, steht in der Meldung.
    roh = _tv_uia_roh(w, typen_pos)
    # Fuer den naechsten Anker: was ist seit dem Klick NEU auf dem Schirm?
    neu_seit = [str(e[0]).strip()[:60] for e in roh if e[1] and str(e[0]).strip() not in namen_vorher
                and 2 < len(str(e[0]).strip()) <= 60]
    neu_txt = " | Neu seit dem Klick: " + (" | ".join(list(dict.fromkeys(neu_seit))[:15]) or "nichts")
    if not quelle:
        return False, ("Kauf-Klick ist RAUS, aber nicht beweisbar: der Reader ist aus/pausiert und die "
                       "Positions-Tabelle unten in TradingView (Reiter 'Positions', Kopf 'Symbol') "
                       "war nicht zu lesen. In TradingView nachsehen — NICHT blind erneut starten. Tabellen-Zone: "
                       + tv_positions_zone(roh) + neu_txt)
    return False, (f"Ergebnis UNKLAR: 25 s nach dem Kauf-Klick zeigt die Quelle '{quelle}' keine neue Position. "
                   "Erst in TradingView nachsehen, ob die Order liegt — NICHT blind erneut starten. Tabellen-Zone: "
                   + tv_positions_zone(roh) + neu_txt)


TV_BRUECKE_FELDER = ("symbol", "richtung", "volumen", "tp_usd", "sl_usd", "probe", "scharf")


def tv_bruecke_auspacken(cmd):
    """BRUECKE AM PANEL VORBEI (22.09.2026, Finns Lauf: Schritt 3 'ist glaube
    noch gar nicht live' — stimmte: Bot und Frontend waren neu, das PANEL am PC
    noch alt und reichte 'symbol' nicht durch. Das Panel ist der langsame Teil
    der Auslieferung, bis ~5 min, und kann sich sogar eine veraltete Datei
    holen). Das Frontend legt neue Felder deshalb ZUSAETZLICH als markierte
    Eintraege '@feld=wert' in die 'geschwister'-Liste — die reicht JEDES Panel
    seit .316 durch. Hier werden sie wieder herausgenommen: sie duerfen nie als
    Kontonummer gelten, und ein echtes Feld im Befehl gewinnt immer."""
    if not isinstance(cmd, dict):
        return cmd
    rest = []
    for x in (cmd.get("geschwister") or []):
        t = str(x)
        if t.startswith("@") and "=" in t:
            feld, wert = t[1:].split("=", 1)
            if feld in TV_BRUECKE_FELDER and cmd.get(feld) in (None, "", False):
                cmd[feld] = wert.strip()
            continue
        rest.append(x)
    cmd["geschwister"] = rest
    return cmd


def modus_tvkette(cmd):
    """Die neue Kette, so weit sie steht: Schritt 1+2 (modus_tvkonto, live
    bewiesen) und bei Erfolg Schritt 3. modus_tvkonto bleibt dafuer
    UNANGETASTET — seine Ausgabe wird abgefangen statt umgebaut."""
    import io
    cmd = tv_bruecke_auspacken(cmd)
    puffer, echt = io.StringIO(), sys.stdout
    sys.stdout = puffer
    try:
        modus_tvkonto(cmd)
    finally:
        sys.stdout = echt
    zeilen = [z for z in puffer.getvalue().strip().splitlines() if z.strip()]
    try:
        res = json.loads(zeilen[-1])
    except (ValueError, IndexError):
        print(json.dumps({"ok": False, "schritt": "absturz",
                          "msg": "Konto-Schritt ohne lesbare Antwort: " + (zeilen[-1][:160] if zeilen else "leer")}))
        return
    symbol = str(cmd.get("symbol") or "").strip()
    if not res.get("ok") or not symbol:
        print(json.dumps(res))
        return
    trail = _StempelSpur()
    # Fenstersuche MIT dem Plan-Symbol (Rang 3, falls der Chart schon darauf steht)
    # und mit Geduld: direkt nach dem Login laedt der Tab noch, sein Titel wechselt.
    w, f, ende_w = None, "", time.time() + 8.0
    while not w:
        w, f = _tv_fenster_holen([], "", symbol)
        if w or time.time() >= ende_w:
            break
        _warte(0.3, 0.15)
    if not w:
        ok, msg = False, "TradingView-Fenster fuer den Asset-Schritt nicht gefunden."
    else:
        try:
            ok, msg = tv_asset_schritt(w, symbol, trail)
        except Exception as e:
            ok, msg = False, f"Asset-Schritt abgebrochen: {type(e).__name__}: {e}"
    if ok and str(cmd.get("richtung") or "").strip():
        # Schritt 4a: Order-Panel ausfuellen + beweisen. 4b (22.09.2026): mit der
        # Marke 'scharf' danach der EINE Kauf-Klick + Beweis ueber den Reader.
        asset_msg = msg
        erg = {}
        try:
            ok, msg = tv_order_schritt(w, cmd, trail, erg)
        except Exception as e:
            ok, msg = False, f"Order-Schritt abgebrochen: {type(e).__name__}: {e}"
            if erg.get("gesendet"):
                msg = ("Ergebnis UNKLAR: der Kauf-Klick ging raus, danach brach der Bot ab "
                       f"({type(e).__name__}). Erst in TradingView nachsehen — NICHT blind erneut starten.")
        msg = f"{asset_msg} · {msg}" if ok else f"Asset steht, aber: {msg}"
        res["schritt_order"] = True
        res["scharf"] = tv_ist_scharf(cmd)
        if erg.get("gesendet"):
            # retry_ok=False heisst wie auf der MT5-Route (18.08.2026): es KANN
            # gesendet worden sein — nie blind wiederholen.
            res["gesendet"] = True
            res["retry_ok"] = False
            res["bestaetigt"] = bool(erg.get("bestaetigt"))
            for _k in ("menge", "einstieg", "tv_symbol"):
                res[_k] = erg.get(_k)
    res["konto_msg"] = res.get("msg")
    res["ok"] = bool(ok)
    res["schritt"] = ("fertig" if res.get("bestaetigt") else "unklar" if res.get("gesendet")
                      else "order" if res.get("schritt_order") else "asset")
    res["msg"] = (f"{res.get('msg')} · {msg}" if ok else
                  f"Konto steht ({res.get('konto_aktiv')}), aber: {msg} | Zuletzt: " + " > ".join(list(trail)[-3:]))
    res["trail"] = str(res.get("trail") or "") + " || Asset/Order: " + " > ".join(trail)
    print(json.dumps(res))


# ═══════════════════════════════════════════════════════════════════════════
# ORBIT-V2-RUNDGANG: tvlesen (24.09.2026 nachts)
#
# Finn: "Der Bot geht sich in einem gewissen Intervall automatisch in das
# Konto bei Tradovate auf TradingView, genauso wie man einen Trade startet. Er
# liest, ob die Position noch offen ist oder schon beendet. Ist sie beendet,
# kann man bei Today's P&L sehen, wie viel sich bewegt hat, weil man immer nur
# eine Position pro Tag macht." Duplikum ist weg; Orbit V2 (route tvv2) hat
# damit keinen Copier mehr, der Ende + P&L liefert — das macht jetzt dieser
# Rundgang, gerufen vom Panel (/api/tv-lesen) im Intervall aus Prophos.
#
# Bauweise, bewusst NUR additiv:
#   · Der Konto-Schritt ist modus_tvkonto — UNVERAENDERT und wie in
#     modus_tvkette mit abgefangener Ausgabe aufgerufen. Damit gelten exakt
#     dieselben Schritte und Beweise wie vor einer Order: TradingView nach
#     vorn / starten (tv_sicherstellen), lesen (tv_konto_zustand, UIA-Auge),
#     Dropdown nur wenn noetig, Beweis ueber frischen Stand nach dem Klick.
#     Steht das Konto schon richtig, wird nichts geklickt.
#   · Danach KEIN Klick mehr: Bedienfeld (Userscript 0.5.0+ mit 'summary')
#     und Positions-Stand vom Reader holen — beide muessen JUENGER sein als
#     der Beginn der Lesephase, sonst koennten sie noch vom vorigen Konto
#     stammen (dieselbe Frische-Doktrin wie _tv_bf(nach=...)).
#   · OHNE Reader (24.09.2026, Finn: „Nein — alles ohne Tampermonkey-Script,
#     wenn es geht."): der Bot liest Positions-Tabelle und Konto-Zusammen-
#     fassung selbst per Windows-UI-Automation (_tv_uia_stand — dieselben
#     Augen wie der Order-Beweis: tv_positions_kopf, jetzt mit den Spalten
#     Einstieg und Unrealisierter G&V, dazu tv_summary_uia fuer Today's P&L).
#     Der Reader bleibt BEVORZUGT, wenn er da und >= 0.5.0 ist (Stand < 1 s
#     statt UIA-Scan ~1–2 s). Die Antwort nennt die Quelle: quelle 'reader'
#     oder 'uia'; bei UIA ist alter_s 0.0 (Lesezeitpunkt = jetzt).
#   · Zahlen ueber tv_zahl_lesen (deutsch wie englisch), Vorzeichen U+2212
#     vorher normalisiert — TradingView schreibt "−0,69 %" mit dem
#     typografischen Minus, und tv_zahl_lesen wuerde es still verschlucken.
#   · today_pnl ist float oder None — nie 0.0 aus "nichts gefunden".
# Rueckgabe-Codes (Vertrag mit der Prophos-Seite): konto_nicht_erreicht (+
# konto_aktiv), fenster (kein TradingView-Fenster), tabelle_unklar (Positions-
# Tabelle per UIA nicht zu sehen), bot_fehlt, tv_fehlt. Seit 24.09.2026 KEINE
# Fehler mehr: reader_fehlt / userscript_alt / reader_pausiert / reader_unfrisch
# — sie fuehren auf den UIA-Weg (Vermerk in der Spur). Das Panel setzt aus
# konto_nicht_erreicht den HTTP-Code 409; puls_beschaeftigt vergibt das Panel
# selbst ueber TV_ORDER_LOCK.
# ═══════════════════════════════════════════════════════════════════════════

TV_USERSCRIPT_LESEN_MIN = "0.5.0"      # ab hier gibt es 'summary' im Bedienfeld
# Erster Treffer gewinnt (Teilstring, ohne Gross/Klein). Welches Label
# Tradovate in TradingView WIRKLICH zeigt, sagt der erste Live-Lauf (Antwort
# 'summary') — dann nur diese Liste anpassen, hier UND im Userscript.
TV_TODAY_PNL_LABELS = ("Today's P&L", "Today's Realized P&L", "Realized P&L",
                       "Heutiger G&V", "Heutiger realisierter G&V", "Realisierter G&V",
                       "Tages-G&V", "Realisiert")
# "Unrealized P&L" enthaelt "Realized P&L" als Teilstring — der OFFENE G&V ist
# aber genau nicht das Tagesergebnis. Solche Labels zaehlen nie.
TV_RX_NICHT_TODAY = re.compile(r"unreal|nicht\s*real|offen", re.I)


def tv_geld_lesen(text):
    """Geldbetrag aus einem TradingView-Text, deutsch oder englisch, mit dem
    typografischen Minus (U+2212) und dem Gedankenstrich als Vorzeichen.
    None, wenn nichts Zaehlbares drinsteht — nie ein stilles 0.0."""
    if text is None:
        return None
    t = str(text).replace("−", "-").replace("–", "-").strip()
    # "(12,50)" = Buchhalter-Minus
    if re.fullmatch(r"\(\s*[^()]*\d[^()]*\)", t):
        t = "-" + t.strip("() ")
    return tv_zahl_lesen(t)


def tv_today_pnl(summary, today_text=None, today_label=None):
    """-> (wert|None, label|None, text|None). Nimmt den Vorschlag des
    Userscripts (today_pnl_text), sucht sonst selbst in summary — dieselbe
    Liste, derselbe Riegel gegen 'Unrealized'."""
    if today_text not in (None, "") and today_label and not TV_RX_NICHT_TODAY.search(str(today_label)):
        w = tv_geld_lesen(today_text)
        if w is not None:
            return w, str(today_label), str(today_text)
    if not isinstance(summary, dict):
        return None, None, None
    keys = [k for k in summary.keys() if not TV_RX_NICHT_TODAY.search(str(k))]
    for such in TV_TODAY_PNL_LABELS:
        sl = such.lower()
        for k in keys:
            if sl in str(k).lower():
                w = tv_geld_lesen(summary.get(k))
                if w is not None:
                    return w, str(k), str(summary.get(k))
    return None, None, None


def pruefe_tv_lesen_befehl(cmd):
    """Fehlerliste fuer den tvlesen-Befehl (leer = in Ordnung)."""
    if not isinstance(cmd, dict):
        return ["Befehl ist kein Objekt"]
    fehler = []
    if len(_nur_alnum(cmd.get("konto") or cmd.get("ext_id"))) < 3:
        fehler.append("Konto (External ID) fehlt oder ist kuerzer als 3 Zeichen")
    t = cmd.get("timeout_s")
    if t not in (None, ""):
        try:
            float(t)
        except (TypeError, ValueError):
            fehler.append("timeout_s ist keine Zahl")
    g = cmd.get("geschwister")
    if g is not None and not isinstance(g, list):
        fehler.append("geschwister muss eine Liste sein")
    return fehler


def tv_lesen_timeout(cmd):
    """timeout_s aus dem Befehl, geklemmt 10..180, Standard 45 (Vertrag)."""
    try:
        t = float(cmd.get("timeout_s") or 45.0)
    except (TypeError, ValueError):
        t = 45.0
    return max(10.0, min(180.0, t))


def tv_positionen_auspacken(pos):
    """Reader-Zeilen -> Vertragsform: Texte bleiben, dazu die geparsten Zahlen."""
    out = []
    for p in (pos or []):
        if not isinstance(p, dict):
            continue
        out.append({"symbol": p.get("symbol"), "seite": p.get("seite"),
                    "menge": p.get("menge"), "einstieg": p.get("einstieg"),
                    "pnl": p.get("pnl"), "sl": p.get("sl"), "tp": p.get("tp"),
                    "menge_zahl": tv_geld_lesen(p.get("menge")),
                    "einstieg_zahl": tv_geld_lesen(p.get("einstieg")),
                    "pnl_zahl": tv_geld_lesen(p.get("pnl"))})
    return out


def tv_avg_fill_je_wurzel(positionen):
    """REIN RECHNEND (testbar, 25.09.2026): Avg Fill der offenen Position je Symbol-Wurzel aus den gelesenen
    Zeilen — fuer den Nachtrag von einstieg_nq, wenn der Nachlauf nach dem Order-Klick nichts lesen konnte
    (Plan 273fd74f: Reiter 'Positions' direkt nach der Order sekundenlang verdeckt). Tradovate nettet je
    Symbol → eine Zeile je Kontrakt; bei mehreren Zeilen derselben Wurzel gewinnt die erste mit Zahl.
    -> {wurzel: {avg_fill, symbol, seite, menge}}"""
    out = {}
    for p in (positionen or []):
        if not isinstance(p, dict):
            continue
        w = tv_symbol_root(p.get("symbol"))
        z = p.get("einstieg_zahl")
        if z is None:
            z = tv_geld_lesen(p.get("einstieg"))
        if not w or z is None or w in out:
            continue
        out[w] = {"avg_fill": z, "symbol": p.get("symbol"), "seite": p.get("seite"),
                  "menge": p.get("menge_zahl") if p.get("menge_zahl") is not None else tv_geld_lesen(p.get("menge"))}
    return out


def tv_tabellen_diagnose(roh, anker, symbol):
    """REIN RECHNEND (testbar, 25.09.2026): warum war der Avg Fill nicht lesbar? Fuer die Spur, wenn der
    Nachlauf scheitert — Zone, Kopf ja/nein, Zeilen n, Einstieg-Spalte ja/nein, Symbol der ersten Zeile."""
    try:
        kopf = tv_positions_kopf(roh, anker)
        sp = tv_positions_spalten(roh, kopf) if kopf else None
        zeilen = tv_positions_lesen(roh, kopf) if kopf else []
        root = tv_symbol_root(symbol)
        treffer = [z for z in zeilen if tv_symbol_root(z.get("symbol")) == root]
        teile = [f"Kopf {'ja' if kopf else 'nein'}" + (" (per Anker)" if (kopf and anker) else ""),
                 f"Zeilen {len(zeilen)}", f"Zeilen {root or '?'} {len(treffer)}",
                 f"Einstieg-Spalte {'ja' if (sp and sp.get('einstieg')) else 'nein'}",
                 f"erste Zeile {(zeilen[0].get('symbol') if zeilen else '—')}"
                 + (f" Einstieg '{zeilen[0].get('einstieg')}'" if zeilen else "")]
        return " · ".join(teile) + " · Zone: " + tv_positions_zone(roh, 12)
    except Exception as e:
        return f"Diagnose fehlgeschlagen ({type(e).__name__})"


def tv_gegenseite(richtung):
    return {"buy": "sell", "sell": "buy"}.get(str(richtung or "").lower())


def tv_positionen_treffer(positionen, symbol, richtung=None):
    """Reader-Zeilen mit der Symbol-Wurzel. 'richtung' schliesst NUR Zeilen aus,
    deren Seite BEWIESEN die Gegenseite ist (Short bei buy) — eine leere oder
    unlesbare Seite zaehlt mit. Grund (24.09.2026, zweites Lesen): tvclose
    meldet 'schon_flach' (ok:true), wenn hier nichts uebrig bleibt; ein
    unlesbares 'Side'-Feld darf eine offene Position nie fuer flach erklaeren."""
    root = tv_symbol_root(symbol)
    gegen = tv_gegenseite(richtung)
    out = []
    for p in (positionen or []):
        if not root or tv_symbol_root(p.get("symbol")) != root:
            continue
        if gegen and tv_seite_passt(p.get("seite"), gegen):
            continue
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# UIA-Weg fuer Rundgang und Schliessen (24.09.2026, Finn: „Nein — alles ohne
# Tampermonkey-Script, wenn es geht."). Bis hierher verlangten tvlesen und
# tvclose den Reader (Userscript 0.5.0+ und reader-server) und brachen sonst
# mit reader_fehlt/userscript_alt ab. Jetzt liest der Bot Positions-Tabelle
# und Konto-Zusammenfassung selbst aus der Windows-UI-Automation — mit den
# Augen, mit denen der Order-Klick die Tabelle und die Knoepfe liest
# (_tv_uia_roh / tv_positions_kopf). Alles rein rechnend bis auf die zwei
# Hilfsklicks in _tv_uia_stand (Reiter 'Positions', Panel hochholen), beide
# eindeutig und ohne Marktwirkung — dieselben wie in tvclose.
# ---------------------------------------------------------------------------

TV_UIA_LESEN_TYPEN = ("Text", "Button", "TabItem", "DataItem", "HeaderItem", "Header", "Custom",
                      "Hyperlink", "MenuItem", "ListItem", "CheckBox")
# Reader-Frische hoechstens so lange abwarten, wenn UIA als Ersatz da ist —
# ein frischer Stand kommt sonst < 1 s nach dem Konto-Schritt; wer laenger
# braucht, ist pausiert/blind/verdeckt, und dann liest der Bot eben selbst.
TV_READER_WARTE_S = 12.0
# Optionale Spalten der Positions-Tabelle (Kopf-Text, deutsch wie englisch).
TV_RX_POS_EINSTIEG = re.compile(r"^(avg(\.|erage)?\s*(fill\s*)?(price|preis)?|durchschn|einstieg|entry|fill\s*price|"
                                r"open\s*price|er(ö|oe)ffnung)", re.I)
TV_RX_POS_PNL = re.compile(r"(p&l|p/l|pnl|profit|g&v|gewinn)", re.I)
TV_RX_POS_PNL_OFFEN = re.compile(r"(unreal|open|offen|nicht\s*real)", re.I)
TV_RX_POS_PNL_REAL = re.compile(r"real", re.I)
# Symbol-Zelle: ein Wort, Buchstaben vorn, eine Ziffer oder das '!' des
# Dauerkontrakts (NQZ6, MNQZ2026, NQ1!, CME_MINI:MNQ1!) — 'Total'/'Long' nie.
TV_RX_POS_SYMBOLZELLE = re.compile(r"^[A-Za-z]{1,6}(?:[A-Za-z0-9!:._-]{0,10}\d[A-Za-z0-9!]{0,6}|\d*!)$")
# Wert einer Kennzahl (Port von RX_WERT aus dem Userscript 0.5.1): Vorzeichen
# auch U+2212, Waehrung vorn oder hinten, Prozent, Buchhalter-Klammern.
TV_RX_SUMMARY_WERT = re.compile(r"^\(?\s*[+\-−–]?\s*(?:[$€£]|USD|EUR|GBP|CHF)?\s*[+\-−–]?\d[\d.,\s ']*\s*"
                                r"(?:%|USD|EUR|GBP|CHF|\$|€|£)?\s*\)?$")
TV_SUMMARY_MAX = 40


def tv_positions_spalten(roh, kopf):
    """Alle Kopfzellen der Positions-Kopfzeile (rechts von 'Symbol', gleiche
    Hoehe +-14 px) mit ihrem x-Band: von der eigenen linken Kante (-12) bis zur
    linken Kante des naechsten Kopfes (-12); das letzte Band reicht 260 px
    weiter. So landet jede Zelle in GENAU einem Band, egal ob die Spalte links-
    oder rechtsbuendig ist (Zelle und Kopf teilen dann die linke ODER die rechte
    Kante — die Ueberlappung mit dem eigenen Band ist trotzdem die groesste).
    Benannt: symbol/seite/menge (aus tv_positions_kopf) und NEU einstieg
    ('Avg Fill Price' / 'Durchschn. Ausführungspreis') und pnl ('Unrealized
    P&L' / 'P&L' / 'Profit' / 'Unrealisierter G&V'). Der OFFENE G&V hat Vorrang;
    ein Kopf 'Realized P&L' zaehlt nie als pnl (das ist der Tages-, nicht der
    Positionswert). Rein rechnend.
    -> {'symbol','seite','menge','einstieg','pnl': rect|None, 'y': Kopf-Mitte,
        'baender': [(name|None, links, rechts, rect)]}"""
    rs, rd, rq = kopf
    mitte_y = lambda r: (r[1] + r[3]) // 2
    y0 = mitte_y(rs)
    koepfe = []
    for e in roh or ():
        if not e[1]:
            continue
        n, r = str(e[0]).strip(), tuple(e[1])
        if not n or len(n) > 40 or abs(mitte_y(r) - y0) > 14 or r[0] < rs[0]:
            continue
        if any(abs(r[0] - k[1][0]) <= 2 for k in koepfe):      # Doppelte (Text + DataItem)
            continue
        koepfe.append((n, r))
    koepfe.sort(key=lambda k: k[1][0])
    out = {"symbol": tuple(rs), "seite": tuple(rd) if rd else None, "menge": tuple(rq) if rq else None,
           "einstieg": None, "pnl": None, "y": y0, "baender": []}
    pnl_offen, pnl_schlicht = None, None
    for n, r in koepfe:
        if r in (out["symbol"], out["seite"], out["menge"]):
            continue
        if out["einstieg"] is None and TV_RX_POS_EINSTIEG.search(n):
            out["einstieg"] = r
        elif TV_RX_POS_PNL.search(n):
            if TV_RX_POS_PNL_OFFEN.search(n):
                pnl_offen = pnl_offen or r
            elif not TV_RX_POS_PNL_REAL.search(n):
                pnl_schlicht = pnl_schlicht or r
    out["pnl"] = pnl_offen or pnl_schlicht
    namen = {out["symbol"]: "symbol"}
    for k in ("seite", "menge", "einstieg", "pnl"):
        if out[k]:
            namen[out[k]] = k
    for i, (n, r) in enumerate(koepfe):
        rechts = (koepfe[i + 1][1][0] - 12) if i + 1 < len(koepfe) else (r[2] + 260)
        out["baender"].append((namen.get(r), r[0] - 12, rechts, r))
    return out


def tv_positions_lesen(roh, kopf, max_zeilen=40):
    """Alle Zeilen der Positions-Tabelle aus dem UIA-Rohbild — im Format des
    Readers (Texte; die Zahlen haengt tv_positionen_auspacken an). Zeile =
    ein Symbol-Wort im Symbol-Band unter der Kopfzeile (eine Zeile je 10 px,
    wie tv_positions_zeilen); die uebrigen Zellen derselben Zeile (+-12 px)
    werden ueber die groesste x-Ueberlappung ihrem Band zugeordnet. Wert-
    Spalten werden per Leerzeichen zusammengesetzt ('+190.00' + 'USD'), die
    Seite nimmt nur die erste Zelle. Rein rechnend.
    -> [{'symbol','seite','menge','einstieg','pnl','sl','tp','y'}]"""
    if not kopf:
        return []
    sp = tv_positions_spalten(roh, kopf)
    mitte_y = lambda r: (r[1] + r[3]) // 2
    rs = sp["symbol"]

    def band_von(r):
        best, best_ov = None, 0
        for b in sp["baender"]:
            ov = min(r[2], b[2]) - max(r[0], b[1])
            if ov > best_ov:
                best, best_ov = b, ov
        return best

    els = [(str(e[0]).strip(), tuple(e[1])) for e in roh or () if e[1] and str(e[0]).strip()]
    zeilen_y = []
    for n, r in els:
        y = mitte_y(r)
        if not (sp["y"] + 8 < y <= sp["y"] + 700) or " " in n or len(n) > 24:
            continue
        b = band_von(r)
        if not b or b[0] != "symbol" or not TV_RX_POS_SYMBOLZELLE.match(n) or not tv_symbol_root(n):
            continue
        if any(abs(y - z[0]) <= 10 for z in zeilen_y):
            continue
        zeilen_y.append((y, n))
    out = []
    for y, sym in sorted(zeilen_y)[:max_zeilen]:
        zellen = {}
        for n, r in els:
            if abs(mitte_y(r) - y) > 12 or r[0] < rs[0] - 30:
                continue
            b = band_von(r)
            if not b or not b[0] or b[0] == "symbol":
                continue
            zellen.setdefault(b[0], []).append((r[0], n))
        def text(k, nur_erste=False):
            z = sorted(zellen.get(k) or [])
            if not z:
                return None
            return z[0][1][:20] if nur_erste else " ".join(t for _x, t in z)[:40]
        out.append({"symbol": sym[:30], "seite": text("seite", True), "menge": text("menge"),
                    "einstieg": text("einstieg"), "pnl": text("pnl"), "sl": None, "tp": None, "y": y})
    return out


def tv_summary_uia(roh, ber=None, tabelle_y=None):
    """Konto-Zusammenfassung (Balance, Today's P&L …) aus dem UIA-Rohbild — das
    Gegenstueck zu liesZusammenfassung() im Userscript, nur ueber Bildschirm-
    Geometrie statt DOM-Geschwister. Label = Text-Element mit Buchstaben, ohne
    Ziffer, <= 40 Zeichen; Wert = das naechste Text-Element RECHTS auf derselben
    Zeile (y-Ueberlappung, bis 3 Nachbarn, ein Label beendet die Suche — sonst
    naehme 'Balance' den Wert von 'Equity'), sonst DIREKT DARUNTER (x-Ueber-
    lappung, Oberkante 0..40 px tiefer), sofern es als Geld parst. Dazu 'Label:
    Wert' bzw. 'Label Wert' in EINEM Element. Erster Treffer je Label gewinnt
    (Reihenfolge oben->unten, links->rechts), gekappt auf TV_SUMMARY_MAX.
    'ber' = Bereich des Account-Managers (l, t, r, b) oder None; 'tabelle_y' =
    Oberkante der Positions-Kopfzeile — alles darunter sind Positionszellen,
    keine Kennzahlen. Reiter 'Account Summary' wird NIE angeklickt: bei
    Tradovate steht die Leiste oben im Panel. Rein rechnend. -> dict"""
    def ist_wert(t):
        return 1 <= len(t) <= 24 and re.search(r"\d", t) and TV_RX_SUMMARY_WERT.match(t) \
            and tv_geld_lesen(t) is not None

    def ist_label(t):
        return 2 <= len(t) <= 40 and re.search(r"[A-Za-zÄÖÜäöüß]{2}", t) and not re.search(r"\d", t)

    els = []
    for e in roh or ():
        if not e[1]:
            continue
        n, r, typ = " ".join(str(e[0]).split()), tuple(e[1]), (e[2] if len(e) > 2 else "")
        if not n or len(n) > 70 or typ not in ("Text", "DataItem", "Custom", "HeaderItem", "Header", ""):
            continue
        mx, my = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
        if ber and not (ber[0] <= mx <= ber[2] and ber[1] <= my <= ber[3]):
            continue
        if tabelle_y is not None and my > tabelle_y - 6:
            continue
        els.append((n, r))
    els.sort(key=lambda e: (e[1][1], e[1][0]))
    paare = {}

    def setze(l, w):
        l, w = l.strip(" :"), w.strip()
        if l and w and l not in paare and len(paare) < TV_SUMMARY_MAX:
            paare[l] = w

    for i, (n, r) in enumerate(els):
        if len(paare) >= TV_SUMMARY_MAX:
            break
        m = re.match(r"^([^:\d]{2,40}):\s*(.+)$", n)
        if m and ist_label(m.group(1).strip()) and ist_wert(m.group(2).strip()):
            setze(m.group(1), m.group(2))
            continue
        if not ist_label(n):
            tok = n.split()
            for k in range(1, len(tok)):
                l, w = " ".join(tok[:k]), " ".join(tok[k:])
                if ist_label(l) and ist_wert(w):
                    setze(l, w)
                    break
            continue
        rechts = sorted(((n2, r2) for j, (n2, r2) in enumerate(els) if j != i
                         and r2[0] >= r[2] - 4 and r2[0] - r[2] <= 260
                         and min(r[3], r2[3]) - max(r[1], r2[1]) > 0), key=lambda e: e[1][0])
        gefunden = False
        for n2, _r2 in rechts[:3]:
            if ist_wert(n2):
                setze(n, n2)
                gefunden = True
                break
            if ist_label(n2):
                break
        if gefunden:
            continue
        unten = sorted(((n2, r2) for j, (n2, r2) in enumerate(els) if j != i
                        and -2 <= r2[1] - r[3] <= 40 and min(r[2], r2[2]) - max(r[0], r2[0]) > 0),
                       key=lambda e: (e[1][1], e[1][0]))
        for n2, _r2 in unten[:2]:
            if ist_wert(n2):
                setze(n, n2)
                break
            if ist_label(n2):
                break
    return paare


def tv_summary_bereich(roh, fenster, kopf=None):
    """Bereich des Account-Managers fuer tv_summary_uia: ab 90 px ueber der
    obersten Marke (Reiter 'Positions', Panel-Kopfzeile 'Account Balance'/
    'Equity'/'Profit' in der unteren Fensterhaelfte, Positions-Kopf) bis zum
    Fensterrand; ohne Marke die untere Fensterhaelfte. Rein rechnend."""
    if not fenster:
        return None
    l, t, r, b = fenster
    mitte_y = lambda rr: (rr[1] + rr[3]) // 2
    ys = []
    for e in roh or ():
        if not e[1]:
            continue
        n = str(e[0]).strip()
        if TV_RX_POS_TAB.search(n) or (TV_RX_PANEL_KOPF.match(n) and mitte_y(e[1]) > t + (b - t) * 0.35):
            ys.append(mitte_y(e[1]))
    if kopf:
        ys.append(mitte_y(kopf[0]))
    y_von = (min(ys) - 90) if ys else (t + (b - t) // 2)
    return (l, max(t, y_von), r, b)


def _tv_fenster_geduldig(trail, symbol="", sek=8.0):
    """TradingView-Fenster mit Geduld (Bauart aus tvclose Schritt 3): bis 'sek'
    Sekunden probieren, denn der erste Blick faellt gern in eine Ladephase.
    -> (fenster|None, fehlertext)"""
    w, fw, ende_w = None, "", time.time() + sek
    while not w:
        try:
            w, fw = _tv_fenster_holen(trail, "", symbol)
        except Exception as e:
            w, fw = None, f"{type(e).__name__}: {e}"
        if w or time.time() >= ende_w:
            break
        _warte(0.3, 0.15)
    return w, (fw or "")


def _tv_uia_stand(w, trail, symbol=None, anker=None, maximiert=None, hilfsklicks=True, sek=6.0):
    """EIN Stand per UIA: Positions-Tabelle (alle Zeilen) + Konto-Zusammen-
    fassung + Today's P&L. Bis 'sek' Sekunden auf die Kopfzeile warten; dabei
    hoechstens zwei Hilfsklicks (nur mit hilfsklicks=True): (a) der Reiter
    'Positions', wenn er GENAU EINMAL zu sehen ist und die Kopfzeile fehlt,
    (b) das Panel nach oben holen, wenn es eingeklappt ist (maximiert[0]=True,
    der Aufrufer bringt es in raus() wieder nach unten). Sonst kein Klick.
    Frische: alter_s 0.0 — gelesen ist gelesen, es gibt keinen Zwischenspeicher.
    -> {'ok', 'code', 'msg', 'kopf', 'anker', 'roh', 'positionen', 'summary',
        'today_pnl', 'today_label', 'today_pnl_text', 'summary_hinweis',
        'gelesen_at', 'alter_s'}"""
    fr = _tv_fenster_rect(w)
    ende = time.time() + sek
    roh, kopf, tab_geklickt, oben_versucht = [], None, False, False
    while True:
        roh = _tv_uia_roh(w, TV_UIA_LESEN_TYPEN)
        kopf = tv_positions_kopf(roh, anker)
        if kopf or not hilfsklicks or time.time() >= ende:
            break
        if not tab_geklickt:
            tabs = [e for e in roh if e[1] and TV_RX_POS_TAB.search(str(e[0]).strip())
                    and (len(e) < 3 or e[2] in ("TabItem", "Button", "Text", ""))]
            if len(tabs) == 1:
                tab_geklickt = True
                r = tabs[0][1]
                _tv_uia_klick({"punkt": ((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)}, "Reiter Positions", trail)
                _warte(0.5, 0.3)
                continue
        if not oben_versucht:
            oben_versucht = True
            try:
                if tv_panel_eingeklappt(roh, fr) and _tv_panel_umschalten(w, trail, "oben"):
                    if maximiert is not None:
                        maximiert[0] = True
                    _warte(0.6, 0.3)
                    continue
            except Exception as e:
                trail.append(f"Panel-Umschalten abgebrochen: {type(e).__name__}")
        _warte(0.4, 0.25)
    summary = tv_summary_uia(roh, tv_summary_bereich(roh, fr, kopf), tabelle_y=(kopf[0][1] if kopf else None))
    today, label, text = tv_today_pnl(summary)
    out = {"ok": bool(kopf), "code": "", "msg": "", "kopf": bool(kopf),
           "anker": tuple(kopf[0]) if kopf else anker, "roh": roh, "positionen": [],
           "summary": summary, "today_pnl": today, "today_label": label, "today_pnl_text": text,
           "summary_hinweis": None if today is not None else
           ("kein Label in UIA" if summary else "keine Label→Wert-Paare in UIA"),
           "gelesen_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "alter_s": 0.0}
    if not kopf:
        out["code"] = "tabelle_unklar"
        out["msg"] = ("Positions-Tabelle (Reiter 'Positions', Kopf 'Symbol') per UIA nicht zu sehen — "
                      "kein Stand ohne Tabelle. Zone: " + tv_positions_zone(roh))
        trail.append(f"UIA: Tabelle nicht zu sehen, {len(summary)} Summary-Paare, Today {today} ('{label}')")
        return out
    out["positionen"] = tv_positionen_auspacken(tv_positions_lesen(roh, kopf))
    trail.append(f"UIA: {len(out['positionen'])} Pos, {len(summary)} Summary-Paare, Today {today} ('{label}')")
    return out


def _tv_today_aus_uia(u):
    """Today-Felder fuer die Antwort aus einem _tv_uia_stand-Ergebnis."""
    return {"summary": u.get("summary"), "today_pnl": u.get("today_pnl"), "today_label": u.get("today_label"),
            "today_pnl_text": u.get("today_pnl_text"), "summary_hinweis": u.get("summary_hinweis"),
            "sprache_fremd": False, "summary_fehler": None}


# ---------------------------------------------------------------------------
# Gemeinsame Bausteine von tvlesen und tvclose (24.09.2026 — beim Bau von
# tvclose herausgezogen, damit der Konto-Schritt und die Frische-Doktrin an
# GENAU EINER Stelle stehen; tvlesen verhaelt sich unveraendert).
# ---------------------------------------------------------------------------

def _tv_quelle_waehlen(trail):
    """Schritt 0 (24.09.2026, vorher _tv_reader_bereit: ohne Reader war Schluss
    — reader_fehlt/userscript_alt; Finn: „Nein — alles ohne Tampermonkey-
    Script, wenn es geht."). Jetzt nur noch die WAHL der Quelle: Reader da UND
    Userscript >= 0.5.0 -> ('reader', bf0), sonst ('uia', None) — der Bot liest
    dann selbst. Kein Fehler mehr, nur ein Vermerk in der Spur."""
    bf0 = _tv_http("/bedienfeld", timeout=2.0)
    if bf0 is None:
        trail.append("Reader (127.0.0.1:8790) antwortet nicht -> UIA-Weg")
        return "uia", None
    if not bf0.get("ok"):
        trail.append("Reader ohne Bedienfeld (Userscript stumm?) -> UIA-Weg")
        return "uia", None
    if not tv_version_min(bf0.get("version"), TV_USERSCRIPT_LESEN_MIN):
        trail.append(f"Userscript {bf0.get('version') or '?'} < {TV_USERSCRIPT_LESEN_MIN} (keine Zusammenfassung) "
                     "-> UIA-Weg; Tampermonkey aktualisiert von selbst (@updateURL)")
        return "uia", None
    trail.append(f"Reader da (Userscript {bf0.get('version')}, Bedienfeld {bf0.get('alter_s')}s alt) -> Reader-Weg")
    return "reader", bf0


def _tv_konto_abgefangen(cmd, ext, geschwister, res, trail):
    """Schritt 1: Konto-Schritt = modus_tvkonto, UNVERAENDERT, Ausgabe abgefangen
    (Bauart aus modus_tvkette). Schreibt konto_aktiv/konto_trail/konto_msg/
    konto_klicks nach res. -> (code, msg, extra); code '' = Konto steht.
    konto_klicks (24.09.2026, Pruefauftrag 'wenn das Konto schon aktiv ist,
    wirklich kein Klick'): zaehlt die '… geklickt'-Stationen in der Spur des
    Konto-Schritts. Steht das Konto laut Bedienfeld/UIA schon richtig, endet
    modus_tvkonto VOR jedem Klick (Zweig zustand == 'richtig') — die Zahl im
    Panel-Log beweist das je Lauf, statt es zu behaupten."""
    import io
    cmd_k = {k: str(cmd.get(k) or "").strip()
             for k in ("tv_url", "tv_browser_path", "tv_chrome_profil", "tv_username", "firma")}
    cmd_k["ext_id"] = ext
    cmd_k["geschwister"] = geschwister
    cmd_k["sitzung_merken"] = bool(cmd.get("sitzung_merken"))
    puffer, echt = io.StringIO(), sys.stdout
    sys.stdout = puffer
    try:
        modus_tvkonto(cmd_k)
    except Exception as e:
        sys.stdout = echt
        return "tv_fehlt", f"Konto-Schritt abgebrochen: {type(e).__name__}: {e}", {}
    finally:
        sys.stdout = echt
    zeilen = [z for z in puffer.getvalue().strip().splitlines() if z.strip()]
    try:
        res_k = json.loads(zeilen[-1])
    except (ValueError, IndexError):
        return "tv_fehlt", "Konto-Schritt ohne lesbare Antwort: " + (zeilen[-1][:160] if zeilen else "leer"), {}
    res["konto_aktiv"] = str(res_k.get("konto_aktiv") or "")[:80]
    res["konto_trail"] = str(res_k.get("trail") or "")
    res["konto_msg"] = str(res_k.get("msg") or "")[:300]
    res["konto_klicks"] = res["konto_trail"].count("geklickt")
    if not res_k.get("ok"):
        schritt_k = str(res_k.get("schritt") or "")
        if schritt_k in ("start", "befehl", "tradingview"):
            # pywinauto fehlt (Mac) / Befehl / TradingView laesst sich nicht oeffnen
            code = "bot_fehlt" if "pywinauto" in res["konto_msg"] else "tv_fehlt"
        else:
            code = "konto_nicht_erreicht"
        return code, (res["konto_msg"] or "Konto-Schritt fehlgeschlagen"), {
            "zustand": res_k.get("zustand"), "diagnose": res_k.get("diagnose")}
    trail.append(f"Konto steht ({res['konto_aktiv'][:40]}) — {res_k.get('schritt')}, "
                 f"{res['konto_klicks']} Klick(s) im Konto-Schritt")
    return "", "", {}


def _tv_frisch_lesen(ext, geschwister, t_ab, timeout_s, res):
    """Schritt 2: Bedienfeld + Positions-Stand holen, beide JUENGER als t_ab —
    kein Klick. Aktualisiert res['konto_aktiv'] aus dem Reader-Auge.
    -> {'ok': True, 'bf', 'st', 'empf', 'konto_quelle'} oder
       {'ok': False, 'code', 'msg', 'konto_quelle', ...}"""
    ende = t_ab + timeout_s
    bf, st, grund, empf = None, None, "noch kein Stand", None
    konto_quelle = None
    while time.time() < ende:
        rest = ende - time.time()
        bf = _tv_bf(nach=t_ab, timeout=min(3.0, max(0.3, rest)))
        if not bf:
            grund = "kein Bedienfeld-Stand nach dem Konto-Schritt (Userscript stumm? Tab verdeckt?)"
            continue
        z, aktiv = tv_konto_zustand(bf, ext, geschwister)
        if z == "richtig":
            res["konto_aktiv"], konto_quelle = aktiv[:80], "reader"
        elif z in ("gleicher_login", "falsch"):
            # Das Reader-Auge sieht ein ANDERES Konto als das UIA-Auge eben — zwei
            # Augen, die sich widersprechen, sind kein Beweis. Nichts liefern.
            return {"ok": False, "code": "konto_nicht_erreicht", "konto_quelle": konto_quelle,
                    "msg": f"Konto-Schritt meldete {ext}, der Reader sieht aber '{aktiv[:40]}' im Panel — "
                           "kein Stand ohne eindeutiges Konto.", "konto_aktiv": aktiv[:80], "zustand": z}
        elif time.time() - t_ab < 3.0:
            grund = "Reader-Auge sieht das Konto (noch) nicht"
            _warte(0.3, 0.2)
            continue
        else:
            # Der Reader kennt den Konto-Umschalter nicht (TradingView hat die Anker
            # umbenannt, Fund 21.09.2026) — dann gilt der UIA-Beweis von eben (nach
            # dem Klick frisch gelesen, derselbe Beweis, mit dem tvkonto Orders freigibt).
            konto_quelle = "uia"
        st = _tv_http("/positions", timeout=2.0)
        if not st:
            grund = "Positions-Stand nicht abrufbar"
            _warte(0.3, 0.2)
            continue
        if st.get("an") is False:
            return {"ok": False, "code": "reader_pausiert", "konto_quelle": konto_quelle,
                    "msg": "TV-Reader ist pausiert (Orbit-Schalter) — der Positions-Stand ist eingefroren, "
                           "stale ist nicht flat. Reader in Prophos einschalten."}
        if st.get("blind"):
            grund = "Reader blind: " + str(st.get("blind_grund") or "")[:120]
            _warte(0.4, 0.3)
            continue
        if not isinstance(st.get("positionen"), list):
            grund = "Positions-Stand ohne Liste"
            _warte(0.3, 0.2)
            continue
        # Frische: Server-Alter (reader-server 24.09.2026+), sonst Browser-ts
        # (gleicher PC, gleiche Uhr).
        try:
            if st.get("alter_s") is not None:
                empf = time.time() - float(st["alter_s"])
            else:
                empf = float(st.get("ts") or 0) / 1000.0
        except (TypeError, ValueError):
            empf = None
        if empf is None or empf < t_ab:
            grund = "Positions-Stand aelter als der Lesebeginn (noch vom vorigen Konto?)"
            _warte(0.3, 0.2)
            continue
        return {"ok": True, "bf": bf, "st": st, "empf": empf, "konto_quelle": konto_quelle}
    return {"ok": False, "code": "reader_unfrisch", "konto_quelle": konto_quelle,
            "msg": f"In {timeout_s:.0f} s kein beweisbarer Stand: {grund}."}


def _absturz_ort(e):
    """'funktion:zeile' der letzten Stelle in order_bot.py aus dem Traceback — fuer die Ferndiagnose."""
    try:
        import traceback
        eigene = [f for f in traceback.extract_tb(e.__traceback__) if "order_bot" in str(f.filename)]
        f = (eigene or traceback.extract_tb(e.__traceback__))[-1]
        return f"{f.name}:{f.lineno}"
    except Exception:
        return "?"


def modus_tvlesen(cmd):
    res = {"ok": False, "code": "", "msg": "", "trail": "", "schritt": "start",
           "konto_aktiv": "", "konto_quelle": None, "quelle": None}
    trail = _StempelSpur()
    fenster = [None]
    maximiert = [False]        # Panel per Hilfsklick hochgeholt -> in raus() wieder nach unten
    reader_da = [False]

    def raus(code, msg, schritt, **extra):
        if maximiert[0]:
            maximiert[0] = False
            try:
                if fenster[0]:
                    _tv_panel_umschalten(fenster[0], trail, "unten")
            except Exception:
                pass
        res["code"], res["msg"], res["schritt"] = code, msg, schritt
        res.update(extra)
        res["trail"] = " > ".join(trail) + ((" || Konto: " + res["konto_trail"]) if res.get("konto_trail") else "")
        res.pop("konto_trail", None)
        if reader_da[0]:
            _tv_http("/suche", {"texte": []}, timeout=1.5)     # Textsuche nie im Dauerbetrieb
        try:
            print(json.dumps(res, ensure_ascii=False))
        except UnicodeEncodeError:
            print(json.dumps(res, ensure_ascii=True))   # Konsole ohne UTF-8 (24.09.2026): JSON-Escapes statt Absturz

    fehler = pruefe_tv_lesen_befehl(cmd)
    if fehler:
        return raus("befehl", "Befehl unvollstaendig: " + " / ".join(fehler), "befehl")
    ext = str(cmd.get("konto") or cmd.get("ext_id") or "").strip()
    timeout_s = tv_lesen_timeout(cmd)
    geschwister = [str(x).strip() for x in (cmd.get("geschwister") or [])
                   if len(_nur_alnum(x)) >= 3][:60]

    # --- 0: Quelle waehlen — Reader, wenn da und neu genug, sonst UIA. Kein
    # Abbruch mehr ohne Reader (24.09.2026). Der billigste Blick zuerst.
    quelle, bf0 = _tv_quelle_waehlen(trail)
    reader_da[0] = bf0 is not None
    res["quelle"] = quelle

    # --- 1: Konto-Schritt = modus_tvkonto, unveraendert, Ausgabe abgefangen.
    # Laeuft ohne Reader (UIA-Auge; bei Finn seit 22.09.2026 der Normalfall).
    code, msg, extra = _tv_konto_abgefangen(cmd, ext, geschwister, res, trail)
    if code:
        return raus(code, msg, "konto", **extra)

    # --- 2a: Reader-Weg — lesen, kein Klick. Alles muss JUENGER sein als t_lese.
    t_lese = time.time()
    if quelle == "reader":
        _tv_http("/suche", {"texte": [ext] + geschwister}, timeout=1.5)   # Konto-Auge per Text (tv_konto_per_text)
        f = _tv_frisch_lesen(ext, geschwister, t_lese, min(timeout_s, TV_READER_WARTE_S), res)
        if f["ok"]:
            bf, st, empf, konto_quelle = f["bf"], f["st"], f["empf"], f["konto_quelle"]
            positionen = tv_positionen_auspacken(st.get("positionen"))
            summary = bf.get("summary") if isinstance(bf.get("summary"), dict) else None
            today, today_label, today_text = tv_today_pnl(summary, bf.get("today_pnl_text"), bf.get("today_label"))
            trail.append(f"gelesen (Reader): {len(positionen)} Pos, {len(summary or {})} Summary-Paare, "
                         f"Today {today} ('{today_label}')")
            res.update({"ok": True, "positionen": positionen, "offen": bool(positionen),
                        "avg_fill_je_wurzel": tv_avg_fill_je_wurzel(positionen),   # 25.09.2026: Nachtrag einstieg_nq
                        "summary": summary, "today_pnl": today, "today_label": today_label,
                        "today_pnl_text": today_text,
                        "alter_s": round(time.time() - empf, 3),
                        "gelesen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "konto_quelle": konto_quelle, "userscript": bf.get("version"),
                        "sprache_fremd": bool(bf.get("sprache_fremd")),
                        "summary_fehler": bf.get("summary_fehler"), "quelle": "reader"})
            return raus("", f"Konto {res['konto_aktiv'][:40]}: {len(positionen)} Position(en)"
                        + (f", Today's P&L {today:g} ({today_label})" if today is not None else
                           ", Tages-G&V nicht gefunden — 'summary' in der Antwort zeigt die Labels"),
                        "fertig")
        if f["code"] == "konto_nicht_erreicht":
            # Zwei Augen, die sich widersprechen (Reader sieht ein anderes Konto) —
            # das heilt kein UIA-Blick. Ehrlich abbrechen.
            extra = {k: v for k, v in f.items() if k not in ("ok", "code", "msg")}
            return raus(f["code"], f["msg"], "lesen", **extra)
        # reader_pausiert / reader_unfrisch: kein Fehler mehr — der Bot liest selbst.
        trail.append(f"Reader ohne beweisbaren Stand ({f['code']}: {str(f['msg'])[:80]}) -> UIA-Weg")
        quelle = "uia"
        res["quelle"] = "uia"

    # --- 2b: UIA-Weg — Fenster, dann EIN Stand (Tabelle + Zusammenfassung).
    w, fw = _tv_fenster_geduldig(trail, "", 8.0)
    if not w:
        return raus("fenster", "TradingView-Fenster nicht gefunden — kein Stand. " + fw, "fenster")
    fenster[0] = w
    u = _tv_uia_stand(w, trail, None, None, maximiert)
    if not u["ok"]:
        return raus(u["code"], u["msg"], "lesen", konto_quelle=res.get("konto_quelle") or "uia",
                    **_tv_today_aus_uia(u))
    positionen = u["positionen"]
    res.update({"ok": True, "positionen": positionen, "offen": bool(positionen),
                "avg_fill_je_wurzel": tv_avg_fill_je_wurzel(positionen),   # 25.09.2026: Nachtrag einstieg_nq
                "alter_s": 0.0, "gelesen_at": u["gelesen_at"],
                "konto_quelle": res.get("konto_quelle") or "uia", "userscript": None,
                "quelle": "uia", **_tv_today_aus_uia(u)})
    today, today_label = u["today_pnl"], u["today_label"]
    return raus("", f"Konto {res['konto_aktiv'][:40]}: {len(positionen)} Position(en) (UIA)"
                + (f", Today's P&L {today:g} ({today_label})" if today is not None else
                   ", Tages-G&V nicht gefunden — 'summary' in der Antwort zeigt die Labels"),
                "fertig")


# ═══════════════════════════════════════════════════════════════════════════
# ORBIT V2 SCHLIESSEN: tvclose (24.09.2026)
#
# Finns Auto-Close-Regel (22.09.2026): 23:45–00:00 Dubai alles schliessen —
# fuer Echo laengst gebaut (/api/master-close), fuer Orbit stand in der Notiz
# nur „Orbit-Schliessen in TV offen — Positions-Tabelle → ✕ / Flatten". Mit
# dem Vollumstieg auf „Ohne Hedge" (Finn 24.09.2026: „riesen Umstieg — geh
# alles durch") ist Orbit V2 der Standardweg fuer Futures, also braucht das
# Auto-Close diesen Schritt jetzt wirklich.
#
# Bauweise, additiv, dieselben Mechaniken wie Order-Start und Rundgang:
#   · Schritt 0/1/2 EXAKT wie tvlesen (Quelle waehlen, modus_tvkonto abge-
#     fangen, frischer Stand) — steht das Konto, wird im Konto-Schritt nichts
#     geklickt. Seit 24.09.2026 (Finn: „alles ohne Tampermonkey-Script, wenn
#     es geht") ist der Reader keine Pflicht mehr: ohne ihn liefert
#     _tv_uia_stand den Vorher-Stand, den Beweis und Today's P&L per UIA.
#   · Ist laut frischem Stand (Reader oder UIA) keine Position der Wurzel
#     offen: {ok:true, code:'schon_flach'} — nichts geklickt, Today's P&L dabei.
#   · Sonst mit dem UIA-Auge (tv_positions_kopf / tv_positions_zeilen —
#     dieselbe Kopf-/Zeilen-Regel wie der Order-Beweis) GENAU EINE Zeile der
#     Wurzel finden und in DIESER Zeile GENAU EINEN benannten Knopf, dessen
#     Name auf TV_RX_CLOSE passt (Close / Schliessen / Flatten / Close position,
#     deutsch wie englisch, exakt — nie 'Close all', nie 'Closed', nie ein
#     unbenannter Knopf). Alles andere: {ok:false, code:'close_knopf_unklar',
#     gesehen:<UIA-Spur>} — NIE raten, NIE den Kauf-Knopf anfassen.
#   · Nach dem Klick: TradingViews Rueckfrage 'Close position' / 'Position
#     schliessen' bestaetigen — nur ueber einen NEU erschienenen, eindeutigen
#     Bestaetigen-Knopf (TV_RX_CLOSE_JA, Rang 1). Ein blosses 'Close' im
#     Dialog kann auch das X zum Wegklicken sein und zaehlt deshalb nicht.
#     Zwei Kandidaten oder keiner in 8 s: 'bestaetigung_unklar' + ESC (ESC ist
#     Abbrechen, nie Bestaetigen), retry_ok bleibt False (ein Klick ist raus).
#   · Beweis wie beim Order-Start, nur gespiegelt: Reader-Stand JUENGER als
#     der Klick und OHNE die Position — zweimal hintereinander (Streak 2, zwei
#     verschiedene Staende). Ist der Reader blind oder gar nicht da (UIA-Weg),
#     die UIA-Tabelle zweimal ohne die Zeile — und NUR, wenn dabei kein
#     Rueckfrage-Dialog zu sehen ist (Chrome blendet hinter einem modalen
#     Dialog die Seite per aria-hidden aus der UIA aus: eine verschwundene
#     Tabelle waere sonst ein falsches 'weg'). Danach Today's P&L aus einem
#     frischen Bedienfeld bzw. UIA-Stand; die Antwort nennt 'quelle'.
# Rueckgabe-Codes (zusaetzlich zu denen von tvlesen): schon_flach (ok), fenster
# (kein TradingView-Fenster), close_knopf_unklar, bestaetigung_unklar,
# ende_unklar (geklickt, Position 'timeout_s' lang nicht weg), absturz.
# ═══════════════════════════════════════════════════════════════════════════

# Der Schliessen-Knopf in der Positions-Zeile — EXAKTER Name, optional ein
# Symbol dahinter ('Close MNQZ6'); das Symbol muss dann die Plan-Wurzel tragen.
TV_RX_CLOSE = re.compile(r"^(?:close(?: position)?|position schlie(?:ß|ss)en|schlie(?:ß|ss)en|flatten|glattstellen)"
                         r"(?:\s+(?P<sym>[A-Za-z][A-Za-z0-9!:._-]{1,20}))?$", re.I)
# 'Close all' / 'Alle schliessen' / 'Close all positions' — nie, in keiner Form.
TV_RX_CLOSE_ALLE = re.compile(r"\b(all|alle|everything|sämtliche|saemtliche)\b", re.I)
# Rueckfrage-Dialog: Rang 1 = eindeutige Bestaetigung. Ein blosses 'Close'/
# 'Schliessen' gehoert NICHT hierher (kann das X des Dialogs sein).
TV_RX_CLOSE_JA = re.compile(r"^(?:yes|ja|confirm|bestätigen|bestaetigen|ok|close position|position schlie(?:ß|ss)en|"
                            r"flatten|glattstellen)(?:\s+[A-Za-z][A-Za-z0-9!:._-]{1,20})?$", re.I)
TV_RX_CLOSE_NEIN = re.compile(r"^(?:cancel|abbrechen|no|nein|zurück|zurueck)$", re.I)
TV_RX_CLOSE_DIALOG = re.compile(r"^(?:close position|position schlie(?:ß|ss)en|are you sure|sind sie sicher|"
                                r"wirklich schlie(?:ß|ss)en)", re.I)


def tv_close_text_passt(text, symbol):
    """Ist dieser Knopf-Name der Schliessen-Knopf fuer die Wurzel von 'symbol'?
    Exakt (nach strip), deutsch/englisch; 'Close all', 'Closed', 'Close all
    positions' nie. Traegt der Name ein Symbol, muss es die Wurzel sein."""
    t = str(text or "").strip()
    if not t or TV_RX_CLOSE_ALLE.search(t):
        return False
    m = TV_RX_CLOSE.match(t)
    if not m:
        return False
    sym = m.group("sym")
    if sym:
        root = tv_symbol_root(symbol)
        return bool(root) and tv_symbol_root(sym) == root
    return True


def tv_close_knopf(roh, symbol, richtung=None, anker=None):
    """Zeile + Schliessen-Knopf in der Positions-Tabelle (rein rechnend).
    -> {'kopf': bool, 'anker': rect|None, 'zeilen': n, 'zeile': {...}|None,
        'knopf': {...}|None, 'kandidaten': [...], 'grund': str}
    knopf nur bei GENAU EINER Zeile der Wurzel und GENAU EINEM passenden,
    BENANNTEN Element in dieser Zeile (+-14 px), rechts der Symbol-Spalte."""
    mitte_y = lambda r: (r[1] + r[3]) // 2
    root = tv_symbol_root(symbol)
    out = {"kopf": False, "anker": None, "zeilen": 0, "zeile": None, "knopf": None, "kandidaten": [], "grund": ""}
    kopf = tv_positions_kopf(roh, anker)
    if not kopf:
        out["grund"] = "Positions-Tabelle (Reiter 'Positions', Kopf 'Symbol') nicht zu sehen"
        return out
    out["kopf"], out["anker"] = True, tuple(kopf[0])
    zeilen = tv_positions_zeilen(roh, kopf, symbol, richtung)
    out["zeilen"] = len(zeilen)
    if len(zeilen) != 1:
        out["grund"] = (f"keine Zeile mit {root or '?'} in der Positions-Tabelle" if not zeilen else
                        f"{len(zeilen)} Zeilen mit {root} — nicht eindeutig")
        return out
    z = zeilen[0]
    out["zeile"] = {"symbol": z["symbol"], "y": z["y"], "seite": z["seite"]}
    rs = kopf[0]
    kand = []
    for e in roh or ():
        if not e[1]:
            continue
        n, r, typ = str(e[0]).strip(), e[1], (e[2] if len(e) > 2 else "")
        if abs(mitte_y(r) - z["y"]) > 14 or r[0] <= rs[0]:
            continue
        if not tv_close_text_passt(n, symbol):
            continue
        if any(k["r"] == tuple(r) for k in kand):
            continue
        kand.append({"text": n[:60], "typ": typ, "r": tuple(r),
                     "punkt": ((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)})
    out["kandidaten"] = kand
    if len(kand) == 1:
        out["knopf"] = kand[0]
    else:
        out["grund"] = (f"kein benannter Schliessen-Knopf in der Zeile {z['symbol']} (y={z['y']})" if not kand
                        else f"{len(kand)} Schliessen-Knoepfe in der Zeile {z['symbol']} — nicht eindeutig")
    return out


def tv_close_bestaetigung(roh, namen_vorher):
    """Rueckfrage nach dem Klick: NEUE Elemente seit dem Klick sichten.
    -> {'ja': [...Rang-1-Knoepfe...], 'nein': n, 'dialog': bool, 'neu': [...]}"""
    ja, nein, dialog, neu = [], 0, False, []
    for e in roh or ():
        if not e[1]:
            continue
        n, r, typ = str(e[0]).strip(), e[1], (e[2] if len(e) > 2 else "")
        if not n or n in namen_vorher:
            continue
        if len(n) <= 60 and n not in neu:
            neu.append(n)
        if TV_RX_CLOSE_DIALOG.search(n):
            dialog = True
        if TV_RX_CLOSE_NEIN.match(n):
            nein += 1
            dialog = True
            continue
        if TV_RX_CLOSE_JA.match(n) and not TV_RX_CLOSE_ALLE.search(n) and typ in ("Button", "", "Hyperlink"):
            if not any(k["r"] == tuple(r) for k in ja):
                ja.append({"text": n[:60], "typ": typ, "r": tuple(r),
                           "punkt": ((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)})
    return {"ja": ja, "nein": nein, "dialog": dialog, "neu": neu[:15]}


def pruefe_tv_close_befehl(cmd):
    """Fehlerliste fuer den tvclose-Befehl (leer = in Ordnung)."""
    fehler = pruefe_tv_lesen_befehl(cmd)
    if not isinstance(cmd, dict):
        return fehler
    if not tv_symbol_root(cmd.get("symbol")):
        fehler.append("Symbol fehlt (z.B. NQZ6 / MNQ)")
    r = str(cmd.get("richtung") or "").strip().lower()
    if r and r not in ("buy", "sell"):
        fehler.append("Richtung muss buy/sell sein (oder leer)")
    return fehler


def modus_tvclose(cmd):
    res = {"ok": False, "code": "", "msg": "", "trail": "", "schritt": "start",
           "konto_aktiv": "", "konto_quelle": None, "quelle": None, "geklickt": False, "bestaetigt": False,
           "retry_ok": True}
    trail = _StempelSpur()
    fenster = [None]
    maximiert = [False]
    reader_da = [False]

    def raus(code, msg, schritt, **extra):
        # Panel wieder nach unten, falls es fuer die Tabelle hochgeholt wurde
        # (dieselbe Nachsorge wie in modus_tvkonto: maximiert verdeckt es den Chart).
        if maximiert[0]:
            maximiert[0] = False
            try:
                if fenster[0]:
                    _tv_panel_umschalten(fenster[0], trail, "unten")
            except Exception:
                pass
        res["code"], res["msg"], res["schritt"] = code, msg, schritt
        res.update(extra)
        res["trail"] = " > ".join(trail) + ((" || Konto: " + res["konto_trail"]) if res.get("konto_trail") else "")
        res.pop("konto_trail", None)
        if reader_da[0]:
            _tv_http("/suche", {"texte": []}, timeout=1.5)
        try:
            print(json.dumps(res, ensure_ascii=False))
        except UnicodeEncodeError:
            print(json.dumps(res, ensure_ascii=True))   # Konsole ohne UTF-8 (24.09.2026): JSON-Escapes statt Absturz

    fehler = pruefe_tv_close_befehl(cmd)
    if fehler:
        return raus("befehl", "Befehl unvollstaendig: " + " / ".join(fehler), "befehl")
    ext = str(cmd.get("konto") or cmd.get("ext_id") or "").strip()
    symbol = str(cmd.get("symbol") or "").strip()
    root = tv_symbol_root(symbol)
    richtung = str(cmd.get("richtung") or "").strip().lower() or None
    timeout_s = tv_lesen_timeout(cmd)
    geschwister = [str(x).strip() for x in (cmd.get("geschwister") or [])
                   if len(_nur_alnum(x)) >= 3][:60]
    res["symbol"], res["wurzel"], res["richtung"] = symbol, root, richtung

    def today_aus(bf):
        summary = bf.get("summary") if isinstance(bf.get("summary"), dict) else None
        t, lab, txt = tv_today_pnl(summary, bf.get("today_pnl_text"), bf.get("today_label"))
        return {"summary": summary, "today_pnl": t, "today_label": lab, "today_pnl_text": txt,
                "sprache_fremd": bool(bf.get("sprache_fremd")), "summary_fehler": bf.get("summary_fehler")}

    # --- 0 + 1: wie tvlesen -------------------------------------------------
    quelle, bf0 = _tv_quelle_waehlen(trail)
    reader_da[0] = bf0 is not None
    res["quelle"] = quelle
    code, msg, extra = _tv_konto_abgefangen(cmd, ext, geschwister, res, trail)
    if code:
        return raus(code, msg, "konto", **extra)

    # --- 2: Vorher-Stand, frisch — ist ueberhaupt etwas offen? --------------
    # Reader-Weg: Bedienfeld + Positions-Stand juenger als t_lese (hoechstens
    # TV_READER_WARTE_S — danach liest der Bot selbst, kein Fehler mehr).
    # UIA-Weg: Fenster holen, dann _tv_uia_stand (Tabelle + Zusammenfassung).
    t_lese = time.time()
    bf, st, u_vor, anker, w = None, None, None, None, None
    typen = TV_UIA_LESEN_TYPEN
    if quelle == "reader":
        _tv_http("/suche", {"texte": [ext] + geschwister}, timeout=1.5)
        f = _tv_frisch_lesen(ext, geschwister, t_lese, min(timeout_s, TV_READER_WARTE_S), res)
        if f["ok"]:
            bf, st = f["bf"], f["st"]
            res["konto_quelle"] = f["konto_quelle"]
            vorher = tv_positionen_auspacken(st.get("positionen"))
        elif f["code"] == "konto_nicht_erreicht":
            extra = {k: v for k, v in f.items() if k not in ("ok", "code", "msg")}
            return raus(f["code"], f["msg"], "lesen", **extra)
        else:
            trail.append(f"Reader ohne beweisbaren Stand ({f['code']}: {str(f['msg'])[:80]}) -> UIA-Weg")
            quelle = "uia"
            res["quelle"] = "uia"
    if quelle == "uia":
        w, fw = _tv_fenster_geduldig(trail, symbol, 8.0)
        if not w:
            return raus("fenster", "TradingView-Fenster nicht gefunden — nichts geklickt. " + fw, "fenster")
        fenster[0] = w
        u_vor = _tv_uia_stand(w, trail, symbol, None, maximiert)
        if not u_vor["ok"]:
            return raus(u_vor["code"], u_vor["msg"] + " Nichts geklickt.", "lesen",
                        konto_quelle=res.get("konto_quelle") or "uia", **_tv_today_aus_uia(u_vor))
        anker = u_vor["anker"]
        res["konto_quelle"] = res.get("konto_quelle") or "uia"
        vorher = u_vor["positionen"]
    treffer = tv_positionen_treffer(vorher, symbol, richtung)
    res["positionen_vorher"] = vorher
    trail.append(f"Vorher ({quelle}): {len(vorher)} Pos, davon {len(treffer)} mit {root}"
                 + (f" ({richtung})" if richtung else ""))
    if not treffer:
        t_info = today_aus(bf) if quelle == "reader" else _tv_today_aus_uia(u_vor)
        return raus("schon_flach", f"Keine offene Position {root} auf {res['konto_aktiv'][:40]} — nichts geklickt"
                    + (f", Today's P&L {t_info['today_pnl']:g}" if t_info["today_pnl"] is not None else ""),
                    "fertig", ok=True, positionen_danach=vorher, geklickt=False, retry_ok=False,
                    gelesen_at=time.strftime("%Y-%m-%dT%H:%M:%S"), **t_info)

    # --- 3: TradingView-Fenster (wie modus_tvkette, mit Geduld) — auf dem
    #        UIA-Weg steht es schon --------------------------------------------
    if not w:
        w, fw = _tv_fenster_geduldig(trail, symbol, 8.0)
        if not w:
            return raus("fenster", "TradingView-Fenster nicht gefunden — nichts geklickt. " + fw, "fenster")
        fenster[0] = w

    # --- 4: Zeile + Knopf mit dem UIA-Auge, hoechstens ~10 s ------------------
    # Nur zwei Hilfsklicks sind erlaubt, beide eindeutig und ohne Marktwirkung:
    # (a) der Reiter 'Positions' (genau ein Treffer), wenn die Kopfzeile fehlt,
    # (b) das Panel nach oben holen (_tv_panel_umschalten, Kopfzeilen-Anker),
    #     wenn es eingeklappt ist. Sonst kein Klick ausser dem Schliessen-Knopf.
    # Zwischen den Blicken faehrt die Maus ueber die Zeile (kein Klick): bei
    # TradingView erscheint das ✕ mancher Tabellen erst beim Hover.
    ende = time.time() + 10.0
    roh, k, tab_geklickt, oben_versucht, gehovert = [], None, False, False, False
    while True:
        roh = _tv_uia_roh(w, typen)
        k = tv_close_knopf(roh, symbol, richtung, anker)
        anker = k["anker"] or anker
        if k["knopf"]:
            break
        if time.time() >= ende:
            break
        if not k["kopf"] and not tab_geklickt:
            tabs = [e for e in roh if e[1] and TV_RX_POS_TAB.search(str(e[0]).strip())
                    and (len(e) < 3 or e[2] in ("TabItem", "Button", "Text", ""))]
            if len(tabs) == 1:
                tab_geklickt = True
                r = tabs[0][1]
                _tv_uia_klick({"punkt": ((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)}, "Reiter Positions", trail)
                _warte(0.5, 0.3)
                continue
        if not k["kopf"] and not oben_versucht:
            oben_versucht = True
            try:
                if tv_panel_eingeklappt(roh, _tv_fenster_rect(w)) and _tv_panel_umschalten(w, trail, "oben"):
                    maximiert[0] = True
                    _warte(0.6, 0.3)
                    continue
            except Exception as e:
                trail.append(f"Panel-Umschalten abgebrochen: {type(e).__name__}")
        if k["zeile"] and not gehovert:
            gehovert = True
            zr = k["zeile"]
            try:
                _maus_fahren(int(k["anker"][0] + 40) if k["anker"] else 200, int(zr["y"]))
                trail.append(f"Maus ueber Zeile {zr['symbol']} (y={zr['y']}), kein Klick")
            except Exception:
                pass
        _warte(0.4, 0.25)
    if not k["knopf"]:
        gesehen = (k["grund"] + " | Kandidaten: " + (" | ".join(f"{x['typ']}:{x['text']}" for x in k["kandidaten"]) or "keine")
                   + " | Zone: " + tv_positions_zone(roh))
        return raus("close_knopf_unklar", f"Schliessen-Knopf fuer {root} nicht eindeutig — nichts geklickt. "
                    + k["grund"], "knopf", gesehen=gesehen, zeile=k["zeile"], zeilen=k["zeilen"])
    trail.append(f"Zeile {k['zeile']['symbol']} (Seite {k['zeile']['seite'] or '?'}), Knopf '{k['knopf']['text']}'")
    namen_vorher = {str(e[0]).strip() for e in roh if e[1]}

    # ═══ AB HIER UNUMKEHRBAR: genau der Knopf, dessen Name eben bewiesen wurde ═══
    t_klick = time.time()
    ok, fk = _tv_uia_klick(k["knopf"], f"Schliessen ({k['knopf']['text'][:30]})", trail)
    if not ok:
        return raus("close_knopf_unklar", fk + " — nichts geschlossen.", "knopf")
    res["geklickt"], res["retry_ok"] = True, False

    letzt_uia = [None]          # letzter UIA-Blick: Positionen (fuer positionen_danach / ende_unklar)

    def weg_in_tabelle(roh_x):
        """UIA-Blick ohne die Zeile der Wurzel? -> True/False/None (Kopf nicht zu sehen).
        NIE 'weg', solange ein Rueckfrage-Dialog mit Knoepfen (Bestaetigen/
        Abbrechen, neu seit dem Klick) zu sehen ist (24.09.2026, UIA-Vollpfad:
        Chrome nimmt die Seite hinter einem modalen Dialog per aria-hidden aus
        der UIA — die Tabelle 'fehlt' dann, obwohl die Position offen ist).
        Bewusst NUR Knoepfe, nicht der Dialog-Text: TradingViews Toast 'Close
        position order placed …' passt auf TV_RX_CLOSE_DIALOG, hat aber keine
        Knoepfe — er darf den Beweis nicht blockieren."""
        kb = tv_close_knopf(roh_x, symbol, richtung, anker)
        if not kb["kopf"]:
            return None
        letzt_uia[0] = tv_positionen_auspacken(tv_positions_lesen(roh_x, tv_positions_kopf(roh_x, anker)))
        b = tv_close_bestaetigung(roh_x, namen_vorher)
        if b["ja"] or b["nein"]:
            return False
        return kb["zeilen"] == 0

    def weg_im_reader(nach):
        """Frischer Reader-Stand nach 'nach' ohne die Position? -> (True/False/None, st, empf)
        Auf dem UIA-Weg immer (None, None, None) — der Reader wird nicht gefragt."""
        if quelle != "reader":
            return None, None, None
        st2 = _tv_http("/positions", timeout=2.0)
        if not st2 or st2.get("an") is False or st2.get("blind") or not isinstance(st2.get("positionen"), list):
            return None, st2, None
        try:
            e2 = (time.time() - float(st2["alter_s"])) if st2.get("alter_s") is not None else float(st2.get("ts") or 0) / 1000.0
        except (TypeError, ValueError):
            return None, st2, None
        if e2 < nach:
            return None, st2, None
        return (not tv_positionen_treffer(st2["positionen"], symbol, richtung)), st2, e2

    # --- 5: Rueckfrage bestaetigen (falls TradingView eine zeigt) — bis 8 s ---
    ende_d = time.time() + 8.0
    bestaetigung, letzte = "keine", None
    while time.time() < ende_d:
        _warte(0.3, 0.2)
        roh_d = _tv_uia_roh(w, typen)
        weg = weg_im_reader(t_klick)[0] if quelle == "reader" else weg_in_tabelle(roh_d)
        if weg:
            break                        # ohne Rueckfrage direkt geschlossen
        letzte = tv_close_bestaetigung(roh_d, namen_vorher)
        if len(letzte["ja"]) == 1:
            ok, fk = _tv_uia_klick(letzte["ja"][0], f"Bestaetigen ({letzte['ja'][0]['text'][:30]})", trail)
            if not ok:
                return raus("bestaetigung_unklar", fk + " — Rueckfrage steht evtl. noch offen, in TradingView nachsehen.",
                            "dialog", gesehen=" | ".join(letzte["neu"]))
            bestaetigung = "dialog"
            break
        if len(letzte["ja"]) >= 2 or (letzte["dialog"] and time.time() > t_klick + 4.0 and not letzte["ja"]):
            # Zwei Bestaetigen-Kandidaten, oder ein Dialog ohne eindeutigen Knopf:
            # nichts raten — ESC (= Abbrechen) und ehrlich melden.
            try:
                from pywinauto import keyboard
                keyboard.send_keys("{ESC}")
                trail.append("ESC (Rueckfrage abgebrochen, nichts bestaetigt)")
            except Exception:
                pass
            # War es gar keine Rueckfrage, sondern TradingViews Meldung zum schon
            # erfolgten Schliessen ('Close position … placed')? Dann sagt der Reader
            # jetzt 'weg' — und der Beweis unten zaehlt, nicht das ESC.
            _warte(0.4, 0.3)
            weg = weg_im_reader(t_klick)[0] if quelle == "reader" else weg_in_tabelle(_tv_uia_roh(w, typen))
            if weg:
                trail.append(f"{'Reader' if quelle == 'reader' else 'UIA-Tabelle'} meldet die Position schon weg "
                             "— keine Rueckfrage, weiter zum Beweis")
                break
            return raus("bestaetigung_unklar", "Rueckfrage nach dem Klick nicht eindeutig — mit ESC abgebrochen, "
                        "nichts bestaetigt. In TradingView nachsehen. Neu seit dem Klick: " + " | ".join(letzte["neu"]),
                        "dialog", gesehen=" | ".join(letzte["neu"]),
                        kandidaten=[x["text"] for x in letzte["ja"]])
    res["bestaetigung"] = bestaetigung
    if bestaetigung == "dialog":
        trail.append("Rueckfrage bestaetigt")

    # --- 6: Beweis — Reader JUENGER als der Klick und OHNE die Position, Streak 2;
    #        Reader blind oder UIA-Weg -> UIA-Tabelle zweimal ohne Zeile --------
    ende_b = t_klick + timeout_s
    streak, streak_tab, e_letzt, st_letzt, blind_seit = 0, 0, None, None, None
    while time.time() < ende_b:
        _warte(0.35, 0.25)
        if quelle != "reader":
            streak_tab = streak_tab + 1 if weg_in_tabelle(_tv_uia_roh(w, typen)) else 0
            if streak_tab >= 2:
                trail.append("Position weg (UIA-Tabelle, 2 Blicke)")
                res["beweis"] = "tabelle"
                break
            continue
        weg, st2, e2 = weg_im_reader(t_klick)
        if weg is None:
            blind_seit = blind_seit or time.time()
            if time.time() - blind_seit >= 3.0:
                streak_tab = streak_tab + 1 if weg_in_tabelle(_tv_uia_roh(w, typen)) else 0
                if streak_tab >= 2:
                    trail.append("Position weg (UIA-Tabelle, 2 Blicke; Reader blind)")
                    res["beweis"] = "tabelle"
                    break
            continue
        blind_seit = None
        if weg and (e_letzt is None or e2 > e_letzt):
            streak += 1
            st_letzt, e_letzt = st2, e2
            if streak >= 2:
                trail.append("Position weg (Reader, 2 frische Staende)")
                res["beweis"] = "reader"
                break
        elif not weg:
            streak, st_letzt = 0, st2
    if not res.get("beweis"):
        roh_u = _tv_uia_roh(w, typen)
        neu = [n for n in (str(e[0]).strip() for e in roh_u if e[1]) if n and n not in namen_vorher and 2 < len(n) <= 60]
        return raus("ende_unklar", f"Schliessen geklickt, aber {timeout_s:.0f} s danach zeigt "
                    f"{'der Reader' if quelle == 'reader' else 'die UIA-Tabelle'} die Position "
                    f"{root} noch — erst in TradingView nachsehen, NICHT blind wiederholen. Neu seit dem Klick: "
                    + (" | ".join(list(dict.fromkeys(neu))[:12]) or "nichts"), "beweis",
                    positionen_danach=(tv_positionen_auspacken((st_letzt or {}).get("positionen"))
                                       if quelle == "reader" else (letzt_uia[0] or [])))

    # --- 7: Today's P&L aus einem Bedienfeld bzw. UIA-Stand NACH dem Beweis --
    t_ende = time.time()
    _warte(1.0, 0.6)          # Tradovate bucht den realisierten G&V einen Moment spaeter
    if quelle == "reader":
        bf2 = _tv_bf(nach=t_ende, timeout=6.0) or bf
        t_info = today_aus(bf2)
        danach = tv_positionen_auspacken((st_letzt or {}).get("positionen"))
        userscript = bf2.get("version")
    else:
        u2 = _tv_uia_stand(w, trail, symbol, anker, None, hilfsklicks=False, sek=0.0)
        t_info = _tv_today_aus_uia(u2)
        danach = u2["positionen"] if u2["ok"] else (letzt_uia[0] or [])
        userscript = None
    trail.append(f"Danach ({quelle}): {len(danach)} Pos, Today {t_info['today_pnl']} ('{t_info['today_label']}')")
    return raus("", f"Position {root} auf {res['konto_aktiv'][:40]} geschlossen (bewiesen: {res['beweis']}"
                + (", Rueckfrage bestaetigt" if bestaetigung == "dialog" else "") + ")"
                + (f", Today's P&L {t_info['today_pnl']:g}" if t_info["today_pnl"] is not None else
                   ", Tages-G&V nicht gefunden — 'summary' zeigt die Labels"),
                "fertig", ok=True, bestaetigt=True, positionen_danach=danach,
                gelesen_at=time.strftime("%Y-%m-%dT%H:%M:%S"), userscript=userscript, **t_info)


def modus_tvorder(cmd):
    """Die Kette 1-5. Jeder Schritt beweist sich am naechsten Bedienfeld-Stand,
    bevor der naechste beginnt."""
    trail = _StempelSpur()
    res = {"ok": False, "retry_ok": True, "msg": "", "trail": "",
           "schritt": "start"}

    def raus(msg, schritt, retry_ok=True):
        res["msg"] = msg
        res["schritt"] = schritt
        res["retry_ok"] = retry_ok
        res["trail"] = _spur(trail)
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
    w, f = _tv_fenster_holen(trail, begriff, cmd["symbol"])
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

    # --- Schritt 5: das Handelspanel bedienen ------------------------------
    # Es wird NICHTS geoeffnet: bei TradingView ist das "Order-Ticket" kein
    # Dialog, sondern das fest angedockte Panel rechts (Fund aus Finns
    # Panel-Dump 31.08.2026 -- Shift+T aus .195 war ein Irrweg, das erzeugt eine
    # Order-Linie im Chart). Ist der Trade-Bereich zugeklappt, gibt es das
    # Element gar nicht.
    richtung = str(cmd["richtung"]).lower()
    mit_sltp = cmd.get("sl_usd") not in (None, "", 0)

    if not (bf.get("ticket") or {}).get("offen"):
        return raus("Das TradingView-Handelspanel ist zu. Oben rechts auf 'Trade' "
                    "klicken, sodass rechts Markt/Limit/Stop, Einheiten und der "
                    "Kauf-Knopf stehen — dann erneut starten. Puls klappt es "
                    "BEWUSST nicht selbst auf: ein Klick auf einen Knopf, den er "
                    "nicht sicher erkennt, ist auf dieser Seite kein harmloser "
                    "Fehlversuch.", "panel")

    if mit_sltp:
        # Die TP/SL-Wertfelder im Panel tragen weder id noch data-name -- sie
        # sind nur ueber ihre Lage zu finden. Raten waere hier besonders teuer:
        # eine Zahl im falschen Feld ist ein falscher Stop. Also ehrlich
        # anhalten, statt die Order ohne Absicherung durchzuschieben.
        return raus("SL/TP kann Puls im Handelspanel noch nicht setzen — die "
                    "Wertfelder dort haben keine eindeutige Kennung. Entweder im "
                    "Order-Popup den SL/TP-Schalter ausschalten und von Hand "
                    "setzen, oder auf die naechste Stufe warten. Es wurde NICHTS "
                    "platziert.", "sltp")

    # Orderart auf Markt. Ein Klick auf einen bereits aktiven Reiter ist
    # folgenlos, deshalb wird nicht erst geprueft, ob er schon steht.
    markt = _tv_element(bf, "ticket", "markt")
    if not markt:
        return raus("Der Reiter 'Markt' im Handelspanel wurde nicht gefunden. "
                    "Steht das Panel auf Limit/Stop? Von Hand auf Markt stellen.",
                    "markt")
    ok, f = _tv_klick(markt["rect"], bf["geo"], klient(), "Reiter Markt", trail)
    if not ok:
        return raus(f, "markt")
    _warte(0.4, 0.3)

    # Menge
    bf = _tv_bf(nach=time.time(), timeout=6.0) or bf
    menge_el = _tv_element(bf, "ticket", "menge")
    if not menge_el:
        return raus("Das Einheiten-Feld im Handelspanel wurde nicht gefunden — "
                    "nichts platziert.", "menge")
    ok, f = _tv_klick(menge_el["rect"], bf["geo"], klient(), "Einheiten-Feld", trail)
    if not ok:
        return raus(f, "menge")
    ok, f = _tv_tippen(tv_zahl_text(cmd["volumen"]), "Einheiten", trail)
    if not ok:
        return raus(f, "menge")
    _warte(0.3, 0.3)

    # Richtung waehlen (Kauf-/Verkauf-Kachel oben im Panel). Das platziert noch
    # nichts -- es stellt nur ein, was der grosse Knopf unten tun wird.
    bf = _tv_bf(nach=time.time(), timeout=6.0) or bf
    seite_el = _tv_element(bf, "panel", "kaufen" if richtung == "buy" else "verkaufen")
    if not seite_el:
        return raus(f"Die {'Kauf' if richtung == 'buy' else 'Verkauf'}-Kachel im "
                    "Handelspanel wurde nicht gefunden — nichts platziert.", "seite")
    ok, f = _tv_klick(seite_el["rect"], bf["geo"], klient(),
                      "Kauf" if richtung == "buy" else "Verkauf", trail)
    if not ok:
        return raus(f, "seite")
    _warte(0.5, 0.4)

    # --- Ruecklesen am Senden-Knopf, bevor geklickt wird -------------------
    # Der Knopf beschriftet sich selbst mit Richtung, Menge, Symbol und
    # Orderart ("Kauf 3 NQU6 MARKT"). Das prueft nicht ein Eingabefeld,
    # sondern das, was das Panel selbst zu tun glaubt -- die belastbarste
    # Probe im ganzen Ablauf.
    bf = _tv_bf(nach=time.time(), timeout=8.0)
    if not bf:
        return raus("Kein frischer Bedienfeld-Stand zum Ruecklesen — nichts "
                    "platziert.", "ruecklesen")
    senden = _tv_element(bf, "ticket", "senden")
    if not senden:
        return raus("Der Senden-Knopf im Handelspanel wurde nicht gefunden — "
                    "alles eingestellt, der letzte Klick fehlt. In TradingView "
                    "selbst ausloesen.", "senden")
    passt, grund = tv_senden_text_passt(senden.get("text"), richtung, cmd["volumen"])
    if not passt:
        return raus(f"Senden-Knopf zeigt nicht die geplante Order: {grund}. "
                    "NICHTS platziert.", "ruecklesen")
    trail.append(f"Senden-Knopf zurueckgelesen: '{(senden.get('text') or '')[:40]}'")

    # --- Probelauf: alles ausser dem Klick ---------------------------------
    # {"probe": true} faehrt die VOLLE Kette -- Tab, Konto, Symbol, Markt-Reiter,
    # Menge, Richtung -- und haelt genau hier an. Der Halt sitzt bewusst NACH
    # dem Ruecklesen: ein Probelauf, der ausgerechnet die letzte Pruefung
    # auslaesst, beantwortet die interessanteste Frage nicht. Das Panel bleibt
    # danach ausgefuellt stehen; wegklicken ist Handarbeit, weil ein
    # Abbruch-Klick wieder ein geratener Klick waere.
    if cmd.get("probe"):
        res["ok"] = True
        res["probe"] = True
        res["senden_text"] = senden.get("text")
        return raus("PROBELAUF: alles eingestellt und zurueckgelesen, NICHT "
                    f"geklickt. Der Knopf zeigt '{(senden.get('text') or '')[:40]}'. "
                    "Das Panel bleibt so stehen — von Hand ausloesen oder aendern.",
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


def _kind_fenster(hauptfenster, voll=False):
    """Kind-'Window'-Elemente des Hauptfensters — Standard: nur Kinder und
    Enkel, NIE der volle Baum (02.09.2026, Finns '10 Sekunden zwischen jedem
    Step' trotz Anker: descendants() ueber das MT5-HAUPTfenster kostet auf
    seinem Build Sekunden PRO AUFRUF, und die Dialog-Sucher riefen es in
    ihren Poll-Schleifen nach jedem F9/Rechtsklick erneut. MT5 haengt seine
    Dialoge als DIREKTE Kinder ans Hauptfenster — Fund 15.08.2026 — die
    Enkel-Ebene ist nur Sicherheitsmarge aus je einem billigen
    Children-Aufruf pro Kind). voll=True ist der eine Abschluss-Versuch,
    bevor ein Sucher endgueltig aufgibt."""
    if voll:
        try:
            return hauptfenster.descendants(control_type="Window")
        except Exception:
            return []
    out = []
    try:
        kinder = hauptfenster.children()
    except Exception:
        return out
    for k in kinder:
        try:
            if (k.element_info.control_type or "") == "Window":
                out.append(k)
        except Exception:
            pass
    # Enkel IMMER mitnehmen, nicht nur wenn oben nichts kam: Chart-Fenster
    # sind selbst 'Window'-Kinder — ein Dialog unter dem MDI-Bereich waere
    # sonst unsichtbar, obwohl Kinder gefunden wurden.
    for k in kinder:
        try:
            out.extend(k.children(control_type="Window"))
        except Exception:
            continue
    return out


def _finde_order_dialog(hauptfenster, timeout=10.0):
    """Nach F9: den Order-Dialog suchen — als TOP-LEVEL-Fenster UND als
    Kind-Fenster des Terminals (Fund 15.08.2026: MT5 haengt den F9-Dialog als
    Child ans Hauptfenster, die reine Top-Level-Suche fand ihn nie, obwohl er
    sichtbar offen war). Titel 'Order…' oder die typische Feldstruktur.
    Kind-Suche seit 02.09.2026 billig (s. _kind_fenster); der fruehere
    title_re-Griff ist raus — er lief als Regex-Suche jeden Schleifendurchlauf
    durch den ganzen Baum und fand nie etwas, das a/b nicht auch finden."""
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
        # b) Kind-/Enkel-Fenster des Hauptfensters (billig)
        try:
            for d in _kind_fenster(hauptfenster):
                if _ist_order_dialog(d):
                    return d
        except Exception:
            pass
        _warte(0.3, 0.3)
    # Abschluss: EINMAL der volle Baum — falls der Dialog je tiefer haengt
    # als Kinder/Enkel (bisher nie beobachtet), kostet das einen Durchlauf
    # statt eines Fehllaufs.
    try:
        for d in _kind_fenster(hauptfenster, voll=True):
            if _ist_order_dialog(d):
                return d
    except Exception:
        pass
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


def _feld_tippen(el, wert, name, trail, rahmen=None):
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
    # 31.08.2026, Finns Frage "wie kann es sein, dass er manchmal den TP/SL
    # einfach nicht trifft? 5x geklappt, beim 6. nicht":
    # Seine Spur endete mit "SL NICHT uebernommen: 29311.07" — und DAVOR stand
    # nichts. Genau das ist die Auskunft: schlaegt nur das Ruecklesen fehl,
    # steht dort "SL-Ruecklesen zeigt 'X' statt Y"; fuellt sich das Feld selbst,
    # steht "SL-Feld leert nicht". Beide Zeilen fehlten. Es sind also beide
    # Versuche in einer AUSNAHME gelandet — und die verschwand hier im
    # 'except Exception: continue', ohne dass irgendwo stand, welche.
    # Zwei Konsequenzen:
    #  (1) Die Ausnahme wandert in die Spur. Ohne sie ist jede Ursachensuche
    #      Raten — dieselbe Lehre wie beim Copier-Log heute frueh.
    #  (2) Ein Wiederholungsversuch, der EXAKT dasselbe tut, hilft nur gegen
    #      Zufall. Der wahrscheinlichste Grund fuer ein fehlgeschlagenes
    #      set_focus() ist, dass in diesem Moment ein anderes Fenster den
    #      Vordergrund hat — bei fuenf offenen MT5-Terminals plus Browser auf
    #      dem PC keine Seltenheit, und es erklaert genau das Muster
    #      "meistens gut, manchmal nicht". Deshalb gehen Versuch 2 und 3 den
    #      MENSCHEN-Weg: kurz Luft holen und ins Feld KLICKEN.
    # Geklickt wird nur, wenn das Feld nachweislich INNERHALB des Dialogs
    # liegt (rahmen): ein veraltetes UIA-Element koennte sonst ein Rechteck
    # von irgendwo liefern, und ein Klick ins Blaue ist im Terminal das
    # Letzte, was man will.
    def _ins_feld_klicken():
        r = el.rectangle()
        if rahmen is not None:
            try:
                rr = rahmen.rectangle()
                if not (rr.left <= r.left and r.right <= rr.right
                        and rr.top <= r.top and r.bottom <= rr.bottom):
                    trail.append(f"{name}-Feld liegt ausserhalb des Dialogs — nicht geklickt")
                    return False
            except Exception:
                return False
        return _klick_absolut(r.mid_point().x, r.mid_point().y)

    for _versuch in (1, 2, 3):
        try:
            if _versuch == 1:
                el.set_focus()
            else:
                _warte(0.25, 0.25)      # dem Vordergrund-Wechsel Zeit geben
                try:
                    el.set_focus()
                except Exception:
                    pass
                if _ins_feld_klicken():
                    trail.append(f"{name}-Feld angeklickt (Versuch {_versuch})")
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
        except Exception as e:
            # Die Ausnahme IST die Antwort — sie darf nicht hier verschwinden.
            trail.append(f"{name}-Versuch {_versuch} abgebrochen: "
                         f"{type(e).__name__}: {str(e)[:70]}")
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
    15.08.2026 gilt fuer jeden MT5-Dialog), aber auf den Aendern-Dialog.
    Kind-Suche billig (02.09.2026, s. _kind_fenster) — dieser Sucher laeuft
    im Zeilen-Scan nach JEDEM Rechtsklick, der volle Baum-Durchlauf hier war
    ein Kern der '10 Sekunden pro Schritt'."""
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
            for d in _kind_fenster(hauptfenster):
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
    lesend auf 'Position schon weg' geprueft wird (Ein-Klick-Modus).
    Kind-Suche billig statt voller Baum (02.09.2026, s. _kind_fenster) —
    dieser Sucher laeuft in der Aufrufer-Schleife im Sekundentakt."""
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
    fenster.extend(_kind_fenster(hauptfenster))
    for w in fenster:
        try:
            for b in w.descendants(control_type="Button"):
                if ist_schliessen_knopf(b.window_text(), ticket):
                    return w, b
        except Exception:
            continue
    return None, None


def _einklick_kennzeichen(w):
    """Traegt dieses Fenster das Kennzeichen des Ein-Klick-Haftungsausschlusses?
    Titel ODER sichtbarer Text (01.09.2026, zweiter Anlauf): der Titel allein
    als Pflicht-Haelfte war zu streng — liefert UIA fuer ein KIND-Fenster keine
    oder eine andere Beschriftung, faellt die Erkennung still aus, und still
    ausfallen ist hier dasselbe wie gar nicht da sein. Der Fliesstext des
    Dialogs nennt 'Ein-Klick-Handel'/'One Click Trading' ohnehin mehrfach."""
    try:
        if ist_einklick_dialog(w.window_text()):
            return True
    except Exception:
        pass
    for typ in ("Text", "Document", "Edit"):
        try:
            for t in w.descendants(control_type=typ):
                x = (t.window_text() or "").lower()
                if ("ein-klick" in x or "ein klick" in x or "one click" in x
                        or "one-click" in x):
                    return True
        except Exception:
            continue
    return False


def _einklick_haftung_annehmen(hauptfenster, trail, melden=False):
    """Den Ein-Klick-Haftungsausschluss durch ZUSTIMMEN wegbekommen (Finns
    Auftrag 01.09.2026: "sollte diese Meldung kommen, er okay drueckt und dann
    neu aufs x drueckt").

    Das ist die EINZIGE Stelle, an der der Bot einen fremden Dialog bestaetigt
    statt ihn per Abbrechen/ESC wegzuraeumen (_fremde_dialoge_schliessen).
    Erlaubt ist sie, weil dieser Dialog NICHTS ausloest: er schaltet nur den
    Ein-Klick-Modus frei, der Close selbst braucht danach ohnehin einen neuen
    Klick. Getroffen wird ueber die eigene Knopf-Signatur, nie ueber Position
    oder Reihenfolge im Dialog.

    Gesucht wird in DENSELBEN ZWEI QUELLEN wie beim Close-Dialog
    (_finde_close_dialog): Top-Level-Fenster des Terminal-Prozesses UND
    Kind-Fenster des Hauptfensters. Die erste Fassung sah nur die erste Quelle
    und traf bei Finn nicht — und dieser Dialog hat auf demselben PC auch schon
    die Abbrechen-Runde von _fremde_dialoge_schliessen ueberlebt, die genauso
    nur dort nachsieht. Zwei Wege, ein Fund: die Vermutung "Kind-Fenster" ist
    damit die einzige, die beides erklaert.

    Erkannt wird aus zwei Haelften: Knopf-Signatur UND Kennzeichen des Fensters
    (_einklick_kennzeichen). Andere Zustimmungs-Dialoge von MT5 — Broker-AGB
    beim Login, Algo-Handel — traegt der Bot damit nicht mit an.

    Beweis wie ueberall: angenommen ist er erst, wenn Dialog UND Knopf WEG
    sind. Rueckgabe: 'angenommen' | 'gescheitert' | 'keiner'."""
    from pywinauto import Desktop
    try:
        pid = hauptfenster.element_info.process_id
    except Exception:
        return "keiner"

    fenster, gesehen = [], []
    try:
        for d in Desktop(backend="uia").windows():
            try:
                if d.element_info.process_id == pid and d.is_visible() \
                        and d.element_info.class_name != MT5_KLASSE:
                    fenster.append(d)
            except Exception:
                continue
    except Exception:
        pass
    # Kind-/Enkel-Suche statt vollem Baum (02.09.2026, s. _kind_fenster) —
    # der Haftungs-Dialog wurde am 01.09. als Kind-Fenster bewiesen, tiefer
    # hing er nie; der volle Durchlauf lief bei JEDEM Close zweimal mit.
    fenster.extend(_kind_fenster(hauptfenster))

    dlg = knopf = None
    for d in fenster:
        try:
            titel = (d.window_text() or "").strip()
            treffer = None
            for b in d.descendants(control_type="Button"):
                if ist_einklick_akzeptieren_knopf(b.window_text()):
                    treffer = b
                    break
            if treffer is None:
                if melden and titel:
                    gesehen.append(titel[:28])
                continue
            if not _einklick_kennzeichen(d):
                # Zustimmen-Knopf ohne Ein-Klick-Kennzeichen: ein anderer
                # Vertrag. Nicht anfassen, aber in die Spur schreiben — sonst
                # sieht "kein Dialog gefunden" wie Abwesenheit aus.
                trail.append(f"Zustimmungs-Dialog OHNE Ein-Klick-Kennzeichen "
                             f"uebergangen ('{titel[:28]}')")
                continue
            dlg, knopf = d, treffer
            break
        except Exception:
            continue

    if knopf is None:
        if melden:
            trail.append("kein Haftungsausschluss offen"
                         + (f" (Fenster im Prozess: {', '.join(gesehen[:6])})"
                            if gesehen else " (keine Nebenfenster)"))
        return "keiner"
    try:
        trail.append(f"Ein-Klick-Haftungsausschluss offen "
                     f"('{(dlg.window_text() or '?')[:32]}')")
    except Exception:
        pass

    def _zu():
        """Weg ist er, wenn der Knopf nicht mehr da ist — der Dialog kann als
        Kind-Fenster im Baum stehenbleiben, der Knopf verschwindet aber."""
        try:
            if not knopf.is_visible():
                return True
        except Exception:
            return True   # Element nicht mehr ansprechbar = weg
        try:
            return not dlg.is_visible()
        except Exception:
            return True

    def _weg_leertaste():
        knopf.set_focus()
        _warte(0.1, 0.15)
        knopf.type_keys("{SPACE}", set_foreground=False)

    def _weg_sendinput():
        r = knopf.rectangle()
        _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=6)
        if not _klick_absolut(r.mid_point().x, r.mid_point().y):
            raise RuntimeError("SendInput abgelehnt")

    # Dieselbe Kaskade wie beim Schliessen-/Aendern-Knopf (.52/.64): echte
    # Eingabe zuerst, nach jedem Weg lesend pruefen — nie zwei Wege blind
    # hintereinander. Der Grund fuer JEDEN gescheiterten Weg geht in die Spur
    # (Lehre 31.08.2026): ein Bot, der den Grund kennt und wegwirft, schickt
    # die naechste Ferndiagnose in die falsche Richtung.
    for wegname, tu in (("Fokus+Leertaste", _weg_leertaste),
                        ("SendInput-Klick", _weg_sendinput),
                        (".click()", lambda: knopf.click()),
                        ("click_input", lambda: knopf.click_input())):
        try:
            tu()
        except Exception as e:
            trail.append(f"Zustimmen {wegname}: {type(e).__name__}")
            continue
        ende = time.time() + 2.0
        while time.time() < ende:
            _warte(0.2, 0.2)
            if _zu():
                trail.append(f"Haftungsausschluss angenommen ({wegname})")
                return "angenommen"
        trail.append(f"Zustimmen {wegname}: ohne Wirkung")
    trail.append("Haftungsausschluss liess sich nicht annehmen")
    return "gescheitert"


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


def _anker_lesen(pfad):
    """Anker-Datei als dict lesen — fehlt/kaputt = leeres dict."""
    if not pfad:
        return {}
    try:
        with open(pfad, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _anker_schreiben(pfad, **felder):
    """Felder in die Anker-Datei MERGEN statt sie zu ueberschreiben
    (01.09.2026): seit der Handel-Tab seinen Klickpunkt mitspeichert, darf
    der Zeilen-Anker den Tab-Punkt nicht mehr wegschreiben — und umgekehrt.
    Wert None LOESCHT den Schluessel (02.09.2026): ein Anker, der bewiesen
    danebenlag, muss raus, sonst klickt jeder Lauf denselben Fehlpunkt."""
    if not pfad:
        return
    d = _anker_lesen(pfad)
    for k, v in felder.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    try:
        with open(pfad, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def _reihen_scan(w, ticket, trail, maus_grenze, anker_pfad=None, nur_anker=False):
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
    try:
        a = _anker_lesen(anker_pfad)
        ax = hr.left + int((hr.right - hr.left) * float(a["x_frac"]))
        ay = hr.bottom - int(a["y_off"])
        if maus_grenze is None or ay >= maus_grenze:
            punkte.append(("Anker", ax, ay))
    except Exception:
        pass
    # Anker-SCHNELLWEG (01.09.2026, Finns Tempo-Beschwerde): nur_anker=True
    # probiert AUSSCHLIESSLICH den gemerkten Punkt — sitzt er (Normalfall:
    # Terminal blieb offen, Zeile liegt wo sie beim letzten Trade lag), ist
    # der Dialog nach einem Rechtsklick offen. Ohne gemerkten Anker gibt es
    # nichts zu probieren: sofort zurueck, der Aufrufer faehrt den vollen Weg.
    if nur_anker and not punkte:
        return None
    if not nur_anker:
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
                _anker_schreiben(anker_pfad,
                                 x_frac=(px_ - hr.left) / max(1, hr.right - hr.left),
                                 y_off=hr.bottom - py_)
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
    if nur_anker:
        trail.append(f"Anker-Schnellweg ohne Treffer ({grau}x ausgegraut)")
    else:
        trail.append(f"Zeilen-Scan ohne Treffer (Fenster {hr.right - hr.left}x{hr.bottom - hr.top}, "
                     f"Band -60..-{band_max}px, x={gx}, {len(punkte)} Punkte, {grau}x ausgegraut)")
    return None


def _handel_tab_aktivieren(w, trail=None, maus_grenze=None, anker_pfad=None,
                           anker_nutzen=True):
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
    # Gemerkter Tab-Klickpunkt ZUERST (01.09.2026, Finns Tempo-Beschwerde
    # '10 Sekunden pro Schritt'): die Element-Suche unten enumeriert
    # schlimmstenfalls den KOMPLETTEN UIA-Baum des Terminals — Marktuebersicht,
    # Navigator, Charts — und auf Builds, deren Toolbox fuer UIA unsichtbar
    # ist (18.08.), laufen ALLE fuenf Durchgaenge jedes Mal ins Leere. Der
    # Reiter sitzt aber fest in der Toolbox-Leiste, also wird sein einmal
    # gefundener Punkt pro PC in der Anker-Datei gemerkt und direkt angeklickt.
    # X ABSOLUT vom linken Rand, nicht als Breiten-Anteil (02.09.2026, Finns
    # Fund am VPS: der Bot klickte 'Belastung' statt 'Handel' — die Reiter
    # sitzen links FEST und skalieren nicht mit der Fensterbreite; der
    # x_frac-Punkt vom Vortag wanderte bei anderer RDP-Breite genau einen
    # Reiter nach rechts). Alte handel_x_frac-Eintraege werden ignoriert und
    # beim naechsten Suche-Treffer geloescht. Ob der Klick WIRKLICH in der
    # Handel-Liste gelandet ist, beweist der Aufrufer lesend (Rechtsklick-Menue
    # mit 'Aendern'-Punkt) — schlaegt das fehl, verwirft er diesen Anker.
    if anker_nutzen:
        try:
            a = _anker_lesen(anker_pfad)
            wr = w.rectangle()
            tx = wr.left + int(a["handel_x_off"])
            ty = wr.bottom - int(a["handel_y_off"])
            if maus_grenze is None or ty >= maus_grenze:
                _maus_fahren(tx, ty, schritte=4)
                _klick_absolut(tx, ty)
                if trail is not None:
                    trail.append(f"Handel-Tab per Anker geklickt @({tx},{ty})")
                _warte(0.3, 0.3)
                return "anker"
        except Exception:
            pass
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
                # Punkt fuer den naechsten Lauf merken (01.09.2026, s.o.):
                # x absolut vom linken Rand (Reiter sitzen links fest),
                # y vom unteren Rand (Toolbox haengt unten) — der stale
                # x_frac-Schluessel fliegt dabei raus (02.09.2026).
                try:
                    wr = w.rectangle()
                    _anker_schreiben(anker_pfad,
                                     handel_x_off=cx - wr.left,
                                     handel_y_off=wr.bottom - cy,
                                     handel_x_frac=None)
                except Exception:
                    pass
                _warte(0.3, 0.3)
                return "suche"
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

    # Echo pausiert? (28.08.2026, Not-Aus) — dann gar nicht erst anfangen zu
    # klicken. Die Order ist da laengst platziert; SL/TP traegt Finn von Hand
    # nach oder nach dem Fortsetzen ein neuer Lauf.
    if is_paused():
        trail.append("⏸ Echo pausiert — keine SL/TP-Klicks")
        return None

    # 0) Anker-SCHNELLWEG zuerst (01.09.2026, Finns Tempo-Beschwerde: 'von
    # Popup oeffnen bis SL setzen soll das grob in 10 Sekunden gehen'). Die
    # Tab-Aktivierung stand bisher VOR jedem Scan und bezahlte auf Builds mit
    # UIA-unsichtbarer Toolbox jeden Lauf mit mehreren vollen Baum-Durchlaeufen
    # — der Hauptteil der '10 Sekunden pro Schritt'. Im Normalfall (Terminal
    # blieb offen, Toolbox steht noch auf 'Handel', Anker vom letzten Trade
    # sitzt) ist der Aendern-Dialog nach EINEM Rechtsklick offen. Nur wenn der
    # Schnellweg leer ausgeht (frischer Start, Posteingang-Fall vom 28.08.,
    # verschobene Zeile), laeuft die Reparatur: Toolbox auf 'Handel', dann der
    # volle Band-Scan. Sicherheit unveraendert: geklickt wird nie blind, und
    # ob der RICHTIGE Dialog offen ist, entscheidet weiter _dialog_gehoert_zu.
    dlg = _reihen_scan(w, ticket, trail, maus_grenze, anker_pfad=anker_pfad,
                       nur_anker=True)
    if dlg is None:
        # Toolbox auf 'Handel' — sonst ist die Positionsliste unsichtbar
        # (28.08.2026, frischer Terminal-Start stand auf 'Posteingang', s.o.).
        tab_weg = _handel_tab_aktivieren(w, trail, maus_grenze, anker_pfad=anker_pfad)
        dlg = _reihen_scan(w, ticket, trail, maus_grenze, anker_pfad=anker_pfad)
        if dlg is None and tab_weg == "anker":
            # Der gemerkte Tab-Punkt hat NICHT in die Handel-Liste gefuehrt
            # (02.09.2026, Finns Fund: der Anker-Klick traf 'Belastung' statt
            # 'Handel', und ab da lief der Scan in der falschen Liste — 'ab
            # dann war der Wurm drin'). Der Scan ist der lesende BEWEIS fuer
            # den Tab-Klick: kein 'Aendern'-Menuepunkt = falsche Liste. Also:
            # verdaechtigen Punkt LOESCHEN (nie zweimal denselben Fehlklick),
            # einmal ECHT per Element-Suche aktivieren, und nur wenn die
            # wirklich einen Reiter geklickt hat, ein zweiter Scan.
            _anker_schreiben(anker_pfad, handel_x_off=None, handel_y_off=None,
                             handel_x_frac=None)
            trail.append("Tab-Anker verworfen (Scan fand nach Anker-Klick keine Handel-Zeile)")
            if _handel_tab_aktivieren(w, trail, maus_grenze, anker_pfad=anker_pfad,
                                      anker_nutzen=False) == "suche":
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
            # rahmen=dlg: erlaubt _feld_tippen den Klick-Anlauf, aber nur
            # innerhalb DIESES Dialogs (31.08.2026, s. dort).
            if not _feld_tippen(el, wert, name, trail, rahmen=dlg):
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
        msg = lese["fehler"]
        if _ist_verbindungsfehler(msg):
            msg += " — " + _UAC_HINWEIS
        return {"ok": False, "retry_ok": True, "msg": msg}
    digits = lese["digits"]
    contract_size = lese["contract_size"]
    vorher_tickets = {p["ticket"] for p in lese["positionen"]}

    # Schritt-Spur (15.08.2026): jede Station vermerken — steht bei Erfolg UND
    # Fehler in der Meldung, damit Finn/ich sofort sieht, wo der Bot steht.
    # Seit 01.09.2026 mit Sekunden-Stempel pro Station (s. _StempelSpur).
    trail = _StempelSpur()

    # Start-Versatz (28.08.2026, Finns Sorge): starten mehrere Flotten-Instanzen
    # im selben Moment, blieben sie trotz gestreuter Einzelschritte anfangs eng
    # beieinander. 0-1.2 s Wuerfel VOR dem ersten sichtbaren Schritt zieht die
    # Laeufe von Beginn an auseinander.
    _warte(0.0, 1.2)

    # 2b) Ins (vom Check bereits geoeffnete) Terminal gehen -> Guard
    w = _finde_terminal(expected)
    if w is None:
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein MT5-Fenster mit Konto {expected} gefunden. "
                       + _UAC_HINWEIS}
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
                "msg": "F9-Dialog nicht gefunden — Abbruch, nichts gesendet. [" + _spur(trail) + "]"}
    trail.append("F9-Dialog offen")
    # Kurze Setz-Zeit NACH dem Fund (02.09.2026, Finns Fund direkt nach dem
    # Tempo-Umbau: "manchmal vertippt er sich beim Asset und findet es nicht —
    # seit heute"). Vorher lieferte die sekundenlange Baum-Suche dem frisch
    # geoeffneten Dialog ungewollt Zeit, seine Felder zu verdrahten; seit der
    # Sucher in Millisekunden traf, griff der Bot ins noch bootende Feld.
    _warte(0.3, 0.25)

    # SL/TP-Schalter EINMAL oben bestimmen (frueher in Schritt 5 lokal) — der
    # F9-Direktweg (02.09.2026, Finns Idee) braucht ihn schon beim Tippen.
    mit_sltp = False
    try:
        mit_sltp = (float(cmd.get("sl_usd") or 0) > 0
                    and float(cmd.get("tp_usd") or 0) > 0)
    except (TypeError, ValueError):
        mit_sltp = False
    # Vor dem try definiert, damit Schritt 5 sie sicher sieht, auch wenn das
    # Tippen sie nie erreicht.
    sl_f9 = tp_f9 = None
    f9_getippt = False

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
        # Tipp-Weg mit Beweis und Wiederholung (02.09.2026, Finns "Vertippen"-
        # Fund): der alte Weg tippte GENAU EINMAL, in voller Geschwindigkeit
        # und ohne Leer-Beweis — MT5s Autovervollstaendigung legt aber mitten
        # im Tippen eigenen Text ins Feld, und bei vollem Tempo gewinnt mal
        # der Bot, mal die Vervollstaendigung: genau das sichtbare
        # "Vertippen". Jetzt wie in _feld_tippen: leeren UND leer nachlesen,
        # mit Tasten-Pause tippen (die Vervollstaendigung kommt mit), TAB,
        # ruecklesen — bis zu drei Anlaeufe, und jeder Fehlversuch schreibt
        # den ECHTEN Feldinhalt in die Spur statt still zu scheitern.
        for _sv in (1, 2, 3):
            if gewaehlt:
                break
            try:
                sym_combo.set_focus(); _warte(0.15, 0.2)
                sym_combo.type_keys("^a{DELETE}", set_foreground=False)
                sym_combo.type_keys("{HOME}+{END}{DELETE}", set_foreground=False)
                _warte(0.1, 0.12)
                if (_feld_lesen(sym_combo) or "").strip():
                    # Feld leert nicht (Vervollstaendigung fuellt nach) —
                    # alles markieren und DRUEBERtippen, wie in _feld_tippen
                    sym_combo.type_keys("^a", set_foreground=False)
                # Tasten-Pause pro Anschlag, pro Versuch neu gewuerfelt
                # (Jitter-Doktrin; das fixe 12-ms-Muster gilt nur fuer die
                # Maus-Animation)
                sym_combo.type_keys(symbol, with_spaces=False,
                                    set_foreground=False,
                                    pause=0.05 + random.uniform(0.0, 0.04))
                _warte(0.12, 0.15)
                sym_combo.type_keys("{TAB}", set_foreground=False)
                _warte(0.2, 0.25)
            except Exception as e:
                trail.append(f"Symbol-Tippversuch {_sv} abgebrochen: "
                             f"{type(e).__name__}: {str(e)[:60]}")
                continue
            gewaehlt = _symbol_drin()
            if not gewaehlt:
                trail.append(f"Symbol-Tippversuch {_sv}: Feld zeigt "
                             f"'{(_feld_lesen(sym_combo) or '').strip()[:24]}'")
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
        if not _feld_tippen(vol_el, f"{vol:g}", "Volumen", trail, rahmen=dlg):
            raise RuntimeError(f"Volumen-Feld uebernimmt {vol:g} nicht — "
                               f"Abbruch VOR dem Order-Knopf.")
        _warte(0.2, 0.25)

        # SL/TP SCHON HIER in den F9-Dialog tippen (02.09.2026, Finns Idee):
        # der Bot liest den Live-Kurs (ref_ask/ref_bid) ohnehin lesend vor dem
        # Platzieren, rechnet SL/TP daraus und tippt sie in die Dialogfelder —
        # dieselbe getippte Mechanik wie beim Volumen, die API bleibt lesend.
        # Nimmt der Broker sie in der Markt-Order an, entfaellt der ganze
        # fehleranfaellige Nachtrag-Weg (Zeilen-Scan/Aendern-Dialog). Der SL/TP-
        # Kurs vom Vor-Fill weicht nur um den Spread vom echten Fill ab — bei
        # $-Abstaenden vernachlaessigbar (Finns Tempo-vor-Cent-Abwaegung).
        # WICHTIG als Sicherung: schlaegt das Tippen nicht sauber an, werden
        # BEIDE Felder wieder auf 0 gesetzt — eine halb gesetzte Order koennte
        # der Broker sonst komplett ablehnen (kein Fill). Bei 0/0 laeuft alles
        # exakt wie bisher, der Nachtrag nach dem Fill uebernimmt.
        if mit_sltp:
            ref = lese.get("ref_ask") if kauf else lese.get("ref_bid")
            if not ref:
                trail.append("kein Live-Kurs fuer F9-SL/TP — Nachtrag nach Fill")
            else:
                try:
                    sl_f9, tp_f9 = berechne_sl_tp(cmd["richtung"], ref, vol,
                                                  contract_size, cmd["sl_usd"],
                                                  cmd["tp_usd"], digits)
                    fmap = _map_felder(dlg)
                    sl_el, tp_el = fmap.get("sl"), fmap.get("tp")
                    if sl_el is None or tp_el is None:
                        trail.append("F9-SL/TP-Felder nicht gefunden — Nachtrag nach Fill")
                    else:
                        ok_sl = _feld_tippen(sl_el, fmt_preis(sl_f9, digits),
                                             "F9-SL", trail, rahmen=dlg)
                        ok_tp = _feld_tippen(tp_el, fmt_preis(tp_f9, digits),
                                             "F9-TP", trail, rahmen=dlg)
                        f9_getippt = bool(ok_sl and ok_tp)
                        if not f9_getippt:
                            # Beide auf 0 zuruecksetzen — keine halb gesetzte
                            # Order (sonst evtl. komplette Ablehnung).
                            _feld_tippen(sl_el, "0", "F9-SL-Reset", trail, rahmen=dlg)
                            _feld_tippen(tp_el, "0", "F9-TP-Reset", trail, rahmen=dlg)
                            trail.append("F9-SL/TP nicht sicher — Felder auf 0, Nachtrag nach Fill")
                except Exception as _fe:
                    sl_f9 = tp_f9 = None
                    f9_getippt = False
                    trail.append(f"F9-SL/TP uebersprungen ({type(_fe).__name__}) — Nachtrag nach Fill")
            _warte(0.15, 0.2)
    except Exception as e:
        return {"ok": False, "retry_ok": True,
                "msg": f"Abbruch VOR dem Order-Knopf (nichts platziert): {e} [" + _spur(trail) + "]"}

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
                       f"Knoepfe: {', '.join(inventar) or 'keine'} [" + _spur(trail) + "]"}
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
        # ERST pruefen, DANN warten (31.08.2026, Finns Tempo-Frage): die Order
        # ist beim ersten Blick meistens schon da. Die alte Reihenfolge legte
        # trotzdem jedes Mal die volle Wartezeit davor — und weil _api_lesen
        # damals pro Aufruf neu ans Terminal andockte, war der erste Blick
        # ohnehin ueber eine Sekunde entfernt. Der Takt darunter ist jetzt
        # kurz, weil ein Lesen auf offener Verbindung nur noch Millisekunden
        # kostet. Was NICHT kuerzer wird: das Zeitfenster insgesamt.
        ende_s = time.time() + sekunden
        while True:
            st = _api_lesen(path, expected)
            if "fehler" not in st and finde_neue_position(
                    vorher_tickets, st["positionen"], symbol, cmd["richtung"], vol):
                return True
            if _dialog_weg():
                return True
            if time.time() >= ende_s:
                return False
            _warte(0.12, 0.15)

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
                       "[" + _spur(trail) + "]"}

    # 5) LESEND: Bestaetigung am Positionsstand (bis 12 s), nie der UI glauben.
    # Erster Blick sofort, erst danach im kurzen Takt nachfassen (31.08.2026) —
    # das 12-s-Fenster bleibt unveraendert, nur die Leerzeit davor faellt weg.
    ende = time.time() + 12
    _erster_blick = True
    while time.time() < ende:
        if _erster_blick:
            _erster_blick = False
        else:
            _warte(0.15, 0.2)
        nachher = _api_lesen(path, expected)
        if "fehler" in nachher:
            continue
        p = finde_neue_position(vorher_tickets, nachher["positionen"], symbol,
                                cmd["richtung"], vol)
        if p:
            fill = p["preis"]   # ECHTER Einstiegskurs der offenen Position
            trail.append(f"Position offen @ {fill}")
            # Schalter aus (18.08.2026): Order pur, SL/TP macht Finn von Hand —
            # Dialog zu, fertig, KEIN Scan. (mit_sltp steht seit 02.09. oben.)
            if not mit_sltp:
                try:
                    dlg.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                trail.append("SL/TP: manuell (Schalter aus)")
                return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                        "msg": "per Klick platziert — SL/TP bewusst NICHT gesetzt "
                               "(Schalter aus), von Hand nachtragen "
                               f"· {trail.sekunden():.0f}s",
                        "trail": _spur(trail), "symbol": symbol,
                        "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill, "ticket": p["ticket"]}
            # F9-DIREKTWEG (02.09.2026, Finns Idee): hat der Broker die im
            # F9-Dialog getippten SL/TP in die Markt-Order uebernommen, traegt
            # die frische Position sie schon (ein Deal traegt seine Stops
            # atomar). Dann ist der ganze Nachtrag-Weg unnoetig — der Fall, der
            # fast alle Klick-Probleme der letzten Tage erspart.
            if f9_getippt and sl_f9 is not None and tp_f9 is not None \
                    and sltp_bestaetigt(p["sl"], p["tp"], sl_f9, tp_f9, digits):
                try:
                    dlg.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                trail.append(f"SL {fmt_preis(sl_f9, digits)} / TP {fmt_preis(tp_f9, digits)} "
                             f"direkt im F9-Dialog gesetzt")
                return {"ok": True, "retry_ok": False, "verified": True, "mode": "f9",
                        "msg": "per Klick platziert, SL/TP direkt im Order-Dialog "
                               f"gesetzt · {trail.sekunden():.0f}s",
                        "trail": _spur(trail),
                        "symbol": symbol, "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill,
                        "sl": sl_f9, "tp": tp_f9, "ticket": p["ticket"]}
            if f9_getippt:
                # SL/TP getippt, aber die Position traegt sie nicht: dieser
                # Broker nimmt SL/TP in der Markt-Order nicht an (IOC). Einmal
                # in die Spur — das ist der Beweis, ob der Direktweg hier geht —
                # dann uebernimmt der bewaehrte Nachtrag per Klick.
                trail.append("F9-SL/TP nicht an der Position — Broker nimmt sie in "
                             "der Markt-Order nicht; Nachtrag per Klick")
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
            _erster2 = True
            while time.time() < ende2 and not bestaetigt:
                if _erster2:
                    _erster2 = False   # sofort nachsehen, s. Schritt 5
                else:
                    _warte(0.15, 0.2)
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
                        # Dauer in der Meldung (02.09.2026, Finns '10 sec pro
                        # Step, total 1-2 min'): die Sekunde steht damit direkt
                        # im Prophos-Toast, die Stationen in der Panel-Spur.
                        "msg": "per Klick platziert, SL/TP per Klick am echten "
                               f"Einstieg gesetzt · {trail.sekunden():.0f}s",
                        "trail": _spur(trail),
                        "symbol": symbol, "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill,
                        "sl": sl, "tp": tp, "ticket": p["ticket"]}
            # Position IST offen, aber SL/TP nicht bestaetigt — kritisch: klar
            # melden, NICHT erneut platzieren (retry_ok False), von Hand nachtragen.
            return {"ok": False, "retry_ok": False,
                    "msg": f"Position ist OFFEN @ {fill}, aber SL/TP-Klick nicht bestaetigt "
                           f"({k.get('msg')}) — im Terminal SL {fmt_preis(sl, digits)} / "
                           f"TP {fmt_preis(tp, digits)} SOFORT von Hand nachtragen! "
                           f"Spur: [" + _spur(trail) + "]",
                    "trail": _spur(trail), "symbol": symbol,
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
                       "die Order kann jetzt nicht ausgefuehrt werden. Spur: [" + _spur(trail) + "]",
                "trail": _spur(trail)}
    # F9-SL/TP-Verdacht (02.09.2026): wurde SL/TP direkt in den Order-Dialog
    # getippt und kam GAR KEINE Position, kann der Broker die Markt-Order wegen
    # der Stops komplett abgelehnt haben (statt sie nur zu ignorieren). Das ist
    # der Fall, den der Direktweg riskiert — beim Test klar benennen, damit wir
    # ihn sofort erkennen und den Direktweg ggf. abschalten.
    f9_hinweis = (" · Hinweis: SL/TP wurden direkt in den Order-Dialog getippt — "
                  "moeglich, dass dieser Broker sie in der Markt-Order ablehnt und "
                  "deshalb keine Position kam." if f9_getippt else "")
    return {"ok": False, "retry_ok": False,
            "msg": "KEINE Bestaetigung binnen 12 s — Position nicht am Konto, Dialog "
                   "geschlossen. Spur: [" + _spur(trail) + "] · Dialog: " + struktur
                   + f9_hinweis,
            "trail": _spur(trail)}


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
    Rueckgabe: 'zu' | 'knopf' | 'ohne_wirkung' | 'kein_treffer' | 'pause' |
    'haftung' (Ein-Klick-Haftungsausschluss stand im Weg und liess sich nicht
    annehmen)."""
    try:
        hr = w.rectangle()
        maus_grenze = hr.top + (hr.bottom - hr.top) // 2
    except Exception:
        return "kein_treffer"
    gx = hr.left + int((hr.right - hr.left) * 0.4)
    # Haftungsausschluss ZUERST, dann erst die Abbrechen/ESC-Runde: ein Rest
    # aus einem frueheren Lauf soll angenommen werden, nicht abgebrochen —
    # sonst steht er beim naechsten Close-Klick sofort wieder da.
    _einklick_haftung_annehmen(w, trail, melden=True)
    _fremde_dialoge_schliessen(w)
    # Toolbox auf 'Handel' — sonst ist die Positionsliste unsichtbar (gleicher
    # Fund wie beim SL/TP-Weg: frischer Terminal-Start steht auf 'Posteingang').
    # Mit anker_pfad: der gemerkte Tab-Punkt erspart die Baum-Suche (01.09.2026).
    tab_weg = _handel_tab_aktivieren(w, trail, maus_grenze, anker_pfad=anker_pfad)
    if is_paused():
        trail.append("⏸ Echo pausiert — kein Close-Klick")
        return "pause"
    # Punkte wie _reihen_scan: gemerkter Anker zuerst — bewusst DIESELBE
    # anker-Datei, die Positions-Zeile ist dieselbe, die der SL/TP-Weg beim
    # Platzieren schon Ticket-geprueft getroffen hat.
    punkte = []
    try:
        a = _anker_lesen(anker_pfad)
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

    def _punkt_klicken(px_, py_):
        """Finns Handgriff auf EINEM Punkt: Zeile markieren -> Rechtsklick ->
        nur den LESBAREN 'Position schliessen' klicken. Als eigene Funktion,
        weil der Nachklick nach dem Haftungsausschluss exakt dasselbe tun muss
        (01.09.2026) — zwei Kopien derselben Klickfolge waeren genau die Art
        Stelle, an der spaeter nur eine von beiden gepflegt wird."""
        _maus_fahren(px_, py_, schritte=3)
        _klick_absolut(px_, py_)          # Finns Schritt 1: Zeile markieren
        _warte(0.15, 0.2)
        if not _klick_absolut(px_, py_, taste="rechts"):
            return "kein_menue"
        _warte(0.25, 0.3)
        return _kontextmenue_close_klicken(timeout=0.8)

    grau = 0
    for pname, px_, py_ in punkte:
        if is_paused():
            trail.append("⏸ Echo pausiert — Close-Scan abgebrochen")
            return "pause"
        st_menue = _punkt_klicken(px_, py_)
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
        # MERGEN statt roh schreiben (01.09.2026): sonst wischte der Close den
        # gemerkten Handel-Tab-Punkt wieder weg.
        _anker_schreiben(anker_pfad,
                         x_frac=(px_ - hr.left) / max(1, hr.right - hr.left),
                         y_off=hr.bottom - py_)
        dlg = knopf = None
        # Der Haftungsausschluss wird pro Lauf genau EINMAL behandelt: MT5
        # zeigt ihn nur beim allerersten Ein-Klick-Handel eines Terminals, und
        # ein Nachklick, der sich wiederholen darf, waere ein blinder
        # Mehrfach-Close.
        haftung_offen = True
        ende = time.time() + 3.0
        while time.time() < ende:
            if position_weg():
                trail.append("Position weg (Ein-Klick-Modus)")
                return "zu"
            dlg, knopf = _finde_close_dialog(w, ticket)
            if knopf is not None:
                break
            if haftung_offen:
                st_haft = _einklick_haftung_annehmen(w, trail)
                if st_haft != "keiner":
                    haftung_offen = False
                if st_haft == "gescheitert":
                    return "haftung"
                if st_haft == "angenommen":
                    # Zustimmung hat den Close verschluckt — derselbe Punkt
                    # noch einmal. Zulaessig, weil dieser Punkt sich eben
                    # durch den lesbaren Menuepunkt als Positions-Zeile
                    # ausgewiesen hat und der Aufrufer lesend geprueft hat,
                    # dass GENAU EINE Position offen ist.
                    if is_paused():
                        trail.append("⏸ Echo pausiert — kein zweiter Close-Klick")
                        return "pause"
                    if _punkt_klicken(px_, py_) != "geklickt":
                        trail.append("Nach der Zustimmung kam der Menuepunkt "
                                     "nicht mehr — nichts nachgeklickt")
                        return "ohne_wirkung"
                    trail.append(f"'Position schliessen' nach der Zustimmung "
                                 f"erneut geklickt ({pname})")
                    ende = time.time() + 3.0
                    continue
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
    if tab_weg == "anker":
        # Gleiche Lehre wie im SL/TP-Weg (02.09.2026, Belastung-Fehlklick):
        # kein einziger lesbarer 'Position schliessen'-Punkt nach einem
        # Anker-Tab-Klick heisst, der gemerkte Punkt ist verdaechtig — raus
        # damit, der naechste Lauf sucht den Reiter frisch. Bewusst KEIN
        # zweiter Scan hier: der Close bleibt ein Versuch pro Lauf.
        _anker_schreiben(anker_pfad, handel_x_off=None, handel_y_off=None,
                         handel_x_frac=None)
        trail.append("Tab-Anker verworfen (kein Schliessen-Menuepunkt nach Anker-Klick)")
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
        msg = lese["fehler"]
        if _ist_verbindungsfehler(msg):
            msg += " — " + _UAC_HINWEIS
        return {"ok": False, "retry_ok": True, "msg": msg}
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

    trail = _StempelSpur()
    _warte(0.0, 1.2)   # Start-Versatz wie run() (28.08.2026, Flotten-Streuung)

    # 2) Ins Terminal gehen -> Guard
    w = _finde_terminal(expected)
    if w is None:
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein MT5-Fenster mit Konto {expected} gefunden. "
                       + _UAC_HINWEIS}
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
                       "[" + _spur(trail) + "]", "trail": _spur(trail)}
    if ausgang == "haftung":
        # Der Dialog wird trotzdem weggeraeumt (Abbrechen/ESC): ein stehendes
        # modales Fenster blockiert das Terminal, an dem das Lesen haengt.
        _fremde_dialoge_schliessen(w)
        return {"ok": False, "retry_ok": True,
                "msg": "MT5 wollte vor dem Schliessen erst den Haftungsausschluss zum "
                       "Ein-Klick-Handel bestaetigt haben, und der Zustimmen-Knopf liess "
                       "sich nicht druecken — nichts geschlossen. Einmal im Terminal von "
                       "Hand eine Position per Rechtsklick schliessen und dabei zustimmen, "
                       "danach fragt MT5 nie wieder. [" + _spur(trail) + "]",
                "trail": _spur(trail)}
    if ausgang == "kein_treffer":
        _fremde_dialoge_schliessen(w)
        return {"ok": False, "retry_ok": True,
                "msg": f"Positions-Zeile #{ticket} nicht gefunden (Zeilen-Scan ohne Treffer) — "
                       f"nichts geklickt. [" + _spur(trail) + "]",
                "trail": _spur(trail)}

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
                "trail": _spur(trail), "ticket": ticket, "profit": profit}
    if ausgang == "ohne_wirkung":
        return {"ok": False, "retry_ok": True,
                "msg": f"'Position schliessen' geklickt, aber Position #{ticket} liegt noch "
                       f"und kein Close-Dialog kam — im Terminal nachsehen. Wiederholen ist "
                       f"ungefaehrlich (der Bot prueft vorher lesend). [" + _spur(trail) + "]",
                "trail": _spur(trail)}
    return {"ok": False, "retry_ok": True,
            "msg": f"Close-Dialog war offen, aber Position #{ticket} ist nach 12 s weiter "
                   f"offen — im Terminal pruefen (Dialog wurde geschlossen). Wiederholen ist "
                   f"ungefaehrlich. [" + _spur(trail) + "]",
            "trail": _spur(trail)}


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
    # Konsole robust (24.09.2026 abends, Finns PC: tvlesen 'absturz @ raus' = UnicodeEncodeError, cp1252 kann
    # '\u25bc' aus dem TradingView-Tab-Titel nicht kodieren — die Spur traegt den Titel, die JSON-Antwort
    # scheiterte beim print). Unkodierbares wird ersetzt statt zu werfen; das Panel liest mit errors=replace.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(errors="replace")
        except Exception:
            pass
    if len(sys.argv) >= 2 and sys.argv[1] == "mousetest":
        modus_mousetest()
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "tvfokus":
        # Orbit Schritt 1 (28.08.2026): nur den TradingView-Tab nach vorn —
        # wie mousetest ohne Config, und ohne den Prophos-Heimweg unten.
        modus_tvfokus()
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "tvstart":
        # Futures-Puls Neuaufbau Schritt 1 (21.09.2026): pruefen, ob
        # TradingView offen ist — wenn nicht, starten. Optionales JSON mit
        # tv_url / tv_browser_path / tv_chrome_profil (kommt vom Panel aus der
        # Config). Wie tvfokus ohne Prophos-Heimweg: der PC soll danach auf
        # TradingView stehen.
        try:
            cfg = json.loads(sys.argv[2]) if len(sys.argv) >= 3 else {}
        except ValueError:
            cfg = {}
        modus_tvstart(cfg if isinstance(cfg, dict) else {})
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "tvkonto":
        # Futures-Puls Neuaufbau Schritt 2a (21.09.2026): TradingView
        # sicherstellen, dann pruefen, ob das richtige Tradovate-Konto aktiv
        # ist. Liest nur — kein Klick in die Seite, keine Order.
        try:
            cmd = json.loads(sys.argv[2])
        except ValueError as e:
            print(json.dumps({"ok": False, "msg": f"Befehl kein gueltiges JSON: {e}"}))
            return 2
        try:
            modus_tvkette(cmd)      # Schritt 1+2, mit 'symbol' im Befehl auch Schritt 3
        except Exception as e:
            print(json.dumps({"ok": False, "schritt": "absturz",
                              "msg": f"TV-Kette abgebrochen: {type(e).__name__}: {e}"}))
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "tvlesen":
        # Orbit-V2-Rundgang (24.09.2026): Konto anfahren, dann NUR lesen —
        # Position offen? Today's P&L? Klickt hoechstens den Konto-Umschalter
        # (ueber modus_tvkonto), nie ins Order-Panel. Kein Prophos-Heimweg:
        # der PC bleibt auf TradingView, sonst drosselt Chrome den Reader.
        try:
            cmd = json.loads(sys.argv[2])
        except ValueError as e:
            print(json.dumps({"ok": False, "code": "befehl", "msg": f"Befehl kein gueltiges JSON: {e}"}))
            return 2
        try:
            modus_tvlesen(cmd)
        except Exception as e:
            # Ort dazu (24.09.2026 abends, Finn: 'der Reader ist aktiv, liest die Position trotzdem
            # nicht' — in der DB stand nur 'absturz'): letzte eigene Stelle aus dem Traceback.
            print(json.dumps({"ok": False, "code": "absturz", "schritt": "absturz",
                              "msg": f"TV-Lesen abgebrochen: {type(e).__name__}: {e} @ {_absturz_ort(e)}"}))
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "tvclose":
        # Orbit V2 schliessen (24.09.2026, Auto-Close 23:45–00:00 Dubai): Konto
        # anfahren wie tvlesen, dann in der Positions-Tabelle GENAU EINE Zeile
        # der Wurzel ueber TradingViews eigenen Schliessen-Knopf flatten und den
        # Beweis (Reader ohne die Position, Streak 2) + Today's P&L liefern.
        # Kein Prophos-Heimweg, derselbe Grund wie bei tvlesen.
        try:
            cmd = json.loads(sys.argv[2])
        except ValueError as e:
            print(json.dumps({"ok": False, "code": "befehl", "retry_ok": True,
                              "msg": f"Befehl kein gueltiges JSON: {e}"}))
            return 2
        try:
            modus_tvclose(cmd)
        except Exception as e:
            # retry_ok=False: der Bot weiss nach einem Absturz nicht, ob der
            # Schliessen-Klick schon raus war (Doktrin wie tvorder).
            print(json.dumps({"ok": False, "code": "absturz", "schritt": "absturz", "retry_ok": False,
                              "msg": f"TV-Schliessen abgebrochen: {type(e).__name__}: {e} — erst in "
                                     "TradingView nachsehen, ob die Position noch offen ist."}))
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
    _api_stat_reset()
    try:
        if str(cmd.get("aktion") or "").lower() == "close":
            res = run_close(sys.argv[1], cmd)
        else:
            res = run(sys.argv[1], cmd)
    finally:
        # Die offen gehaltene Terminal-Verbindung sauber loesen (31.08.2026) —
        # hier statt in run(), damit JEDER Ausgang sie loest, auch der Absturz.
        # Ohne das haenge der Prozess bis zu seinem Ende am Terminal.
        _api_trennen()
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
