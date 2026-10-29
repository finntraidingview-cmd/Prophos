#!/usr/bin/env python3
"""Selbsttest: UPDATE-SCHUTZ (29.10.2026, Befund „Deploy-Welle"). Lokales app.py startet für ein Update nur ohne laufenden /copier-Aufruf
und mit freiem Panel neu, der Panel-Versions-Wächter prüft direkt vor dem Beenden noch einmal, beide gestreut 0–60 s, nach 15 min Deckel
trotzdem. Ohne Netz.  Aufruf: python3 tools/selftest_update_schutz.py"""
import io
import json
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel  # noqa: E402


def lade_app():
    src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(r"^LOCAL_UPDATE_DECKEL_S = .*$", src, re.M).group(0)]
    i = src.index("\ndef local_update_entscheiden(") + 1
    teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns, src


def main():
    f = []
    ok = lambda b, t: f.append(t) if not b else print("✓", t)   # noqa: E731
    ns, src = lade_app()
    L = ns["local_update_entscheiden"]
    T = 10_000.0
    # lokales app.py
    ok(L(0, [], T - 60, T, T + 30)[0] == "warten" and "Streuung" in L(0, [], T - 60, T, T + 30)[1], "app.py: in der Streuzeit nie neu starten")
    ok(L(0, [], T - 60, T, T - 1) == ("jetzt", ""), "app.py: kein Aufruf, Panel frei → jetzt")
    ok(L(0, None, T - 60, T, T - 1) == ("jetzt", ""), "app.py: Panel aus/alt (None) und kein Aufruf → jetzt (wie bisher)")
    e, g = L(2, [], T - 60, T, T - 1)
    ok(e == "warten" and "2 laufende" in g, f"app.py: laufender /copier-Aufruf → warten ({g})")
    e, g = L(0, ["TradingView-/TopstepX-Lauf (TV_ORDER_LOCK)"], T - 60, T, T - 1)
    ok(e == "warten" and "TV_ORDER_LOCK" in g, "app.py: Panel belegt → warten")
    e, g = L(1, ["MT5-Order x"], T - 15 * 60, T, T - 1)
    ok(e == "erzwingen" and "15 min" in g, f"app.py: 15 min belegt → Deckel erzwingt ({g[:40]})")
    ok(L(1, [], T - 14 * 60, T, T - 1)[0] == "warten", "app.py: 14 min belegt → noch warten")
    # Proxy-Zähler und Schließen im Quelltext (der Proxy ist nur mit Flask testbar)
    ok("_PROXY[\"n\"] += 1" in src and "_PROXY[\"n\"] -= 1" in src and "finally:" in src[src.index("def copier_proxy("):src.index("def _copier_proxy_lauf(")]
       and '"code": "backend_neustart"' in src, "app.py: Zähler mit finally um jeden /copier-Aufruf, geschlossener Proxy antwortet 503 backend_neustart")
    w = src[src.index("def _local_version_watcher("):src.index("def _local_port_taken(")]
    ok(w.index('_PROXY["zu"] = True') < w.index("os._exit(0)") and "if noch and entsch != \"erzwingen\"" in w and "_local_update_spur(" in w,
       "app.py-Watcher: erst schließen, dann Nachzählen (Lücke), Deckel meldet Spur, dann Exit")

    # Panel
    P = panel.update_neustart_entscheiden
    ok(P([], T - 60, T, T + 5)[0] == "warten" and P([], T - 60, T, T - 1) == ("jetzt", ""), "Panel: Streuung, dann frei → jetzt")
    ok(P(["Polar-Lauf"], T - 60, T, T - 1)[0] == "warten" and P(["Polar-Lauf"], T - 900, T, T - 1)[0] == "erzwingen", "Panel: belegt → warten, nach 15 min Deckel")
    alt_prov = panel.PROV_JOB
    try:
        panel.PROV_JOB = None
        ok(panel.panel_beschaeftigt_gruende() == [] or all("Handlauf" in x for x in panel.panel_beschaeftigt_gruende()), "Panel: ohne Lauf frei")
        with panel.TV_ORDER_LOCK:
            g = panel.panel_beschaeftigt_gruende()
        ok(any("TV_ORDER_LOCK" in x for x in g), f"Panel: TV_ORDER_LOCK gehalten → belegt ({g})")
        lk = panel.MASTER_ORDER_LOCKS.setdefault("config-test.json", panel.threading.Lock())
        with lk:
            g = panel.panel_beschaeftigt_gruende()
        panel.MASTER_ORDER_LOCKS.pop("config-test.json", None)
        ok(any("MT5-Order" in x for x in g), "Panel: MT5-Order-Sperre → belegt")
        panel.PROV_JOB = {"done": False}
        ok("Provisionierung" in panel.panel_beschaeftigt_gruende(), "Panel: laufende Provisionierung → belegt")
    finally:
        panel.PROV_JOB = alt_prov
    q = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
    vw = q[q.index("def _version_watcher("):q.index("def _selbst_auffrischen(")]
    ok(vw.index("_panel_code_geaendert(neuester)") < vw.index("update_neustart_entscheiden(panel_beschaeftigt_gruende()") < vw.rindex("os._exit(0)"),
       "Panel-Watcher: zweite Prüfung NACH dem Holen und direkt vor os._exit")
    ok('if path == "/api/beschaeftigt":' in q and q.index('if not self._local_ok():') < q.index('if path == "/api/beschaeftigt":'),
       "Panel: /api/beschaeftigt hinter _local_ok (nur lokal)")
    # Prüfer-Befunde: laufende Panel-POSTs zählen, zu → 503, Leerlauf mit/ohne Deckel, Lauf-Teilmenge für app.py
    panel._PANEL_POST.update(n=1, zu=False)
    g = panel.panel_beschaeftigt_gruende()
    ok(any("Panel-Aufruf" in x for x in g) and panel.panel_lauf_gruende(g) == [x for x in g if "Panel-Aufruf" in x or "TV_ORDER_LOCK" in x],
       "Panel: laufender POST → belegt und zählt für app.py")
    ok(panel.panel_lauf_gruende(["Polar-Lauf", "K3-Handlauf", "Provisionierung"]) == [], "Panel: Polar/Handlauf/Provisionierung betreffen app.py nicht")
    ok(panel._panel_zu_und_leeren(False) is False and panel._PANEL_POST["zu"] is False, "Panel: ohne Deckel und belegt → wieder auf, nicht beenden")
    alt_l = panel.UPDATE_LEERLAUF_S
    try:
        panel.UPDATE_LEERLAUF_S = 1.0
        import threading as _th, time as _t
        _th.Timer(0.6, lambda: panel._PANEL_POST.update(n=0)).start()
        t0 = _t.time()
        r = panel._panel_zu_und_leeren(True)
        ok(r is True and 0.5 <= _t.time() - t0 < 1.5 and panel._PANEL_POST["zu"] is True, "Panel: Deckel → zu, wartet auf das Ende des Laufs, dann beenden")
    finally:
        panel.UPDATE_LEERLAUF_S = alt_l
        panel._PANEL_POST.update(n=0, zu=False)
    hq = q[q.index("    def do_POST(self):"):q.index("    def _do_post_innen(self):")]
    ok('"/api/tsx-stand"' in hq and '_PANEL_POST["n"] += 1' in hq and "finally:" in hq and '"code": "backend_neustart"' in hq and '"_nichtGesendet": True' in hq,
       "Panel: do_POST zählt (außer tsx-stand) mit finally, zu → 503 backend_neustart/_nichtGesendet")
    vw2 = q[q.index("def _version_watcher("):q.index("def _selbst_auffrischen(")]
    ok('upd["code"] = {neuester: _panel_code_geaendert(neuester)}' in vw2 and "_panel_zu_und_leeren(" in vw2 and vw2.rindex("finally:") < vw2.rindex("os._exit(0)"),
       "Panel-Watcher: Codeänderung je Stand nur einmal geholt, zu+leeren vor dem Beenden, os._exit im finally")
    # app.py: Panel-Abfrage (aus/alt → None, unklar → belegt, lauf zählt)
    class _Exc:
        class ConnectionError(Exception):
            pass
    class _R:
        def __init__(self, code, d):
            self.status_code, self._d = code, d
        def json(self):
            if isinstance(self._d, Exception):
                raise self._d
            return self._d
    def gruende(antwort):
        ns2 = {"COPIER_PANEL": "http://x"}
        class _Rq:
            exceptions = _Exc
            @staticmethod
            def get(url, timeout=5):
                if isinstance(antwort, Exception):
                    raise antwort
                return antwort
        ns2["requests"] = _Rq
        i = src.index("\ndef _local_panel_gruende(") + 1
        exec(src[i:src.find("\n\n\n", i)], ns2)
        return ns2["_local_panel_gruende"]()
    ok(gruende(_Exc.ConnectionError()) is None and gruende(_R(404, {})) is None, "app.py: Panel aus (refused) oder alt (404) → None")
    ok(gruende(TimeoutError()) and gruende(_R(500, {})) and gruende(_R(200, ValueError())), "app.py: Zeitüberschreitung/500/kein JSON → belegt (unklar)")
    ok(gruende(_R(200, {"frei": False, "gruende": ["Polar-Lauf"], "lauf": []})) == [] and gruende(_R(200, {"lauf": ["MT5-Order a"]})) == ["MT5-Order a"],
       "app.py: nur die Lauf-Gründe zählen (Polar hält app.py nicht auf)")
    ok('upd["code"] = {rv: _local_code_geaendert()}' in w or 'upd["code"] = {rv: _local_code_geaendert()}' in src, "app.py-Watcher: app.py je Stand nur einmal holen")
    for t in f:
        print("✗", t)
    print("alle Tests bestanden" if not f else f"FEHLER ({len(f)})")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
