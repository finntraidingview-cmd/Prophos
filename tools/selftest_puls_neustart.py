#!/usr/bin/env python3
"""Selbsttest Puls-Chrome-Neustart (mt5-copier/order_bot.py, 07.10.2026, Finn: „wenn beim Platzieren der Order ein Fehler kommt,
schließt er einfach das komplette Chrome-Ding … und öffnet ihn neu") — alles mit Attrappen, kein Chrome, kein Netz, keine Order.

Aufruf:  python3 tools/selftest_puls_neustart.py
Prueft neustart_entscheid (vor/nach Klick, Budget, Nie-Codes, nie zweimal), neustart_beleg_leer (Doppel-Order-Schutz), den Wrapper
_puls_mit_neustart (Fehler vor Klick → Neustart + zweiter Versuch; nach Klick ohne Beleg → kein zweiter Versuch, UNKLAR bleibt;
zweiter Fehler → Fehler-Ausgang; nie zwei Neustarts; Topstep nach Klick → kein Neustart), _puls_chrome_beenden (Port frei → fertig,
haengt → nur eigene PIDs hart, Zeitlimit → False), _puls_lauf_abfangen (echter stdout fuer den Wachhund) und _tsx_frist."""
import inspect
import io
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

OK = True


def check(bed, text):
    global OK
    print(("✓ " if bed else "✗ ") + text)
    OK = OK and bool(bed)


def erg(**k):
    """Antwort eines Versuchs wie die raus()-Helfer: ok False, gesendet False, retry_ok True — ueberschreibbar."""
    d = {"ok": False, "code": "", "msg": "", "schritt": "", "trail": "x", "gesendet": False, "retry_ok": True}
    d.update(k)
    return d


class Attrappe:
    """Zaehlt Neustarts, Versuche, Ausgaben und Diagnosen; die Antworten der Versuche sind vorgegeben."""

    def __init__(self, r1, r2=None, lesung=None, neustart_ok=True, verstrichen=30.0, zeitsprung=0.0):
        self.r1, self.r2, self.lesung_res, self.neustart_ok = r1, r2, lesung, neustart_ok
        self.neustarts, self.zweite, self.lesungen, self.ausgaben, self.diagnosen = 0, [], 0, [], []
        self.t = [verstrichen]
        self.zeitsprung = zeitsprung

    def erster(self):
        return json.dumps(self.r1, ensure_ascii=False), dict(self.r1)

    def zweiter(self, frist):
        self.zweite.append(frist)
        return (json.dumps(self.r2, ensure_ascii=False), dict(self.r2)) if self.r2 else ("", {})

    def lesung(self, spur):
        self.lesungen += 1
        spur.append("Attrappe: Lesung")
        return self.lesung_res

    def neustart(self, spur, url):
        self.neustarts += 1
        self.url = url
        spur.append("Attrappe: Neustart")
        self.t[0] += self.zeitsprung
        return self.neustart_ok

    def jetzt(self):
        return self.t[0]

    def ausgeben(self, res):
        self.ausgaben.append(res)

    def diagnose(self, spur=None, schritt=""):
        self.diagnosen.append((schritt, " > ".join(spur or [])))

    def lauf(self, weg="tvv2", mit_lesung=True):
        return ob._puls_mit_neustart(weg, self.erster, self.zweiter, self.lesung if mit_lesung else None, "https://x/",
                                     neustart=self.neustart, jetzt=self.jetzt, t0=0.0, ausgeben=self.ausgeben, diagnose=self.diagnose)


