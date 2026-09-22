-- 2026-09-23 03:5x: Winning-Day-Farmer — eigene TP/SL-Vorgabe je Konto + Scharf-Schalter (Nachtrag).
-- BEFUND: die TP/SL-Vorgabe des Farmers lag in accounts.max_profit_per_trade / max_loss_per_trade. Das sind
-- aber die Prop-Firm-Limits „Max Profit / Trade" (Tradeify 3600) und „Max Loss / Trade" (4500) — Jacobs
-- Farmer-Pläne bekamen dadurch TP 3600 / SL 4500 statt 270–290. Deshalb eigene Spalten:
alter table public.accounts add column if not exists wd_tp numeric;   -- TP-Vorgabe des Farmers ($), NULL = Firmen-Spanne
alter table public.accounts add column if not exists wd_sl numeric;   -- SL-Vorgabe des Farmers ($), NULL = kein SL

-- Scharf-Schalter (bereits am 23.09. 02:xx direkt in Supabase angelegt, hier nachgetragen):
-- false = würfeln/planen ja, aber tpStartUmTick startet keine Farmer-Pläne (notes 'Winning-Day-Farmer').
alter table public.wd_farmer_regeln add column if not exists scharf boolean not null default false;

-- wd_konto_setzen schreibt jetzt wd_tp / wd_sl (NULL = nicht anfassen, <= 0 = löschen, > 0 = setzen)
create or replace function public.wd_konto_setzen(p_account uuid, p_wd_farm boolean default null, p_tp numeric default null, p_sl numeric default null)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'nicht angemeldet'; end if;
  update public.accounts
     set wd_farm = coalesce(p_wd_farm, wd_farm),
         wd_tp = case when p_tp is null then wd_tp when p_tp <= 0 then null else p_tp end,
         wd_sl = case when p_sl is null then wd_sl when p_sl <= 0 then null else p_sl end
   where id = p_account;
  return found;
end $$;

-- wd_konten_alle liefert zusätzlich wd_tp / wd_sl (Rückgabetyp geändert → drop + create)
drop function if exists public.wd_konten_alle();
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
  where auth.uid() is not null and a.account_type in ('funded', 'live')
$$;
revoke all on function public.wd_konten_alle() from public;
grant execute on function public.wd_konten_alle() to authenticated;

-- Reparatur der zwei falschen Pläne von Jacob (23.09.2026, planned, nicht gestartet): TP 3600 → 275/286, SL 4500 → NULL
-- (im Supabase-Editor ausgeführt, hier dokumentiert).
