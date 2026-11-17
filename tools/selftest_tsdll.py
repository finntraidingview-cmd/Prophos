#!/usr/bin/env python3
"""Selbsttest TS-DLL (17.11.2026, Finn ~07:05/07:07/07:13 Dubai: „Bei Funded ist auch ein 3K Daily Loss Limit … Stop Loss, Take Profit, alles anpassen“ — „Ist Soft
Breach wie bei Lucid, nur eben 3k.“ — „Ja, für alle.“ = auch SKUs ohne „DLL“). Prüft gegen den Stand VOR TS-DLL (BASIS = 4a09fdc0, fest — nicht origin/main, das
läuft weiter):
  (1) app.py wd_sl_fuer_plan (Express-Zweig): Puffer bis zum näheren von MLL + 100 und Tagesstart − 3.000 + 100, Pflicht-SL bei „ohne SL“ wie Lucid DL2
  (2) app.py liq_topstep_dll / wd_sl_dll_firma / liq_regel_felder (Radar) mit den neuen liq_regeln-Zeilen Topstep funded/winning_days
  (3) prophos.html hedgeTopstepDll: Funded/WD ohne SKU-Bedingung, Challenge unverändert
  (4) BITGLEICH: alle anderen Firmen, und Topstep solange die SQL nicht eingespielt ist (alte Regeln), alter gegen neuen Stand.
Aufruf:  python3 tools/selftest_tsdll.py"""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, HIER)
import selftest_wd_sl_wuerfel as ws1   # noqa: E402

BASIS = "4a09fdc0"   # origin/main beim Bau von TS-DLL
APP_N = "app" + ".py"
FEHLER = []


def check(ok, t):
    print(("✓ " if ok else "✗ ") + t)
    if not ok:
        FEHLER.append(t)


def zusatz(ns, src):
    """liq_topstep_dll + TOPSTEP_DLL_RE + wd_sl_dll_firma in den Namensraum von ws1.lade()."""
    exec(re.search(r"^TOPSTEP_DLL_RE = .*$", src, re.M).group(0), ns)
    for fn in ("liq_topstep_dll", "wd_sl_dll_firma"):
        i = src.index(f"\ndef {fn}(") + 1
        m = re.compile(r"\n(?=\S)").search(src, src.index("\n", i))
        exec(src[i:m.start()], ns)
    return ns


def lade_aus(src):
    import builtins
    orig = builtins.open

    class _F:
        def __init__(self, s): self.s = s
        def read(self): return self.s
        def __enter__(self): return self
        def __exit__(self, *a): return False
    builtins.open = lambda p, *a, **k: _F(src) if str(p).endswith(APP_N) else orig(p, *a, **k)
    try:
        return zusatz(ws1.lade(), src)
    finally:
        builtins.open = orig


git = lambda pfad: subprocess.run(["git", "-C", WURZEL, "show", f"{BASIS}:{pfad}"], capture_output=True, text=True, check=True).stdout
NEU_SRC = open(os.path.join(WURZEL, APP_N), encoding="utf-8").read()
ALT_SRC = git(APP_N)
NEU, ALT = lade_aus(NEU_SRC), lade_aus(ALT_SRC)
check("TS-DLL" not in ALT_SRC and "TS-DLL" in NEU_SRC, f"Alt = {BASIS} ohne TS-DLL, Neu = dieser Stand")


class Folge:
    def __init__(self, *w): self.w = list(w)
    def random(self): return self.w.pop(0) if self.w else 0.5


R8 = {"id": 8, "firma": "Topstep", "kontotyp": "challenge", "groesse": None, "art": "tagesstart", "betrag_usd": 3000, "wie_kontotyp": None, "dll_schutz": None}
R6 = {"id": 6, "firma": None, "kontotyp": "winning_days", "groesse": None, "art": None, "betrag_usd": None, "wie_kontotyp": "funded"}
RF = {"id": 26, "firma": "Topstep", "kontotyp": "funded", "groesse": None, "art": "tagesstart", "betrag_usd": 3000, "wie_kontotyp": None, "dll_schutz": None}
RW = dict(RF, id=27, kontotyp="winning_days")
REGELN_ALT, REGELN = [R8, R6], [R8, R6, RF, RW]
regel = NEU["_wd_sl_std"]()
fuer, fuer_alt = NEU["wd_sl_fuer_plan"], ALT["wd_sl_fuer_plan"]
J = datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc)
iso = lambda d: d.isoformat()
SIMON = {"id": "s6316", "firm": "Topstep", "account_type": "winning_days", "name": "150k EXPRESS-V2-DLL-702233-24036316 → Funded",
         "external_id": "EXPRESS-V2-DLL-702233-24036316", "max_drawdown": 4500, "tv_balance": 19477.5, "tv_balance_at": iso(J - timedelta(hours=1)), "dll_usd": None}
