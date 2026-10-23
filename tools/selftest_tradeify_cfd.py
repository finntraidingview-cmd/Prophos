#!/usr/bin/env python3
"""Selbsttest TRADEIFY CFD (23.10.2026, Auftrag Master zu Finns neuer CFD-Firma „Tradeify CFD": MT5, NAS100 in Lots, Echo V2 ohne Hedge,
Split 80 %). Prophos prüfte an ~25 Stellen nur den Teilstring „tradeify" — „Tradeify CFD" wäre überall Tradeify-Futures gewesen
(TradingView-Weg, Winning Days, 90 % Split, Tradovate-Lesung). Geprüft je Funktion für „Tradeify", „Tradeify CFD", „Blue Guardian"
(+ Schreibweisen „TradeifyCFD", „tradeify-cfd"):
(A) app.py — _ist_tradeify_cfd, _firm_norm, _wd_v2_route, balance_lese_weg, _wd_good_day, ap_klasse; DB-Schlüssel prophos_firma_key aus
    sql/2026-10-23_tradeify_cfd_firma_key.sql (Bedingungen aus dem SQL-Text) = _firm_norm.
(B) prophos.html (per macOS-jsc) — istTradeifyCfd, admPayoutPctDefault, firmNormRichtung, istFutures (Balance-Lesung), firmToPreset-Netz,
    tpFirmIstFutures/tpFirmIstCfd (mit und ohne firm_specs-Zeile), tpFundedHedgeVorgabe, apPrKurz, tplFirmaKurz/-Mini, tpVorplanFirmaKey,
    wdFuturesFirma, tcGoodDayGrenze, pbFirmKey, mpNorm.
(C) „Tradeify" und „Blue Guardian" liefern überall EXAKT dasselbe wie der Stand vor dem Umbau (git HEAD bzw. --alt <commit>).
Gibt die Belegtabelle „Firmenname → Ergebnis" je Funktion aus. Ohne Netz. Aufruf: python3 tools/selftest_tradeify_cfd.py [--alt <commit>]"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
SQL_KEY = os.path.join(WURZEL, "sql", "2026-10-23_tradeify_cfd_firma_key.sql")
NAMEN = ["Tradeify", "Tradeify CFD", "Blue Guardian", "TradeifyCFD", "tradeify-cfd"]
GLEICH = ["Tradeify", "Blue Guardian"]   # müssen exakt wie vorher sein
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def quelle(pfad, commit):
    if not commit:
        return open(os.path.join(WURZEL, pfad), encoding="utf-8").read()
    return subprocess.run(["git", "-C", WURZEL, "show", f"{commit}:{pfad}"], capture_output=True, text=True, check=True).stdout


# ── (A) app.py ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def py_lauf(src):
    ns = {"re": re}

    def block(name):
        i = src.find(f"\ndef {name}(")
        if i < 0:
            return ""
        i += 1
        return src[i:src.find("\n\n\n", i)]

    for k in ("WD_FUTURES_FIRMEN", "WD_BALANCE_FUTURES", "WD_GOOD_DAY_MIN", "AP_CFD_ROUTEN"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    i = src.index("\n_FIRM_RULES = [") + 1
    exec(src[i:src.index("\n]\n", i) + 3], ns)
    for f in ("_ist_tradeify_cfd", "_firm_norm", "_wd_v2_route", "balance_lese_weg", "_wd_good_day", "ap_klasse"):
        b = block(f)
        if b:
            exec(b, ns)
    tab = {}
    for n in NAMEN:
        wd = {"account_type": "winning_days", "firm": n, "name": "100k " + n}
        tab[n] = {
            "_ist_tradeify_cfd": ns["_ist_tradeify_cfd"](n) if "_ist_tradeify_cfd" in ns else None,
            "_firm_norm": ns["_firm_norm"](n),
            "_wd_v2_route": ns["_wd_v2_route"](n),
            "balance_lese_weg": list(ns["balance_lese_weg"](n, "", "100000"))[0],
            "_wd_good_day(+300 $)": ns["_wd_good_day"](wd, 300.0),
            "ap_klasse(ohne Route)": ns["ap_klasse"](None, n),
            "ap_klasse(mt5v2)": ns["ap_klasse"]("mt5v2", n),
        }
    return tab


def sql_firma_key(sql_text):
    """prophos_firma_key aus dem SQL-Text (wie tools/selftest_auto_firmen_abstand.py): `if <Bedingung> then return '<X>'; end if;`"""
    rumpf = sql_text[sql_text.index("function public.prophos_firma_key"):]
    rumpf = rumpf[:rumpf.index("end $$;")]
    regeln = []
    for m in re.finditer(r"if (.+?) then return '([^']*)'; end if;", rumpf, re.S):
        py = re.sub(r"strpos\(f, '([^']*)'\) > 0", lambda x: repr(x.group(1)) + " in f", m.group(1))
        py = py.replace("f = ''", "f == ''").replace("\n", " ")
        regeln.append((compile(py, "sql", "eval"), m.group(2)))

    def key(name):
        f = str(name or "").strip().lower()
        for c, wert in regeln:
            if eval(c, {"f": f}):
                return wert
        return str(name or "").strip()
    return key


# ── (B) prophos.html per jsc ────────────────────────────────────────────────────────────────────────────────────────────────
def js_funktion(src, name):
    i = src.find(f"function {name}(")
    if i < 0:
        return ""
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


def js_const(src, name, ende="\n    const "):
    i = src.index(f"const {name} = ")
    return src[i:src.index(ende, i)]


def js_lauf(src):
    teile = ["var CUSTOM = []; function getCustomFirms(){ return CUSTOM }; function tpWdAktiv(){ return false }; var FIRM_PRESETS = {};"]
    teile.append(js_funktion(src, "istTradeifyCfd") or "function istTradeifyCfd(){ return false }")
    for f in ("firmNormRichtung", "apPrKurz", "tplFirmaKurz", "tplFirmaMini", "tpVpApex100", "tpVorplanFirmaKey", "tpFirmIstFutures",
              "tpFirmIstCfd", "tcGoodDayGrenze", "pbFirmKey", "mpNorm", "firmToPreset", "tpFundedHedgeVorgabe"):
        teile.append(js_funktion(src, f))
    teile.append(js_const(src, "admIstFundedNext"))
    teile.append(js_const(src, "admPayoutPctDefault"))
    teile.append(re.search(r"const TC_GOOD_DAY_MIN = \{.*?\}\s*\}", src).group(0))
    teile.append("const WD_FUTURES_RX = " + re.search(r"WD_FUTURES_RX = (/[^/]+/i)", src).group(1))
    m = re.search(r"const wdFuturesFirma = .*", src)
    teile.append(m.group(0) if m else "const wdFuturesFirma = f => WD_FUTURES_RX.test(String(f || ''))")
    i = src.index("const PB_FIRMEN = {")
    teile.append(src[i:src.index("\n  }\n", i) + 4])
    zeile = re.search(r"const istFutures = (.*?)(?:\s*//.*)?$", src, re.M).group(1)
    teile.append(f"function istFuturesBalance(acc){{ return {zeile} }}")
    teile.append("""
