-- WAAGE-DECKEL (Finn 23.10.2026 ~13:50/13:55 Dubai, live 1 Long : 7 Short im Futures-Buch: „4:1 ist too much, 7:1 sowieso. Dann lieber gar
-- keinen Trade starten. Verschieben geht, kommt ja selten vor." — „Mach die Regel mit ‚würde‘" — ~14:05: „Nie mehr als 2 darf der Abstand sein.
-- 3:1 okay, 4:1 nicht okay. 2:0 okay, 3:0 nicht mehr. Immer 2 darf der Abstand sein.")
--
-- Regel: Ein AUTOMATISCHER Start, nach dem seine Seite im Futures-Buch mehr als waage_max_abstand Trades über der anderen liegt, startet
-- nicht — keine Ausnahme durch „Gegentrade folgt", Paar-Partner, Drehen oder den Topstep-Weg. 3 : 1 / 2 : 0 / 6 : 4 gehen, 4 : 1 / 3 : 0 /
-- 7 : 4 nicht. Ein Start in die leichte Seite ist nie gesperrt. Die weiche Waage bis 2 : 1 (Vorziehen, Drehen in die leichtere Seite) bleibt
-- unverändert darunter. Werte in auto_plan_regeln.regeln.ausgleich (dieselben wie app.py ap_ausgleich_param):
--   waage_max_abstand  Standard 2, geklemmt 1–20
--   waage_deckel_an    Standard an; nur ein echtes false schaltet den Deckel ab (Not-Aus per SQL, Python und DB lesen denselben Schalter)
--
-- Zählweise wie die Waage (app.py ap_klassen_waage / ap_waage_deckel): Klasse Futures (Route tv…/ts…, Echo-Routen mt5/mt5v2 nie, sonst
-- Firmenname wie WD_BALANCE_FUTURES ohne „Tradeify CFD"), ohne Firmen aus regeln.ausgleich.waage_ohne (Standard Apex), nur Konten
-- challenge/phase1/phase2 (AP_TYPEN, also ohne Winning Days/Funded), ohne Hedge (Fusion-Hedge offen/öffnet/schließt, Slave, klassisches
-- Echo mt5, geplant mit hedge_eur > 0), ohne IDs der Gruppen MIT Verwalter (wie app.py _ap_namen/_admin_verwalter_gruppen_ids — die Standard-
-- Sicht von Planer, Waage und Bot; die ADMIN_EXCLUDE-Konten sind heute Verwalter bzw. ohne Pläne). Gezählt werden laufende Trades (status
-- open — review zählt für Long und Short gleich NICHT, wie die Waage-Kachel) und gerade geclaimte, noch nicht gestartete Pläne (Claim
-- ≤ 15 min, AP_WAAGE_CLAIM_MAX_MIN), dazu dieser Start.
--
-- Wo: BEFORE-Trigger auf den Claim (start_um_gestartet_at NULL → gesetzt) — jeder automatische Start läuft über diesen Claim des PC-Tabs
-- (Railway claimt nie selbst; Nachholen/Neu einplanen setzen nur start_um). Hand-Starts per Knopf setzen keinen Claim; Auto-Pläne mit
-- hand_werte_at lässt der Riegel durch (der PC-Tab zeigt dort nur einen Hinweis). Verbrauchs-Claims (start_claim_art = 'verbrauch': Archiv,
-- Manuelle Arbeit, Ziel erreicht, verpasst) bremst er nie.
--   Reihenfolge im Trigger: erst alles, was ohne Zählung entscheidet (Verbrauch, Hand, CFD-Route, Hedge, Schalter, Kontoart, Firma ohne
--   Waage, Verwalter-Gruppe) — ein CFD-, Apex- oder Verbrauchs-Claim berührt die Zählung und den Lock nie; dann Advisory-Lock über die ganze
--   Waage (zwei Claims im selben Moment laufen nacheinander, der zweite sieht den ersten), dann die Zählung. Fail-closed: ein Fehler ab hier
--   lässt den Claim scheitern.
--   Gesperrt → Claim trifft 0 Zeilen; neuer Start wie der PC-Tab (rkVerschieben): jetzt + 10–20 min gewürfelt, nach oben auf das Ende des
--   Startfensters gedeckelt, in dem der erste gesperrte Start lag (zeiten.fenster in zeiten.fenster_tz, außerhalb aller Fenster erster Start
--   + 60 min, wie rkFensterEnde), höchstens bis zur deutschen Tagesgrenze. Passt nicht einmal die Untergrenze mehr → aufgegeben: start_um
--   bleibt (das Aufräumen ap_plan_verfallen sieht ihn), mt5_baseline.richtung_konflikt status 'aufgegeben' wie der Tab — der Start-Takt
--   lässt ihn aus (rkAufgegeben, „startet nur von Hand oder mit neuer Uhrzeit"), „Braucht dich" zeigt ihn. Die eigene Uhr (erster Start,
--   Versuche) steht in mt5_baseline.waage_deckel — start_sperre überschreiben andere Riegel (ein_finaler, gegenhedge). start_sperre art
--   'waage_deckel' bleibt für den Chip an der Karte. Protokoll „[Waage-Deckel]" in auto_plan_umplanung.
-- Der PC-Tab prüft dieselbe Lage vorher über /admin/auto-plan/waage-start (deckel_sperrt) — dieser Riegel ist das Netz für jeden Weg.
-- Idempotent. Die Spalte start_claim_art legt auch sql/2026-10-23_start_claim_art.sql an; hier zur Sicherheit noch einmal (if not exists),
-- damit der Trigger nie auf eine fehlende Spalte trifft, falls die Reihenfolge beim Einspielen vertauscht wird.

alter table public.trade_plans add column if not exists start_claim_art text;

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

-- ── 2. Einstellungen aus regeln.ausgleich ──────────────────────────────────────────────────────────────────────────────────────────
-- -> {an, max_abstand, ohne[]}
create or replace function public.prophos_waage_deckel_param()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  a jsonb;
  v text;
  m numeric := 2;
  ohne text[] := array['apex'];
begin
  select regeln->'ausgleich' into a from public.auto_plan_regeln where id = 1;
  v := btrim(coalesce(a->>'waage_max_abstand', ''));
  if v ~ '^[0-9]+(\.[0-9]+)?$' then
    m := greatest(1, least(20, v::numeric));
  end if;
  if jsonb_typeof(a->'waage_ohne') = 'array' then
    select coalesce(array_agg(lower(btrim(x))) filter (where btrim(x) <> ''), array[]::text[]) into ohne
      from jsonb_array_elements_text(a->'waage_ohne') x;
  end if;
  return jsonb_build_object('an', coalesce(a->'waage_deckel_an', 'true'::jsonb) <> 'false'::jsonb, 'max_abstand', m, 'ohne', to_jsonb(ohne));
end $$;

-- ── 3. IDs außerhalb der Standard-Sicht (Gruppen MIT Verwalter: Verwalter + Mitglieder) ───────────────────────────────────────────
create or replace function public.prophos_waage_ausgeblendet(p_user uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.id_gruppen g where g.verwalter_user_id is not null and g.verwalter_user_id = p_user)
      or exists (select 1 from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
                  where g.verwalter_user_id is not null and m.user_id = p_user)
$$;

-- ── 4. Lage: würde dieser Start das Futures-Buch über den Abstand bringen? ──────────────────────────────────────────────────────────
-- -> {zaehlt, sperrt, n_long, n_short (mit diesem Start), max_abstand, grund}; zaehlt=false (aus, CFD, Apex, WD/Funded, gehedgt, Verwalter-
-- Gruppe) → sperrt=false. Der Trigger prüft „zählt" schon vorher ohne Zählung; hier noch einmal, damit die Funktion allein stimmt (Probe).
create or replace function public.prophos_waage_deckel_lage(p_plan uuid, p_richtung text default null)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  pl record;
  r text;
  pa jsonb := public.prophos_waage_deckel_param();
  max_abstand numeric := (pa->>'max_abstand')::numeric;
  ohne text[] := array(select jsonb_array_elements_text(pa->'ohne'));
  firm text;
  nl int := 0;
  ns int := 0;
  seite int;
  andere int;
begin
  select p.id, p.user_id, p.richtung, p.route, p.master_firm, p.hedge_eur, p.slave_account_id, a.account_type, a.firm
    into pl
    from public.trade_plans p left join public.accounts a on a.id = p.master_account_id
   where p.id = p_plan;
  if not found then
    return jsonb_build_object('zaehlt', false, 'sperrt', false, 'grund', 'Plan unbekannt');
  end if;
  r := coalesce(p_richtung, pl.richtung);
  firm := coalesce(pl.firm, pl.master_firm);
  if not coalesce((pa->>'an')::boolean, true)
     or r not in ('buy', 'sell')
     or coalesce(pl.account_type, '') not in ('challenge', 'phase1', 'phase2')
     or coalesce(pl.hedge_eur, 0) > 0 or pl.slave_account_id is not null or lower(coalesce(pl.route, '')) = 'mt5'
     or not public.prophos_waage_futures(pl.route, firm)
     or exists (select 1 from unnest(ohne) o
                 where strpos(lower(coalesce(public.prophos_firma_key(firm), '') || '|' || coalesce(firm, '')), o) > 0)
     or public.prophos_waage_ausgeblendet(pl.user_id) then
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
     and not public.prophos_waage_ausgeblendet(p.user_id)
     and (p.status = 'open'
          or (p.status = 'planned' and p.started_at is null and coalesce(p.hedge_eur, 0) <= 0
              and p.start_um_gestartet_at > now() - interval '15 minutes'));
  if r = 'buy' then nl := nl + 1; seite := nl; andere := ns; else ns := ns + 1; seite := ns; andere := nl; end if;
  return jsonb_build_object('zaehlt', true, 'sperrt', seite - andere > max_abstand, 'n_long', nl, 'n_short', ns, 'max_abstand', max_abstand,
    'grund', 'Futures würde ' || nl || ' Long : ' || ns || ' Short (Abstand höchstens ' || trim(to_char(max_abstand, 'FM990.##'), '.') || ')');
end $$;

-- ── 5. Ende des Startfensters wie rkFensterEnde, höchstens bis zur deutschen Tagesgrenze ───────────────────────────────────────────
create or replace function public.prophos_waage_fenster_ende(p_erst timestamptz)
returns timestamptz
language plpgsql stable security definer set search_path = public as $$
declare
  z jsonb;
  tz text;
  lokal timestamp;
  m int;
  f jsonb;
  a int;
  b int;
  ende timestamptz := p_erst + interval '60 minutes';   -- außerhalb aller Fenster: erster Start + 60 min (rkFensterEnde)
  tag_ende timestamptz := (date_trunc('day', p_erst at time zone 'Europe/Berlin') + interval '1 day') at time zone 'Europe/Berlin';
begin
  select zeiten into z from public.auto_plan_regeln where id = 1;
  tz := coalesce(nullif(z->>'fenster_tz', ''), nullif(z->>'tz', ''), 'Europe/Berlin');
  lokal := p_erst at time zone tz;
  m := extract(hour from lokal)::int * 60 + extract(minute from lokal)::int;
  if jsonb_typeof(z->'fenster') = 'array' then
    for f in select * from jsonb_array_elements(z->'fenster') loop
      begin
        a := split_part(f->>0, ':', 1)::int * 60 + split_part(f->>0, ':', 2)::int;
        b := split_part(f->>1, ':', 1)::int * 60 + split_part(f->>1, ':', 2)::int;
      exception when others then
        continue;
      end;
      if b = 0 then b := 1440; end if;
      if m >= a and m < b then
        ende := (date_trunc('day', lokal) + make_interval(mins => b)) at time zone tz;
        exit;
      end if;
    end loop;
  end if;
  return least(ende, tag_ende);
end $$;

-- nur der Trigger (security definer) und Proben im SQL-Editor brauchen die Funktionen — kein Aufruf aus dem Tab
revoke all on function public.prophos_waage_deckel_param() from public, anon, authenticated;
revoke all on function public.prophos_waage_ausgeblendet(uuid) from public, anon, authenticated;
revoke all on function public.prophos_waage_deckel_lage(uuid, text) from public, anon, authenticated;
revoke all on function public.prophos_waage_fenster_ende(timestamptz) from public, anon, authenticated;
grant execute on function public.prophos_waage_deckel_param() to service_role;
grant execute on function public.prophos_waage_ausgeblendet(uuid) to service_role;
grant execute on function public.prophos_waage_deckel_lage(uuid, text) to service_role;
grant execute on function public.prophos_waage_fenster_ende(timestamptz) to service_role;

-- ── 6. Claim-Trigger ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.trade_plans_waage_deckel()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  pa jsonb;
  ohne text[];
  typ text;
  firm text;
  lage jsonb;
  wd jsonb := coalesce(new.mt5_baseline, '{}'::jsonb)->'waage_deckel';
  erst timestamptz;
  ende timestamptz;
  n int;
  rest numeric;
  ziel timestamptz;
  txt text;
begin
  -- ── ohne Zählung entscheiden (kein Lock, keine Zählung — CFD/Apex/Verbrauch trifft ein Fehler im Deckel nie) ──
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
  if lower(coalesce(new.route, '')) in ('mt5', 'mt5v2') or coalesce(new.hedge_eur, 0) > 0 or new.slave_account_id is not null then
    return new;                                                   -- CFD-Weg bzw. gehedgt: nie in der Futures-Waage
  end if;
  pa := public.prophos_waage_deckel_param();
  if not coalesce((pa->>'an')::boolean, true) then
    return new;                                                   -- Not-Aus regeln.ausgleich.waage_deckel_an = false
  end if;
  select a.account_type, coalesce(a.firm, new.master_firm) into typ, firm from public.accounts a where a.id = new.master_account_id;
  firm := coalesce(firm, new.master_firm);
  ohne := array(select jsonb_array_elements_text(pa->'ohne'));
  if coalesce(typ, '') not in ('challenge', 'phase1', 'phase2')
     or not public.prophos_waage_futures(new.route, firm)
     or exists (select 1 from unnest(ohne) o where strpos(lower(coalesce(public.prophos_firma_key(firm), '') || '|' || coalesce(firm, '')), o) > 0)
     or public.prophos_waage_ausgeblendet(new.user_id) then
    return new;
  end if;
  -- ── zählen (fail-closed) ──
  perform pg_advisory_xact_lock(hashtext('prophos_waage_deckel'));
  lage := public.prophos_waage_deckel_lage(new.id, new.richtung);
  if not coalesce((lage->>'sperrt')::boolean, false) then
    return new;
  end if;
  -- eigene Uhr in mt5_baseline.waage_deckel (start_sperre überschreiben andere Riegel): erster gesperrter Start, solange er wartet und frisch ist
  if coalesce(wd->>'status', '') = 'wartet' and (wd->>'erst') is not null and (wd->>'erst')::timestamptz > now() - interval '24 hours' then
    erst := (wd->>'erst')::timestamptz;
    n := coalesce((wd->>'versuche')::int, 0) + 1;
  else
    erst := coalesce(old.start_um, now());
    n := 1;
  end if;
  ende := public.prophos_waage_fenster_ende(erst);
  rest := extract(epoch from (ende - now())) / 60.0;
  txt := coalesce(lage->>'grund', 'Futures-Abstand würde über den Deckel') || ' — der '
         || case new.richtung when 'buy' then 'Long' else 'Short' end || ' startet nicht';
  if rest < 10 then
    -- Startfenster bzw. Tag zu Ende: aufgeben wie rkVerschieben — start_um bleibt, Marke wie der Tab, Start nur noch von Hand/neue Uhrzeit
    update public.trade_plans set
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb)
             || jsonb_build_object('waage_deckel', jsonb_build_object('status', 'aufgegeben', 'erst', erst, 'versuche', n, 'at', now(), 'text', txt))
             || jsonb_build_object('start_sperre', jsonb_build_object('art', 'waage_deckel', 'status', 'aufgegeben', 'text', txt, 'at', now(), 'versuche', n))
             || jsonb_build_object('richtung_konflikt', jsonb_build_object('quelle', 'start', 'status', 'aufgegeben', 'um', now(), 'erst_start', erst,
                  'versuche', n, 'gegen', null, 'saldo', true, 'text', '[Waage-Deckel] ' || txt, 'start', old.start_um, 'pc', null))
     where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, old.start_um,
            '[Waage-Deckel] ' || txt || ' — Startfenster endet ' || to_char(ende at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai, aufgegeben (Versuch ' || n
            || '): Plan bleibt Geplant, Start von Hand oder neue Uhrzeit', 'start');
    return null;
  end if;
  -- Jitter-Regel: 10–20 min gewürfelt, nach oben auf das Fensterende gedeckelt (wie rkVerschieben)
  ziel := now() + make_interval(secs => round((10 + random() * greatest(0, least(20, rest) - 10)) * 60)::int);
  update public.trade_plans set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb)
           || jsonb_build_object('waage_deckel', jsonb_build_object('status', 'wartet', 'erst', erst, 'versuche', n, 'at', now(), 'naechster', ziel,
                'ende', ende, 'text', txt))
           || jsonb_build_object('start_sperre', jsonb_build_object('art', 'waage_deckel', 'status', 'wartet', 'text', txt, 'at', now(), 'naechster', ziel,
                'versuche', n))
   where id = new.id;
  insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
  values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
          '[Waage-Deckel] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai (Versuch ' || n
          || ', Fenster bis ' || to_char(ende at time zone 'Asia/Dubai', 'HH24:MI') || ')', 'start');
  return null;
end $$;

drop trigger if exists trade_plans_waage_deckel on public.trade_plans;
create trigger trade_plans_waage_deckel
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_waage_deckel();

notify pgrst, 'reload schema';

-- ── PROBE nach dem Einspielen (nur lesen) ──────────────────────────────────────────────────────────────────────────────────────────
-- Klasse:  select x.r, x.f, public.prophos_waage_futures(x.r, x.f) from (values ('tvv2','Tradeify'), ('tsv2','Topstep'), ('mt5v2','Tradeify CFD'),
--            (null,'Tradeify CFD'), (null,'Apex Trader'), ('mt5','FundedNext')) x(r, f);                        → t, t, f, f, t, f
-- Werte:   select public.prophos_waage_deckel_param();                                → {"an": true, "max_abstand": 2, "ohne": ["apex"]}
-- Fenster: select public.prophos_waage_fenster_ende(now());                          → Fensterende 20:00 Dubai bzw. Tagesgrenze dt
-- Lage je geplantem Futures-Plan heute (wie würde ein Start jetzt stehen):
--   select left(id::text, 8), master_firm, richtung, public.prophos_waage_deckel_lage(id) from public.trade_plans
--    where status = 'planned' and start_um::date = current_date and route in ('tvv2', 'tsv2') order by start_um limit 20;
-- Protokoll:  select um, left(plan_id::text, 8), grund from public.auto_plan_umplanung where grund like '[Waage-Deckel]%' order by um desc limit 20;
-- Not-Aus:    update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{ausgleich,waage_deckel_an}', 'false'), updated_at = now() where id = 1;
