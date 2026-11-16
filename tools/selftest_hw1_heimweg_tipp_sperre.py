#!/usr/bin/env python3
"""Selbsttest HW1 (mt5-copier/order_bot.py _lese_lauf_mit_tipp_sperre, _lese_tipp_sperre_versuch, lese_tipp_sperre_antwort, _echo_tipp_sperre_holen;
Master 16.11.2026 nach IN1): Ina pc-xc5c52 14:58 — Echo tippte im F9-Dialog, der Heimweg der Heim-Wache (Bot-Lauf tvlesen) holte das Puls-Chrome nach vorn →
Symbol 'EURUSD' statt 'NAS100', Abbruch vor dem Knopf. Jetzt: Lese-Lauf im Puls-Chrome (tvlesen, tsxlesen) versucht die PC-Tipp-Sperre EINMAL — belegt →
sofort puls_beschaeftigt (nichts angefasst, kein Warten vor dem Modus, Prüfer M1), frei → gehalten bis Laufende (nicht bei der Auge-Reparatur); Echo wartet
blockierend und bekommt die Sperre direkt nach der Lesung (Prüfer S2). Windows-Mutex mit gestellter Uhr nachgebaut. Ohne Netz.
Aufruf: python3 tools/selftest_hw1_heimweg_tipp_sperre.py"""
import ast
import contextlib
import io
import json
import os
import random
import sys
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


uhr = [1000.0]


class Mutex:
    """besitzer = 'ich' (dieser Prozess) | 'echo' / 'lese' (anderer Prozess) | None; bis = Uhrzeit, zu der der andere freigibt."""
    def __init__(self):
        self.besitzer, self.bis, self.offen, self.zu, self.waits = None, 0.0, 0, 0, []

    def frei_jetzt(self):
        if self.besitzer in ("echo", "lese") and uhr[0] >= self.bis:
            self.besitzer = None
        return self.besitzer is None


M = Mutex()


class K32:
    def CreateMutexW(self, a, b, name):
        M.offen += 1
        return 77 if name == "Local\\ProphosEchoTipp" else 0

    def WaitForSingleObject(self, h, ms):
        """wie Windows: frei → sofort; belegt → blockiert bis Freigabe (dann sofort Besitz) oder bis die Frist um ist (WAIT_TIMEOUT)."""
        M.waits.append(ms)
        if M.frei_jetzt() or M.besitzer == "ich":
            M.besitzer = "ich"
            return 0
        if ms and M.bis <= uhr[0] + ms / 1000.0:
            uhr[0] = M.bis
            M.besitzer = "ich"
            return 0
        uhr[0] += ms / 1000.0
        return 0x102

    def ReleaseMutex(self, h):
        if M.besitzer == "ich":
            M.besitzer = None

    def CloseHandle(self, h):
        M.zu += 1


fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(kernel32=K32()))
stderr = io.StringIO()
ns = {"time": types.SimpleNamespace(time=lambda: uhr[0]), "sys": types.SimpleNamespace(stderr=stderr), "json": json, "random": random,
      "_warte": lambda a, b: uhr.__setitem__(0, uhr[0] + a + b / 2)}
NAMEN_A = ("ECHO_TIPP_MUTEX", "ECHO_TIPP_WARTE_MAX_S", "_ECHO_TIPP", "FEHLERFOTO_CODES_OHNE")
NAMEN_F = ("echo_tipp_sperre_urteil", "_echo_tipp_sperre_holen", "_echo_tipp_sperre_frei", "_lese_tipp_sperre_versuch", "lese_tipp_sperre_antwort",
           "_lese_lauf_mit_tipp_sperre")
for n in ast.parse(SRC).body:
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in NAMEN_A for t in n.targets):
        exec(ast.get_source_segment(SRC, n), ns)
    if isinstance(n, ast.FunctionDef) and n.name in NAMEN_F:
        exec(ast.get_source_segment(SRC, n), ns)
L, HOLEN = ns["_lese_lauf_mit_tipp_sperre"], ns["_echo_tipp_sperre_holen"]
echt_ctypes = sys.modules.get("ctypes")


def neu(anderer=None, s=0.0):
    M.__init__(); stderr.seek(0); stderr.truncate()
    uhr[0] += 1000
    if anderer:
        M.besitzer, M.bis = anderer, uhr[0] + s


def lauf_merker():
    st = {"besitzer": None, "t": None, "n": 0}

    def f():
        st["besitzer"], st["t"], st["n"] = M.besitzer, uhr[0], st["n"] + 1
        return "gelesen"
    return st, f


