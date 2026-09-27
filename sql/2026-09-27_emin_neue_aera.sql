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

-- Nachtrag 27.09.2026 16:15 (Finn: „da soll alles resetet“, Screenshot zeigte „Alle“ mit −11.450,79 €):
-- auch der FTMO-Kauf und der offene FTMO-Trade gehen ins Archiv. Das Konto e9e7f60d selbst
-- bleibt in Kapitel 2 — Payouts darauf erben per Trigger das Konto-Kapitel und zählen damit neu.
update public.transactions set kapitel_id = 1
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 2;
update public.trade_plans set kapitel_id = 1
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 2;

-- Die Kachel „Aktueller Zyklus“ rechnet über ALLE Buchungen (ohne Kapitel-Filter) minus
-- Baseline der letzten Abrechnung — deshalb eine Abrechnung als Nullpunkt (Emin behält 100 %).
insert into public.finanzen_settlements (user_id, cycle_netto, cumulative_baseline, profit_share_pct, client_amount, house_amount, note)
select '6cceb3f3-dc78-48ee-8668-26081da3e70f', s, s, 0, 0, s, 'Neustart Finanz-Tracking 27.09.2026 (alte Ära archiviert)'
  from (select coalesce(sum(amount), 0) s from public.transactions
         where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f') x;

-- Umschalter oben auf „Ohne Hedge“ (gesynct über user_settings 'kapitel').
update public.user_settings set value = '{"id":2}'::jsonb, updated_at = now()
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and key = 'kapitel';
