-- LOTS-DECKEL, DB-NETZ (Finn 02.11.2026: „Wenn beim PreCheck mal irgendwas durchgeht und auf dem Fusion-Account mehr als 16 Lots geplant sind, startet der Trade nicht. Stattdessen
-- kriegt man erst mal eine Meldung und muss dann einmal auf OK drücken."; Vorfall Marc 32 statt 3,2 Lot). Genau 16 geht.
-- Der PC-Tab sperrt selbst vor dem Puls-Auftrag (tpLotsDeckelFehlt); dieser Riegel ist nur das Netz für alte Tabs am Claim, Muster trade_plans_a0_hedge_freigabe. Rechnet Kontrakte × Multiplikator,
-- nicht die feinere Tab-Rechnung. OK = mt5_baseline.lots_ok, setzt POST /admin/auto-plan/lots-ok; es gilt nur, solange Kontrakte und Multiplikator gleich sind. Nur echte Starts, Verbrauchs-Claims gehen durch.
-- Rückbau: drop trigger trade_plans_a0_lots_deckel on public.trade_plans; drop function public.trade_plans_a0_lots_deckel();
-- REIHENFOLGE: erst Railway + prophos.html, dann diese Datei. Wiederholbar. NICHT vom Slave eingespielt.

create or replace function public.trade_plans_a0_lots_deckel()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  lots numeric := coalesce(new.master_contracts, 0) * coalesce(new.multiplier, 0);
  ok jsonb := new.mt5_baseline->'lots_ok';
begin
  if new.status is distinct from 'planned' or coalesce(new.start_claim_art, 'start') <> 'start' or lots <= 16 then
    return new;
  end if;
  if not ((new.route in ('tvv2', 'tsv2') and coalesce(new.hedge_eur, 0) > 0) or (new.route = 'mt5' and new.slave_firm ilike '%fusion%')) then
    return new;
  end if;
  if ok is not null and abs(coalesce((ok->>'kt')::numeric, -1) - new.master_contracts) < 0.000001 and abs(coalesce((ok->>'mult')::numeric, -1) - new.multiplier) < 0.000001 then
    return new;
  end if;
  return null;                                    -- Claim fällt aus, Plan bleibt stehen; Meldung und OK kommen aus „Braucht dich“ und alarm_tick
end $$;

drop trigger if exists trade_plans_a0_lots_deckel on public.trade_plans;
create trigger trade_plans_a0_lots_deckel
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_a0_lots_deckel();

-- Prüfen: select tgname from pg_trigger where tgname = 'trade_plans_a0_lots_deckel';
