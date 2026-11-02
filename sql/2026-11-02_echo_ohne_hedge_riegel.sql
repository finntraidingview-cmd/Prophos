-- ECHO OHNE HEDGE HÄLT (Finn über Eingang 02.11.2026: „alles Offene durchdrücken"). Bisher startete ein bestätigter Auto-Plan als Echo V2 ohne Hedge, wenn eh_tick den Hedge nicht rechnen konnte
-- (app.py _eh_ohne, Vorfall-Gefahr Julian FTMO 100k „Balance des Kontos nicht lesbar"). Das löst die frühere Regel „Rückfall ohne Hedge" aus sql/2026-10-29_echo_hedge_an.sql für diese Gründe ab.
-- HÄLT nur mt5_baseline.echo_hedge {status 'ohne', code in balance, lesung, marge, grenze}: vorübergehend, Hedge vorgesehen. Gleiche Liste wie EH_HALT_CODES in app.py.
-- HÄLT NICHT: mini (Tage sammeln), kein_konto (ID ohne Fusion), groesse (u. a. unter 0,01 Lot), Pläne ohne Marke (HT-CFD-Regel aus, Firma nicht auf Echo V2, Hand-Pläne: eh_tick schreibt nichts),
-- Verbrauchs-Claims (verpasst, Ziel erreicht, starten nichts), Schalter echo_hedge.an aus. Ein Start von Hand läuft ohne Claim und bleibt möglich.
-- Wie trade_plans_a1_apex_hedge: Claim scheitert, Start rückt je 15–30 min, start_sperre {art 'echo_hedge'}. ANDERS: höchstens 8 h ab dem ersten Halt, sonst rollte ein Plan über Nacht und Wochenende
-- mit alten Werten; danach bleibt die Zeit stehen, der Tab bucht ihn als verpasst. ⚪ kommt einmal aus _eh_ohne. Rechnet eh_tick wieder, stellt er auf route mt5 um, der Riegel greift nicht mehr.
-- REIHENFOLGE: erst Code ausliefern, dann diese Datei. Wiederholbar. Rückbau: drop trigger trade_plans_a1_echo_hedge on public.trade_plans; drop function public.trade_plans_a1_echo_hedge();
-- NICHT vom Slave eingespielt.

create or replace function public.trade_plans_a1_echo_hedge()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  eh jsonb;
  ss jsonb;
  ziel timestamptz;
  erst boolean;
  txt text;
  erst_at timestamptz;
begin
  eh := new.mt5_baseline->'echo_hedge';
  if new.status is distinct from 'planned' or not coalesce(new.auto_plan, false) or coalesce(new.route, '') <> 'mt5v2'
     or coalesce(new.start_claim_art, 'start') <> 'start'
     or coalesce(eh->>'status', '') <> 'ohne' or coalesce(eh->>'code', '') not in ('balance', 'lesung', 'marge', 'grenze')
     or not public.prophos_ht_echo_hedge_an() then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'echo_hedge' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
  end if;
  erst := coalesce(ss->>'art', '') <> 'echo_hedge';
  erst_at := case when erst then now() else coalesce((ss->>'erst_at')::timestamptz, now()) end;
  txt := 'Echo-Hedge nicht rechenbar: ' || left(coalesce(eh->>'grund', '?'), 160);
  if erst_at < now() - interval '8 hours' then    -- aufgegeben: Zeit bleibt stehen, der Tab bucht den Plan als verpasst
    if coalesce(ss->>'status', '') <> 'aufgegeben' then
      update public.trade_plans
         set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', ss || jsonb_build_object('status', 'aufgegeben', 'text', txt, 'at', now()))
       where id = new.id;
    end if;
    return null;
  end if;
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'echo_hedge', 'text', txt, 'at', now(), 'naechster', ziel, 'erst_at', erst_at,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Echo ohne Hedge gehalten] ' || txt || ' — Start rückt je 15–30 min weiter, bis der Hedge rechenbar ist, höchstens 8 h', 'start');
  end if;
  return null;
end $$;

drop trigger if exists trade_plans_a1_echo_hedge on public.trade_plans;
create trigger trade_plans_a1_echo_hedge
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_a1_echo_hedge();
