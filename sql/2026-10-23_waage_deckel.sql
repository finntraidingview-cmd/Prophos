-- WAAGE-DECKEL (Finn 23.10.2026 ~13:50/13:55 Dubai, live 1 Long : 7 Short im Futures-Buch: „4:1 ist too much, 7:1 sowieso. Dann lieber gar
-- keinen Trade starten. Verschieben geht, kommt ja selten vor." — „Mach die Regel mit ‚würde‘" — ~14:05: „Nie mehr als 2 darf der Abstand sein.
-- 3:1 okay, 4:1 nicht okay. 2:0 okay, 3:0 nicht mehr. Immer 2 darf der Abstand sein.")
--
-- Regel: Ein AUTOMATISCHER Start, nach dem seine Seite im Futures-Buch mehr als waage_max_abstand Trades über der anderen liegt, startet
-- nicht — keine Ausnahme durch „Gegentrade folgt", Paar-Partner, Drehen oder den Topstep-Weg. 3 : 1 / 2 : 0 / 6 : 4 gehen, 4 : 1 / 3 : 0 /
-- 7 : 4 nicht. Ein Start in die leichte Seite ist nie gesperrt. Die weiche Waage bis 2 : 1 (Vorziehen, Drehen in die leichtere Seite) bleibt
-- unverändert darunter. Wert: auto_plan_regeln.regeln.ausgleich.waage_max_abstand (Standard 2, geklemmt 1–20) — dieselbe Zahl wie app.py
-- ap_ausgleich_param.
--
-- Zählweise wie die Waage (app.py ap_klassen_waage / ap_waage_deckel): Klasse Futures (Route tv…/ts…, Echo-Routen mt5/mt5v2 nie, sonst
-- Firmenname wie WD_BALANCE_FUTURES ohne „Tradeify CFD"), ohne Firmen aus regeln.ausgleich.waage_ohne (Standard Apex), nur Konten
-- challenge/phase1/phase2 (AP_TYPEN, also ohne Winning Days/Funded), ohne Hedge (Fusion-Hedge offen/öffnet/schließt, Slave, klassisches
-- Echo mt5, geplant mit hedge_eur > 0). Gezählt werden laufende Trades (status open — review zählt für Long und Short gleich NICHT, wie die
-- Waage-Kachel) und gerade geclaimte, noch nicht gestartete Pläne (Claim ≤ 15 min), dazu dieser Start.
--
-- Wo: BEFORE-Trigger auf den Claim (start_um_gestartet_at NULL → gesetzt) — jeder automatische Start läuft über diesen Claim des PC-Tabs
-- (Railway claimt nie selbst; Nachholen/Neu einplanen setzen nur start_um). Hand-Starts per Knopf setzen keinen Claim; Auto-Pläne mit
-- hand_werte_at lässt der Riegel durch (der PC-Tab zeigt dort nur einen Hinweis). Gesperrt → Claim trifft 0 Zeilen, start_um +10–20 min
-- gewürfelt (Jitter-Regel), mt5_baseline.start_sperre art 'waage_deckel', Protokoll „[Waage-Deckel]" in auto_plan_umplanung. Nach 120 min
-- ohne Platz (ab dem ersten Riegel) gibt er auf: start_um = NULL, der Plan bleibt Geplant (Start von Hand), Protokoll. Fail-closed: ein
-- Fehler in der Prüfung lässt den Claim scheitern. Advisory-Lock über die ganze Waage: zwei Claims im selben Moment laufen nacheinander,
-- der zweite sieht den ersten (READ COMMITTED, Prüfung NACH dem Lock). Trigger-Name nach Alphabet als letzter der Claim-Riegel.
-- Der PC-Tab prüft dieselbe Lage vorher über /admin/auto-plan/waage-start (deckel_sperrt) und verschiebt mit seinem Startfenster — dieser
-- Riegel ist das Netz für jeden anderen Weg. Idempotent (create or replace / drop trigger if exists).
-- VORAUSSETZUNG: sql/2026-10-23_start_claim_art.sql ZUERST einspielen (Spalte start_claim_art) — der Trigger liest sie; ohne Spalte scheiterte
-- jeder Claim. Verbrauchs-Claims (start_claim_art = 'verbrauch': Archiv, Manuelle Arbeit, Ziel erreicht, verpasst) bremst er nie.

-- ── 1. Klasse Futures (wie app.py ap_klasse + _ist_tradeify_cfd) ─────────────────────────────────────────────────────────────────────
create or replace function public.prophos_waage_futures(p_route text, p_firm text)
returns boolean
language plpgsql immutable as $$
declare
  r text := lower(btrim(coalesce(p_route, '')));
  f text := lower(btrim(coalesce(p_firm, '')));
  n text := regexp_replace(lower(coalesce(p_firm, '')), '[^a-z0-9]', '', 'g');
begin
  if r in ('mt5v2', 'mt5') then return false; end if;          -- AP_CFD_ROUTEN
  if r like 'tv%' or r like 'ts%' then return true; end if;     -- TradingView / TopstepX
  if f = '' then return false; end if;
  if strpos(n, 'tradeify') > 0 and strpos(n, 'cfd') > 0 then return false; end if;   -- Tradeify CFD (23.10.2026) ist CFD
  return strpos(f, 'tradeify') > 0 or strpos(f, 'apex') > 0 or strpos(f, 'topstep') > 0 or strpos(f, 'futur') > 0
      or strpos(f, 'mffu') > 0 or strpos(f, 'lucid') > 0 or strpos(f, 'alpha future') > 0 or strpos(f, 'alphafutures') > 0;
end $$;

-- ── 2. Lage: würde dieser Start das Futures-Buch über den Deckel bringen? ───────────────────────────────────────────────────────────────
-- -> {zaehlt, sperrt, n_long, n_short (mit diesem Start), max_abstand, grund}; zaehlt=false (CFD, Apex, WD/Funded, gehedgt) → sperrt=false
create or replace function public.prophos_waage_deckel_lage(p_plan uuid, p_richtung text default null)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  pl record;
  r text;
  reg jsonb;
  v text;
  max_abstand numeric := 2;
  ohne text[] := array['apex'];
  firm text;
  nl int := 0;
  ns int := 0;
  seite int;
  andere int;
begin
  select p.id, p.richtung, p.route, p.master_firm, p.hedge_eur, p.slave_account_id, a.account_type, a.firm
    into pl
    from public.trade_plans p left join public.accounts a on a.id = p.master_account_id
   where p.id = p_plan;
  if not found then
    return jsonb_build_object('zaehlt', false, 'sperrt', false, 'grund', 'Plan unbekannt');
  end if;
  r := coalesce(p_richtung, pl.richtung);
  select regeln into reg from public.auto_plan_regeln where id = 1;
  v := btrim(coalesce(reg->'ausgleich'->>'waage_max_abstand', ''));
  if v ~ '^[0-9]+(\.[0-9]+)?$' then
    max_abstand := greatest(1, least(20, v::numeric));
  end if;
  if jsonb_typeof(reg->'ausgleich'->'waage_ohne') = 'array' then
    select coalesce(array_agg(lower(btrim(x))) filter (where btrim(x) <> ''), array[]::text[]) into ohne
      from jsonb_array_elements_text(reg->'ausgleich'->'waage_ohne') x;
  end if;
  firm := coalesce(pl.firm, pl.master_firm);
  if r not in ('buy', 'sell')
     or coalesce(pl.account_type, '') not in ('challenge', 'phase1', 'phase2')
     or coalesce(pl.hedge_eur, 0) > 0 or pl.slave_account_id is not null or lower(coalesce(pl.route, '')) = 'mt5'
     or not public.prophos_waage_futures(pl.route, firm)
     or exists (select 1 from unnest(ohne) o
                 where strpos(lower(coalesce(public.prophos_firma_key(firm), '') || '|' || coalesce(firm, '')), o) > 0) then
    return jsonb_build_object('zaehlt', false, 'sperrt', false, 'max_abstand', max_abstand);
  end if;
  select count(*) filter (where p.richtung = 'buy'), count(*) filter (where p.richtung = 'sell')
    into nl, ns
    from public.trade_plans p left join public.accounts a on a.id = p.master_account_id
   where p.id <> pl.id
     and p.richtung in ('buy', 'sell')
     and coalesce(a.account_type, '') in ('challenge', 'phase1', 'phase2')
     and p.slave_account_id is null
     and lower(coalesce(p.route, '')) <> 'mt5'
     and coalesce(p.mt5_baseline->'hedge'->>'status', '') not in ('offen', 'oeffnet', 'schliesst')
     and public.prophos_waage_futures(p.route, coalesce(a.firm, p.master_firm))
     and not exists (select 1 from unnest(ohne) o
                      where strpos(lower(coalesce(public.prophos_firma_key(coalesce(a.firm, p.master_firm)), '') || '|'
                                         || coalesce(a.firm, p.master_firm, '')), o) > 0)
     and (p.status = 'open'
          or (p.status = 'planned' and p.started_at is null and coalesce(p.hedge_eur, 0) <= 0
              and p.start_um_gestartet_at > now() - interval '15 minutes'));
  if r = 'buy' then nl := nl + 1; seite := nl; andere := ns; else ns := ns + 1; seite := ns; andere := nl; end if;
  return jsonb_build_object('zaehlt', true, 'sperrt', seite - andere > max_abstand, 'n_long', nl, 'n_short', ns, 'max_abstand', max_abstand,
    'grund', 'Futures würde ' || nl || ' Long : ' || ns || ' Short (Abstand höchstens ' || trim(to_char(max_abstand, 'FM990.##'), '.') || ')');
end $$;
grant execute on function public.prophos_waage_futures(text, text) to authenticated, service_role;
grant execute on function public.prophos_waage_deckel_lage(uuid, text) to authenticated, service_role;

-- ── 3. Claim-Trigger ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.trade_plans_waage_deckel()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  lage jsonb;
  alt jsonb := coalesce(new.mt5_baseline, '{}'::jsonb)->'start_sperre';
  erst timestamptz;
  n int;
  ziel timestamptz;
  txt text;
begin
  if new.status is distinct from 'planned' or new.auto_plan is not true or new.hand_werte_at is not null
     or coalesce(new.richtung, '') not in ('buy', 'sell') then
    return new;
  end if;
  -- VERBRAUCH NIE BREMSEN (Master 23.10.2026): Archiv, Manuelle Arbeit, Ziel erreicht, verpasst schließen den Plan nur ab — „Ziel erreicht =
  -- kein Start" darf nie in ein Verschieben kippen (sql/2026-10-23_start_claim_art.sql, der Tab schreibt 'verbrauch' im selben Update)
  if coalesce(new.start_claim_art, '') = 'verbrauch' then
    return new;
  end if;
  -- ÜBERGANG (Tab noch ohne Feld, NULL): ein Claim lange nach der Startzeit ist der „verpasst"-Verbrauch des Tabs (pulsStartFenster 30 min;
  -- die 60 min des Winning-Days-Farmers zählen hier nicht, WD ist keine AP_TYPEN-Kontoart) — durchlassen, nie verschieben (ein verschobener
  -- „verpasst" sähe beim nächsten Tick wie ein pünktlicher Start aus). Schwelle 25 statt 30 min: Puffer für eine vorgehende PC-Uhr. Ziel/
  -- Manuell/Archiv eines alten Tabs werden höchstens verschoben und beim nächsten Tick vom Tab VOR jedem Start neu erkannt (planKontoSperre).
  if new.start_claim_art is null and old.start_um is not null and old.start_um < now() - interval '25 minutes' then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_waage_deckel'));
  lage := public.prophos_waage_deckel_lage(new.id, new.richtung);
  if not coalesce((lage->>'sperrt')::boolean, false) then
    return new;
  end if;
  if coalesce(alt->>'art', '') = 'waage_deckel' then
    erst := coalesce((alt->>'erst')::timestamptz, old.start_um, now());
    n := coalesce((alt->>'versuche')::int, 0) + 1;
  else
    erst := coalesce(old.start_um, now());
    n := 1;
  end if;
  txt := coalesce(lage->>'grund', 'Futures-Abstand würde über den Deckel') || ' — der '
         || case new.richtung when 'buy' then 'Long' else 'Short' end || ' startet nicht';
  if now() > erst + interval '120 minutes' then
    -- 120 min ohne Platz: aufgeben — Plan bleibt Geplant, ohne Startzeit (Start von Hand), nichts startet still später
    update public.trade_plans set start_um = null,
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
             'art', 'waage_deckel', 'status', 'aufgegeben', 'text', txt, 'at', now(), 'erst', erst, 'versuche', n))
     where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, null,
            '[Waage-Deckel] ' || txt || ' — seit ' || to_char(erst at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai kein Platz, aufgegeben: Plan bleibt Geplant, Start von Hand', 'start');
    return null;
  end if;
  -- Jitter-Regel: gewürfelt 10–20 min, nie ein fester Takt
  ziel := now() + interval '10 minutes' + make_interval(secs => floor(random() * 600));
  update public.trade_plans set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'waage_deckel', 'status', 'wartet', 'text', txt, 'at', now(), 'naechster', ziel, 'erst', erst, 'versuche', n))
   where id = new.id;
  insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
  values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
          '[Waage-Deckel] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai (Versuch ' || n || ')', 'start');
  return null;
end $$;

drop trigger if exists trade_plans_waage_deckel on public.trade_plans;
create trigger trade_plans_waage_deckel
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_waage_deckel();

-- ── PROBE nach dem Einspielen (nur lesen) ──────────────────────────────────────────────────────────────────────────────────────────
-- Klasse:  select x.r, x.f, public.prophos_waage_futures(x.r, x.f) from (values ('tvv2','Tradeify'), ('tsv2','Topstep'), ('mt5v2','Tradeify CFD'),
--            (null,'Tradeify CFD'), (null,'Apex Trader'), ('mt5','FundedNext')) x(r, f);                        → t, t, f, f, t, f
-- Lage je geplantem Futures-Plan heute (wie würde ein Start jetzt stehen):
--   select left(id::text, 8), master_firm, richtung, public.prophos_waage_deckel_lage(id) from public.trade_plans
--    where status = 'planned' and start_um::date = current_date and route in ('tvv2', 'tsv2') order by start_um limit 20;
-- Protokoll:  select um, left(plan_id::text, 8), grund from public.auto_plan_umplanung where grund like '[Waage-Deckel]%' order by um desc limit 20;
