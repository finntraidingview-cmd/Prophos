-- PROBE für sql/2026-10-08_firmen_abstand_pruefen_rpc.sql (08.10.2026, Slave-Terminal 3, Prüfer: orbit_gesendet_at nie anfassen).
-- Legt prophos_firma_key + prophos_firmen_abstand_halten in EINER Transaktion an, simuliert Logins per set_config('request.jwt.claims'),
-- spielt 7 Fälle mit Platzhalter-Plänen der Firma „Riegeltest" durch und bricht mit RAISE ab → alles zurückgerollt. Lauf ~01:45 UTC:
--   1 andere ID vor 1 min echt gestartet → false, ziel +275 s, Claim NULL, orbit NULL (nie gesetzt, nie gelöscht), Protokoll 1, Name ein Wort ohne @
--   2 nochmal → false, Protokoll 1 (kein Spam) | 3 eigene Order schon gesendet → true („Order schon gesendet — kein Eingriff"), orbit + start_um unverändert
--   4 fremder Plan → true („kein eigener Plan") | 5 ID1 → false (richtig: ID2 hat in Fall 3 vor 10 s eine Order gesendet)
--   6 ID1 nur Claim vor 3 min ohne Start (gescheitert) → true | 7 ID1 Claim vor 30 s, Start unterwegs → false
-- Danach geprüft: 0 Funktionen, 0 Testpläne, 0 Protokollzeilen übrig. Wiederholbar; ändert nichts dauerhaft.

do $test$
declare
  u1 uuid; u2 uuid; a uuid; b uuid; c uuid; d uuid; e uuid; j jsonb; erg text := ''; s0 timestamptz; p int;
begin
  execute $q1$create or replace function public.prophos_firma_key(name text) returns text
language plpgsql immutable as $$
declare
  f text := lower(btrim(coalesce(name, '')));
begin
  if f = '' then return '—'; end if;
  if strpos(f, '5%er') > 0 or strpos(f, '5ers') > 0 or strpos(f, 'five percent') > 0 then return 'The5%ers'; end if;
  if strpos(f, 'futur') > 0 and (strpos(f, 'fundednext') > 0 or strpos(f, 'funded next') > 0
                                 or strpos(f, 'foundednext') > 0 or strpos(f, 'founded next') > 0) then return 'FundedNext Futures'; end if;
  if (strpos(f, 'funded') > 0 or strpos(f, 'founded') > 0) and strpos(f, 'futur') > 0 then return 'MyFundedFutures'; end if;
  if strpos(f, 'apex') > 0 then return 'Apex Trader'; end if;
  if strpos(f, 'tradeify') > 0 then return 'Tradeify'; end if;
  if strpos(f, 'fundednext') > 0 or strpos(f, 'founded next') > 0 or strpos(f, 'foundednext') > 0 then return 'FundedNext'; end if;
  if strpos(f, 'fundingpips') > 0 or strpos(f, 'funding pips') > 0 then return 'FundingPips'; end if;
  if strpos(f, 'topstep') > 0 then return 'Topstep'; end if;
  if strpos(f, 'ftmo') > 0 then return 'FTMO'; end if;
  if strpos(f, 'alpha') > 0 then return 'Alpha Future'; end if;
  if strpos(f, 'fusion') > 0 then return 'Fusion Markets'; end if;
  if strpos(f, 'lucid') > 0 then return 'Lucid Trading'; end if;
  return btrim(coalesce(name, ''));
end $$$q1$;
  execute $q2$create or replace function public.prophos_firmen_abstand_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pl public.trade_plans%rowtype;
  k text;
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
  select p.user_id,
         case when p.started_at is not null or p.orbit_gesendet_at is not null
              then greatest(coalesce(p.started_at, '-infinity'::timestamptz), coalesce(p.orbit_gesendet_at, '-infinity'::timestamptz))
              else p.start_um_gestartet_at end as t
    into wer, letzter
    from public.trade_plans p
   where p.id <> pl.id
     and p.user_id is distinct from pl.user_id
     and (p.started_at > now() - interval '5 minutes'
          or p.orbit_gesendet_at > now() - interval '5 minutes'
          or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null and p.orbit_gesendet_at is null))
     and public.prophos_firma_key(p.master_firm) = k
   order by t desc
   limit 1;
  if letzter is null or letzter <= now() - interval '5 minutes' then
    return jsonb_build_object('frei', true);
  end if;
  ziel := letzter + interval '5 minutes' + make_interval(secs => 20 + floor(random() * 70));
  select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(wer::text, 8))
    into name from auth.users u where u.id = wer;
  if pl.start_um is null or abs(extract(epoch from pl.start_um - ziel)) > 120 then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Firmen-Abstand] ' || k || ': ' || coalesce(name, 'andere ID') || ' hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start (Neu starten/von Hand) wartet bis ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'letzter', letzter);
