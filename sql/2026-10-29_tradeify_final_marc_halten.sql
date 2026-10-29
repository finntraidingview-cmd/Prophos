-- Tradeify-Final-Trade Marc …127231 heute NICHT starten (Finn 29.10.2026 ~17:20 Dubai: „Für alle Tradeify-Trades, die heute geplant sind
-- und auf 157.000 sind, bitte heute nicht starten … beim finalen Trade wollen wir das mit Gegenhedge machen, da muss erst die Logik gebaut
-- werden … die verfallen dann nicht"). Einziger betroffener Plan: 880b8b11 (Stand 157.021,20 $, TP +2.039 $ → Ziel 159k), Start war
-- 16:09 Dubai, noch nicht gestartet. Plan bleibt erhalten: Start auf morgen 16:09 Dubai verschoben, hand_werte_at gesetzt, damit
-- Planer/Railway ihn nicht umschreiben. Rücknahme: start_um auf den gewünschten Zeitpunkt, hand_werte_at = null.
update public.trade_plans
   set start_um = start_um + interval '1 day', hand_werte_at = now(), updated_at = now()
 where id = '880b8b11-0226-430d-9ce6-7675b951314f' and status = 'planned' and start_um_gestartet_at is null;
