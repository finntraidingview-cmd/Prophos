-- PROBE für sql/2026-10-08_gegenhedge_3min.sql (08.10.2026, Slave-Terminal 4). Funktionen 1:1 aus der Datei in EINER Transaktion,
-- Platzhalter-Pläne „GH3-Test n", Probe-Tabelle fremd_positionen falls nicht da, RAISE am Ende → alles zurückgerollt.
-- Erwartung: 1 andere ID läuft seit 10 min gegenläufig → frei (1) | 2 andere ID vor 1 min gestartet → gesperrt (0), Ziel = deren Start +3 |
-- 3 gleiche ID anderes Konto vor 1 min geclaimt → 0, „dein Konto" | 4 andere ID startet 1 min VOR uns (ungeclaimt) → 0 | 5 andere ID
-- 5 min vor uns → frei | 6 Hand-Position vor 1 min eröffnet → 0 | 7 Hand-Position vor 10 min, noch offen → frei | 8 RPC Hand-Start →
-- frei false | dazu Lesung Emins Pläne 2ad836de / 8c4fe637 mit der neuen Regel.

do $test$
declare
  u1 uuid; u2 uuid; a1 uuid; a2 uuid; b uuid; c uuid; n int; erg text := ''; s1 timestamptz; z record;
begin
  execute $q0$create or replace function public.prophos_gegenhedge_fenster() returns interval
language sql immutable as $$ select interval '3 minutes' $$$q0$;
  execute $q1$create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)
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
  -- (a) andere ID / anderes Konto derselben ID hat in den letzten 3 min gegenläufig gestartet bzw. geclaimt
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
  -- (c) Hand-Position (Slave 1, fremd_positionen) in den letzten 3 min gegenläufig eröffnet — jede ID, jedes Konto
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
  -- (b) andere ID / anderes Konto startet gegenläufig in den nächsten 3 min und FRÜHER als wir (bestätigt/Hand, noch nicht geclaimt)
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
end $$$q1$;
  execute $q2$create or replace function public.trade_plans_gegenhedge() returns trigger
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
  ziel := c.ziel + make_interval(secs => 10 + floor(random() * 30));   -- kleiner Jitter (Finn: 3 min, nicht 30)
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;   -- Spalte start_um: kein Claim-Trigger feuert dafür
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Gegenhedge 3 min] ' || k || ': ' || case when c.grund like 'Hand-Position%' then 'eine ' when c.wer = new.user_id then 'dein Konto '
                                                       else 'eine andere ID ' end || c.grund
            || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$$q2$;
  execute $q3$create or replace function public.prophos_gegenhedge_halten(p_plan uuid) returns jsonb
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
  ziel := c.ziel + make_interval(secs => 10 + floor(random() * 30));
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
            '[Gegenhedge 3 min] ' || k || ': ' || coalesce(name, 'andere ID') || ' ' || c.grund || ' — Start (Neu starten/von Hand) wartet bis '
            || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'grund', c.grund);
end $$$q3$;
  if to_regclass('public.fremd_positionen') is null then
    create table public.fremd_positionen (user_id uuid, konto_id uuid, firma_key text, richtung text, seit timestamptz,
      zuletzt_gesehen timestamptz, weg_at timestamptz, konto_name text, quelle text, symbol text, menge numeric, ident text);
  end if;
  select user_id into u1 from accounts group by user_id having count(*) >= 2 order by user_id limit 1;
  select id into a1 from accounts where user_id = u1 order by id limit 1;
  select id into a2 from accounts where user_id = u1 order by id limit 1 offset 1;
  select id into u2 from auth.users where id <> u1 order by created_at limit 1;
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u2, null, 'Konto 1', 'GH3-Test 1', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto 1', 'GH3-Test 1', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '1 läuft seit 10 min: ' || n || ', ' || coalesce((select left(grund, 40) from auto_plan_umplanung where plan_id = b order by um desc limit 1), '-') || ' | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u2, null, 'Konto 2', 'GH3-Test 2', 'open', now() - interval '1 minutes', 'buy', now() - interval '1 minutes', now() - interval '1 minutes') returning id into c;
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto 2', 'GH3-Test 2', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; select start_um into s1 from trade_plans where id = b;
  erg := erg || '2 vor 1 min gestartet: ' || n || ' Zeilen, +' || round(extract(epoch from s1 - (select started_at from trade_plans where id = c))) || ' s, ' || coalesce((select left(grund, 40) from auto_plan_umplanung where plan_id = b order by um desc limit 1), '-') || ' | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, start_um_gestartet_at) values (u1, a1, 'Konto 3', 'GH3-Test 3', 'planned', now() - interval '1 minutes', 'buy', now() - interval '1 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto 3', 'GH3-Test 3', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '3 gleiche ID anderes Konto: ' || n || ' („' || coalesce((select left(grund, 80) from auto_plan_umplanung where plan_id = b limit 1), '') || '“) | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u2, null, 'Konto 4', 'GH3-Test 4', 'planned', now() - interval '1 minutes', 'buy');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto 4', 'GH3-Test 4', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '4 andere ID 1 min vor uns: ' || n || ', ' || coalesce((select left(grund, 40) from auto_plan_umplanung where plan_id = b order by um desc limit 1), '-') || ' | ';
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u2, null, 'Konto 5', 'GH3-Test 5', 'planned', now() - interval '5 minutes', 'buy');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto 5', 'GH3-Test 5', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '5 andere ID 5 min vor uns: ' || n || ' | ';
  insert into public.fremd_positionen (user_id, konto_id, firma_key, richtung, seit, zuletzt_gesehen, weg_at, konto_name, quelle)
    values (u2, null, prophos_firma_key('GH3-Test 6'), 'buy', now() - interval '1 minutes', now(), null, 'Hand 6', 'mt5');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto 6', 'GH3-Test 6', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '6 Hand vor 1 min: ' || n || ', ' || coalesce((select left(grund, 40) from auto_plan_umplanung where plan_id = b order by um desc limit 1), '-') || ' | ';
  insert into public.fremd_positionen (user_id, konto_id, firma_key, richtung, seit, zuletzt_gesehen, weg_at, konto_name, quelle)
    values (u2, null, prophos_firma_key('GH3-Test 7'), 'buy', now() - interval '10 minutes', now(), null, 'Hand 7', 'mt5');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a2, 'Konto 7', 'GH3-Test 7', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '7 Hand vor 10 min offen: ' || n || ' | ';
  perform set_config('request.jwt.claims', json_build_object('sub', u1::text, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', u1::text, true);
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u2, null, 'Konto 8', 'GH3-Test 8', 'open', now() - interval '1 minutes', 'buy', now() - interval '1 minutes', now() - interval '1 minutes');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, richtung) values (u1, a2, 'Konto 8', 'GH3-Test 8', 'planned', 'sell') returning id into b;
  erg := erg || '8 RPC: ' || coalesce((select (prophos_gegenhedge_halten(b))::text), 'null') || ' | ';
  for z in select left(p.id::text, 8) id, p.master_firm, p.richtung, (select k.grund from prophos_gegenhedge_konflikt(p.id, p.user_id, p.master_firm, p.richtung, coalesce(p.start_um, now())) k) g
             from trade_plans p where p.id::text like '2ad836de%' or p.id::text like '8c4fe637%' loop
    erg := erg || 'Emin ' || z.id || ' ' || z.master_firm || ' ' || z.richtung || ': ' || coalesce(z.g, 'FREI') || ' | ';
  end loop;
  raise exception 'GEGENHEDGE-3MIN-TEST (alles zurückgerollt): %', erg;
end $test$;
