#!/usr/bin/env python3
"""Selbsttest TOPSTEPX GEBLOWT-AUGE (14.10.2026 — Finn am Bild von Mikes TopstepX-Dropdown: „…37040641 (MAXIMUM_LOSS Violation)“,
„…72341888 (MAXIMUM_LOSS Violation)“, „…21889193 (Ineligible)“; Vorfall 13.10.: Endlesungen scheiterten 8× an „You Hit Your Maximum
Loss Limit. Account: …“). Geprüft mit genau diesen Texten, rein rechnend (kein Chrome): order_bot tsx_konto_verletzung /
tsx_verletzungen_aus_liste / tsx_blow_dialog / tsx_blow_dialog_knopf / tsx_geblowt_urteil und augen_tsx.js RX_LISTE (Klammertext als
Hinweis). Aufruf: python3 tools/selftest_tsx_geblowt.py"""
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


def main():
    import order_bot as ob
    # (1) Klammertext → Art
    check(ob.tsx_konto_verletzung("MAXIMUM_LOSS Violation") == "maximum_loss", "MAXIMUM_LOSS Violation → maximum_loss")
    check(ob.tsx_konto_verletzung("DAILY_LOSS Violation") == "daily_loss", "DAILY_LOSS Violation → daily_loss")
    check(ob.tsx_konto_verletzung("Ineligible") == "ineligible", "Ineligible → ineligible")
    check(ob.tsx_konto_verletzung("CONSISTENCY Violation") == "violation", "sonstige Violation → violation")
    check(ob.tsx_konto_verletzung("") == "" and ob.tsx_konto_verletzung(None) == "", "leer → gesund")
    check(ob.tsx_konto_verletzung("Funded") == "", "Fremdtext ohne Verletzung → gesund")

    # (2) Liste wie augen_tsx.js kontoListe() sie liefert (Bild Mike 14.10.2026)
    liste = [
        {"text": "150K DLL COMBINE | 150KTC-SKU-V2-DLL-682437-17758280", "id": "150KTC-SKU-V2-DLL-682437-17758280", "hinweis": None, "ineligible": False},
        {"text": "$150K TRADING COMBINE | 150KTC-SKU-V2-682437-37040641 (MAXIMUM_LOSS Violation)", "id": "150KTC-SKU-V2-682437-37040641",
         "hinweis": "MAXIMUM_LOSS Violation", "ineligible": False},
        {"text": "$150K TRADING COMBINE | 150KTC-SKU-V2-682437-72341888 (MAXIMUM_LOSS Violation)", "id": "150ktc-sku-v2-682437-72341888",
         "hinweis": "MAXIMUM_LOSS Violation", "ineligible": False},
        {"text": "$150K TRADING COMBINE | 150KTC-SKU-V2-682437-21889193 (Ineligible)", "id": "150KTC-SKU-V2-682437-21889193",
         "hinweis": None, "ineligible": True},
        "kaputt", {"id": "", "hinweis": "MAXIMUM_LOSS Violation"},
    ]
    v = ob.tsx_verletzungen_aus_liste(liste)
    check(set(v) == {"150KTC-SKU-V2-682437-37040641", "150KTC-SKU-V2-682437-72341888", "150KTC-SKU-V2-682437-21889193"},
          "Liste → genau die drei Konten mit Hinweis (Kennung groß, gesunde fehlen, kaputte Zeilen ignoriert)")
    check(v["150KTC-SKU-V2-682437-37040641"] == {"art": "maximum_loss", "text": "MAXIMUM_LOSS Violation"}, "…41 maximum_loss mit Text")
    check(v["150KTC-SKU-V2-682437-21889193"]["art"] == "ineligible", "…93 Ineligible nur aus dem Flag")
    check(ob.tsx_verletzungen_aus_liste(None) == {} and ob.tsx_verletzungen_aus_liste([]) == {}, "leere Liste → {}")

    # (3) augen_tsx.js RX_LISTE fängt den Klammertext (Gruppe 3) — Parität JS/Python
    src = open(os.path.join(HIER, "..", "mt5-copier", "augen_tsx.js"), encoding="utf-8").read()
    m = re.search(r"var RX_LISTE = /(.+)/(i?);\n", src)
    rx = re.compile(m.group(1), re.I)
    t = rx.match("$150K TRADING COMBINE | 150KTC-SKU-V2-682437-37040641 (MAXIMUM_LOSS Violation)")
    check(bool(t) and t.group(2) == "150KTC-SKU-V2-682437-37040641" and t.group(3) == "MAXIMUM_LOSS Violation", "RX_LISTE: Kennung + Hinweis „MAXIMUM_LOSS Violation“")
    t = rx.match("150K DLL COMBINE | 150KTC-SKU-V2-DLL-682437-75407161")
    check(bool(t) and t.group(3) is None, "RX_LISTE: gesunde Zeile ohne Hinweis")
    check("text_voll" in src and "tsx-0.6.2" in src, "augen_tsx.js tsx-0.6.2 mit text_voll für Loss-Limit-Meldungen")

    # (4) TopstepX-Meldung (Befund 13.10.2026: „You Hit Your Maximum Loss Limit.Account:“ — Text ohne Leerzeichen vor „Account“)
    pops = [{"role": "dialog", "titel": "", "text": "You Hit Your Maximum Loss Limit.Account: 150KTC-SKU-V2-682437-72341888 Your positions have been liquidated.",
             "knoepfe": [{"tag": "button", "text": "OK", "aria": "", "rect": [500, 400, 80, 32]}]}]
    bd = ob.tsx_blow_dialog(pops)
    check(bd is not None and bd["art"] == "maximum_loss" and bd["konto"] == "150KTC-SKU-V2-682437-72341888", "Meldung → maximum_loss + Kennung")
    check(ob.tsx_blow_dialog([{"text": "Session disconnected", "knoepfe": []}]) is None, "fremder Dialog → keine Meldung")
    check(ob.tsx_blow_dialog([{"text": "You Hit Your Daily Loss Limit.", "text_voll": "You Hit Your Daily Loss Limit. Account: 150KTC-SKU-V2-DLL-682437-17758280"}])["konto"]
          == "150KTC-SKU-V2-DLL-682437-17758280", "Kennung aus text_voll (hinter den 160 Zeichen), Daily → daily_loss")
    check(ob.tsx_blow_dialog([{"text": "You Hit Your Maximum Loss Limit."}])["konto"] == "", "Meldung ohne Kennung → konto ''")
    check(ob.tsx_blow_dialog(None) is None and ob.tsx_blow_dialog(["x"]) is None, "kein/kaputtes popups → None")

    # (5) Schließ-Knopf: genau einer mit reinem Schließ-Wort, nie Order-/Positions-Wort, nie zwei
    check(ob.tsx_blow_dialog_knopf(bd["popup"])["text"] == "OK", "ein OK-Knopf → gedrückt werden darf OK")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "Close Position", "rect": [1, 1, 50, 20]}]}) is None, "„Close Position“ nie")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "OK", "rect": [1, 1, 50, 20]}, {"text": "Close", "rect": [1, 1, 50, 20]}]}) is None,
          "zwei Kandidaten → nichts drücken")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "OK", "rect": [1, 1, 0, 0]}]}) is None, "Knopf ohne Rechteck → nichts")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "Close", "rect": [1, 1, 20, 20]}]})["text"] == "Close", "X-Knopf nur mit aria „Close“")
    check(not re.search(ob.TSX_DIALOG_TABU, "OK", re.I) and re.search(ob.TSX_DIALOG_TABU, "Flatten all", re.I), "Tabu: OK frei, Flatten tabu")

    # (6) Urteil fürs Zielkonto
    ext = "150KTC-SKU-V2-682437-72341888"
    g = ob.tsx_geblowt_urteil({"konto_hinweis": "MAXIMUM_LOSS Violation"}, ext)
    check(g == {"art": "maximum_loss", "quelle": "liste", "text": "MAXIMUM_LOSS Violation"}, "konto_hinweis am Ziel → liste/maximum_loss")
    g = ob.tsx_geblowt_urteil({"konto_verletzungen": v}, ext)
    check(g is not None and g["quelle"] == "liste" and g["art"] == "maximum_loss", "konto_verletzungen[ext] → liste")
    check(ob.tsx_geblowt_urteil({"konto_verletzungen": v}, "150KTC-SKU-V2-DLL-682437-75407161") is None, "gesundes Ziel trotz Liste → None")
    g = ob.tsx_geblowt_urteil({"blow_dialog": {"art": "maximum_loss", "konto": ext, "text": "You Hit…"}}, ext)
    check(g is not None and g["quelle"] == "dialog", "Meldung nennt das Ziel → dialog")
    check(ob.tsx_geblowt_urteil({"blow_dialog": {"art": "maximum_loss", "konto": "150KTC-SKU-V2-682437-37040641", "text": "x"}}, ext) is None,
          "Meldung nennt ein ANDERES Konto → Ziel nicht geblowt")
    check(ob.tsx_geblowt_urteil({"blow_dialog": {"art": "maximum_loss", "konto": "", "text": "x"}}, ext, aktiv=ext)["quelle"] == "dialog",
          "Meldung ohne Kennung + Ziel aktiv → dialog")
    check(ob.tsx_geblowt_urteil({"blow_dialog": {"art": "maximum_loss", "konto": "", "text": "x"}}, ext, aktiv="150KTC-SKU-V2-DLL-682437-75407161") is None,
          "Meldung ohne Kennung + anderes Konto aktiv → None")
    check(ob.tsx_geblowt_urteil({"konto_hinweis": "Ineligible"}, ext)["art"] == "ineligible", "Ineligible zählt als geblowt (Finn 14.10.2026)")
    check(ob.tsx_geblowt_urteil({}, ext) is None and ob.tsx_geblowt_urteil(None, "") is None, "ohne Beweis → None")

    # (7) Verdrahtung: Felder laufen durch, Meldung nur einmal je Lauf, Ineligible bleibt lesbar (tsx_k2_eintrag)
    quelle = open(os.path.join(HIER, "..", "mt5-copier", "order_bot.py"), encoding="utf-8").read()
    check('"konto_verletzungen", "blow_dialog")' in quelle, "Lesepfad reicht konto_verletzungen/blow_dialog durch")
    check(quelle.count("_tsx_geblowt_merken(res, ext, st)") >= 2, "Urteil im Lesepfad bei K2-Fehler UND nach der Lesung")
    check('_raus("konto_geblowt"' in quelle, "K2: Meldung nennt das Ziel → Code konto_geblowt")
    check('res["_blow_dialog_versucht"] = True' in quelle, "Meldung wird höchstens einmal je Lauf gedrückt")
    x, n, grund = ob.tsx_k2_eintrag([{"id": "150KTC-SKU-V2-682437-21889193", "hinweis": "Ineligible", "ineligible": True, "rect": [10, 10, 300, 30], "zu": {}}],
                                    "150KTC-SKU-V2-682437-21889193")
    check(x is not None and n == 1, "Ineligible-Zeile bleibt zum Lesen wählbar (Entscheidung 01.10.2026)")
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    check("async function tsxGeblowtFolge(" in html and html.count("tsxGeblowtFolge(") >= 3, "PC-Tab: tsxGeblowtFolge in Balance-Lesen + Endlesung")
    check("grund: 'tsx'" in html and "anlass = " in open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read(), "Push-Text: TopstepX-Grund statt „nicht in der Liste“")

    # (8) NEUE MELDUNG + SYMBOL-X (19.10.2026, Finn am Bild von Mikes TopstepX nach dem Login — „This account is no longer eligible for
    # funding", Knöpfe RESET TRADING COMBINE / USE ACCOUNT TO PRACTICE / X ohne Text und aria; 16.10. 4× „kein eindeutiger Schließ-Knopf“)
    neu = {"role": "dialog", "titel": "This account is no longer eligible for funding",
           "text": "This account is no longer eligible for funding Account: 150KTC-SKU-V2-DLL-682437-17758280 You hit the Maximum Loss Limit on this account on 10/16/2026, so it's no longer eligib",
           "text_voll": "This account is no longer eligible for funding Account: 150KTC-SKU-V2-DLL-682437-17758280 You hit the Maximum Loss Limit on this account on 10/16/2026, so it's no longer eligible for funding. It's still yours to trade in practice mode. Reset it whenever you're ready to trade for funding again. Ready to Reset? Reset your Trading Combine and get back to trading with a fresh account. RESET TRADING COMBINE USE ACCOUNT TO PRACTICE Don't remind me again for this account",
           "knoepfe": [{"tag": "button", "text": "", "aria": "", "icon": "CloseIcon", "ecke": True, "rect": [1180, 218, 24, 24]},
                       {"tag": "button", "text": "RESET TRADING COMBINE", "aria": "", "ecke": False, "rect": [792, 656, 392, 34]},
                       {"tag": "button", "text": "USE ACCOUNT TO PRACTICE", "aria": "", "ecke": False, "rect": [776, 732, 424, 40]}]}
    bd = ob.tsx_blow_dialog([neu])
    check(bd is not None and bd["art"] == "maximum_loss" and bd["konto"] == "150KTC-SKU-V2-DLL-682437-17758280",
          "neue Meldung „no longer eligible for funding“ → maximum_loss + volle Kennung (nicht „account is“)")
    check(ob.tsx_blow_dialog([{"text": "You hit the Maximum Loss Limit on this account on 10/16/2026"}]) is not None, "„hit the … Loss Limit“ erkannt")
    kn = ob.tsx_blow_dialog_knopf(neu)
    check(kn is not None and kn.get("icon_x") is True and kn["text"] == "" and kn["rect"][0] == 1180, "Symbol-X (CloseIcon, Ecke) ist der Schließ-Knopf — nie RESET/PRACTICE")
    kn = ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "", "ecke": True, "rect": [1180, 218, 24, 24]}, {"text": "RESET TRADING COMBINE", "rect": [1, 1, 50, 20]}]})
    check(kn is not None and kn.get("icon_x") is True, "Symbol-X nur über die Ecke (ohne icon-Namen)")
    kn = ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "", "icon": "CloseIcon", "ecke": False, "rect": [600, 400, 24, 24]}]})
    check(kn is not None and kn.get("icon_x") is True, "Symbol-X nur über den icon-Namen (nicht in der Ecke)")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "", "icon": "ExpandMoreIcon", "ecke": True, "rect": [1180, 218, 24, 24]}]}) is None,
          "Symbol in der Ecke mit Expand-Namen → nichts")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "Reset account", "ecke": True, "rect": [1180, 218, 24, 24]}]}) is None,
          "Symbol-Knopf mit fremdem aria → nichts")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "", "ecke": True, "rect": [1180, 218, 24, 24]},
                                                 {"text": "", "aria": "", "ecke": True, "rect": [1150, 218, 24, 24]}]}) is None, "zwei Symbol-X → nichts")
    kn = ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "OK", "rect": [1, 1, 50, 20]}, {"text": "", "aria": "", "icon": "CloseIcon", "ecke": True, "rect": [1180, 218, 24, 24]}]})
    check(kn is not None and kn["text"] == "OK" and not kn.get("icon_x"), "Schließ-Wort geht vor dem Symbol-X")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "", "icon": "CloseIcon", "ecke": True, "rect": [1180, 218, 0, 0]}]}) is None,
          "Symbol-X ohne Rechteck → nichts")
    v2 = ob.tsx_blow_dialog_verletzung(bd)
    check(v2 == {"150KTC-SKU-V2-DLL-682437-17758280": {"art": "maximum_loss", "text": bd["text"][:60], "quelle": "dialog"}},
          "genanntes Konto (volle Kennung) → konto_verletzungen-Eintrag mit Quelle dialog")
    check(ob.tsx_blow_dialog_verletzung({"art": "maximum_loss", "konto": "150KTC-SKU-V2-DLL-6", "text": "x"}) == {}, "gekürzte Kennung (16.10.) → kein Eintrag")
    check(ob.tsx_blow_dialog_verletzung({"art": "maximum_loss", "konto": "", "text": "x"}) == {} and ob.tsx_blow_dialog_verletzung(None) == {}, "ohne Kennung → {}")
    check(ob.tsx_geblowt_urteil({"konto_verletzungen": v2}, "150KTC-SKU-V2-DLL-682437-17758280")["quelle"] == "dialog", "Urteil nimmt die Quelle des Eintrags (dialog)")
    check(ob.tsx_geblowt_urteil({"konto_verletzungen": v2}, "EXPRESS-V2-682437-57131691") is None, "Meldung fürs vorgewählte Konto → Ziel EXPRESS nicht geblowt (Finn 19.10.2026)")
    check(bool(ob.TSX_RX_KENNUNG_VOLL.match("EXPRESS-V2-682437-57131691")) and not ob.TSX_RX_KENNUNG_VOLL.match("150KTC-SKU-V2-682437"), "Kennungs-Form …-USERID-NUMMER")
    check("tsx-0.6.3" in src and "function xMerkmale" in src and "kurz(b, xMerkmale(b, d))" in src and "eligible for funding" in src,
          "augen_tsx.js tsx-0.6.3: icon/ecke je Dialog-Knopf, text_voll auch bei „eligible for funding“")
    check('verletzungen.update(bd_res.get("konto_verletzungen") or {})' in quelle and 'bd_offen = tsx_blow_dialog(' in quelle,
          "K2: Meldung vor dem Auslöser-Klick (auch ohne „verdeckt“), genanntes Konto in die Antwort")
    check('"tabu": TSX_DIALOG_TABU}' in quelle and 'if kn.get("icon_x"):' in quelle, "Symbol-X wird mit Rechteck-/Tabu-Beweis gedrückt")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} Fehler:")
        for f in FEHLER:
            print("  - " + f)
        sys.exit(1)
    print("alles grün")


if __name__ == "__main__":
    main()
