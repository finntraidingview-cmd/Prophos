-- CFD-PLANER NUR ECHO (E3, Finn 03.11.2026 ~23:10 Dubai, wörtlich über den Master: „Es ist kein einziger Trade des CFD-Planers, ganz egal was. CFD-Planer
-- only Echo, fertig." und „immer Echo mit Hedge, fertig … sowohl bei HT-ID oder bei Emin-ID immer Echo beim Challenge-Planer"). Einzige Ausnahme bleiben die
-- Minis „Tage sammeln" (E2).
-- Code dazu (app.py, gleicher Commit): ap_planen legt CFD-Challenges gleich als Echo an (route mt5, Slave = Fusion der ID, Multiplikator B2, echo_hedge
-- {status geplant}); eh_tick rechnet vor dem Start nur noch nach (status mit bzw. ohne + Grund), stellt nie zurück auf Echo V2 (eh_zurueck = 0).
-- TEIL 1 — Claim-Riegel trade_plans_a1_echo_hedge = E2-Fassung (sql/2026-11-03_echo_riegel_mini_frei.sql) PLUS: Echo mit Slave, aber echo_hedge 'ohne'
--   (eh_tick konnte vor dem Start Lots/Marge/Lesung nicht stellen) ODER 'geplant' (noch nicht frisch geprüft, fail-closed), wird gehalten wie Echo V2.
--   Heute trägt kein Echo-Plan 'ohne'/'geplant' (beides schreibt erst der neue Code bzw. Teil 2) → gefahrlos vor dem Code-Push einspielbar.
-- TEIL 2 — offene Echo-V2-Pläne auf CFD-Challenges, die noch starten sollen (nicht Mini, nie geclaimt, nie gestartet/an Orbit, Startzeit in der Zukunft
--   oder leer) → Echo mit Hedge aus der Hedge-Vorschau (ehv_tick = dieselbe B2-Rechnung wie eh_tick): multiplier = hedge_vorschau.multiplier, slave_risk =
--   hedge_vorschau.blow_eur, Slave = eigenes Fusion-Konto aus user_settings.echo_hedge_account; echo_hedge {status geplant, quelle sql_e3} → eh_tick rechnet
--   vor dem Start frisch nach. start_sperre fällt weg, Start-Fehler bleiben stehen. Ohne Vorschau-Lots oder eigenes Fusion-Konto: unverändert (Riegel hält).
--   Der DB-Trigger trade_plans_kontoart_weg lässt das nur bei Schalter echo_hedge an zu (live: an).
--   Trockenlauf 03.11.2026 ~23:55 Dubai: 0 Treffer. Die 10 heute hängenden Echo-V2-Pläne (9 HT, 1 Emin, Liste im Bericht S7_E3) sind verbraucht bzw. ihre
--   Startzeit ist vorbei — sie bleiben, wie sie sind; der Nachtlauf-Tagesreset räumt sie (verbraucht/zu spät → gelöscht, nie geclaimt → gelöscht).
--   Teil 2 ist das Netz für Echo-V2-Pläne, die nach dem Code-Push noch mit Startzeit in der Zukunft offen sind (z. B. vor dem Push angelegte Nachplanungen).
-- Wiederholbar (Teil 2 trifft danach nichts mehr). Rückbau Teil 1: sql/2026-11-03_echo_riegel_mini_frei.sql erneut einspielen.
-- NICHT vom Slave eingespielt.

-- TEIL 1: Claim-Riegel
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
  -- E3: Echo aus dem Planer hält, bis eh_tick den Hedge vor dem Start frisch gerechnet hat (echo_hedge 'mit'): 'ohne' = nicht stellbar, 'geplant' = noch
  -- nicht geprüft (Master-Entscheid fail-closed 03.11.2026: fällt Railway aus, startet kein Echo mit ungeprüftem Hedge; im Normalbetrieb stellt eh_tick
  -- ≥ 20 min vorher um, keine Verzögerung). Echo ohne echo_hedge-Marke (Hand-Pläne, Gruppen-Planer gp_planen) läuft wie bisher.
  if new.route = 'mt5' and new.slave_account_id is not null and coalesce(new.multiplier, 0) > 0
     and coalesce(new.mt5_baseline->'echo_hedge'->>'status', '') not in ('ohne', 'geplant') then
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
    when eh->>'status' = 'ohne' then 'Echo-Hedge nicht stellbar: ' || left(coalesce(eh->>'grund', eh->>'code', '?'), 160)
    when eh->>'status' = 'geplant' then 'Echo-Hedge vor dem Start noch nicht frisch geprüft (Railway eh_tick) — startet erst danach'
    when new.route = 'mt5' then 'Echo ohne Fusion-Slave/Multiplikator — CFD-Challenges nur mit Hedge'
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

-- TEIL 2: offene Echo-V2-CFD-Challenges → Echo mit Hedge (aus der Hedge-Vorschau)
update public.trade_plans p
   set route = 'mt5',
       slave_account_id = h.id, slave_name = h.name, slave_firm = h.firm,
       multiplier = (p.mt5_baseline->'hedge_vorschau'->>'multiplier')::numeric,
       slave_risk = (p.mt5_baseline->'hedge_vorschau'->>'blow_eur')::numeric,
       mt5_baseline = (coalesce(p.mt5_baseline, '{}'::jsonb) - 'start_sperre')
         || jsonb_build_object('echo_hedge', jsonb_build_object(
              'status', 'geplant', 'quelle', 'sql_e3', 'at', now(),
              'lots', (p.mt5_baseline->'hedge_vorschau'->>'lots')::numeric,
              'q', (p.mt5_baseline->'hedge_vorschau'->>'q')::numeric,
              'multiplier', (p.mt5_baseline->'hedge_vorschau'->>'multiplier')::numeric,
              'login', coalesce(nullif(s.value->>'hedgeLogin', ''), h.external_id))),
       notes = rtrim(coalesce(p.notes, '')) || E'\nEcho mit Hedge (E3, aus Echo V2 umgestellt): ' || (p.mt5_baseline->'hedge_vorschau'->>'lots') || ' Lot Fusion'
  from public.accounts a, public.user_settings s, public.accounts h
 where a.id = p.master_account_id and lower(coalesce(a.account_type, '')) in ('challenge', 'phase1', 'phase2')
   and s.user_id = p.user_id and s.key = 'echo_hedge_account' and h.id::text = s.value->>'accountId' and h.user_id = p.user_id
   and p.status = 'planned' and p.route = 'mt5v2' and coalesce(p.auto_plan, false)
   and p.started_at is null and p.orbit_gesendet_at is null
   and p.start_um_gestartet_at is null                              -- nie geclaimt: ein „verbraucht"er Plan (verpasst, Ziel, Archiv) bleibt verbraucht
   and (p.start_um is null or p.start_um >= now())                   -- nur, was noch starten soll (alte Vorschau vergangener Tage nie)
   and not (coalesce(p.mt5_baseline, '{}'::jsonb) ? 'tage_mini')
   and coalesce((p.mt5_baseline->'hedge_vorschau'->>'lots')::numeric, 0) > 0
   and coalesce((p.mt5_baseline->'hedge_vorschau'->>'multiplier')::numeric, 0) > 0
   and coalesce((p.mt5_baseline->'hedge_vorschau'->>'blow_eur')::numeric, 0) > 0;
