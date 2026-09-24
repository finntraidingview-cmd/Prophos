#!/usr/bin/env python3
"""Prophos TV-Reader — lokaler Empfaenger.

Nimmt die Positionsdaten vom Tampermonkey-Reader (tv-reader.user.js) entgegen,
haelt den aktuellen Stand im Speicher, schreibt ihn atomar nach positions.json
und gibt ihn als Live-Zeile im Terminal aus.

Das ist der Andockpunkt fuer den echten Hedge-Copier: der liest entweder
GET http://127.0.0.1:8790/positions oder direkt die Datei positions.json.

Bedienfeld (30.08.2026, Orbit-Puls Schritt 2): POST /bedienfeld nimmt die
Steuerelement-Geometrie des Userscripts entgegen (Konto-Umschalter, Symbol-
Suche, Order-Ticket, Kaufen/Verkaufen — je mit Rechteck in CSS-Pixeln), GET
/bedienfeld gibt sie an den Puls. Der Puls klickt daraus mit ECHTER Maus; das
Userscript klickt bewusst nie selbst (isTrusted-Doktrin, s. tv-reader.user.js).
Der Stand wird NICHT in eine Datei geschrieben: er ist Sekunden-frisch relevant
und waere auf Platte nur eine Quelle fuer alte Koordinaten.
POST /dump-an schaltet den Kandidaten-Dump des Userscripts fuer 60 s scharf —
die Ferndiagnose, wenn Puls ein Steuerelement nicht findet (gleiche Rolle wie
modus_inspect beim MT5-Puls).

Ein/Aus-Schalter (28.08.2026, Orbit-View in Prophos — hiess damals "Echo +"): POST /schalter
{"an": false} pausiert den Reader — der Stand friert ein (stale != flat:
ein pausierter Reader meldet NIE "keine Positionen", sonst wuerde ein
spaeterer Copier-Konsument die Hedges schliessen). Persistiert als
reader_aus.flag, ueberlebt also einen Neustart des Servers. Jeder Konsument
von positions.json MUSS das Feld "an" pruefen: an=false -> nicht syncen.

Blind-Riegel (01.09.2026, Finns Tabwechsel-Fund): meldet das Userscript
{"blind": true}, wird der Stand NICHT uebernommen — er friert ein, wie bei
Pause. Grund: ein verdeckter Chrome-Tab liefert leere Tabellenzellen, und
daraus wurde bis 0.3.7 ein frisches "0 Positionen" — der einzige Fall, in dem
die Frische-Doktrin der ganzen Kette versagt, weil die Daten ja frisch SIND.
Der Copier schloss den Hedge und riss ihn im naechsten Tick wieder auf.
Dazu ein Struktur-Riegel: eine Nachricht ohne Feld 'positionen' (Liste) wird
abgelehnt statt als "flat" gelesen.

Konto-Zusammenfassung (24.09.2026, Orbit-V2-Rundgang): das Userscript ab
0.5.0 schickt im Bedienfeld zusaetzlich 'summary' (alle Label→Wert-Paare des
Account Managers: Balance, Today's P&L, …), 'today_pnl_text' und 'today_label'.
Hier wird NICHTS daran gedeutet — der Puls (order_bot.py tvlesen) parst die
Zahlen. Durchgereicht wird es an zwei Stellen: GET /bedienfeld (der ganze
Stand, wie gehabt) und GET /positions (nur die drei Felder + summary_alter_s,
damit ein Konsument des Positions-Stands nicht zweimal fragen muss).
Dazu 'alter_s' im Positions-Stand (Server-Zeit seit dem letzten UEBERNOMMENEN
Stand): der Puls braucht den Beweis, dass der Stand JUENGER ist als sein
Kontowechsel — bisher stand nur die Browser-Zeit 'ts' drin.

Nur Python-Standardbibliothek — kein pip, keine Cloud, keine Schluessel.
Laeuft auf Mac/Windows/Linux gleich.
"""
import json
import re
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8790
# Versionsstand DIESES Servers (25.09.2026, Moritz' PC: Tab-Build .495 meldet sich alle 5 s,
# tv_kurse bleibt leer — aus der Cloud war nicht zu sehen, ob ein reader-server von vor dem
# Kurs-Feed laeuft (Selbst-Update nur beim Start via start-reader.bat) oder ein Userscript
# < 0.7.0 (Tampermonkey prueft nur taeglich). Ab jetzt sagt jede Antwort, welcher Server und
# welches Script wirklich laufen; die Bruecke schreibt beides nach echoplus_live, der Markt-
# Kopf zeigt es. Bei JEDER Aenderung an dieser Datei mitbumpen.
READER_VERSION = "0.8.8"
HIER = os.path.dirname(os.path.abspath(__file__))
DATEI = os.path.join(HIER, "positions.json")
AUS_FLAG = os.path.join(HIER, "reader_aus.flag")   # Datei vorhanden = pausiert


# ── QuickEdit aus (25.09.2026, Live-Befund pc-usq1i6: Feed stand 6 min, Finns Foto zeigte die Titelleiste
# „Auswählen Prophos TV-Reader"). Windows-Konsolen starten bei einem Klick ins Fenster eine MARKIERUNG
# (QuickEdit) — solange sie steht, blockiert Windows jede Ausgabe, der Prozess haengt beim naechsten print()
# und nimmt nichts mehr an. Beim Start abschalten; auf Mac/Linux nichts.
def _quickedit_modus(mode):
    """REIN RECHNEND (testbar): Konsolen-Modus ohne ENABLE_QUICK_EDIT_MODE (0x0040), mit ENABLE_EXTENDED_FLAGS (0x0080)."""
    return (int(mode) & ~0x0040) | 0x0080


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

# Letzter bekannter Stand (wird von POST gesetzt, von GET/Datei gelesen)
_stand = {"ts": 0, "positionen": []}
_stand_s = 0.0      # Server-Zeit des letzten UEBERNOMMENEN Stands (24.09.2026, fuer alter_s)
_an = not os.path.exists(AUS_FLAG)
# Version des Userscripts aus dem letzten POST (positions/bedienfeld/kerzen tragen 'version'),
# None = noch nie eines gemeldet (oder Script < 0.4, das kein Feld schickt).
_script_version = None
_script_s = 0.0

# Bedienfeld: letzter Stand der Steuerelement-Geometrie + Empfangszeit.
# empfangen_s ist die SERVER-Zeit — das Userscript schickt seine eigene
# Browser-Zeit mit (ts), und die beiden Uhren muessen sich nicht einig sein.
# Puls braucht "juenger als mein letzter Klick", also zaehlt hier die Uhr,
# die auch der Puls liest.
_bedienfeld = None
_bedienfeld_s = 0.0
# Live-Kurs aus dem Tab-Titel (Userscript 0.6.0, 24.09.2026, Winning-Day-Gegenhedge):
# {symbol, text, ts} + Server-Empfangszeit. Liegt BEWUSST neben _stand: der
# Pause-Schalter friert die Positionen ein (stale != flat), der Kurs darf aber
# weiter ticken — er ist eine Beobachtung des Markts, kein Hedge-Befehl.
_kurs = None
_kurs_s = 0.0
# Minutenkerzen aus den Titel-Ticks (24.09.2026 abends, Markt-Chart + Demo-Orders):
# die 250-ms-Ticks bleiben hier, in die Cloud gehen nur Kerzen. _k1m = laufende
# Minute, _k1m_vor = letzte abgeschlossene — beide stehen in jeder GET-Antwort
# (kurs_1m), die Bruecke im Prophos-Tab upsertet sie idempotent.
_k1m = None
_k1m_vor = None
# 0.7.0 (24.09.2026): BEIDE Symbole — je Wurzel ('NQ'/'MNQ') der letzte Kurs + Empfangszeit
# und die Minutenkerzen (laufend/abgeschlossen). _kurs/_k1m oben bleiben fuer alte
# Userscripts (0.6.0, nur Tab-Titel) und alte Bruecken (Feld 'kurs') bestehen.
_kurs_quelle_titel = {"q": None}   # 0.8.6: welcher Tab liefert den Titel-Kurs
_feed_zeile = {"s": 0.0}           # 0.8.6: Drossel fuer die Live-Zeile aus Feed-POSTs
_kurse = {}        # wurzel -> {bid, ask, text, preis, ts, quelle, stale, sichtbar, symbol_text, empf_s}
_k1m_je = {}       # wurzel -> laufende Kerze
_k1m_vor_je = {}   # wurzel -> letzte abgeschlossene Kerze
_reload_grund = None
_reload_s = 0.0
STALE_S = 45.0     # kein neuer Kurs > 45 s → stale (Userscript sagt es, der Server prueft es zusaetzlich am Alter)
# 0.8.0: Bars aus TradingViews Socket (POST /kerzen) — Ring je Wurzel, nur Aufloesung '1'
KERZEN_MAX = 600
_kerzen = {}          # wurzel -> {minute(int): {wurzel, symbol, aufloesung, minute, o, h, l, c, vol}}
_kerzen_s = 0.0       # Server-Zeit des letzten Bar-Empfangs
_kerzen_modus = None  # 'streaming' | 'delayed_streaming_600' (aus dem Userscript)
_kerzen_delay_s = None
_aufl_warnung = None


