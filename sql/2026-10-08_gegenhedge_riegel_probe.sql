-- PROBE für sql/2026-10-08_gegenhedge_riegel.sql (08.10.2026, Slave-Terminal 4). Legt prophos_firma_key, den Firmen-Abstand-Riegel und
-- den Gegenhedge-Riegel in EINER Transaktion an (Text 1:1 aus beiden Dateien, erzeugt), spielt Fälle mit Platzhalter-Plänen eigener
-- Firmennamen („GH-Test n") durch und bricht mit RAISE ab → alles wird zurückgerollt, die Ergebnisse stehen in der Fehlermeldung.
-- Erwartung: 1 läuft gegenläufig → 0 Zeilen, +30 min, Protokoll 1 | 11 zweiter Claim → 0, Protokoll bleibt 1 | 2 gleiche Richtung → 1 |
-- 3 gleiche ID → 1 | 4 andere Firma → 1 | 5 Gegenseite beendet → 1 | 6 Gegenseite früher geplant → 0, deren Start + 30 min |
-- 7 Gegenseite später → 1 | 8 Gegenseite unbestätigt → 1 | 9 Start unterwegs → 0 (Firmen-Abstand zuerst) | 10 verpasst → 1 |
-- 12 RPC Hand-Start gegen laufende Gegenseite → frei false, ziel ≈ jetzt + 30 min | 13 RPC gleiche Richtung → frei true.
-- Lauf 08.10.2026 ~02:16 UTC gegen die Live-DB (Funktionstext ohne Kommentarzeilen, sonst identisch), alle 13 wie erwartet:
--   1 läuft gegenläufig: 0 Zeilen, +31 min, Protokoll 1 („[Gegenhedge] GH-Test 1: eine andere ID läuft dort in Gegenrichtung …“) |
--   11 zweiter Claim: 0 Zeilen, Protokoll 1 | 2: 1 | 3: 1 | 4: 1 | 5: 1 | 6: 0 Zeilen, neuer Start = deren Start +30 min | 7: 1 | 8: 1 |
--   9: 0 Zeilen ([Firmen-Abstand] greift zuerst) | 10: 1 | 12 RPC: {frei:false, ziel jetzt+30 min, wer Vorname, grund „läuft dort …“} |
--   13 RPC: {frei:true}. Danach geprüft: 0 Funktionen, 0 Trigger, 0 Testpläne, 0 Protokollzeilen übrig.

do $test$
declare
  u1 uuid; u2 uuid; a uuid; b uuid; n int; erg text := ''; s0 timestamptz; s1 timestamptz; p int;
begin
  execute $q0$create or replace function public.prophos_firma_key(name text) returns text
language plpgsql immutable as $$
declare
  f text := lower(btrim(coalesce(name, '')));
begin
  -- gleiche Reihenfolge wie app.py _firm_norm / _FIRM_RULES (tools/selftest_auto_firmen_abstand.py prüft den Gleichlauf)
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
end $$$q0$;
  execute $q1$create or replace function public.trade_plans_firmen_abstand() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  letzter timestamptz;
  ziel timestamptz;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;                                   -- „verpasst"-Claim: startet nichts, nicht aufhalten
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- echter Start (started_at/orbit_gesendet_at) zählt 5 min; ein Claim ohne Start nur 2 min (Start unterwegs), danach gilt er als
  -- gescheitert und sperrt nicht mehr
  select max(case when p.started_at is not null or p.orbit_gesendet_at is not null
                  then greatest(coalesce(p.started_at, '-infinity'::timestamptz), coalesce(p.orbit_gesendet_at, '-infinity'::timestamptz))
                  else p.start_um_gestartet_at end)
    into letzter
    from public.trade_plans p
   where p.id <> new.id
     and p.user_id is distinct from new.user_id
     and (p.started_at > now() - interval '5 minutes'
          or p.orbit_gesendet_at > now() - interval '5 minutes'
          or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null and p.orbit_gesendet_at is null))
     and public.prophos_firma_key(p.master_firm) = k;
  if letzter is null or letzter <= now() - interval '5 minutes' then
    return new;                                   -- frei: Claim normal schreiben
  end if;
  ziel := letzter + interval '5 minutes' + make_interval(secs => 20 + floor(random() * 70));
  if old.start_um is null or old.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel where id = new.id;   -- Spalte start_um: dieser Trigger feuert dafür nicht
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Firmen-Abstand] ' || k || ': eine andere ID hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start frühestens 5 min danach (' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ')',
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$$q1$;
  execute $q2$drop trigger if exists trade_plans_firmen_abstand on public.trade_plans$q2$;
  execute $q3$create trigger trade_plans_firmen_abstand
  before update of start_um_gestartet_at on public.trade_plans
  for each row
  when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_firmen_abstand()$q3$;
  execute $q4$create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)
returns table(ziel timestamptz, wer uuid, grund text)
language plpgsql stable security definer set search_path = public as $$
declare
  k text := public.prophos_firma_key(p_firma);
  gegen text := case p_richtung when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  t timestamptz;
  u uuid;
