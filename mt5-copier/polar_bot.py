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
     das Schließen-× der eigenen Positionszeile parken (Profit-Spalte, ganz rechts — NIE die × neben S/L und T/P, die löschen nur die
     Level), GET /polar/warte?auf=zu halten → Signal = EIN Klick auf das × (Ein-Klick-Handel = sofort zu), Beweis lesend ≤ 2 s, sonst
     Rückfall Rechtsklick + „Position schließen"; nie per EA (FundedNext ≥ 50k = nur manuell, der Deal-Grund ist für die Firma sichtbar)
     → Balance/P&L lesen. Dazu die Slave-Wache: eigene Position alle 100 ms lesend — weg (SL/TP/Hand) → sofort POST /polar/melden zu.
     SYMMETRISCH (Finn 20.10.2026 01:10 Dubai, „egal ob Master-PC A oder Slave-PC B, egal wer zuerst — der andere schließt in 1–2 s"):
     der Master parkt nach dem Fill die Maus auf dem × der Positions-Linie im Chart (Tooltip „Position Schließen"), hält parallel zur
     Reader-Wache GET /polar/warte?auf=zu — kommt „zu" vom Slave zuerst, EIN Klick aufs ×, Beweis Reader flach ≤ 2 s, sonst Rückfall
     über den Close-Knopf der Positions-Tabelle (tvclose-Weg).
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
import queue
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import order_bot as ob  # noqa: E402  — nur benutzen, nie ändern

RAILWAY = "https://web-production-bec81.up.railway.app"
POLAR_ORDNER = os.path.join(HIER, "polar")
VERSION = "0.3.10"   # 0.3.10 (21.10.2026): CDP-Flach nur bei sichtbarem Positions-Reiter, „Inactive" nie aktiv · 0.3.9 (21.10.2026): „zu" erst nach zwei Lesungen, Airbag-Abbruch bei Master-zu · 0.3.8 (21.10.2026): Master bestätigt die „Close position"-Rückfrage, Level aus dem Orders-Reiter · 0.3.7 (21.10.2026): Puffer fest 2,5 % vom Abstand (Railway) · 0.3.6 (21.10.2026): Slave-SL/TP als Airbag aus beiden Fills + Master-Liquidation · 0.3.5 (21.10.2026): Slave-× per Bild bewiesen (MT5-Liste ohne UIA-Zellen), Maus-Test belegt × und Rechtsklick · 0.3.4 (21.10.2026): Master-Level 1:1 wie Orbit (Ticket-Klammer, keine Nachkorrektur) · 0.3.3 (21.10.2026): Symbol-Prüfung über den Feld-Wert · 0.3.2 (21.10.2026): Notfall-SL/TP Pflicht, F9 bei Abbruch zu · 0.3.1 (21.10.2026): Slave bricht ohne config_file benannt ab · 0.2.0 (20.10.2026): Schließen per × auf beiden Seiten, egal wer zuerst zu ist · 0.3.0 (21.10.2026): Schritte an Railway (Live-Ablauf)


# ── Zustand / Dateien ───────────────────────────────────────────────────────────────────────────────────────────────────────────
class Lauf:
    def __init__(self, seite, cmd, test=None):
        self.seite = seite
        self.cmd = cmd
        self.test = test
        self.lauf_id = str(cmd.get("lauf_id") or "").strip()
        if test:
            # MAUS-TEST (20.10.2026): kein Lauf, keine Railway-Meldung — Log test_x_<seite>.log und stand_test_<seite>.json direkt unter polar/
            self.ordner = POLAR_ORDNER
        else:
            self.ordner = os.path.join(POLAR_ORDNER, re.sub(r"[^0-9a-f-]", "", self.lauf_id)[:36] or "ohne")
        os.makedirs(self.ordner, exist_ok=True)
        self.trail = ob._StempelSpur()
        self.stand = {"seite": seite, "lauf_id": self.lauf_id, "plan_id": cmd.get("plan_id"), "phase": "start", "pid": os.getpid(),
                      "version": VERSION, "at_ms": jetzt_ms(), "test": test}
        self.uhr_versatz_ms = 0.0      # Railway-Uhr − eigene Uhr
        self.token = None
        try:
            with open(os.path.join(HIER, "code_token.txt"), "r", encoding="utf-8") as f:
                self.token = f.read().strip() or None
        except OSError:
            self.token = None
        self.log_datei = os.path.join(self.ordner, f"{test}_{seite}.log" if test else f"{seite}.log")
        # LIVE-ABLAUF (Finn 20.10.2026 ~23:55 Dubai: „… was die gerade genau machen: wird geöffnet, platziert, bereit zum Drücken — die ganzen
        # Steps dahin schreiben"): jede Phase geht als Schritt an Railway (/polar/schritt). Eigener Hintergrund-Sender, Queue ohne Warten —
        # ein langsamer oder fehlgeschlagener Melde-Call hält den Lauf NIE auf (voll = Schritt verworfen, Fehler nur im Log).
        self._schritte = queue.Queue(maxsize=SCHRITT_QUEUE_MAX)
        self._sender = None
        self.stand_datei = os.path.join(self.ordner, f"stand_test_{seite}.json" if test else f"stand_{seite}.json")

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
        schreiben(self.stand_datei, self.stand)
        self.schritt(name, schritt_text(self.seite, name, felder, self.cmd), self.stand["at_ms"])

    def schritt(self, name, text, at_ms=None):
        """Schritt an Railway, nie blockierend (put_nowait; Sender-Thread einmal je Lauf). Maus-Test meldet nichts."""
        if self.test or not self.lauf_id or not self.token:
            return
        try:
            self._schritte.put_nowait({"lauf_id": self.lauf_id, "seite": self.seite, "phase": name, "text": str(text or "")[:160],
                                       "at_ms": int(at_ms or jetzt_ms())})
        except queue.Full:
            return
        if self._sender is None:
            self._sender = threading.Thread(target=_schritt_sender, args=(self,), daemon=True)
            self._sender.start()
            _SCHRITT_LAEUFE.append(self)

    def abbruch_gewuenscht(self):
        return os.path.exists(os.path.join(self.ordner, "abbruch.json"))


def jetzt_ms():
    return int(time.time() * 1000)


SCHRITT_QUEUE_MAX = 60        # mehr Schritte hat kein Lauf; voll = verwerfen statt warten
SCHRITT_TIMEOUT_S = 4         # ein Melde-Call wartet höchstens so lange (im Sender-Thread, nie im Lauf)
SCHRITT_ABSTAND_S = 0.2       # Drossel zwischen zwei Calls
SCHRITT_ABWARTEN_S = 6.0      # am Lauf-Ende höchstens so lange warten, bis die letzten Schritte (zu_bestaetigt, ende) draußen sind
_SCHRITT_LAEUFE = []          # Läufe mit gestartetem Sender (für das Abwarten in main)


def _schritt_sender(lauf):
    """Hintergrund: Schritte nacheinander an /polar/schritt. railway() wirft nie; scheitert ein Call, bleibt der Schritt weg (Log).
    Läuft bis zum Prozessende (daemon) — KEIN Ruhe-Timeout (Prüfer S2 21.10.2026: mit get(timeout=600) starb er in der stundenlangen
    Wache, die End-Schritte blieben in der Queue und die Live-Tabelle stand bei „Wache läuft")."""
    while True:
        d = lauf._schritte.get()
        try:
            railway(lauf, "POST", "/polar/schritt", d, timeout=SCHRITT_TIMEOUT_S)
        finally:
            lauf._schritte.task_done()
        time.sleep(SCHRITT_ABSTAND_S)


def schritte_abwarten(max_s=SCHRITT_ABWARTEN_S):
    """Am Lauf-Ende (main): höchstens max_s warten, bis alle Sender ihre Queue geleert haben — der Prozess endet sonst, bevor „ende" gesendet
    ist. Wartet nie länger; nichts hier kann den Lauf selbst aufhalten (der ist zu diesem Zeitpunkt schon beendet)."""
    ende = time.time() + max(0.0, float(max_s))
    while time.time() < ende and any(getattr(l._schritte, "unfinished_tasks", 0) for l in _SCHRITT_LAEUFE):
        time.sleep(0.1)


def _preis(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "?"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def schritt_text(seite, name, felder, cmd):
    """REIN RECHNEND (testbar, tools/selftest_polar_close.py): kurze Zeile je Phase für die Live-Ablauf-Tabelle (Slave links, Master rechts).
    Nennt nie Kontonummern oder Logins — nur Richtung, Menge, Symbol, Preise, Gründe."""
    f, c = felder or {}, cmd or {}
    ri = str(c.get("richtung") or "").upper() or "?"
    menge = c.get("volumen") if c.get("volumen") is not None else c.get("kontrakte")
    sym = str(c.get("symbol") or ("NAS100" if seite == "slave" else "?"))
    order = f"{ri} {menge if menge is not None else '?'} {sym}"
    if name == "vorbereiten":
        return "MT5 öffnen, Ticket vorbereiten" if seite == "slave" else "Puls-Chrome: Konto wählen, Order-Ticket vorbereiten"
    if name == "bereit":
        return f"{order} steht vor dem Klick — wartet auf die Feuerzeit"
    if name == "feuer":
        ms = f.get("feuer_ms")
        try:
            uhr = time.strftime("%H:%M:%S", time.localtime(int(ms) / 1000)) + f".{int(ms) % 1000:03d}"
        except (TypeError, ValueError):
            uhr = "?"
        return f"Feuerzeit {uhr}"
    if name == "geklickt":
        return f"{order} gedrückt"
    if name == "gefuellt":
        return f"gefüllt {_preis(f.get('fill'))}"
    if name == "level":
        lv = f.get("level") if isinstance(f.get("level"), dict) else f
        sl, tp = lv.get("sl_soll", lv.get("sl")), lv.get("tp_soll", lv.get("tp"))
        ok = lv.get("level_ok", lv.get("ok"))
        ab = (f" · Airbag vor Master-Liq {_preis(lv.get('master_liq'))}" if lv.get("quelle") == "airbag" and lv.get("master_stop_art") == "liq"
              else " · Airbag vor Master-SL" if lv.get("quelle") == "airbag" else "")
        return f"SL/TP gesetzt {_preis(sl)} / {_preis(tp)}{ab}" + (" — nicht bestätigt, von Hand prüfen" if ok is False else "")
    if name == "geparkt_x":
        return "Maus auf dem Schließen-×"
    if name == "wache":
        return "Wache läuft — Position offen" + ("" if f.get("x_geparkt", True) else " (Maus auf der Zeile, × nicht bewiesen)")
    if name == "x_geklickt":
        return "× geklickt" + ("" if f.get("x_ok", True) else " — Beweis fehlt")
    if name == "zu_bestaetigt":
        q = f.get("zu_quelle") or f.get("zu_weg") or ""
        return "zu bestätigt" + (f" ({q})" if q else "")
    if name in ("fehler", "abbruch", "unklar", "nicht_zu"):
        return f"{name}: {str(f.get('msg') or '')[:120]}".rstrip(": ")
    if name == "ende":
        return "Ende gemeldet — Railway rechnet ab"
    return name


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


# ── AIRBAG-LEVEL AUS BEIDEN FILLS (Finn 21.10.2026: „Wir wissen ja erst genau, wo der hin muss, wenn wir den Fill bekommen … Bei Radar-Trades
# ist es nie 1:1 mit dem TP/SL, den wir einstellen, weil sich der Preis ändert, während die Order platziert wird") ──────────────────────
# Der Master hat meist KEINEN Stop-Loss, sein Stopp ist die Liquidation. Railway rechnet beim Start ihren $-Abstand wie der Radar
# (polar_app.liq_vorgabe → master.liq). Nach beiden Fills überträgt der Slave die Abstände in Punkten auf den EIGENEN Fill (NQ/MNQ ↔ NAS100
# = Indexpunkte):
#   Slave-TP (Airbag)  = Abstand bis zur Master-Liquidation (bzw. seinem echten SL, falls näher) × (1 − Puffer)
#   Slave-SL           = Abstand bis zum ECHTEN Master-TP (aus TradingViews Meldung) × (1 + Puffer)
# Puffer = polar_app.POLAR_PUFFER_PCT (2,5 %, Finn 21.10.2026), kommt mit master.liq.puffer_pct — keine zweite Konstante hier.
AIRBAG_WARTE_S = 20.0         # so lange wartet der Slave nach dem eigenen Fill auf Master-Fill + Master-Level (Notfall-SL/TP schützen solange)


def airbag_level(s_richtung, s_fill, m_fill, m_tp, m_sl, liq, digits=2):
    """REIN RECHNEND (testbar): exakte Slave-Level aus beiden Fills. liq = master.liq von Railway ({ok, abstand_pkt, puffer_pct, master_tp_pkt}).
    m_tp/m_sl = echte Master-Level aus TradingViews Meldungen (None = keins; ohne TP gilt Fill ± master_tp_pkt).
    -> {ok, sl, tp, master_liq, master_stop, master_stop_art, master_tp, master_tp_quelle, abstand_tp_pkt, abstand_stop_pkt, puffer_pct} | {ok False, grund}"""
    if not isinstance(liq, dict) or not liq.get("ok"):
        return {"ok": False, "grund": "Liq des Masters fehlt: " + str((liq or {}).get("grund") or "kein master.liq")}
    try:
        sf, mf = float(s_fill), float(m_fill)
        liq_pkt, pct = float(liq["abstand_pkt"]), float(liq["puffer_pct"])
    except (TypeError, ValueError, KeyError):
        return {"ok": False, "grund": "Fill/Liq nicht lesbar"}
    if str(s_richtung).lower() not in ("buy", "sell") or sf <= 0 or mf <= 0 or liq_pkt <= 0 or not (0 <= pct < 50):
        return {"ok": False, "grund": "Fill/Liq ungültig"}
    m_kauf = str(s_richtung).lower() == "sell"            # Master steht immer gegen den Slave
    vz = 1.0 if m_kauf else -1.0                          # + = Gewinnseite des Masters
    m_liq = mf - vz * liq_pkt
    stop, art = m_liq, "liq"
    sl_m = _zahl(m_sl)
    if sl_m is not None and vz * (mf - sl_m) > 0 and vz * (sl_m - m_liq) > 0:
        stop, art = sl_m, "sl"                            # echter Master-SL liegt näher als die Liquidation
    tp_m, tp_q = _zahl(m_tp), "tradingview"
    if tp_m is None or vz * (tp_m - mf) <= 0:
        mtp = _zahl(liq.get("master_tp_pkt"))
        if not mtp or mtp <= 0:
            return {"ok": False, "grund": "Master-TP weder gemeldet noch im Auftrag"}
        tp_m, tp_q = mf + vz * mtp, "plan"
    d_tp, d_stop = abs(tp_m - mf), abs(stop - mf)
    tp_pkt, sl_pkt = d_stop * (1 - pct / 100.0), d_tp * (1 + pct / 100.0)
    if tp_pkt <= 0:
        return {"ok": False, "grund": f"Master-Stopp {d_stop:g} Pkt — kein Airbag-TP"}
    sl, tp = level_vom_fill(s_richtung, sf, sl_pkt, tp_pkt, digits)
    return {"ok": True, "sl": sl, "tp": tp, "master_fill": mf, "master_liq": round(m_liq, 2), "master_stop": round(stop, 2), "master_stop_art": art,
            "master_tp": round(tp_m, 2), "master_tp_quelle": tp_q, "abstand_tp_pkt": round(d_tp, 2), "abstand_stop_pkt": round(d_stop, 2),
            "puffer_pct": pct, "liq_balance": liq.get("liq_balance"), "slave_sl_pkt": round(sl_pkt, 2), "slave_tp_pkt": round(tp_pkt, 2)}


def airbag_holen(lauf, s_richtung, s_fill, digits, warte_s=AIRBAG_WARTE_S):
    """Nach dem eigenen Fill: GET /polar/stand bis Master-Fill UND Master-Level da sind (höchstens warte_s; Master-Fill ohne Level nach
    Ablauf → TP aus dem Plan), dann airbag_level. Kein Fill / kein master.liq → {ok False, grund}, der Slave bleibt bei den Plan-Leveln."""
    ende, m, a = time.time() + float(warte_s), {}, None
    while True:
        a = railway(lauf, "GET", f"/polar/stand?lauf_id={lauf.lauf_id}", timeout=5)
        m = (a or {}).get("master") or {}
        if a and (a.get("master_zu_ms") or a.get("status") in ("fehler", "abbruch", "fertig")):
            return {"ok": False, "abbruch": True, "grund": "Master schon zu" if a.get("master_zu_ms") else f"Lauf {a.get('status')}"}
        if a and not m.get("liq"):
            return {"ok": False, "grund": "Railway liefert kein master.liq (alter Stand?)"}
        if (m.get("gefuellt") or {}).get("fill") and m.get("level") is not None:
            break
        if time.time() >= ende:
            break
        time.sleep(0.4)
    fill = (m.get("gefuellt") or {}).get("fill")
    if not fill:
        return {"ok": False, "grund": f"kein Master-Fill in {warte_s:g} s (Status {(a or {}).get('status')})"}
    lv = m.get("level") or {}
    return airbag_level(s_richtung, s_fill, fill, lv.get("tp"), lv.get("sl"), m.get("liq"), digits)


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


READER_BEREIT_ALTER_S = 5.0   # lokaler Reader (Port 8790): Positions-Stand höchstens so alt, sonst „nicht bereit"


def reader_bereit(d):
    """REIN RECHNEND (testbar, tools/selftest_polar_close.py) — READER-PFLICHT VOR DEM KLICK (21.10.2026, Prüfer S2: das Zu-Signal des Masters
    kommt vom lokalen Reader /positions, den der Server nicht sehen kann; Finn 13.10.: „liest das Tampermonkey-Script insta aus … an den zweiten
    Computer"). → (ok, grund). ok nur: Reader antwortet, an, nicht blind, positionen_ok, Stand ≤ READER_BEREIT_ALTER_S. Das Konto prüft die Wache
    selbst (reader_flach) — es darf hier noch das vorige sein (Rückfall Puls-Chrome-Tabelle bleibt)."""
    if not isinstance(d, dict):
        return False, "Reader (Port 8790) antwortet nicht — Tampermonkey-Reader im Puls-Chrome an?"
    if d.get("an") is False:
        return False, "Reader ist aus"
    if d.get("blind"):
        return False, "Reader ist blind (sieht die Positions-Tabelle nicht)"
    if not d.get("positionen_ok"):
        return False, "Reader liefert keine Positionen"
    try:
        alt = float(d.get("positionen_alter_s") if d.get("positionen_alter_s") is not None else d.get("alter_s") if d.get("alter_s") is not None else 99)
    except (TypeError, ValueError):
        alt = 99.0
    if alt > READER_BEREIT_ALTER_S:
        return False, f"Reader-Stand {alt:.1f} s alt (Grenze {READER_BEREIT_ALTER_S:.0f} s)"
    return True, ""


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


def order_zeile_arbeitet(zeile):
    """REIN RECHNEND (testbar): Order-Zeile noch aktiv? Mit Status-Spalte nur Working/Placed/Active/Arbeitet/Aktiv (der Reiter kann je
    nach Filter auch Filled/Cancelled früherer Läufe zeigen); ohne Status-Spalte zählt die Zeile."""
    sp = (zeile or {}).get("spalten") or {}
    st = str(sp.get("Status") or sp.get("Zustand") or "").strip().lower()
    if re.search(r"inactive|inaktiv", st):                # „Inactive" enthält „active" (Prüfung 21.10.2026)
        return False
    return not st or bool(re.search(r"working|placed|\bactive\b|arbeit|\baktiv\b|offen|pending", st))


def zeilen_preis(zeile):
    sp = (zeile or {}).get("spalten") or {}
    for k in ("Limit Price", "Limitpreis", "Stop Price", "Stopp-Preis", "Price", "Preis"):
        z = ob.cdp_zahl(sp.get(k))
        if z:
            return z
    return None


# ── SCHLIESSEN PER × (20.10.2026, Finn: „einfach auf das X, und die Position ist insta weg") ────────────────────────────────────
X_BEWEIS_S = 2.0              # nach dem ×-Klick muss die Position in ≤ 2 s lesend weg sein, sonst Rückfall auf den alten Weg
X_TAKT_S = 0.05               # Lesetakt des Beweises (Slave: API, Master: Reader)
SLAVE_WACHE_TAKT_S = 0.1      # Slave-Wache: eigene Position alle 100 ms lesen (Finn: 1–2 s bis der andere zu ist)
PROFIT_X_RAND_PX = 14         # MT5-Toolbox „Trade": das × sitzt ~14 px links vom rechten Rand der Profit-Spalte (Finn-Zoom 20.10.2026 „115.38 ×")
ZELLE_X_RAND_PX = 10          # … bzw. ~10 px links vom rechten Rand der PROFIT-ZELLE der eigenen Zeile (UIA, Master-Entscheid 20.10.2026 03:3x)
RX_X_TOOLTIP = re.compile(r"schlie(?:ß|ss)|close", re.I)
RX_CLOSE_TEXT = re.compile(r"position schlie(?:ß|ss)en|close position|schlie(?:ß|ss)en|\bclose\b", re.I)
RX_NICHT_CLOSE = re.compile(r"close all|alle schlie|reverse|umkehr|protect|settings|einstell|cancel|storn|order", re.I)
RX_LEVEL_SPALTE = re.compile(r"^\s*(s\s*/\s*l|t\s*/\s*p|sl|tp|stop|take)\b", re.I)


def profit_x_wahl(zeile_y, rechts, spalten=None, rand=PROFIT_X_RAND_PX):
    """REIN RECHNEND (testbar): Punkt des Schließen-× in der Positionszeile des MT5-Handel-Reiters. Das × steht GANZ RECHTS in der
    Profit-Spalte (Finns Screenshot 20.10.2026); die × neben S/L und T/P in derselben Zeile löschen nur die Level und sind tabu.
    spalten = [{name, left, right}] (Spaltenköpfe, wenn lesbar) → Spalte Profit/Gewinn, x = right − rand, und sie muss rechts von jeder
    S/L-/T/P-Spalte liegen; ohne Spaltenliste gilt der rechte Rand der Liste (Profit ist die letzte Spalte). -> (x, y, beweis) | None"""
    try:
        y, r = int(round(float(zeile_y))), int(round(float(rechts)))
    except (TypeError, ValueError):
        return None
    if spalten:
        profit = [c for c in spalten if isinstance(c, dict) and re.search(r"profit|gewinn", str(c.get("name") or ""), re.I)]
        level = [c for c in spalten if isinstance(c, dict) and RX_LEVEL_SPALTE.search(str(c.get("name") or ""))]
        if len(profit) != 1:
            return None
        pr = profit[0]
        try:
            x = int(round(float(pr["right"]))) - int(rand)
            if any(x <= float(c.get("right") or 0) + rand for c in level) or x <= float(pr.get("left") or 0):
                return None
        except (TypeError, ValueError, KeyError):
            return None
        return x, y, f"Spalte '{pr.get('name')}' (rechts {pr.get('right')}) − {rand} px"
    return r - int(rand), y, f"rechter Listenrand {r} − {rand} px (Profit = letzte Spalte)"


def profit_x_aus_zelle(zelle, rand=ZELLE_X_RAND_PX):
    """REIN RECHNEND (testbar, Master-Entscheid 20.10.2026 nach S1s Gegenprüfung): ×-Punkt aus dem Rechteck der PROFIT-ZELLE der eigenen
    Zeile [x, y, w, h] — rechter Zellenrand − rand, Mitte der Zeilenhöhe; nie „Fensterrand − 14 px" (Rahmen, Scrollbar, Leerraum rechts
    bei breitem Terminal lagen daneben). Zelle zu schmal/zu flach → None. -> (x, y) | None"""
    try:
        x, y, w, h = (float(v) for v in zelle)
    except (TypeError, ValueError):
        return None
    if w < rand + 6 or h < 6:
        return None
    return int(round(x + w - rand)), int(round(y + h / 2.0))


def x_klick_erlaubt(zelle, tooltip, einzig, bild=None):
    """REIN RECHNEND (testbar): der Slave klickt das × NUR mit Beweis — Profit-Zelle per UIA gelesen (Punkt liegt in der Zelle), Tooltip
    unter der geparkten Maus sagt Schließen/Close UND genau eine (die eigene) Position ist offen. Fehlt eines → sofort der bewährte
    Rechtsklick-Weg, kein ×-Klick ins Leere (Master-Entscheid 20.10.2026). -> bool
    Seit 21.10.2026 zweiter Beweis-Weg für Builds ohne UIA-Zellen: bild = slave_x_bild mit genau einem × am Listenrand in der
    Ticket-Zeile. Dort ist ein fremder Tooltip ein Gegenbeweis; ein fehlender nur mit BILD_TOOLTIP_PFLICHT."""
    if not einzig:
        return False
    tip = str(tooltip or "").strip()
    if zelle is not None and profit_x_aus_zelle(zelle) is not None:
        return bool(RX_X_TOOLTIP.search(tip))
    if isinstance(bild, dict) and bild.get("punkt") and bild.get("n_x") == 1 and not bild.get("ohne_zeile"):
        return bool(RX_X_TOOLTIP.search(tip)) if tip else not BILD_TOOLTIP_PFLICHT
    return False


def uia_profit_zelle(zellen, zeile_rect):
    """REIN RECHNEND (testbar): aus UIA-Zellen [{text, rect}] derselben Zeile (gleiche Höhe ± 3 px wie zeile_rect) die PROFIT-Zelle =
    die am weitesten rechts liegende; Zellen außerhalb des Zeilenbands zählen nicht. -> Zelle | None"""
    try:
        zy, zh = float(zeile_rect[1]), float(zeile_rect[3])
    except (TypeError, ValueError, IndexError):
        return None
    im_band = []
    for c in zellen or ():
        r = c.get("rect") if isinstance(c, dict) else None
        try:
            cy, ch = float(r[1]), float(r[3])
        except (TypeError, ValueError, IndexError):
            continue
        if abs(cy - zy) <= 3 and abs(ch - zh) <= 3 and float(r[2]) >= 16:
            im_band.append(c)
    if not im_band:
        return None
    return max(im_band, key=lambda c: float(c["rect"][0]) + float(c["rect"][2]))


# ── ×-BEWEIS PER BILD (21.10.2026, erster echter Lauf 8870f1de: „Profit-Zelle per UIA nicht lesbar") ──────────────────────────────────
# Ursache: Die Handel-Liste der MT5-Toolbox ist ein selbst gezeichnetes Gitter OHNE UIA-Zellen. Das ist derselbe Befund wie bei
# order_bot._reihen_scan vom 18.08.2026. Auf diesen Builds kommt die UIA-Zelle nie, das × blieb unbewiesen, der Slave parkte nur auf
# der Zeile. Jetzt sieht der Bot das × selbst: Listenfenster per Win32 (WindowFromPoint auf der Ticket-Zeile), rechter Streifen per
# BitBlt, darin das ×-Zeichen als Pixelform (zwei Diagonalen, Mitte gekreuzt, Kantenmitten leer). Beweis = GENAU EIN × am rechten
# Listenrand (Profit = letzte Spalte, die × neben S/L und T/P liegen weiter links), in der Zeile des Ticket-Ankers, und genau eine
# offene Position per API. Liest UIA die Zelle doch, gilt weiter der Zellen-Weg.
BILD_TINTE = 60               # Farbabstand |ΔR|+|ΔG|+|ΔB| zum Hintergrund der Pixelzeile, ab dem ein Pixel „Tinte" ist
BILD_STREIFEN_PX = 160        # rechter Streifen der Handel-Liste, in dem das Schließen-× gesucht wird
BILD_RAND_MAX_PX = 40         # das × endet ≤ 40 px vor dem Listenrand (Finn-Zoom 20.10.2026: ~14 px, dazu Platz für eine Scrollleiste)
BILD_ZEILE_TOL_PX = 14        # × muss in der Zeile des Ticket-Ankers liegen (± halbe Zeile plus Rand)
# Tooltip beim Bild-Weg: Sagt ein Tooltip unter der Maus etwas anderes als Schließen/Close, ist das ein Gegenbeweis und es gibt keinen
# Klick. Ob MT5 auf dem × überhaupt einen Tooltip zeigt, ist offen (Finn-Screenshot). Ohne Tooltip reicht der Bild-Beweis oben.
BILD_TOOLTIP_PFLICHT = False


def _rgb_abstand(a, b):
    return abs((a >> 16) - (b >> 16)) + abs(((a >> 8) & 255) - ((b >> 8) & 255)) + abs((a & 255) - (b & 255))


def tinte_maske(pix, schwelle=BILD_TINTE):
    """REIN RECHNEND (testbar): pix = Zeilen von 0xRRGGBB → Zeilen von bool. Hintergrund je Pixelzeile = ihre häufigste Farbe. Damit
    zählt eine markierte (blau hinterlegte) Positionszeile genauso wie eine weiße, und Gitterlinien über die volle Breite sind keine Tinte."""
    out = []
    for zeile in pix or ():
        if not zeile:
            out.append([])
            continue
        zahl = {}
        for p in zeile:
            zahl[p] = zahl.get(p, 0) + 1
        hg = max(zahl, key=zahl.get)
        out.append([_rgb_abstand(p, hg) > schwelle for p in zeile])
    return out


def ist_x_glyphe(punkte, x0, y0, b, h):
    """REIN RECHNEND (testbar): ist die Tinte-Komponente (Menge von (x, y), Rahmen x0/y0/b/h) ein ×? Quadratisch 5–16 px, beide
    Diagonalen ≥ 85 % getroffen (±1 px für Kantenglättung), Mitte gekreuzt, die vier Kantenmitten leer. Das unterscheidet das × von
    Ziffern (0, 8), Kästchen, Plus und Text."""
    if not (5 <= b <= 16 and 5 <= h <= 16 and abs(b - h) <= 2):
        return False
    n = max(b, h)
    if not (1.6 * n <= len(punkte) <= 5 * n):
        return False
    s = punkte if isinstance(punkte, set) else set(punkte)

    def nahe(x, y):
        return any((x + dx, y + dy) in s for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    ta = tb = 0
    for i in range(b):
        t = i / float(b - 1)
        ta += nahe(x0 + i, int(round(y0 + t * (h - 1))))
        tb += nahe(x0 + i, int(round(y0 + (1 - t) * (h - 1))))
    if ta < 0.85 * b or tb < 0.85 * b:
        return False
    cx, cy = int(round(x0 + (b - 1) / 2.0)), int(round(y0 + (h - 1) / 2.0))
    if not nahe(cx, cy):
        return False
    return not any(p in s for p in ((x0, cy), (x0 + b - 1, cy), (cx, y0), (cx, y0 + h - 1)))


def x_glyphen(maske):
    """REIN RECHNEND (testbar): zusammenhängende Tinte (8er-Nachbarschaft) → alle ×-Zeichen [{x, y, b, h, cx, cy}] in Masken-Koordinaten."""
    hoehe = len(maske or ())
    gesehen, out = set(), []
    for y in range(hoehe):
        for x, ink in enumerate(maske[y]):
            if not ink or (x, y) in gesehen:
                continue
            komp, stapel = set(), [(x, y)]
            gesehen.add((x, y))
            while stapel:
                px, py = stapel.pop()
                komp.add((px, py))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = px + dx, py + dy
                        if 0 <= ny < hoehe and 0 <= nx < len(maske[ny]) and maske[ny][nx] and (nx, ny) not in gesehen:
                            gesehen.add((nx, ny))
                            stapel.append((nx, ny))
            if len(komp) > 400:
                continue
            xs, ys = [p[0] for p in komp], [p[1] for p in komp]
            x0, y0, b, h = min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if ist_x_glyphe(komp, x0, y0, b, h):
                out.append({"x": x0, "y": y0, "b": b, "h": h, "cx": x0 + b // 2, "cy": y0 + h // 2})
    return out


def schliess_x_wahl(glyphen, breite, zeile_y=None, rand_max=BILD_RAND_MAX_PX, tol=BILD_ZEILE_TOL_PX):
    """REIN RECHNEND (testbar): das Schließen-× aus den ×-Zeichen des rechten Listenstreifens. Zählt nur, was ≤ rand_max px vor dem
    rechten Rand endet; je Zeile das rechteste. GENAU EINE Zeile mit × in der ganzen Liste (eine Position, keine Order), sonst kein
    Beweis. Mit zeile_y (Ticket-Anker im Streifen) muss das × in dieser Zeile liegen. -> (glyphe | None, zeilen_mit_x, grund)"""
    rechts = [g for g in glyphen or () if g["x"] + g["b"] >= breite - rand_max]
    zeilen = []
    for g in sorted(rechts, key=lambda g: g["cy"]):
        if zeilen and abs(g["cy"] - zeilen[-1]["cy"]) < 6:
            if g["x"] > zeilen[-1]["x"]:
                zeilen[-1] = g
        else:
            zeilen.append(g)
    if not zeilen:
        return None, 0, f"kein × am rechten Listenrand ({len(glyphen or ())} ×-Zeichen im Streifen)"
    if len(zeilen) > 1:
        return None, len(zeilen), f"{len(zeilen)} Zeilen mit × am Rand — nicht eindeutig (weitere Position/Order?)"
    g = zeilen[0]
    if zeile_y is not None and abs(g["cy"] - float(zeile_y)) > tol:
        return None, 1, f"× liegt {int(round(g['cy'] - float(zeile_y)))} px neben der Ticket-Zeile"
    return g, 1, "genau ein × am rechten Listenrand" + (" in der Ticket-Zeile" if zeile_y is not None else "")


def maske_ascii(maske, x0, y0, b, h):
    """Ausschnitt der Tinte als Text fürs Log (# = Tinte): zeigt ohne Screenshot, was der Bot am Listenrand gesehen hat."""
    zeilen = []
    for y in range(max(0, y0), min(len(maske or ()), y0 + h)):
        z = maske[y]
        zeilen.append("".join("#" if 0 <= x < len(z) and z[x] else "." for x in range(max(0, x0), x0 + b)))
    return zeilen


def chart_x_wahl(kandidaten):
    """REIN RECHNEND (testbar): GENAU EIN Schließen-× der Positions-Linie im TradingView-Chart aus den gelesenen Kandidaten
    [{rect, text, aria, title, dn, im_chart, in_tabelle}]. Zählt nur, was im Chart liegt (nicht Positions-Tabelle/Order-Panel) und
    als Schließen beschriftet ist (aria/title/Tooltip „Position Schließen"/„Close position" oder ein ×/✕ mit Close-Tooltip) — nie
    Reverse/Protect/Close all. -> Kandidat | None"""
    gut = []
    for k in kandidaten or ():
        if not isinstance(k, dict) or not k.get("im_chart") or k.get("in_tabelle"):
            continue
        r = k.get("rect")
        if not (isinstance(r, (list, tuple)) and len(r) == 4 and float(r[2]) >= 3 and float(r[3]) >= 3):
            continue
        lab = " ".join(str(k.get(f) or "") for f in ("aria", "title", "tooltip", "dn", "text"))
        sicht = " ".join(str(k.get(f) or "") for f in ("aria", "title", "tooltip", "text"))
        kreuz = str(k.get("text") or "").strip() in ("×", "✕", "x", "X", "✖")
        if RX_NICHT_CLOSE.search(sicht):
            continue
        if RX_CLOSE_TEXT.search(lab) or (kreuz and RX_CLOSE_TEXT.search(" ".join(str(k.get(f) or "") for f in ("aria", "title", "tooltip")))):
            gut.append(k)
    einzeln = {}
    for k in gut:
        einzeln.setdefault(tuple(int(round(float(v))) for v in k["rect"]), k)
    return list(einzeln.values())[0] if len(einzeln) == 1 else None


def position_zu_bewiesen(st, ticket):
    """REIN RECHNEND (testbar, Prüfung 21.10.2026): „zu" NUR aus einer gelungenen Lesung ohne das Ticket. None (API-Fehler) = unbekannt = nicht zu."""
    if not isinstance(st, dict) or not isinstance(st.get("positionen"), list):
        return False
    return not any(isinstance(p, dict) and p.get("ticket") == ticket for p in st["positionen"])


RX_MODAL_CLOSE = re.compile(r"^(close position|position schlie(?:ß|ss)en)$", re.I)
RX_MODAL_SEITE = re.compile(r"\b(long|short)\s+([\d.,]+)", re.I)


def close_modal_wahl(modals, root, richtung, menge):
    """REIN RECHNEND (testbar, Finn 21.10.2026): „Close position"-Rückfrage nach dem ×-Klick → (knopf | None, grund). Gedrückt wird nur,
    wenn GENAU EIN solches Modal offen ist, darin genau das Symbol (Wurzel), die Richtung (Long = buy, Short = sell) und die Menge der
    eigenen Position stehen und es genau EINEN Knopf „Close position" gibt. „Cancel" nie. grund: kein_modal | passt | <Klartext>."""
    # Rückfrage = Kasten mit „Cancel"-Knopf daneben; ein „Close position" in der Positions-Tabelle ist kein Modal und zählt nicht mit
    ms = [m for m in (modals or ()) if isinstance(m, dict)
          and any(re.match(r"^(cancel|abbrechen)$", str(k.get("text") or "").strip(), re.I) for k in (m.get("knoepfe") or ()) if isinstance(k, dict))]
    if not ms:
        return None, "kein_modal"
    if len(ms) > 1:
        return None, f"{len(ms)} Close-Modals offen — nicht eindeutig"
    m = ms[0]
    text = str(m.get("text") or "")
    roots = {ob.tv_symbol_root(t) for t in re.findall(r"[A-Z0-9_]+:[A-Z0-9!]+", text.upper())}
    if roots != {str(root or "").upper()}:
        return None, f"Modal nennt {sorted(roots) or 'kein Symbol'} statt {root}"
    sm = RX_MODAL_SEITE.search(text)
    if not sm:
        return None, "Modal ohne Long/Short + Menge"
    seite = "buy" if sm.group(1).lower() == "long" else "sell"
    if seite != str(richtung).lower():
        return None, f"Modal {sm.group(1)} statt {'Long' if str(richtung).lower() == 'buy' else 'Short'}"
    try:
        n = float(sm.group(2).replace(",", ""))
    except ValueError:
        return None, f"Menge '{sm.group(2)}' unlesbar"
    if abs(n - float(menge)) > 0.01:
        return None, f"Modal-Menge {n:g} statt {float(menge):g}"
    kn = [k for k in (m.get("knoepfe") or ()) if isinstance(k, dict) and RX_MODAL_CLOSE.match(str(k.get("text") or "").strip())]
    if len(kn) != 1 or not (isinstance(kn[0].get("rect"), (list, tuple)) and len(kn[0]["rect"]) == 4):
        return None, f"{len(kn)} Knöpfe „Close position\" im Modal"
    return kn[0], "passt"


ZU_ZWEITE_LESUNG_S = 0.15     # „zu" erst nach der zweiten Lesung ohne Ticket, ≥ 150 ms später


def zu_doppelt(lesen, st, ticket, warte_s=ZU_ZWEITE_LESUNG_S, schlaf=time.sleep):
    """REIN RECHNEND mit eingereichter Lesung (testbar, Prüfung 21.10.2026): order_bot._api_lesen_einmal macht aus positions_get() == None
    (Fehler) eine LEERE Liste — eine scheinbar gelungene Lesung ohne Ticket. Ein Aussetzer in der Wache meldete so „zu", der Master schloss
    per ×, und die Slave-Position blieb offen und unbewacht. Darum: „zu" nur, wenn diese UND eine zweite Lesung ≥ warte_s später das
    Ticket nicht zeigen (position_zu_bewiesen). -> bool"""
    if not position_zu_bewiesen(st, ticket):
        return False
    schlaf(float(warte_s))
    return position_zu_bewiesen(lesen(), ticket)


def schliess_urteil(geklickt, weg_nach_s, dialog_knopf=False, limit_s=X_BEWEIS_S):
    """REIN RECHNEND (testbar): nach dem ×-Klick → 'zu' (Position in ≤ limit s weg), 'dialog' (Bestätigungsdialog mit eindeutigem
    Knopf — Ein-Klick-Handel aus, Knopf drücken), 'rueckfall' (nicht geklickt oder nach limit s noch offen → alter Weg)."""
    if not geklickt:
        return "rueckfall"
    if weg_nach_s is not None and float(weg_nach_s) <= float(limit_s):
        return "zu"
    if dialog_knopf:
        return "dialog"
    return "rueckfall"


def zu_signal_urteil(antwort, seite):
    """REIN RECHNEND (testbar): Antwort von /polar/warte?auf=zu für DIESE Seite → 'zu' (die andere Seite ist zu, oder Lauf mit
    Fehler = nie einseitig offen bleiben), 'ende' (fertig/abbruch), None (weiter warten). Das eigene zu_ms weckt nie."""
    if not isinstance(antwort, dict):
        return None
    gegen = "slave" if seite == "master" else "master"
    if antwort.get(f"{gegen}_zu_ms") is not None:
        return "zu"
    st = str(antwort.get("status") or "")
    if st == "fehler":
        return "zu"
    if st in ("fertig", "abbruch"):
        return "ende"
    return None


def _tooltip_text(timeout=1.0):
    """Windows-Tooltip (tooltips_class32 / ToolTip) unter der geparkten Maus lesen — nur Beweis, nie Pflicht. -> Text | ''"""
    try:
        from pywinauto import Desktop
    except Exception:
        return ""
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            for t in Desktop(backend="uia").windows():
                try:
                    if t.element_info.class_name == "tooltips_class32" or t.element_info.control_type == "ToolTip":
                        txt = str(t.window_text() or "").strip()
                        if txt:
                            return txt[:120]
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.1)
    return ""


def _warte_signal(lauf, seite, signal, stop):
    """Hintergrund: /polar/warte?auf=zu halten, bis die ANDERE Seite zu ist (zu_signal_urteil). signal = {da, ende, status, antwort}."""
    while not stop.is_set() and not signal["da"] and not signal["ende"]:
        a = railway(lauf, "GET", f"/polar/warte?lauf_id={lauf.lauf_id}&seite={seite}&auf=zu&max_s=20", timeout=30)
        if not a:
            time.sleep(0.3)
            continue
        signal["status"] = a.get("status")
        u = zu_signal_urteil(a, seite)
        if u == "zu":
            signal["da"], signal["antwort"], signal["signal_ms"] = True, a, jetzt_ms()
        elif u == "ende":
            signal["ende"] = True


# Schließen-× der Positions-Linie im TradingView-Chart (Finns Screenshot 20.10.2026: Umkehr · TP · SL · Menge · P&L · ×, Tooltip
# „Position Schließen") — nur lesen: Kandidaten mit Beschriftung, Tooltip-Text und Lage (im Chart / in einer Tabelle).
CHART_X_JS = r"""(function () {
  function sb(e) { try { var r = e.getBoundingClientRect(); if (r.width < 3 || r.height < 3 || r.bottom < 0 || r.top > innerHeight) return false;
    var s = getComputedStyle(e); return s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; } catch (_) { return false; } }
  function R(e) { var r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }
  function T(e) { return String((e && e.textContent) || '').replace(/\s+/g, ' ').trim(); }
  function A(e, n) { try { return e.getAttribute(n) || ''; } catch (_) { return ''; } }
  var rx = /position schlie|close position|schlie(ß|ss)en|^close$/i, out = [];
  var tips = Array.prototype.slice.call(document.querySelectorAll('[role="tooltip"],[class*="tooltip"]')).filter(sb).map(T).filter(Boolean);
  var alle = Array.prototype.slice.call(document.querySelectorAll('button,[role="button"],[data-name],[class*="close"],[class*="Close"],span,div'));
  for (var i = 0; i < alle.length && out.length < 40; i++) {
    var e = alle[i]; if (!sb(e)) continue;
    var txt = T(e); if (txt.length > 40) continue;
    var lab = [A(e, 'aria-label'), A(e, 'title'), A(e, 'data-tooltip'), A(e, 'data-name'), txt].join(' ');
    var kreuz = /^[×✕✖xX]$/.test(txt);
    if (!rx.test(lab) && !kreuz) continue;
    var r = R(e); if (r[2] > 60 || r[3] > 60) continue;
    var imChart = !!e.closest('.chart-container,.chart-markup-table,[class*="chart-widget"],[class*="chart-gui"],[data-name="pane"]');
    var inTab = !!e.closest('table,[role="table"],[role="grid"],[data-name="order-panel"],[class*="bottom-widgetbar"],[class*="widgetbar"]');
    out.push({ rect: r, text: txt.slice(0, 40), aria: A(e, 'aria-label').slice(0, 60), title: A(e, 'title').slice(0, 60),
               tooltip: A(e, 'data-tooltip').slice(0, 60), dn: A(e, 'data-name').slice(0, 60), im_chart: imChart, in_tabelle: inTab });
  }
  return { kandidaten: out, tooltips: tips.slice(0, 5) };
})()"""

# „Close position"-Rückfrage nach dem ×-Klick am Master (Finn 21.10.2026: „… dann muss man einfach noch aufs X drücken und dann noch ganz
# kurz auf Close Position. Aber das kommt nur manchmal"): Screenshot = Modal mit Titel „Close position", Zeile „CME_MINI:MNQZ2026 · Long 1
# @ 29,983.00", Knöpfe „Cancel" und „Close position". Nur lesen: je Modal Titel, Text und alle Knöpfe (Text, Rechteck, data-name).
CLOSE_MODAL_JS = r"""(function () {
  function sb(e) { try { var r = e.getBoundingClientRect(); if (r.width < 3 || r.height < 3 || r.bottom < 0 || r.top > innerHeight) return false;
    var s = getComputedStyle(e); return s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; } catch (_) { return false; } }
  function R(e) { var r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }
  function T(e) { return String((e && e.textContent) || '').replace(/\s+/g, ' ').trim(); }
  var rx = /^(close position|position schlie(ß|ss)en)$/i, boxen = [], out = [];
  Array.prototype.slice.call(document.querySelectorAll('button,[role="button"]')).filter(function (b) { return sb(b) && rx.test(T(b)); }).forEach(function (b) {
    var box = b.closest('[role="dialog"],[data-dialog-name]'), p = b.parentElement;
    for (var i = 0; !box && p && i < 8; i++, p = p.parentElement) {
      if (p.querySelectorAll('button,[role="button"]').length >= 2 && T(p).length > T(b).length + 8) box = p; }
    box = box || b;
    if (boxen.indexOf(box) < 0) boxen.push(box);
  });
  boxen.forEach(function (box) {
    var kn = Array.prototype.slice.call(box.querySelectorAll('button,[role="button"]')).filter(sb).map(function (k) {
      return { text: T(k).slice(0, 40), rect: R(k), dn: k.getAttribute('data-name') || '' }; });
    var h = box.querySelector('h1,h2,h3,[class*="title"],[data-name*="title"]');
    out.push({ titel: T(h).slice(0, 60), text: T(box).slice(0, 240), knoepfe: kn.slice(0, 8), rect: R(box) });
  });
  return out;
})()"""

TOOLTIP_JS = r"""(function () {
  function T(e) { return String((e && e.textContent) || '').replace(/\s+/g, ' ').trim(); }
  return Array.prototype.slice.call(document.querySelectorAll('[role="tooltip"],[class*="tooltip"]')).filter(function (e) {
    try { var r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; } catch (_) { return false; } }).map(T).filter(Boolean).slice(0, 5);
})()"""


def uia_zeile_wahl(zeilen, symbol, ticket=None):
    """REIN RECHNEND (testbar, Maus-Test ×): Positionszeile aus UIA-Elementen [{text, rect}] — mit Ticket GENAU die Zeile, die die
    Ticket-Nummer trägt; ohne Ticket die erste Zeile mit dem Symbol. Mehrdeutig (zwei Ticket-Treffer) → None. -> Zeile | None"""
    z = [x for x in (zeilen or ()) if isinstance(x, dict) and isinstance(x.get("rect"), (list, tuple)) and len(x["rect"]) == 4]
    if ticket:
        t = [x for x in z if re.search(r"(?<!\d)" + re.escape(str(ticket)) + r"(?!\d)", str(x.get("text") or ""))]
        return t[0] if len(t) == 1 else None
    sym = str(symbol or "").strip().lower()
    for x in z:
        if sym and sym in str(x.get("text") or "").lower():
            return x
    return None


def x_abstand_rechts(punkt, rechts):
    """REIN RECHNEND (testbar): Abstand des ×-Punkts zum rechten Rand in px (Beweis im Log; negativ = außerhalb)."""
    try:
        return int(round(float(rechts) - float(punkt[0])))
    except (TypeError, ValueError, IndexError):
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


def master_level_lesen(lauf, s, root, plan):
    """NUR LESEN (21.10.2026, Lauf 3a1cc58e: level {ok:false, tp:null, sl:null}, obwohl in TradingView Sell limit 30.003,50 und Sell stop
    29.954,00 standen — die Meldungen hatten die Level diesmal nicht): Reiter Orders → je Bracket (TP = Limit, SL = Stop der Gegenseite)
    GENAU EINE Zeile → Preis. Nichts wird geändert; danach zurück auf Positionen. -> {tp, sl, teile}"""
    erg = {"tp": None, "sl": None, "teile": []}
    try:
        if not ob._cdp_reiter(s, "orders", lauf.trail):
            erg["teile"].append("Reiter Orders nicht aktiv")
            return erg
        ob._warte(0.4, 0.2)
        gegen = "sell" if plan["richtung"] == "buy" else "buy"
        zeilen = [z for z in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(z, dict) and z.get("sichtbar") and ob.tv_symbol_root(str(z.get("symbol") or "")) == root
                  and order_zeile_arbeitet(z)]
        for art in ("tp", "sl"):
            treffer = [z for z in zeilen if order_zeile_passt(z, gegen, art)]
            if len(treffer) == 1 and zeilen_preis(treffer[0]) is not None:
                erg[art] = float(zeilen_preis(treffer[0]))
            erg["teile"].append(f"{art.upper()} {erg[art] if erg[art] is not None else '—'} ({len(treffer)} Zeile(n))")
    except Exception as e:
        erg["teile"].append(f"Lesen: {type(e).__name__}")
    finally:
        # Rückkehr auf Positionen BEWEISEN (Prüfung 21.10.2026): bleibt Orders aktiv, liefert stand() positionen [] und der CDP-Zweitblick
        # der Wache hielte den Master für flach. master_wache lässt CDP-Flach ohnehin nur bei sichtbarem Positions-Reiter zu (positions_sichtbar)
        try:
            zurueck = bool(ob._cdp_reiter(s, "positions", lauf.trail))
        except Exception as e:
            zurueck = False
            erg["teile"].append(f"Rückkehr: {type(e).__name__}")
        erg["teile"].append("zurück auf Positionen ✓" if zurueck else "Rückkehr auf Positionen NICHT bewiesen")
    lauf.log("Polar-Level Master aus dem Orders-Reiter (nur lesen): " + " · ".join(erg["teile"]))
    return erg


def positions_sichtbar(s):
    """Ist der Reiter Positionen des Account-Managers nachweislich aktiv (aria-selected)? Nur lesen, Fehler = nein. Ohne diesen Beweis ist
    eine leere Positions-Liste kein „flach" — Orders-Reiter aktiv (Level-Lesung, Hand-Klick) zeigt ebenfalls keine Position."""
    try:
        return bool(ob.cdp_reiter_aktiv(s.lese_js(ob.CDP_REITER_JS) or [], "positions"))
    except Exception:
        return False


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


def master_x_parken(lauf, s, opts, root, plan):
    """Nach Fill + Level: Maus auf dem Schließen-× parken (20.10.2026). Zuerst das × der Positions-Linie IM CHART (Finns Screenshot:
    Label Umkehr · TP · SL · Menge · P&L · ×, Tooltip „Position Schließen"), Beweis = Tooltip nach dem Hover; liegt die Linie nicht im DOM
    (Canvas), der Close-Knopf der Positions-Tabelle (k3_close_knopf, tvclose-Weg) als Park-Platz. -> {art, rect, beweis} | None"""
    park = None
    try:
        d = s.lese_js(CHART_X_JS) or {}
        kand = d.get("kandidaten") or []
        x = chart_x_wahl(kand)
        if x is not None and s.hin(x.get("rect"), "Chart-× der Positions-Linie"):
            ob._warte(0.4, 0.2)
            tips = [t for t in (s.lese_js(TOOLTIP_JS) or []) if isinstance(t, str)]
            tip = next((t for t in tips if RX_CLOSE_TEXT.search(t)), "")
            park = {"art": "chart", "rect": list(x["rect"]), "beweis": f"Tooltip '{tip}'" if tip else f"DOM {x.get('aria') or x.get('title') or x.get('text')}", "tooltip": tip}
            lauf.log(f"Polar: Maus parkt auf dem Chart-× @{x['rect']} — Beweis {park['beweis']}")
        else:
            lauf.log(f"Polar: Chart-× nicht eindeutig im DOM ({len(kand)} Kandidaten, Tooltips {d.get('tooltips')}) — Park-Platz Positions-Tabelle")
    except Exception as e:
        lauf.log(f"Polar: Chart-× lesen ({type(e).__name__}) — Park-Platz Positions-Tabelle")
    if park is None:
        try:
            ob._cdp_reiter(s, "positions", lauf.trail)
            for runde in range(2):
                zeilen = [z for z in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(z, dict) and z.get("sichtbar")
                          and ob.tv_symbol_root(str(z.get("symbol") or "")) == root
                          and not any(k in (z.get("spalten") or {}) for k in ("Status", "Order ID", "Order-ID"))]
                if len(zeilen) != 1:
                    lauf.log(f"Polar: {len(zeilen)} {root}-Zeilen in der Positions-Tabelle — kein Park-Platz")
                    break
                kn, _n = ob.k3_close_knopf(zeilen[0])
                if kn and s.hin(ob.cdp_rect(kn), f"Close-Knopf der {root}-Zeile"):
                    park = {"art": "tabelle", "rect": list(ob.cdp_rect(kn)), "beweis": f"Knopf '{ob.k3_label(kn)}'", "tooltip": ""}
                    lauf.log(f"Polar: Maus parkt auf dem Close-Knopf der Positions-Tabelle — {park['beweis']}")
                    break
                if runde == 0 and ob.cdp_rect(zeilen[0].get("zeile")):
                    s.hin(zeilen[0].get("zeile"), f"{root}-Zeile (Knöpfe einblenden)")
                    ob._warte(0.6, 0.3)
        except Exception as e:
            lauf.log(f"Polar: Park-Platz Tabelle ({type(e).__name__})")
    melden(lauf, "geparkt", {"art": (park or {}).get("art"), "beweis": (park or {}).get("beweis"), "rect": (park or {}).get("rect")})
    lauf.phase("geparkt_x", park=park)
    return park


def master_vor_klick(lauf, s, opts, ext, root, plan, park, gesehen):
    """VOR-KLICK-LESUNG (Prüfer S2 über den Master, 20.10.2026): unmittelbar vor dem ×-Klick lesend prüfen, dass die eigene Position noch
    offen ist und das geparkte × zu ihr gehört. Reader flach → 'schon_zu' (nicht klicken). Park-Platz Tabelle: die Zeile muss Wurzel,
    Richtung und Menge des Plans zeigen und der Close-Knopf noch dasselbe Rechteck haben, sonst neu suchen. Chart: das Chart-× muss noch
    an derselben Stelle (± 3 px) im DOM stehen, sonst neu suchen. -> (park | None, grund)"""
    if reader_flach(ob._tv_http("/positions", timeout=0.3), ext, root, gesehen) == "flach":
        return None, "schon_zu"
    if not park:
        return None, "kein_park"
    try:
        if park.get("art") == "chart":
            x = chart_x_wahl((s.lese_js(CHART_X_JS) or {}).get("kandidaten") or [])
            if x is None:
                return None, "chart_x_weg"
            if any(abs(float(a) - float(b)) > 3 for a, b in zip(x["rect"], park["rect"])):
                return dict(park, rect=list(x["rect"])), "chart_x_neu"
            return park, "ok"
        zeilen = [z for z in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(z, dict) and z.get("sichtbar")
                  and ob.tv_symbol_root(str(z.get("symbol") or "")) == root
                  and not any(k in (z.get("spalten") or {}) for k in ("Status", "Order ID", "Order-ID"))]
        if len(zeilen) != 1:
            return None, f"{len(zeilen)}_zeilen"
        z = zeilen[0]
        menge = ob.cdp_zahl(z.get("menge"))
        if str(z.get("seite") or "").lower() != str(plan["richtung"]).lower() or (menge is not None and abs(float(menge) - float(plan["menge"])) > 0.01):
            return None, "zeile_fremd"
        kn, _n = ob.k3_close_knopf(z)
        if not kn:
            return None, "knopf_weg"
        r = list(ob.cdp_rect(kn))
        return (park if r == list(park["rect"]) else dict(park, rect=r)), ("ok" if r == list(park["rect"]) else "knopf_neu")
    except Exception as e:
        return None, f"lesung_{type(e).__name__}"


def master_x_klicken(lauf, s, opts, ext, root, plan, park, gesehen):
    """Signal vom Slave: Vor-Klick-Lesung (< 50 ms Reader) → EIN Klick auf das geparkte × → Beweis Reader flach (50 ms) ≤ 2 s (Tabelle als
    zweiter Blick); Rückfrage-Dialog nur über [data-name=submit-button] mit Close/Schließen; sonst Rückfall Close-Knopf der Tabelle
    (tvclose-Regel). -> (zu_ms, quelle) | (None, grund)"""
    t0 = time.time()
    park, grund = master_vor_klick(lauf, s, opts, ext, root, plan, park, gesehen)
    lauf.log(f"Polar: Vor-Klick-Lesung {int((time.time() - t0) * 1000)} ms → {grund}")
    if grund == "schon_zu":
        lauf.phase("zu_bestaetigt", zu_quelle="schon_zu")
        return jetzt_ms(), "schon_zu"
    geklickt = bool(park) and bool(s.klick(park["rect"], f"Schließen-× ({park['art']})"))
    klick_ms = jetzt_ms()
    lauf.phase("x_geklickt", klick_ms=klick_ms, x_art=(park or {}).get("art"), x_ok=geklickt)
    lauf.log(f"Polar: × geklickt ({(park or {}).get('art')}, {int((time.time() - t0) * 1000)} ms nach dem Signal)" if geklickt else "Polar: × NICHT gedrückt (Maus/Fenster nicht bewiesen)")

    modal_fremd = [None]

    def flach_beweis(limit_s):
        # „Close position"-Rückfrage (Finn 21.10.2026: „kommt nur manchmal … ganz wichtig: es muss schnell gehen"): ab dem ERSTEN Takt
        # (~50 ms) mitlesen, nicht erst nach 0,6 s. Passt das Modal zur eigenen Position (close_modal_wahl) → EIN Klick auf „Close
        # position" mit Ziel-Beweis am Punkt (pruef); passt es nicht → nie klicken, Grund ins Log, der Rückfall bzw. „SOFORT schließen" folgt.
        ende, flach_seit, dialog_zu = time.time() + limit_s, None, False
        while time.time() < ende:
            u = reader_flach(ob._tv_http("/positions", timeout=0.5), ext, root, gesehen)
            if u == "flach":
                flach_seit = flach_seit or time.time()
                if time.time() - flach_seit >= 0.1:
                    return time.time() - t0, dialog_zu
            else:
                flach_seit = None
            if not dialog_zu:
                try:
                    kn, mg = close_modal_wahl(s.lese_js(CLOSE_MODAL_JS, timeout=1) or [], root, plan["richtung"], plan["menge"])
                    if kn is not None:
                        if s.klick(kn["rect"], "Close position (Rückfrage)",
                                   pruef={"rect": kn["rect"], "text": str(kn.get("text") or "").lower(), "aria": "", "tabu": r"cancel|abbrechen|reverse|umkehr"}):
                            dialog_zu = True
                            lauf.log(f"Polar: Rückfrage 'Close position' bestätigt {int((time.time() - t0) * 1000)} ms nach dem Signal")
                    elif mg != "kein_modal" and modal_fremd[0] != mg:
                        modal_fremd[0] = mg
                        lauf.log(f"Polar: Close-Modal NICHT bestätigt — {mg}")
                except Exception:
                    pass
            time.sleep(X_TAKT_S)
        return None, dialog_zu
    weg, dialog = (None, False)
    if geklickt:
        weg, dialog = flach_beweis(X_BEWEIS_S)
        if weg is None and dialog:
            weg, _d = flach_beweis(X_BEWEIS_S)        # Rückfrage bestätigt → noch einmal 2 s Beweis
    urteil = schliess_urteil(geklickt, weg)
    if urteil == "zu":
        zu_ms = jetzt_ms()
        lauf.log(f"Polar: Master flach {weg * 1000:.0f} ms nach dem Signal — × hat geschlossen")
        return zu_ms, f"x_{park['art']}"
    # RÜCKFALL: Close-Knopf der Positions-Tabelle (dieselbe Regel wie tvclose: genau eine Zeile, genau ein Knopf), dann Beweis
    lauf.log("Polar: × ohne Beweis — Rückfall Close-Knopf der Positions-Tabelle" + (f" (Close-Modal passte nicht: {modal_fremd[0]})" if modal_fremd[0] else ""))
    try:
        if not (park and park.get("art") == "tabelle"):
            ob._cdp_reiter(s, "positions", lauf.trail)
        zeilen = [z for z in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(z, dict) and z.get("sichtbar")
                  and ob.tv_symbol_root(str(z.get("symbol") or "")) == root]
        if not zeilen:
            weg2, _d = flach_beweis(1.5)
            if weg2 is not None:
                return jetzt_ms(), "x_spaet"
        if len(zeilen) == 1:
            s.hin(zeilen[0].get("zeile"), f"{root}-Zeile (Knöpfe einblenden)")
            ob._warte(0.5, 0.2)
            z2 = next((x for x in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(x, dict) and x.get("zeile") == zeilen[0].get("zeile")), zeilen[0])
            kn, _n = ob.k3_close_knopf(z2)
            if reader_flach(ob._tv_http("/positions", timeout=0.3), ext, root, gesehen) == "flach":   # Vor-Klick-Lesung auch hier (S1-Prüfung 20.10.2026)
                lauf.log("Polar: Rückfall — Reader meldet inzwischen flach, kein Klick")
                return jetzt_ms(), "x_spaet"
            if kn and s.klick(ob.cdp_rect(kn), f"Close-Knopf der {root}-Zeile (Rückfall)"):
                weg2, _d = flach_beweis(6.0)
                if weg2 is not None:
                    lauf.log(f"Polar: Master flach über den Tabellen-Knopf ({weg2 * 1000:.0f} ms nach dem Signal)")
                    return jetzt_ms(), "rueckfall_tabelle"
    except Exception as e:
        lauf.log(f"Polar: Rückfall ({type(e).__name__})")
    return None, ("modal_fremd" if modal_fremd[0] else "nicht_zu")


def master_wache(lauf, s, opts, ext, root, plan, park=None):
    """Nach dem Fill: Reader (8790) alle 50 ms, Puls-Chrome-Tabelle alle 1 s als Rückfall. Flach mit Beweis → sofort 'zu' an Railway.
    Parallel (20.10.2026) /polar/warte?auf=zu: meldet der Slave zuerst zu → EIN Klick aufs geparkte × (master_x_klicken).
    -> (zu_ms, quelle) | (None, grund)"""
    gesehen = False
    naechst_cdp = time.time() + 1.0
    flach_seit = None
    ende_max = time.time() + 6 * 3600
    lauf.phase("wache", park=park)
    signal = {"da": False, "ende": False, "status": None, "antwort": None, "signal_ms": None}
    stop = threading.Event()
    threading.Thread(target=_warte_signal, args=(lauf, "master", signal, stop), daemon=True).start()
    try:
        while time.time() < ende_max:
            if signal["da"]:
                a = signal["antwort"] or {}
                lauf.log(f"Polar: Signal — Slave zu ({a.get('slave_zu_ms')}, Status {a.get('status')}) → Master schließt per ×")
                zu_ms, quelle = master_x_klicken(lauf, s, opts, ext, root, plan, park, gesehen)
                if zu_ms:
                    melden(lauf, "zu", {"quelle": quelle, "zu_ms": zu_ms, "signal_ms": signal["signal_ms"]})
                    lauf.phase("zu_bestaetigt", zu_ms=zu_ms, zu_quelle=quelle)
                    return zu_ms, quelle
                lauf.log("Polar: Master-Position nach Signal NICHT zu — SOFORT in TradingView schließen!")
                return None, quelle
            if signal["ende"]:
                return None, f"lauf_{signal['status']}"
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
                    lauf.phase("zu_bestaetigt", zu_ms=zu_ms, zu_quelle="reader")
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
                        # CDP-Flach nur bei NACHWEISLICH sichtbarem Positions-Reiter (Prüfung 21.10.2026): steht Orders vorn (Level-Lesung
                        # ohne Rückkehr, Hand-Klick), ist die Liste leer, ohne dass der Master flach ist → Reiter zurückholen, diese Runde nichts
                        vorn = positions_sichtbar(s)
                        if not vorn:
                            ok_r = ob._cdp_reiter(s, "positions", lauf.trail)
                            lauf.log(f"Wache CDP: Positions-Reiter nicht vorn — zurückgeholt {'✓' if ok_r else 'NICHT bewiesen'}, kein Flach aus dieser Runde")
                        st2 = None
                        if vorn:
                            ob._warte(0.3, 0.1)               # zwei Blicke: der nächste bestätigt
                            st2 = s.stand(opts)
                        if st2 is not None and positions_sichtbar(s) and ob.cdp_zeilen_menge(ob.k3_zeilen(st2.get("positionen"), root), plan["richtung"]) == 0:
                            zu_ms = jetzt_ms()
                            melden(lauf, "zu", {"quelle": "cdp", "zu_ms": zu_ms})
                            lauf.log("Polar: Master flach laut Puls-Chrome-Tabelle — 'zu' an Railway gemeldet")
                            lauf.phase("zu_bestaetigt", zu_ms=zu_ms, zu_quelle="cdp")
                            return zu_ms, "cdp"
                except Exception as e:
                    lauf.log(f"Wache CDP: {type(e).__name__}")
            time.sleep(0.05)
        return None, "zeitlimit"
    finally:
        stop.set()


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
        # READER-PFLICHT (21.10.2026): ohne lokalen Reader kein Zu-Signal → Abbruch VOR bereit/Feuer (melden abbruch, nichts gesendet)
        r_ok, r_grund = reader_bereit(ob._tv_http("/positions", timeout=2.0))
        lauf.log(f"Reader-Pflicht: {'ok' if r_ok else r_grund}")
        if not r_ok:
            raise RuntimeError(f"Reader: {r_grund}")
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
        # Level 1:1 WIE ORBIT (Finn 21.10.2026 ~04:15 Dubai nach dem ersten echten Lauf 8870f1de: „erst mal nichts ändern, einfach nur die
        # 1:1-Sache vom normalen Orbit nehmen, weil der auch immer perfekt ausliest"): die TP/SL-Klammer kommt aus dem Ticket ($-Werte, setzt
        # TradingView selbst vom Fill aus), Puls ändert danach nichts mehr und liest nur Fill + TP/SL aus den Meldungen (cdp_order_beweis).
        # Die eigene Nachkorrektur über Orders → Ändern (master_level_setzen) ist raus — im Lauf 8870f1de fand sie „0 passende Order-Zeilen",
        # geschützt hat trotzdem die Ticket-Klammer (TP +46,96 $). Funktion bleibt im Modul, wird nicht mehr aufgerufen.
        sl_pkt, tp_pkt = _zahl(cmd.get("sl_pkt")), _zahl(cmd.get("tp_pkt"))
        sl_s, tp_s = level_vom_fill(plan["richtung"], fill, sl_pkt, tp_pkt, 2, tick=0.25) if (fill and sl_pkt and tp_pkt) else (None, None)
        tp_t, sl_t = ob.cdp_zahl(b.get("tp")) if b.get("tp") is not None else None, ob.cdp_zahl(b.get("sl")) if b.get("sl") is not None else None
        quelle_l = "meldung"
        if tp_t is None or (sl_t is None and cmd.get("sl_usd")):
            # Meldungen ohne Level (Lauf 3a1cc58e) → Orders-Reiter nur lesen; der Slave rechnet seinen Airbag-SL aus genau diesem TP
            nl = master_level_lesen(lauf, s, root, plan)
            if tp_t is None and nl["tp"] is not None:
                tp_t, quelle_l = nl["tp"], "orders"
            if sl_t is None and nl["sl"] is not None:
                sl_t, quelle_l = nl["sl"], "orders"
        res["level"] = {"ok": tp_t is not None, "tp": tp_t, "sl": sl_t, "quelle": f"ticket (wie Orbit), gelesen aus {quelle_l}", "sl_soll": sl_s, "tp_soll": tp_s}
        melden(lauf, "level", res["level"])
        lauf.phase("level", level=res["level"])
        lauf.log(f"Level wie Orbit aus dem Ticket: TP {tp_t if tp_t is not None else '?'} / SL {sl_t if sl_t is not None else '?'} (Soll vom Fill {tp_s} / {sl_s})")
        # Maus aufs Schließen-× parken (20.10.2026), dann Wache: Master zu → sofort melden; Slave zu zuerst → × klicken
        park = master_x_parken(lauf, s, opts, root, plan)
        zu_ms, quelle = master_wache(lauf, s, opts, ext, root, plan, park)
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
    dlg = None   # F9-Dialog — bei jedem Abbruch vor dem Klick wieder zu (21.10.2026, s. except)
    try:
        # Ohne Instanz-Datei gar nicht erst öffnen (21.10.2026, erster Live-Lauf 407f8efa: leerer Pfad → Ordner C:\mt5-copier\ geöffnet,
        # FileNotFoundError ohne Hinweis) — benannter Abbruch vor jeder Maus-Bewegung, nichts gesendet
        if not str(cmd.get("config_file") or "").strip():
            raise RuntimeError("Auftrag ohne config_file (Instanz-Datei der MT5-Instanz) — PC-Tab zu alt? Tab neu laden")
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
        # Symbol über den WERT prüfen, nicht über window_text() — das liefert bei UIA nur die Beschriftung „Symbol:" (Lauf 2a854cb4,
        # 21.10.2026: NAS100 stand richtig im Feld, der Bot las „Symbol:" und brach ab; derselbe Fund wie order_bot._feld_lesen 18.08.2026).
        # Kandidaten: Wert der ComboBox, Wert ihres Edit-Kinds, Name als letzter Rest
        kand = [ob._feld_lesen(cb)]
        try:
            kand += [ob._feld_lesen(x) for x in cb.descendants(control_type="Edit")]
        except Exception:
            pass
        if not any(symbol.lower() in str(k or "").lower() for k in kand):
            raise RuntimeError(f"Symbol steht nicht im Dialog (gelesen: {' | '.join(str(k) for k in kand if k)[:120] or 'leer'})")
        fmap = ob._map_felder(dlg)
        vol_el = fmap.get("volumen") or fmap.get("vol") or fmap.get("volume")
        if vol_el is None or not ob._feld_tippen(vol_el, f"{vol:g}", "Volumen", lauf.trail, rahmen=dlg):
            raise RuntimeError("Volumen nicht sicher getippt")
        # grobe SL/TP schon im F9-Dialog (Schutz ab dem Fill, 2 Pkt weiter weg); exakt per Klick vom Fill danach.
        # PFLICHT seit 0.3.2 (Finn 21.10.2026 ~03:50 Dubai nach Lauf 2a854cb4: „Wir wollen ja auch Notfall Take Profit / Stop Loss immer
        # einstellen, auf jeden Fall"): vorher fiel der Weg bei fehlendem Kurs/Feld oder Tippfehler still auf 0/0 zurück und feuerte ohne
        # Schutz. Jetzt kein Notfall-Level = kein Druck (Abbruch vor der Feuerzeit, nichts gesendet).
        ref = lese.get("ref_ask") if kauf else lese.get("ref_bid")
        if not ref or fmap.get("sl") is None or fmap.get("tp") is None:
            raise RuntimeError("Notfall-SL/TP nicht setzbar (" + ("kein Kurs" if not ref else "SL-/TP-Feld im F9-Dialog nicht gefunden") + ") — kein Druck ohne Schutz")
        # Notfall bewusst 2 Pkt WEITER außen als der Plan (21.10.2026, fester Puffer 2,5 %): sl_pkt/tp_pkt tragen den Puffer schon (Railway),
        # das F9 steht aber vor dem Fill am Referenzkurs — der Abstand fängt den Kursweg bis zum Fill ab, und das exakte Ändern zieht immer
        # nach innen statt nach außen. Abschalten darf ihn nichts (Pflicht seit 0.3.2).
        sl_g, tp_g = level_vom_fill(richtung, ref, sl_pkt + 2.0, tp_pkt + 2.0, digits)
        if not (ob._feld_tippen(fmap["sl"], ob.fmt_preis(sl_g, digits), "F9-SL", lauf.trail, rahmen=dlg)
                and ob._feld_tippen(fmap["tp"], ob.fmt_preis(tp_g, digits), "F9-TP", lauf.trail, rahmen=dlg)):
            raise RuntimeError(f"Notfall-SL/TP nicht sicher getippt (SL {ob.fmt_preis(sl_g, digits)} / TP {ob.fmt_preis(tp_g, digits)}) — kein Druck ohne Schutz")
        lauf.log(f"Notfall-Level im F9: SL {ob.fmt_preis(sl_g, digits)} / TP {ob.fmt_preis(tp_g, digits)}")
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
        # AIRBAG (Finn 21.10.2026, s. airbag_level): exakte Level aus BEIDEN Fills + Liquidation des Masters. Ohne Master-Fill/Liq bleibt
        # es bei den Plan-Abständen vom eigenen Fill (bisheriger Weg); die Notfall-Level aus dem F9 schützen in jedem Fall bis dahin.
        ab = airbag_holen(lauf, richtung, fill, digits)
        if ab.get("abbruch"):
            # Master schon zu / Lauf mit Fehler während der Holphase (Prüfung 21.10.2026): kein Ändern-Dialog mehr — sofort in die Wache,
            # die parkt und schließt; bis dahin schützen die Notfall-Level aus dem F9
            sl, tp = sl_g, tp_g
            lauf.log(f"Airbag übersprungen ({ab.get('grund')}) — kein Ändern, sofort Wache/Schließen; Notfall SL {ob.fmt_preis(sl, digits)} / TP {ob.fmt_preis(tp, digits)}")
        elif ab.get("ok"):
            sl, tp = ab["sl"], ab["tp"]
            lauf.log(f"Airbag: Master-Fill {ab['master_fill']:g}, TP {ab['master_tp']:g} ({ab['master_tp_quelle']}), Stopp {ab['master_stop']:g} "
                     f"({ab['master_stop_art']}, Liq {ab['master_liq']:g}) → Slave SL {ob.fmt_preis(sl, digits)} (+{ab['slave_sl_pkt']:g} Pkt) / "
                     f"TP {ob.fmt_preis(tp, digits)} (−{ab['slave_tp_pkt']:g} Pkt), Puffer {ab['puffer_pct']:g} %")
        else:
            sl, tp = level_vom_fill(richtung, fill, sl_pkt, tp_pkt, digits)
            lauf.log(f"Airbag nicht rechenbar ({ab.get('grund')}) — Plan-Abstände vom eigenen Fill: SL {ob.fmt_preis(sl, digits)} / TP {ob.fmt_preis(tp, digits)}")
        anker_pfad = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "anker-" + os.path.basename(cfg_path))
        bestaetigt = ob.sltp_bestaetigt(p["sl"], p["tp"], sl, tp, digits)
        if not bestaetigt and not ab.get("abbruch"):
            ob._sltp_klicken(w, ticket, symbol, ob.fmt_preis(sl, digits), ob.fmt_preis(tp, digits), lauf.trail, anker_pfad=anker_pfad)
            ende2 = time.time() + 10
            while time.time() < ende2 and not bestaetigt:
                st = ob._api_lesen(path, expected)
                if "fehler" not in st:
                    bestaetigt = any(q["ticket"] == ticket and ob.sltp_bestaetigt(q["sl"], q["tp"], sl, tp, digits) for q in st["positionen"])
                if not bestaetigt:
                    ob._warte(0.15, 0.15)
        res.update(sl=sl, tp=tp, level_ok=bestaetigt)
        # level-Felder (21.10.2026, Live-Ablauf von Slave 2): sl/tp = gesetzte Soll-Werte, ok = per API bestätigt, quelle airbag|plan,
        # notfall = F9-Level; mit Airbag dazu master_fill/master_tp/master_liq/master_stop(_art)/puffer_pct (s. airbag_level), sonst grund
        lv = {"sl": sl, "tp": tp, "ok": bestaetigt, "quelle": "airbag" if ab.get("ok") else ("notfall" if ab.get("abbruch") else "plan"), "notfall": {"sl": sl_g, "tp": tp_g}}
        lv.update({k: v for k, v in ab.items() if k not in ("ok", "sl", "tp")} if ab.get("ok") else {"grund": ab.get("grund")})
        res["airbag"] = lv
        melden(lauf, "level", lv)
        lauf.phase("level", sl=sl, tp=tp, level_ok=bestaetigt, quelle=lv["quelle"], master_liq=lv.get("master_liq"), master_stop_art=lv.get("master_stop_art"))
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
        # F9-Dialog zu, solange nichts gesendet ist (Lauf 2a854cb4, 21.10.2026: Abbruch beim Eintragen, Moritz' MT5 stand danach mit offenem
        # Order-Fenster „Volumen 23,00", SL/TP 0 — ein Fehlklick hätte 23 Lot gehandelt)
        if dlg is not None and not res.get("gesendet"):
            try:
                dlg.type_keys("{ESC}", set_foreground=False)
                lauf.log("F9-Dialog geschlossen (Esc)")
            except Exception:
                pass
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


def uia_zeilen_lesen(w, ticket, symbol=None):
    """UIA-Elemente der Toolbox-Liste (DataItem/ListItem/Custom/Text) → [{text, rect, typ}]. Auf vielen MT5-Builds ist die Liste für UIA
    unsichtbar (Befund 18.08.2026) — dann leer, und der Slave bleibt beim Rechtsklick-Weg. Nur Lesen."""
    out = []
    for ct in ("DataItem", "ListItem", "Custom", "Text"):
        try:
            els = w.descendants(control_type=ct)
        except Exception:
            continue
        for el in els:
            try:
                t = str(el.window_text() or "")
                r = el.rectangle()
                if r.right - r.left < 4 or r.bottom - r.top < 4:
                    continue
                out.append({"text": t[:80], "rect": [r.left, r.top, r.right - r.left, r.bottom - r.top], "typ": ct})
            except Exception:
                continue
        if len(out) > 2000:
            break
    return out


def slave_profit_zelle(w, ticket, symbol=None):
    """PROFIT-ZELLE der eigenen Zeile per UIA (Master-Entscheid 20.10.2026): Zeile = Element mit der Ticket-Nummer (uia_zeile_wahl),
    Zelle = die am weitesten rechts im Zeilenband (uia_profit_zelle). -> {zeile, zelle, punkt, n} | None"""
    zellen = uia_zeilen_lesen(w, ticket, symbol)
    zeile = uia_zeile_wahl(zellen, symbol, ticket)
    if not zeile:
        return None
    zelle = uia_profit_zelle(zellen, zeile["rect"])
    if not zelle:
        return None
    p = profit_x_aus_zelle(zelle["rect"])
    return {"zeile": zeile, "zelle": zelle, "punkt": p, "n": len(zellen)} if p else None


def _liste_fenster(w, punkt):
    """Win32-Fenster der Handel-Liste unter dem Zeilen-Punkt (WindowFromPoint), nur wenn es zum MT5-Prozess gehört und NICHT das
    Hauptfenster selbst ist. Client-Rechteck in Bildschirm-Koordinaten (ohne native Scrollleiste). Nur lesen.
    -> {hwnd, klasse, rect [l, t, r, b]} | {grund}"""
    import ctypes
    import ctypes.wintypes as wt
    u32 = ctypes.windll.user32
    u32.WindowFromPoint.restype = ctypes.c_void_p
    u32.WindowFromPoint.argtypes = [wt.POINT]
    u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.DWORD)]
    u32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.RECT)]
    u32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.POINT)]
    u32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    h = u32.WindowFromPoint(wt.POINT(int(punkt[0]), int(punkt[1])))
    if not h:
        return {"grund": "kein Fenster unter der Zeile"}
    kl = ctypes.create_unicode_buffer(128)
    u32.GetClassNameW(h, kl, 128)
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if int(pid.value) != int(w.element_info.process_id):
        return {"grund": f"Fenster unter der Zeile gehört nicht zu MT5 ({kl.value})", "klasse": kl.value}
    if int(h) == int(w.handle):
        return {"grund": "unter der Zeile liegt das MT5-Hauptfenster selbst, keine eigene Liste", "klasse": kl.value}
    rc, p = wt.RECT(), wt.POINT(0, 0)
    if not u32.GetClientRect(h, ctypes.byref(rc)) or not u32.ClientToScreen(h, ctypes.byref(p)):
        return {"grund": "Listen-Rechteck nicht lesbar", "klasse": kl.value}
    return {"hwnd": int(h), "klasse": kl.value, "rect": [p.x, p.y, p.x + rc.right, p.y + rc.bottom]}


