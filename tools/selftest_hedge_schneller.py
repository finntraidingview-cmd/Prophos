#!/usr/bin/env python3
"""Selbsttest HEDGE-SCHNELLER (02.11.2026, Finn: „Sobald die Order weg ist, zack direkt auf Fusion durch"). Ohne Netz, Kennungen und Zahlen erfunden:
- Text → Fill: echter Wortlaut der Meldung durch fillsAusTexten des Userscripts, dann hedgeToastBeweis aus prophos.html (jsc)
- schließt nur bei Konto exakt/angeklebte Ziffern, Gegenrichtung, voller Menge, nach Start, frisch; hedgeToastLesung für die Rückkehr-Wache
- Quelltext: Flach-Weg bleibt, kein await im Takt, Plan-Ende erst nach flach, Toast-Takt im Puls-Chrome; Alarm über alarm_ereignisse
Aufruf: python3 tools/selftest_hedge_schneller.py"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
US = open(os.path.join(WURZEL, "tv-reader", "tv-reader.user.js"), encoding="utf-8").read()
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


FILL_TEIL = US[US.index("  const FILL_MAX = 10"):US.index("  function fillsLesen() {")].replace("GM_getValue(FILL_SPERRE_KEY, '{}')", "null")
JS = "\n".join(["const window = {}", "const HEDGE_TOAST_FRISCH_MS = 3000, KONTO_KURZ_MIN = 12"]
               + ["const HEDGE_TOAST_KURS_PKT = 10, HEDGE_TOAST_MIN_VERSION = '0.10.7'"] + [js_funktion(HTML, n) for n in ("hedgeToastVersionOk", "hedgeToastNachbar", "hedgeToastOhneFlach", "hedgeKontoPasst", "kontoTextBezug", "kontoTextEindeutig", "tvSymbolWurzel", "hedgeMasterTeilweise",
                                                  "hedgeToastBeweis", "hedgeToastLesung")]
               + ["const readerKontoPasst = (k, e) => ['ja', 'klebt'].includes(kontoTextBezug(k, e))", FILL_TEIL, r"""
