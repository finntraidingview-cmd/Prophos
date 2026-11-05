-- RÜCKBAU zu sql/2026-11-05_unt5_fremd_konflikte.sql: Live-Fassung von prophos_fremd_konflikte() am 05.11.2026 (pg_get_functiondef, md5 9bb3a0198249043c7a3ed3cfdfbdb44f).
CREATE OR REPLACE FUNCTION public.prophos_fremd_konflikte()
 RETURNS TABLE(fremd_id bigint, art text, gegen_id text, gegen_user uuid, gegen_konto text, gegen_richtung text, gegen_seit timestamp with time zone)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  w interval := interval '90 seconds';
begin
  if to_regprocedure('public.prophos_gegenhedge_fenster()') is not null then
    execute 'select public.prophos_gegenhedge_fenster()' into w;
  end if;
  return query
  with f as (
    select * from public.fremd_positionen x
     where x.weg_at is null and x.zuletzt_gesehen > now() - interval '3 minutes'
  ), p as (
    select t.id, t.user_id, t.master_name, t.master_account_id, t.richtung,
           public.prophos_firma_key(t.master_firm) as firma_key,
           coalesce(t.started_at, t.orbit_gesendet_at) as start
      from public.trade_plans t
     where t.status in ('planned', 'open', 'review', 'completed')
       and coalesce(t.started_at, t.orbit_gesendet_at) > now() - interval '1 day'
       and not (t.started_at is null
                and t.mt5_baseline ? 'start_fehler'
                and coalesce(t.mt5_baseline->'start_fehler'->>'unklar', 'false') <> 'true'
                and coalesce(t.mt5_baseline->'start_fehler'->>'status', '') <> 'behoben')
  )
  select f.id, 'plan'::text, p.id::text, p.user_id, p.master_name, p.richtung, p.start
    from f
    join p on p.firma_key = f.firma_key
          and p.richtung = case f.richtung when 'buy' then 'sell' else 'buy' end
          and p.master_account_id is distinct from f.konto_id
          and p.start between f.seit - w and f.seit + w
  union all
  select f.id, 'hand'::text, g.id::text, g.user_id, g.konto_name, g.richtung, g.seit
    from f
    join public.fremd_positionen g
      on g.firma_key = f.firma_key and g.richtung <> f.richtung and g.id <> f.id
     and g.konto_id is distinct from f.konto_id
     and g.seit between f.seit - w and f.seit + w;
end $function$;