def bild_noch_gueltig(bild, sichtbar, rect_jetzt, hwnd_unter_x):
    """REIN RECHNEND (testbar, Prüfung 21.10.2026): gilt der Bild-Beweis noch? Er entsteht EINMAL beim Parken, die Wache läuft bis zu 6 h —
    in der Zeit kann die Toolbox ihre Höhe ändern, abgedockt werden, ein Toast/Browser/Menü oder ein F9-Dialog über dem × liegen. Dann
    klickte _klick_absolut blind an die alte Stelle. Gültig nur, solange das Listenfenster sichtbar ist, sein Rechteck gleich dem beim Foto
    ist UND unter dem ×-Punkt genau dieses Fenster liegt. -> (bool, grund)"""
    if not isinstance(bild, dict) or not bild.get("hwnd") or not bild.get("liste"):
        return False, "kein Bild-Beweis"
    if not sichtbar:
        return False, "Liste nicht mehr sichtbar"
    if [int(v) for v in (rect_jetzt or [])] != [int(v) for v in bild["liste"]]:
        return False, f"Liste verändert {list(bild['liste'])} → {list(rect_jetzt or [])}"
    if int(hwnd_unter_x or 0) != int(bild["hwnd"]):
        return False, "über dem × liegt ein anderes Fenster"
    return True, "Lage unverändert"


