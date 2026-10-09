-- GEGENRICHTUNG DERSELBEN ID GESPERRT, SOLANGE DORT EIN TRADE LÄUFT (Finn 09.10.2026 ~09:25 Dubai über Master: „90 s macht keinen Sinn —
-- Gegenrichtung ist verboten"; gleiche Richtung frei).
-- Anlass 09.10.2026 05:19–05:21 UTC: Topstep-Kette 1/2 auf zwei Konten DERSELBEN ID — d369e8d5 SELL läuft seit 05:19:32, 333d4791 BUY wurde
-- nur 90 s geschoben („[Gegenhedge 90 s] … dein Konto … in Gegenrichtung gestartet — wartet bis 09:21:41") und danach geclaimt. Puls
-- platzierte nichts (TopstepX-Ticket noch nicht lesbar), der Plan wurde von Hand auf SELL gedreht. Ursache: prophos_gegenhedge_konflikt
-- zählt einen gegenläufigen Trade nur in den ersten 90 s nach seinem Start (sql/2026-10-08_gegenhedge_90s.sql) — für ALLE IDs gleich.
--
-- Neu (nur prophos_gegenhedge_konflikt + die Texte in Trigger/RPC; Signaturen, Trigger, Lock, Protokoll unverändert):
--   GLEICHE ID (p.user_id = p_user), anderes Konto, dieselbe Firma, Gegenrichtung, status 'open' (gestartet in den letzten 12 h — ein vergessener
--     „open" sperrt nicht unbegrenzt, Prüfer T3) → gesperrt, solange er läuft. Ziel = jetzt + 10 min (rollend: jeder neue Claim bzw. jede
--     RPC-Abfrage vor dem Start schiebt erneut, bis der Trade zu ist; 10 statt 5 min halbiert die Protokollzeilen, Prüfer T3).
--     Grund „„<Konto>" läuft dort seit HH:MI Dubai in Gegenrichtung — gegen den laufenden Trade gesperrt, bis er zu ist".
--   ANDERE IDs: unverändert 90 s ab Start/Claim (prophos_gegenhedge_fenster) — über IDs ist die Gegenrichtung erlaubt, nur nicht gleichzeitig.
--   GLEICHE RICHTUNG: nie ein Abstand (war schon so — gesucht wird nur p.richtung = gegen). Der Firmen-Abstand 1 min (trade_plans_firmen_abstand,
--     .1353) gilt für jede Richtung weiter und ist hier NICHT angefasst.
--   Dasselbe Konto bleibt außen vor (ein Konto hat nie zwei Trades gleichzeitig; Kette T2 entsteht erst nach dem Ende von T1).
--   Protokoll-Präfix: „[Gegenrichtung gleiche ID]" statt „[Gegenhedge 90 s]", wenn die neue Regel greift.
--
-- VORAUSSETZUNG: sql/2026-10-08_gegenhedge_90s.sql (bzw. der Live-Stand mit prophos_gegenhedge_fenster) ist eingespielt. Wiederholbar.
-- Rückbau: sql/2026-10-08_gegenhedge_90s.sql erneut einspielen. NICHT von T5 eingespielt — Master nach Vorprüfung T3.

do $pruef$
begin
  perform 'public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz)'::regprocedure;
  perform 'public.prophos_gegenhedge_fenster()'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-08_gegenhedge_90s.sql einspielen (prophos_gegenhedge_konflikt/_fenster fehlt)';
end $pruef$;

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
  -- (neu 09.10.2026) GLEICHE ID, anderes Konto, Gegenrichtung LÄUFT → gesperrt, solange er läuft (rollend jetzt + 5 min)
  select p.started_at, p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and (konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status = 'open'
     and p.started_at > now() - interval '12 hours'      -- Prüfer T3: ein vergessener „open" (nie abgehakt) sperrt nicht unbegrenzt
     and public.prophos_firma_key(p.master_firm) = k
   order by p.started_at desc nulls last
   limit 1;
  if u is not null then
    return query select now() + interval '10 minutes', u,
      '„' || coalesce(n, 'Konto') || '“ läuft dort' || coalesce(' seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai', '')
      || ' in Gegenrichtung — gegen den laufenden Trade gesperrt, bis er zu ist';
    return;
  end if;
  -- ab hier unverändert (90 s, jede ID): frisch gestartet/geclaimt gegenläufig
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

create or replace function public.trade_plans_gegenhedge()
returns trigger
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
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  select * into c from public.prophos_gegenhedge_konflikt(new.id, new.user_id, new.master_firm, new.richtung, coalesce(old.start_um, now()));
  if c.ziel is null then
    return new;
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 20));
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            case when c.grund like '%gegen den laufenden Trade gesperrt%' then '[Gegenrichtung gleiche ID] ' else '[Gegenhedge 90 s] ' end
            || k || ': ' || case when c.grund like 'Hand-Position%' then 'eine ' when c.wer = new.user_id then 'dein Konto '
                                 else 'eine andere ID ' end || c.grund
            || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;
end $$;

create or replace function public.prophos_gegenhedge_halten(p_plan uuid)
returns jsonb
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
    name := 'eine';
  elsif c.wer = pl.user_id then
    name := 'dein Konto';
  else
    select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(c.wer::text, 8))
      into name from auth.users u where u.id = c.wer;
  end if;
  if pl.start_um is null or pl.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            case when c.grund like '%gegen den laufenden Trade gesperrt%' then '[Gegenrichtung gleiche ID] ' else '[Gegenhedge 90 s] ' end
            || k || ': ' || coalesce(name, 'andere ID') || ' ' || c.grund || ' — Start (Neu starten/von Hand) wartet bis '
            || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'grund', c.grund,
                            'laeuft', c.grund like '%gegen den laufenden Trade gesperrt%');
end $$;

-- PROBE (nur lesen, nach dem Einspielen): ein offener Trade einer ID + ein geplanter Gegenrichtungs-Plan eines anderen Kontos derselben ID
-- und Firma muss einen Konflikt mit „gegen den laufenden Trade gesperrt" liefern; gleiche Richtung nie.
-- select p.id, c.* from public.trade_plans p, lateral public.prophos_gegenhedge_konflikt(p.id, p.user_id, p.master_firm, p.richtung, coalesce(p.start_um, now())) c
--  where p.status = 'planned' and p.start_um::date = current_date;
