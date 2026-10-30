-- ZWEI ORBIT Stück 2 (30.10.2026, Auftrag ZWEI-ORBIT, Bauplan S5; Finn ~07:50: „2 Orbit je Fenster"): die DB lässt bis zu
-- puls_heim_regel.big_max_je_id Big Trades je ID und Fenster (TradingView / TopstepX) gleichzeitig zu. Standard 1 → alles wie heute
-- (zweiter wartet 15 min + 20–90 s). Ab 2: weitere Claims gehen durch, solange weniger als big_max_je_id laufen — den Abstand von 2.500 $
-- zum laufenden prüft der Klick-Riegel (/richtung/frei → puls_heim_zweit_pruefen, Stück 1, live VOR diesem Schalter). Ist es voll:
-- statt 15 min Marke mt5_baseline.start_sperre {art 'zweit', text, at, naechster, versuche}, Start in 1–1,5 min (Sofort-Start-Wächter
-- im Tab, S7, fragt /admin/zweit-frei), Protokoll „[Zwei Orbit] …" nur beim ersten Mal.
-- prophos_big_trade_max(): Spalte/Zeile fehlt oder Fehler → 1 (fail-closed). prophos_big_trade_anzahl: dieselbe Auswahl wie
-- prophos_big_trade_laeuft (Fenster-Klausel + prophos_wd_wie, Stück 0), nur gezählt. prophos_big_trade_laeuft selbst bleibt unverändert.
-- GEMEINSAME FASSUNG: sql/2026-10-30_apex_hedge.sql trägt seit diesem Commit dieselben Funktionstexte (Zeichen für Zeichen, per Skript
-- verglichen) — wer prophos_big_trade_halten / trade_plans_big_trade danach neu anlegt, nimmt alle Blöcke mit (prophos_wd_wie + Zwei Orbit).
-- Voraussetzung: sql/2026-10-30_big_trade_fenster_zurueck.sql (prophos_big_trade_fenster), sql/2026-10-30_puls_heim_zweit.sql (Spalte;
-- ohne sie gilt 1). Wiederholbar. Schalter an NUR auf Finns Wort, zuerst eine Test-ID:
--   update public.puls_heim_regel set big_max_je_id = 2 where id = 1;   -- (gilt für alle IDs — Test-ID-Steuerung gibt es noch nicht)
-- Rückbau: big_max_je_id = 1 genügt.

do $pruef$
begin
  perform 'public.prophos_big_trade_fenster(text)'::regprocedure;
  perform 'public.prophos_wd_wie(boolean, jsonb)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-30_big_trade_fenster_zurueck.sql (und sql/2026-10-30_apex_hedge.sql) einspielen';
end $pruef$;

CREATE OR REPLACE FUNCTION public.prophos_big_trade_max()
 RETURNS integer
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  m integer;
begin
  -- ZWEI ORBIT (30.10.2026): Big Trades je ID und Fenster gleichzeitig = puls_heim_regel.big_max_je_id (1 = nur einer, wie bis heute).
  -- Spalte/Zeile fehlt oder Fehler → 1 (fail-closed: wie bisher nur einer)
  select r.big_max_je_id into m from public.puls_heim_regel r where r.id = 1;
  return greatest(1, least(3, coalesce(m, 1)));
exception when others then
  return 1;
end $function$;

CREATE OR REPLACE FUNCTION public.prophos_big_trade_anzahl(p_id uuid, p_user uuid)
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  -- dieselbe Auswahl wie prophos_big_trade_laeuft (Fenster, prophos_wd_wie, open bzw. gerade gesendet/geclaimt), nur gezählt
  select count(*)::integer
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and public.prophos_big_trade(p.route, p.hedge_eur, p.orbit_v3, public.prophos_wd_wie(p.winning_day, p.mt5_baseline))
     and (not exists (select 1 from public.trade_plans s where s.id = p_id)
          or public.prophos_big_trade_fenster(p.route) = (select public.prophos_big_trade_fenster(s.route) from public.trade_plans s where s.id = p_id))
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
$function$;
revoke all on function public.prophos_big_trade_anzahl(uuid, uuid) from public;

CREATE OR REPLACE FUNCTION public.prophos_big_trade_halten(p_plan uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  pl public.trade_plans%rowtype;
  c record;
  ziel timestamptz;
  mx integer;
  n integer;
begin
  select * into pl from public.trade_plans where id = p_plan;
  if not found or pl.user_id is distinct from auth.uid() then
    return jsonb_build_object('frei', true, 'grund', 'kein eigener Plan');
  end if;
  if pl.status is distinct from 'planned' or not public.prophos_big_trade(pl.route, pl.hedge_eur, pl.orbit_v3, public.prophos_wd_wie(pl.winning_day, pl.mt5_baseline)) then
    return jsonb_build_object('frei', true);
  end if;
  if pl.started_at is not null or pl.orbit_gesendet_at is not null then
    return jsonb_build_object('frei', true, 'grund', 'Order schon gesendet — kein Eingriff');
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_big_trade:' || pl.user_id::text));
  select * into c from public.prophos_big_trade_laeuft(pl.id, pl.user_id);
  if c.plan_id is null then
    return jsonb_build_object('frei', true);
  end if;
  -- ZWEI ORBIT (30.10.2026): bis big_max_je_id gleichzeitig — die 2.500-$-Prüfung macht der Klick-Riegel (/richtung/frei, puls_heim_zweit_pruefen)
  mx := public.prophos_big_trade_max();
  if mx > 1 then
    n := public.prophos_big_trade_anzahl(pl.id, pl.user_id);
    if n < mx then
      return jsonb_build_object('frei', true, 'zweit', true, 'grund', 'weiterer Big Trade erlaubt — Abstand zum laufenden prüft der Klick');
    end if;
    ziel := now() + interval '1 minute' + make_interval(secs => floor(random() * 30));
    update public.trade_plans
       set start_um = ziel, start_um_gestartet_at = null,
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
             'art', 'zweit', 'text', 'schon ' || n || ' Big Trades in diesem Fenster (höchstens ' || mx || ')', 'at', now(), 'naechster', ziel,
             'versuche', case when mt5_baseline->'start_sperre'->>'art' = 'zweit' then coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1 else 1 end))
     where id = pl.id;
    return jsonb_build_object('frei', false, 'laeuft', true, 'zweit', true, 'ziel', ziel, 'wer', coalesce(c.name, '?'), 'seit', c.seit,
                              'grund', 'schon ' || n || ' Big Trades in diesem Fenster (höchstens ' || mx || ')');
  end if;
  ziel := now() + interval '15 minutes' + make_interval(secs => 20 + floor(random() * 70));
  if pl.start_um is null or pl.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Big Trade] „' || coalesce(c.name, '?') || '" läuft in diesem Fenster seit ' || to_char(c.seit at time zone 'Asia/Dubai', 'HH24:MI')
            || ' Dubai — Start (Neu starten/von Hand) wartet bis ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'laeuft', true, 'ziel', ziel, 'wer', coalesce(c.name, '?'), 'seit', c.seit,
                            'grund', 'Big Trade „' || coalesce(c.name, '?') || '" läuft noch in diesem Fenster');
