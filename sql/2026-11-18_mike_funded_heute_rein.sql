-- Finn 18.11.2026 ~04:00 Dubai (Screenshot Funded Planer → „Heute nicht drin“): „mike bitte heute mitplanen“.
-- Mike: Lucid 150k LFF…0001 + LFF…0002 (Pause-Tag Firma, Firmen-Würfel 90 %) und Apex 100k PAAPEX…0006 (Pause-Tag Handels-Würfel 85 %).
-- Würfel-Ausnahme je Konto nur für heute (wie Marc …7821 am 17.11.) → der Funded-Planer plant sie im nächsten Takt. Idempotent.
insert into public.planer_wuerfel_ausnahme (user_id, firma, konto_id, tag, angelegt_von)
select '32b854d1-866f-4e7e-ba0b-9bf63df2d993', null, k.id, date '2026-11-18', 'Master SQL (Finn 18.11.2026: Mike Funded heute mitplanen)'
from (values ('66baa785-1f56-44e7-824b-0e9002919d54'::uuid), ('2e8f9c58-53cc-43e9-ac48-78dbb414d680'::uuid),
             ('88df28b8-ff24-438a-bcac-920259195020'::uuid)) as k(id)
where not exists (select 1 from public.planer_wuerfel_ausnahme x where x.konto_id = k.id and x.tag = date '2026-11-18');
