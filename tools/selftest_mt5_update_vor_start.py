#!/usr/bin/env python3
"""Selbsttest UPDATE VOR JEDEM KALTSTART (mt5-copier/panel.py _update_vor_start_noetig / _update_dann_start / start_terminal /
_heal_ea_inner / _mt5_update_stand, 08.10.2026, Slave-Terminal 4 — Finn: UAC „Client Terminal AVX2" mit liveupdate\\terminal64.exe
/updateadmin bei C:\\MT5-100kpips21002811, „so fixen, dass die nie wieder kommt"). Ohne Windows: provision wird nachgebildet.
Geprüft: (1) nur DIESE Installation (Pfad normalisiert), (2) ohne stille Aufgabe → None (nichts tun, wie bisher), (3) Prüf-Fehler → None,
(4) _update_dann_start räumt UPDATE_LAEUFT/HEAL_ACTIVE auch bei Fehler und startet danach mit ohne_update=True (kein Kreislauf),
(5) Quelltext: start_terminal prüft vor dem Kaltstart (vor _update_abwarten), legt Marker an und kehrt sofort zurück; die Heilung
spielt vor dem Neustart synchron ein; snapshot liefert mt5_update. Aufruf: python3 tools/selftest_mt5_update_vor_start.py"""
import os
import re
import sys
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HIER, "..", "mt5-copier", "panel.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    src = open(PANEL, encoding="utf-8").read()
    i = src.index("\nUPDATE_LAEUFT = set()")
    j = src.index("\ndef _mt5_update_stand(")
    k = src.find("\n\n\n", j)
    return src, src[i:k]


class Prov:
    def __init__(self, ok=True, aus=None, wirf=False):
        self.ok, self.aus, self.wirf, self.eingespielt = ok, aus or [], wirf, []

    def update_aufgabe_ok(self):
        return self.ok

    def update_ausstehend(self):
        if self.wirf:
            raise OSError("kaputt")
        return list(self.aus)

    def mt5_updates_einspielen(self, aus, max_s=300):
        self.eingespielt.append(list(aus))
        if self.wirf:
            raise RuntimeError("schtasks")
        return ["OK C:\\\\MT5-x 5.0.0.1 -> 5.0.0.2"]


def main():
    src, teil = lade()
    starts = []
    ns = {"os": os, "time": time, "threading": threading, "HEAL_LOCK": threading.Lock(), "HEAL_ACTIVE": set(),
          "UPDATE_ABGELEHNT": "/nicht/da", "print": lambda *a, **k: None,
          "start_terminal": lambda f, c=None, ohne_update=False: (starts.append((f, c, ohne_update)), (True, "gestartet"))[1]}
    exec(teil, ns)
    A, B = r"C:\MT5-100kpips21002811", r"C:\MT5-andere"
    p = Prov(aus=[(A, (5, 0, 0, 1), (5, 0, 0, 2)), (B, (5, 0, 0, 1), (5, 0, 0, 2))])
    ns["provision"] = p
    r = ns["_update_vor_start_noetig"](A)
    check(r == [(A, (5, 0, 0, 1), (5, 0, 0, 2))], f"1 nur diese Installation ({r})")
    check(ns["_update_vor_start_noetig"](r"C:\MT5-ohne") is None, "1b kein Build für diese Installation → None")
    ns["provision"] = Prov(ok=False, aus=p.aus)
    check(ns["_update_vor_start_noetig"](A) is None, "2 ohne stille Aufgabe → None (Start wie bisher)")
    ns["provision"] = Prov(wirf=True)
    check(ns["_update_vor_start_noetig"](A) is None, "3 Prüf-Fehler → None")
    # 4: Hintergrund räumt Marker und startet ohne erneute Prüfung — auch wenn das Einspielen wirft
    for wirf in (False, True):
        starts.clear()
        q = Prov(aus=[(A, (5, 0, 0, 1), (5, 0, 0, 2))], wirf=wirf)
        ns["provision"] = q
        ns["UPDATE_LAEUFT"].add(A); ns["HEAL_ACTIVE"].add(A)
        ns["_update_dann_start"]("config-x.json", A, q.aus, {"login": "1"})
        check(A not in ns["UPDATE_LAEUFT"] and A not in ns["HEAL_ACTIVE"] and starts == [("config-x.json", {"login": "1"}, True)]
              and q.eingespielt == [q.aus], f"4 Marker geräumt + Start mit ohne_update=True (Einspielen {'wirft' if wirf else 'ok'})")
    # 5: Quelltext
    st = src[src.index("\ndef start_terminal("):src.index("\nPAGE = r")]
    i_upd, i_abw = st.find("_update_vor_start_noetig(install_dir)"), st.find("_update_abwarten(install_dir)")
    check(0 < i_upd < i_abw, "5 start_terminal prüft vor dem Kaltstart (vor _update_abwarten)")
    check("ohne_update=False" in st.split("\n")[1] and "None if ohne_update else" in st, "5b ohne_update schaltet die Prüfung ab")
    check(re.search(r"UPDATE_LAEUFT\.add\(install_dir\)\s+HEAL_ACTIVE\.add\(install_dir\)", st) is not None
          and "threading.Thread(target=_update_dann_start" in st, "5c Marker unter Lock, Einspielen im Hintergrund (Proxy-Timeout 25 s)")
    he = src[src.index("\ndef _heal_ea_inner("):src.index("\ndef _remove_later(")]
    check(he.find("_update_vor_start_noetig(install_dir)") < he.find("_update_abwarten(install_dir)") and "_update_einspielen(fname, aus)" in he,
          "5d Heilung spielt vor dem Neustart synchron ein")
    check('"mt5_update": _mt5_update_stand()' in src, "5e snapshot liefert mt5_update")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