MIKE = {"id": "m1691", "firm": "Topstep", "account_type": "winning_days", "name": "EXPRESS-V2-682437-57131691 → Winning Days",
        "external_id": "EXPRESS-V2-682437-57131691", "max_drawdown": 4500, "tv_balance": 2026.04, "tv_balance_at": iso(J - timedelta(hours=1)), "dll_usd": None}


def lesung(acc, h=40, mll=0.0):
    return {"id": f"alt-{acc['id']}", "master_account_id": acc["id"], "started_at": iso(J - timedelta(hours=h)), "ended_at": iso(J - timedelta(hours=h - 0.2)),
            "mll_start": mll, "bal_end": None, "bal_start": None}


PLAN = {"master_firm": "Topstep", "start_um": iso(J + timedelta(hours=1))}

print("1) WD-SL-Würfel (Express-Zweig)")
w0 = fuer_alt(regel, PLAN, SIMON, REGELN, [lesung(SIMON)], rnd=Folge(0.59, 0.5))
w = fuer(regel, PLAN, SIMON, REGELN, [lesung(SIMON)], rnd=Folge(0.59, 0.5))
check(w0["puffer"] == 19377.5 and w0["liq_balance"] == 100.0, f"vorher Simon …6316: Puffer {w0['puffer']} · Liq {w0['liq_balance']} (MLL 0 + 100)")
check(w["puffer"] == 2900.0 and w["liq_balance"] == 16577.5 and "Tageslimit 3.000" in w["liq_quelle"] and w["dll"]["usd"] == 3000.0 and not w["ohne"]
      and w["usd"] == round(2900 * w["pct"] / 100), f"nachher …6316: Puffer {w['puffer']} · Liq {w['liq_balance']} · SL {w['usd']} $ ({w['pct']} %)")
w = fuer(regel, PLAN, SIMON, REGELN, [lesung(SIMON)], rnd=Folge(0.1, 0.5))
check(not w["ohne"] and w["usd"] == 2900 and w.get("pflicht_dll") is True, f"…6316 „ohne SL“ gewürfelt → Pflicht-SL {w['usd']} $ (DLL − 100, wie Lucid DL2)")
M2 = dict(MIKE, tv_balance=19477.5)
w0 = fuer_alt(regel, PLAN, M2, REGELN, [lesung(M2)], rnd=Folge(0.59, 0.5))
w = fuer(regel, PLAN, M2, REGELN, [lesung(M2)], rnd=Folge(0.59, 0.5))
check(w0["puffer"] == 19377.5 and w["puffer"] == 2900.0, "Mike-SKU ohne „DLL“ (Finn „Ja, für alle.“): Puffer 19.377,50 → 2.900")
w0 = fuer_alt(regel, PLAN, MIKE, REGELN, [lesung(MIKE)], rnd=Folge(0.1, 0.5))
w = fuer(regel, PLAN, MIKE, REGELN, [lesung(MIKE)], rnd=Folge(0.1, 0.5))
check({k: v for k, v in w.items() if k != "dll"} == w0 and w["ohne"] and w["dll"]["liq_balance"] == -873.96,
      "Mike …1691 echt (BAL 2.026,04): MLL + 100 näher als das DLL → Puffer 1.926,04 wie vorher, kein Pflicht-SL (DL2b sperrt „ohne SL“, wie Lucid)")
erster = {"id": "t1", "master_account_id": "s6316", "started_at": iso(J + timedelta(minutes=10)), "ended_at": iso(J + timedelta(minutes=40)),
          "mll_start": 0.0, "bal_end": 20000.0, "bal_start": 21000.0}
S3 = dict(SIMON, tv_balance=20000.0, tv_balance_at=iso(J + timedelta(minutes=50)))
w = fuer(regel, dict(PLAN, start_um=iso(J + timedelta(hours=2))), S3, REGELN, [lesung(S3), erster], rnd=Folge(0.1, 0.5))
check(w["liq_balance"] == 18100.0 and w["puffer"] == 1900.0 and w["usd"] == 1900 and w["dll"]["tagesstart"] == 21000.0,
      f"2. Trade: Tagesstart 21.000 → Puffer 1.900, Pflicht-SL {w['usd']} $")
