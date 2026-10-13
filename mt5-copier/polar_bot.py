"""POLAR-PULS (13.10.2026, Finn): Funded-Futures (Master, TradingView, PC A) gegen Funded-CFD (Slave, MT5, PC B) als Airbag statt
Fusion-Live. „Der indirekte Master ist der Future, der indirekte Slave ist der CFD."

EIGENE DATEI, BEWUSST (Finn 13.10.2026: „nichts am bestehenden Setup der Puls-Bots ändern — nur an neuen Sachen arbeiten"):
order_bot.py wird hier nur BENUTZT (Fenster finden, Dialog füllen, Klick, lesende API, Puls-Chrome-Sitzung), keine Zeile dort
geändert. Läuft der alte Puls weiter wie bisher, läuft Polar daneben als eigener Prozess.

Ablauf je Seite (Railway ist der Taktgeber, Schlüssel = code_token.txt neben dieser Datei, wie bei order_bot):
  1. Vorbereiten bis direkt vor den Kauf-Klick (Master: Ticket im Puls-Chrome, Maus über dem Senden-Knopf, Hover bewiesen;
     Slave: F9-Dialog mit Symbol/Volumen/groben SL/TP, Maus über dem Buy/Sell-Knopf).
  2. POST /polar/bereit, dann GET /polar/warte?auf=feuer (wartende Verbindung). Sind beide bereit, gibt Railway EINE Feuerzeit.
     Jede Seite rechnet sie auf die eigene Uhr um (Uhrabgleich über /polar/zeit, Median aus 5 Messungen).
  3. Zur Feuerzeit EIN SendInput-Druck — beide PCs in derselben Millisekunde, so genau die Uhren gehen. Ab der Feuerzeit kein
     Zurück mehr; Abbruch (abbruch.json / Railway-Status abbruch) gibt es nur davor.
  4. Master: Fill beweisen, TP/SL per Reiter Orders → Modify exakt auf Fill ± Abstand nachziehen, Position über den Reader
     (Tampermonkey, Port 8790, 50-ms-Takt) beobachten → flach = sofort POST /polar/melden zu (vor jeder Datenbank) → Balance lesen.
     Slave: Fill lesend beweisen, SL/TP per Klick vom ECHTEN Fill (Abstände = Master-Abstände × polar_pct, z. B. 102,5 %), Maus auf
     die Positionszeile parken, GET /polar/warte?auf=zu halten → Signal = Rechtsklick + „Position schließen" (Ein-Klick-Handel),
     nie per EA (FundedNext ≥ 50k = nur manuell, der Deal-Grund ist für die Firma sichtbar) → Balance/P&L lesen.
  5. POST /polar/melden ende (Balance, Zeiten) — Railway rechnet beide Seiten an Plan und Konten ab.

Aufruf (vom Panel als langlebiger Prozess):  python polar_bot.py master|slave "<befehl-json>"
Befehl Master: {lauf_id, plan_id, ext_id, tv_username, firma, geschwister, symbol, richtung, volumen, tp_usd, sl_usd, sl_pkt, tp_pkt}
Befehl Slave:  {lauf_id, plan_id, config_file, symbol, richtung, volumen, sl_pkt, tp_pkt}
Dateien im Ordner polar/<lauf_id>/: stand_<seite>.json (lesbar fürs Panel), abbruch.json (vom Panel, nur vor der Feuerzeit), <seite>.log"""
import json
import math
import os
import re
import sys
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import order_bot as ob  # noqa: E402  — nur benutzen, nie ändern

RAILWAY = "https://web-production-bec81.up.railway.app"
POLAR_ORDNER = os.path.join(HIER, "polar")
VERSION = "0.1.0"


# ── Zustand / Dateien ───────────────────────────────────────────────────────────────────────────────────────────────────────────
class Lauf:
    def __init__(self, seite, cmd):
        self.seite = seite
        self.cmd = cmd
        self.lauf_id = str(cmd.get("lauf_id") or "").strip()
        self.ordner = os.path.join(POLAR_ORDNER, re.sub(r"[^0-9a-f-]", "", self.lauf_id)[:36] or "ohne")
        os.makedirs(self.ordner, exist_ok=True)
        self.trail = ob._StempelSpur()
        self.stand = {"seite": seite, "lauf_id": self.lauf_id, "plan_id": cmd.get("plan_id"), "phase": "start", "pid": os.getpid(),
                      "version": VERSION, "at_ms": jetzt_ms()}
        self.uhr_versatz_ms = 0.0      # Railway-Uhr − eigene Uhr
        self.token = None
        try:
            with open(os.path.join(HIER, "code_token.txt"), "r", encoding="utf-8") as f:
                self.token = f.read().strip() or None
        except OSError:
            self.token = None
        self.log_datei = os.path.join(self.ordner, f"{seite}.log")

    def log(self, text):
        self.trail.append(text)
        try:
            with open(self.log_datei, "a", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d} {text}\n")
        except OSError:
            pass

    def phase(self, name, **felder):
        self.stand.update(felder)
        self.stand["phase"] = name
        self.stand["at_ms"] = jetzt_ms()
        self.stand["trail_ende"] = ob._spur(self.trail)[-600:]
        schreiben(os.path.join(self.ordner, f"stand_{self.seite}.json"), self.stand)

    def abbruch_gewuenscht(self):
        return os.path.exists(os.path.join(self.ordner, "abbruch.json"))


def jetzt_ms():
    return int(time.time() * 1000)


def schreiben(pfad, daten):
    """Atomar (tmp + replace) — das Panel liest nie eine halbe Datei."""
    try:
        tmp = pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, default=str)
        os.replace(tmp, pfad)
    except OSError:
        pass


