-- APEX-CHALLENGE-WD-HEDGE (30.10.2026, Finn 29.10. ~16:30 Dubai: „Für Apex die Trades mit der normalen Winning-Days-Logik starten, eins zu
-- eins wie Winning Days … mit der gleichen Priorität plus mit dem gleichen Gegenhedge-Verfahren … bei Apex IMMER bei den Challenges mit
-- Gegenhedge"). Railway (app.py ah_tick) stellt bestätigte HT-Apex-Challenge-Auto-Pläne (route tvv2) ab 20 min vor dem Start auf den
-- Winning-Day-Weg: hedge_eur = Kontowert, master_risk = Polster, slave_risk/multiplier nach q = Kaufpreis ÷ Max DD ÷ 0,89, winning_day = false,
-- Marke mt5_baseline.apex_hedge. Er läuft wie ein WD (Start, Priorität, Verspätung, Fusion-Hedge), zählt aber nicht als WD; der Fusion-Hedge
-- schließt am Challenge-Boden (apex_hedge.liq_balance), nicht bei Größe + 100.
--
-- 1. Schalter auto_plan_regeln.regeln.apex_hedge = {an, netto_faktor, min_lot, vorlauf_min, nachlauf_min}. Standard AUS; ein schon gesetzter
--    Wert bleibt (Merge). Die 60-Lot-Grenze je Fusion-Login teilt er mit dem Echo-Hedge (regeln.echo_hedge.max_lots). Umschalten: Admin →
--    Trade-Planer, Schalter „Apex-Hedge" neben „Echo-Hedge", oder per SQL:
--      update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{apex_hedge,an}', 'true') where id = 1;   -- an
--      update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{apex_hedge,an}', 'false') where id = 1;  -- aus (ah_tick stellt
--      umgestellte, noch nicht gestartete Pläne zurück auf Orbit V2 ohne Hedge; laufende bleiben, wie sie sind)
-- 2. Riegel trade_plans_kontoart_weg: eine Apex-Challenge mit Hedge auf tvv2 darf es, wenn sie ein Auto-Plan mit Marke apex_hedge 'mit' ist
--    und der Schalter an ist (prophos_apex_hedge_an). Sonst Wort für Wort die Fassung aus S4s sql/2026-10-29_tradeify_final_hedge.sql
--    (Stand 36be4e0c: Live-Fassung mit HT ECHO-HEDGE + FINALER TRADEIFY + dieser Block) — GEMEINSAME FASSUNG (S2 30.10.2026: wer
--    die Funktion als Zweites neu anlegt, darf den Block des anderen nicht löschen).
-- REIHENFOLGE EGAL (S4-Absprache 30.10.2026): beide Dateien tragen DIESELBE Fassung mit allen Blöcken (Funktionstext Zeichen für Zeichen wie
-- S4s Datei, per diff geprüft) und legen die Schalter-Funktion des anderen an, falls sie fehlt (Standard aus, derselbe Wortlaut) — der Trigger
-- bricht so nie an einer fehlenden Funktion ab. Voraussetzung nur sql/2026-10-29_ht_echo_hedge.sql (live). Wer trade_plans_kontoart_weg
-- danach neu anlegt, nimmt alle Blöcke mit.
-- Wiederholbar. Rückbau: Schalter aus genügt; die Funktion ohne den Block „APEX-CHALLENGE-WD-HEDGE" neu anlegen
-- (= sql/2026-10-29_tradeify_final_hedge.sql, Abschnitt 3).

do $pruef$
begin
  perform 'public.prophos_ht_echo_hedge_an()'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-29_ht_echo_hedge.sql einspielen';
end $pruef$;

-- Schalter-Funktion des finalen Tradeify (S4), falls sql/2026-10-29_tradeify_final_hedge.sql noch nicht eingespielt ist — derselbe Wortlaut,
-- Standard aus (nur ein echtes JSON-true zählt); S4s Datei legt sie später wortgleich neu an
do $schalter$
begin
  if to_regprocedure('public.prophos_tradeify_final_hedge_an()') is null then
    execute $f$create function public.prophos_tradeify_final_hedge_an()
      returns boolean language sql stable security definer set search_path = public as $b$
        select coalesce((select (r.regeln->'tradeify_final_hedge'->'an') = 'true'::jsonb from public.auto_plan_regeln r where r.id = 1), false)
      $b$$f$;
    execute 'grant execute on function public.prophos_tradeify_final_hedge_an() to authenticated, service_role';
  end if;
