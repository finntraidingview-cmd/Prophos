-- TEST-Person für den Rechnungs-Generator (28.08.2026, Finns Wunsch:
-- „erstell schonmal ein Test user mit test einträgen").
--
-- Legt eine Person „Test" an, die im Admin-Rechnungs-Dropdown auftaucht und
-- einen kompletten August voller Daten hat: 2 Accounts, 4 abgeschlossene
-- Trades (einer blown), 8 Finanzen-Buchungen (Käufe, Payouts, Live-P&L,
-- Manuell). Erwarteter Zeitraum-Saldo 01.–31.08.2026: 2.505,25 €.
--
-- SICHERHEIT: der auth.users-Eintrag hat encrypted_password = '' — mit diesem
-- Konto kann sich NIEMAND einloggen (bcrypt-Vergleich schlägt immer fehl).
-- Er existiert nur, damit die Auth-Admin-API den Namen „Test" liefert.
-- Alle GoTrue-Token-Textfelder stehen auf '' statt NULL — NULL in diesen
-- Spalten lässt die Admin-User-Liste von GoTrue crashen (bekannter Scan-Bug),
-- und an dieser Liste hängt /admin/overview für ALLE.
--
-- AUFRÄUMEN nach dem Test: Block ganz unten (auskommentiert).

-- 1) Auth-Eintrag (nur Name, kein Login möglich)
insert into auth.users (
  instance_id, id, aud, role, email, encrypted_password,
  email_confirmed_at, created_at, updated_at,
  raw_app_meta_data, raw_user_meta_data,
  confirmation_token, recovery_token,
  email_change_token_new, email_change, email_change_token_current,
  phone_change, phone_change_token, reauthentication_token
) values (
  '00000000-0000-0000-0000-000000000000',
  'eeeeeeee-0000-4000-a000-000000000001',
  'authenticated', 'authenticated',
  'test@prophos.test', '',
  now(), now(), now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"name":"Test"}'::jsonb,
  '', '', '', '', '', '', '', ''
) on conflict (id) do nothing;

-- 2) Zwei Accounts (Prop + Hedge)
insert into accounts (id, user_id, name, firm, account_type, balance, currency, purchase_cost, external_id, notes)
values
  ('eeeeeeee-0000-4000-a000-0000000000a1', 'eeeeeeee-0000-4000-a000-000000000001',
   'TEST FN 25k', 'FundedNext', 'funded', 25000, 'USD', 159, 'TEST-001', 'TEST-Daten für Rechnungs-Generator'),
  ('eeeeeeee-0000-4000-a000-0000000000a2', 'eeeeeeee-0000-4000-a000-000000000001',
   'TEST Fusion Live', 'Fusion Markets', 'live', 1000, 'EUR', null, 'TEST-002', 'TEST-Daten für Rechnungs-Generator')
on conflict (id) do nothing;

-- 3) Vier abgeschlossene Trades im August (einer blown)
insert into trade_plans (id, user_id, master_account_id, slave_account_id,
  master_name, master_firm, slave_name, slave_firm,
  master_risk, slave_risk, multiplier, priority, planned_for, status,
  master_pl, slave_pl, blown, started_at, completed_at, created_at)
values
  ('eeeeeeee-0000-4000-a000-0000000000d1'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a1', 'eeeeeeee-0000-4000-a000-0000000000a2',
   'TEST FN 25k', 'FundedNext', 'TEST Fusion Live', 'Fusion Markets',
   500, 450, 0.1, 'medium', '2026-08-05', 'completed',
   420.50, -388.20, false, '2026-08-05T09:12:00Z', '2026-08-05T11:40:00Z', '2026-08-04T21:00:00Z'),
  ('eeeeeeee-0000-4000-a000-0000000000d2'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a1', 'eeeeeeee-0000-4000-a000-0000000000a2',
   'TEST FN 25k', 'FundedNext', 'TEST Fusion Live', 'Fusion Markets',
   500, 450, 0.1, 'medium', '2026-08-12', 'completed',
   -310.00, 295.75, false, '2026-08-12T08:30:00Z', '2026-08-12T10:05:00Z', '2026-08-11T20:30:00Z'),
  ('eeeeeeee-0000-4000-a000-0000000000d3'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a1', 'eeeeeeee-0000-4000-a000-0000000000a2',
   'TEST FN 25k', 'FundedNext', 'TEST Fusion Live', 'Fusion Markets',
   1200, 1100, 0.1, 'medium', '2026-08-21', 'completed',
   1250.00, -1102.40, false, '2026-08-21T13:00:00Z', '2026-08-21T16:20:00Z', '2026-08-20T22:10:00Z'),
  ('eeeeeeee-0000-4000-a000-0000000000d4'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a1', 'eeeeeeee-0000-4000-a000-0000000000a2',
   'TEST FN 25k', 'FundedNext', 'TEST Fusion Live', 'Fusion Markets',
   2000, 1850, 0.1, 'high', '2026-08-26', 'completed',
   -1980.00, 1844.10, true, '2026-08-26T09:45:00Z', '2026-08-26T12:15:00Z', '2026-08-25T21:40:00Z')
