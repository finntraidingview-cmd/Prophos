-- Flotte: offene V2-Pläne ALLER anderen IDs lesbar machen (Finn 25.09.2026 mittags: „Unter Trades → Offen sieht man aktuell
-- nur die eigenen offenen Trades und nicht mehr die von den anderen — wenn Jacob eingeloggt ist, nicht die, die gerade bei Mike
-- live sind. Das war früher anders. Bei Echo V2, Orbit V2, Winning Days V2 und Topstep V2 soll jede ID die Trades aller sehen,
-- außer von Emin und Finn.")
-- Warum eine Funktion: trade_plans ist per RLS nur für die eigene user_id lesbar („users can view own trade_plans"). Die alte
-- Flotten-Anzeige lebte von mt5_live / dup_live / TopstepX-Positionen — Orbit V2, Winning Days und Topstep V2 stehen dort nicht,
-- sie existieren nur als Plan. SECURITY DEFINER liefert deshalb NUR offene V2-Pläne der anderen, nur lesend und nur mit den
-- Feldern, die eine Karte braucht (kein P&L-Verlauf, keine Notizen, keine Zugangsdaten). Der Ausschluss Emin/Finn passiert wie
-- in der bestehenden Flotten-Anzeige im Frontend (ADMIN_EXCLUDE über /admin/overview → _fleetPers.exclUids).

create or replace function public.flotte_offene_plaene()
returns table (
  id uuid, user_id uuid, route text, richtung text, winning_day boolean,
  master_name text, master_firm text, master_symbol text, master_symbol_root text, master_contracts numeric,
  master_tp numeric, hedge_eur numeric, started_at timestamptz, kapitel_id smallint, hedge jsonb
)
language sql
stable
security definer
set search_path = public
as $$
  select t.id, t.user_id, t.route, t.richtung, t.winning_day,
         t.master_name, t.master_firm, t.master_symbol, t.master_symbol_root, t.master_contracts,
         t.master_tp, t.hedge_eur, t.started_at, t.kapitel_id,
         case when t.mt5_baseline ? 'hedge' then jsonb_build_object(
           'status', t.mt5_baseline->'hedge'->'status', 'richtung', t.mt5_baseline->'hedge'->'richtung',
           'lots', t.mt5_baseline->'hedge'->'lots', 'ticket', t.mt5_baseline->'hedge'->'ticket',
           'pl', t.mt5_baseline->'hedge'->'pl', 'einstieg_nq', t.mt5_baseline->'hedge'->'einstieg_nq',
           'einstieg_wurzel', t.mt5_baseline->'hedge'->'einstieg_wurzel',
           'schliesst_bei_nq', t.mt5_baseline->'hedge'->'schliesst_bei_nq', 'sl', t.mt5_baseline->'hedge'->'sl',
           'pc', t.mt5_baseline->'hedge'->'pc') end as hedge
  from public.trade_plans t
  where auth.uid() is not null
    and t.user_id <> auth.uid()
    and t.status = 'open'
    and t.route in ('mt5v2', 'tvv2', 'tsv2')
  order by t.started_at nulls last
$$;

revoke all on function public.flotte_offene_plaene() from public, anon;
grant execute on function public.flotte_offene_plaene() to authenticated;
