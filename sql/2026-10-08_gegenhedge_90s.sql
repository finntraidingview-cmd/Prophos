-- GEGENHEDGE-RIEGEL NUR NOCH IM 90-SEKUNDEN-FENSTER (08.10.2026, Slave-Terminal 4 — Finn zuletzt: „stellt das Ganze bitte auf 90 Sekunden";
-- davor: „Die Regel heißt ja einfach: Wenn eine
-- ID z. B. Tradeify longt, können innerhalb von 20 Minuten andere IDs nur auch longen, nicht shorten. Kannst du die auf 3 Minuten
-- runterstellen?" Anlass: Emins Hand-Trades 2ad836de (FundingPips Sell) und 8c4fe637 (FTMO Buy) wurden immer wieder um +30 min geschoben,
-- weil Chris dort in Gegenrichtung LIEF — die Laufzeit-Regel aus sql/2026-10-08_gegenhedge_riegel.sql.)
--
-- Neue Regel (DB-Riegel am Claim trade_plans_gegenhedge + RPC prophos_gegenhedge_halten vor jedem Start, beide über prophos_gegenhedge_konflikt):
--   Konflikt NUR (Fenster 90 s, symmetrisch um Start/Claim), wenn eine andere ID — oder ein anderes Konto derselben ID — bei derselben Firma in Gegenrichtung
--     (a) in den letzten 90 s gestartet bzw. geclaimt hat (started_at / orbit_gesendet_at / start_um_gestartet_at), oder
--     (b) in den nächsten 90 s startet: bestätigter/Hand-Plan, noch nicht geclaimt, Start bis 90 s VOR unserem (der Spätere weicht;
--         gleich: kleinere id zuerst), oder
--     (c) eine Hand-Position (Slave 1, public.fremd_positionen) in den letzten 90 s eröffnet hat („seit" zählt als Start).
--   Dann Start auf deren Start + 90 s + 20–40 s Jitter, nicht mehr +30 min. Laufende Trades allein blockieren NICHT mehr.
--   Fenster als eine Konstante: prophos_gegenhedge_fenster() = 90 s (symmetrisch).
--   Planer und Ausgleichs-Bot (app.py, AP_GEGEN_FIRMA_MIN) bleiben unverändert — sie halten ihre Richtungsmischung je Firma wie bisher
--   („gelegentlich ok, kein Muster"); hier geht es nur um den harten Riegel.
-- Ohne Konto (master_account_id NULL auf einer Seite) zählt immer als anderes Konto. Dasselbe Konto bleibt außen vor (Richtungsschutz).
--
-- ERSETZT sql/2026-10-08_gegenhedge_3min.sql und sql/2026-10-08_gegenhedge_gleiche_id.sql (beide nie eingespielt) und die Funktionsrümpfe aus sql/2026-10-08_gegenhedge_riegel.sql
-- (gleiche Signaturen/Rückgabetypen, Trigger bleibt stehen). fremd_positionen per to_regclass + EXECUTE — darf vor Slave 1s
-- sql/2026-10-08_fremd_positionen.sql eingespielt werden. Wiederholbar. Rückbau: sql/2026-10-08_gegenhedge_riegel.sql erneut einspielen.

do $pruef$
begin
  perform 'public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-08_gegenhedge_riegel.sql einspielen (prophos_gegenhedge_konflikt fehlt)';
end $pruef$;

-- Fenster zentral (Finn 08.10.2026: „stellt das Ganze bitte auf 90 Sekunden") — hier und nur hier ändern
create or replace function public.prophos_gegenhedge_fenster() returns interval
language sql immutable as $$ select interval '90 seconds' $$;

create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)
returns table(ziel timestamptz, wer uuid, grund text)
language plpgsql stable security definer set search_path = public as $$
declare
  k text := public.prophos_firma_key(p_firma);
  gegen text := case p_richtung when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  f interval := public.prophos_gegenhedge_fenster();
  konto uuid;
  t timestamptz;
  u uuid;
  n text;
begin
  if gegen is null or coalesce(btrim(p_firma), '') = '' then
    return;
  end if;
  select master_account_id into konto from public.trade_plans where id = p_id;
  -- (a) andere ID / anderes Konto derselben ID hat in den letzten 90 s gegenläufig gestartet bzw. geclaimt
  select greatest(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at), p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status in ('planned', 'open')
     and greatest(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if t is not null then
    return query select t + f, u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'hat dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung gestartet';
    return;
  end if;
  -- (c) Hand-Position (Slave 1, fremd_positionen) in den letzten 90 s gegenläufig eröffnet — jede ID, jedes Konto
  if to_regclass('public.fremd_positionen') is not null then
    execute 'select f.seit, f.user_id, f.konto_name from public.fremd_positionen f
              where f.firma_key = $1 and f.richtung = $2 and f.weg_at is null and f.seit > now() - $3
              order by f.seit desc limit 1'
      into t, u, n using k, gegen, f;
    if t is not null then
      return query select t + f, u,
        'Hand-Position „' || coalesce(n, '?') || '“ wurde dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung eröffnet';
      return;
    end if;
  end if;
  -- (b) andere ID / anderes Konto startet gegenläufig in den nächsten 90 s und FRÜHER als wir (bestätigt/Hand, noch nicht geclaimt)
  select p.start_um, p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status = 'planned'
     and p.start_um_gestartet_at is null
     and (not coalesce(p.auto_plan, false) or p.auto_bestaetigt_at is not null)
     and p.start_um >= p_ref - f
     and p.start_um >= now() - f
     and (p.start_um < p_ref or (p.start_um = p_ref and p.id < p_id))
     and public.prophos_firma_key(p.master_firm) = k
   order by p.start_um desc
   limit 1;
  if t is not null then
    return query select greatest(t + f, now() + interval '30 seconds'), u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'startet dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung';
  end if;
end $$;
revoke all on function public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz) from public;

create or replace function public.trade_plans_gegenhedge() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  c record;
  ziel timestamptz;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' or new.richtung not in ('buy', 'sell') then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;                                   -- „verpasst"-Claim: startet nichts, nicht aufhalten
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));   -- derselbe Lock wie der Firmen-Abstand
  select * into c from public.prophos_gegenhedge_konflikt(new.id, new.user_id, new.master_firm, new.richtung, coalesce(old.start_um, now()));
  if c.ziel is null then
    return new;                                   -- frei: Claim normal schreiben
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 20));   -- kleiner Jitter 20–40 s (Finn: 90 s, nicht 30 min)
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;   -- Spalte start_um: kein Claim-Trigger feuert dafür
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Gegenhedge 90 s] ' || k || ': ' || case when c.grund like 'Hand-Position%' then 'eine ' when c.wer = new.user_id then 'dein Konto '
                                                       else 'eine andere ID ' end || c.grund
            || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$;

