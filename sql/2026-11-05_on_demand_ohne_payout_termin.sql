-- ON DEMAND OHNE PAYOUT-TERMIN (OD1, 05.11.2026, Finn über den Master, Marc FundedNext 100k …7821 + …7823 „→ Funded · On Demand“):
-- „Wenn man das On-Demand-Addon hat, dann gibt es keine Mindestanzahl mehr, auf die man warten muss. Also per Datum-Feld und per Tagen fällt hier
-- beides mal weg.“ — NICHT automatisch einspielen, Finn/Master spielt ein (DML (1) per execute_sql/apply_migration, DDL (2)–(4) per apply_migration).
--
-- accounts.payout_ready_at („Payout anfragbar ab“) gilt für On-Demand-Konten nicht mehr. Einziger Schreiber bleibt der Funded-CFD-Planer (app.py, O1):
-- erreicht ein On-Demand-Konto Ziel + Consistency, setzt er das Feld auf HEUTE → Chip „Payout jetzt“. Sonst zeigt das Frontend „Payout bei Ziel · On Demand“
-- (payoutAbInfo, kein Datum, keine Tage).
--
-- (1) Bestand: Termine der On-Demand-Konten leeren — jeden KÜNFTIGEN, und einen vergangenen nur, wenn das Konto NICHT in Waiting for Payout steht.
--     Stand 05.11.2026 (SELECT): 5 Konten, 4 mit Datum — 2026-11-24 (…7823, Anlege-Termin +21), 2026-11-18, 2026-11-04, 2026-10-23. Vergangene Daten
--     (Anlegen/von Hand) sind vom Planer-„heute“ nicht zu unterscheiden; der Planer setzt „heute“ beim nächsten Lauf für jedes nicht wartende Konto,
--     das Ziel + Consistency wirklich erreicht hat, wieder. Wartende überspringt der Planer (Fremd-Review OD1) — ihr vergangenes Datum bleibt („Payout jetzt“).
-- (2) Anlege-Trigger accounts_payout_termin_neu (sql/2026-11-03_payout_termin_beim_anlegen.sql): kein +14/+21-Termin für ein Konto, das schon mit
--     on_demand = true angelegt wird. Sonst Wort für Wort wie bisher.
-- (3) On Demand einschalten (Accounts → Add-ons → On Demand bzw. Konto bearbeiten): ein künftiger Termin fällt weg (heute/gestern bleibt — kann vom Planer sein).
-- (4) Payout angefragt (pending_payouts neu, jeder Weg: Accounts, Finanzen, Admin → Payouts „Anfragen“): bei On Demand Termin leeren — sonst stünde
--     das Planer-„heute“ nach dem Payout weiter als „Payout jetzt“ da. Der Frontend-Vorschlag „heute + 14“ ist für On Demand schon leer (finNextPayoutVorschlag).
--
-- Rückbau: (4) drop trigger if exists pending_payouts_on_demand_termin on public.pending_payouts; drop function if exists public.pending_payouts_on_demand_termin();
--          (3) drop trigger if exists accounts_on_demand_termin on public.accounts; drop function if exists public.accounts_on_demand_termin();
--          (2) Funktion aus sql/2026-11-03_payout_termin_beim_anlegen.sql neu einspielen;  (1) nicht rückbaubar (Werte oben im Kommentar).

-- (1)
update public.accounts
   set payout_ready_at = null
 where account_type = 'funded_cfd' and on_demand is true and payout_ready_at is not null
   and (payout_ready_at > (now() at time zone 'Europe/Berlin')::date or waiting_payout_since is null);

-- (2)
create or replace function public.accounts_payout_termin_neu()
returns trigger
language plpgsql as $$
begin
  if new.account_type = 'funded_cfd' and new.payout_ready_at is null and not coalesce(new.on_demand, false) then
    new.payout_ready_at := (coalesce(new.created_at, now()) at time zone 'Europe/Berlin')::date
      + case when regexp_replace(lower(coalesce(new.firm, '')), '\s', '', 'g') like '%fundednext%' then 21 else 14 end;
  end if;
  return new;
end $$;

-- (3)
create or replace function public.accounts_on_demand_termin()
returns trigger
language plpgsql as $$
begin
  if new.account_type = 'funded_cfd' and coalesce(new.on_demand, false) and not coalesce(old.on_demand, false)
     and new.payout_ready_at is not null and new.payout_ready_at > (now() at time zone 'Europe/Berlin')::date then
    new.payout_ready_at := null;
  end if;
  return new;
end $$;

drop trigger if exists accounts_on_demand_termin on public.accounts;
create trigger accounts_on_demand_termin
  before update of on_demand on public.accounts
  for each row execute function public.accounts_on_demand_termin();

-- (4)
create or replace function public.pending_payouts_on_demand_termin()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
begin
  if new.account_id is not null then
    update public.accounts
       set payout_ready_at = null
     where id = new.account_id and account_type = 'funded_cfd' and on_demand is true and payout_ready_at is not null;
  end if;
  return new;
end $$;

drop trigger if exists pending_payouts_on_demand_termin on public.pending_payouts;
create trigger pending_payouts_on_demand_termin
  after insert on public.pending_payouts
  for each row execute function public.pending_payouts_on_demand_termin();

-- Kontrolle (nur lesen, nach dem Einspielen 0):
-- select count(*) from public.accounts where account_type = 'funded_cfd' and on_demand is true and payout_ready_at > (now() at time zone 'Europe/Berlin')::date;
