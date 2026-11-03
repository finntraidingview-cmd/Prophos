-- ZWEI ORBIT: JE FIRMA NUR EIN BIG TRADE + MARKTERÖFFNUNG (03.11.2026, Auftrag Z5; Finn ~17:40 Dubai):
--  (a) „Bei jeder Firma nur ein einziger Big Trade" — je ID: dieselbe ID darf bei derselben Firma (prophos_firma_key(master_firm)) nie zwei
--      Big Trades gleichzeitig haben, über beide Fenster (TradingView / TopstepX) und auch bei big_max_je_id = 2. Big Trade = prophos_big_trade
--      wie heute (Orbit MIT Hedge, Polar); Orbit V2 ohne Hedge zählt nicht. Läuft = dieselbe Auswahl wie prophos_big_trade_anzahl (open bzw.
--      gerade gesendet/geclaimt), nur ohne Fenster-Klausel und mit Firmen-Klausel.
--  (b) Markteröffnung: in 09:28–09:35 America/New_York (heute 18:28–18:35 Dubai, wandert mit der US-Zeitumstellung) startet KEIN WEITERER
--      Big Trade, wenn bei der ID im Fenster schon einer läuft (Finn: „nicht aktiv sein, sondern starten"). Laufen schon big_max_je_id, greift
--      wie bisher „voll". Nach dem Fenster gilt wieder der Schalter. Mit big_max_je_id = 1 ändert (b) nichts (dann wartet ein zweiter ohnehin).
-- Gleiche Entscheidung im Klick-Riegel: app.py puls_heim_zweit_urteil / puls_heim_zweit_pruefen (Codes firma_laeuft / markt_oeffnung,
-- Fenster PULS_HEIM_MARKT_NY). Reihenfolge an beiden Stellen: nichts im Fenster → nur (a); sonst voll (big_max_je_id, bei 1 der alte 15-min-Weg)
-- → (a) → (b) → frei.
-- Sperre: Marke mt5_baseline.start_sperre {art 'firma' | 'markt', text, at, naechster, versuche}; (a) neue Prüfung in 1–1,5 min (bis der
-- andere zu ist), (b) Start nach Fensterende + 20–90 s gestreut. Protokoll in auto_plan_umplanung nur beim ersten Mal je Art.
-- NEUE FASSUNG von prophos_big_trade_halten und trade_plans_big_trade: ersetzt die Texte aus sql/2026-10-30_zwei_big_trades.sql und
-- sql/2026-10-30_apex_hedge.sql (dort bleiben sie als Geschichte; wer neu anlegt, nimmt diese Datei NACH jenen beiden).
-- Schalter big_max_je_id wird nicht angefasst. Wiederholbar (create or replace).

do $pruef$
begin
  perform 'public.prophos_big_trade_fenster(text)'::regprocedure;
  perform 'public.prophos_wd_wie(boolean, jsonb)'::regprocedure;
  perform 'public.prophos_big_trade_anzahl(uuid, uuid)'::regprocedure;
  perform 'public.prophos_firma_key(text)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-30_big_trade_fenster_zurueck.sql, sql/2026-10-30_apex_hedge.sql und sql/2026-10-30_zwei_big_trades.sql einspielen';
end $pruef$;

-- (b) Fensterende (timestamptz), wenn p_jetzt in 09:28–09:35 New York liegt, sonst null. Wie app.py puls_heim_markt_oeffnung.
CREATE OR REPLACE FUNCTION public.prophos_big_trade_markt_oeffnung(p_jetzt timestamptz)
 RETURNS timestamptz
 LANGUAGE sql
 STABLE
AS $function$
  select case when (p_jetzt at time zone 'America/New_York')::time >= time '09:28'
               and (p_jetzt at time zone 'America/New_York')::time <  time '09:35'
         then (((p_jetzt at time zone 'America/New_York')::date + time '09:35') at time zone 'America/New_York') end
$function$;

-- (a) ein laufender Big Trade DERSELBEN ID bei DERSELBEN FIRMA (beide Fenster) — Auswahl wie prophos_big_trade_anzahl ohne Fenster-Klausel
CREATE OR REPLACE FUNCTION public.prophos_big_trade_firma(p_id uuid, p_user uuid)
 RETURNS TABLE(plan_id uuid, name text, firma text, seit timestamp with time zone)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select p.id, p.master_name, public.prophos_firma_key(p.master_firm), coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now())
    from public.trade_plans p
    join public.trade_plans s on s.id = p_id
   where p.id <> p_id
     and p.user_id = p_user
     and public.prophos_big_trade(p.route, p.hedge_eur, p.orbit_v3, public.prophos_wd_wie(p.winning_day, p.mt5_baseline))
     and public.prophos_firma_key(p.master_firm) = public.prophos_firma_key(s.master_firm)
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
   order by 4 desc
   limit 1
