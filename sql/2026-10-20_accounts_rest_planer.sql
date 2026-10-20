-- Rest zurück in den Trade-Planer (Finn 20.10.2026 22:55 Dubai, Radar → Bestanden → Rest von Hand: „Vor allem bei CFDs soll bei so vielen
-- Dollar einfach noch ein Trade automatisch gemacht werden … entweder ich mache den Trade manuell, oder ‚OK, abhaken und zurück in den
-- Trade-Planer' — der macht den Rest automatisch fertig").
-- Knopf „→ Trade-Planer" in der Radar-Station setzt rest_planer_at; der Planer (app.py ap_konto_rechnen) plant dann auch unter der
-- Rest-Grenze (Futures < 100 $, CFD < 10 $) einen Klein-Trade statt „Rest … von Hand". Die Ziel-Wache (zw_tick) löscht das Feld, sobald
-- die Balance das Ziel erreicht; das Archivieren des Kontos löscht es ebenfalls. Nur eine Zusatzspalte, leer — nichts Bestehendes ändert sich.
alter table public.accounts add column if not exists rest_planer_at timestamptz;
comment on column public.accounts.rest_planer_at is 'Rest zurück in den Planer (20.10.2026): gesetzt = der Planer holt den Rest bis zum Ziel auch unter der Rest-Grenze; null = Rest von Hand';
