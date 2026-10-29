-- Korrektur zu 2026-10-29_topstep_immer_2nq.sql: Das Update der geplanten tsv2-Pläne hat auch die zwei Topstep-Winning-Days-Pläne
-- (MNQ, Gewinntag ~163 $) von 3 auf 2 MNQ gesetzt. Finns „immer 2 NQ" galt den Challenge-Trades (NQ, vorher 3–4). WD-Pläne in MNQ
-- zurück auf 3 (Farmer-Regel vorplan.kt.topstep [3,3] bleibt unverändert).
update public.trade_plans set master_contracts = 3, updated_at = now()
where route = 'tsv2' and status = 'planned' and master_symbol ilike 'MNQ%' and master_contracts = 2
  and master_name ilike '%winning days%';
