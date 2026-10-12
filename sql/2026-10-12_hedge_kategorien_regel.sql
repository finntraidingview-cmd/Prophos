-- HEDGE-KATEGORIEN-REGEL (12.10.2026, Finn: „das System soll ganz klar zwischen Trades mit Hedge und ohne Hedge unterscheiden"):
--   1. Challenge / Phase 1 / Phase 2 laufen IMMER ohne Hedge (Echo V2 · Orbit V2 · Topstep V2, automatischer Trade-Plan).
--   2. Funded / Funded CFD / Winning Days laufen IMMER mit Hedge (Echo · Orbit V3 · Winning Day · Topstep mit Hedge).
--      Einzige Ausnahme nach oben: der Schalter „Challenges mit Hedge" (user_settings 'tp_challenges_mit_hedge', 09.10.2026 für
--      Amirs Echo-Instanzen auf Phase-1/2-Konten) — mit ihm darf eine Challenge MIT Hedge laufen. Nach unten gibt es keine Ausnahme.
--   3. Echo (MT5) darf beliebig viele Hedge-Trades gleichzeitig fahren — alle Terminals sind offen, der Copier sieht jedes Konto.
--   4. Orbit und Topstep (Finn: „Topstep zählt zu Orbit"): höchstens EIN Big Trade (Hedge-Weg) je Fenster gleichzeitig — das
--      Tampermonkey-Lesen (Reader) sieht nur das eingeloggte Konto, der Hedge-Beweis braucht es lückenlos. Grenze ist das Fenster
--      der ID (ein PC = eine ID = ein TradingView-/TopstepX-Fenster), nicht die Firma. Puls darf währenddessen für andere Konten
--      Orders setzen (Rückfall: Radar-Spiegel + Notfall-SL) und kehrt danach ins Big-Trade-Konto zurück (PC-Tab, bigTradeHeim).
-- Befund vor dieser Datei (letzte 14 Tage): 20 Funded-Pläne von Hand ohne Hedge (mt5v2/tvv2/tsv2), 14 Challenge-Pläne mit Hedge
-- ohne Schalter — alle von Hand, keiner vom Auto-Planer (der plant nur AP_TYPEN challenge/phase1/phase2 über V2-Wege).
--
-- Bausteine:
--   prophos_hedge_weg(route, hedge_eur, orbit_v3, winning_day) → true (mit Hedge) / false (ohne) / null (Weg unbekannt)
--   prophos_big_trade(route, hedge_eur, orbit_v3, winning_day) → Big Trade im Fenster = tvv2/tsv2 MIT Hedge (Orbit V3, Winning Day,
--       Fusion-Hedge, Topstep mit Hedge). tvplus/dup (Duplikum kopiert, kein Reader nötig) zählen NICHT — Puls darf die weiter setzen.
--   Trigger trade_plans_kontoart_weg (insert/update): Regel 1+2 — Fehler mit genauer Ursache + Fix, der Plan wird nicht geschrieben.
--   Trigger trade_plans_big_trade (am Claim, wie Firmen-Abstand/Gegenhedge): Regel 4 — läuft in diesem Fenster schon ein Big Trade,
--       wandert der Start um 15 min (+20–90 s Streuung), Protokoll in auto_plan_umplanung „[Big Trade] …", Claim nicht geschrieben.
--   RPC prophos_big_trade_halten(p_plan) für Hand-Starts/„Neu starten" (faVorStart im PC-Tab fragt sie wie die beiden anderen).
-- Wiederholbar. Rückbau:
--   drop trigger if exists trade_plans_kontoart_weg on public.trade_plans; drop trigger if exists trade_plans_big_trade on public.trade_plans;
--   drop function if exists public.trade_plans_kontoart_weg(); drop function if exists public.trade_plans_big_trade();
--   drop function if exists public.prophos_big_trade_halten(uuid); drop function if exists public.prophos_big_trade_laeuft(uuid, uuid);
--   drop function if exists public.prophos_big_trade(text, numeric, boolean, boolean); drop function if exists public.prophos_hedge_weg(text, numeric, boolean, boolean);

create or replace function public.prophos_hedge_weg(p_route text, p_hedge_eur numeric, p_orbit_v3 boolean, p_winning_day boolean)
returns boolean language sql immutable as $$
  select case
    when coalesce(p_route, '') in ('mt5', 'tvplus', 'dup') then true                           -- Echo, Orbit mit Duplikum, Duplikum manuell
    when coalesce(p_route, '') in ('mt5v2', 'tvv2', 'tsv2')
      then (coalesce(p_hedge_eur, 0) > 0 or coalesce(p_orbit_v3, false) or coalesce(p_winning_day, false))   -- V2 nur mit Fusion/V3/WD
    else null                                                                                   -- Alt-Pläne ohne Weg: keine Aussage
  end
$$;

create or replace function public.prophos_big_trade(p_route text, p_hedge_eur numeric, p_orbit_v3 boolean, p_winning_day boolean)
returns boolean language sql immutable as $$
  select coalesce(p_route, '') in ('tvv2', 'tsv2') and coalesce(public.prophos_hedge_weg(p_route, p_hedge_eur, p_orbit_v3, p_winning_day), false)
$$;

-- ── Regel 1+2: Kontoart ⇒ Weg ─────────────────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.trade_plans_kontoart_weg() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  typ text;
  kname text;
  mit boolean;
  schalter boolean := false;
begin
  if new.master_account_id is null or coalesce(new.status, 'planned') <> 'planned' then
    return new;                                   -- nur neue/geplante Pläne; beendete Alt-Pläne nie anfassen
  end if;
  select lower(coalesce(a.account_type, '')), a.name into typ, kname from public.accounts a where a.id = new.master_account_id;
  if typ is null then
    return new;
  end if;
  mit := public.prophos_hedge_weg(new.route, new.hedge_eur, new.orbit_v3, new.winning_day);
  if mit is null then
    return new;                                   -- Weg unbekannt (Alt-Modell): keine Aussage
  end if;
  if typ in ('funded', 'funded_cfd', 'winning_days') and not mit then
    raise exception 'Funded-Konto „%" nur mit Hedge: Weg % ohne Hedge ist für Challenges — im Trade-Popup Echo, Orbit V3, Winning Day oder Topstep (mit Hedge) wählen.',
      coalesce(kname, '?'), coalesce(new.route, '?')
      using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
  end if;
  if typ in ('challenge', 'phase1', 'phase2') and mit and coalesce(new.route, '') in ('mt5', 'mt5v2', 'tvv2', 'tsv2') then
    select coalesce((s.value->>'an')::boolean, false) into schalter
      from public.user_settings s where s.user_id = new.user_id and s.key = 'tp_challenges_mit_hedge';
    if not coalesce(schalter, false) then
      raise exception 'Challenge-/Phase-Konto „%" nur ohne Hedge: Echo V2, Orbit V2 oder Topstep V2 wählen — oder im Trade-Popup oben „Challenges mit Hedge" einschalten.',
        coalesce(kname, '?')
        using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists trade_plans_kontoart_weg on public.trade_plans;
create trigger trade_plans_kontoart_weg
  before insert or update of route, hedge_eur, orbit_v3, winning_day, master_account_id on public.trade_plans
  for each row execute function public.trade_plans_kontoart_weg();

-- ── Regel 4: ein Big Trade je Fenster ─────────────────────────────────────────────────────────────────────────────────────────────
-- Läuft in diesem Fenster (= dieselbe ID) ein anderer Big Trade? status open, Orbit gesendet (≤ 10 min) oder Claim ohne Start (≤ 2 min).
create or replace function public.prophos_big_trade_laeuft(p_id uuid, p_user uuid)
returns table(plan_id uuid, name text, seit timestamptz)
language sql stable security definer set search_path = public as $$
  select p.id, p.master_name, coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now())
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and public.prophos_big_trade(p.route, p.hedge_eur, p.orbit_v3, p.winning_day)
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
   order by 3 desc
   limit 1
