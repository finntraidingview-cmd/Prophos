-- 2026-09-25: eigene Finanzen-Kategorie für den Winning-Days-Gegenhedge (Finn: „Auf ‚Beendet' öffnet sich das
-- Popup ‚Trade erledigt', ich gebe Master- und Slave-P&L von Hand ein, auf ‚Erledigt' wird es in Finanzen gebucht —
-- eigene Finanzen-Kategorie für den Winning-Days-Gegenhedge; das sind ab jetzt die einzigen Hedgekosten.").
-- Befund: tradeCompleteSave bucht slave_pl nur als 'live_pnl', wenn der Plan ein Live-Slave-Konto hat — Farm-Pläne
-- (route tvv2, Fusion-Solo-Hedge über den Copier) haben keins, ihr Fusion-P&L landete bisher nirgends in Finanzen.
-- transactions.kind: payout | live_pnl | account_purchase | manual — NEU 'wd_hedge' = realisierter P&L des
-- Fusion-Gegenhedges eines Winning Days in EUR (Vorzeichen = P&L: negativ = Kosten). Gebucht von
-- PATCH /admin/wd-plaene {aktion:'erledigt'} auf das Fusion-Hedge-Konto im Profil der ID (user_settings
-- echo_hedge_account, Rückfall Konto mit external_id 488579), notes 'Trade #<plan8> WD-Hedge · <Person> · <Konto>'
-- (idempotent über den Schlüssel 'Trade #<plan8> WD-Hedge'), auto_generated true, kapitel_id per Trigger.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.transactions drop constraint if exists transactions_kind_check;
alter table public.transactions add constraint transactions_kind_check
  check (kind = any (array['payout'::text, 'live_pnl'::text, 'account_purchase'::text, 'manual'::text, 'wd_hedge'::text]));
comment on column public.transactions.kind is
  'payout | live_pnl | account_purchase | manual | wd_hedge (seit 25.09.2026: Fusion-Gegenhedge eines Winning Days, EUR, P&L-Vorzeichen)';
