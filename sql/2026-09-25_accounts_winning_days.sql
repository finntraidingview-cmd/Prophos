-- 2026-09-25: vierter Kontotyp „Winning Days" (Finn: „Wir fügen ein Viertes bei Account-Typen hinzu:
-- Phase 1, Phase 2, Challenge, Funded — jetzt noch Winning Days. Hat ein Funded-Konto den Big Trade
-- gewonnen, gibt man an, dass es bestanden ist, und es kommt zu Winning Days. Dann können wir bei
-- Admin/Hedge-Quoten genau zuordnen, welcher Trade ein Winning Day war, und im Trade-Plan-Dropdown
-- für Winning Days nur die sehen.").
-- accounts.account_type ist text MIT Check-Constraint accounts_account_type_check (challenge | phase1 |
-- phase2 | funded | live) — der erste Anlauf der Migration scheiterte genau daran (23514). Constraint neu
-- mit 'winning_days'. Der Tages-Haken wd_farm bleibt unabhängig davon erhalten.
alter table public.accounts drop constraint if exists accounts_account_type_check;
alter table public.accounts add constraint accounts_account_type_check
  check (account_type = any (array['challenge'::text, 'phase1'::text, 'phase2'::text, 'funded'::text, 'live'::text, 'winning_days'::text]));
comment on column public.accounts.account_type is
  'phase1 | phase2 | challenge | funded | live | winning_days (seit 25.09.2026: Funded-Konto nach bestandenem Big Trade)';

-- Einmal-Migration: die heutigen Farmer-Konten (wd_farm = true, Typ funded/live) sind Winning-Days-Konten.
-- Stand 25.09.2026 vor der Migration: 1 Konto (funded + wd_farm). Challenge-/Phase-Konten mit wd_farm
-- bleiben unangetastet — sie sind noch nicht bestanden.
update public.accounts
   set account_type = 'winning_days'
 where coalesce(wd_farm, false) = true and account_type in ('funded', 'live');

-- RPC des Farmers: nur noch Winning-Days-Konten (Finn: „immer nur die Winning Days sehen").
-- Signatur = Live-Stand (inkl. wd_tp/wd_sl aus einer späteren Migration), nur die WHERE-Klausel ändert sich.
create or replace function public.wd_konten_alle()
returns table (
  id uuid, user_id uuid, person text, name text, firm text, account_type text, external_id text,
  max_drawdown numeric, balance numeric, wd_farm boolean,
  max_profit_per_trade numeric, max_loss_per_trade numeric, wd_tp numeric, wd_sl numeric,
  goal_kind text, goal_target integer, goal_done_offset integer, goal_manual boolean, goal_since text,
  winning_days integer, live_balance numeric, live_ccy text, live_at timestamptz
)
language sql security definer set search_path = public as $$
  with tage as (
    select p.master_account_id::text as acc,
           (coalesce(p.ended_at, p.started_at, p.completed_at, p.created_at) at time zone 'Europe/Berlin')::date as tag,
           sum(p.master_pl) as pl
    from public.trade_plans p
    where p.status in ('completed', 'review') and p.master_pl is not null
    group by 1, 2
  ),
  live as (
    select x->>'login' as login, (x->>'balance')::numeric as bal, x->>'ccy' as ccy, d.updated_at
    from public.dup_live d, jsonb_array_elements(coalesce(d.accounts, '[]'::jsonb)) x
    where x->>'login' is not null
  )
  select a.id, a.user_id,
         coalesce(nullif(u.raw_user_meta_data->>'name', ''), split_part(coalesce(u.email, ''), '@', 1)) as person,
         a.name, a.firm, a.account_type, a.external_id, a.max_drawdown, a.balance, a.wd_farm,
         a.max_profit_per_trade, a.max_loss_per_trade, a.wd_tp, a.wd_sl,
         a.goal_kind, a.goal_target, a.goal_done_offset, a.goal_manual, a.goal_since::text,
         (case when a.goal_manual then coalesce(a.goal_done_offset, 0)
               else coalesce(a.goal_done_offset, 0) + (select count(*) from tage t
                      where t.acc = a.id::text and t.pl > coalesce(a.goal_min_profit, 0)
                        and (a.goal_since is null or t.tag >= a.goal_since::date))
          end)::integer as winning_days,
         (select l.bal from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as live_balance,
         (select l.ccy from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as live_ccy,
         (select l.updated_at from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as live_at
  from public.accounts a
  left join auth.users u on u.id = a.user_id
  where auth.uid() is not null and a.account_type = 'winning_days'
$$;
revoke all on function public.wd_konten_alle() from public;
grant execute on function public.wd_konten_alle() to authenticated;
