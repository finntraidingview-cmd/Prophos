-- Jacob ins Striking für Apex freischalten (Finn 23.11.2026 ~03:00 Dubai: „Jacob ist auch im Programm drin“ + Dashboard-Screenshot).
-- Apex-Dashboard PA-APEX-670805-03: Status Active, Trader Probation „only profit earned after 11/20/2026 counts toward payouts“,
-- Starting balance 110.105,82, Approved Payouts 1 (letzte Anfrage 20.11. 2.000 $, approved), 0 von 5 Trading Days.
-- Abweichung zur vorbereiteten Zeile in sql/2026-11-20_marc_apex_wieder_aktiv.sql: Probation ist laut Dashboard JA (dort stand „keine“).
-- Zyklus-Beginn wie bei Marc einen Tag NACH dem genannten Datum („after 11/20“ → Zählung ab 21.11., Korrektur 20.11. ~05:20).
-- wd_farm bleibt AUS (Striking-Konten nie wd_farm=true, sonst legt der PC-Tab-Rückfall WD-Pläne am Striking vorbei an).
-- Idempotent.

-- 1) Gate je ID (wie Marc 20.11.): addon_firma apex/striking für Jacobs ID.
insert into public.addon_firma (user_id, firma, addon, an, updated_at)
values ('368076fd-67c1-460c-aa86-38d81ae69350', 'apex', 'striking', true, now())
on conflict (user_id, firma, addon) do update set an = true, updated_at = now();

-- 2) Startwerte am Konto 100k PAAPEX6708050000003.
update public.accounts
   set striking_zyklus_start = 110105.82,
       striking_payout_nr    = 2,
       striking_probation    = true,
       striking_zyklus_seit  = '2026-11-21',
       wd_farm               = false
 where id = '7e3a65a5-73e5-4286-9458-c5a4cf12a026';

-- Rückweg: update public.addon_firma set an = false, updated_at = now()
--   where user_id = '368076fd-67c1-460c-aa86-38d81ae69350' and firma = 'apex' and addon = 'striking';
