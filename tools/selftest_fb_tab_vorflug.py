#!/usr/bin/env python3
"""Selbsttest F-B Tab-Vorflug (Master 11.11.2026 nach FS2, K4): 2–3 min vor jedem Start der IDs dieses PCs prüft das Panel die Lebenszeichen des Prophos-Tabs
und startet bei rot die vorhandene Stufen-Heilung sofort (TAB_HEIL_SOFORT, FS1-Riegel).
 a) tab_vorflug_starts: „next_start_um“ als ISO oder Liste; fehlt/ungültig → [] (Railway noch ohne Feld = nichts tun).
 b) tab_vorflug_faellig: nur im gewürfelten Fenster, nie näher als 45 s, je Start einmal.
 c) tab_vorflug_urteil: still ≥ 30 s / nicht angemeldet / Supabase ≥ 90 s / Realtime ≥ 2 min / Marke unbeantwortet → rot; gesund und pong None → nicht rot.
 d) _tab_vorflug_schritt (echte Funktion, Attrappen): ohne Startzeiten nichts; fällig + rot → TAB_HEIL_SOFORT mit eigenem Grund; Puls-Lauf → nichts,
    nächste Runde erneut; gesund → keine Heilung; Marke: Tab mit vpong → beantwortet.
 e) tab_heil_sofort_lage nennt den Vorflug-Grund; /api/instances gibt die Marke mit; tab_gesehen nimmt vpong an.
Aufruf: python3 tools/selftest_fb_tab_vorflug.py"""
import os
import sys
import time
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel as pn  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


J = 1_800_000_000.0
# a)
check(pn.tab_vorflug_starts({"next_start_um": iso(J + 150)}) == [J + 150], "a1 ISO-Text")
check(pn.tab_vorflug_starts({"next_start_um": [iso(J + 300), "kaputt", iso(J + 150), iso(J + 150)]}) == [J + 150, J + 300], "a2 Liste, sortiert, doppelt/ungültig raus")
check(pn.tab_vorflug_starts({}) == [] and pn.tab_vorflug_starts(None) == [] and pn.tab_vorflug_starts({"next_start_um": None}) == [], "a3 Feld fehlt → []")
# b)
z = {J + 150: 160.0}
check(pn.tab_vorflug_faellig([J + 150], J, {}, z) == J + 150, "b1 150 s vor dem Start bei Ziel 160 → fällig")
check(pn.tab_vorflug_faellig([J + 170], J, {}, {J + 170: 160.0}) is None, "b2 170 s vor dem Start bei Ziel 160 → noch nicht")
check(pn.tab_vorflug_faellig([J + 40], J, {}, {}) is None, "b3 40 s vor dem Start → zu spät, nie")
check(pn.tab_vorflug_faellig([J + 150], J, {J + 150: J - 10}, z) is None, "b4 schon erledigt → nicht noch einmal")
check(pn.tab_vorflug_faellig([J - 30, J + 150], J, {}, z) == J + 150, "b5 vergangener Start wird übersprungen")
# c)
check(pn.tab_vorflug_urteil(4.0, True, 3, 0, None) == (False, "Prophos-Tab antwortet"), "c1 gesund, Tab ohne Marke → nicht rot")
check(pn.tab_vorflug_urteil(31.0, True, 3, 0, None)[0], "c2 fragt seit 31 s nicht → rot")
check(pn.tab_vorflug_urteil(4.0, False, None, None, None)[0], "c3 nicht angemeldet → rot")
check(pn.tab_vorflug_urteil(4.0, True, 95, 0, None)[0] and pn.tab_vorflug_urteil(4.0, True, 3, 130, None)[0], "c4 Supabase ≥ 90 s / Realtime ≥ 2 min → rot")
check(not pn.tab_vorflug_urteil(4.0, None, None, None, None)[0], "c5 alter Tab ohne Login-Feld → nicht rot")
check(pn.tab_vorflug_urteil(4.0, True, 3, 0, False)[0] and pn.tab_vorflug_urteil(4.0, True, 3, 0, True) == (False, "Prophos-Tab antwortet (Vorflug-Marke beantwortet)"),
      "c6 Marke unbeantwortet → rot; beantwortet → nicht rot")

# d) Schritt mit Attrappen
gemeldet = []
pn._tab_stand_holen = lambda pc, spur: gemeldet.append(spur)
frei = [True]
pn._browser_und_mt5_frei = lambda *a, **k: frei[0]


