-- ZIEL ZURÜCK (03.11.2026, Finn — FundingPips 50k Flex Phase 2, Konto a956a1a8-549c-45ed-a34c-43acd84fedf1, ziel_pct_konto {"phase2": 8}):
-- die Ziel-Wache rechnete 52.500 (Flex-50k-Block phase2 5 % überschrieb das Konto-Ziel, Fix in app.py ap_regel_konto) und setzte um
-- 20:19 Dubai „Ziel erreicht" bei 52.516,02 → Konto stand fälschlich unter „Review". Richtig: 50.000 × 1,08 = 54.000.
-- ERST NACH DEM PUSH des app.py-Fixes einspielen (sonst setzt zw_tick es im nächsten 5-min-Takt sofort wieder). Nur dieses Konto.
update public.accounts
   set ziel_usd = 54000, ziel_erreicht_at = null, ziel_erreicht_bal = null
 where id = 'a956a1a8-549c-45ed-a34c-43acd84fedf1'
   and (ziel_pct_konto ->> 'phase2')::numeric = 8
   and account_type = 'phase2';
