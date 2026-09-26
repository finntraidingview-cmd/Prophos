-- 2026-09-26: Schein-Kerzen vom Wochenende löschen (Auftrag Koordination B7). Reader 0.9.5 auf pc-usq1i6 schrieb nach
-- Finns Neustart (Sa 19:38 UTC) jede Minute eine Tick-Kerze o=h=l=c=30889.25 (Freitags-Schluss, modus 'endofday') —
-- die 250-ms-Stichproben des unveränderten Quotes zählten als Ticks. Ab Reader 0.9.6 entstehen Tick-Kerzen nur bei
-- offenem CME-Markt aus echten Ticks. Stand beim Schreiben: 8 Zeilen (MNQ + NQ je 4, 19:38–19:41 UTC).
-- Gelöscht werden NUR Tick-Kerzen (quelle 'ws-tick') mit o=h=l=c zwischen Fr 16:00 CT (21:00 UTC) und So 17:00 CT
-- (22:00 UTC) — also genau die geschlossene Zeit. Chart-Serien-Kerzen (quelle 'ws') bleiben unberührt.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
delete from public.tv_kurs_1m
 where quelle = 'ws-tick'
   and minute >= '2026-09-25 21:00:00+00' and minute < '2026-09-27 22:00:00+00'
   and o = h and h = l and l = c;
