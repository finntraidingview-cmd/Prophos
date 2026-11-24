#!/usr/bin/env python3
"""Selbsttest KL1 (24.11.2026, Plan e20b62f5 Ina FTMO572103 pc-xc5c52, 19:17 Dubai: „Konto FTMO572103 steht im Dropdown 0x … auch nach dem
Tradovate-Login 'FTMOhwethy'" — wie KA1-F am 23.11. 26×). Kein Chrome, kein Netz, keine Order.

Befund aus der Spur: eigener Formular-Login klappte, die Kontoliste war VOLLSTÄNDIG (liste_kurz true, gescrollt: 1 Abschnitt, Ende, scrollTop
0→0 von 196 = 5 Zeilen) und enthielt das Ziel nicht. Prophos führt 7 FTMO-Konten, TradingView zeigt 5 — es fehlen die zwei ältesten (27.10.);
572103 lief zuletzt am 12.11. cdp_konto_familie kannte FTMO nicht → cdp_konto_weg (gleiche Familie verlangt) griff nie → kein 'konto_weg',
endloses Neu-Einplanen. Prüft:
 (1) FTMO-Nummern sind Familie 'ftmo' (auch 7-stellig, auch aus dem gekürzten Stück), alle anderen Familien unverändert;
 (2) der echte Fall ergibt nach dem eigenen Login cdp_konto_weg = (True, 5 Konten, kein Einzelkonto) — vorher nein;
 (3) Riegel bleiben: ohne eigenen Formular-Login, mit hängender Liste, mit Ziel im Text oder bei anderer Firma nie 'konto_weg';
 (4) Login-Belege: andere Firma (Tradeify/Apex aktiv, FTMO-Ziel) = sicher anderer Login; FTMO↔FTMO nur mit vollständiger Liste (wie Tradeify)."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# (1) Familie
for nr in ("FTMO572103", "FTMO9512332", "ftmo535039", "FTMO-644459"):
    check(ob.cdp_konto_familie(nr) == "ftmo", f"{nr} → ftmo")
check(ob.cdp_konto_familie("FTMOX123") == "" and ob.cdp_konto_familie("1510012345") == "", "kein FTMO+Ziffer bzw. MT5-Nummer → unbekannt")
check(ob.cdp_konto_familie_stueck("FTMO53503") == "ftmo", "gekürztes Stück FTMO53503… → ftmo")
alt = {"PAAPEX6687940000012": "apex:668794", "TDFYU460373529": "tradeify", "FTDFY12345": "tradeify", "LFE0001": "lucid", "TOF12": "lucid",
       "FNFTCHAHMAD59829": "fundednext", "MFFU1234": "mff"}
check(all(ob.cdp_konto_familie(k) == v for k, v in alt.items()), "Apex/Tradeify/Lucid/FundedNext/MFF unverändert")

# (2) der echte Fall (order_signale eb4fccf8 15:17 UTC, extra + Login-Spur)
EX = {"konto_treffer": 0, "liste_aktiv": "FTMO535039 47,033.36 USD", "liste_zu": True, "ziel_im_text": False,
      "konto_eintraege": ["FTMO535039 USD", "FTMO272515 USD", "FTMO9512332 USD", "FTMO439839 USD", "FTMO644459 USD"]}
check(ob.cdp_konto_weg(EX, True, "FTMO572103") == (True, 5, False), "eigener Login + vollständige Liste ohne Ziel → konto_weg (5 Konten im Login)")
alt_f = ob.cdp_konto_familie
try:
    ob.cdp_konto_familie = lambda nr: "" if str(nr).upper().startswith("FTMO") else alt_f(nr)
    check(ob.cdp_konto_weg(EX, True, "FTMO572103") == (False, None, False), "Gegenprobe: ohne FTMO-Familie (alter Stand) nie konto_weg")
finally:
    ob.cdp_konto_familie = alt_f

# (2b) zweiter Fall (Master 24.11.2026 19:2x Dubai, Chris pc-c19p2l Plan da9dd15c FTMO110764, order_signale 15:24 UTC): gleiches Muster —
# eigener Login klappte, Liste vollständig (4 Konten, scrollTop 0→0 von 164), Ziel zuletzt gehandelt 17.11.
EX2 = {"konto_treffer": 0, "liste_aktiv": "FTMO879191 47,003.36 USD", "liste_zu": True, "ziel_im_text": False,
       "konto_eintraege": ["FTMO879191 USD", "FTMO296819 USD", "FTMO943996 USD", "FTMO220768 USD"]}
check(ob.cdp_konto_weg(EX2, True, "FTMO110764") == (True, 4, False), "Chris FTMO110764: eigener Login + vollständige Liste ohne Ziel → konto_weg (4 Konten)")

# (3) Riegel unverändert
check(ob.cdp_konto_weg(EX, False, "FTMO572103")[0] is False, "ohne eigenen Formular-Login nie konto_weg")
check(ob.cdp_konto_weg(dict(EX, liste_zu=False), True, "FTMO572103")[0] is False, "hängende Liste nie Beleg")
check(ob.cdp_konto_weg(dict(EX, ziel_im_text=True), True, "FTMO572103")[0] is False, "Ziel im sichtbaren Text → nie konto_weg")
check(ob.cdp_konto_weg(dict(EX, liste_aktiv="TDFYU460373529 150,000.00 USD"), True, "FTMO572103")[0] is False,
      "aktiver Login einer anderen Firma → nie konto_weg (erst Login-Wechsel)")
check(ob.cdp_konto_weg(dict(EX, konto_treffer=None), True, "FTMO572103")[0] is False, "ohne Listen-Beleg (konto_treffer None) nie konto_weg")

# (4) Login-Belege
KO = {"liste_voll": False, "liste_kurz": True, "liste_voll_grund": "Container ragt aus dem Fenster",
      "eintraege": [{"text": t} for t in EX["konto_eintraege"]]}
check(ob.cdp_liste_beleg(KO, "FTMO535039 47,033.36 USD", "FTMO572103") == (True, ""), "FTMO↔FTMO: vollständige Liste mit aktivem Konto = Beleg (wie bisher)")
check(ob.cdp_liste_beleg(dict(KO, liste_kurz=False), "FTMO535039 47,033.36 USD", "FTMO572103")[0] is False,
      "FTMO↔FTMO: unvollständige Liste = kein Beleg (wie Tradeify)")
check(ob.cdp_liste_beleg({"liste_voll": False, "liste_kurz": False}, "TDFYU460373529 150,000.00 USD", "FTMO572103") == (True, ""),
      "Tradeify aktiv, FTMO-Ziel → sicher anderer Login, auch ohne vollständige Liste")
check(ob.cdp_ein_konto_beleg("TDFYU4603735… 150,000.00 USD", "FTMO572103") is True, "gekürztes Tradeify-Konto aktiv, FTMO-Ziel → anderer Login")
check(ob.tv_login_urteil("FTMO535039 47,033.36 USD", "FTMO572103") == "passt" and ob.tv_login_urteil("TDFYU460373529 1 USD", "FTMO572103") == "anderer",
      "tv_login_urteil: FTMO↔FTMO passt, Tradeify↔FTMO anderer")
check(ob.cdp_scroll_noetig({"liste_voll": False}, "FTMO535039 47,033.36 USD", "FTMO572103") is True
      and ob.cdp_scroll_noetig({"liste_voll": False}, "TDFYU460373529 1 USD", "FTMO572103") is False,
      "Scrollen nur im FTMO-Login, bei anderer Firma nicht (Login-Wechsel kommt ohnehin)")

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
