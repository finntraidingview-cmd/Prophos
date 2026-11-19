#!/usr/bin/env python3
"""Selbsttest TL1 Stufe 1 (Finn 19.11.2026: „Unter Winning Days … Tradeify Live Accounts … als eigene Tabelle für Hedging“; Master: Erkennung Variante A
= accounts.echtgeld). Prüft mit dem echten Code aus prophos.html (JavaScriptCore über osascript, wie selftest_lf1b_wd_50k.py):
(1) Schlüssel 'tradeifylive' NUR bei Tradeify Futures + echtgeld (nicht über Name/Startbalance 0, nie Tradeify CFD, nie andere Firmen);
(2) Firmen-Schlüssel, Name, Kontrakte (Spanne von Tradeify ohne 50k-Drittel), TP-Vorgabe 270–290;
(3) Hedge: ohne eigene Tabelle sichtbar „Hedge-Werte fehlen für Tradeify Live“ (kein Rückfall auf Tradeify/Standard), mit Tabelle Stand = Balance selbst (Start 0 $);
(4) normale Tradeify-Konten bitgleich (Stand = Balance − 150k, Tradeify-Tabelle); (5) Live-Stand 0–1.000 $ zählt bei Live; (6) Einstellungen/Mapper/SQL.
Aufruf: python3 tools/selftest_tl1_tradeify_live.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-11-19_tl1_accounts_echtgeld.sql"), encoding="utf-8").read()
FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


def fn(name):
    i = html.index(f"  function {name}(")
    return html[i:html.index("\n  }\n", i) + 4]


def zeile(praefix):
    i = html.index(praefix)
    return html[i:html.index("\n", i)] + "\n"


js = ("const istTradeifyCfd = f => /tradeify/i.test(String(f || '')) && /cfd/i.test(String(f || ''));\n"
      + zeile("  const TP_VP_VORGABE = ") + zeile("  function wdBasisKey(") + zeile("  function wd50kName(") + zeile("  function wdIst50kKey(")
      + fn("kontoIstTradeifyLive") + zeile("  const TP_VP_FIRMEN = ")
      + fn("tpVpLucidWieTradeify") + fn("tpVpApex100") + fn("tpVp50k") + fn("tpVorplanFirmaKey") + fn("wdKtSpanne") + fn("tpStaffelListe") + fn("tpVorplanStaffel")
      + zeile("  function tpVorplanSpanne(") + zeile("  function tpVorplanIstFunded(") + fn("tpVorplanZeile") + fn("tpVorplanLive") + """
const tpTopstepMll = () => 0, kontoIstTopstepExpress = () => false, wdZyklusVon = () => null, tpVorplanSlaveWaehrung = e => e;
const tpKontoGroesseAusName = (n) => { const m = String(n || '').match(/(\\d{2,3})\\s*k\\b/i); return m ? Number(m[1]) * 1000 : 0 };
const K = (firm, echtgeld, extra) => Object.assign({ firm, name: '150k 2332402 → Funded · Elite Live', type: 'funded', startingBalance: 0, maxDrawdown: 4500, echtgeld }, extra || {});
const r = {};
r.keys = [tpVorplanFirmaKey('Tradeify', K('Tradeify', true)), tpVorplanFirmaKey('Tradeify', K('Tradeify', false)), tpVorplanFirmaKey('Tradeify', K('Tradeify', undefined)),
  tpVorplanFirmaKey('Tradeify CFD', K('Tradeify CFD', true)), tpVorplanFirmaKey('Lucid Trading', K('Lucid Trading', true)), tpVorplanFirmaKey('Apex Trader', K('Apex Trader', true)),
  tpVorplanFirmaKey('Tradeify', null), tpVorplanFirmaKey('Tradeify', K('Tradeify', 'true')), tpVorplanFirmaKey('Tradeify', { name: '150k X', echtgeld: true })];
r.basis = [wdBasisKey('tradeifylive'), wd50kName('tradeifylive'), wdBasisKey('lucid50'), wdBasisKey('tradeify'), TP_VP_FIRMEN.indexOf('tradeifylive'), TP_VP_VORGABE.fu.tradeifylive];
const vp = { kt: 1, regeln: { kt: { tradeify: [2, 3], lucid: [2, 3] } } };
r.kt = [wdKtSpanne('tradeifylive', vp), wdKtSpanne('tradeifylive', { kt: 1, regeln: { kt: { tradeify: [2, 3], tradeifylive: [5, 6] } } }),
  wdKtSpanne('lucid50', vp), wdKtSpanne('tradeify', vp), wdKtSpanne('tradeifylive', { kt: 4, regeln: { kt: {} } })];
