do $t$
declare u1 uuid; u2 uuid; a1 uuid; a2 uuid; b uuid; c uuid; erg text := ''; j jsonb; su timestamptz; cl timestamptz;
begin
  execute $q0$create or replace function public.prophos_firmen_abstand_fenster() returns interval
language sql immutable as $$ select interval '60 seconds' $$$q0$;
  execute $q1$create or replace function public.trade_plans_firmen_abstand() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  f interval := public.prophos_firmen_abstand_fenster();
  letzter timestamptz;
  ziel timestamptz;
  eigen boolean;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- jeder andere Plan derselben Firma (auch derselben ID), dessen Start in den letzten 60 s lag — Start = der CLAIM (gewollte Startzeit;
  -- alle Wege haben danach dieselbe Puls-/Echo-Dauer), ohne Claim Order bzw. started_at (Hand: „Läuft"). Prüfer Slave 2: mit started_at
  -- (15–40 s nach dem Claim) hätte der Riegel die eigene Staffel einer Tranche (abstand_konto_s 60–120 s, WD 80 s) ständig verschoben
  select coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at), p.user_id = new.user_id
    into letzter, eigen
    from public.trade_plans p
   where p.id <> new.id
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if letzter is null or letzter <= now() - f then
    return new;
  end if;
  ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));   -- Jitter 10–30 s
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Firmen-Abstand 1 min] ' || k || ': ' || case when eigen then 'ein anderes Konto dieser ID' else 'eine andere ID' end
            || ' hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start frühestens 1 min danach (' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai)',
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$$q1$;
  execute $q2$create or replace function public.prophos_firmen_abstand_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
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
  select p.user_id, coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) as t
    into wer, letzter
    from public.trade_plans p
   where p.id <> pl.id
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by t desc
   limit 1;
  if letzter is null or letzter <= now() - f then
    return jsonb_build_object('frei', true);
  end if;
  ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));   -- Jitter 10–30 s
  if wer = pl.user_id then
    name := 'deinem anderen Konto';                                         -- eigene ID (seit 1-min-Regel auch gezählt)
  else
    select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(wer::text, 8))
      into name from auth.users u where u.id = wer;                         -- nur Vorname, nie E-Mail
  end if;
  if pl.start_um is null or abs(extract(epoch from pl.start_um - ziel)) > 30 then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;   -- orbit_gesendet_at nie
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Firmen-Abstand 1 min] ' || k || ': ' || coalesce(name, 'andere ID') || ' hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start (Neu starten/von Hand) wartet bis ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai', 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'letzter', letzter);
end $$$q2$;
  select user_id into u1 from accounts group by user_id having count(*) >= 2 order by user_id limit 1;
  select id into a1 from accounts where user_id = u1 order by id limit 1;
  select id into a2 from accounts where user_id = u1 order by id limit 1 offset 1;
  select user_id into u2 from accounts where user_id <> u1 order by user_id limit 1;
  perform set_config('request.jwt.claims', json_build_object('sub', u1, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', u1::text, true);
  -- 1 andere ID vor 30 s gestartet
  insert into trade_plans (user_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u2, 'X', 'FA1-1', 'open', now() - interval '30 seconds', 'buy', now() - interval '30 seconds', now() - interval '30 seconds');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-1', 'planned', now(), 'buy') returning id into b;
  j := prophos_firmen_abstand_halten(b); erg := erg || '1 andere ID vor 30 s: frei=' || (j->>'frei') || ' wer=' || coalesce(j->>'wer','-') || ' ziel+' || coalesce(round(extract(epoch from (j->>'ziel')::timestamptz - (now() - interval '30 seconds')))::text, '-') || 's | ';
  -- 2 andere ID vor 70 s
  insert into trade_plans (user_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u2, 'X', 'FA1-2', 'open', now() - interval '70 seconds', 'buy', now() - interval '70 seconds', now() - interval '70 seconds');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-2', 'planned', now(), 'buy') returning id into b;
  j := prophos_firmen_abstand_halten(b); erg := erg || '2 andere ID vor 70 s: frei=' || (j->>'frei') || ' | ';
  -- 3 gleiche ID, anderes Konto vor 30 s
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, a2, 'K2', 'FA1-3', 'open', now() - interval '30 seconds', 'buy', now() - interval '30 seconds', now() - interval '30 seconds');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-3', 'planned', now(), 'buy') returning id into b;
  j := prophos_firmen_abstand_halten(b); erg := erg || '3 gleiche ID vor 30 s: frei=' || (j->>'frei') || ' wer=' || coalesce(j->>'wer','-') || ' | ';
  -- 4 andere Firma
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-4', 'planned', now(), 'buy') returning id into b;
  j := prophos_firmen_abstand_halten(b); erg := erg || '4 andere Firma: frei=' || (j->>'frei') || ' | ';
  -- 5 nur Claim (ohne Start) vor 30 s
  insert into trade_plans (user_id, master_name, master_firm, status, start_um, richtung, start_um_gestartet_at) values (u2, 'X', 'FA1-5', 'planned', now() - interval '30 seconds', 'buy', now() - interval '30 seconds');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-5', 'planned', now(), 'buy') returning id into b;
  j := prophos_firmen_abstand_halten(b); erg := erg || '5 Claim vor 30 s: frei=' || (j->>'frei') || ' | ';
  -- 6 Riegel am Claim: gleiche ID anderes Konto vor 20 s gestartet
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, a2, 'K2', 'FA1-6', 'open', now() - interval '20 seconds', 'buy', now() - interval '20 seconds', now() - interval '20 seconds');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-6', 'planned', now(), 'buy') returning id into c;
  update trade_plans set start_um_gestartet_at = now() where id = c and start_um_gestartet_at is null;
  select start_um, start_um_gestartet_at into su, cl from trade_plans where id = c;
  erg := erg || '6 Riegel Claim: claim=' || coalesce(cl::text, 'NULL') || ' start+' || round(extract(epoch from su - (now() - interval '20 seconds'))) || 's grund=' || coalesce((select left(grund, 90) from auto_plan_umplanung where plan_id = c order by um desc limit 1), '-') || ' | ';
  -- 7 Riegel frei: andere Firma
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-7', 'planned', now(), 'buy') returning id into c;
  update trade_plans set start_um_gestartet_at = now() where id = c and start_um_gestartet_at is null;
  erg := erg || '7 Riegel andere Firma: claim gesetzt=' || ((select start_um_gestartet_at from trade_plans where id = c) is not null)::text || ' | ';
  -- 8 Staffel: anderes Konto derselben ID vor 70 s geclaimt, Order erst vor 30 s raus → zählt der Claim → frei
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, a2, 'K2', 'FA1-8', 'open', now() - interval '70 seconds', 'buy', now() - interval '30 seconds', now() - interval '70 seconds');
  insert into trade_plans (user_id, master_account_id, master_name, master_firm, status, start_um, richtung) values (u1, a1, 'K1', 'FA1-8', 'planned', now(), 'buy') returning id into b;
  j := prophos_firmen_abstand_halten(b); erg := erg || '8 Staffel Claim vor 70 s / Order vor 30 s: frei=' || (j->>'frei') || ' | ';
  erg := erg || 'fenster=' || prophos_firmen_abstand_fenster()::text;
  raise exception 'FA1-PROBE (zurückgerollt): %', erg;
end $t$;