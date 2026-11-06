-- TESTKONTEN OHNE GEBLOWT-AUGE (NV1 §4b, Finn 06.11.2026): Nova-Testkonto Marco Topstep Combine 150k …24551329 (Konto 0752271a, „· NOVA-TEST")
-- ist in TopstepX „Ineligible" und wurde vom Geblowt-Auge (prophos.html tsxGeblowtKonto) bei jeder Lesung wieder als 'blown' archiviert
-- (zuletzt 06.11.2026 03:59:52 nach Plan adc10fd9). Konto-IDs in dieser Liste archiviert der PC-Tab nicht und setzt ihre Pläne nicht blown;
-- der Bot liest und meldet unverändert. Eigene Spalte statt vorplan (das Speichern der Hedge-Tabelle baut vorplan neu). Idempotent.
-- Rücknahme: update public.wd_farmer_regeln set tsx_test_konten = '{}' where id = 1;
alter table public.wd_farmer_regeln add column if not exists tsx_test_konten text[] not null default '{}';
update public.wd_farmer_regeln
   set tsx_test_konten = (select coalesce(array_agg(distinct x), '{}') from unnest(coalesce(tsx_test_konten, '{}') || (
         select array_agg(id::text) from public.accounts
          where id = '0752271a-2d01-4c1d-bd58-ecb50cb08dd1' and external_id = '150KTC-SKU-V2-DLL-696284-24551329')) x)
 where id = 1;
-- Prüfung danach (muss die volle ID 0752271a-2d01-4c1d-bd58-ecb50cb08dd1 zeigen; leer = Konto-ID/External ID passte nicht):
select tsx_test_konten from public.wd_farmer_regeln where id = 1;
