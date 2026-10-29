-- ============================================================================
-- Prophos: GEGENRICHTUNG — AUCH HAND-POSITIONEN OHNE PLAN SPERREN (30.10.2026, RICHTUNG-E)
--
-- Finn: „auf gar keinen Fall ein interner Hedge" (gleiche ID × gleiche Firma gleichzeitig Long und Short). S2 bei der Prüfung von Lücke D:
-- prophos_gegenhedge_konflikt zählt fremd_positionen nur 90 s ab seit, der harte Riegel prophos_gegenrichtung_frei_konto gar nicht. Liegt
-- bei derselben ID × Firma eine Hand-Position (ohne Plan, weg_at leer) länger als 90 s Long, durfte ein Plan dort Short starten.
--
-- Neu in prophos_gegenrichtung_frei_konto, sonst 1:1 die Live-Fassung (inkl. Claim/UNKLAR aus sql/2026-10-29_gegenrichtung_claim_unklar.sql,
-- eingespielt 30.10.2026):
--   (3) erst wenn kein Plan sperrt: fremd_positionen mit user_id = p_user, firma_key = k, richtung = gegen, weg_at is null und
--       seit > now() − 72 h ODER zuletzt_gesehen > now() − 30 min (eine sichtbar laufende Hand-Position sperrt egal wie alt).
--       Antwort art 'hand', plan null, Grund „Hand-Position „…“ läuft dort seit … — gesperrt, bis die Position zu ist".
--   Konto wird NICHT ausgenommen (anders als bei Plänen): eine Gegen-Order aufs selbe Konto mit unbekannter Hand-Position ist nie gewollt.
--   fremd_positionen.firma_key ist eine generierte Spalte = prophos_firma_key(firma) → derselbe Schlüssel wie bei den Plänen.
-- Simulation (DO-Block, neue Fassung per execute, Test-ID, am Ende Exception → zurückgerollt): Hand LONG seit 2 h, eben gesehen → SHORT
-- gesperrt (art hand), Claim abgewiesen · gleiche Richtung frei · weg_at gesetzt frei · Leiche (5 Tage, 5 Tage nicht gesehen) frei · 5 Tage alt,
-- vor 5 min gesehen → gesperrt · andere Firma frei · andere ID frei · laufender Plan sperrt weiter (art open).
-- Live-Stand 30.10.2026 (nur gelesen): 5 offene Zeilen (weg_at leer), alle Leichen vom 09.–23.10. (seit > 72 h, zuletzt gesehen am selben Tag)
-- → keine sperrt. Davon HT: Aurel Tradeify SELL 23.10., Finn + Pascal MFF SELL 13.10., Moritz Apex SELL 09.10.; Emin-Gruppe: Emin Tradeify 2×.
-- Wirkt überall, wo die Regel gilt: Claim-Trigger trade_plans_gegenhedge, order_signale_gegenrichtung, Railway /richtung/frei (Panel vor
-- jedem scharfen Klick: Orbit, Nova, Echo), Planer „Richtung drehen", Polar-Riegel. prophos_gegenhedge_konflikt unverändert.
--
-- RÜCKNAHME (Live-Fassung bis 30.10.2026 = sql/2026-10-29_gegenrichtung_claim_unklar.sql):
--   create or replace function public.prophos_gegenrichtung_frei_konto(p_user uuid, p_firma text, p_richtung text, p_ausser_plan uuid default null, p_ausser_konto uuid default null)
--    returns jsonb
--    language plpgsql
--    stable security definer
--    set search_path to 'public'
--   as $function$
--   declare
--     r text;
--     gegen text;
--     k text;
--     g record;
--   begin
--     r := lower(btrim(coalesce(p_richtung, '')));
--     r := case when r in ('buy', 'long', 'kauf') then 'buy' when r in ('sell', 'short', 'verkauf') then 'sell' else null end;
--     gegen := case r when 'buy' then 'sell' when 'sell' then 'buy' else null end;
--     if p_user is null or gegen is null or coalesce(btrim(p_firma), '') = '' then
--       return jsonb_build_object('frei', true, 'grund', 'keine Richtung/Firma');
--     end if;
--     k := public.prophos_firma_key(p_firma);
--     select x.id, x.master_name, x.user_id, x.status, x.seit, x.art
--       into g
--       from (
--         select p.id, p.master_name, p.user_id, p.status,
--                coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) as seit,
--                case when p.status in ('open', 'review') then p.status
--                     when (p.mt5_baseline ? 'puls_unklar' and p.mt5_baseline->'puls_unklar' is distinct from 'null'::jsonb)
--                          or (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object'
--                              and p.mt5_baseline->'start_fehler'->>'unklar' = 'true'
--                              and p.mt5_baseline->'start_fehler'->>'status' is distinct from 'behoben') then 'unklar'
--                     else 'startet' end as art
--           from public.trade_plans p
--          where (p_ausser_plan is null or p.id <> p_ausser_plan)
--            and p.user_id = p_user
--            and (p_ausser_konto is null or p.master_account_id is null or p.master_account_id is distinct from p_ausser_konto)
--            and p.richtung = gegen
--            and public.prophos_firma_key(p.master_firm) = k
--            and (
--              -- wie bisher: läuft oder zu Ende ohne Endlesung (72 h)
--              (p.status in ('open', 'review')
--               and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))
--               and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours')
--              -- (2) UNKLAR: Order vielleicht im Markt — ohne Zeitgrenze, bis gelöst
--              or (p.status = 'planned'
--                  and ((p.mt5_baseline ? 'puls_unklar' and p.mt5_baseline->'puls_unklar' is distinct from 'null'::jsonb)
--                       or (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object'
--                           and p.mt5_baseline->'start_fehler'->>'unklar' = 'true'
--                           and p.mt5_baseline->'start_fehler'->>'status' is distinct from 'behoben')))
--              -- (1) START LÄUFT: echter Start-Claim ≤ 15 min, kein Verbrauch, kein bewiesener Fehlstart nach diesem Claim
--              or (p.status = 'planned'
--                  and coalesce(p.start_claim_art, 'start') <> 'verbrauch'
--                  and greatest(p.start_um_gestartet_at, p.orbit_gesendet_at) > now() - interval '15 minutes'
--                  and not (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object'
--                           and coalesce(p.mt5_baseline->'start_fehler'->>'unklar', 'false') <> 'true'
--                           and p.mt5_baseline->'start_fehler'->>'status' is distinct from 'behoben'
--                           and coalesce(p.mt5_baseline->'start_fehler'->>'at', '') ~ '^\d{4}-\d{2}-\d{2}'
--                           and (p.mt5_baseline->'start_fehler'->>'at')::timestamptz >= greatest(p.start_um_gestartet_at, p.orbit_gesendet_at)))
--            )
--       ) x
--      order by x.seit desc
--      limit 1;
--     if g.id is null then
--       return jsonb_build_object('frei', true, 'firma', k, 'richtung', r);
--     end if;
--     return jsonb_build_object('frei', false, 'firma', k, 'richtung', r, 'plan', g.id, 'wer', 'dein Konto', 'user_id', p_user, 'art', g.art,
--       'grund', '„' || coalesce(g.master_name, 'Konto') || '“ '
--                || case g.art when 'review' then 'ist dort zu Ende, aber noch nicht gelesen'
--                              when 'unklar' then 'hat dort einen UNKLAREN Start (Order liegt vielleicht)'
--                              when 'startet' then 'startet dort gerade'
--                              else 'läuft dort' end
--                || coalesce(' (seit ' || to_char(g.seit at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)', '')
--                || ' ' || upper(case gegen when 'buy' then 'long' else 'short' end)
--                || ' — ' || upper(case r when 'buy' then 'long' else 'short' end) || ' wäre die Gegenrichtung (Selbst-Hedge). Gesperrt, bis '
--                || case g.art when 'review' then 'die Endlesung da ist'
--                              when 'unklar' then 'die UNKLAR-Marke gelöst ist (in der Plattform nachsehen, auf der Karte lösen)'
--                              when 'startet' then 'der Start durch ist und er zu und gelesen ist'
--                              else 'er zu und gelesen ist' end);
--   end $function$;
-- ============================================================================

create or replace function public.prophos_gegenrichtung_frei_konto(p_user uuid, p_firma text, p_richtung text, p_ausser_plan uuid default null, p_ausser_konto uuid default null)
 returns jsonb
 language plpgsql
 stable security definer
 set search_path to 'public'
as $function$
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
           -- wie bisher: läuft oder zu Ende ohne Endlesung (72 h)
           (p.status in ('open', 'review')
            and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))
            and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours')
           -- (2) UNKLAR: Order vielleicht im Markt — ohne Zeitgrenze, bis gelöst
           or (p.status = 'planned'
               and ((p.mt5_baseline ? 'puls_unklar' and p.mt5_baseline->'puls_unklar' is distinct from 'null'::jsonb)
                    or (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object'
                        and p.mt5_baseline->'start_fehler'->>'unklar' = 'true'
                        and p.mt5_baseline->'start_fehler'->>'status' is distinct from 'behoben')))
           -- (1) START LÄUFT: echter Start-Claim ≤ 15 min, kein Verbrauch, kein bewiesener Fehlstart nach diesem Claim
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
    -- (3) HAND-POSITION (30.10.2026, RICHTUNG-E): offene Position ohne Plan derselben ID × Firma in Gegenrichtung (fremd_positionen, weg_at
    -- leer) — eröffnet in den letzten 72 h ODER in den letzten 30 min noch gesehen (läuft sichtbar, egal wie alt). Alte Leichen (weder
    -- frisch eröffnet noch gesehen) sperren nicht. Ohne Tabelle (Altstand) nichts.
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
