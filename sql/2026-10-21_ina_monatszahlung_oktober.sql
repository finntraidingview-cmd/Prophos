-- Ina: Monatszahlung Oktober fehlte (Finn 21.10.2026 ~23:00 Dubai: „dann füg die einfach hinzu"). Gebucht waren nur 28.09. (Rechnung #1)
-- und 02.11. (vorab, 13.10. angelegt); die Dauerbuchung am 2. stand am 02.10. noch nicht → Oktober nachtragen, 500 € am 02.10.2026.
insert into transactions (user_id, kind, amount, currency, occurred_at, notes, auto_generated)
select 'd1f5bcae-2129-49a4-8415-915ab6474a64', 'manual', -500, 'EUR', '2026-10-02', 'Monatliche Kundenzahlung', false
 where not exists (select 1 from transactions where user_id = 'd1f5bcae-2129-49a4-8415-915ab6474a64' and kind = 'manual' and amount = -500 and occurred_at = '2026-10-02');
