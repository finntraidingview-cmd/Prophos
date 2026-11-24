-- EM1 (Master 24.11.2026): Funded-CFD-Planer — Flex-Variante für FundingPips 100k (Max DD 12.000). ERST NACH FINNS OK EINSPIELEN.
-- Anlass: Emin · FundingPips 100k …8250 · Emin („Funded · Striking · Flex“) wird nie geplant („Flex-Konto — plant der Funded-CFD-Planer noch nicht“).
-- Code ed4dede9: greift regel.flex (Max DD ≥ ab_dd_pct % der Größe, wie BG2 Blue Guardian Nano), sperrt „flex“ im Namen nicht mehr.
--
-- Vorschlag (Herleitung je Wert):
--   dd        12.000   Max DD des Flex-Kontos (12 % von 100k), wie die Challenge-Flex-Regel (dd_pct 12).
--   ziel      1.250–2.000 $   wie FundingPips Funded Standard 100k — Flex ändert den Drawdown, nicht die Payout-Regeln; bei Striking-Konten entscheidet
--                              ohnehin Striking (7 Gewinntage ≥ 500 $, Consistency 35 %), das Ziel gilt erst in Phase B.
--   sl        1.300–1.600 $   wie Standard — die Challenge-Flex-Regel behält die SL des Standards (1.800–2.250 beide), die 2.000 $ Extra-DD sind Puffer
--                              zur Liq; liegt unter Emins Daily DD 2.500. Striking deckelt den SL zusätzlich auf 826 $ (ST1b).
--   lots      0,75–0,80        wie Standard — Challenge Flex 1,0–1,4 vs. Standard 1,0–1,5, also praktisch gleich.
--   hedge_eur 2.000 €          wie Standard — der Kontowert von FundingPips Flex ist laut Challenge-Planer gleich dem Standard (kein flex.kauf_eur);
--                              Alternative bei Satz × Max DD (0,2 €/$): 2.400 €.
-- Finn 25.11.2026: „ja nimm die Standardwerte“ → 100k wie oben, dazu 50k (Jacob · FundingPips 50k …0101 · HT, DD 6.000) = Standard 50k
--   (Ziel 625–1.000, SL 650–800, Lots 0,375–0,40, Hedge 1.000 €). Master: Sicherungstabelle mit RLS an + revoke. Eingespielt vom Master.
-- Idempotent: setzt flex nur, wenn FundingPips noch keine Flex-Variante hat. Sicherung der ganzen Zeile vorher.

create table if not exists em1_fcp_regeln_20261124 as
  select id, firmen, now() as gesichert_at from funded_cfd_plan_regeln where id = 1;
alter table em1_fcp_regeln_20261124 enable row level security;
revoke all on em1_fcp_regeln_20261124 from anon, authenticated;

update funded_cfd_plan_regeln r
   set firmen = (
     select jsonb_agg(
              case when f->'namen' ? 'fundingpips' and (f->'flex') is null
                   then f || jsonb_build_object('flex', jsonb_build_object(
                          'name', 'Flex',
                          'ab_dd_pct', 12,
                          'je_groesse', jsonb_build_object('100000', jsonb_build_object(
                              'dd', 12000, 'ziel', jsonb_build_array(1250, 2000), 'sl', jsonb_build_array(1300, 1600),
                              'lots', jsonb_build_array(0.75, 0.8), 'hedge_eur', 2000),
                          '50000', jsonb_build_object(
                              'dd', 6000, 'ziel', jsonb_build_array(625, 1000), 'sl', jsonb_build_array(650, 800),
                              'lots', jsonb_build_array(0.375, 0.4), 'hedge_eur', 1000))))
                   else f end
              order by ord)
     from jsonb_array_elements(r.firmen) with ordinality as t(f, ord))
 where r.id = 1
   and exists (select 1 from jsonb_array_elements(r.firmen) f where f->'namen' ? 'fundingpips' and (f->'flex') is null);

-- Kontrolle
select f->'namen' namen, f->'ohne_namen' ohne, f->'flex' flex
  from funded_cfd_plan_regeln r, jsonb_array_elements(r.firmen) f where r.id = 1 and f->'namen' ? 'fundingpips';

-- Zurück (nur falls nötig):
-- update funded_cfd_plan_regeln r set firmen = s.firmen from em1_fcp_regeln_20261124 s where r.id = s.id;
