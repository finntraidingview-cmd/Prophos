-- WD-FARMER: HAND-ÄNDERUNGEN AN FREMDEN KONTEN — DB-RIEGEL (02.11.2026, Slave 15)
-- Finn 02.11.2026: „Bei Hermann Technologies soll nur die Admin-ID ‚Finn + Pascal' fremde Konten ändern dürfen." und
-- „Bei Emin darf es nur Emin ändern." Mitglieder (Ahmad & Co.) und HT-Kunden ändern von Hand nichts, auch nicht am eigenen Konto.
-- Heute live (geprüft 02.11.2026): wd_tagesplan und wd_farmer_regeln haben die Policy „… angemeldet" ALL true für authenticated,
-- wd_konto_setzen prüft nur „eingeloggt" — jeder Login kann per supabase-js jede Zeile und jedes Konto ändern, die Riegel sitzen nur im
-- Browser (prophos.html wdDarf/wdNurLesen, Capture-Riegel ~16144). Der Entwurf sql/2026-10-30_wd_verwalter_riegel.sql (nie eingespielt)
-- ließ noch alle HT-Logins alles; dieser hier ersetzt ihn.
--
-- REGEL (Funktion wd_hand_recht(p_user) = darf der Login Hand-Änderungen an Konten/Zeilen der ID p_user machen?):
--   • p_user in einer Gruppe MIT Verwalter (heute nur „Emin", 5 Mitglieder inkl. Emin selbst — live belegt 02.11.2026: id_gruppe_mitglied
--     hat Emins Zeile in seiner Gruppe): nur deren Verwalter. Auch nicht die Admin-ID. Vor dem Einspielen nochmal prüfen (Probe unten).
--   • sonst (Gruppe „Hermann Technologies" ohne Verwalter, 15 IDs): nur die Admin-IDs aus admin_voll (sql/2026-10-30_admin_voll.sql,
--     heute „Finn + Pascal" und „Pascal"). Keine neue Liste — eine Zeile mehr/weniger in admin_voll, kein SQL. Offen bei Finn (Eingang
--     02.11.2026): bleibt „Pascal" drin? (delete from admin_voll … nähme ihm auch Payout-erhalten/Hedge-Freigabe.)
--   • Jede auth.users-ID steht heute in genau einer Gruppe (Trigger id_gruppe_neu_ht); eine ID ohne Gruppe fiele in den HT-Fall.
-- WO DIE REGEL GREIFT:
--   • wd_konto_setzen (WD-Haken, TP-Vorgabe, Risiko Master): nur mit wd_hand_recht(Besitzer des Kontos). Alle 6 Aufrufe sind Klicks im
--     Admin-WD-Reiter (prophos.html 68907 wdKontoHaken, 68933 wdHakenSofort, 68985 wdKontoHakenOhneZeile, 69791 wdKontoEinwuerfeln,
--     70473 wdSpeichern, 70576 Klick „Risiko Master an alle Konten" hinter wdRiskZaehlen); der PC-Tab-Takt wdTick (68447–68485) ruft keine RPC — geprüft 02.11.2026, kein Automatik-Weg.
--   • wd_tagesplan: schreiben, wenn user_id = auth.uid() (technischer Weg der PC-Tabs, siehe unten) ODER wd_hand_recht(user_id).
--     Die eigene Zeile bleibt für jeden Login schreibbar — der PC-Tab und ein Hand-Klick derselben ID sind in RLS nicht unterscheidbar.
--   • wd_farmer_regeln (EINE globale Zeile id = 1: Automatik, Zeitfenster, Vorplan, ids_aus, SCHARF, Puls-Schalter): schreiben nur Admin-IDs.
--     Eine Emin-eigene Fassung gibt es dort nicht; Emin kann sie also nicht mehr ändern (bis .1961 konnte es jeder Login).
--   • Lesen bleibt offen wie heute (Markt/PC-Tabs lesen den Tagesplan aller IDs). Policy backup_reader_select bleibt unangetastet.
--   • Railway/support_app schreiben mit dem Service-Key an RLS vorbei — unverändert (app.py /admin/wd-plaene prüft selbst).
-- PC-TABS GEHEN WEITER DURCH (geprüft gegen prophos.html .1961+): wdRegistrieren (insert mit user.id, 67982), wdRegistrierenNachziehen /
-- wdTick → wdAbgleich / tpWdTagesplanStartSetzen/-Austragen (update … eq user_id = eigener Login), alles eigene Zeile.
-- WÜRFELN UM 00:10 (wdWuerfelnSchreiben 68010, Takt 68465): rechnet deterministisch (Seed = Tag + alle offenen user_ids, die jeder Tab
-- lesen darf) und schreibt „wer zuerst schreibt". Jeder PC-Tab trifft so seine EIGENE Zeile selbst; fremde Zeilen verweigert RLS still
-- (0 Zeilen, kein Fehler). Fremde Zeilen schreiben ab jetzt nur noch Admin-Tabs (Mac/Finn + Pascal) bzw. Emin für seine Gruppe statt
-- aller HT-Tabs. Eine ID, deren PC um 00:10 aus ist, bekommt ihren Wurf beim Einschalten (eigener Tab) oder vom Admin-Tab.
-- Idempotent: Funktionen create or replace, Policies drop if exists + create. Rückbau: sql/2026-11-02_wd_riegel_nur_admin_zurueck.sql.
-- Prüfer-Pflicht (DB-Schreiblogik/RLS). Einspielen: Betrieb 1 auf Finns Wort, per apply_migration.

-- 1) Hand-Recht des Logins an der ID p_user (security definer: admin_voll hat RLS ohne Policy für authenticated, nur so lesbar)
create or replace function public.wd_hand_recht(p_user uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select case
    -- ID in einer verwalteten Gruppe (Emin & Co.): nur ihr Verwalter
    when exists (select 1 from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
                  where m.user_id = p_user and g.verwalter_user_id is not null)
      then exists (select 1 from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
                    where m.user_id = p_user and g.verwalter_user_id = auth.uid())
    -- Hermann Technologies: nur die Admin-IDs
    else exists (select 1 from public.admin_voll a where a.user_id = auth.uid())
  end;
$$;
revoke all on function public.wd_hand_recht(uuid) from public;
grant execute on function public.wd_hand_recht(uuid) to authenticated;

-- 1b) Ist der Login eine Admin-ID? (für wd_farmer_regeln; security definer wie oben)
create or replace function public.wd_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.admin_voll a where a.user_id = auth.uid());
$$;
revoke all on function public.wd_admin() from public;
grant execute on function public.wd_admin() to authenticated;

