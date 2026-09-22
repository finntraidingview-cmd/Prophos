-- ============================================================================
-- Prophos: Wallet-Zweck-Vorlage „Profit Split" (22.09.2026)
--
-- Finn 22.09.2026 (Screenshot „Was war das?", Kommentar „Profit Split Aurel"):
-- „Füg hier noch Profit Split dazu als Zweck." — die Anteile, die an die
-- Trader (z.B. Aurel) ausgezahlt werden, sind weder Payout (Prop-Firm → uns)
-- noch interner Transfer; bisher landeten sie nur im Kommentar.
--
-- Farbe 'danger' (Geld geht raus, wie Account Kauf vor der Farb-Migration),
-- sort 25 = direkt nach Payout. Läuft NACH …_kategorien_farben.sql (danger ist
-- im Check erlaubt). Im Supabase SQL Editor einfügen und auf "Run" klicken.
-- Idempotent.
-- ============================================================================

insert into public.wallet_tx_kategorien (name, farbe, sort, aktiv, source) values
  ('Profit Split', 'danger', 25, true, 'seed')
on conflict (name) do update
  set farbe = excluded.farbe, sort = excluded.sort, aktiv = true;
