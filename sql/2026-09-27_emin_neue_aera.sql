-- Emin (6cceb3f3-…) startet ab 27.09.2026 mit dem Tracken der Finanzen bei 0.
-- Finn 27.09.2026: „neue Ära bei Emin erstellen, die alte nicht löschen, nur archivieren“.
-- Kapitel sind global (keine Nutzer-Spalte) — ein neues Kapitel hätte Finn mit
-- zurückgesetzt. Deshalb: Emins abgeschlossene Trades aus „Ohne Hedge“ (2) ins
-- Archiv „Hedge-Ära“ (1) schieben. Nichts wird gelöscht.
-- Bleibt bewusst in Kapitel 2: das FTMO-Konto e9e7f60d (Kauf −1.000 €, 25.09.)
-- und sein noch offener Trade 457ace32 — die laufen weiter.

update public.trade_plans
   set kapitel_id = 1
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f'
   and kapitel_id = 2
   and status = 'completed';
