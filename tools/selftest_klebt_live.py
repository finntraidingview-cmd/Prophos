#!/usr/bin/env python3
"""Selbsttest KLEBT LIVE (02.11.2026, Anlass Simon Tradeify-Final …4357: Master-TP im Reader, Hedge erst per Notfall-SL, kein reader_wartet). Über JavaScriptCore mit dem echten Code:
angeklebte Konto-Ziffern folgen dem Live-Stand „USD“, Equity bleibt im Trade stehen. Das Plan-Konto muss über den ganzen Trade als Plan-Konto gelten, nach dem Fill greift 1 s flach;
fremde Ziffern, fehlendes USD, alte Zusammenfassung und mehrdeutiger Text bleiben nein. Kennungen sind Platzhalter. Aufruf:  python3 tools/selftest_klebt_live.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def fn(name):
    i = HTML.index(f"  function {name}(")
    return HTML[i:HTML.index("\n  }\n", i) + 4]


NAMEN = ["hedgeKontoPasst", "tvGeldText", "tvBalanceAus", "kontoTextBezug", "kontoTextEindeutig", "kontoKlebtBalance", "kontoKlebtLive", "readerKontoPasst",
         "hedgeMasterWegEntscheid", "hedgeExitFillWahl"]
JS = "const KONTO_KURZ_MIN = 12; const ID = 'TDFYSL150000000000'; let ALLE = [ID, 'TDFYSL150000000111'];\nconst kontoExtIds = () => ALLE; const tvKursZahl = x => Number(x); const tvSymbolWurzel = s => /^MNQ/.test(s) ? 'MNQ' : 'NQ';\n" \
     + "\n".join(fn(n) for n in NAMEN) + r"""
