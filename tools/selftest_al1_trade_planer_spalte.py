#!/usr/bin/env python3
"""Selbsttest AL1 · Admin → Alle Accounts: Spalte „Trade“ (läuft · heute ±$ · geplant · zuletzt) und Planer-Haken (06.11.2026, Slave 4 —
Finn: „Bei ‚Trade‘ immer, wenn heute schon getradet wurde: der heutige Profit und/oder der heutige Verlust, und wenn er noch gemacht wird:
geplant dann und dann … das einfach in eine Spalte machen. Bei ‚Planer‘ immer einen Haken, ob der gerade im Planer drin ist und aktiv geplant wurde.“)

Ohne Netz per macOS-JavaScriptCore (jsc): admKontoHeute (Planer-Tag = Berliner Kalendertag, Summe master_pl {wert} bzw. Zahl der heute beendeten
Pläne, Überprüfen-Zähler, Planer-Plan heute), admKontoTradeZelleHtml (Rangfolge, Farben, „zuletzt“), admKontoPlanerHtml (✓ bzw. — mit Grund).
Dazu Markup: eine Spalte weniger, Kopf sortiert weiter. Alle Kennungen erfunden. Aufruf: python3 tools/selftest_al1_trade_planer_spalte.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(name):
    i = HTML.index(f"function {name}(")
    j = HTML.index("{", HTML.index(")", i))
    t = 0
    for k in range(j, len(HTML)):
        t += {"{": 1, "}": -1}.get(HTML[k], 0)
        if t == 0:
            return HTML[i:k + 1]
    raise ValueError(name)


def js_zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


JS = r"""
const escapeHtml = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const ADM_LT_AMBER_T = 5, ADM_LT_ROT_T = 10
%s
const _tpl = { lt: new Map() }
const wdlPlTrade = t => (t && t.pl_balance != null && isFinite(Number(t.pl_balance))) ? Number(t.pl_balance) : null   // wie der Radar (vereinfacht)
let _admFcp = { at: 0, aus: new Map(), plant: new Set(), dabei: new Set(), fehler: '' }
const jetzt = '2026-11-06T12:00:00.000Z'                       // 13:00 Berlin, 16:00 Dubai
const Z = (o) => Object.assign({ konto_id: 'k1', user_id: 'u1', plattform: 'orbit', richtung: 'buy', kt: 2, symbol_root: 'NQ' }, o)
const setze = arr => { _tpl.lt = new Map(arr.map((t, i) => [String(i), t])) }
const aus = {}
// 1) heute zwei fertige (+1.500, −398), einer davon review; gestern einer (+999, zählt nicht); ein Plan 19:44 Dubai
setze([Z({ status: 'completed', started_at: '2026-11-06T06:00:00Z', ended_at: '2026-11-06T06:40:00Z', master_pl: { wert: 1500, at: '2026-11-06T06:40:00Z' }, auto_plan: true }),
       Z({ status: 'review', started_at: '2026-11-06T08:00:00Z', ended_at: '2026-11-06T08:30:00Z', master_pl: -398 }),
       Z({ status: 'completed', started_at: '2026-11-05T09:00:00Z', ended_at: '2026-11-05T10:00:00Z', master_pl: { wert: 999 } }),
       Z({ status: 'planned', start_um: '2026-11-06T15:44:00Z' })])
aus.h1 = admKontoHeute('k1', [..._tpl.lt.values()], jetzt)
aus.z1 = admKontoTradeZelleHtml({ id: 'k1' }, { user_id: 'u1' }, jetzt)
aus.p1 = admKontoPlanerHtml({ id: 'k1', type: 'challenge' }, { user_id: 'u1', balance: 100000 }, jetzt, '')
// 2) läuft + heute schon einer fertig (Verlust)
setze([Z({ status: 'open', started_at: '2026-11-06T10:05:00Z', plattform: 'echo', lots: 1.54 }),
       Z({ status: 'completed', started_at: '2026-11-06T05:00:00Z', ended_at: '2026-11-06T05:30:00Z', master_pl: { wert: -250.4 }, planer_plan: true })])
