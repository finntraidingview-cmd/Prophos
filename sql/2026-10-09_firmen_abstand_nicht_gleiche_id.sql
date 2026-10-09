-- FIRMEN-ABSTAND NICHT MEHR INNERHALB DERSELBEN ID (Finn 09.10.2026 ~10:35 Dubai über Master): Jacob startete zwei Tradeify-SELLs
-- direkt nacheinander, der zweite (WD) wurde um ~70 s geschoben („[Firmen-Abstand 1 min] … deinem anderen Konto hat um 10:33:53
-- gestartet — wartet bis 10:35:05", auto_plan_umplanung 199/200). Finn: diese Sekunden-Regel soll weg.
-- Neu: der 1-min-Abstand je Firma gilt nur noch zwischen VERSCHIEDENEN IDs (Tarnung über IDs, Finns Regel 08.10.2026). Gegenrichtung
-- derselben ID × Firma sperrt weiter der Gegenrichtungs-Riegel (.1427). Code-Seite: app.py (Planer/Bot/Startzeit per Klick) gleichzeitig.
-- Ändert NUR die Auswahl des „letzten Starts" in trade_plans_firmen_abstand (Riegel am Claim) und prophos_firmen_abstand_halten (RPC vor
-- jedem Start): p.user_id <> eigene user_id. Fenster (prophos_firmen_abstand_fenster, 60 s) unverändert. Idempotent (create or replace).
-- NICHT eingespielt — der Master spielt nach der Vorprüfung ein. Rückweg am Ende (Stand vor dieser Datei = sql/2026-10-08_firmen_abstand_1min.sql).

create or replace function public.trade_plans_firmen_abstand()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare
  k text;
  f interval := public.prophos_firmen_abstand_fenster();
  letzter timestamptz;
  ziel timestamptz;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- nur Starts ANDERER IDs (09.10.2026) — eigene Konten derselben Firma dürfen direkt nacheinander starten
  select coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at)
    into letzter
    from public.trade_plans p
   where p.id <> new.id
     and p.user_id is distinct from new.user_id
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if letzter is null or letzter <= now() - f then
    return new;
  end if;
  ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Firmen-Abstand 1 min] ' || k || ': eine andere ID hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start frühestens 1 min danach (' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai)',
            'start');
  end if;
  return null;
end $function$;

create or replace function public.prophos_firmen_abstand_halten(p_plan uuid)
 returns jsonb
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare
  pl public.trade_plans%rowtype;
  k text;
  f interval := public.prophos_firmen_abstand_fenster();
  letzter timestamptz;
  wer uuid;
  ziel timestamptz;
  name text;
begin
  select * into pl from public.trade_plans where id = p_plan;
  if not found or pl.user_id is distinct from auth.uid() then
    return jsonb_build_object('frei', true, 'grund', 'kein eigener Plan');
  end if;
  if pl.status is distinct from 'planned' or coalesce(btrim(pl.master_firm), '') = '' then
    return jsonb_build_object('frei', true);
  end if;
  if pl.started_at is not null or pl.orbit_gesendet_at is not null then
    return jsonb_build_object('frei', true, 'grund', 'Order schon gesendet — kein Eingriff');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- nur Starts ANDERER IDs (09.10.2026) — eigene Konten derselben Firma dürfen direkt nacheinander starten
  select p.user_id, coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) as t
    into wer, letzter
    from public.trade_plans p
   where p.id <> pl.id
     and p.user_id is distinct from pl.user_id
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by t desc
   limit 1;
  if letzter is null or letzter <= now() - f then
    return jsonb_build_object('frei', true);
  end if;
  ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));
  select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(wer::text, 8))
    into name from auth.users u where u.id = wer;
  if pl.start_um is null or abs(extract(epoch from pl.start_um - ziel)) > 30 then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Firmen-Abstand 1 min] ' || k || ': ' || coalesce(name, 'andere ID') || ' hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start (Neu starten/von Hand) wartet bis ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai', 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'letzter', letzter);
end $function$;

-- PRÜFEN nach dem Einspielen:
--   select position('is distinct from new.user_id' in pg_get_functiondef('public.trade_plans_firmen_abstand()'::regprocedure)) > 0,
--          position('is distinct from pl.user_id' in pg_get_functiondef('public.prophos_firmen_abstand_halten(uuid)'::regprocedure)) > 0;   -- t, t
--
-- RÜCKWEG: sql/2026-10-08_firmen_abstand_1min.sql erneut einspielen (dort ohne die user_id-Bedingung, mit „eigen"/„deinem anderen Konto").