w = fuer(regel, dict(PLAN, start_um=iso(J + timedelta(hours=2))), S3, REGELN, [lesung(S3), dict(erster, bal_start=23500.0)], rnd=Folge(0.59, 0.5))
check(w["liq_balance"] == 100.0 and "dll" not in w, "Tagesstart 3.500 über der Balance → unplausibel, nur MLL (wie hedgeTopstepDll)")
for rg, name in ((None, "liq_regeln None"), ([], "liq_regeln leer"), ([{"x": 1}], "ohne Topstep-Zeile")):
    check(fuer_alt(regel, PLAN, SIMON, rg, [lesung(SIMON)], rnd=Folge(0.59, 0.5)) == fuer(regel, PLAN, SIMON, rg, [lesung(SIMON)], rnd=Folge(0.59, 0.5)), f"{name}: bitgleich")
check(fuer(regel, PLAN, dict(SIMON, dll_usd=0), REGELN, [lesung(SIMON)], rnd=Folge(0.59, 0.5))["puffer"] == 19377.5, "dll_usd 0 → ausdrücklich kein Tageslimit")
# Prüfer-Befund Henne-Ei: ohne MLL-Lesung (kein früherer Trade) — Express-MLL ≤ 0 → DLL sicher näher, wenn Tagesstart − 2.900 > 100
INA = dict(MIKE, id="i8936", name="150k PRO-V2-DLL-688698-92558936 → Winning Days", external_id="PRO-V2-DLL-688698-92558936", tv_balance=18347.76)
w0 = fuer_alt(regel, PLAN, INA, REGELN, [], rnd=Folge(0.1, 0.5))
w = fuer(regel, PLAN, INA, REGELN, [], rnd=Folge(0.1, 0.5))
check(w0["ohne"] and w0["puffer"] is None and not w["ohne"] and w["usd"] == 2900 and w["puffer"] == 2900.0 and w["liq_balance"] == 15447.76 and "MLL nicht gelesen" in w["liq_quelle"],
      f"Ina ohne MLL-Lesung (BAL 18.347,76): vorher ohne SL/Puffer unbekannt → Pflicht-SL {w['usd']} $ ({w['liq_quelle'][:60]}…)")
for s_ in (0.1, 0.59):
    w0 = fuer_alt(regel, PLAN, dict(INA, tv_balance=2500.0), REGELN, [], rnd=Folge(s_, 0.5))
    w = fuer(regel, PLAN, dict(INA, tv_balance=2500.0), REGELN, [], rnd=Folge(s_, 0.5))
    check(w == w0 and w["ohne"] and w["puffer"] is None, f"ohne MLL-Lesung bei BAL 2.500 (DLL-Level −400 nicht sicher näher als MLL ≤ 0) → wie vorher ohne SL (Würfel {s_})")
w0 = fuer_alt(regel, PLAN, dict(INA, external_id="PRO-V2-1", name="PRO-V2-1"), REGELN_ALT, [], rnd=Folge(0.1, 0.5))
w = fuer(regel, PLAN, dict(INA, external_id="PRO-V2-1", name="PRO-V2-1"), REGELN_ALT, [], rnd=Folge(0.1, 0.5))
check(w == w0, "ohne Lesung, SKU ohne DLL, alte Regeln (SQL nicht eingespielt): bitgleich")
w = fuer(regel, PLAN, dict(SIMON, dll_usd=2000), REGELN, [lesung(SIMON)], rnd=Folge(0.1, 0.5))
check(w["puffer"] == 1900.0 and w["usd"] == 1900, "dll_usd 2.000 (Konto) geht vor der Regel → Puffer 1.900, Pflicht-SL 1.900")

