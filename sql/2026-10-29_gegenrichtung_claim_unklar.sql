-- ============================================================================
-- Prophos: GEGENRICHTUNG — AUCH LAUFENDE STARTS UND UNKLARE STARTS SPERREN (30.10.2026)
--
-- Finn 29.10.2026 („ganz wichtig", „auf gar keinen Fall ein interner Hedge" = gleiche ID × gleiche Firma gleichzeitig Long und Short).
-- Audit Slave 1 (richtungsschutz-audit.md, Simulation S2): prophos_gegenrichtung_frei_konto zählte nur status open/review. Ein Plan,
-- dessen Start gerade läuft (geclaimt, noch planned) oder UNKLAR endete (Order vielleicht im Markt, Plan bleibt planned), sperrte nur
-- 90 s über prophos_gegenhedge_konflikt — danach durfte die Gegenrichtung derselben ID × Firma claimen, und auch das Panel am PC
-- (richtung_frei → /richtung/frei → prophos_gegenrichtung_frei) sagte „frei".
--
-- Neu in prophos_gegenrichtung_frei_konto, sonst 1:1 die Live-Fassung (Signatur, Rückgabe, 72 h, review/gelesen unverändert):
--   (1) START LÄUFT: status planned, Start-Claim (start_um_gestartet_at / orbit_gesendet_at, der jüngere) ≤ 15 min alt, Claim-Art nicht
--       'verbrauch' (verpasst/Archiv/Manuelle Arbeit/Ziel erreicht startet nie). Ausnahme wie im Tab (rkZaehlt): ein Start-Fehler NACH
--       diesem Claim, der nicht unklar ist, beweist „nichts gesendet" → sperrt nicht.
--   (2) UNKLAR: status planned und mt5_baseline.puls_unklar gesetzt (Orbit/Nova) oder start_fehler.unklar = true mit status ≠ behoben
--       (auch Echo v2order) — OHNE Zeitgrenze, bis die Marke gelöst ist oder der Plan planned verlässt (open sperrt dann wie bisher,
--       completed/gelöscht gibt frei).
-- Wirkt überall, wo die Regel gilt: Claim-Trigger trade_plans_gegenhedge (über prophos_gegenrichtung_frei), order_signale_gegenrichtung,
-- Railway /richtung/frei (Panel vor jedem scharfen Klick, seit 30.10.2026 auch Echo /api/master-order), Planer „Richtung drehen"
-- (ap_richtung_plan_pruefen), Polar-Riegel. prophos_gegenhedge_konflikt (90-s-Fenster, andere IDs, Hand-Positionen, Schlange) ist
-- unverändert — es ruft diese Funktion nicht.
--
-- RÜCKNAHME (Live-Fassung bis 30.10.2026, sql/2026-10-19_gegenrichtung_review_gelesen.sql):
--   create or replace function public.prophos_gegenrichtung_frei_konto(p_user uuid, p_firma text, p_richtung text, p_ausser_plan uuid default null, p_ausser_konto uuid default null)
--    returns jsonb language plpgsql stable security definer set search_path to 'public' as $function$
--   declare r text; gegen text; k text; g record;
--   begin
--     r := lower(btrim(coalesce(p_richtung, '')));
--     r := case when r in ('buy', 'long', 'kauf') then 'buy' when r in ('sell', 'short', 'verkauf') then 'sell' else null end;
--     gegen := case r when 'buy' then 'sell' when 'sell' then 'buy' else null end;
--     if p_user is null or gegen is null or coalesce(btrim(p_firma), '') = '' then
--       return jsonb_build_object('frei', true, 'grund', 'keine Richtung/Firma');
--     end if;
--     k := public.prophos_firma_key(p_firma);
--     select p.id, p.master_name, p.user_id, p.status, coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) as seit into g
--       from public.trade_plans p
--      where (p_ausser_plan is null or p.id <> p_ausser_plan) and p.user_id = p_user
--        and (p_ausser_konto is null or p.master_account_id is null or p.master_account_id is distinct from p_ausser_konto)
--        and p.richtung = gegen and p.status in ('open', 'review') and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))
--        and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours'
--        and public.prophos_firma_key(p.master_firm) = k
--      order by 5 desc limit 1;
--     if g.id is null then return jsonb_build_object('frei', true, 'firma', k, 'richtung', r); end if;
--     return jsonb_build_object('frei', false, 'firma', k, 'richtung', r, 'plan', g.id, 'wer', 'dein Konto', 'user_id', p_user,
--       'grund', '„' || coalesce(g.master_name, 'Konto') || '“ ' || case when g.status = 'review' then 'ist dort zu Ende, aber noch nicht gelesen' else 'läuft dort' end
--                || coalesce(' (seit ' || to_char(g.seit at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)', '') || ' ' || upper(case gegen when 'buy' then 'long' else 'short' end)
--                || ' — ' || upper(case r when 'buy' then 'long' else 'short' end) || ' wäre die Gegenrichtung (Selbst-Hedge). Gesperrt, bis '
--                || case when g.status = 'review' then 'die Endlesung da ist' else 'er zu und gelesen ist' end);
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
