-- 2026-09-24 (abends): neuer Weg „Topstep V2" (route = 'tsv2') — Topstep OHNE API, alles von Hand.
-- Finn: „Im neuen Kapitel kann man noch keine Topstep-Trades machen, weil es bisher nur Echo V2 und
-- Orbit V2 gibt … und in Zukunft wird bei Topstep auch nichts über die API gemacht, alles nur manuell."
-- tsv2 = wie die V2-Wege ohne Slave/Hedge: Plan → „Läuft" per Hand → „Erledigt" mit P&L von Hand.
-- Zwei Stellen kennen die V2-Liste: die generierte Spalte ohne_hedge und der Kapitel-Trigger set_kapitel.
-- Die Views hängen an ohne_hedge → erst weg, Spalte neu, Views wieder anlegen (Text = kapitel2_schema.sql).

drop view if exists public.v_kapitel_summen;
drop view if exists public.v_kapitel_trades;
drop index if exists public.trade_plans_ohne_hedge_idx;
alter table public.trade_plans drop column if exists ohne_hedge;
alter table public.trade_plans
  add column ohne_hedge boolean
  generated always as (coalesce(route, '') in ('mt5v2','tvv2','tsv2')) stored;
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



-- set_kapitel: V2-Liste um tsv2 erweitert, Rest exakt wie 2026-09-24_kapitel_konto_vererbung.sql
create or replace function public.set_kapitel()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_ohne smallint;
  v_konto smallint;
begin
  if tg_table_name = 'trade_plans' then
    if coalesce(new.route, '') in ('mt5v2', 'tvv2', 'tsv2') then
      select id into v_ohne from public.kapitel where hedge = false order by von desc limit 1;
      if v_ohne is not null then
        new.kapitel_id := v_ohne;
        return new;
      end if;
    end if;
    if new.kapitel_id is null then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
    end if;
    return new;
  end if;
  if tg_table_name in ('transactions', 'pending_payouts') then
    if new.account_id is not null then
      select a.kapitel_id into v_konto from public.accounts a where a.id = new.account_id;
      if v_konto is not null then
        new.kapitel_id := v_konto;
        return new;
      end if;
    end if;
    if new.kapitel_id is null then
      if tg_table_name = 'transactions' then
        new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
      else
        new.kapitel_id := public.kapitel_fuer(coalesce(new.requested_at, current_date));
      end if;
    end if;
    return new;
  end if;
  if new.kapitel_id is null then
    new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
  end if;
  return new;
end;
$$;

-- Bestand: tsv2-Pläne gibt es noch keine — nichts nachzuziehen. Idempotent.
