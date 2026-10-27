-- BIG TRADE JE FENSTER: TOPSTEPX UND TRADINGVIEW GETRENNT (27.10.2026, Finn: „Okay, parallel zu Big Trade für Topstep").
--
-- Regel 4 der Hedge-Kategorien (sql/2026-10-12_hedge_kategorien_regel.sql): höchstens EIN Big Trade je Fenster, weil das Auge (Userscript)
-- nur das eingeloggte Konto liest. Bisher war „Fenster" = die ganze ID: ein Topstep-Big-Trade (tsv2 mit Orbit-Hedge) und ein Orbit-Big-Trade
-- (tvv2) derselben ID sperrten sich gegenseitig 15 min. Es sind aber zwei Tabs mit je eigenem Auge: TradingView (tv-reader.user.js →
-- reader-server 8790) und TopstepX (tsx-auge.user.js → Panel /api/tsx-stand). Jetzt zählt nur ein Big Trade im SELBEN Fenster:
--   'tsx' = route tsv2 · 'tv' = alles andere (tvv2, polar — Polar-Master ist Orbit in TradingView).
-- Unverändert: prophos_big_trade (Winning Day nie Big Trade), Trigger/RPC (sie rufen prophos_big_trade_laeuft mit der eigenen Plan-ID).
-- Wiederholbar. Rückbau: die Fassung aus sql/2026-10-12_hedge_kategorien_regel.sql erneut einspielen.

create or replace function public.prophos_big_trade_fenster(p_route text) returns text
language sql immutable as $$
  select case when coalesce(p_route, '') = 'tsv2' then 'tsx' else 'tv' end
$$;

create or replace function public.prophos_big_trade_laeuft(p_id uuid, p_user uuid)
returns table(plan_id uuid, name text, seit timestamptz)
language sql stable security definer set search_path = public as $$
  select p.id, p.master_name, coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now())
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and public.prophos_big_trade(p.route, p.hedge_eur, p.orbit_v3, p.winning_day)
     -- 27.10.2026: nur dasselbe Fenster (TopstepX bzw. TradingView) — ohne eigenen Plan (unbekannte ID) wie bisher die ganze ID
     and (not exists (select 1 from public.trade_plans s where s.id = p_id)
          or public.prophos_big_trade_fenster(p.route) = (select public.prophos_big_trade_fenster(s.route) from public.trade_plans s where s.id = p_id))
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
   order by 3 desc
   limit 1
$$;
revoke all on function public.prophos_big_trade_laeuft(uuid, uuid) from public;

-- Probe (nur lesen): je ID und Fenster die laufenden Big Trades
-- select user_id, public.prophos_big_trade_fenster(route) fenster, count(*) from public.trade_plans
--  where status = 'open' and public.prophos_big_trade(route, hedge_eur, orbit_v3, winning_day) group by 1, 2;
