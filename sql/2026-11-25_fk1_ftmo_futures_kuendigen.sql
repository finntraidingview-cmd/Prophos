-- FK1 (Finn 25.11.2026): FTMO-Futures-Challenges verlängern sich nach einem Monat automatisch und kosten weiter — auch geblowte. Nur bestandene
-- verlängern sich nicht. Geblowte FTMO-Futures-Challenges (user_settings 'archive' reason 'blown') erscheinen bei ihrer ID in „Braucht dich"
-- („Abo kündigen, verlängert sich am TT.MM."), bis jemand „✓ gekündigt" drückt → accounts.abo_gekuendigt_at.
-- Eine kleine Spalte, keine neue Tabelle (accounts hat schon RLS je Besitzer; Railway schreibt fremde IDs mit dem Service-Key).
-- NICHT eingespielt (Slave 5) — der Master spielt ein. Ohne Spalte liefert GET /konto/abo-kuendigen eine leere Liste (sql_fehlt), nichts bricht.
-- Idempotent. Einmal-Nachlauf nicht nötig: die Liste rechnet aus Archiv + Spalte, bestehende geblowte Konten erscheinen sofort.

alter table public.accounts add column if not exists abo_gekuendigt_at timestamptz;
comment on column public.accounts.abo_gekuendigt_at is 'FK1: Abo bei der Firma gekündigt (FTMO Futures verlängert geblowte Challenges sonst alle 30 Tage)';

-- Prüfung (heute 7 geblowte FTMO-Futures-Challenges, 25.11.2026; Archiv über ALLE Profile — archivierender Login kann ein Admin sein):
--   select distinct a.id, a.user_id, a.name, a.created_at::date, a.abo_gekuendigt_at
--     from accounts a join user_settings s on s.key = 'archive' and jsonb_typeof(s.value) = 'object'
--    where a.firm = 'FTMO Futures' and a.account_type = 'challenge' and s.value -> a.id::text ->> 'reason' = 'blown';
-- Zurück: alter table public.accounts drop column abo_gekuendigt_at;
