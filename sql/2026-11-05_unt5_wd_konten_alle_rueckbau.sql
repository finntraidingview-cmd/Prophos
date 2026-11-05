-- RÜCKBAU zu sql/2026-11-05_unt5_wd_konten_alle.sql: Live-Fassung von wd_konten_alle() am 05.11.2026 (pg_get_functiondef, md5 62d4b9ecdb11a7a852cccf86f309e35d).
-- Danach liefert die RPC wieder jedem Login alle Winning-Day-Konten aller IDs.
CREATE OR REPLACE FUNCTION public.wd_konten_alle()
 RETURNS TABLE(id uuid, user_id uuid, person text, name text, firm text, account_type text, external_id text, max_drawdown numeric, balance numeric, wd_farm boolean, max_profit_per_trade numeric, max_loss_per_trade numeric, wd_tp numeric, wd_sl numeric, goal_kind text, goal_target integer, goal_done_offset integer, goal_manual boolean, goal_since text, winning_days integer, live_balance numeric, live_ccy text, live_at timestamp with time zone, starting_balance numeric)
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  with tage as (
    select p.master_account_id::text as acc,
           (coalesce(p.ended_at, p.started_at, p.completed_at, p.created_at) at time zone 'Europe/Berlin')::date as tag,
           sum(p.master_pl) as pl
      from public.trade_plans p
     where p.status in ('completed', 'review') and p.master_pl is not null
     group by 1, 2
  ), live as (
    select x->>'login' as login, (x->>'balance')::numeric as bal, x->>'ccy' as ccy, d.updated_at
      from public.dup_live d, jsonb_array_elements(coalesce(d.accounts, '[]'::jsonb)) x
     where x->>'login' is not null
  ), basis as (
    select a.*,
           coalesce(nullif(u.raw_user_meta_data->>'name', ''), split_part(coalesce(u.email, ''), '@', 1)) as person,
           (select l.bal from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as dup_bal,
           (select l.ccy from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as dup_ccy,
           (select l.updated_at from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as dup_at
      from public.accounts a
      left join auth.users u on u.id = a.user_id
     where auth.uid() is not null and a.account_type = 'winning_days'
  )
  select b.id, b.user_id, b.person, b.name, b.firm, b.account_type, b.external_id, b.max_drawdown, b.balance, b.wd_farm,
         b.max_profit_per_trade, b.max_loss_per_trade, b.wd_tp, b.wd_sl, b.goal_kind, b.goal_target, b.goal_done_offset, b.goal_manual,
         b.goal_since::text,
         (case when b.goal_manual then coalesce(b.goal_done_offset, 0)
               else coalesce(b.goal_done_offset, 0) + (select count(*) from tage t where t.acc = b.id::text and t.pl > coalesce(b.goal_min_profit, 0)
                                                        and (b.goal_since is null or t.tag >= b.goal_since::date)) end)::integer as winning_days,
         case when b.tv_balance is not null and (b.dup_at is null or b.tv_balance_at >= b.dup_at) then b.tv_balance else b.dup_bal end as live_balance,
         case when b.tv_balance is not null and (b.dup_at is null or b.tv_balance_at >= b.dup_at) then 'USD' else b.dup_ccy end as live_ccy,
         case when b.tv_balance is not null and (b.dup_at is null or b.tv_balance_at >= b.dup_at) then b.tv_balance_at else b.dup_at end as live_at,
         b.starting_balance
    from basis b
$function$;
grant execute on function public.wd_konten_alle() to anon, authenticated;
