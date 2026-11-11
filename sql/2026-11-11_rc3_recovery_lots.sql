-- RC3 (Finn 11.11.2026 19:24 + 19:27 über den Master): Lots ALLER Recovery-Trades nach TP — < 500 $ → 3 MNQ · 500 bis < 1.000 $ → 4 MNQ ·
-- 1.000 bis 2.000 $ → 7 MNQ · über 2.000 $ → 1 NQ. Eigene Spalte (firmen_regeln[firma] schreibt e4Speichern im Frontend jedes Mal ganz neu).
-- Leser: app.py _rc3_regeln_lesen / rc3_recovery_lots — Tradeify + Lucid (Ausgleichs-Trade, tradeify_zyklus_konto), Apex (Recoverer, wd_zyklus_konto).
-- Topstep hat heute keinen Recovery-Weg (kein Eintrag). Spalte fehlt oder Firma ohne Eintrag → wie bisher (Tradeify/Lucid Farmer-Spanne, Apex 1 NQ).
-- max_mnq = Max-Kontrakte je Größe in MNQ-Äquivalent (1 NQ = 10 MNQ); über dem Limit gilt die nächstkleinere Stufe (Hinweis im Grund).
--   Tradeify Select laut firm_rules.json: 25K 2/20 · 50K 4/40 · 100K 8/80 · 150K 12/120.
--   Apex laut firm_rules.json Half-Size-Phase des PA bis zum Safety Net: 50K 2 · 100K 3 · 150K 4 Mini (die kleinere Grenze).
--   Lucid steht NICHT in firm_rules.json — vorsichtige Annahme wie Apex Half-Size (25K 1 · 50K 2 · 100K 3 · 150K 4 Mini), bitte von Finn bestätigen.

alter table public.wd_farmer_regeln add column if not exists recovery_lots jsonb;

with st as (
  select jsonb_build_array(
           jsonb_build_object('ab', 0,    'ab_inkl', true,  'kt', 3, 'instr', 'mnq'),
           jsonb_build_object('ab', 500,  'ab_inkl', true,  'kt', 4, 'instr', 'mnq'),
           jsonb_build_object('ab', 1000, 'ab_inkl', true,  'kt', 7, 'instr', 'mnq'),
           jsonb_build_object('ab', 2000, 'ab_inkl', false, 'kt', 1, 'instr', 'nq')) as stufen
)
update public.wd_farmer_regeln
   set recovery_lots = coalesce(recovery_lots, '{}'::jsonb) || jsonb_build_object(
         'tradeify', jsonb_build_object('an', true, 'stufen', st.stufen,
                                        'max_mnq', jsonb_build_object('25000', 20, '50000', 40, '100000', 80, '150000', 120)),
         'lucid',    jsonb_build_object('an', true, 'stufen', st.stufen,
                                        'max_mnq', jsonb_build_object('25000', 10, '50000', 20, '100000', 30, '150000', 40)),
         'apex',     jsonb_build_object('an', true, 'stufen', st.stufen,
                                        'max_mnq', jsonb_build_object('50000', 20, '100000', 30, '150000', 40))),
       updated_at = now()
  from st
 where id = 1;

-- Prüfen:
-- select recovery_lots from public.wd_farmer_regeln where id = 1;
