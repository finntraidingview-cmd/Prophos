-- 2026-09-25: trade_plans.winning_day — Trade ausdrücklich als Winning Day markiert.
-- Finn (Statistik-Tab): „Wir unterscheiden jetzt in Winning Day auch noch, wenn man bei Trade
-- abhakt: dieser Trade ist ein Winning Day. Später auch bei Winning Day Farm, das auch als
-- Winning Day gekennzeichnet wird." Der Haken sitzt im Erledigt-Modal (nur Funded/Live-Master),
-- der Winning-Day-Farmer setzt ihn beim Anlegen seiner Pläne.
-- Auswertung (app.py _hq_typ_trade): true → Typ 'wd', false → Kontotyp (Big Trade),
-- null (Bestand, nie durchs Modal) → Faustregel Master-Risiko < 1.000 $ auf Funded = Winning Day.
alter table public.trade_plans add column if not exists winning_day boolean;
comment on column public.trade_plans.winning_day is
  'Trade ausdrücklich als Winning Day markiert (Erledigt-Modal / Farmer, 25.09.2026). null = unbekannt → Faustregel Master-Risiko < 1.000 $ auf Funded.';
