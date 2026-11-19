-- Marc: Apex hat das Profil ab 18.11.2026 auf „Trader Probation“ gesetzt (Mail Apex Risk Management, Finn 19.11.2026 ~17:10 Dubai).
-- Probation: jeder PA-Trade braucht harten SL, jeder Payout zählt wie ein Erst-Payout, 10 Kalendertage keine Anfrage, mind. 90 Tage.
-- Finn: „Erstmal bei Marc komplett die Accounts einfach mal deaktivieren. Ich denke, die sind jetzt eh wertlos.“
-- Befund vorher: der Winning-Day-Farmer lief auf allen drei PAs meist OHNE SL (auch 18.11. und 19.11., nach Probation-Beginn).
-- Weg: der vorhandene Riegel accounts.deaktiviert_at (sql/2026-10-30_konto_deaktiviert.sql) — kein Farmer, kein Planer, Claim gesperrt.
-- Kein Archiv, kein Blow: Konten und offene Payout-Zeilen (…0002 2.233,55 $, …0005 1.786,84 $, beide angefragt 09.11.) bleiben stehen.
-- Stand beim Deaktivieren (TV-Balance): …0002 150k 162.907,84 · …0005 100k 112.344,96 · …0006 100k 112.649,38. Keine planned/open-Pläne.
-- Rückweg: dieselbe where-Klausel mit „set deaktiviert_at = null“ und „and a.deaktiviert_at is not null“.

update public.accounts a
   set deaktiviert_at = now(), updated_at = now()
 where a.user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'
   and a.firm = 'Apex Trader'
   and a.account_type in ('winning_days', 'funded')
   and a.id::text ~ '^(2aa6f1a9|6f7f4acd|171fd292)'
   and a.deaktiviert_at is null;
