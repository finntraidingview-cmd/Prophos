#!/usr/bin/env python3
"""Selbsttest GF2 GOAT FUNDED TRADER IM CHALLENGE-AUTO-PLANER (Master 25.11.2026, Finn). Ohne Netz.
Rechnet den Planer (app.py ap_regel_konto + ap_konto_rechnen) mit dem GFT-Eintrag, wie ihn sql/2026-11-25_gf2_gft_autoplaner.sql setzt:
- Gewinntag-Weg wie Blue Guardian: 0/3 und 1/3 → TP 1.000–1.100 $, Big Trade erst ab 2/3;
- das Ziel (Phase 1 10 %, Phase 2 5 %) fällt in keiner Folge von Gewinnen vor dem 3. Gewinntag (u = 0 / 0,5 / 1);
- SL ≤ 2.475 $ und ≤ Tagesgrenze 3 % − 100 $, Lots 2–3, Tagesgrenze 3 % der Tagesstart-Balance;
dazu Text-Prüfung der SQL-Datei und kontoMindesttage (prophos.html) per JavaScriptCore.
Aufruf:  python3 tools/selftest_gf2_gft_autoplaner.py"""
import copy
import os
import re
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


# GFT-Eintrag wie live (auto_plan_regeln id 1, gelesen 25.11.2026) + GF2 (planen, gewinntage)
GFT = {"boden": "statisch", "namen": ["goatfundedtrader", "goatfunded", "gft"], "route": "mt5v2", "dd_pct": 8, "daily_pct": 3,
       "phasen": {"phase1": {"sl": [2070, 2475], "tp": [4500, 7200], "menge": [2, 3], "puffer": [25, 50], "ziel_pct": 10, "boden_pct": 8, "menge_schritt": 0.1},
                  "phase2": {"sl": [2070, 2475], "tp": [3150, 4050], "menge": [2, 3], "puffer": [25, 50], "ziel_pct": 5, "boden_pct": 8, "menge_schritt": 0.1}},
       "planen": True, "groessen": [100000], "kauf_eur": {"100000": 90}, "ziel_pct": {"phase1": 10, "phase2": 5},
       "gewinntage": {"tp": [1000, 1100]}}
PPL = 10.0   # firm_specs „Goat Funded Trader“ NAS100.x, 10 $/Pkt je Lot


def u_(x):
    return {"tp": x, "sl": x, "menge": x, "puffer": x}


def konto(typ="phase1"):
    return {"id": "00000000-0000-0000-0000-0000000000f1", "firm": "Goat Funded Trader", "account_type": typ, "max_drawdown": 8000,
            "goal_kind": "winning_days", "goal_target": 3, "goal_min_profit": 500}


def plan(typ, bal, u, tage):
    k = konto(typ)
    return app.ap_konto_rechnen(app.ap_regel_konto(copy.deepcopy(GFT), k, bal), typ, bal, u, ppl=PPL, tage=tage)


