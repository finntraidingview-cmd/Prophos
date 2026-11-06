-- „Waiting for Payout“ leeren bei zwei The5%ers-Funded unter dem Start (Finn 06.11.2026 ~17:40 Dubai: „ja mach du das“; Befund FC3 + Broker-Foto
-- Moritz …26584292: Balance 99.516, Payout 0 $, Consistency „—“). Nach dem Setzen kamen Hand-Trades mit Verlust, nichts auszuzahlen,
-- keine Anfrage offen → der Funded-CFD-Planer (fcp_planen springt bei Waiting aus) plant beide wieder: erst zurück über den Start, dann Zyklus-Gewinn.
--   Moritz The5%ers 100k …26584292 (3b304186) · Jacob The5%ers 200k …26696076 (0dded2ea)
update public.accounts
   set waiting_payout_since = null
 where id in ('3b304186-86c5-40ca-a9ee-4b68cc5a2dc4', '0dded2ea-81f9-491b-bc51-98c61d90cf0e')
   and waiting_payout_since is not null;
