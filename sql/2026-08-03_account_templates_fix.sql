-- ============================================================================
-- Prophos: account_templates — Schema an den Code angleichen
--
-- BEFUND 03.08.2026: Bulk-Vorlagen wurden NIE in Supabase gespeichert
-- (`select count(*) from account_templates` = 0). Ursache: die live existierende
-- Tabelle hat die Spalte `type`, der Code in prophos.html schreibt aber
-- `account_type` (konsistent zur accounts-Tabelle). Der Insert scheiterte,
-- der Fehler wurde im Frontend verschluckt und still auf localStorage
-- zurückgefallen — daher waren die Vorlagen nach Profilwechsel/Cache-Leerung weg.
--
-- Zusätzlich lagen account_size / purchase_cost / max_drawdown als TEXT vor,
-- obwohl der Code Zahlen schreibt und liest. Da die Tabelle leer ist, kann der
-- Typ gefahrlos korrigiert werden.
--
-- Die alte Spalte `type` bleibt bestehen (nullable, unbenutzt) — Wegwerfen wäre
-- unnötiges Risiko, falls irgendwo noch darauf gelesen wird.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

-- 1. Fehlende Spalte ergänzen (das war der eigentliche Blocker)
alter table public.account_templates
  add column if not exists account_type text;

-- 2. Zahlenspalten auf numeric (Tabelle ist leer → kein Datenverlust möglich)
alter table public.account_templates
  alter column account_size  type numeric using nullif(account_size,'')::numeric,
  alter column purchase_cost type numeric using nullif(purchase_cost,'')::numeric,
  alter column max_drawdown  type numeric using nullif(max_drawdown,'')::numeric;

-- 3. Alt-Zeilen (falls doch welche existieren) von `type` nach `account_type` ziehen
update public.account_templates
   set account_type = type
 where account_type is null and type is not null;
