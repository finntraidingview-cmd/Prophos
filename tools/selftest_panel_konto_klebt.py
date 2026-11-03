#!/usr/bin/env python3
"""Selbsttest KLEBENDE BALANCE im Panel (03.11.2026, Lotse L1 → Auftrag X1): das Userscript (kontoNummerAmSchalter) nimmt alle Leerzeichen aus dem
Konto-Knopf, „FTDFYSLX150306272833 161,470.34 USD“ wird „FTDFYSLX150306272833161“. Seit .2013 zählte für den Exit-Fill nur der volle Kontotext — bei allen
5 Big Trades 17:26–17:30 Dubai verwarf das Panel den Fill, der Tab schloss nach 1–3 s. Rohtexte unten echt aus scharf_spur.log / Reader-Stand
(Marco pc-t8wg97, Pascal pc-3wghru, Finn+Pascal pc-2zc2we, Marc pc-7ftp5l, Mike pc-l5o8bv). Geprüft: scharf_fill_konto_ok, scharf_konto_kern(…, ext),
scharf_entscheid mit Exit-Fill. Ohne Netz. Aufruf: python3 tools/selftest_panel_konto_klebt.py"""
import ast
import json
import os
import random
import re
import sys
import tempfile
import threading
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


tmp = tempfile.mkdtemp()
uhr = [10000.0]
ns = {"os": os, "re": re, "json": json, "random": random, "threading": threading, "HERE": tmp, "datetime": __import__("datetime").datetime,
      "time": types.SimpleNamespace(time=lambda: uhr[0], sleep=lambda s: None), "HEDGE_SOLO_LOCK": threading.Lock(), "print": lambda *a, **k: None,
      "_win_leerlauf_s": lambda: 1e9}
for n in ast.parse(SRC).body:
    if isinstance(n, ast.FunctionDef) and n.name == "read_json":
        exec(ast.get_source_segment(SRC, n), ns)
exec(SRC[SRC.index("SCHARF_PFAD = os.path.join(HERE"):SRC.index("_TAB_PULS_OEFFNEN_CODE = (")], ns)
OK, KERN, ENTSCHEID = ns["scharf_fill_konto_ok"], ns["scharf_konto_kern"], ns["scharf_entscheid"]

# echte Kennungen (gemerkt im Panel) und echte Reader-/Fill-Texte
MARCO = "FTDFYSLX150306272833"            # Tradeify WD …2833, Plan fcf2bc87
MARCO_CFD = "FTDFYSLX1503062728"           # Reader-Konto auf Marcos PC 15:57 Dubai: kürzeres Konto derselben ID
FTMO = "FTMO327341"                        # Reader „FTMO32734149“ = FTMO327341 + 49 (49.208,36 $) auf Marcos PC
PASCAL, FP, MARC, MIKE = "FTDFYSLX150742744758", "FTDFYSLX150889401362", "PAAPEX6843320000005", "PAAPEX6708370000001"
NB_MARCO = [MARCO, MARCO_CFD, FTMO, "FTDFYSLX150306272899", "PAAPEX6850100000015"]
NB = lambda eid: [eid, "FTDFYSLX150000000000", "PAAPEX6850100000011"]   # noqa: E731

print("1) Fill-Konto: positiv (richtiges Konto, Balance klebt)")
check(OK("FTDFYSLX150306272833161", MARCO, NB_MARCO), "Marco …2833 + 161 (161.470 $) → zählt")
check(OK("FTDFYSLX150742744758145", PASCAL, NB(PASCAL)), "Pascal …4758 + 145 → zählt")
check(OK("FTDFYSLX150889401362166", FP, NB(FP)), "Finn+Pascal …1362 + 166 → zählt")
check(OK("PAAPEX6843320000005105", MARC, NB(MARC)) and OK("PAAPEX6708370000001157", MIKE, NB(MIKE)), "Apex Marc …5 + 105, Mike …1 + 157 → zählt")
check(OK("FTDFYSLX150306272833", MARCO, [MARCO, FTMO]) and OK("ftdfyslx150306272833 161,470.34 USD", MARCO, [MARCO, FTMO]), "voller Text (auch mit Balance getrennt) → zählt")
check(OK("FTDFYSLX1503062728331", MARCO, NB(MARCO)) and OK("FTDFYSLX150306272833523", MARCO, NB_MARCO), "1 Ziffer (≥ 1 Mio $) / 3 Ziffern (< 1.000 $) → zählt")

