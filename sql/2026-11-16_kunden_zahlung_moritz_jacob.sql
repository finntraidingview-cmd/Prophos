-- Moritz + Jacob Schwarzmann: Monatszahlung Kunde 375 €/Monat (Treuhand v5, ab 01.08.2026) fehlte in den Dauerbuchungen
-- und im Sheet „Kundenzahlungen am 1.“ (Befund Slave 8 beim Kundendaten-Aufräumen). Finn 16.11.2026: „ja hinzufügen“.
-- Wie die übrigen Kunden (Simon/Chris/Mike/Ina, sql/2026-11-01_kunden_zahltag_erster.sql): Zahltag am 1., nächste Fälligkeit 01.12.2026.
-- Rückstände Aug–Nov sind hier NICHT gebucht (offene Frage an Finn). Idempotent: nur anlegen, wenn noch keine aktive Kundenzahlung der ID existiert.
insert into public.wiederkehrende_buchungen (user_id, kind, amount, currency, notes, tag_im_monat, naechste_am, aktiv)
select v.uid, 'manual', -375.00, 'EUR', 'Monatszahlung Kunde', 1, date '2026-12-01', true
from (values ('aff98e60-e9a0-4821-9d1d-31634571a2f4'::uuid),   -- Moritz
             ('368076fd-67c1-460c-aa86-38d81ae69350'::uuid))   -- Jacob
     as v(uid)
where not exists (select 1 from public.wiederkehrende_buchungen w
                  where w.user_id = v.uid and w.aktiv and w.notes ilike 'Monats%zahlung%Kunde%');

-- Nachtrag (Finn 16.11.2026 „ja, das stimmt“): Aug–Nov 2026 sind noch offen → je eine Einzelbuchung 4 × 375 € = 1.500 € heute,
-- damit der P&L der IDs stimmt. Überweisen tut Finn selbst. Idempotent über die Notiz.
insert into public.transactions (user_id, kind, amount, currency, occurred_at, notes, auto_generated)
select v.uid, 'manual', -1500.00, 'EUR', date '2026-11-16', 'Monatszahlung Kunde · Rückstand Aug–Nov 2026 (4 × 375 €)', false
from (values ('aff98e60-e9a0-4821-9d1d-31634571a2f4'::uuid), ('368076fd-67c1-460c-aa86-38d81ae69350'::uuid)) as v(uid)
where not exists (select 1 from public.transactions t where t.user_id = v.uid and t.notes = 'Monatszahlung Kunde · Rückstand Aug–Nov 2026 (4 × 375 €)');
