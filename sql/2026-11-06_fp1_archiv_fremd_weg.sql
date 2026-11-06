-- FP1 GEISTER-HAND-POSITIONEN AUF ARCHIVIERTEN KONTEN (Master 06.11.2026, Nova-Test): der Gegenrichtungs-Riegel blockierte einen Start bei Marco.
-- Grund: fremd_positionen 7573 auf Marcos Topstep-Konto (seit 05.11. als geblowt archiviert), zuletzt gesehen 05.11. 05:26 Dubai, nie weg_at —
-- das archivierte Konto liest kein Reader mehr, also schloss fp_tick (app.py) die Zeile nie. Live waren es 10 solche Geister, alle auf archivierten
-- Konten (5× tsx, 5× tv, zuletzt gesehen 09.10.–05.11.), Bestand per sql 24222d17 bereinigt. Dauerhaft:
--   (a) Trigger auf user_settings (key 'archive'): jedes Konto mit archived = true im geschriebenen Archiv-Blob → offene fremd_positionen dieses
--       Kontos, die ≥ 30 min nicht gesehen wurden, bekommen weg_at (= zuletzt_gesehen, wie die Bereinigung). Frisch gesehene bleiben offen
--       (gleiche Grenze wie (b), Prüfer S2 06.11.: sonst schlösse jedes der häufigen Archiv-Schreiben eine noch lebende Position auf einem
--       „manual“-archivierten Konto bis zum nächsten Reader-Upsert → Riegel in der Lücke frei). Ein Geist, der beim Archivieren noch
--       frisch war, sperrt nach 30 min nicht mehr (b) und wird beim nächsten Archiv-Schreiben geschlossen. Konto-IDs sind global eindeutig, darum ohne Inhaber-Abgleich — wie
--       app.py _ap_archiviert / _archiv_eintrag_entfernen, die das Archiv auch über alle Profile lesen (Gegenprüfung FP1). Das Archiv liegt NUR dort (Tab archiveAccount → archivCloudMerge,
--       Server-Blows/Geblowt-Auge, Abhaken, SQL-Wege per update user_settings) — ein Trigger deckt damit jeden Weg ab, ohne Tab-Änderung
--       (der Tab dürfte fremd_positionen per RLS auch gar nicht schreiben). Fehler im Trigger brechen das Archivieren nie ab (nur warning; Sperr-
--       Wartezeit auf 2 s gedeckelt, sonst könnte statement_timeout der Rolle das Archivieren abbrechen — query_canceled fängt „others“ nicht).
--   (b) prophos_gegenrichtung_frei_konto (Panel/Railway/Planer, Text „Hand-Position … läuft dort seit …“): Hand-Positionen auf archivierten
--       Konten zählen nicht — AUSSER der Reader hat sie in den letzten 30 min gesehen (frische Sichtung schlägt das Archiv: auch „manual“
--       archiviert zählt, ein noch lebendes Konto mit echter Hand-Position sperrt so weiter; Gegenprüfung FP1).
--       Sonst 1:1 die Live-Fassung vom 06.11.2026 (md5 b5cebfd95301747578b4f0c149a351c2 = sql/2026-11-05_gegenrichtung_nichts_gesendet.sql).
-- Nicht berührt: prophos_gegenhedge_konflikt (zählt fremd nur 90 s ab seit), prophos_fremd_konflikte (Anzeige/Alarm — mit weg_at aus (a) weg).
-- Idempotent (create or replace, drop trigger if exists, Bestand-Update mit enger where-Klausel). Rückbau: sql/2026-11-06_fp1_archiv_fremd_weg_rueckbau.sql.
-- NICHT vom Slave eingespielt.

