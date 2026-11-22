#!/usr/bin/env python3
"""Selbsttest EH3-1 (23.11.2026, Master nach Befund EH2): der PC-Tab friert final eines Echo-Plans mit Hedge erst ein, wenn der Copier den
Hedge-Close im Fenster verbucht hat — höchstens ECHO_HEDGE_BUCHUNG_MS (20 s) ab dem ersten flachen Takt, danach wie bisher.
Prüft echoHedgeBuchungAbwarten aus prophos.html per JavaScriptCore (macOS) und die Verdrahtung im mt5-Poll (Quelltext). Kennungen erfunden.
Aufruf: python3 tools/selftest_eh3_tab_hedge_buchung.py"""
import json
import os
import subprocess
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
a = html.index("  const ECHO_HEDGE_BUCHUNG_MS = 20000")
b = html.index("  function echoBeruhigen(pid)")
code = html[a:b]

START = "2026-11-22T23:30:32.830Z"
T0 = 1795390232830            # = START in ms
FLACH = T0 + 22000            # Master seit hier flach
MIT = {"startedAt": START, "mt5Baseline": {"echo_hedge": {"status": "mit", "lots": 1.4}}}
faelle = {
    "mit_ohne_close_5s": [MIT, {"closed_hedges": []}, FLACH, FLACH + 5000],
    "mit_ohne_close_19s": [MIT, {"closed_hedges": []}, FLACH, FLACH + 19000],
    "mit_ohne_close_21s": [MIT, {"closed_hedges": []}, FLACH, FLACH + 21000],
    "mit_close_im_fenster": [MIT, {"closed_hedges": [{"ticket": 1, "profit": 30.4, "closed_at": "2026-11-22T23:30:56.000Z"}]}, FLACH, FLACH + 3000],
    "mit_close_vor_start": [MIT, {"closed_hedges": [{"ticket": 1, "profit": 30.4, "closed_at": "2026-11-22T23:10:00.000Z"}]}, FLACH, FLACH + 3000],
    "mit_nur_dryrun": [MIT, {"closed_hedges": [{"ticket": 1, "profit": 0, "note": "dryrun", "closed_at": "2026-11-22T23:30:56.000Z"}]}, FLACH, FLACH + 3000],
    "mit_extern_marker": [MIT, {"closed_hedges": [{"ticket": 1, "profit": None, "note": "extern_geschlossen", "closed_at": "2026-11-22T23:30:56.000Z"}]}, FLACH, FLACH + 3000],
    "ohne_echo_hedge": [{"startedAt": START, "mt5Baseline": {}}, {"closed_hedges": []}, FLACH, FLACH + 3000],
    "echo_hedge_ohne": [{"startedAt": START, "mt5Baseline": {"echo_hedge": {"status": "ohne"}}}, {"closed_hedges": []}, FLACH, FLACH + 3000],
    "kein_status": [MIT, None, FLACH, FLACH + 3000],
    "ohne_flach_seit": [MIT, {"closed_hedges": []}, None, FLACH + 3000],
}
if not os.path.exists(JSC):
    print("· JavaScriptCore fehlt — übersprungen")
    sys.exit(0)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "t.js")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(code + "\nvar F = " + json.dumps(faelle) + ";\nvar o = {};\nfor (var k in F) o[k] = echoHedgeBuchungAbwarten(F[k][0], F[k][1], F[k][2], F[k][3]);\n"
                 "print(JSON.stringify(o));\n")
    r = subprocess.run([JSC, f], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {"fehler": (r.stdout + r.stderr)[-300:]}
check(o.get("mit_ohne_close_5s") is True and o.get("mit_ohne_close_19s") is True, f"Hedge erwartet, kein Close im Fenster, < 20 s flach → warten ({o})")
check(o.get("mit_ohne_close_21s") is False, "nach 20 s → einfrieren wie bisher (leer = kein Beleg)")
check(o.get("mit_close_im_fenster") is False, "Close im Fenster → sofort einfrieren (wie heute)")
check(o.get("mit_close_vor_start") is True and o.get("mit_nur_dryrun") is True, "Close vor dem Start / nur dryrun zählt nicht → warten")
check(o.get("mit_extern_marker") is False, "Extern-Marker im Fenster → nicht warten (wie heute: closed_sum null, aber Beleg da)")
check(o.get("ohne_echo_hedge") is False and o.get("echo_hedge_ohne") is False, "ohne echo_hedge bzw. status ≠ 'mit' → unverändert")
check(o.get("kein_status") is True and o.get("ohne_flach_seit") is False, "kein Copier-Status → warten (bis 20 s); ohne flachSeit → nie warten")

poll = html[html.index("if(!echoEndeReif(zEnde, Date.now()))"):]
poll = poll[:poll.index("const startedMs = plan.startedAt")]
check("if(!istV2 && echoHedgeBuchungAbwarten(plan, s, zEnde.flachSeit, Date.now())) continue" in poll
      and poll.index("echoHedgeBuchungAbwarten(") < poll.index("mt5PlanPoll.streak.set(String(plan.id), 0)"),
      "Poll: Warten steht nach echoEndeReif und VOR dem Zurücksetzen von streak/flachSeit, nur für Echo (nicht V2)")
check("hedgeWarten: echoHedgeBuchungAbwarten" in html, "Test-Haken window._echoGeist.hedgeWarten")
print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