$function$;
revoke all on function public.prophos_big_trade_firma(uuid, uuid) from public;
revoke all on function public.prophos_big_trade_firma(uuid, uuid) from anon, authenticated;   -- liest fremde IDs, nur über Halten/Trigger

-- Marke start_sperre + neuer Start setzen (Halten und Claim-Trigger), Protokoll nur beim ersten Mal je Art. Nie vorziehen.
CREATE OR REPLACE FUNCTION public.prophos_big_trade_sperre(p_id uuid, p_art text, p_text text, p_ziel timestamptz)
 RETURNS timestamptz
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  pl public.trade_plans%rowtype;
  ziel timestamptz;
begin
  select * into pl from public.trade_plans where id = p_id;
  if not found then
    return p_ziel;
  end if;
  ziel := greatest(p_ziel, coalesce(pl.start_um, p_ziel));
  update public.trade_plans
     set start_um = ziel, start_um_gestartet_at = null,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', p_art, 'text', p_text, 'at', now(), 'naechster', ziel,
           'versuche', case when mt5_baseline->'start_sperre'->>'art' = p_art then coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1 else 1 end))
   where id = p_id;
  if coalesce(pl.mt5_baseline->'start_sperre'->>'art', '') <> p_art then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            case p_art when 'firma' then '[Ein Big Trade je Firma] ' else '[Markteröffnung] ' end || p_text, 'start');
  end if;
  return ziel;
end $function$;
revoke all on function public.prophos_big_trade_sperre(uuid, text, text, timestamptz) from public;
revoke all on function public.prophos_big_trade_sperre(uuid, text, text, timestamptz) from anon, authenticated;   -- schreibt jeden Plan, nur über Halten/Trigger

CREATE OR REPLACE FUNCTION public.prophos_big_trade_halten(p_plan uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  pl public.trade_plans%rowtype;
  c record;
  f record;
  ziel timestamptz;
  bis timestamptz;
  mx integer;
  n integer;
  t text;
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
  -- JE FIRMA NUR EINER (03.11.2026, Finn: „Bei jeder Firma nur ein einziger Big Trade"): über beide Fenster, unabhängig vom Schalter
  select * into f from public.prophos_big_trade_firma(pl.id, pl.user_id);
  if c.plan_id is null then
    if f.plan_id is null then
      return jsonb_build_object('frei', true);
    end if;
    t := 'Big Trade „' || coalesce(f.name, '?') || '" läuft schon bei ' || f.firma || ' — je Firma nur einer gleichzeitig';
    ziel := public.prophos_big_trade_sperre(pl.id, 'firma', t, now() + interval '1 minute' + make_interval(secs => floor(random() * 30)));
    return jsonb_build_object('frei', false, 'laeuft', true, 'zweit', true, 'code', 'firma_laeuft', 'firma', f.firma, 'ziel', ziel,
                              'wer', coalesce(f.name, '?'), 'seit', f.seit, 'grund', t);
  end if;
  -- ZWEI ORBIT (30.10.2026): bis big_max_je_id gleichzeitig — die 2.500-$-Prüfung macht der Klick-Riegel (/richtung/frei, puls_heim_zweit_pruefen)
  mx := public.prophos_big_trade_max();
  if pl.route = 'polar' then
    mx := 1;          -- Polar startet ohne Panel-Klick (kein /richtung/frei, keine 2.500-$-Prüfung) → nie als weiterer Big Trade
  end if;
  if mx > 1 then
    n := public.prophos_big_trade_anzahl(pl.id, pl.user_id);
    if n >= mx then
      ziel := greatest(now() + interval '1 minute' + make_interval(secs => floor(random() * 30)), coalesce(pl.start_um, now()));   -- nie vorziehen
      update public.trade_plans
         set start_um = ziel, start_um_gestartet_at = null,
             mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
               'art', 'zweit', 'text', 'schon ' || n || ' Big Trades in diesem Fenster (höchstens ' || mx || ')', 'at', now(), 'naechster', ziel,
               'versuche', case when mt5_baseline->'start_sperre'->>'art' = 'zweit' then coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1 else 1 end))
       where id = pl.id;
      return jsonb_build_object('frei', false, 'laeuft', true, 'zweit', true, 'code', 'zweit_wartet', 'ziel', ziel, 'wer', coalesce(c.name, '?'), 'seit', c.seit,
                                'grund', 'schon ' || n || ' Big Trades in diesem Fenster (höchstens ' || mx || ')');
    end if;
    if f.plan_id is not null then
      t := 'Big Trade „' || coalesce(f.name, '?') || '" läuft schon bei ' || f.firma || ' — je Firma nur einer gleichzeitig';
      ziel := public.prophos_big_trade_sperre(pl.id, 'firma', t, now() + interval '1 minute' + make_interval(secs => floor(random() * 30)));
      return jsonb_build_object('frei', false, 'laeuft', true, 'zweit', true, 'code', 'firma_laeuft', 'firma', f.firma, 'ziel', ziel,
                                'wer', coalesce(f.name, '?'), 'seit', f.seit, 'grund', t);
    end if;
    -- MARKTERÖFFNUNG (03.11.2026, Finn: kein weiterer Big Trade starten in 18:28–18:35 Dubai = 09:28–09:35 New York)
    bis := public.prophos_big_trade_markt_oeffnung(now());
    if bis is not null then
      t := 'Markteröffnung 09:28–09:35 New York (bis ' || to_char(bis at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai): kein weiterer Big Trade, solange „'
           || coalesce(c.name, '?') || '" läuft';
      ziel := public.prophos_big_trade_sperre(pl.id, 'markt', t, bis + make_interval(secs => 20 + floor(random() * 70)));
      return jsonb_build_object('frei', false, 'laeuft', true, 'zweit', true, 'code', 'markt_oeffnung', 'bis', bis, 'ziel', ziel,
                                'wer', coalesce(c.name, '?'), 'seit', c.seit, 'grund', t);
    end if;
    return jsonb_build_object('frei', true, 'zweit', true, 'grund', 'weiterer Big Trade erlaubt — Abstand zum laufenden prüft der Klick');
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
  f record;
  ziel timestamptz;
  bis timestamptz;
  mx integer;
  n integer;
  ss jsonb;
  firma_da boolean;
  gesendet boolean := new.orbit_gesendet_at is not null or new.started_at is not null;
