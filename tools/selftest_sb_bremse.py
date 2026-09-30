#!/usr/bin/env python3
"""Selbsttest Supabase-Bremse (app.py, AUSFALL-BREMSE, 01.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_sb_bremse.py
Lädt die Bremse per Quelltext aus app.py (app.py zieht beim Import Flask und startet Threads). Prüft die Zustandsmaschine mit
falscher Uhr (öffnet nach SB_BREMSE_N Fehlern, Nachzügler verlängern nicht, genau eine Probe, Stufen 30 → 60 → 120, Erfolg
schließt, kritisch geht durch, 4xx zählen nicht, 5xx schon) und _sb_anfrage mit einem gestellten requests und 48 echten
Threads: nie zwei Proben gleichzeitig, gesperrte Anfragen gehen gar nicht erst raus."""
import os
import re
import sys
import threading
import time
import types

import requests as echtes_requests

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade(fake_requests):
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def zuweisung(name):
        i = src.index(f"\n{name} = ") + 1
        return src[i:src.index("\n", i)]

    i = src.index("class SupabaseGesperrt(")
    klasse = src[i:src.find("\n\n\n", i)]
    ns = {"requests": fake_requests, "threading": threading, "time": time, "SUPABASE_URL": "https://beispiel.invalid",
          "SUPABASE_SERVICE_KEY": "x", "_sb_headers": lambda prefer=None: {}}
    code = "\n".join([zuweisung(n) for n in ("SB_BREMSE_N", "SB_BREMSE_STUFEN", "SB_BREMSE_HALB_S", "SB_TIMEOUT", "SB_PROBE_TIMEOUT")]
                     + [klasse] + [block(n) for n in ("sb_bremse_neu", "sb_bremse_vorher", "sb_bremse_nach")]
                     + ['_SB_BREMSE = {"rest": sb_bremse_neu(), "auth": sb_bremse_neu()}', "_SB_BREMSE_LOCK = threading.Lock()",
                        '_SB_GEHEILT_AT = {"rest": 0.0, "auth": 0.0}']
                     + [block(n) for n in ("_sb_bremse_melden", "schleifen_pause", "_ist_db_fehler", "sb_bremse_stand",
                                           "sb_bremse_rest_s", "_sb_probe", "_sb_anfrage", "_sb_pruefen")])
    exec(code, ns)
    return ns


class Antwort:
    def __init__(self, status):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise echtes_requests.exceptions.HTTPError(f"http {self.status_code}", response=self)


