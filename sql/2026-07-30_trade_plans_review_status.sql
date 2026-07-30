-- ============================================================================
-- Prophos: trade_plans.status — neuer Status 'review' (Überprüfen)
--
-- Neuer Trade-Lifecycle: planned → open → review → completed.
-- 'review' = Trade-Ende wurde automatisch erkannt, Auto-P&L ist schon in
-- master_pl/slave_pl gespeichert, wartet auf Finns Bestätigung im Modal.
-- Erst beim Bestätigen (→ completed) entstehen die Finanzen-Buchungen.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

-- Alten Status-Check entfernen (Name kann je nach Anlage-Historie variieren,
-- deshalb dynamisch über pg_constraint gesucht statt festen Namen zu raten)
do $$
declare c record;
begin
  for c in
    select conname from pg_constraint
    where conrelid = 'public.trade_plans'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%status%'
  loop
    execute format('alter table public.trade_plans drop constraint %I', c.conname);
  end loop;
end $$;

alter table public.trade_plans
  add constraint trade_plans_status_check
  check (status in ('planned','open','review','completed'));
