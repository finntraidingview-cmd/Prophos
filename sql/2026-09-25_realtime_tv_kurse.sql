-- ============================================================================
-- Prophos: Supabase Realtime für den Markt-Feed (25.09.2026, Aufgabe B)
--
-- Finn am ersten Live-Feed: „Eventuell geht es jetzt ein bisschen schneller,
-- sodass man echt quasi live die Daten kriegt." Mac/Handy hören per
-- supabase.channel('markt-live') auf postgres_changes von tv_kurse (Kopf,
-- laufende Kerze) und tv_kurs_1m (Kerzen) — statt nur alle 5 s zu pollen
-- (Polling bleibt als Rückfall, 15 s bei SUBSCRIBED).
--
-- Dafür müssen beide Tabellen in der Publikation supabase_realtime stehen.
-- Die RLS-Lesepolicies (authenticated, using true) gelten auch für Realtime —
-- eingeloggte Prophos-Nutzer sehen die Änderungen, sonst niemand.
-- Idempotent: fügt nur hinzu, was fehlt.
-- ============================================================================
do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'tv_kurse') then
    alter publication supabase_realtime add table public.tv_kurse;
  end if;
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'tv_kurs_1m') then
    alter publication supabase_realtime add table public.tv_kurs_1m;
  end if;
end $$;
