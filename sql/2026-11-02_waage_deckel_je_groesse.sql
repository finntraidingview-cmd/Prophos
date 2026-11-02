-- WAAGE-DECKEL JE KONTOGRÖSSE (Finn 02.11.2026 „ok ja bau“, über den Eingang): Ein 50k-Long gleicht keinen 150k-Short mehr aus. Ein automatischer Futures-Start
-- startet nur, wenn danach in SEINER Kontogröße |Long − Short| ≤ waage_max_abstand (2). Jede Größe ist eine eigene Waage (150k, 100k, 50k, 300k …). Ohne
-- bestimmbare Größe: eigene Waage „unbekannt“, nie frei (fail-closed). Zählmenge, Sperre, Verschieben 10–20 min, Aufgeben am Fensterende, Verbrauchs-Claims
-- und Hand-Werte bleiben wie in sql/2026-10-23_waage_deckel.sql. Prüffälle Finn: 150k 5 : 3 → Long gesperrt, Short frei; 100k 2 : 0 → Long gesperrt;
-- 50k 3 : 0 → Long gesperrt.
-- Größe (prophos_waage_groesse): „150k“ aus dem Kontonamen zuerst (auch Topstep „150KTC-…“), sonst accounts.account_size, sonst „unbekannt“ — dieselbe Regel
-- wie app.py ap_waage_groesse. starting_balance bewusst nicht (08.10.2026: ein 100k-Konto trug 150000).
-- SPUR (Befund S18 02.11.2026: 00001e43, 7883ce9e, f9e0c9ee rutschten 15:04–15:44 Dubai durch, obwohl die Nachrechnung 5 : 8, 5 : 9 und 6 : 10 ergibt; die
-- Ursache ist ohne Historie nicht beweisbar): Bei jedem Durchlassen und jeder Sperre steht mt5_baseline.waage_lage {groesse, n_long, n_short, ids, at}.
-- ROBUSTE ZÄHLUNG (Eingang 02.11.2026): laufend = gestartet und nicht beendet (started_at gesetzt, ended_at leer), egal welcher Status — dazu wie bisher status
-- open und frische Claims (≤ 15 min, noch nicht gestartet). Nur Starts der letzten 3 Tage: zwölf alte Pläne vom 22.09. tragen completed ohne ended_at (die Spalte
-- kam erst am 22.09.) und zählten sonst für immer. Die Hedge-Ausnahme gilt nur für echte Hedge-Pläne (hedge_eur > 0 und Fusion-Hedge offen/öffnet/schließt); ein
-- Plan mit leerem Hedge-Feld zählt immer.
-- Idempotent, nur Funktionen, kein Datenumbau.

create or replace function public.prophos_waage_groesse(p_name text, p_size numeric)
returns text language sql immutable as $$
  select coalesce((regexp_match(coalesce(p_name, ''), '(^|[^0-9])(\d{2,3})\s*k(\M|tc)', 'i'))[2] || 'k',
                  case when coalesce(p_size, 0) > 0 then round(p_size / 1000)::text || 'k' end,
                  'unbekannt')
$$;

create or replace function public.prophos_waage_deckel_lage(p_plan uuid, p_richtung text default null)
returns jsonb language plpgsql stable security definer set search_path to 'public' as $function$
declare
  pl record;
  r text;
  pa jsonb := public.prophos_waage_deckel_param();
  max_abstand numeric := (pa->>'max_abstand')::numeric;
  ohne text[] := array(select jsonb_array_elements_text(pa->'ohne'));
  firm text;
  gr text;
  nl int := 0;
  ns int := 0;
  seite int;
  andere int;
  ids jsonb;
