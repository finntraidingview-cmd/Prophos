-- Trade-Limits pro Account:
--   max_daily_drawdown  = Max Daily Loss   (Spalte existiert bereits)
--   max_loss_per_trade  = Max Loss pro Trade   (NEU)
--   max_profit_per_trade = Max Profit pro Trade (NEU)
-- Im Supabase SQL-Editor ausführen.

alter table public.accounts
  add column if not exists max_loss_per_trade  numeric,
  add column if not exists max_profit_per_trade numeric;

-- Bulk-Vorlagen tragen die Limits mit
alter table public.account_templates
  add column if not exists max_loss_per_trade  numeric,
  add column if not exists max_profit_per_trade numeric;

comment on column public.accounts.max_daily_drawdown   is 'Max Daily Loss ($) — optional beim Anlegen (seit 28.07.2026 abends; war kurz Pflicht)';
comment on column public.accounts.max_loss_per_trade   is 'Max Loss pro Trade ($) — optional beim Anlegen (seit 28.07.2026 abends; war kurz Pflicht)';
comment on column public.accounts.max_profit_per_trade is 'Max Profit pro Trade ($) — optional beim Anlegen (seit 28.07.2026 abends; war kurz Pflicht)';
