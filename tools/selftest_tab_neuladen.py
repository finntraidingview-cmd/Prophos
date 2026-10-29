#!/usr/bin/env python3
"""Selbsttest TAB SELBST NEU LADEN (mt5-copier/panel.py tab_neuladen_entscheiden + app.py tab_stand_riegel, 16.10.2026).

Anlass: Finn 16.10.2026 „Wenn man den Tab neu laden muss, mach das als Bot — wie beim Balancelesen. Nie mehr Hand-F5." (Chris · PC
hing auf .1565 mit „Popup offen").
Aufruf:  python3 tools/selftest_tab_neuladen.py
Geprüft: (1) Tab aktuell / inhaltsgleich → nichts; (2) hinter < 20 min → warten; ≥ 20 min → laden (auch über tab_bw.hinter_seit);
(3) stumm ≥ 10 min → laden; (4) Riegel/Puls-Lock/Eingabe am PC/15-min-Abstand → warten mit Grund; (5) Railway nicht lesbar → nichts;
(6) Server-Riegel: Signal läuft, Hedge öffnet, Start geclaimt, Start bald (unbestätigter Vorschlag zählt nicht)."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def bloecke(pfad, namen, konst=()):
    src = open(pfad, encoding="utf-8").read()
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in konst]
    for n in namen:
        i = src.index(f"\ndef {n}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    return "\n\n".join(teile)


def main():
    ns = {"re": re, "datetime": datetime}
    exec(bloecke(os.path.join(HIER, "..", "mt5-copier", "panel.py"), ["_build_nr", "tab_neuladen_entscheiden", "tab_oeffnen_entscheiden", "puls_tab_entscheiden"],
                 ["TAB_NL_HINTER_S", "TAB_NL_HINTER_BG_S", "TAB_NL_STUMM_S", "TAB_NL_IDLE_S", "TAB_NL_ABSTAND_S", "TAB_OEFFNEN_FEHLT_S", "TAB_OEFFNEN_ANLAUF_S",
                  "TAB_OEFFNEN_ABSTAND_S", "TAB_OEFFNEN_MAX_TAG"]), ns)
    f = ns["tab_neuladen_entscheiden"]
    jetzt = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc).timestamp()
    iso = lambda s: datetime.fromtimestamp(jetzt - s, timezone.utc).isoformat()   # noqa: E731
    st = lambda **kw: dict({"ok": True, "origin": "2026-09-22.1586", "tab_build": "2026-09-22.1586", "tab_at": iso(20), "riegel": ""}, **kw)  # noqa: E731

    l, g, h = f(st(), jetzt, None, 0, 999, True)
    check(not l and g == "" and h is None, "Tab aktuell → nichts")
    l, g, h = f(st(tab_build="2026-09-22.1580", tab_gleich="2026-09-22.1586"), jetzt, None, 0, 999, True)
    check(not l and g == "", "inhaltsgleich → nichts")
    l, g, h = f(st(tab_build="2026-09-22.1565"), jetzt, jetzt - 300, 0, 999, True)
    check(not l and "hat bis 20 min Zeit" in g, f"hinter 5 min → warten ({g})")
    l, g, h = f(st(tab_build="2026-09-22.1565"), jetzt, jetzt - 1300, 0, 999, True)
    check(l and "seit 21 min hinter" in g, f"hinter 21 min → laden ({g})")
    l, g, h = f(st(tab_build="2026-09-22.1565", tab_bw={"hinter_seit": (jetzt - 3600) * 1000}), jetzt, None, 0, 999, True)
    check(l and "seit 60 min" in g, f"tab_bw.hinter_seit (Tab-Wächter) zählt ({g})")
    l, g, h = f(st(tab_at=iso(700)), jetzt, None, 0, 999, True)
    check(l and "stumm seit 11 min" in g, f"stumm 11 min → laden ({g})")
    alt = st(tab_build="2026-09-22.1565")
    l, g, h = f(dict(alt, riegel="Start in ≤ 5 min"), jetzt, jetzt - 1300, 0, 999, True)
    check(not l and "wartet: Start in ≤ 5 min" in g, f"Server-Riegel → warten ({g})")
    l, g, h = f(alt, jetzt, jetzt - 1300, 0, 999, False)
    check(not l and "Puls/MT5-Order läuft" in g, "TV_ORDER_LOCK oder MASTER_ORDER_LOCKS belegt → warten")
    l, g, h = f(alt, jetzt, jetzt - 1300, 0, 30, True)
    check(not l and "letzte Eingabe vor 30 s" in g, "Eingabe am PC vor 30 s → warten")
    l, g, h = f(alt, jetzt, jetzt - 1300, jetzt - 300, 999, True)
    check(not l and "höchstens 1 je 15 min" in g, "letzter Versuch vor 5 min → warten")
    l, g, h = f(alt, jetzt, jetzt - 1300, jetzt - 1000, None, True)
    check(l, "Abstand > 15 min, Eingabe unbekannt → laden")
    l, g, h = f(None, jetzt, None, 0, 999, True)
    check(not l and "nicht lesbar" in g, "Railway nicht lesbar → nichts")
    l, g, h = f({"ok": False, "msg": "x"}, jetzt, None, 0, 999, True)
    check(not l, "Railway ok:false → nichts")

    # lokal still (keine /api/instances-Abfrage) zählt wie stumm — auch ohne mt5_live-Zeile
    l, g, h = f({"ok": True, "origin": "2026-09-22.1587", "tab_build": None, "tab_at": None, "riegel": ""}, jetzt, None, 0, 999, True, 700)
    check(l and "keine Abfrage beim Panel" in g, f"lokal still 11 min, ohne mt5_live → laden ({g})")
    l, g, h = f(st(), jetzt, None, 0, 999, True, 120)
    check(not l and g == "", "lokal still 2 min → nichts")

    o = ns["tab_oeffnen_entscheiden"]
    s0 = jetzt - 3600
    check(o(jetzt, jetzt - 20, s0, False, 0, 0, True, 999) == (False, ""), "Tab fragt → nichts öffnen")
    check(o(s0 + 60, 0, s0, False, 0, 0, True, 999) == (False, ""), "Panel läuft erst 1 min → nichts")
    a, g = o(jetzt, jetzt - 400, s0, False, 0, 0, True, 999)
    check(a and "seit 6 min keine Abfrage" in g, f"6 min still, kein Fenster → öffnen ({g})")
    a, g = o(jetzt, jetzt - 400, s0, True, 0, 0, True, 999)
    check(not a and "kein zweiter Tab" in g, "Prophos-Fenster da → nie zweiter Tab")
    a, g = o(jetzt, jetzt - 400, s0, False, jetzt - 600, 0, True, 999)
    check(not a and "höchstens 1 je 20 min" in g, "letzter Versuch vor 10 min → warten")
    a, g = o(jetzt, jetzt - 400, s0, False, 0, 8, True, 999)
    check(not a and "Deckel 8" in g, "8× heute → Deckel")
    a, g = o(jetzt, jetzt - 400, s0, False, 0, 0, False, 999)
    check(not a and "Puls/MT5-Order" in g, "Lock belegt → warten")
    a, g = o(jetzt, jetzt - 400, s0, False, 0, 0, True, 20)
    check(not a and "letzte Eingabe vor 20 s" in g, "Eingabe am PC → warten")
    a, g = o(jetzt, jetzt - 400, s0, False, 0, 0, True, 999, True)
    check(not a and "im Hintergrund oder von Chrome verworfen" in g, "Chrome läuft, Prophos-Tab im Puls-Chrome (Heilung) → nie zweiter (S2)")
    a, g = o(jetzt, jetzt - 400, s0, False, 0, 0, True, 999, True, False)
    check(a and "seit 6 min keine Abfrage" in g, "Chrome läuft, aber kein Prophos-Tab im Puls-Chrome → dort öffnen (alter Tab wird nur ansehen)")

    # PROPHOS IM PULS-CHROME HALTEN (30.10.2026): Haupt-Tab lebt woanders, im Puls-Chrome fehlt Prophos
    pt = ns["puls_tab_entscheiden"]
    check(pt(jetzt, s0, True, 0, True, 0, 0, "", True, 999)[0] is True, "Puls-Chrome ohne Prophos, Haupt-Tab lebt woanders → öffnen")
    check(pt(jetzt, s0, True, 1, True, 0, 0, "", True, 999) == (False, "") and pt(jetzt, s0, False, 0, True, 0, 0, "", True, 999) == (False, "")
          and pt(jetzt, s0, True, 0, False, 0, 0, "", True, 999) == (False, "") and pt(s0 + 60, s0, True, 0, True, 0, 0, "", True, 999) == (False, ""),
          "schon einer im Puls-Chrome / Puls-Chrome aus / gar kein Tab lebt (alter Weg) / Anlauf → nichts")
    check("einer ist Haupt-Tab" in pt(jetzt, s0, True, 2, True, 0, 0, "", True, 999)[1], "zwei im Puls-Chrome → melden, keiner geschlossen")
    check("Signal läuft" in pt(jetzt, s0, True, 0, True, 0, 0, "Signal läuft", True, 999)[1] and "Puls/MT5-Order" in pt(jetzt, s0, True, 0, True, 0, 0, "", False, 999)[1]
          and "Eingabe vor 20 s" in pt(jetzt, s0, True, 0, True, 0, 0, "", True, 20)[1] and "Deckel" in pt(jetzt, s0, True, 0, True, 0, 8, "", True, 999)[1]
          and "höchstens 1 je 20 min" in pt(jetzt, s0, True, 0, True, jetzt - 600, 0, "", True, 999)[1],
          "Riegel: Server-Riegel, Puls/MT5-Order, Eingabe am PC, Tages-Deckel, Abstand")

    # Herzschlag mit Login/URL/Kennung (16.10.2026)
    import time as _t
    hz = {"re": re, "time": _t}
    exec(bloecke(os.path.join(HIER, "..", "mt5-copier", "panel.py"), ["haupt_tab_waehlen", "tab_gesehen", "neben_tab_frei"],
                 ["_TAB_OEFFNEN", "TAB_URL_RE", "TAB_HAUPT_FRISCH_S", "_TABS", "_TAB_HAUPT"]), hz)
    hz["tab_gesehen"]("Mozilla/5.0", {"tab": ["1"], "login": ["1"], "url": ["http://localhost:5000/"]})
    check(hz["_TAB_OEFFNEN"]["zuletzt"] == 0.0, "Panel-Seite im Browser zählt nicht als Tab")
    hz["tab_gesehen"]("python-requests/2.32", {"tab": ["1"], "login": ["0"], "url": ["http://127.0.0.1:5000/"], "tid": ["abc"]})
    t0 = hz["_TAB_OEFFNEN"]
    check(t0["zuletzt"] > 0 and t0["url"] == "http://127.0.0.1:5000/" and t0["login"] is False and t0["tid"] == "abc",
          f"Herzschlag: URL/Login/Kennung gemerkt ({t0['url']}, {t0['login']})")
    hz["tab_gesehen"]("python-requests/2.32", {"tab": ["1"], "login": ["1"], "url": ["https://boese.example/x"]})
    check(t0["url"] == "http://127.0.0.1:5000/" and t0["login"] is True, "fremde URL wird nie übernommen (nur localhost/127.0.0.1)")
    hz["tab_gesehen"]("python-requests/2.32", None)
    check(t0["login"] is True, "alter Tab ohne Angaben: nur Herzschlag")

    # HAUPT-TAB (30.10.2026): genau einer zählt — angemeldet vor nicht angemeldet, Puls-Chrome vor anderem Chrome, kein Flattern
    H, T = hz["haupt_tab_waehlen"], hz["_TABS"]
    check(hz["tab_gesehen"]("python-requests/2.32", {"tab": ["1"], "login": ["1"], "url": ["http://localhost:5000/"], "tid": ["neu"]}) is True
          and hz["tab_gesehen"]("python-requests/2.32", {"tab": ["1"], "login": ["0"], "url": ["http://127.0.0.1:5000/"], "tid": ["abc"]}) is False
          and hz["_TAB_HAUPT"]["tid"] == "neu", "angemeldeter Tab wird Haupt-Tab, der nicht angemeldete bekommt haupt_tab:false")
    z0 = t0["zuletzt"]
    _t.sleep(0.01)
    hz["tab_gesehen"]("python-requests/2.32", {"tab": ["1"], "login": ["0"], "url": ["http://127.0.0.1:5000/"], "tid": ["abc"]})
    check(t0["zuletzt"] == z0 and t0["url"] == "http://localhost:5000/", "zweiter Tab zählt nie als Herzschlag, überschreibt nichts")
    j1 = 1000.0
    tabs = {"a": {"at": j1 - 5, "login": True, "puls": None}, "b": {"at": j1 - 1, "login": True, "puls": None}}
    check(H(tabs, j1, "a") == "a" and H(tabs, j1, "") == "b", "gleicher Rang → der bisherige bleibt (kein Flattern), sonst der jüngste")
    tabs["b"]["puls"] = True
    check(H(tabs, j1, "a") == "b", "Tab im Puls-Chrome schlägt den anderen Chrome")
    tabs["b"]["login"] = False
    check(H(tabs, j1, "b") == "a", "nicht angemeldet im Puls-Chrome verliert gegen angemeldet woanders")
    check(H({"a": {"at": j1 - 61, "login": True}}, j1, "a") == "", "kein Tab fragt ≤ 60 s → keiner")
    N = hz["neben_tab_frei"]
    check(N(tabs, "b", False, j1, "a") is False and N(tabs, "b", True, j1, "a") is True and N({"a": {"at": j1 - 120, "login": True}}, "b", False, j1, "a") is True,
          "nur ansehen → wieder Haupt-Tab, wenn der Haupt-Tab tot ist oder dieser Tab höher rangiert (angemeldet + Puls-Chrome)")

    an = {"_ap_ts": lambda r: datetime.fromisoformat(str(r).replace("Z", "+00:00")) if r else None}
    exec(bloecke(os.path.join(HIER, "..", "app.py"), ["tab_stand_riegel"]), an)
    r = an["tab_stand_riegel"]
    j = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)
    t = lambda m: (j + timedelta(minutes=m)).isoformat()   # noqa: E731
    check(r([{"id": 1}], [], "pc-a", j).startswith("Puls/Signal läuft"), "Signal läuft → Riegel")
    check(r([], [{"status": "open", "hedge_status": "oeffnet", "hedge_pc": "pc-a"}], "pc-a", j) == "Hedge öffnet/schließt", "Hedge öffnet → Riegel")
    check(r([], [{"status": "open", "hedge_status": "oeffnet", "hedge_pc": "pc-b"}], "pc-a", j) == "", "Hedge auf anderem PC → frei")
    check(r([], [{"status": "planned", "start_um_gestartet_at": t(-3)}], "pc-a", j) == "Start geclaimt (< 6 min)", "Start geclaimt → Riegel")
    check(r([], [{"status": "planned", "start_um": t(4)}], "pc-a", j) == "Start in ≤ 5 min", "Handplan startet in 4 min → Riegel")
    check(r([], [{"status": "planned", "start_um": t(4), "auto_plan": True}], "pc-a", j) == "", "unbestätigter Vorschlag startet nie → frei")
    check(r([], [{"status": "planned", "start_um": t(30)}], "pc-a", j) == "", "Start in 30 min → frei")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