def _fenster_lage(hwnd, punkt):
    """Win32, < 1 ms, kein Foto: (sichtbar, Client-Rechteck in Bildschirm-Koordinaten, Fenster unter dem Punkt). Nur lesen."""
    import ctypes
    import ctypes.wintypes as wt
    u32 = ctypes.windll.user32
    u32.IsWindow.argtypes = [ctypes.c_void_p]
    u32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    u32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.RECT)]
    u32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.POINT)]
    u32.WindowFromPoint.restype = ctypes.c_void_p
    u32.WindowFromPoint.argtypes = [wt.POINT]
    h = ctypes.c_void_p(int(hwnd))
    sichtbar = bool(u32.IsWindow(h)) and bool(u32.IsWindowVisible(h))
    rect = None
    rc, p = wt.RECT(), wt.POINT(0, 0)
    if sichtbar and u32.GetClientRect(h, ctypes.byref(rc)) and u32.ClientToScreen(h, ctypes.byref(p)):
        rect = [p.x, p.y, p.x + rc.right, p.y + rc.bottom]
    unter = u32.WindowFromPoint(wt.POINT(int(punkt[0]), int(punkt[1])))
    return sichtbar, rect, int(unter or 0)


def bild_pruefen(bild, punkt_x):
    """Lage-Wache vor jedem ×-Klick und alle 0,5 s in der Wache. Fehler beim Lesen = nicht gültig. -> (bool, grund)"""
    try:
        return bild_noch_gueltig(bild, *_fenster_lage(bild["hwnd"], punkt_x))
    except Exception as e:
        return False, f"Lage nicht lesbar ({type(e).__name__})"