begin
  if gegen is null or coalesce(btrim(p_firma), '') = '' then
    return;
  end if;
  -- (a) eine andere ID läuft gegenläufig (oder ihr Start ist gerade unterwegs)
  select coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now()), p.user_id
    into t, u
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id is distinct from p_user
     and p.richtung = gegen
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if t is not null then
    return query select now() + interval '30 minutes', u,
      'läuft dort in Gegenrichtung (seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)';
    return;
  end if;
  -- (b) eine andere ID startet gegenläufig früher (bestätigt/Hand, noch nicht geclaimt, höchstens 30 min alt) — der Spätere weicht
  select p.start_um, p.user_id
    into t, u
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id is distinct from p_user
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
      'startet dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung';
  end if;
end $$$q4$;
  execute $q5$create or replace function public.trade_plans_gegenhedge() returns trigger
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
            '[Gegenhedge] ' || k || ': eine andere ID ' || c.grund || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$$q5$;
  execute $q6$drop trigger if exists trade_plans_gegenhedge on public.trade_plans$q6$;
  execute $q7$create trigger trade_plans_gegenhedge
  before update of start_um_gestartet_at on public.trade_plans
  for each row
  when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_gegenhedge()$q7$;
  execute $q8$create or replace function public.prophos_gegenhedge_halten(p_plan uuid) returns jsonb
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
  select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(c.wer::text, 8))
    into name from auth.users u where u.id = c.wer;                                -- nur Vorname, nie E-Mail
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
end $$$q8$;
  select id into u1 from auth.users order by created_at limit 1;
  select id into u2 from auth.users order by created_at limit 1 offset 1;
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, 'GH-Test 1', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 1', 'planned', now(), 'sell') returning id into b;
  select start_um into s0 from trade_plans where id = b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; select start_um into s1 from trade_plans where id = b; select count(*) into p from auto_plan_umplanung where plan_id = b;
  erg := erg || '1 läuft gegenläufig: ' || n || ' Zeilen, +' || round(extract(epoch from s1 - s0) / 60) || ' min, Protokoll ' || p || ' („' || coalesce((select left(grund, 95) from auto_plan_umplanung where plan_id = b limit 1), '') || '“) | ';
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; select count(*) into p from auto_plan_umplanung where plan_id = b;
  erg := erg || '11 zweiter Claim: ' || n || ' Zeilen, Protokoll ' || p || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 1', 'planned', now(), 'buy') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '2 gleiche Richtung: ' || n || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, 'GH-Test 3', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u1, 'GH-Test 3', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '3 gleiche ID: ' || n || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 4', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '4 andere Firma: ' || n || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, 'GH-Test 5', 'review', now() - interval '40 minutes', 'buy', now() - interval '40 minutes', now() - interval '40 minutes');
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 5', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '5 Gegenseite beendet: ' || n || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u1, 'GH-Test 6', 'planned', now() - interval '5 minutes', 'buy') returning id into a;
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 6', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; select start_um into s1 from trade_plans where id = b;
  erg := erg || '6 Gegenseite früher geplant: ' || n || ' Zeilen, neuer Start = deren Start +' || round(extract(epoch from s1 - (select start_um from trade_plans where id = a)) / 60) || ' min | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u1, 'GH-Test 7', 'planned', now() + interval '10 minutes', 'buy');
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 7', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '7 Gegenseite später: ' || n || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, auto_plan) values (u1, 'GH-Test 8', 'planned', now() - interval '5 minutes', 'buy', true);
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 8', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '8 Gegenseite unbestätigt: ' || n || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, start_um_gestartet_at) values (u1, 'GH-Test 9', 'planned', now() - interval '1 minute', 'buy', now() - interval '30 seconds');
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 9', 'planned', now(), 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '9 Start unterwegs: ' || n || ' Zeilen (' || coalesce((select left(grund, 17) from auto_plan_umplanung where plan_id = b limit 1), '-') || ') | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung, started_at, start_um_gestartet_at) values (u1, 'GH-Test 10', 'open', now() - interval '10 minutes', 'buy', now() - interval '10 minutes', now() - interval '10 minutes');
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'GH-Test 10', 'planned', now() - interval '2 hours', 'sell') returning id into b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '10 verpasst: ' || n;
  -- 12/13: RPC prophos_gegenhedge_halten (Hand-Start ohne Startzeit) als ID2
  perform set_config('request.jwt.claims', json_build_object('sub', u2::text, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', u2::text, true);
  insert into trade_plans (user_id, master_firm, status, richtung) values (u2, 'GH-Test 1', 'planned', 'sell') returning id into b;
  erg := erg || ' | 12 RPC Hand-Start gegen laufende ID1: ' || coalesce((select (prophos_gegenhedge_halten(b))::text), 'null');
  insert into trade_plans (user_id, master_firm, status, richtung) values (u2, 'GH-Test 1', 'planned', 'buy') returning id into b;
  erg := erg || ' | 13 RPC gleiche Richtung: ' || coalesce((select (prophos_gegenhedge_halten(b))::text), 'null');
  raise exception 'GEGENHEDGE-TEST (alles zurückgerollt): %', erg;
end $test$;
