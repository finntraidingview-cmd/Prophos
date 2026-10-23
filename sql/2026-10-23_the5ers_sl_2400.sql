-- The5%ers: SL-Bereich im Auto-Planer 2.000–2.500 $ → 2.000–2.400 $ je 100k, Phase 1 + Phase 2 (Finn 23.10.2026 ~12:35 Dubai:
-- „Tu den Stop Loss einfach auf 2,4 … Das war's"). Anlass: ein Phase-2-Konto am 22.10. geblowt — Tageslimit The5%ers rechnet
-- vom Equity, der Trade ging mit −2.925 $ raus (SL geplant 2.291 $). Finn: „nur Pech, sonst ändern wir nichts" — also kein
-- Tageslimit-Feld, nur der SL-Deckel. 200k skaliert der Planer selbst (skaliert: true).
-- Nur der Eintrag mit namen „the5ers", nur wenn dort noch [2000,2500] steht (sonst 0 Zeilen, nichts geändert).
update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(case when x->'namen' ? 'the5ers'
        then jsonb_set(jsonb_set(x, '{phasen,phase1,sl}', '[2000,2400]'), '{phasen,phase2,sl}', '[2000,2400]')
        else x end order by i)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality t(x, i))),
    updated_at = now()
where exists (select 1 from jsonb_array_elements(r.regeln->'firmen') x
              where x->'namen' ? 'the5ers'
                and x->'phasen'->'phase1'->'sl' = '[2000,2500]'
                and x->'phasen'->'phase2'->'sl' = '[2000,2500]')
returning (select x->'phasen' from jsonb_array_elements(r.regeln->'firmen') x where x->'namen' ? 'the5ers') as the5ers_phasen;
