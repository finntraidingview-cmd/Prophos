-- Topstep immer 2 NQ (Finn 29.10.2026 ~14:15 Dubai: „Positionsgrößen immer auf 2 NQs … ab jetzt immer nur noch 2 NQs starten und nicht
-- 4 oder so … es geht gerade um Topstep"). Vorher Challenge-Planer Topstep: phasen.challenge.menge [2,3], kette.menge [2,3],
-- kette.t2_menge [3,4] (daher die 4 NQ). Jetzt alle drei [2,2]. TP/SL bleiben in $ (Planer-Logik), nur die Kontraktzahl sinkt.
-- Dazu: alle noch geplanten (nicht gestarteten) Topstep-Pläne (route tsv2, status planned) mit mehr als 2 Kontrakten auf 2.
-- Rücknahme: menge [2,3], kette.menge [2,3], kette.t2_menge [3,4]; geplante Pläne nicht automatisch zurück.

update public.auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(
               case when f->'namen' ? 'topstep' then
                 jsonb_set(jsonb_set(jsonb_set(f,
                   '{phasen,challenge,menge}', '[2,2]'::jsonb),
                   '{kette,menge}', '[2,2]'::jsonb),
                   '{kette,t2_menge}', '[2,2]'::jsonb)
               else f end order by i)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality t(f, i))),
    updated_at = now()
where r.id = 1;

update public.trade_plans
set master_contracts = 2, updated_at = now()
where route = 'tsv2' and status = 'planned' and master_contracts > 2;
