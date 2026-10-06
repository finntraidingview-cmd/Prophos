-- Topstep in den Auto-Plan (Finn 07.10.2026): Kernwert-Eintrag „topstep" in auto_plan_regeln.regeln.firmen[] —
-- Weg Topstep V2 (route tsv2, Puls für Topstep in TopstepX), planen true, Challenge (Combine) 150k: Ziel +9.000 (6 %),
-- Consistency 50 % → größter Tag 4.500, TP-Spanne [4.350, 4.450], kein SL (Drawdown 4.500 nachziehend ist der SL),
-- Menge NQ 2–3 und Puffer wie Tradeify. Express/XFA-Konten plant der Planer nie (ist_topstep_express).
-- ACHTUNG: Der PC-Tab startet tsv2-Pläne zur start_um noch NICHT von selbst (tpStartUmTick: „bis Etappe K4 grün") —
-- Auto-Pläne für Topstep bleiben bis dahin mit ihrer Startzeit stehen und werden nur von Hand gestartet.
-- Nur der topstep-Eintrag wird ersetzt; alle anderen Firmen bleiben, wie sie sind.

update public.auto_plan_regeln
set regeln = jsonb_set(regeln, '{firmen}', (
      select jsonb_agg(
               case when f->'namen' ? 'topstep'
                    then f || jsonb_build_object(
                           'planen', true,
                           'route', 'tsv2',
                           'symbol', 'NQ',
                           'phasen', jsonb_build_object('challenge', jsonb_build_object(
                             'sl', null,
                             'tp', '[4350, 4450]'::jsonb,
                             'menge', '[2, 3]'::jsonb,
                             'dd_usd', 4500,
                             'tp_max', 4500,
                             'ziel_pct', 6,
                             'menge_schritt', 1,
                             'puffer_je_menge', '{"2": [15, 25], "3": [25, 40]}'::jsonb)))
                    else f end
               order by ord)
      from jsonb_array_elements(regeln->'firmen') with ordinality as t(f, ord))),
    updated_at = now()
where id = 1;

-- Prüfen:
-- select f from public.auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'topstep';