def main():
    print("1 Gewinntag-Weg")
    for typ in ("phase1", "phase2"):
        for t in (0, 1):
            w, g = plan(typ, 100000.0 + 1050 * t, u_(0.5), (t, 3))
            check(w is not None and 1000 <= w["tp"] <= 1100 and str(w.get("stufe", "")).startswith(f"Gewinntag {t}/3"),
                  f"{typ} {t}/3: Gewinntag-Trade TP {w and w['tp']} ({g or (w and w['stufe'])})")
        w, g = plan(typ, 102100.0, u_(0.5), (2, 3))
        check(w is not None and "Gewinntag" not in str(w.get("stufe")) and w["tp"] > 1100, f"{typ} 2/3: Big Trade ({g or (w and w['stufe'])}, TP {w and w['tp']})")

    print("2 Ziel nie vor dem 3. Gewinntag (lauter Gewinne)")
    for typ, ziel in (("phase1", 110000.0), ("phase2", 105000.0)):
        for x in (0.0, 0.5, 1.0):
            bal, tage, schritte, frueh, letzter = 100000.0, 0, 0, False, None
            while schritte < 20:
                w, g = plan(typ, bal, u_(x), (tage, 3))
                if w is None:
                    letzter = g
                    break
                bal += w["tp"]
                tage += 1 if w["tp"] >= 500 else 0
                schritte += 1
                if bal >= ziel and tage < 3:
                    frueh = True
            check(not frueh and bal >= ziel and tage >= 3, f"{typ} u={x}: Ziel bei {bal:,.0f} mit {tage}/3 Gewinntagen nach {schritte} Trades ({letzter})")

    print("3 SL, Lots, Tagesgrenze 3 %")
    for typ in ("phase1", "phase2"):
        for t in (0, 2):
            for x in (0.0, 1.0):
                for bal in (100000.0, 97000.0):
                    w, g = plan(typ, bal, u_(x), (t, 3))
                    ok = (w is not None and w["sl"] <= 2475 and w["sl"] <= bal * 0.03 - 100 and 2 <= w["menge"] <= 3
                          and w.get("tages_grenze_usd") == round(bal * 0.03, 2))
                    check(ok, f"{typ} {t}/3 u={x} bal {bal:,.0f}: SL {w and w['sl']} · {w and w['menge']} Lot · Grenze {w and w.get('tages_grenze_usd')}")
    w, g = plan("phase1", 100000.0, u_(1.0), (2, 3))
    pkt = w["sl"] / (w["menge"] * PPL) if w else 0
    check(w is not None and 60 <= pkt <= 130, f"NAS100.x: SL {w and w['sl']} $ bei {w and w['menge']} Lot = {pkt:.0f} Pkt (10 $/Pkt je Lot)")

    print("4 SQL-Datei")
    sql = open(os.path.join(WURZEL, "sql", "2026-11-25_gf2_gft_autoplaner.sql"), encoding="utf-8").read()
    code = "\n".join(z for z in sql.splitlines() if not z.lstrip().startswith("--"))
    check("enable row level security" in code and "revoke all on public.gf2_20261125_sicherung from anon, authenticated" in code, "Sicherung: RLS an + revoke")
    check(code.index("insert into public.gf2_20261125_sicherung") < code.index("update public.auto_plan_regeln"), "Sicherung vor dem Update")
    check('f || \'{"planen": true, "gewinntage": {"tp": [1000, 1100]}}\'::jsonb' in code and "with ordinality" in code and "order by i" in code,
          "Regel: nur GFT bekommt planen true + gewinntage, Reihenfolge bleibt")
    check("coalesce((f->>'planen')::boolean, false) = false" in code and "f->>'route' = 'mt5v2'" in code and "= 1" in code, "Regel-Guard: genau ein GFT-Eintrag, noch aus, mt5v2")
    check('"route"' not in code.split("update public.auto_plan_regeln")[1].split("returning")[0].replace("f->>'route'", ""),
          "Route bleibt mt5v2 (Echo mit Hedge über eh_tick wie alle HT-CFD-Challenges)")
    ids = re.findall(r"'([0-9a-f]{8}-[0-9a-f-]{27})'", code.split("update public.accounts")[1])
    konten = set(ids) - {"48f272b4-913e-4598-a06a-1dcc3d5679fb"}   # ohne die user_id „Finn + Pascal“
    check(len(konten) == 4, f"Konten: genau 4 ({len(konten)})")
    check("goal_kind = 'winning_days', goal_target = 3, goal_min_profit = 500" in code and "a.goal_kind = 'trading_days' and a.goal_min_profit is null" in code
          and "q.started_at is not null" in code, "Konten: winning_days 3 × 500, Guard alter Stand + kein Trade")
    check(not re.search(r"^\s*(drop|delete|truncate)\b", code, re.I | re.M), "nichts Destruktives")

    print("5 kontoMindesttage (Vorbelegung neuer Konten)")
    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    m = re.search(r"  const MINDESTTAGE_JE_FIRMA = .*?\n  function kontoMindesttage\(firm, typ\)\{.*?\n  \}\n", html, re.S)
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
    check(bool(m), "Block MINDESTTAGE/GEWINNTAGE + kontoMindesttage gefunden")
    if m and os.path.exists(jsc):
        js = m.group(0) + r"""
const F = [['Goat Funded Trader', 'phase1', 'winning_days', 3, 500], ['goat funded trader', 'phase2', 'winning_days', 3, 500],
           ['Goat Funded Trader', 'funded_cfd', null, null, null], ['Blue Guardian', 'phase1', 'winning_days', 3, 500],
           ['FTMO', 'phase1', 'trading_days', 4, null], ['FundedNext', 'phase2', 'trading_days', 5, null]]
for(const [f, t, k, z, p] of F){ const r = kontoMindesttage(f, t)
  const ok = k === null ? r === null : (r && r.kind === k && r.target === z && r.minProfit === p)
  print((ok ? 'OK ' : 'FEHL ') + f + ' ' + t + ' → ' + JSON.stringify(r)) }
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
        out = subprocess.run([jsc, f.name], capture_output=True, text=True)
        os.unlink(f.name)
        zeilen = [z for z in out.stdout.splitlines() if z.strip()]
        check(len(zeilen) == 6 and all(z.startswith("OK ") for z in zeilen), "GFT Phase 1/2 → winning_days 3 × 500, Funded nie, BG/FTMO/FundedNext unverändert"
              + ("" if all(z.startswith("OK ") for z in zeilen) else " · " + " | ".join(zeilen) + out.stderr[-300:]))

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ GF2 GFT-Auto-Planer: alles grün")


if __name__ == "__main__":
    main()
