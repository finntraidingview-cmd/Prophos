-- REVIEW ZÄHLT NUR UNGELESEN ALS LAUFEND (Finn 19.10.2026 23:55 Dubai): „Solange der beendete Trade nicht vom Auge gelesen wurde, darf
-- kein Trade in Gegenrichtung stattfinden. Die Lesung muss ERFOLGREICH sein — nicht ‚konnte nicht ausgelesen werden wegen …'. Sobald
-- die Lesung erfolgreich war und wir eine Antwort haben, darf die Gegenrichtung starten. Ich muss nicht abhaken."
--
-- Anlass: seit regeln.abhaken_auto aus (19.10.2026 13:55 Dubai, Finn hakt selbst ab) bleiben beendete Pläne in review stehen und
-- sperren die Gegenrichtung derselben ID × Firma bis zum Abhaken (sql/2026-10-13_gegenrichtung_review.sql: review = laufend, 72 h).
-- Befund 19.10.2026 (Slave 4): 199 Umplanungen „[Gegenrichtung gleiche ID] … noch nicht nachgelesen" an einem Tag, 12 Pläne —
-- Marc fe1c95ea (The5%ers) 58× zwischen 09:36 und 19:21 Dubai, Mike c27bef98 (Tradeify) pendelte 18:37–19:24 Long/Short und startete
-- nie, Marco faf338d4/43a02dd4 (Apex) 22×. Die sperrenden reviews waren längst gelesen (ended_at, Endlesung, Balance da).
--
-- Regel: status open zählt unverändert als laufend. status review zählt als laufend, SOLANGE keine erfolgreiche Endlesung vorliegt;
-- liegt sie vor, ist die Gegenrichtung frei — unabhängig vom Abhaken. Ein review ohne Beweis (leeres mt5_baseline, tabelle_unklar,
-- „Stand UNBEKANNT", Login-Fehler, Snapshot eingefroren) bleibt gesperrt, höchstens 72 h wie bisher.
--
-- EINE Definition „gelesen" = prophos_plan_gelesen(plan), aus dem Code abgeleitet (app.py ap_echte_balancen: „Demo-, Hand-, Level- und
-- Reader-Werte zählen nie" — Reader zählt HIER seit 20.10.2026 doch, Finns Wort unten; prophos.html Puls-Endlesung tvV2EndlesungLauf,
-- Echo-Nachlesung mt5BalanceNachlesen, Reader-Flach-Beweis hedgeReaderBalanceEntscheid):
--   • Orbit V2 (tvv2) / TopstepX (tsv2): mt5_baseline.final.quelle = 'puls' — das schreibt NUR die erfolgreiche Puls-Endlesung
--     (erg.ok); scheitert sie, bleibt quelle demo/level/close/reader_leer und final.puls_fehler wird gesetzt — ODER
--     final.balance_quelle = 'reader' (Finn 20.10.2026 01:45 Dubai: „die gleiche Logik wie vom Orbit-Bot und vom Echo-Bot nehmen, die
--     funktioniert schon perfekt, um zu erkennen, ob flach oder nicht"): der PC-Reader hat die Balance aus der TradingView-Zusammenfassung
--     gelesen, mit dem Flach-Beweis des Tabs (hedgeReaderEndBalance: Summary ≤ 2 s alt, Balance = Equity, zweimal gleich); bei 105 von
--     201 Orbit-V2-Plänen (7 Tage) ist das die einzige Lesung, weil der Tab danach keine Puls-Endlesung mehr anstößt — UND jeweils
--     final.balance_end als Zahl > 0 (balance_end allein reicht nicht: Folgetrade/Userscript schreiben es ohne Flach-Beweis).
--   • Echo (mt5, mt5v2): mt5_baseline.final gesetzt (Copier-Schluss) UND bal_nach.ok = true mit bal_nach.balance als Zahl > 0
--     (Nachlesung der Balance am MT5 nach dem Trade; bei Fehlschlag ok=false mit msg/code).
--   • dazu immer ended_at und master_pl gesetzt. Andere Routen (tvplus, …): nie „gelesen" → wie bisher gesperrt bis completed.
-- Geändert: prophos_gegenrichtung_frei + prophos_gegenhedge_konflikt (Zweig „gleiche ID, läuft") lassen gelesene reviews aus.
-- Claim-Trigger trade_plans_gegenhedge, order_signale_gegenrichtung und app.py /richtung/frei bleiben — sie rufen diese Funktionen.
-- Der PC-Tab (v2RichtungKonflikt, rkPlanGelesen) rechnet dieselbe Definition. Wiederholbar (create or replace).
-- Rückweg: sql/2026-10-13_gegenrichtung_review.sql erneut einspielen, dann drop function public.prophos_plan_gelesen(uuid).

do $pruef$
begin
  perform 'public.prophos_gegenrichtung_frei(uuid, text)'::regprocedure;
  perform 'public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz)'::regprocedure;
  perform 'public.prophos_gegenhedge_fenster()'::regprocedure;
  perform 'public.prophos_firma_key(text)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-13_gegenrichtung_hart.sql + _review.sql einspielen';
end $pruef$;

-- ── 1. Die eine Definition „gelesen" ─────────────────────────────────────────────────────────────────────────────────────
create or replace function public.prophos_plan_gelesen(p_plan uuid)
returns boolean
language plpgsql stable security definer set search_path = public as $$
declare
  p record;
  fin jsonb;
  bn jsonb;
  zahl constant text := '^-?[0-9]+(\.[0-9]+)?$';   -- nur echte Zahlen casten, sonst fliegt die Funktion bei „n/a" o. ä.
begin
  select status, route, ended_at, master_pl, mt5_baseline into p from public.trade_plans where id = p_plan;
  if not found or p.status is distinct from 'review' or p.ended_at is null or p.master_pl is null then
    return false;
  end if;
  fin := case when jsonb_typeof(p.mt5_baseline->'final') = 'object' then p.mt5_baseline->'final' end;
  bn  := case when jsonb_typeof(p.mt5_baseline->'bal_nach') = 'object' then p.mt5_baseline->'bal_nach' end;
  if p.route in ('tvv2', 'tsv2') then
    return coalesce(fin is not null and (fin->>'quelle' = 'puls' or fin->>'balance_quelle' = 'reader')
                    and coalesce(fin->>'balance_end', '') ~ zahl and (fin->>'balance_end')::numeric > 0, false);
  elsif p.route in ('mt5', 'mt5v2') then
    return coalesce(fin is not null and bn is not null and bn->>'ok' = 'true'
                    and coalesce(bn->>'balance', '') ~ zahl and (bn->>'balance')::numeric > 0, false);
  end if;
  return false;
end $$;
grant execute on function public.prophos_plan_gelesen(uuid) to authenticated, service_role;

-- ── 2. Reine Leseprüfung: open oder ungelesener review sperrt, gelesener review nicht ──────────────────────────────────────
create or replace function public.prophos_gegenrichtung_frei(p_plan uuid, p_richtung text default null)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  pl record;
  r text;
  gegen text;
  k text;
  g record;
begin
  select id, user_id, master_account_id, master_firm, master_name, richtung, status into pl from public.trade_plans where id = p_plan;
  if not found then
    return jsonb_build_object('frei', true, 'grund', 'Plan unbekannt');
  end if;
  r := lower(btrim(coalesce(p_richtung, pl.richtung, '')));
  r := case when r in ('buy', 'long', 'kauf') then 'buy' when r in ('sell', 'short', 'verkauf') then 'sell' else null end;
  gegen := case r when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  if gegen is null or coalesce(btrim(pl.master_firm), '') = '' then
    return jsonb_build_object('frei', true, 'grund', 'keine Richtung/Firma');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  select p.id, p.master_name, p.user_id, p.status,
         coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) as seit
    into g
    from public.trade_plans p
   where p.id <> pl.id
     and p.user_id = pl.user_id
     and (pl.master_account_id is null or p.master_account_id is null or p.master_account_id is distinct from pl.master_account_id)
     and p.richtung = gegen
     and p.status in ('open', 'review')
     and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))   -- gelesener review sperrt nicht mehr (19.10.2026)
     and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours'
     and public.prophos_firma_key(p.master_firm) = k
   order by 5 desc
   limit 1;
  if g.id is null then
    return jsonb_build_object('frei', true, 'firma', k, 'richtung', r);
  end if;
  return jsonb_build_object('frei', false, 'firma', k, 'richtung', r, 'plan', g.id, 'wer', 'dein Konto', 'user_id', pl.user_id,
    'grund', '„' || coalesce(g.master_name, 'Konto') || '“ '
             || case when g.status = 'review' then 'ist dort zu Ende, aber noch nicht gelesen' else 'läuft dort' end
             || coalesce(' (seit ' || to_char(g.seit at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)', '')
             || ' ' || upper(case gegen when 'buy' then 'long' else 'short' end)
             || ' — ' || upper(case r when 'buy' then 'long' else 'short' end) || ' wäre die Gegenrichtung (Selbst-Hedge). Gesperrt, bis '
             || case when g.status = 'review' then 'die Endlesung da ist' else 'er zu und gelesen ist' end);
end $$;
grant execute on function public.prophos_gegenrichtung_frei(uuid, text) to authenticated, service_role;

-- ── 3. Konflikt-Funktion: Zweig „gleiche ID, läuft" mit derselben Definition; alles danach unverändert ─────────────────────
create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)
returns table(ziel timestamptz, wer uuid, grund text)
language plpgsql stable security definer set search_path = public as $$
declare
  k text := public.prophos_firma_key(p_firma);
  gegen text := case p_richtung when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  f interval := public.prophos_gegenhedge_fenster();
  konto uuid;
  t timestamptz;
  u uuid;
  n text;
