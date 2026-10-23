-- Tradeify CFD: Auto-Planer einschalten — ERST nach dem Push des Umbaus „Tradeify CFD ≠ Tradeify-Futures" (Slave 4, 23.10.2026).
-- Bis dahin stand die Regel auf planen:false (sql/2026-10-23_tradeify_cfd_firma.sql, Schablone vorab live auf Finns Wort).
update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(case when x->'namen' ? 'tradeifycfd' then jsonb_set(x, '{planen}', 'true') else x end order by i)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality t(x, i))),
    updated_at = now()
where exists (select 1 from jsonb_array_elements(r.regeln->'firmen') x where x->'namen' ? 'tradeifycfd' and x->'planen' = 'false');
