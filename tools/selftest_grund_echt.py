#!/usr/bin/env python3
"""Selbsttest LABEL-RADAR-STATT-NOTFALL (30.10.2026, Befund S5: Marc Apex f77f23c8 „Notfall-SL", geschlossen hat Radar). Prüft mit den 19 echten
level_mt5-Plänen der letzten 14 Tage (SELECT 30.10.2026): hedgeGrundEcht (prophos.html, JavaScriptCore) und hedge_grund_echt (app.py) liefern dasselbe und
treffen final.grund bzw. bei final.quelle reader_leer den Reader-Weg; grund_copier unbekannt bleibt level_mt5. Dazu hedgeZuAusRing: schon geschlossen →
Grund bleibt, altes Ticket → nichts, Schließbefehl unterwegs → kein level_mt5.
Aufruf:  python3 tools/selftest_grund_echt.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def js(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n  }\n", i) + 4]


# id, grund_copier, master_weg_quelle, master_weg_seite, ausloeser, kurs_bei_close, tp_level_nq, sl_level_nq, soll
R, F = "master_ende_reader", None
FAELLE = [
    ("eb1ae0f4", "close", F, F, "kerze_high NQ ws −0,37", "29594.38", "29589.75", "25530.52", "tp_feed"),
    ("4b5f6de5", "close", F, F, F, F, "30578.5", "30128.5", R),
    ("6e6e103f", "close", F, F, F, F, "30258", "30091", R),
    ("11f55e89", "close", F, F, F, F, "29766.67", "29422", R),
    ("302a6868", "close", F, F, F, F, "29281.25", "29528.75", R),
    ("6692568c", "close", F, F, F, F, "30045", "29696.25", R),
    ("3edb92ae", "close", F, F, "kerze_low NQ ws −6,06", "29394.44", "29397", "33452.48", "tp_feed"),
    ("119847ee", "close", F, F, F, "29123", "28948", "31776.78", R),
    ("faf091bc", "close", F, F, F, F, "29019.75", "32083.08", R),
    ("ee1f175c", "close", "reader", F, F, F, "28881", "28914", R),
    ("e40e84bc", "unbekannt", F, F, F, F, "29136.5", "31248.33", "level_mt5"),
    ("3e03aeaf", "close", F, F, F, F, "29152.25", "30964.97", R),
    ("e018db62", "close", F, F, F, F, "29123.75", "30441.18", R),
    ("71221689", "close", F, F, "kurs", "29187", "29427.5", "29187.5", "sl_feed"),
    ("0b910b37", "close", "feed", "sl", "kurs", "29623", "29937.75", "29624.5", "sl_feed"),
    ("99275a29", "close", "feed", "sl", "kurs", "28833.5", "28853.75", "28833.75", "sl_feed"),
    ("fb055faf", "close", "reader", F, F, F, "28855.5", "28821.5", R),
    ("e5fec901", "close", "reader", F, F, F, "28559.5", "28924.75", R),
    ("f77f23c8", "close", "feed", "tp", "kerze_high MNQ ws", "29022", "29018.5", "28292.83", "tp_feed"),
]
KEYS = ("grund_copier", "master_weg_quelle", "master_weg_seite", "ausloeser", "kurs_bei_close", "tp_level_nq", "sl_level_nq")
hs = [dict(zip(KEYS, f[1:8]), id=f[0], grund="level_mt5", close_at="2026-10-30T00:00:00Z", soll=f[8]) for f in FAELLE]
hs += [dict(id="ohne close_at", grund="level_mt5", grund_copier="close", soll="level_mt5"),
       dict(id="grund_tab", grund="level_mt5", grund_copier="close", close_at="x", grund_tab="sl_feed", soll="sl_feed"),
       dict(id="echtes level_tp", grund="level_tp", grund_copier="tp", close_at="x", soll="level_tp"),
       dict(id="fill mit ausloeser", grund="level_mt5", grund_copier="close", close_at="x", master_weg_quelle="fill", ausloeser="kurs", soll=R),
       dict(id="feed ohne Anhalt", grund="level_mt5", grund_copier="close", close_at="x", ausloeser="kurs", soll="master_ende")]

# Python
i = APP.index("\ndef hedge_grund_echt(") + 1
ns = {}
exec(APP[i:APP.index("\n\n\n", i)] if "\n\n\n" in APP[i:i + 2000] else APP[i:APP.index("\n\ndef ", i)], ns)
for h in hs:
    p = {"hedge_grund": h["grund"], "h_gc": h.get("grund_copier"), "h_close_at": h.get("close_at"), "h_tab": h.get("grund_tab"), "h_mq": h.get("master_weg_quelle"),
         "h_seite": h.get("master_weg_seite"), "h_ausl": h.get("ausloeser"), "h_kurs": h.get("kurs_bei_close"), "h_tp": h.get("tp_level_nq"), "h_sl": h.get("sl_level_nq")}
    soll(f"py {h['id']} → {h['soll']}", ns["hedge_grund_echt"](p) == h["soll"])

# JavaScript (Lesen + Schreiber mit Attrappen)
code = "const window = {}\n" + js("  function hedgeGrundEcht(") + "\n" + js("  async function hedgeZuAusRing(") + r"""
var _frisch = null, _schrieb = []
const supabase = { from(){ return { select(){ return { eq(){ return { maybeSingle: async () => ({ data: { mt5_baseline: { hedge: _frisch } }, error: null }) } } } } } } }
async function hedgeAmPlanSchreiben(id, patch, extra){ _schrieb.push(patch); return patch }
function hedgePlGesamt(b, pl){ return pl }
function hedgeGrundText(g){ return g }
const atToast = () => {}
const aus = { lesen: HS.map(h => [h.id, hedgeGrundEcht(h), h.soll]) }
async function fall(frisch, zu){ _frisch = frisch; _schrieb = []; const plan = { id: 'p', mt5Baseline: { hedge: { status: 'offen', ticket: 1 } } }; await hedgeZuAusRing(plan, zu); return _schrieb }
(async () => {
  aus.geschlossen = await fall({ status: 'geschlossen', ticket: 1, grund: 'master_ende_reader', pl: 803 }, { ticket: 1, grund: 'close', pl: 803 })
  aus.plNach = await fall({ status: 'geschlossen', ticket: 1, grund: 'master_ende_reader', pl: null }, { ticket: 1, grund: 'close', pl: 12 })
  aus.altTicket = await fall({ status: 'offen', ticket: 2 }, { ticket: 1, grund: 'close', pl: 5 })
  aus.schliesst = await fall({ status: 'schliesst', ticket: 1, grund: 'tp_feed', close_at: 'x' }, { ticket: 1, grund: 'close', pl: 5 })
  aus.offenClose = await fall({ status: 'offen', ticket: 1, close_at: 'x', master_weg_quelle: 'reader' }, { ticket: 1, grund: 'close', pl: 5 })
  aus.levelEcht = await fall({ status: 'offen', ticket: 1 }, { ticket: 1, grund: 'level_tp', pl: 5 })
  aus.ohneBefehl = await fall({ status: 'offen', ticket: 1 }, { ticket: 1, grund: 'close', pl: 5 })
  aus.verloren = await fall({ status: 'offen', ticket: 1, grund: 'hand', close_at: 'x' }, { ticket: 1, grund: 'close', pl: 5 })
  aus.nieDa = await fall({ status: 'offen', ticket: 1, grund: 'master_nie_da', close_at: 'x' }, { ticket: 1, grund: 'close', pl: 5 })
  aus.oeffnet = await fall({ status: 'oeffnet', ticket: 1 }, { ticket: 1, grund: 'close', pl: 5 })
  aus.reset = await fall(null, { ticket: 1, grund: 'close', pl: 5 })
  print(JSON.stringify(aus))
})()
""".replace("HS.map", json.dumps(hs, ensure_ascii=False) + ".map")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(code)
out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=30)
os.unlink(f.name)
if out.returncode or not out.stdout.strip():
    print(out.stdout, out.stderr)
    sys.exit(1)
a = json.loads(out.stdout.strip().splitlines()[-1])
for i_, g, s in a["lesen"]:
    soll(f"js {i_} → {s}", g == s)
soll("Schreiber: schon geschlossen → nichts", a["geschlossen"] == [])
soll("Schreiber: fehlendes P&L nachtragen, kein Grund", len(a["plNach"]) == 1 and a["plNach"][0].get("pl") == 12 and "grund" not in a["plNach"][0])
soll("Schreiber: altes Ticket → nichts", a["altTicket"] == [])
soll("Schreiber: schliesst → eigener Grund", a["schliesst"][0]["grund"] == "tp_feed")
soll("Schreiber: Befehl unterwegs → Reader statt level_mt5", a["offenClose"][0]["grund"] == "master_ende_reader")
soll("Schreiber: echtes Level bleibt", a["levelEcht"][0]["grund"] == "level_tp")
soll("Schreiber: ohne Befehl weiter level_mt5", a["ohneBefehl"][0]["grund"] == "level_mt5")
soll("Schreiber: Antwort verloren, hand bleibt hand", a["verloren"][0]["grund"] == "hand")
soll("Schreiber: Antwort verloren, master_nie_da bleibt", a["nieDa"][0]["grund"] == "master_nie_da")
soll("Schreiber: oeffnet → nichts", a["oeffnet"] == [])
soll("Schreiber: Plan ohne Hedge → nichts", a["reset"] == [])
print("OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
