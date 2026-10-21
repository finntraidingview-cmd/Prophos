#!/usr/bin/env python3
"""Selbsttest CFD-TP AM FILL NACHZIEHEN (Finn über Master 21.10.2026 ~23:30 Dubai: „SL/TP grob platzieren und nach der Platzierung
genau anpassen, wie bei Polar" — dann: „Also nur, wenn es ein finaler Trade ist, dann das Ganze machen"). order_bot.py sltp_vom_fill /
sltp_abweichung_usd / kommission_runde (rein rechnend), Verdrahtung in run() (nur Echo V2 = cmd ohne_hedge, nur finale Seite = cmd.final),
Urteil echoV2Final im PC-Tab (prophos.html, per macOS-jsc), panel.py reicht ohne_hedge/final durch, app.py CFD-Puffer letzter Trade 1,5 Pkt.
Der Ändern-Weg selbst (Dialog, Felder, Wiederholung, finale Seite) steht in tools/selftest_mt5_aendern.py.
Fälle mit den echten Zahlen aus trade_plans (mt5v2, TP-Treffer 14.–21.10.2026): je Firma Fill → TP-Preis → Netto am TP = Plan-TP auf
wenige Cent, mit und ohne Kommission. Ohne Netz. Aufruf: python3 tools/selftest_cfd_tp_fill.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
BOT = os.path.join(WURZEL, "mt5-copier", "order_bot.py")
PANEL = os.path.join(WURZEL, "mt5-copier", "panel.py")
APP = os.path.join(WURZEL, "app.py")
HTML = os.path.join(WURZEL, "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_abhaken_geblowt_vorbelegen.py)."""
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


# Urteil im PC-Tab: (Notiz des Auto-Planers, TP $, SL $, erwartet) — Notiz-Format wie app.py ap_notiz / ap_klein_trade
URTEILE = [
    ("Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.964 $ bis Ziel · Balance 105.036 (MT5)", 3006, 2500, "pass"),
    ("Auto-Planer · Klein-Trade · Rest 36 $ · 0,18 Lots · TP 54 $ (Rest + Puffer 18 $) · Rest 36 $ bis Ziel · Balance 107.964 (MT5)", 54, 3000, "pass"),
    ("Auto-Planer · letzter Trade (auf Tageshöchstwert gedeckelt) · Rest 3.900 $ bis Ziel · Balance 104.100 (MT5)", 4000, 2500, "pass"),
    ("Auto-Planer · Etappe · Rest 8.000 $ bis Ziel · Balance 100.000 (MT5)", 4000, 2500, None),
    ("Auto-Planer · Etappe, SL hinter den Boden (+50 $) · Rest 8.000 $ bis Ziel · Balance 91.500 (MT5)", 4000, 1550, "blow"),
    ("Auto-Planer · Etappe, SL auf Boden gekappt · Rest 8.000 $ bis Ziel · Balance 91.500 (MT5)", 4000, 1500, "blow"),
    ("Auto-Planer · letzter Trade (Rest bis Ziel), SL hinter den Boden (+50 $) · Rest 500 $ bis Ziel · Balance 91.200 (MT5)", 520, 1250, "beide"),
    ("", 3000, 2000, None),                                     # Handplan ohne Notiz
    ("Winning-Day-Farmer", 3000, 2000, None),
    ("Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.964 $ bis Ziel · Balance 105.036 (MT5)", None, None, None),   # Order pur
]


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


# (Firma, Richtung, Lots, Kontraktgröße $/Pkt/Lot, TP $, SL $, Fill, grober F9-TP aus der Spur)
FAELLE = [
    ("Blue Guardian NAS100", "sell", 5.2, 10, 6063, 3000, 29399.11, 29277.57),     # Plan 76393260: heute +327 $
    ("FundedNext NDX100", "buy", 3.2, 10, 3140, 2600, 29499.53, 29594.49),          # Plan bb409c4d: heute −101 $
    ("FTMO US100.cash", "buy", 29, 1, 6648, 2400, 29597.68, 29830.12),              # Plan 6447b206: heute +119 $
    ("FundingPips NDX100", "buy", 0.51, 20, 2990, 1296, 29500.00, None),
    ("The5ers NAS100", "sell", 40, 1, 4000, 2500, 29500.00, None),
]


