-- APEX-WD BESTÄTIGEN (Finn 02.11.2026 04:30, Diktat: „Da wir jetzt alle Pläne automatisieren, will ich im Funded-Planer unter Winning Days
-- alle Apex-Trades kurz einzeln bestätigen müssen — bei Tradeify nichts, bei Topstep nichts, nur Apex — damit ich sehe, dass alles gut
-- läuft. Später können wir das Bestätigen wieder ausmachen.")
--
-- IST (S13-Befund): Der Block „Zu bestätigen" unter Funded-Planer → Winning Days (prophos.html wdUebersicht, 30.10.2026) existiert schon,
-- speist sich aber nur aus Hedge-Freigaben mit mt5_baseline.hedge_art = 'apex' — die setzt ah_tick (app.py) allein für Apex-CHALLENGE-
-- Autopläne (account_type challenge). Apex-WINNING-DAY-Pläne des Farmers (winning_day = true, notes 'Winning-Day-Farmer', auto_plan false)
-- laufen daran vorbei: der Block blieb leer, der PC-Tab startet sie zur Startzeit ohne Klick.
--
-- SOLL: derselbe Bestätigungs-Weg wie bei den Hedge-Trades (sql/2026-10-29_hedge_freigabe.sql): trade_plans.hedge_freigabe_at. Bestätigen = POST
-- /admin/auto-plan/hedge-freigabe (Admin, Service-Key), Knöpfe „Bestätigen" je Trade + „✓ alle" im WD-Block. Andere Firmen unverändert.
-- Der PC-Tab versucht einen unbestätigten Apex-WD gar nicht erst (suStartetNichtWeil). Dieser Riegel ist nur das NETZ für alte Tabs und unlesbare Regeln.
-- ANDERS als bei den Hedge-Arten rückt start_um NICHT weiter: ein unbestätigter WD läuft ab und wird wie jeder nie gestartete Farmer-Plan weggeräumt, sonst
-- rollte er ohne Ende, das Konto bliebe belegt, und ein Bestätigen Tage später startete ihn sofort (Review 02.11.2026). Verbrauchs-Claims (verpasst, Ziel erreicht,
-- Manuelle Arbeit) starten nichts und gehen im WD-Fall durch. Der Weg der Hedge-Arten bleibt Zeichen für Zeichen, wie er war.
-- Schalter: wd_farmer_regeln.bestaetigen_firmen (jsonb-Liste der Farmer-Firmenschlüssel wie in vorplan.regeln.fu: 'apex' = 150k,
-- 'apex100' = 100k). Leer = kein Gate. Später abschalten:  update wd_farmer_regeln set bestaetigen_firmen = '[]' where id = 1;
-- Firma eines Plans ↔ Schlüssel: Ziffern am Ende des Schlüssels weg ('apex100' → 'apex'), dann Teilstring von lower(master_firm) ('Apex Trader').
-- REIHENFOLGE: erst Railway + prophos.html ausliefern, dann diese Datei (sonst hält das Netz, aber die Liste zeigt nichts). Vor dem Einspielen pg_get_functiondef von
-- trade_plans_a0_hedge_freigabe gegen sql/2026-10-29_hedge_freigabe.sql vergleichen. Wiederholbar: das Gate geht nur beim ersten Anlegen der Spalte an, ein
-- abgeschaltetes bleibt aus. NICHT vom Slave eingespielt.

do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'wd_farmer_regeln' and column_name = 'bestaetigen_firmen') then
    alter table public.wd_farmer_regeln add column bestaetigen_firmen jsonb not null default '[]'::jsonb;
    update public.wd_farmer_regeln set bestaetigen_firmen = '["apex", "apex100"]'::jsonb, updated_at = now() where id = 1;
  end if;
end $$;

-- REIN: braucht dieser Plan eine Bestätigung als Apex-WD? (Winning Day + Firma in bestaetigen_firmen)
-- NICHT für Gruppen mit Verwalter (Emins Gruppe): die stehen nie in Finns Liste (app.py _ap_namen/_admin_standard_aus) — ohne diese Ausnahme
-- würden sie gehalten, ohne dass jemand sie bestätigen kann. Dieselbe Menge wie _admin_verwalter_gruppen_ids.
drop function if exists public.wd_bestaetigen_noetig(boolean, text);
create or replace function public.wd_bestaetigen_noetig(p_winning_day boolean, p_master_firm text, p_user_id uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(p_winning_day, false)
     and not exists (select 1 from public.id_gruppen g where g.verwalter_user_id is not null and (g.verwalter_user_id = p_user_id
                     or exists (select 1 from public.id_gruppe_mitglied m where m.gruppe_id = g.id and m.user_id = p_user_id)))
     and exists (
       select 1 from public.wd_farmer_regeln r, jsonb_array_elements_text(coalesce(r.bestaetigen_firmen, '[]'::jsonb)) k(key)
        where r.id = 1
          and length(regexp_replace(k.key, '[0-9]+$', '')) > 0
          and lower(coalesce(p_master_firm, '')) like '%' || lower(regexp_replace(k.key, '[0-9]+$', '')) || '%');
$$;

create or replace function public.trade_plans_a0_hedge_freigabe()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  ss jsonb;
  ziel timestamptz;
  erst boolean;
begin
  if new.status is distinct from 'planned' or new.hedge_freigabe_at is not null then
    return new;
  end if;
  if coalesce(new.mt5_baseline->>'hedge_art', '') not in ('apex', 'tradeify_final') then
    -- APEX-WD BESTÄTIGEN (02.11.2026): nur Netz, schiebt nichts. Nur ein echter Start wird gehalten, ⚪ kommt aus alarm_tick (wo 'wd').
    if coalesce(new.notes, '') !~ 'Winning-Day-Farmer' or coalesce(new.start_claim_art, 'start') <> 'start'
       or not public.wd_bestaetigen_noetig(new.winning_day, new.master_firm, new.user_id) then
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

-- Trigger bleibt wie in sql/2026-10-29_hedge_freigabe.sql (before update of start_um_gestartet_at, alphabetisch erster Claim-Riegel);
-- hier nur zur Sicherheit neu gebunden, falls er fehlt.
drop trigger if exists trade_plans_a0_hedge_freigabe on public.trade_plans;
create trigger trade_plans_a0_hedge_freigabe
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_a0_hedge_freigabe();

-- Prüfen: select bestaetigen_firmen from wd_farmer_regeln where id = 1;
--         select public.wd_bestaetigen_noetig(true, 'Apex Trader', '<HT-uid>'), public.wd_bestaetigen_noetig(true, 'Tradeify', '<HT-uid>'), public.wd_bestaetigen_noetig(false, 'Apex Trader', '<HT-uid>');  -- t, f, f
