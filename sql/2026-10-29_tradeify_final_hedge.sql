-- FINALER TRADEIFY MIT GEGENHEDGE (Finn 29.10.2026 ~16:30 Dubai, über Master): der finale Tradeify-Futures-Trade startet als Orbit V3
-- (tvv2 + orbit_v3 + Fusion-Gegenhedge) — Railway tfh_tick stellt ihn kurz vor dem Start um. Alle anderen Tradeify-Trades bleiben Orbit V2
-- ohne Hedge. Voraussetzung: sql/2026-10-29_tradeify_final_halten.sql (Halte-Riegel) ist eingespielt.
--
-- (1) Schalter auto_plan_regeln.regeln.tradeify_final_hedge {an: false, netto_faktor 0.89, min_lot, max_lots 60, vorlauf/nachlauf} —
--     Standard AUS: solange aus, gilt nur der Halte-Riegel (finale Trades starten nicht). Einschalten:
--       update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{tradeify_final_hedge,an}', 'true'::jsonb) where id = 1;
-- (2) Halte-Riegel verfeinert: ein finaler Tradeify-Plan startet nur noch als umgestellter Orbit V3 mit Hedge (orbit_v3 + hedge_eur > 0);
--     gehalten wird, solange tradeify_final_halten ODER tradeify_final_hedge.an gilt — bei Hedge-Weg an also nie ohne Hedge, auch wenn die
--     Umstellung scheitert (Fusion-Lesung, Marge, 60-Lot-Grenze …).
-- (3) Riegel trade_plans_kontoart_weg: Ausnahme für genau diesen Weg — Auto-Plan, Tradeify (Futures-Schlüssel), Challenge/Phase, tvv2 +
--     orbit_v3, mt5_baseline.tradeify_hedge.status 'mit', Schalter an. Sonst Wort für Wort die Live-Fassung vom 29.10.2026 ~17:00
--     (pg_get_functiondef: Funded nur mit Hedge, Rest von Hand, HT ECHO-HEDGE aus sql/2026-10-29_ht_echo_hedge.sql, Schalter je ID).
-- Mehrfach-Claim < 1 min nach einem Halt schiebt nicht noch einen Tag weiter (S2-Hinweis zu a6db74b0).
-- Rückbau: Schalter aus genügt (tfh_tick stellt nicht gestartete Pläne zurück, der Halte-Riegel hält). Komplett: Funktion
-- trade_plans_kontoart_weg ohne den Block „FINALER TRADEIFY MIT GEGENHEDGE" neu anlegen, prophos_tradeify_final_hedge_an droppen und
-- trade_plans_a_final_halten aus sql/2026-10-29_tradeify_final_halten.sql neu einspielen.

do $pruef$
begin
  perform 'public.trade_plans_a_final_halten()'::regprocedure;
  perform 'public.prophos_hedge_weg(text, numeric, boolean, boolean)'::regprocedure;
  perform 'public.prophos_ht_echo_hedge_an()'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-29_tradeify_final_halten.sql und sql/2026-10-29_ht_echo_hedge.sql einspielen';
end $pruef$;

-- ── 1. Schalter (Standard AUS) ─────────────────────────────────────────────────────────────────────────────────────────
update public.auto_plan_regeln
   set regeln = jsonb_set(coalesce(regeln, '{}'::jsonb), '{tradeify_final_hedge}',
                          coalesce(regeln->'tradeify_final_hedge', '{}'::jsonb)
                          || jsonb_build_object('an', coalesce((regeln->'tradeify_final_hedge'->>'an')::boolean, false),
                                                'netto_faktor', 0.89, 'min_lot', 0.01, 'max_lots', 60, 'vorlauf_min', 20, 'nachlauf_min', 30))
 where id = 1;

create or replace function public.prophos_tradeify_final_hedge_an()
returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select (regeln->'tradeify_final_hedge'->>'an')::boolean from public.auto_plan_regeln where id = 1), false)
$$;
grant execute on function public.prophos_tradeify_final_hedge_an() to authenticated, service_role;

-- ── 2. Halte-Riegel verfeinert ─────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.trade_plans_a_final_halten()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  ziel timestamptz;
  txt text;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if public.prophos_firma_key(new.master_firm) is distinct from public.prophos_firma_key('Tradeify') then
    return new;   -- nur Tradeify Futures (Tradeify CFD hat einen eigenen Schlüssel)
  end if;
  -- umgestellt auf Orbit V3 mit Gegenhedge (tfh_tick) → darf starten
  if coalesce(new.orbit_v3, false) and coalesce(new.hedge_eur, 0) > 0 and public.prophos_tradeify_final_hedge_an() then
    return new;
  end if;
  if not (public.prophos_tradeify_final_halten_an() or public.prophos_tradeify_final_hedge_an()) or not public.prophos_plan_final(new.id) then
    return new;
  end if;
  -- Mehrfach-Claim (S2 29.10.2026): eben erst gehalten → nicht noch einen Tag weiter schieben
  if new.mt5_baseline->'start_sperre'->>'art' = 'final_halten'
     and (new.mt5_baseline->'start_sperre'->>'at')::timestamptz > now() - interval '1 minute' then
    return null;
  end if;
  ziel := greatest(coalesce(old.start_um, now()), now() - interval '12 hours') + interval '1 day'
          + make_interval(secs => floor(random() * 1200));
  if ziel < now() + interval '12 hours' then
    ziel := now() + interval '1 day' + make_interval(secs => floor(random() * 1200));
  end if;
  txt := 'finaler Tradeify-Trade wartet auf Gegenhedge (TP ' || coalesce(round(new.master_tp)::text, '?') || ' $'
         || coalesce(', ' || nullif(new.mt5_baseline->'tradeify_hedge'->>'grund', ''), '') || ')';
  update public.trade_plans
     set start_um = ziel,
         hand_werte_at = coalesce(hand_werte_at, now()),
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'final_halten', 'text', txt, 'at', now(), 'naechster', ziel,
           'versuche', case when mt5_baseline->'start_sperre'->>'art' = 'final_halten'
                            then coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1 else 1 end))
   where id = new.id;
  insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
  values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
          '[finaler Tradeify gehalten] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'DD.MM. HH24:MI'), 'start');
  return null;
end $$;

-- ── 3. Riegel trade_plans_kontoart_weg mit Ausnahme ───────────────────────────────────────────────────────────────────
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
  -- HT ECHO-HEDGE B2 (29.10.2026): Auto-Plan auf dem klassischen Echo mit Slave, solange der zentrale Schalter an ist
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'mt5' and coalesce(new.auto_plan, false)
     and new.slave_account_id is not null and public.prophos_ht_echo_hedge_an() then
    return new;
  end if;
  -- FINALER TRADEIFY MIT GEGENHEDGE (29.10.2026): finaler Tradeify-Futures-Auto-Plan als Orbit V3, umgestellt von tfh_tick, Schalter an
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false)
     and coalesce(new.auto_plan, false) and new.mt5_baseline->'tradeify_hedge'->>'status' = 'mit'
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
