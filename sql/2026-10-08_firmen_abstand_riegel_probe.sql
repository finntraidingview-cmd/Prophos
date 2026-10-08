-- PROBE für sql/2026-10-08_firmen_abstand_riegel.sql (08.10.2026, Slave-Terminal 3, Prüfer-Befund a: „UPDATE derselben Zeile im
-- BEFORE-Trigger mit return NULL ungetestet — ein Fehler 27000 würde jeden betroffenen Claim abbrechen"). Legt Funktion + Trigger in
-- EINER Transaktion an, spielt 8 Fälle mit Platzhalter-Plänen der Firma „Riegeltest" durch und bricht mit RAISE ab → alles wird
-- zurückgerollt, die Ergebnisse stehen in der Fehlermeldung. Lauf 08.10.2026 ~01:20 UTC gegen die Live-DB (danach geprüft: 0 Funktionen,
-- 0 Trigger, 0 Testpläne, 0 Protokollzeilen übrig):
--   1 erster Start (ID1) frei: 1 Zeile | 2 Claim ID2 kurz danach: 0 Zeilen, start_um +347 s, Protokoll 1, Claim NULL |
--   3 erneuter Claim ID2: 0 Zeilen, Protokoll 1, start_um gleich true | 4 gleiche ID1: 1 Zeile |
--   5 ID1 nur Claim vor 3 min ohne Start (gescheitert) → ID2: 1 Zeile | 6 ID1 Claim vor 30 s, Start unterwegs → ID2: 0 Zeilen |
--   7 verpasst (Start vor 2 h) → ID2: 1 Zeile | 8 Firmen-Schlüssel: The5%ers / Apex Trader / MyFundedFutures
-- Kein Fehler 27000. Wiederholbar; ändert nichts dauerhaft.

do $test$
declare
  u1 uuid; u2 uuid; a uuid; b uuid; c uuid; e uuid; f uuid; g uuid; h uuid;
  n int; erg text := ''; s0 timestamptz; s1 timestamptz; p int;
begin
  execute $q1$create or replace function public.prophos_firma_key(name text) returns text
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
end $$$q1$;
  execute $q2$create or replace function public.trade_plans_firmen_abstand() returns trigger
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
end $$$q2$;
  execute $q3$drop trigger if exists trade_plans_firmen_abstand on public.trade_plans$q3$;
  execute $q4$create trigger trade_plans_firmen_abstand
  before update of start_um_gestartet_at on public.trade_plans
  for each row
  when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_firmen_abstand()$q4$;
  select id into u1 from auth.users order by created_at limit 1;
  select id into u2 from auth.users order by created_at limit 1 offset 1;
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u1, 'Riegeltest', 'planned', now() - interval '1 minute', 'buy') returning id into a;
  update trade_plans set start_um_gestartet_at = now(), started_at = now() where id = a and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '1 erster Start (ID1) frei: ' || n || ' Zeile | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'Riegeltest', 'planned', now(), 'sell') returning id into b;
  select start_um into s0 from trade_plans where id = b;
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count;
  select start_um into s1 from trade_plans where id = b;
  select count(*) into p from auto_plan_umplanung where plan_id = b;
  erg := erg || '2 Claim ID2 1 s danach: ' || n || ' Zeilen, start_um +' || round(extract(epoch from s1 - s0)) || ' s, Protokoll ' || p
         || ', Claim ' || coalesce((select start_um_gestartet_at::text from trade_plans where id = b), 'NULL') || ' | ';
  update trade_plans set start_um_gestartet_at = now() where id = b and start_um_gestartet_at is null;
  get diagnostics n = row_count;
  select count(*) into p from auto_plan_umplanung where plan_id = b;
  erg := erg || '3 erneuter Claim ID2: ' || n || ' Zeilen, Protokoll ' || p || ', start_um gleich ' || ((select start_um from trade_plans where id = b) = s1) || ' | ';
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u1, 'Riegeltest', 'planned', now(), 'buy') returning id into c;
  update trade_plans set start_um_gestartet_at = now() where id = c and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '4 gleiche ID1: ' || n || ' Zeile | ';
  delete from trade_plans where id = c;
  update trade_plans set started_at = null, orbit_gesendet_at = null, start_um_gestartet_at = now() - interval '3 minutes' where id = a;
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'Riegeltest', 'planned', now(), 'sell') returning id into e;
  update trade_plans set start_um_gestartet_at = now() where id = e and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '5 ID1 nur Claim vor 3 min ohne Start (gescheitert) → ID2: ' || n || ' Zeile | ';
  update trade_plans set start_um_gestartet_at = null where id = e;
  update trade_plans set start_um_gestartet_at = now() - interval '30 seconds' where id = a;
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'Riegeltest', 'planned', now(), 'sell') returning id into g;
  update trade_plans set start_um_gestartet_at = now() where id = g and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '6 ID1 Claim vor 30 s, Start unterwegs → ID2: ' || n || ' Zeilen | ';
  update trade_plans set start_um_gestartet_at = now(), started_at = now() where id = a;
  insert into trade_plans (user_id, master_firm, status, start_um, richtung) values (u2, 'Riegeltest', 'planned', now() - interval '2 hours', 'sell') returning id into h;
  update trade_plans set start_um_gestartet_at = now() where id = h and start_um_gestartet_at is null;
  get diagnostics n = row_count; erg := erg || '7 verpasst (Start vor 2 h) → ID2: ' || n || ' Zeile | ';
  erg := erg || '8 Firmen-Schlüssel: ' || prophos_firma_key('The 5ers') || ' / ' || prophos_firma_key('Apex') || ' / ' || prophos_firma_key('MyFoundedFutures');
  raise exception 'RIEGELTEST (alles zurückgerollt): %', erg;
end
$test$;