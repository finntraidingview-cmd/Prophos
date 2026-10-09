#!/usr/bin/env python3
"""Selbsttest TOPSTEPX-DLL-KONTEN OHNE „$" (09.10.2026, Terminal 2 — Inas neue Topstep-Konten: Balance-Lesen meldete „Konto
150KTC-SKU-V2-DLL-688698-… in der TopstepX-Liste: Konto nicht in der Liste (0×)", obwohl TopstepX beide Einträge zeigte).
Ursache: alle TopstepX-Konto-Muster verlangten „$" vor der Kontogröße („$150K Trading Combine|…"), die DLL-Konten heißen
„150K DLL Combine|150KTC-SKU-V2-DLL-…". Geprüft mit genau diesen Texten: augen_tsx.js RX_LISTE / RX_AUSLOESER / RX_OHNE_ID (aus der
Datei gezogen, Syntax = Python re) und order_bot.py tsx_konto_sichtbar / tsx_konto_steht / tsx_k2_eintrag / TSX_RX_KONTO; alte
Texte mit „$" unverändert. Aufruf: python3 tools/selftest_tsx_dll_konto.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_rx(src, name):
    m = re.search(r"var " + name + r" = /(.+)/(i?);\n", src)
    return re.compile(m.group(1), re.I if m.group(2) else 0)


def main():
    js = open(os.path.join(HIER, "..", "mt5-copier", "augen_tsx.js"), encoding="utf-8").read()
    liste, ausl, ohne = js_rx(js, "RX_LISTE"), js_rx(js, "RX_AUSLOESER"), js_rx(js, "RX_OHNE_ID")
    dll1, dll2 = "150KTC-SKU-V2-DLL-688698-78993822", "150KTC-SKU-V2-DLL-688698-79232396"

    for t, idw in ((f"150K DLL COMBINE | {dll1}", dll1), (f"150K DLL Combine|{dll2}", dll2)):
        m = liste.match(t)
        check(bool(m) and m.group(2).upper() == idw, f"JS RX_LISTE: „{t}“ → {idw}")
    m = liste.match("$150K Trading Combine|150KTC-SKU-V2-123456-12345678 (Ineligible)")
    check(bool(m) and m.group(2) == "150KTC-SKU-V2-123456-12345678" and m.group(3) == "Ineligible", "JS RX_LISTE: alter Text mit „$“ + (Ineligible) unverändert")
    check(not liste.match("Market") and not liste.match("MNQZ26"), "JS RX_LISTE: Order-Typ/Contract-Optionen weiter kein Konto")
    m = ausl.search("150K DLL Combine|150KTC-SKU-V2-DLL-68869…")
    check(bool(m) and m.group(1).upper().startswith("150KTC-SKU-V2-DLL-68869") and m.group(2), "JS RX_AUSLOESER: gekürzter DLL-Auslöser erkannt")
    check(bool(ohne.match("150K DLL COMBINE |")), "JS RX_OHNE_ID: DLL-Auslöser ohne Kennung erkannt")

    # Negativfälle (Prüfer T3, 09.10.2026): eine nackte Menge ohne „$“ und ohne Wort nach dem K ist kein Konto
    for t in ("5K", "12.5K", "1K", "5K |", "12.5K|ABCDEF-123"):
        check(not ausl.search(t) and not ohne.match(t) and not liste.match(t), f"JS: „{t}“ ist kein Konto-Auslöser/keine Kontozeile")
    import order_bot as ob
    for t in ("5K", "12.5K", "1K"):
        check(ob.tsx_konto_sichtbar(t) == ("", False) and not ob.TSX_RX_OHNE_ID.match(t) and ob.tsx_konto_steht(t, "ABCDEF-123") == "nein",
              f"Python: „{t}“ ist kein Konto-Auslöser")
    k, kurz = ob.tsx_konto_sichtbar(f"150K DLL Combine|{dll1}")
    check(k == dll1 and not kurz, "tsx_konto_sichtbar: volle DLL-Kennung ohne „$“")
    check(ob.tsx_konto_steht(f"150K DLL Combine|{dll1}", dll1) == "ja", "tsx_konto_steht: DLL-Konto 'ja'")
    check(ob.tsx_konto_steht("150K DLL Combine|150KTC-SKU-V2-DLL-68869…", dll2) == "vielleicht", "tsx_konto_steht: gekürzt 'vielleicht'")
    check(ob.tsx_konto_steht("150K DLL COMBINE |", dll1) == "unbekannt", "tsx_konto_steht: ohne Kennung 'unbekannt' (Liste beweist)")
    check(ob.tsx_konto_steht("$150K EXPRESS | EXPRESS-V2-000000-00000000", "EXPRESS-V2-000000-00000000") == "ja", "tsx_konto_steht: alter Text mit „$“ unverändert")
    m = ob.TSX_RX_KONTO.search(f"150K DLL COMBINE | {dll1}")
    check(bool(m) and m.group(1).upper() == dll1, "TSX_RX_KONTO: DLL-Zeile ohne „$“")
    zeilen = [{"id": liste.match(t).group(2).upper(), "rect": [10, 10, 300, 30], "zu": {}}
              for t in (f"150K DLL COMBINE | {dll1}", f"150K DLL COMBINE | {dll2}")]
    e, n, grund = ob.tsx_k2_eintrag(zeilen, dll2)
    check(e is not None and n == 1, f"tsx_k2_eintrag: {dll2} genau einmal gefunden ({grund})")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
