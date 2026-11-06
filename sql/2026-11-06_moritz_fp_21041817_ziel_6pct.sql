-- Moritz FundingPips 100k …21041817 (b1d6c326), Phase 2: Ziel 6 % = 106.000 statt 5 % = 105.000 (Finn 06.11.2026 ~04:15 Dubai, Foto Accounts
-- Moritz → FundingPips: „der hat ein 6.000-$-Take-Profit-Target … da fehlen noch 800 $ … neu planen, dass wir die restlichen machen, aber der ist noch
-- nicht gepasst"). Wie Mike FP …5253 (03.11.2026, feedback-konto-ziel-nachpruefen): Konto-Wert ziel_pct_konto geht vor Firmen-/Größen-Regel.
-- Stand vorher: ziel_usd 105000, ziel_erreicht_at 04.11. 12:05 Dubai (→ Review), Balance 105.273,54 → Rest 726,46 $.
-- ziel_erreicht_at = null holt das Konto aus „Ziel erreicht/Review“ zurück, der Auto-Planer plant den Rest.
update public.accounts
   set ziel_pct_konto = coalesce(ziel_pct_konto, '{}'::jsonb) || '{"phase2": 6}'::jsonb,
       ziel_usd = 106000,
       ziel_erreicht_at = null
 where id = 'b1d6c326-c535-4ac5-bd3c-782a83dbaeb0';
