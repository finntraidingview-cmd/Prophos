-- TP1 (05.11.2026, Amirs erster Futures-Start über Orbit Prio 2, Plan cdb03c77 FundedNext Futures 50k, 15:19 UTC): PC pc-i8vyq8 (Amir) stand
-- NICHT in wd_farmer_regeln.puls_augen_cdp → der Order-Bot nahm den alten UIA-Weg im normalen Chrome. Dort zeigte TradingView das TP-Feld als
-- „Take profit price" und dieser Weg kennt keine $-Umstellung (nur der CDP-Weg über das Puls-Chrome, seit 14.10.2026) → „'Take profit price'
-- steht nicht auf $", sauberer Abbruch, nichts platziert. Mit diesem Eintrag läuft pc-i8vyq8 wie die übrigen 17 Orbit-PCs über das Puls-Chrome.
-- Voraussetzung: Puls-Chrome dort eingerichtet (Userscript 0.10.9 meldet von pc-i8vyq8). Nur puls_augen_cdp — Amir hat kein Topstep.
-- Idempotent. NICHT eingespielt — nur auf Finns Wort (Master).

update public.wd_farmer_regeln
   set puls_augen_cdp = array_append(puls_augen_cdp, 'pc-i8vyq8'), updated_at = now()
 where id = 1 and not ('pc-i8vyq8' = any(coalesce(puls_augen_cdp, '{}')));

-- Kontrolle:
-- select 'pc-i8vyq8' = any(puls_augen_cdp) as drin, array_length(puls_augen_cdp, 1) as n from public.wd_farmer_regeln where id = 1;

-- Rückbau:
-- update public.wd_farmer_regeln set puls_augen_cdp = array_remove(puls_augen_cdp, 'pc-i8vyq8'), updated_at = now() where id = 1;
