-- NOTIZ FÜR ALLE IDs — VERWALTEN (Finn 29.10.2026 01:05: „Wenn ich den [Slider ‚für alle IDs'] drücke, sehen ihn alle IDs und können
-- ihn auch verwalten. Relativ simpel, nicht so advanced mit Admin und so.")
--
-- Nachtrag zu sql/2026-10-29_notiz_fuer_alle.sql (Spalten fuer_alle/geteilt_von, Lese-Policy „notes geteilte lesen"): ein geteilter Zettel
-- ist für alle IDs DERSELBEN Gruppe (prophos_gruppe_von) auch änderbar und löschbar — inklusive Slider wieder aus (dann verschwindet er
-- bei den anderen, gewollt). Nicht geteilte Zettel bleiben wie bisher nur beim Ersteller („own notes …"). Idempotent, nie direkt
-- migrieren — Finn/Master spielen die Datei ein.

drop policy if exists "notes geteilte aendern" on public.notes;
create policy "notes geteilte aendern" on public.notes
  for update
  using (
    fuer_alle
    and public.prophos_gruppe_von(user_id) is not null
    and public.prophos_gruppe_von(user_id) = public.prophos_gruppe_von((select auth.uid()))
  )
  with check (
    -- nur innerhalb der Gruppe; fuer_alle darf auf false gehen (Slider aus = „nicht mehr teilen", danach sieht ihn nur noch der
    -- Ersteller). Hinweis Prüfer 29.10.2026: with check sieht die alte Zeile nicht — ein Gruppenmitglied könnte per rohem Request
    -- user_id auf sich umschreiben. Die Oberfläche schickt user_id nie, Notizen sind „nie was Wichtiges" (Finn 29.09.); wenn das je
    -- stören soll: revoke update (user_id) on public.notes from authenticated.
    public.prophos_gruppe_von(user_id) is not null
    and public.prophos_gruppe_von(user_id) = public.prophos_gruppe_von((select auth.uid()))
  );

drop policy if exists "notes geteilte loeschen" on public.notes;
create policy "notes geteilte loeschen" on public.notes
  for delete using (
    fuer_alle
    and public.prophos_gruppe_von(user_id) is not null
    and public.prophos_gruppe_von(user_id) = public.prophos_gruppe_von((select auth.uid()))
  );

-- Prüfung nach dem Einspielen (als anderer HT-Login): update notes set content = content where fuer_alle;  -- Zeilen > 0

-- Nachtrag Prüfer S2 (29.10.2026, eingespielt 01:45 Dubai): notes.user_id darf niemand umschreiben. Ein Spalten-Revoke
-- allein greift nicht, weil authenticated ein tabellenweites UPDATE hält — deshalb Tabellenrecht weg, Spaltenrechte nur
-- für die Felder, die die Oberfläche schreibt (noteSave: content, updated_at · noteTeilen: fuer_alle, geteilt_von).
revoke update on public.notes from authenticated;
grant update (content, updated_at, fuer_alle, geteilt_von) on public.notes to authenticated;