def _kerzen_uebernehmen(ring, bars, erstladung, maximum=KERZEN_MAX):
    """REIN RECHNEND (testbar): Bars {wurzel, symbol, aufloesung, minute, o, h, l, c, vol?} in den
    Ring je Wurzel (upsert auf minute — dieselbe Kerze kommt mehrfach mit wachsendem Volumen).
    Nur Aufloesung '1' zaehlt; andere liefern eine Warnung. erstladung=True ersetzt den Ring der
    betroffenen Wurzeln (Serie neu geladen). -> (ring, uebernommen, warnung)"""
    ring = dict(ring or {})
    n, warnung, ersetzt = 0, None, set()
    for b in (bars or []):
        if not isinstance(b, dict):
            continue
        aufl = str(b.get("aufloesung") or "")
        if aufl != "1":
            warnung = f"Chart-Aufloesung {aufl or '?'} statt 1 — keine Minutenkerzen"
            continue
        w = _kurs_wurzel(b.get("wurzel")) or str(b.get("wurzel") or "").upper()[:8]
        try:
            minute = int(float(b.get("minute")))
            o, h, l, c = (float(b.get("o")), float(b.get("h")), float(b.get("l")), float(b.get("c")))
        except (TypeError, ValueError):
            continue
        if not w or minute <= 0 or c <= 0:
            continue
        # 0.8.4: taucht fuer eine Wurzel erstmals eine Chart-Serie auf, verdraengt sie die Tick-Kerzen
        # (Ring der Wurzel neu) — Serien-Bars sind exakt, Tick-Kerzen nur eine Naeherung.
        if w not in ersetzt and (erstladung or _ring_ist_tick(ring.get(w))):
            ring[w] = {}
            ersetzt.add(w)
        r = ring.setdefault(w, {})
        vol = b.get("vol")
        r[minute] = {"wurzel": w, "symbol": str(b.get("symbol") or w)[:32], "aufloesung": "1", "minute": minute,
                     "o": o, "h": h, "l": l, "c": c, "vol": (float(vol) if isinstance(vol, (int, float)) else None),
                     "quelle": "ws"}
        n += 1
        if len(r) > maximum:
            for k in sorted(r)[:len(r) - maximum]:
                del r[k]
    return ring, n, warnung


def _ring_ist_tick(r):
    """True, wenn der Ring einer Wurzel (nur) aus Quote-Tick-Kerzen besteht."""
    return bool(r) and all(b.get("quelle") == "ws-tick" for b in r.values())


