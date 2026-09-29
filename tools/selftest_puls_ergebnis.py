#!/usr/bin/env python3
"""Selbsttest für POST /puls-ergebnis/<pc_id> (app.py) — nur die rein rechnende Säuberung, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_puls_ergebnis.py
Anlass 29.09.2026: Finns Order 15:50 UTC lief am PC durch, die Antwort erreichte Prophos nie — seitdem meldet der Bot das Ergebnis
zusätzlich selbst; die Route darf nur bekannte Felder und gültige Pakete annehmen."""
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json}

    def block(name):
        i = src.index(f"def {name}(")
        j = src.find("\n\n\n", i)
        return src[i:j]

    def zeile(name):
        return re.search(rf"^{name} = .*?(?=\n\S)", src, re.M | re.S).group(0)
    exec("\n".join([zeile("PULS_ERGEBNIS_MAX"), zeile("PULS_ERGEBNIS_FELDER"), zeile("_PLAN_ID_MUSTER"), block("puls_ergebnis_saeubern")]), ns)
    return ns


def main():
    a = lade()
    s = a["puls_ergebnis_saeubern"]
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    paket = {"plan_id": "5ab15b24-fe29-45c1-a8d5-f1672b169bc4", "art": "order", "stufe": "ende", "at_ms": 1790697033000,
             "konto": "TDFYSL150800892182", "symbol": "MNQZ6", "richtung": "buy",
             "ergebnis": {"ok": True, "gesendet": True, "einstieg": "30606", "tp_limit": 30722.5, "sl_limit": 30490.5,
                          "balance_start": 157065.08, "passwort": "nie", "meldung_roh": ["x"] * 20, "trail_ende": "t" * 5000}}
    z = s(paket, "pc-usq1i6")
    check(z and z["plan_id"] == paket["plan_id"] and z["art"] == "order" and z["stufe"] == "ende" and z["pc_id"] == "pc-usq1i6"
          and z["abgeholt_at"] is None, "gültiges Paket → Zeile, abgeholt_at zurückgesetzt")
    e = (z or {}).get("ergebnis", {})
    check("passwort" not in e and e.get("konto") == "TDFYSL150800892182" and e.get("symbol") == "MNQZ6" and e.get("richtung") == "buy"
          and e.get("at_ms") == 1790697033000, "nur bekannte Felder, Top-Level ins ergebnis")
    check(len(e.get("meldung_roh", [])) == 14 and len(e.get("trail_ende", "")) == 1500, "Listen und Spur gekürzt")
    check(s(dict(paket, art="kauf"), "pc-x1234") is None and s(dict(paket, plan_id="x;drop"), "pc-x1234") is None
          and s(dict(paket, stufe="mitte"), "pc-x1234") is None and s({"plan_id": paket["plan_id"], "art": "order"}, "pc-x1234") is None
          and s(None, "pc-x1234") is None, "ungültige Art/Plan-ID/Stufe/ohne ergebnis → None")
    gross = dict(paket, ergebnis=dict(paket["ergebnis"], pruefung={"text": "p" * 40000}))
    zg = s(gross, "pc-usq1i6")
    check(zg and "pruefung" not in zg["ergebnis"], "zu groß → pruefung/Spur fallen weg, Rest bleibt")
    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
