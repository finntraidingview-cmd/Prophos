-- GEGENHEDGE AUCH ÜBER KONTEN DERSELBEN ID (08.10.2026, Slave-Terminal 4 — Master: Finn fragt, ob der Gegenhedge-Schutz bei JEDEM Start
-- greift; Lücke: prophos_gegenhedge_konflikt prüfte nur ANDERE IDs (p.user_id is distinct from p_user). Ein zweites Konto DERSELBEN ID bei
-- derselben Firma in Gegenrichtung (z. B. Hand-Trade) ging durch — für die Firma ist das genauso ein Hedge. Finn 08.10.2026: „bei der
-- Prop-Firm nur in eine Richtung, nicht gegenseitig hedgen".)
--
-- Ersetzt die drei Funktionen aus sql/2026-10-08_gegenhedge_riegel.sql (gleiche Signaturen und Rückgabetypen, Trigger bleibt stehen):
--   prophos_gegenhedge_konflikt: jetzt auch dieselbe ID mit ANDEREM Konto (master_account_id ≠ das des eigenen Plans; das eigene Konto wird
--     aus p_id gelesen, die Signatur bleibt). Dasselbe Konto bleibt außen vor (dort gilt der Richtungsschutz rkVorStart). Ohne Konto
--     (master_account_id NULL auf einer Seite) zählt immer als anderes Konto — lieber sperren als durchlassen (Prüfer Slave 2).
--     Grund bei derselben ID: „„<Kontoname>" läuft dort in Gegenrichtung …" bzw. „„<Kontoname>" startet dort um … in Gegenrichtung".
--   trade_plans_gegenhedge (Claim-Trigger) und prophos_gegenhedge_halten (RPC vor jedem Start): Texte „eine andere ID …" bzw. bei
--     derselben ID „dein Konto …" — die RPC liefert dann wer = 'dein Konto', der PC-Tab zeigt „wartet: dein Konto „…" läuft dort …".
--   Dazu HAND-POSITIONEN (Slave 1, Tabelle public.fremd_positionen aus sql/2026-10-08_fremd_positionen.sql — Trades, die Finn direkt in
--     TradingView/MT5 klickt): eine offene Hand-Position derselben Firma in Gegenrichtung (weg_at null, zuletzt_gesehen ≤ 3 min) sperrt
--     jede ID und jedes Konto, Ziel jetzt + 5 min (der app.py-Takt bewertet die Position dann neu). Grund „Hand-Position „<Konto>" läuft
--     dort in Gegenrichtung …", Texte „eine Hand-Position …". to_regclass-Riegel: diese Datei darf VOR der Tabelle eingespielt werden.
-- Sonst unverändert: Fenster 30 min, „der Spätere weicht", Advisory-Lock je Firma wie der Firmen-Abstand, Protokoll auto_plan_umplanung.
-- Heute live 0 Fälle (Master 08.10.2026: 0 Gegenhedges offen, 0 gleiche ID × Firma mit zwei Richtungen).
--
-- VORAUSSETZUNG: sql/2026-10-08_gegenhedge_riegel.sql ist eingespielt. Wiederholbar. Rückbau: sql/2026-10-08_gegenhedge_riegel.sql erneut
-- einspielen (stellt die alten Funktionsrümpfe her).

do $pruef$
begin
  perform 'public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-08_gegenhedge_riegel.sql einspielen (prophos_gegenhedge_konflikt fehlt)';
end $pruef$;

create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)
returns table(ziel timestamptz, wer uuid, grund text)
language plpgsql stable security definer set search_path = public as $$
declare
  k text := public.prophos_firma_key(p_firma);
  gegen text := case p_richtung when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  konto uuid;
  t timestamptz;
  u uuid;
  n text;
