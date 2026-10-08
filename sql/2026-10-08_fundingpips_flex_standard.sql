-- FUNDINGPIPS FLEX ODER STANDARD JE KONTO (08.10.2026, Finn: „Bei FundingPips in Zukunft alle neuen Accounts kommen auch zum Standard …
-- bei allen Accounts, wo das Maximum Drawdown 12 % vom Initial Balance ist — das ist alles Flex, die anderen sind in Zukunft alles Neues
-- immer Standard"). Bisher galt je_groesse["50000"] (Flex-Werte) für JEDES 50k-FundingPips-Konto. Jetzt (app.py ap_regel_flex, ab 2026-09-22.1335):
--   flex.ab_dd_pct 12  → Konto ist Flex, wenn accounts.max_drawdown ≥ 12 % der Anfangsgröße (starting_balance, sonst account_size,
--                        sonst die erkannte Größe); Nachfolger erben, weil der Nachfolger-Assistent max_drawdown übernimmt
--   flex.je_groesse    → die bisherigen 50k-Flex-Werte; Flex 100k hat noch keine Werte → „FundingPips 100k Flex: Werte fehlen"
--   flex.dd_pct 12     → Boden der Flex-Konten (auch ohne Größen-Block)
--   standard_groessen  → die Phasen-Werte der Firma sind absolute 100k-Werte; Standard 50k → „FundingPips 50k Standard: Werte fehlen"
--   je_groesse         → leer (der 50k-Block wandert nach flex.je_groesse)
-- Einspielen erst, wenn der Code (.1335+) live ist. Vorher wirkt der Code nicht (ohne flex-Block bleibt alles wie bisher); nach dem SQL
-- ohne neuen Code fehlte je_groesse["50000"] → 50k-Flex-Konten plante der alte Stand mit 100k-Werten. Folge: Flex 100k (2 Konten) wird
-- nicht mehr geplant („FundingPips 100k Flex: Werte fehlen"), bis Finn Werte nennt.
-- Wiederholbar nur einmal sinnvoll (liest je_groesse["50000"]); Rückbau: je_groesse = flex.je_groesse, flex/standard_groessen entfernen.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'fundingpips' and f->'je_groesse' ? '50000'
                               then (f - 'je_groesse')
                                    || jsonb_build_object(
                                         'je_groesse', '{}'::jsonb,
                                         'standard_groessen', jsonb_build_array(100000),
                                         'flex', jsonb_build_object('ab_dd_pct', 12, 'dd_pct', 12,
                                                                    'je_groesse', jsonb_build_object('50000', (f->'je_groesse'->'50000') - 'flex')))
                               else f end order by o)
           from jsonb_array_elements(regeln->'firmen') with ordinality as e(f, o))),
       updated_at = now()
 where id = 1;
-- Prüfen: select f->'flex', f->'standard_groessen', f->'je_groesse' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f
--          where id = 1 and f->'namen' ? 'fundingpips';
