#!/usr/bin/env python3
"""Selbsttest NL1 (Master 24.11.2026, Ina · Lucid 150k …0009, Plan 22c144fc): Endlesung 23.11. 18:23 UTC scheiterte 4× am Tradovate-Login
(login_formular) — danach griff die Login-Bremse („Login prüfen“, nur noch von Hand) und es wurde nie wieder gelesen; der Plan sperrte das Konto drei Tage.
Geprüft: (1) prophos.html tvV2EndlesungGrund + Spät-Lesung (alle 2–4 h gestreut, nur mit Start-Balance, ≤ 72 h nach dem Ende; Konto weg/aufgegeben/ohne
Start-Balance wie bisher), endlesungStatus (Radar-Zeile) und pulsTermine-Quelltext; (2) app.py alarm_endlesung_haengt (einmal 🟠 je Plan 12 h nach dem
Ende, Format ID · Firma Größe …4) und der Aufruf im alarm_tick. Ohne Netz. Aufruf: python3 tools/selftest_nl1_endlesung_spaet.py"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) PC-Tab: tvV2EndlesungGrund + Spät-Lesung")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
a = html.index("  const TV_ENDLESUNG_MAX = 8")
b = html.index("  function tvV2EndlesungFaellig(")
block = html[a:b]
s = html.index("  function endlesungStatus(")
e = html.index("  window._endlesungStatus = endlesungStatus")
status_fn = html[s:e]
STUBS = """
var window = {}; var tradePlans = [];
function planIstPuls(p){ return true }
function planPlUserscript(p){ return false }
function tvV2Handelstag(x){ return '2026-11-23' }
function tvV2NachleseAb(){ return 0 }
function kontoWegChipText(){ return 'weg' }
function kontoWegUrteilVon(){ return null }
function tpKetteLesenWeiter(){ return false }
function tpKetteNr(){ return null }
function tvV2NachleseMs(){ return 60000 }
"""
TEST = r"""
const ENDE = Date.parse('2026-11-23T08:00:43.599Z'), PULS = Date.parse('2026-11-23T18:23:21.280Z')
const fin = { at: '2026-11-23T08:00:43.599Z', datum: '2026-11-23', grund: 'demo_tp', quelle: 'demo', puls_at: '2026-11-23T18:23:21.280Z', puls_versuche: 4,
  puls_aufgegeben: false, puls_login_fehler: 4, puls_login_at: '2026-11-23T18:23:21.280Z', puls_login_code: 'login_formular',
  puls_fehler: "konto_nicht_erreicht: Tradovate-Login 'LTT0TAM2F74' nicht geschafft (login_formular)" }
