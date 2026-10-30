#!/usr/bin/env python3
"""Selbsttest COPIER-UPDATE-FIX (30.10.2026, Marco pc-t8wg97: Copier blieb auf altem Code, meldete aber .1940): copier.py update_schritt + code_kennung,
Verdrahtung in Hauptschleife und Status, panel.py zieht VERSION erst nach 90 s nach, app.py update_wartet_ereignisse. Aufruf: python3 tools/selftest_copier_update.py"""
import ast
import hashlib
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
ok = True


def chk(bed, text):
    global ok
    print(("  OK   " if bed else "  FEHLER ") + text)
    ok = ok and bool(bed)


def funktionen(pfad, namen, ns):
    baum = ast.parse(open(pfad, encoding="utf-8").read())
    for n in baum.body:
        if isinstance(n, ast.FunctionDef) and n.name in namen:
            exec(compile(ast.Module([n], []), pfad, "exec"), ns)
    return ns


cp_pfad = os.path.join(WURZEL, "mt5-copier", "copier.py")
cp_src = open(cp_pfad, encoding="utf-8").read()
ns = funktionen(cp_pfad, {"update_schritt", "code_kennung", "neustart_bremse", "hedges_teilen", "hedges_halten_auf", "solo_haelt_auf"},
                {"hashlib": hashlib, "NEUSTART_BREMSE_MAX": 3, "NEUSTART_BREMSE_S": 21600, "NEUSTART_ABSTAND_S": 300})
us, ck, nb, hh, sh = ns["update_schritt"], ns["code_kennung"], ns["neustart_bremse"], ns["hedges_halten_auf"], ns["solo_haelt_auf"]


def nie():
    raise AssertionError("darf copier.py nicht holen")


# Der Vorfall: Panel hat die VERSION-Datei schon nachgezogen, der Prozess läuft auf .1 — der Stand des Prozesses zählt, nicht die Datei
chk(us("v2", "v1", False, lambda: True) == ("v1", True), "reiner copier.py-Commit: Neustart, auch wenn die Datei schon v2 sagt")
chk(us("v2", "v1", False, lambda: False) == ("v2", False), "nur Frontend-Bump: Nummer nachziehen, kein Neustart")
chk(us("v2", "v2", False, nie) == ("v2", None), "nichts Neues: copier.py wird nicht jede Minute geholt")
chk(us("", "v1", False, nie) == ("v1", None), "keine Antwort: nichts tun")
chk(us("v2", "v1", False, lambda: None) == ("v1", True), "neue Nummer, nicht prüfbar: wie bisher Neustart sobald flach")
chk(us("v2", "v2", True, lambda: True) == ("v2", True), "erster Takt: gleiche Nummer, aber anderer Code (Download beim Start gescheitert) → Neustart")
chk(us("v2", "v2", True, lambda: False) == ("v2", False), "erster Takt: gleicher Code → kein Neustart")
chk(us("v2", "v2", True, lambda: None) == ("v2", None), "erster Takt: nicht prüfbar, keine neue Nummer → kein Anlass")
# Bump, Bump, Rücknahme: die letzte Entscheidung folgt dem neuesten Stand
chk(us("v3", "v1", False, lambda: False) == ("v3", False), "Commit zurückgenommen: Neustart-Wunsch fällt weg")

chk(ck(b"a\r\nb\r\n") == ck(b"\xef\xbb\xbfa\nb\n") and len(ck(b"x")) == 12 and ck(b"a") != ck(b"b"), "Code-Kennung: unabhängig von Zeilenende/BOM, 12 Zeichen")

mk, frei = None, []
for i_ in range(5):
    e_, mk = nb(mk, "z1", 1000.0 + i_ * 301)
    frei.append(e_)