create or replace function public.prophos_gegenhedge_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pl public.trade_plans%rowtype;
  k text;
  c record;
  ziel timestamptz;
  name text;
begin
  select * into pl from public.trade_plans where id = p_plan;
  if not found or pl.user_id is distinct from auth.uid() then
    return jsonb_build_object('frei', true, 'grund', 'kein eigener Plan');
  end if;
  if pl.status is distinct from 'planned' or coalesce(btrim(pl.master_firm), '') = '' or pl.richtung not in ('buy', 'sell') then
    return jsonb_build_object('frei', true);
  end if;
  if pl.started_at is not null or pl.orbit_gesendet_at is not null then
    return jsonb_build_object('frei', true, 'grund', 'Order schon gesendet — kein Eingriff');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  select * into c from public.prophos_gegenhedge_konflikt(pl.id, pl.user_id, pl.master_firm, pl.richtung, coalesce(pl.start_um, now()));
  if c.ziel is null then
    return jsonb_build_object('frei', true);
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 20));
  if c.grund like 'Hand-Position%' then
    name := 'eine';                                                                -- „eine Hand-Position „…" wurde dort … eröffnet"
  elsif c.wer = pl.user_id then
    name := 'dein Konto';                                                          -- gleiche ID, anderes Konto
  else
    select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(c.wer::text, 8))
      into name from auth.users u where u.id = c.wer;                              -- nur Vorname, nie E-Mail
  end if;
  if pl.start_um is null or pl.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;   -- orbit_gesendet_at nie
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Gegenhedge 90 s] ' || k || ': ' || coalesce(name, 'andere ID') || ' ' || c.grund || ' — Start (Neu starten/von Hand) wartet bis '
            || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'grund', c.grund);
end $$;

revoke all on function public.prophos_gegenhedge_halten(uuid) from public;
grant execute on function public.prophos_gegenhedge_halten(uuid) to authenticated;