begin
  select p.id, p.user_id, p.richtung, p.route, p.master_firm, p.hedge_eur, p.slave_account_id, a.account_type, a.firm, a.name acc_name, a.account_size
    into pl
    from public.trade_plans p left join public.accounts a on a.id = p.master_account_id
   where p.id = p_plan;
  if not found then
    return jsonb_build_object('zaehlt', false, 'sperrt', false, 'grund', 'Plan unbekannt');
  end if;
  r := coalesce(p_richtung, pl.richtung);
  firm := coalesce(pl.firm, pl.master_firm);
  if not coalesce((pa->>'an')::boolean, true)
     or r not in ('buy', 'sell')
     or coalesce(pl.account_type, '') not in ('challenge', 'phase1', 'phase2')
     or coalesce(pl.hedge_eur, 0) > 0 or pl.slave_account_id is not null or lower(coalesce(pl.route, '')) = 'mt5'
     or not public.prophos_waage_futures(pl.route, firm)
     or exists (select 1 from unnest(ohne) o
                 where strpos(lower(coalesce(public.prophos_firma_key(firm), '') || '|' || coalesce(firm, '')), o) > 0)
     or public.prophos_waage_ausgeblendet(pl.user_id) then
    return jsonb_build_object('zaehlt', false, 'sperrt', false, 'max_abstand', max_abstand);
  end if;
  gr := public.prophos_waage_groesse(pl.acc_name, pl.account_size);
  select count(*) filter (where p.richtung = 'buy'), count(*) filter (where p.richtung = 'sell'),
         coalesce(jsonb_agg(left(p.id::text, 8) || ':' || p.richtung || ':' || p.status), '[]'::jsonb)
    into nl, ns, ids
    from public.trade_plans p left join public.accounts a on a.id = p.master_account_id
   where p.id <> pl.id
     and p.richtung in ('buy', 'sell')
     and coalesce(a.account_type, '') in ('challenge', 'phase1', 'phase2')
     and public.prophos_waage_groesse(a.name, a.account_size) = gr
     and p.slave_account_id is null
     and lower(coalesce(p.route, '')) <> 'mt5'
     and not (coalesce(p.hedge_eur, 0) > 0 and coalesce(p.mt5_baseline->'hedge'->>'status', '') in ('offen', 'oeffnet', 'schliesst'))
     and public.prophos_waage_futures(p.route, coalesce(a.firm, p.master_firm))
     and not exists (select 1 from unnest(ohne) o
                      where strpos(lower(coalesce(public.prophos_firma_key(coalesce(a.firm, p.master_firm)), '') || '|'
                                         || coalesce(a.firm, p.master_firm, '')), o) > 0)
     and not public.prophos_waage_ausgeblendet(p.user_id)
     and (p.status = 'open'
          or (p.started_at is not null and p.ended_at is null and p.started_at > now() - interval '3 days')
          or (p.status = 'planned' and p.started_at is null and coalesce(p.hedge_eur, 0) <= 0
              and p.start_um_gestartet_at > now() - interval '15 minutes'));
  if r = 'buy' then nl := nl + 1; seite := nl; andere := ns; else ns := ns + 1; seite := ns; andere := nl; end if;
  return jsonb_build_object('zaehlt', true, 'groesse', gr,
    'sperrt', gr = 'unbekannt' or seite - andere > max_abstand, 'n_long', nl, 'n_short', ns, 'max_abstand', max_abstand, 'ids', ids,
    'grund', case when gr = 'unbekannt'
                  then 'Futures: Kontogröße unbekannt (Name ohne „…k“, account_size leer) — eigene Waage, startet nie automatisch'
                  else 'Futures ' || gr || ' würde ' || nl || ' Long : ' || ns || ' Short (Abstand höchstens ' || trim(to_char(max_abstand, 'FM990.##'), '.') || ')' end);
end $function$;

-- Trigger: unverändert bis auf die Spur waage_lage im Durchlass- und in beiden Sperr-Zweigen
create or replace function public.trade_plans_waage_deckel()
returns trigger language plpgsql security definer set search_path to 'public' as $function$
declare
  pa jsonb;
  ohne text[];
  typ text;
  firm text;
  lage jsonb;
  wd jsonb := coalesce(new.mt5_baseline, '{}'::jsonb)->'waage_deckel';
  erst timestamptz;
  ende timestamptz;
  n int;
  rest numeric;
  ziel timestamptz;
  txt text;
  spur jsonb;