print("2) liq_topstep_dll · wd_sl_dll_firma · Radar")
ltd, ltd0 = NEU["liq_topstep_dll"], ALT["liq_topstep_dll"]
check(ltd(REGELN, MIKE) == (3000.0, "Topstep-DLL") and ltd(REGELN, dict(MIKE, account_type="funded")) == (3000.0, "Topstep-DLL"), "Mike WD/Funded ohne DLL-SKU → 3.000")
check(ltd(REGELN_ALT, MIKE) == (None, None) == ltd0(REGELN_ALT, MIKE), "ohne die neuen Zeilen (SQL nicht eingespielt): wie vorher keins")
C_NO = dict(MIKE, account_type="challenge", name="150k 150KTC-SKU-V2-682437-1 → Challenge", external_id="150KTC-SKU-V2-682437-1")
check(ltd(REGELN, C_NO) == (None, None) and ltd(REGELN, dict(C_NO, external_id="150KTC-SKU-V2-DLL-1")) == (3000.0, "Topstep-DLL"), "Challenge unverändert: nur DLL-SKU (id 8)")
dfirma, dfirma0 = NEU["wd_sl_dll_firma"], ALT["wd_sl_dll_firma"]
check(dfirma(REGELN, MIKE) is True and dfirma(REGELN_ALT, MIKE) is False, "wd_sl_dll_firma: Topstep-WD mit der neuen Zeile = Tageslimit-Firma (DL2b wie Lucid)")
lrf = NEU["liq_regel_felder"]
P = {"route": "tsv2", "winning_day": True, "konto_typ": "winning_days", "mt5_baseline": {"tv": {"balance_relativ": True}}}
f = lrf(REGELN, MIKE, P, 19477.5, 19477.5, 28630, "buy", 2, 3, mll=0)
check(f["liq_gilt"] == "regel" and f["liq_regel_soft"] is True and f["liq_regel_balance"] == 16477.5 and "Daily Loss 3.000" in f["liq_regel_text"],
      f"Radar Mike-SKU (BAL 19.477,50): {f['liq_regel_text']}")
f = lrf(REGELN, MIKE, P, 2026.04, 2026.04, 28630, "buy", 2, 3, mll=0)
check(f["liq_gilt"] == "boden" and f["liq_regel_balance"] == 0, "Radar Mike …1691 echt (BAL 2.026): MLL 0 näher → Boden")
f = lrf(REGELN, SIMON, P, 19477.5, 19477.5, 28630, "buy", 2, 3, mll=0)
check(f["liq_regel_balance"] == 16477.5 and f["liq_regel_soft"] is True, "Radar Simon …6316: 16.477,50 (vorher über TX4 dasselbe Level)")
f0 = ALT["liq_regel_felder"](REGELN_ALT, SIMON, P, 19477.5, 19477.5, 28630, "buy", 2, 3, mll=0)
check(f0["liq_regel_balance"] == 16477.5, "… vorher (TX4, Topstep-DLL) ebenfalls 16.477,50")
# Prüfer-Befund Radar-Fail-closed: Tagesstart mehr als 3.000 über der Start-Balance → nur MLL (wie TX4 vorher)
for ts_x in (23000, 170000):
    f = lrf(REGELN, SIMON, P, 19477.5, ts_x, 28630, "buy", 2, 3, mll=0)
    f0 = ALT["liq_regel_felder"](REGELN_ALT, SIMON, P, 19477.5, ts_x, 28630, "buy", 2, 3, mll=0)
    check(f["liq_gilt"] == "boden" and f["liq_regel_balance"] == 0 and f["liq_regel_level_nq"] == f0["liq_regel_level_nq"] and f["liq_regel_level_nq"] is not None,
          f"Radar Tagesstart {ts_x} unplausibel → MLL-Level {f['liq_regel_level_nq']} wie vorher")
f = lrf(REGELN, SIMON, P, 19477.5, 22000, 28630, "buy", 2, 3, mll=0)
check(f["liq_gilt"] == "regel" and f["liq_regel_balance"] == 19000, "Radar Tagesstart 22.000 (2.522 über Start, plausibel) → Tageslimit 19.000")
# Topstep-Challenge (id 8) unverändert, auch mit unplausiblem Tagesstart
C_D = dict(C_NO, external_id="150KTC-SKU-V2-DLL-1", starting_balance=150000, max_drawdown=4500)
Pc = {"route": "tsv2", "konto_typ": "challenge"}
for ts_x in (152000, 156000):
    a_, b_ = lrf(REGELN, C_D, Pc, 152000, ts_x, 28630, "buy", 20, 2, mll=145500), ALT["liq_regel_felder"](REGELN_ALT, C_D, Pc, 152000, ts_x, 28630, "buy", 20, 2, mll=145500)
    check(a_ == b_, f"Radar Topstep-Challenge Tagesstart {ts_x}: bitgleich")

