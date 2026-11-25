#!/usr/bin/env python3
"""Selbsttest T5C (Finn 25.11.2026): The5%ers High Stakes 2-Step „New" (Phase 1 8 %, wie bisher) und „Classic" (Phase 1 10 %, Phase 2 5 %, Funded gleich).
Erkennung je Konto über den Namen (Add-on „ · Classic"), ohne = New. Geprüft mit echtem app.py-Code (ohne Netz): ap_konto_variante, ap_regel_konto (Planer,
Ziel-Wache, Konten-Stand), zw_ziel (110k statt 108k), ap_konto_rechnen (kein „Ziel erreicht" bei 108,5k Classic), Kontowert (Classic-Kauf 200k 245 €,
100k offen = Firmen-Kauf), Konto-Wert ziel_pct_konto geht weiter vor; Frontend (kontoVorlageZusatz / Mehrdeutigkeit in JavaScriptCore) und SQL.
Aufruf: python3 tools/selftest_t5c_the5ers_classic.py"""
import copy
import os
import random
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


# Regel The5%ers wie auto_plan_regeln id 1 (Stand 25.11.2026) + varianten aus sql/2026-11-25_t5c_the5ers_classic.sql
PH = lambda z: {"sl": [1800, 2160], "tp": [5400, 6300], "menge": [20, 30], "puffer": [25, 50], "ziel_pct": z, "boden_pct": 10, "menge_schritt": 1}
PH2 = lambda z: {"sl": [3600, 4320], "tp": [10800, 12600], "menge": [50, 60], "puffer": [110, 150], "ziel_pct": z, "boden_pct": 10, "menge_schritt": 1}
T5 = {"boden": "statisch", "namen": ["the5ers"], "route": "mt5v2", "dd_pct": 10, "phasen": {"phase1": PH(8), "phase2": PH(5)}, "groessen": [100000, 200000],
      "kauf_eur": {"100000": 146, "200000": 226}, "skaliert": True, "ziel_pct": {"phase1": 8, "phase2": 5},
      "je_groesse": {"200000": {"phasen": {"phase1": PH2(8), "phase2": PH2(5)}}},
      "varianten": {"classic": {"ziel_pct": {"phase1": 10, "phase2": 5}, "kauf_eur": {"200000": 245}}}}
T5_ALT = {k: v for k, v in T5.items() if k != "varianten"}
K = lambda name, typ="phase1", **o: dict({"id": "k", "name": name, "firm": "The5%ers", "account_type": typ}, **o)
CL1, NEW1 = K("100k 26999999 → Phase 1 · Classic"), K("100k 26962175 → Phase 1")

print("1) Erkennung über den Namen")
V = app.ap_konto_variante
check(V(T5, CL1) == "classic" and V(T5, K("200k 1 → Phase 1 · 1% Rule · CLASSIC")) == "classic" and V(T5, K("100k 1 Classic")) == "classic",
      "„ · Classic“ (auch groß, nach anderen Add-ons, ohne Punkt) → classic")
check(V(T5, NEW1) is None and V(T5, K("100k 1 → Phase 1 · Classical")) is None and V(T5, K("100k Neoclassic")) is None and V(T5, {}) is None,
      "ohne Wort (auch nicht „Classical“/„Neoclassic“) → None = New")
check(V(T5_ALT, CL1) is None and app.ap_regel_variante(T5_ALT, CL1) is T5_ALT and app.ap_regel_variante(T5, NEW1) is T5,
      "ohne varianten / ohne Classic: Regel unverändert (dasselbe Objekt, bitgleich)")

print("2) Regel je Konto (ap_regel_konto) + Ziel (zw_ziel)")
rc, rn = app.ap_regel_konto(copy.deepcopy(T5), CL1, 100000.0), app.ap_regel_konto(copy.deepcopy(T5), NEW1, 100000.0)
check(rc["ziel_pct"] == {"phase1": 10.0, "phase2": 5.0} and rc["phasen"]["phase1"]["ziel_pct"] == 10.0 and rc["je_groesse"]["200000"]["phasen"]["phase1"]["ziel_pct"] == 10.0
      and rc.get("variante") == "classic", "Classic: Phase 1 10 % (Firma, phasen, Größen-Block 200k), Phase 2 5 %")
