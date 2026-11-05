-- Simon Topstep Express …27936430 (19163697): Hand-Trade nachtragen (Finn 05.11.2026 ~05:40 Dubai, Foto Funded Futures „heute offen“:
-- „da bitte Master −2.700, Slave +430“ — sein manueller Short von eben, von Hand gegen gehedgt).
-- Muster 2026-11-04_marco_topstep_handtrades.sql (route tsv2, pl_quelle hand, Fusion-Gewinn als slave_pl + hedge_eur) + Buchung wd_hedge
-- auf Simons Fusion-Konto 488579 (18d9b582, wie seine übrigen WD-Hedge-Buchungen). Konto NICHT archivieren. Einmalig über notes.
with neu as (
  insert into public.trade_plans (user_id, master_account_id, master_name, master_firm, priority, planned_for, notes, status, master_pl, slave_pl,
                                  blown, started_at, ended_at, completed_at, master_contract_type, route, richtung, pl_quelle, hedge_eur, konto_typ, auto_plan, kapitel_id)
  select a.user_id, a.id, a.name, a.firm, 'medium', date '2026-11-05', 'Hand-Trade, von Hand gegen gehedgt: Master −2.700 $, Fusion +430 € (Finn 05.11.2026)',
         'completed', -2700, 430, false, now(), now(), now(), 'micro', 'tsv2', 'sell', 'hand', 430, 'funded', false, 2
    from public.accounts a
   where a.id = '19163697-d0a7-4a58-a18b-12649c2feb12'
     and not exists (select 1 from public.trade_plans p where p.master_account_id = a.id and p.notes = 'Hand-Trade, von Hand gegen gehedgt: Master −2.700 $, Fusion +430 € (Finn 05.11.2026)')
  returning id
)
insert into public.transactions (user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated, kapitel_id)
select '5409e926-09bc-4789-9c99-f8584d87a89a', '18d9b582-244e-4d3d-8de2-6501b23c98ef', '488579 → Live', 'Fusion Markets', 'wd_hedge', 430, 'EUR', '2026-11-05',
       'Trade #' || left(neu.id::text, 8) || ' WD-Hedge · Simon · Fusion 488579', true, 2
  from neu;
