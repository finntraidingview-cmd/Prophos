-- UNT5 (05.11.2026, Master/Finn: „Finn + Pascal sehen als HT-Admins nichts von Emin, und Emin sieht nichts von HT") — NICHT eingespielt (Master, auf Finns Wort).
-- prophos_fremd_konflikte() (nur service_role, Railway fp_tick) paarte eine Hand-Position mit Plänen/Hand-Positionen derselben Firma über ALLE IDs —
-- eine HT-Hand-Position gegen einen Emin-Plan war ein „Gegenhedge", Push an beide Besitzer + HT-Admins mit Konto- und Personennamen des anderen
-- Unternehmens. Neu: beide Joins nur innerhalb eines Unternehmens (prophos_gruppe_von); ohne Unternehmen nur dieselbe ID. Sonst zeichengleich.
-- Railway filtert seit UNT5 schon selbst (fp_tick, ap_unternehmen_schluessel) — diese Datei macht es auch in der DB fest. Reihenfolge egal.
-- Live-md5 vorher: 9bb3a0198249043c7a3ed3cfdfbdb44f. Rückbau: sql/2026-11-05_unt5_fremd_konflikte_rueckbau.sql.
begin;
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
          -- UNT5: nur innerhalb eines Unternehmens (prophos_gruppe_von wie die DB-Riegel); ohne Unternehmen (null) nur dieselbe ID
          and (p.user_id = f.user_id
               or (public.prophos_gruppe_von(f.user_id) is not null
                   and public.prophos_gruppe_von(p.user_id) = public.prophos_gruppe_von(f.user_id)))
  union all
  select f.id, 'hand'::text, g.id::text, g.user_id, g.konto_name, g.richtung, g.seit
    from f
    join public.fremd_positionen g
      on g.firma_key = f.firma_key and g.richtung <> f.richtung and g.id <> f.id
     and g.konto_id is distinct from f.konto_id
     and g.seit between f.seit - w and f.seit + w
     and (g.user_id = f.user_id
          or (public.prophos_gruppe_von(f.user_id) is not null
              and public.prophos_gruppe_von(g.user_id) = public.prophos_gruppe_von(f.user_id)));
end $function$;
revoke all on function public.prophos_fremd_konflikte() from public, anon, authenticated;
grant execute on function public.prophos_fremd_konflikte() to service_role;
commit;

-- Kontrolle (nur lesen, als Service-Rolle): kein Paar über Unternehmen
--   select k.* from public.prophos_fremd_konflikte() k join public.fremd_positionen f on f.id = k.fremd_id
--    where k.gegen_user <> f.user_id and public.prophos_gruppe_von(k.gegen_user) is distinct from public.prophos_gruppe_von(f.user_id);   -- 0 Zeilen
--   select has_function_privilege('authenticated', 'public.prophos_fremd_konflikte()', 'execute');   -- false (wie vorher)
