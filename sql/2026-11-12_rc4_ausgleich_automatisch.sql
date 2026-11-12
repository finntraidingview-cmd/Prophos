-- RC4 (Finn 12.11.2026 ~20:00 Dubai, Frage „Sollen Recovery-Trades weiter einzeln bestätigt werden?“): „Nein, automatisch.“ — überholt das „yes“ vom 03.11.2026
-- (sql/2026-11-03_tradeify_ausgleich_bestaetigen.sql). Der Claim-Riegel hält Ausgleichs-WD (mt5_baseline.wd_ausgleich, Tradeify/Lucid) und Recoverer (Apex,
-- mt5_baseline.wd_recoverer bzw. ohne Marke Apex-WD auf NQ wie wd_ist_recoverer_plan) nicht mehr an; sie starten wie normale WD zur geplanten Zeit.
-- Unverändert: Hedge-Trades (hedge_art apex / tradeify_final) und normale Apex-WD der Liste wd_farmer_regeln.bestaetigen_firmen (wd_bestaetigen_noetig).
-- Basis: pg_get_functiondef(trade_plans_a0_hedge_freigabe) live am 12.11.2026 ~20:15 Dubai, nur die Bedingung im WD-Zweig geändert. Vor dem Einspielen erneut vergleichen.
-- Reihenfolge (Prüfer RC4 SOLLTE): ZUERST bzw. gleichzeitig mit dem app.py/prophos.html-Push (RC4). Diese Datei vorab ist harmlos (der alte Tab wartet weiter auf ✓).
-- Umgekehrt NICHT: der neue Tab versuchte den Ausgleich zu starten, der alte Riegel blockte den Claim, und „Zu bestätigen“ zeigte ihn nicht mehr → Plan hinge
-- unsichtbar. Wiederholbar (create or replace). Vorher: select position('\"' in pg_get_functiondef('public.trade_plans_a0_hedge_freigabe'::regproc)) — 0 erwartet.
create or replace function public.trade_plans_a0_hedge_freigabe()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare
  ss jsonb;
  ziel timestamptz;
  erst boolean;
begin
  if new.status is distinct from 'planned' or new.hedge_freigabe_at is not null then
    return new;
  end if;
  if coalesce(new.mt5_baseline->>'hedge_art', '') not in ('apex', 'tradeify_final') then
    if coalesce(new.notes, '') !~ 'Winning-Day-Farmer' or coalesce(new.start_claim_art, 'start') <> 'start'
       or not (public.wd_bestaetigen_noetig(new.winning_day, new.master_firm, new.user_id)
               -- RC4: Ausgleich und Recoverer nie bestätigungspflichtig (bis 12.11.2026: Ausgleich immer)
               and coalesce(new.mt5_baseline->>'wd_ausgleich', '') <> 'true'
               and coalesce(new.mt5_baseline->>'wd_recoverer', '') <> 'true'
               and not (new.mt5_baseline->>'wd_recoverer' is null and coalesce(new.master_firm, '') ~* 'apex'
                        and coalesce(new.master_symbol, '') ~* '^NQ')) then
      return new;
    end if;
    if coalesce(new.mt5_baseline->'start_sperre'->>'wo', '') <> 'wd' then
      update public.trade_plans
         set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
               'art', 'hedge_freigabe', 'wo', 'wd', 'text', 'wartet auf deine Bestätigung im Funded-Planer → Winning Days', 'at', now()))
       where id = new.id;
    end if;
    return null;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'hedge_freigabe' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;
  end if;
  erst := coalesce(ss->>'art', '') <> 'hedge_freigabe';
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'hedge_freigabe', 'text', 'wartet auf deine Bestätigung im Challenge-Planer', 'at', now(), 'naechster', ziel,
           'erst_at', case when erst then now() else coalesce(ss->'erst_at', to_jsonb(now())) end,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Hedge-Trade wartet auf Bestätigung] ' || coalesce(new.mt5_baseline->>'hedge_art', '?')
            || ' — erst nach „Bestätigen" im Challenge-Planer; Start rückt bis dahin je 15–30 min weiter', 'start');
  end if;
  return null;
end $function$;

-- Kontrolle: Ausgleichs-Zweig ist raus
select position('wd_ausgleich'', '''') <> ''true''' in pg_get_functiondef('public.trade_plans_a0_hedge_freigabe'::regproc)) > 0 as rc4_drin;
