-- 2026-09-15 — Manuelle Winning-Day-Zählung für Futures-Funded-Accounts (Finn:
-- "bei jedem Trade, der erledigt wird, ein Kästchen 'Dieser Trade war ein
-- Winning Day' — wenn ich drauf drücke, +1; bei 5 ist der Payout anfragbar").
-- Die automatische Zählung (Tages-P&L aus trade_plans, 10.09.) greift bei
-- Futures nicht verlässlich — der Master-P&L kommt dort nicht sauber an.
-- Deshalb ein zweiter Modus: goal_manual=true → der Zählstand ist
-- goal_done_offset (im Account-Modal als „Stand" editierbar), +1 kommt über
-- das Häkchen im Trade-Abschluss, höchstens einmal pro Berlin-Tag
-- (goal_manual_last). Payout anfragen setzt Stand auf 0.
alter table public.accounts
  add column if not exists goal_manual      boolean not null default false,  -- true = Häkchen-Zählung statt Tages-P&L
  add column if not exists goal_manual_last date;                            -- letzter manuell abgehakter Tag (einmal pro Tag)
