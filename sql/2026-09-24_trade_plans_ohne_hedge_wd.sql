-- 2026-09-24 (spät): trade_plans.ohne_hedge berücksichtigt den Fusion-Gegenhedge.
-- Befund der Koordinations-Session (per SQL bestätigt): ohne_hedge war
--   coalesce(route,'') in ('mt5v2','tvv2','tsv2')
-- — ein Winning-Days-Farm-Plan (route tvv2 + hedge_eur > 0) zählte damit als „ohne Hedge",
-- obwohl er auf Fusion gegengehedgt ist (Solo-Hedge, magic 790001). Kapitel-Vergleich und
-- „Nicht gehedgt = gespart" hätten gelogen. Neu:
--   … and coalesce(hedge_eur, 0) = 0
-- Generierte Spalten dürfen nur eigene Spalten referenzieren — hedge_eur liegt in trade_plans
-- (sql/2026-09-24_tv_kurse_hedge_eur.sql), passt. Der Kapitel-Trigger set_kapitel bleibt
-- unverändert: Winning-Days-Farm-Pläne gehören weiter zu Kapitel 2 (Finns Entscheidung —
-- Winning Days sind der einzige Hedge-Fall der neuen Ära). Die Views hängen an der Spalte →
-- erst weg, Spalte neu, Views wieder anlegen (Text = kapitel2_schema.sql / route_tsv2.sql).
-- Stand vor der Migration: 10 tvv2-Pläne ohne_hedge, 0 mit hedge_eur — nichts kippt rückwirkend.

drop view if exists public.v_kapitel_summen;
drop view if exists public.v_kapitel_trades;
drop index if exists public.trade_plans_ohne_hedge_idx;
alter table public.trade_plans drop column if exists ohne_hedge;
alter table public.trade_plans
  add column ohne_hedge boolean
  generated always as (coalesce(route, '') in ('mt5v2','tvv2','tsv2') and coalesce(hedge_eur, 0) = 0) stored;
comment on column public.trade_plans.ohne_hedge is
  'generiert: V2-Weg (mt5v2/tvv2/tsv2) UND kein Fusion-Gegenhedge (hedge_eur leer/0). Winning-Days-Farm-Pläne mit hedge_eur > 0 sind gehedgt (24.09.2026 spät).';
create index if not exists trade_plans_ohne_hedge_idx
  on public.trade_plans (user_id, ohne_hedge);

create or replace view public.v_kapitel_trades
with (security_invoker = on)
as
select p.id,
       p.user_id,
       p.kapitel_id,
       k.name                          as kapitel_name,
       p.route,
       p.ohne_hedge,
       coalesce(a.name, p.master_name) as master_name,
       coalesce(a.firm, p.master_firm) as master_firm,
       p.master_symbol_root,
       p.richtung,
       p.master_contracts,
       p.master_pl,
       p.slave_pl,
       p.blown,
       p.status,
       p.created_at,
       p.started_at,
       p.ended_at,
       p.completed_at,
       p.pl_quelle
  from public.trade_plans p
  left join public.kapitel  k on k.id = p.kapitel_id
  left join public.accounts a on a.id = p.master_account_id;


create or replace view public.v_kapitel_summen
with (security_invoker = on)
as
with
  pl as (
    select user_id, kapitel_id,
           count(*)                                   as trades,
           count(*) filter (where ohne_hedge)         as trades_ohne_hedge,
           count(*) filter (where blown)              as blown,
           coalesce(sum(master_pl), 0)                as master_pl_sum,
           coalesce(sum(slave_pl), 0)                 as slave_pl_sum
      from public.trade_plans
     where status = 'completed'
     group by user_id, kapitel_id
  ),
  ac as (
    select user_id, kapitel_id,
           coalesce(sum(purchase_cost), 0)            as kauf_sum
      from public.accounts
     where coalesce(account_type, '') <> 'live'
     group by user_id, kapitel_id
  ),
  tx as (
    select user_id, kapitel_id,
           coalesce(sum(amount) filter (where kind = 'payout'),   0) as payouts_sum,
           coalesce(sum(amount) filter (where kind = 'live_pnl'), 0) as live_pnl_sum
      from public.transactions
     group by user_id, kapitel_id
  ),
  keys as (
    select user_id, kapitel_id from pl
    union select user_id, kapitel_id from ac
    union select user_id, kapitel_id from tx
  )
select ks.user_id,
       ks.kapitel_id,
       k.name                              as kapitel_name,
       coalesce(pl.trades, 0)              as trades,
       coalesce(pl.trades_ohne_hedge, 0)   as trades_ohne_hedge,
       coalesce(pl.blown, 0)               as blown,
       coalesce(pl.master_pl_sum, 0)       as master_pl_sum,
       coalesce(pl.slave_pl_sum, 0)        as slave_pl_sum,
       coalesce(ac.kauf_sum, 0)            as kauf_sum,
       coalesce(tx.payouts_sum, 0)         as payouts_sum,
       coalesce(tx.live_pnl_sum, 0)        as live_pnl_sum
  from keys ks
  left join public.kapitel k on k.id = ks.kapitel_id
  left join pl on pl.user_id = ks.user_id and pl.kapitel_id is not distinct from ks.kapitel_id
  left join ac on ac.user_id = ks.user_id and ac.kapitel_id is not distinct from ks.kapitel_id
  left join tx on tx.user_id = ks.user_id and tx.kapitel_id is not distinct from ks.kapitel_id;

revoke all on public.v_kapitel_trades, public.v_kapitel_summen from anon;
grant select on public.v_kapitel_trades, public.v_kapitel_summen to authenticated, service_role;

-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