def _bildschirm_lesen(x, y, b, h):
    """Bildschirm-Ausschnitt per GDI-BitBlt → Zeilen von 0xRRGGBB (ohne Mauszeiger). Kein PIL nötig. Nur lesen. -> Liste | None"""
    import ctypes
    import ctypes.wintypes as wt
    u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
    vp = ctypes.c_void_p
    u32.GetDC.restype, u32.GetDC.argtypes = vp, [vp]
    u32.ReleaseDC.argtypes = [vp, vp]
    g32.CreateCompatibleDC.restype, g32.CreateCompatibleDC.argtypes = vp, [vp]
    g32.CreateCompatibleBitmap.restype, g32.CreateCompatibleBitmap.argtypes = vp, [vp, ctypes.c_int, ctypes.c_int]
    g32.SelectObject.restype, g32.SelectObject.argtypes = vp, [vp, vp]
    g32.BitBlt.argtypes = [vp, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, vp, ctypes.c_int, ctypes.c_int, wt.DWORD]
    g32.GetDIBits.argtypes = [vp, vp, wt.UINT, wt.UINT, vp, vp, wt.UINT]
    g32.DeleteObject.argtypes = [vp]
    g32.DeleteDC.argtypes = [vp]

    class _BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    class _BI(ctypes.Structure):
        _fields_ = [("bmiHeader", _BIH), ("bmiColors", wt.DWORD * 3)]
    b, h = int(b), int(h)
    hdc = u32.GetDC(None)
    mem = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, b, h)
    alt = g32.SelectObject(mem, bmp)
    try:
        ok = g32.BitBlt(mem, 0, 0, b, h, hdc, int(x), int(y), 0x00CC0020)   # SRCCOPY
        g32.SelectObject(mem, alt)                                          # GetDIBits will die Bitmap NICHT in einem DC
        alt = None
        if not ok:
            return None
        bi = _BI()
        bi.bmiHeader.biSize = ctypes.sizeof(_BIH)
        bi.bmiHeader.biWidth, bi.bmiHeader.biHeight = b, -h                # negativ = von oben nach unten
        bi.bmiHeader.biPlanes, bi.bmiHeader.biBitCount = 1, 32
        buf = ctypes.create_string_buffer(b * h * 4)
        if g32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0) != h:
            return None
        roh = buf.raw
        return [[(roh[i + 2] << 16) | (roh[i + 1] << 8) | roh[i] for i in range(z * b * 4, (z + 1) * b * 4, 4)] for z in range(h)]
    finally:
        if alt is not None:
            g32.SelectObject(mem, alt)
        g32.DeleteObject(bmp)
        g32.DeleteDC(mem)
        u32.ReleaseDC(None, hdc)