end $function$;

CREATE OR REPLACE FUNCTION public.trade_plans_big_trade()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  c record;
  ziel timestamptz;
  mx integer;
  n integer;
  ss jsonb;
begin
  if new.status is distinct from 'planned' or not public.prophos_big_trade(new.route, new.hedge_eur, new.orbit_v3, public.prophos_wd_wie(new.winning_day, new.mt5_baseline)) then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_big_trade:' || new.user_id::text));
  select * into c from public.prophos_big_trade_laeuft(new.id, new.user_id);
  if c.plan_id is null then
    return new;
  end if;
  -- ZWEI ORBIT (30.10.2026): bis big_max_je_id gleichzeitig (Claim geht durch, den 2.500-$-Abstand prüft der Klick-Riegel). Voll →
  -- Marke start_sperre art 'zweit' + Start in 1–1,5 min statt 15 min (der Sofort-Start-Wächter im Tab fragt /admin/zweit-frei)
  mx := public.prophos_big_trade_max();
  if mx > 1 then
    n := public.prophos_big_trade_anzahl(new.id, new.user_id);
    if n < mx then
      return new;
    end if;
    ss := new.mt5_baseline->'start_sperre';
    ziel := now() + interval '1 minute' + make_interval(secs => floor(random() * 30));
    update public.trade_plans
       set start_um = ziel,
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
             'art', 'zweit', 'text', 'schon ' || n || ' Big Trades in diesem Fenster (höchstens ' || mx || ')', 'at', now(), 'naechster', ziel,
             'versuche', case when ss->>'art' = 'zweit' then coalesce((ss->>'versuche')::int, 0) + 1 else 1 end))
     where id = new.id;
    if coalesce(ss->>'art', '') <> 'zweit' then
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
              '[Zwei Orbit] schon ' || n || ' Big Trades in diesem Fenster (höchstens ' || mx || ') — startet, sobald einer zu ist', 'start');
    end if;
    return null;
  end if;
  ziel := now() + interval '15 minutes' + make_interval(secs => 20 + floor(random() * 70));
  if old.start_um is null or old.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Big Trade] „' || coalesce(c.name, '?') || '" läuft in diesem Fenster seit ' || to_char(c.seit at time zone 'Asia/Dubai', 'HH24:MI')
            || ' Dubai — Orbit/Topstep nur ein Big Trade gleichzeitig, neue Prüfung ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;
end $function$;
