-- ============================================================================
-- Prophos/Echo: echo_loesch_auftraege — Terminal-Löschaufträge für
-- archivierte Accounts
--
-- Finns Ansage (07.09.2026): „Wenn der Account archiviert wird — also
-- geblowet wurde oder bestanden —, dann soll automatisch in Unterecho dieses
-- Terminal für den Account gelöscht werden, weil ich sonst hier irgendwann
-- mal auf einmal so 1000 Terminals rumliegen habe, wo quasi nur alte Dinge
-- rumliegen."
--
-- Warum ein AUFTRAG statt eines direkten Lösch-Calls beim Archivieren:
--  · Das Terminal liegt auf einem Windows-PC — archiviert wird aber womöglich
--    am Mac oder unter einem anderen Profil. Der Auftrag wartet, bis der
--    Prophos-Tab des RICHTIGEN PCs ihn sieht (echoLoeschGuard in mtcLoad).
--  · Direkt nach dem Trade-Ende baut der Copier oft noch den Hedge ab — der
--    Lösch-Riegel in panel.py sagt dann zu Recht 409. Der Auftrag bleibt
--    liegen, der Guard versucht es beim nächsten Poll wieder, bis der Riegel
--    durchlässt. Kein force, niemals — alle vier Riegel bleiben unangetastet.
--
-- Schlüssel ist der Master-Login (Prop-Firm-Kontonummer) — PC-übergreifend
-- stabil, gleiche Wahl wie mt5_links/mt5LinkCellHtml. Erledigte Aufträge
-- werden markiert statt gelöscht (erledigt_am/erledigt_info): nachschaubar,
-- welcher PC wann welches Terminal entfernt hat.
--
-- Geteilt wie echo_hedge/echo_notfall: die Flotte ist EINE Operation, jeder
-- eingeloggte User liest und schreibt (die PCs laufen unter verschiedenen
-- Profilen — wer auch immer dort eingeloggt ist, darf aufräumen).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.echo_loesch_auftraege (
  mt5_login     text primary key,
  grund         text not null,            -- 'blown' | 'passed' | 'passed_pending'
  account_name  text,                     -- reine Anzeige (Banner/Nachvollziehbarkeit)
  angelegt_am   timestamptz not null default now(),
  erledigt_am   timestamptz,              -- null = offen, Guard versucht weiter
  erledigt_info text                      -- z.B. die gelöschte config-Datei
);

alter table public.echo_loesch_auftraege enable row level security;

drop policy if exists "echo_loesch read"   on public.echo_loesch_auftraege;
drop policy if exists "echo_loesch insert" on public.echo_loesch_auftraege;
drop policy if exists "echo_loesch update" on public.echo_loesch_auftraege;

create policy "echo_loesch read"   on public.echo_loesch_auftraege for select to authenticated using (true);
create policy "echo_loesch insert" on public.echo_loesch_auftraege for insert to authenticated with check (true);
create policy "echo_loesch update" on public.echo_loesch_auftraege for update to authenticated using (true) with check (true);
