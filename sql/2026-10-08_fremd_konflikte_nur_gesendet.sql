-- FREMD-KONFLIKTE: NUR GESENDETE PLÄNE ZÄHLEN (08.10.2026, Befund Prüfer über Master). prophos_fremd_konflikte (sql/2026-10-08_fremd_positionen.sql)
-- nahm als Plan-Start coalesce(started_at, orbit_gesendet_at, start_um_gestartet_at) — schon der bloße Start-CLAIM löste den Alarm aus.
-- Vorfall 13:35 UTC: ein von Hand gewollter TV-Tradeify-BUY gegen einen Tradeify-SELL-Plan einer anderen ID, der nur geclaimt war und nie
-- gesendet hat (start_fehler rot, Schritt cdp, „nichts gesendet") → Push „⚠ Gegenhedge …" an beide IDs und die Admins. Falsch.
--
-- Jetzt für ALARM (Push) und rote Zeile (fremd_positionen.gegen, von app.py fp_tick jeden Takt neu geschrieben):
--   Plan-Start = coalesce(started_at, orbit_gesendet_at) — nur, was wirklich gesendet hat; Pläne ohne beides fallen heraus.
--   Plan mit start_fehler und ohne started_at fällt ebenfalls heraus (rot ohne Order geendet) — außer der Fehler ist „unklar"
--   (Order vielleicht doch platziert) oder schon „behoben". Damit verschwindet die rote Zeile beim nächsten Takt (15 s) von selbst.
-- Unverändert: der Start-RIEGEL prophos_gegenhedge_konflikt zählt weiter ab dem Claim (dort richtig), Hand gegen Hand, Fenster
-- prophos_gegenhedge_fenster(), Rückgabe-Spalten, Rechte. Bereits gemeldete alarm_keys bleiben stehen (nur Doppel-Push-Schutz).
-- Wiederholbar (create or replace). Rückbau: sql/2026-10-08_fremd_positionen.sql (Funktionsteil) erneut einspielen.
create or replace function public.prophos_fremd_konflikte()
returns table(fremd_id bigint, art text, gegen_id text, gegen_user uuid, gegen_konto text, gegen_richtung text, gegen_seit timestamptz)
language plpgsql stable security definer set search_path to 'public'
as $$
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
       -- rot ohne Order geendet: Startfehler, nie gestartet, nicht unklar, nicht behoben → kein Gegenüber
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
end $$;

revoke all on function public.prophos_fremd_konflikte() from public, anon, authenticated;
grant execute on function public.prophos_fremd_konflikte() to service_role;
-- Prüfen (nach dem Einspielen): select * from public.prophos_fremd_konflikte();  -- der 13:35-Fall taucht nicht mehr auf
