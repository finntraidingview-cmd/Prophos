-- 2026-11-25 — FN1 FundedNext: „Payout anfragbar ab“ immer einen Tag später (Finn 25.11.2026: „Für FundedNext-Payout-Anfragen: Wenn da steht ‚in 14 Tagen‘,
-- kann man immer erst in 15 Tagen anfragen, immer erst einen Tag danach. Also nicht 14 oder 21, sondern immer +1 Tag: 15 und 22 Tage.“).
-- Gleiche Regel wie prophos.html payoutZyklusTage (Anlegen 22, nach jeder Anfrage/Erhalten 15; alle anderen Firmen 14, unverändert).
-- Das Backend (app.py /admin/payout-anfragen, /admin/payout-erhalten) rechnet keinen Termin selbst — es speichert das Datum aus dem Formular.
--
-- Reihenfolge: ERST Teil B (Bestand), DANN Teil A (Trigger), dann das Frontend pushen.
-- Teil A: Trigger beim Anlegen (Stand live = sql/2026-11-05_on_demand_ohne_payout_termin.sql, nur 21 → 22). Wiederholbar.
-- Teil B: Bestand einmalig +1 Tag — FundedNext, Funded CFD, nicht On Demand, Termin heute (Berlin) oder später. Vorher gesicherte Liste in
--         public.fn1_payout_backup_20261125; nur Konten, die dort noch NICHT stehen, werden verschoben → zweimal ausführen schiebt nicht doppelt.
--         Nur Termine, die VOR FN1 entstanden sind (Prüfung): Stichtag fn1_stichtag unten = Zeitpunkt, an dem FN1 live geht. Termine, die danach
--         gesetzt wurden (neues Konto über den 22-Tage-Trigger, Anfrage/Erhalten mit + 15), tragen die +1 schon. accounts hat kein Änderungsdatum je Feld,
--         darum: B VOR dem Push des Frontends und VOR Teil A einspielen (Reihenfolge unten: B, dann A) und Konten ab dem Stichtag (created_at) auslassen.
--         Alle Gruppen (Firmenregel, kein Planer-Setting); die Vorschau zeigt die Gruppe. Stand 25.11.2026: 18 Konten (11 HT, 7 Emin).
-- Rückbau B (nur wo seither nichts Neues gesetzt wurde): update public.accounts a set payout_ready_at = b.payout_ready_alt
--   from public.fn1_payout_backup_20261125 b where a.id = b.id and a.payout_ready_at = b.payout_ready_alt + 1;
-- Ausführen nur auf Finns Wort (Master), nicht von einem Slave.

-- ── Teil B1: Vorschau (nur lesen) ──
select g.mitglied as id_name, g.gruppe, a.name, a.payout_ready_at as alt, a.payout_ready_at + 1 as neu,
       a.waiting_payout_since is not null as waiting
  from public.accounts a
  left join public.id_gruppen_uebersicht g on g.user_id = a.user_id
 where regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
   and a.account_type = 'funded_cfd'
   and not coalesce(a.on_demand, false)
   and a.payout_ready_at >= (now() at time zone 'Europe/Berlin')::date
   and a.created_at < timestamptz '2026-11-24 19:00:00+00'   -- fn1_stichtag = Lauf von B (Master 24.11. 23:00 Dubai)
 order by a.payout_ready_at, g.mitglied;

-- ── Teil B2: sichern + verschieben (eine Transaktion) ──
begin;
create table if not exists public.fn1_payout_backup_20261125 (id uuid primary key, payout_ready_alt date not null, gesichert_at timestamptz not null default now());
alter table public.fn1_payout_backup_20261125 enable row level security;   -- Prüfer S2: wie alle Sicherungstabellen
revoke all on public.fn1_payout_backup_20261125 from anon, authenticated;
with kandidat as (
  select a.id, a.payout_ready_at
    from public.accounts a
   where regexp_replace(lower(coalesce(a.firm, '')), '\s', '', 'g') like '%fundednext%'
     and a.account_type = 'funded_cfd'
     and not coalesce(a.on_demand, false)
     and a.payout_ready_at >= (now() at time zone 'Europe/Berlin')::date
     and not exists (select 1 from public.fn1_payout_backup_20261125 b where b.id = a.id)
     and a.created_at < timestamptz '2026-11-24 19:00:00+00'   -- fn1_stichtag (wie oben)
), gesichert as (
  insert into public.fn1_payout_backup_20261125 (id, payout_ready_alt)
  select id, payout_ready_at from kandidat
  returning id, payout_ready_alt
)
update public.accounts a
   set payout_ready_at = g.payout_ready_alt + 1
  from gesichert g
 where a.id = g.id
returning a.name, g.payout_ready_alt as alt, a.payout_ready_at as neu;
commit;

-- ── Teil A: Trigger ──
create or replace function public.accounts_payout_termin_neu()
returns trigger
language plpgsql as $$
begin
  if new.account_type = 'funded_cfd' and new.payout_ready_at is null and not coalesce(new.on_demand, false) then
    new.payout_ready_at := (coalesce(new.created_at, now()) at time zone 'Europe/Berlin')::date
      + case when regexp_replace(lower(coalesce(new.firm, '')), '\s', '', 'g') like '%fundednext%' then 22 else 14 end;   -- FN1: FundedNext 21 + 1
  end if;
  return new;
end $$;

-- Prüfen (nur lesen): select count(*) from public.fn1_payout_backup_20261125;   -- Stand 25.11.: 18
