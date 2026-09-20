-- ============================================================================
-- Prophos: Wallet-Zweck-Vorlagen auf vier eingedampft (20.09.2026)
--
-- Finn 20.09.2026 (Screenshot des „Was war das?"-Modals mit den 9 Startwerten):
-- „mach hier nur 1. Fusion Deposit 2. Payout 3. Account Kauf 4. Interner Transfer".
--
-- Die 9 Vorlagen aus sql/2026-09-18_wallet_tx.sql waren geraten — im Alltag
-- kommen nur diese vier Fälle vor. BEFUND vor dem Lauf: keine einzige Zeile in
-- wallet_tx trägt bisher eine kategorie, es hängt also nichts an den alten Namen.
--
-- Die alten Startwerte werden NICHT gelöscht, sondern auf aktiv = false gesetzt:
-- das Frontend lädt nur aktive (prophos.html, walLoad: .eq('aktiv', true)), und
-- der Schritt bleibt umkehrbar. Nur source = 'seed' — selbst angelegte Vorlagen
-- (source = 'manuell') fasst ein erneuter Lauf nie an.
--
-- Farben hier nur als Startwert für eine frische DB — die endgültigen (jede
-- Vorlage eine eigene) setzt sql/2026-09-20_wallet_tx_kategorien_farben.sql.
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

insert into public.wallet_tx_kategorien (name, farbe, sort, aktiv, source) values
  ('Fusion Deposit',    'danger', 10, true, 'seed'),
  ('Payout',            'good',   20, true, 'seed'),
  ('Account Kauf',      'danger', 30, true, 'seed'),
  ('Interner Transfer', 'violet', 40, true, 'seed')
on conflict (name) do update
  set sort = excluded.sort, aktiv = true;   -- farbe bewusst NICHT: die setzt 2026-09-20_wallet_tx_kategorien_farben.sql

update public.wallet_tx_kategorien
   set aktiv = false
 where source = 'seed'
   and name not in ('Fusion Deposit', 'Payout', 'Account Kauf', 'Interner Transfer');