end $schalter$;

update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{apex_hedge}',
         '{"an": false, "netto_faktor": 0.89, "min_lot": 0.01, "vorlauf_min": 20, "nachlauf_min": 30}'::jsonb
         || coalesce(case when jsonb_typeof(regeln->'apex_hedge') = 'object' then regeln->'apex_hedge' end, '{}'::jsonb)),
       updated_at = now()
 where id = 1;

create or replace function public.prophos_apex_hedge_an()
returns boolean language sql stable security definer set search_path to 'public' as $$
  -- nur ein echtes JSON-true zählt (kein Cast: ein Tippfehler im Schalter darf den Riegel nie mit einem Fehler abbrechen)
  select coalesce((select (r.regeln->'apex_hedge'->'an') = 'true'::jsonb from public.auto_plan_regeln r where r.id = 1), false)
$$;

create or replace function public.trade_plans_kontoart_weg()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare
  typ text;
  kname text;
  mit boolean;
  schalter boolean := false;
begin
  if new.master_account_id is null or coalesce(new.status, 'planned') <> 'planned' then
    return new;
  end if;
  select lower(coalesce(a.account_type, '')), a.name into typ, kname from public.accounts a where a.id = new.master_account_id;
  if typ is null then
    return new;
  end if;
  mit := public.prophos_hedge_weg(new.route, new.hedge_eur, new.orbit_v3, new.winning_day);
  if mit is null then
    return new;
  end if;
  if typ in ('funded', 'funded_cfd', 'winning_days') and not mit then
    raise exception 'Funded-Konto „%" nur mit Hedge: Weg % ohne Hedge ist für Challenges — im Trade-Popup Echo, Orbit V3, Winning Day oder Topstep (mit Hedge) wählen.',
      coalesce(kname, '?'), coalesce(new.route, '?')
      using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
  end if;
  -- Rest von Hand mit Hedge (26.10.2026): Orbit-Plan aus dem Radar-Knopf — nur tvv2 + orbit_v3, sonst gilt die Kennung nicht
  if coalesce(new.rest_hedge, false) and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false) then
    return new;
  end if;
  -- APEX-CHALLENGE-WD-HEDGE (30.10.2026): Apex-Challenge-Auto-Plan auf dem Winning-Day-Weg (tvv2 + hedge_eur, Marke apex_hedge 'mit'),
  -- solange regeln.apex_hedge.an true ist — nur die Umstellung von Railway (ah_tick) trägt die Marke
  if typ = 'challenge' and coalesce(new.route, '') = 'tvv2' and coalesce(new.auto_plan, false) and coalesce(new.hedge_eur, 0) > 0
     and not coalesce(new.orbit_v3, false) and public.prophos_firma_key(new.master_firm) = 'Apex Trader'
     and coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = 'mit' and public.prophos_apex_hedge_an() then
    return new;
  end if;
  -- HT ECHO-HEDGE B2 (29.10.2026): Auto-Plan auf dem klassischen Echo mit Slave, solange der zentrale Schalter an ist
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'mt5' and coalesce(new.auto_plan, false)
     and new.slave_account_id is not null and public.prophos_ht_echo_hedge_an() then
    return new;
  end if;
  -- FINALER TRADEIFY MIT GEGENHEDGE (29.10.2026): finaler Tradeify-Futures-Auto-Plan als Orbit V3, umgestellt von tfh_tick, Schalter an
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false)
     and coalesce(new.auto_plan, false) and coalesce(new.mt5_baseline->'tradeify_hedge'->>'status', '') = 'mit'
     and public.prophos_firma_key(new.master_firm) = public.prophos_firma_key('Tradeify')
     and public.prophos_tradeify_final_hedge_an() then
    return new;
  end if;
  if typ in ('challenge', 'phase1', 'phase2') and mit and coalesce(new.route, '') in ('mt5', 'mt5v2', 'tvv2', 'tsv2') then
    select coalesce((s.value->>'an')::boolean, false) into schalter
      from public.user_settings s where s.user_id = new.user_id and s.key = 'tp_challenges_mit_hedge';
    if not coalesce(schalter, false) then
      raise exception 'Challenge-/Phase-Konto „%" nur ohne Hedge: Echo V2, Orbit V2 oder Topstep V2 wählen — oder im Trade-Popup oben „Challenges mit Hedge" einschalten.',
        coalesce(kname, '?')
        using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
    end if;
  end if;
  return new;
