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

# e) Marke über /api/instances + tab_gesehen
pn.TAB_VORFLUG.update(marke="abc-1", marke_at=time.time() - 1, pong_at=0.0, kann_pong=False)
pn._TAB_HAUPT["tid"] = None
pn._TABS.clear()
pn.tab_gesehen("python-requests/2.31", {"tab": ["1"], "tid": ["t1"], "login": ["1"], "vpong": ["abc-1"]})
check(pn.TAB_VORFLUG["kann_pong"] and pn.TAB_VORFLUG["pong_at"] >= pn.TAB_VORFLUG["marke_at"], "e1 tab_gesehen nimmt die richtige vpong-Marke an")
pn.TAB_VORFLUG.update(pong_at=0.0)
pn.tab_gesehen("python-requests/2.31", {"tab": ["1"], "tid": ["t1"], "login": ["1"], "vpong": ["falsch"]})
check(pn.TAB_VORFLUG["pong_at"] == 0.0, "e2 falsche Marke zählt nicht")
with open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8") as f:
    src = f.read()
check('"vorflug_ping": TAB_VORFLUG["marke"]' in src[src.find('if path == "/api/instances":'):src.find('if path == "/api/deals":')],
      "e3 /api/instances gibt die Marke nur mit, solange eine gilt")
i = src.find("_puls_wache_schritt(pc)   # PULS-WACHE")
check(0 < i < src.find("_tab_vorflug_schritt(pc)", i) < src.find("_tab_heil_schritt(pc, still0)", i), "e4 Vorflug läuft im Wächter vor der Stufen-Heilung")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
