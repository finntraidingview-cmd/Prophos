#!/usr/bin/env python3
"""Selbsttest MT5-EINLOGGEN-FENSTER (order_bot.py ist_mt5_login_dialog / _login_dann_lesen / modus_loginok, panel.py _login_ok_wache,
08.10.2026, Slave-Terminal 4 — Moritz 8a05ebaa: Claim 05:59 → offen 06:04, „API-Lesen 5x 137.4s", erst bei 140 s drückte der Bot OK).
Ohne Windows/MT5: die Funktionen laufen aus dem Quelltext gegen nachgebaute Dialog-/API-Stubs. Geprüft: Signatur (eigenes Konto ja,
fremdes Konto/Titel/ohne OK/ohne Server nein); _login_dann_lesen: ohne Dialog eine Runde mit initialize-Timeout 10 s; Dialog erscheint
erst nach dem ersten Fehlschlag → in der nächsten Runde bestätigt → Erfolg; ohne Erfolg Abbruch nach der Gesamtgeduld; modus_loginok
bestätigt NUR per invoke, gibt nach Ablauf „kein Login-Dialog" zurück, ungültige Eingaben → ok:false; Panel startet die Wache nur nach
dem Kaltstart mit bekanntem Konto. Aufruf: python3 tools/selftest_login_ok.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HIER, "..", "mt5-copier", "order_bot.py")
PANEL = os.path.join(HIER, "..", "mt5-copier", "panel.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


class Uhr:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t


def main():
    src = open(BOT, encoding="utf-8").read()
    uhr = Uhr()
    ns = {"re": re, "time": uhr}
    exec(fn(src, "ist_mt5_login_dialog"), ns)
    sig = ns["ist_mt5_login_dialog"]
    lb = ["Login:", "Passwort:", "Server:"]
    check(sig("Einloggen", lb, ["OK", "Abbrechen"], ["26747348"], 26747348), "Signatur: eigenes Konto → ja")
    check(not sig("Einloggen", lb, ["OK"], ["26747349"], 26747348), "Signatur: fremdes Konto → nein")
    check(not sig("Eigenschaften", lb, ["OK"], ["26747348"], 26747348) and not sig("Einloggen", lb, ["Abbrechen"], ["26747348"], 26747348)
          and not sig("Einloggen", ["Login:"], ["OK"], ["26747348"], 26747348), "Signatur: anderer Titel / ohne OK / ohne Passwort+Server → nein")
    # _login_dann_lesen mit Stubs
    m = re.search(r"^LOGIN_RUNDE_MS = (\d+).*$\n^LOGIN_GEDULD_S = ([\d.]+)", src, re.M)
    runde_ms, geduld = int(m.group(1)), float(m.group(2))
    check(runde_ms == 10000 and geduld >= 100, f"Konstanten: Runde {runde_ms} ms, Geduld {geduld} s")
    welt = {"dialog_ab": None, "ok_nach_bestaetigt": False, "bestaetigt": 0, "aufrufe": [], "dauer": 0.0}

    def bestaetigen(expected, trail=None, wege=("invoke", "klick", "enter")):
        if welt["dialog_ab"] is not None and len(welt["aufrufe"]) >= welt["dialog_ab"]:
            welt["bestaetigt"] += 1
            welt["dialog_ab"] = None
            welt["ok_nach_bestaetigt"] = True
            return "bestaetigt"
        return "keiner"

    def lesen(path, expected, symbol=None, timeout_ms=None):
        welt["aufrufe"].append(timeout_ms)
        uhr.t += welt["dauer"]
        if welt["dialog_ab"] is None and (welt["ok_nach_bestaetigt"] or welt.get("sofort")):
            return {"login": expected}
        return {"fehler": "Terminal-Verbindung fehlgeschlagen"}
    ns.update(_mt5_login_bestaetigen=bestaetigen, _api_lesen=lesen, _warte=lambda a, b: setattr(uhr, "t", uhr.t + a),
              LOGIN_RUNDE_MS=runde_ms, LOGIN_GEDULD_S=geduld)
    exec(fn(src, "_login_dann_lesen"), ns)
    lies = ns["_login_dann_lesen"]
    welt.update(sofort=True); r = lies("C:\\MT5-x\\terminal64.exe", 26747348)
    check("fehler" not in r and welt["aufrufe"] == [10000], f"ohne Dialog: eine Runde, initialize-Timeout 10 s ({welt['aufrufe']})")
    welt.update(sofort=False, aufrufe=[], dialog_ab=1, ok_nach_bestaetigt=False, bestaetigt=0, dauer=20.0)
    r = lies("C:\\MT5-x\\terminal64.exe", 26747348)
    check("fehler" not in r and welt["bestaetigt"] == 1 and len(welt["aufrufe"]) == 2,
          f"Dialog erst nach dem 1. Fehlschlag → nächste Runde bestätigt → Erfolg ({len(welt['aufrufe'])} Lese-Runden)")
    t0 = uhr.t
    welt.update(aufrufe=[], dialog_ab=None, ok_nach_bestaetigt=False, bestaetigt=0, dauer=20.0)
    r = lies("C:\\MT5-x\\terminal64.exe", 26747348)
    check("fehler" in r and geduld <= uhr.t - t0 <= geduld + 25, f"ohne Erfolg: Abbruch nach der Gesamtgeduld ({uhr.t - t0:.0f} s, {len(welt['aufrufe'])} Runden)")
    # modus_loginok: nur invoke
    rufe = []
    ns["_mt5_login_bestaetigen"] = lambda exp, trail=None, wege=None: (rufe.append(wege), "bestaetigt" if len(rufe) >= 3 else "keiner")[1]
    exec(fn(src, "modus_loginok"), ns)
    r = ns["modus_loginok"]("26747348", "90")
    check(r.get("ok") and "bestätigt" in r.get("msg", "") and all(w == ("invoke",) for w in rufe), f"loginok: nur invoke, beim 3. Blick bestätigt ({rufe})")
    rufe.clear(); ns["_mt5_login_bestaetigen"] = lambda exp, trail=None, wege=None: (rufe.append(wege), "keiner")[1]
    r = ns["modus_loginok"]("26747348", "10")
    check(r.get("ok") and r.get("msg") == "kein Login-Dialog" and 2 <= len(rufe) <= 8, f"loginok: ohne Dialog nach Ablauf zurück ({len(rufe)} Blicke)")
    check(ns["modus_loginok"]("abc", "90").get("ok") is False, "loginok: ungültiges Konto → ok:false")
    check('sys.argv[1] == "loginok"' in src, "Bot kennt den Modus loginok")
    # Panel
    ps = open(PANEL, encoding="utf-8").read()
    st = ps[ps.index("\ndef start_terminal("):ps.index("\nPAGE = r")]
    check(re.search(r"if expected:\s+threading\.Thread\(target=_login_ok_wache, args=\(fname, expected\)", st) is not None
          and st.find("_login_ok_wache") > st.find("subprocess.Popen"), "Panel: Wache nur nach dem Kaltstart und nur mit bekanntem Konto")
    w = fn(ps, "_login_ok_wache")
    check('"loginok"' in w and "timeout=sekunden + 30" in w, "Panel: Wache ruft den Bot im Modus loginok mit Zeitlimit")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
