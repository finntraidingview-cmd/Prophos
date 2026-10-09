#!/usr/bin/env python3
"""Selbsttest BOT-STAND ERST NACH DEM ABRUF MERKEN (mt5-copier/panel.py ensure_bot_source + _version_watcher, 09.10.2026, Push e621d2b:
ein Panel bekam beim Umschalten von Railway den neuen Stand, der Abruf von order_bot.py scheiterte — der Watcher hielt den Stand
trotzdem für erledigt und holte bis zum nächsten Push nie nach). Mit Attrappen: kein Netz, kein Neustart, temporärer Ordner.

Aufruf:  python3 tools/selftest_panel_bot_nachholen.py
Prueft: (1) Abruf scheitert → geholt_sha bleibt alt, Datei unverändert; (2) Inhalt gleich → geholt_sha = Stand; (3) Watcher: erster
Takt scheitert → zweiter Takt holt nach, danach kein weiterer Abruf; (4) Versatz nach Fehlschlag gestreut (nicht fix) und ≥ 2 s;
(5) Watcher startet von geholt_sha, nicht vom bloß angefragten sha."""
import os
import random
import re
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HIER, "..", "mt5-copier", "panel.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def stueck(src, anfang, ende):
    i = src.index(anfang)
    return src[i:src.index(ende, i + 1)]


SRC = open(PANEL, encoding="utf-8").read()
CODE = stueck(SRC, "\ndef ensure_bot_source(", "\ndef ensure_pywinauto(") + stueck(SRC, "\ndef _version_watcher(", "\ndef _selbst_auffrischen(")
GUT = b"def run(cfg, cmd):\n    return 1\n" + b"# " + b"x" * 600 + b"\n"
NEU = GUT.replace(b"return 1", b"return 2")


class Stopp(Exception):
    pass


class Exit(Exception):
    pass


def umgebung(ordner, dateien, shas, sleep_log, runden, version=b"2026-09-22.9999\n", panel_neu=None, log=None):
    """Namensraum mit Attrappen: repo_datei liefert je Aufruf den nächsten Eintrag aus `dateien` (Exception = Abruf scheitert)."""
    folge, sha_folge = list(dateien), list(shas)
    abrufe = []

    def repo_datei(pfad, sha=None, timeout=15):
        if pfad.endswith("VERSION"):
            return version
        abrufe.append(sha)
        x = folge.pop(0) if folge else GUT
        if isinstance(x, Exception):
            raise x
        return x

    def schlafen(s):
        sleep_log.append(s)
        if s == 15 and len([x for x in sleep_log if x == 15]) > runden:
            raise Stopp()

    zeit = type("Zeit", (), {"sleep": staticmethod(schlafen), "time": staticmethod(time.time)})
    log = log if log is not None else {}
    log.setdefault("geaendert", []); log.setdefault("uebernommen", []); log.setdefault("print", [])

    def geaendert(sha):
        log["geaendert"].append(sha)
        return sha == panel_neu

    def raus(code):
        raise Exit()

    os_attrappe = type("OsA", (), {"path": os.path, "replace": staticmethod(os.replace), "_exit": staticmethod(raus)})
    ns = {"_panel_code_geaendert": geaendert, "_version_uebernehmen": lambda v: log["uebernommen"].append(v),
          "os": os_attrappe, "re": re, "random": random, "time": zeit, "print": lambda *a, **k: log["print"].append(" ".join(map(str, a))), "HERE": ordner,
          "BOT_STAND": {"sha": None, "version": None, "geholt_sha": None}, "repo_datei": repo_datei,
          "repo_sha": lambda timeout=8: sha_folge.pop(0) if sha_folge else "b" * 40,
          "PROV_JOB": None, "TV_ORDER_LOCK": __import__("threading").Lock(), "MASTER_ORDER_LOCKS": {}}
    exec(compile(CODE, "panel_ausschnitt", "exec"), ns)
    return ns, abrufe


