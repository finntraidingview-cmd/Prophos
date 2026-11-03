-- 2026-11-04 — „Payout anfragbar ab“ für bestehende FundedNext-Futures-Funded-Konten (P2, Finn 04.11.2026 ~00:20 Dubai zur Frage FundedNext Futures:
-- „1. 21 Tage, danach alles 14“). Neue Konten: prophos.html payoutErsterTermin (Anlegetag + 21, Formular); nach jeder Payout-Anfrage + 14
-- (finNextPayoutVorschlag). Der Trigger accounts_payout_termin_neu (sql/2026-11-03_payout_termin_beim_anlegen.sql) kennt nur Funded CFD und bleibt so.
--
-- Wer: accounts mit Firma FundedNext Futures (Name enthält fundednext UND futures), account_type 'funded' oder 'winning_days', payout_ready_at leer,
-- noch nie ein Payout (keine Zeile in pending_payouts / managed_payouts, keine Buchung kind 'payout' in transactions). Danach gilt schon der 14-Tage-Zyklus.
-- Datum: frühestes started_at eines Trades auf dem Konto (trade_plans.master_account_id) als Berlin-Kalendertag + 21; ohne Trade: Anlegetag (created_at,
-- Berlin) + 21 — wie das Formular beim Anlegen.
-- Nur Gruppe „Hermann Technologies“ (Memory prophos-amir-nicht-ht; „… (ohne Zeile)“ = IDs ohne Gruppen-Zeile, gehören zu HT). Die Emin-Gruppe wird nur gezählt.
-- Idempotent: setzt nur, wo payout_ready_at noch leer ist. Rückbau: die Liste aus Schritt 1 vorher sichern; update … set payout_ready_at = null where id in (…).
-- Ausführen nur auf Finns Wort (Master), nicht von einem Slave.

-- ── 1. Vorschau (nur lesen): alle Kandidaten mit ID-Namen, auch die Emin-Gruppe (Spalte wird_gesetzt) ──
with kandidat as (
  select a.id, a.user_id, a.name, a.external_id, a.firm, a.account_type, a.created_at,
         (select min(p.started_at) from public.trade_plans p where p.master_account_id = a.id and p.started_at is not null) as erster_trade
    from public.accounts a
   where regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
     and lower(coalesce(a.firm, '')) like '%futures%'
     and a.account_type in ('funded', 'winning_days')
     and a.payout_ready_at is null
     and not exists (select 1 from public.pending_payouts pp where pp.account_id = a.id)
     and not exists (select 1 from public.managed_payouts mp where mp.account_id = a.id)
     and not exists (select 1 from public.transactions tx where tx.account_id = a.id and tx.kind = 'payout')
)
select g.mitglied                                                                     as id_name,
       g.gruppe,
       k.name, k.external_id, k.account_type,
       (k.erster_trade at time zone 'Europe/Berlin')::date                            as erster_trade_tag,
       (k.created_at at time zone 'Europe/Berlin')::date                              as angelegt,
       (coalesce(k.erster_trade, k.created_at) at time zone 'Europe/Berlin')::date + 21 as payout_ready_at_neu,
       case when k.erster_trade is null then 'ohne Trade: angelegt + 21' else 'erster Trade + 21' end as quelle,
       g.gruppe like 'Hermann Technologies%'                                          as wird_gesetzt
  from kandidat k
  left join public.id_gruppen_uebersicht g on g.user_id = k.user_id
 order by wird_gesetzt desc, g.mitglied, k.name;

-- ── 2. Emin-Gruppe nur zählen ──
-- select count(*) from public.accounts a join public.id_gruppen_uebersicht g on g.user_id = a.user_id
--  where g.gruppe not like 'Hermann Technologies%' and regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
--    and lower(coalesce(a.firm, '')) like '%futures%' and a.account_type in ('funded', 'winning_days') and a.payout_ready_at is null
--    and not exists (select 1 from public.pending_payouts pp where pp.account_id = a.id)
--    and not exists (select 1 from public.managed_payouts mp where mp.account_id = a.id)
--    and not exists (select 1 from public.transactions tx where tx.account_id = a.id and tx.kind = 'payout');

-- ── 3. Setzen (nur Hermann Technologies, nur leere Felder) ──
update public.accounts a
   set payout_ready_at = (coalesce(
         (select min(p.started_at) from public.trade_plans p where p.master_account_id = a.id and p.started_at is not null),
         a.created_at) at time zone 'Europe/Berlin')::date + 21
  from public.id_gruppen_uebersicht g
 where g.user_id = a.user_id
   and g.gruppe like 'Hermann Technologies%'
   and regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
   and lower(coalesce(a.firm, '')) like '%futures%'
   and a.account_type in ('funded', 'winning_days')
   and a.payout_ready_at is null
   and not exists (select 1 from public.pending_payouts pp where pp.account_id = a.id)
   and not exists (select 1 from public.managed_payouts mp where mp.account_id = a.id)
   and not exists (select 1 from public.transactions tx where tx.account_id = a.id and tx.kind = 'payout');
