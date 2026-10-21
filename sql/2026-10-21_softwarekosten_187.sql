-- Softwarekosten 187 € monatlich am 1. je ID (Finn 21.10.2026 ~22:15 Dubai: „bei jeder einzelnen ID immer zum Ersten automatisch monthly mit der
-- Beschreibung ‚Softwarekosten' 187 €" — „alle außer Finn + Pascal und Pascal"). Hermann-Technologies-IDs mit Trading; nicht: Finn + Pascal, Pascal,
-- Finn (archiviert), Test, moritzczehak (keine Trades), Gruppe Emin. Erste Buchung 01.11.2026 über Railway wb_loop (keine Rückbuchung).
insert into wiederkehrende_buchungen (user_id, kind, amount, currency, notes, tag_im_monat, naechste_am, letzte_am, aktiv)
select u.id, 'manual', -187, 'EUR', 'Softwarekosten', 1, '2026-11-01', null, true
  from (values ('13905525-69d0-4949-b081-efdbc397e888'::uuid),   -- Aurel
               ('7b1bc9a3-94d3-4603-a232-c10fc2df3262'::uuid),   -- Chris
               ('8ad6a2f1-816e-4229-85cd-03a9c693bb71'::uuid),   -- EzPoker
               ('d1f5bcae-2129-49a4-8415-915ab6474a64'::uuid),   -- Ina
               ('368076fd-67c1-460c-aa86-38d81ae69350'::uuid),   -- Jacob
               ('6c206a34-c4a7-4352-8097-bb17366bcea1'::uuid),   -- Marc
               ('1c96cf0f-5aa6-46c6-8073-617e083e4378'::uuid),   -- Marco
               ('32b854d1-866f-4e7e-ba0b-9bf63df2d993'::uuid),   -- Mike
               ('aff98e60-e9a0-4821-9d1d-31634571a2f4'::uuid),   -- Moritz
               ('5409e926-09bc-4789-9c99-f8584d87a89a'::uuid))   -- Simon
       as u(id)
 where not exists (select 1 from wiederkehrende_buchungen w where w.user_id = u.id and w.aktiv and w.notes = 'Softwarekosten');
