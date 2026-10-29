-- HEDGE-TRADES BESTÄTIGEN (Finn 29.10.2026, über Master: „Bevor wir die Trades mit Auto-Planen machen, will ich alle Trades, die mit der
-- neuen Logik kommen, unter Admin → Challenge-Planer bestätigen müssen.") — GEMEINSAM für beide neuen Hedge-Wege: finaler Tradeify mit
-- Gegenhedge (Slave 4, mt5_baseline.hedge_art = 'tradeify_final') und Apex-WD-Hedge (Slave 1, hedge_art = 'apex').
--
-- (1) trade_plans.hedge_freigabe_at timestamptz (null = nicht freigegeben) + hedge_freigabe_von text — gesetzt nur über
--     POST /admin/auto-plan/hedge-freigabe (Admin, Block „Neue Hedge-Trades bestätigen" im Challenge-Planer).
-- (2) Claim-Riegel trade_plans_a0_hedge_freigabe (feuert als ERSTER Claim-Trigger, alphabetisch vor trade_plans_a_final_halten): ein
--     geplanter Plan mit hedge_art in ('apex','tradeify_final') und ohne hedge_freigabe_at startet nicht — Claim scheitert (return null),
--     der Plan bleibt planned. start_um rückt 15–30 min weiter (gestreut, Jitter-Regel; so räumen Nachtlauf/Tages-Reset ihn nie weg und
--     er startet kurz nach der Bestätigung), mt5_baseline.start_sperre {art 'hedge_freigabe'} → ⚪ EINMAL „wartet auf deine Bestätigung im
--     Challenge-Planer" (alarm_tick), Protokoll auto_plan_umplanung nur beim ersten Halt. Mehrfach-Claim < 1 min: nichts neu schieben.
--     Ein Start von Hand ohne Claim bleibt möglich (Finns Entscheidung).
-- Wiederholbar. Rückbau: drop trigger trade_plans_a0_hedge_freigabe on public.trade_plans; drop function public.trade_plans_a0_hedge_freigabe();
-- (die Spalten dürfen bleiben).

alter table public.trade_plans add column if not exists hedge_freigabe_at timestamptz;
alter table public.trade_plans add column if not exists hedge_freigabe_von text;

create or replace function public.trade_plans_a0_hedge_freigabe()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  ss jsonb;
  ziel timestamptz;
  erst boolean;
begin
  if new.status is distinct from 'planned' or new.hedge_freigabe_at is not null
     or coalesce(new.mt5_baseline->>'hedge_art', '') not in ('apex', 'tradeify_final') then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'hedge_freigabe' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
  end if;
  erst := coalesce(ss->>'art', '') <> 'hedge_freigabe';
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'hedge_freigabe', 'text', 'wartet auf deine Bestätigung im Challenge-Planer', 'at', now(), 'naechster', ziel,
           'erst_at', case when erst then now() else coalesce(ss->'erst_at', to_jsonb(now())) end,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Hedge-Trade wartet auf Bestätigung] ' || coalesce(new.mt5_baseline->>'hedge_art', '?')
            || ' — erst nach „Bestätigen" im Challenge-Planer; Start rückt bis dahin je 15–30 min weiter', 'start');
  end if;
  return null;
end $$;

drop trigger if exists trade_plans_a0_hedge_freigabe on public.trade_plans;
create trigger trade_plans_a0_hedge_freigabe
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_a0_hedge_freigabe();
