-- 2026-09-24 (abends): Regel „V2 = neues Kapitel" im Trigger.
-- Finn: „Alle Trades über Echo V2 / Orbit V2 gehören jetzt zur neuen Kapitel." Bis hierhin setzte
-- der Trigger das Kapitel eines Trade-Plans rein nach Anlagedatum; nur der Backfill hatte die
-- V2-Ausnahme. Jetzt gilt sie dauerhaft und auch beim Ändern der Route (Plan bearbeiten):
--   route in (mt5v2, tvv2)  → das jüngste Kapitel OHNE Hedge (heute id 2), egal wann angelegt
--   alle anderen Routen     → wie bisher nach Datum, nur wenn kapitel_id noch leer ist
-- Kein Rück-Mapping: wird ein V2-Plan wieder auf einen Hedge-Weg gestellt, bleibt das Kapitel
-- stehen (Finn kann es dann bewusst per SQL setzen). Keine Regel-/Compliance-Prüfung.
create or replace function public.set_kapitel()
returns trigger
language plpgsql
as $$
declare
  v_ohne smallint;
begin
  if tg_table_name = 'trade_plans' and coalesce(new.route, '') in ('mt5v2', 'tvv2') then
    select id into v_ohne from public.kapitel where hedge = false order by von desc limit 1;
    if v_ohne is not null then
      new.kapitel_id := v_ohne;
      return new;
    end if;
  end if;
  if new.kapitel_id is null then
    if tg_table_name = 'transactions' then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
    else
      new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
    end if;
  end if;
  return new;
end;
$$;

-- trade_plans: zusätzlich bei Routen-Änderung feuern (Plan bearbeiten → Weg auf V2 gedreht).
drop trigger if exists trade_plans_set_kapitel on public.trade_plans;
create trigger trade_plans_set_kapitel
  before insert or update of route on public.trade_plans
  for each row execute function public.set_kapitel();

-- Bestand nachziehen (idempotent): alle V2-Pläne ins Kapitel ohne Hedge.
update public.trade_plans p
   set kapitel_id = k.id
  from (select id from public.kapitel where hedge = false order by von desc limit 1) k
 where coalesce(p.route, '') in ('mt5v2', 'tvv2') and p.kapitel_id is distinct from k.id;

-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
