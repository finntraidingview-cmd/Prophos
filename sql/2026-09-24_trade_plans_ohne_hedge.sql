-- 2026-09-24: trade_plans.ohne_hedge — explizite Markierung „kein Gegen-Hedge" je Trade.
-- Finn (24.09.2026, Nachtrag zum Kapitel-Feature): „Alle Trades, die über Echo V2 und Orbit V2
-- gestartet werden, sind ab jetzt ohne Gegenhedge. Vielleicht kann man es in die Datenbank mit
-- einwerten." Die V2-Wege (route mt5v2 = Echo V2, tvv2 = Orbit V2) platzieren per Definition nur
-- die Master-Order — kein Slave, kein Copier, kein Duplikum-Push (siehe .436, 23.09.2026).
--
-- Generierte Spalte statt Trigger/Handpflege: sie leitet sich immer aus route ab, kann also nicht
-- driften und braucht keine Frontend-Änderung. Auswertungen (Admin-Kapitel-Vergleich) zählen
-- damit „Trades ohne Hedge" direkt. Kommt ein weiterer hedgefreier Weg dazu, wird nur die
-- Liste hier erweitert. Das Kapitel (kapitel_id) bleibt davon unabhängig rein zeitlich.
-- coalesce: 1.342 Altpläne haben route = null (vor dem Routen-Feld, bis 14.08.2026) — ohne
-- coalesce wäre ohne_hedge dort null statt false (im ersten Lauf am 24.09. so passiert).
drop index if exists public.trade_plans_ohne_hedge_idx;
alter table public.trade_plans drop column if exists ohne_hedge;
alter table public.trade_plans
  add column ohne_hedge boolean
  generated always as (coalesce(route, '') in ('mt5v2','tvv2')) stored;

create index if not exists trade_plans_ohne_hedge_idx
  on public.trade_plans (user_id, ohne_hedge);

-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
