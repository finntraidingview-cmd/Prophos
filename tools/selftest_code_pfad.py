#!/usr/bin/env python3
"""Selbsttest CODE-PFAD (app.py code_pfad_ok / CODE_PFAD_MUSTER, LO1 05.11.2026): welche Repo-Pfade /code/datei mit X-Code-Token ausliefert.
Erlaubt: app.py, prophos.html, sw.js, requirements.txt, mt5-copier/*, tv-reader/*, pc-fernzugriff/{setup-pc,rueckbau-pc,diagnose}.ps1,
pc-fernzugriff/agent/*, pc-fernzugriff/foto/* (je eine Ebene). Verboten: mac/, acl.hujson, ANLEITUNG.md, foto/mac/, alles mit „..", Unterordner.
Dazu: jede ausgelieferte pc-fernzugriff-Datei ohne eingebautes Geheimnis (Key-/Token-Muster).
Aufruf: python3 tools/selftest_code_pfad.py"""
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def lade():
    src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    i = src.index("_CODE_NAME = ")
    j = src.index("_CODE_WURZEL = ", i)
    ns = {"re": re}
    exec(src[i:j], ns)
    k = src.index("\ndef code_pfad_ok(") + 1
    exec(src[k:src.find("\n\n\n", k)], ns)
    return ns["code_pfad_ok"]


def main():
    ok = lade()
    erlaubt = ["app.py", "prophos.html", "sw.js", "requirements.txt", "mt5-copier/start-alles.bat", "mt5-copier/VERSION", "tv-reader/reader-server.py",
               "pc-fernzugriff/setup-pc.ps1", "pc-fernzugriff/rueckbau-pc.ps1", "pc-fernzugriff/diagnose.ps1",
               "pc-fernzugriff/agent/agent.py", "pc-fernzugriff/agent/agent-aufgabe.ps1", "pc-fernzugriff/agent/auftrag.py",
               "pc-fernzugriff/foto/foto.ps1", "pc-fernzugriff/foto/foto-schuss.py", "pc-fernzugriff/foto/foto-aufgabe.ps1"]
    verboten = ["pc-fernzugriff/acl.hujson", "pc-fernzugriff/ANLEITUNG.md", "pc-fernzugriff/mac/do.sh", "pc-fernzugriff/mac/pc.sh",
                "pc-fernzugriff/mac/ssh_config.beispiel", "pc-fernzugriff/foto/mac/foto.sh", "pc-fernzugriff/agent/../acl.hujson",
                "pc-fernzugriff/../app.py", "pc-fernzugriff/setup-pc.ps1/x", "pc-fernzugriff/", "pc-fernzugriff/agent/", "pc-fernzugriff/agent/.env",
                "pc-fernzugriff/x.ps1", "pc-fernzugriff/setup-pc.ps1.bak", "pc-fernzugriff/agent/sub/x.py", "/etc/passwd", "../app.py",
                ".env", "pc-fernzugriff\\agent\\agent.py", "mt5-copier/../app.py", "tools/selftest_code_pfad.py", "pc-fernzugriffX/setup-pc.ps1",
                "xpc-fernzugriff/setup-pc.ps1", None, 5]
    check(all(ok(p) for p in erlaubt), f"erlaubt: {len(erlaubt)} Pfade ({[p for p in erlaubt if not ok(p)] or 'alle ok'})")
    check(not any(ok(p) for p in verboten), f"verboten: {len(verboten)} Pfade ({[p for p in verboten if ok(p)] or 'alle gesperrt'})")
    # alle getrackten Dateien unter pc-fernzugriff: ausgeliefert genau die PC-Seite
    dateien = subprocess.run(["git", "-C", WURZEL, "ls-files", "pc-fernzugriff"], capture_output=True, text=True).stdout.split()
    soll_nein = lambda p: p.startswith("pc-fernzugriff/mac/") or p.startswith("pc-fernzugriff/foto/mac/") or p in ("pc-fernzugriff/acl.hujson", "pc-fernzugriff/ANLEITUNG.md")   # noqa: E731
    falsch = [p for p in dateien if ok(p) == soll_nein(p)]
    check(dateien and not falsch, f"pc-fernzugriff: {sum(1 for p in dateien if ok(p))} von {len(dateien)} Dateien ausgeliefert, Mac-Seite/ACL/Anleitung nie ({falsch or 'stimmt'})")
    # keine Geheimnisse in dem, was ausgeliefert wird
    muster = re.compile(r"tskey-(?:auth|api)-[A-Za-z0-9]{6,}|sb_secret_[A-Za-z0-9_-]{6,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}"
                        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|[0-9a-f-]{36}\.pc-[a-z0-9]{4,12}\.[0-9a-f]{40}|AKIA[0-9A-Z]{16}|ssh-(?:ed25519|rsa) [A-Za-z0-9+/]{40,}")
    funde = []
    for p in dateien:
        if ok(p):
            t = open(os.path.join(WURZEL, p), encoding="utf-8", errors="replace").read()
            funde += [(p, m.group(0)[:16]) for m in muster.finditer(t)]
    check(not funde, f"keine Geheimnisse in den ausgelieferten pc-fernzugriff-Dateien ({funde or 'sauber'})")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
