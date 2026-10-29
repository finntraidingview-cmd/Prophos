#!/usr/bin/env python3
"""Selbsttest: TV-Konten lesen trotz offener Echo-/Echo-V2-Pläne (Master 29.10.2026, Befund Chris: drei mt5v2-Trades sperrten das Lesen den
ganzen Tag). PC-Tab: tvkFrei lässt nur mt5/mt5v2 als „offener Plan" aus; Panel /api/tv-konten-liste: bei laufender MT5-Order/Polar oder Arbeit
am PC (< 120 s) → 409 belegt, kein Bot-Start. Panel-Handler mit nachgebauter Anfrage, ohne Netz/Bot.  Aufruf: python3 tools/selftest_tvk_mt5frei.py"""
import io
import json
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel  # noqa: E402


class _Kopf(dict):
    def get(self, k, d=None):
        return super().get(k.lower(), d)


def aufruf(body):
    h = panel.Handler.__new__(panel.Handler)
    raw = json.dumps(body).encode()
    h.path = "/api/tv-konten-liste"
    h.headers = _Kopf({"content-length": str(len(raw)), "content-type": "application/json", "host": "127.0.0.1:8770"})
    h.rfile = io.BytesIO(raw)
    gesendet = {}
    h._send = lambda code, b, ctype=None: gesendet.update(code=code, body=json.loads(b))
    h._local_ok = lambda: True
    h.do_POST()
    return gesendet


def main():
    f = []
    ok = lambda b, t: f.append(t) if not b else print("✓", t)   # noqa: E731
    alt = {k: getattr(panel, k) for k in ("_browser_und_mt5_frei", "_win_leerlauf_s", "subprocess", "polar_panel")}
    gestartet = []

    class _Sub:
        TimeoutExpired = panel.subprocess.TimeoutExpired

        @staticmethod
        def run(*a, **k):
            gestartet.append(a[0][2] if a and len(a[0]) > 2 else "?")
            return type("R", (), {"stdout": json.dumps({"ok": True, "konten": ["APEX-1"], "trail": "x"}), "stderr": ""})()
    try:
        panel.subprocess = _Sub
        panel.polar_panel = None
        b = {"konto": "APEX0000000000001", "firma": "Apex Trader"}
        panel._browser_und_mt5_frei, panel._win_leerlauf_s = (lambda tv_eigen=False: False), (lambda: 999)
        r = aufruf(b)
        ok(r["code"] == 409 and r["body"]["code"] == "puls_beschaeftigt" and "MT5" in r["body"]["msg"] and not gestartet
           and not panel.TV_ORDER_LOCK.locked(), f"MT5-Order läuft → 409 belegt, kein Bot-Start, Lock wieder frei ({r['body'].get('msg')})")
        panel._browser_und_mt5_frei, panel._win_leerlauf_s = (lambda tv_eigen=False: True), (lambda: 30)
        r = aufruf(b)
        ok(r["code"] == 409 and "gearbeitet" in r["body"]["msg"] and not gestartet, "am PC wird gearbeitet (30 s) → 409 belegt")
        panel._win_leerlauf_s = lambda: 300
        r = aufruf(b)
        ok(r["code"] == 200 and r["body"].get("ok") is True and gestartet == ["tvkontenliste"], f"frei + Leerlauf 300 s → Bot liest ({gestartet})")
        panel._win_leerlauf_s = lambda: None     # Mac/ohne Windows: Leerlauf unbekannt → wie bisher
        gestartet.clear()
        r = aufruf(b)
        ok(r["code"] == 200 and gestartet == ["tvkontenliste"], "Leerlauf unbekannt (kein Windows) → wie bisher lesen")
    finally:
        for k, v in alt.items():
            setattr(panel, k, v)
    ph = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    i = ph.index("  function tvkFrei(){")
    blk = ph[i:ph.index("  async function tvkTick(){", i)]
    zeile = next(z for z in blk.splitlines() if "plaene.some(p => p && p.status === 'open'" in z)
    bed = zeile[zeile.index("p => ") + 5:zeile.index(")) return")]
    js = bed.replace("&&", " and ").replace("!==", "!=").replace("===", "==").replace("'", '"')
    sperrt = lambda route: bool(eval(js, {}, {"p": type("P", (), {"status": "open", "route": route})()}))   # noqa: E731
    ok(not sperrt("mt5") and not sperrt("mt5v2"), "PC-Tab: offene Echo/Echo-V2-Pläne (mt5, mt5v2) sperren das Lesen nicht mehr")
    ok(all(sperrt(r) for r in ("tvv2", "tsv2", "tvplus", "polar", "dup", "topstep", None)),
       "PC-Tab: tvv2, tsv2, tvplus (Duplikum Puls), polar, dup, topstep und Pläne ohne route sperren weiter")
    ok("TVK_START_ABSTAND_MS" in blk, "PC-Tab: Start < 45 min bleibt für alle Routen")
    j = ph.index("  function tvnRuhe(")
    ok("if(plaene.some(p => p && p.status === 'open')) return 'offener Plan'" in ph[ph.index("  function tvnPlanSperre("):j],
       "TV-Neuladen/Tampermonkey (tvnPlanSperre) unverändert: jeder offene Plan sperrt")
    for t in f:
        print("✗", t)
    print("alle Tests bestanden" if not f else f"FEHLER ({len(f)})")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
