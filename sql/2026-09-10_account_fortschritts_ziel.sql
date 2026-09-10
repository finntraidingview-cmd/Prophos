-- 2026-09-10 — Fortschritts-Ziel pro Account (Finn: "man weiß nie, wie viele
-- Winning Days mir noch fehlen"). Zwei Zieltypen: winning_days (Tag zählt bei
-- positivem Tages-P&L bzw. >= goal_min_profit, z.B. Apex $50) und trading_days
-- (jeder Tag mit mindestens einem realisierten Trade zählt — auch die
-- 0,01-Evertrades). Der Zählstand selbst wird NICHT persistiert — das Frontend
-- leitet ihn live aus trade_plans ab (master_pl/slave_pl, completed+review,
-- Berlin-Tag, gleiche Doktrin wie tagesPlFuer). Hier liegt nur die Konfiguration.
alter table public.accounts
  add column if not exists goal_kind        text,      -- 'winning_days' | 'trading_days' | null = kein Ziel
  add column if not exists goal_target      integer,   -- z.B. 5 ("3 von 5 Winning Days")
  add column if not exists goal_min_profit  numeric,   -- Mindest-Tagesgewinn für einen Winning Day (optional)
  add column if not exists goal_done_offset integer,   -- außerhalb von Prophos erreichte Tage (darf negativ sein)
  add column if not exists goal_since       date;      -- Tage davor zählen nicht (z.B. nach Payout auf heute setzen)