check(rn["ziel_pct"] == {"phase1": 8, "phase2": 5} and "variante" not in rn, "New: Phase 1 8 % wie bisher")
check(rc["kauf_eur"] == {"100000": 146, "200000": 245} and rn["kauf_eur"] == {"100000": 146, "200000": 226},
      "Kauf: Classic 200k 245 €, 100k offen → Firmen-Kauf 146 €; New unverändert")
z = lambda r, ph, b: app.zw_ziel(r, ph, b)
check(z(rc, "phase1", 100000.0)[0] == 110000.0 and z(rn, "phase1", 100000.0)[0] == 108000.0, "Ziel 100k: Classic 110.000, New 108.000")
rc2 = app.ap_regel_konto(copy.deepcopy(T5), K("200k 2 → Phase 1 · Classic"), 200000.0)
check(z(rc2, "phase1", 200000.0)[0] == 220000.0 and z(app.ap_regel_konto(copy.deepcopy(T5), K("200k 2 → Phase 1"), 200000.0), "phase1", 200000.0)[0] == 216000.0,
      "Ziel 200k: Classic 220.000, New 216.000")
check(z(app.ap_regel_konto(copy.deepcopy(T5), K("100k 3 → Phase 2 · Classic", "phase2"), 100000.0), "phase2", 100000.0)[0] == 105000.0,
      "Phase 2 Classic: 105.000 (5 %, gleich wie New)")
rk = app.ap_regel_konto(copy.deepcopy(T5), dict(CL1, ziel_pct_konto={"phase1": 9}), 100000.0)
check(z(rk, "phase1", 100000.0)[0] == 109000.0, "accounts.ziel_pct_konto geht weiter vor (9 % → 109.000)")

print("3) Planer (ap_konto_rechnen)")
u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
wc, gc = app.ap_konto_rechnen(rc, "phase1", 108500.0, u, ppl=1.0)
wn, gn = app.ap_konto_rechnen(rn, "phase1", 108500.0, u, ppl=1.0)
check(wc is not None and abs(float(wc.get("ziel")) - 110000.0) < 0.01 and abs(float(wc.get("rest")) - 1500.0) < 0.01, f"Classic bei 108.500: weiter planen, Rest 1.500 ({gc or wc.get('stufe')})")
check(wn is None and "Ziel erreicht" in str(gn), f"New bei 108.500: Ziel erreicht wie bisher ({gn})")
w1, _ = app.ap_konto_rechnen(rc, "phase1", 100000.0, u, ppl=1.0)
check(w1 and str(w1.get("stufe", "")).startswith("Etappe") and abs(float(w1.get("ziel")) - 110000.0) < 0.01, f"Classic Start 100k: Etappe (TP {w1 and w1.get('tp')}), Ziel 110.000")

print("4) Kontowert / Echo-Hedge")
kc = app.ap_kontowert_konto(K("200k 2 → Phase 1 · Classic"), 200000.0, [copy.deepcopy(T5)])
kn = app.ap_kontowert_konto(K("200k 2 → Phase 1"), 200000.0, [copy.deepcopy(T5)])
check(kc.get("kauf_eur") == 245 and kn.get("kauf_eur") == 226, f"Kontowert-Kauf 200k: Classic 245 €, New 226 € ({kc.get('kauf_eur')}/{kn.get('kauf_eur')})")
check(kc.get("wert_eur") and kn.get("wert_eur") and kc["wert_eur"] != kn["wert_eur"], f"Kontowert Classic {kc.get('wert_eur')} € vs. New {kn.get('wert_eur')} €")
SRC = open(os.path.join(WURZEL, "app" + ".py"), encoding="utf-8").read()
check("regel = ap_regel_variante(regel, konto)        # T5C" in SRC and 'ap_regel_variante(_hb_r, acc or {"name": p.get("master_name")})' in SRC,
      "Planer/Ziel-Wache/Konten-Stand (ap_regel_konto), Kontowert (ap_kw_regel_konto) und Hypo-Bilanz nutzen die Variante")

print("5) Frontend (JavaScriptCore)")
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
def fn(name):
    i = HTML.index(f"function {name}(")
    j = HTML.index("\n  }\n", i)
    return HTML[i:j + 4]