const plan = (f, mitBal) => ({ id: '22c144fc-7b40-4811-a009-10ae39ecf237', status: 'review', route: 'tvv2', mt5Baseline: Object.assign({ final: f }, mitBal === false ? { tv: {} } : { tv: { balance_start: 154139 } }) })
const P = tvV2SpaetPauseMs('22c144fc-7b40-4811-a009-10ae39ecf237', 4)
const R = {}
R.pause_h = P / 3600000
const pausen = []; for(let i = 0; i < 300; i++) pausen.push(tvV2SpaetPauseMs('plan-' + i, i % 9) / 3600000)
R.p_min = Math.min(...pausen); R.p_max = Math.max(...pausen); R.p_gleich = tvV2SpaetPauseMs('x', 3) === tvV2SpaetPauseMs('x', 3)
R.p_neu = tvV2SpaetPauseMs('x', 3) !== tvV2SpaetPauseMs('x', 4) || tvV2SpaetPauseMs('x', 3) !== tvV2SpaetPauseMs('y', 3)
R.vor = tvV2EndlesungGrund(plan(fin), PULS + P - 60000, false)
R.dran = tvV2EndlesungGrund(plan(fin), PULS + P + 60000, false)
R.jetzt_ina = tvV2EndlesungGrund(plan(fin), Date.parse('2026-11-24T18:32:14Z'), false)
R.nach72 = tvV2EndlesungGrund(plan(fin), ENDE + 73 * 3600000, false)
R.ohne_bal = tvV2EndlesungGrund(plan(fin, false), PULS + P + 60000, false)
R.aufg = tvV2EndlesungGrund(plan(Object.assign({}, fin, { puls_aufgegeben: true })), PULS + P + 60000, false)
R.weg = tvV2EndlesungGrund(plan(Object.assign({}, fin, { konto_weg: true })), PULS + P + 60000, false)
const f8 = Object.assign({}, fin, { puls_versuche: 8, puls_login_fehler: 0, puls_login_code: null, puls_login_at: null })
R.v8_vor = tvV2EndlesungGrund(plan(f8), PULS + 30 * 60000, false)
R.v8_dran = tvV2EndlesungGrund(plan(f8), PULS + 4 * 3600000 + 60000, false)
R.v8_login = tvV2EndlesungGrund(plan(Object.assign({}, fin, { puls_versuche: 9 })), PULS + 4 * 3600000 + 60000, false)
R.deckel = tvV2EndlesungGrund(plan(Object.assign({}, fin, { puls_spaet_n: 6 })), PULS + 4 * 3600000 + 60000, false)
R.deckel5 = tvV2EndlesungGrund(plan(Object.assign({}, fin, { puls_spaet_n: 5 })), PULS + 4 * 3600000 + 60000, false)
R.vermutet = tvV2EndlesungGrund(plan(Object.assign({}, fin, { konto_weg_vermutet: true })), PULS + 4 * 3600000 + 60000, false)
R.liq = tvV2EndlesungGrund(plan(Object.assign({}, fin, { grund: 'demo_liq' })), PULS + 4 * 3600000 + 60000, false)
R.offen = tvV2EndlesungGrund(plan(Object.assign({}, fin, { puls_offen_n: 2 })), ENDE + 25 * 3600000, false)
const f2 = Object.assign({}, fin, { puls_versuche: 2, puls_login_fehler: 0, puls_login_code: null, puls_login_at: null })
R.normal = tvV2EndlesungGrund(plan(f2), PULS + 30 * 1000, false)
R.normal2 = tvV2EndlesungGrund(plan(f2), PULS + 20 * 60000, false)
const f1 = Object.assign({}, fin, { puls_login_fehler: 1 })
R.lb1 = tvV2EndlesungGrund(plan(f1), PULS + 10 * 60000, false)
R.force = tvV2EndlesungGrund(plan(fin), PULS + 60000, true)
const st1 = endlesungStatus(fin, 'review', PULS + 60000, '22c144fc', 'tvv2', true)
const st2 = endlesungStatus(fin, 'review', PULS + 60000, '22c144fc', 'tvv2', undefined)
const st3 = endlesungStatus(fin, 'review', ENDE + 80 * 3600000, '22c144fc', 'tvv2', true)
R.st1 = [st1.art, st1.text, !!st1.knopf, st1.bisMs]; R.st2 = [st2.art, st2.text]; R.st3 = [st3.art, st3.text]
print(JSON.stringify(R))
"""
js = STUBS + block + "\n" + status_fn + "\n" + TEST
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as d:
    d.write(js)
p = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
check(p.returncode == 0, f"jsc läuft ({p.stderr[:300]} {p.stdout[-400:]})")
R = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else {}
check(2 <= R.get("pause_h", 0) <= 4 and 2 <= R.get("p_min", 0) and R.get("p_max", 9) <= 4 and R.get("p_min", 9) < 2.2 and R.get("p_max", 0) > 3.8
      and R.get("p_gleich") and R.get("p_neu"), f"Pause 2–4 h, fest je Plan + Versuch, gestreut ({R.get('p_min')} … {R.get('p_max')} h, Ina {R.get('pause_h')} h)")
check(str(R.get("vor", "")).startswith("Pause bis") and "Spät-Lesung" in R.get("vor", "") and "4× Login/Verbindung login_formular" in R.get("vor", ""),
      f"Ina vor der Spät-Lesung → „Pause bis …“ (Reiter Warte auf Puls), nicht „Login prüfen“ ({R.get('vor')})")
check(R.get("dran") == "", "Ina nach 2–4 h → Lesung fällig (vorher: nie wieder)")
check(R.get("jetzt_ina") == "", f"Ina heute (24.11. 18:32 UTC, 24 h nach dem letzten Versuch) → sofort fällig ({R.get('jetzt_ina')!r})")
check(str(R.get("nach72", "")).startswith("Login prüfen"), "72 h nach dem Ende → wie bisher „Login prüfen“ (nur noch von Hand)")
check(str(R.get("ohne_bal", "")).startswith("Login prüfen"), "ohne Start-Balance → wie bisher (Today's P&L hängt am Handelstag)")
check(str(R.get("aufg", "")).startswith("aufgegeben") and R.get("weg") and "Spät-Lesung" not in R.get("weg", ""),
      f"aufgegeben bleibt Stopp ({R.get('aufg')}) · Konto weg → keine Spät-Lesung ({R.get('weg')})")
check(R.get("v8_vor") == "8 Versuche erfolglos" and R.get("v8_dran") == "8 Versuche erfolglos",
      f"Review NL1: 8 Versuche ohne Login-Fehler → wie bisher Schluss (Blow-/Bestanden-Urteile hängen am letzten Fehler) ({R.get('v8_vor')})")
check(R.get("v8_login") == "", "Login-Bremse + schon 9 Versuche (nach Spät-Läufen) → Spät-Lesung läuft weiter bis zum eigenen Deckel")
check(str(R.get("deckel", "")).startswith("Login prüfen") and R.get("deckel5") == "",
      "Deckel: nach 6 Spät-Versuchen wie bisher „Login prüfen“ (kein Login-Sturm bis zur Broker-Sperre)")
check(str(R.get("vermutet", "")).startswith("Login prüfen") and str(R.get("liq", "")).startswith("Login prüfen"),
      "Konto weg vermutet / Liquidations-Ende → keine Spät-Lesung (wie bisher)")
check(R.get("offen") and "Spät-Lesung" not in str(R.get("offen")), f"Position > 24 h offen → keine Spät-Lesung, Stopp wie bisher ({R.get('offen')})")
vs = html[html.index("  async function tvV2EndlesungVersuch("):html.index("  async function tvV2EndlesungVersuch(") + 16000]
check("if(spaetLauf) patch.puls_spaet_n = (Number(fin0.puls_spaet_n) || 0) + 1" in vs and "!force && !spaetLauf && versuch >= TV_ENDLESUNG_MAX" in vs,
      "Versuch zählt puls_spaet_n und toastet bei Spät-Läufen nicht")
check(R.get("normal") == "Pause bis zum nächsten Versuch" and R.get("normal2") == "",
      f"Versuch 2 ohne Bremse → unverändert (45 s Pause, dann fällig) ({R.get('normal')!r} / {R.get('normal2')!r})")
check(str(R.get("lb1", "")).startswith("Pause bis") and "kein schneller neuer Login" in R.get("lb1", ""), "1 Login-Fehler → 30-min-Pause wie bisher")
check(R.get("force") == "", "„Jetzt lesen“ (force) geht immer")
st1, st2, st3 = R.get("st1") or [], R.get("st2") or [], R.get("st3") or []
check(st1[:1] == ["laeuft"] and "Spät-Lesung ab" in st1[1] and st1[2] is True and st1[3], f"Radar/Karte: „Wartet · … Spät-Lesung ab HH:MM“ mit Knopf ({st1[1] if st1 else ''})")
check(st2[:1] == ["aufgegeben"] and "Login prüfen" in st2[1], "Zeile ohne Plan (fremde ID, Start-Balance unbekannt) → wie bisher")
check(st3[:1] == ["aufgegeben"], "nach 72 h → wie bisher „Login prüfen“")
pt = html[html.index("  function pulsTermine("):html.index("  window._pulsTermine = pulsTermine")]
check("tvV2SpaetLesung(p, fin, jetzt)" in pt and "if(lb && lb.pruefen && !sp) continue" in pt and "let t = sp ? sp.bis" in pt, "Puls-Termine kündigen die Spät-Lesung an (Countdown)")

print("2) Railway: alarm_endlesung_haengt")
J = datetime(2026, 11, 24, 18, 32, tzinfo=timezone.utc)
INA = {"id": "22c144fc-7b40-4811-a009-10ae39ecf237", "user_id": "d1f5bcae-2129-49a4-8415-915ab6474a64", "status": "review", "route": "tvv2",
       "master_firm": "Lucid Trading", "master_name": "150k LFE15098406450009 → Challenge", "ended_at": "2026-11-23T08:00:43.599+00:00",
       "fa": "2026-11-23T08:00:43.599Z", "be": None, "tp": None, "q": "demo", "auf": "false", "weg": None, "vers": "4", "lf": "4", "lc": "login_formular", "bs": "154139"}
N = {INA["user_id"]: "Ina"}
ev = app.alarm_endlesung_haengt([INA], N, J)
check(len(ev) == 1 and ev[0][0] == f"{INA['id']}|endlesung_haengt" and ev[0][1] == 2 and ev[0][2] == "endlesung_haengt",
      f"Ina → genau eine 🟠, Schlüssel ohne Zeit (einmal je Plan) ({ev[0][:3] if ev else ''})")
t = ev[0][4] if ev else ""
check(t.startswith("Ina · Lucid Trading 150k …0009: Trade seit 34 h beendet") and "4× Login/Verbindung gescheitert (login_formular)" in t and "Spät-Lesung" in t,
      f"Text: ID · Firma Größe …4, Grund, wie es weitergeht ({t[:200]})")
check(not app.alarm_endlesung_haengt([dict(INA, fa="2026-11-24T07:00:00Z")], N, J), "erst 11,5 h nach dem Ende → noch nichts")
check(not app.alarm_endlesung_haengt([dict(INA, be="155000")], N, J) and not app.alarm_endlesung_haengt([dict(INA, tp="861.5")], N, J)
      and not app.alarm_endlesung_haengt([dict(INA, q="puls")], N, J), "gelesen (Balance / Today's P&L / quelle puls) → nichts")
check(len(app.alarm_endlesung_haengt([dict(INA, route="tsv2", tp="861.5")], N, J)) == 1, "Topstep V2: Today's P&L allein zählt nicht als gelesen → 🟠")
check(not app.alarm_endlesung_haengt([dict(INA, auf="true")], N, J) and not app.alarm_endlesung_haengt([dict(INA, weg="true")], N, J)
      and not app.alarm_endlesung_haengt([dict(INA, kv="true")], N, J), "aufgegeben / Konto weg / Konto weg vermutet → nichts (andere Wege melden das)")
t3 = app.alarm_endlesung_haengt([dict(INA, sn="6")], N, J)[0][4]
check("nur noch „Jetzt lesen“" in t3, "6 Spät-Versuche verbraucht → Text „nur noch Jetzt lesen“")
check(not app.alarm_endlesung_haengt([dict(INA, fa="2026-11-16T08:00:00Z")], N, J), "älter als 7 Tage → nichts (kein Alt-Schwall)")
check(not app.alarm_endlesung_haengt([dict(INA, route="mt5")], N, J) and not app.alarm_endlesung_haengt([dict(INA, status="completed")], N, J),
      "Echo / erledigt → nichts")
t2 = app.alarm_endlesung_haengt([dict(INA, bs=None, lf="0", vers="8", fa="2026-11-21T08:00:00Z", ended_at="2026-11-21T08:00:00Z")], N, J)[0][4]
check("8 Leseversuche erfolglos" in t2 and "nur noch „Jetzt lesen“" in t2, f"ohne Start-Balance / > 72 h → „nur noch Jetzt lesen“ ({t2[60:200]})")
check(app._alarm_konto_kurz("Tradeify", "50k TDYG150123 → Funded") == "Tradeify 50k …0123" and app._alarm_konto_kurz("FTMO", "") == "FTMO",
      "Konto-Kurzform aus master_name")
src = open(os.path.join(WURZEL, "app" + ".py"), encoding="utf-8").read()
tk = src[src.index("def alarm_tick("):src.index("def alarm_tick(") + 9000]
check("alarm_endlesung_haengt(eh, namen, jetzt)" in tk and "(ALARM_ENDLESUNG_FENSTER_TAGE + 1) * 86400" in tk and "_alarm_fremd_verwaltet" in tk,
      "alarm_tick: eigene Abfrage, nur HT (wie die anderen), 8 Tage Gedächtnis im alarm_log")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