def slave_x_bild(w, zeile_punkt, zeile_pruefen=True):
    """×-Beweis per Bild (21.10.2026, s. BILD_*): Listenfenster unter der Ticket-Zeile → rechter Streifen → genau ein × am Rand in
    dieser Zeile. Nur lesen, nie klicken. -> {punkt, glyph, liste, klasse, n_x, abstand_rechts, grund, ascii} (punkt fehlt = kein Beweis)
    zeile_pruefen=False nur im Maus-Test ohne Ticket-Anker: × zur Ansicht, ohne_zeile=True → x_klick_erlaubt sagt nie ja."""
    lf = _liste_fenster(w, zeile_punkt)
    if not lf.get("rect"):
        return {"grund": lf.get("grund") or "Liste nicht gefunden", "klasse": lf.get("klasse")}
    l, t, r, b = lf["rect"]
    breite, hoehe = min(BILD_STREIFEN_PX, r - l), b - t
    out = {"klasse": lf["klasse"], "liste": lf["rect"], "hwnd": lf["hwnd"], "ohne_zeile": not zeile_pruefen}
    if breite < 40 or not (12 <= hoehe <= 1600) or not (t <= zeile_punkt[1] < b):
        out["grund"] = f"Listen-Rechteck unbrauchbar {lf['rect']} ({lf['klasse']})"
        return out
    pix = _bildschirm_lesen(r - breite, t, breite, hoehe)
    if not pix:
        out["grund"] = "Bildschirm nicht lesbar (BitBlt)"
        return out
    maske = tinte_maske(pix)
    gl = x_glyphen(maske)
    zy = int(zeile_punkt[1]) - t
    g, n, grund = schliess_x_wahl(gl, breite, zy if zeile_pruefen else None)
    out.update(n_x=n, glyphen=len(gl), grund=grund)
    if g is None:
        out["ascii"] = maske_ascii(maske, 0, zy - 10, breite, 21)          # Band um die Ticket-Zeile — was lag dort?
        return out
    ox = r - breite
    out.update(punkt=(ox + g["cx"], t + g["cy"]), glyph=[ox + g["x"], t + g["y"], g["b"], g["h"]], abstand_rechts=r - (ox + g["x"] + g["b"]),
               ascii=maske_ascii(maske, max(0, g["x"] - 4), g["y"] - 3, g["b"] + 8, g["h"] + 6))
    ok, warum = bild_pruefen(out, out["punkt"])           # schon beim Foto: unter dem × liegt genau die Liste (nichts verdeckt)
    if not ok:
        out["grund"] = f"× gesehen, aber {warum}"
        out.pop("punkt")
    return out


