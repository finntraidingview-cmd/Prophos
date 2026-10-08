-- PROBE für sql/2026-10-08_gegenhedge_gleiche_id.sql (08.10.2026, Slave-Terminal 4). Legt die drei Funktionen aus der Datei in EINER
-- Transaktion neu an (Text 1:1, erzeugt), legt eine Probe-Tabelle public.fremd_positionen mit Slave 1s Spalten an (falls nicht da), spielt
-- Fälle mit Platzhalter-Plänen eigener Firmennamen („GH2-Test n") auf zwei echten Konten EINER ID durch und bricht mit RAISE ab →
-- alles zurückgerollt. Erwartung: 1 gleiche ID anderes Konto gegenläufig → 0 Zeilen, „dein Konto „…"" | 2 gleiches Konto → 1 |
-- 3 gleiche Richtung → 1 | 4 andere ID gegenläufig → 0 | 5 gleiche ID früher geplant → 0, deren Start +30 | 6 RPC → wer „dein Konto" |
-- 7 Hand-Position gegenläufig (auch eigene ID) → 0, „eine Hand-Position „…"" | 8 Hand-Position weg → 1 | 9 Hand-Position zu alt
-- (zuletzt_gesehen > 3 min) → 1 | 10 RPC Hand → wer „eine".

do $test$
declare
  u1 uuid; u2 uuid; a1 uuid; a2 uuid; b uuid; c uuid; n int; erg text := ''; s1 timestamptz; p int;
begin
  execute $q0$create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)
returns table(ziel timestamptz, wer uuid, grund text)
language plpgsql stable security definer set search_path = public as $$
declare
  k text := public.prophos_firma_key(p_firma);
  gegen text := case p_richtung when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  konto uuid;
  t timestamptz;
  u uuid;
  n text;
begin
  if gegen is null or coalesce(btrim(p_firma), '') = '' then
    return;
  end if;
  select master_account_id into konto from public.trade_plans where id = p_id;
  -- (a) eine andere ID ODER ein anderes Konto derselben ID läuft gegenläufig (oder der Start ist gerade unterwegs)
  select coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now()), p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if t is not null then
    return query select now() + interval '30 minutes', u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'läuft dort in Gegenrichtung (seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)';
    return;
  end if;
  -- (a2) offene Hand-Position derselben Firma in Gegenrichtung (Slave 1, fremd_positionen) — jede ID, jedes Konto
  if to_regclass('public.fremd_positionen') is not null then
    execute 'select f.seit, f.user_id, f.konto_name from public.fremd_positionen f
              where f.firma_key = $1 and f.richtung = $2 and f.weg_at is null and f.zuletzt_gesehen > now() - interval ''3 minutes''
              order by f.seit desc limit 1'
      into t, u, n using k, gegen;
    if t is not null then
      return query select now() + interval '5 minutes', u,
        'Hand-Position „' || coalesce(n, '?') || '“ läuft dort in Gegenrichtung (seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)';
      return;
    end if;
  end if;
  -- (b) eine andere ID oder ein anderes Konto derselben ID startet gegenläufig früher (bestätigt/Hand, noch nicht geclaimt, ≤ 30 min alt)
  select p.start_um, p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status = 'planned'
     and p.start_um_gestartet_at is null
     and (not coalesce(p.auto_plan, false) or p.auto_bestaetigt_at is not null)
     and p.start_um >= now() - interval '30 minutes'
     and (p.start_um < p_ref or (p.start_um = p_ref and p.id < p_id))
     and public.prophos_firma_key(p.master_firm) = k
   order by p.start_um desc
   limit 1;
  if t is not null then
    return query select greatest(t + interval '30 minutes', now() + interval '5 minutes'), u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'startet dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung';
  end if;
end $$$q0$;
  execute $q1$create or replace function public.trade_plans_gegenhedge() returns trigger
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
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 70));
  if old.start_um is null or old.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel where id = new.id;   -- Spalte start_um: kein Claim-Trigger feuert dafür
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Gegenhedge] ' || k || ': ' || case when c.grund like 'Hand-Position%' then 'eine ' when c.wer = new.user_id then 'dein Konto '
                                                 else 'eine andere ID ' end || c.grund
            || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$$q1$;
  execute $q2$create or replace function public.prophos_gegenhedge_halten(p_plan uuid) returns jsonb
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
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 70));
  if c.grund like 'Hand-Position%' then
    name := 'eine';                                                                -- „eine Hand-Position „…" läuft dort …" (Slave 1)
  elsif c.wer = pl.user_id then
    name := 'dein Konto';                                                          -- gleiche ID, anderes Konto (08.10.2026)
  else
    select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(c.wer::text, 8))
      into name from auth.users u where u.id = c.wer;                              -- nur Vorname, nie E-Mail
  end if;
  if pl.start_um is null or pl.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;   -- orbit_gesendet_at nie
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Gegenhedge] ' || k || ': ' || coalesce(name, 'andere ID') || ' ' || c.grund || ' — Start (Neu starten/von Hand) wartet bis '
            || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'grund', c.grund);
