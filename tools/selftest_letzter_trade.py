#!/usr/bin/env python3
"""Selbsttest: LETZTER TRADE JE KONTO (27.10.2026, Finn: „Unter Admin bei allen Accounts … wann zuletzt getradet wurde … damit Accounts nicht
wegen Inaktivität gebannt werden"). Backend app.py letzter_trade_je_konto (rein rechnend) und Frontend prophos.html admLetzterTradeInfo über
das macOS-eigene JavaScriptCore (ohne Node). Aufruf: python3 tools/selftest_letzter_trade.py"""
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def backend():
    src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    exec(block("_ap_ts") + "\n\n" + block("letzter_trade_je_konto"), ns)
    f = ns["letzter_trade_je_konto"]
    plaene = [{"master_account_id": "a", "status": "completed", "started_at": "2026-10-20T10:00:00+00:00"},
              {"master_account_id": "a", "status": "review", "started_at": "2026-10-25 09:00:00.123+00"},
              {"master_account_id": "b", "slave_account_id": "c", "status": "open", "started_at": "2026-10-27T08:00:00Z"},
              {"master_account_id": "d", "status": "completed", "started_at": None, "ended_at": "2026-10-01T08:00:00Z"},
              {"master_account_id": "e", "status": "planned", "start_um": "2026-10-27T12:00:00Z"}]
    r = f(plaene)
    check(r["a"]["at"].startswith("2026-10-25") and not r["a"]["laeuft"], "Backend: jüngster Start gewinnt (Postgres-Zeitform)")
    check(r["b"]["laeuft"] and r["c"]["laeuft"] and r["c"]["at"].startswith("2026-10-27"), "Backend: offener Plan zählt für Master UND Slave als läuft")
    check(r["d"]["at"].startswith("2026-10-01"), "Backend: Hand-Eintrag ohne Start → Ende zählt")
    check("e" not in r, "Backend: nur geplant zählt nicht")
    check(set(f(plaene, {"a"}).keys()) == {"a"}, "Backend: nur die übergebenen Konten")


def frontend():
    s = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    i = s.index("    const ADM_LT_AMBER_T = 5")
    j = s.index("    window._admLetzterTradeInfo = admLetzterTradeInfo")
    code = s[i:j] + r"""
var J = '2026-10-27T11:00:00Z', aus = [], f = (b, t) => aus.push((b ? 'OK ' : 'ROT ') + t), I = (at, l) => admLetzterTradeInfo({ at: at, laeuft: !!l }, J)
f(I('2026-10-27T10:10:00Z').text === 'heute 14:10' && I('2026-10-27T10:10:00Z').stufe === 'ok', 'Frontend: heute HH:MM (Dubai)')
f(I('2026-10-26T21:30:00Z').text === 'heute 01:30' && I('2026-10-26T19:30:00Z').text === 'gestern', 'Frontend: Dubai-Tag statt UTC-Tag (21:30 UTC = heute 01:30, 19:30 UTC = gestern 23:30)')
f(I('2026-10-26T10:00:00Z').text === 'gestern', 'Frontend: gestern')
f(I('2026-10-23T10:00:00Z').text === 'vor 4 T' && I('2026-10-23T10:00:00Z').stufe === 'ok', 'Frontend: vor 4 T ohne Farbe')
f(I('2026-10-22T10:00:00Z').stufe === 'amber' && I('2026-10-17T10:00:00Z').stufe === 'rot', 'Frontend: ab 5 T amber, ab 10 T rot')
f(I(null).stufe === 'nie' && I(null).sortMs === 0, 'Frontend: nie, sortiert ganz nach vorn (älteste zuerst)')
f(I('2026-10-20T10:00:00Z', true).stufe === 'lauf' && I('2026-10-20T10:00:00Z', true).sortMs > 1e15, 'Frontend: läuft jetzt, sortiert ganz nach hinten')
f(admLetzterTradeInfo(null, J) === null, 'Frontend: ohne Feld kein Urteil')
print(aus.join('\n'))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fd:
        fd.write(code)
        p = fd.name
    try:
        out = subprocess.run([JSC, p], capture_output=True, text=True, timeout=30).stdout.strip()
    finally:
        os.unlink(p)
    for z in (out or "ROT JavaScriptCore lieferte nichts").splitlines():
        check(z.startswith("OK "), z[3:] if z.startswith("OK ") else z)


if __name__ == "__main__":
    print("Backend"); backend()
    print("Frontend"); frontend()
    if FEHLER:
        print(f"\n✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("\n✓ alle Prüfungen grün")