on conflict (id) do nothing;

-- 4) Acht Finanzen-Buchungen (Saldo: −159 −388,20 +295,75 −1.102,40 +1.844,10 +850 +1.200 −35 = 2.505,25 €)
insert into transactions (id, user_id, account_id, account_name, account_firm,
  kind, amount, currency, occurred_at, notes, auto_generated)
values
  ('eeeeeeee-0000-4000-a000-0000000000b1'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a1', 'TEST FN 25k', 'FundedNext',
   'account_purchase', -159.00, 'EUR', '2026-08-01', 'TEST Kauf FN 25k', false),
  ('eeeeeeee-0000-4000-a000-0000000000b2'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a2', 'TEST Fusion Live', 'Fusion Markets',
   'live_pnl', -388.20, 'EUR', '2026-08-05', 'TEST Trade #t1 Slave', true),
  ('eeeeeeee-0000-4000-a000-0000000000b3'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a2', 'TEST Fusion Live', 'Fusion Markets',
   'live_pnl', 295.75, 'EUR', '2026-08-12', 'TEST Trade #t2 Slave', true),
  ('eeeeeeee-0000-4000-a000-0000000000b4'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a1', 'TEST FN 25k', 'FundedNext',
   'payout', 850.00, 'EUR', '2026-08-15', 'TEST 1. Payout', false),
  ('eeeeeeee-0000-4000-a000-0000000000b5'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a2', 'TEST Fusion Live', 'Fusion Markets',
   'manual', -35.00, 'EUR', '2026-08-18', 'TEST VPS anteilig', false),
  ('eeeeeeee-0000-4000-a000-0000000000b6'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a2', 'TEST Fusion Live', 'Fusion Markets',
   'live_pnl', -1102.40, 'EUR', '2026-08-21', 'TEST Trade #t3 Slave', true),
  ('eeeeeeee-0000-4000-a000-0000000000b7'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a2', 'TEST Fusion Live', 'Fusion Markets',
   'live_pnl', 1844.10, 'EUR', '2026-08-26', 'TEST Trade #t4 Slave', true),
  ('eeeeeeee-0000-4000-a000-0000000000b8'::uuid, 'eeeeeeee-0000-4000-a000-000000000001',
   'eeeeeeee-0000-4000-a000-0000000000a1', 'TEST FN 25k', 'FundedNext',
   'payout', 1200.00, 'EUR', '2026-08-27', 'TEST 2. Payout', false)
on conflict (id) do nothing;

-- ══════════════════════════════════════════════════════════════════════════
-- AUFRÄUMEN nach dem Test (löscht die Test-Person restlos, inkl. Rechnungen):
-- delete from rechnungen   where user_id = 'eeeeeeee-0000-4000-a000-000000000001';
-- delete from transactions where user_id = 'eeeeeeee-0000-4000-a000-000000000001';
-- delete from trade_plans  where user_id = 'eeeeeeee-0000-4000-a000-000000000001';
-- delete from accounts     where user_id = 'eeeeeeee-0000-4000-a000-000000000001';
-- delete from auth.users   where id      = 'eeeeeeee-0000-4000-a000-000000000001';
-- ══════════════════════════════════════════════════════════════════════════
