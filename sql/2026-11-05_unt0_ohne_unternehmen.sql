-- UNT0 — NEUE ID BEKOMMT KEIN UNTERNEHMEN (Finn 05.11.2026 ~07:20 Dubai: „Wenn wir eine neue ID kriegen, stelle ich den PC auf und sage, wo sie
-- hinkommt. Sag mir aber immer Bescheid"; Schritt 1 aus berichte/2026-11-05_G2b_unternehmen_ebene.md).
--
-- Bis heute legte der Trigger id_gruppe_neu_ht (sql/2026-10-08_admin_gruppen.sql:79-93) jede neue Registrierung in „Hermann Technologies" — und eine
-- ID ohne Zeile zählte ohnehin als HT (= alles sehen, Kasse/Wallets ändern). Ab jetzt:
--   1) der Trigger ist weg — eine neue ID hat KEINE Zeile in id_gruppe_mitglied (= ohne Unternehmen);
--   2) admin_nur_eigene() gilt auch für eine eingeloggte ID ohne Zeile (solange es Unternehmen gibt) → die restriktiven Policies auf kasse_entries,
--      id_wallets, wallet_tx, wallet_snapshots, wallet_labels lassen sie nur an Eigenes (admin_sichtbare_ids = nur sie selbst);
--   3) die Übersicht id_gruppen_uebersicht nennt sie „ohne Unternehmen (zuordnen)" statt „Hermann Technologies (ohne Zeile)".
-- Das Backend (app.py admin_sicht_menge) zeigt ihr im Admin nur sich selbst; die Master-IDs bekommen 🟠 einmal je neuer ID (ohne_unternehmen_tick),
-- zugeordnet wird im Admin („Ohne Unternehmen" → Zuordnen, POST /admin/id-gruppe) oder wie bisher per update.
-- BITGLEICH für alle bestehenden IDs: live 05.11.2026 haben alle 21 IDs eine Zeile (15 HT, 6 Emin) — die neue Bedingung trifft keine von ihnen.
-- auth.uid() is null (Service-Key, Backup-Rolle, anon) bleibt unberührt.
-- Live-md5 vor dem Einspielen (05.11.2026): admin_nur_eigene 1196bb68a48ac010088cc760267ebc4d, id_gruppe_neu_ht ebfab840dc6e1a439c07e19736cd3265.
-- Rückbau: sql/2026-11-05_unt0_ohne_unternehmen_rueckbau.sql. NICHT vom Slave eingespielt (Master, auf Finns Wort).

begin;

-- 1) Kein automatisches HT mehr. Die Funktion bleibt liegen (Rückbau = Trigger wieder anlegen).
drop trigger if exists id_gruppe_neu_ht on auth.users;

-- 2) ohne Unternehmen = nur eigene
create or replace function public.admin_nur_eigene()
 returns boolean
 language sql
 stable security definer
 set search_path to ''
as $function$
  select exists (select 1 from public.admin_zugang z where z.user_id = auth.uid() and z.nur_eigene)
      or exists (select 1 from public.id_gruppen g where g.verwalter_user_id = auth.uid())
      or exists (select 1 from public.id_gruppe_mitglied m
                   join public.id_gruppen g on g.id = m.gruppe_id
                  where m.user_id = auth.uid() and g.verwalter_user_id is not null)
      -- UNT0: eingeloggt, es gibt Unternehmen, aber diese ID hat keine Zeile (und ist kein Verwalter, s. oben) → nur eigene
      or (auth.uid() is not null
          and exists (select 1 from public.id_gruppen)
          and not exists (select 1 from public.id_gruppe_mitglied m where m.user_id = auth.uid()));
$function$;

-- 3) Übersicht: Beschriftung „ohne Unternehmen" (Spalten unverändert)
create or replace view public.id_gruppen_uebersicht as
 SELECT COALESCE(g.name, 'ohne Unternehmen (zuordnen)'::text) AS gruppe,
        CASE
            WHEN g.verwalter_user_id IS NULL THEN NULL::text
            ELSE COALESCE(NULLIF(v.raw_user_meta_data ->> 'name'::text, ''::text), "left"(v.id::text, 8))
        END AS verwalter,
    COALESCE(NULLIF(u.raw_user_meta_data ->> 'name'::text, ''::text), "left"(u.id::text, 8)) AS mitglied,
    u.id AS user_id,
    m.seit,
    m.notiz
   FROM auth.users u
     LEFT JOIN id_gruppe_mitglied m ON m.user_id = u.id
     LEFT JOIN id_gruppen g ON g.id = m.gruppe_id
     LEFT JOIN auth.users v ON v.id = g.verwalter_user_id
  ORDER BY (g.verwalter_user_id IS NOT NULL), (COALESCE(g.name, 'ohne Unternehmen (zuordnen)'::text)), (COALESCE(NULLIF(u.raw_user_meta_data ->> 'name'::text, ''::text), "left"(u.id::text, 8)));

-- Prüfung: jede bestehende ID hat eine Zeile (sonst verlöre sie ab jetzt ihre Sicht) — wirft und rollt alles zurück
do $$
declare n int;
begin
  select count(*) into n from auth.users u where not exists (select 1 from public.id_gruppe_mitglied m where m.user_id = u.id)
                                             and not exists (select 1 from public.id_gruppen g where g.verwalter_user_id = u.id);
  if n > 0 then
    raise exception 'UNT0: % bestehende ID(s) ohne Zeile — erst zuordnen (id_gruppen_uebersicht), dann einspielen', n;
  end if;
end $$;

commit;

-- Nachsehen (nur lesen):
-- select tgname from pg_trigger where tgrelid = 'auth.users'::regclass and not tgisinternal;      -- id_gruppe_neu_ht fehlt
-- select * from public.id_gruppen_uebersicht where gruppe like 'ohne%';                           -- erst nach einer neuen Registrierung
