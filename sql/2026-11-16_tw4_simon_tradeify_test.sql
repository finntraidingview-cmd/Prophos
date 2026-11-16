-- TW4-Ausnahme je Konto (Finn 16.11.2026 ~05:35 Dubai: Testtrade Pump in zwei Trades auf Simons zweitem Tradeify-Funded).
-- 150k FTDFYSLX150373284577 → Funded stand heute auf „Pause-Tag (Handels-Würfel 75 %)“. Nur dieses Konto, nur heute (Plan-Tag 16.11.).
-- Der Pump-Weg ist fest gewürfelt (fdp_pump_tag_wurf): für dieses Konto heute „zwei“ (14,5 < 30 % Zwei-Trade-Anteil).
insert into public.planer_wuerfel_ausnahme (user_id, konto_id, tag, angelegt_von)
select a.user_id, a.id, '2026-11-16', 'Master SQL (Finn 16.11.2026, Tradeify-Test zwei Trades)'
from public.accounts a where a.id = 'caa8c405-9461-4680-88fa-142ae7bd1800'
on conflict do nothing;