# ── Railway ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def railway(lauf, methode, pfad, daten=None, timeout=10):
    """Ein Aufruf mit dem PC-Schlüssel. -> dict | None (nie werfen — der Takt wiederholt)."""
    import urllib.request
    if not lauf.token:
        return None
    try:
        roh = json.dumps(daten).encode("utf-8") if daten is not None else None
        req = urllib.request.Request(RAILWAY + pfad, data=roh, method=methode,
                                     headers={"X-Code-Token": lauf.token, "User-Agent": "prophos-polar", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace") or "{}")
    except Exception as e:
        lauf.log(f"Railway {pfad}: {type(e).__name__}")
        return None


def uhr_abgleichen(lauf, n=5):
    """Versatz Railway-Uhr − eigene Uhr: je Messung (Antwort-ms − Mitte der Laufzeit), Median aus n. Fehlschlag = 0 (Vorlauf 1,5 s fängt es)."""
    import urllib.request
    werte = []
    for _ in range(n):
        try:
            t0 = time.time()
            with urllib.request.urlopen(urllib.request.Request(RAILWAY + "/polar/zeit", headers={"User-Agent": "prophos-polar"}), timeout=5) as r:
                d = json.loads(r.read().decode("utf-8") or "{}")
            t1 = time.time()
            if d.get("ms"):
                werte.append(float(d["ms"]) - (t0 + t1) / 2.0 * 1000.0)
        except Exception:
            pass
        time.sleep(0.05)
    if werte:
        werte.sort()
        lauf.uhr_versatz_ms = werte[len(werte) // 2]
    lauf.log(f"Uhr: Railway − PC = {lauf.uhr_versatz_ms:+.0f} ms ({len(werte)} Messungen)")
    return bool(werte)


def feuerzeit_lokal_s(feuer_ms, versatz_ms):
    """REIN RECHNEND (testbar): Railway-Feuerzeit → eigene Uhr (Epoch s)."""
    return (float(feuer_ms) - float(versatz_ms)) / 1000.0


def bereit_und_warten(lauf, halten, extra=None):
    """POST bereit, dann /polar/warte?auf=feuer halten. halten() läuft alle ~0,5 s (Hover/Fenster prüfen); False = Abbruch.
    -> lokale Feuerzeit (Epoch s) | None (Abbruch — NICHT drücken). Nach gelesener Feuerzeit kein Zurück mehr."""
    r = railway(lauf, "POST", "/polar/bereit", {"lauf_id": lauf.lauf_id, "seite": lauf.seite, "daten": extra or {}})
    if not r or not r.get("ok"):
        lauf.log(f"bereit nicht angenommen: {(r or {}).get('msg') or 'keine Antwort'}")
        return None
    lauf.phase("bereit")
    lauf.log("Polar: bereit gemeldet — warte auf die gemeinsame Feuerzeit")
    feuer = r.get("feuer_ms")
    ergebnis = {"feuer": feuer, "fertig": feuer is not None, "status": r.get("status")}
    stop = threading.Event()

    def _warten():
        while not stop.is_set() and not ergebnis["fertig"]:
            a = railway(lauf, "GET", f"/polar/warte?lauf_id={lauf.lauf_id}&seite={lauf.seite}&auf=feuer&max_s=20", timeout=30)
            if not a:
                time.sleep(0.5)
                continue
            ergebnis["status"] = a.get("status")
            if a.get("feuer_ms") is not None:
                ergebnis["feuer"] = a["feuer_ms"]
                ergebnis["fertig"] = True
            elif str(a.get("status")) in ("abbruch", "fehler", "fertig"):
                ergebnis["fertig"] = True
    threading.Thread(target=_warten, daemon=True).start()
    naechst = time.time() + 0.5
    while not ergebnis["fertig"]:
        if lauf.abbruch_gewuenscht():
            railway(lauf, "POST", "/polar/melden", {"lauf_id": lauf.lauf_id, "seite": lauf.seite, "ereignis": "abbruch", "daten": {"grund": "panel_abbruch"}})
            stop.set()
            lauf.log("Polar: Abbruch vom Panel vor der Feuerzeit — nichts gedrückt")
            return None
        if time.time() >= naechst:
            naechst = time.time() + 0.5
            try:
                if halten() is False:
                    railway(lauf, "POST", "/polar/melden", {"lauf_id": lauf.lauf_id, "seite": lauf.seite, "ereignis": "abbruch", "daten": {"grund": "vorbereitung_verloren"}})
                    stop.set()
                    lauf.log("Polar: Vorbereitung verloren (Hover/Fenster) — Abbruch vor dem Druck")
                    return None
            except Exception as e:
                lauf.log(f"halten(): {type(e).__name__}")
        time.sleep(0.005)
    stop.set()
    if ergebnis["feuer"] is None:
        lauf.log(f"Polar: Lauf endete vor der Feuerzeit ({ergebnis['status']}) — nichts gedrückt")
        return None
    ziel = feuerzeit_lokal_s(ergebnis["feuer"], lauf.uhr_versatz_ms)
    rest = ziel - time.time()
    lauf.log(f"Polar: Feuerzeit in {rest:.3f} s")
    lauf.phase("feuer", feuer_ms=ergebnis["feuer"], feuer_lokal_s=ziel)
    if rest < -0.25:
        lauf.log(f"Polar: Feuerzeit kam {-rest:.2f} s zu spät an — trotzdem sofort drücken (nie einseitig zurück)")
    while True:                               # präzise: grob schlafen, die letzten ~3 ms aktiv
        r_ = ziel - time.time()
        if r_ <= 0:
            break
        time.sleep(min(r_ - 0.003, 0.01) if r_ > 0.004 else 0)
    return ziel


def melden(lauf, ereignis, daten=None):
    return railway(lauf, "POST", "/polar/melden", {"lauf_id": lauf.lauf_id, "seite": lauf.seite, "ereignis": ereignis, "daten": daten or {}})


# ── Rechnen (testbar) ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def level_vom_fill(richtung, fill, sl_pkt, tp_pkt, digits=2, tick=None):
    """Level vom ECHTEN Fill aus. richtung = Richtung DIESER Position. -> (sl, tp)"""
    f = float(fill)
    kauf = str(richtung).lower() == "buy"
    sl = f - float(sl_pkt) if kauf else f + float(sl_pkt)
    tp = f + float(tp_pkt) if kauf else f - float(tp_pkt)
    if tick:
        t = float(tick)
        sl, tp = round(round(sl / t) * t, 6), round(round(tp / t) * t, 6)
    return round(sl, int(digits)), round(tp, int(digits))


def reader_flach(d, ext, root, gesehen):
    """REIN RECHNEND (testbar): Reader-Stand → 'flach' | 'offen' | 'unklar'. Flach nur mit Beweis: Reader an, nicht blind,
    positionen_ok, Stand ≤ 1,5 s alt, richtiges Konto, Master seit dem Fill mindestens einmal gesehen."""
    if not isinstance(d, dict) or d.get("an") is False or d.get("blind") or not d.get("positionen_ok"):
        return "unklar"
    try:
        if float(d.get("positionen_alter_s") or d.get("alter_s") or 99) > 1.5:
            return "unklar"
    except (TypeError, ValueError):
        return "unklar"
    konto = str(d.get("konto") or "")
    e = re.sub(r"[^0-9a-z]", "", str(ext or "").lower())
    if e and e not in re.sub(r"[^0-9a-z]", "", konto.lower()):
        return "unklar"
    offen = [p for p in (d.get("positionen") or []) if isinstance(p, dict)
             and ob.tv_symbol_root(str(p.get("wurzel") or p.get("symbol") or "")) == root]
    if offen:
        return "offen"
    return "flach" if gesehen else "unklar"


def preisfeld_wahl(felder, art):
    """Genau ein beschreibbares Preisfeld im Ändern-Dialog. art 'tp' = Limit-Order, 'sl' = Stop-Order. -> Feld | None"""
    frei = [f for f in (felder or []) if isinstance(f, dict) and not f.get("aus")]
    lab = lambda f: str(f.get("label") or "").lower()
    if art == "tp":
        k = [f for f in frei if re.search(r"limit", lab(f)) and re.search(r"pre?is|price", lab(f))]
    else:
        k = [f for f in frei if re.search(r"stop", lab(f)) and re.search(r"pre?is|price", lab(f))]
    if len(k) == 1:
        return k[0]
    k = [f for f in frei if re.search(r"^(price|preis)\b", lab(f))]
    return k[0] if len(k) == 1 else None


def aendern_knopf(zeile):
    """Genau EIN Ändern-Knopf einer Order-Zeile (Modify/Edit/Ändern/Bearbeiten), nie Cancel/Close/Protect. -> Knopf | None"""
    kn = [k for k in ((zeile or {}).get("knoepfe") or []) if isinstance(k, dict)]
    txt = lambda k: " ".join(str(k.get(x) or "") for x in ("text", "aria", "title", "dn")).lower()
    gut = [k for k in kn if re.search(r"modify|edit|ändern|aendern|bearbeiten", txt(k))
           and not re.search(r"cancel|close|storn|abbrech|schlie|flatten|reverse|protect", txt(k))]
    return gut[0] if len(gut) == 1 else None


def order_zeile_passt(zeile, gegen, art):
    sp = (zeile or {}).get("spalten") or {}
    seite = str(sp.get("Side") or sp.get("Seite") or "").lower()
    typ = str(sp.get("Type") or sp.get("Typ") or "").lower()
    seite_ok = gegen in seite or (gegen == "sell" and "verk" in seite) or (gegen == "buy" and "kauf" in seite)
    if not seite_ok:
        return False
    return ("limit" in typ and "stop" not in typ) if art == "tp" else ("stop" in typ)


def zeilen_preis(zeile):
    sp = (zeile or {}).get("spalten") or {}
    for k in ("Limit Price", "Limitpreis", "Stop Price", "Stopp-Preis", "Price", "Preis"):
        z = ob.cdp_zahl(sp.get(k))
        if z:
            return z
    return None


# Ändern-Dialog einer offenen TradingView-Order: Modify-Knopf + Eingabefelder mit Beschriftung. Nur lesen.
AENDERN_JS = r"""(function () {
  function sb(e) { try { var r = e.getBoundingClientRect(); if (r.width < 3 || r.height < 3 || r.bottom < 0 || r.top > innerHeight) return false;
    var s = getComputedStyle(e); return s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; } catch (_) { return false; } }
  function R(e) { var r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }
  function T(e) { return String((e && e.textContent) || '').replace(/\s+/g, ' ').trim(); }
  function A(e, n) { try { return e.getAttribute(n) || ''; } catch (_) { return ''; } }
  var knoepfe = Array.prototype.slice.call(document.querySelectorAll('button,[role="button"]')).filter(function (b) {
    return sb(b) && /^(modify|ändern|aendern)\b/i.test(T(b)); });
  if (knoepfe.length !== 1) return { knoepfe: knoepfe.length };
  var k = knoepfe[0], box = k;
  for (var i = 0; i < 12 && box.parentElement; i++) { box = box.parentElement; if (box.querySelectorAll('input').length >= 1 && box.getBoundingClientRect().height > 120) break; }
  var felder = Array.prototype.slice.call(box.querySelectorAll('input')).filter(sb).map(function (inp) {
    var l = '', e = inp;
    for (var j = 0; j < 5 && e && !l; j++) { e = e.parentElement; if (!e) break;
      var lab = e.querySelector('label,[class*="label"],[class*="title"]'); if (lab && !lab.contains(inp)) l = T(lab); }
    return { label: (l || A(inp, 'aria-label') || A(inp, 'placeholder') || A(inp, 'data-name')).slice(0, 40), wert: String(inp.value || '').slice(0, 20),
             rect: R(inp), aus: !!inp.disabled || inp.readOnly }; });
  return { knoepfe: 1, knopf: { text: T(k).slice(0, 40), rect: R(k), aus: !!k.disabled || A(k, 'aria-disabled') === 'true' }, felder: felder.slice(0, 12) };
})()"""


# ── MASTER (TradingView im Puls-Chrome) ────────────────────────────────────────────────────────────────────────────────────────
def master_level_setzen(lauf, s, opts, plan, root, sl_soll, tp_soll, tick=0.25):
    """TP/SL nach dem Fill exakt: Reiter Orders → je Bracket (TP = Limit, SL = Stop der Gegenseite) genau EINE Zeile → Modify →
    Preisfeld → Rücklesung → Modify-Knopf → Zeile nachlesen. Jede Unsicherheit: ESC, die Ticket-Level bleiben (nur Punkte daneben)."""
    erg = {"ok": False, "tp": None, "sl": None, "teile": []}
    if not ob._cdp_reiter(s, "orders", lauf.trail):
        erg["teile"].append("Reiter Orders nicht aktiv")
        return erg
    gegen = "sell" if plan["richtung"] == "buy" else "buy"
    alle_ok = True
    for art, soll in (("tp", tp_soll), ("sl", sl_soll)):
        if soll is None:
            continue
        soll = round(round(float(soll) / tick) * tick, 2)
        ob._warte(0.4, 0.2)
        zeilen = [z for z in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(z, dict) and z.get("sichtbar")
                  and ob.tv_symbol_root(str(z.get("symbol") or "")) == root and order_zeile_passt(z, gegen, art)]
        if len(zeilen) != 1:
            erg["teile"].append(f"{art.upper()}: {len(zeilen)} passende Order-Zeilen — nicht geändert")
            alle_ok = False
            continue
        z = zeilen[0]
        ist = zeilen_preis(z)
        if ist is not None and abs(float(ist) - soll) < tick / 2:
            erg["teile"].append(f"{art.upper()} steht schon auf {soll:g}")
            erg[art] = soll
            continue
        s.hin(z.get("zeile"), f"Order-Zeile {art.upper()}")
        ob._warte(0.3, 0.2)
        z2 = next((x for x in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(x, dict) and x.get("zeile") == z.get("zeile")), z)
        kn = aendern_knopf(z2)
        if not kn or not s.klick(ob.cdp_rect(kn), f"Modify {art.upper()}"):
            erg["teile"].append(f"{art.upper()}: kein eindeutiger Ändern-Knopf — nicht geändert")
            alle_ok = False
            continue
        ob._warte(0.6, 0.3)
        d = s.lese_js(AENDERN_JS) or {}
        feld = preisfeld_wahl(d.get("felder"), art)
        knopf = d.get("knopf") if d.get("knoepfe") == 1 else None
        if not feld or not knopf or knopf.get("aus"):
            erg["teile"].append(f"{art.upper()}: Ändern-Dialog unklar (Felder {[f.get('label') for f in (d.get('felder') or [])][:6]}) — ESC")
            s.taste("Escape")
            alle_ok = False
            continue
        if not s.feld_setzen(ob.cdp_rect(feld), f"{soll:.2f}", f"{art.upper()}-Preis"):
            s.taste("Escape")
            erg["teile"].append(f"{art.upper()}: Preis nicht getippt — ESC")
            alle_ok = False
            continue
        ob._warte(0.3, 0.2)
        d2 = s.lese_js(AENDERN_JS) or {}
        f2 = preisfeld_wahl(d2.get("felder"), art)
        w2 = ob.cdp_zahl((f2 or {}).get("wert"))
        if w2 is None or abs(float(w2) - soll) >= tick / 2:
            s.taste("Escape")
            erg["teile"].append(f"{art.upper()}: Rücklesung '{(f2 or {}).get('wert')}' ≠ {soll:g} — ESC")
            alle_ok = False
            continue
        if not s.klick(ob.cdp_rect((d2.get("knopf") or knopf)), f"Modify-Knopf {art.upper()}"):
            s.taste("Escape")
            alle_ok = False
            continue
        ob._warte(0.8, 0.3)
        z3 = next((x for x in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(x, dict)
                   and ob.tv_symbol_root(str(x.get("symbol") or "")) == root and order_zeile_passt(x, gegen, art)), None)
        neu = zeilen_preis(z3)
        if neu is not None and abs(float(neu) - soll) < tick / 2:
            erg[art] = soll
            erg["teile"].append(f"{art.upper()} → {soll:g} ✓")
        else:
            alle_ok = False
            erg["teile"].append(f"{art.upper()}: nach Modify gelesen {neu} statt {soll:g}")
    ob._cdp_reiter(s, "positions", lauf.trail)
    erg["ok"] = alle_ok
    lauf.log("Polar-Level Master: " + (" · ".join(erg["teile"]) or "nichts zu ändern"))
    return erg


def master_druck(lauf, punkt, hwnd):
    """Zur Feuerzeit: Vordergrund + Fenster am Punkt (Millisekunden), dann EIN SendInput-Druck. -> (ok, klick_ms)"""
    if not punkt or not hwnd:
        lauf.log("Polar: kein gemerkter Klickpunkt — kein Druck")
        return False, None
    try:
        if ob._win_vordergrund() != int(hwnd):
            ob._win_nach_vorn(int(hwnd))
            if ob._win_vordergrund() != int(hwnd):
                lauf.log("Polar: Puls-Chrome nicht vorn — kein Druck")
                return False, None
        wurzel, titel = ob._win_root_am_punkt(*punkt)
        if wurzel != int(hwnd):
            lauf.log(f"Polar: am Klickpunkt liegt ein anderes Fenster ('{str(titel)[:40]}') — kein Druck")
            return False, None
    except Exception as e:
        lauf.log(f"Polar: Fenster-Prüfung vor dem Druck ({type(e).__name__}) — kein Druck")
        return False, None
    ok = bool(ob._klick_absolut(punkt[0], punkt[1]))
    return ok, jetzt_ms()


def master_wache(lauf, s, opts, ext, root, plan):
    """Nach dem Fill: Reader (8790) alle 50 ms, Puls-Chrome-Tabelle alle 1 s als Rückfall. Flach mit Beweis → sofort 'zu' an Railway.
    -> (zu_ms, quelle) | (None, grund)"""
    gesehen = False
    naechst_cdp = time.time() + 1.0
    flach_seit = None
    ende_max = time.time() + 6 * 3600
    lauf.phase("wache")
    while time.time() < ende_max:
        d = ob._tv_http("/positions", timeout=1.0)
        u = reader_flach(d, ext, root, gesehen)
        if u == "offen":
            gesehen = True
            flach_seit = None
        elif u == "flach":
            flach_seit = flach_seit or time.time()
            if time.time() - flach_seit >= 0.1:
                zu_ms = jetzt_ms()
                melden(lauf, "zu", {"quelle": "reader", "zu_ms": zu_ms})
                lauf.log("Polar: Master flach laut Reader — 'zu' an Railway gemeldet")
                return zu_ms, "reader"
        if time.time() >= naechst_cdp:
            naechst_cdp = time.time() + 1.0
            try:
                st = s.stand(opts)
                zeilen = ob.k3_zeilen(st.get("positionen"), root)
                menge = ob.cdp_zeilen_menge(zeilen, plan["richtung"])
                if menge > 0:
                    gesehen = True
                elif gesehen and u != "offen" and st.get("positionen") is not None:
                    ob._warte(0.3, 0.1)                   # zwei Blicke: der nächste bestätigt
                    st2 = s.stand(opts)
                    if ob.cdp_zeilen_menge(ob.k3_zeilen(st2.get("positionen"), root), plan["richtung"]) == 0:
                        zu_ms = jetzt_ms()
                        melden(lauf, "zu", {"quelle": "cdp", "zu_ms": zu_ms})
                        lauf.log("Polar: Master flach laut Puls-Chrome-Tabelle — 'zu' an Railway gemeldet")
                        return zu_ms, "cdp"
            except Exception as e:
                lauf.log(f"Wache CDP: {type(e).__name__}")
        time.sleep(0.05)
    return None, "zeitlimit"


def _punkt_aus_spur(trail):
    """Der bewiesene Bildschirmpunkt des letzten „Maus über … @x,y"-Eintrags (s.hin schreibt ihn in die Spur)."""
    for t in reversed(list(trail)):
        m = re.search(r"Maus über .*?@(-?\d+),(-?\d+)", str(t))
        if m:
            return (int(m.group(1)), int(m.group(2)))
    return None


def _zahl(x):
    try:
        v = float(x)
        return v if math.isfinite(v) and v > 0 else None
    except (TypeError, ValueError):
        return None


def lauf_master(cmd):
    lauf = Lauf("master", cmd)
    res = {"ok": False, "seite": "master", "gesendet": False, "retry_ok": True}
    sitz = [None]
    try:
        if ob.augen_modus_lauf() != "cdp":
            raise RuntimeError("Polar-Master braucht das Puls-Chrome (CDP) auf diesem PC")
        if ob._handlauf_aktiv():
            raise RuntimeError("K3-Handlauf läuft im Puls-Chrome")
        uhr_abgleichen(lauf)
        ext = str(cmd.get("ext_id") or "").strip()
        symbol = str(cmd.get("symbol") or "").strip()
        plan, fehler = ob.tv_order_plan(dict(cmd, scharf=True))
        if not plan:
            raise RuntimeError(f"Befehl: {fehler}")
        geschwister = [str(x).strip() for x in (cmd.get("geschwister") or []) if len(ob._nur_alnum(x)) >= 3][:60]
        opts = {"kontoTexte": [ext] + geschwister}
        root = ob.tv_symbol_root(symbol)
        lauf.log(f"Polar-Master v{VERSION}: {plan['richtung']} {plan['menge']} {symbol} Konto {ext}")
        lauf.phase("vorbereiten")
        s = sitz[0] = ob._cdp_sitzung_holen(cmd, lauf.trail)
        ok, code, msg, st, extra = ob._cdp_konto_mit_login(sitz, ext, opts, cmd, lauf.trail, res)
        s = sitz[0]
        if not ok:
            raise RuntimeError(f"Konto: {msg}")
        try:
            sm0, _t0, _l0, _x0 = ob._cdp_today_aus_reiter(s, opts, lauf.trail)
            res.update(ob.cdp_summary_start(sm0))
            st = s.stand(opts)
        except Exception as e_:
            lauf.log(f"Start-Werte nicht lesbar ({type(e_).__name__})")
        ok, code, msg, schritt, st, kk = ob._cdp_ticket_fuellen(s, st, plan, symbol, opts, lauf.trail)
        if not ok:
            raise RuntimeError(f"Ticket: {msg}")
        ob._cdp_positions_reiter_sichern(s, lauf.trail)
        # K4-Prüfungen aus EINEM frischen Blick (wie der alte Puls), dann Maus auf den Knopf + Hover beweisen
        st = s.stand(opts)
        rl_ok, rl_text, rl_fehler = ob.cdp_ticket_ruecklesung(st, plan)
        lauf.log(f"Rücklesung: {rl_text}")
        if not rl_ok:
            raise RuntimeError("Ticket passt nicht: " + "; ".join(rl_fehler))
        kk = st.get("kauf_knopf") if isinstance(st.get("kauf_knopf"), dict) else {}
        ko = st.get("konto") if isinstance(st.get("konto"), dict) else {}
        sym_k = str(kk.get("symbol") or "").strip() or symbol
        if ob.tv_symbol_root(sym_k) != root or not ob.k3_knopf_exakt(kk.get("text"), plan["richtung"], plan["menge"], sym_k):
            raise RuntimeError(f"Knopf zeigt '{kk.get('text')}', verlangt '{ob.k3_knopf_soll(plan['richtung'], plan['menge'], sym_k)}'")
        if kk.get("disabled") or ob.cdp_klickpunkt(ob.cdp_rect(kk)) is None:
            raise RuntimeError("Senden-Knopf gesperrt oder ohne Rechteck")
        if st.get("popups"):
            raise RuntimeError("Dialog/Popup offen")
        if not ob.cdp_konto_passt(str(ko.get("aktiv") or ""), ext):
            raise RuntimeError(f"Konto vor dem Klick nicht mehr {ext}")
        u_offen = ob._cdp_konto_offen_blick(s, st, root, lauf.trail, res)
        if u_offen["urteil"] == "offen":
            raise RuntimeError("Konto hat schon eine offene Position")
        menge0 = ob.cdp_zeilen_menge(ob.k3_zeilen(st.get("positionen"), root), plan["richtung"])
        vorher_m = [ob.k3_meldung_schluessel(m) for m in ((st.get("toasts") or {}).get("meldungen") or []) if isinstance(m, dict)]
        if not s.hin(ob.cdp_rect(kk), "SENDEN-Knopf (Polar scharf)"):
            raise RuntimeError("Maus nicht bewiesen über dem Senden-Knopf")
        punkt = _punkt_aus_spur(lauf.trail)          # s.hin merkt den Punkt nicht selbst — aus der Spur (ohne order_bot zu ändern)
        hwnd = s._win_vorn()[0] if hasattr(s, "_win_vorn") else None

        def halten():
            if not punkt:
                return False
            if ob._cursor_pos() != tuple(punkt):
                ob._maus_fahren(*punkt, schritte=3)
            return True
        ziel = bereit_und_warten(lauf, halten, {"symbol": sym_k, "menge": plan["menge"], "balance_start": res.get("balance_start")})
        if ziel is None:
            res["msg"] = "Polar abgebrochen vor dem Klick — nichts gesendet"
            lauf.phase("abbruch", msg=res["msg"])
            return res
        res["gesendet"], res["retry_ok"] = True, False
        ok_k, klick_ms = master_druck(lauf, punkt, hwnd)
        res["order_klick_ms"] = klick_ms
        if not ok_k:
            res["gesendet"] = False
            melden(lauf, "fehler", {"msg": "Senden-Knopf nicht gedrückt (Fenster/Hover) — nichts gesendet", "nichts_gesendet": True})
            res["msg"] = "Senden nicht gedrückt"
            lauf.phase("fehler", msg=res["msg"])
            return res
        lauf.log("Senden geklickt — ab hier zählt nur der Beweis")
        lauf.phase("geklickt", klick_ms=klick_ms)
        # Beweis (bis 15 s): neue Fill-Meldung oder gewachsene Positionsmenge (dieselbe reine Prüfung wie der alte Puls)
        b, fill = {}, None
        ende = time.time() + 15.0
        while time.time() < ende:
            ob._warte(0.4, 0.2)
            try:
                st = s.stand(opts)
            except Exception:
                continue
            alle = [m for m in ((st.get("toasts") or {}).get("meldungen") or []) if isinstance(m, dict)]
            neu = [m for m in alle if ob.k3_meldung_schluessel(m) not in vorher_m]
            b = ob.cdp_order_beweis(neu, ob.k3_zeilen(st.get("positionen"), root), plan, menge0) or {}
            if b.get("bestaetigt") and b.get("einstieg") is not None:
                fill = ob.cdp_zahl(b["einstieg"])
                break
        if not b.get("bestaetigt"):
            melden(lauf, "fehler", {"msg": "Senden geklickt, in 15 s kein Fill-Beweis — UNKLAR, in TradingView nachsehen", "unklar": True})
            res["msg"] = "Ergebnis unklar"
            lauf.phase("unklar", msg=res["msg"])
            return res
        res.update(bestaetigt=True, einstieg=fill, einstieg_quelle=b.get("einstieg_quelle"), tp_limit=b.get("tp"), sl_limit=b.get("sl"))
        melden(lauf, "gefuellt", {"fill": fill, "quelle": b.get("einstieg_quelle"), "klick_ms": klick_ms, "balance_start": res.get("balance_start")})
        lauf.phase("gefuellt", fill=fill)
        # Level exakt vom Fill (Finn: „der Master passt nach dem Platzieren TP und SL noch mal neu an")
        sl_pkt, tp_pkt = _zahl(cmd.get("sl_pkt")), _zahl(cmd.get("tp_pkt"))
        if fill and sl_pkt and tp_pkt:
            sl_s, tp_s = level_vom_fill(plan["richtung"], fill, sl_pkt, tp_pkt, 2, tick=0.25)
            lv = master_level_setzen(lauf, s, opts, plan, root, sl_s, tp_s)
            res["level"] = dict(lv, sl_soll=sl_s, tp_soll=tp_s)
            melden(lauf, "level", res["level"])
            lauf.phase("level", level=res["level"])
        # Wache: Master zu → sofort melden, dann Balance lesen
        zu_ms, quelle = master_wache(lauf, s, opts, ext, root, plan)
        ende_daten = {"zu_ms": zu_ms, "zu_quelle": quelle, "balance_start": res.get("balance_start")}
        try:
            info = ob._cdp_today_info(s, opts, lauf.trail) or {}
            ende_daten.update({k: info.get(k) for k in ("balance_end", "equity_end", "today_pnl") if k in info})
        except Exception as e_:
            lauf.log(f"Balance am Ende nicht lesbar ({type(e_).__name__})")
        melden(lauf, "ende", ende_daten)
        res.update(ok=zu_ms is not None, ende=ende_daten, msg="Polar-Master fertig" if zu_ms else "Wache ohne Ende")
        lauf.phase("ende", ende=ende_daten)
        return res
    except Exception as e:
        res["msg"] = f"{type(e).__name__}: {str(e)[:200]}"
        lauf.log("ABBRUCH: " + res["msg"])
        if res.get("gesendet"):
            melden(lauf, "fehler", {"msg": res["msg"]})
        else:
            melden(lauf, "abbruch", {"grund": res["msg"]})
        lauf.phase("fehler" if res.get("gesendet") else "abbruch", msg=res["msg"])
        return res
    finally:
        try:
            if sitz[0]:
                ob._cdp_panel_zurueck(sitz[0], lauf.trail)
                sitz[0].zu()
        except Exception:
            pass
        res["trail"] = ob._spur(lauf.trail)


# ── SLAVE (MT5-Terminal) ───────────────────────────────────────────────────────────────────────────────────────────────────────
def lauf_slave(cmd):
    """Eigener Order-Weg mit denselben Bausteinen wie order_bot.run(): F9 → Symbol → Volumen → grobe SL/TP → Maus über dem Knopf →
    bereit/Feuerzeit → EIN Druck → Fill lesend → SL/TP per Klick vom Fill → parken → Signal → Rechtsklick „Position schließen"."""
    lauf = Lauf("slave", cmd)
    res = {"ok": False, "seite": "slave", "gesendet": False, "retry_ok": True}
    cfg_path = os.path.join(HIER, str(cmd.get("config_file") or ""))
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        path = str(cfg.get("master_terminal_path") or "").strip()
        expected = int(cfg.get("master_expected_login") or 0)
        if not path or not os.path.exists(path) or not expected:
            raise RuntimeError("Config: master_terminal_path/master_expected_login fehlen")
        import pywinauto  # noqa: F401
        from pywinauto.timings import Timings
        Timings.window_find_timeout = 1.0
        Timings.exists_timeout = 0.3
        uhr_abgleichen(lauf)
        symbol = str(cmd["symbol"]).strip()
        richtung = str(cmd["richtung"]).lower()
        kauf = richtung == "buy"
        vol = float(cmd["volumen"])
        sl_pkt, tp_pkt = _zahl(cmd.get("sl_pkt")), _zahl(cmd.get("tp_pkt"))
        if not sl_pkt or not tp_pkt:
            raise RuntimeError("sl_pkt/tp_pkt fehlen")
        lauf.log(f"Polar-Slave v{VERSION}: {richtung} {vol:g} {symbol} Konto {expected} · SL {sl_pkt:g} / TP {tp_pkt:g} Pkt vom Fill")
        lauf.phase("vorbereiten")
        lese = ob._login_dann_lesen(path, expected, trail=lauf.trail, symbol=symbol)
        if "fehler" in lese:
            raise RuntimeError(lese["fehler"])
        digits, contract_size = lese["digits"], lese["contract_size"]
        vorher_tickets = {p["ticket"] for p in lese["positionen"]}
        res["balance_start"] = lese.get("balance")
        w = ob._finde_terminal(expected)
        if w is None:
            raise RuntimeError(f"Kein MT5-Fenster mit Konto {expected}")
        ob._fenster_betreten(w)
        if str(expected) not in (w.window_text() or ""):
            raise RuntimeError("Fenster-Guard: Titelzeile passt nicht")
        w.type_keys("{F9}")
        ob._warte(0.4, 0.35)
        dlg = ob._finde_order_dialog(w)
        if dlg is None:
            raise RuntimeError("F9-Dialog nicht gefunden")
        ob._warte(0.5, 0.3)
        combos = dlg.descendants(control_type="ComboBox")
        if not combos:
            raise RuntimeError("Symbol-Feld im F9-Dialog nicht gefunden")
        cb = combos[0]
        try:
            cb.set_focus()
            ob._warte(0.1, 0.1)
            cb.type_keys("^a" + symbol + "{ENTER}", with_spaces=True, set_foreground=False)
        except Exception as e_:
            raise RuntimeError(f"Symbol tippen: {type(e_).__name__}")
        ob._warte(0.5, 0.3)
        if symbol.lower() not in str(cb.window_text() or "").lower():
            raise RuntimeError(f"Symbol steht nicht im Dialog ('{cb.window_text()}')")
        fmap = ob._map_felder(dlg)
        vol_el = fmap.get("volumen") or fmap.get("vol") or fmap.get("volume")
        if vol_el is None or not ob._feld_tippen(vol_el, f"{vol:g}", "Volumen", lauf.trail, rahmen=dlg):
            raise RuntimeError("Volumen nicht sicher getippt")
        # grobe SL/TP schon im F9-Dialog (Schutz ab dem Fill, 2 Pkt weiter weg); exakt per Klick vom Fill danach
        ref = lese.get("ref_ask") if kauf else lese.get("ref_bid")
        if ref and fmap.get("sl") is not None and fmap.get("tp") is not None:
            sl_g, tp_g = level_vom_fill(richtung, ref, sl_pkt + 2.0, tp_pkt + 2.0, digits)
            if not (ob._feld_tippen(fmap["sl"], ob.fmt_preis(sl_g, digits), "F9-SL", lauf.trail, rahmen=dlg)
                    and ob._feld_tippen(fmap["tp"], ob.fmt_preis(tp_g, digits), "F9-TP", lauf.trail, rahmen=dlg)):
                ob._feld_tippen(fmap["sl"], "0", "F9-SL-Reset", lauf.trail, rahmen=dlg)
                ob._feld_tippen(fmap["tp"], "0", "F9-TP-Reset", lauf.trail, rahmen=dlg)
        muster = "buy" if kauf else "sell"
        knopf = next((b for b in dlg.descendants(control_type="Button")
                      if muster in (b.window_text() or "").lower() and "stop" not in (b.window_text() or "").lower()
                      and "limit" not in (b.window_text() or "").lower()), None)
        if knopf is None:
            raise RuntimeError(f"Kein {muster}-Knopf im Dialog")
        ziel_punkt = ob._echo_klickziel(knopf.rectangle())
        ob._maus_fahren(*ziel_punkt, schritte=6)

        def dialog_weg():
            try:
                return not dlg.is_visible()
            except Exception:
                return True

        def halten():
            if dialog_weg():
                return False
            if ob._cursor_pos() != tuple(ziel_punkt):
                ob._maus_fahren(*ziel_punkt, schritte=3)
            return True
        ziel = bereit_und_warten(lauf, halten, {"symbol": symbol, "volumen": vol, "balance_start": res.get("balance_start")})
        if ziel is None:
            try:
                dlg.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            res["msg"] = "Polar abgebrochen vor dem Knopf — nichts gesendet"
            lauf.phase("abbruch", msg=res["msg"])
            return res
        res["gesendet"], res["retry_ok"] = True, False
        if not ob._klick_absolut(ziel_punkt[0], ziel_punkt[1]):
            res["gesendet"] = False
            melden(lauf, "fehler", {"msg": "SendInput abgelehnt — nichts gesendet", "nichts_gesendet": True})
            raise RuntimeError("SendInput abgelehnt")
        klick_ms = jetzt_ms()
        res["order_klick_ms"] = klick_ms
        lauf.log(f"{muster}-Knopf: Polar-Druck")
        lauf.phase("geklickt", klick_ms=klick_ms)
        p = None
        ende = time.time() + 12
        while time.time() < ende and p is None:
            st = ob._api_lesen(path, expected)
            if "fehler" not in st:
                p = ob.finde_neue_position(vorher_tickets, st["positionen"], symbol, richtung, vol)
            if p is None:
                ob._warte(0.12, 0.1)
        if p is None:
            melden(lauf, "fehler", {"msg": "Druck ohne neue Position in 12 s — UNKLAR, im Terminal nachsehen", "unklar": True})
            res["msg"] = "kein Fill"
            lauf.phase("unklar", msg=res["msg"])
            return res
        fill, ticket = p["preis"], p["ticket"]
        res.update(price=fill, ticket=ticket, volumen=p["volumen"])
        melden(lauf, "gefuellt", {"fill": fill, "ticket": ticket, "volumen": p["volumen"], "klick_ms": klick_ms, "balance_start": res.get("balance_start")})
        lauf.phase("gefuellt", fill=fill, ticket=ticket)
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        ob._warte(0.2, 0.2)
        sl, tp = level_vom_fill(richtung, fill, sl_pkt, tp_pkt, digits)
        anker_pfad = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "anker-" + os.path.basename(cfg_path))
        bestaetigt = ob.sltp_bestaetigt(p["sl"], p["tp"], sl, tp, digits)
        if not bestaetigt:
            ob._sltp_klicken(w, ticket, symbol, ob.fmt_preis(sl, digits), ob.fmt_preis(tp, digits), lauf.trail, anker_pfad=anker_pfad)
            ende2 = time.time() + 10
            while time.time() < ende2 and not bestaetigt:
                st = ob._api_lesen(path, expected)
                if "fehler" not in st:
                    bestaetigt = any(q["ticket"] == ticket and ob.sltp_bestaetigt(q["sl"], q["tp"], sl, tp, digits) for q in st["positionen"])
                if not bestaetigt:
                    ob._warte(0.15, 0.15)
        res.update(sl=sl, tp=tp, level_ok=bestaetigt)
        melden(lauf, "level", {"sl": sl, "tp": tp, "ok": bestaetigt})
        lauf.phase("level", sl=sl, tp=tp, level_ok=bestaetigt)
        if not bestaetigt:
            lauf.log(f"SL/TP NICHT bestätigt — im Terminal SL {ob.fmt_preis(sl, digits)} / TP {ob.fmt_preis(tp, digits)} von Hand nachtragen")
        wache = slave_wache(lauf, w, path, expected, ticket, anker_pfad)
        wache["balance_start"] = res.get("balance_start")
        res["wache"] = wache
        melden(lauf, "ende", {"wache": wache, "fill": fill, "ticket": ticket, "balance_start": res.get("balance_start")})
        res.update(ok=bool(wache.get("ok")), msg=wache.get("msg") or "Polar-Slave fertig")
        lauf.phase("ende", wache=wache)
        return res
    except Exception as e:
        res["msg"] = f"{type(e).__name__}: {str(e)[:200]}"
        lauf.log("ABBRUCH: " + res["msg"])
        if res.get("gesendet"):
            melden(lauf, "fehler", {"msg": res["msg"]})
        else:
            melden(lauf, "abbruch", {"grund": res["msg"]})
        lauf.phase("fehler" if res.get("gesendet") else "abbruch", msg=res["msg"])
        return res
    finally:
        try:
            ob._api_trennen()
        except Exception:
            pass
        res["trail"] = ob._spur(lauf.trail)


def slave_wache(lauf, w, path, expected, ticket, anker_pfad):
    """Maus auf der (ticket-bewiesenen) Positionszeile parken, /polar/warte?auf=zu halten. Signal → Rechtsklick an derselben Stelle →
    „Position schließen" (Ein-Klick-Handel = sofort zu); sonst der volle bewährte _close_klicken. Schließt der Broker selbst (SL/TP),
    endet die Wache ohne Klick. Zwischendurch (nie zwischen Signal und Druck) Fenster/Maus prüfen und neu parken."""
    erg = {"ok": False, "ticket": ticket, "geparkt": False}

    def lesen():
        st = ob._api_lesen(path, expected)
        return None if "fehler" in st else st

    def offen(st):
        return any(p["ticket"] == ticket for p in (st or {}).get("positionen") or [])

    def punkt_rechnen():
        hr = w.rectangle()
        a = ob._anker_lesen(anker_pfad)
        return (hr.left + int((hr.right - hr.left) * float(a["x_frac"])), hr.bottom - int(a["y_off"])), (hr.left, hr.top, hr.right, hr.bottom)

    try:
        punkt, fenster = punkt_rechnen()
    except Exception as e:
        punkt, fenster = None, None
        lauf.log(f"Wache: kein Zeilen-Anker ({type(e).__name__}) — Schließen läuft dann über den vollen Zeilen-Scan")
    if punkt:
        ob._maus_fahren(*punkt, schritte=6)
        erg["geparkt"] = True
        lauf.log(f"Wache: Maus parkt auf der Positionszeile #{ticket} @{punkt[0]},{punkt[1]}")
    melden(lauf, "geparkt", {"ticket": ticket, "punkt": list(punkt) if punkt else None})
    lauf.phase("wache", geparkt=erg["geparkt"])
    signal = {"da": False, "status": None, "ende": False}
    stop = threading.Event()

    def _warten():
        while not stop.is_set() and not signal["da"] and not signal["ende"]:
            a = railway(lauf, "GET", f"/polar/warte?lauf_id={lauf.lauf_id}&seite=slave&auf=zu&max_s=20", timeout=30)
            if not a:
                time.sleep(0.3)
                continue
            signal["status"] = a.get("status")
            if a.get("master_zu_ms") is not None:
                signal["da"] = True
            elif str(a.get("status")) == "fehler":
                signal["da"] = True        # Master-Fehler nach der Feuerzeit: Slave schließt ebenfalls (nie einseitig offen bleiben)
            elif str(a.get("status")) in ("fertig", "abbruch"):
                signal["ende"] = True
    threading.Thread(target=_warten, daemon=True).start()
    st0 = lesen()
    einzig = bool(st0) and len(st0["positionen"]) == 1 and offen(st0)
    naechst_lesen, naechst_blick = time.time() + 1.0, time.time() + 0.5
    ende_max = time.time() + 6 * 3600
    weg = None
    while time.time() < ende_max and not signal["da"]:
        if signal["ende"]:
            break
        jetzt = time.time()
        if jetzt >= naechst_lesen:
            naechst_lesen = jetzt + 1.0
            st = lesen()
            if st is not None:
                if not offen(st):
                    lauf.log("Wache: Position beim Broker zu (SL/TP oder von Hand) — kein Klick nötig")
                    erg.update(ok=True, zu_weg="broker", zu_ms=jetzt_ms())
                    stop.set()
                    break
                einzig = len(st["positionen"]) == 1
        if punkt and jetzt >= naechst_blick:
            naechst_blick = jetzt + 0.5
            try:
                if ob._win_vordergrund() != int(w.handle):
                    ob._fenster_betreten(w)
                p_neu, f_neu = punkt_rechnen()
                if f_neu != fenster or p_neu != punkt:
                    punkt, fenster = p_neu, f_neu
                    lauf.log(f"Wache: Fenster bewegt — neu geparkt @{punkt[0]},{punkt[1]}")
                    ob._maus_fahren(*punkt, schritte=4)
                elif ob._cursor_pos() != tuple(punkt):
                    ob._maus_fahren(*punkt, schritte=4)
            except Exception:
                pass
        time.sleep(0.004)
    stop.set()
    if signal["da"] and not erg.get("zu_weg"):
        t_sig = time.time()
        erg["signal_ms"] = jetzt_ms()
        if punkt and einzig and not ob.is_paused():
            # EIN Handgriff: Rechtsklick auf die geparkte Zeile → „Position schließen". Der Anker ist die Stelle, an der beim SL/TP-Setzen
            # der Ändern-Dialog mit DIESEM Ticket aufging, und es ist genau eine Position offen (die Wache liest mit).
            if ob._klick_absolut(punkt[0], punkt[1], taste="rechts"):
                st_m = ob._kontextmenue_close_klicken(timeout=0.8)
                erg["klick_ms"] = jetzt_ms()
                if st_m == "geklickt":
                    lauf.log(f"Polar: 'Position schließen' {int((time.time() - t_sig) * 1000)} ms nach dem Signal")
                    ende = time.time() + 3.0
                    while time.time() < ende:
                        if not offen(lesen()):
                            weg = "ein_klick"
                            break
                        dlg, knopf = ob._finde_close_dialog(w, ticket)
                        if knopf is not None:
                            try:
                                r = knopf.rectangle()
                                ob._klick_absolut(r.mid_point().x, r.mid_point().y)
                                lauf.log("Polar: Close-Dialog (Ein-Klick-Handel aus) — Schließen-Knopf gedrückt")
                            except Exception:
                                pass
                        time.sleep(0.05)
                else:
                    try:
                        w.type_keys("{ESC}", set_foreground=False)
                    except Exception:
                        pass
                    lauf.log(f"Polar: Kontextmenü ohne 'Position schließen' ({st_m}) — voller Zeilen-Scan")
        if weg is None and offen(lesen()):
            st_n = lesen()
            if st_n and len(st_n["positionen"]) == 1:
                ausgang = ob._close_klicken(w, ticket, lauf.trail, anker_pfad, lambda: not offen(lesen()))
                lauf.log(f"Polar: voller Schließ-Scan → {ausgang}")
            else:
                lauf.log("Polar: mehrere Positionen offen — Zeilen-Scan nicht sicher, Schließen von Hand nötig")
        ende = time.time() + 8.0
        while time.time() < ende and offen(lesen()):
            time.sleep(0.1)
        zu = not offen(lesen())
        erg.update(ok=zu, zu_weg=(weg or ("scan" if zu else None)), zu_ms=jetzt_ms() if zu else None)
        if not zu:
            erg["msg"] = f"Polar: Position #{ticket} nach dem Signal NICHT zu — SOFORT im Terminal schließen!"
    elif not erg.get("zu_weg"):
        erg["msg"] = f"Wache beendet ohne Signal ({signal['status']})"
    if erg.get("ok"):
        try:
            ob._fremde_dialoge_schliessen(w)
        except Exception:
            pass
        erg["profit"] = ob._deal_profit_lesen(path, expected, ticket)
        st_b = lesen()
        if st_b:
            erg["balance_end"], erg["equity_end"] = st_b.get("balance"), st_b.get("equity")
    return erg


# ── Start ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(errors="replace")
        except Exception:
            pass
    if len(sys.argv) < 3 or sys.argv[1] not in ("master", "slave"):
        print(json.dumps({"ok": False, "msg": "Aufruf: polar_bot.py master|slave '<json>'"}))
        return 2
    try:
        cmd = json.loads(sys.argv[2])
    except ValueError as e:
        print(json.dumps({"ok": False, "msg": f"Befehl kein gültiges JSON: {e}"}))
        return 2
    res = lauf_master(cmd) if sys.argv[1] == "master" else lauf_slave(cmd)
    print(json.dumps(res, ensure_ascii=False, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
