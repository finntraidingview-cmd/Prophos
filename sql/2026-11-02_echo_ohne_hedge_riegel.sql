-- ECHO OHNE HEDGE HÄLT (Finn über Eingang 02.11.2026: „alles Offene durchdrücken"). Bisher startete ein bestätigter Auto-Plan als Echo V2 ohne Hedge, wenn eh_tick den Hedge nicht rechnen konnte
-- (app.py _eh_ohne, Vorfall-Gefahr Julian FTMO 100k „Balance des Kontos nicht lesbar"). Das löst die frühere Regel „Rückfall ohne Hedge" aus sql/2026-10-29_echo_hedge_an.sql für diese Gründe ab.
-- HÄLT nur mt5_baseline.echo_hedge {status 'ohne', code in balance, lesung, groesse}: Hedge vorgesehen, aber nicht rechenbar (Entscheid Eingang 02.11.2026). Gleiche Liste wie EH_HALT_CODES in app.py.
-- HÄLT NICHT: klein („Hedge unter 0,01 Lot", nicht kaufbar, Betrag vernachlässigbar), marge und grenze (Rückfall ohne Hedge, Finns Regel 29.10.), mini (Tage sammeln), kein_konto (ID ohne Fusion), Pläne ohne Marke (HT-CFD-Regel aus, Firma nicht auf Echo V2, Hand-Pläne: eh_tick schreibt nichts),
-- Verbrauchs-Claims (verpasst, Ziel erreicht, starten nichts), Schalter echo_hedge.an aus. Ein Start von Hand läuft ohne Claim und bleibt möglich.
-- Wie trade_plans_a1_apex_hedge: Claim scheitert, Start rückt je 15–30 min, start_sperre {art 'echo_hedge'}. ANDERS: höchstens 8 h ab dem ersten Halt und nie hinter das CFD-Fensterende bzw. die deutsche
-- Tagesgrenze, sonst rollte ein Plan über Nacht und Wochenende mit alten Werten; danach bleibt die Zeit stehen, der Tab bucht ihn als verpasst. ⚪ kommt einmal aus _eh_ohne, beim Ablauf ein zweites aus alarm_ereignisse. Rechnet eh_tick wieder, stellt er auf route mt5 um, der Riegel greift nicht mehr.
-- REIHENFOLGE: erst Code ausliefern, dann diese Datei. Wiederholbar. Rückbau: drop trigger trade_plans_a1_echo_hedge on public.trade_plans; drop function public.trade_plans_a1_echo_hedge(); drop function public.prophos_echo_fenster_ende(timestamptz);
-- NICHT vom Slave eingespielt.

-- Ende des CFD-Startfensters (zeiten.cfd_bis: {tz, uhr} oder "HH:MM" deutscher Zeit, wie app.py ap_zeit_dt_min), höchstens deutsche Tagesgrenze, je Tag des ersten Halts (Stopp S17 02.11.2026:
-- sonst rollte ein Plan von 17:00 bis 01:00 Dubai und startete Freitagabend am Marktschluss). Unlesbar = nur die Tagesgrenze.
create or replace function public.prophos_echo_fenster_ende(p_erst timestamptz)
returns timestamptz
language plpgsql stable security definer set search_path = public as $$
declare
  cb jsonb;
  tag date := (p_erst at time zone 'Europe/Berlin')::date;
  tag_ende timestamptz := ((tag + 1)::timestamp) at time zone 'Europe/Berlin';
  ende timestamptz;
begin
  select zeiten->'cfd_bis' into cb from public.auto_plan_regeln where id = 1;
  begin
    if jsonb_typeof(cb) = 'object' then
      ende := (tag + (cb->>'uhr')::time) at time zone coalesce(nullif(cb->>'tz', ''), 'Europe/Berlin');
    elsif jsonb_typeof(cb) = 'string' then
      ende := (tag + (cb #>> '{}')::time) at time zone 'Europe/Berlin';
    end if;
  exception when others then
    ende := null;
  end;
  return least(coalesce(ende, tag_ende), tag_ende);
end $$;
revoke all on function public.prophos_echo_fenster_ende(timestamptz) from public, anon, authenticated;

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
  grund text;
begin
  eh := new.mt5_baseline->'echo_hedge';
  if new.status is distinct from 'planned' or not coalesce(new.auto_plan, false) or coalesce(new.route, '') <> 'mt5v2'
     or coalesce(new.start_claim_art, 'start') <> 'start'
     or coalesce(eh->>'status', '') <> 'ohne' or coalesce(eh->>'code', '') not in ('balance', 'lesung', 'groesse')
     or not public.prophos_ht_echo_hedge_an() then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'echo_hedge' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
  end if;
  if ss->>'art' = 'echo_hedge' and ss->>'status' = 'aufgegeben' then
    return null;                                  -- aufgegeben bleibt aufgegeben (Stopp S17): sonst entschiede der Würfel beim nächsten Claim neu, obwohl ⚪ „neu planen“ schon raus ist
  end if;
  erst := coalesce(ss->>'art', '') <> 'echo_hedge';
  erst_at := case when erst then now() else coalesce((ss->>'erst_at')::timestamptz, now()) end;
  txt := 'Echo-Hedge nicht rechenbar: ' || left(coalesce(eh->>'grund', '?'), 160);
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  -- Aufgeben: 8 h um, oder der nächste Versuch läge hinter dem Fensterende. Zeit bleibt stehen, der Tab bucht den Plan als verpasst; eh_tick stellt ihn nicht mehr um (⚪ aus alarm_ereignisse).
  grund := case when erst_at < now() - interval '8 hours' then '8h'
                when ziel >= public.prophos_echo_fenster_ende(erst_at) then 'fenster' end;
  if grund is not null then
    if erst or coalesce(ss->>'status', '') <> 'aufgegeben' then
      update public.trade_plans
         set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
               'art', 'echo_hedge', 'status', 'aufgegeben', 'ablauf', grund, 'text', txt, 'at', now(), 'erst_at', erst_at,
               'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
       where id = new.id;
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, old.start_um,
              '[Echo ohne Hedge aufgegeben] ' || txt || case when grund = 'fenster' then ' — CFD-Startfenster zu Ende' else ' — nach 8 h' end, 'start');
    end if;
    return null;
  end if;
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