const TAB_T = [{ von: 0, eur: 50 }, { von: 2000, eur: 60 }], TAB_L = [{ von: 0, eur: 150 }, { von: 2000, eur: 300 }, { von: 4000, eur: 450 }];
const R0 = { fu: { tradeify: [270, 290] }, staffel: [{ von: 0, eur: 40 }], staffelFirma: { tradeify: TAB_T } };
const R1 = Object.assign({}, R0, { staffelFirma: { tradeify: TAB_T, tradeifylive: TAB_L } });
const z = (acc, R, live) => { const x = tpVorplanZeile(acc, { regeln: R, live, zufall: 0.5 }); return [x.fehler || null, x.slaveEur, x.plus, x.groesse, x.tpVon, x.tpBis, x.hinweis || ''] };
r.z = [z(K('Tradeify', true), R0, 2500), z(K('Tradeify', true), R1, 500), z(K('Tradeify', true), R1, 2500), z(K('Tradeify', true), R1, 4200),
  z(K('Tradeify', true), R1, 0), z(K('Tradeify', true), R1, null),
  z(K('Tradeify', false, { name: '150k T1 → Funded' }), R1, 152500), z(K('Tradeify', false, { name: '150k T1 → Funded' }), R1, 2500)];
r.live = [tpVorplanLive(K('Tradeify', true, { tvBalance: 500 })), tpVorplanLive(K('Tradeify', true, { tvBalance: 0 })), tpVorplanLive(K('Tradeify', false, { tvBalance: 500 })),
  tpVorplanLive(K('Tradeify', false, { tvBalance: 152000 }))];
JSON.stringify(r);
""")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
    fh.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", fh.name], capture_output=True, text=True, timeout=30)
    jr = json.loads(aus.stdout.strip() or "{}")
    if not jr:
        print(aus.stderr[:900])
finally:
    os.unlink(fh.name)

print("— 1) Erkennung —")
ok(jr.get("keys") == ["tradeifylive", "tradeify", "tradeify", "sonst", "lucid", "apex", "tradeify", "tradeify", "tradeifylive"],
   f"tradeifylive nur bei Tradeify Futures + echtgeld === true; Start 0 allein, CFD, Lucid, Apex, ohne Konto, 'true' als Text → wie bisher; Firma als Parameter reicht ({jr.get('keys')})")
print("— 2) Schlüssel, Kontrakte, TP —")
ok(jr.get("basis") == ["tradeify", "Tradeify Live", "lucid", "tradeify", 1, [270, 290]],
   f"Firmen-Schlüssel tradeify, Name „Tradeify Live“, 50k unverändert, direkt nach Tradeify in der Liste, TP-Vorgabe 270–290 ({jr.get('basis')})")
ok(jr.get("kt") == [[2, 3], [5, 6], [1, 1], [2, 3], [4, 4]],
   f"Kontrakte: ohne eigene = Tradeify 2–3 (kein Drittel), eigene 5–6 gelten, Lucid 50k weiter 1–1, sonst Standard-Zahl ({jr.get('kt')})")
print("— 3) Hedge-Tabelle + Stand ab 0 —")
zz = jr.get("z") or [[None] * 7] * 8
ok(zz[0][0] and "Hedge-Werte fehlen für Tradeify Live" in zz[0][0], f"ohne eigene Tabelle: sichtbarer Fehler, kein Rückfall auf Tradeify/Standard ({zz[0][0]})")
ok(zz[1][:4] == [None, 150, 500, 0] and zz[2][:3] == [None, 300, 2500] and zz[3][:3] == [None, 450, 4200],
   f"Stand = Balance selbst (Größe 0): 500 $ → 150 €, 2.500 $ → 300 €, 4.200 $ → 450 € ({zz[1][:4]}, {zz[2][:3]}, {zz[3][:3]})")
ok(zz[4][:3] == [None, 150, 0] and zz[5][1] == 150 and "kein Live-Stand" in zz[5][6], f"Balance 0 $ = echter Stand (kleinste Stufe), ohne Lesung Hinweis ({zz[4][:3]}, {zz[5]})")
ok(zz[2][4:6] == [270, 290], f"TP aus der Vorgabe 270–290 ({zz[2][4:6]})")
ok(zz[6][:4] == [None, 60, 2500, 150000] and zz[7][:3] == [None, 50, -147500],
   f"normales Tradeify unverändert: Stand = Balance − 150k, Tradeify-Tabelle ({zz[6][:4]}, {zz[7][:3]})")
print("— 4) Live-Balance —")
ok(jr.get("live") == [500, 0, None, 152000], f"tpVorplanLive: Live 500/0 $ zählen, normales Tradeify unter 1.000 $ weiter leer ({jr.get('live')})")
print("— 5) Einstellungen, Mapper, SQL —")
ok("tradeifylive: ['Tradeify Live', '#a29bfe'," in html, "Winning Days → Einstellungen: eigene Zeile/Chip „Tradeify Live“")
ok("k === 'tradeifylive' ? '<div class=\"kf\"" in html, "Live-Zeile zeigt keine zweite Kopie der Tradeify-Payout-Regeln")
ok("echtgeld: row.echtgeld === true," in html and "echtgeld: kd.echtgeld === true" in html, "Konten-Mapper + wdAccLike tragen echtgeld")
ok("add column if not exists echtgeld boolean not null default false" in SQL and SQL.count("'2332402', '2332403', '2332404'") == 1
   and "368076fd-67c1-460c-aa86-38d81ae69350" in SQL and "wd_farm" not in SQL.split("update public.accounts", 1)[1].split("-- Kontrolle", 1)[0],
   "SQL: Spalte idempotent, nur Jacobs 3 Elite-Live-Konten, wd_farm/auto_planer unberührt")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
