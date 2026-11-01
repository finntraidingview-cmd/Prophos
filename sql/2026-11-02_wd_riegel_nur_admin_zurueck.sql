-- RÜCKBAU zu sql/2026-11-02_wd_riegel_nur_admin.sql (02.11.2026, Slave 15): stellt den Stand vor dem Riegel wieder her, wie er am
-- 02.11.2026 live gelesen wurde — Policies „wd_tagesplan angemeldet" / „wd_farmer_regeln angemeldet" ALL true für authenticated und
-- wd_konto_setzen ohne Besitz-Riegel (Wortlaut aus pg_get_functiondef). backup_reader_select bleibt unangetastet, admin_voll bleibt.
-- Idempotent. Einspielen nur auf Finns Wort (Betrieb 1).

-- 1) wd_konto_setzen wie vorher: nur „eingeloggt"
create or replace function public.wd_konto_setzen(p_account uuid, p_wd_farm boolean default null, p_tp numeric default null, p_sl numeric default null)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'nicht angemeldet'; end if;
  update public.accounts
     set wd_farm = coalesce(p_wd_farm, wd_farm),
         wd_tp = case when p_tp is null then wd_tp when p_tp <= 0 then null else p_tp end,
         wd_sl = case when p_sl is null then wd_sl when p_sl <= 0 then null else p_sl end
   where id = p_account;
  return found;
end $$;

-- 2) wd_tagesplan: wieder eine Policy ALL true
drop policy if exists "wd_tagesplan lesen" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan schreiben" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan aendern" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan loeschen" on public.wd_tagesplan;
drop policy if exists "wd_tagesplan angemeldet" on public.wd_tagesplan;
create policy "wd_tagesplan angemeldet" on public.wd_tagesplan for all to authenticated using (true) with check (true);

-- 3) wd_farmer_regeln: wieder eine Policy ALL true
drop policy if exists "wd_farmer_regeln lesen" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln ht" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln admin" on public.wd_farmer_regeln;
drop policy if exists "wd_farmer_regeln angemeldet" on public.wd_farmer_regeln;
create policy "wd_farmer_regeln angemeldet" on public.wd_farmer_regeln for all to authenticated using (true) with check (true);

-- 4) Hilfsfunktionen weg (nichts anderes nutzt sie)
drop function if exists public.wd_admin();
drop function if exists public.wd_hand_recht(uuid);

-- Probe: select policyname, cmd from pg_policies where tablename in ('wd_tagesplan','wd_farmer_regeln') order by 1;