end $function$;

-- ── Big Trade: Apex mit Hedge läuft wie ein Winning Day ─────────────────────────────────────────────────────────────────────────────
-- prophos_big_trade(route, hedge_eur, orbit_v3, winning_day) sieht mt5_baseline nicht. Ein umgestellter Apex-Plan (hedge_eur > 0,
-- winning_day false) wäre sonst ein Big Trade („ein Big Trade je ID und Fenster", 15-min-Verschiebung). Die drei Aufrufer reichen
-- deshalb prophos_wd_wie(winning_day, mt5_baseline) statt winning_day weiter. Rümpfe sonst 1:1 wie live (gelesen 29.10.2026).
-- Rückbau: die drei Funktionen mit p.winning_day / pl.winning_day / new.winning_day neu anlegen.
create or replace function public.prophos_wd_wie(p_winning_day boolean, p_baseline jsonb)
returns boolean language sql immutable as $$
  select coalesce(p_winning_day, false) or coalesce(p_baseline->'apex_hedge'->>'status', '') = 'mit'
$$;

-- Fenster-Klausel (27.10.2026) seit sql/2026-10-30_big_trade_fenster_zurueck.sql wieder drin — DIESELBE Fassung wie dort (Zeichen für Zeichen).
create or replace function public.prophos_big_trade_fenster(p_route text) returns text
language sql immutable as $$
  select case when coalesce(p_route, '') = 'tsv2' then 'tsx' else 'tv' end
$$;

CREATE OR REPLACE FUNCTION public.prophos_big_trade_laeuft(p_id uuid, p_user uuid)
 RETURNS TABLE(plan_id uuid, name text, seit timestamp with time zone)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select p.id, p.master_name, coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now())
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and public.prophos_big_trade(p.route, p.hedge_eur, p.orbit_v3, public.prophos_wd_wie(p.winning_day, p.mt5_baseline))
     -- 27.10.2026: nur dasselbe Fenster (TopstepX bzw. TradingView) — ohne eigenen Plan (unbekannte ID) wie bisher die ganze ID
     and (not exists (select 1 from public.trade_plans s where s.id = p_id)
          or public.prophos_big_trade_fenster(p.route) = (select public.prophos_big_trade_fenster(s.route) from public.trade_plans s where s.id = p_id))
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
   order by 3 desc
   limit 1
$function$;
revoke all on function public.prophos_big_trade_laeuft(uuid, uuid) from public;

-- Halten + Trigger mit ZWEI ORBIT (big_max_je_id) — DIESELBE Fassung wie sql/2026-10-30_zwei_big_trades.sql (Zeichen für Zeichen).
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
  if pl.route = 'polar' then
    mx := 1;          -- Polar startet ohne Panel-Klick (kein /richtung/frei, keine 2.500-$-Prüfung) → nie als weiterer Big Trade
  end if;
  if mx > 1 then
    n := public.prophos_big_trade_anzahl(pl.id, pl.user_id);
    if n < mx then
      return jsonb_build_object('frei', true, 'zweit', true, 'grund', 'weiterer Big Trade erlaubt — Abstand zum laufenden prüft der Klick');
    end if;
    ziel := greatest(now() + interval '1 minute' + make_interval(secs => floor(random() * 30)), coalesce(pl.start_um, now()));   -- nie vorziehen
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
  if new.route = 'polar' then
    mx := 1;          -- Polar startet ohne Panel-Klick (kein /richtung/frei, keine 2.500-$-Prüfung) → nie als weiterer Big Trade
  end if;
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
