-- 2026-09-23: Winning-Day-Farmer — alle IDs aus dem Admin managen, ohne Profilwechsel und ohne Railway
-- (Finn: „ich muss gerade auf jede ID gehen und mich von jeder ID hinzufügen — ich will im Admin alle
-- IDs managen"; „ich will das Balance sehen, keinen Puffer"; „wie viele Winning Days die jeweils haben").
-- RLS lässt einen Nutzer nur eigene accounts sehen/ändern. Zwei SECURITY-DEFINER-Funktionen für
-- Angemeldete: Lesen aller Funded/Live-Konten (mit Person, Live-Balance aus dem dup_live-Spiegel und
-- gezählten Winning Days) und Setzen von Farm-Haken / TP / SL an jedem Konto.

create or replace function public.wd_konten_alle()
returns table (
  id uuid, user_id uuid, person text, name text, firm text, account_type text, external_id text,
  max_drawdown numeric, balance numeric, wd_farm boolean,
  max_profit_per_trade numeric, max_loss_per_trade numeric,
  goal_kind text, goal_target integer, goal_done_offset integer, goal_manual boolean, goal_since text,
  winning_days integer, live_balance numeric, live_ccy text, live_at timestamptz
)
language sql security definer set search_path = public as $$
  with tage as (
    -- Tagessumme je Master-Konto (Trade-Ende zählt, wie tpTradeTagZeit im Frontend)
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
         a.max_profit_per_trade, a.max_loss_per_trade,
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
  where auth.uid() is not null and a.account_type in ('funded', 'live')
$$;
revoke all on function public.wd_konten_alle() from public;
grant execute on function public.wd_konten_alle() to authenticated;

-- Farm-Haken, TP-Vorgabe (max_profit_per_trade) und SL-Vorgabe (max_loss_per_trade) an JEDEM Konto setzen.
-- NULL = Feld nicht anfassen.
create or replace function public.wd_konto_setzen(p_account uuid, p_wd_farm boolean default null, p_tp numeric default null, p_sl numeric default null)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'nicht angemeldet'; end if;
  update public.accounts
     set wd_farm = coalesce(p_wd_farm, wd_farm),
         max_profit_per_trade = coalesce(p_tp, max_profit_per_trade),
         max_loss_per_trade = coalesce(p_sl, max_loss_per_trade)
   where id = p_account;
  return found;
end $$;
revoke all on function public.wd_konto_setzen(uuid, boolean, numeric, numeric) from public;
grant execute on function public.wd_konto_setzen(uuid, boolean, numeric, numeric) to authenticated;

-- Nachtrag 23.09.2026 01:4x (Finn: „Emin und Finn — die ID immer weglassen, immer"): feste Ausschlussliste
-- von Nutzer-IDs in den Farmer-Regeln (gilt für Mac-Tab und alle PC-Tabs), dazu deren Konten aus dem Farm.
-- Emin = 6cceb3f3-dc78-48ee-8668-26081da3e70f, Finn = b55d7ab4-5246-4101-abca-f729c71d17ec („Finn + Pascal" bleibt drin).
alter table public.wd_farmer_regeln add column if not exists ids_aus jsonb not null default '[]'::jsonb;
update public.wd_farmer_regeln set ids_aus = '["6cceb3f3-dc78-48ee-8668-26081da3e70f","b55d7ab4-5246-4101-abca-f729c71d17ec"]'::jsonb where id = 1;
update public.accounts set wd_farm = false where user_id in ('6cceb3f3-dc78-48ee-8668-26081da3e70f','b55d7ab4-5246-4101-abca-f729c71d17ec');
