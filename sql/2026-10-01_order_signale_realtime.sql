-- Supabase-Diät Teil A (01.10.2026): Realtime-Wecker für den Signal-Empfänger der PC-Tabs.
-- Befund: Compute NANO, DB hing in Wellen (12:10/12:30/12:50 UTC, PGRST003); 19.295 GET order_signale ?status=eq.wartet
-- (+ 4.889 OPTIONS) in 09:00–12:50 UTC von den PC-Tabs — der Poll lief meist im 5-s-Takt und kam fast immer leer zurück,
-- bei ~5–10 Signalen je Stunde.
-- Änderung: order_signale in die Publication supabase_realtime. Die PC-Tabs abonnieren NUR event INSERT, gefiltert auf die
-- eigene user_id (RLS „order_signale eigene" = user_id = auth.uid(), dieselben Zeilen wie der Poll) und wecken damit den
-- Empfänger; der Poll bleibt als Reserve. Die Publication kann nicht je Tabelle auf INSERT beschränkt werden — die UPDATEs
-- (~1.300/h) werden mit dekodiert, ohne UPDATE-Abo aber an niemanden verteilt.
-- Keine Daten werden verändert oder gelöscht.
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'order_signale'
  ) then
    alter publication supabase_realtime add table public.order_signale;
  end if;
end $$;
