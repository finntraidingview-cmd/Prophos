-- Blue Guardian in den Auto-Planer (Finn 07.10.2026, Werte von Finn selbst — vorher „keine Regel für diese Firma" bei
-- 2 × 100k Phase 1 in „Braucht dich"). 2-Step Standard, CFD NAS100 über Echo V2 (route mt5v2), 10 $/Punkt je Lot wie FundedNext.
-- Kernwerte (Screenshots Blue Guardian + Finn): Phase 1 Ziel 8 % (108.000), Phase 2 Ziel 4 % (104.000), Static Drawdown 8 %
-- (Boden 92.000 in beiden Phasen), Max Daily Loss 4 % = 4.000 (harter Breach, daher kein soft — nur zur Info/Einsatz),
-- Kaufpreis ~300 € (100k) / ~600 € (200k). Planer plant vorerst nur 100k („erstmal nur 100k"), 200k zählt nur für den Kontowert.
-- Planer-Werte (Finn 07.10.2026): Lot 3–4 (Schritt 0,1), TP Phase 1 5.500–6.500 $, TP Phase 2 3.000–3.500 $,
-- SL 2.000–3.000 $ (am Boden gekappt, bleibt unter dem Daily 4.000), Puffer 100 $ über dem Ziel.
-- Die 3 Gewinntage ≥ 0,5 % plant der Planer NICHT ein (wie FTMO-Mindesttage: Finn farmt von Hand, keine Regel-Prüfung).
-- Wiederholbar: ein vorhandener blueguardian-Eintrag wird ersetzt, alle anderen Firmen bleiben, wie sie sind.

update public.auto_plan_regeln
set regeln = jsonb_set(regeln, '{firmen}', (
      select coalesce(jsonb_agg(f order by ord) filter (where not (f->'namen' ? 'blueguardian')), '[]'::jsonb)
      from jsonb_array_elements(regeln->'firmen') with ordinality as t(f, ord)
    ) || '[{
      "namen": ["blueguardian"],
      "planen": true,
      "route": "mt5v2",
      "kauf_eur": {"100000": 300, "200000": 600},
      "dd_pct": 8,
      "boden": "statisch",
      "ziel_pct": {"phase1": 8, "phase2": 4},
      "groessen": [100000],
      "wert_groessen": [100000, 200000],
      "phasen": {
        "phase1": {"sl": [2000, 3000], "tp": [5500, 6500], "menge": [3, 4], "menge_schritt": 0.1,
                   "puffer": [100, 100], "ziel_pct": 8, "boden_pct": 8},
        "phase2": {"sl": [2000, 3000], "tp": [3000, 3500], "menge": [3, 4], "menge_schritt": 0.1,
                   "puffer": [100, 100], "ziel_pct": 4, "boden_pct": 8}
      }
    }]'::jsonb),
    updated_at = now()
where id = 1;

-- Prüfen:
-- select jsonb_pretty(f) from public.auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'blueguardian';
