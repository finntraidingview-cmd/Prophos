-- Moritz The5%ers 200k …26776641 (8100ae6c): „Waiting for Payout“ leeren, KEIN Broker-Override (Finn 06.11.2026 ~18:40 Dubai).
-- The5%ers-Support (Mensch, Haruna K, 06.11.2026): „The 50% consistency requirement is reset after each payout“ / „Yes, the rule resets after
-- each withdrawal.“ → Prophos rechnet schon je Zyklus richtig. Nach dem Payout vom 03.11. zählt nur der 04.11. (+1.194,04, Trade-Liste vom Broker)
-- = genau das Dashboard „Days 100 %“. Die DB kennt diesen Zyklus richtig (B = W = 1.194,04), die 1.476,59 auf dem Dashboard sind der
-- auszahlbare Betrag, nicht der beste Tag → fcp_ziel.broker wird NICHT gesetzt (sql/2026-11-06_fcp_broker_consistency.sql bleibt uneingespielt).
-- Planer plant danach selbst (≈ 2 Trades an zwei Tagen, bester Tag ≤ 50 %).
update public.accounts
   set waiting_payout_since = null
 where id = '8100ae6c-5431-4d72-92c7-4c1c4cb69e66' and waiting_payout_since is not null;