def main():
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    # gestelltes requests: exceptions wie echt, request/get steuerbar
    lage = {"modus": "timeout", "proben": 0, "anfragen": 0, "probe_gleichzeitig": 0, "probe_max": 0}
    sperre = threading.Lock()

    def request(methode, url, timeout=None, **kw):
        with sperre:
            lage["anfragen"] += 1
        time.sleep(0.002)
        if lage["modus"] == "timeout":
            raise echtes_requests.exceptions.ReadTimeout("hängt")
        return Antwort(lage.get("status", 200))

    def get(url, params=None, headers=None, timeout=None):
        with sperre:
            lage["proben"] += 1
            lage["probe_gleichzeitig"] += 1
            lage["probe_max"] = max(lage["probe_max"], lage["probe_gleichzeitig"])
        try:
            time.sleep(0.05)
            if lage["modus"] == "timeout":
                raise echtes_requests.exceptions.ConnectTimeout("hängt")
            return Antwort(200)
        finally:
            with sperre:
                lage["probe_gleichzeitig"] -= 1

    fake = types.SimpleNamespace(exceptions=echtes_requests.exceptions, request=request, get=get)
    a = lade(fake)
    V, N, neu = a["sb_bremse_vorher"], a["sb_bremse_nach"], a["sb_bremse_neu"]
    ST = a["SB_BREMSE_STUFEN"]

    # 1) Zustandsmaschine mit falscher Uhr
    z = neu()
    for i in range(a["SB_BREMSE_N"] - 1):
        N(z, 100.0 + i, False)
    check(z["stufe"] == -1 and V(z, 104.0)[0] == "frei", f"{a['SB_BREMSE_N'] - 1} Fehler: noch frei")
    N(z, 104.0, False)
    check(z["stufe"] == 0 and V(z, 105.0) == ("zu", 104.0 + ST[0] - 105.0), f"{a['SB_BREMSE_N']}. Fehler: gesperrt für {ST[0]} s")
    N(z, 110.0, False)
    check(z["offen_bis"] == 104.0 + ST[0] and z["folge"] == a["SB_BREMSE_N"], "Nachzügler-Fehler verlängern nicht")
    check(V(z, 105.0, kritisch=True)[0] == "frei", "kritisch geht durch, obwohl gesperrt")
    t = 104.0 + ST[0] + 1
    check(V(z, t)[0] == "probe", "nach Ablauf: genau eine Probe")
    z["probe"] = True
    check(V(z, t) == ("zu", float(a["SB_BREMSE_HALB_S"])), f"während der Probe: gesperrt mit {a['SB_BREMSE_HALB_S']} s (nie 0)")
    N(z, t, False, probe=True)
    check(z["stufe"] == 1 and z["offen_bis"] == t + ST[1] and not z["probe"], f"Probe gescheitert: Stufe 2 = {ST[1]} s")
    N(z, t + ST[1] + 1, False, probe=True)
    N(z, t + 999, False, probe=True)
    check(z["stufe"] == len(ST) - 1 and z["offen_bis"] == t + 999 + ST[-1], f"Stufen gedeckelt bei {ST[-1]} s")
    N(z, t + 1200, True, probe=True)
    check(z["stufe"] == -1 and z["folge"] == 0 and V(z, t + 1200)[0] == "frei", "Erfolg schließt die Sicherung")
    z2 = neu()
    N(z2, 1.0, False)
    N(z2, 2.0, True)
    check(z2["folge"] == 0, "ein Erfolg setzt die Fehlerfolge zurück (nur in Folge zählt)")

    # 2) _sb_anfrage: 5xx zählen, 4xx nicht; Ausnahmen tragen sb_netz
    lage.update(modus="ok", status=404)
    r = a["_sb_anfrage"]("GET", "u")
    check(r.status_code == 404 and a["_SB_BREMSE"]["rest"]["folge"] == 0, "404 zählt nicht als Fehler")
    lage.update(status=503)
    r = a["_sb_anfrage"]("GET", "u")
    try:
        a["_sb_pruefen"](r)
        markiert = False
    except echtes_requests.exceptions.HTTPError as e:
        markiert = getattr(e, "sb_netz", False)
    check(a["_SB_BREMSE"]["rest"]["folge"] == 1 and markiert, "503 zählt und wird als sb_netz markiert")
    lage.update(modus="timeout")
    try:
        a["_sb_anfrage"]("GET", "u")
        netz = False
    except echtes_requests.exceptions.ReadTimeout as e:
        netz = getattr(e, "sb_netz", False)
    check(netz and a["_SB_BREMSE"]["rest"]["folge"] == 2, "Timeout zählt, Ausnahme trägt sb_netz")

    # 3) 48 Threads: nach dem Öffnen gehen keine Anfragen mehr raus, nie zwei Proben gleichzeitig
    a["_SB_BREMSE"]["rest"] = neu()
    lage.update(modus="timeout", anfragen=0, proben=0, probe_max=0)
    ergebnisse = {"gesperrt": 0, "timeout": 0}
    el = threading.Lock()

    def lauf():
        for _ in range(5):
            try:
                a["_sb_anfrage"]("GET", "u")
            except a["SupabaseGesperrt"]:
                with el:
                    ergebnisse["gesperrt"] += 1
            except echtes_requests.exceptions.RequestException:
                with el:
                    ergebnisse["timeout"] += 1

    th = [threading.Thread(target=lauf) for _ in range(48)]
    [x.start() for x in th]
    [x.join() for x in th]
    check(ergebnisse["gesperrt"] > 0 and lage["anfragen"] < 48 * 5, f"48 Threads × 5: {lage['anfragen']} Anfragen raus, "
          f"{ergebnisse['gesperrt']} sofort gesperrt (ohne Bremse wären es 240 × Timeout)")
    check(a["_SB_BREMSE"]["rest"]["stufe"] == 0, "Sicherung offen auf Stufe 1")
    # Ablauf simulieren: Probe fällig, alle Threads gleichzeitig — genau eine Probe
    a["_SB_BREMSE"]["rest"]["offen_bis"] = time.time() - 1
    lage.update(proben=0, probe_max=0, anfragen=0)
    th = [threading.Thread(target=lauf) for _ in range(48)]
    [x.start() for x in th]
    [x.join() for x in th]
    check(lage["proben"] == 1 and lage["probe_max"] == 1, f"Probe fällig bei 48 Threads: genau {lage['proben']} Probe, "
          f"höchstens {lage['probe_max']} gleichzeitig")
    check(a["_SB_BREMSE"]["rest"]["stufe"] == 1 and lage["anfragen"] == 0, "Probe gescheitert → Stufe 2, keine echte Anfrage raus")
    # Erholung: Probe gelingt, danach geht die eigentliche Anfrage raus
    a["_SB_BREMSE"]["rest"]["offen_bis"] = time.time() - 1
    lage.update(modus="ok", status=200, proben=0, anfragen=0)
    r = a["_sb_anfrage"]("GET", "u")
    check(r.status_code == 200 and lage["proben"] == 1 and lage["anfragen"] == 1 and a["_SB_BREMSE"]["rest"]["stufe"] == -1,
          "Erholung: eine Probe, dann die Anfrage selbst, Sicherung zu")
    check(a["_SB_GEHEILT_AT"]["rest"] > 0, "Heil-Zeitpunkt gesetzt (Karenz der Reader-Wacht)")
    st = a["sb_bremse_stand"]()
    check(st["rest"]["zustand"] == "normal" and st["auth"]["zustand"] == "normal" and "letzter" not in st["rest"],
          "Stand für /health: normal, keine Fehlertexte nach außen")

    # 3b) Schleifen-Pausen: ohne DB-Fehler Takt; Wächter ohne Exponential (≤ 120 s), Kompass/Reader-Wacht verdoppeln bis 300 s
    P = a["schleifen_pause"]
    check(P(30, 0, 0, 120, verdoppeln=False) == 30 and P(30, 5, 0, 120, verdoppeln=False) == 30
          and P(30, 3, 55, 120, verdoppeln=False) == 55 and P(30, 3, 999, 120, verdoppeln=False) == 120,
          "Wächter: Takt, mindestens bis die Sicherung fragt, höchstens 120 s — kein Exponential")
    check([P(60, n, 0, 300) for n in range(5)] == [60, 120, 240, 300, 300] and P(30, 1, 100, 300) == 100,
          "Kompass/Reader-Wacht: 60 → 120 → 240 → 300 s, Rest der Sicherung als Untergrenze")

    # 4) /puls-regel: Fehl-Cache — ohne guten Stand 10 s lang False ohne DB-Read; Netzfehler lösen keinen Rückfall-Read aus
    src = open(APP, encoding="utf-8").read()
    i = src.index("def puls_regel_stand(")
    ns = {"_PULS_REGEL_CACHE": {"at": 0.0, "cdp": [], "tsx": [], "gut": False, "tsx_gut": False}, "PULS_REGEL_CACHE_S": 10}
    exec(src[i:src.find("\n\n\n", i)], ns)
    R, reads = ns["puls_regel_stand"], []

    class Netz(Exception):
        sb_netz = True

    def lesen_netz(tab, params):
        reads.append(params["select"])
        raise Netz("Timeout")
    check(R(1000.0, lesen_netz) is False and reads == ["puls_augen_cdp,puls_topstep_pcs"],
          "DB weg ohne guten Stand: False, genau EIN Read (kein Rückfall-Read bei Netzfehler)")
    check(R(1005.0, lesen_netz) is False and len(reads) == 1, "5 s später: False aus dem Fehl-Cache, kein weiterer Read")
    check(R(1011.0, lesen_netz) is False and len(reads) == 2, "nach 11 s: neuer Versuch")

    print("\nALLES OK" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