def _kontextmenue_close_lesen(timeout=1.0):
    """Wie ob._kontextmenue_close_klicken, aber NUR lesen (Maus-Test 21.10.2026): steht im offenen Kontextmenü ein Punkt, der
    ob.ist_close_menuepunkt besteht, und ist er aktiv? Ausgelöst wird nichts. -> ('aktiv'|'ausgegraut'|'kein_menue', text)"""
    from pywinauto import Desktop
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            for m in Desktop(backend="uia").windows():
                try:
                    if m.element_info.class_name != "#32768" and m.element_info.control_type != "Menu":
                        continue
                    for it in m.descendants(control_type="MenuItem"):
                        txt = it.window_text()
                        if ob.ist_close_menuepunkt(txt):
                            try:
                                return ("aktiv" if it.is_enabled() else "ausgegraut"), str(txt)[:60]
                            except Exception:
                                return "aktiv", str(txt)[:60]
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.15)
    return "kein_menue", ""


def slave_x_punkte(w, anker_pfad, ticket=None, symbol=None):
    """Punkte der eigenen Positionszeile: zeile = Park-Punkt des Ticket-bewiesenen Ankers (Rechtsklick-Rückfall, x_frac/y_off vom
    SL/TP-Weg), x = das Schließen-× aus der PROFIT-ZELLE per UIA (slave_profit_zelle) — ohne lesbare Zelle KEIN ×-Punkt (Master-Entscheid
    20.10.2026 nach S1s Gegenprüfung: „Fensterrand − 14 px" trifft bei Rahmen/Scrollbar/breitem Terminal daneben).
    Seit 21.10.2026 (Lauf 8870f1de): ohne UIA-Zelle der Bild-Weg (slave_x_bild) an der Anker-Zeile; die Zeile rückt dann auf die
    Höhe des gesehenen × (genauer als der gemerkte Anker, auch für den Rechtsklick).
    -> (zeile, x | None, fenster, beweis_text, zelle_rect | None, bild | None)"""
    hr = w.rectangle()
    fenster = (hr.left, hr.top, hr.right, hr.bottom)
    a = ob._anker_lesen(anker_pfad)
    zeile = None
    try:
        zeile = (hr.left + int((hr.right - hr.left) * float(a["x_frac"])), hr.bottom - int(a["y_off"]))
    except (KeyError, TypeError, ValueError):
        pass
    z = slave_profit_zelle(w, ticket, symbol) if ticket else None
    if z:
        if zeile is None:
            zr = z["zeile"]["rect"]
            zeile = (int(zr[0] + zr[2] * 0.4), int(zr[1] + zr[3] / 2))
        return zeile, z["punkt"], fenster, f"Profit-Zelle {z['zelle']['rect']} '{z['zelle'].get('text')}' − {ZELLE_X_RAND_PX} px ({z['n']} UIA-Elemente)", z["zelle"]["rect"], None
    if not ticket:
        return zeile, None, fenster, "ohne Ticket kein ×", None, None
    if zeile is None:
        return None, None, fenster, "Profit-Zelle per UIA nicht lesbar, kein Zeilen-Anker — kein ×, Zeilen-Scan", None, None
    try:
        bild = slave_x_bild(w, zeile)
    except Exception as e:
        bild = {"grund": f"Bild nicht lesbar ({type(e).__name__}: {str(e)[:60]})"}
    if bild.get("punkt"):
        zeile = (zeile[0], bild["punkt"][1])
        return zeile, bild["punkt"], fenster, (f"Bild: {bild['grund']} · × {bild['glyph']} {bild['abstand_rechts']} px vor dem Listenrand "
                                               f"(Liste {bild['liste']} {bild['klasse']})"), None, bild
    return zeile, None, fenster, f"Profit-Zelle per UIA nicht lesbar, Bild: {bild.get('grund')} — kein ×, Rechtsklick-Weg", None, bild


