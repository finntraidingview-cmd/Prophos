-- Meta Wallet + Kasse für IDs mit eigenem Admin-Zugang (27.09.2026, Finn nach Screenshot von
-- Emins Admin → Meta Wallet mit Pascal/EzPoker/Aurel/Moritz: „da soll nur seine sein").
-- Die Wallet-Tabellen und kasse_entries liest das Frontend direkt (RLS „true" für alle
-- Angemeldeten) — die Backend-Grenze aus 2026-09-27_admin_zugang.sql greift dort nicht.
-- Lösung: RESTRICTIVE-Policies, die nur für IDs in admin_zugang (nur_eigene) etwas ändern;
-- für alle anderen bleibt es exakt wie bisher (die permissiven Policies bleiben stehen).

create or replace function public.admin_nur_eigene()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.admin_zugang z
                  where z.user_id = auth.uid() and z.nur_eigene);
$$;
revoke all on function public.admin_nur_eigene() from public;
grant execute on function public.admin_nur_eigene() to authenticated;

-- Wallets: nur die eigenen (person_uid ist text)
drop policy if exists nur_eigene_wallets on public.id_wallets;
create policy nur_eigene_wallets on public.id_wallets as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene()) or person_uid = (select auth.uid())::text)
  with check (not (select public.admin_nur_eigene()) or person_uid = (select auth.uid())::text);

-- Tagesstände + Transaktionen: nur an eigenen Wallets
drop policy if exists nur_eigene_snapshots on public.wallet_snapshots;
create policy nur_eigene_snapshots on public.wallet_snapshots as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w where w.person_uid = (select auth.uid())::text))
  with check (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w where w.person_uid = (select auth.uid())::text));

drop policy if exists nur_eigene_wallet_tx on public.wallet_tx;
create policy nur_eigene_wallet_tx on public.wallet_tx as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w where w.person_uid = (select auth.uid())::text))
  with check (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w where w.person_uid = (select auth.uid())::text));

-- Adress-Labels (gemeinsame Liste über alle Wallets) und Kasse (Finn/Pascal): gar nicht
drop policy if exists nur_eigene_wallet_labels on public.wallet_labels;
create policy nur_eigene_wallet_labels on public.wallet_labels as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene()))
  with check (not (select public.admin_nur_eigene()));

drop policy if exists nur_eigene_kasse on public.kasse_entries;
create policy nur_eigene_kasse on public.kasse_entries as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene()))
  with check (not (select public.admin_nur_eigene()));