with tempfile.TemporaryDirectory() as d:
    datei = os.path.join(d, "order_bot.py")
    with open(datei, "wb") as f:
        f.write(GUT)

    # (1) Abruf scheitert
    ns, _ = umgebung(d, [ConnectionResetError("Railway-Umschaltung")], [], [], 0)
    ns["BOT_STAND"]["geholt_sha"] = "a" * 40
    ns["ensure_bot_source"]("b" * 40)
    check(ns["BOT_STAND"]["geholt_sha"] == "a" * 40, "Abruf scheitert → geholt_sha bleibt beim alten Stand")
    check(open(datei, "rb").read() == GUT, "Abruf scheitert → order_bot.py unverändert")

    # (2) gleicher Inhalt → liegt vor
    ns, _ = umgebung(d, [GUT], [], [], 0)
    ns["ensure_bot_source"]("c" * 40)
    check(ns["BOT_STAND"]["geholt_sha"] == "c" * 40, "Inhalt schon gleich → geholt_sha = Stand (kein Dauer-Nachholen)")

    # (3)+(4) Watcher: Takt 1 scheitert, Takt 2 holt nach, Takt 3 ruft nicht mehr ab
    schlaf = []
    ns, abrufe = umgebung(d, [ConnectionResetError("weg"), NEU], ["b" * 40, "b" * 40, "b" * 40], schlaf, 3)
    ns["BOT_STAND"]["geholt_sha"] = "a" * 40
    try:
        ns["_version_watcher"]("2026-09-22.9999")
    except Stopp:
        pass
    check(abrufe == ["b" * 40, "b" * 40], f"Takt 1 scheitert, Takt 2 holt nach, Takt 3 ruft nicht mehr ab (Abrufe {len(abrufe)})")
    check(open(datei, "rb").read() == NEU, "nach dem Nachholen liegt der neue order_bot.py auf der Platte")
    check(ns["BOT_STAND"]["geholt_sha"] == "b" * 40, "geholt_sha = neuer Stand")
    versatz = [x for x in schlaf if x != 15]
    check(len(versatz) == 1 and 2 <= versatz[0] <= 10, f"genau ein Zufalls-Versatz nach dem Fehlschlag (2–10 s): {versatz}")

    # (4b) Versatz streut
    werte = set()
    for _ in range(5):
        s2 = []
        ns, _ = umgebung(d, [ConnectionResetError("weg")], ["d" * 40], s2, 1)
        try:
            ns["_version_watcher"]("2026-09-22.9999")
        except Stopp:
            pass
        werte.update(x for x in s2 if x != 15)
    check(len(werte) > 1, "Versatz je Lauf verschieden (kein fester Takt)")

    # (5) Start: angefragter sha ohne erfolgreichen Abruf → Watcher holt beim ersten Takt
    ns, abrufe = umgebung(d, [GUT], ["e" * 40], [], 1)
    ns["BOT_STAND"].update(sha="e" * 40, geholt_sha=None)
    try:
        ns["_version_watcher"]("2026-09-22.9999")
    except Stopp:
        pass
    check(abrufe == ["e" * 40], "Start-Abruf gescheitert (sha gesetzt, geholt_sha leer) → erster Takt holt nach")

    # (6) Prüfer T3: Abruf scheitert, VERSION neu, panel.py im NEUEN Stand anders → Neustart, VERSION nicht still übernommen
    log = {}
    ns, abrufe = umgebung(d, [ConnectionResetError("weg"), ConnectionResetError("weg")], ["f" * 40, "f" * 40], [], 3,
                          version=b"2026-09-22.9999\n", panel_neu="f" * 40, log=log)
    ns["BOT_STAND"].update(sha="a" * 40, geholt_sha="a" * 40)
    raus = False
    try:
        ns["_version_watcher"]("2026-09-22.9998")
    except Exit:
        raus = True
    except Stopp:
        pass
    check(log["geaendert"] and log["geaendert"][-1] == "f" * 40, "Neustart-Check bekommt den NEUESTEN Stand, nicht den alten `letzter`")
    check(raus and not log["uebernommen"], "panel.py im neuen Stand anders → Neustart, VERSION nicht still übernommen")

    # (7) Inhaltsfehler (zu klein) → einmal melden, kaputt_sha, nie wiederholen
    log = {}
    ns, abrufe = umgebung(d, [b"kaputt", b"kaputt", b"kaputt"], ["g" * 40] * 4, [], 4, log=log)
    ns["BOT_STAND"]["geholt_sha"] = "a" * 40
    try:
        ns["_version_watcher"]("2026-09-22.9999")
    except Stopp:
        pass
    check(abrufe == ["g" * 40], f"zu kleine Datei: genau EIN Abruf, kein Wiederholen ({len(abrufe)} Abrufe)")
    check(ns["BOT_STAND"]["kaputt_sha"] == "g" * 40 and ns["BOT_STAND"]["geholt_sha"] == "a" * 40, "kaputt_sha gemerkt, geholt_sha unverändert")
    check(sum("unbrauchbar" in z for z in log["print"]) == 1, "Inhaltsfehler steht genau einmal in der Konsole")
    check(open(datei, "rb").read() != b"kaputt", "alter Bot bleibt liegen")

    # (8) Syntaxfehler im Stand → ebenso nie wiederholen
    kaputt = b"def run(:\n" + b"#" * 700
    ns, abrufe = umgebung(d, [kaputt, kaputt], ["h" * 40] * 3, [], 3)
    try:
        ns["_version_watcher"]("2026-09-22.9999")
    except Stopp:
        pass
    check(abrufe == ["h" * 40] and ns["BOT_STAND"]["kaputt_sha"] == "h" * 40, "compile-Fehler: ein Abruf, kaputt_sha, kein Wiederholen")

    # (9) Netzfehler wiederholt → Abstand wächst
    schlaf = []
    ns, abrufe = umgebung(d, [OSError("weg")] * 4, ["i" * 40] * 4, schlaf, 4)
    try:
        ns["_version_watcher"]("2026-09-22.9999")
    except Stopp:
        pass
    v = [x for x in schlaf if x != 15]
    check(len(v) == 4 and v[0] <= 10 and v[2] >= 2 + 2 * 12 and v[3] >= 2 + 3 * 12, f"Netzfehler: Abstand wächst je Fehlschlag ({[round(x) for x in v]})")
    check(len(abrufe) == 4, "Netzfehler: jeder Takt versucht es erneut")

print("\nALLES GRÜN" if not FEHLER else f"\nFEHLER: {FEHLER}")
raise SystemExit(1 if FEHLER else 0)