print("2) Fill-Konto: negativ (nie schließen)")
check(not OK("FTDFYSLX150306272834161", MARCO, NB_MARCO), "anderes Konto mit ähnlicher Endung (…2834) → nie")
check(not OK("FTDFYSLX150306272899161", MARCO, NB_MARCO), "Nachbarkonto der ID (…2899) mit Balance → nie")
check(not OK("2833161", MARCO, NB_MARCO) and not OK("…2833", MARCO, NB_MARCO) and not OK("272833161", MARCO, NB_MARCO), "nur die Endung → nie")
check(not OK("", MARCO, NB_MARCO) and not OK(None, MARCO, NB_MARCO) and not OK("FTDFYSLX150306272833161", "", NB_MARCO), "leerer Text / leere Kennung → nie")
check(not OK("FTDFYSLX1503062728…", MARCO, NB_MARCO) and not OK("FTDFYSLX15030627283", MARCO, NB_MARCO), "gekürzt (mit und ohne „…“) → nie")
check(not OK("FTDFYSLX1503062728331610", MARCO, NB_MARCO), "4 angeklebte Ziffern → keine Balance-Gruppe → nie")
check(not OK("FTDFYSLX150306272833161", MARCO, [MARCO]) and not OK("FTDFYSLX150306272833161", MARCO, None),
      "Balance klebt, aber Konten der ID unbekannt → nie (fail-closed)")
check(not OK("FTDFYSLX150306272833", MARCO, NB_MARCO),
      "kürzeres Konto der ID + Balance-Ziffern ergibt genau die Kennung („…2728“ + 33.xxx $) → mehrdeutig → nie")
check(not OK("FTDFYSLX1503062728331", MARCO, NB_MARCO), "„…2833“ + 1 Ziffer = „…2728“ + 331.xxx $ (Nachbar der ID) → mehrdeutig → nie")
check(not OK("FTMO32734149", MARCO, NB_MARCO) and not OK("FTMO32734149", FTMO, [FTMO]), "FTMO-Konto (Balance klebt) gegen Marco / ohne Nachbarn → nie")

LANG = MARCO + "16"                          # gedachtes längeres Konto: „…283316“ + 1 → derselbe Text „…2833161“
check(not OK("FTDFYSLX150306272833161", MARCO, [MARCO, "FTDFYSLX 15030627283316"]) and not OK("FTDFYSLX150306272833161", MARCO, [MARCO, "ftdfyslx-150306272833-16"]),
      "Nachbar-ID mit Leerzeichen/Bindestrich (in Prophos), ohne in TradingView → trotzdem als mehrdeutig erkannt → nie")
check(not OK("FTDFYSLX150306272833161", MARCO, NB_MARCO, True) and OK("FTDFYSLX150306272833", MARCO, [MARCO, FTMO], True),
      "Nachbarliste gekappt → angeklebte Balance nie, voller Text weiter")
uhr[0] += 1
nb600 = [MARCO] + [f"FTDFYSLX{150000000000 + i}" for i in range(600)]
ns["scharf_setzen"]({"ext_id": MARCO, "wurzel": "MNQ", "nachbarn": nb600, "richtung": "buy", "menge": 2}, "plan-fcf2bc87", 4711,
                    {"tabs": [{"tab_id": "puls-mw0q0nnf9jy1j1", "version": "0.10.9"}]})
e600 = [x for x in ns["scharf_laden"]() if x.get("ticket") == 4711]
check(len(e600) == 1 and e600[0]["nachbarn_gekappt"] is True and len(e600[0]["nachbarn"]) == ns["SCHARF_NACHBARN_MAX"],
      f"601 Konten der ID → gemerkt mit nachbarn_gekappt true ({ns['SCHARF_NACHBARN_MAX']} gespeichert)")
ns["scharf_setzen"]({"ext_id": MARCO, "wurzel": "MNQ", "nachbarn": NB_MARCO, "richtung": "buy", "menge": 2}, "plan-fcf2bc87", 4712,
                    {"tabs": [{"tab_id": "puls-mw0q0nnf9jy1j1", "version": "0.10.9"}]})
check([x.get("nachbarn_gekappt") for x in ns["scharf_laden"]() if x.get("ticket") == 4712] == [False], "5 Konten → nicht gekappt")

print("3) Kern: Balance-Ziffern sind kein Kontowechsel")
check(KERN("FTDFYSLX150889401362162", FP) == FP == KERN("FTDFYSLX150889401362166", FP), "Finn+Pascal 162 → 166 → derselbe Kern")
check(KERN("PAAPEX6843320000005104", MARC) == KERN("PAAPEX6843320000005105", MARC) == MARC, "Apex 104 ↔ 105 → derselbe Kern")
check(KERN("FTMO32734148", MARCO) == "FTMO32734148" != MARCO and KERN("FTDFYSLX1503062728", MARCO) == "FTDFYSLX1503062728",
      "anderes Konto → anderer Kern (Kontowechsel bleibt sichtbar)")
