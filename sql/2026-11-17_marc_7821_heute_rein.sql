-- Finn 17.11.2026 ~05:10 Dubai zu Marcs FundedNext 100k …7821 On Demand (27f94392): „ne plan es für heute direkt mit rein“.
-- Das Konto hat heute einen Pause-Tag (Handels-Würfel funded_cfd 99,5 ≥ 85). Ausnahme TW4 nur für DIESES Konto an diesem Tag (konto_id-Zeile, wie
-- caa8c405 am 16.11.) → der Funded-CFD-Takt plant es mit OD2 (On-Demand-Ziel 4.901,40 $, Tagesdeckel ~1.863 $). Idempotent.

insert into public.planer_wuerfel_ausnahme (user_id, firma, konto_id, tag, angelegt_von)
select '6c206a34-c4a7-4352-8097-bb17366bcea1', null, '27f94392-6d8d-4ccf-92a0-9edf5c008aad', date '2026-11-17',
       'Master SQL (Finn 17.11.2026: Marc …7821 heute trotz Pause-Tag planen)'
where not exists (select 1 from public.planer_wuerfel_ausnahme
                   where konto_id = '27f94392-6d8d-4ccf-92a0-9edf5c008aad' and tag = date '2026-11-17');
