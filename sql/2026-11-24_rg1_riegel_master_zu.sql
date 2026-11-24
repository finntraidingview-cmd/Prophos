-- RG1 (24.11.2026, KC1-Befund D2, Auftrag Master nach Finns Go „A + B bauen“) — idempotent, NICHT selbst einspielen (Prüfer, dann Master).
--
-- Anlass: Simon FundedNext 100k …9853 (Plan 0a1e29c4, mt5, SELL 23.11. 08:13–08:15 UTC) sperrte per Riegel Gegenrichtung das Schwesterkonto …9852
-- (24 Versuche „Schwesterkonto zu Ende, aber noch nicht gelesen“), obwohl der Master nachweislich zu und gelesen war (final.master_balance 99.930,73,
-- master_pl −69,27). Er stand nur in „Überprüfen“, weil der Hedge-P&L fehlte (abhaken_vorgemerkt „Hedge-P&L fehlt“). prophos_plan_gelesen verlangt
-- für mt5/mt5v2 die Balance-Nachlesung bal_nach.ok — die gab es hier nicht. Bis zu 72 h Sperre ohne Grund.
--
-- A) prophos_plan_master_zu(plan): NUR für den Riegel (prophos_plan_gelesen bleibt unverändert, es wird anderswo benutzt). Echo-Plan (mt5/mt5v2)
--    im Status review gilt als zu, wenn ALLES belegt ist: ended_at, master_pl gesetzt, final.master_balance > 0 (Copier-Schluss mit Master-Balance),
--    kein UNKLAR (puls_unklar, start_fehler unklar, final.art unklar) und laut mt5_live/mt5_live_flotte KEINE offene Master-Position für den Login
--    des Kontos (Zeile mit nicht leerer status.master_positions → nicht zu). Fehlt nur der Hedge-P&L, sperrt der Plan damit nicht mehr.
-- B) prophos_riegel_alt(stunden): welche heute geplanten Pläne sperrt der Riegel gerade über einen review-/UNKLAR-Plan, der älter als `stunden` ist
--    oder vom Vortag (Dubai) stammt? Für die 🟠-Meldung aus app.py (rg1_tick, einmal je sperrendem Plan). Liest nur, ändert nichts — die Sperre bleibt.

create or replace function public.prophos_plan_master_zu(p_plan uuid)
returns boolean
language plpgsql
stable security definer
set search_path to 'public'
as $function$
declare
  p record;
  fin jsonb;
  login text;
  zahl constant text := '^-?[0-9]+(\.[0-9]+)?$';
begin
  select tp.status, tp.route, tp.ended_at, tp.master_pl, tp.mt5_baseline, a.cred_login, a.external_id
    into p
    from public.trade_plans tp left join public.accounts a on a.id = tp.master_account_id
   where tp.id = p_plan;
  if not found or p.status is distinct from 'review' or p.route not in ('mt5', 'mt5v2') or p.ended_at is null or p.master_pl is null then
    return false;
  end if;
  fin := case when jsonb_typeof(p.mt5_baseline->'final') = 'object' then p.mt5_baseline->'final' end;
  if fin is null or not (coalesce(fin->>'master_balance', '') ~ zahl and (fin->>'master_balance')::numeric > 0) then
    return false;
  end if;
  -- nie bei UNKLAR (Order kann liegen)
  if (p.mt5_baseline ? 'puls_unklar' and p.mt5_baseline->'puls_unklar' is distinct from 'null'::jsonb)
     or (jsonb_typeof(p.mt5_baseline->'start_fehler') = 'object' and p.mt5_baseline->'start_fehler'->>'unklar' = 'true')
     or fin->>'art' = 'unklar' then
    return false;
  end if;
  -- keine offene Master-Position laut Live-Stand des Copiers (beide Tabellen; ohne Zeile gilt der Schluss aus final)
  login := regexp_replace(coalesce(nullif(btrim(p.cred_login), ''), p.external_id, ''), '[^0-9]', '', 'g');
  if login <> '' and (
       exists (select 1 from public.mt5_live l
                where regexp_replace(coalesce(l.master_login::text, ''), '[^0-9]', '', 'g') = login
                  and jsonb_typeof(l.status->'master_positions') = 'array' and jsonb_array_length(l.status->'master_positions') > 0)
    or (to_regclass('public.mt5_live_flotte') is not null and exists (select 1 from public.mt5_live_flotte l
                where regexp_replace(coalesce(l.master_login::text, ''), '[^0-9]', '', 'g') = login
                  and jsonb_typeof(l.status->'master_positions') = 'array' and jsonb_array_length(l.status->'master_positions') > 0))
  ) then
    return false;
  end if;
  return true;
