-- RÜCKBAU zu sql/2026-11-05_gegenrichtung_nichts_gesendet.sql: Live-Fassung von prophos_gegenrichtung_frei_konto am 05.11.2026 (pg_get_functiondef, md5 d6c1f7d508a4d0d2fad8def2994834dd).
-- Einspielen stellt den Stand vor R4c wieder her; prophos_plan_nichts_gesendet bleibt dann ungenutzt liegen (drop optional).
CREATE OR REPLACE FUNCTION public.prophos_gegenrichtung_frei_konto(p_user uuid, p_firma text, p_richtung text, p_ausser_plan uuid DEFAULT NULL::uuid, p_ausser_konto uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  r text;
  gegen text;
  k text;
  g record;
  h record;
begin
  r := lower(btrim(coalesce(p_richtung, '')));
  r := case when r in ('buy', 'long', 'kauf') then 'buy' when r in ('sell', 'short', 'verkauf') then 'sell' else null end;
  gegen := case r when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  if p_user is null or gegen is null or coalesce(btrim(p_firma), '') = '' then
    return jsonb_build_object('frei', true, 'grund', 'keine Richtung/Firma');
  end if;
  k := public.prophos_firma_key(p_firma);
  select x.id, x.master_name, x.user_id, x.status, x.seit, x.art
    into g
    from (
      select p.id, p.master_name, p.user_id, p.status,
             coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) as seit,
             case when p.status in ('open', 'review') then p.status
                  when (p.mt5_baseline ? 'puls_unklar' and p.mt5_baseline->'puls_unklar' is distinct from 'null'::jsonb)
                       or (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object'
                           and p.mt5_baseline->'start_fehler'->>'unklar' = 'true'
                           and p.mt5_baseline->'start_fehler'->>'status' is distinct from 'behoben') then 'unklar'
                  else 'startet' end as art
        from public.trade_plans p
       where (p_ausser_plan is null or p.id <> p_ausser_plan)
         and p.user_id = p_user
         and (p_ausser_konto is null or p.master_account_id is null or p.master_account_id is distinct from p_ausser_konto)
         and p.richtung = gegen
         and public.prophos_firma_key(p.master_firm) = k
         and (
           (p.status in ('open', 'review')
            and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))
            and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours')
           or (p.status = 'planned'
               and ((p.mt5_baseline ? 'puls_unklar' and p.mt5_baseline->'puls_unklar' is distinct from 'null'::jsonb)
                    or (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object'
                        and p.mt5_baseline->'start_fehler'->>'unklar' = 'true'
                        and p.mt5_baseline->'start_fehler'->>'status' is distinct from 'behoben')))
           or (p.status = 'planned'
               and coalesce(p.start_claim_art, 'start') <> 'verbrauch'
               and greatest(p.start_um_gestartet_at, p.orbit_gesendet_at) > now() - interval '15 minutes'
               and not (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object'
                        and coalesce(p.mt5_baseline->'start_fehler'->>'unklar', 'false') <> 'true'
                        and p.mt5_baseline->'start_fehler'->>'status' is distinct from 'behoben'
                        and coalesce(p.mt5_baseline->'start_fehler'->>'at', '') ~ '^\d{4}-\d{2}-\d{2}'
                        and (p.mt5_baseline->'start_fehler'->>'at')::timestamptz >= greatest(p.start_um_gestartet_at, p.orbit_gesendet_at)))
         )
    ) x
   order by x.seit desc
   limit 1;
  if g.id is null then
    if to_regclass('public.fremd_positionen') is not null then
      execute 'select f.seit, f.konto_name, f.symbol, f.menge from public.fremd_positionen f
                where f.user_id = $1 and f.firma_key = $2 and f.richtung = $3 and f.weg_at is null
                  and (f.seit > now() - interval ''72 hours'' or f.zuletzt_gesehen > now() - interval ''30 minutes'')
                order by f.seit desc limit 1'
        into h using p_user, k, gegen;
      if h.seit is not null then
        return jsonb_build_object('frei', false, 'firma', k, 'richtung', r, 'plan', null, 'wer', 'Hand-Position', 'user_id', p_user, 'art', 'hand',
          'grund', 'Hand-Position „' || coalesce(h.konto_name, '?') || '“' || coalesce(' (' || h.symbol || coalesce(' × ' || h.menge::text, '') || ')', '')
                   || ' läuft dort seit ' || to_char(h.seit at time zone 'Asia/Dubai', 'DD.MM. HH24:MI') || ' Dubai '
                   || upper(case gegen when 'buy' then 'long' else 'short' end)
                   || ' — ' || upper(case r when 'buy' then 'long' else 'short' end) || ' wäre die Gegenrichtung (Selbst-Hedge). Gesperrt, bis die Position zu ist.');
      end if;
    end if;
    return jsonb_build_object('frei', true, 'firma', k, 'richtung', r);
  end if;
  return jsonb_build_object('frei', false, 'firma', k, 'richtung', r, 'plan', g.id, 'wer', 'dein Konto', 'user_id', p_user, 'art', g.art,
    'grund', '„' || coalesce(g.master_name, 'Konto') || '“ '
             || case g.art when 'review' then 'ist dort zu Ende, aber noch nicht gelesen'
                           when 'unklar' then 'hat dort einen UNKLAREN Start (Order liegt vielleicht)'
                           when 'startet' then 'startet dort gerade'
                           else 'läuft dort' end
             || coalesce(' (seit ' || to_char(g.seit at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)', '')
             || ' ' || upper(case gegen when 'buy' then 'long' else 'short' end)
             || ' — ' || upper(case r when 'buy' then 'long' else 'short' end) || ' wäre die Gegenrichtung (Selbst-Hedge). Gesperrt, bis '
             || case g.art when 'review' then 'die Endlesung da ist'
                           when 'unklar' then 'die UNKLAR-Marke gelöst ist (in der Plattform nachsehen, auf der Karte lösen)'
                           when 'startet' then 'der Start durch ist und er zu und gelesen ist'
                           else 'er zu und gelesen ist' end);
end $function$;
