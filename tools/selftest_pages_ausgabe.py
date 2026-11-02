#!/usr/bin/env python3
"""Selbsttest PAGES-AUSGABE (02.11.2026, Eingang, Stufe 1): tools/pages_ausgabe.sh legt genau die erwartete Liste an, Inhalt gleich dem Repo, kein Backend und nichts Internes.
Bricht ab bei fehlender Datei, leerer Datei oder prophos.html ohne OS_TAB_BUILD; andere Ordnernamen als _pages löscht es nie. Die Liste steht hier absichtlich noch einmal von
Hand: eine neue Datei im Skript muss bewusst auch hier eingetragen werden. Läuft in einem Temp-Ordner, nur die Dateien der Liste werden kopiert. Aufruf:  python3 tools/selftest_pages_ausgabe.py"""
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPT = os.path.join(W, "tools", "pages_ausgabe.sh")
SOLL = {
    "index.html", "prophos.html", "sw.js", "prophos-icon-180.png", "prophos-icon-192.png", "prophos-icon-512.png",
    "mt5-copier/VERSION", "mt5-copier/augen_tsx.js", "tv-reader/tsx-auge.user.js",
}
VERBOTEN_ORDNER = ("sql/", "tools/", ".claude/", ".git/", "pc-fernzugriff/", "backup-agent/", "topstep-agent/", "functions/", "tv-reader/")
VERBOTEN_NAMEN = {"app.py", "kapital_app.py", "polar_app.py", "support_app.py", "ai_advisor.py", "firm_rules.json", "knowledge_base.md", "support_wissen.md",
                  "order_bot.py", "panel.py", "copier.py", "provision.py", "augen.js", "GEHEIMNISSE.md", "_worker.js", "_routes.json", "_headers", "_redirects"}
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def liste(ordner):
    out = set()
    for wurzel, _, dateien in os.walk(ordner):
        for d in dateien:
            out.add(os.path.relpath(os.path.join(wurzel, d), ordner).replace(os.sep, "/"))
    return out


def baum(ziel):
    """Kleine Kopie: Skript + nur die Dateien der Liste, plus Köder, die nie mit dürfen."""
    for f in SOLL | {"tools/pages_ausgabe.sh"}:
        os.makedirs(os.path.dirname(os.path.join(ziel, f)) or ziel, exist_ok=True)
        shutil.copy(os.path.join(W, f), os.path.join(ziel, f))
    for koeder in ("app.py", "sql/x.sql", "tools/geheim.py", ".claude/CODEMAP.md", "mt5-copier/order_bot.py", "tv-reader/README.md", "tv-reader/reader-server.py", "tv-reader/tv-reader.user.js", "pc-fernzugriff/GEHEIMNISSE.md"):
        pfad = os.path.join(ziel, koeder)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        open(pfad, "w", encoding="utf-8").write("Köder")


def lauf(wurzel, *arg):
    return subprocess.run(["bash", os.path.join(wurzel, "tools", "pages_ausgabe.sh"), *arg], capture_output=True, text=True, cwd=wurzel)


with tempfile.TemporaryDirectory() as t:
    a = os.path.join(t, "a")
    baum(a)
    r = lauf(a)
    aus = os.path.join(a, "_pages")
    ist = liste(aus)
    soll("Lauf ohne Fehler", r.returncode == 0)
    soll("genau die erwartete Liste", ist == SOLL)
    if ist != SOLL:
        print("     zu viel:", sorted(ist - SOLL), " fehlt:", sorted(SOLL - ist))
    soll("Inhalt gleich dem Repo", all(filecmp.cmp(os.path.join(W, f), os.path.join(aus, f), shallow=False) for f in SOLL & ist))
    soll("kein Backend, kein Bot, keine Betriebsdaten", not {os.path.basename(f) for f in ist} & VERBOTEN_NAMEN)
    soll("keine sql/, tools/, .claude/, pc-fernzugriff/", not any(f.startswith(VERBOTEN_ORDNER) for f in ist - {"tv-reader/tsx-auge.user.js"}))
    soll("Köder bleiben draußen", not {"app.py", "sql/x.sql", "tools/geheim.py", ".claude/CODEMAP.md", "mt5-copier/order_bot.py", "tv-reader/README.md", "tv-reader/reader-server.py", "tv-reader/tv-reader.user.js"} & ist)
    open(os.path.join(aus, "alt.txt"), "w").write("alt")
    soll("sw.js und VERSION bleiben", {"sw.js", "mt5-copier/VERSION"} <= ist)
    soll("zweiter Lauf räumt Altes weg", lauf(a).returncode == 0 and liste(aus) == SOLL)

    b = os.path.join(t, "b")
    baum(b)
    os.remove(os.path.join(b, "mt5-copier", "VERSION"))
    soll("VERSION fehlt → Abbruch, keine Ausgabe", lauf(b).returncode != 0 and not os.path.exists(os.path.join(b, "_pages")))
    c = os.path.join(t, "c")
    baum(c)
    open(os.path.join(c, "sw.js"), "w").close()
    soll("leere Datei → Abbruch", lauf(c).returncode != 0)
    d = os.path.join(t, "d")
    baum(d)
    open(os.path.join(d, "prophos.html"), "w", encoding="utf-8").write("<!DOCTYPE html>kaputt")
    soll("prophos.html ohne OS_TAB_BUILD → Abbruch", lauf(d).returncode != 0)
    e = os.path.join(t, "e")
    baum(e)
    wert = os.path.join(t, "wertvoll")
    os.makedirs(wert)
    open(os.path.join(wert, "bleibt.txt"), "w").write("x")
    soll("anderer Ordnername → Abbruch, nichts gelöscht", lauf(e, wert).returncode == 2 and os.path.exists(os.path.join(wert, "bleibt.txt")))

soll("nichts im Repo erzeugt", not os.path.exists(os.path.join(W, "_pages")))
print("ALLE OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