end $function$;

-- Riegel: wie live (Stand 24.11.2026), einzige Änderung in der review-Zeile: „gelesen ODER Master zu“
create or replace function public.prophos_gegenrichtung_frei_konto(p_user uuid, p_firma text, p_richtung text, p_ausser_plan uuid default null::uuid, p_ausser_konto uuid default null::uuid)
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
           (p.status in ('open', 'review')
            -- RG1 (24.11.2026): review zählt nicht mehr, wenn gelesen ODER der Echo-Master belegt zu ist (prophos_plan_master_zu)
            and not (p.status = 'review' and (public.prophos_plan_gelesen(p.id) or public.prophos_plan_master_zu(p.id)))
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
         and not (p.status in ('planned', 'review') and public.prophos_plan_nichts_gesendet(p.id))
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
    'seit', g.seit,
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

-- B) Alte Sperren für die 🟠-Meldung (app.py rg1_tick): heute (Dubai) geplante Pläne, die der Riegel über einen review-/UNKLAR-Plan sperrt, der älter
--    als p_stunden ist oder vom Vortag stammt. Nur lesen.
create or replace function public.prophos_riegel_alt(p_stunden numeric default 6)
returns table (gesperrt_plan uuid, sperrt_plan uuid, art text, seit timestamptz, grund text)
language plpgsql
stable security definer
set search_path to 'public'
as $function$
declare
  q record;
  f jsonb;
  heute date := (now() at time zone 'Asia/Dubai')::date;
  s timestamptz;
begin
  for q in select tp.id from public.trade_plans tp
            where tp.status = 'planned' and tp.planned_for = heute and tp.richtung in ('buy', 'sell')
  loop
    f := public.prophos_gegenrichtung_frei(q.id, null);
    if coalesce((f->>'frei')::boolean, true) or f->>'art' not in ('review', 'unklar') or coalesce(f->>'plan', '') = '' then
      continue;
    end if;
    s := nullif(f->>'seit', '')::timestamptz;
    -- Prüfer RG1: bei review zählt das Alter ab dem ENDE (ab da sperrt er als „ungelesen“), nicht ab dem Start — sonst Fehlalarm, sobald ein
    -- vor > 6 h gestarteter Plan in review geht; bei unklar ab dem Start (seit)
    if f->>'art' = 'review' then
      select coalesce(tp.ended_at, s) into s from public.trade_plans tp where tp.id = (f->>'plan')::uuid;
    end if;
    if s is null or (s > now() - make_interval(secs => p_stunden * 3600) and (s at time zone 'Asia/Dubai')::date >= heute) then
      continue;
    end if;
    gesperrt_plan := q.id; sperrt_plan := (f->>'plan')::uuid; art := f->>'art'; seit := s; grund := f->>'grund';
    return next;
  end loop;
end $function$;

-- Prüfer RG1: security definer → nur der Dienst (Railway) darf; die Default-ACL gäbe EXECUTE an PUBLIC/anon/authenticated (wie FP1 entziehen)
revoke all on function public.prophos_plan_master_zu(uuid) from public, anon, authenticated;
revoke all on function public.prophos_riegel_alt(numeric) from public, anon, authenticated;
grant execute on function public.prophos_plan_master_zu(uuid) to service_role;
grant execute on function public.prophos_riegel_alt(numeric) to service_role;
