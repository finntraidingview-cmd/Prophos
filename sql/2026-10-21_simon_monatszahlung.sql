-- Simon: Monatszahlung an den Kunden 500 € wie bei Chris (16.), Mike (21.), Ina (2.) — Finn 21.10.2026 ~22:10 Dubai: „bei Simon gab es das noch nicht,
-- zum ersten Mal vor zwei Tagen geschickt". Erste Zahlung 19.10.2026 als Buchung, danach monatlich am 19. über die Dauerbuchung (Railway wb_loop).
insert into transactions (user_id, kind, amount, currency, occurred_at, notes, auto_generated)
select '5409e926-09bc-4789-9c99-f8584d87a89a', 'manual', -500, 'EUR', '2026-10-19', 'Monatszahlung Kunde · Zahlung #1', false
 where not exists (select 1 from transactions where user_id = '5409e926-09bc-4789-9c99-f8584d87a89a' and kind = 'manual' and amount = -500 and occurred_at = '2026-10-19');

insert into wiederkehrende_buchungen (user_id, kind, amount, currency, notes, tag_im_monat, naechste_am, letzte_am, aktiv)
select '5409e926-09bc-4789-9c99-f8584d87a89a', 'manual', -500, 'EUR', 'Monatszahlung Kunde', 19, '2026-11-19', '2026-10-19', true
 where not exists (select 1 from wiederkehrende_buchungen where user_id = '5409e926-09bc-4789-9c99-f8584d87a89a' and aktiv and amount = -500);
