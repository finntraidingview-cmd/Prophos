-- R4c GEGENRICHTUNG: SCHWESTER-PLAN MIT BELEG „NICHTS GESENDET“ SPERRT NICHT (Master 05.11.2026, Befund S7 R4 (3)):
-- Marco Tradeify CFD …115952 (b98697dc, 04.11. 08:58 Dubai, PC von Marco pc-t8wg97): das Panel brach VOR dem Bot ab — „Riegel-Prüfung (Gegenrichtung)
-- nicht erreichbar: <urlopen error [Errno 11001] getaddrinfo failed> — nichts gesendet“ (mt5-copier/panel.py richtung_frei, code riegel_unerreichbar,
-- fail-closed: der Bot wird gar nicht gestartet). Der Plan stand trotzdem 13 h als UNKLAR bzw. „zu Ende, aber nicht gelesen“ und sperrte über
-- prophos_gegenrichtung_frei_konto das Schwesterkonto …116895 (16 × geschoben, dann in die Index-Pause).
-- NUR der Gegenrichtungs-Riegel: ein Schwester-Plan zählt nicht als UNKLAR/offen, wenn prophos_plan_nichts_gesendet(id) — eindeutiger Beleg, dass für den
-- LETZTEN Claim keine Order raus ist. Das Nachhol-Verhalten (start_fehler, sfTick, Tagesreset, P1 .2040) bleibt unverändert; die Marke am Plan bleibt.
-- Beleg (alle Bedingungen):
--   • nie gestartet: started_at und orbit_gesendet_at leer, status planned oder review, master_pl leer oder 0
--   • Puls-Antwort dieses Claims (puls_spur.at ≥ Claim − 5 s) mit ok = false und leerer Spur (kein Klick-Protokoll), deren KOPF ein Panel-Abbruch VOR
--     dem Bot ist: „Riegel-Prüfung (Gegenrichtung) nicht erreichbar|möglich … nichts gesendet“ oder „Gegenrichtung gesperrt:“ (panel.py richtung_frei)
--   • keine Spur einer Order: kein order_signale-Eintrag mit gesendet/ok true, keine puls_ergebnisse-Order mit gesendet/ok true, kein ticket, hedge,
--     puls_unklar, live, echo_pos_gesehen_at, schon_zu am Plan
-- Kein Beleg (z. B. Chris …117784 am 04.11.: „keine Order-Antwort und Master-Konto nicht lesbar“, keine puls_spur) → bleibt UNKLAR und sperrt wie bisher.
-- Idempotent (create or replace). Rückbau: sql/2026-11-05_gegenrichtung_nichts_gesendet_rueckbau.sql (Live-Fassung, md5 05.11.2026 d6c1f7d508a4d0d2fad8def2994834dd —
-- vor dem Einspielen pg_get_functiondef sichern). NICHT vom Slave eingespielt.

create or replace function public.prophos_plan_nichts_gesendet(p_plan uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((
    select p.started_at is null and p.orbit_gesendet_at is null and p.status in ('planned', 'review')
       and coalesce(p.master_pl, 0) = 0
       and p.start_um_gestartet_at is not null
       and jsonb_typeof(p.mt5_baseline->'puls_spur') = 'object'
       and p.mt5_baseline->'puls_spur'->>'ok' = 'false'
       and coalesce(p.mt5_baseline->'puls_spur'->>'trail', '') = ''
       and coalesce(p.mt5_baseline->'puls_spur'->>'at', '') ~ '^\d{4}-\d{2}-\d{2}'
       and (p.mt5_baseline->'puls_spur'->>'at')::timestamptz >= p.start_um_gestartet_at - interval '5 seconds'
       and (   (p.mt5_baseline->'puls_spur'->>'msg') ~* '^Riegel-Prüfung \(Gegenrichtung\) nicht (erreichbar|möglich):.*nichts gesendet'
            or (p.mt5_baseline->'puls_spur'->>'msg') ~ '^Gegenrichtung gesperrt:')
       and not (p.mt5_baseline ?| array['ticket', 'hedge', 'puls_unklar', 'live', 'echo_pos_gesehen_at', 'schon_zu'])
       and not exists (select 1 from public.order_signale o where o.plan_id = p.id::text
                        and (o.ergebnis->>'gesendet' = 'true' or o.ergebnis->>'ok' = 'true'))
       and not exists (select 1 from public.puls_ergebnisse e where e.plan_id = p.id::text and e.art = 'order'
                        and (e.ergebnis->>'gesendet' = 'true' or e.ergebnis->>'ok' = 'true'))
      from public.trade_plans p where p.id = p_plan), false)
$$;

create or replace function public.prophos_gegenrichtung_frei_konto(p_user uuid, p_firma text, p_richtung text, p_ausser_plan uuid DEFAULT NULL::uuid, p_ausser_konto uuid DEFAULT NULL::uuid)
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
         -- R4c: eindeutig nichts gesendet (Panel-Abbruch vor dem Bot, keine Order-Spur) → sperrt die Gegenrichtung nicht
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

revoke all on function public.prophos_plan_nichts_gesendet(uuid) from public, anon, authenticated;
grant execute on function public.prophos_plan_nichts_gesendet(uuid) to service_role;

-- Proben (SQL-Editor, nur lesen):
-- select public.prophos_plan_nichts_gesendet('b98697dc-a571-4b05-9a00-538209e58731');  -- Marco …115952 04.11. → true (Panel-Abbruch, DNS)
-- select public.prophos_plan_nichts_gesendet('dc66f1f4-81a4-4d23-ab74-f692fa06e102');  -- Chris …117784 04.11. → false (keine Antwort = kein Beleg)
