-- TRADEIFY-AUSGLEICH AUCH IN GRUPPEN BESTÄTIGEN (Finn 03.11.2026 über den Eingang auf die Frage, ob Gruppen mit Verwalter ohne Bestätigung laufen: „Nein, auch bestätigen“).
-- Jeder Tradeify-Ausgleichs-Trade (mt5_baseline.wd_ausgleich) wartet auf hedge_freigabe_at, auch bei Emins Gruppe. Bestätigen: Finn (Admin, Liste „Zu bestätigen“)
-- oder der Verwalter der Gruppe in seiner Ansicht (app.py admin_auto_plan_hedge_freigabe mit ?ansicht=admin, hf_zeile_fuer) — so hängt keiner unsichtbar.
-- Basis: die heute eingespielte Fassung (sql/2026-11-03_tradeify_ausgleich_bestaetigen.sql, live md5 6a8e3906…), nur das „not exists“ (Gruppe mit Verwalter) im
-- Ausgleichs-Zweig entfällt. Apex-WD und Hedge-Arten unverändert. Vor dem Einspielen pg_get_functiondef gegen diese Basis vergleichen.
-- Reihenfolge: erst Railway + prophos.html ausliefern (sonst hielte das Netz einen Gruppen-Ausgleich, den noch niemand sieht), dann diese Datei. Wiederholbar.
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
               -- TRADEIFY-AUSGLEICH (03.11.2026): Marke am Plan + Winning Day — auch Gruppen mit Verwalter (Finn: „Nein, auch bestätigen“)
               or (coalesce(new.mt5_baseline->>'wd_ausgleich', '') = 'true' and coalesce(new.winning_day, false))) then
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