def _tick_kerze_in_ring(ring, wurzel, symbol, preis, jetzt_s, maximum=KERZEN_MAX):
    """REIN RECHNEND (testbar, 0.8.4): Minutenkerze aus einem Quote-Tick (qsd: lp, sonst Mitte Bid/Ask)
    fuer Wurzeln OHNE Chart-Serie — Finn will NQ und MNQ als Chart, ohne das TradingView-Layout
    umzubauen (Moritz' PC: NQ nur in der Watchlist → keine Serie, nur Ticks). O und C sind exakt,
    H/L nur so gut wie die Tick-Dichte; Volumen gibt es nicht. quelle 'ws-tick' sagt das dem
    Frontend. Liegt fuer die Wurzel schon eine Serie im Ring, passiert NICHTS (die Serie gewinnt).
    -> (ring, geschrieben)"""
    ring = dict(ring or {})
    w = _kurs_wurzel(wurzel) or str(wurzel or "").upper()[:8]
    try:
        preis = float(preis)
    except (TypeError, ValueError):
        return ring, False
    if not w or preis <= 0:
        return ring, False
    r = ring.get(w)
    if r and not _ring_ist_tick(r):
        return ring, False                       # Serie vorhanden → keine Tick-Kerzen fuer diese Wurzel
    r = ring.setdefault(w, {})
    minute = int(jetzt_s // 60) * 60
    k = r.get(minute)
    if k:
        k["h"] = max(k["h"], preis); k["l"] = min(k["l"], preis); k["c"] = preis; k["n"] = k.get("n", 0) + 1
    else:
        r[minute] = {"wurzel": w, "symbol": str(symbol or w)[:32], "aufloesung": "1", "minute": minute,
                     "o": preis, "h": preis, "l": preis, "c": preis, "vol": None, "n": 1, "quelle": "ws-tick"}
        if len(r) > maximum:
            for kk in sorted(r)[:len(r) - maximum]:
                del r[kk]
    return ring, True


def _kerzen_liste(ring, seit=None):
    """REIN RECHNEND: alle Bars aller Wurzeln chronologisch, optional nur minute >= seit."""
    out = []
    for w in sorted((ring or {}).keys()):
        for m in sorted(ring[w]):
            if seit is None or m >= seit:
                out.append(ring[w][m])
    return out


def _kurs_1m_aus_ring(ring):
    """REIN RECHNEND: letzte abgeschlossene + laufende Minute je Wurzel in der Form von kurs_1m
    (minute in Unix-Sekunden, o/h/l/c, n = ticks unbekannt → 0) — damit die bestehende Bruecke
    unveraendert nach tv_kurs_1m schreibt."""
    out = []
    for w in sorted((ring or {}).keys()):
        for m in sorted(ring[w])[-2:]:
            b = ring[w][m]
            out.append({"minute": m, "wurzel": w, "symbol": b["symbol"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                        "n": int(b.get("n") or 0), "quelle": b.get("quelle") or "ws"})
    return out


def _kurse_uebernehmen(kurse, sichtbar, jetzt_s, alt, k1m_je, k1m_vor_je):
    """REIN RECHNEND (testbar): Payload-Feld 'kurse' {wurzel: {bid, ask, text, ts, quelle,
    stale?}} in den Server-Stand uebernehmen. preis = Mitte aus bid/ask (sonst text);
    Kerzen je Wurzel aus dem preis, nur aus SICHTBAREM Tab. Unlesbares bleibt stehen.
    -> (kurse_neu, k1m_je, k1m_vor_je)"""
    neu = dict(alt or {})
    if not isinstance(kurse, dict):
        return neu, k1m_je, k1m_vor_je
    for w, k in kurse.items():
        if not isinstance(k, dict):
            continue
        wurzel = _kurs_wurzel(w) or str(w).upper()[:8]
        bid = _kurs_zahl(k.get("bid")) if k.get("bid") else None
        ask = _kurs_zahl(k.get("ask")) if k.get("ask") else None
        txt = _kurs_zahl(k.get("text")) if k.get("text") else None
        if bid and ask:
            preis = round((bid + ask) / 2.0, 2)
        else:
            preis = bid or ask or txt
        if not preis or preis <= 0:
            continue
        lp = _kurs_zahl(str(k.get("lp"))) if isinstance(k.get("lp"), (int, float)) else None
        if lp and lp > 0:
            preis = float(lp)                     # WS: der letzte Trade ist der Kurs, Bid/Ask nur Beiwerk
        neu[wurzel] = {"bid": bid, "ask": ask, "lp": lp, "text": str(k.get("text") or "")[:32], "preis": preis,
                       "ts": k.get("ts"), "lp_time": k.get("lp_time"), "quelle": str(k.get("quelle") or "")[:12],
                       "modus": (str(k.get("modus"))[:32] if k.get("modus") else None), "delay_s": k.get("delay_s"),
                       "stale": bool(k.get("stale")), "unveraendert_s": k.get("unveraendert_s"),
                       "sichtbar": bool(sichtbar), "symbol_text": str(k.get("symbol_text") or "")[:60],
                       "empf_s": jetzt_s}
        if sichtbar and str(k.get("quelle") or "") != "ws":   # WS-Kurse: die Bars kommen fertig ueber /kerzen
            k1m_je[wurzel], k1m_vor_je[wurzel] = _kerze_fortschreiben(
                k1m_je.get(wurzel), k1m_vor_je.get(wurzel), wurzel, str(k.get("symbol_text") or wurzel)[:32], preis, jetzt_s)
    return neu, k1m_je, k1m_vor_je


def _kurse_ausgabe(kurse, jetzt_s):
    """REIN RECHNEND (testbar): Ausgabeform je Wurzel mit alter_s (Server-Sekunden seit Empfang)
    und stale (Userscript-Urteil ODER Empfang aelter als STALE_S)."""
    out = {}
    for w, k in (kurse or {}).items():
        alter = round(jetzt_s - float(k.get("empf_s") or 0), 3) if k.get("empf_s") else None
        o = {kk: vv for kk, vv in k.items() if kk != "empf_s"}
        o["alter_s"] = alter
        o["stale"] = bool(k.get("stale")) or alter is None or alter > STALE_S
        out[w] = o
    return out


def _kurs_zahl(text):
    """'30,448.25' / '29.491,75' / '30,448' -> float — dieselbe Regel wie
    tv_snapshot.parse_de_zahl (beide Trenner: der letzte ist das Dezimalzeichen;
    reine Dreiergruppen = Tausender; sonst einzelner Trenner = Dezimal)."""
    t = str(text or "").replace("\u2212", "-").replace(" ", "").replace("'", "").strip()
    if not t:
        return None
    neg = t.startswith("-")
    t = t.lstrip("+-")
    if not t or not all(ch.isdigit() or ch in ".," for ch in t) or not t[0].isdigit():
        return None
    ip, ik = t.rfind("."), t.rfind(",")
    if ip >= 0 and ik >= 0:
        dez = "." if ip > ik else ","
        s = t.replace("," if dez == "." else ".", "").replace(",", ".")
    elif ip >= 0 or ik >= 0:
        tr = "." if ip >= 0 else ","
        teile = t.split(tr)
        gruppen = len(teile) > 1 and all(len(x) == 3 for x in teile[1:]) and len(teile[0]) <= 3
        s = "".join(teile) if gruppen else t.replace(",", ".")
    else:
        s = t
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _kurs_wurzel(sym):
    """'CME_MINI:MNQ1!' / 'MNQZ2026' / 'NQ' -> 'MNQ' / 'MNQ' / 'NQ' (Port von tv_symbol_root)."""
    s = str(sym or "").strip().upper().split()[0] if str(sym or "").strip() else ""
    if ":" in s:
        s = s.split(":")[-1]
    s = "".join(ch for ch in s if ch.isalnum() or ch == "!")
    if s.endswith("!"):
        return s.rstrip("!").rstrip("0123456789")
    m = re.match(r"^([A-Z]{1,4})[FGHJKMNQUVXZ]\d{1,4}$", s)
    if m:
        return m.group(1)
    return s.rstrip("0123456789")


def _kerze_fortschreiben(k1m, k1m_vor, wurzel, symbol, preis, jetzt_s):
    """REIN RECHNEND (testbar): (laufende Kerze, letzte abgeschlossene) nach einem
    Tick. Minute = floor(jetzt_s / 60) in Server-UTC-Sekunden."""
    minute = int(jetzt_s // 60) * 60
    if k1m and k1m.get("minute") == minute and k1m.get("wurzel") == wurzel:
        k1m["h"] = max(k1m["h"], preis)
        k1m["l"] = min(k1m["l"], preis)
        k1m["c"] = preis
        k1m["n"] += 1
        return k1m, k1m_vor
    neu = {"minute": minute, "wurzel": wurzel, "symbol": symbol, "o": preis, "h": preis, "l": preis, "c": preis, "n": 1}
    # die bisherige laufende Kerze ist jetzt abgeschlossen (nur, wenn es eine war)
    return neu, (k1m if k1m else k1m_vor)
_dump_bis = 0.0   # bis zu dieser Server-Zeit fordert der Server einen Dump an

# Text-Suche (21.09.2026, Futures-Puls Schritt 2): der Puls nennt Texte (die
# External IDs der Konten), das Userscript (0.4.2+) sucht sie im GANZEN DOM und
# meldet die Rechtecke im Bedienfeld unter 'treffer'. Grund: TradingView hat
# die data-name-Anker des Konto-Umschalters umbenannt, und die Aufklappliste
# haengt am Ende des DOM — hinter der Kappung der Element-Listen. Die eigene
# Kontonummer ist der eine Anker, den TradingView nicht umbenennen kann.
# Zeitlich begrenzt wie der Dump: nie im Dauerbetrieb durchs ganze DOM.
_such_texte = []
_such_bis = 0.0

# Blind-Zustand (01.09.2026): das Userscript ab 0.4.0 sagt selbst, wenn sein
# Lesevorgang nichts beweist (Tabelle nicht auffindbar, Zellen leer). Solche
# Staende werden NICHT uebernommen — _stand friert ein, und die Frische-
# Doktrin des Verbinders haelt daraufhin den Hedge. Der Grund wird trotzdem
# gemerkt, damit Terminal und Ferndiagnose ihn zeigen koennen.
_blind_grund = ""
_blind_seit = 0.0
_letzte_zahl = None   # letzte gemeldete Positionszahl (Beweisspur)

# ── Mehrere TradingView-Tabs an EINEM reader-server (0.8.6, 25.09.2026) ─────────────────────────────
# Finn richtet auf Moritz' PC einen DAUERHAFTEN Feed-Tab (eigenes TV-Konto mit CME-Abo, OHNE Broker) ein;
# daneben oeffnet Puls eigene Tabs im Broker-Konto. Beide posten hierher. BEFUND bis 0.8.5: Positions-Stand
# und Bedienfeld = der letzte POST gewinnt KOMPLETT, Kurse = der letzte je Wurzel, Kerzen mischen sich (eine
# Erstladung des einen Tabs ersetzt den Ring des anderen). Sieht der Feed-Tab eine Konto-Leiste (z. B. Paper
# Trading), meldet er ehrlich 'flach' und ueberschreibt den Puls-Tab → der Master-weg-Waechter koennte den
# Fusion-Hedge schliessen, obwohl der Master laeuft. Ab jetzt: Stand JE TAB (tab_id), Rolle 'broker' (Konto
# gelesen) oder 'feed'; Positionen/Konto/Bedienfeld-Summary NUR aus Broker-Tabs, Kurse/Kerzen je Wurzel aus
# der besten Quelle (Echtzeit vor verzoegert, Feed vor Broker, bei Stille uebernimmt der andere).
BROKER_FRISCH_S = 10.0   # Broker-Tab ohne POST laenger als das → kein Positions-Urteil (positionen_ok false)
KURS_QUELLE_S = 5.0      # Kurs-Quelle einer Wurzel gilt als still nach so vielen Sekunden → andere darf
KERZEN_QUELLE_S = 90.0   # dasselbe fuer den Kerzen-Ring (du-Frames kommen nur alle paar Sekunden)
_tabs = {}               # tab_id -> {rolle, stand, stand_s, blind_grund, blind_seit, bf, bf_s, last_s, version, sichtbar, fokus, quelle}
_kerzen_quelle = {}      # wurzel -> {tab, rolle, modus, s}


def _rang(rolle, modus):
    """Rang einer Kurs-/Kerzen-Quelle: Echtzeit (modus ohne 'delayed') zaehlt doppelt, Feed-Tab vor Broker-Tab."""
    return (0 if "delayed" in str(modus or "") else 2) + (1 if rolle == "feed" else 0)


def _quelle_gewinnt(alt, tab, rolle, modus, jetzt, still_s):
    """REIN RECHNEND (testbar): darf ein Wert von (tab, rolle, modus) den bisherigen einer Wurzel ersetzen?
    alt = {tab, rolle, modus, s} oder None. Ja, wenn es keinen gibt, derselbe Tab liefert, der bisherige
    seit still_s schweigt, oder die neue Quelle mindestens gleichen Rang hat."""
    if not alt:
        return True
    if alt.get("tab") == tab:
        return True
    if jetzt - float(alt.get("s") or 0) > still_s:
        return True
    return _rang(rolle, modus) >= _rang(alt.get("rolle"), alt.get("modus"))


def _broker_wahl(tabs, jetzt, frisch_s=BROKER_FRISCH_S):
    """REIN RECHNEND (testbar): welcher Broker-Tab liefert den Positions-Stand? -> (tab_id | None, frisch).
    Unter den frischen Broker-Tabs (letzter POST <= frisch_s) gewinnt der mit dem juengsten konto_ts, dann
    der juengste Stand; ohne frischen der zuletzt aktive (frisch False = kein Urteil)."""
    broker = [(tid, t) for tid, t in (tabs or {}).items() if t.get("rolle") == "broker" and t.get("stand_s")]
    if not broker:
        return None, False
    frische = [(tid, t) for tid, t in broker if jetzt - float(t.get("last_s") or 0) <= frisch_s]
    if frische:
        tid, _t = max(frische, key=lambda x: (float((x[1].get("stand") or {}).get("konto_ts") or 0), float(x[1].get("stand_s") or 0)))
        return tid, True
    tid, _t = max(broker, key=lambda x: float(x[1].get("stand_s") or 0))
    return tid, False


def _bf_wahl(tabs, jetzt, broker_zuerst=False, frisch_s=BROKER_FRISCH_S):
    """REIN RECHNEND (testbar): welches Bedienfeld? Fuer Klicks (Puls) zaehlt der Tab MIT FOKUS, dann Broker,
    dann der juengste; fuer die Konto-Summary (broker_zuerst) der Broker vor dem Fokus. Frische zuerst,
    sonst der juengste ueberhaupt. -> tab_id | None"""
    mit = [(tid, t) for tid, t in (tabs or {}).items() if t.get("bf") is not None]
    if not mit:
        return None
    frisch = [(tid, t) for tid, t in mit if jetzt - float(t.get("bf_s") or 0) <= frisch_s] or mit

    def schluessel(x):
        t = x[1]
        fok, brk = (1 if t.get("fokus") else 0), (1 if t.get("rolle") == "broker" else 0)
        return ((brk, fok) if broker_zuerst else (fok, brk)) + (float(t.get("bf_s") or 0),)
    return max(frisch, key=schluessel)[0]


def _tab(daten, jetzt):
    """Tab-Eintrag zum Payload holen/anlegen. Ohne tab_id (Userscript < 0.8.5) = 'standard' als Broker —
    genau das alte Ein-Tab-Verhalten."""
    daten = daten if isinstance(daten, dict) else {}
    tid = str(daten.get("tab_id") or "standard")[:40]
    rolle = str(daten.get("rolle") or "broker")
    rolle = rolle if rolle in ("broker", "feed") else "broker"
    t = _tabs.setdefault(tid, {"stand": None, "stand_s": 0.0, "blind_grund": "", "blind_seit": 0.0, "bf": None, "bf_s": 0.0})
    t.update({"rolle": rolle, "last_s": jetzt, "version": daten.get("version") or t.get("version")})
    if "sichtbar" in daten:
        t["sichtbar"] = daten.get("sichtbar") is not False
    if "fokus" in daten:
        t["fokus"] = bool(daten.get("fokus"))
    # verwaiste Tabs (Puls oeffnet/schliesst eigene) nach 10 min vergessen
    for alt in [k for k, v in _tabs.items() if jetzt - float(v.get("last_s") or 0) > 600 and k != tid]:
        _tabs.pop(alt, None)
    return tid, t


def _effektiv_setzen(jetzt):
    """Globale Kompatibilitaets-Sicht (_stand/_stand_s/_blind_grund) = gewaehlter Broker-Tab."""
    global _stand, _stand_s, _blind_grund, _blind_seit
    tid, _frisch = _broker_wahl(_tabs, jetzt)
    if tid:
        t = _tabs[tid]
        _stand, _stand_s = t.get("stand") or {"ts": 0, "positionen": []}, float(t.get("stand_s") or 0)
        _blind_grund, _blind_seit = t.get("blind_grund") or "", float(t.get("blind_seit") or 0)


def _tabs_liste(jetzt):
    """Diagnose fuer GET /positions: je Tab Rolle, Alter, Quelle, Sicht/Fokus, Version, Konto."""
    out = []
    for tid, t in sorted(_tabs.items(), key=lambda x: -float(x[1].get("last_s") or 0)):
        out.append({"tab_id": tid, "rolle": t.get("rolle"), "alter_s": round(jetzt - float(t.get("last_s") or 0), 1),
                    "quelle": t.get("quelle"), "sichtbar": t.get("sichtbar"), "fokus": t.get("fokus"),
                    "version": t.get("version"),
                    "konto": ((t.get("stand") or {}).get("konto") if t.get("rolle") == "broker" else None),
                    "blind": bool(t.get("blind_grund"))})
    return out


# ── Konsole entlasten (0.8.8, 25.09.2026, Koordination: zwei Tabs auf Script 0.8.4 → bei JEDEM POST
# 'Reader BLIND … / Reader sieht wieder …' plus Statuszeile, mehrere Zeilen pro Sekunde; Windows-Konsolen sind
# beim Schreiben langsam, die Bruecken-GETs liefen in Timeouts, das Badge zeigte 'Timeout'). Zustandswechsel
# werden je Tab erst nach STABIL_S gemeldet und hoechstens alle MELDE_ABSTAND_S, die Statuszeile nur bei
# Aenderung oder alle ZEILE_ABSTAND_S.
STABIL_S = 3.0
MELDE_ABSTAND_S = 10.0
ZEILE_ABSTAND_S = 5.0
_zeile_merk = {}      # Statuszeile: {inhalt, s}
_version_je_tab = {}  # tab_id -> zuletzt gemeldete Userscript-Version
_zahl_merk = {}       # tab_id -> {zahl, s, wechsel}


def _entprellt(merk, zustand, jetzt, stabil_s=STABIL_S, abstand_s=MELDE_ABSTAND_S):
    """REIN RECHNEND (testbar): soll ein Zustandswechsel (z. B. blind True/False) JETZT gemeldet werden?
    merk = je Tab {gemeldet, kand, kand_s, meld_s}; bei JEDEM POST aufrufen. Ja erst, wenn der neue Zustand
    seit stabil_s unveraendert anliegt UND die letzte Meldung >= abstand_s her ist."""
    if merk.get("kand") != zustand:
        merk["kand"], merk["kand_s"] = zustand, jetzt
    if zustand == merk.get("gemeldet", False):
        return False
    if jetzt - float(merk.get("kand_s") or jetzt) >= stabil_s and jetzt - float(merk.get("meld_s", -1e9)) >= abstand_s:
        merk["gemeldet"], merk["meld_s"] = zustand, jetzt
        return True
    return False


def _zeile_faellig(merk, inhalt, jetzt, abstand_s=ZEILE_ABSTAND_S):
    """REIN RECHNEND (testbar): Statuszeile nur bei geaendertem Inhalt oder alle abstand_s."""
    if inhalt != merk.get("inhalt") or jetzt - float(merk.get("s", -1e9)) >= abstand_s:
        merk["inhalt"], merk["s"] = inhalt, jetzt
        return True
    return False


def _tabs_zeile(jetzt):
    """Kurzform fuer die Live-Zeile: 'Tabs: feed 1 · broker 1' (Tabs mit POST in den letzten 60 s)."""
    n = {"feed": 0, "broker": 0}
    for t in _tabs.values():
        if jetzt - float(t.get("last_s") or 0) <= 60 and t.get("rolle") in n:
            n[t["rolle"]] += 1
    return f"Tabs: feed {n['feed']} · broker {n['broker']}"


def _schreibe_datei(stand):
    """Atomar schreiben, damit ein mitlesender Copier nie eine halbe Datei sieht."""
    tmp = DATEI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stand, f, ensure_ascii=False)
    os.replace(tmp, DATEI)


def _versionen(jetzt_s=None):
    """Die drei Versions-Felder fuer jede Antwort (GET /positions, GET /bedienfeld)."""
    jetzt_s = time.time() if jetzt_s is None else jetzt_s
    return {"reader_version": READER_VERSION,
            "script_version": _script_version,
            "script_alter_s": round(jetzt_s - _script_s, 3) if _script_s else None}


def _script_merken(daten, jetzt_s):
    """Userscript-Version aus einem POST-Payload uebernehmen. Gibt (version, zeit) zurueck,
    unveraendert, wenn der Payload kein brauchbares 'version'-Feld traegt."""
    v = daten.get("version") if isinstance(daten, dict) else None
    if isinstance(v, str) and v.strip():
        return v.strip()[:16], jetzt_s
    return _script_version, _script_s


def _kerzen_diag(kerzen, bedienfeld, aufl_warnung, script_version):
    """REIN RECHNEND (testbar): Kerzen-Diagnose fuer die Live-Zeile (0.8.2, Koordinations-Session
    25.09.2026: 'ein Foto des Reader-Fensters soll reichen, Finn soll keine URLs oeffnen muessen').
    Moritz' PC: Kurse per Socket da, tv_kurs_1m leer — ob keine du-Frames kommen, die Serie nicht
    zuordenbar ist oder der Server die Bars verwirft, war nur ueber /positions im Browser zu sehen."""
    ring = "/".join(f"{w} {len(r)}" + ("(tick)" if _ring_ist_tick(r) else "") for w, r in sorted(kerzen.items())) or "leer"
    feed = (bedienfeld or {}).get("feed") if isinstance(bedienfeld, dict) else None
    if isinstance(feed, dict):
        serien = feed.get("serien") if isinstance(feed.get("serien"), dict) else {}
        geraten = sum(1 for v in serien.values() if isinstance(v, dict) and v.get("geraten"))
        teil = (f"du/min {feed.get('du_min', '?')} · Serien {len(serien)}"
                + (f" ({geraten} geraten)" if geraten else "")
                + f" · unbek {feed.get('unbekannte_serien', '?')}")
        # 0.8.3: Ursache je Serie (Script 0.8.2) — fremd = Symbol bekannt, aber weder NQ noch MNQ (kein Fehler),
        # unaufgeloest = Send gehoert, Klartext fehlt noch, unbekannt = kein Send und kein Rueckfall
        fremd = feed.get("fremd") if isinstance(feed.get("fremd"), dict) else {}
        if fremd:
            teil += " · fremd " + ",".join(str((v or {}).get("symbol") or sid).split(":")[-1][:12] for sid, v in list(fremd.items())[:3])
        unauf = feed.get("unaufgeloest") if isinstance(feed.get("unaufgeloest"), dict) else {}
        if unauf:
            teil += f" (unaufgel. {len(unauf)})"
    else:
        teil = "kein feed (Script < 0.8.0?)"
    aufl = f"Aufl-WARNUNG {aufl_warnung}" if aufl_warnung else "Aufl ok"
    return f"Kerzen {ring} · {teil} · {aufl} · Script {script_version or '?'} · Reader {READER_VERSION}"


def _mit_an(stand):
    """Stand + Schalter-Zustand — 'an' gehoert in JEDE Ausgabe (Datei und GET),
    damit kein Konsument den Schalter uebersehen kann."""
    out = dict(stand)
    out["an"] = _an
    # blind gehoert in JEDE Ausgabe, aus demselben Grund wie 'an': ein
    # Konsument darf nicht uebersehen koennen, dass dieser Stand steht.
    out["blind"] = bool(_blind_grund)
    out["blind_grund"] = _blind_grund
    # Alter des Stands in SERVER-Sekunden (24.09.2026): 'ts' ist Browser-Zeit,
    # der Puls vergleicht aber gegen seine eigene Uhr — also gegen diese hier.
    # None = noch nie ein Stand uebernommen.
    out["alter_s"] = round(time.time() - _stand_s, 3) if _stand_s else None
    # Konto-Zusammenfassung aus dem letzten Bedienfeld (Userscript 0.5.0+),
    # rein durchgereicht; bei aelterem Userscript fehlen die Felder im
    # Bedienfeld und stehen hier als None.
    jetzt_ = time.time()
    _bft = _bf_wahl(_tabs, jetzt_, broker_zuerst=True)
    bf = ((_tabs.get(_bft) or {}).get("bf") if _bft else None) or _bedienfeld or {}
    out["summary"] = bf.get("summary")
    out["today_pnl_text"] = bf.get("today_pnl_text")
    out["today_label"] = bf.get("today_label")
    out["summary_alter_s"] = round(time.time() - _bedienfeld_s, 3) if _bedienfeld_s else None
    # Kurs aus dem Titel (0.6.0): rein durchgereicht, mit eigenem Alter — der
    # Prophos-Tab schreibt ihn nach tv_kurse (Cloud), der Hedge-Waechter liest dort.
    out["kurs"] = _kurs
    out["kurs_alter_s"] = round(time.time() - _kurs_s, 3) if _kurs_s else None
    # 0.7.0: beide Wurzeln — kurse.NQ / kurse.MNQ mit alter_s + stale, Kerzen aller Wurzeln in EINER Liste
    # (Form wie bisher, wurzel unterscheidet; alte Bruecken lesen weiter kurs_1m). Ohne 0.7.0-Userscript
    # fallen die Titel-Kerzen (_k1m) hinein, damit nichts verloren geht.
    out["kurse"] = _kurse_ausgabe(_kurse, time.time())
    # 0.8.0: Kerzen zuerst aus dem Socket-Ring (fertige TradingView-Bars), sonst Tick-Kerzen (Legende/Titel)
    kerzen = _kurs_1m_aus_ring(_kerzen) if _kerzen else []
    if not kerzen:
        for w in sorted(_k1m_je.keys()):
            kerzen += [k for k in (_k1m_vor_je.get(w), _k1m_je.get(w)) if k]
    if not kerzen:
        kerzen = [k for k in (_k1m_vor, _k1m) if k]
    out["kurs_1m"] = kerzen
    out["kerzen_alter_s"] = round(time.time() - _kerzen_s, 3) if _kerzen_s else None
    out["kerzen_anzahl"] = {w: len(r) for w, r in _kerzen.items()}
    out["kerzen_quelle"] = {w: ("ws-tick" if _ring_ist_tick(r) else "ws") for w, r in _kerzen.items()}   # 0.8.4
    out["aufloesung_warnung"] = _aufl_warnung
    out["modus"] = _kerzen_modus
    out["delay_s"] = _kerzen_delay_s
    out["feed"] = (bf.get("feed") if isinstance(bf.get("feed"), dict) else None)   # Nachweis aus dem Userscript (0.8.0)
    out["reload_grund"] = _reload_grund
    out["reload_alter_s"] = round(time.time() - _reload_s, 3) if _reload_s else None
    out.update(_versionen())   # reader_version / script_version / script_alter_s (0.8.1)
    # 0.8.5: Beweis-Felder fuer den Master-zu-Waechter (Script 0.8.3 liefert sie; aelteres Script:
    # positionen_ts = ts des Stands, konto null). Blind = keine Aussage, egal was das Script sagt.
    _btid, _bfrisch = _broker_wahl(_tabs, jetzt_)
    # 0.8.6: nur ein FRISCHER Broker-Tab liefert ein Urteil; ohne Tab-Buchfuehrung (noch kein POST) wie bisher
    out["positionen_ok"] = bool(stand.get("positionen_ok", True)) and not _blind_grund and (_bfrisch or not _tabs)
    out["positionen_ts"] = stand.get("positionen_ts") or stand.get("ts") or None
    out["positionen_alter_s"] = round(time.time() - _stand_s, 3) if _stand_s else None
    out["konto"] = stand.get("konto") or None
    out["konto_ts"] = stand.get("konto_ts") or None
    out["positionen_tab"] = _btid
    out["tabs"] = _tabs_liste(jetzt_)
    return out


def _schalte(an_neu):
    """Schalter setzen + persistieren + positions.json sofort aktualisieren
    (damit ein Datei-Konsument den neuen Zustand ohne naechsten Tick sieht)."""
    global _an
    _an = bool(an_neu)
    try:
        if _an:
            if os.path.exists(AUS_FLAG):
                os.remove(AUS_FLAG)
        else:
            with open(AUS_FLAG, "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        print(f"\n[WARN] Schalter-Flag nicht schreibbar: {e}")
    try:
        _schreibe_datei(_mit_an(_stand))
    except Exception as e:
        print(f"\n[WARN] positions.json nicht schreibbar: {e}")


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        # Chrome Private-Network-Access: erlaubt einer HTTPS-Seite (Prophos auf
        # pages.dev) den Zugriff auf 127.0.0.1 — noetig fuer die Orbit-View.
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, code, obj):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        global _stand, _stand_s, _bedienfeld, _bedienfeld_s, _dump_bis, _blind_grund, _blind_seit, _letzte_zahl
        global _such_texte, _such_bis, _kurs, _kurs_s, _k1m, _k1m_vor, _kurse, _k1m_je, _k1m_vor_je, _reload_grund, _reload_s
        global _kerzen, _kerzen_s, _kerzen_modus, _kerzen_delay_s, _aufl_warnung
        global _script_version, _script_s, _kerzen_quelle
        laenge = int(self.headers.get("Content-Length", 0) or 0)
        roh = self.rfile.read(laenge) if laenge else b""
        try:
            daten = json.loads(roh)
        except Exception:
            self.send_response(400)
            self._cors()
            self.end_headers()
            return
        # 0.8.1: Userscript-Version aus JEDEM Payload merken (positions, bedienfeld, kerzen
        # tragen sie) — Wechsel sichtbar machen, denn "Update eingespielt, Tab nie neu
        # geladen" war schon dreimal die Erklaerung fuer fehlende Felder.
        if isinstance(daten, dict):
            v_neu, s_neu = _script_merken(daten, time.time())
            # 0.8.8: je Tab melden — bei zwei Tabs mit verschiedenen Versionen flatterte die globale Zeile
            _vtid = str(daten.get("tab_id") or "standard")[:40]
            if v_neu and _version_je_tab.get(_vtid) != v_neu:
                print(f"\n[{time.strftime('%H:%M:%S')}] Userscript {_version_je_tab.get(_vtid) or 'unbekannt'} -> {v_neu}"
                      f" ({_vtid}, reader-server {READER_VERSION})", flush=True)
                _version_je_tab[_vtid] = v_neu
            _script_version, _script_s = v_neu, s_neu

        # Schalter (Orbit-View): POST /schalter {"an": true/false}
        if self.path.rstrip("/") == "/schalter":
            if "an" not in daten:
                self._json(400, {"ok": False, "msg": "Feld 'an' fehlt"})
                return
            _schalte(daten["an"])
            zeit = time.strftime("%H:%M:%S")
            print(f"\n[{zeit}] Schalter: Reader {'AN' if _an else 'PAUSIERT'}")
            self._json(200, {"ok": True, "an": _an})
            return

        # Bedienfeld-Geometrie vom Userscript (30.08.2026, Orbit-Puls
        # Schritt 2). BEWUSST VOR dem Pause-Gate: der Schalter friert die
        # POSITIONEN ein (stale != flat), er blendet nicht die Augen ab —
        # Geometrie ist harmlos und ohne sie kaeme der Puls nie zu einer
        # ehrlichen Fehlermeldung. Ob ueberhaupt geordert werden darf,
        # entscheidet der Puls selbst am Feld 'an' von GET /positions.
        if self.path.rstrip("/") == "/bedienfeld":
            _tid, _t = _tab(daten, time.time())
            _t["bf"], _t["bf_s"] = daten, time.time()
            _bedienfeld = daten
            _bedienfeld_s = time.time()
            # dump-Anforderung zurueckgeben: das Userscript haengt beim
            # NAECHSTEN Tick den Kandidaten-Dump an (nie im Dauerbetrieb —
            # der Dump laeuft durchs ganze DOM).
            self._json(200, {"ok": True, "dump": time.time() < _dump_bis,
                             "suche": _such_texte if time.time() < _such_bis else []})
            return

        # 0.8.0: Bars aus TradingViews Socket — {ts, quelle:'ws', erstladung, modus, delay_s, bars:[...]}.
        # VOR dem Pause-Gate wie der Kurs (Beobachtung, kein Hedge-Befehl).
        if self.path.rstrip("/") == "/kerzen":
            bars = daten.get("bars")
            if not isinstance(bars, list):
                self._json(400, {"ok": False, "msg": "Feld 'bars' fehlt oder ist keine Liste"})
                return
            # 0.8.6: je Wurzel nur die beste Quelle (Echtzeit vor verzoegert, Feed vor Broker, bei Stille die andere)
            _jetzt = time.time()
            _tid, _t = _tab(daten, _jetzt)
            _modus = daten.get("modus")
            _wz = lambda b: (_kurs_wurzel(b.get("wurzel")) or str(b.get("wurzel") or "").upper()[:8])
            erlaubt = {}
            for b in bars:
                if isinstance(b, dict) and _wz(b) and _wz(b) not in erlaubt:
                    erlaubt[_wz(b)] = _quelle_gewinnt(_kerzen_quelle.get(_wz(b)), _tid, _t["rolle"], _modus, _jetzt, KERZEN_QUELLE_S)
            bars = [b for b in bars if isinstance(b, dict) and erlaubt.get(_wz(b))]
            for w, ok_ in erlaubt.items():
                if ok_:
                    _kerzen_quelle[w] = {"tab": _tid, "rolle": _t["rolle"], "modus": _modus, "s": _jetzt}
            _kerzen, n, warnung = _kerzen_uebernehmen(_kerzen, bars, bool(daten.get("erstladung")))
            if n:
                _kerzen_s = time.time()
            _aufl_warnung = warnung
            if daten.get("modus"):
                _kerzen_modus = str(daten.get("modus"))[:32]
            if isinstance(daten.get("delay_s"), (int, float)):
                _kerzen_delay_s = daten.get("delay_s")
            if daten.get("erstladung") and n:
                print(f"\n[{time.strftime('%H:%M:%S')}] Kerzen-Erstladung: {n} Bars "
                      f"({', '.join(f'{w}:{len(r)}' for w, r in _kerzen.items())})"
                      + (f" · {_kerzen_modus}" if _kerzen_modus else ""), flush=True)
            self._json(200, {"ok": True, "uebernommen": n, "warnung": warnung,
                             "anzahl": {w: len(r) for w, r in _kerzen.items()}})
            return

        # Text-Suche scharfschalten: POST /suche {"texte": [...]} — 90 s lang
        # bekommt das Userscript die Liste in jeder /bedienfeld-Antwort mit.
        # Leere Liste = sofort aus.
        if self.path.rstrip("/") == "/suche":
            roh_texte = daten.get("texte") if isinstance(daten, dict) else None
            texte = []
            for t in (roh_texte if isinstance(roh_texte, list) else []):
                t = str(t).strip()[:60]
                if len(t) >= 3 and t not in texte:
                    texte.append(t)
            _such_texte = texte[:60]
            _such_bis = time.time() + 90.0 if _such_texte else 0.0
            self._json(200, {"ok": True, "texte": len(_such_texte), "bis_s": 90 if _such_texte else 0})
            return

        # Kandidaten-Dump scharfschalten (Ferndiagnose, 60 s): der Puls ruft
        # das selbst auf, wenn er ein Steuerelement nicht eindeutig findet —
        # der naechste Fehlversuch bringt dann die Beweise gleich mit.
        if self.path.rstrip("/") == "/dump-an":
            _dump_bis = time.time() + 60.0
            print("\n[info] Kandidaten-Dump fuer 60 s scharf")
            self._json(200, {"ok": True, "bis_s": 60})
            return

        # Ab hier gilt: NUR /positions ist ein Positions-Stand (30.08.2026,
        # Fund an Finns PC). Vorher nahm dieser Handler JEDEN unbekannten Pfad
        # als Positionsdaten an — ein Userscript 0.3, das an einen alten Server
        # ohne /bedienfeld sendet, ueberschrieb damit alle 500 ms den echten
        # Stand mit einem Objekt ohne 'positionen'. Ergebnis: positions.json
        # meldet "flat", der Verbinder friert nicht ein (die Daten sind ja
        # frisch!), und der Copier schliesst die Hedges — der schlimmste
        # denkbare Ausgang, ausgeloest von einer Nachricht, die der Server gar
        # nicht verstand. Unbekannte Pfade werden jetzt ehrlich abgelehnt.
        if self.path.rstrip("/") not in ("/positions", ""):
            self._json(404, {"ok": False, "msg":
                f"Unbekannter Pfad {self.path!r} — dieser reader-server kennt "
                "/positions, /schalter, /bedienfeld, /dump-an, /suche. Aeltere Version?"})
            return

        # Kurs aus dem Titel (0.6.0) VOR dem Pause-Gate uebernehmen — siehe
        # Kommentar bei _kurs. Nur, wenn das Feld wirklich ein Kurs-Objekt ist;
        # null (kein Chart-Tab) laesst den letzten Stand stehen, das Alter sagt es.
        _jetzt = time.time()
        _tid, _t = _tab(daten, _jetzt)
        k = daten.get("kurs")
        _titel_ok = _quelle_gewinnt(_kurs_quelle_titel.get("q"), _tid, _t["rolle"], None, _jetzt, KURS_QUELLE_S)
        if isinstance(k, dict) and k.get("symbol") and k.get("text") and _titel_ok:
            _kurs_quelle_titel["q"] = {"tab": _tid, "rolle": _t["rolle"], "modus": None, "s": _jetzt}
            _kurs = {"symbol": str(k.get("symbol"))[:32], "text": str(k.get("text"))[:32],
                     "ts": k.get("ts") or daten.get("ts"),
                     "sichtbar": daten.get("sichtbar") is not False}
            _kurs_s = time.time()
            # Minutenkerze fortschreiben — nur mit lesbarer Zahl und nur aus einem
            # SICHTBAREN Tab (verdeckt tickt der Titel gedrosselt, das waere eine
            # Kerze aus drei Ticks). Fehler hier duerfen den Positions-Strom nie stoeren.
            try:
                pz = _kurs_zahl(_kurs["text"])
                if pz is not None and pz > 0 and _kurs["sichtbar"]:
                    _k1m, _k1m_vor = _kerze_fortschreiben(_k1m, _k1m_vor, _kurs_wurzel(_kurs["symbol"]),
                                                          _kurs["symbol"], pz, time.time())
            except Exception:
                pass

        # 0.7.0: beide Symbole aus den Legenden (kurse) + Selbstheilungs-Grund — ebenfalls VOR dem Pause-Gate
        try:
            if isinstance(daten.get("kurse"), dict):
                jetzt = time.time()
                # 0.8.6: je Wurzel nur die beste Quelle uebernehmen (Rang aus Rolle + modus des Tabs)
                _gefiltert = {}
                for w_, k_ in daten.get("kurse").items():
                    wz = _kurs_wurzel(w_) or str(w_).upper()[:8]
                    alt_ = _kurse.get(wz)
                    alt_q = ({"tab": alt_.get("tab_id"), "rolle": alt_.get("rolle"), "modus": alt_.get("modus"), "s": alt_.get("empf_s")}
                             if alt_ else None)
                    if isinstance(k_, dict) and _quelle_gewinnt(alt_q, _tid, _t["rolle"], k_.get("modus"), jetzt, KURS_QUELLE_S):
                        _gefiltert[w_] = k_
                _kurse, _k1m_je, _k1m_vor_je = _kurse_uebernehmen(_gefiltert, daten.get("sichtbar") is not False,
                                                                  jetzt, _kurse, _k1m_je, _k1m_vor_je)
                for w_, k_ in _kurse.items():
                    if k_.get("empf_s") == jetzt:
                        k_["tab_id"], k_["rolle"] = _tid, _t["rolle"]
                        _t["quelle"] = k_.get("quelle")
                # 0.8.4: Wurzeln, die per Socket ticken, aber keine Chart-Serie haben, bekommen
                # Minutenkerzen aus den Quote-Ticks (auch im verdeckten Tab — der Socket ist nicht gedrosselt).
                for w, k in _kurse.items():
                    if k.get("quelle") == "ws" and k.get("empf_s") == jetzt:
                        _kerzen, ok = _tick_kerze_in_ring(_kerzen, w, k.get("symbol_text") or w, k.get("preis"), jetzt)
                        if ok:
                            _kerzen_s = jetzt
            if daten.get("reload_grund"):
                _reload_grund = str(daten.get("reload_grund"))[:120]
                _reload_s = time.time()
                print(f"\n[{time.strftime('%H:%M:%S')}] Userscript hat sich selbst neu geladen: {_reload_grund}", flush=True)
        except Exception:
            pass

        # Positionsdaten vom Userscript. Pausiert: Antwort traegt an=false
        # (Badge zeigt es), der Stand friert ein — stale != flat.
        if not _an:
            self._json(200, {"ok": True, "an": False})
            return

        # Struktur-Riegel (01.09.2026): eine Nachricht OHNE Positionsliste ist
        # kein Positions-Stand. Der Pfad-Riegel vom 30.08. deckt den bekannten
        # Fall ab (Userscript 0.3 an altem Server); dieser hier deckt jeden
        # kuenftigen ab — eine leere Liste darf nur ankommen, wenn wirklich
        # eine Liste geschickt wurde.
        # 0.8.6: Feed-Tab (kein Broker) liefert NIE einen Positions-Stand — auch nicht 'flach'
        if _t["rolle"] == "feed":
            # Live-Zeile auch ohne Broker-Tab auffrischen (hoechstens alle ZEILE_ABSTAND_S), sonst stuende im Fenster ein alter Stand
            if _jetzt - _feed_zeile["s"] >= ZEILE_ABSTAND_S:
                _feed_zeile["s"] = _jetzt
                _bfs = _t.get("bf") or _bedienfeld
                _btid, _bfr = _broker_wahl(_tabs, _jetzt)
                kopf = f"\r[{time.strftime('%H:%M:%S')}] " + ("Broker-Tab still/fehlt — kein Positions-Urteil" if not _bfr else "Feed-Tab")
                zeile = kopf + " | " + _tabs_zeile(_jetzt) + " · " + _kerzen_diag(_kerzen, _bfs, _aufl_warnung, _script_version)
                if not _bfr:
                    print(zeile.ljust(160)[:160], end="", flush=True)
            self._json(200, {"ok": True, "an": True, "rolle": "feed", "reader_version": READER_VERSION})
            return
        if not isinstance(daten.get("positionen"), list):
            self._json(400, {"ok": False, "msg":
                "Feld 'positionen' fehlt oder ist keine Liste — wird NICHT als "
                "Stand uebernommen (ein fehlendes Feld ist kein 'flat')."})
            return

        # Blind-Riegel (01.09.2026, Finns Tabwechsel-Fund): das Userscript ab
        # 0.4.0 meldet selbst, wenn sein Lesevorgang nichts beweist — Tab
        # verdeckt und die Zellen kamen leer zurueck, Panel zugeklappt, Tabelle
        # weg. Vorher wurde daraus ein FRISCHES "0 Positionen", der Verbinder
        # sah frische Daten, und der Copier machte den Hedge zu — im naechsten
        # Tick wieder auf. Genau dieses Flattern. Blinde Staende frieren den
        # Stand jetzt ein, statt ihn platt zu schreiben.
        #
        # Versions-Riegel (gleicher Abend): ein Userscript VOR 0.4 schickt im
        # /positions-Payload gar kein 'version'-Feld — und kann per Bauart
        # blind sein, ohne es zu wissen. Meldet so ein Script ploetzlich flat,
        # waehrend der letzte Stand Positionen hatte, ist das keine Aussage,
        # sondern der ungefixte Tabwechsel-Bug. Der haeufigste Weg dahin:
        # Update eingespielt, aber der TradingView-Tab nie mit F5 neu geladen
        # — im offenen Tab laeuft dann still der alte Code weiter, und genau
        # das war von aussen bisher nicht erkennbar.
        alt_und_ploetzlich_flach = ("version" not in daten
                                    and not daten.get("positionen")
                                    and ((_t.get("stand") or {}).get("positionen")))
        _jetzt_p = time.time()
        # Uebergangsschutz (0.8.8): mehrere Tabs mit Script < 0.8.5 landen alle im Tab 'standard'. Ein BLINDER
        # POST von dort ersetzt nicht den Stand eines nicht-blinden, der hoechstens BROKER_FRISCH_S alt ist — er
        # kommt dann mit hoher Wahrscheinlichkeit aus dem ANDEREN Tab. Ein einzelner, wirklich blinder Tab wird
        # nach BROKER_FRISCH_S blind wie bisher (bis dahin bleibt sein letzter guter Stand, alter_s waechst).
        if (_tid == "standard" and daten.get("blind") and _t.get("stand_s")
                and not _t.get("blind_grund") and _jetzt_p - float(_t["stand_s"]) <= BROKER_FRISCH_S):
            # bewusst OHNE _entprellt: ein ignorierter POST darf die BLIND-Meldung nicht verbrauchen
            self._json(200, {"ok": True, "an": True, "blind": True, "ignoriert": "standard_uebergang"})
            return
        _ist_blind = bool(daten.get("blind") or alt_und_ploetzlich_flach)
        _melden = _entprellt(_t.setdefault("meld", {}), _ist_blind, _jetzt_p)
        if daten.get("blind") or alt_und_ploetzlich_flach:
            if daten.get("blind"):
                _t["blind_grund"] = str(daten.get("blind_grund") or "Reader meldet blind")
            else:
                _t["blind_grund"] = ("Userscript ohne Versionsfeld (aelter als 0.4) meldet "
                                     "ploetzlich flat — im TradingView-Tab laeuft noch der "
                                     "alte Code. Tab mit F5 neu laden!")
            if not _t.get("blind_seit"):
                _t["blind_seit"] = time.time()
            if _melden:
                print(f"\n[{time.strftime('%H:%M:%S')}] Reader BLIND ({_tid}): {_t['blind_grund']} — "
                      f"Stand eingefroren, Hedges bleiben stehen.")
            _effektiv_setzen(time.time())
            try:
                _schreibe_datei(_mit_an(_stand))
            except Exception as e:
                print(f"\n[WARN] positions.json nicht schreibbar: {e}")
            self._json(200, {"ok": True, "an": True, "blind": True})
            return

        if _t.get("blind_grund"):
            if _melden:
                print(f"\n[{time.strftime('%H:%M:%S')}] Reader sieht wieder ({_tid}) "
                      f"(war {round(time.time() - float(_t.get('blind_seit') or 0), 1)}s blind).")
            _t["blind_grund"], _t["blind_seit"] = "", 0.0
        elif _melden:
            print(f"\n[{time.strftime('%H:%M:%S')}] Reader sieht wieder ({_tid}).")

        _t["stand"], _t["stand_s"] = daten, time.time()
        _effektiv_setzen(time.time())
        try:
            _schreibe_datei(_mit_an(_stand))
        except Exception as e:
            # Datei-Schreibfehler soll den Empfang nicht killen
            print(f"\n[WARN] positions.json nicht schreibbar: {e}")

        pos = daten.get("positionen", [])
        zeit = time.strftime("%H:%M:%S")
        # Beweisspur bei jeder Aenderung der Positionszahl (01.09.2026).
        # Die Live-Zeile unten ueberschreibt sich selbst — ein Wechsel auf
        # "flat" war damit nach 0,25 s nicht mehr nachweisbar, obwohl genau
        # daraus der Copier einen Close ableitet. Wechsel bleiben jetzt stehen,
        # inklusive der Userscript-Version: so ist von aussen belegbar, welcher
        # Stand die Aussage getroffen hat (der Grund, warum VERSION im
        # Userscript ueberhaupt doppelt steht).
        # 0.8.8: je Tab und hoechstens alle 2 s; unterdrueckte Zwischenwechsel werden mitgezaehlt
        # (Beweisspur bleibt: 'Positionen 1 -> 0 (+4 Wechsel dazwischen)').
        _zm = _zahl_merk.setdefault(_tid, {"zahl": None, "s": -1e9, "wechsel": 0})
        if _zm["zahl"] is None or len(pos) != _zm["zahl"]:
            if time.time() - _zm["s"] >= 2.0:
                extra = f", +{_zm['wechsel']} Wechsel dazwischen" if _zm["wechsel"] else ""
                print(f"\n[{zeit}] Positionen {_zm['zahl']} -> {len(pos)} ({_tid}"
                      f", Userscript {daten.get('version') or 'unbekannt'},"
                      f" Tab {'vorn' if daten.get('sichtbar') else 'verdeckt/unbekannt'}{extra})")
                _zm.update(zahl=len(pos), s=time.time(), wechsel=0)
            else:
                _zm["wechsel"] += 1
        _letzte_zahl = len(pos)
        if pos:
            zeilen = " · ".join(
                f"{p.get('symbol')} {p.get('seite')} {p.get('menge')}"
                f"@{p.get('einstieg')} SL {p.get('sl') or '-'} TP {p.get('tp') or '-'}"
                f" P&L {p.get('pnl')}"
                for p in pos
            )
        else:
            zeilen = "flat"
        # \r haelt es als eine aktualisierende Live-Zeile. 0.8.2: rechts die Kerzen-Diagnose,
        # die Positionen werden dafuer bei Bedarf gekuerzt (Konsole meist 120–160 Zeichen breit).
        _feed_bf = next((t_.get("bf") for t_ in _tabs.values() if t_.get("rolle") == "feed" and t_.get("bf")), None)
        diag = _tabs_zeile(time.time()) + " · " + _kerzen_diag(_kerzen, _feed_bf or _bedienfeld, _aufl_warnung, _script_version)
        kopf = f"\r[{zeit}] {len(pos)} Pos · "
        platz = max(20, 160 - len(kopf) - len(diag) - 3)
        if _zeile_faellig(_zeile_merk, zeilen[:platz] + " | " + diag, time.time()):
            print((kopf + zeilen[:platz] + " | " + diag).ljust(160)[:160], end="", flush=True)

        self._json(200, {"ok": True, "an": True, "reader_version": READER_VERSION})

    def do_GET(self):
        # Bedienfeld: das holt sich der Puls vor jedem Klick. 'alter_s' ist
        # das einzige Feld, auf das er sich verlaesst — er wartet auf einen
        # Stand, der JUENGER ist als sein letzter Klick, statt zu hoffen,
        # dass sich die Seite inzwischen aktualisiert hat.
        if self.path.rstrip("/") == "/bedienfeld":
            if _bedienfeld is None:
                self._json(200, {"ok": False, "msg":
                    "Noch kein Bedienfeld empfangen — laeuft das Userscript "
                    "(Version 0.3+) im TradingView-Tab?"})
                return
            # 0.8.6: das Bedienfeld des Tabs, in dem Puls gerade klickt (Fokus), sonst Broker, sonst juengstes
            _bft = _bf_wahl(_tabs, time.time())
            _src = _tabs.get(_bft) if _bft else None
            out = dict((_src or {}).get("bf") or _bedienfeld)
            out["ok"] = True
            out["alter_s"] = round(time.time() - float((_src or {}).get("bf_s") or _bedienfeld_s), 3)
            out["tab_id"], out["rolle"] = _bft, (_src or {}).get("rolle")
            out.update(_versionen())
            self._json(200, out)
            return

        # 0.8.0: GET /kerzen[?seit=<unix s>] — alle Bars des Rings (bis 600 je Wurzel), fuer die
        # Bruecke beim ersten Sehen eines PCs (Erstladung nach tv_kurs_1m), danach reicht kurs_1m.
        if self.path.split("?")[0].rstrip("/") == "/kerzen":
            seit = None
            try:
                q = self.path.split("?", 1)[1] if "?" in self.path else ""
                for teil in q.split("&"):
                    if teil.startswith("seit="):
                        seit = int(float(teil[5:]))
            except (ValueError, TypeError):
                seit = None
            self._json(200, {"ok": True, "quelle": "ws", "bars": _kerzen_liste(_kerzen, seit),
                             "anzahl": {w: len(r) for w, r in _kerzen.items()},
                             "alter_s": round(time.time() - _kerzen_s, 3) if _kerzen_s else None,
                             "aufloesung_warnung": _aufl_warnung, "modus": _kerzen_modus, "delay_s": _kerzen_delay_s})
            return

        # Aktuellen Stand abfragbar machen (fuer den Copier, die Orbit-View
        # oder zum Reinschauen im Browser) — inkl. Schalter-Zustand.
        self._json(200, _mit_an(_stand))

    def log_message(self, *a):
        pass  # kein Request-Log-Spam ueber der Live-Zeile


if __name__ == "__main__":
    if quickedit_aus():
        print("QuickEdit aus (Klick ins Fenster hält den Reader nicht mehr an)")
    print(f"Prophos TV-Reader-Empfaenger {READER_VERSION} laeuft auf http://127.0.0.1:{PORT}")
    print(f"Schreibt den Stand nach {DATEI}")
    print(f"Reader ist {'AN' if _an else 'PAUSIERT (reader_aus.flag liegt)'}")
    print("Warte auf Daten vom Tampermonkey-Reader … (Strg+C zum Beenden)\n")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nbeendet.")
