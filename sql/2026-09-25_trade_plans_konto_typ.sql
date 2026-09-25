-- 2026-09-25 · trade_plans.konto_typ = Kontotyp ZUM ZEITPUNKT des Trades
--
-- Anlass (Finn 25.09.2026 am Admin-Statistik-Tab, über die Koordination): Mikes Trade 2ff62bb5 (tsv2, Topstep
-- EXPRESS-V2-682437-57131691, +10.900 $, completed 24.09. 17:11 UTC) lief als „Topstep · Winning Day" mit Quote 0,55
-- (≈ −5.965 € Hedge) — war aber ein FUNDED-Trade; das Konto wurde erst um 20:41 UTC auf account_type 'winning_days'
-- umgestellt. Die Statistik (/admin/kapitel, _hq_typ_trade) ordnete jeden Trade nach dem HEUTIGEN accounts.account_type
-- ein; seit der Einführung des Typs (24.09. ab ~20:00 UTC) zählten dadurch ~68 ältere Funded-Trades als Winning Day.
-- Fix: der Typ wird am Plan festgehalten, sobald er nach review/completed geht (Frontend + /admin/wd-plaene), und die
-- Statistik liest ihn zuerst (Rückfall: aktueller Kontotyp).
--
-- Backfill (nur Pläne auf review/completed, nur leere Werte):
--   1) Winning-Day-Pläne (route 'tvv2' und hedge_eur > 0 oder winning_day = true) → 'winning_days'
--   2) sonst accounts.account_type des Master-Kontos — AUSSER 'winning_days' bei completed_at vor 24.09.2026 20:00 UTC → 'funded'
--      (den Typ gab es vorher nicht; die Trades wurden bis dahin als Funded gezählt)
-- Stand beim Schreiben: 68 Trades vor 20:00 UTC auf heute-'winning_days'-Konten → 'funded'; 6 danach bleiben 'winning_days'.

alter table public.trade_plans add column if not exists konto_typ text;

comment on column public.trade_plans.konto_typ is
  'Kontotyp des Master-Kontos zum Zeitpunkt des Trades (funded/challenge/winning_days/…). Gesetzt beim Übergang nach review/completed; Statistik liest ihn vor accounts.account_type.';

update public.trade_plans t
   set konto_typ = 'winning_days'
 where t.konto_typ is null
   and t.status in ('review', 'completed')
   and t.route = 'tvv2'
   and (coalesce(t.hedge_eur, 0) > 0 or t.winning_day is true);

update public.trade_plans t
   set konto_typ = case
         when a.account_type = 'winning_days' and t.completed_at < '2026-09-24 20:00:00+00' then 'funded'
         else a.account_type
       end
  from public.accounts a
 where a.id = t.master_account_id
   and t.konto_typ is null
   and t.status in ('review', 'completed')
   and a.account_type is not null;