check(KERN("FTDFYSLX1508111613… 149,969.50 USD", "FTDFYSLX150811161322") == "FTDFYSLX1508111613", "gekürzt → bleibt gekürzter Kern (wie bisher)")
check(KERN("ftdfyslx150811161322 150,000.00 USD") == "FTDFYSLX150811161322" and KERN("") == "" and KERN(None) == "", "ohne ext wie bisher")

print("4) scharf_entscheid mit echten Abläufen")
POS = [{"symbol": "MNQZ6", "wurzel": "MNQ", "richtung": "buy", "menge_zahl": 2}]


def st(konto, pos=None, fill_konto=None, menge=2, seite="sell"):
    return {"an": True, "konto": konto, "positionen": pos or [], "positionen_ok": True, "alter_s": 0.05, "blind": False, "positionen_ts": uhr[0] * 1000,
            "script_version": "0.10.9", "positionen_tab": "puls-mw0q0nnf9jy1j1", "leer_beweis": True,
            "fills": [{"tab_id": "puls-mw0q0nnf9jy1j1", "seite": seite, "menge": menge, "preis": 28284.5, "at": (uhr[0] - 0.17) * 1000, "symbol": "MNQZ6",
                       "art": "tp", "konto": fill_konto, "text": "Sell 2 at 28,284.50"}] if fill_konto is not None else []}


def ablauf(ext, nb, vorher, nachher, fill_konto, beleg=None, gekappt=False, **kw):
    """Position im Konto gesehen (Text vorher), dann erste flache Lesung (Text nachher) mit Exit-Fill → (zu, grund)."""
    e = {"at": uhr[0] - 3600, "ext_id": ext, "wurzel": "MNQ", "nachbarn": nb, "nachbarn_gekappt": gekappt, "richtung": "buy", "menge": 2, "gesehen": False,
         "flach_seit": None, "flach_ts": []}
    zu, e, g = ENTSCHEID(e, st(vorher, POS), uhr[0], beleg)
    if zu or g != "Position da":
        return zu, "vorher: " + g
    uhr[0] += 1
    zu, e, g = ENTSCHEID(e, st(nachher, fill_konto=fill_konto, **kw), uhr[0], beleg)
    uhr[0] += 1
    return zu, g


zu, g = ablauf(MARCO, NB_MARCO, "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", "FTDFYSLX150306272833161")
check(zu and "Exit-Fill" in g, f"Marco fcf2bc87: Fill „…2833161“ → Panel schließt bei der ersten flachen Lesung ({g})")
zu, g = ablauf(FP, NB(FP), "FTDFYSLX150889401362162", "FTDFYSLX150889401362166", "FTDFYSLX150889401362166", menge=2)
check(zu, f"Finn+Pascal 43c68171: Balance 162 → 166 während des Trades → kein „Konto gewechselt“, schließt ({g})")
zu, g = ablauf(MARCO, NB_MARCO, "FTDFYSLX150306272833161", "FTDFYSLX150306272834161", "FTDFYSLX150306272834161")
check(not zu, f"Kontowechsel ins Konto mit ähnlicher Endung → nie ({g})")
zu, g = ablauf(MARCO, NB_MARCO, "FTDFYSLX150306272833161", "FTMO32734148", "FTMO32734148", seite="sell")
check(not zu and g == "Konto nicht sicher", f"Kontowechsel ins FTMO-Konto (Spur 17:24:56) → nie ({g})")
zu, g = ablauf(MARCO, NB_MARCO, "FTDFYSLX150306272833161", "FTDFYSLX150306272833", "FTDFYSLX150306272833")
check(not zu, f"Wechsel ins kürzere Konto „…2728“ mit 33.xxx $ (Text = Kennung) → Fill mehrdeutig → nie ({g})")
zu, g = ablauf(MARCO, NB_MARCO, "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", "")
check(not zu, f"Fill mit leerem Konto → nie ({g})")
zu, g = ablauf(MARCO, NB_MARCO, "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", menge=1)
check(not zu, f"Teil-Fill (1 statt 2) → nie ({g})")
zu, g = ablauf(MARCO, [MARCO, LANG], "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", beleg=MARCO)
check(not zu, f"Puls-Beleg macht den mehrdeutigen Reader-Text sicher, Kern = Kennung — der Fill bleibt mehrdeutig → nie ({g})")
zu, g = ablauf(MARCO, NB_MARCO, "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", gekappt=True)
check(not zu, f"Eintrag mit gekappter Nachbarliste → nie, der Tab schließt ({g})")
zu, g = ablauf(MARCO, [], "FTDFYSLX150306272833161", "FTDFYSLX150306272833161", "FTDFYSLX150306272833161")
check(not zu, f"alter Eintrag ohne Nachbarn, Balance klebt → nie, der Tab schließt ({g})")

print()
if FEHLER:
    print("FEHLER:\n  " + "\n  ".join(FEHLER))
    sys.exit(1)
print("alles grün")
