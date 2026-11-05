-- Marco Topstep Combine 150k …24551329 (0752271a) zurück aus dem Archiv als NOVA-TESTKONTO (Finn 06.11.2026 ~04:00 Dubai, Foto TopstepX
-- „Ineligible Accounts · 150K DLL Combine 150KTC…1329 BAL $149,949.52": „Füge mir bitte den TopstepX-Account wieder hinzu … der ist schon
-- geblowt, aber den können wir zum Testen nutzen … weil er eh schon geblowt wurde und es nicht juckt, da bei Nova testen").
-- Marco ist die einzige ID mit TopstepX-Userscript. Archiv seit 28.10. (reason blown) → Eintrag entfernt.
-- auto_planer = false: kein Planer plant echte Trades auf das Testkonto; Name bekommt den Zusatz „· NOVA-TEST“ (Konto-Namensregel: Zusatz hinten).
-- Achtung Geblowt-Auge: TopstepX zeigt das Konto als „Ineligible" → eine Puls-Lesung kann es wieder archivieren (Rückweg = diese Datei).
update public.user_settings
   set value = value::jsonb - '0752271a-2d01-4c1d-bd58-ecb50cb08dd1', updated_at = now()
 where user_id = '1c96cf0f-5aa6-46c6-8073-617e083e4378' and key = 'archive'
   and value ? '0752271a-2d01-4c1d-bd58-ecb50cb08dd1';

update public.accounts
   set auto_planer = false,
       name = case when name like '%NOVA-TEST%' then name else name || ' · NOVA-TEST' end
 where id = '0752271a-2d01-4c1d-bd58-ecb50cb08dd1';
