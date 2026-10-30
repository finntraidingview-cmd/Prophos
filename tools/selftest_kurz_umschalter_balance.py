#!/usr/bin/env python3
"""Selbsttest KURZ-UMSCHALTER-BALANCE (30.10.2026, Slave 6 — Simon pc-pmqd8g Test 5, Plan 2cb6c973: reader_kurz_nein „Balance fehlt"; Prüfer S2:
kein Rückfall in tvBalanceAus, nur im Kurz-Ende die Umschalter-Balance „USD" mit Flach-Beweis aus der Tabelle). kurzUmschalterBalance, tvGeldText,
tvBalanceAus, kurzEndeEntscheid per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten.
Simons echte Zahlen: Start balance_start = 149.356,54 (Puls, Account summary); Long 1 MNQ @ 28.875,75; Kurs-Fenster lo = hi = 28.873;
Augen 01:27:52 UTC bei OFFENER Position: USD 149.344,09 · Equity 149.355,59 · Net Liq 149.356,54 · Open P/L 0.00 · alle Margins 0.00 · Profit −11,50
(→ Umschalter = Start − 11,50 G&V − 0,95 Gebühr).
Aufruf: python3 tools/selftest_kurz_umschalter_balance.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_kurz_summary_keys.py)."""
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


def summary(usd):
    return {"Total P/L": "-131.18", "Open P/L": "0.00", "Net Liq": "149356.54", "Total Margin Used": "0.00", "Available Margin": "149356.54",
            "Day Margin": "0.00", "Initial Margin": "0.00", "Maintenance Margin": "0.00", "USD": usd, "Equity": "149,355.59", "Profit": "0.00"}


def main():
    src = open(HTML, encoding="utf-8").read()
    i = src.index("const KURZ_TOL_PKT")
    tol = src[i:src.index("\n", i)]
    flach_st = lambda usd, **u: dict({"positionen_ok": True, "positionen": [], "positionen_tab": "puls-abc123", "positionen_alter_s": 0.4,
                                      "summary_alter_s": 1.2, "summary": summary(usd)}, **u)
    # Ausstieg 28.873,00 bei Long 1 MNQ: G&V (28873 − 28875,75) × 2 = −5,50, Gebühren 2 × 0,95 = −1,90 → USD = 149.356,54 − 7,40 = 149.349,14
    st_ok = flach_st("149,349.14")
    faelle_u = [
        ("flach (Tabelle 0 Pos, ok, Summary 1,2 s) → Umschalter-USD", st_ok, 149349.14),
        ("OFFENE Position (wie Augen 01:27:52) → nie", dict(st_ok, positionen=[{"symbol": "MNQZ6", "menge": 1}]), None),
        ("positionen_ok false (blind) → nie", dict(st_ok, positionen_ok=False), None),
        ("positionen_ok fehlt → nie", {k: v for k, v in st_ok.items() if k != "positionen_ok"}, None),
        ("Summary 5 s alt → nie", dict(st_ok, summary_alter_s=5), None),
        ("ohne USD-Feld → nie", dict(st_ok, summary={k: v for k, v in summary("x").items() if k != "USD"}), None),
        ("USD unlesbar → nie", flach_st("—"), None),
        ("Tab t… (normaler Modus) mit 0 Positionen → nie", dict(st_ok, positionen_tab="tmvu6eqsyft4461"), None),
        ("ohne positionen_tab → nie", {k: v for k, v in st_ok.items() if k != "positionen_tab"}, None),
        ("Positions-Stand 5 s alt → nie", dict(st_ok, positionen_alter_s=5), None),
        ("positionen_alter_s fehlt → nie", {k: v for k, v in st_ok.items() if k != "positionen_alter_s"}, None),
        ("kein Stand → nie", None, None),
    ]
    code = "\n".join(js_funktion(src, n) for n in ("tvGeldText", "tvBalanceAus", "kurzUmschalterBalance", "kurzEndeEntscheid")) + "\n" + tol + \
        "\nvar FU = " + json.dumps([f[1] for f in faelle_u]) + ";\nvar U = FU.map(function (s) { return kurzUmschalterBalance(s); });\n" + \
        "var B = tvBalanceAus(" + json.dumps(summary("149,349.14")) + ");\n" + \
        "var E = [\n" + \
        " kurzEndeEntscheid({ b0: 149356.54, b1: 149349.14, eq1: null, flachTabelle: true, einstieg: 28875.75, kontrakte: 1, pv: 2, dir: 1, lo: 28873, hi: 28873 }),\n" + \
        " kurzEndeEntscheid({ b0: 149356.54, b1: 149349.14, eq1: null, flachTabelle: false, einstieg: 28875.75, kontrakte: 1, pv: 2, dir: 1, lo: 28873, hi: 28873 }),\n" + \
        " kurzEndeEntscheid({ b0: 149356.54, b1: 149344.09, eq1: null, flachTabelle: true, einstieg: 28875.75, kontrakte: 1, pv: 2, dir: 1, lo: 28873, hi: 28873 }),\n" + \
        " kurzEndeEntscheid({ b0: 149356.54, b1: 149355.59, eq1: 149355.59, einstieg: 28875.75, kontrakte: 1, pv: 2, dir: 1, lo: 28873, hi: 28873 })\n];\n" + \
        "print(JSON.stringify({ U: U, B: B, E: E }));\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(code)
    r = subprocess.run([JSC, fh.name], capture_output=True, text=True)
    os.unlink(fh.name)
    if r.returncode != 0 or not r.stdout.strip():
        print(r.stdout, r.stderr)
        sys.exit(1)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    for (name, _s, soll), ist in zip(faelle_u, d["U"]):
        check(ist == soll, f"kurzUmschalterBalance: {name} ({ist})")
    check(d["B"] == {"balance": None, "equity": 149355.59}, f"tvBalanceAus unverändert: kein Rückfall auf Equity/Net Liq ({d['B']})")
    e0, e1, e2, e3 = d["E"]
    check(e0.get("ok") is True and abs(e0.get("exit") - 28872.05) < 0.01,
          f"Simon flach, Umschalter 149.349,14: Ausstieg 28.872,05 (inkl. Gebühren) im Fenster 28.873 ± 3 → ok ({e0})")
    check(e1.get("ok") is False and "Equity" in e1.get("grund", ""), f"ohne flachTabelle und ohne Equity → nein wie bisher ({e1})")
    check(e2.get("ok") is False, f"Umschalter MITTEN im Trade (149.344,09, Profit −11,50) ergäbe 28.869,53 → außerhalb, nein ({e2})")
    check(e3.get("ok") is True, f"alter Weg (Balance = Equity) unverändert ({e3})")
    us = src[src.index("function kurzEndeBeweis("):src.index("function kurzEndeBeweis(") + 4000]
    check("if(bq.balance == null){ const u = kurzUmschalterBalance(st); if(u != null){ bq = { balance: u, equity: null }; flachTabelle = true } }" in us,
          "kurzEndeBeweis: Umschalter nur, wenn tvBalanceAus keine Balance hat")
    if FEHLER:
        print(f"\nFEHLER ({len(FEHLER)})")
        sys.exit(1)
    print("\nalle Tests bestanden")


if __name__ == "__main__":
    main()