def lauf(stand, zuletzt_vor_s, login=True, kann_pong=False):
    jetzt = time.time()
    pn.TAB_NL.update(stand=stand, stand_at=jetzt)
    pn._TAB_OEFFNEN.update(zuletzt=jetzt - zuletzt_vor_s, start=jetzt - 3600, login=login, sb_s=2, rt_aus_s=0)
    pn.TAB_VORFLUG.update(ziel={}, erledigt={}, marke=None, marke_at=0.0, pong_at=0.0, kann_pong=kann_pong)
    pn.TAB_HEIL_SOFORT.update(at=0.0, plan="", erledigt=False, geheilt=False, grund="")
    gemeldet.clear()
    pn._tab_vorflug_schritt("pc-xxxxxx")
    return jetzt


lauf({"ok": True}, 60)
check(pn.TAB_HEIL_SOFORT["at"] == 0.0, "d1 ohne next_start_um → nichts (auch bei stillem Tab)")
_orig_uniform = pn.random.uniform
pn.random.uniform = lambda a, b: 170.0
jetzt = lauf({"ok": True, "next_start_um": iso(time.time() + 140)}, 60)
check(pn.TAB_HEIL_SOFORT["at"] >= jetzt and "Vorflug:" in pn.TAB_HEIL_SOFORT["grund"] and gemeldet and "Vorflug Tab" in gemeldet[0],
      "d2 Start in 140 s, Tab still 60 s → Stufen-Heilung sofort mit Vorflug-Grund + Spur an Railway")
d, txt = pn.tab_heil_sofort_lage(pn.TAB_HEIL_SOFORT, time.time())
check(d is not None and txt.startswith("Vorflug: Prophos-Tab fragt seit"), "d3 tab_heil_sofort_lage nennt den Vorflug-Grund")
frei[0] = False
lauf({"ok": True, "next_start_um": iso(time.time() + 140)}, 60)
check(pn.TAB_HEIL_SOFORT["at"] == 0.0 and not pn.TAB_VORFLUG["erledigt"], "d4 Puls-Lauf/MT5-Order läuft → nichts, nicht erledigt (nächste Runde)")
frei[0] = True
lauf({"ok": True, "next_start_um": iso(time.time() + 140)}, 3)
check(pn.TAB_HEIL_SOFORT["at"] == 0.0 and pn.TAB_VORFLUG["erledigt"] and not gemeldet, "d5 gesunder Tab → keine Heilung, erledigt, keine Spur")
pn.TAB_NL.update(stand={"ok": True, "next_start_um": iso(time.time() + 140)}, stand_at=time.time() - 400)
pn.TAB_VORFLUG.update(erledigt={})
pn._tab_vorflug_schritt("pc-xxxxxx")
check(not pn.TAB_VORFLUG["erledigt"], "d6 Tab-Stand älter als 3 min → nichts")
pn.random.uniform = _orig_uniform

# e) Marke über /api/instances + tab_gesehen (Prüfer S4: kann_pong je Tab und frisch)
pn.TAB_VORFLUG.update(marke="abc-1", marke_at=time.time() - 1, pong_at=0.0, vpong_tid="", vpong_at=0.0)
pn._TAB_HAUPT["tid"] = None
pn._TABS.clear()
pn.tab_gesehen("python-requests/2.31", {"tab": ["1"], "tid": ["t1"], "login": ["1"], "vpong": ["abc-1"]})
check(pn.TAB_VORFLUG["pong_at"] >= pn.TAB_VORFLUG["marke_at"] and pn.tab_kann_pong(pn.TAB_VORFLUG, "t1", time.time()),
      "e1 tab_gesehen nimmt die richtige vpong-Marke an, Tab t1 kann Pong")
pn.TAB_VORFLUG.update(pong_at=0.0)
pn.tab_gesehen("python-requests/2.31", {"tab": ["1"], "tid": ["t1"], "login": ["1"], "vpong": ["falsch"]})
check(pn.TAB_VORFLUG["pong_at"] == 0.0, "e2 falsche Marke zählt nicht")
check(not pn.tab_kann_pong(pn.TAB_VORFLUG, "t2", time.time()), "e2b anderer Haupt-Tab ohne vpong → kann nicht (nur Lebenszeichen)")
check(not pn.tab_kann_pong(dict(pn.TAB_VORFLUG, vpong_at=time.time() - 120), "t1", time.time()), "e2c vpong älter als 60 s → kann nicht")

