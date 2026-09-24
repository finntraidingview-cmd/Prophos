-- 2026-09-25 · Winning Days ohne Stop Loss
--
-- Finn (verbindliche Regel): „Bei Winning Days ist NIE ein Stop Loss drin. Wir geben beim Planen nur einen Take Profit an."
-- Bis .560 schrieben Popup 1 (Risiko Master = SL) und der Winning-Day-Farmer (sl_vorgabe / wd_sl) den Wert zusätzlich nach
-- master_sl — Puls setzte damit einen echten SL in TradingView, der Fusion-Hedge bekam ein zweites Level am Master-SL.
-- Ab .561 speichert das Frontend bei Winning Days master_sl immer NULL; Risiko Master bleibt nur in master_risk (Lot-Rechnung).
-- Diese Einmal-Bereinigung nimmt den SL von allen noch GEPLANTEN Winning-Day-Plänen. Laufende/abgeschlossene bleiben unberührt.
-- Stand beim Anwenden (25.09.2026): 0 Zeilen betroffen (26dc77f7 existierte nicht mehr).

update public.trade_plans
   set master_sl = null
 where status = 'planned'
   and route = 'tvv2'
   and master_sl is not null
   and (hedge_eur > 0
        or notes = 'Winning-Day-Farmer'
        or master_account_id in (select id from public.accounts where account_type = 'winning_days'));
