-- TRADEIFY ÜBER ORBIT PRIO 2 + EIN HEDGE JE PLAN (TM1, 05.11.2026, Finn über den Master: „du kannst ja machen bei Tradeify, auch über Orbit, Prio 2 bei ihm“ — Emin)
-- NICHT automatisch einspielen, Finn/Master spielt ein.
--
-- Tradeify ist im Modell-Dropdown jetzt wählbar (app.py, AP_MODELL_NICHT_WAEHLBAR entfernt). Zwei Hedge-Wege können dann dieselbe Firma treffen:
--   Orbit Prio 2   (Railway ah_tick)  → mt5_baseline.hedge_art 'apex', apex_hedge.status 'mit', hedge_eur > 0, orbit_v3 = false
--   finaler Trade  (Railway tfh_tick) → mt5_baseline.hedge_art 'tradeify_final', tradeify_hedge.status 'mit', orbit_v3 = true, hedge_eur > 0
-- Railway trennt sie über dieselbe Final-Erkennung (tfh_ist_final = prophos_plan_final): ah_tick nimmt nur nicht-finale Tradeify-Pläne, tfh_tick lässt
-- einen schon auf Prio 2 umgestellten Plan aus. Dieser Riegel ist die zweite Wand in der DB (Vorfall Duplikum-Doppelhedge 05.11.2026, Emin): ein
-- geplanter Plan, der schon den Prio-2-Hedge trägt, kann NICHT zusätzlich auf Orbit V3 oder den Final-Hedge gestellt werden — das UPDATE scheitert
-- (tfh_tick fängt den Fehler und schreibt ihn in die Spur), der Plan bleibt mit genau einem Hedge.
-- Bestand 05.11.2026 (SELECT vor dem Schreiben): 0 Pläne mit apex_hedge 'mit' + orbit_v3, 0 mit beiden 'mit', 0 Tradeify-Pläne mit hedge_art 'apex'.
-- Der Kontoart-Riegel trade_plans_kontoart_weg braucht KEINE Änderung: sein Prio-2-Zweig (sql/2026-11-05_orbit_prio2.sql (3)) lässt jede Firma mit
-- der Marke hedge_art 'apex' durch, der Final-Zweig verlangt orbit_v3 + tradeify_hedge 'mit' — ein Plan erfüllt nie beide.
--
-- Rückbau:
--   drop trigger if exists trade_plans_a1_ein_hedge on public.trade_plans;
--   drop function if exists public.trade_plans_a1_ein_hedge();

create or replace function public.trade_plans_a1_ein_hedge()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
begin
  if coalesce(new.status, 'planned') <> 'planned' then
    return new;
  end if;
  if coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = 'mit'
     and (coalesce(new.orbit_v3, false) or coalesce(new.mt5_baseline->'tradeify_hedge'->>'status', '') = 'mit') then
    raise exception 'Plan % trägt schon den Orbit-Prio-2-Hedge — kein zweiter Hedge (Orbit V3 / finaler Tradeify) auf demselben Plan.', new.id
      using errcode = 'check_violation', hint = 'ein_hedge_je_plan';
  end if;
  return new;
end $function$;

drop trigger if exists trade_plans_a1_ein_hedge on public.trade_plans;
create trigger trade_plans_a1_ein_hedge
  before insert or update of orbit_v3, hedge_eur, mt5_baseline, status on public.trade_plans
  for each row execute function public.trade_plans_a1_ein_hedge();

-- Kontrolle (muss 0 sein, vor und nach dem Einspielen):
-- select count(*) from public.trade_plans where status = 'planned' and mt5_baseline->'apex_hedge'->>'status' = 'mit'
--    and (coalesce(orbit_v3, false) or mt5_baseline->'tradeify_hedge'->>'status' = 'mit');
