-- Geister-Hand-Positionen auf archivierten Konten schließen (Finn 06.11.2026 ~04:15 Dubai, Nova-Test Marco …1329: „Signal konnte nicht
-- gesendet werden: Gegenrichtung gesperrt: Hand-Position „150k EXPRESS-V2-DLL-696284-49529477 → Funded" (NQ × 3) läuft dort seit 05.11.
-- 05:25 Dubai SHORT"). Das Konto …9477 ist seit 05.11. als geblowt archiviert; die Position wurde zuletzt 05:26 gesehen und bekam nie weg_at.
-- Live 06.11.: 10 offene fremd_positionen, ALLE auf archivierten Konten (5× Marco Topstep tsx, 5× TV bei anderen IDs, zuletzt gesehen 09.10.–05.11.).
-- Ein archiviertes (geblowtes/bestandenes) Konto hat keine offene Position mehr → weg_at = zuletzt_gesehen. Idempotent.
update public.fremd_positionen f
   set weg_at = f.zuletzt_gesehen
 where f.weg_at is null
   and exists (select 1 from public.user_settings s
                where s.user_id = f.user_id and s.key = 'archive'
                  and coalesce((s.value->f.konto_id::text->>'archived')::boolean, false));
