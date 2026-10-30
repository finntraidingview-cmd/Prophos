#!/usr/bin/env python3
"""Selbsttest MINDESTTAGE FTMO (prophos.html kontoMindesttage + app.py ap_konto_rechnen tage=, 30.10.2026 — Finn: „Bei FTMO gibt's ab jetzt auch 4, in Phase 1 4
und in Phase 2 4"). Aufruf:  python3 tools/selftest_mindesttage_ftmo.py   (ohne Netz; Firmenregel läuft echt in JavaScriptCore, Planer per Quelltext-Lader).
Geprüft: FTMO P1/P2 = 4, FundedNext unverändert 5, FTMO Futures und Funded ohne; am Planer: FTMO-Mini mit ganzen Lots (1 Lot, 20–40 Pkt), ohne goal_kind wie heute."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(HIER, "..", "sql", "2026-10-30_ftmo_mindesttage.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# ── Firmenregel echt: Konstanten + kontoMindesttage + tpFirmIstFutures aus dem Quelltext ──
regel = html[html.index("const MINDESTTAGE_JE_FIRMA"):html.index("function tpFirmIstCfd(")]
fut = html[html.index("function tpFirmIstFutures("):html.index("// Nova-Anzeige (27.10.2026)")]
FAELLE = [("FTMO", "phase1", ("trading_days", 4)), ("FTMO", "phase2", ("trading_days", 4)), ("ftmo", "phase1", ("trading_days", 4)), (" FTMO ", "phase2", ("trading_days", 4)),
          ("FundedNext", "phase1", ("trading_days", 5)), ("FundedNext", "phase2", ("trading_days", 5)),
          ("FTMO Futures", "challenge", None), ("FTMO Futures", "phase1", None), ("FundedNext Futures", "phase1", None),
          ("FTMO", "funded", None), ("FTMO", "funded_cfd", None), ("FTMO", "challenge", None), ("FundingPips", "phase1", None), ("The5%ers", "phase1", None)]
js = ("const istTradeifyCfd = () => false, getCustomFirms = () => [];\n" + fut + "\n" + regel
      + "\nconst F = " + json.dumps([f[:2] for f in FAELLE]) + "; print(JSON.stringify(F.map(f => kontoMindesttage(f[0], f[1])).concat([kontoMindesttage('Blue Guardian', 'phase1')])));")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:200]})")
erg = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else [None] * (len(FAELLE) + 1)
for (firma, typ, soll), ist in zip(FAELLE, erg):
    check((ist["kind"], ist["target"]) == soll if soll else ist is None, f"{firma!r} {typ} → {soll or 'keine Mindesttage'} (ist {ist})")
check(erg[-1] == {"kind": "winning_days", "target": 3, "minProfit": 500}, "Blue Guardian bleibt Gewinntage 3 × 500 $")

# ── Planer: Wirkung mit und ohne goal_kind, FTMO-Regel wie sql/2026-10-08_ftmo_kernwerte.sql ──
import selftest_auto_delta as sd  # noqa: E402
FTMO = {"namen": ["ftmo"], "route": "mt5v2", "groessen": [100000, 200000], "ziel_pct": {"phase1": 10, "phase2": 5}, "planen": True,
        "phasen": {"phase1": {"sl": [2300, 2750], "tp": [5000, 8000], "menge": [25, 35], "menge_schritt": 1, "puffer": [75, 75], "ziel_pct": 10, "boden_pct": 10},
                   "phase2": {"sl": [2300, 2750], "tp": [3500, 4500], "menge": [20, 30], "menge_schritt": 1, "puffer": [50, 50], "ziel_pct": 5, "boden_pct": 10}}}
U = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
a = sd.lade()
R, ist_tage = a["ap_konto_rechnen"], a["ap_tage_ist"]
w, g = R(FTMO, "phase1", 110420.0, U, ppl=1.0, tage=(2, 4))
tm = (w or {}).get("tage_mini") or {}
check(w and w["menge"] == 1 and tm.get("soll") == 4 and 20 <= tm.get("sl_pkt", 0) <= 40 and 20 <= w["sl"] <= 40 and tm.get("sofort_zu") is True, f"Ziel erreicht, 2/4 Tage → Mini 1 Lot, SL 20–40 $ ({g or w})")
w, g = R(FTMO, "phase1", 110420.0, U, ppl=1.0, tage=(4, 4))
check(w is None and "Ziel erreicht" in (g or ""), f"Ziel erreicht, 4/4 Tage → kein Plan ({g})")
w, g = R(FTMO, "phase1", 110420.0, U, ppl=1.0, tage=None)
check(w is None and "Ziel erreicht" in (g or ""), f"ohne goal_kind wie heute: kein Plan ({g})")
w, g = R(FTMO, "phase1", 110010.0, U, ppl=1.0, tage=(2, 4))
check(w is None and "von Hand" in (g or ""), f"zu wenig Luft über dem Ziel → Grund statt Plan ({g})")
w, g = R(FTMO, "phase1", 102000.0, U, ppl=1.0, tage=(2, 4))
check(w and not w.get("tage_mini"), f"unter dem Ziel mit fehlenden Tagen: normaler Trade, kein Mini ({g or (w or {}).get('stufe')})")
konto = {"id": "k", "goal_kind": "trading_days", "goal_target": 4, "goal_done_offset": 1, "goal_since": "2026-10-30"}
plaene = [{"master_account_id": "k", "started_at": "2026-10-30T10:00:00+00:00"}, {"master_account_id": "k", "started_at": "2026-10-30T11:00:00+00:00"},
          {"master_account_id": "k", "started_at": "2026-10-29T11:00:00+00:00"}, {"master_account_id": "x", "started_at": "2026-10-31T11:00:00+00:00"}]
check(ist_tage(konto, plaene) == (2, 4), f"Zähler n/4: Offset + Tage ab goal_since ({ist_tage(konto, plaene)})")
check(ist_tage({"id": "k"}, plaene) is None, "ohne goal_kind zählt der Planer nichts")

# ── SQL: Teil 3 (Ziel erreicht) bleibt auskommentiert, Bestand idempotent, Futures draußen ──
aktiv = "\n".join(z for z in sql.splitlines() if not z.lstrip().startswith("--"))
check(aktiv.count("update ") == 2 and "a.ziel_erreicht_at is null" in aktiv and "ziel_erreicht_at is not null" not in aktiv, "aktiv nur Vorlagen + Bestand ohne Ziel-Markierung")
check(aktiv.count("goal_kind is null") == 2 and aktiv.count("lower(trim(") == 2 and "ilike" not in aktiv and "goal_target = 4" in aktiv and "goal_target = 5" not in aktiv, "idempotent, ohne FTMO Futures, Ziel 4")
# ── Formular: bestehende FTMO-Konten nur über SQL, Vorbelegung geht zurück, wenn die Firma sich ändert ──
ac = html[html.index("function acMindesttage("):html.index("function tpFirmIstCfd(")]
check("_editingAccountId" in ac and "editAccount" not in ac and "=== 'ftmo'" in ac, "Speichern im Formular setzt bei bestehendem FTMO-Konto keine Tage")
check("acMindesttage(firm, type) : null" in html and "const mt = acMindesttage(firm, typ)" in html, "Formular nutzt acMindesttage")
check("_acZielAusRegel = null\n    if(istPhase" in html, "Vorbelegung wird vor jeder neuen Prüfung zurückgenommen")
print("\n" + (f"✗ {len(FEHLER)} Fehler" if FEHLER else "✓ alles grün"))
sys.exit(1 if FEHLER else 0)
