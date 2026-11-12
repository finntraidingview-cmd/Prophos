-- Marc Topstep 150k …22631094 zurückholen (Finn 12.11.2026 ~20:00 Dubai, Screenshot TopstepX: „150KTC-SKU-V2-DLL-697339-22631094 · $152,352.20 ·
-- active · Evaluation“ — „der Account lebt bei Marc noch … archiviert“). Das Konto wurde am 11.11. 03:04 UTC als „blown“ archiviert, Balance auf 0
-- gesetzt, und Plan 109bf70d (11.11., −1.628 $) wurde blown=true markiert. Puls hatte aber um 01:03 UTC nach dem Trade 152.352,20 $ gelesen
-- (tv_balance, Quelle puls): Der Verlust-Trade hat das Konto nicht geblowt.
-- Was passiert: (1) Archiv-Eintrag in ALLEN Profilen entfernen (wie /account/entarchivieren, sonst löscht der Archiv-Sweep neue Pläne), (2) Plan
-- 109bf70d blown=false, (3) balance = gelesene tv_balance, (4) Puls um eine frische Balance-Lesung bitten (konto_balance, wie „↻ Balance lesen“).
-- Idempotent.

begin;

update public.user_settings
   set value = value - '57750c95-b096-4716-a85b-db96419253c1', updated_at = now()
 where key = 'archive' and value ? '57750c95-b096-4716-a85b-db96419253c1';

update public.trade_plans set blown = false, updated_at = now()
 where id::text like '109bf70d%' and master_account_id = '57750c95-b096-4716-a85b-db96419253c1' and blown;

update public.accounts set balance = 152352.20, updated_at = now()
 where id = '57750c95-b096-4716-a85b-db96419253c1' and coalesce(balance, 0) = 0;

insert into public.order_signale (user_id, plan_id, status, params)
select '6c206a34-c4a7-4352-8097-bb17366bcea1', 'konto:57750c95-b096-4716-a85b-db96419253c1', 'wartet',
       jsonb_build_object('account_id', '57750c95-b096-4716-a85b-db96419253c1', 'external_id', '150KTC-SKU-V2-DLL-697339-22631094',
                          'firm', 'Topstep', 'name', '150k 150KTC-SKU-V2-DLL-697339-22631094 → Challenge', 'von', 'admin', 'aktion', 'konto_balance')
 where not exists (select 1 from public.order_signale where plan_id = 'konto:57750c95-b096-4716-a85b-db96419253c1' and status = 'wartet');

commit;