js = fn("kontoVorlageZusatz") + fn("kontoVorlagenMehrdeutig") + r"""
const L = [
  {name: 'The5%ers 100k New Phase 1', firm: 'The5%ers', account_type: 'phase1', account_size: 100000, purchase_cost: 142, max_drawdown: 10000, max_daily_drawdown: 3000},
  {name: 'The5%ers 100k Classic Phase 1', firm: 'The5%ers', account_type: 'phase1', account_size: 100000, purchase_cost: null, max_drawdown: 10000, max_daily_drawdown: 3000},
  {name: 'The5%ers 100k New Phase 2', firm: 'The5%ers', account_type: 'phase2', account_size: 100000, purchase_cost: null, max_drawdown: 10000, max_daily_drawdown: 3000},
  {name: 'The5%ers 100k Classic Phase 2', firm: 'The5%ers', account_type: 'phase2', account_size: 100000, purchase_cost: null, max_drawdown: 10000, max_daily_drawdown: 3000},
  {name: 'Blue Guardian 100k Standard Phase 1', firm: 'Blue Guardian', account_type: 'phase1', account_size: 100000, purchase_cost: 300, max_drawdown: 8000},
  {name: 'Blue Guardian 100k Nano Phase 1', firm: 'Blue Guardian', account_type: 'phase1', account_size: 100000, purchase_cost: 116, max_drawdown: 10000}]
const r = []
r.push(kontoVorlageZusatz(L[1]) === 'Classic' && kontoVorlageZusatz(L[0]) === '' && kontoVorlageZusatz({name: 'X Classical'}) === '' && kontoVorlageZusatz(null) === '')
r.push(JSON.stringify(kontoVorlagenMehrdeutig({firma: 'The5%ers', groesse: 100, typ: 'phase1'}, L)) === JSON.stringify(['The5%ers 100k New Phase 1', 'The5%ers 100k Classic Phase 1']))
r.push(kontoVorlagenMehrdeutig({firma: 'The5%ers', groesse: 100, typ: 'phase2'}, L) === null)
r.push(Array.isArray(kontoVorlagenMehrdeutig({firma: 'Blue Guardian', groesse: 100, typ: 'phase1'}, L)))
print(r.join(','))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(js)
out = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", f.name], capture_output=True, text=True).stdout.strip()
os.unlink(f.name)
r = out.split(",")
check(len(r) == 4 and r[0] == "true", f"kontoVorlageZusatz: Classic-Schablone → „Classic“, sonst '' ({out})")
check(len(r) == 4 and r[1] == "true", "Phase 1: New und Classic mehrdeutig → Modal (ein Mensch wählt 8 % / 10 %)")
check(len(r) == 4 and r[2] == "true", "Phase 2: gleiche Werte → nicht mehrdeutig (Ein-Klick bleibt)")
check(len(r) == 4 and r[3] == "true", "Blue Guardian Standard/Nano weiter mehrdeutig (BG1)")
# Prüfer-Stopp S2 (25.11.2026): der T5C-Kommentar stand mitten im acc-Literal von kontoDirektAnlegen → type/externalId/purchaseCost auskommentiert,
# Ein-Klick „Bestätigen" 400 für jede Firma. Das echte Literal aus prophos.html in JavaScriptCore auswerten.
i0 = HTML.index("    const acc = { name: kontoNameRegel(gr + 'k', z.ext, z.typ, kontoVorlageZusatz(v))")
lit = HTML[i0:HTML.index("\n    let d = null", i0)]
js2 = fn("kontoVorlageZusatz") + r"""
const kontoNameRegel = (g, e, t, zs) => g + ' ' + e + ' → ' + t + (zs ? ' · ' + zs : '')
const zahl = x => x != null && isFinite(Number(x)) && Number(x) > 0 ? Number(x) : null
const gr = 200, z = {ext: '26999999', firma: 'The5%ers', typ: 'phase1'}
const v = {name: 'The5%ers 200k Classic Phase 1', purchase_cost: 245, max_drawdown: 20000, goal_kind: null}
""" + lit + r"""
print(JSON.stringify([acc.name, acc.firm, acc.type, acc.externalId, acc.purchaseCost, acc.maxDrawdown, acc.autoPlaner]))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(js2)
out2 = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", f.name], capture_output=True, text=True)
os.unlink(f.name)
check(out2.stdout.strip() == '["200k 26999999 → phase1 · Classic","The5%ers","phase1","26999999",245,20000,true]',
      f"Ein-Klick-Anlegen: acc hat name (mit „ · Classic“), firm, type, externalId, purchaseCost, maxDrawdown ({out2.stdout.strip() or out2.stderr.strip()[:120]})")
