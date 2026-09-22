-- 2026-09-23: Kompass-Forecasts (Finn: „bau eine Seite in Prophos unter Admin, wo ich die Daten
-- immer live bekomme + alles in die DB packen immer"). Pascals Research-Agent „Kompass" postet
-- mehrmals täglich Nasdaq-100-Forecasts (LONG/SHORT, Konfidenz 1–5) in einen Cloudflare-Worker
-- (kompass-api.pascal-hermann-22.workers.dev?category=k:ideas). Der Worker liefert nur die
-- laufende Liste — nichts davon ist bei uns dauerhaft. Diese Tabelle ist das Archiv:
-- eine Zeile je Forecast (Pascals id ist der Schlüssel), gefüllt vom Sammler in app.py
-- (Railway, alle 5 min) UND vom Admin-Tab beim Laden (Browser-Upsert, falls Railway hängt).
create table if not exists public.kompass_forecasts (
  id              text primary key,                 -- Pascals id, z. B. idea-1790114840
  session         text not null,                    -- asia | prelondon | london | ny | ny_update | hourly | sonst
  kontext         text,                             -- Pascals context-Text im Original
  datum           date,
  zeit            text,                             -- 'HH:MM' Dubai-Zeit, nur beim Hourly gesetzt
  bias            text check (bias in ('LONG','SHORT')),
  konfidenz       smallint check (konfidenz between 1 and 5),
  titel           text,
  text            text,                             -- Recherche-Volltext (body)
  roh             jsonb,                            -- kompletter Roh-Eintrag
  erfasst_at      timestamptz not null default now(),   -- wann wir ihn zum ersten Mal gesehen haben
  aktualisiert_at timestamptz not null default now()
);
create index if not exists kompass_forecasts_session_datum on public.kompass_forecasts (session, datum desc);
create index if not exists kompass_forecasts_erfasst on public.kompass_forecasts (erfasst_at desc);

alter table public.kompass_forecasts enable row level security;
-- Wie wd_farmer_regeln: offen für alle angemeldeten Nutzer. Keine Geheimnisse drin,
-- und jeder Admin-Tab darf nachtragen, was der Sammler noch nicht hat.
drop policy if exists "kompass_forecasts angemeldet" on public.kompass_forecasts;
create policy "kompass_forecasts angemeldet" on public.kompass_forecasts
  for all to authenticated using (true) with check (true);
