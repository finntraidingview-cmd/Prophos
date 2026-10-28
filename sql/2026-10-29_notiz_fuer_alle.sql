-- NOTIZ FÜR ALLE IDs (Finn 29.10.2026 01:35: „Füge unter Admin auch einen Notizzettel hinzu — quasi eine Option an einem Zettel:
-- da, wo ‚Kopieren' und ‚Löschen' steht, auch ein Feld, um die Notiz für alle IDs zu teilen. So kann ich als Person eine Notiz
-- kurz für alle IDs teilen.")
--
-- Weg (a): ein Haken am Zettel statt Kopien je ID. Ein geteilter Zettel bleibt beim Ersteller (nur er ändert/löscht ihn — die
-- bestehenden Policies „own notes update/delete" bleiben), alle IDs DERSELBEN Gruppe (id_gruppe_mitglied, prophos_gruppe_von:
-- Hermann Technologies bzw. Emins Gruppe) dürfen ihn zusätzlich LESEN. Keine Gruppe = nichts geteilt. geteilt_von trägt den
-- Anzeigenamen des Teilenden, damit der Chip „von <ID>" im Notizzettel ohne Admin-Daten geht (ein normaler Login kennt die
-- Namen der anderen IDs nicht). Idempotent. Nie direkt migrieren — Finn/Master spielen die Datei ein.

alter table public.notes add column if not exists fuer_alle   boolean not null default false;
alter table public.notes add column if not exists geteilt_von text;

-- Lesen: eigene Zettel wie bisher („own notes select"), dazu geteilte Zettel aus der eigenen Gruppe.
drop policy if exists "notes geteilte lesen" on public.notes;
create policy "notes geteilte lesen" on public.notes
  for select using (
    fuer_alle
    and public.prophos_gruppe_von(user_id) is not null
    and public.prophos_gruppe_von(user_id) = public.prophos_gruppe_von((select auth.uid()))
  );

-- Schnell für die Gruppen-Lesung (die Tabelle ist klein, der Index hält die Policy trotzdem billig)
create index if not exists notes_fuer_alle_idx on public.notes (user_id) where fuer_alle;

-- Prüfung nach dem Einspielen (als beliebiger HT-Login):
--   select id, left(content, 30), fuer_alle, geteilt_von from notes where fuer_alle;   -- zeigt geteilte Zettel der eigenen Gruppe
