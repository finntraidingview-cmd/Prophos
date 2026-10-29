-- WD-FARMER: VERWALTER BEARBEITET SEINE GRUPPE — DB-RIEGEL (30.10.2026, Slave 7; Finn als Emin: „Der soll ja ändern können.")
-- Bisher prüfte nur der Browser (wdDarf), ob ein eingeschränkter Login (Gruppen-Verwalter, Mitglied einer Verwalter-Gruppe,
-- admin_zugang „nur eigene") eine fremde ID beschreibt: wd_konto_setzen prüfte nur „eingeloggt", wd_tagesplan und wd_farmer_regeln
-- hatten RLS ALL true. Jetzt in der DB, nach demselben Muster wie id_wallets/kasse_entries (admin_nur_eigene + admin_sichtbare_ids):
--   • HT-Logins (nicht eingeschränkt): unverändert alles.
--   • Verwalter (Emin): nur Konten/Zeilen seiner Gruppe inkl. sich selbst.
--   • Mitglied ohne eigenen Code / „nur eigene": nur die eigene ID (wie sein PC-Tab heute schreibt).
--   • wd_farmer_regeln (Automatik, Zeitfenster, Firmen-Regeln, ids_aus, SCHARF): schreiben nur HT.
-- Lesen bleibt offen (Markt/PC-Tabs lesen den Tagesplan aller IDs, gefiltert wird in der Anzeige). Railway schreibt mit dem Service-Key
-- (an RLS vorbei) und prüft selbst (/admin/wd-plaene). Einspielen: Master.
-- PC-TABS BLEIBEN DRIN (Master 30.10.2026, geprüft): wdRegistrieren (Insert mit eigener user_id), wdTick → wdAbgleich (nur Zeilen
-- eq user_id = eigener Login), tpWdTagesplanStartSetzen/-Austragen (dito) — die eigene ID liegt für JEDE Rolle in admin_sichtbare_ids()
-- (union auth.uid()): HT-Kunde (nicht eingeschränkt), Verwalter Emin, Mitglieder (Ahmad & Co.), „nur eigene"-Code. Die Automatik um 00:10
-- (wdWuerfelnSchreiben) rechnet deterministisch und schreibt „wer zuerst schreibt" — einem Mitglied-Tab verweigert RLS fremde Zeilen
-- still (0 Zeilen, kein Fehler), die schreiben HT-Tabs/Mac. Kein PC-Tab ruft wd_konto_setzen oder schreibt wd_farmer_regeln; Puls
-- (order_bot.py) liest Regeln nur über Railway, support_app.py schreibt mit Service-Key. Keine DB-Funktion/kein Trigger fasst die Tabellen an.
-- Stand live 30.10.: 17 IDs im Tagesplan (3 Tage), davon 5 in der Verwalter-Gruppe, 1 mit „nur eigene"-Code.

-- 1) RPC wd_konto_setzen: Besitz prüfen
create or replace function public.wd_konto_setzen(p_account uuid, p_wd_farm boolean default null, p_tp numeric default null, p_sl numeric default null)
returns boolean language plpgsql security definer set search_path = public as $$
declare v_owner uuid;
begin
  if auth.uid() is null then raise exception 'nicht angemeldet'; end if;
  select a.user_id into v_owner from public.accounts a where a.id = p_account;
  if v_owner is null then return false; end if;
  if public.admin_nur_eigene() and v_owner not in (select s from public.admin_sichtbare_ids() s) then
    raise exception 'Nur Konten der eigenen Gruppe' using errcode = '42501';
  end if;
  update public.accounts
     set wd_farm = coalesce(p_wd_farm, wd_farm),
         wd_tp = case when p_tp is null then wd_tp when p_tp <= 0 then null else p_tp end,
         wd_sl = case when p_sl is null then wd_sl when p_sl <= 0 then null else p_sl end
   where id = p_account;
  return found;
end $$;

-- 2) wd_tagesplan: lesen alle, schreiben HT oder eigene Sicht
drop policy if exists "wd_tagesplan angemeldet" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan lesen" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan schreiben" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan aendern" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan loeschen" on public.wd_tagesplan;
create policy "wd_tagesplan lesen" on public.wd_tagesplan for select to authenticated using (true);
create policy "wd_tagesplan schreiben" on public.wd_tagesplan for insert to authenticated
  with check ((not (select public.admin_nur_eigene())) or user_id in (select s from public.admin_sichtbare_ids() s));
create policy "wd_tagesplan aendern" on public.wd_tagesplan for update to authenticated
  using ((not (select public.admin_nur_eigene())) or user_id in (select s from public.admin_sichtbare_ids() s))
  with check ((not (select public.admin_nur_eigene())) or user_id in (select s from public.admin_sichtbare_ids() s));
create policy "wd_tagesplan loeschen" on public.wd_tagesplan for delete to authenticated
  using ((not (select public.admin_nur_eigene())) or user_id in (select s from public.admin_sichtbare_ids() s));

-- 3) wd_farmer_regeln: lesen alle, schreiben nur HT
drop policy if exists "wd_farmer_regeln angemeldet" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln lesen" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln ht" on public.wd_farmer_regeln;
create policy "wd_farmer_regeln lesen" on public.wd_farmer_regeln for select to authenticated using (true);
create policy "wd_farmer_regeln ht" on public.wd_farmer_regeln for all to authenticated
  using (not (select public.admin_nur_eigene())) with check (not (select public.admin_nur_eigene()));

-- Probe nach dem Einspielen (nur lesen):
--   select policyname, cmd from pg_policies where tablename in ('wd_tagesplan','wd_farmer_regeln') order by 1;
--   select pg_get_functiondef('public.wd_konto_setzen(uuid,boolean,numeric,numeric)'::regprocedure) ilike '%admin_sichtbare_ids%';
