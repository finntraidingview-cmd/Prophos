-- Buchungen nach Datum statt nach Konto-Kapitel für IDs mit eigenem Admin-Zugang
-- (27.09.2026, Emin). Regel seit 24.09.2026: Buchungen/Payout-Anfragen erben das Kapitel
-- des KONTOS. Für Emin heißt das: seine alten Konten tragen Kaufpreise der Hedge-Ära — im
-- Kapitel 2 stünden sie als Kauf (Screenshot Finn: „Ohne Hedge · Kauf 25.732 €"), im
-- Kapitel 1 würde jeder neue Payout unsichtbar. Emin fängt sein Tracking heute bei 0 an:
-- Konten bleiben in der alten Ära, NEUE Buchungen zählen nach ihrem Datum (→ aktuelles
-- Kapitel). Gilt nur für IDs in admin_zugang (nur_eigene), für alle anderen unverändert.

create or replace function public.set_kapitel()
 returns trigger
 language plpgsql
 set search_path to ''
as $function$
declare
  v_ohne smallint;
  v_konto smallint;
begin
  if tg_table_name = 'trade_plans' then
    if coalesce(new.route, '') in ('mt5v2', 'tvv2', 'tsv2') then
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
    if new.account_id is not null
       and not exists (select 1 from public.admin_zugang z
                        where z.user_id = new.user_id and z.nur_eigene) then
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
  if new.kapitel_id is null then
    new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
  end if;
  return new;
end;
$function$;