def main():
    bsrc = open(BOT, encoding="utf-8").read()
    ns = {"re": re}
    exec(re.search(r"^NACHZIEHEN_AB_USD = .*$", bsrc, re.M).group(0), ns)
    for name in ("berechne_sl_tp", "sltp_vom_fill", "sltp_abweichung_usd", "kommission_runde"):
        exec(fn(bsrc, name), ns)
    V, A, K = ns["sltp_vom_fill"], ns["sltp_abweichung_usd"], ns["kommission_runde"]

    def netto(richtung, fill, preis, vol, cs, komm=0.0):
        d = (preis - fill) if richtung == "buy" else (fill - preis)
        return d * vol * cs - komm

    for firma, r, vol, cs, tp_usd, sl_usd, fill, tp_f9 in FAELLE:
        sl, tp = V(r, fill, vol, cs, sl_usd, tp_usd, 0.0, 2)
        tol = 0.005 * vol * cs + 0.01           # halber Tick (2 Stellen) × Lots × Kontrakt
        n_tp, n_sl = netto(r, fill, tp, vol, cs), netto(r, fill, sl, vol, cs)
        check(abs(n_tp - tp_usd) <= tol and abs(n_sl + sl_usd) <= tol,
              f"{firma}: TP {tp} / SL {sl} ab Fill {fill} → Netto +{n_tp:.2f} / {n_sl:.2f} (Plan +{tp_usd} / −{sl_usd})")
        check((tp > fill > sl) if r == "buy" else (tp < fill < sl), f"{firma}: Seiten richtig ({r})")
        if tp_f9 is not None:
            heute = netto(r, fill, tp_f9, vol, cs)
            abw = A(sl, tp_f9, sl, tp, vol, cs)
            check(abw >= ns["NACHZIEHEN_AB_USD"] and abs(abw - abs(heute - tp_usd)) <= tol,
                  f"{firma}: grober F9-TP {tp_f9} brachte +{heute:.0f} $ → {abw:.0f} $ daneben → nachziehen")
        # Kommission der Runde: TP weiter weg, SL näher — Netto bleibt am Plan
        k = 14.5
        slk, tpk = V(r, fill, vol, cs, sl_usd, tp_usd, k, 2)
        check(abs(netto(r, fill, tpk, vol, cs, k) - tp_usd) <= tol and abs(netto(r, fill, slk, vol, cs, k) + sl_usd) <= tol,
              f"{firma}: mit {k} $ Kommission Netto am TP +{netto(r, fill, tpk, vol, cs, k):.2f}, am SL {netto(r, fill, slk, vol, cs, k):.2f}")

    # Ohne Kommission = exakt der alte Weg (berechne_sl_tp) — Echo mit Hedge/Nachtrag rechnet unverändert
    check(V("buy", 20000.0, 0.2, 1.0, 100, 300, 0.0, 2) == ns["berechne_sl_tp"]("buy", 20000.0, 0.2, 1.0, 100, 300, 2),
          "Kommission 0 → identisch mit berechne_sl_tp")
    check(V("buy", 20000.0, 1.0, 10.0, 100, 300, None, 2) == ns["berechne_sl_tp"]("buy", 20000.0, 1.0, 10.0, 100, 300, 2),
          "Kommission None (nicht lesbar) → wie 0")
    sl, _tp = V("buy", 20000.0, 1.0, 10.0, 100, 300, 500, 2)
    check(abs((20000.0 - sl) * 10 - 50) < 0.01, f"unplausible Kommission 500 $ zieht den SL höchstens auf den halben Abstand ({sl})")
    check(A(19990.0, 20030.0, 19990.0, 20030.1, 1, 1) < ns["NACHZIEHEN_AB_USD"], "0,1 Pkt × 1 Lot × 1 $ → kein Ändern-Dialog")
    check(K([{"commission": -3.5}, {"commission": -3.75}]) == 14.5, "Kommission: Einstiegs-Deals −7,25 $ → Runde 14,50 $")
    check(K([]) is None and K(None) is None, "keine Einstiegs-Deals → None (nicht gelesen)")
    check(K([{"commission": 0}]) == 0, "Broker ohne Kommission → 0")

    # Verdrahtung run(): nur Echo V2, grobe Level bleiben bei Fehlschlag, nie ein API-Schreibweg
    r = fn(bsrc, "run")
    f9 = r[r.index("direkt im F9-Dialog gesetzt\")"):r.index("if f9_getippt:\n")]
    check("if cmd.get(\"ohne_hedge\"):" in f9 and "_sltp_nachziehen(" in f9, "F9-Zweig: Nachziehen nur mit cmd ohne_hedge (Echo V2)")
    check("sl_end, tp_end = nz[\"sl\"], nz[\"tp\"]" in f9 and "\"sl\": sl_end, \"tp\": tp_end" in f9, "Antwort trägt die tatsächlich gesetzten Level")
    check("if not nz[\"ok\"]:" in f9 and "SOFORT" in f9 and "\"retry_ok\": False" in f9, "fehlt ein Level → ok False, nie erneut platzieren")
    nach = r[r.index("if f9_getippt:\n"):]
    check("sltp_vom_fill(cmd[\"richtung\"], fill, vol, contract_size," in nach
          and "if cmd.get(\"ohne_hedge\") and any(nachzieh_seiten(cmd.get(\"final\"))) else None" in nach,
          "Nachtrag-Weg: Kommission nur bei Echo V2 UND finalem Trade, sonst 0 = wie bisher")
    z = fn(bsrc, "_sltp_nachziehen")
    check("_sltp_klicken(" in z and "sltp_bestaetigt(" in z and "order_send" not in z and "TRADE_ACTION" not in z,
          "Nachziehen per Ändern-Dialog + lesender Bestätigung (kein API-Schreibweg)")
    check("grobe F9-Level bleiben" in z and "trail.append(\"Nachziehen: \" + erg[\"grund\"])" in z, "Fehlschlag: Grund in die Spur, grobe Level bleiben")
    check("abw < NACHZIEHEN_AB_USD" in z, "kleine Abweichung → kein Dialog")
    check(z.index("nachzieh_seiten(cmd.get(\"final\"))") < z.index("_kommission_lesen(") < z.index("_sltp_klicken(")
          and "if not seiten:" in z, "ohne finales Urteil: kein Lesen, kein Klick (früh zurück)")
    kl = fn(bsrc, "_kommission_lesen")
    check("history_deals_get(position=" in kl and "order_send" not in kl, "Kommission nur lesend aus den Einstiegs-Deals")

    # Panel reicht ohne_hedge an den Bot (master-order)
    psrc = open(PANEL, encoding="utf-8").read()
    i = psrc.index("cmd[\"ohne_hedge\"] = ohne_hedge")
    check(psrc.rfind("ohne_hedge = bool(body.get(\"ohne_hedge\"))", 0, i) > psrc.rfind("\"sl_usd\": body.get(\"sl_usd\"), \"tp_usd\": body.get(\"tp_usd\")}", 0, i)
          and psrc.index("json.dumps(cmd)", i) > i, "panel: ohne_hedge steht vor dem Bot-Start im Befehl")
    check('cmd["final"] = _fin if ohne_hedge and _fin in ("pass", "blow", "beide") else None' in psrc
          and psrc.index('cmd["final"] =', i) < psrc.index("json.dumps(cmd)", i), "panel: final nur pass/blow/beide und nur bei Echo V2")

    # PC-Tab: Urteil echoV2Final (jsc) + es reist im Befehl mit
    html = open(HTML, encoding="utf-8").read()
    check("final: _fin.final, final_grund: _fin.grund" in html and "const _fin = echoV2Final(plan, po)" in html,
          "PC-Tab: /api/master-order trägt final + final_grund aus echoV2Final")
    if not os.path.exists(JSC):
        check(False, "jsc fehlt — Urteil im PC-Tab nicht ausführbar")
    else:
        js = "\n".join(js_funktion(html, n) for n in ("planSchritt", "planAutoNotiz", "echoV2Final"))
        js += "\nconst F = %s\nprint(JSON.stringify(F.map(f => echoV2Final({ notes: f[0] }, { tp_usd: f[1], sl_usd: f[2] }))))\n" % json.dumps(
            [[n, tp, sl] for n, tp, sl, _e in URTEILE])
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        try:
            r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(f.name)
        if r.returncode != 0:
            check(False, "jsc: " + (r.stdout + r.stderr)[-400:])
        else:
            aus = json.loads(r.stdout.strip().splitlines()[-1])
            for (notiz, tp, _sl, soll), ist in zip(URTEILE, aus):
                check(ist["final"] == soll and ist["grund"], f"echoV2Final {(notiz or '(ohne Notiz)')[:58]}… TP {tp} → {ist['final']} ({ist['grund']})")

    # Planer: CFD-Puffer des letzten Trades 1,5 Pkt
    asrc = open(APP, encoding="utf-8").read()
    pk = float(re.search(r"^AP_PUFFER_PKT = ([\d.]+)", asrc, re.M).group(1))
    check(abs(pk / 3 - 1.5) < 1e-9, f"AP_PUFFER_PKT {pk:g} ÷ 3 = 1,5 Pkt")
    check(round(pk * 5 * 10 / 3) == 75 and round(pk * 2.1 * 10 / 3) == 32 and round(pk * 42 * 1 / 3) == 63,
          "Puffer BG 5 Lot 75 $ · FN 2,1 Lot 32 $ · The5ers 42 Lot 63 $")
    check("puffer = round(AP_PUFFER_PKT * float(menge) * float(ppl) / 3)" in asrc, "Formel unverändert (nur die Zahl)")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("ALLES GRÜN")


if __name__ == "__main__":
    main()