const S = (usd, eq, alter) => ({ summary_alter_s: alter === undefined ? 0.4 : alter, summary: Object.assign({ 'Open P/L': '0.00', 'Net Liq': eq }, usd ? { USD: usd } : {}, { Equity: eq, Profit: '0.00' }) });
const P = (t, st) => readerKontoPasst(t, ID, st);
const out = {};
out.einstieg = P(ID + '155', S('155,813.00', '155,812.05'));
out.tausender = P(ID + '156', S('156,013.00', '155,812.05'));
out.am_tp = P(ID + '159', S('159,013.00', '155,812.05'));
out.nach_fill = P(ID + '159', S('159,073.16', '159,073.16'));
out.wechsel_text_vor = P(ID + '159', S('158,998.00', '155,812.05'));
out.wechsel_text_nach = P(ID + '158', S('159,002.00', '155,812.05'));
out.verlust = P(ID + '149', S('149,950.00', '150,000.20'));
out.fern = P(ID + '159', S('155,813.00', '155,812.05'));
out.ohne_usd = P(ID + '159', S(null, '155,812.05'));
out.alt = P(ID + '156', S('156,013.00', '155,812.05', 11));
out.vier_ziffern = P(ID + '1560', S('156,013.00', '155,812.05'));
out.anderes_konto = P('TDFYSL150000000111156', S('156,013.00', '155,812.05'));
out.voll = P(ID + ' 156,013.00 USD', S(null, '155,812.05'));
out.kurz = P('TDFYSL15000000', S('156,013.00', '155,812.05'));
ALLE = [ID, ID + '15'];
out.mehrdeutig = P(ID + '156', S('156,013.00', '155,812.05'));
ALLE = [ID];
out.million = kontoKlebtLive(ID + '1', ID, { USD: '1,056,981.00' });
out.null_vorn = kontoKlebtLive(ID + '050', ID, { USD: '50,123.00' });
out.null_allein = kontoKlebtLive(ID + '0', ID, { USD: '1,000.00' });
out.grenze_runter = kontoKlebtLive(ID + '100', ID, { USD: '99,950.00' });
out.grenze_hoch = kontoKlebtLive(ID + '99', ID, { USD: '100,050.00' });
out.fremd_id_plus_1 = kontoKlebtLive(ID + '156', ID, { USD: '56,000.00' });
const E = { liste: [], positionenOk: true, alterMs: 200, sekundenSeitOpen: 1800, wurzel: 'NQ', richtung: 'buy', kontoPlan: ID, kontoAktiv: ID + '159', kontoBewiesen: true, kontenAnzahl: 99, schnell: true, gesehen: true };
out.entscheid_durchgehend = hedgeMasterWegEntscheid(Object.assign({}, E, { kontoStabilMs: 1800000, leerSeitMs: 1000, gesehenImZeitraum: true }));
out.entscheid_uhr_neu = hedgeMasterWegEntscheid(Object.assign({}, E, { kontoStabilMs: 3000, leerSeitMs: 3000, gesehenImZeitraum: false }));
const F = { seite: 'sell', menge: 2, preis: 28701.5, at: 5000000, symbol: 'NQZ6', konto: ID + '159' };
const O = { ext: ID, seite: 'sell', menge: 2, wurzel: 'NQ', startMs: 1000, endeMs: 5002000 };
out.fill_klebt = hedgeExitFillWahl([F], Object.assign({}, O, { kurzOk: () => true })) === F;
out.fill_ohne_ok = hedgeExitFillWahl([F], Object.assign({}, O, { kurzOk: () => false })) === null;
print(JSON.stringify(out));
"""
SOLL = [
    ("Einstieg: Ziffern = Equity = USD", "einstieg", True),
    ("+5 Pkt: Tausender gewechselt, Equity steht → bleibt Plan-Konto (war nein)", "tausender", True),
    ("kurz vor dem TP: …159, Equity 155.812 → bleibt Plan-Konto (war nein)", "am_tp", True),
    ("nach dem Fill: alles 159", "nach_fill", True),
    ("Wechsel, Text schon neu, USD noch alt → ±1 hält die Konto-Uhr", "wechsel_text_vor", True),
    ("Wechsel, USD schon neu, Text noch alt → ±1 hält die Konto-Uhr", "wechsel_text_nach", True),
    ("Verlust-Trade unter den Tausender (…149, Fill bei 150)", "verlust", True),
    ("Ziffern weit neben USD und Equity → nein", "fern", False),
    ("ohne USD, Equity passt nicht → nein", "ohne_usd", False),
    ("Zusammenfassung 11 s alt → nein", "alt", False),
    ("4 angeklebte Ziffern (fremde längere Kennung) → nein", "vier_ziffern", False),
    ("anderes Konto desselben Logins → nein", "anderes_konto", False),
    ("volle Kennung mit Leerzeichen → ja ohne Zusammenfassung", "voll", True),
    ("gekürzt bleibt ohne Reader-Weg → nein", "kurz", False),
    ("Text passt auf zwei erfasste Konten → nein", "mehrdeutig", False),
    ("Million: „1“ = 1,056,981", "million", True),
    ("führende Null „050“ bei USD 50.123 → nein (fremdes Konto „ID + 0“)", "null_vorn", False),
    ("„0“ allein → nein", "null_allein", False),
    ("Grenze: Text 100, USD 99.950 → ja", "grenze_runter", True),
    ("Grenze: Text 99, USD 100.050 → ja", "grenze_hoch", True),
    ("fremdes Konto „ID + 1“ mit eigener Balance 56k zeigt „156“ → nein", "fremd_id_plus_1", False),
    ("durchgehende Konto-Uhr + gesehen: 1 s flach schließt", "entscheid_durchgehend", True),
    ("Probe alte Lage: neue Uhr, 3 s flach → nein (Regel unverändert)", "entscheid_uhr_neu", False),
    ("Exit-Fill mit angeklebtem Konto wird gestempelt", "fill_klebt", True),
    ("Exit-Fill ohne kurzOk nicht", "fill_ohne_ok", True),
]


def main():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.js")
        open(p, "w", encoding="utf-8").write(JS)
        r = subprocess.run([JSC, p], capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        print(r.stdout, r.stderr)
        sys.exit(1)
    e, fehler = json.loads(r.stdout.strip().splitlines()[-1]), 0
    for name, k, soll in SOLL:
        ok = e.get(k) is soll
        print(("ok   " if ok else "FEHL ") + name)
        fehler += 0 if ok else 1
    print("ALLE OK" if not fehler else f"{fehler} FEHLER")
    sys.exit(1 if fehler else 0)


main()