try:
    sys.modules["ctypes"] = fake_ctypes
    # (a) frei → sofort lesen, Sperre im Lauf gehalten, danach frei
    neu(); st, f = lauf_merker(); t0 = uhr[0]
    r = L("tvlesen", f)
    check(r == "gelesen" and st["t"] == t0 and st["besitzer"] == "ich" and M.besitzer is None and M.zu == M.offen == 1,
          "a) Sperre frei → sofort gelesen, Sperre während des Laufs gehalten, danach frei, Handle zu")
    # (b) Ina 14:58: Echo tippt (hält die Sperre) → Heimweg liest NICHT, antwortet sofort puls_beschaeftigt
    neu("echo", 25); st, f = lauf_merker(); t0 = uhr[0]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        r = L("tvlesen", f)
    ant = json.loads(out.getvalue().strip().splitlines()[-1]) if out.getvalue().strip() else {}
    check(st["n"] == 0 and uhr[0] == t0 and M.besitzer == "echo" and M.zu == 1,
          "b) Echo hält die Sperre → kein Lesen, kein Warten (Uhr steht), Echos Sperre unberührt, Handle zu")
    check(ant.get("ok") is False and ant.get("code") == "puls_beschaeftigt" and ant.get("retry_ok") is True and ant.get("gesendet") is False
          and "nichts angefasst" in ant.get("msg", "") and isinstance(ant.get("trail"), str) and ant.get("trail"),
          f"b) Antwort puls_beschaeftigt · retry_ok · nichts angefasst · Spur ({ant.get('msg', '')[:70]}…)")
    check("puls_beschaeftigt" in ns["FEHLERFOTO_CODES_OHNE"], "b) puls_beschaeftigt macht kein Fehlerfoto")
    check("const HW_SPAETER_CODES = new Set(['puls_beschaeftigt'" in HTML, "b) Heim-Wache verschiebt bei puls_beschaeftigt (HW_SPAETER_CODES, kein Fehlerzähler)")
    # (c) halten=False (Auge-Reparatur, lange Läufe) → lesen, Sperre im Lauf NICHT gehalten
    neu(); st, f = lauf_merker()
    L("tsxlesen", f, halten=False)
    check(st["n"] == 1 and st["besitzer"] is None and M.besitzer is None, "c) halten=False → gelesen, Sperre nur geprüft (Echo blockiert nicht hinter 240 s)")
    # (d) Lauf wirft → Sperre frei
    neu()

    def wirft():
        raise RuntimeError("Absturz im Lauf")
    try:
        L("tvlesen", wirft); geworfen = False
    except RuntimeError:
        geworfen = True
    check(geworfen and M.besitzer is None and M.zu == 1, "d) Lauf wirft → Fehler geht an main (Absturz-JSON), Sperre trotzdem frei")
    # (e) WAIT_ABANDONED (Vorbesitzer tot) zählt als frei
    check(ns["echo_tipp_sperre_urteil"](0x80, 0.0) == "frei", "e) verwaister Mutex (WAIT_ABANDONED) → frei")
    # (f) GEGENRICHTUNG: Echo startet, während eine Lesung die Sperre hält (anderer Prozess, gibt nach 30 s frei) → Echo wartet blockierend und
    #     bekommt die Sperre unmittelbar bei der Freigabe (kein Schlaf-Spalt, in den der nächste Heimweg schlüpfen könnte)
    neu("lese", 30); t0 = uhr[0]; trail = []
    u = HOLEN(trail)
    check(u == "frei" and abs((uhr[0] - t0) - 30) < 0.01 and M.besitzer == "ich" and any("Lesung im Puls-Chrome" in x for x in trail),
          f"f) Echo hinter einer Lesung: wartet {uhr[0] - t0:.1f} s und hat die Sperre im Moment der Freigabe")
    blk = [ms for ms in M.waits if ms]
    check(M.waits[0] == 0 and blk and all(1500 <= ms <= 2500 for ms in blk), f"f) erster Blick ohne Warten, dann blockierende Takte 1,5–2,5 s gestreut ({blk[:3]} ms)")
    ns["_echo_tipp_sperre_frei"]()
    neu("lese", 10_000); t0 = uhr[0]
    check(HOLEN([]) == "aufgeben" and 150 <= uhr[0] - t0 <= 153, f"f) Echo-Grenze unverändert: nach {uhr[0] - t0:.0f} s aufgeben (retry_ok wie bisher)")
    ns["_echo_tipp_sperre_frei"]()
    # (g) ohne Windows → wie bisher
    sys.modules["ctypes"] = types.SimpleNamespace()
    neu("echo", 600); st, f = lauf_merker(); t0 = uhr[0]
    L("tvlesen", f)
    check(st["n"] == 1 and st["t"] == t0 and M.offen == 0, "g) ohne Windows/ctypes → sofort gelesen, wie bisher")
finally:
    if echt_ctypes is not None:
        sys.modules["ctypes"] = echt_ctypes
    else:
        sys.modules.pop("ctypes", None)

# (h) Einbau in main
m = SRC[SRC.index("\ndef main():"):]
blk_ = lambda key: m[m.index(key):m.index("return 0", m.index(key))]   # noqa: E731
check('_lese_lauf_mit_tipp_sperre("tvlesen", lambda: modus_tvlesen(cmd))' in blk_('sys.argv[1] == "tvlesen"'), "h) tvlesen (Heimweg TradingView) über den Claim der Sperre")
tb = blk_('("tsxinventar", "tsxlesen")')
check('_lese_lauf_mit_tipp_sperre("tsxlesen", lambda: modus_tsxlesen(' in tb and 'if sys.argv[1] == "tsxlesen" and not (isinstance(cmd, dict) and cmd.get("auge_reparieren") is True):' in tb
      and 'elif sys.argv[1] == "tsxlesen":\n                modus_tsxlesen(cmd' in tb and "modus_tsxinventar(cmd" in tb,
      "h) tsxlesen (Heimweg TopstepX) über die Sperre; Auge-Reparatur und tsxinventar wie bisher ohne Sperre")
check(all("_lese_lauf_mit_tipp_sperre" not in blk_(k) for k in ('sys.argv[1] == "tvkonto"', 'sys.argv[1] == "tsxorder"', 'sys.argv[1] == "tvkontenliste"')),
      "h) Orders (tvkonto/tsxorder) und tvkontenliste unberührt")
lf = SRC[SRC.index("def _lese_lauf_mit_tipp_sperre("):SRC.index("def _echo_tipp_sperre_antwort(")]
check("_warte(" not in lf and "_echo_tipp_sperre_holen(" not in lf, "h) der Lese-Weg wartet nie vor dem Modus (Wachhund-Puffer bleibt, Prüfer M1)")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