begin
  if gegen is null or coalesce(btrim(p_firma), '') = '' then
    return;
  end if;
  select master_account_id into konto from public.trade_plans where id = p_id;
  -- (a) eine andere ID ODER ein anderes Konto derselben ID läuft gegenläufig (oder der Start ist gerade unterwegs)
  select coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now()), p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if t is not null then
    return query select now() + interval '30 minutes', u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'läuft dort in Gegenrichtung (seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)';
    return;
  end if;
  -- (a2) offene Hand-Position derselben Firma in Gegenrichtung (Slave 1, fremd_positionen) — jede ID, jedes Konto
  if to_regclass('public.fremd_positionen') is not null then
    execute 'select f.seit, f.user_id, f.konto_name from public.fremd_positionen f
              where f.firma_key = $1 and f.richtung = $2 and f.weg_at is null and f.zuletzt_gesehen > now() - interval ''3 minutes''
              order by f.seit desc limit 1'
      into t, u, n using k, gegen;
    if t is not null then
      return query select now() + interval '5 minutes', u,
        'Hand-Position „' || coalesce(n, '?') || '“ läuft dort in Gegenrichtung (seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)';
      return;
    end if;
  end if;
  -- (b) eine andere ID oder ein anderes Konto derselben ID startet gegenläufig früher (bestätigt/Hand, noch nicht geclaimt, ≤ 30 min alt)
  select p.start_um, p.user_id, p.master_name
    into t, u, n
    from public.trade_plans p
   where p.id <> p_id
     and (p.user_id is distinct from p_user or konto is null or p.master_account_id is null or p.master_account_id is distinct from konto)
     and p.richtung = gegen
     and p.status = 'planned'
     and p.start_um_gestartet_at is null
     and (not coalesce(p.auto_plan, false) or p.auto_bestaetigt_at is not null)
     and p.start_um >= now() - interval '30 minutes'
     and (p.start_um < p_ref or (p.start_um = p_ref and p.id < p_id))
     and public.prophos_firma_key(p.master_firm) = k
   order by p.start_um desc
   limit 1;
  if t is not null then
    return query select greatest(t + interval '30 minutes', now() + interval '5 minutes'), u,
      case when u = p_user then '„' || coalesce(n, 'Konto') || '“ ' else '' end
      || 'startet dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung';
  end if;
end $$;
revoke all on function public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz) from public;

create or replace function public.trade_plans_gegenhedge() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  c record;
  ziel timestamptz;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' or new.richtung not in ('buy', 'sell') then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;                                   -- „verpasst"-Claim: startet nichts, nicht aufhalten
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));   -- derselbe Lock wie der Firmen-Abstand
  select * into c from public.prophos_gegenhedge_konflikt(new.id, new.user_id, new.master_firm, new.richtung, coalesce(old.start_um, now()));
  if c.ziel is null then
    return new;                                   -- frei: Claim normal schreiben
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 70));
  if old.start_um is null or old.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel where id = new.id;   -- Spalte start_um: kein Claim-Trigger feuert dafür
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Gegenhedge] ' || k || ': ' || case when c.grund like 'Hand-Position%' then 'eine ' when c.wer = new.user_id then 'dein Konto '
                                                 else 'eine andere ID ' end || c.grund
            || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$;

create or replace function public.prophos_gegenhedge_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pl public.trade_plans%rowtype;
  k text;
  c record;
  ziel timestamptz;
  name text;
begin
  select * into pl from public.trade_plans where id = p_plan;
  if not found or pl.user_id is distinct from auth.uid() then
    return jsonb_build_object('frei', true, 'grund', 'kein eigener Plan');
  end if;
  if pl.status is distinct from 'planned' or coalesce(btrim(pl.master_firm), '') = '' or pl.richtung not in ('buy', 'sell') then
    return jsonb_build_object('frei', true);
  end if;
  if pl.started_at is not null or pl.orbit_gesendet_at is not null then
    return jsonb_build_object('frei', true, 'grund', 'Order schon gesendet — kein Eingriff');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  select * into c from public.prophos_gegenhedge_konflikt(pl.id, pl.user_id, pl.master_firm, pl.richtung, coalesce(pl.start_um, now()));
  if c.ziel is null then
    return jsonb_build_object('frei', true);
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 70));
  if c.grund like 'Hand-Position%' then
    name := 'eine';                                                                -- „eine Hand-Position „…" läuft dort …" (Slave 1)
  elsif c.wer = pl.user_id then
    name := 'dein Konto';                                                          -- gleiche ID, anderes Konto (08.10.2026)
  else
    select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(c.wer::text, 8))
      into name from auth.users u where u.id = c.wer;                              -- nur Vorname, nie E-Mail
  end if;
  if pl.start_um is null or pl.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;   -- orbit_gesendet_at nie
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Gegenhedge] ' || k || ': ' || coalesce(name, 'andere ID') || ' ' || c.grund || ' — Start (Neu starten/von Hand) wartet bis '
            || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'grund', c.grund);
end $$;

revoke all on function public.prophos_gegenhedge_halten(uuid) from public;
grant execute on function public.prophos_gegenhedge_halten(uuid) to authenticated;