end $$$q2$;
  if to_regclass('public.fremd_positionen') is null then
    create table public.fremd_positionen (user_id uuid, konto_id uuid, firma_key text, richtung text, seit timestamptz,
      zuletzt_gesehen timestamptz, weg_at timestamptz, konto_name text, quelle text, symbol text, menge numeric, ident text);
  end if;
  select user_id into u1 from accounts group by user_id having count(*) >= 2 order by user_id limit 1;
  select id into a1 from accounts where user_id = u1 order by id limit 1;
  select id into a2 from accounts where user_id = u1 order by id limit 1 offset 1;
  select id into u2 from auth.users where id <> u1 order by created_at limit 1;
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, a1, 'Konto a1', 'GH2-Test 1', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 1', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; select count(*) into p from auto_plan_umplanung where plan_id = b;
  erg := erg || '1 gleiche ID anderes Konto: ' || n || ' Zeilen („' || coalesce((select left(grund, 90) from auto_plan_umplanung where plan_id = b limit 1), '') || '“) | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, a1, 'Konto a1', 'GH2-Test 2', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'Konto a1', 'GH2-Test 2', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '2 gleiches Konto: ' || n || ' | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, a1, 'Konto a1', 'GH2-Test 3', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 3', 'planned', now(), 'buy') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '3 gleiche Richtung: ' || n || ' | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u2, null, 'Konto null', 'GH2-Test 4', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 4', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '4 andere ID: ' || n || ' | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'Konto a1', 'GH2-Test 5', 'planned', now() - interval '5 minutes', 'buy') returning id into c;
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 5', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; select start_um into s1 from trade_plans where id = b;
  erg := erg || '5 früher geplant: ' || n || ' Zeilen, +' || round(extract(epoch from s1 - (select start_um from trade_plans where id = c)) / 60) || ' min | ';
  -- Hand-Positionen (firma_key wie prophos_firma_key)
  insert into public.fremd_positionen (user_id, konto_id, firma_key, richtung, seit, zuletzt_gesehen, weg_at, konto_name, quelle)
    values (u1, a1, prophos_firma_key('GH2-Test 7'), 'buy', now() - interval '4 minutes', now() - interval '20 seconds', null, 'Hand-Konto 7', 'mt5');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'Konto a1', 'GH2-Test 7', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '7 Hand-Position gegenläufig: ' || n || ' Zeilen („' || coalesce((select left(grund, 100) from auto_plan_umplanung where plan_id = b limit 1), '') || '“) | ';
  insert into public.fremd_positionen (user_id, konto_id, firma_key, richtung, seit, zuletzt_gesehen, weg_at, konto_name, quelle)
    values (u2, null, prophos_firma_key('GH2-Test 8'), 'buy', now() - interval '9 minutes', now() - interval '20 seconds', now() - interval '1 minute', 'weg', 'mt5');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 8', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '8 Hand-Position weg: ' || n || ' | ';
  insert into public.fremd_positionen (user_id, konto_id, firma_key, richtung, seit, zuletzt_gesehen, weg_at, konto_name, quelle)
    values (u2, null, prophos_firma_key('GH2-Test 9'), 'buy', now() - interval '20 minutes', now() - interval '5 minutes', null, 'alt', 'mt5');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 9', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '9 Hand-Position zu alt: ' || n || ' | ';
  perform set_config('request.jwt.claims', json_build_object('sub', u1::text, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', u1::text, true);
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, a1, 'Konto a1', 'GH2-Test 6', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 6', 'planned', 'sell') returning id into b;
  erg := erg || '6 RPC: ' || coalesce((select (prophos_gegenhedge_halten(b) ->> 'wer')), 'null') || ' | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, richtung) values (u1, a2, 'Konto a2', 'GH2-Test 7', 'planned', 'sell') returning id into b;
  erg := erg || '10 RPC Hand: ' || coalesce((select (prophos_gegenhedge_halten(b))::text), 'null');
  raise exception 'GEGENHEDGE-GLEICHE-ID-TEST (alles zurückgerollt): %', erg;
end $test$;
