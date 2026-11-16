-- PC von Artur (pc-dw1dko, ID in Emins Gruppe): Puls-Chrome (CDP, Port 9333, %LOCALAPPDATA%\Prophos\puls-chrome) am 17.11.2026 eingerichtet
-- (Finn: order_bot.py + puls-chrome-starten.bat nachgeladen, TradingView/Tradovate/Tampermonkey im Puls-Chrome). Puls ging trotzdem ins
-- normale Chrome, weil der PC in keiner Puls-Liste stand → wie Simon 21.10.2026 (sql/2026-10-21_puls_cdp_simon_pc.sql) beide Listen setzen
-- (puls_augen_cdp für TradingView, puls_topstep_pcs für den Topstep-Weg, sonst UIA-Rückfall ins Haupt-Chrome). Idempotent.
update public.wd_farmer_regeln
   set puls_augen_cdp = array_append(puls_augen_cdp, 'pc-dw1dko'), updated_at = now()
 where id = 1 and not ('pc-dw1dko' = any(coalesce(puls_augen_cdp, '{}')));

update public.wd_farmer_regeln
   set puls_topstep_pcs = array_append(puls_topstep_pcs, 'pc-dw1dko'), updated_at = now()
 where id = 1 and not ('pc-dw1dko' = any(coalesce(puls_topstep_pcs, '{}')));
