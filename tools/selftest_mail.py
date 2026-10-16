#!/usr/bin/env python3
"""Selbsttest: Mail-Reiter (app.py mail_zeile, 16.10.2026) — rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_mail.py"""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    i = src.index("MAIL_MAX_STAPEL = ")
    j = src.index("\n\n\ndef _mail_user_zum_schluessel(", i)
    exec(src[i:j], ns)
    return ns


def main():
    ns = lade()
    z = ns["mail_zeile"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)
    u = "11111111-1111-1111-1111-111111111111"
    voll = {"id": "18c1a2b3d4e5f6a7", "thread": "18c1a2b3d4e5f6a0", "von": "Firma <info@example.com>", "an": "x@example.com",
            "betreff": "Payout", "datum": "2026-10-16T05:10:00.000Z", "snippet": "Hallo", "text": "t" * 60_000,
            "html": "<p>" + "h" * 250_000, "anhaenge": [{"name": "rechnung.pdf", "groesse": 12345, "typ": "application/pdf", "daten": "xx"}],
            "gelesen": True, "labels": ["INBOX", None, "Prophos"], "user_id": "22222222-2222-2222-2222-222222222222"}
    r = z(voll, u)
    check(r is not None and r["user_id"] == u, "user_id kommt aus dem Schlüssel, nie aus dem Body")
    check(len(r["text"]) == 50_000 and len(r["html"]) == 200_000, "Text 50 KB, HTML 200 KB gedeckelt")
    check(r["anhaenge"] == [{"name": "rechnung.pdf", "groesse": 12345, "typ": "application/pdf"}], "Anhänge nur Name/Größe/Typ")
    check(r["datum"] == "2026-10-16T05:10:00+00:00", "Datum als UTC-ISO")
    check(r["labels"] == ["INBOX", "Prophos"] and r["gelesen"] is True, "Labels ohne None, gelesen übernommen")
    check(set(r) == {"user_id", "gmail_msg_id", "thread_id", "von", "an", "betreff", "datum", "snippet", "text", "html",
                     "anhaenge", "gelesen", "labels"}, "nur erlaubte Spalten")
    check(z({"id": "../../x"}, u) is None and z({"id": ""}, u) is None and z("kaputt", u) is None, "ungültige ID → verworfen")
    r2 = z({"id": "abc", "datum": "kein datum", "thread": "a b", "anhaenge": "x"}, u)
    check(r2 and r2["datum"] is None and r2["thread_id"] is None and r2["anhaenge"] == [] and r2["text"] is None,
          "kaputte Felder → leer statt Fehler")
    print(f"\n{sum(f)} Fehler von {len(f)}")
    return sum(f)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
