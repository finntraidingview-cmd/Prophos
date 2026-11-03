-- MINI „TAGE SAMMELN" WIEDER FREI (E2, Finn 03.11.2026 ~18:45 über den Master: „Die Mini-Trades ‚Tage sammeln' haben perfekt funktioniert, gar nichts
-- ändern, eins zu eins lassen."). Seit sql/2026-11-03_cfd_challenge_nie_ohne_hedge.sql (E1, .2018) hielt der Claim-Riegel trade_plans_a1_echo_hedge auch die
-- Mini-Trades des Auto-Planers (Echo V2, 0,01 Lot bzw. 1 Lot FTMO, sofort zu) und gab sie am Fensterende auf. Diese Datei ist die E1-Funktion unverändert
-- PLUS genau eine Ausnahme für den Mini (Erkennung im Block „MINI" unten). Alles andere bleibt hart: keine CFD-Challenge auf Echo V2 oder Echo ohne Slave.
-- Gegenstück im PC-Tab: prophos.html echoV2Gesperrt (echoV2IstMini, dieselben Bedingungen). Wiederholbar. Rückbau: E1-Datei erneut einspielen.
-- Die Mini-Ausnahme steht vor der start_sperre-Prüfung: ein seit E1 gehaltener Mini läuft beim nächsten Claim durch (ein schon als verpasst gebuchter nicht).
-- NICHT vom Slave eingespielt.

create or replace function public.trade_plans_a1_echo_hedge()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  eh jsonb;
  ss jsonb;
  ziel timestamptz;
  erst boolean;
  txt text;
  erst_at timestamptz;
  grund text;
  kt text;
  gefunden boolean;
begin
  if new.status is distinct from 'planned' or coalesce(new.start_claim_art, 'start') <> 'start'
     or coalesce(new.route, '') not in ('mt5v2', 'mt5') then
    return new;
  end if;
  select lower(coalesce(a.account_type, '')), true into kt, gefunden from public.accounts a where a.id = new.master_account_id;
  if coalesce(gefunden, false) and kt <> '' and kt not in ('challenge', 'phase1', 'phase2') then   -- leere Kontoart = nicht lesbar (Prüfung 03.11.2026)
    return new;                                   -- Funded CFD u. a.: eigene Regeln (trade_plans_kontoart_weg)
  end if;
  if new.route = 'mt5' and new.slave_account_id is not null and coalesce(new.multiplier, 0) > 0 then
    return new;                                   -- Echo mit Fusion-Slave: gehedgt
  end if;
  -- MINI „TAGE SAMMELN" (E2, Finn 03.11.2026 ~18:45: „Die Mini-Trades ‚Tage sammeln' haben perfekt funktioniert, gar nichts ändern, eins zu eins
  -- lassen."): genau der Mini-Trade des Auto-Planers (ap_tage_mini) läuft wie vor E1 als Echo V2 ohne Hedge. Eng erkannt, nur an Feldern des Planers
  -- und am Geld: Auto-Plan, mt5_baseline.tage_mini mit sofort_zu, Notiz „Auto-Planer · Tage sammeln …", höchstens 1 Lot (0,01 bzw. kleinste ganze
  -- Stufe FTMO/The5%ers) und SL wie TP je über 0 und höchstens 50 $ (bisher 2–4 $, FTMO 1 Lot 27 $). Alles andere bleibt hart.
  if new.route = 'mt5v2' and coalesce(new.auto_plan, false)
     and jsonb_typeof(new.mt5_baseline->'tage_mini') = 'object' and new.mt5_baseline->'tage_mini'->>'sofort_zu' = 'true'
     and coalesce(new.notes, '') like 'Auto-Planer · Tage sammeln%'
     and coalesce(new.master_contracts, 0) > 0 and new.master_contracts <= 1
     and coalesce(new.master_sl, new.master_risk, 0) > 0 and coalesce(new.master_sl, new.master_risk) <= 50
     and coalesce(new.master_tp, 0) > 0 and new.master_tp <= 50 then
    return new;
  end if;
  eh := new.mt5_baseline->'echo_hedge';
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'echo_hedge' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
  end if;
  if ss->>'art' = 'echo_hedge' and ss->>'status' = 'aufgegeben' then
    return null;                                  -- aufgegeben bleibt aufgegeben (Stopp S17 02.11.2026)
  end if;
  erst := coalesce(ss->>'art', '') <> 'echo_hedge';
  erst_at := case when erst then now() else coalesce((ss->>'erst_at')::timestamptz, now()) end;
  txt := case
    when not coalesce(gefunden, false) or kt = '' then 'Kontoart des Masters nicht lesbar — CFD-Challenge vermutet, nie ohne Hedge'
    when new.route = 'mt5' then 'Echo ohne Fusion-Slave/Multiplikator — CFD-Challenges nur mit Hedge'
    when eh->>'status' = 'ohne' then 'Echo-Hedge nicht umgestellt: ' || left(coalesce(eh->>'grund', eh->>'code', '?'), 160)
    else 'Echo V2 (ohne Hedge) — CFD-Challenges laufen immer mit Fusion-Hedge, Umstellung steht noch aus' end;
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  grund := case when erst_at < now() - interval '8 hours' then '8h'
                when ziel >= public.prophos_echo_fenster_ende(erst_at) then 'fenster' end;
  if grund is not null then
    if erst or coalesce(ss->>'status', '') <> 'aufgegeben' then
      update public.trade_plans
         set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
               'art', 'echo_hedge', 'status', 'aufgegeben', 'ablauf', grund, 'text', txt, 'at', now(), 'erst_at', erst_at,
               'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
       where id = new.id;
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, old.start_um,
              '[Echo ohne Hedge aufgegeben] ' || txt || case when grund = 'fenster' then ' — CFD-Startfenster zu Ende' else ' — nach 8 h' end, 'start');
    end if;
    return null;
  end if;
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'echo_hedge', 'text', txt, 'at', now(), 'naechster', ziel, 'erst_at', erst_at,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Echo ohne Hedge gehalten] ' || txt || ' — Start rückt je 15–30 min weiter, bis der Hedge steht, höchstens 8 h', 'start');
  end if;
  return null;
end $$;
