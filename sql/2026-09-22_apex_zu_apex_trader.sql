-- 22.09.2026 — Firma „Apex" in „Apex Trader" aufgehen lassen (Finn: „Es gibt Apex
-- Trader und Apex Apex … Überall, wo es Apex-Accounts gibt, lösche sie und füge
-- sie zu Apex Trader hinzu").
--
-- Lage vorher: „Apex Trader" ist die geseedete Standard-Firma (DEFAULT_FIRM_SPECS)
-- bei allen 11 Logins; „Apex" war ein zusätzlich angelegter Eintrag bei zwei Logins
-- (6cceb3f3… ohne eigenes „Apex Trader", aff98e60… mit beidem, TV-Login nur am
-- „Apex"-Eintrag). 31 Accounts, 1 Vorlage, 115 Trade-Pläne und 32 Transaktionen
-- hingen am Namen „Apex". Firmen sind kein Fremdschlüssel, sondern Text — deshalb
-- wird überall der Name umgeschrieben, nicht nur firm_specs.
--
-- Die Datei dokumentiert, was am 22.09.2026 gegen die Live-DB lief.

BEGIN;

-- 1) firm_specs: TV-Login vom „Apex"-Eintrag mitnehmen, wo „Apex Trader" keinen hat
UPDATE firm_specs t
   SET tv_username = s.tv_username
  FROM firm_specs s
 WHERE s.user_id = t.user_id
   AND s.name = 'Apex' AND t.name = 'Apex Trader'
   AND t.tv_username IS NULL AND s.tv_username IS NOT NULL;

-- 2) firm_specs: Login ohne „Apex Trader" → „Apex" umbenennen (Specs bleiben erhalten)
UPDATE firm_specs s
   SET name = 'Apex Trader'
 WHERE s.name = 'Apex'
   AND NOT EXISTS (SELECT 1 FROM firm_specs t WHERE t.user_id = s.user_id AND t.name = 'Apex Trader');

-- 3) firm_specs: verbleibende „Apex"-Duplikate löschen
DELETE FROM firm_specs WHERE name = 'Apex';

-- 4) Alle Textreferenzen umhängen
UPDATE accounts           SET firm = 'Apex Trader'         WHERE firm = 'Apex';
UPDATE account_templates  SET firm = 'Apex Trader'         WHERE firm = 'Apex';
UPDATE trade_plans        SET master_firm = 'Apex Trader'  WHERE master_firm = 'Apex';
UPDATE trade_plans        SET slave_firm  = 'Apex Trader'  WHERE slave_firm  = 'Apex';
UPDATE transactions       SET account_firm = 'Apex Trader' WHERE account_firm = 'Apex';
UPDATE pending_payouts    SET account_firm = 'Apex Trader' WHERE account_firm = 'Apex';
UPDATE acc_plan           SET firma = 'Apex Trader'        WHERE firma = 'Apex';

COMMIT;