begin
  if new.status is distinct from 'planned' or new.auto_plan is not true or new.hand_werte_at is not null
     or coalesce(new.richtung, '') not in ('buy', 'sell') then
    return new;
  end if;
  if coalesce(new.start_claim_art, '') = 'verbrauch' then
    return new;
  end if;
  if new.start_claim_art is null and old.start_um is not null and old.start_um < now() - interval '25 minutes' then
    return new;
  end if;
  if lower(coalesce(new.route, '')) in ('mt5', 'mt5v2') or coalesce(new.hedge_eur, 0) > 0 or new.slave_account_id is not null then
    return new;
  end if;
  pa := public.prophos_waage_deckel_param();
  if not coalesce((pa->>'an')::boolean, true) then
    return new;
  end if;
  select a.account_type, coalesce(a.firm, new.master_firm) into typ, firm from public.accounts a where a.id = new.master_account_id;
  firm := coalesce(firm, new.master_firm);
  ohne := array(select jsonb_array_elements_text(pa->'ohne'));
  if coalesce(typ, '') not in ('challenge', 'phase1', 'phase2')
     or not public.prophos_waage_futures(new.route, firm)
     or exists (select 1 from unnest(ohne) o where strpos(lower(coalesce(public.prophos_firma_key(firm), '') || '|' || coalesce(firm, '')), o) > 0)
     or public.prophos_waage_ausgeblendet(new.user_id) then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_waage_deckel'));
  lage := public.prophos_waage_deckel_lage(new.id, new.richtung);
  spur := jsonb_build_object('groesse', lage->'groesse', 'n_long', lage->'n_long', 'n_short', lage->'n_short', 'ids', lage->'ids', 'at', now(),
                             'richtung', new.richtung, 'sperrt', coalesce((lage->>'sperrt')::boolean, false));
  if not coalesce((lage->>'sperrt')::boolean, false) then
    -- SPUR (02.11.2026): was der Riegel beim Durchlassen gezählt hat
    new.mt5_baseline := (coalesce(new.mt5_baseline, '{}'::jsonb) - 'waage_deckel') || jsonb_build_object('waage_lage', spur);
    return new;
  end if;
  if coalesce(wd->>'status', '') = 'wartet' and (wd->>'erst') is not null and (wd->>'erst')::timestamptz > now() - interval '24 hours'
     and (wd->>'naechster') is not null and old.start_um is not null and (wd->>'naechster')::timestamptz = old.start_um then
    erst := (wd->>'erst')::timestamptz;
    n := coalesce((wd->>'versuche')::int, 0) + 1;
  else
    erst := coalesce(old.start_um, now());
    n := 1;
  end if;
  ende := public.prophos_waage_fenster_ende(erst);
  rest := extract(epoch from (ende - now())) / 60.0;
  txt := coalesce(lage->>'grund', 'Futures-Abstand würde über den Deckel') || ' — der '
         || case new.richtung when 'buy' then 'Long' else 'Short' end || ' startet nicht';
  if rest < 10 then
    update public.trade_plans set
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb)
             || jsonb_build_object('waage_deckel', jsonb_build_object('status', 'aufgegeben', 'erst', erst, 'versuche', n, 'at', now(), 'text', txt))
             || jsonb_build_object('waage_lage', spur)
             || jsonb_build_object('start_sperre', jsonb_build_object('art', 'waage_deckel', 'status', 'aufgegeben', 'text', txt, 'at', now(), 'versuche', n))
             || jsonb_build_object('richtung_konflikt', jsonb_build_object('quelle', 'start', 'status', 'aufgegeben', 'um', now(), 'erst_start', erst,
                  'versuche', n, 'gegen', null, 'saldo', true, 'text', '[Waage-Deckel] ' || txt, 'start', old.start_um, 'pc', null))
     where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, old.start_um,
            '[Waage-Deckel] ' || txt || ' — Startfenster endet ' || to_char(ende at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai, aufgegeben (Versuch ' || n
            || '): Plan bleibt Geplant, Start von Hand oder neue Uhrzeit', 'start');
    return null;
  end if;
  ziel := now() + make_interval(secs => round((10 + random() * greatest(0, least(20, rest) - 10)) * 60)::int);
  update public.trade_plans set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb)
           || jsonb_build_object('waage_deckel', jsonb_build_object('status', 'wartet', 'erst', erst, 'versuche', n, 'at', now(), 'naechster', ziel,
                'ende', ende, 'text', txt))
           || jsonb_build_object('waage_lage', spur)
           || jsonb_build_object('start_sperre', jsonb_build_object('art', 'waage_deckel', 'status', 'wartet', 'text', txt, 'at', now(), 'naechster', ziel,
                'versuche', n))
   where id = new.id;
  insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
  values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
          '[Waage-Deckel] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai (Versuch ' || n
          || ', Fenster bis ' || to_char(ende at time zone 'Asia/Dubai', 'HH24:MI') || ')', 'start');
  return null;
end $function$;

-- Prüfung nach dem Einspielen (nur lesen): je laufendem Futures-Plan Größe und Lage
-- select left(p.id::text,8), p.richtung, (public.prophos_waage_deckel_lage(p.id, p.richtung))->>'groesse',
--        (public.prophos_waage_deckel_lage(p.id, p.richtung))->>'grund'
--   from public.trade_plans p where p.status = 'open' and p.route in ('tvv2','tsv2');
