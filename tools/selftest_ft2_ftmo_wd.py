#!/usr/bin/env python3
"""Selbsttest FT2 + AP6 (Master 11.11.2026, Finn 21:05): FTMO Futures Winning Days — Farmer-Schlüssel ftmofutures, Gewinntag 200 $ (zählt schon in der
Funded-Phase), fester WD-SL 750–850 $ gekappt am Daily Loss 1.000 $ ab Tagesstart (Hard Breach, sonst kein Plan), Abhaken → Waiting for Payout auch für
Winning Days, „→ Funded“ → „→ Winning Days“ beim Umstellen. Echte Funktionen aus app.py, Frontend-Funktionen in JavaScriptCore. Ohne Netz, Platzhalter-IDs.
Aufruf: python3 tools/selftest_ft2_ftmo_wd.py"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


K = "f0000000-0000-0000-0000-00000000000f"
print("1) Firmen-Schlüssel und Gewinntag")
check(app.fdp_wd_schluessel("FTMO Futures", "50000") == "ftmofutures" and app.fdp_wd_schluessel("FTMO", "100000") == "sonst"
      and app.fdp_wd_schluessel("FundedNext Futures") == "fnfutures" and app.fdp_wd_schluessel("Apex Trader", "100000") == "apex100",
      "FTMO Futures → ftmofutures, FTMO CFD bleibt „sonst“, andere unverändert")
check(app.WD_FU_STANDARD["ftmofutures"] == [220, 240], "TP-Standard 220–240 $")
FT = {"id": K, "name": "50k FTMO0000000 → Funded", "firm": "FTMO Futures", "account_type": "funded", "created_at": "2026-11-03T08:00:00Z", "goal_wd_korrektur": 0}
check(app.wd_min_gewinn(FT) == 200.0 and app.wd_min_gewinn(dict(FT, firm="FTMO")) is None and app.wd_min_gewinn(dict(FT, goal_min_profit=300)) == 300,
      "Gewinntag ≥ 200 $ (FTMO CFD ohne Linie, goal_min_profit am Konto gewinnt)")
check(app.wd_auto_konto(FT) and app.wd_auto_konto(dict(FT, account_type="winning_days")), "Funded- und WD-Konto zählen automatisch (Futures-Firma)")
pl = lambda tag, v: {"master_account_id": K, "status": "completed", "master_pl": v, "ended_at": f"{tag}T15:00:00Z"}   # noqa: E731
P = [pl("2026-11-04", 4100), pl("2026-11-05", 199.99), pl("2026-11-06", 230), pl("2026-11-06", -20), pl("2026-11-07", -500), pl("2026-11-10", 240)]
tage = app.wd_auto_tage(FT, P)
check([t for t, _v in tage] == ["2026-11-04", "2026-11-06", "2026-11-10"] and app.wd_auto_stand(FT, P) == 3,
      f"schon in der Funded-Phase: Big Trade 4.100 $, 06.11. Tagessumme 230 − 20 = 210 $ und 240 $ zählen; 199,99 $ und der Verlusttag nicht ({tage})")

print("2) Fester SL je Firma (sl_wuerfel.firmen)")
STD = {"an": True, "stufen": [{"anteil": 50, "von": None, "bis": None}, {"anteil": 10, "von": 10, "bis": 20}, {"anteil": 10, "von": 20, "bis": 30}, {"anteil": 30, "von": 30, "bis": 40}]}
r, q = app.wd_sl_wuerfel_regel(dict(STD, firmen={"ftmofutures": {"usd": [750, 850]}, "kaputt": {"usd": [900, 100]}, "x": {"usd": "a"}}))
check(q == "db" and r["firmen"] == {"ftmofutures": {"usd": [750.0, 850.0]}} and r["stufen"] == STD["stufen"], "firmen gelesen, kaputte Einträge fallen einzeln weg, Stufen unverändert")
r0, _ = app.wd_sl_wuerfel_regel(STD)
check("firmen" not in r0 and app.wd_sl_wuerfel_regel(dict(STD, an=False))[0] is None, "ohne firmen wie bisher; Würfel aus → aus")
F = app.wd_sl_fest
werte = [F([750, 850], 1000.0, rnd=random.Random(i))["usd"] for i in range(400)]
check(min(werte) >= 750 and max(werte) <= 850 and min(werte) < 770 and max(werte) > 830, f"Puffer 1.000 $: SL immer 750–850 $, Spanne genutzt ({min(werte)}–{max(werte)})")
g = F([750, 850], 600.0, rnd=random.Random(1))
check(g["usd"] == 550 and g["gekappt"] and g["ohne"] is False and "gekappt" in g["grund"], f"Puffer 600 $ (heute schon −400 $): SL auf 550 $ gekappt ({g['usd']})")
s1, s2 = F([750, 850], 140.0, rnd=random.Random(1)), F([750, 850], None, rnd=random.Random(1))
check(s1["sperre"] and s1["ohne"] and "kein Plan" in s1["grund"] and s2["sperre"] and "unbekannt" in s2["grund"],
      "Puffer 140 $ (SL < 100 $) bzw. unbekannt → kein Plan mit Grund (Hard Breach)")

print("3) wd_sl_fest_fuer_plan — fail-closed, echte Puffer-Rechnung (liq_regeln tagesstart 1.000 $)")
LIQ = [{"id": 99, "firma": "FTMO Futures", "kontotyp": "winning_days", "groesse": 50000, "art": "tagesstart", "betrag_usd": 1000, "maxdd_art": "eod_trailing",
        "maxdd_usd": None, "lock_ueber_start_usd": None, "stufen": None, "wie_kontotyp": None, "maxdd_lock_ueber_groesse_usd": None},
       {"id": 6, "firma": None, "kontotyp": "winning_days", "groesse": None, "art": None, "betrag_usd": None, "maxdd_art": None, "maxdd_usd": None,
        "lock_ueber_start_usd": None, "stufen": None, "wie_kontotyp": None, "maxdd_lock_ueber_groesse_usd": None}]
ACC = {"id": K, "name": "50k FTMO0000000 → Winning Days", "firm": "FTMO Futures", "account_type": "winning_days", "max_drawdown": 3000, "starting_balance": 50000,
       "tv_balance": 54700.0, "tv_balance_at": "2026-11-12T01:00:00Z"}
PLAN = {"master_account_id": K, "start_um": "2026-11-12T06:00:00Z"}
SP = [750.0, 850.0]
FF = app.wd_sl_fest_fuer_plan
w = FF(SP, PLAN, ACC, LIQ, [], rnd=random.Random(5))
check(w["regel"] == "sl_fest" and w["ohne"] is False and 750 <= w["usd"] <= 850 and abs(w["puffer"] - 1000.0) < 0.01 and abs(w["liq_balance"] - 53700.0) < 0.01,
      f"erster Trade des Tages: Puffer = Daily Loss 1.000 $ ab Tagesstart 54.700 → SL {w['usd']} $ (Grenze 53.700)")
FR = [{"id": "alt", "master_account_id": K, "started_at": "2026-11-12T03:00:00Z", "ended_at": "2026-11-12T03:40:00Z", "bal_start": 54700.0, "bal_end": 54300.0}]
w2 = FF(SP, dict(PLAN, start_um="2026-11-12T07:00:00Z"), dict(ACC, tv_balance=54300.0, tv_balance_at="2026-11-12T04:00:00Z"), LIQ, FR, rnd=random.Random(5))
check(w2["ohne"] is False and w2["usd"] == 550 and abs(w2["puffer"] - 600.0) < 0.01,
      f"zweiter Trade nach −400 $: Tagesstart bleibt 54.700, Puffer 600 $ → SL 550 $ (mit SL nie über die Tagesgrenze) ({w2['usd']}, {w2['puffer']})")
w3 = FF(SP, dict(PLAN, start_um="2026-11-12T07:00:00Z"), dict(ACC, tv_balance=53840.0, tv_balance_at="2026-11-12T04:00:00Z"), LIQ, [dict(FR[0], bal_end=53840.0)],
        rnd=random.Random(5))
check(w3.get("sperre") is True and w3["sperre_art"] == "puffer" and "kein Plan" in w3["grund"], f"nach −860 $: nur 140 $ bis zur Grenze → kein Plan ({w3['grund']})")
fehler_faelle = {
    "Konto fehlt": FF(SP, PLAN, None, LIQ, []),
    "liq_regeln fehlen": FF(SP, PLAN, ACC, [], []),
    "Balance nicht nachgelesen": FF(SP, dict(PLAN, start_um="2026-11-12T07:00:00Z"), dict(ACC, tv_balance_at="2026-11-12T02:00:00Z"), LIQ,
                                    [dict(FR[0], ended_at="2026-11-12T03:40:00Z", bal_end=None)]),
    "früherer Trade heute ohne Start-Balance": FF(SP, dict(PLAN, start_um="2026-11-12T07:00:00Z"), dict(ACC, tv_balance_at="2026-11-12T04:00:00Z"), LIQ,
                                                  [dict(FR[0], bal_start=None)]),
}
check(all(v.get("sperre") is True and v.get("sperre_art") == "daten" and v.get("ohne") is True and not v.get("usd") for v in fehler_faelle.values()),
      f"jede Unsicherheit sperrt (nie ohne SL geplant): {', '.join(fehler_faelle)}")
w4 = FF(SP, dict(PLAN, start_um="2026-11-12T07:00:00Z"), dict(ACC, tv_balance=54300.0, tv_balance_at="2026-11-12T04:00:00Z"), LIQ,
        [dict(FR[0], started_at="2026-11-11T03:00:00Z", bal_start=None)], rnd=random.Random(5))
check(w4.get("sperre") is None and w4["ohne"] is False, "Trade von GESTERN ohne Start-Balance stört nicht (nur derselbe CME-Tag)")
check(app.wd_sl_fest_schluessel({"ftmofutures": {"usd": SP}}, ACC) == {"usd": SP} and app.wd_sl_fest_schluessel({"ftmofutures": {"usd": SP}}, dict(ACC, firm="FTMO")) is None
      and app.wd_sl_fest_schluessel({}, ACC) is None, "Schlüssel je Konto: FTMO Futures ja, FTMO CFD nein, ohne Einrichtung nein")
AP = {"id": "a1", "name": "100k PAAPEX0000 → Winning Days", "firm": "Apex Trader", "account_type": "winning_days", "max_drawdown": 3000,
      "tv_balance": 103000.0, "tv_balance_at": "2026-11-12T01:00:00Z"}
wa = app.wd_sl_fuer_plan(dict(r), {"master_account_id": "a1", "start_um": "2026-11-12T06:00:00Z"}, AP, LIQ, [], rnd=random.Random(5))
check(wa["regel"] == "sl_wuerfel" and "sperre" not in wa, "andere Firma (Apex) würfelt weiter nach Stufen (wd_sl_fuer_plan unverändert)")

print("3b) Lesen unabhängig vom globalen Schalter, Nachwürfel-Takt")
_sb_alt = app.sb_select
app.sb_select = lambda t, p: [{"sl_wuerfel": {"an": False, "stufen": [], "firmen": {"ftmofutures": {"usd": [750, 850]}}}}] if t == "wd_farmer_regeln" else []
check(app._wd_sl_fest_lesen() == {"ftmofutures": {"usd": [750.0, 850.0]}}, "Würfel aus + kaputte Stufen: feste SL gelten trotzdem (Prüfer MUSS 5)")
app.sb_select = lambda t, p: (_ for _ in ()).throw(RuntimeError("weg"))
check(app._wd_sl_fest_lesen() == {"ftmofutures": {"usd": [750.0, 850.0]}}, "Lesefehler → letzter guter Stand")
# SL1-Takt mit nachgebauter DB: Würfel AUS, FTMO-Rückfall-Pläne bekommen trotzdem den festen SL; Puffer zu klein → Grund ohne master_sl; Daten unklar → nichts
import datetime as _dt  # noqa: E402
J = _dt.datetime(2026, 11, 12, 4, 0, tzinfo=_dt.timezone.utc)
RUECK = {"ohne": True, "grund": app.WD_SL_RUECKFALL_GRUND}
PL1 = {"id": "p-ok", "master_account_id": K, "status": "planned", "start_um": "2026-11-12T06:00:00Z", "winning_day": True, "master_firm": "FTMO Futures",
       "notes": "Winning-Day-Farmer", "mt5_baseline": {"wd_sl": RUECK}, "updated_at": "2026-11-12T03:59:00Z", "route": "tvv2"}
K2, K3 = "f0000000-0000-0000-0000-0000000000f2", "f0000000-0000-0000-0000-0000000000f3"
PL2 = dict(PL1, id="p-eng", master_account_id=K2)
PL3 = dict(PL1, id="p-daten", master_account_id=K3)
KONTEN = {K: ACC, K2: dict(ACC, id=K2, tv_balance=53840.0, tv_balance_at="2026-11-12T03:50:00Z"), K3: dict(ACC, id=K3, tv_balance=None)}
FR2 = [{"id": "alt2", "master_account_id": K2, "started_at": "2026-11-12T02:00:00Z", "ended_at": "2026-11-12T02:40:00Z", "bal_start": 54700.0, "bal_end": 53840.0}]
DBU = []


def sb_select_fake(t, p):
    if t == "wd_farmer_regeln":
        return [{"sl_wuerfel": {"an": False, "firmen": {"ftmofutures": {"usd": [750, 850]}}}}]
    if t == "trade_plans":
        return [dict(PL1), dict(PL2), dict(PL3)]
    if t == "accounts":
        return [dict(v) for v in KONTEN.values()]
    return []


app.sb_select = sb_select_fake
_alt = (app._liq_regeln_laden, app._wd_fruehere_trades, app.sb_update)
app._liq_regeln_laden = lambda *a, **k: LIQ
app._wd_fruehere_trades = lambda mids: FR2
app.sb_update = lambda t, f, u: DBU.append((f["id"], u)) or [dict(u)]
if hasattr(app, "wd_sl_nach_kandidat"):
    _kand = app.wd_sl_nach_kandidat
    app.wd_sl_nach_kandidat = lambda p, j: True
erg = app.wd_sl_nach_tick(J, rnd=random.Random(3))
geschrieben = {pid: u for pid, u in DBU}
ok1 = "eq.p-ok" in geschrieben and 750 <= (geschrieben["eq.p-ok"].get("master_sl") or 0) <= 850 and geschrieben["eq.p-ok"]["mt5_baseline"]["wd_sl"]["regel"] == "sl_fest"
ok2 = ("eq.p-eng" in geschrieben and "master_sl" not in geschrieben["eq.p-eng"] and geschrieben["eq.p-eng"]["mt5_baseline"]["wd_sl"].get("sperre") is True
       and geschrieben["eq.p-eng"].get("start_claim_art") == "verbrauch" and geschrieben["eq.p-eng"].get("start_um_gestartet_at"))
ok3 = "eq.p-daten" not in geschrieben and any(x["id"] == "p-daten" for x in erg.get("uebersprungen", []))
check(not erg.get("aus") and ok1 and ok2 and ok3, f"Würfel aus: SL fest 750–850 gesetzt · Puffer zu klein → Plan verbraucht (Claim 'verbrauch', kein master_sl, Kette frei) · Daten unklar → nichts, nächster Takt ({erg.get('uebersprungen')})")
app.sb_select = _sb_alt
app._liq_regeln_laden, app._wd_fruehere_trades, app.sb_update = _alt
if hasattr(app, "wd_sl_nach_kandidat"):
    app.wd_sl_nach_kandidat = _kand

print("4) POST /admin/wd-plaene, Abhaken (AP6)")
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
i_f, i_rec, i_w, i_ins = (SRC.find("_fest = wd_sl_fest_schluessel(sl_fest, sl_konten.get(mid) or acc[0])"),
                          SRC.find('elif sl_regel and (wd_ist_recoverer_plan(body) or (r or {}).get("wd_ausgleich") is True):'),
                          SRC.find("wd_sl = wd_sl_fuer_plan(sl_regel, body, sl_konten.get(mid), sl_liq, sl_frueher)"), SRC.find('angelegt.append(sb_insert("trade_plans", body))'))
check(0 < i_f < i_rec < i_w < i_ins and 'if wd_sl.get("sperre") or not wd_sl.get("usd"):' in SRC and "mit_fest=bool(sl_fest)" in SRC
      and 'sl_fest_fehler = f"Kontext nicht lesbar' in SRC,
      "POST: fester SL vor Recoverer/Ausgleich/Würfel, Kontext auch bei Würfel aus, Kontext-/Rechenfehler sperren, nie ohne SL angelegt")
check('uebersprungen.append({"master_account_id": mid, "grund": WD_GRUND_WAITING}); continue' in SRC and '"select": "id,user_id,name,firm,waiting_payout_since"' in SRC,
      "Konto auf Waiting for Payout wird übersprungen")
check('_ws.get("regel") in ("sl_wuerfel", "sl_fest")' in SRC, "PATCH: fester SL bleibt stehen wie der gewürfelte (Prüfer MUSS 4)")
check('else WD_GRUND_SL_DATEN)}); continue' in SRC and app.WD_GRUND_SL_DATEN in open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read().split("const WD_AUTO_HINWEISE")[1][:600],
      "Daten-Sperre im POST mit festem Text, der in WD_AUTO_HINWEISE steht (nächster Lauf versucht es wieder)")
U = app.wd_erl_konto_umstellen_upd
u1, g1 = U({"account_type": "winning_days", "firm": "FTMO Futures", "waiting_payout_since": None}, "waiting", "2026-11-12T10:00:00Z", "12.11.2026")
u2, g2 = U({"account_type": "winning_days", "firm": "Tradeify", "waiting_payout_since": "2026-11-11T10:00:00Z"}, "waiting", "x", "y")
u3, g3 = U({"account_type": "funded", "firm": "Apex Trader"}, "waiting", "x", "y")
check(u1 == {"waiting_payout_since": "2026-11-12T10:00:00Z"} and u2 is None and "schon" in g2 and u3 is None,
      "AP6a: Winning Days → Waiting for Payout (wie Funded CFD), schon wartend / Funded Futures → nein")
u4, _ = U({"account_type": "funded", "firm": "FTMO Futures", "name": "50k FTMO0000000 → Funded", "notes": None}, "winning_days", "x", "12.11.2026")
u5, _ = U({"account_type": "funded", "firm": "FTMO Futures", "name": "50k FTMO ohne Pfeil", "notes": None}, "winning_days", "x", "12.11.2026")
check(u4["name"] == "50k FTMO0000000 → Winning Days" and u4["account_type"] == "winning_days" and "name" not in u5,
      "AP6b: „→ Funded“ → „→ Winning Days“ beim Umstellen (wie fdp_planen); ohne Pfeil Name unverändert")
check('"select": "id,name,account_type,firm,notes,waiting_payout_since"' in SRC, "Erledigt-Weg liest den Namen mit")
z = app.payout_anfrage_konto_felder({"account_type": "winning_days", "firm": "FTMO Futures", "waiting_payout_since": "2026-11-12T10:00:00Z", "goal_target": 5}, None, "2026-11-13")
check(z.get("waiting_payout_since", "x") is None, "Payout-Anfrage leert Waiting wieder (Farmer plant danach weiter)")

print("5) Frontend (JavaScriptCore + Anker)")
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
js_key = HTML[HTML.index("  function tpVorplanFirmaKey(firm, konto){"):HTML.index("\n  }\n", HTML.index("  function tpVorplanFirmaKey(firm, konto){")) + 4]
js_min = HTML[HTML.index("  function zielWdMin(a){"):HTML.index("\n  }\n", HTML.index("  function zielWdMin(a){")) + 4]
if shutil.which("osascript"):
    js = ("function run(){ var tpVpApex100 = function(k){ return /100k/i.test(String(k && k.name || '')) }; var istTradeifyCfd = function(f){ return /tradeify/.test(f) && /cfd/.test(f) };\n"
          + js_key + "\n" + js_min + "\nreturn JSON.stringify({ k: [tpVorplanFirmaKey('FTMO Futures'), tpVorplanFirmaKey('FTMO'), tpVorplanFirmaKey('FundedNext Futures'), tpVorplanFirmaKey('Apex Trader', { name: '100k x' })],"
          " m: [zielWdMin({ firm: 'FTMO Futures' }), zielWdMin({ firm: 'FTMO' }), zielWdMin({ firm: 'FTMO Futures', goalMinProfit: 300 })] }) }")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
    os.unlink(f.name)
    check(aus.returncode == 0, f"Frontend-Funktionen laufen ({aus.stderr.strip()[:160]})")
    if aus.returncode == 0:
        j = json.loads(aus.stdout)
        check(j["k"] == ["ftmofutures", "sonst", "fnfutures", "apex100"] and j["m"] == [200, None, 300],
              f"tpVorplanFirmaKey / zielWdMin wie app.py ({j})")
else:
    check(False, "osascript fehlt — Frontend-Teil nicht geprüft")
check("'topstep', 'ftmofutures', 'sonst']" in HTML and "ftmofutures: [220, 240], sonst: [270, 290] }" in HTML and "ftmofutures: ['FTMO Futures'," in HTML,
      "TP_VP_FIRMEN, TP_VP_VORGABE, WD_FIRMEN kennen ftmofutures")
check('data-vp-fu="ftmofutures-von"' in HTML and 'data-vp-fu="ftmofutures-bis"' in HTML, "altes TP-Formular hat ein Feld (sonst schriebe tpVorplanRegelnLesen [0, 0])")
check("if(altF && typeof altF === 'object') neu.firmen = altF" in HTML and "from('wd_farmer_regeln').select('sl_wuerfel').eq('id', 1).maybeSingle()" in HTML,
      "Zufalls-SL speichern behält sl_wuerfel.firmen — frisch aus der DB, Lesefehler speichert nicht")
check("if(acc && acc.waitingPayoutSince) return { fehler: 'Waiting for Payout" in HTML, "Tab-Rückfall plant kein Konto auf Waiting for Payout")
i_p, i_l = HTML.find("const fp = await wdSlFestPflicht(plan, sl)"), HTML.find("    _tpOrbitLaeuft = true\n    sfSendetHier(plan.id)   // CL1")
check(0 < i_p < i_l and "async function wdSlFestPflicht(plan, sl){" in HTML, "Tab: Pflicht-SL-Prüfung vor dem ersten Klick (auch Hand-/Fern-Start; im Stub geprüft: FTMO ohne SL blockiert, sonst frei)")
check("&& !festDa)) return null" in HTML, "Rückfall-Marke auch bei Würfel aus, wenn feste SL eingerichtet sind (Nachwürfeln findet den Plan)")
check("'ftmo futures': 200, apex:" in HTML and "['ftmo futures', 200]" in HTML, "Gewinntag-Linien im Frontend 200 $ (TC_GOOD_DAY_MIN, zielWdMin)")
std_js = re.search(r"  const E4_WD_FIRMEN_STD = \{(.*?)\} \}\n", HTML, re.S)
check(std_js is not None and "ftmofutures:" in std_js.group(1) and "ftmofutures" in app.WD_FIRMEN_REGELN_STD, "E4-Standard in Frontend und app.py mit ftmofutures")

print("6) SQL-Datei")
sq = open(os.path.join(WURZEL, "sql", "2026-11-11_ft2_ftmo_futures_winning_days.sql"), encoding="utf-8").read()
check('\'{"ftmofutures": [220, 240]}\'' in sq and '\'{"ftmofutures": [2, 3]}\'' in sq and '\'{"ftmofutures": {"usd": [750, 850]}}\'' in sq
      and "'FTMO Futures', 'winning_days', 50000, 'tagesstart', 1000" in sq and "where lower(firma) = 'ftmo futures'" in sq, "TP, Kontrakte, fester SL, Daily Loss 1.000 $ (idempotent)")
check("create trigger trade_plans_wd_sl_pflicht before update on public.trade_plans" in sq and "coalesce(new.master_sl, 0) <= 0" in sq
      and "coalesce(new.start_claim_art, '') <> 'verbrauch'" in sq and "select a.firm from public.accounts a where a.id = new.master_account_id" in sq
      and """else '{"an": false, "firmen": {"ftmofutures": {"usd": [750, 850]}}}'::jsonb end""" in sq
      and "(old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)" in sq and "(w.sl_wuerfel->'firmen') ? 'ftmofutures'" in sq
      and "REIHENFOLGE" in sq, "DB-Riegel: FTMO-Futures-WD startet nie ohne Master-SL (Claim/Start), nur solange eingerichtet; Reihenfolge Code → Tabs → SQL")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
