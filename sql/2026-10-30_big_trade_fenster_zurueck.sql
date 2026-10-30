-- BIG TRADE JE FENSTER ZURÜCK (30.10.2026, Befund S5 „Zwei-Orbit-Analyse"; Auftrag ZWEI-ORBIT Stück 0). Die Fenster-Trennung TradingView /
-- TopstepX vom 27.10. (sql/2026-10-27_big_trade_fenster_topstep.sql, Finn: „Okay, parallel zu Big Trade für Topstep") fehlt live: sie war nie
-- eingespielt (prophos_big_trade_fenster gibt es nicht), und sql/2026-10-30_apex_hedge.sql hat prophos_big_trade_laeuft ohne sie neu angelegt
-- (mit prophos_wd_wie). Folge heute: ein Topstep-Big-Trade (tsv2) und ein Orbit-Big-Trade (tvv2) derselben ID sperren sich gegenseitig 15 min,
-- obwohl jedes Fenster sein eigenes Auge hat (tv-reader.user.js bzw. tsx-auge.user.js).
-- Hier EINE Fassung mit BEIDEN Blöcken: prophos_wd_wie (Apex mit Hedge zählt wie ein Winning Day, kein Big Trade) UND die Fenster-Klausel
-- ('tsx' = route tsv2 · 'tv' = alles andere, auch polar). sql/2026-10-30_apex_hedge.sql trägt seit diesem Commit denselben Funktionstext
-- (Zeichen für Zeichen) — wer prophos_big_trade_laeuft danach neu anlegt, nimmt beide Blöcke mit.
-- Trigger trade_plans_big_trade und RPC prophos_big_trade_halten bleiben unverändert (sie rufen prophos_big_trade_laeuft mit der eigenen Plan-ID).
-- Voraussetzung: prophos_wd_wie (sql/2026-10-30_apex_hedge.sql, live). Wiederholbar.
-- Rückbau: die Fassung aus sql/2026-10-30_apex_hedge.sql vor diesem Commit (ohne Fenster-Klausel) — dann sperrt wieder die ganze ID.

do $pruef$
begin
  perform 'public.prophos_wd_wie(boolean, jsonb)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-30_apex_hedge.sql einspielen (prophos_wd_wie)';
end $pruef$;

create or replace function public.prophos_big_trade_fenster(p_route text) returns text
language sql immutable as $$
  select case when coalesce(p_route, '') = 'tsv2' then 'tsx' else 'tv' end
$$;

CREATE OR REPLACE FUNCTION public.prophos_big_trade_laeuft(p_id uuid, p_user uuid)
 RETURNS TABLE(plan_id uuid, name text, seit timestamp with time zone)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select p.id, p.master_name, coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now())
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and public.prophos_big_trade(p.route, p.hedge_eur, p.orbit_v3, public.prophos_wd_wie(p.winning_day, p.mt5_baseline))
     -- 27.10.2026: nur dasselbe Fenster (TopstepX bzw. TradingView) — ohne eigenen Plan (unbekannte ID) wie bisher die ganze ID
     and (not exists (select 1 from public.trade_plans s where s.id = p_id)
          or public.prophos_big_trade_fenster(p.route) = (select public.prophos_big_trade_fenster(s.route) from public.trade_plans s where s.id = p_id))
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
   order by 3 desc
   limit 1
$function$;
revoke all on function public.prophos_big_trade_laeuft(uuid, uuid) from public;

-- Probe (nur lesen): je ID und Fenster die laufenden Big Trades
-- select user_id, public.prophos_big_trade_fenster(route) fenster, count(*) from public.trade_plans
--  where status = 'open' and public.prophos_big_trade(route, hedge_eur, orbit_v3, public.prophos_wd_wie(winning_day, mt5_baseline)) group by 1, 2;
