-- MARC: WD APEX 150k …0001 — HEDGE-LOTS VON 32,00 AUF 3,20 KORRIGIERT (22.10.2026 ~16:45 Dubai, Finn: „ungefähr 3 Lot erwartet")
-- Plan 842453ce (MNQZ6, 3 Kt, TP 386 $, Risiko Master 386 $, Staffel 175 €) trug multiplier 10,6675 → 32,00 Lot BUY. Gerechnet mit
-- 20 $/Pkt (NQ) statt 2 $/Pkt (MNQ): 386 $ ÷ (2 × 3) = 64,33 Pkt → 175 € ÷ (0,85 €/Pkt × 64,33) = 3,20 Lot = 1,0667 je Kontrakt.
-- Der Start-Check (Fusion-Marge) sah 32 Lot und hielt den Auto-Start an. Code-Fix in .1712 (wdFarmHedge + fusionHedgeLots nach
-- Plan-Symbol); diese Datei korrigiert nur den schon angelegten Plan. hedge_eur (174,99 € am TP) und Risiko-Werte bleiben, sie stimmten.
-- Angewendet 22.10.2026 direkt gegen die DB.
update public.trade_plans
   set multiplier = 1.0667,
       hedge_faktor = 1.067
 where id = '842453ce-b91c-46d9-aa0b-c901927c9f53'
   and status = 'planned'
   and started_at is null
   and master_symbol like 'MNQ%'
   and multiplier = 10.6675;
