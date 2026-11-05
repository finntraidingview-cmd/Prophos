#!/usr/bin/env python3
"""Selbsttest FW1 (Master 05.11.2026, Hinweis S2 aus UNT2): Die Fenster-Wache bewacht auch die Pläne jeder aktiven Verwalter-Gruppe, und zwar
mit dem Stand IHRES Unternehmens (je Unternehmen getrennt). HT bleibt bitgleich. Ist ein Gruppen-Stand nicht lesbar, wird nur diese Gruppe
übersprungen und gemeldet.
Ohne Netz: ap_fenster_wache_tick (+ _ap_fenster_wache_lauf) aus app.py; Stand, Gruppen und DB sind gestellt. BASIS = app.py aus dem
main-Commit vor FW1 (git show).
  1 ohne Gruppen: NEU == BASIS (Ergebnis + jede Umplanung, gleicher Zufall)
  2 mit Gruppen: HT-Teil == BASIS (zuerst, gleicher Zufall); danach jede Gruppe gegen ihren eigenen Stand (eigene = ihre IDs)
  3 Gruppen-Stand nicht lesbar → nur diese Gruppe übersprungen + gemeldet (_ap_fenster_wache["gruppen"]); HT und andere Gruppen laufen
  4 Gruppen-Liste nicht lesbar → HT == BASIS, Meldung _liste
  5 Unternehmen gesperrt (ap_unt_je_uid) → Gruppen-Pläne bleiben stehen
  6 inaktive Gruppe: nur_aktiv=True (wie der Waage-Takt)
  8 HT-Stand nicht lesbar → Gruppen laufen trotzdem, HT-Fehler fliegt danach (Aufrufer meldet wie bisher)
Aufruf: python3 tools/selftest_fw1_fenster_wache_gruppen.py [basis-commit]"""
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
BASIS = "03f4e0e9"   # main .2073 (UNT2 live), Stand vor FW1 — main-Commit, nie ein Branch-SHA