end $$$q2$;
  select id into u1 from auth.users order by created_at limit 1;
  select id into u2 from auth.users order by created_at limit 1 offset 1;
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, 'Riegeltest', 'open', now() - interval '1 minute', 'buy', now() - interval '1 minute', now() - interval '1 minute') returning id into a;
  perform set_config('request.jwt.claim.sub', u2::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u2::text, 'role', 'authenticated')::text, true);
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, start_um_gestartet_at) values (u2, 'Riegeltest', 'planned', now(), 'sell', now()) returning id into b;
  j := public.prophos_firmen_abstand_halten(b);
  select count(*) into p from auto_plan_umplanung where plan_id = b;
  erg := erg || '1 andere ID vor 1 min echt gestartet → ' || (j->>'frei') || ', ziel +' || round(extract(epoch from (j->>'ziel')::timestamptz - now()))
         || ' s, Claim ' || coalesce((select start_um_gestartet_at::text from trade_plans where id = b), 'NULL')
         || ', orbit ' || coalesce((select orbit_gesendet_at::text from trade_plans where id = b), 'NULL') || ', Protokoll ' || p
         || ', Name ein Wort ohne @: ' || (position('@' in (j->>'wer')) = 0 and position(' ' in (j->>'wer')) = 0) || ' | ';
  j := public.prophos_firmen_abstand_halten(b);
  select count(*) into p from auto_plan_umplanung where plan_id = b;
  erg := erg || '2 nochmal → ' || (j->>'frei') || ', Protokoll ' || p || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, orbit_gesendet_at) values (u2, 'Riegeltest', 'planned', now(), 'sell', now() - interval '10 seconds') returning id into c;
  select start_um into s0 from trade_plans where id = c;
  j := public.prophos_firmen_abstand_halten(c);
  erg := erg || '3 eigene Order schon gesendet → ' || (j->>'frei') || ' (' || coalesce(j->>'grund', '') || '), orbit unverändert '
         || ((select orbit_gesendet_at from trade_plans where id = c) is not null) || ', start_um unverändert ' || ((select start_um from trade_plans where id = c) = s0) || ' | ';
  perform set_config('request.jwt.claim.sub', u1::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u1::text, 'role', 'authenticated')::text, true);
  j := public.prophos_firmen_abstand_halten(b);
  erg := erg || '4 fremder Plan (Login ID1, Plan ID2) → ' || (j->>'frei') || ' (' || coalesce(j->>'grund', '') || ') | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u1, 'Riegeltest', 'planned', now(), 'buy') returning id into d;
  j := public.prophos_firmen_abstand_halten(d);
  erg := erg || '5 gleiche ID1 → ' || (j->>'frei') || ' | ';
  update trade_plans set started_at = null, status = 'planned', start_um_gestartet_at = now() - interval '3 minutes' where id = a;
  perform set_config('request.jwt.claim.sub', u2::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u2::text, 'role', 'authenticated')::text, true);
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'Riegeltest', 'planned', now(), 'sell') returning id into e;
  j := public.prophos_firmen_abstand_halten(e);
  erg := erg || '6 ID1 nur Claim vor 3 min ohne Start (gescheitert) → ' || (j->>'frei') || ' | ';
  update trade_plans set start_um_gestartet_at = now() - interval '30 seconds' where id = a;
  j := public.prophos_firmen_abstand_halten(e);
  erg := erg || '7 ID1 Claim vor 30 s, Start unterwegs → ' || (j->>'frei');
  raise exception 'RPC-PROBE (alles zurückgerollt): %', erg;
end
$test$;