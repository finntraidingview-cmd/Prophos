-- FUNDINGPIPS-BULK-VORLAGE AUF STANDARD (26.10.2026, Master/Slave 3, Anlass: Jacobs FundingPips 100k Phase 1 vom 16.10.2026).
-- Die Bulk-Vorlage „FundingPips 100k Phase 1" trägt Flex-Werte: max_drawdown 12.000 (12 %), max_daily_drawdown 4.000,
-- max_loss_per_trade 4.000. Gespeichert wurde sie am 03.10.2026 16:14:24, sechs Sekunden vor dem Anlegen von Jacobs echtem
-- Flex-Konto (100k Phase 1, 03.10.2026 16:14:30). Jedes Konto aus dieser Vorlage ist für den Planer deshalb Flex
-- (ap_konto_flex: max_drawdown ≥ 12 % der Größe): Ziel 110.000, Boden 88.000, SL-Spanne Flex. Gemeint ist aber Standard:
-- FundingPips-Dashboard Boden 90.000 = 10 %, Daily 3 % der Tagesstart-Equity.
-- Folge am 23.10.2026: Bei Jacob …6924 riss der Daily Loss (SL 2.948 > 3 % × 96.463 = 2.894), …6925 fiel unter den Boden 90.000
-- (SL 2.754 bei nur 1.535 $ Luft).
-- Neu: dieselben Werte wie die aktiven Standard-Konten von Chris/Mike (100k: max_drawdown 10.000, Daily und Max-Loss je Trade leer).
-- Damit plant der Planer Ziel 108.000, Boden 90.000, SL Standard-Spanne. Größe/Startbalance 100.000 bleiben stehen.
--
-- Konten: Aus der Vorlage entstanden und noch aktiv sind in Hermann Technologies nur Jacobs …6924/…6925. Beide sind geblowt und werden
-- archiviert, deshalb NICHT umgestellt (Master 26.10.2026). Alle anderen aktiven HT-FundingPips-100k-Konten stehen schon auf 10.000.
-- Konten anderer Gruppen fasst diese Datei nicht an.
--
-- Nur Daten, kein Code. Wiederholbar: greift nur, solange die alten Flex-Werte drinstehen.

update public.bulk_vorlagen
   set max_drawdown       = 10000,
       max_daily_drawdown = null,
       max_loss_per_trade = null,
       updated_at         = now()
 where id = 'eadce0de-65a7-46a3-b948-f19c0cd51bc7'          -- „FundingPips 100k Phase 1"
   and max_drawdown = 12000;

-- Prüfen:
-- select name, account_size, starting_balance, max_drawdown, max_daily_drawdown, max_loss_per_trade, updated_at
--   from bulk_vorlagen where id = 'eadce0de-65a7-46a3-b948-f19c0cd51bc7';
--
-- Rückbau (alter Stand vor dieser Datei):
-- update public.bulk_vorlagen
--    set max_drawdown = 12000, max_daily_drawdown = 4000, max_loss_per_trade = 4000, updated_at = now()
--  where id = 'eadce0de-65a7-46a3-b948-f19c0cd51bc7';
