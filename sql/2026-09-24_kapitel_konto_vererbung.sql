-- 2026-09-24 (vormittags): Buchungen erben das Kapitel ihres Kontos.
-- Finn: „Das verfälscht die Zahlen, wenn wir die bestehenden Accounts in die neue Ära reinzählen —
-- in die ist schon so viel Geld reingepumpt, teilweise funded, ready for payout. Die bestehenden
-- Accounts gehören einfach noch zum alten Kapitel, neu angelegte Accounts ab jetzt zum neuen.
-- Die Trades zählen aber schon mal in die neue Statistik."
--
-- Regel seit heute:
--   accounts        → Kapitel nach Anlagedatum (wie bisher; ein altes Konto bleibt Kapitel 1)
--   transactions    → Kapitel des Kontos (account_id), ohne Konto nach occurred_at
--   pending_payouts → Kapitel des Kontos, sonst nach requested_at
--   trade_plans     → V2-Routen immer Kapitel ohne Hedge, sonst nach Datum (unverändert)
-- Damit landet ein Payout auf einem Hedge-Ära-Konto in der Hedge-Ära, egal wann er eingeht; das
-- „Ohne Hedge"-Kapitel zeigt Kauf/Payouts nur für Konten, die seit dem 24.09.2026 angelegt sind.
create or replace function public.set_kapitel()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_ohne smallint;
  v_konto smallint;
begin
  if tg_table_name = 'trade_plans' then
    if coalesce(new.route, '') in ('mt5v2', 'tvv2') then
      select id into v_ohne from public.kapitel where hedge = false order by von desc limit 1;
      if v_ohne is not null then
        new.kapitel_id := v_ohne;
        return new;
      end if;
    end if;
    if new.kapitel_id is null then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
    end if;
    return new;
  end if;
  if tg_table_name in ('transactions', 'pending_payouts') then
    if new.account_id is not null then
      select a.kapitel_id into v_konto from public.accounts a where a.id = new.account_id;
      if v_konto is not null then
        new.kapitel_id := v_konto;
        return new;
      end if;
    end if;
    if new.kapitel_id is null then
      if tg_table_name = 'transactions' then
        new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
      else
        new.kapitel_id := public.kapitel_fuer(coalesce(new.requested_at, current_date));
      end if;
    end if;
    return new;
  end if;
  -- accounts: Anlagedatum
  if new.kapitel_id is null then
    new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
  end if;
  return new;
end;
$$;

-- transactions/pending_payouts: auch feuern, wenn das Konto nachträglich gesetzt/geändert wird
drop trigger if exists transactions_set_kapitel on public.transactions;
create trigger transactions_set_kapitel
  before insert or update of account_id on public.transactions
  for each row execute function public.set_kapitel();

drop trigger if exists pending_payouts_set_kapitel on public.pending_payouts;
create trigger pending_payouts_set_kapitel
  before insert or update of account_id on public.pending_payouts
  for each row execute function public.set_kapitel();

-- Bestand nachziehen (idempotent): Buchungen mit Konto → Kapitel des Kontos
update public.transactions t
   set kapitel_id = a.kapitel_id
  from public.accounts a
 where t.account_id = a.id and a.kapitel_id is not null and t.kapitel_id is distinct from a.kapitel_id;

update public.pending_payouts p
   set kapitel_id = a.kapitel_id
  from public.accounts a
 where p.account_id = a.id and a.kapitel_id is not null and p.kapitel_id is distinct from a.kapitel_id;

-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
