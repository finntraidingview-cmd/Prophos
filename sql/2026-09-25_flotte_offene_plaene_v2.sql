-- 2026-09-25 · flotte_offene_plaene: Start-Balance für Echo V2 mitliefern
--
-- Anlass (Finn 25.09.2026: „Warum sehe ich bei Mike nicht den Live-P&L, wenn es doch über Echo V2 gemacht wurde?"): die
-- Flotten-Karte fremder Echo-V2-Pläne zeigt jetzt den MASTER-Chip aus mt5_live (Equity des Master-Kontos). Mit der Start-Balance
-- des Plans (mt5_baseline.master_balance, beim bewiesenen Puls-Klick eingefroren) ist das der echte Trade-P&L (Equity − Start);
-- ohne sie zeigt das Frontend ehrlich nur den schwebenden Teil (Equity − Balance jetzt). Die Funktion gibt deshalb zusätzlich
-- master_balance zurück — sonst nichts Neues (keine Positionen, kein Verlauf, keine Zugangsdaten).
-- Rückgabetyp ändert sich → drop + create (create or replace kann keine Spalte anhängen). Rechte wie vorher.

drop function if exists public.flotte_offene_plaene();

create function public.flotte_offene_plaene()
returns table (
  id uuid, user_id uuid, route text, richtung text, winning_day boolean,
  master_name text, master_firm text, master_symbol text, master_symbol_root text, master_contracts numeric,
  master_tp numeric, hedge_eur numeric, started_at timestamptz, kapitel_id smallint, hedge jsonb,
  master_balance numeric
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
           'pc', t.mt5_baseline->'hedge'->'pc') end as hedge,
         case when t.route = 'mt5v2' and jsonb_typeof(t.mt5_baseline->'master_balance') = 'number'
              then (t.mt5_baseline->>'master_balance')::numeric end as master_balance
  from public.trade_plans t
  where auth.uid() is not null
    and t.user_id <> auth.uid()
    and t.status = 'open'
    and t.route in ('mt5v2', 'tvv2', 'tsv2')
  order by t.started_at nulls last
$$;

revoke all on function public.flotte_offene_plaene() from public, anon;
grant execute on function public.flotte_offene_plaene() to authenticated;