$$;
revoke all on function public.prophos_big_trade_laeuft(uuid, uuid) from public;

create or replace function public.trade_plans_big_trade() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  c record;
  ziel timestamptz;
begin
  if new.status is distinct from 'planned' or not public.prophos_big_trade(new.route, new.hedge_eur, new.orbit_v3, new.winning_day) then
    return new;                                   -- kein Big Trade: Echo, V2 ohne Hedge, Duplikum — nie aufhalten
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;                                   -- „verpasst"-Claim: startet nichts
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_big_trade:' || new.user_id::text));
  select * into c from public.prophos_big_trade_laeuft(new.id, new.user_id);
  if c.plan_id is null then
    return new;
  end if;
  ziel := now() + interval '15 minutes' + make_interval(secs => 20 + floor(random() * 70));
  if old.start_um is null or old.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Big Trade] „' || coalesce(c.name, '?') || '" läuft in diesem Fenster seit ' || to_char(c.seit at time zone 'Asia/Dubai', 'HH24:MI')
            || ' Dubai — Orbit/Topstep nur ein Big Trade gleichzeitig, neue Prüfung ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → der Tab startet nicht
end $$;

drop trigger if exists trade_plans_big_trade on public.trade_plans;
create trigger trade_plans_big_trade
  before update of start_um_gestartet_at on public.trade_plans
  for each row
  when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_big_trade();

-- RPC vor jedem Start (faVorStart): Hand-Starts ohne Claim und „Neu starten" laufen am Claim-Trigger vorbei.
create or replace function public.prophos_big_trade_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pl public.trade_plans%rowtype;
  c record;
  ziel timestamptz;
begin
  select * into pl from public.trade_plans where id = p_plan;
  if not found or pl.user_id is distinct from auth.uid() then
    return jsonb_build_object('frei', true, 'grund', 'kein eigener Plan');
  end if;
  if pl.status is distinct from 'planned' or not public.prophos_big_trade(pl.route, pl.hedge_eur, pl.orbit_v3, pl.winning_day) then
    return jsonb_build_object('frei', true);
  end if;
  if pl.started_at is not null or pl.orbit_gesendet_at is not null then
    return jsonb_build_object('frei', true, 'grund', 'Order schon gesendet — kein Eingriff');
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_big_trade:' || pl.user_id::text));
  select * into c from public.prophos_big_trade_laeuft(pl.id, pl.user_id);
  if c.plan_id is null then
    return jsonb_build_object('frei', true);
  end if;
  ziel := now() + interval '15 minutes' + make_interval(secs => 20 + floor(random() * 70));
  if pl.start_um is null or pl.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Big Trade] „' || coalesce(c.name, '?') || '" läuft in diesem Fenster seit ' || to_char(c.seit at time zone 'Asia/Dubai', 'HH24:MI')
            || ' Dubai — Start (Neu starten/von Hand) wartet bis ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'laeuft', true, 'ziel', ziel, 'wer', coalesce(c.name, '?'), 'seit', c.seit,
                            'grund', 'Big Trade „' || coalesce(c.name, '?') || '" läuft noch in diesem Fenster');
end $$;

revoke all on function public.prophos_big_trade_halten(uuid) from public;
grant execute on function public.prophos_big_trade_halten(uuid) to authenticated;
