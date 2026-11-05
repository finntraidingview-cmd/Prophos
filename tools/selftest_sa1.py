#!/usr/bin/env python3
"""Selbsttest SA1 (05.11.2026, offene Prüfer-Hinweise aus berichte/2026-11-05_NK1.md (c)). Je Punkt ein Block; ohne Netz.
Aufruf: python3 tools/selftest_sa1.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


def block(name, n=2500):
    i = HTML.find(name)
    return HTML[i:i + n] if i >= 0 else ""


# ── #1 Claim-Guard auf die Startzeit der Kopie ──
f = block("  async function suClaimSetzen(planId, art, guard, startUm){", 900)
ok("if(startUm !== undefined) q = startUm ? q.eq('start_um', startUm) : q.is('start_um', null)" in f,
   "#1 suClaimSetzen: mit startUm nur genau diese Startzeit (null → start_um is null)")
for marke in ("'verbrauch' : 'start', true, plan.startUm || null)",                       # Start / verpasst nach Fenster
              "'verbrauch', true, plan.startUm || null)   // Verbrauch: verpasst",          # verpasst nach Vorprüfung
              "'verbrauch', false, plan.startUm || null)   // Verbrauch: nie in der Pause",  # Index-Pause aufgegeben
              "'verbrauch', false, plan.startUm || null)   // Verbrauch: Riegel hat aufgegeben"):
    ok(marke in HTML, f"#1 zeitabhängiger Claim mit Startzeit: {marke[:48]}…")
for marke in ("'verbrauch', false)   // Verbrauch: nie starten", "'verbrauch', false)   // Verbrauch: Manuelle Arbeit",
              "'verbrauch', false)   // Verbrauch: Ziel erreicht"):
    ok(marke in HTML, f"#1 Verbrauch ohne Uhrzeit-Bezug bleibt ohne Zeit-Guard: {marke[22:58]}…")
ok(len(re.findall(r"suClaimSetzen\(", HTML)) == 8, "#1 genau 7 Aufrufer + Definition (kein neuer Claim-Weg ohne Entscheidung)")

# ── #4 WD: Payout offen beim Anlegen nur aus der frischen Zeile + Server-Prüfung ──
i = HTML.find("async function wdPlaeneAnlegen(")
blk = HTML[i:HTML.find("// 2) Ein Aufruf", i)]
ok("if(k.hinweis === WD_HINWEIS_PAYOUT){ k.aktiv = false; delete k.nach_start; ge = true; continue }" in blk
   and "wdKontoPayoutOffen(" not in blk and "_wd.payoutOffen" not in blk, "#4 wdPlaeneAnlegen: nur Zeilen-Hinweis, kein alter Mac-/PC-Stand")
APP = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
j = APP.find("# PAYOUT OFFEN (R2c, 05.11.2026")
ok(j > 0 and 'if mid in po_offen:' in APP[j:j + 4000] and '"grund": WD_HINWEIS_PAYOUT' in APP[j:j + 4000],
   "#4 POST /admin/wd-plaene prüft pending_payouts frisch und gibt WD_HINWEIS_PAYOUT als Grund zurück")
ok("if(rein && wdKontoPayoutOffen(k)) return wdSay(" in HTML, "#4 Hand-Weg „heute rein“ behält die strenge Prüfung (sicher in die richtige Richtung)")

# ── #5 Patch-Route: on_demand.* nur für FundedNext ──
import app  # noqa: E402
FIRMEN = [{"name": "FundedNext", "namen": ["fundednext"], "je_groesse": {"100000": {"ziel": [5000, 5500]}}},
          {"name": "FTMO", "namen": ["ftmo"], "je_groesse": {"100000": {"ziel": [5000, 5500]}},
           "on_demand": {"consistency_pct": 30}}]               # Alt-Override zum Aufräumen
Z = {"id": 1, "firmen": FIRMEN}
u, f = app.fcp_regel_patch(Z, {"firma": "FundedNext", "feld": "on_demand.consistency_pct", "wert": 35})
ok(f is None and u["firmen"][0]["on_demand"] == {"consistency_pct": 35}, "#5 FundedNext: on_demand.consistency_pct setzbar")
for feld, wert in (("on_demand.consistency_pct", 35), ("on_demand.ziel_je_100k", [2000, 2200])):
    u, f = app.fcp_regel_patch(Z, {"firma": "FTMO", "feld": feld, "wert": wert})
    ok(u is None and f == "On Demand gibt es nur bei FundedNext", f"#5 FTMO: {feld} setzen → abgelehnt ({f})")
u, f = app.fcp_regel_patch(Z, {"firma": "FTMO", "feld": "on_demand.consistency_pct", "wert": None})
ok(f is None and "on_demand" not in u["firmen"][1], "#5 FTMO: alten Override leeren bleibt erlaubt")
ok(list(app.FCP_ON_DEMAND_STANDARD) == ["fundednext"], "#5 On Demand gibt es heute nur bei FundedNext (FCP_ON_DEMAND_STANDARD)")

# ── #6 sl_1pct nur bei FundedNext (Planer + Patch), SQL leert FTMO ──
JG = {"ziel": [5000, 5000], "sl": [1750, 1750], "sl_1pct": [700, 700], "lots": [10, 10], "hedge_eur": 1500, "dd": 10000}
FN = {"name": "FundedNext", "namen": ["fundednext"], "je_groesse": {"100000": dict(JG)}}
FT = {"name": "FTMO", "namen": ["ftmo"], "je_groesse": {"100000": dict(JG)}}


def sl_von(regel, eins):
    r = app.fcp_konto_rechnen(dict(JG), 100000.0, 100000.0, 2, eins, 1.0, 1.0, None, regel)
    return r.get("sl")


ok(sl_von(FN, True) == 700 and sl_von(FN, False) == 1750, f"#6 FundedNext: 1-%-Konto → sl_1pct, sonst SL ({sl_von(FN, True)}/{sl_von(FN, False)})")
ok(sl_von(FT, True) == 1750, f"#6 FTMO: sl_1pct (unsichtbar) wird nie genommen ({sl_von(FT, True)})")
ok(sl_von(None, True) == 700, "#6 ohne Regel (alte Aufrufe) wie bisher: kleinerer SL")
r = app.fcp_konto_rechnen(dict(JG), 100000.0, 100000.0, 2, True, 1.0, 1.0, None, FT, max_sl=1000)
ok(r.get("sl") == 1000, f"#6 FTMO mit max_risiko_trade: Deckel greift weiter ({r.get('sl')})")
Z6 = {"id": 1, "firmen": [FN, FT]}
u, f = app.fcp_regel_patch(Z6, {"firma": "FTMO", "groesse": 100000, "feld": "sl_1pct", "wert": [600, 700]})
ok(u is None and "nur bei FundedNext" in str(f), f"#6 Patch: sl_1pct bei FTMO setzen → abgelehnt ({f})")
u, f = app.fcp_regel_patch(Z6, {"firma": "FTMO", "groesse": 100000, "feld": "sl_1pct", "wert": None})
ok(f is None and "sl_1pct" not in u["firmen"][1]["je_groesse"]["100000"], "#6 Patch: sl_1pct bei FTMO leeren erlaubt")
u, f = app.fcp_regel_patch(Z6, {"firma": "FundedNext", "groesse": 100000, "feld": "sl_1pct", "wert": [650, 750]})
ok(f is None and u["firmen"][0]["je_groesse"]["100000"]["sl_1pct"] == [650, 750], "#6 Patch: sl_1pct bei FundedNext setzbar")
SQL6 = open(os.path.join(WURZEL, "sql", "2026-11-05_sa1_ftmo_sl_1pct_leeren.sql"), encoding="utf-8").read()
ok("f->'namen'->>0 = 'ftmo'" in SQL6 and "g.value - 'sl_1pct'" in SQL6 and "NICHT EINGESPIELT" in SQL6 and "RÜCKBAU" in SQL6,
   "#6 SQL: nur FTMO, nur sl_1pct, nicht eingespielt, mit Rückbau")
ok("const einsFirma = String((f.namen || [])[0] || '') === 'fundednext'" in HTML and app.FCP_SL_1PCT_FIRMEN == ("fundednext",),
   "#6 Planer-Firmen = sichtbares Feld in der UI (nur FundedNext)")

# ── #8b waage_ohne schon beim Laden aus den Modellen ──
F_OHNE = [{"name": "Apex", "namen": ["apex"]}, {"name": "Lucid", "namen": ["lucid"]}, {"name": "Tradeify", "namen": ["tradeify"]}]
F_MIT = [{"name": "Apex", "namen": ["apex"]}, {"name": "Lucid", "namen": ["lucid"], "modell": "orbit_prio2"}, {"name": "Tradeify", "namen": ["tradeify"]}]
p0 = app.ap_ausgleich_param({"firmen": F_OHNE})
ok(p0["waage_ohne"] == ["apex"] and p0.get("waage_ohne_modell") == [], f"#8b ohne Prio-2-Firma bitgleich: nur apex ({p0['waage_ohne']})")
p1 = app.ap_ausgleich_param({"firmen": F_MIT})                      # nie gespeichert: ausgleich fehlt ganz
ok("apex" in p1["waage_ohne"] and any("lucid" in k for k in p1["waage_ohne"]) and p1["waage_ohne_modell"],
   f"#8b Prio-2-Firma ohne je gespeichertes Modell: schon beim Laden raus aus der Waage ({p1['waage_ohne']})")
gesp = app.ap_waage_ohne_modell({}, F_MIT)                          # Stand nach dem Speichern des Modells
p2 = app.ap_ausgleich_param({"firmen": F_MIT, "ausgleich": gesp})
ok(p2["waage_ohne"] == gesp["waage_ohne"] and p2["waage_ohne_modell"] == gesp["waage_ohne_modell"], "#8b nach dem Speichern dieselbe Liste (idempotent)")
p3 = app.ap_ausgleich_param({"firmen": F_OHNE, "ausgleich": gesp})  # Modell zurück auf Orbit V2
ok(p3["waage_ohne"] == ["apex"], f"#8b Modell zurückgestellt → Eintrag fällt beim Laden weg ({p3['waage_ohne']})")
hand = {"waage_ohne": ["apex", "topstep"]}
ok(app.ap_ausgleich_param({"firmen": F_MIT, "ausgleich": hand})["waage_ohne"][:2] == ["apex", "topstep"], "#8b Hand-Einträge bleiben")
pg = app.ap_waage_param_gruppe(p1, {}, F_MIT, {})                   # Gruppe ohne eigenes Modell: HT-Prio-2 (nur beim Laden abgeleitet) fällt weg
ok(pg["waage_ohne"] == ["apex"], f"#8b Gruppe: abgeleitete HT-Modell-Einträge werden abgezogen ({pg['waage_ohne']})")

if __name__ == "__main__":
    print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
    sys.exit(1 if FEHLER else 0)
