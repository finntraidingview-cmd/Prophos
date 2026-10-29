#!/usr/bin/env python3
"""Selbsttest RÜCKGÄNGIG NACH EIN-KLICK-ANLEGEN (30.10.2026): app.py konto_rueckgaengig_pruefen (rein) + Route /konto-rueckgaengig
(archivieren, nie löschen; Reset: alte Zeile wieder aktiv) und prophos.html kontoUndoToast/kontoRueckgaengig. Ohne Netz.
Aufruf: python3 tools/selftest_konto_rueckgaengig.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    ns = {"datetime": datetime, "timezone": timezone}
    i = app.index("\ndef konto_rueckgaengig_pruefen(") + 1
    exec(re.search(r"^KONTO_RUECK_S = .*$", app, re.M).group(0) + "\n" + app[i:app.find("\n\n\n", i)], ns)
    pr = ns["konto_rueckgaengig_pruefen"]
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    jetzt = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    neu = {"id": "n1", "user_id": "u1", "created_at": "2026-10-30T11:55:00+00:00"}
    ok(pr(neu, None, jetzt) is None, "frisch angelegt → erlaubt")
    ok(pr(dict(neu, created_at="2026-10-30T11:55:00Z"), None, jetzt) is None, "Z-Zeitzone")
    ok(pr(dict(neu, created_at="2026-10-30T11:55:00"), None, jetzt) is None, "ohne Zeitzone = UTC")
    ok("zu alt" in (pr(dict(neu, created_at="2026-10-30T11:00:00+00:00"), None, jetzt) or ""), "älter als 30 min → nein")
    ok(pr(None, None, jetzt) == "Konto nicht gefunden" and pr({}, None, jetzt) == "Konto nicht gefunden", "fehlt")
    ok(pr(dict(neu, created_at="kaputt"), None, jetzt) == "Anlegezeit unbekannt", "Zeit kaputt")
    ok(pr(neu, {"id": "a1", "user_id": "u1"}, jetzt) is None, "Reset: alte Zeile gleicher Besitzer")
    ok("anderen ID" in (pr(neu, {"id": "a1", "user_id": "u2"}, jetzt) or ""), "alte Zeile fremder Besitzer → nein")
    ok(pr(neu, {"id": "n1", "user_id": "u1"}, jetzt) == "alte Zeile ungültig", "alt = neu → nein")
    # Route: archivieren statt löschen, Recht wie /admin/konto-anlegen, Reset holt alte Zeile zurück
    i = app.index("def konto_rueckgaengig():")
    r = app[i:app.find("\n\n\n", i)]
    ok('_konto_archiv_eintragen(besitzer, kid, "rueckgaengig"' in r, "neues Konto wird archiviert")
    ok("sb_delete" not in r and "DELETE" not in r, "nichts wird gelöscht")
    ok("_archiv_eintrag_entfernen(alt_id) if alt else 0" in r, "Reset: alte Zeile wieder aktiv")
    ok("if besitzer != str(uid):" in r and "_admin_konto_gate()" in r, "Recht: Besitzer oder Gate von /admin/konto-anlegen")
    ok("profile = _archiv_eintrag_entfernen(kid)" in app, "Entarchivieren nutzt dieselbe Funktion")
    # Frontend
    i = html.index("function kontoUndoToast(o){")
    t = html[i:html.index("window._kontoUndoToast", i)]
    ok("Angelegt: ${o.name} · " in t and "(für ${o.fremd.name})" in t and "atToast(txt, 'ok', 15000)" in t, "Toast-Text + 15 s")
    ok("b.textContent = 'Rückgängig'" in t and "/konto-rueckgaengig" in t, "Rückgängig ruft die Route")
    ok("_origLocalStorageSetItem.call(localStorage, ARCH_LS" in t and "saveArchive(" not in t, "eigene ID: Archiv vom Server spiegeln, kein Upload")
    ok("kontoUndoToast({ id: d && d.account && d.account.id" in html and "kontoFuerAnlegen(fuer, acc, zahl(v.consistency_pct), true)" in html, "Ein-Klick zeigt den Toast")
    ok("altId: d.archiviert && d.alt ? d.alt.id : null" in html, "Reset zeigt den Toast mit alter Zeile")
    for x in f:
        print("✗", x)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
