#!/usr/bin/env python3
"""Selbsttest KURZ-SUMMARY-KEYS (30.10.2026, Slave 5 — Master nach dem Befund „Userscript 0 von 26": auf PCs mit Script 0.10.x scheiterte das
Reader-Ende bei gekürzten Kontonamen (FTDFYSLX…/PAAPEX…) 4× an „Balance fehlt", b1 null — tvBalanceAus fand in der Reader-Zusammenfassung keine
Balance). Diagnose: bei fehlender Balance gehen die LABEL-NAMEN der Zusammenfassung (nie Beträge) als summary_keys an reader_kurz_nein.

Ohne Netz und ohne Node: summaryKeysKurz + tvBalanceAus per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten. Dazu der Quelltext-
Vertrag: kurzEndeBeweis gibt summary_keys NUR ohne Balance mit, kurzEndeMelden schreibt sie an reader_kurz_nein.
Aufruf: python3 tools/selftest_kurz_summary_keys.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_abhaken_geblowt_vorbelegen.py)."""
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


def main():
    src = open(HTML, encoding="utf-8").read()
    faelle = {
        "leer": None,
        "array": [],
        "ohne": {},
        "neu": {"Cash": "$150,123.45", "Net Liq": "$150,123.45", "Realized P&L": "$0.00"},
        "lang": {("Label " + str(i) + " " + "x" * 50): "1" for i in range(30)},
        "alt": {"Account Balance": "$150,123.45", "Equity": "$150,123.45"},
        # Prüfer S2 zu f5b81959: Beträge im Label-Namen werden maskiert
        "betrag": {"Net Liq $51,234.56": "x", "Balance 48.512,30": "y", "Day 2 P&L": "z"},
    }
    js = "\n".join([
        "function tvGeldText(v){ var n = Number(String(v).replace(/[^0-9.\\-]/g, '')); return isFinite(n) && String(v).trim() ? n : null }",
        js_funktion(src, "summaryKeysKurz"), js_funktion(src, "tvBalanceAus"),
        f"var F = {json.dumps(faelle)}, out = {{}};",
        "for (var k in F) out[k] = { keys: summaryKeysKurz(F[k]), bal: tvBalanceAus(F[k]).balance };",
        "print(JSON.stringify(out));",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        pfad = f.name
    try:
        r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(pfad)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        check(False, "jsc lief nicht")
        return 1
    o = json.loads(r.stdout.strip().splitlines()[-1])
    check(o["leer"]["keys"] == "keine Zusammenfassung" and o["array"]["keys"] == "keine Zusammenfassung", "ohne Objekt → 'keine Zusammenfassung'")
    check(o["ohne"]["keys"] == "Zusammenfassung leer", "leeres Objekt → 'Zusammenfassung leer'")
    check(o["neu"]["keys"] == ["Cash", "Net Liq", "Realized P&L"] and o["neu"]["bal"] is None,
          f"unbekanntes Label: Namen ohne Beträge, tvBalanceAus findet nichts ({o['neu']})")
    check(isinstance(o["lang"]["keys"], list) and len(o["lang"]["keys"]) == 24 and all(len(x) <= 40 for x in o["lang"]["keys"]),
          "höchstens 24 Namen à 40 Zeichen")
    check(o["alt"]["bal"] == 150123.45, "bekanntes Label 'Account Balance' liest weiter die Balance")
    check(o["betrag"]["keys"] == ["Net Liq $#", "Balance #", "Day # P&L"] and not any(c.isdigit() for k in o["betrag"]["keys"] for c in k),
          f"Ziffern im Label maskiert, nie ein Betrag ({o['betrag']['keys']})")
    beweis, melden = js_funktion(src, "kurzEndeBeweis"), js_funktion(src, "kurzEndeMelden")
    check("bq.balance == null ? summaryKeysKurz(st.summary) : undefined" in beweis and "summary_keys: sk" in beweis,
          "kurzEndeBeweis: summary_keys nur ohne Balance")
    check("reader_kurz_nein: Object.assign(" in melden and "summary_keys: kurz.summary_keys" in melden, "kurzEndeMelden schreibt summary_keys an reader_kurz_nein")
    check("window._summaryKeysKurz = summaryKeysKurz" in src, "Test-Haken window._summaryKeysKurz")
    print("alle Prüfungen bestanden" if not FEHLER else f"{len(FEHLER)} Fehler")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
