-- ============================================================================
-- Prophos: trade_plans.watch_tickets — der Ticket-Beweis überlebt Deploys
--
-- KONTEXT 07.08.2026: Der Server-Wächter ordnet P&L ausschließlich über die
-- beim Trade-Start beobachteten MASTER-Ticket-Nummern zu (exakter Beweis,
-- kein Raten). Diese Tickets lagen bisher nur im RAM des Railway-Prozesses —
-- jeder Deploy/Restart im falschen Moment hat den Beweis gelöscht, und der
-- Plan wanderte mit ehrlich-leerem P&L nach "Überprüfen", obwohl der Wächter
-- den Start selbst beobachtet hatte (Review-Finding, bestätigt).
--
-- Diese Spalte persistiert die Tickets am Plan. Der Code schreibt sie
-- best-effort (fehlt die Spalte, läuft alles wie bisher — nur ohne
-- Restart-Schutz) und liest sie als Fallback, wenn der RAM-State leer ist.
-- Auch das Überprüfen-Modal im Frontend nutzt sie für beweisbare Vorschläge.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.trade_plans
  add column if not exists watch_tickets jsonb;

comment on column public.trade_plans.watch_tickets is
  'Master-Ticket-Nummern des laufenden Trades (vom Server-Wächter beim Start beobachtet). Grundlage für die exakte P&L-Zuordnung über masterTicket in Duplikums getClosedPositions.';