-- Hilfe: ist das Konto archiviert? (archived true in irgendeinem Archiv-Blob — Konto-IDs global eindeutig, wie app.py _ap_archiviert; auch
-- passed/passed_pending/manual; Entarchivieren entfernt den Schlüssel). p_user bleibt in der Signatur (Aufrufer übergeben den Inhaber), prüft aber nicht mit.
create or replace function public.prophos_konto_archiviert(p_user uuid, p_konto uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select p_konto is not null and exists (
    select 1 from public.user_settings s
     where s.key = 'archive'
       and jsonb_typeof(s.value) = 'object'
       and s.value -> (p_konto::text) ->> 'archived' = 'true')
$$;

revoke all on function public.prophos_konto_archiviert(uuid, uuid) from public, anon, authenticated;
grant execute on function public.prophos_konto_archiviert(uuid, uuid) to service_role;

-- (a) Archivieren schließt die offenen Hand-Positionen des Kontos
create or replace function public.prophos_archiv_fremd_weg()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  lt_vorher text;
begin
  if new.key is distinct from 'archive' or jsonb_typeof(new.value) is distinct from 'object' then
    return new;
  end if;
  lt_vorher := current_setting('lock_timeout');
  begin
    perform set_config('lock_timeout', '2s', true);
    update public.fremd_positionen f
       set weg_at = coalesce(f.zuletzt_gesehen, now())
     where f.weg_at is null
       and f.konto_id is not null
       and coalesce(f.zuletzt_gesehen, '-infinity'::timestamptz) < now() - interval '30 minutes'   -- wie der Riegel: frisch gesehen bleibt offen (Prüfer S2)
       and new.value -> (f.konto_id::text) ->> 'archived' = 'true';
  exception when others then
    raise warning 'prophos_archiv_fremd_weg: % (Archiv trotzdem gespeichert)', sqlerrm;
  end;
  perform set_config('lock_timeout', lt_vorher, true);
  return new;
end $$;

revoke all on function public.prophos_archiv_fremd_weg() from public, anon, authenticated;

drop trigger if exists user_settings_archiv_fremd_weg on public.user_settings;
create trigger user_settings_archiv_fremd_weg
  after insert or update of value on public.user_settings
  for each row when (new.key = 'archive')
  execute function public.prophos_archiv_fremd_weg();

-- Bestand (heute 0 Zeilen, Bereinigung 24222d17): offene Hand-Positionen auf schon archivierten Konten
update public.fremd_positionen f
   set weg_at = coalesce(f.zuletzt_gesehen, now())
 where f.weg_at is null
   and f.konto_id is not null
   and coalesce(f.zuletzt_gesehen, '-infinity'::timestamptz) < now() - interval '30 minutes'
   and public.prophos_konto_archiviert(f.user_id, f.konto_id);

-- (b) Riegel: Hand-Positionen auf archivierten Konten sperren nicht
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
         and not (p.status in ('planned', 'review') and public.prophos_plan_nichts_gesendet(p.id))
    ) x
   order by x.seit desc
   limit 1;
  if g.id is null then
    if to_regclass('public.fremd_positionen') is not null then
      -- FP1 (06.11.2026): Hand-Positionen auf archivierten Konten sperren nicht (Geister ohne weg_at, Marco Topstep 05.11.) — außer frisch gesehen (≤ 30 min)
      execute 'select f.seit, f.konto_name, f.symbol, f.menge from public.fremd_positionen f
                where f.user_id = $1 and f.firma_key = $2 and f.richtung = $3 and f.weg_at is null
                  and (f.seit > now() - interval ''72 hours'' or f.zuletzt_gesehen > now() - interval ''30 minutes'')
                  and not (f.konto_id is not null and coalesce(f.zuletzt_gesehen, ''-infinity''::timestamptz) < now() - interval ''30 minutes''
                           and public.prophos_konto_archiviert(f.user_id, f.konto_id))
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

-- Proben (SQL-Editor, nur lesen):
-- select count(*) from public.fremd_positionen f where f.weg_at is null and public.prophos_konto_archiviert(f.user_id, f.konto_id);   -- → 0
-- Archiv-Blobs, die keine Objekte sind (würden übergangen, 06.11.2026: 0): select count(*) from public.user_settings where key = 'archive' and jsonb_typeof(value) <> 'object';
-- select tgname from pg_trigger where tgrelid = 'public.user_settings'::regclass and tgname = 'user_settings_archiv_fremd_weg';         -- → 1 Zeile
