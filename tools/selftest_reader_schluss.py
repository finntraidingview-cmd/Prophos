#!/usr/bin/env python3
"""Selbsttest SCHLUSS EINFACH (02.11.2026, Finn): Konto über Puls-Klick, Position gesehen, Position weg = Reiter + leere Tabelle, 0,3 s und 2 Lesungen. Fälle e6914376 (Puls unterwegs),
Mike 15.10. (Sichtung nur vor dem Wechsel), leerer P&L, gekürzter Name. Ohne Netz, jsc. Aufruf: python3 tools/selftest_reader_schluss.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
US = open(os.path.join(W, "tools", "userscript-test", "tv-reader-0.10.8.user.js"), encoding="utf-8").read()   # bis zum Rollout nur Testgerät
MAIN = open(os.path.join(W, "tv-reader", "tv-reader.user.js"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    t = 0
    for k in range(j, len(src)):
        t += {"{": 1, "}": -1}.get(src[k], 0)
        if t == 0:
            return src[i:k + 1]
    raise ValueError(name)


RX_NICHT = [z for z in US.split("\n") if z.strip().startswith("const RX_LEER_NICHT")][0]
JS = "\n".join(["const KONTO_KURZ_MIN = 12, HEDGE_EINFACH_LEER_MS = 300, HEDGE_EINFACH_LESUNGEN = 2, HEDGE_TOAST_MIN_VERSION = '0.10.7', HEDGE_EINFACH_MIN_VERSION = '0.10.8'", "const hedgeReaderEinfachAn = st => hedgeToastVersionOk(st, HEDGE_EINFACH_MIN_VERSION)", RX_NICHT, "let _kontoBeleg = { ext: '', at: 0 }, _beleg = false, _ids = []",
                "const kontoExtIds = () => _ids, kontoBelegGilt = () => _beleg"]
               + [fn(HTML, n) for n in ("hedgeToastVersionOk", "hedgeKontoPasst", "kontoTextBezug", "kontoTextEindeutig", "tvSymbolWurzel", "hedgeReaderEinfachKonto", "hedgeReaderEinfachEntscheid")]
               + [fn(US, "tabelleFlach"), r"""
