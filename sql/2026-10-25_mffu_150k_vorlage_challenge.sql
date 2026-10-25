-- Vorlage „MyFundedFutures 150k Eval Pro" von phase1 auf challenge (Finn 25.10.2026: Futures-Evals sind Challenges,
-- phase1/phase2 gibt es nur bei CFD). Fiel beim Anlegen der MFFU 50k Flex auf, die den Wert von hier übernommen hatte.
update bulk_vorlagen set account_type = 'challenge', updated_at = now()
where name = 'MyFundedFutures 150k Eval Pro' and account_type = 'phase1';
