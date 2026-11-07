#!/usr/bin/env python3
"""Selbsttest WE1 · Am Markt-Wochenende nie eine Order (07.11.2026, Slave 4 — Vorfall Sa 07.11. 07:18 Dubai: finaler Tradeify Moritz …9823,
Plan 63d32af5, Start von final_halten auf Sa 06:52 geschoben, tfh_tick Hedge „mit" Sa 06:33, Puls klickte bei geschlossenem Markt, kein Fill).

Ohne Netz:
  app.py: cme_wochenende (Grenzen Fr 16:00 CT / So 17:00 CT, Sommer- und Winterzeit), tfh_tick._faellig stellt am Wochenende nicht um.
  Frontend per jsc: cmeWochenende (gleiche Grenzen), suStartetNichtWeil (Wochenende → Grund, werktags unverändert) und faVorStart (Hand-Start
  blockt mit Grund, ohne DB-Abfrage). SQL-Vertrag (sql/2026-11-07_wochenende_kein_start.sql): Funktionen, Patch von final_halten, Claim-Riegel vor
  allen anderen (a00…w < a0…, a_…), Verbrauch-Claims frei, Rückbau.
  (Die Datei lief am 07.11.2026 (Samstag) als DO-Block mit erzwungenem Abbruch gegen Supabase: Fr 21:59Z nein / Fr 22:00Z ja / Sa ja / So 22:59Z ja /
  So 23:00Z nein / Mo nein / Mi nein; nächster Handelstag Sa 06:52 Dubai → Mo 09.11 06:52, Mi bleibt, Fr 16:30 CT → Mo 17:30 CT (aus der Tagespause);
  final_halten gepatcht; Start-Claim am Samstag → Plan planned, kein Claim, start_sperre art wochenende; Verbrauch-Claim gesetzt; danach nichts übrig.)
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_we1_wochenende.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

HTML = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(HIER, "..", "sql", "2026-11-07_wochenende_kein_start.sql"), encoding="utf-8").read()
RUECK = open(os.path.join(HIER, "..", "sql", "2026-11-07_wochenende_kein_start_rueckbau.sql"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


U = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
FAELLE = [  # (UTC, erwartet) — Winter (CST = UTC−6) und Sommer (CDT = UTC−5); ab Fr 15:55 CT (5 min Puffer vor dem Schluss)
    ("2026-11-06T21:54:00Z", False), ("2026-11-06T21:55:00Z", True), ("2026-11-06T22:00:00Z", True), ("2026-11-07T03:18:00Z", True), ("2026-11-08T22:59:00Z", True),
    ("2026-11-08T23:00:00Z", False), ("2026-11-09T03:18:00Z", False), ("2026-11-11T12:00:00Z", False), ("2026-11-11T22:30:00Z", False),
    ("2026-07-10T20:54:00Z", False), ("2026-07-10T20:55:00Z", True), ("2026-07-12T21:59:00Z", True), ("2026-07-12T22:00:00Z", False),
]
for t, soll in FAELLE:
    check(app.cme_wochenende(U(t)) is soll, f"cme_wochenende({t}) = {soll}")
check(app.cme_wochenende(U("2026-11-07T03:18:00Z").timestamp()) is True, "cme_wochenende nimmt auch Unix-Sekunden")

i = app.__file__ and open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
k = i.index("def tfh_tick(")
fa = i[k:i.index("kauf = _ap_kauf_echt(", k)]
check("if cme_wochenende(jetzt) or cme_wochenende(st_):\n            return False" in fa and fa.index("cme_wochenende") < fa.index("return von <= st_ <= bis"),
      "tfh_tick: am Wochenende (jetzt oder Start) nie auf Hedge „mit“ umstellen, werktags unverändert")


def js_funktion(name, asynch=False):
    i0 = HTML.index(("async " if asynch else "") + f"function {name}(")
    j = HTML.index("{", HTML.index(")", i0))
    t = 0
    for q in range(j, len(HTML)):
        t += {"{": 1, "}": -1}.get(HTML[q], 0)
        if t == 0:
            return HTML[i0:q + 1]


JS = r"""
%s
%s
const aus = { we: {} }
for(const [t, soll] of %s) aus.we[t] = cmeWochenende(Date.parse(t)) === soll
// suStartetNichtWeil: nur die ersten beiden Zeilen (Weg + Wochenende) zählen hier — der Rest ist unverändert
const routeIstOrbit = r => r === 'tvv2' || r === 'tsv2', routeIstEcho = r => r === 'mt5' || r === 'mt5v2', POLAR_AUTO = false
let jetztMs = Date.parse('2026-11-07T03:18:00Z')
const cmeWochenendeEcht = cmeWochenende
cmeWochenende = ms => cmeWochenendeEcht(ms == null ? jetztMs : ms)
const tpIstFarmerPlan = () => false, tpKetteNr = () => 0, tpIstWdPlan = () => false, tsPulsModus = () => 'scharf', tpLotsDeckelFehlt = () => false
const suUnbestaetigt = () => false, tpWdWartetAufBestaetigung = () => false, planKontoDeaktiviert = () => false
%s
aus.sa = suStartetNichtWeil({ route: 'tvv2' }, true)
jetztMs = Date.parse('2026-11-09T07:00:00Z')
let werktag = null; try{ werktag = suStartetNichtWeil({ route: 'tvv2' }, true) }catch(e){ werktag = 'weiter:' + e.message }
aus.mo = werktag
// faVorStart am Samstag: Grund, Toast, keine RPC
jetztMs = Date.parse('2026-11-07T03:18:00Z')
let rpc = 0; const supabase = { rpc: () => { rpc++; return Promise.resolve({ data: { frei: true } }) } }, TOASTS = []
const atToast = t => TOASTS.push(t), tradePlans = [], renderTradePlans = () => {}, _faFrei = new Map(), console = { warn(){} }
%s
faVorStart({ id: 'p1', masterName: '150k …9823' }).then(t => { aus.hand = t; aus.toast = TOASTS[0]; aus.rpc = rpc; print(JSON.stringify(aus)) })
"""
if not os.path.exists(JSC):
    check(False, "jsc fehlt")
else:
    i1 = HTML.index("const WOCHENENDE_GRUND = ")
    konst = HTML[i1:HTML.index("\n", i1)]
    js = JS % (js_funktion("cmeWochenende").replace("function cmeWochenende(", "var cmeWochenende = function("), konst,
               json.dumps([[t, s] for t, s in FAELLE]), js_funktion("suStartetNichtWeil"), js_funktion("faVorStart", True))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    try:
        a = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        a = None
        check(False, "jsc: " + (r.stdout + r.stderr)[-600:])
    if a:
        check(all(a["we"].values()), f"cmeWochenende im Tab = gleiche Grenzen wie Railway ({sum(a['we'].values())}/{len(a['we'])})")
        check(str(a["sa"]).startswith("Markt-Wochenende"), f"suStartetNichtWeil Samstag → {a['sa']}")
        check(a["mo"] != a["sa"] and not str(a["mo"] or "").startswith("Markt-Wochenende"), f"suStartetNichtWeil Montag → weiter wie bisher ({a['mo']})")
        check(str(a["hand"]).endswith("kein Start, der Plan bleibt geplant") and a["toast"].startswith("⏳") and a["rpc"] == 0, "faVorStart Samstag: Hand-Start blockt mit Grund, ohne RPC")
i2 = HTML.index("function suStartetNichtWeil(")
su = HTML[i2:HTML.index("\n  }\n", i2)]
check(su.index("if(cmeWochenende()) return WOCHENENDE_GRUND") < su.index("Polar manuell"), "Tab: Wochenend-Grund ganz vorn in suStartetNichtWeil")

# SQL-Vertrag
check("create or replace function public.prophos_markt_wochenende(p_t timestamptz)" in SQL and "when 5 then (p_t at time zone 'America/Chicago')::time >= time '15:55'" in SQL
      and "when 7 then (p_t at time zone 'America/Chicago')::time <  time '17:00'" in SQL, "SQL: Wochenende Fr 15:55 (Puffer) – So 17:00 CT")
check("while public.prophos_markt_wochenende(t) and i < 4 loop" in SQL and "t := t + interval '1 day';" in SQL and "t := t + interval '1 hour';" in SQL,
      "SQL: nächster Handelstag, gleiche Uhrzeit, aus der Tagespause heraus")
check("ziel := public.prophos_naechster_handelstag(ziel);   -- WE1" in SQL and "raise exception 'final_halten: Stelle" in SQL and "schon gepatcht" in SQL,
      "SQL: final_halten per Textersatz gepatcht, wiederholbar, bricht bei geändertem Live-Text ab")
check("coalesce(new.start_claim_art, '') = 'verbrauch'" in SQL and "return null;" in SQL and "'art', 'wochenende'" in SQL, "SQL: Claim-Riegel blockt Starts, Verbrauch frei, Marke wochenende")
namen = sorted(["trade_plans_a00_wochenende", "trade_plans_a00_konto_deaktiviert", "trade_plans_a0_hedge_freigabe", "trade_plans_a0_lots_deckel",
                "trade_plans_a1_apex_hedge", "trade_plans_a1_echo_hedge", "trade_plans_a_final_halten", "trade_plans_big_trade"])
check(namen.index("trade_plans_a00_wochenende") < namen.index("trade_plans_a_final_halten") and namen.index("trade_plans_a00_wochenende") < namen.index("trade_plans_a0_hedge_freigabe"),
      "SQL: Wochenend-Riegel läuft vor final_halten und den Hedge-Riegeln (Postgres: Trigger alphabetisch; konto_deaktiviert davor, blockt ebenfalls)")
for fn in ("async function tpPreflightMt5V2(plan){", "async function tpPreflightMt5(plan){"):
    j0 = HTML.index(fn)
    kopf = HTML[j0:j0 + 1400]
    check("if(cmeWochenende()){" in kopf and "_pfRemoteMelde(plan.id, { ok:false, msg: t })" in kopf and kopf.index("cmeWochenende") < (kopf.find("tpLotsDeckelFrisch") if "tpLotsDeckelFrisch" in kopf else kopf.index("_pfMt5StopTimer")),
          f"Echo-Fernstart: {fn.split('(')[0].split()[-1]} sperrt am Wochenende ganz vorn und meldet ans Handy")
check("if(s.art === 'wochenende') return { kurz: '⏳ Markt-Wochenende — kein Start'" in HTML and "|| s.art === 'wochenende') ||" in HTML, "Karten-Chip kennt die Sperre „wochenende“")
check(RUECK.lstrip().split("\n")[0].startswith("--") and "\nbegin;\n" in RUECK and RUECK.rstrip().endswith("commit;") and "Rückbau abgebrochen" in RUECK, "Rückbau in einer Transaktion, bricht ab statt halb zu löschen")
check("drop trigger if exists trade_plans_a00_wochenende" in RUECK and "execute replace(def, zeile, '')" in RUECK and "drop function if exists public.prophos_markt_wochenende" in RUECK,
      "Rückbau vollständig")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
    sys.exit(1)
print("alle Prüfungen bestanden")