const B = x => Object.assign({ unterwegs: '', kontoOk: true, liste: [], wurzel: 'MNQ', sekundenSeitOpen: 60, gesehenImZeitraum: true, leerSeitMs: 400, lesungen: 3 }, x || {})
const E = x => hedgeReaderEinfachEntscheid(B(x))
const ID = 'PAAPEX670837000000123', KURZ = 'PAAPEX670837000000… 151,407.70 USD'
const zelle = textContent => ({ textContent })
const Z = (...z) => ({ querySelectorAll: () => z.map(zelle) })
const T = (...zn) => ({ querySelectorAll: q => q === 'tr' ? zn.map(x => Z(...x)) : zn.flat().map(zelle) })
const B0 = { zeilen: 0 }
const o = {}
o.weg = E(); o.e6914376 = E({ unterwegs: 'Rück-Login ins Big-Trade-Konto' }); o.mike = E({ gesehenImZeitraum: false })
o.pnl_leer_zeile = E({ liste: [{ wurzel: 'MNQ', richtung: 'buy', menge_zahl: 2, pnl: null, pnl_unklar: true }] })
o.pnl_leer_fremd = E({ liste: [{ wurzel: 'ES', richtung: 'buy', menge_zahl: 1, pnl_unklar: true }] })
o.gegenrichtung = E({ liste: [{ wurzel: 'MNQ', richtung: 'sell', menge_zahl: 1 }] })
o.symbol_ohne_feld = E({ liste: [{ symbol: 'MNQZ6', menge_zahl: 1 }] })
o.ohne_wurzel = E({ liste: [{ symbol: '', menge_zahl: 1 }] })
o.frueh = E({ leerSeitMs: 299 }); o.eine_lesung = E({ lesungen: 1 }); o.grenze = E({ leerSeitMs: 300, lesungen: 2 }); o.hedge_jung = E({ sekundenSeitOpen: 2.9 }); o.konto_nein = E({ kontoOk: false })
_ids = [ID]; o.kurz_eindeutig = hedgeReaderEinfachKonto(KURZ, ID)
_ids = [ID, 'PAAPEX670837000000456']; o.kurz_nachbar_ohne_beleg = hedgeReaderEinfachKonto(KURZ, ID)
_beleg = true; _kontoBeleg = { ext: ID, at: 5 }; o.kurz_beleg = hedgeReaderEinfachKonto(KURZ, ID); o.kurz_balance_neu = hedgeReaderEinfachKonto('PAAPEX670837000000… 150,000.00 USD', ID)
_kontoBeleg.at = 5; o.kurz_anderes_wort = hedgeReaderEinfachKonto('PAAPEX6708370000… 150,000.00 USD', ID); _beleg = false
o.fremd = hedgeReaderEinfachKonto('ANDERES12345678 1 USD', ID); o.exakt = hedgeReaderEinfachKonto(ID, ID)
_ids = ['TDFYSL150000000000']; o.klebt = hedgeReaderEinfachKonto('TDFYSL150000000000159', 'TDFYSL150000000000')
o.t_leer = tabelleFlach(B0, T()); o.t_nothing = tabelleFlach(B0, T(['Nothing to show yet'])); o.t_make = tabelleFlach(B0, T(['Make your first trade']))
o.t_laedt = tabelleFlach(B0, T(['Loading…'])); o.t_conn = tabelleFlach(B0, T(['Connecting to broker'])); o.t_fehler = tabelleFlach(B0, T(['Something went wrong'])); o.t_keine = tabelleFlach(B0, null)
o.t_daten = tabelleFlach(B0, T(['MNQZ6', 'Buy', '3', '28,700.25', '+120.00 USD'])); o.t_zwei = tabelleFlach(B0, T(['', '3', '28,700.25'])); o.t_ziffer = tabelleFlach(B0, T(['28,700.25'])); o.t_zeile_gelesen = tabelleFlach({ zeilen: 1 }, T()); o.t_ohne_befund = tabelleFlach(null, T())
const V = v => ({ positionen_tab: 'p', tabs: [{ tab_id: 'p', version: v }] })
o.v8 = hedgeReaderEinfachAn(V('0.10.8')); o.v9 = hedgeReaderEinfachAn(V('0.11.0')); o.v7 = hedgeReaderEinfachAn(V('0.10.7')); o.v_leer = hedgeReaderEinfachAn(V('')); o.v_fremd = hedgeReaderEinfachAn({ positionen_tab: 'p', script_version: '0.10.8', tabs: [{ tab_id: 'x', version: '0.10.8' }, { tab_id: 'p', version: '0.10.7' }] }); o.v_ohne = hedgeReaderEinfachAn({})
o.toast7 = hedgeToastVersionOk(V('0.10.7')); o.toast6 = hedgeToastVersionOk(V('0.10.6'))
print(JSON.stringify(o))
"""])
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
e = json.loads(r.stdout.strip().splitlines()[-1])
check(e["weg"] and e["grenze"], "Position weg: zu, Grenze 0,3 s und 2 Lesungen")
check(not e["e6914376"], "Vorfall e6914376: Puls unterwegs, kein Urteil")
check(not e["mike"], "Vorfall Mike 15.10.: nur vor dem Wechsel gesehen, kein Schluss")
check(not e["pnl_leer_zeile"] and e["pnl_leer_fremd"], "leerer P&L: Plan-Zeile zählt als da, andere Wurzel stört nicht")
check(not e["gegenrichtung"] and not e["symbol_ohne_feld"] and not e["ohne_wurzel"], "Gegenrichtung, Symbol ohne Feld, Zeile ohne Wurzel: kein Schluss")
check(not e["frueh"] and not e["eine_lesung"] and not e["hedge_jung"] and not e["konto_nein"], "zu früh, eine Lesung, Hedge jung, Konto nein: kein Schluss")
check(e["kurz_eindeutig"] and not e["kurz_nachbar_ohne_beleg"], "gekürzter Name: eindeutig ja, Nachbar ohne Beleg nein")
check(e["kurz_beleg"] and e["kurz_balance_neu"], "gekürzter Name mit Puls-Beleg: ja, auch wenn sich die Balance ändert")
check(not e["kurz_anderes_wort"], "Kontowort seit dem Klick anders: nein")
check(e["exakt"] and e["klebt"] and not e["fremd"], "exakt und angeklebte Ziffern ja, fremd nein")
check(e["t_leer"] and e["t_nothing"] and e["t_make"], "leere Tabelle ohne Fehlertext: flach, auch ohne bekannten Leer-Text")
check(not (e["t_laedt"] or e["t_conn"] or e["t_fehler"] or e["t_keine"]), "Laden, Verbinden, Fehler, keine Tabelle: kein Urteil")
check(not (e["t_daten"] or e["t_zwei"] or e["t_ziffer"]), "Tabelle mit Datenzellen ohne data-label oder einzelner Ziffer: blind, nie flach")
check(not (e["t_zeile_gelesen"] or e["t_ohne_befund"]), "Reader las eine Zeile oder kein Befund: nie flach")
_m = HTML[HTML.index("function hedgeReaderMasterDa("):HTML.index("window._hedgeReaderMasterDa")]
check("hedgeReaderEinfachAn(st) ? hedgeReaderEinfachKonto(st.konto, kontoPlan) : readerKontoPasst(st.konto, kontoPlan, st)" in _m and _m.index("hedgeMasterTeilweise") < _m.index("st.leer_beweis === false || !readerKontoPasst"), "Rückkehr-Wache kennt gekürzte Konten; „flach“ nur mit Leer-Text und voll belegtem Konto")
i = HTML.index("async function hedgeReaderSchnellTick(")
t = HTML[i:HTML.index("setInterval(hedgeReaderSchnellTick, 50)", i)]
check(e["v8"] and e["v9"] and not any(e[k] for k in ("v7", "v_leer", "v_fremd", "v_ohne")), "neue Regel nur, wenn der Positions-Tab 0.10.8 meldet; älter, unbekannt, anderer Tab: alte Regel")
check(e["toast7"] and not e["toast6"], "Toast-Sperre bleibt bei 0.10.7")
check("const einfach = hedgeReaderEinfachAn(st)" in t and "einfach ? hedgeReaderEinfachKonto(st.konto, kontoPlan) : (readerKontoPasst(st.konto, kontoPlan, st) || kurzEndeKontoPasst(st.konto, kontoPlan, st))" in t, "Tick wählt die Konto-Regel nach Version")
_alt = t[t.index("if(!einfach){"):t.index("if(st.positionen.some(x => x && (x.wurzel || tvSymbolWurzel(x.symbol || '')) === wz))")]
check("hedgeMasterWegEntscheid({" in _alt and "if(kurzEndeSperrt(kurz)){ kurzEndeMelden(p, kurz); continue }" in _alt and "if(st.positionen.some(x => x && x.pnl_unklar)) continue" in _alt and "continue\n        }" in _alt, "alte Regel unverändert im eigenen Zweig")
_neu = t[t.index("if(st.positionen.some(x => x && (x.wurzel || tvSymbolWurzel(x.symbol || '')) === wz))"):]
check("kurzEndeSperrt(" not in _neu and "hedgeReaderEinfachEntscheid({" in _neu, "neue Regel: Balance entscheidet nicht")
check("const TVTM_VERSION_SOLL = '0.10.7'" in HTML and "const VERSION    = '0.10.7'" in MAIN and "leer_beweis" not in MAIN and "const VERSION    = '0.10.8'" in US, "main bleibt 0.10.7, Rollout-Soll 0.10.7, 0.10.8 nur im Testordner")
check("if(hedgeTvUnterwegs()){ verwerfen(); return }" in t, "Puls unterwegs setzt Konto-Zeitraum zurück")
check("jetzt - _hedgeSchnellKonto.get(pid) >= 5000) _hedgeSchnellGesehenAt.set" in t, "Sichtung zählt ab 5 s im Konto")
i = HTML.index("async function hedgeTsxSchnellTick(")
check("hedgeMasterWegEntscheid({" in HTML[i:i + 12000], "TopstepX unverändert")
check("st.leer_beweis === false ? false : st.positionen_ok" in HTML and "st.positionen_ok === false || st.leer_beweis === false" in HTML and "st.positionen_ok !== true || st.leer_beweis === false" in HTML, "1-s-Wächter, Master-nie-da, Neuladen bleiben beim Leer-Text")
check("leer_beweis: leerBeweisMerk" in US, "Userscript meldet leer_beweis")
print("\nSCHLUSS EINFACH: alles grün" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