def slave_wache(lauf, w, path, expected, ticket, anker_pfad):
    """Maus auf dem Schließen-× der (ticket-bewiesenen) Positionszeile parken (20.10.2026, Finn: „nicht Rechtsklick → Position
    schließen → bestätigen, sondern einfach auf das X"), /polar/warte?auf=zu halten. Signal → EIN Klick aufs × → lesend bewiesen
    weg in ≤ 2 s (Rückfrage-Dialog = Ein-Klick-Handel aus → nur den eindeutigen Ticket-Knopf), sonst Rückfall: Rechtsklick auf die
    Zeile + „Position schließen", dann der volle bewährte _close_klicken. SLAVE-WACHE: eigene Position alle 100 ms lesend (API, nie EA) —
    weg (SL/TP/Hand) → SOFORT POST /polar/melden zu (vor jeder DB), damit der Master in 1–2 s per × nachzieht.
    Zwischendurch (nie zwischen Signal und Druck) Fenster/Maus prüfen und neu parken."""
    erg = {"ok": False, "ticket": ticket, "geparkt": False, "x_geparkt": False}

    def lesen():
        st = ob._api_lesen(path, expected)
        return None if "fehler" in st else st

    def offen(st):
        return any(p["ticket"] == ticket for p in (st or {}).get("positionen") or [])

    def zu_bewiesen(st):
        # Lesefehler (None) ist NIE „zu" (Prüfung 21.10.2026): offen(None) war False — ein API-Aussetzer nach dem ×-Klick galt als
        # „weg", der Rückfall fiel aus und der Slave meldete „zu", obwohl die Position offen war. Dazu die zweite Lesung (zu_doppelt):
        # eine leere Liste aus einem positions_get-Fehler sieht aus wie „ohne Ticket"
        return zu_doppelt(lesen, st, ticket)

    symbol = str(lauf.cmd.get("symbol") or "").strip() or None

    def parken_mit_beweis():
        """Zeile/× lesen, Maus hinfahren, × nur mit Beweis behalten (x_klick_erlaubt). Am Start und nach einer Fensterbewegung.
        -> (punkt, punkt_x, fenster, zelle, bild, tooltip, beweis_text)"""
        try:
            p, px, f, bw, z, bd = slave_x_punkte(w, anker_pfad, ticket, symbol)
        except Exception as e:
            lauf.log(f"Wache: Zeile/Zelle nicht lesbar ({type(e).__name__}) — Schließen läuft dann über den vollen Zeilen-Scan")
            return None, None, None, None, None, "", ""
        if bd and bd.get("ascii") and not px:
            lauf.log("Wache: Bild um die Ticket-Zeile (# = Tinte):\n  " + "\n  ".join(bd["ascii"]))
        tip = ""
        if px or p:
            ob._maus_fahren(*(px or p), schritte=6)
        if px:
            tip = _tooltip_text(1.5)
            if not x_klick_erlaubt(z, tip, True, bd):
                # PFLICHT-BEWEIS (Master-Entscheid 20.10.2026): Zellen-Weg ohne Tooltip „Schließen/Close" bzw. Bild-Weg mit fremdem Tooltip
                # → das × ist nicht bewiesen, Maus zurück auf die Zeile, Schließen später über den Rechtsklick-Weg
                lauf.log(f"Wache: × NICHT bewiesen — Tooltip '{tip or '—'}' ({bw}) → Rechtsklick-Weg")
                px = None
                if p:
                    ob._maus_fahren(*p, schritte=4)
        return p, px, f, z, bd, tip, bw

    punkt, punkt_x, fenster, zelle, bild, x_tip, x_beweis = parken_mit_beweis()
    park = punkt_x or punkt
    x_ruht, naechst_foto = None, 0.0                     # × mit verworfener Lage (Lage-Wache), wartet auf ein frisches Foto
    if park:
        erg["geparkt"], erg["x_geparkt"] = True, punkt_x is not None
        erg["x_beweis"] = (f"{x_beweis}; Tooltip '{x_tip or '—'}'") if punkt_x else f"Zeile (kein bewiesenes ×: {x_beweis})"
        lauf.log(f"Wache: Maus parkt auf dem {'Schließen-×' if punkt_x else 'Positionszeile'} #{ticket} @{park[0]},{park[1]} — Beweis {erg['x_beweis']}")
    # geparkt-Felder (21.10.2026, Live-Anzeige „Maus auf ×" baut Slave 2): x = Punkt des BEWIESENEN × (sonst null), x_art zelle|bild|null,
    # tooltip = Text unter der Maus (leer = keiner), beweis = Klartext; punkt = Zeile für den Rechtsklick-Rückfall
    melden(lauf, "geparkt", {"ticket": ticket, "punkt": list(punkt) if punkt else None, "x": list(punkt_x) if punkt_x else None,
                             "x_art": ("zelle" if zelle else "bild") if punkt_x else None, "tooltip": x_tip if punkt_x else "",
                             "beweis": erg.get("x_beweis")})
    lauf.phase("geparkt_x" if punkt_x else "wache", geparkt=erg["geparkt"], x_geparkt=erg["x_geparkt"], x_beweis=erg.get("x_beweis"))
    signal = {"da": False, "ende": False, "status": None, "antwort": None, "signal_ms": None}
    stop = threading.Event()
    threading.Thread(target=_warte_signal, args=(lauf, "slave", signal, stop), daemon=True).start()
    st0 = lesen()
    einzig = bool(st0) and len(st0["positionen"]) == 1 and offen(st0)
    naechst_lesen, naechst_blick = time.time() + SLAVE_WACHE_TAKT_S, time.time() + 0.5
    ende_max = time.time() + 6 * 3600
    weg = None
    while time.time() < ende_max and not signal["da"]:
        if signal["ende"]:
            break
        jetzt = time.time()
        if jetzt >= naechst_lesen:
            naechst_lesen = jetzt + SLAVE_WACHE_TAKT_S
            st = lesen()
            if st is not None:
                if zu_bewiesen(st):
                    zu_ms = jetzt_ms()
                    melden(lauf, "zu", {"quelle": "slave", "zu_ms": zu_ms})      # ZUERST das Signal — der Master zieht per × nach
                    lauf.log("Wache: Position beim Broker zu (SL/TP oder von Hand) — 'zu' an Railway gemeldet, kein Klick nötig")
                    erg.update(ok=True, zu_weg="broker", zu_ms=zu_ms)
                    lauf.phase("zu_bestaetigt", zu_ms=zu_ms, zu_weg="broker")
                    stop.set()
                    break
                einzig = len(st["positionen"]) == 1
        if park and jetzt >= naechst_blick:
            naechst_blick = jetzt + 0.5
            try:
                if ob._win_vordergrund() != int(w.handle):
                    ob._fenster_betreten(w)
                # Neu lesen NUR, wenn das Fenster sich bewegt hat (21.10.2026): der Bild-Beweis fotografiert sonst alle 0,5 s unter der
                # parkenden Maus (Hover-Effekt am ×) und würde das bewiesene × grundlos fallen lassen
                # LAGE-WACHE (Prüfung 21.10.2026): der Bild-Beweis gilt nur, solange Liste, Rechteck und das Fenster unter dem × gleich
                # sind (bild_noch_gueltig, Win32, kein Foto). Weicht etwas ab → × ruht, Maus auf die Zeile (Rechtsklick-Rückfall). Steht die
                # Lage später wieder, zählt das × erst nach einem FRISCHEN Foto am selben Punkt (Maus dabei auf der Zeile, nicht am ×).
                if punkt_x and bild and not zelle:
                    ok_l, warum_l = bild_pruefen(bild, punkt_x)
                    if not ok_l:
                        x_ruht, punkt_x, erg["x_geparkt"] = punkt_x, None, False
                        park = punkt
                        lauf.log(f"Wache: × ruht — {warum_l} → Maus auf die Zeile, Schließen über den Rechtsklick")
                        melden(lauf, "geparkt", {"ticket": ticket, "punkt": list(punkt) if punkt else None, "x": None, "x_art": None, "tooltip": "",
                                                 "beweis": f"× ruht: {warum_l}", "neu": True})
                        if park:
                            ob._maus_fahren(*park, schritte=4)
                elif x_ruht and bild and punkt and jetzt >= naechst_foto and bild_pruefen(bild, x_ruht)[0]:
                    naechst_foto = jetzt + 3.0                   # Foto höchstens alle 3 s (BitBlt + Auswertung ~0,1 s)
                    neu_b = slave_x_bild(w, punkt)
                    if neu_b.get("punkt") and tuple(neu_b["punkt"]) == tuple(x_ruht):
                        punkt_x, bild, x_ruht, erg["x_geparkt"] = x_ruht, neu_b, None, True
                        park = punkt_x
                        lauf.log(f"Wache: × wieder bewiesen (frisches Foto, Lage gleich) @{park[0]},{park[1]}")
                        melden(lauf, "geparkt", {"ticket": ticket, "punkt": list(punkt), "x": list(punkt_x), "x_art": "bild", "tooltip": x_tip,
                                                 "beweis": f"× wieder bewiesen: {neu_b.get('grund')}", "neu": True})
                        ob._maus_fahren(*park, schritte=4)
                hr_n = w.rectangle()
                if (hr_n.left, hr_n.top, hr_n.right, hr_n.bottom) != fenster:
                    punkt, punkt_x, fenster, zelle, bild, x_tip, x_beweis = parken_mit_beweis()   # Zelle/Bild mitziehen (S2-Hinweis 20.10.2026)
                    x_ruht = None
                    park = punkt_x or punkt
                    erg["x_geparkt"] = punkt_x is not None
                    melden(lauf, "geparkt", {"ticket": ticket, "punkt": list(punkt) if punkt else None, "x": list(punkt_x) if punkt_x else None,
                                             "x_art": ("zelle" if zelle else "bild") if punkt_x else None, "tooltip": x_tip if punkt_x else "",
                                             "beweis": x_beweis, "neu": True})   # Live-Anzeige bleibt wahr
                    if park:
                        lauf.log(f"Wache: Fenster bewegt — neu geparkt @{park[0]},{park[1]} ({'×' if punkt_x else 'Zeile'}: {x_beweis})")
                    else:
                        lauf.log("Wache: Fenster bewegt — Zeile nicht mehr lesbar, Schließen über den Zeilen-Scan")
                elif ob._cursor_pos() != tuple(park):
                    ob._maus_fahren(*park, schritte=4)
            except Exception:
                pass
        time.sleep(0.004)
    stop.set()
    if signal["da"] and not erg.get("zu_weg"):
        t_sig = time.time()
        a = signal["antwort"] or {}
        erg["signal_ms"] = signal["signal_ms"] or jetzt_ms()
        lauf.log(f"Polar: Signal — Master zu ({a.get('master_zu_ms')}, Status {a.get('status')}) → Slave schließt per ×")
        # VOR-KLICK-LESUNG (Prüfer S2 über den Master, 20.10.2026): frisch lesen — eigene Position noch offen und die EINZIGE Zeile
        # (die MT5-Liste ist für UIA unsichtbar, also ist „genau eine Position = mein Ticket" der Beweis, dass das × meiner Zeile gehört);
        # schon flach → nicht klicken, 'zu' melden; mehrere Positionen → nie das × (Zeile unklar), nur der Ticket-geprüfte Scan
        st_v = lesen()
        if zu_bewiesen(st_v):
            zu_ms = jetzt_ms()
            melden(lauf, "zu", {"quelle": "slave", "zu_ms": zu_ms, "weg": "schon_zu", "signal_ms": erg["signal_ms"]})
            lauf.log("Polar: Vor-Klick-Lesung — Position schon zu, kein Klick")
            erg.update(ok=True, zu_weg="schon_zu", zu_ms=zu_ms, zu_nach_signal_ms=zu_ms - erg["signal_ms"])
            lauf.phase("zu_bestaetigt", zu_ms=zu_ms, zu_weg="schon_zu")
            weg = "schon_zu"
        einzig = bool(st_v) and len(st_v["positionen"]) == 1 and offen(st_v)
        lauf.log(f"Polar: Vor-Klick-Lesung {int((time.time() - t_sig) * 1000)} ms → {'einzige Position #' + str(ticket) if einzig else ('Position zu' if weg else str(len((st_v or {}).get('positionen') or [])) + ' Positionen — × tabu')}")
        # 1) EIN Klick aufs geparkte × — nur mit vollem Beweis (x_klick_erlaubt: Profit-Zelle per UIA mit Tooltip Schließen/Close oder
        #    Bild-Beweis, genau EINE Position = die eigene, Vor-Klick-Lesung) und nicht pausiert; sonst sofort 2) Rechtsklick-Weg
        #    (Finn 21.10.2026: „Maus auf dem X, sobald das Signal vom Master kommt, insta schließen")
        lage_ok, lage_grund = (True, "Zellen-Weg") if (zelle or not punkt_x) else bild_pruefen(bild, punkt_x)   # direkt vor dem Klick, < 1 ms
        if punkt_x and not lage_ok:
            lauf.log(f"Polar: × nicht geklickt — {lage_grund} → Rechtsklick-Rückfall")
        if weg is None and punkt_x and lage_ok and x_klick_erlaubt(zelle, x_tip, einzig, bild) and not ob.is_paused():
            geklickt = bool(ob._klick_absolut(punkt_x[0], punkt_x[1]))
            erg["klick_ms"] = jetzt_ms()
            lauf.phase("x_geklickt", klick_ms=erg["klick_ms"], x_ok=geklickt)
            lauf.log(f"Polar: × geklickt {int((time.time() - t_sig) * 1000)} ms nach dem Signal" if geklickt else "Polar: × NICHT gedrückt (SendInput)")
            weg_nach, dialog_knopf, ende = None, False, time.time() + X_BEWEIS_S
            while time.time() < ende:
                if zu_bewiesen(lesen()):
                    weg_nach = time.time() - t_sig
                    break
                if not dialog_knopf:
                    dlg, knopf = ob._finde_close_dialog(w, ticket)          # Ein-Klick-Handel aus: nur der Knopf mit DIESEM Ticket
                    if knopf is not None:
                        try:
                            r = knopf.rectangle()
                            ob._klick_absolut(r.mid_point().x, r.mid_point().y)
                            dialog_knopf = True
                            ende = time.time() + X_BEWEIS_S
                            lauf.log("Polar: Close-Dialog (Ein-Klick-Handel aus) — Schließen-Knopf des Tickets gedrückt")
                        except Exception:
                            pass
                time.sleep(X_TAKT_S)
            u = schliess_urteil(geklickt, weg_nach, dialog_knopf)
            if u == "zu":
                weg = "x_dialog" if dialog_knopf else "x"
                lauf.log(f"Polar: Position #{ticket} weg {weg_nach * 1000:.0f} ms nach dem Signal (×)")
            else:
                lauf.log(f"Polar: × ohne Beweis in {X_BEWEIS_S:g} s ({u}) — Rückfall Rechtsklick auf die Zeile")
                try:
                    w.type_keys("{ESC}", set_foreground=False)       # ein versehentlich offenes Menü/Dialog zu, nie bestätigen
                except Exception:
                    pass
        # 2) Rückfall: Rechtsklick auf die geparkte Zeile → „Position schließen" (der bewährte Weg bis 19.10.2026)
        if weg is None and punkt and einzig and not ob.is_paused() and not zu_bewiesen(lesen()):
            ob._maus_fahren(*punkt, schritte=3)
            if ob._klick_absolut(punkt[0], punkt[1], taste="rechts"):
                st_m = ob._kontextmenue_close_klicken(timeout=0.8)
                erg["klick_ms"] = jetzt_ms()
                if st_m == "geklickt":
                    lauf.log(f"Polar: 'Position schließen' {int((time.time() - t_sig) * 1000)} ms nach dem Signal")
                    ende = time.time() + 3.0
                    while time.time() < ende:
                        if zu_bewiesen(lesen()):
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
        # 3) Letzter Weg: der volle Zeilen-Scan (nur bei genau einer Position)
        if weg is None and not zu_bewiesen(lesen()):
            st_n = lesen()
            if st_n and len(st_n["positionen"]) == 1:
                ausgang = ob._close_klicken(w, ticket, lauf.trail, anker_pfad, lambda: zu_bewiesen(lesen()))
                lauf.log(f"Polar: voller Schließ-Scan → {ausgang}")
            else:
                lauf.log("Polar: mehrere Positionen offen — Zeilen-Scan nicht sicher, Schließen von Hand nötig")
        ende, zu = time.time() + 8.0, False
        while time.time() < ende:
            if zu_bewiesen(lesen()):
                zu = True
                break
            time.sleep(0.1)
        zu_ms = erg.get("zu_ms") or (jetzt_ms() if zu else None)
        erg.update(ok=zu, zu_weg=(weg or ("scan" if zu else None)), zu_ms=zu_ms, zu_nach_signal_ms=(zu_ms - erg["signal_ms"]) if zu else None)
        if zu and weg == "schon_zu":
            pass                                                         # schon gemeldet
        elif zu:
            melden(lauf, "zu", {"quelle": "slave", "zu_ms": zu_ms, "weg": erg["zu_weg"], "signal_ms": erg["signal_ms"]})   # Bestätigung ans Railway
            lauf.phase("zu_bestaetigt", zu_ms=zu_ms, zu_weg=erg["zu_weg"], zu_nach_signal_ms=erg["zu_nach_signal_ms"])
        else:
            erg["msg"] = f"Polar: Position #{ticket} nach dem Signal NICHT zu — SOFORT im Terminal schließen!"
            lauf.phase("nicht_zu", msg=erg["msg"])
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


