-- ════════════════════════════════════════════════════════════════════════════
-- 2026-09-01: Nur-Lese-Rolle "backup_reader" für das tägliche Offsite-Backup
-- (Finn: "einen Agenten, der mir jeden Tag ein Backup macht, falls Supabase
-- mal downgeht")
--
-- Warum eine eigene Rolle statt des service_role-Keys:
--   - Auf dem Mac lag bisher gar kein Supabase-Key (com.prophos.flask.plist
--     setzt keinen). Statt den Allmachts-Key dort abzulegen, bekommt das
--     Backup einen Zugang, der AUSSCHLIESSLICH lesen kann — selbst wenn die
--     Zugangsdaten abhandenkommen, kann damit nichts verändert werden.
--   - Das Passwort liegt NUR lokal auf dem Mac (~/.prophos/backup-config.json,
--     chmod 600), nie im Repo. Der Platzhalter unten wird beim Einrichten
--     per ALTER ROLE ersetzt.
--
-- ABSICHTLICH keine ALTER DEFAULT PRIVILEGES: Eine später neu angelegte
-- Tabelle soll beim Backup laut mit "permission denied" scheitern statt
-- still leer gesichert zu werden. Dann diese Datei einfach ERNEUT einspielen
-- (sie ist idempotent) — sie holt alle neuen Tabellen nach.
-- ════════════════════════════════════════════════════════════════════════════

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'backup_reader') then
    -- noinherit: die Rolle soll nichts von anderen Rollen erben, nur ihre
    -- eigenen, unten explizit vergebenen SELECT-Rechte haben
    create role backup_reader login noinherit password 'PLATZHALTER-WIRD-BEIM-EINRICHTEN-ERSETZT';
  end if;
end $$;

grant usage on schema public to backup_reader;

-- SELECT-Recht + RLS-Policy für JEDE Tabelle in public. Die Policy ist nötig,
-- weil auf allen Tabellen RLS aktiv ist — ohne sie sähe backup_reader trotz
-- GRANT nur leere Ergebnisse (RLS filtert nach auth.uid(), das es bei einer
-- direkten DB-Verbindung nicht gibt).
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public'
  loop
    execute format('grant select on table public.%I to backup_reader', t.tablename);
    if not exists (
      select 1 from pg_policies
      where schemaname = 'public' and tablename = t.tablename
        and policyname = 'backup_reader_select'
    ) then
      execute format(
        'create policy backup_reader_select on public.%I for select to backup_reader using (true)',
        t.tablename);
    end if;
  end loop;
end $$;
