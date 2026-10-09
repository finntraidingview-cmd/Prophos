#!/usr/bin/env python3
"""Selbsttest ABMELDEN: GENAUE URSACHE BEI OFFENEM DIALOG (order_bot.py _cdp_abmelden / _cdp_abmelden_dialog, 09.10.2026, Terminal 2 —
Muster „Tradovate-Login … nicht geschafft (abmelden)": ~13× in 7 Tagen auf 4 PCs; in den Spuren vom 06.10. und 09.10. lag „Go ad-free.
Everywhere" über der Seite, die Meldung sprach nur von „kein eindeutiges 'Log out' (0 Treffer)").
Ohne Windows/Chrome: _cdp_abmelden läuft aus dem Quelltext gegen nachgebaute Sitzung/Blick. Geprüft: Menü leer + Dialog offen → Meldung
nennt den Dialog mit Handgriff, KEIN Esc; Menü leer ohne Dialog → alte Meldung + Esc; Menü mit anderem Eintrag → alte Meldung + Esc (kein
zusätzliches Lesen); Knopf nicht klickbar + Dialog → Dialog in der Meldung; fremdes Fenster → Fenster-Hinweis bleibt, Dialog wird dann
nicht gelesen; Erfolgsweg liest den Stand nicht zusätzlich. Aufruf: python3 tools/selftest_puls_abmelden_dialog.py"""
import os
import re
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HIER, "..", "mt5-copier", "order_bot.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


class Sitzung:
    def __init__(self, popups=None, klick_ok=True, fremd=""):
        self.popups, self.klick_ok, self.fremd = popups or [], klick_ok, fremd
        self.ws, self.tasten, self.stand_n, self.klicks = None, [], 0, []

    def werbung_weg(self, zwang=False):
        return 0

    def klick(self, rect, name):
        self.klicks.append(name)
        return self.klick_ok if name == "Kontextmenü neben Tradovate" else True

    def taste(self, k):
        self.tasten.append(k)

    def fremd_hinweis(self):
        return f" Fenster '{self.fremd}' liegt über dem Puls-Chrome — immer im Vordergrund?" if self.fremd else ""

    def stand(self, opts=None):
        self.stand_n += 1
        return {"popups": self.popups, "abgemeldet": True}


def lauf(src, sitzung, menue):
    ns = {"time": time, "re": re}

    class Ort:
        def __init__(self, *a):
            pass

        def blick(self):
            return {"ctx": [10, 10, 20, 20], "menue": menue, "dialoge": []}

    ns.update({
        "_K3Ort": Ort,
        "cdp_rect": lambda r: r if r else None,
        "_cdp_menue_abwarten": lambda ort, trail, praefix: {"menue": menue},
        "k3_label": lambda m: str(m.get("text") if isinstance(m, dict) else m),
        "K3_RX_ABMELDEN": re.compile(r"^log ?out$", re.I),
        "_warte": lambda *a: None,
        "cdp_abgemeldet": lambda st: bool(st.get("abgemeldet")),
    })

    def k3_eindeutig(liste, rx):
        t = [m for m in (liste or []) if rx.search(str(m.get("text") or ""))]
        return (t[0] if len(t) == 1 else None), len(t)

    ns["k3_eindeutig"] = k3_eindeutig
    exec(fn(src, "_cdp_abmelden_dialog"), ns)
    exec(fn(src, "_cdp_abmelden"), ns)
    trail = []
    ok, text = ns["_cdp_abmelden"](sitzung, {}, trail)
    return ok, text, trail


def main():
    src = open(BOT, encoding="utf-8").read()
    dlg = [{"titel": "Go ad-free. Everywhere"}]

    s = Sitzung(popups=dlg)
    ok, text, trail = lauf(src, s, [])
    check(not ok and "Dialog 'Go ad-free. Everywhere' liegt über der Seite" in text and "→ im Puls-Chrome den Dialog schließen" in text,
          "Menü leer + Dialog offen → Meldung nennt den Dialog mit Handgriff")
    check("Escape" not in s.tasten and any("kein Esc" in t for t in trail), "… und kein Esc in den offenen Dialog")
    check("0 Treffer" not in text, "… keine Sammelmeldung „0 Treffer“")

    s = Sitzung()
    ok, text, _ = lauf(src, s, [])
    check(not ok and text.startswith("Im Kontextmenü kein eindeutiges 'Log out' (0 Treffer)") and s.tasten == ["Escape"],
          "Menü leer ohne Dialog → alte Meldung + Esc")

    s = Sitzung(popups=dlg)
    ok, text, _ = lauf(src, s, [{"text": "Settings"}])
    check(not ok and "(0 Treffer)" in text and s.tasten == ["Escape"] and s.stand_n == 0,
          "Menü mit anderem Eintrag → alte Meldung + Esc, Stand nicht zusätzlich gelesen")

    s = Sitzung(popups=dlg, klick_ok=False)
    ok, text, _ = lauf(src, s, [])
    check(not ok and text.startswith("Kontextmenü neben 'Tradovate' ließ sich nicht klicken: Dialog 'Go ad-free. Everywhere'"),
          "Knopf nicht klickbar + Dialog → Dialog in der Meldung")

    s = Sitzung(popups=dlg, klick_ok=False, fremd="Tradeify Dashboard")
    ok, text, _ = lauf(src, s, [])
    check(not ok and "Fenster 'Tradeify Dashboard' liegt über dem Puls-Chrome" in text and s.stand_n == 0,
          "fremdes Fenster → Fenster-Hinweis bleibt, Dialog wird nicht gelesen")

    s = Sitzung(popups=dlg)
    ok, text, _ = lauf(src, s, [{"text": "Log out"}])
    check(ok and s.stand_n == 1 and "Menü 'Log out'" in s.klicks,
          "Erfolgsweg: Log out geklickt, Stand nur für den Abmelde-Beweis gelesen")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
