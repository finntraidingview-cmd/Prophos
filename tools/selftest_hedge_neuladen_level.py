#!/usr/bin/env python3
"""Selbsttest Fusion schneller zu (Finn 02.11.2026: „4 Sekunden ist auch inakzeptabel“). Ohne Netz, echte Funktionen aus prophos.html (jsc):
- Sicht über Tab-Neuladen (Simon pc-pmqd8g, Plan 88b28130: Tab 10 s vor dem Exit neu offen → 30-s-Regel, 34,5 s): hedgeSichtWiederher + hedgeReaderEinfachEntscheid
- Exit-Toast bei gekürztem Apex-Namen am TP/SL-Level (Ina pc-xc5c52, Plan c7b0c76f): hedgeToastBeweis mit kurzLevel
- Close: retry_ok des Copiers → 1 s statt 10 s, letzter Fehlertext bleibt
Aufruf: python3 tools/selftest_hedge_neuladen_level.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
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


def zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


JS = "\n".join(["const window = {}", "const KONTO_KURZ_MIN = 12", zeile("  const HEDGE_TOAST_FRISCH_MS"), zeile("  const HEDGE_TOAST_LEVEL_PKT"),
                zeile("  const HEDGE_SICHT_LS"), zeile("  const HEDGE_EINFACH_LEER_MS")]
               + [js_funktion(HTML, n) for n in ("hedgeKontoPasst", "kontoTextBezug", "kontoTextEindeutig", "tvSymbolWurzel", "hedgeToastBeweis", "hedgeSichtWiederher", "hedgeReaderEinfachEntscheid")]
               + [r"""
const OPEN = 1000000, EXIT = OPEN + 7200000
// Simon: letzte Sichtung im alten Tab 6 min vor dem Exit, Tab 10 s vor dem Exit neu offen, Reader zeigt dasselbe Konto
const KONTO = 'TDFYSL150000000000 151,407.70 USD'
// Simon: letzte Sichtung im alten Tab 20 s vor dem Neuladen, Tab 10 s vor dem Exit neu offen
const T0 = EXIT - 10000
const alt = { konto: KONTO, kontoSeit: OPEN + 1000, gesehenAt: T0 - 20000 }
const neu = hedgeSichtWiederher(alt, KONTO, OPEN, T0, true)
const ohne = hedgeSichtWiederher(null, KONTO, OPEN, T0, true)
const anderesKonto = hedgeSichtWiederher(alt, 'TDFYSL150000000099 1.00 USD', OPEN, T0, true)
const zuAlt = hedgeSichtWiederher(Object.assign({}, alt, { gesehenAt: T0 - 61000 }), KONTO, OPEN, T0, true)
const vorOpen = hedgeSichtWiederher(Object.assign({}, alt, { gesehenAt: OPEN - 1000, kontoSeit: OPEN - 5000 }), KONTO, OPEN, T0, true)
const gekuerzt = hedgeSichtWiederher(alt, KONTO, OPEN, T0, false)
// Schluss-einfach-Regel mit übernommener Sicht: 0,3 s flach + 2 Lesungen
const ent = (imZr, leer, n) => hedgeReaderEinfachEntscheid({ unterwegs: '', kontoOk: true, liste: [], sekundenSeitOpen: 7200, gesehenImZeitraum: imZr, wurzel: 'NQ', leerSeitMs: leer, lesungen: n })
// Ina: gekürzter Apex-Name, Exit am TP 28.755 (TP-Level 28.754,5), 2 NQ long
const ID = 'PAAPEX6780960000006', KURZ = 'PAAPEX678096000000'
const O = x => Object.assign({ ext: ID, extIds: [ID, 'PAAPEX6780960000007'], seite: 'sell', menge: 2, wurzel: 'NQ', startMs: OPEN, openMs: OPEN + 500, jetzt: EXIT + 100, offen: 2, kurs: 28750, kurzLevel: [28754.5, 28679.62] }, x || {})
const F = x => Object.assign({ at: EXIT, seite: 'sell', menge: 2, preis: 28755, symbol: 'NQZ6', konto: KURZ }, x || {})
const ja = (f, o) => !!hedgeToastBeweis([f], O(o))
print(JSON.stringify({ bezug: kontoTextBezug(KURZ, ID), T0, gekuerzt, neu, ohne, anderesKonto, zuAlt, vorOpen, einfachMit: ent(true, 400, 2), einfachOhne: ent(false, 400, 2),
  ina: ja(F()), inaSl: ja(F({ preis: 28681 }), { kurs: 28683 }), inaNeben: ja(F({ preis: 28745 })), inaOhneLevel: ja(F(), { kurzLevel: null }), inaMenge: ja(F({ menge: 1 })), inaSeite: ja(F({ seite: 'buy' })) }))
"""])
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(JS)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
try:
    e = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout[-600:], r.stderr[-600:])
    sys.exit(1)
check(e["neu"] is not None and e["neu"]["kontoSeit"] == e["T0"] - 2000 and e["neu"]["gesehenAt"] == e["T0"] - 2000, "Simon: Sichtung übernommen, Konto-Ruhe neu ab jetzt − 2 s (keine sofort erfüllte Ruhe, keine 30-s-Strafe)")
check(e["ohne"] is None and e["anderesKonto"] is None and e["zuAlt"] is None and e["vorOpen"] is None, "kein Merker, anderes Konto, älter als 60 s oder vor dem Hedge-Open: nichts übernommen")
check(e["gekuerzt"] is None, "nur bei vollem Kontotext, nie gekürzt (Nachbarkonten heißen gleich)")
check(e["einfachMit"] is True and e["einfachOhne"] is False, "Simon-Fall: mit übernommener Sicht reichen 0,3 s flach + 2 Lesungen (< 1 s), ohne gilt die alte Wartezeit")
check(e["ina"] is True and e["inaSl"] is True, "Ina: Exit-Toast mit gekürztem Namen am TP- bzw. SL-Level zählt")
check(e["inaNeben"] is False and e["inaOhneLevel"] is False and e["inaMenge"] is False and e["inaSeite"] is False, "gekürzter Name neben dem Level, ohne Level, falsche Menge oder Seite: kein Beweis")

# Quelltext: Einbau an den richtigen Stellen
check("jetzt, readerKontoPasst(st.konto, kontoPlan, st))" in HTML and "const alt = hedgeSichtWiederher(hedgeSichtLesen(pid), st.konto," in HTML and "hedgeSichtMerken(pid, st.konto, _hedgeSchnellKonto.get(pid), jetzt)" in HTML
      and "_hedgeSchnellLeer.delete(pid); hedgeSichtVergessen(pid)" in HTML, "Schnell-Wächter: Sicht laden, merken, beim Kontowechsel löschen")
check("kurzLevel: [h.tp_level_nq, h.sl_level_nq]" in HTML and "!kurzEndeSperrt(kurzEndeBeweis(p, kontoPlan, st, wz))" in HTML and "!hedgeToastNachbar(tp, p, wz)" in HTML,
      "gekürzter Toast nur ohne Nachbar-Plan und ohne Bündel-Sperre, hinter dem Schalter hedgeToastAn")
check("h.close_retry_ok === true ? 200 :" in HTML and "close_retry_ok: !!(res && res.retry_ok)" in HTML and "close_fehler_letzter: {" in HTML,
      "Close: retry_ok → 200 ms, solange offen; letzter Fehlertext samt Versuchen in eigenem Feld")

print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