aus.z2 = admKontoTradeZelleHtml({ id: 'k1' }, { user_id: 'u1' }, jetzt)
aus.p2 = admKontoPlanerHtml({ id: 'k1', type: 'funded_cfd' }, { user_id: 'u1', balance: 1 }, jetzt, '')
// 3) Berliner Tagesgrenze: 23:30 UTC am 05.11. = 00:30 Berlin am 06.11. → heute; 22:30 UTC am 05.11. = 23:30 Berlin → gestern
setze([Z({ status: 'completed', ended_at: '2026-11-05T23:30:00Z', master_pl: { wert: 100 } }), Z({ status: 'completed', ended_at: '2026-11-05T22:30:00Z', master_pl: { wert: 7 } })])
aus.h3 = admKontoHeute('k1', [..._tpl.lt.values()], jetzt)
// 4) nichts heute → zuletzt vor 7 T (grau), nie; Planer-Gründe
setze([])
aus.z4 = admKontoTradeZelleHtml({ id: 'k1' }, { user_id: 'u1', letzter_trade: { at: '2026-10-30T09:00:00Z', laeuft: false } }, jetzt)
aus.z5 = admKontoTradeZelleHtml({ id: 'k1' }, { user_id: 'u1', letzter_trade: { at: null, laeuft: false } }, jetzt)
aus.p_wait = admKontoPlanerHtml({ id: 'k1', type: 'funded_cfd', waitingPayoutSince: '2026-11-01' }, { balance: 1 }, jetzt, '')
aus.p_flex = admKontoPlanerHtml({ id: 'k1', type: 'funded_cfd', name: '100k Flex 123' }, { balance: 1 }, jetzt, '')
aus.p_arch = admKontoPlanerHtml({ id: 'k1', type: 'funded_cfd' }, { archived: true, balance: 1 }, jetzt, '')
aus.p_bal = admKontoPlanerHtml({ id: 'k1', type: 'funded_cfd' }, { balance: null }, jetzt, '')
aus.p_aus = admKontoPlanerHtml({ id: 'k1', type: 'challenge', autoPlaner: false }, { balance: 1 }, jetzt, '<label title="Vom Auto-Planer ausgenommen">x</label>')
aus.p_wd = admKontoPlanerHtml({ id: 'k1', type: 'winning_days' }, { balance: 1 }, jetzt, '')
aus.p_leer = admKontoPlanerHtml({ id: 'k1', type: 'funded' }, { balance: 1 }, jetzt, '<span title="Heute ist ein Trade geplant: 19:44 Dubai">◷</span>')
// 5) fremdes Konto / Planer-Plan von gestern zählt nicht
setze([Z({ konto_id: 'k2', status: 'planned', start_um: '2026-11-06T15:00:00Z', auto_plan: true }), Z({ status: 'completed', ended_at: '2026-11-05T10:00:00Z', started_at: '2026-11-05T09:00:00Z', auto_plan: true })])
aus.p5 = admKontoPlanerHtml({ id: 'k1', type: 'challenge' }, { balance: 1 }, jetzt, '')
// 6) Funded CFD ohne Plan heute: Grund aus dem Planer-Lauf; Vorschlag; nicht im Planer
setze([])
_admFcp = { at: 1, aus: new Map([['k1', 'heute schon getradet']]), plant: new Set(['k3']), dabei: new Set(['k1', 'k3']), fehler: '' }
aus.f1 = admKontoTradeZelleHtml({ id: 'k1', type: 'funded_cfd' }, { user_id: 'u1', balance: 1, letzter_trade: { at: '2026-11-05T09:00:00Z' } }, jetzt)
aus.f2 = admKontoTradeZelleHtml({ id: 'k2', type: 'funded_cfd' }, { user_id: 'u1', balance: 1 }, jetzt)
aus.f3 = admKontoTradeZelleHtml({ id: 'k3', type: 'funded_cfd' }, { user_id: 'u1', balance: 1 }, jetzt)
aus.f4 = admKontoTradeZelleHtml({ id: 'k1', type: 'funded_cfd', waitingPayoutSince: '2026-11-01' }, { user_id: 'u1', balance: 1 }, jetzt)
setze([Z({ status: 'planned', start_um: null, created_at: '2026-11-06T05:00:00Z', planer_plan: true })])
aus.f5 = admKontoTradeZelleHtml({ id: 'k1', type: 'funded_cfd' }, { user_id: 'u1', balance: 1 }, jetzt)
aus.f5p = admKontoPlanerHtml({ id: 'k1', type: 'funded_cfd' }, { user_id: 'u1', balance: 1 }, jetzt, '')
// 7) Echo im Überprüfen: master_pl leer, P&L aus pl_balance; ohne jeden P&L → „P&L offen“; Farmer-Plan (planer_quelle wd) → ✓
setze([Z({ status: 'review', plattform: 'echo', started_at: '2026-11-06T08:00:00Z', ended_at: '2026-11-06T09:00:00Z', master_pl: null, pl_balance: 1100 })])
aus.e1 = admKontoTradeZelleHtml({ id: 'k1' }, { user_id: 'u1' }, jetzt)
setze([Z({ status: 'review', started_at: '2026-11-06T08:00:00Z', ended_at: '2026-11-06T09:00:00Z', master_pl: null })])
aus.e2 = admKontoTradeZelleHtml({ id: 'k1' }, { user_id: 'u1' }, jetzt)
setze([Z({ status: 'planned', start_um: '2026-11-06T15:00:00Z', planer_quelle: 'wd' })])
aus.wd = admKontoPlanerHtml({ id: 'k1', type: 'winning_days' }, { user_id: 'u1', balance: 1 }, jetzt, '')
setze([Z({ konto_id: 'm9', plattform: 'polar', slave_account_id: 'k1', status: 'completed', ended_at: '2026-11-06T09:00:00Z', master_pl: { wert: 500 }, slave_pl: -480 })])
aus.polar = admKontoHeute('k1', [..._tpl.lt.values()], jetzt)
print(JSON.stringify(aus))
"""

if not os.path.exists(JSC):
    check(False, "jsc fehlt")
else:
    code = "\n".join([js_zeile("const admPlanerTag = iso =>"), js_funktion("admKontoTradeInfo"), js_funktion("admLetzterTradeInfo"),
                      js_funktion("admKontoHeute"), js_funktion("admKontoNichtGrund"), js_funktion("admKontoTradeZelleHtml"), js_funktion("admKontoPlanerHtml")])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(JS % code)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    try:
        a = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        a = None
        check(False, "jsc: " + (r.stdout + r.stderr)[-700:])
    if a:
        h = a["h1"]
        check(h["n"] == 2 and h["pl"] == 1102 and h["pruef"] == 1 and h["planer"] and h["planer"]["art"] == "Challenge-Planer",
              f"heute: 2 beendet, +1.500 − 398 = +1.102 $, 1× Überprüfen, gestern zählt nicht ({h})")
        z = a["z1"]
        check("is-plus" in z and "heute +1.102 $" in z and "<small>Überprüfen</small>" in z and "geplant · 19:44" in z and z.index("heute +") < z.index("geplant"),
              "Zelle: heute +1.102 $ (grün) mit „Überprüfen“, dahinter „geplant 19:44“")
        check('class="adm-k-ap is-an"' in a["p1"] and "✓" in a["p1"] and "Challenge-Planer" in a["p1"], "Planer ✓: heute vom Challenge-Planer geplant")
        z2 = a["z2"]
        check("is-lauf" in z2 and "läuft · BUY 1,54 Lot · seit 14:05" in z2 and "is-minus" in z2 and "heute −250 $" in z2 and z2.index("läuft") < z2.index("heute"),
              "Zelle: läuft · BUY 1,54 Lot · seit 14:05, daneben heute −250 $ (rot)")
        check("✓" in a["p2"] and "Funded-Planer" in a["p2"], "Planer ✓: Funded-CFD-Plan heute (planer_plan)")
        check(a["h3"]["n"] == 1 and a["h3"]["pl"] == 100, "Tagesgrenze Berlin: 00:30 Berlin zählt zu heute, 23:30 Berlin am Vortag nicht")
        check("adm-k-lt-zuletzt" in a["z4"] and "zuletzt: vor 7 T" in a["z4"] and "is-amber" in a["z4"], "nichts heute → „zuletzt: vor 7 T“ (klein, grau, Punkt amber)")
        check("noch nie getradet" in a["z5"], "nie getradet → „noch nie getradet“")
        grund = lambda x: x.split('title="', 1)[1].split('"', 1)[0]  # noqa: E731
        check("—" in a["p_wait"] and grund(a["p_wait"]).startswith("Waiting for Payout"), "Planer —: Waiting for Payout")
        check(grund(a["p_flex"]).startswith("Flex-Konto"), "Planer —: Flex-Konto")
        check(grund(a["p_arch"]) == "archiviert", "Planer —: archiviert")
        check(grund(a["p_bal"]).startswith("keine Balance"), "Planer —: keine Balance")
        check(grund(a["p_aus"]).startswith("Haken „Auto-Planer“ am Konto aus") and "Vom Auto-Planer ausgenommen" in grund(a["p_aus"]), "Planer —: Haken aus, alter Stand im Tooltip")
        check(grund(a["p_wd"]).startswith("heute (Planer-Tag) kein Plan vom Planer"), "Planer —: Winning Days ohne Farmer-Plan heute (Farmer ist ein Planer)")
        check(grund(a["p_leer"]).startswith("heute (Planer-Tag) kein Plan vom Planer") and "19:44" in grund(a["p_leer"]), "Planer —: kein Plan heute, Heute-traden-Stand im Tooltip")
        check("—" in a["p5"] and "✓" not in a["p5"], "Planer: Plan eines anderen Kontos bzw. von gestern zählt nicht")
        check("nicht geplant · heute schon getradet" in a["f1"] and "zuletzt: gestern" in a["f1"], "Funded CFD ohne Plan: Grund aus dem Planer-Lauf + „zuletzt“")
        check("nicht geplant · nicht im Funded-CFD-Planer<" in a["f2"] and "Firma aus oder ID nicht im Planer" in a["f2"], "Funded CFD nicht im Planer-Lauf → klarer Grund")
        check("nicht geplant · würde geplant" in a["f3"], "Funded CFD, den der Planer planen würde → Hinweis nächster Lauf")
        check("nicht geplant · Waiting for Payout" in a["f4"], "Funded CFD Waiting → Grund vom Konto vor dem Planer-Lauf")
        check("heute +1.100 $" in a["e1"] and "Überprüfen" in a["e1"], "Echo im Überprüfen: P&L aus der Balance (wie Radar), nicht ±0")
        check("heute erledigt · P&amp;L offen" in a["e2"], "kein P&L gelesen → „P&L offen“ statt ±0")
        check("✓" in a["wd"] and "Winning-Day-Farmer" in a["wd"], "Planer ✓: Winning-Day-Farmer über planer_quelle")
        check(a["polar"]["n"] == 1 and a["polar"]["pl"] == -480, "Polar-Slave-Konto: Tagesbilanz mit slave_pl")
        check("Vorschlag · wartet auf Bestätigung" in a["f5"] and "◐" in a["f5p"], "Vorschlag ohne Startzeit → „Vorschlag · wartet auf Bestätigung“, Planer ◐")

# Markup
i = HTML.rfind('<th>Balance</th>', 0, HTML.index('id="adm-k-lt-kopf"'))   # der Admin-Kopf (Accounts hat einen eigenen)
kopf = re.sub(r"<!--.*?-->", "", HTML[i:HTML.index("</tr>", i)], flags=re.S)
check(kopf.count("<th") == 3 and ">Trade</th>" in kopf and 'id="adm-k-lt-kopf"' in kopf and ">Planer</th>" in kopf and "Letzter Trade" not in kopf,
      "Kopf: Balance · Trade (sortierbar) · Planer — „Letzter Trade“ weg")
check("<td>${admLetzterTradeHtml(r, jetztIso)}</td>" not in HTML and "<td>${trade}</td>\n          <td style=\"padding-right:20px\">${planer}</td>" in HTML, "Zeile: eine Zelle weniger")
check("th.textContent = 'Trade' + (admK.ltSort" in HTML, "Sortier-Pfeile am Kopf „Trade“")
k = HTML.index("function admKTvRender(")
tv = HTML[k:HTML.index("\n  }\n", k)]
zeile = tv[tv.index("tr.innerHTML = "):tv.index("tvZelleAccount(")]
check(zeile.count("<td") == 7 and "tr.children[6], z" in tv and "children[7]" not in tv, "Neue TV-Konten: 7 Zellen wie der Kopf, Knöpfe in Spalte 7")
j = HTML.index("function admKontoZeileHtml(")
zl = HTML[j:HTML.index("return `", j)]
check(zl.index("heuteKompaktHtml(r.heute_traden)") < zl.index("planer = admKontoPlanerHtml("), "Planer-Haken nach „Heute traden“ (überschreibt, alter Stand im Tooltip)")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
    sys.exit(1)
print("alle Prüfungen bestanden")