def main():
    # ── neustart_entscheid (rein rechnend) ────────────────────────────────────────────────────────────────────────────────────────
    e = ob.neustart_entscheid
    check(e(erg(code="login", schritt="login"), "tvv2", 30.0)[0] == "direkt", "vor dem Klick (anderer Fehler, z. B. login) → direkt")
    # Master 08.10.2026: Ticket/Konto/Login-Feld → kein Neustart (zerlegte den Folgeversuch: halbes Fenster, ConnectionAborted)
    check(all(e(erg(code=c, schritt=c), "tvv2", 30.0)[0] == "nein" for c in ("ticket", "konto", "konto_nicht_erreicht")),
          "ticket/konto/konto_nicht_erreicht → nein (kein Chrome-Neustart)")
    check(e(erg(code="knopf", schritt="knopf", msg="nichts gesendet"), "tsv2", 20.0)[0] == "direkt", "Topstep vor dem Klick (knopf) → direkt")
    check(e(erg(code="unklar", schritt="unklar", gesendet=True, retry_ok=False), "tvv2", 60.0)[0] == "lesung",
          "nach dem Klick ohne Beweis (Orbit) → nur mit Lesung")
    a, g, _ = e(erg(code="beweis", schritt="beweis", gesendet=True, retry_ok=False, unklar=True), "tsv2", 40.0, lesung_moeglich=False)
    check(a == "nein" and "UNKLAR bleibt" in g, "Topstep nach dem Klick (keine Order-Lesung) → nein, UNKLAR bleibt")
    check(e(erg(ok=True), "tvv2", 30.0)[0] == "nein", "ok → nein")
    check(e({}, "tvv2", 30.0)[0] == "nein", "unlesbare Antwort → nein")
    check(all(e(erg(code=c), "tvv2", 10.0)[0] == "nein" for c in ("befehl", "handlauf", "cdp_folgt", "markt_zu", "zeit", "haenger", "abgelehnt")),
          "Nie-Codes (befehl/handlauf/cdp_folgt/markt_zu/zeit/haenger/abgelehnt) → nein")
    check(e(erg(code="cdp_fehler", bestaetigt=True, gesendet=True), "tvv2", 30.0)[0] == "nein", "Fill bewiesen → nein (bestehender Weg)")
    check(e(erg(code="tabelle_unklar", offen=True, positionen=[{"symbol": "MNQZ6"}]), "tsv2", 20.0)[0] == "nein", "offene Position → nein")
    a, g, _ = e(erg(code="login"), "tvv2", 200.0)
    check(a == "nein" and "zu wenig Zeit" in g, "Orbit: 200 s verstrichen von 250 → zu wenig Zeit")
    a, g, _ = e(erg(code="login"), "tsv2", 50.0)
    check(a == "nein" and "zu wenig Zeit" in g, "Topstep: 50 s verstrichen von 160 (Rest 90 < 100) → zu wenig Zeit")
    check(e(erg(code="login"), "tsv2", 30.0)[0] == "direkt", "Topstep: 30 s verstrichen (Rest 110) → direkt")
    check(e(erg(code="login"), "tvv2", 30.0, schon=True)[0] == "nein", "schon ein Neustart → nein (nie zwei)")

    # ── neustart_beleg_leer (Doppel-Order-Schutz) ────────────────────────────────────────────────────────────────────────────────
    b = ob.neustart_beleg_leer
    erst = {"today_pnl_start": -12.5, "balance_start": 150000.0}
    leer = {"ok": True, "positionen_sichtbar": True, "pos_root": 0, "orders_gelesen": True, "orders_root": 0, "today_pnl": -12.5, "balance": 150000.0}
    check(b(leer, erst)[0] is True, "Beleg: Tabelle sichtbar, keine Position, keine Order, P/L + Balance gleich → leer")
    check(b(dict(leer, pos_root=1), erst)[0] is False, "Beleg: Position der Wurzel → nicht leer")
    check(b(dict(leer, orders_root=1), erst)[0] is False, "Beleg: offene Order → nicht leer")
    check(b(dict(leer, orders_gelesen=False), erst)[0] is False, "Beleg: Reiter Orders nicht gelesen → nicht leer")
    check(b(dict(leer, positionen_sichtbar=None), erst)[0] is False, "Beleg: Tabelle nicht sichtbar → nicht leer")
    check(b(dict(leer, today_pnl=9.5), erst)[0] is False, "Beleg: Total P/L veraendert (Fill schon wieder zu) → nicht leer")
    check(b(leer, {"balance_start": 150000.0})[0] is False, "Beleg: Start-P/L fehlt → nicht leer")
    check(b(dict(leer, balance=149995.0), erst)[0] is False, "Beleg: Balance veraendert → nicht leer")
    check(b(dict(leer, balance=None), erst)[0] is True, "Beleg: Balance nachher nicht lesbar, P/L gleich → leer (Balance nur wenn beide lesbar)")
    check(b({"ok": False, "msg": "Konto nicht erreicht"}, erst)[0] is False and b(None, erst)[0] is False, "Beleg: Lesung fehlgeschlagen/None → nicht leer")

    # ── Wrapper: Fehler vor dem Klick → EIN Neustart + zweiter Versuch ───────────────────────────────────────────────────────────
    a = Attrappe(erg(code="login", schritt="login", msg="Login hing"), erg(ok=True, code="", schritt="fertig", msg="Order platziert", gesendet=True, bestaetigt=True), verstrichen=30.0)
    r = a.lauf("tvv2")
    check(a.neustarts == 1 and len(a.zweite) == 1 and a.lesungen == 0, "vor Klick: genau ein Neustart, ein zweiter Versuch, keine Lesung")
    check(len(a.ausgaben) == 1 and a.ausgaben[0] is r and r.get("ok") is True and r.get("msg") == "Order platziert", "vor Klick: genau EINE Ausgabe = Antwort des zweiten Versuchs")
    check("chrome_neustart: Grund" in r["trail"] and "zweiter Versuch ja" in r["trail"] and "1. Versuch: code 'login'" in r["trail"],
          "vor Klick: Spur traegt Grund, ersten Versuch und „zweiter Versuch ja\"")
    check(r.get("chrome_neustart", {}).get("zweiter_versuch") is True and a.diagnosen and a.diagnosen[-1][0] == "chrome_neustart",
          "vor Klick: chrome_neustart-Info in der Antwort, Entscheidung nach puls_diagnose (schritt chrome_neustart)")
    check(a.url == "https://x/" and abs(a.zweite[0] - (250.0 - 30.0)) < 0.01, "vor Klick: Start-URL durchgereicht, Frist = Budget − verstrichen")

    # ── Wrapper: zweiter Fehler → Fehler-Ausgang des zweiten Versuchs unveraendert, kein weiterer Neustart ─────────────────────
    a = Attrappe(erg(code="login", schritt="login", msg="erst"), erg(code="ticket", schritt="ticket", msg="Contract nicht gewaehlt"), verstrichen=20.0)
    r = a.lauf("tsv2")
    check(a.neustarts == 1 and len(a.zweite) == 1 and len(a.ausgaben) == 1, "zweiter Fehler: ein Neustart, ein zweiter Versuch, eine Ausgabe")
    check(r.get("code") == "ticket" and r.get("msg") == "Contract nicht gewaehlt" and r.get("ok") is False and r.get("gesendet") is False,
          "zweiter Fehler: code/msg/gesendet des zweiten Versuchs unveraendert")
    check("2. Versuch: code ticket" in a.diagnosen[-1][1], "zweiter Fehler: Diagnose nennt den zweiten Versuch")

    # ── Wrapper: Fehler nach dem Klick ohne Positionsbeleg → kein zweiter Versuch, UNKLAR bleibt ──────────────────────────────
    unklar = erg(code="unklar", schritt="unklar", msg="Senden geklickt … Ergebnis UNKLAR", gesendet=True, retry_ok=False)
    a = Attrappe(unklar, erg(ok=True), lesung={"ok": True, "positionen_sichtbar": True, "pos_root": 1, "orders_gelesen": True, "orders_root": 0,
                                                "today_pnl": 0.0, "balance": 1.0}, verstrichen=70.0)
    r = a.lauf("tvv2")
    check(a.neustarts == 1 and a.lesungen == 1 and len(a.zweite) == 0, "nach Klick, Position da: Neustart + Lesung, KEIN zweiter Versuch")
    check(r.get("code") == "unklar" and r.get("gesendet") is True and r.get("retry_ok") is False and "UNKLAR" in r.get("msg"),
          "nach Klick, Position da: UNKLAR-Ausgang unveraendert (gesendet true, retry_ok false)")
    check("zweiter Versuch nein, weil Beleg fehlt" in r["trail"] and "Position(en) der Wurzel" in r["trail"], "nach Klick: Spur erklaert „zweiter Versuch nein, weil …\"")
    a = Attrappe(unklar, erg(ok=True), lesung={"ok": False, "msg": "Konto nicht erreicht"}, verstrichen=70.0)
    r = a.lauf("tvv2")
    check(len(a.zweite) == 0 and r.get("code") == "unklar", "nach Klick, Lesung scheitert: kein zweiter Versuch, UNKLAR bleibt")
    # Topstep: keine Order-Lesung → gar kein Neustart (Chrome bleibt stehen, Finn sieht dort nach)
    a = Attrappe(erg(code="beweis", schritt="beweis", msg="⚠ Ergebnis UNKLAR", gesendet=True, retry_ok=False, unklar=True), erg(ok=True), verstrichen=40.0)
    r = a.lauf("tsv2", mit_lesung=False)
    check(a.neustarts == 0 and len(a.zweite) == 0 and r.get("code") == "beweis" and r.get("unklar") is True,
          "Topstep nach Klick: kein Neustart, kein zweiter Versuch, Antwort unveraendert (unklar true)")
    check("chrome_neustart: nein" in r["trail"] and "UNKLAR bleibt" in r["trail"], "Topstep nach Klick: Spur traegt die Entscheidung")

    # ── Wrapper: nach dem Klick, Lesung leer (bewiesen nichts gesetzt) → zweiter Versuch ─────────────────────────────────────
    a = Attrappe(dict(unklar, today_pnl_start=-5.0, balance_start=100.0), erg(ok=True, msg="Order platziert", gesendet=True, bestaetigt=True),
                 lesung={"ok": True, "positionen_sichtbar": True, "pos_root": 0, "orders_gelesen": True, "orders_root": 0, "today_pnl": -5.0, "balance": 100.0},
                 verstrichen=70.0)
    r = a.lauf("tvv2")
    check(a.neustarts == 1 and a.lesungen == 1 and len(a.zweite) == 1 and r.get("ok") is True, "nach Klick, Lesung leer: zweiter Versuch laeuft")
    check("Beleg: keine Position, keine offene Order" in r["trail"] and "zweiter Versuch ja, weil die Lesung" in r["trail"], "nach Klick, Lesung leer: Beleg in der Spur")

    # ── Wrapper: Budget, Neustart scheitert, ok, Nie-Code ────────────────────────────────────────────────────────────────────────
    a = Attrappe(erg(code="login", msg="x"), erg(ok=True), verstrichen=200.0)
    r = a.lauf("tvv2")
    check(a.neustarts == 0 and len(a.zweite) == 0 and r.get("code") == "login" and "zu wenig Zeit" in r["trail"], "Budget knapp: kein Neustart, erster Fehler + Spur")
    a = Attrappe(erg(code="login", msg="x"), erg(ok=True), verstrichen=30.0, zeitsprung=200.0)
    r = a.lauf("tvv2")
    check(a.neustarts == 1 and len(a.zweite) == 0 and "nach dem Neustart zu wenig Zeit" in r["trail"], "Neustart dauerte zu lange: kein zweiter Versuch")
    a = Attrappe(erg(code="login", msg="x"), erg(ok=True), neustart_ok=False, verstrichen=30.0)
    r = a.lauf("tsv2")
    check(a.neustarts == 1 and len(a.zweite) == 0 and r.get("code") == "login" and "nicht sauber beenden" in r["trail"], "Chrome nicht beendet: erster Fehler-Ausgang")
    a = Attrappe(erg(ok=True, code="", msg="Order platziert"), erg(ok=True), verstrichen=30.0)
    r = a.lauf("tvv2")
    check(a.neustarts == 0 and len(a.ausgaben) == 1 and isinstance(a.ausgaben[0], str) and json.loads(a.ausgaben[0]).get("ok") is True,
          "erster Versuch ok: Ausgabe wortgleich (roh), kein Neustart")
    a = Attrappe(erg(code="handlauf", msg="laeuft"), erg(ok=True), verstrichen=5.0)
    r = a.lauf("tvv2")
    check(a.neustarts == 0 and r.get("code") == "handlauf" and "kein Chrome-Problem" in r["trail"], "handlauf: kein Neustart (anderer Lauf klickt gerade)")

    # ── _puls_chrome_beenden mit Attrappen (kein Chrome) ─────────────────────────────────────────────────────────────────────────
    alt = {n: getattr(ob, n) for n in ("_cdp_http", "_puls_chrome_prozesse", "_puls_prozesse_beenden", "_CdpVerbindung", "_warte")}
    try:
        ob._warte = lambda a_, b_: None
        ob._cdp_http = lambda pfad, methode="GET", timeout=2.0: None
        ob._puls_chrome_prozesse = lambda: []
        spur = []
        ok1, t1 = ob._puls_chrome_beenden(spur, warten_s=3.0, hart_ab_s=1.0)
        check(ok1 is True and "beendet" in t1 and any("antwortet nicht" in s for s in spur), "beenden: Port frei + keine Prozesse → sofort fertig, kein Browser.close")
        # Chrome haengt: Port antwortet immer, Browser.close wirkt nicht → nach hart_ab_s nur die eigenen PIDs, dann Zeitlimit → False
        getoetet = []

        class WS:
            def __init__(self, url, timeout=0):
                pass

            def rufe(self, m, params=None, timeout=0):
                if m == "SystemInfo.getProcessInfo":
                    return {"processInfo": [{"type": "renderer", "id": 11}, {"type": "browser", "id": 4242}]}
                return {}

            def zu(self):
                pass
        ob._CdpVerbindung = WS
        ob._cdp_http = lambda pfad, methode="GET", timeout=2.0: {"webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/browser/abc"}
        ob._puls_chrome_prozesse = lambda: [4242, 4243]
        ob._puls_prozesse_beenden = lambda pids: getoetet.append(sorted(pids))
        import time as _t
        echt_time = ob.time.time
        uhr = [1000.0]
        ob.time.time = lambda: uhr.__setitem__(0, uhr[0] + 0.5) or uhr[0]
        try:
            spur = []
            ok2, t2 = ob._puls_chrome_beenden(spur, warten_s=6.0, hart_ab_s=2.0)
        finally:
            ob.time.time = echt_time
        check(ok2 is False and "nicht beendet" in t2 and getoetet == [[4242, 4243]],
              "beenden: haengt → genau einmal taskkill auf die eigenen PIDs (CDP-Browser-PID + Profil-Filter), Zeitlimit → False")
        check(any("Browser.close" in s and "PID 4242" in s for s in spur), "beenden: Spur nennt Browser.close und die Browser-PID")
    finally:
        for n, f in alt.items():
            setattr(ob, n, f)

    # ── _puls_lauf_abfangen: echter stdout fuer den Wachhund, letzte Zeile = JSON ────────────────────────────────────────────────
    gesehen = []

    def lauf_():
        gesehen.append(ob._PULS_AUSGABE_ECHT.get("stdout") is not None and ob._PULS_AUSGABE_ECHT["stdout"] is not sys.stdout)
        print("Zwischenzeile")
        print(json.dumps({"ok": False, "code": "x"}))
    roh, res = ob._puls_lauf_abfangen(lauf_)
    check(gesehen == [True] and ob._PULS_AUSGABE_ECHT.get("stdout") is None and res.get("code") == "x" and roh.startswith("Zwischenzeile"),
          "abfangen: echter stdout waehrend des Laufs gemerkt und danach geloescht, letzte Zeile als Antwort")
    puffer, echt = io.StringIO(), sys.stdout
    sys.stdout = puffer
    try:
        ob._puls_antwort_drucken("roh-text")
        ob._puls_antwort_drucken({"ok": True, "msg": "ü"})
    finally:
        sys.stdout = echt
    z = puffer.getvalue().strip().splitlines()
    check(z[0] == "roh-text" and json.loads(z[1]) == {"ok": True, "msg": "ü"}, "drucken: Text wortgleich, dict als JSON")

    # ── Frist des Topstep-Laufs ──────────────────────────────────────────────────────────────────────────────────────────────────
    sp = ob._StempelSpur()
    check(abs(ob._tsx_frist(sp) - ob.TSX_K3_WACHHUND_S) < 0.01 and abs(ob._tsx_frist([]) - ob.TSX_K3_WACHHUND_S) < 0.01, "_tsx_frist: ohne eigene Frist = TSX_K3_WACHHUND_S")
    sp.frist_s = 95.0
    check(abs(ob._tsx_frist(sp) - 95.0) < 0.01, "_tsx_frist: eigene Frist der Spur zaehlt")
    check("frist_s" in inspect.signature(ob.modus_tsxlesen_cdp).parameters, "modus_tsxlesen_cdp nimmt frist_s (zweiter Versuch mit Restzeit)")
    check("PULS_NEUSTART_NIE" in dir(ob) and "zeit" in ob.PULS_NEUSTART_NIE and ob.PULS_NEUSTART_BUDGET_S["tsv2"] < 170 and ob.PULS_NEUSTART_BUDGET_S["tvv2"] < 260,
          "Budgets liegen unter den Panel-Zeitlimits (tsx-konto 170 s, tv-konto 260 s)")
    check(len(ob.PULS_ERGEBNIS_FELDER) == 47 and "unklar" in ob.PULS_ERGEBNIS_FELDER and "warnung" in ob.PULS_ERGEBNIS_FELDER,
          "PULS_ERGEBNIS_FELDER unveraendert (47 Felder, unklar/warnung)")

    # ── Abriss der CDP-Verbindung (08.10.2026, Muster WinError 10053): sanft neu anhängen statt Chrome-Neustart ──────────────────
    ab = ob.cdp_abriss_erkannt
    m10053 = "Puls-Chrome/CDP: ConnectionAbortedError: [WinError 10053] Eine bestehende Verbindung wurde softwaregesteuert abgebrochen — nichts gesendet."
    check(ab(erg(code="cdp_fehler", schritt="cdp", msg=m10053)) and ab(erg(code="cdp_fehler", msg="Puls-Chrome/CDP: ConnectionError: CDP-Verbindung zu — nichts gesendet."))
          and ab(erg(code="cdp_fehler", msg="Puls-Chrome/CDP: RuntimeError: CDP-Handshake abgelehnt: HTTP/1.1 500")),
          "Abriss erkannt: 10053, CDP-Verbindung zu, Handshake")
    check(not ab(erg(code="cdp_fehler", msg="Puls-Chrome/CDP: TimeoutError: timed out — nichts gesendet."))
          and not ab(erg(code="konto", msg=m10053)) and not ab(erg(code="cdp_fehler", msg=m10053, gesendet=True))
          and not ab(erg(code="unklar", msg=m10053, gesendet=True, retry_ok=False)) and not ab(erg(ok=True, msg=m10053)) and not ab(None),
          "kein Abriss: Zeitüberschreitung, anderer Code, nach dem Klick, ok, None")

    class Sanft(Attrappe):
        def __init__(self, *a, sanft_ok=True, **k):
            super().__init__(*a, **k)
            self.sanft_ok, self.sanfte = sanft_ok, 0

        def sanft(self, spur):
            self.sanfte += 1
            spur.append("Attrappe: neu anhängen")
            return self.sanft_ok

        def lauf(self, weg="tvv2", mit_lesung=True):
            return ob._puls_mit_neustart(weg, self.erster, self.zweiter, self.lesung if mit_lesung else None, "https://x/",
                                         neustart=self.neustart, jetzt=self.jetzt, t0=0.0, ausgeben=self.ausgeben, diagnose=self.diagnose,
                                         neustart_sanft=self.sanft)
    a1 = Sanft(erg(code="cdp_fehler", schritt="cdp", msg=m10053), erg(ok=True, gesendet=True, bestaetigt=True), verstrichen=30.0)
    r = a1.lauf()
    check(a1.sanfte == 1 and a1.neustarts == 0 and len(a1.zweite) == 1 and r.get("ok") and r.get("chrome_neustart", {}).get("neu_angehaengt") is True
          and "neu anhängen" in r.get("trail", ""), "Abriss vor dem Klick: nur neu angehängt (kein Chrome-Neustart), zweiter Versuch läuft, ok")
    a2 = Sanft(erg(code="cdp_fehler", schritt="cdp", msg=m10053), erg(ok=True, gesendet=True, bestaetigt=True), verstrichen=30.0, sanft_ok=False)
    r = a2.lauf()
    check(a2.sanfte == 1 and a2.neustarts == 1 and r.get("ok") and r.get("chrome_neustart", {}).get("neu_gestartet") is True,
          "Chrome/Tab weg (sanft False) → harter Neustart wie bisher")
    a3 = Sanft(erg(code="login", schritt="login"), erg(ok=True, gesendet=True, bestaetigt=True), verstrichen=30.0)
    a3.lauf()
    check(a3.sanfte == 0 and a3.neustarts == 1, "kein Abriss (login) → sanfter Weg nicht gefragt, Chrome-Neustart")
    a4 = Sanft(erg(code="unklar", schritt="unklar", msg=m10053, gesendet=True, retry_ok=False), erg(ok=True), verstrichen=60.0)
    a4.lesung_res = {"ok": False, "msg": "x"}
    a4.lauf()
    check(a4.sanfte == 0 and len(a4.zweite) == 0, "Abriss NACH dem Klick → kein sanfter Weg, kein zweiter Versuch (UNKLAR bleibt)")
    print("\nALLES OK" if OK else "\nFEHLER")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