# ── MAUS-TEST × (Finn 20.10.2026 02:45 Dubai: „erst mal ein separater Test, wo es nur darum geht, dass der Mauscursor das X findet") ──
TEST_PARKEN_S = 10.0


def lauf_test_x(seite, cmd):
    """Trockenlauf: an einer BESTEHENDEN offenen Position das Schließen-× finden, Maus hinfahren, 10 s parken (Finn schaut zu), NIE
    klicken. Master: Chart-× der Positions-Linie per CDP (sonst Close-Knopf der Positions-Tabelle als Vergleich). Slave: Profit-× der
    Positionszeile im MT5-Handel-Reiter — Zeile per UIA (Ticket/Symbol), sonst der Zeilen-Anker des letzten SL/TP-Laufs. Beweis ins Log
    (Tooltip, Rechteck, Abstand zum rechten Rand, Kandidatenzahl) und nach stand_test_<seite>.json."""
    lauf = Lauf(seite, cmd, test="test_x")
    res = {"ok": False, "seite": seite, "test": "test_x", "geklickt": False, "gefunden": False}
    sitz = [None]
    try:
        lauf.log(f"Maus-Test × {seite} v{VERSION}: {json.dumps({k: v for k, v in cmd.items() if k != 'geschwister'}, ensure_ascii=False)[:200]}")
        lauf.phase("suchen")
        if seite == "master":
            if ob.augen_modus_lauf() != "cdp":
                raise RuntimeError("Polar-Master braucht das Puls-Chrome (CDP) auf diesem PC")
            if ob._handlauf_aktiv():
                raise RuntimeError("K3-Handlauf läuft im Puls-Chrome")
            ext = str(cmd.get("ext_id") or "").strip()
            symbol = str(cmd.get("symbol") or "").strip()
            root = ob.tv_symbol_root(symbol) if symbol else ""
            geschwister = [str(x).strip() for x in (cmd.get("geschwister") or []) if len(ob._nur_alnum(x)) >= 3][:60]
            opts = {"kontoTexte": ([ext] if ext else []) + geschwister}
            s = sitz[0] = ob._cdp_sitzung_holen(cmd, lauf.trail)
            if ext:
                ok, code, msg, st, extra = ob._cdp_konto_mit_login(sitz, ext, opts, cmd, lauf.trail, res)
                s = sitz[0]
                if not ok:
                    raise RuntimeError(f"Konto: {msg}")
            ob._cdp_reiter(s, "positions", lauf.trail)
            st = s.stand(opts)
            zeilen = [z for z in (st.get("positionen") or []) if isinstance(z, dict) and z.get("sichtbar") and (not root or ob.tv_symbol_root(str(z.get("symbol") or "")) == root)]
            res["positionen"] = len(zeilen)
            lauf.log(f"Positions-Tabelle: {len(zeilen)} sichtbare Zeile(n){' ' + root if root else ''}")
            d = s.lese_js(CHART_X_JS) or {}
            kand = d.get("kandidaten") or []
            im_chart = [k for k in kand if k.get("im_chart")]
            res.update(kandidaten=len(kand), kandidaten_chart=len(im_chart), tooltips_vorher=d.get("tooltips"))
            lauf.log(f"Chart-×: {len(kand)} Kandidaten ({len(im_chart)} im Chart): " + "; ".join(f"{k.get('text') or k.get('aria') or k.get('title') or k.get('dn')}@{k.get('rect')}" for k in kand[:8]))
            x = chart_x_wahl(kand)
            vw = None
            try:
                vw = s.lese_js("innerWidth")
            except Exception:
                pass
            if x is not None:
                res.update(gefunden=True, art="chart", rect=list(x["rect"]), abstand_rechts=x_abstand_rechts((x["rect"][0] + x["rect"][2], 0), vw) if vw else None)
                s.hin(x["rect"], "Chart-× der Positions-Linie (Test)")
                ob._warte(0.5, 0.2)
                tips = [t for t in (s.lese_js(TOOLTIP_JS) or []) if isinstance(t, str)]
                res["tooltip"] = next((t for t in tips if RX_CLOSE_TEXT.search(t)), "") or (tips[0] if tips else "")
                lauf.log(f"GEFUNDEN Chart-× @{x['rect']} · Tooltip '{res['tooltip']}' · Abstand rechter Rand {res['abstand_rechts']} px (innerWidth {vw})")
            else:
                lauf.log("Chart-× NICHT eindeutig im DOM (Positions-Linie vermutlich Canvas) — Vergleich: Close-Knopf der Positions-Tabelle")
                if len(zeilen) == 1:
                    roh = [z for z in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(z, dict) and z.get("sichtbar") and (not root or ob.tv_symbol_root(str(z.get("symbol") or "")) == root)]
                    if len(roh) == 1:
                        s.hin(roh[0].get("zeile"), "Positions-Zeile (Knöpfe einblenden)")
                        ob._warte(0.6, 0.3)
                        roh2 = next((z for z in (s.lese_js(ob.K3_ZEILEN_JS) or []) if isinstance(z, dict) and z.get("zeile") == roh[0].get("zeile")), roh[0])
                        kn, n = ob.k3_close_knopf(roh2)
                        res["tabelle_knoepfe"] = n
                        if kn:
                            res.update(gefunden=True, art="tabelle", rect=list(ob.cdp_rect(kn)), abstand_rechts=x_abstand_rechts((ob.cdp_rect(kn)[0] + ob.cdp_rect(kn)[2], 0), vw) if vw else None)
                            s.hin(ob.cdp_rect(kn), "Close-Knopf der Positions-Tabelle (Test)")
                            lauf.log(f"GEFUNDEN Tabellen-Close '{ob.k3_label(kn)}' @{res['rect']} ({n} Kandidat)")
            if res["gefunden"]:
                lauf.phase("geparkt_x", rect=res.get("rect"), art=res.get("art"), tooltip=res.get("tooltip"))
                ende = time.time() + TEST_PARKEN_S
                while time.time() < ende:
                    time.sleep(2.0)
                    try:
                        s.hin(res["rect"], "× (parken, Test)")
                    except Exception:
                        pass
                res["ok"] = True
                res["msg"] = f"× gefunden ({res['art']}) — Maus stand {TEST_PARKEN_S:g} s darauf, nichts geklickt"
            else:
                res["msg"] = "× nicht gefunden — nichts bewegt, nichts geklickt"
        else:
            cfg_path = os.path.join(HIER, str(cmd.get("config_file") or ""))
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
            symbol = str(cmd.get("symbol") or "").strip()
            ticket = cmd.get("ticket")
            lese = ob._login_dann_lesen(path, expected, trail=lauf.trail, symbol=symbol or None)
            if "fehler" in lese:
                raise RuntimeError(lese["fehler"])
            pos = [p for p in lese["positionen"] if not symbol or str(p.get("symbol") or "").lower() == symbol.lower()]
            res["positionen"] = len(pos)
            if ticket:
                pos = [p for p in pos if str(p.get("ticket")) == str(ticket)]
            if not pos:
                raise RuntimeError(f"keine offene Position{' ' + symbol if symbol else ''}{' #' + str(ticket) if ticket else ''} auf Konto {expected}")
            ticket = pos[0]["ticket"]
            lauf.log(f"Position #{ticket} {pos[0].get('typ') or ''} {pos[0].get('volumen')} {pos[0].get('symbol')} — {len(lese['positionen'])} offen gesamt")
            w = ob._finde_terminal(expected)
            if w is None:
                raise RuntimeError(f"Kein MT5-Fenster mit Konto {expected}")
            ob._fenster_betreten(w)
            hr = w.rectangle()
            maus_grenze = hr.top + (hr.bottom - hr.top) // 2
            anker_pfad = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "anker-" + os.path.basename(cfg_path))
            tab = ob._handel_tab_aktivieren(w, lauf.trail, maus_grenze, anker_pfad=anker_pfad)
            lauf.log(f"Handel-Reiter: {tab}")
            # Zeile + × wie im scharfen Lauf (slave_x_punkte: UIA-Zelle, sonst Bild-Weg an der Ticket-Anker-Zeile), dazu der Rechtsklick-
            # Rückfall belegt (21.10.2026, Lauf 8870f1de: × unbewiesen, Rechtsklick nie geprüft). Der Bot klickt das × NIE; der Rechtsklick
            # öffnet nur das Kontextmenü, gelesen wird „Position schließen" (aktiv?), dann Esc — ausgelöst wird nichts.
            einzig = len(lese["positionen"]) == 1
            zeile, px, _f, x_beweis, zelle, bild = slave_x_punkte(w, anker_pfad, ticket, symbol or None)
            if zeile is None and not px:
                # kein Ticket-Anker auf diesem PC (noch kein SL/TP-Lauf): Liste über den Erfahrungspunkt finden, × nur zur Ansicht
                probe = (hr.left + int((hr.right - hr.left) * 0.4), max(maus_grenze, hr.bottom - 316))
                try:
                    bild = slave_x_bild(w, probe, zeile_pruefen=False)
                except Exception as e:
                    bild = {"grund": f"Bild nicht lesbar ({type(e).__name__})"}
                if bild.get("punkt"):
                    zeile = (probe[0], bild["punkt"][1])
                x_beweis = f"ohne Ticket-Anker (Erfahrungspunkt): {bild.get('grund')}"
            if bild:
                res["bild"] = {k: bild.get(k) for k in ("klasse", "liste", "n_x", "glyphen", "glyph", "abstand_rechts", "grund")}
                if bild.get("ascii"):
                    lauf.log("Bild am Listenrand (# = Tinte):\n  " + "\n  ".join(bild["ascii"]))
            lauf.log(f"Zeile {'@' + str(zeile) if zeile else 'NICHT gefunden'} · {x_beweis}")
            # 1) Rechtsklick-Rückfall belegen (zuerst, damit die Maus am Ende auf dem × steht)
            if zeile and einzig:
                ob._maus_fahren(*zeile, schritte=5)
                if ob._klick_absolut(zeile[0], zeile[1], taste="rechts"):
                    rk, rk_text = _kontextmenue_close_lesen(1.2)
                else:
                    rk, rk_text = "kein_klick", ""
                try:
                    w.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                ob._warte(0.2, 0.1)
                res["rechtsklick"] = {"menue": rk, "text": rk_text, "punkt": list(zeile)}
                res["rechtsklick_bewiesen"] = rk == "aktiv"
                lauf.log(f"Rechtsklick-Weg @{zeile[0]},{zeile[1]}: {rk} '{rk_text}' → {'BEWIESEN' if rk == 'aktiv' else 'NICHT bewiesen'} (Menü per Esc zu, nichts ausgelöst)")
            elif zeile:
                res["rechtsklick"] = {"menue": "nicht_geprueft", "punkt": list(zeile)}
                lauf.log(f"Rechtsklick-Weg nicht geprüft: {len(lese['positionen'])} Positionen offen (scharf nur bei genau einer)")
            # 2) × anfahren und beweisen
            if px:
                ob._maus_fahren(px[0], px[1], schritte=6)
                res["tooltip"] = _tooltip_text(1.5)
                res["x_bewiesen"] = x_klick_erlaubt(zelle, res["tooltip"], einzig, bild)
                res.update(gefunden=True, art="profit_zelle" if zelle else "bild", punkt=[px[0], px[1]], beweis=x_beweis,
                           abstand_rechts=(x_abstand_rechts(px, zelle[0] + zelle[2]) if zelle else (bild or {}).get("abstand_rechts")))
                lauf.log(f"× @{px[0]},{px[1]} ({res['art']}) · Tooltip '{res['tooltip'] or '—'}' · {res['abstand_rechts']} px vom Rand → "
                         f"{'BEWIESEN (scharf würde klicken)' if res['x_bewiesen'] else 'NICHT bewiesen (scharf: Rechtsklick-Weg)'}")
                park = (px[0], px[1])
            elif zeile and zeile[1] >= maus_grenze:
                vx = profit_x_wahl(zeile[1], hr.right)
                res.update(gefunden=False, art="vergleich_fensterrand", punkt=[vx[0], vx[1]], abstand_rechts=x_abstand_rechts(vx, hr.right),
                           beweis=x_beweis + " — Vergleichspunkt Fensterrand, der Bot klickt hier nie", x_bewiesen=False)
                ob._maus_fahren(vx[0], vx[1], schritte=6)
                res["tooltip"] = _tooltip_text(1.5)
                lauf.log(f"× NICHT gefunden ({x_beweis}) — Vergleichspunkt Fensterrand @{vx[0]},{vx[1]} · Tooltip '{res['tooltip'] or '—'}'")
                park = (vx[0], vx[1])
            else:
                park = None
            x_txt = (f"× BEWIESEN ({res.get('art')}, Tooltip '{res.get('tooltip') or '—'}')" if res.get("x_bewiesen")
                     else f"× NICHT bewiesen ({x_beweis})")
            rk_txt = ("Rechtsklick BEWIESEN" if res.get("rechtsklick_bewiesen")
                      else f"Rechtsklick nicht bewiesen ({(res.get('rechtsklick') or {}).get('menue', 'keine Zeile')})")
            if park:
                lauf.phase("geparkt_x", punkt=res.get("punkt"), tooltip=res.get("tooltip"), x_bewiesen=bool(res.get("x_bewiesen")),
                           msg=f"{x_txt} · {rk_txt} — Maus parkt {TEST_PARKEN_S:g} s, nichts geklickt")
                ende = time.time() + TEST_PARKEN_S
                while time.time() < ende:
                    time.sleep(0.5)
                    try:
                        if ob._cursor_pos() != park:
                            ob._maus_fahren(park[0], park[1], schritte=3)
                    except Exception:
                        pass
            res["ok"] = bool(park)
            res["msg"] = f"{x_txt} · {rk_txt} — nichts geklickt" if park else f"Zeile nicht gefunden ({x_beweis}) — nichts bewegt, nichts geklickt"
        lauf.phase("fertig" if res["ok"] else "nicht_gefunden", msg=res["msg"], ergebnis=res)
        lauf.log(res["msg"])
        return res
    except Exception as e:
        res["msg"] = f"{type(e).__name__}: {str(e)[:200]}"
        lauf.log("ABBRUCH: " + res["msg"])
        lauf.phase("fehler", msg=res["msg"], ergebnis=res)
        return res
    finally:
        try:
            if seite == "slave":
                ob._api_trennen()
            if sitz[0]:
                ob._cdp_panel_zurueck(sitz[0], lauf.trail)
                sitz[0].zu()
        except Exception:
            pass
        res["trail"] = ob._spur(lauf.trail)


# ── Start ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(errors="replace")
        except Exception:
            pass
    # test_x master|slave '<json>' (20.10.2026): Maus-Test ×, klickt nie
    if len(sys.argv) >= 4 and sys.argv[1] == "test_x" and sys.argv[2] in ("master", "slave"):
        try:
            cmd = json.loads(sys.argv[3])
        except ValueError as e:
            print(json.dumps({"ok": False, "msg": f"Befehl kein gültiges JSON: {e}"}))
            return 2
        res = lauf_test_x(sys.argv[2], cmd)
        print(json.dumps(res, ensure_ascii=False, default=str))
        return 0 if res.get("ok") else 1
    if len(sys.argv) < 3 or sys.argv[1] not in ("master", "slave"):
        print(json.dumps({"ok": False, "msg": "Aufruf: polar_bot.py master|slave '<json>'  |  polar_bot.py test_x master|slave '<json>'"}))
        return 2
    try:
        cmd = json.loads(sys.argv[2])
    except ValueError as e:
        print(json.dumps({"ok": False, "msg": f"Befehl kein gültiges JSON: {e}"}))
        return 2
    res = lauf_master(cmd) if sys.argv[1] == "master" else lauf_slave(cmd)
    schritte_abwarten()   # Live-Ablauf (21.10.2026): letzte Schritte noch raus, höchstens 6 s
    print(json.dumps(res, ensure_ascii=False, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