print("3) Hedge-Level im Tab (hedgeTopstepDll)")
html_neu = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
html_alt = git("prophos.html")


def fn(html, name, neu_name=None):
    i = html.index(f"  function {name}(")
    s = html[i:html.index("\n  }\n", i) + 4]
    return s.replace(f"function {name}(", f"function {neu_name}(") if neu_name else s


js = """
const firmNormRichtung = f => String(f || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const hedgeTagesstart = (plan, startBal) => ({ balance: (plan && plan.ts != null) ? plan.ts : startBal, quelle: 'start_balance' });
""" + fn(html_neu, "liqRegelWaehlen") + fn(html_neu, "hedgeTopstepDll") + fn(html_alt, "hedgeTopstepDll", "hedgeTopstepDllAlt") + """
const R = JSON.parse('REGELN'), RA = JSON.parse('RALT'), out = {};
const MIKE = { id: 'm', firm: 'Topstep', type: 'winning_days', name: 'EXPRESS-V2-682437-57131691 → Winning Days', externalId: 'EXPRESS-V2-682437-57131691', dllUsd: null };
const INA = { id: 'i', firm: 'Topstep', type: 'winning_days', name: '150k PRO-V2-DLL-688698-92558936 → Winning Days', externalId: 'PRO-V2-DLL-688698-92558936', dllUsd: null };
const CNO = { id: 'c', firm: 'Topstep', type: 'challenge', name: '150k 150KTC-SKU-V2-1 → Challenge', externalId: '150KTC-SKU-V2-1', dllUsd: null };
out.mike = hedgeTopstepDll({}, MIKE, 19477.5, R);
out.mikeFunded = hedgeTopstepDll({}, Object.assign({}, MIKE, { type: 'funded' }), 19477.5, R);
out.mikeAlt = hedgeTopstepDll({}, MIKE, 19477.5, RA);
out.ina = hedgeTopstepDll({}, INA, 18347.76, R);
out.cno = hedgeTopstepDll({}, CNO, 152000, R);
out.mikeUnpl = hedgeTopstepDll({ ts: 23000 }, MIKE, 19477.5, R);
// Bitgleich: alte Regeln (SQL nicht eingespielt) bzw. andere Firmen — 3.000 Zufallsfälle alt gegen neu
let gleich = 0, n = 0, seed = 17;
const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647 };
const FIRMEN = ['Topstep', 'Topstep', 'Lucid Trading', 'Tradeify', 'Apex Trader'], TYPEN = ['challenge', 'phase1', 'funded', 'winning_days', ''];
const SKUS = ['EXPRESS-V2-682437-1', 'EXPRESS-V2-DLL-1', '150KTC-SKU-V2-DLL-1', 'PRO-V2-1', ''];
for(let k = 0; k < 3000; k++){
  const firm = FIRMEN[Math.floor(rnd() * FIRMEN.length)], alteRegeln = firm === 'Topstep';
  const acc = { id: 'x' + k, firm, type: TYPEN[Math.floor(rnd() * TYPEN.length)], externalId: SKUS[Math.floor(rnd() * SKUS.length)], name: '150k',
                dllUsd: [null, null, 0, 2000][Math.floor(rnd() * 4)] };
  const sb = Math.round(rnd() * 30000 - 3000), plan = rnd() < 0.3 ? { ts: sb + Math.round(rnd() * 8000 - 4000) } : {};
  const rg = alteRegeln ? RA : R;
  n++; if(JSON.stringify(hedgeTopstepDll(plan, acc, sb, rg)) === JSON.stringify(hedgeTopstepDllAlt(plan, acc, sb, rg))) gleich++;
}
out.gleich = gleich; out.n = n;
JSON.stringify(out);
""".replace("'REGELN'", "'" + json.dumps(REGELN) + "'").replace("'RALT'", "'" + json.dumps(REGELN_ALT) + "'")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
    tf.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", tf.name], capture_output=True, text=True, timeout=60)
    r = json.loads(aus.stdout.strip() or "{}")
    if not r:
        print(aus.stderr[:800])
finally:
    os.unlink(tf.name)
