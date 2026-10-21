-- Emin FundingPips 100k …6520 (20936520, Phase 1) ist ein Flex-Konto (Finn 21.10.2026 ~17:30 Dubai: „Das ist ein Flex-Account bei Emin —
-- Take-Profit-Ziel 10 %, nicht 8 %; er hat 8.000, es fehlen noch 2.000"). Prophos erkennt Flex nur am Max Drawdown (ap_konto_flex: ≥ 12 %
-- der Größe); eingetragen waren 10.000 $ → Standard-Regel 8 % → Ziel 108.000, die Ziel-Wache hat es 15:20 als erreicht markiert.
-- Jetzt max_drawdown 12.000 (Flex-Regel: Phase 1 10 % = 110.000, Boden 12 %), Name mit „· Flex" wie die anderen Flex-Konten, und die
-- falsche Ziel-Markierung zurück (dasselbe, was die Ziel-Wache bei „nicht mehr erreicht" macht).
update accounts
   set max_drawdown = 12000,
       name = '100k 20936520 → Phase 1 · Flex',
       ziel_erreicht_at = null, ziel_erreicht_bal = null, ziel_usd = null
 where id = 'b4d48b09-2c9f-4748-8dfd-9288868762c4'
   and name = '100k 20936520 → Phase 1';