-- 2) RPC wd_konto_setzen: Hand-Recht am Besitzer des Kontos
create or replace function public.wd_konto_setzen(p_account uuid, p_wd_farm boolean default null, p_tp numeric default null, p_sl numeric default null)
returns boolean language plpgsql security definer set search_path = public as $$
declare v_owner uuid;
begin
  if auth.uid() is null then raise exception 'nicht angemeldet'; end if;
  select a.user_id into v_owner from public.accounts a where a.id = p_account;
  if v_owner is null then return false; end if;
  if not public.wd_hand_recht(v_owner) then
    raise exception 'WD-Einstellungen ändert nur die Admin-ID (HT) bzw. der Verwalter (Gruppe)' using errcode = '42501';
  end if;
  update public.accounts
     set wd_farm = coalesce(p_wd_farm, wd_farm),
         wd_tp = case when p_tp is null then wd_tp when p_tp <= 0 then null else p_tp end,
         wd_sl = case when p_sl is null then wd_sl when p_sl <= 0 then null else p_sl end
   where id = p_account;
  return found;
end $$;

-- 3) wd_tagesplan: lesen alle, schreiben eigene Zeile (PC-Tab) oder Hand-Recht
drop policy if exists "wd_tagesplan angemeldet" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan lesen" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan schreiben" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan aendern" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan loeschen" on public.wd_tagesplan;
create policy "wd_tagesplan lesen" on public.wd_tagesplan for select to authenticated using (true);
create policy "wd_tagesplan schreiben" on public.wd_tagesplan for insert to authenticated
  with check (user_id = auth.uid() or public.wd_hand_recht(user_id));
create policy "wd_tagesplan aendern" on public.wd_tagesplan for update to authenticated
  using (user_id = auth.uid() or public.wd_hand_recht(user_id))
  with check (user_id = auth.uid() or public.wd_hand_recht(user_id));
create policy "wd_tagesplan loeschen" on public.wd_tagesplan for delete to authenticated
  using (user_id = auth.uid() or public.wd_hand_recht(user_id));

-- 4) wd_farmer_regeln (globale Zeile): lesen alle, schreiben nur Admin-IDs (wd_admin() aus 1b — eine Policy läuft als der
--    anfragende Login, der admin_voll nicht lesen darf; die security-definer-Funktion darf)
drop policy if exists "wd_farmer_regeln angemeldet" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln lesen" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln ht" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln admin" on public.wd_farmer_regeln;
create policy "wd_farmer_regeln lesen" on public.wd_farmer_regeln for select to authenticated using (true);
create policy "wd_farmer_regeln admin" on public.wd_farmer_regeln for all to authenticated
  using (public.wd_admin()) with check (public.wd_admin());

-- Probe nach dem Einspielen (nur lesen):
--   select policyname, cmd, roles from pg_policies where tablename in ('wd_tagesplan','wd_farmer_regeln') order by 1;
--   select pg_get_functiondef('public.wd_konto_setzen(uuid,boolean,numeric,numeric)'::regprocedure) ilike '%wd_hand_recht%';   -- true
--   select coalesce(u.raw_user_meta_data->>'name', left(a.user_id::text, 8)) from public.admin_voll a join auth.users u on u.id = a.user_id;
--   select count(*) from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id where g.verwalter_user_id = m.user_id;   -- 1 (Emin)
