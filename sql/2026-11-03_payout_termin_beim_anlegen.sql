-- 2026-11-03 — Erster Payout-Termin beim Anlegen eines Funded-CFD-Kontos (Finn 03.11.2026 ~01:15 Dubai über den Eingang: „das nächste
-- Payout-Datum eines Funded-Kontos soll Prophos selbst setzen … FundedNext erster Zyklus 21 Tage, ab dem zweiten 14 Tage, alle anderen 14").
-- Ein BEFORE-INSERT-Trigger deckt jeden Anlege-Weg ab: Account hinzufügen, Bulk, Nachfolger-Assistent, Admin-Anlegen über Railway.
-- Gesetzt wird NUR, wenn das Feld leer ist: ein beim Anlegen von Hand eingetragenes Datum bleibt. Basis = Anlegetag in Berlin
-- (Prophos-Kalendertag wie _deTodayStr). Nur account_type 'funded_cfd': Funded Futures (Apex, Topstep, Tradeify Futures, Lucid) zahlen
-- über Winning Days, dort bleibt das Feld unberührt (Rückfrage an Finn offen). Feld = accounts.payout_ready_at („Payout anfragbar ab").
-- Wiederholbar. Rückbau: drop trigger accounts_payout_termin_neu on public.accounts; drop function public.accounts_payout_termin_neu();

create or replace function public.accounts_payout_termin_neu()
returns trigger
language plpgsql as $$
begin
  if new.account_type = 'funded_cfd' and new.payout_ready_at is null then
    new.payout_ready_at := (coalesce(new.created_at, now()) at time zone 'Europe/Berlin')::date
      + case when regexp_replace(lower(coalesce(new.firm, '')), '\s', '', 'g') like '%fundednext%' then 21 else 14 end;
  end if;
  return new;
end $$;

drop trigger if exists accounts_payout_termin_neu on public.accounts;
create trigger accounts_payout_termin_neu
  before insert on public.accounts
  for each row execute function public.accounts_payout_termin_neu();

-- Prüfen (nur lesen):
-- select name, firm, created_at::date, payout_ready_at from public.accounts where account_type = 'funded_cfd' order by created_at desc limit 5;