FEHLER = []
HT1, HT2, E1, E2, K1 = "ht-1", "ht-2", "emin-v", "emin-m", "kaputt-v"
G_EMIN = {"gruppe_id": "g-emin", "name": "Emin", "ids": frozenset({E1, E2}), "aktiv": True}
G_KAPUTT = {"gruppe_id": "g-kaputt", "name": "Kaputt", "ids": frozenset({K1}), "aktiv": True}
G_AUS = {"gruppe_id": "g-aus", "name": "Aus", "ids": frozenset({"aus-v"}), "aktiv": False}
MITTERNACHT = datetime(2026, 11, 5, tzinfo=timezone.utc)


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def block(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


def plan(pid, uid, start):
    return {"plan_id": pid, "user_id": uid, "firma": "F", "firma_name": "F", "route": "tvv2", "richtung": "buy", "start_min": start}


ALLE = [plan("p-ht-1", HT1, 1100), plan("p-ht-2", HT2, 1200), plan("p-ht-ok", HT1, 500),
        plan("p-em-1", E1, 1150), plan("p-em-2", E2, 1300), plan("p-k-1", K1, 1250)]


def lade(src, welt):
    ns = {"time": __import__("time"), "random": random, "timedelta": timedelta, "datetime": datetime, "timezone": timezone,
          "AP_FENSTER_WACHE_TAKT_S": 600, "_ap_fenster_wache": {"at": 0.0, "verschoben": [], "fehler": ""}, "AP_7T_TZ": "UTC",
          "AP_CFD_ROUTEN": ("mt5",), "print": lambda *a, **k: welt["log"].append(" ".join(str(x) for x in a))}
    ns.update(welt["stubs"])
    namen = ["ap_fenster_wache_tick", "_ap_fenster_wache_lauf", "ap_unt_wache_reg"]
    exec("\n\n".join(block(src, n) for n in namen if f"\ndef {n}(" in src), ns)
    return ns


def welt_bauen(gruppen=(G_EMIN,), kaputt=(), liste_fehler=False, gesperrt=None, ht_kaputt=False):
    w = {"log": [], "stand_aufrufe": [], "umpl": []}
    g_ids = set().union(*[g["ids"] for g in gruppen]) if gruppen else set()
    alle_gruppen_ids = {E1, E2, K1, "aus-v"}

    def stand_laden(reg, jetzt=None, **kw):
        eig = kw.get("eigene")
        w["stand_aufrufe"].append(None if eig is None else frozenset(eig))
        if (eig is not None and set(eig) & set(kaputt)) or (eig is None and ht_kaputt):
            raise RuntimeError("Stand nicht lesbar")
        pl = [dict(p) for p in ALLE if (p["user_id"] not in alle_gruppen_ids if eig is None else p["user_id"] in eig)]
        return {"offen": [], "param": {"laufzeit_min": 60}, "jetzt_min": 600.0, "mitternacht": MITTERNACHT, "starts_heute": [],
                "id_fest": {}, "zeiten": {"bis": 1000}, "plaene": pl, "eigene": eig}

    def planer_gruppen(nur_aktiv=False):
        w["nur_aktiv"] = nur_aktiv
        if liste_fehler:
            raise RuntimeError("id_gruppen nicht lesbar")
        return [g for g in gruppen if g["aktiv"] or not nur_aktiv]

    def ueberhang(xs, zt, jm):
        return [(x, zt["bis"]) for x in xs if float(x["start_min"]) > float(zt["bis"])]

    def nachhol(x, plaene, starts, fest, jm, zt, lz, laufend, rnd=None, ab_min=None):
        return round(ab_min + rnd.random(), 4), None

    def anwenden(stand, aend, wer):
        w["umpl"].append((stand.get("eigene") and tuple(sorted(stand["eigene"])), aend[0]["plan_id"], aend[0]["nach_start_min"]))
        return [aend[0]], None

    w["stubs"] = {"sb_select": lambda t, q: [{"aktiv": True, "user_ids": [HT1, HT2]}], "ap_menge_wache": lambda j, r: None,
                  "ap_bal_wache": lambda j: None, "_ap_stand_laden": stand_laden, "_ap_stand_plaene": lambda st: st["plaene"],
                  "ap_unt_je_uid": lambda reg: ({}, set() if gesperrt is None else gesperrt),
                  "ap_fenster_ueberhang": ueberhang, "ap_nachhol_minute": nachhol, "_ap_tz": lambda n: timezone.utc,
                  "_ap_hhmm_txt": lambda m: str(m), "_ap_aenderungen_anwenden": anwenden, "ap_planer_gruppen": planer_gruppen,
                  "_ap_namen": lambda: ({u: u for u in (HT1, HT2, E1, E2, K1)}, set()),
                  "ap_gruppe_ausgeblendet": lambda namen, ids: {str(u) for u in namen} - {str(u) for u in ids}}
    return w


def lauf(src, **kw):
    w = welt_bauen(**kw)
    ns = lade(src, w)
    reg = {"aktiv": True, "user_ids": [HT1, HT2], "zeiten": {"fenster": None}}
    erg = ns["ap_fenster_wache_tick"](MITTERNACHT + timedelta(hours=10), reg=reg, rnd=random.Random(7))
    return erg, w, ns


def main():
    basis = sys.argv[1] if len(sys.argv) > 1 else BASIS
    neu = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    alt = subprocess.run(["git", "-C", WURZEL, "show", f"{basis}:app.py"], capture_output=True, text=True).stdout
    if not alt:
        print(f"✗ BASIS {basis} nicht lesbar")
        sys.exit(1)

    # 1 ohne Gruppen: bitgleich
    e_a, w_a, _ = lauf(alt, gruppen=())
    e_n, w_n, ns_n = lauf(neu, gruppen=())
    check(e_a == e_n and w_a["umpl"] == w_n["umpl"] and len(e_n) == 2,
          f"1 ohne Gruppen: Ergebnis + Umplanungen BITGLEICH zur BASIS ({len(e_n)} HT-Pläne vorgezogen)")

    # 2 mit Gruppen: HT-Teil bitgleich (zuerst), danach Emin gegen seinen eigenen Stand
    e_a, w_a, _ = lauf(alt)
    e_n, w_n, ns_n = lauf(neu)
    ht_n = [u for u in w_n["umpl"] if u[0] is None]
    check(w_a["umpl"] == ht_n == w_n["umpl"][:len(ht_n)] and e_n[:len(e_a)] == e_a,
          "2a HT-Teil == BASIS (gleiche Pläne, gleiche Minuten, gleicher Zufall, zuerst)")
    em = [u for u in w_n["umpl"] if u[0] == tuple(sorted(G_EMIN["ids"]))]
    check({u[1] for u in em} == {"p-em-1", "p-em-2"} and len(w_n["umpl"]) == len(ht_n) + 2,
          "2b Emins Pläne hinter dem Fenster vorgezogen — mit Emins Stand (eigene = seine IDs), kein HT-Plan doppelt")
    check(not any(u[1].startswith("p-em") for u in w_a["umpl"]), "2c BASIS ließ Emins Pläne liegen (das war die Lücke)")
    check(w_n["stand_aufrufe"] == [None, frozenset(G_EMIN["ids"])], "2d Stände: zuerst HT (eigene=None), dann je Gruppe genau ihre IDs")
    st = ns_n["_ap_fenster_wache"].get("gruppen") or {}
    check(st.get("g-emin", {}).get("verschoben") == 2 and not st["g-emin"]["fehler"], "2e Status je Gruppe (_ap_fenster_wache.gruppen)")

    # 3 ein Gruppen-Stand nicht lesbar
    e_n, w_n, ns_n = lauf(neu, gruppen=(G_KAPUTT, G_EMIN), kaputt=(K1,))
    st = ns_n["_ap_fenster_wache"].get("gruppen") or {}
    check("nicht lesbar" in (st.get("g-kaputt") or {}).get("fehler", "") and st.get("g-emin", {}).get("verschoben") == 2
          and not any(u[1] == "p-k-1" for u in w_n["umpl"]) and any("übersprungen" in z for z in w_n["log"]),
          "3 Gruppe „Kaputt“ nicht lesbar → nur sie übersprungen + gemeldet; Emin und HT laufen")
    check([u for u in w_n["umpl"] if u[0] is None] == w_a["umpl"], "3b HT trotzdem == BASIS")

    # 4 Gruppen-Liste nicht lesbar
    e_n, w_n, ns_n = lauf(neu, liste_fehler=True)
    st = ns_n["_ap_fenster_wache"].get("gruppen") or {}
    check(w_n["umpl"] == w_a["umpl"] and "_liste" in st and any("Gruppen nicht lesbar" in z for z in w_n["log"]),
          "4 Gruppen-Liste nicht lesbar → HT == BASIS, Gruppen gemeldet")

    # 5 Unternehmen gesperrt → Gruppen-Pläne bleiben
    e_n, w_n, _ = lauf(neu, gesperrt={E1, E2})
    check(not any(u[1].startswith("p-em") for u in w_n["umpl"]) and [u for u in w_n["umpl"] if u[0] is None] == w_a["umpl"],
          "5 Regel des Unternehmens nicht lesbar (gesperrt) → Emins Pläne unberührt, HT == BASIS")

    # 6 nur aktive Gruppen
    e_n, w_n, _ = lauf(neu, gruppen=(G_EMIN, G_AUS))
    check(w_n.get("nur_aktiv") is True and frozenset(G_AUS["ids"]) not in w_n["stand_aufrufe"], "6 nur aktive Gruppen (nur_aktiv=True wie der Waage-Takt)")

    # 8 HT-Stand nicht lesbar → Gruppen laufen trotzdem, der HT-Fehler fliegt danach wie bisher (Aufrufer setzt fehler)
    w = welt_bauen(ht_kaputt=True)
    ns = lade(neu, w)
    try:
        ns["ap_fenster_wache_tick"](MITTERNACHT + timedelta(hours=10), reg={"aktiv": True, "user_ids": [HT1, HT2], "zeiten": {}}, rnd=random.Random(7))
        flog = False
    except RuntimeError:
        flog = True
    check(flog and {u[1] for u in w["umpl"]} == {"p-em-1", "p-em-2"}, "8 HT-Stand nicht lesbar → Emin trotzdem bewacht, HT-Fehler fliegt danach (wie BASIS)")

    # 7 Quelltext-Vertrag
    tick = block(neu, "ap_fenster_wache_tick")
    check('eigene=gr["ids"]' in tick and "ap_planer_gruppen(nur_aktiv=True)" in tick and tick.index("_ap_fenster_wache_lauf(reg, stand,")
          < tick.index("ap_planer_gruppen("), "7 Quelltext: HT-Lauf vor den Gruppen, Gruppen-Stand mit eigene=gr[\"ids\"]")

    print()
    print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
