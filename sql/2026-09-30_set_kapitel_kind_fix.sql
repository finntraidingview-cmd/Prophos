-- set_kapitel(): „record "new" has no field "kind"" beim Eintragen eines angefragten Payouts.
-- Vorfall 30.09.2026 (Finn, Popup „Payout eintragen", Status Angefragt → pending_payouts):
-- Die WD-Hedge-Zeile von heute prüfte `tg_table_name = 'transactions' and new.kind = 'wd_hedge'`
-- in EINER Bedingung. plpgsql wertet die ganze Bedingung als einen Ausdruck aus, löst also
-- new.kind auch für pending_payouts auf — die Tabelle hat keine Spalte kind → jeder Insert scheitert.
-- Lösung: verschachteln, new.kind wird nur noch im transactions-Zweig angefasst.
--
-- Herkunft des Fehlers: sql/2026-09-30_neue-aera.sql, Abschnitt b (Zeile 49, `if tg_table_name = 'transactions' and
-- new.kind = 'wd_hedge' then`), live seit 30.09.2026 00:57 UTC (Migration neue_aera_2026_09_30). Jene Datei bleibt
-- unverändert als Beleg des Stands vor dem Hotfix — wer set_kapitel() neu aufsetzt, lässt DIESE Datei danach laufen.
-- Live behoben am 30.09.2026 11:00 UTC (Migrationen set_kapitel_kind_fix + set_kapitel_pending_payouts_fix_2026_09_30);
-- der Funktionskörper hier ist wortgleich mit der Live-Funktion (pg_get_functiondef, geprüft 30.09.2026).
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent (create or replace), ändert keine Daten.

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
    -- Winning-Days-Hedge (30.09.2026): zählt zum Kapitel seines DATUMS, nicht zum Kapitel des Fusion-Kontos.
    -- Verschachtelt, weil pending_payouts keine Spalte kind hat (Hotfix 30.09.2026).
    if tg_table_name = 'transactions' then
      if new.kind = 'wd_hedge' then
        new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
        return new;
      end if;
    end if;
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