begin
  if gegen is null or coalesce(btrim(p_firma), '') = '' then
    return;
  end if;
  select master_account_id into konto from public.trade_plans where id = p_id;
  select coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at), p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id = p_user
     and (konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status in ('open', 'review')
     and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))   -- gelesener review sperrt nicht mehr (19.10.2026)
     and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours'
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if u is not null then
    return query select now() + interval '10 minutes', u,
      '„' || coalesce(n, 'Konto') || '“ läuft dort' || coalesce(' seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai', '')
      || ' in Gegenrichtung (oder ist zu Ende und noch nicht gelesen) — gegen den laufenden Trade gesperrt, bis die Endlesung da ist';
    return;
  end if;
  select greatest(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at), p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status in ('planned', 'open')
     and greatest(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if t is not null then
    return query select t + f, u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'hat dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung gestartet';
    return;
  end if;
  if to_regclass('public.fremd_positionen') is not null then
    execute 'select f.seit, f.user_id, f.konto_name from public.fremd_positionen f
              where f.firma_key = $1 and f.richtung = $2 and f.weg_at is null and f.seit > now() - $3
              order by f.seit desc limit 1'
      into t, u, n using k, gegen, f;
    if t is not null then
      return query select t + f, u,
        'Hand-Position „' || coalesce(n, '?') || '“ wurde dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung eröffnet';
      return;
    end if;
  end if;
  select p.start_um, p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status = 'planned'
     and p.start_um_gestartet_at is null
     and (not coalesce(p.auto_plan, false) or p.auto_bestaetigt_at is not null)
     and p.start_um >= p_ref - f
     and p.start_um >= now() - f
     and (p.start_um < p_ref or (p.start_um = p_ref and p.id < p_id))
     and public.prophos_firma_key(p.master_firm) = k
   order by p.start_um desc
   limit 1;
  if t is not null then
    return query select greatest(t + f, now() + interval '30 seconds'), u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'startet dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung';
  end if;
end $$;

-- PROBE (nur lesen, nach dem Einspielen): welche reviews gelten als gelesen (= sperren nicht mehr), welche nicht.
-- select left(p.id::text, 8), p.route, p.master_firm, p.richtung, public.prophos_plan_gelesen(p.id) as gelesen,
--        p.mt5_baseline->'final'->>'quelle' as final_quelle, p.mt5_baseline->'final'->>'balance_quelle' as balance_quelle,
--        p.mt5_baseline->'bal_nach'->>'ok' as bal_nach_ok
--   from public.trade_plans p where p.status = 'review' order by p.user_id;