check(not re.search(r"//[^\n]*\b(type|externalId|purchaseCost): ", HTML[i0:i0 + 600]), "kein Kommentar vor Feldern im acc-Literal")
# Finn (25.11.): Schablonen nur Phase 1 — Phase 2/Funded über den Nachfolger-Assistenten (sucNameVorschlag → kontoNameBauen); „ · Classic" muss mit
i1 = HTML.index("const SUC_PHASE_LABEL = ")
js3 = HTML[i1:HTML.index("\n", i1)] + "\n" + fn("kontoNameRegel") + fn("kontoNameTeile") + fn("kontoNameBauen") + r"""
const p2 = kontoNameBauen('100k 26999999 → Phase 1 · Classic', 'phase2', '27000001')
const f = kontoNameBauen(p2, 'funded_cfd', '27100002')
const n = kontoNameBauen('200k 26962573 → Phase 1', 'phase2', '27000003')
const m = kontoNameBauen('100k 1 → Phase 1 · 1% Rule · Classic', 'phase2', '2')
print(JSON.stringify([p2, f, n, m]))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(js3)
out3 = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", f.name], capture_output=True, text=True)
os.unlink(f.name)
check(out3.stdout.strip() == '["100k 27000001 → Phase 2 · Classic","100k 27100002 → Funded · Classic","200k 27000003 → Phase 2","100k 2 → Phase 2 · 1% Rule · Classic"]',
      f"Nachfolger-Assistent trägt „ · Classic“ weiter: Phase 1 → Phase 2 → Funded; New bleibt ohne ({out3.stdout.strip() or out3.stderr.strip()[:120]})")
check(V(T5, K("100k 27100002 → Funded · Classic", "funded_cfd")) == "classic"
      and z(app.ap_regel_konto(copy.deepcopy(T5), K("100k 27000001 → Phase 2 · Classic", "phase2"), 100000.0), "phase2", 100000.0)[0] == 105000.0,
      "Nachfolger-Namen werden als Classic erkannt; Phase 2 Ziel 105.000")
check("kontoNameRegel(gr + 'k', z.ext, z.typ, kontoVorlageZusatz(v))" in HTML and "window._kontoVorlageZusatz(v)) || '')" in HTML
      and "E.zusatz.value = kontoVorlageZusatz(v)" in HTML, "Ein-Klick, Bulk und Modal setzen das Add-on „Classic“ aus der Schablone")

print("6) SQL")
SQL = open(os.path.join(WURZEL, "sql", "2026-11-25_t5c_the5ers_classic.sql"), encoding="utf-8").read()
check(SQL.count("enable row level security") == 2 and "revoke all on t5c_auto_plan_regeln_20261125" in SQL and "revoke all on t5c_bulk_vorlagen_20261125" in SQL,
      "Sicherung (Regel + Schablonen) mit RLS + revoke")
check('\'{"classic": {"ziel_pct": {"phase1": 10, "phase2": 5}, "kauf_eur": {"200000": 245}}}\'::jsonb' in SQL, "Regel: varianten.classic 10/5 %, Kauf 200k 245 €")
check("'The5%ers 100k New Phase 1'" in SQL and "'The5%ers 200k New Phase 1'" in SQL and "delete from public.bulk_vorlagen" not in SQL.split("commit;")[0],
      "bestehende Schablonen → New (umbenannt, nicht gelöscht)")
neu = re.findall(r"\('The5%ers (\d+k) (New|Classic) (Phase 1|Phase 2|Funded)'", SQL)
check(sorted(neu) == [("100k", "Classic", "Phase 1"), ("200k", "Classic", "Phase 1")] and "funded_cfd" not in SQL and "'phase2'" not in SQL,
      f"nur 2 neue Schablonen: Classic Phase 1 je 100k/200k (Finn: Schablonen nur Phase 1) ({neu})")
check("'The5%ers 200k Classic Phase 1',    'phase1',     200000,          245" in SQL and "'The5%ers 100k Classic Phase 1',    'phase1',     100000::numeric, null" in SQL,
      "Kaufpreis Classic 200k 245 €, 100k offen")
check("where not exists (select 1 from public.bulk_vorlagen b where b.name = v.name)" in SQL, "idempotent (Name ist unique)")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