m = r.get("mike") or {}
check(m.get("dl") == 3000 and m.get("liq_balance") == 16477.5 and m.get("regel_id") == 27, f"Mike-SKU WD → DLL 3.000 aus der WD-Zeile (Liq {m.get('liq_balance')})")
check((r.get("mikeFunded") or {}).get("regel_id") == 26, "Mike-SKU Funded → Funded-Zeile")
check(r.get("mikeAlt") is None, "ohne die neuen Zeilen: Mike-SKU wie vorher kein DLL")
check((r.get("ina") or {}).get("dl") == 3000 and (r.get("ina") or {}).get("liq_balance") == 15347.76, "Ina PRO …8936 → 3.000 (Liq 15.347,76 bei Tagesstart 18.347,76)")
check(r.get("cno") is None, "Challenge ohne DLL-SKU: unverändert kein DLL")
check(r.get("mikeUnpl") is None, "unplausibler Tagesstart → nur MLL (fail-closed wie TX4)")
check(r.get("n") == 3000 and r.get("gleich") == 3000, f"Bitgleich Tab: {r.get('gleich')}/{r.get('n')} (andere Firmen; Topstep mit alten Regeln)")

print("4) Bitgleich WD-SL-Würfel (Backend)")
REGELN_ALLE = [
    {"id": 3, "firma": "Apex Trader", "kontotyp": "challenge", "groesse": None, "art": "tagesstart", "betrag_usd": 2000},
    {"id": 4, "firma": "Apex Trader", "kontotyp": "funded", "groesse": 150000, "art": "stufen",
     "stufen": [{"ab_balance": 150000, "daily_loss_usd": 2500}, {"ab_balance": 155000, "daily_loss_usd": 3000}, {"ab_balance": 160000, "daily_loss_usd": 4000}]},
    {"id": 7, "firma": "Tradeify", "kontotyp": "winning_days", "groesse": None, "art": "boden", "lock_ueber_start_usd": 100},
    {"id": 18, "firma": "Lucid Trading", "kontotyp": "winning_days", "groesse": 150000, "art": "tagesstart", "betrag_usd": 2700},
    {"id": 19, "firma": "FTMO Futures", "kontotyp": "winning_days", "groesse": 50000, "art": "tagesstart", "betrag_usd": 1000}]
rnd0 = random.Random(20261117)
FIRMEN = [("Tradeify", "TDFYSL150-0001", 150000, REGELN), ("Lucid Trading", "LT150-0002", 150000, REGELN), ("Apex Trader", "APEX-150-0003", 150000, REGELN),
          ("FTMO Futures", "FTMO50-0004", 50000, REGELN), ("Topstep", "EXPRESS-V2-682437-57131691", 150000, REGELN_ALT),
          ("Topstep", "PRO-V2-682437-1", 150000, REGELN_ALT)]
gleich = 0
for n in range(4000):
    f, ext, gr, rg = FIRMEN[n % len(FIRMEN)]
    acc = {"id": f"k{n}", "firm": f, "account_type": "winning_days", "name": f"{int(gr / 1000)}k {ext}", "external_id": ext, "starting_balance": gr,
           "max_drawdown": rnd0.choice([None, 2000, 4500]), "tv_balance": round(rnd0.uniform(-3000, 25000) if f == "Topstep" else rnd0.uniform(gr - 4000, gr + 12000), 2),
           "tv_balance_at": iso(J - timedelta(hours=rnd0.uniform(0, 30))), "dll_usd": rnd0.choice([None, None, None, 0])}
    fr = [{"id": f"f{n}-{i}", "master_account_id": acc["id"], "started_at": iso(J - timedelta(hours=rnd0.uniform(1, 60))),
           "ended_at": iso(J - timedelta(hours=rnd0.uniform(0.5, 1))), "mll_start": rnd0.choice([None, 0.0, -2500.0, 145500.0]),
           "bal_end": rnd0.choice([None, acc["tv_balance"]]), "bal_start": round(acc["tv_balance"] + rnd0.uniform(-2000, 2000), 2)} for i in range(rnd0.randint(0, 3))]
    s = rnd0.random()
    gleich += fuer_alt(regel, PLAN, acc, REGELN_ALLE + rg, fr, rnd=Folge(s, 0.37)) == fuer(regel, PLAN, acc, REGELN_ALLE + rg, fr, rnd=Folge(s, 0.37))
check(gleich == 4000, f"Bitgleich: {gleich}/4000 (Tradeify, Lucid, Apex, FTMO Futures mit neuen Regeln; Topstep ohne DLL-SKU mit alten Regeln)")

print("ALLE OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
