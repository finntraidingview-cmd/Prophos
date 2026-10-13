-- GEGENRICHTUNG DERSELBEN ID × FIRMA: HARTE LINIE IN DER DB, UNABHÄNGIG VOM PC-TAB (Finn 13.10.2026 ~04:00 Dubai, Anlass Mike:
-- Topstep 150k …17758280 SHORT läuft seit 23:39 UTC, zwei Topstep-150k-LONGs geplant. Der JS-Wächter (v2RichtungKonflikt) hat die
-- Longs zweimal verschoben — Finn: „wenn aus irgendeinem Grund der Wächter ausfällt, ist es mir wichtig, dass man sich da nicht selber
-- fickt … dass da nie was passieren kann").
--
-- Befund vorher (sql/2026-10-09_gegenhedge_nur_gegenrichtung.sql):
--   1. Claim-Trigger trade_plans_gegenhedge übersprang die Prüfung ganz, wenn start_um älter als 60 min war („verpasst"-Claim) —
--      ein PC-Tab mit kaputtem Spät-Check hätte dann gegen den laufenden Trade geklickt.
--   2. Der laufende Trade zählte nur, wenn started_at in den letzten 12 h lag; ein „open" ohne started_at (Puls-Start ohne Fill-Beweis,
--      Hand-Umstellung) zählte gar nicht.
--   3. Remote-Signale (order_signale, Mac/Handy → PC) kannten keinen DB-Riegel; nur die weiche RPC-Abfrage im Tab (Fehler = frei).
--
-- Neu (wiederholbar, nur Ergänzung — Signaturen/Trigger/Protokoll der bisherigen Dateien bleiben):
--   prophos_gegenrichtung_frei(p_plan, p_richtung) — NUR LESEN, security definer: läuft bei derselben ID × Firma auf einem anderen Konto
--     ein Trade in Gegenrichtung (status open, gestartet/geclaimt/angelegt in den letzten 72 h, started_at darf fehlen) → frei=false mit
--     Grund + Konto. Gleiche Richtung, anderes Konto derselben Richtung, andere ID, andere Firma → frei=true. Dieselbe Funktion fragt
--     Railway (/richtung/frei, service role) für das Panel am PC — das Panel klickt ohne „frei" NICHT (fail-closed), auch nicht, wenn
--     Railway/DB nicht antworten.
--   trade_plans_gegenhedge: diese Prüfung VOR der 60-min-Ausnahme — ein Claim gegen den laufenden Trade derselben ID scheitert immer
--     (return null = Claim trifft keine Zeile, der Tab startet nichts), Start +10 min, Protokoll „[Gegenrichtung gleiche ID]".
--   prophos_gegenhedge_konflikt: Zweig „gleiche ID, läuft" nutzt dieselbe 72-h-/coalesce-Regel (vorher 12 h + started_at Pflicht).
--   order_signale_gegenrichtung (BEFORE INSERT): ein Remote-Signal (status wartet, Orbit/Echo-Order mit Richtung) gegen den laufenden
--     Trade derselben ID × Firma wird mit Fehler abgewiesen — der PC kann es nie claimen. Lokale Spur-Zeilen (status fertig/fehler,
--     params.lokal) sind Protokoll nach dem Klick und bleiben unangetastet.
-- 72 h statt 12 h: ein Trade läuft nie länger als einen Handelstag, 72 h deckt das Wochenende; ein vergessener „open" sperrt also
-- höchstens drei Tage und steht mit Namen im Grund — abhaken löst es.
-- Rückbau: sql/2026-10-09_gegenhedge_nur_gegenrichtung.sql erneut einspielen + drop trigger order_signale_gegenrichtung.

do $pruef$
begin
  perform 'public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz)'::regprocedure;
  perform 'public.prophos_gegenhedge_fenster()'::regprocedure;
  perform 'public.prophos_firma_key(text)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-09_gegenhedge_nur_gegenrichtung.sql einspielen';
end $pruef$;

-- ── 1. Reine Leseprüfung ────────────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.prophos_gegenrichtung_frei(p_plan uuid, p_richtung text default null)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  pl record;
  r text;
  gegen text;
  k text;
  g record;
begin
  select id, user_id, master_account_id, master_firm, master_name, richtung, status into pl from public.trade_plans where id = p_plan;
  if not found then
    return jsonb_build_object('frei', true, 'grund', 'Plan unbekannt');
  end if;
  r := lower(btrim(coalesce(p_richtung, pl.richtung, '')));
  r := case when r in ('buy', 'long', 'kauf') then 'buy' when r in ('sell', 'short', 'verkauf') then 'sell' else null end;
  gegen := case r when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  if gegen is null or coalesce(btrim(pl.master_firm), '') = '' then
    return jsonb_build_object('frei', true, 'grund', 'keine Richtung/Firma');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  select p.id, p.master_name, p.user_id,
         coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) as seit
    into g
    from public.trade_plans p
   where p.id <> pl.id
     and p.user_id = pl.user_id
     and (pl.master_account_id is null or p.master_account_id is null or p.master_account_id is distinct from pl.master_account_id)
     and p.richtung = gegen
     and p.status = 'open'
     and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours'
     and public.prophos_firma_key(p.master_firm) = k
   order by 4 desc
   limit 1;
  if g.id is null then
    return jsonb_build_object('frei', true, 'firma', k, 'richtung', r);
  end if;
  return jsonb_build_object('frei', false, 'firma', k, 'richtung', r, 'plan', g.id, 'wer', 'dein Konto', 'user_id', pl.user_id,
    'grund', '„' || coalesce(g.master_name, 'Konto') || '“ läuft dort'
             || coalesce(' seit ' || to_char(g.seit at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai', '')
             || ' ' || upper(case gegen when 'buy' then 'long' else 'short' end)
             || ' — ' || upper(case r when 'buy' then 'long' else 'short' end) || ' wäre die Gegenrichtung (Selbst-Hedge). Gesperrt, bis er zu ist');
end $$;
grant execute on function public.prophos_gegenrichtung_frei(uuid, text) to authenticated, service_role;

-- ── 2. Konflikt-Funktion: Zweig „gleiche ID, läuft" mit 72 h + coalesce ──────────────────────────────────────────────────
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
  -- GLEICHE ID, anderes Konto, Gegenrichtung LÄUFT → gesperrt, solange er läuft (rollend jetzt + 10 min).
  -- 13.10.2026: 72 h statt 12 h, Zeitpunkt mit Rückfall (started_at fehlt bei Puls-Starts ohne Fill-Beweis) — siehe Dateikopf.
  select coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at), p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and (konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status = 'open'
     and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours'
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
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

-- ── 3. Claim-Trigger: Gegenrichtung derselben ID IMMER prüfen, auch beim „verpasst"-Claim ─────────────────────────────────
create or replace function public.trade_plans_gegenhedge()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  c record;
  ziel timestamptz;
  hart jsonb;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' or new.richtung not in ('buy', 'sell') then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  -- HART (13.10.2026): läuft bei derselben ID × Firma ein Trade in Gegenrichtung, scheitert JEDER Claim — auch der späte
  -- „verpasst"-Claim, der früher ungeprüft durchging. Kein Tab-Code kann daran vorbei: ohne Claim kein Start.
  hart := public.prophos_gegenrichtung_frei(new.id, new.richtung);
  if coalesce((hart->>'frei')::boolean, true) = false then
    perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
    ziel := now() + interval '10 minutes' + make_interval(secs => 20 + floor(random() * 20));
    if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
      update public.trade_plans set start_um = ziel where id = new.id;
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
              '[Gegenrichtung gleiche ID] ' || k || ': dein Konto ' || coalesce(hart->>'grund', 'läuft dort in Gegenrichtung')
              || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
    end if;
    return null;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;                                   -- „verpasst"-Claim: startet nichts, nicht aufhalten (Gegenrichtung ist oben schon geprüft)
  end if;
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

-- ── 4. Remote-Signal: Order gegen den laufenden Trade derselben ID wird gar nicht erst angelegt ────────────────────────────
create or replace function public.order_signale_gegenrichtung()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  pid uuid;
  r text;
  hart jsonb;
begin
  -- Nur echte Aufträge an den PC (status wartet) mit Plan-UUID und Richtung. Spur-Zeilen nach dem Klick (fertig/fehler, params.lokal),
  -- Konto-/Inventar-Aufträge (plan_id 'konto:…', 'tsx:inventar') und Close-Signale ohne Richtung bleiben unberührt.
  if coalesce(new.status, 'wartet') <> 'wartet' or coalesce((new.params->>'lokal')::boolean, false) then
    return new;
  end if;
  if new.plan_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    return new;
  end if;
  pid := new.plan_id::uuid;
  r := coalesce(new.params->'orbit'->>'richtung', new.params->>'richtung');
  if r is null or btrim(r) = '' then
    return new;
  end if;
  hart := public.prophos_gegenrichtung_frei(pid, r);
  if coalesce((hart->>'frei')::boolean, true) = false then
    raise exception 'Gegenrichtung gesperrt: %', coalesce(hart->>'grund', 'bei dieser ID × Firma läuft ein Trade in Gegenrichtung')
      using errcode = 'check_violation';
  end if;
  return new;
end $$;

drop trigger if exists order_signale_gegenrichtung on public.order_signale;
create trigger order_signale_gegenrichtung
  before insert on public.order_signale
  for each row execute function public.order_signale_gegenrichtung();

-- PROBE (nur lesen, nach dem Einspielen): jeder geplante Plan gegen den laufenden Trade derselben ID × Firma muss frei=false liefern.
-- select p.master_name, p.richtung, public.prophos_gegenrichtung_frei(p.id) from public.trade_plans p where p.status = 'planned' and p.start_um::date >= current_date;
