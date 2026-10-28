-- Funded-Planer: Startzeiten nach „Alle 7 bestätigen" auseinandergezogen (28.10.2026, EINGESPIELT 06:39:59 UTC = 10:39:59 Dubai).
-- Vorfall: vier Vorschläge mit schon vergangener Zeit bekamen beim Bestätigen alle „jetzt + 2 min" (fdp_start_bestaetigt) → vier
-- Apex-Big-Trades um 10:39–10:40 Dubai, zwei davon Chris. Chris …0003 (76330365) startete wie geplant, die drei anderen hier verschoben —
-- ≥ 15 min je Firma, ≥ 90 min je ID, nur solange ungestartet. Ursache behoben in app.py fdp_start_verteilen.
update trade_plans t set start_um = v.neu::timestamptz
from (values ('a37fcf6f-83cb-4830-90b6-fe3e7396cbb4','2026-10-28 06:58:17+00'),   -- Ina 100k …0005
             ('d53294a0-95f6-49d1-93de-876111e85bc4','2026-10-28 07:41:08+00'),   -- Marc 150k …0002
             ('8e56c8c0-77dd-429e-8596-73b9b8ab3bce','2026-10-28 08:22:43+00')) v(id, neu)   -- Chris 100k …0006
where t.id = v.id::uuid and t.status = 'planned' and t.start_um_gestartet_at is null and t.started_at is null
returning t.id, t.master_name, t.start_um;
