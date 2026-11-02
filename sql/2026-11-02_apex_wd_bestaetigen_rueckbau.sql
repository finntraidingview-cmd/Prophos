-- RÜCKBAU zu sql/2026-11-02_apex_wd_bestaetigen.sql (Prüfer S12, 02.11.2026). Nur für den Fehlerfall; NUR abschalten geht ohne diese Datei:
--   update wd_farmer_regeln set bestaetigen_firmen = '[]' where id = 1;
-- Diese Datei: Schalter leer, Claim-Riegel Zeichen für Zeichen wie sql/2026-10-29_hedge_freigabe.sql, beide neuen Funktionen weg. Die Spalte bleibt (Railway und Tab lesen sie,
-- leer = kein Gate), bestätigte Pläne behalten hedge_freigabe_at. Wiederholbar. Der Code muss nicht zurück: mit leerer Liste verhält er sich wie vorher.

update public.wd_farmer_regeln set bestaetigen_firmen = '[]'::jsonb, updated_at = now() where id = 1;

create or replace function public.trade_plans_a0_hedge_freigabe()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  ss jsonb;
  ziel timestamptz;
  erst boolean;
begin
  if new.status is distinct from 'planned' or new.hedge_freigabe_at is not null
     or coalesce(new.mt5_baseline->>'hedge_art', '') not in ('apex', 'tradeify_final') then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'hedge_freigabe' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
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
end $$;

drop function if exists public.wd_bestaetigen_noetig(boolean, text, uuid);
drop function if exists public.wd_bestaetigen_ich_ausgenommen();

-- Prüfen: select pg_get_functiondef('public.trade_plans_a0_hedge_freigabe()'::regprocedure);  -- darf 'wd_bestaetigen' nicht mehr enthalten
