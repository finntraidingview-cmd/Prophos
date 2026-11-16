-- Puls-Heim-Wache je Firma für die 50k-Fundeds (Finn 16.11.2026: „ja guter Vorschlag, bau das so").
-- Standard bleibt 2.000 $ vor TP / 2.000 $ vor der engsten Grenze (150k). Bei Lucid Flex 50k (SL 1.000–1.100, MLL 2.000) und FNF Flex 50k
-- (SL 1.300–1.400, MLL 1.500) stünde jeder Trade ab dem Start in der 2.000-$-Zone → Puls käme nie raus. Darum je Firma:
-- Puls bleibt bei ≤ 1.000 $ vor TP oder ≤ 500 $ vor SL/Grenze (puls_heim_schwellen liest firmen[<_ap_norm>].tp_usd / liq_usd).
-- zweit_usd je Firma (1.000 $) steht mit drin, wirkt aber erst mit dem Code-Teil PH1 (heute liest puls_heim_zweit_regel nur den globalen Wert).
update public.puls_heim_regel
set firmen = coalesce(firmen, '{}'::jsonb)
             || '{"lucidtrading": {"tp_usd": 1000, "liq_usd": 500, "zweit_usd": 1000},
                  "fundednextfutures": {"tp_usd": 1000, "liq_usd": 500, "zweit_usd": 1000}}'::jsonb,
    updated_at = now()
where id = 1;
