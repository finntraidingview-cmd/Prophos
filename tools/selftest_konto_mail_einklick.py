#!/usr/bin/env python3
"""Selbsttest MAIL-KONTO EIN KLICK (30.10.2026, Finn: „im Admin die Accounts hinzufügen per E-Mail ist komplett schwammig"). prophos.html:
Admin → Konten aus Mail & TV legt für den BESITZER der Mail an (nie mehr für die eingeloggte ID), Reset über /konto-reset-bestaetigen,
Verwerfen + Server-Merker, ein Klick mit Schablone, Consistency geht nicht verloren. Nur Text-/Strukturprüfung. Aufruf: python3 tools/selftest_konto_mail_einklick.py"""
import os
import sys

HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prophos.html")


def main():
    s = open(HTML, encoding="utf-8").read()
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    ok("function admKontoMailAnlegen(" not in s and "admKontoMailAnlegen(z)" not in s, "alter Weg (Modal bei der eingeloggten ID) ist weg")
    i = s.index("function admKontoMailRender(){")
    r = s[i:s.index("\n  }\n", i)]
    ok("tvKnoepfe(td, z, fremd)" in r and "uid !== String(currentUserId || '')" in r, "Reiter nutzt Bestätigen/Verwerfen für den Besitzer")
    ok("verworfenBei(z.m.user_id, z.ext)" in r and "_admKm.verworfen[String(uid)]" in r, "verworfene Nummern bleiben weg")
    ok("_admKTv.angelegt.has(`${z.m.user_id}|${extIdNorm(z.ext)}`)" in r, "angelegt aus dem gemeinsamen Merker")
    ok("_admKm.verworfen = (d.verworfen && typeof d.verworfen === 'object') ? d.verworfen : {}" in s, "Server-Merker verworfen gelesen")
    i = s.index("async function kontoDirektAnlegen(z, fremd){")
    d = s[i:s.index("\n  }\n", i)]
    ok("if(!z.ext || !z.firma || z.firma === '?' || !(gr > 0) || !z.typ" in d and "if(!v) return 'modal'" in d, "ein Klick nur mit Firma, Größe, Nummer, Typ, Schablone")
    ok("if(v.goal_kind && !(Number(v.goal_target) > 0)) return 'modal'" in d, "Ziel ohne Zahl → Modal (nichts erfunden)")
    ok("kontoNameRegel(gr + 'k', z.ext, z.typ, '')" in d, "Name nach Namensregel")
    ok("await kontoFuerAnlegen(fuer, acc, zahl(v.consistency_pct), true)" in d and "/Nur für Admins|HTTP 403/i" in d, "über /admin/konto-anlegen, 403 → Modal")
    ok("let direkt = 'modal'; try{ direkt = await kontoDirektAnlegen(z, fremd) }" in s, "Bestätigen versucht zuerst den einen Klick")
    ok("if(z.art === 'reset' && z.vorher && !(await kontoResetBestaetigen(z, fremd, td))) return" in s, "Reset vor dem Kauf")
    ok("window._kontoFuerAnlegen = (fuer, acc, cons) => kontoFuerAnlegen(fuer, acc, cons)" in s, "Consistency aus dem Modal geht mit")
    ok(s.count("window._admKontoMailNeu?.(") >= 5, "Reiter zieht nach jeder Aktion mit")
    for t in f:
        print("✗", t)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
