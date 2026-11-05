-- MODELLNAMEN IN DB-TEXTEN (SA2 b, Master 05.11.2026, MORGEN-Liste; Variante A wie modellName()/MODELL_NAME) — Slave 3
-- Zwei Trigger-Funktionen nannten noch alte Modellnamen. Nur die Texte sind geändert, alles andere ist Wort für Wort die Live-Definition
-- (pg_get_functiondef am 05.11.2026; md5 der Ausgangsfassung geprüft: trade_plans_a1_apex_hedge cab664fb29d5d8e16a1a1d96926d09d2,
-- trade_plans_kontoart_weg 6eed66f41750463e191efe0ddc337d99). Keine Logik, keine Schlüssel (art 'apex_hedge', hint, errcode bleiben).
-- Gelesen werden die Texte nur als Anzeige (Start-Sperre/Alarm-Text, Umplanungs-Grund, Fehlermeldung); „von Hand geändert“ bleibt drin
-- (prophos.html prüft /von Hand geändert/ am Sperr-Text). Idempotent (create or replace). NICHT von Slave 3 eingespielt.
--
-- trade_plans_a1_apex_hedge (Orbit Prio 2 ohne Hedge gehalten):
--   'Apex wartet auf Hedge — Werte von Hand geändert, …'  →  'Orbit Prio 2 wartet auf Hedge — Werte von Hand geändert, …'
--   'Apex-Challenge wartet auf Gegenhedge'                 →  'Orbit Prio 2 wartet auf Gegenhedge'   (= Rückfall-Text in app.py alarm_ereignisse)
--   '[Apex ohne Hedge gehalten] '                          →  '[Orbit Prio 2 ohne Hedge gehalten] '
-- trade_plans_kontoart_weg (Funded nur mit Hedge):
--   '… im Trade-Popup Echo, Orbit V3, Winning Day oder Topstep (mit Hedge) wählen.'  →  '… im Trade-Popup Echo, Orbit, Nova oder Winning Day wählen.'
--   (der zweite Fehlertext nennt schon Echo V2, Orbit V2, Topstep V2 — unverändert)
-- Nicht angefasst: der Puls-Heim-Grund „Apex-Challenge …“ in app.py ist ein Schlüssel, den der Tab liest (Rückbau 520e60eb).

begin;

CREATE OR REPLACE FUNCTION public.trade_plans_a1_apex_hedge()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  ss jsonb;
  ziel timestamptz;
  erst boolean;
  txt text;
begin
  if new.status is distinct from 'planned' or not coalesce(new.auto_plan, false)
     or coalesce(new.mt5_baseline->>'hedge_art', '') <> 'apex' then
    return new;
  end if;
  if coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = 'mit' and coalesce(new.hedge_eur, 0) > 0 then
    return new;
  end if;
  if not public.prophos_apex_hedge_an() then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'apex_hedge' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;
  end if;
  erst := coalesce(ss->>'art', '') <> 'apex_hedge';
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  if new.hand_werte_at is not null then
    txt := 'Orbit Prio 2 wartet auf Hedge — Werte von Hand geändert, Takt stellt nicht mehr um: ablehnen und neu planen';
  else
    txt := 'Orbit Prio 2 wartet auf Gegenhedge'
           || coalesce(' (' || nullif(left(new.mt5_baseline->'apex_hedge'->>'grund', 160), '') || ')', ' (noch nicht umgestellt)');
  end if;
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'apex_hedge', 'text', txt, 'at', now(), 'naechster', ziel,
           'erst_at', case when erst then now() else coalesce(ss->'erst_at', to_jsonb(now())) end,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Orbit Prio 2 ohne Hedge gehalten] ' || txt || ' — startet nie ohne Hedge; Start rückt je 15–30 min weiter, bis der Hedge rechenbar ist',
            'start');
  end if;
  return null;
end $function$;

CREATE OR REPLACE FUNCTION public.trade_plans_kontoart_weg()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
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
    raise exception 'Funded-Konto „%" nur mit Hedge: Weg % ohne Hedge ist für Challenges — im Trade-Popup Echo, Orbit, Nova oder Winning Day wählen.',
      coalesce(kname, '?'), coalesce(new.route, '?')
      using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
  end if;
  if coalesce(new.rest_hedge, false) and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false) then
    return new;
  end if;
  -- ORBIT PRIO 2 (05.11.2026): Apex wie bisher ODER Marke hedge_art 'apex' (Railway ah_tick, nur Firmen mit Modell orbit_prio2)
  if typ = 'challenge' and coalesce(new.route, '') = 'tvv2' and coalesce(new.auto_plan, false) and coalesce(new.hedge_eur, 0) > 0
     and not coalesce(new.orbit_v3, false)
     and (public.prophos_firma_key(new.master_firm) = 'Apex Trader' or coalesce(new.mt5_baseline->>'hedge_art', '') = 'apex')
     and coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = 'mit' and public.prophos_apex_hedge_an() then
    return new;
  end if;
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'mt5' and coalesce(new.auto_plan, false)
     and new.slave_account_id is not null and public.prophos_ht_echo_hedge_an() then
    return new;
  end if;
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

commit;

-- Kontrolle (nach dem Einspielen):
-- select proname, md5(pg_get_functiondef(oid)) from pg_proc where proname in ('trade_plans_a1_apex_hedge', 'trade_plans_kontoart_weg');
--   erwartet: trade_plans_a1_apex_hedge 32ee59e50b376eef0b63b22a4e87a2db · trade_plans_kontoart_weg 0d0bed4c0b72b91c452db02b2ee61ca2
