-- EINGESPIELT 30.10.2026 ~01:00 Dubai (Master, nach S2-OK)
-- APEX-CHALLENGE IMMER MIT HEDGE (30.10.2026, Finn über Master: „Apex-Challenges laufen IMMER mit Hedge"). Bisher blieb ein freigegebener
-- Apex-Plan Orbit V2 OHNE Hedge, wenn ah_tick den Hedge nicht rechnen konnte (_ah_ohne: Balance, Kontowert-Satz, Fusion-Konto, Fusion-Lesung,
-- Marge, Lot-Grenze). Jetzt wie beim finalen Tradeify: nie ohne Hedge starten, sondern mit Grund halten.
--
-- Claim-Riegel trade_plans_a1_apex_hedge (feuert nach trade_plans_a0_hedge_freigabe, alphabetisch vor trade_plans_a_final_halten — gibt a0
-- null zurück, läuft dieser gar nicht erst): ein geplanter Auto-Plan mit Marke mt5_baseline.hedge_art = 'apex' (setzt nur ah_tick, nur
-- HT-Apex-Challenges auf tvv2) startet nur, wenn er umgestellt ist (mt5_baseline.apex_hedge.status 'mit' und hedge_eur > 0). Sonst scheitert
-- der Claim (return null), der Plan bleibt planned, start_um rückt 15–30 min weiter (gestreut, Jitter-Regel; ah_tick prüft weiter jede
-- Minute und stellt um, sobald der Hedge rechenbar ist), mt5_baseline.start_sperre {art 'apex_hedge', text mit Grund aus apex_hedge.grund}.
-- Protokoll auto_plan_umplanung nur beim ersten Halt. Mehrfach-Claim < 1 min: nichts neu schieben. ⚪ einmal: ah_tick (_ah_ohne) bzw.
-- alarm_tick, falls ah_tick den Plan noch nicht gesehen hat.
-- Nur solange regeln.apex_hedge.an true ist (prophos_apex_hedge_an aus sql/2026-10-30_apex_hedge.sql) — Schalter aus: wie bisher Orbit V2.
-- hand_werte_at bleibt unberührt (ah_tick stellt nur Pläne ohne Hand-Werte um). Ein Start von Hand ohne Claim bleibt möglich.
-- Nachtrag 30.10.2026 (Prüfer S2 / Master, Variante 2): ein markierter Plan mit späteren Hand-Werten wird von ah_tick nie umgestellt — er
-- bleibt gehalten (nie ohne Hedge), der Sperrtext sagt es: „… Werte von Hand geändert, Takt stellt nicht mehr um: ablehnen und neu planen".
-- Live eingespielt über sql/2026-10-30_apex_immer_hedge_hand.sql (dieselbe Funktion, Wort für Wort).
-- trade_plans_kontoart_weg bleibt unverändert (kein neuer Weg). Wiederholbar.
-- Rückbau: drop trigger trade_plans_a1_apex_hedge on public.trade_plans; drop function public.trade_plans_a1_apex_hedge();

do $pruef$
begin
  perform 'public.prophos_apex_hedge_an()'::regprocedure;
  perform 'public.trade_plans_a0_hedge_freigabe()'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-30_apex_hedge.sql und sql/2026-10-29_hedge_freigabe.sql einspielen';
end $pruef$;

create or replace function public.trade_plans_a1_apex_hedge()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  ss jsonb;
  ziel timestamptz;
  erst boolean;
  txt text;
begin
  if new.status is distinct from 'planned' or not coalesce(new.auto_plan, false)
     or coalesce(new.mt5_baseline->>'hedge_art', '') <> 'apex' then
    return new;
  end if;
  -- umgestellt (ah_tick: WD-Weg mit Fusion-Gegenhedge) → darf starten
  if coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = 'mit' and coalesce(new.hedge_eur, 0) > 0 then
    return new;
  end if;
  if not public.prophos_apex_hedge_an() then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'apex_hedge' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
  end if;
  erst := coalesce(ss->>'art', '') <> 'apex_hedge';
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  -- Hand-Werte (Master 30.10.2026, Variante 2): ah_tick stellt solche Pläne nie mehr um — weiter halten (nie ohne Hedge), Grund sagt es
  if new.hand_werte_at is not null then
    txt := 'Apex wartet auf Hedge — Werte von Hand geändert, Takt stellt nicht mehr um: ablehnen und neu planen';
  else
    txt := 'Apex-Challenge wartet auf Gegenhedge'
           || coalesce(' (' || nullif(left(new.mt5_baseline->'apex_hedge'->>'grund', 160), '') || ')', ' (noch nicht umgestellt)');
  end if;
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'apex_hedge', 'text', txt, 'at', now(), 'naechster', ziel,
           'erst_at', case when erst then now() else coalesce(ss->'erst_at', to_jsonb(now())) end,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Apex ohne Hedge gehalten] ' || txt || ' — startet nie ohne Hedge; Start rückt je 15–30 min weiter, bis der Hedge rechenbar ist',
            'start');
  end if;
  return null;
end $$;

drop trigger if exists trade_plans_a1_apex_hedge on public.trade_plans;
create trigger trade_plans_a1_apex_hedge
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_a1_apex_hedge();