chk(frei == [True, True, True, False, False], "Bremse: 3 Neustarts auf denselben Stand, dann keiner mehr")
chk(nb(mk, "z2", 1000.0)[0] is True and nb(mk, "z1", 1000.0 + 2 * 301 + 21601)[0] is True, "Bremse: neuer Stand oder nach 6 h wieder frei")
m1 = nb(None, "z1", 1000.0)[1]
chk(nb(m1, "z1", 1000.0 + 299)[0] is False and nb(m1, "z1", 1000.0 + 301)[0] is True and nb(m1, "z2", 1001.0)[0] is True, "Bremse: 5 min Abstand je Stand, neuer Stand sofort")
# S2: offene Hedges bei altem Sidecar, Solo-Lesefehler
h_ = {111: [{"ticket": 1}]}
chk(hh(h_, {"111"}, set()) is True and hh(h_, set(), {"111"}) is True, "eigener Hedge und Alt-Hedge (alt_unklar, str gegen int) halten auf")
chk(hh(h_, set(), set()) is False and hh(None, set(), {"111"}) is False and hh({}, {"111"}, {"111"}) is False, "gewöhnlicher Zwilling und leerer Bestand halten nicht auf")
chk(sh(None) is True and sh([{"ticket": 1}]) is True and sh([]) is False, "Solo: nicht lesbar und offen halten auf, nur gelesen-leer ist flach")
chk('_pos_alle = mt5.positions_get()' in cp_src and 'if _pos_alle is None:' in cp_src and "for p_ in (mt5.positions_get() or [])" not in cp_src, "positions_get None wird zu solo=None")
chk(nb("kaputt", "z1", 5.0)[0] is True and nb({"n": "x", "ziel": "z1"}, "z1", 5.0)[0] is True, "Bremse: kaputter Merker sperrt nicht")
chk('getattr(m, "busy", True)' in cp_src and cp_src.count("m.busy = hedges_halten_auf(book.get(m.magic), m.eigene_set, m.alt_unklar) or solo_haelt_auf") == 3
    and 'bool(hedge_acc.get("solo"))' not in cp_src, "Unbekannt zählt nicht als flach, alle Wege nutzen dieselbe Prüfung")
chk('rv and _REMOTE_VERSION.get("neustart")' in cp_src and "rv != my_version" not in cp_src, "Hauptschleife fragt nur die Entscheidung, Standard ist kein Neustart")
chk('"copier_lauf": _LAUF["version"]' in cp_src and '"copier_code": _LAUF["code"]' in cp_src and '"update_wartet":' in cp_src, "Status trägt copier_lauf, copier_code, update_wartet")
chk("busy = [m.file for m in masters" in cp_src and "if not busy:" in cp_src, "Selbst-Update wartet weiter auf flache Master")
chk("Zwilling-PC updaten" not in cp_src and "HEDGE CLOSE" in cp_src, "Alarmtext nennt den PC mit dem HEDGE CLOSE")

pa_src = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
i = pa_src.index('if not upd["code"][neuester]:')
chk("VERSION_NACHZIEHEN_S" in pa_src[i:i + 1200] and pa_src.index("VERSION_NACHZIEHEN_S", i) < pa_src.index("_version_uebernehmen(remote)", i), "Panel zieht VERSION erst nach der Wartezeit nach")

html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
chk("copier_lauf: s.copier_lauf" in html and "copier_code: s.copier_code" in html and "update_wartet: s.update_wartet" in html, "Tab reicht die Felder nach mt5_live durch")

ap_pfad = os.path.join(WURZEL, "app.py")
ans = funktionen(ap_pfad, {"update_wartet_ereignisse"}, {"UPDATE_WARTET_ALARM_S": 3600})
ev = ans["update_wartet_ereignisse"]
J = 1_000_000.0
z = lambda pc, seit, auf="v9": {"pc_name": pc, "user_id": "u", "cl": "v8", "cc": "abc", "uw": {"seit": seit, "auf": auf, "grund": ["config-a.json"]}}
e = ev([z("pc-a", J - 7200), z("pc-a", J - 7200), z("pc-b", J - 100), z("pc-c", "kaputt"), {"pc_name": "pc-d", "uw": None}], J, {"pc-a": {"name": "Marco"}})
chk(len(e) == 1 and e[0][0] == "update_wartet|pc-a|abc", "⚪ nur ab 1 h, einmal je PC × laufendem Code, kaputte Zeilen stören nicht")
chk("PC von Marco (pc-a)" in e[0][1] and "config-a.json" in e[0][1] and "abc" in e[0][1], "Text nennt PC mit Namen, Grund und laufenden Code")
chk(ev([z("pc-a", J - 7200, "v10")], J)[0][0] == e[0][0], "reiner Bump des Zielstands: keine neue Meldung")
chk("not _alarm_fremd_verwaltet(r.get(\"user_id\"))" in open(ap_pfad, encoding="utf-8").read().split("def update_wartet_tick", 1)[1][:700], "Alarm nur für die eigene Gruppe")

print("OK" if ok else "FEHLER")
sys.exit(0 if ok else 1)