const ID = 'TDFYSL150000000000', START = 1000000, JETZT = START + 60000
const NP = { id: 'p', status: 'open', masterAccountId: 'a', richtung: 'buy', masterContracts: 2, masterSymbol: 'MNQZ6', mt5Baseline: { hedge: { pc: 'pc1', symbol_nq: 'MNQZ6' } } }
const O = x => Object.assign({ ext: ID, extIds: [ID, 'TDFYSL150000000099'], seite: 'sell', menge: 1, wurzel: 'MNQ', startMs: START, openMs: START + 500, jetzt: JETZT, offen: null, kurs: 28739 }, x || {})
const F = x => Object.assign({ at: JETZT - 100, seite: 'sell', menge: 1, preis: 28738.5, symbol: 'MNQZ6', konto: ID + ' 151,407.70 USD' }, x || {})
const ja = (f, o) => !!hedgeToastBeweis([f], O(o))
const texte = fillsAusTexten(['Market order executed on CME_MINI:MNQZ6', 'Sell 1 at 28,738.50'])[0]
const S = x => Object.assign({ an: true, positionen_ok: true, positionen: [], positionen_tab: 'puls-1', positionen_alter_s: 0.1, konto: ID }, x || {})
const pos = { wurzel: 'MNQ', richtung: 'buy', menge_zahl: 1 }
print(JSON.stringify({
  text: texte,
  text_voll: ja(F(texte)),
  voll: ja(F()),
  klebt: ja(F({ konto: ID + '159' })),
  klebt_mit_komma: ja(F({ konto: ID + '151,407.70USD' })),
  klebt_nicht_eindeutig: ja(F({ konto: ID + '159' }), { extIds: [ID, ID + '1'] }),
  anderes_konto: ja(F({ konto: 'TDFYSL150000000099 151,000.00 USD' })),
  gekuerzt: ja(F({ konto: 'TDFYSL15000000… 151,407.70 USD' })),
  kein_konto: ja(F({ konto: null })),
  teil_fill: ja(F(), { menge: 2 }),
  rest_in_tabelle: ja(F(), { offen: 2 }),
  tabelle_noch_voll: ja(F(), { offen: 1 }),
  einstieg: ja(F({ seite: 'buy' })),
  vor_start: ja(F({ at: START - 5000 }), { jetzt: START + 1000 }),
  direkt_am_start: ja(F({ at: START + 500 }), { jetzt: START + 1000 }),
  zu_alt: ja(F({ at: JETZT - 3001 })),
  nicht_alt: ja(F({ at: JETZT - 3000 })),
  ohne_symbol: ja(F({ symbol: null })),
  andere_wurzel: ja(F({ symbol: 'NQZ6' })),
  ohne_start: ja(F(), { startMs: 0 }),
  ohne_open: ja(F(), { openMs: 0 }),
  kurs_weit: ja(F(), { kurs: 28760 }),
  kurs_fehlt: ja(F(), { kurs: null }),
  koerper: fillsAusTexten(['Market order executed on MNQZ6', 'Buy 2 at 28,700.00', 'Take profit', 'Sell 2 at 28,772.00']),
  zwei_titel: fillsAusTexten(['Market order executed on MNQZ6', 'Buy 2 at 28,700.00', 'Limit order executed on MNQZ6', 'Sell 2 at 28,772.00']).length,
  sperre_start: fillsSperren([{ seite: 'sell', menge: 1, preis: 1, symbol: 'A' }], [{ seite: 'sell', menge: 1, preis: 1, symbol: 'A' }], {}, 1000, 5000),
  sperre_alt_wieder: (() => { const a = fillsSperren([], [{ seite: 'sell', menge: 1, preis: 1, symbol: 'A' }], {}, 1000, 5000); return fillsSperren([{ seite: 'sell', menge: 1, preis: 1, symbol: 'A' }], [{ seite: 'sell', menge: 1, preis: 1, symbol: 'A' }], a.sperre, 1000 + 2 * 3600000, 2 * 3600000).neu.length })(),
  sperre_neu: fillsSperren([{ seite: 'sell', menge: 1, preis: 2, symbol: 'A' }], [{ seite: 'sell', menge: 1, preis: 2, symbol: 'A' }], {}, 100000, 60000).neu.length,
  sperre_abgelaufen: fillsSperren([{ seite: 'sell', menge: 1, preis: 1, symbol: 'A' }], [], { 'sell|1|1|A': 0 }, 9 * 3600000, 60000).neu.length,
  ver_ok: hedgeToastVersionOk({ positionen_tab: 'p', tabs: [{ tab_id: 'p', version: '0.10.7' }] }),
  ver_neuer: hedgeToastVersionOk({ positionen_tab: 'p', tabs: [{ tab_id: 'p', version: '0.11.0' }] }),
  ver_alt: hedgeToastVersionOk({ positionen_tab: 'p', tabs: [{ tab_id: 'p', version: '0.10.6' }] }),
  ver_fremd_tab: hedgeToastVersionOk({ positionen_tab: 'p', script_version: '0.10.7', tabs: [{ tab_id: 'x', version: '0.10.7' }, { tab_id: 'p', version: '0.10.5' }] }),
  ver_fehlt: hedgeToastVersionOk({ positionen_tab: 'p', tabs: [{ tab_id: 'p' }] }),
  ver_ohne_tabs: hedgeToastVersionOk({ positionen_tab: 'p', version: '0.10.7' }),
  nb_gleich: hedgeToastNachbar([NP, Object.assign({}, NP, { id: 'q', masterAccountId: 'b' })], NP, 'MNQ'),
  nb_ohne_hedge: hedgeToastNachbar([NP, { id: 'q', status: 'open', masterAccountId: 'b', richtung: 'buy', masterContracts: 2, masterSymbol: 'MNQZ6' }], NP, 'MNQ'),
  nb_ohne_wurzel: hedgeToastNachbar([NP, { id: 'q', status: 'open', masterAccountId: 'b', richtung: 'sell', masterContracts: 9 }], NP, 'MNQ'),
  nb_menge: hedgeToastNachbar([NP, Object.assign({}, NP, { id: 'q', masterAccountId: 'b', masterContracts: 3 })], NP, 'MNQ'),
  nb_richtung: hedgeToastNachbar([NP, Object.assign({}, NP, { id: 'q', masterAccountId: 'b', richtung: 'sell' })], NP, 'MNQ'),
  nb_andere_wurzel: hedgeToastNachbar([NP, { id: 'q', status: 'open', masterAccountId: 'b', richtung: 'buy', masterContracts: 2, masterSymbol: 'NQZ6' }], NP, 'MNQ'),
  nb_geplant: hedgeToastNachbar([NP, Object.assign({}, NP, { id: 'q', masterAccountId: 'b', status: 'planned' })], NP, 'MNQ'),
  nb_gleiches_konto: hedgeToastNachbar([NP, Object.assign({}, NP, { id: 'q', masterContracts: 9 })], NP, 'MNQ'),
  nb_allein: hedgeToastNachbar([NP], NP, 'MNQ'),
  puls_gerade: ja(F({ at: JETZT - 100 }), { pulsMs: JETZT - 500 }),
  puls_vorbei: ja(F({ at: JETZT - 100 }), { pulsMs: JETZT - 2000 }),
  zukauf_gesehen: ja(F(), { offen: 2 }),
  teil_text: fillsAusTexten(['Market order partially filled on MNQZ6', 'Sell 1 at 28,738.50']).length,
  ohne_flach_wache_offen: hedgeToastOhneFlach({ toast_beweis_at: 'x', toast_wache: { urteil: 'offen' } }),
  ohne_flach_unklar: hedgeToastOhneFlach({ toast_beweis_at: 'x', toast_wache: { urteil: 'unklar' } }),
  ohne_flach_neu_geladen: hedgeToastOhneFlach({ toast_beweis_at: 'x' }),
  ohne_flach_flach: hedgeToastOhneFlach({ toast_beweis_at: 'x', toast_wache: { urteil: 'flach' } }),
  ohne_flach_altweg: hedgeToastOhneFlach({ grund: 'master_ende_reader' }),
  vor_open: ja(F({ at: START + 5000 }), { openMs: START + 6000, jetzt: START + 6500 }),
  lesung_flach: hedgeToastLesung(S(), ID, 'MNQ', 'buy'),
  lesung_offen: hedgeToastLesung(S({ positionen: [pos] }), ID, 'MNQ', 'buy'),
  lesung_klebt: hedgeToastLesung(S({ konto: ID + '159' }), ID, 'MNQ', 'buy'),
  lesung_blind: hedgeToastLesung(S({ positionen_ok: false }), ID, 'MNQ', 'buy'),
  lesung_alt: hedgeToastLesung(S({ positionen_alter_s: 2 }), ID, 'MNQ', 'buy'),
  lesung_fremd: hedgeToastLesung(S({ konto: 'ANDERES123456' }), ID, 'MNQ', 'buy'),
  lesung_feedtab: hedgeToastLesung(S({ positionen_tab: 'feed-1' }), ID, 'MNQ', 'buy'),
}))
"""])
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
e = json.loads(r.stdout.strip().splitlines()[-1])

t = e["text"]
check(t["seite"] == "sell" and t["menge"] == 1 and t["preis"] == 28738.5 and t["symbol"] == "MNQZ6", "„Sell 1 at 28,738.50“ wird richtig gelesen")
check(e["text_voll"], "echter Text + Plan-Konto → Fusion zu")
check(e["voll"] and e["tabelle_noch_voll"], "volle Menge schließt, auch wenn die Tabelle noch nachhinkt")
check(e["klebt"] and e["klebt_mit_komma"], "TDFYSL mit angehängten Ziffern schließt")
check(not e["klebt_nicht_eindeutig"], "angehängte Ziffern, aber nicht eindeutig: nie")
check(not e["anderes_konto"] and not e["gekuerzt"] and not e["kein_konto"], "anderes, gekürztes oder fehlendes Konto: nie")
check(not e["teil_fill"] and not e["rest_in_tabelle"], "Teil-Fill oder Restmenge: nie")
check(not e["einstieg"], "Einstiegs-Fill (gleiche Richtung): nie")
check(not e["vor_start"] and not e["direkt_am_start"], "Fill vor oder direkt am Plan-Start: nie")
check(not e["zu_alt"] and e["nicht_alt"], "älter als 3 s: nie, 3 s noch ja")
check(not e["ohne_symbol"] and not e["andere_wurzel"], "ohne Symbol oder andere Wurzel: nie")
check(not e["ohne_start"] and not e["ohne_open"] and not e["vor_open"], "ohne Start, ohne Open oder Fill vor dem Hedge-Open: nie")
check(not e["puls_gerade"] and e["puls_vorbei"], "Fill direkt nach einem Puls-Lauf: nie, danach ja")
check(not e["zukauf_gesehen"], "mehr gesehen als der Plan (Zukauf): nie")
check(e["teil_text"] == 0, "„partially filled“ ist kein Fill")
check(e["ohne_flach_wache_offen"] and e["ohne_flach_unklar"] and e["ohne_flach_neu_geladen"] and not e["ohne_flach_flach"] and not e["ohne_flach_altweg"], "Plan-Ende ohne Beweis gesperrt, alter Weg unverändert")
i = HTML.index("async function hedgeReaderSchnellTick(")
tick = HTML[i:HTML.index("setInterval(hedgeReaderSchnellTick, 50)", i)]
check(not e["kurs_weit"] and not e["kurs_fehlt"], "Fill-Preis weit weg vom Kurs oder kein Kurs: nie")
check(len(e["koerper"]) == 1 and e["koerper"][0]["seite"] == "buy" and e["zwei_titel"] == 2, "Körpertext „Sell 2 at <TP>“ ist kein Fill, zweite Meldung schon")
check(e["sperre_start"]["neu"] == [] and e["sperre_alt_wieder"] == 0, "Stand beim Start nie neu, auch 2 h später nicht")
check(e["sperre_neu"] == 1 and e["sperre_abgelaufen"] == 1, "wirklich neue Meldung und nach 8 h wieder neu")
check(e["ver_ok"] and e["ver_neuer"], "Fassung ab 0.10.7: ja")
check(not any(e[k] for k in ("ver_alt", "ver_fremd_tab", "ver_fehlt", "ver_ohne_tabs")), "älter, nur anderer Tab, unbekannt: Flach-Weg")
check(e["nb_gleich"] and e["nb_gleiches_konto"], "anderer Plan gleiche Wurzel/Richtung/Menge oder gleiches Konto: Flach-Weg")
check(e["nb_ohne_hedge"], "Plan ohne Hedge und ohne userId ist Nachbar")
check(e["nb_ohne_wurzel"], "Wurzel nicht bestimmbar: Nachbar")
check(not any(e[k] for k in ("nb_menge", "nb_richtung", "nb_andere_wurzel", "nb_geplant", "nb_allein")), "andere Menge, Richtung, Wurzel, nur geplant, allein: Toast erlaubt")
check("GM_setValue(FILL_SPERRE_KEY" in US and "sessionStorage.setItem(FILL_SPERRE_KEY" not in US, "Fill-Sperre im GM-Speicher")
check("hedgeToastVersionOk(st) && !hedgeToastNachbar(tp, p, wz)" in tick and "kurs: hedgeKursDerWurzel(wz)" in tick, "Takt prüft Version, Nachbar, Kurs")
check("Object.assign({}, HEDGE_WEG_LEER, { toast_beweis_at: null })" in HTML, "abgelehnter Close nimmt die Stempel zurück")
check("default false" in open(os.path.join(WURZEL, "sql", "2026-11-02_hedge_toast_schluss.sql"), encoding="utf-8").read(), "SQL Standard aus")
check(e["lesung_flach"] == "flach" and e["lesung_klebt"] == "flach", "Wache: flach, auch mit angehängten Ziffern")
check(e["lesung_offen"] == "offen", "Wache: Position da → offen")
check(all(e[k] == "unklar" for k in ("lesung_blind", "lesung_alt", "lesung_fremd", "lesung_feedtab")), "Wache: blind, alt, fremdes Konto, Feed-Tab → unklar")

check("hedgeToastSchluss(p, kontoPlan, wz, richtung, tf).catch(" in tick and "await hedgeToastSchluss" not in tick, "Takt wartet nicht auf den Schluss")
check(tick.index("readerKontoPasst(st.konto, kontoPlan, st) || kurzEndeKontoPasst") < tick.index("hedgeToastBeweis(st.fills") < tick.index("hedgeMasterWegEntscheid({"), "Konto-Riegel zuerst, dann Toast, Flach-Weg dahinter")
check("hedgeToastAn() && richtung && p.status === 'open' && readerKontoPasst(st.konto, kontoPlan, st) && kontoMs >= 2000" in tick, "Toast nur im Plan-Konto, nie gekürzt, Konto ≥ 2 s stabil")
check("pulsMs: _pulsAktivAt" in tick and "offen: _hedgeToastMenge.get(pid)" in tick, "Puls-Zeit und größte gesehene Menge gehen in den Beweis")
check("!HEDGE_REVIEW_SPAET[h.grund] || hedgeToastOhneFlach(h)" in HTML and "(HEDGE_REVIEW_SPAET[h.grund] && !hedgeToastOhneFlach(h))" in HTML, "60-s-Nachzügler sperrt, Beweis-Weg übernimmt")
check("_hedgeMasterGesehen.has(pid) && !_hedgeToastGeloest.has(pid)" in tick, "Position vorher gesehen, je Plan einmal")
check("Date.now() - flachSeit >= 1000" in HTML, "Wache: ≥ 1 s durchgehend flach")
check("FILL_DOPPELT_MS = 8 * 3600000" in US, "wieder auftauchende Meldung bleibt alt")
check("hedgeToastAn() && richtung" in tick and "data.hedge_toast_schluss === true" in HTML and "_hedgeToastSchalter.an = false; console.warn" in HTML, "Schalter: aus oder nicht lesbar → nur Flach-Weg")
check("gelesen <= 60000" in HTML and "an: false, at: 0" in HTML, "Schalter: beim Laden aus, alte Lesung zählt nicht")
check("toast_beweis_at: new Date(f.at)" in HTML, "Stempel toast_beweis_at am Hedge")
check("o.flachMinMs >= 0 ? o.flachMinMs : 1000" in HTML, "Flach-Weg unverändert 1 s")
i = HTML.index("async function hedgeToastSchluss(")
s = HTML[i:HTML.index("async function hedgeReaderSchnellTick(", i)]
check(s.index("hedgeSoloSchliessen") < s.index("hedgeToastWache") < s.index("hedgeMasterWegAusfuehren"), "Reihenfolge: Fusion zu, Wache, dann Plan-Ende")
check("if(urteil === 'flach'){ await hedgeMasterWegAusfuehren(tradePlans.find" in s and "if(!(rs && rs.ok)){" in s, "Plan-Ende nur nach flach, frische Zeile; Close gescheitert → Flach-Weg")
check("hedgeMasterWegStempeln(p, 'fill', f.at)" in s, "Quelle fill, Master-Ende ab Fill-Zeit")
check("PULS_CHROME ? 80 + Math.random() * 40 : 250 + Math.random() * 250" in US, "Toast-Takt im Puls-Chrome ~0,1 s, sonst unverändert")
check(US.count("0.10.7") >= 3 and "// @version      0.10.7" in US and "const VERSION    = '0.10.7'" in US and "const EINGEBAUT = '0.10.7'" in US, "Userscript-Version überall 0.10.7")

sys.path.insert(0, HIER)
import selftest_alarme
ns = selftest_alarme.lade()
jetzt = datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc)
seit = (jetzt - timedelta(minutes=1)).isoformat()
plan = {"id": "p1", "user_id": "u1", "status": "open", "route": "tvv2", "master_name": "Konto", "master_firm": "Firma", "started_at": (jetzt - timedelta(minutes=5)).isoformat(),
        "hedge": {"status": "geschlossen", "closed_at": jetzt.isoformat(), "grund": "master_ende_reader",
                  "toast_wache": {"urteil": "offen", "at": jetzt.isoformat(), "menge": 1, "preis": 28738.5}}}
ev = [x for x in ns["alarm_ereignisse"]([plan], {"u1": "Wer"}, jetzt, seit) if x[2] == "hedge_toast_offen"]
check(len(ev) == 1 and ev[0][1] == 1 and "28738.5" in ev[0][4], "Wache „offen“ → 🔴")
p2 = json.loads(json.dumps(plan))
p2["hedge"]["toast_wache"]["urteil"] = "flach"
check(not [x for x in ns["alarm_ereignisse"]([p2], {"u1": "Wer"}, jetzt, seit) if x[2] == "hedge_toast_offen"], "Wache „flach“ → keine Meldung")

print("\nHEDGE-SCHNELLER: alles grün" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
