-- 2026-11-03 — „Payout anfragbar ab“ für bestehende FundedNext-Konten in „Waiting for Payout“ (P1, Finn 03.11.2026 ~22:55 Dubai, über den Master:
-- „FundedNext erster Zyklus 21 Tage … bestehende FundedNext-Konten in Waiting for Payout: Datum = Tag des ERSTEN Trades auf dem Funded-Konto + 21 Tage“).
-- Neue Konten bekommen den Termin beim Anlegen (Formular + Trigger accounts_payout_termin_neu, sql/2026-11-03_payout_termin_beim_anlegen.sql), nach jeder
-- Payout-Anfrage Anfrage-Datum + 14 (prophos.html finNextPayoutVorschlag). Diese Datei holt nur den Bestand nach, der beides nie durchlaufen hat.
--
-- Wer: accounts mit Firma FundedNext, account_type 'funded_cfd', waiting_payout_since gesetzt, payout_ready_at leer, noch nie ein Payout (keine Zeile in
-- pending_payouts und keine Buchung kind 'payout' in transactions für das Konto) — nach einem Payout gilt schon der 14-Tage-Zyklus, das setzt die Anfrage.
-- Datum: frühestes started_at eines Trades auf dem Konto (trade_plans.master_account_id, bei Polar auch slave_account_id) als Berlin-Kalendertag (wie _deTodayStr im Frontend) + 21 Tage;
-- ohne Trade: waiting_payout_since (Berlin-Tag) + 21.
-- Nur Gruppe „Hermann Technologies“ (Memory prophos-amir-nicht-ht; „… (ohne Zeile)“ = IDs ohne Gruppen-Zeile, gehören zu HT). Die Emin-Gruppe wird nur gezählt.
-- Idempotent: setzt nur, wo payout_ready_at noch leer ist. Rückbau: die Liste aus Schritt 1 vorher sichern; update … set payout_ready_at = null where id in (…).
-- Ausführen nur auf Finns Wort (Master), nicht von einem Slave.

-- ── 1. Vorschau (nur lesen): alle Kandidaten mit ID-Namen, auch die Emin-Gruppe (Spalte wird_gesetzt) ──
with kandidat as (
  select a.id, a.user_id, a.name, a.external_id, a.firm, a.waiting_payout_since,
         (select min(p.started_at) from public.trade_plans p where (p.master_account_id = a.id or p.slave_account_id = a.id) and p.started_at is not null) as erster_trade
    from public.accounts a
   where regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
     and a.account_type = 'funded_cfd'
     and a.waiting_payout_since is not null
     and a.payout_ready_at is null
     and not exists (select 1 from public.pending_payouts pp where pp.account_id = a.id)
     and not exists (select 1 from public.transactions tx where tx.account_id = a.id and tx.kind = 'payout')
)
select g.mitglied                                                                     as id_name,
       g.gruppe,
       k.name, k.external_id,
       (k.erster_trade at time zone 'Europe/Berlin')::date                            as erster_trade_tag,
       (k.waiting_payout_since at time zone 'Europe/Berlin')::date                    as waiting_seit,
       (coalesce(k.erster_trade, k.waiting_payout_since) at time zone 'Europe/Berlin')::date + 21 as payout_ready_at_neu,
       case when k.erster_trade is null then 'ohne Trade: waiting + 21' else 'erster Trade + 21' end as quelle,
       g.gruppe like 'Hermann Technologies%'                                          as wird_gesetzt
  from kandidat k
  left join public.id_gruppen_uebersicht g on g.user_id = k.user_id
 order by wird_gesetzt desc, g.mitglied, k.name;
-- Kontrolle: Aurel 100k 14367785 und Marc 100k 14367823 müssen in der Liste stehen (wird_gesetzt = true):
-- select name, external_id, payout_ready_at, waiting_payout_since from public.accounts where external_id in ('14367785', '14367823');

-- ── 2. Emin-Gruppe nur zählen ──
-- select count(*) from public.accounts a join public.id_gruppen_uebersicht g on g.user_id = a.user_id
--  where g.gruppe not like 'Hermann Technologies%' and regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
--    and a.account_type = 'funded_cfd' and a.waiting_payout_since is not null and a.payout_ready_at is null
--    and not exists (select 1 from public.pending_payouts pp where pp.account_id = a.id)
--    and not exists (select 1 from public.transactions tx where tx.account_id = a.id and tx.kind = 'payout');

-- ── 3. Setzen (nur Hermann Technologies, nur leere Felder) ──
update public.accounts a
   set payout_ready_at = (coalesce(
         (select min(p.started_at) from public.trade_plans p where (p.master_account_id = a.id or p.slave_account_id = a.id) and p.started_at is not null),
         a.waiting_payout_since) at time zone 'Europe/Berlin')::date + 21
  from public.id_gruppen_uebersicht g
 where g.user_id = a.user_id
   and g.gruppe like 'Hermann Technologies%'
   and regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
   and a.account_type = 'funded_cfd'
   and a.waiting_payout_since is not null
   and a.payout_ready_at is null
   and not exists (select 1 from public.pending_payouts pp where pp.account_id = a.id)
   and not exists (select 1 from public.transactions tx where tx.account_id = a.id and tx.kind = 'payout');
