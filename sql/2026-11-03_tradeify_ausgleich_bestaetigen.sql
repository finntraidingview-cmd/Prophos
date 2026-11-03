-- TRADEIFY-AUSGLEICH BESTÄTIGEN (Finn 03.11.2026 über den Eingang: „yes“ — jeder Tradeify-Ausgleichs-Trade wird einzeln bestätigt wie der Apex-Recoverer;
-- normale Tradeify-WD bleiben, wie sie sind). Der Farmer legt den Ausgleichs-Trade mit mt5_baseline.wd_ausgleich = true an (app.py /admin/wd-plaene POST,
-- prophos.html wdPlanAnlegen + Nachziehen). Der PC-Tab startet ihn ohne hedge_freigabe_at nicht (tpWdWartetAufBestaetigung), die Liste „Zu bestätigen“ zeigt ihn
-- (hf_basis/hf_ist_wd). Dieser Riegel ist wie beim Apex-WD nur das NETZ für alte Tabs: er hält einen Start-Claim ohne Freigabe, schiebt nichts.
-- Gruppen mit Verwalter (Emin) ausgenommen — sie stehen nie in Finns Liste (wie wd_bestaetigen_noetig).
-- Basis: pg_get_functiondef von trade_plans_a0_hedge_freigabe am 03.11.2026 (live), nur die Bedingung im WD-Zweig erweitert. Vor dem Einspielen erneut vergleichen.
-- Reihenfolge: erst Railway + prophos.html ausliefern, dann diese Datei. Wiederholbar (create or replace).
create or replace function public.trade_plans_a0_hedge_freigabe()
returns trigger
language plpgsql security definer set search_path to 'public' as $function$
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
               -- TRADEIFY-AUSGLEICH (03.11.2026): Marke am Plan, Winning Day, keine Gruppe mit Verwalter
               or (coalesce(new.mt5_baseline->>'wd_ausgleich', '') = 'true' and coalesce(new.winning_day, false)
                   and not exists (select 1 from public.id_gruppen g where g.verwalter_user_id is not null and (g.verwalter_user_id = new.user_id
                                   or exists (select 1 from public.id_gruppe_mitglied m where m.gruppe_id = g.id and m.user_id = new.user_id))))) then
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