begin
  if new.status is distinct from 'planned' or not public.prophos_big_trade(new.route, new.hedge_eur, new.orbit_v3, public.prophos_wd_wie(new.winning_day, new.mt5_baseline)) then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_big_trade:' || new.user_id::text));
  select * into c from public.prophos_big_trade_laeuft(new.id, new.user_id);
  -- JE FIRMA NUR EINER (03.11.2026): über beide Fenster, unabhängig vom Schalter — Claim nicht schreiben, neue Prüfung in 1–1,5 min
  select * into f from public.prophos_big_trade_firma(new.id, new.user_id);
  -- S6-Gegenprüfung: Order schon gesendet (Nachklick/Neu-Claim) → die neuen Regeln greifen nicht, wie prophos_big_trade_halten und der Klick-Riegel
  firma_da := f.plan_id is not null and not gesendet;
  if c.plan_id is null then
    if not firma_da then
      return new;
    end if;
    perform public.prophos_big_trade_sperre(new.id, 'firma', 'Big Trade „' || coalesce(f.name, '?') || '" läuft schon bei ' || f.firma
                                            || ' — je Firma nur einer gleichzeitig', now() + interval '1 minute' + make_interval(secs => floor(random() * 30)));
    return null;
  end if;
  -- ZWEI ORBIT (30.10.2026): bis big_max_je_id gleichzeitig (Claim geht durch, den 2.500-$-Abstand prüft der Klick-Riegel). Voll →
  -- Marke start_sperre art 'zweit' + Start in 1–1,5 min statt 15 min (der Sofort-Start-Wächter im Tab fragt /admin/zweit-frei)
  mx := public.prophos_big_trade_max();
  if new.route = 'polar' then
    mx := 1;          -- Polar startet ohne Panel-Klick (kein /richtung/frei, keine 2.500-$-Prüfung) → nie als weiterer Big Trade
  end if;
  if mx > 1 then
    n := public.prophos_big_trade_anzahl(new.id, new.user_id);
    if n >= mx then
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
    if firma_da then
      perform public.prophos_big_trade_sperre(new.id, 'firma', 'Big Trade „' || coalesce(f.name, '?') || '" läuft schon bei ' || f.firma
                                              || ' — je Firma nur einer gleichzeitig', now() + interval '1 minute' + make_interval(secs => floor(random() * 30)));
      return null;
    end if;
    -- MARKTERÖFFNUNG (03.11.2026): in 09:28–09:35 New York kein weiterer Big Trade → Start nach Fensterende + 20–90 s
    bis := public.prophos_big_trade_markt_oeffnung(now());
    if bis is not null and not gesendet then
      perform public.prophos_big_trade_sperre(new.id, 'markt', 'Markteröffnung 09:28–09:35 New York (bis ' || to_char(bis at time zone 'Asia/Dubai', 'HH24:MI')
                                              || ' Dubai): kein weiterer Big Trade, solange „' || coalesce(c.name, '?') || '" läuft',
                                              bis + make_interval(secs => 20 + floor(random() * 70)));
      return null;
    end if;
    return new;
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

-- Prüfen (nur lesen):
--   select prophos_big_trade_markt_oeffnung('2026-11-03 14:30Z'), prophos_big_trade_markt_oeffnung('2026-11-03 14:40Z');   -- → 14:35Z | null
--   select * from prophos_big_trade_firma('<plan>', '<user>');