var NAMEN = %s, out = {};
for (var n of NAMEN){
  var r = {};
  r.istTradeifyCfd = istTradeifyCfd(n);
  r.admPayoutPctDefault = admPayoutPctDefault(n);
  r.firmNormRichtung = firmNormRichtung(n);
  r['istFutures (Balance)'] = istFuturesBalance({ firm: n });
  r['firmToPreset (ohne Spec)'] = firmToPreset(n);
  CUSTOM = [];
  r['tpFirmIstFutures (ohne Spec)'] = tpFirmIstFutures(n); r['tpFirmIstCfd (ohne Spec)'] = tpFirmIstCfd(n);
  CUSTOM = [{ name: n, unit: /cfd|guardian/i.test(n) ? 'Lots' : 'Kontrakte' }];
  r['tpFirmIstFutures (mit Spec)'] = tpFirmIstFutures(n); r['tpFirmIstCfd (mit Spec)'] = tpFirmIstCfd(n);
  CUSTOM = [];
  var fh = tpFundedHedgeVorgabe({ type: 'funded', maxDrawdown: 4500, firm: n });
  r['tpFundedHedgeVorgabe'] = fh ? JSON.stringify(fh) : null;
  r.apPrKurz = apPrKurz(n); r.tplFirmaKurz = tplFirmaKurz(n); r.tplFirmaMini = tplFirmaMini(n);
  r.tpVorplanFirmaKey = tpVorplanFirmaKey(n, { name: '150k ' + n });
  r.wdFuturesFirma = wdFuturesFirma(n);
  r.tcGoodDayGrenze = tcGoodDayGrenze({ firm: n, name: '150k ' + n });
  r.pbFirmKey = pbFirmKey(n); r.mpNorm = mpNorm(n);
  out[n] = r;
}
print(JSON.stringify(out));
""" % json.dumps(NAMEN))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
        t.write("\n".join(teile))
        pfad = t.name
    try:
        r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(pfad)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("jsc: " + (r.stderr or r.stdout)[:600])
    return json.loads(r.stdout.strip().splitlines()[-1])


def tabelle(titel, tab):
    funcs = list(next(iter(tab.values())).keys())
    print(f"\n{titel}\n| Funktion | " + " | ".join(NAMEN[:3]) + " |\n|---|" + "---|" * 3)
    for f in funcs:
        print(f"| {f} | " + " | ".join(str(tab[n][f]) for n in NAMEN[:3]) + " |")


def main():
    alt = sys.argv[sys.argv.index("--alt") + 1] if "--alt" in sys.argv else "HEAD"
    py_neu, py_alt = py_lauf(quelle("app.py", None)), py_lauf(quelle("app.py", alt))
    js_neu, js_alt = js_lauf(quelle("prophos.html", None)), js_lauf(quelle("prophos.html", alt))
    tabelle("app.py (neu)", py_neu)
    tabelle("prophos.html (neu)", js_neu)

    # (C) Tradeify + Blue Guardian exakt wie vorher
    for welt, neu, vor in (("app.py", py_neu, py_alt), ("prophos.html", js_neu, js_alt)):
        for n in GLEICH:
            abw = {f: (vor[n][f], neu[n][f]) for f in neu[n] if f not in ("_ist_tradeify_cfd", "istTradeifyCfd") and neu[n][f] != vor[n][f]}
            check(not abw, f"{welt}: „{n}\" exakt wie vor dem Umbau ({alt}) — Abweichungen {abw}")

    # (A) Tradeify CFD = CFD wie Blue Guardian
    for n in ("Tradeify CFD", "TradeifyCFD", "tradeify-cfd"):
        p = py_neu[n]
        check(p["_ist_tradeify_cfd"] and p["_firm_norm"] == "Tradeify CFD" and p["_wd_v2_route"] == "mt5v2"
              and p["balance_lese_weg"] == "mt5_balance" and p["_wd_good_day(+300 $)"] is False and p["ap_klasse(ohne Route)"] == "cfd",
              f"app.py „{n}\": eigene Firma, Echo V2, MT5-Balance, kein Good Day, Klasse CFD")
    check(not py_neu["Tradeify"]["_ist_tradeify_cfd"] and not py_neu["Blue Guardian"]["_ist_tradeify_cfd"], "app.py: Tradeify/Blue Guardian sind nicht Tradeify CFD")
    key = sql_firma_key(open(SQL_KEY, encoding="utf-8").read())
    check(all(key(n) == py_neu[n]["_firm_norm"] for n in NAMEN), f"DB prophos_firma_key = _firm_norm ({[(n, key(n)) for n in NAMEN]})")

    # (B) Frontend
    for n in ("Tradeify CFD", "TradeifyCFD", "tradeify-cfd"):
        j = js_neu[n]
        check(j["istTradeifyCfd"] and j["admPayoutPctDefault"] == 80 and j["firmNormRichtung"] == "tradeifycfd" and j["istFutures (Balance)"] is False
              and j["firmToPreset (ohne Spec)"] == js_neu["Blue Guardian"]["firmToPreset (ohne Spec)"]
              and j["tpFirmIstFutures (ohne Spec)"] is False and j["tpFirmIstCfd (ohne Spec)"] is True
              and j["tpFirmIstFutures (mit Spec)"] is False and j["tpFirmIstCfd (mit Spec)"] is True and j["tpFundedHedgeVorgabe"] is None
              and j["apPrKurz"] == "TC" and j["tplFirmaKurz"] == "Tradeify CFD" and j["tpVorplanFirmaKey"] == "sonst"
              and j["wdFuturesFirma"] is False and j["tcGoodDayGrenze"] is None and j["pbFirmKey"] is None and j["mpNorm"] == "tradeify cfd",
              f"prophos.html „{n}\": CFD wie Blue Guardian, 80 %, Kürzel TC, keine Futures-/WD-Regel")
    print("\n" + ("✓ alles grün" if not FEHLER else f"✗ {len(FEHLER)} Fehler"))
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
