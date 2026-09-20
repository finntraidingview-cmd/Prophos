-- ============================================================================
-- Prophos: „Interner Transfer" in Krypto und Bank getrennt (20.09.2026)
--
-- Finn 20.09.2026: „mach Interner Transfer (Krypto) und Interner Transfer auf Bank".
-- Wallet → Wallet und Wallet → Bank sind zwei verschiedene Wege (über die Bank
-- laufen u.a. die Kunden-Payouts) — eine Vorlage für beides sagte zu wenig.
--
-- Die bestehende Vorlage wird UMBENANNT statt neu angelegt, und bereits damit
-- markierte Transfers ziehen mit: vor der Trennung gab es nur Wallet → Wallet,
-- der alte Name meinte also immer Krypto. Farben: Krypto bleibt violet (wie die
-- internen Umbuchungen im Feed), Bank = teal (Token seit …_farben.sql erlaubt).
--
-- Läuft NACH sql/2026-09-20_wallet_tx_kategorien_farben.sql.
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

update public.wallet_tx_kategorien
   set name = 'Interner Transfer (Krypto)'
 where name = 'Interner Transfer'
   and not exists (select 1 from public.wallet_tx_kategorien where name = 'Interner Transfer (Krypto)');

update public.wallet_tx
   set kategorie = 'Interner Transfer (Krypto)'
 where kategorie = 'Interner Transfer';

insert into public.wallet_tx_kategorien (name, farbe, sort, aktiv, source) values
  ('Interner Transfer (Krypto)', 'violet', 40, true, 'seed'),
  ('Interner Transfer auf Bank', 'teal',   50, true, 'seed')
on conflict (name) do update
  set farbe = excluded.farbe, sort = excluded.sort, aktiv = true;

-- Legt ein erneuter Lauf von …_vier.sql den alten Namen wieder an, bleibt er aus.
update public.wallet_tx_kategorien set aktiv = false where name = 'Interner Transfer';