# f) Prüfer M2: „Start in ≤ 5 min“ sperrt im Vorflug-Weg nur das Neuladen, nicht das Wecken
sv = {"grund": "Vorflug: Prophos-Tab fragt seit 60 s nicht"}
check(pn.tab_vorflug_riegel("Start in ≤ 5 min", sv, 0) == "", "f1 Vorflug, Stufe 1 (wecken) trotz „Start in ≤ 5 min“ frei")
check(pn.tab_vorflug_riegel("Start in ≤ 5 min", sv, 1) == "Start in ≤ 5 min", "f2 Vorflug, Stufe 2 (neu laden) bleibt gesperrt")
check(pn.tab_vorflug_riegel("Start in ≤ 5 min", {"grund": ""}, 0) == "Start in ≤ 5 min", "f3 FS1-Sofort-Weg (ohne Vorflug-Grund) unverändert")
check(pn.tab_vorflug_riegel("Puls läuft", sv, 0) == "Puls läuft", "f4 jeder andere Riegel bleibt")
ep0, problem0 = None, "Vorflug: x"
akt, _g, _ep = pn.tab_heil_stufe(ep0, 30, problem0, time.time(), pn.tab_vorflug_riegel("Start in ≤ 5 min", sv, 0), True, 999, 0.0)
check(akt == "wecken", f"f5 tab_heil_stufe weckt mit dem freigegebenen Riegel (Aktion „{akt}“)")
src_hs = __import__("inspect").getsource(pn._tab_heil_schritt)
check("tab_vorflug_riegel(riegel, TAB_HEIL_SOFORT," in src_hs, "f6 _tab_heil_schritt nutzt die Freigabe")
# g) bis = Start, H6 nicht überschreiben, H7 nicht angemeldet = nur melden
jj = time.time()
check(pn.tab_heil_sofort_lage({"at": jj - 5, "erledigt": False, "grund": "Vorflug: x", "bis": jj - 1}, jj)[0] is None, "g1 Vorflug-Befund gilt nur bis zum Start")
pn.random.uniform = lambda a, b: 170.0
jetzt = lauf({"ok": True, "next_start_um": iso(time.time() + 140)}, 60, login=False)
check(pn.TAB_HEIL_SOFORT["at"] == 0.0 and gemeldet, "g2 Prüfer H7: nicht angemeldet → nur Spur, keine Heilung")
pn.TAB_NL.update(stand={"ok": True, "next_start_um": iso(time.time() + 140)}, stand_at=time.time())
pn._TAB_OEFFNEN.update(zuletzt=time.time() - 60, start=time.time() - 3600, login=True)
pn.TAB_VORFLUG.update(ziel={}, erledigt={})
pn.TAB_HEIL_SOFORT.update(at=time.time() - 5, plan="1234abcd", erledigt=False, geheilt=False, grund="", bis=None)
pn._tab_vorflug_schritt("pc-xxxxxx")
check(pn.TAB_HEIL_SOFORT["plan"] == "1234abcd" and pn.TAB_HEIL_SOFORT["grund"] == "", "g3 Prüfer H6: offener FS1-Eintrag wird nicht überschrieben")
# h) Pong-Weg: Tab kann Pong, antwortet nicht → rot
_sl = pn.time.sleep
pn.time.sleep = lambda x: None
_vf = pn.TAB_VF_PONG_S
pn.TAB_VF_PONG_S = 0.05
jetzt = time.time()
pn.TAB_NL.update(stand={"ok": True, "next_start_um": iso(jetzt + 140)}, stand_at=jetzt)
pn._TAB_OEFFNEN.update(zuletzt=jetzt - 2, start=jetzt - 3600, login=True, sb_s=2, rt_aus_s=0, tid="t1")
pn.TAB_VORFLUG.update(ziel={}, erledigt={}, marke=None, pong_at=0.0, vpong_tid="t1", vpong_at=jetzt)
pn.TAB_HEIL_SOFORT.update(at=0.0, plan="", erledigt=False, geheilt=False, grund="", bis=None)
pn._tab_vorflug_schritt("pc-xxxxxx")
check("Vorflug-Marke nicht" in pn.TAB_HEIL_SOFORT["grund"] and pn.TAB_VORFLUG["marke"] is None, "h1 Tab kann Pong, antwortet nicht → rot, Marke wieder weg")
pn.time.sleep, pn.TAB_VF_PONG_S = _sl, _vf
pn.random.uniform = _orig_uniform
# i) Prüfer H8: Zeitformate
check(pn.tab_vorflug_starts({"next_start_um": "2026-11-11T10:00:00.12345+00:00"}) == [datetime(2026, 11, 11, 10, 0, 0, 123450, timezone.utc).timestamp()]
      and pn.tab_vorflug_starts({"next_start_um": "2026-11-11T10:00:00"}) == [datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc).timestamp()],
      "i1 Bruchteile mit 5 Stellen und ISO ohne Zone (= UTC) werden gelesen")
with open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8") as f:
    src = f.read()
check('"vorflug_ping": TAB_VORFLUG["marke"]' in src[src.find('if path == "/api/instances":'):src.find('if path == "/api/deals":')],
      "e3 /api/instances gibt die Marke nur mit, solange eine gilt")
i = src.find("_puls_wache_schritt(pc)   # PULS-WACHE")
check(0 < i < src.find("_tab_vorflug_schritt(pc)", i) < src.find("_tab_heil_schritt(pc, still0)", i), "e4 Vorflug läuft im Wächter vor der Stufen-Heilung")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
