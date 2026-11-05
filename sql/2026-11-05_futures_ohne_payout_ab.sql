-- PF2 (05.11.2026, Finn): Funded Futures / Winning Days haben KEIN „Payout anfragbar ab". Wörtlich: „Futures haben nicht Payout ab. Auch hier bei
-- Apex sehe ich wieder: Payout ab in Tagen macht gar keinen Sinn. Die einzige Regel ist hier, z. B. bei Apex: Winning Days sammeln + Net Profit vom
-- jeweiligen Zyklus + 50 % Consistency … Tradeify: nur Net Profit vom Zyklus + Winning Days; Lucid auch … Payout ab ist meistens nur bei den CFDs."
-- Anlass: Jacob, Apex 100k …0003/…0004/…0005 → Funded (Nachfolger-Assistent 05.11.) zeigten „Payout ab 19.11. · in 14 Tagen". Ursache: P1 (03.11.)
-- belegte das Feld beim Anlegen auch für Funded Futures/Winning Days vor (+ 14, FundedNext + 21) und schlug nach jeder Anfrage „+ 14" vor; K2 (.2054)
-- blendete es nur auf der Konto-Detailseite aus. Code-Fix: prophos.html payoutAbErlaubt / app.py PAYOUT_OHNE_AB_TYPEN.
-- Diese Datei: (1) DB-Wache — egal welcher Weg schreibt (Tab, Bulk, Admin, Kauf-Mail, alter Tab-Stand), bei Funded Futures/Winning Days bleibt
-- payout_ready_at leer; (2) Bestand leeren. Wiederholbar. NICHT eingespielt — nur auf Finns Wort.
-- ÜBERHOLT damit: sql/2026-11-04_fundednext_futures_payout_datum.sql (P2, FundedNext Futures + 21) — NICHT mehr einspielen.

set lock_timeout = '5s';   -- accounts ist eine viel benutzte Tabelle (wie sql/2026-09-29_accounts_funded_cfd.sql)

-- (1) DB-Wache
create or replace function public.accounts_futures_ohne_payout_ab()
returns trigger language plpgsql as $$
begin
  if new.account_type in ('funded', 'winning_days') and new.payout_ready_at is not null then
    new.payout_ready_at := null;
  end if;
  return new;
end $$;

drop trigger if exists accounts_futures_ohne_payout_ab on public.accounts;
create trigger accounts_futures_ohne_payout_ab
  before insert or update of payout_ready_at, account_type on public.accounts
  for each row execute function public.accounts_futures_ohne_payout_ab();

-- (2) Bestand: Vorschau, dann leeren (alle Unternehmen — das Feld hat bei Futures keine Bedeutung; Stand 05.11.2026: 12 Funded + 16 Winning Days,
--     darunter Jacobs Apex …0003/…0004/…0005 mit 19.11.). 'funded' ist per Vereinbarung Futures (sql/2026-09-29_accounts_funded_cfd.sql); am 05.11.
--     trugen alle 'funded'/'winning_days'-Konten Futures-Firmen (Apex, Tradeify, Lucid, Topstep, FundedNext Futures, FTMO Futures, Alpha, MFF) —
--     vor dem Update in der Vorschau trotzdem auf eine CFD-Firma achten (die wäre falsch typisiert, nicht falsch geleert).
select a.id, a.name, a.firm, a.account_type, a.payout_ready_at
  from public.accounts a
 where a.account_type in ('funded', 'winning_days') and a.payout_ready_at is not null
 order by a.firm, a.name;

update public.accounts
   set payout_ready_at = null
 where account_type in ('funded', 'winning_days') and payout_ready_at is not null;

-- Kontrolle (muss 0 sein)
select count(*) as futures_mit_payout_ab from public.accounts
 where account_type in ('funded', 'winning_days') and payout_ready_at is not null;

-- Rückbau Wache (Bestand nicht wiederherstellbar ohne Sicherung — die Vorschau oben ist die Liste):
-- drop trigger if exists accounts_futures_ohne_payout_ab on public.accounts; drop function if exists public.accounts_futures_ohne_payout_ab();
