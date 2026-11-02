-- LOTS-DECKEL, DB-NETZ (Finn 02.11.2026: „Wenn beim PreCheck mal irgendwas durchgeht und auf dem Fusion-Account mehr als 16 Lots geplant sind, startet der Trade nicht. Stattdessen
-- kriegt man erst mal eine Meldung und muss dann einmal auf OK drücken."; Vorfall Marc 32 statt 3,2 Lot). Genau 16 geht.
-- Der PC-Tab sperrt selbst vor dem Puls-Auftrag (tpLotsDeckelFrisch); dieser Riegel fängt alte Tabs am Claim und rechnet Kontrakte × Multiplikator, der Tab nimmt das Größere aus diesem Wert und seiner Open-Rechnung.
-- OK = mt5_baseline.lots_ok, setzt POST /admin/auto-plan/lots-ok; hier gilt es, solange Kontrakte × Multiplikator nicht über der freigegebenen Lot-Zahl liegt. Nur echte Starts, Verbrauchs-Claims gehen durch.
-- Rückbau: drop trigger trade_plans_a0_lots_deckel on public.trade_plans; drop function public.trade_plans_a0_lots_deckel();
-- REIHENFOLGE: erst Railway + prophos.html, dann diese Datei. Wiederholbar. NICHT vom Slave eingespielt.

create or replace function public.trade_plans_a0_lots_deckel()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  lots numeric := round(coalesce(new.master_contracts, 0) * coalesce(new.multiplier, 0), 2);
  ok jsonb := new.mt5_baseline->'lots_ok';
begin
  if new.status is distinct from 'planned' or coalesce(new.start_claim_art, 'start') <> 'start' or lots <= 16 then
    return new;
  end if;
  if not coalesce((new.route in ('tvv2', 'tsv2') and coalesce(new.hedge_eur, 0) > 0) or (new.route in ('mt5', 'tvplus', 'dup') and new.slave_firm ilike '%fusion%'), false) then
    return new;
  end if;
  if lots <= coalesce((ok->>'lots')::numeric, -1) + 0.011 then   -- OK über mindestens diese Menge: das Netz rechnet nur Kontrakte × Multiplikator, der Tab prüft die genaue Zahl
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
