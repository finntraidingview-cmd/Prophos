-- RICHTUNGSSCHUTZ BEIM POLAR-START (Finn 20.10.2026 02:30 Dubai, über den Master): „Vor dem Start für BEIDE Konten den bestehenden
-- Gegenrichtungs-Riegel fragen — Master-ID × Futures-Firma mit der Master-Richtung, Slave-ID × CFD-Firma mit der Gegenrichtung."
-- Keine neue Regel: prophos_gegenrichtung_frei (sql/2026-10-13_gegenrichtung_hart.sql, _review.sql, 2026-10-19_gegenrichtung_review_gelesen.sql)
-- nimmt bisher nur einen PLAN (p_plan) und liest ID × Firma × Richtung aus dessen Zeile. Die Slave-Seite eines Polar-Laufs hat keinen
-- eigenen Plan (der Polar-Plan gehört der Master-ID) — darum hier dieselbe Prüfung je KONTO-TUPEL (ID, Firma, Richtung), und die alte
-- Plan-Funktion ruft nur noch diese. Eine Regel, zwei Einstiege; Rückgabe-JSON und Texte unverändert (Panel /richtung/frei, Claim-Trigger,
-- order_signale-Riegel, app.py, Tab lesen weiter dieselben Felder).
-- Voraussetzung: 2026-10-19_gegenrichtung_review_gelesen.sql (prophos_plan_gelesen) ist eingespielt — sonst bricht dieses Skript ab.
-- Aufrufer: polar_app.py /polar/plan (Speichern & starten) und /polar/start — fail-closed: ohne „frei: true" für beide Seiten kein Start.
-- Wiederholbar (create or replace). Rückweg: 2026-10-19_gegenrichtung_review_gelesen.sql erneut einspielen (stellt die Plan-Funktion
-- eigenständig wieder her), dann drop function public.prophos_gegenrichtung_frei_konto(uuid, text, text, uuid, uuid).

do $pruef$
begin
  perform 'public.prophos_plan_gelesen(uuid)'::regprocedure;
  perform 'public.prophos_firma_key(text)'::regprocedure;
  perform 'public.prophos_gegenrichtung_frei(uuid, text)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-19_gegenrichtung_review_gelesen.sql einspielen (prophos_plan_gelesen fehlt)';
end $pruef$;

-- ── 1. Die Regel je Konto-Tupel (ID, Firma, Richtung) ─────────────────────────────────────────────────────────────────────────
-- p_ausser_plan / p_ausser_konto: der eigene Plan bzw. das eigene Konto zählen nicht als Gegenseite (wie bisher pl.id / pl.master_account_id).
create or replace function public.prophos_gegenrichtung_frei_konto(p_user uuid, p_firma text, p_richtung text,
                                                                   p_ausser_plan uuid default null, p_ausser_konto uuid default null)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  r text;
  gegen text;
  k text;
  g record;
begin
  r := lower(btrim(coalesce(p_richtung, '')));
  r := case when r in ('buy', 'long', 'kauf') then 'buy' when r in ('sell', 'short', 'verkauf') then 'sell' else null end;
  gegen := case r when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  if p_user is null or gegen is null or coalesce(btrim(p_firma), '') = '' then
    return jsonb_build_object('frei', true, 'grund', 'keine Richtung/Firma');
  end if;
  k := public.prophos_firma_key(p_firma);
  select p.id, p.master_name, p.user_id, p.status,
         coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) as seit
    into g
    from public.trade_plans p
   where (p_ausser_plan is null or p.id <> p_ausser_plan)
     and p.user_id = p_user
     and (p_ausser_konto is null or p.master_account_id is null or p.master_account_id is distinct from p_ausser_konto)
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
  return jsonb_build_object('frei', false, 'firma', k, 'richtung', r, 'plan', g.id, 'wer', 'dein Konto', 'user_id', p_user,
    'grund', '„' || coalesce(g.master_name, 'Konto') || '“ '
             || case when g.status = 'review' then 'ist dort zu Ende, aber noch nicht gelesen' else 'läuft dort' end
             || coalesce(' (seit ' || to_char(g.seit at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)', '')
             || ' ' || upper(case gegen when 'buy' then 'long' else 'short' end)
             || ' — ' || upper(case r when 'buy' then 'long' else 'short' end) || ' wäre die Gegenrichtung (Selbst-Hedge). Gesperrt, bis '
             || case when g.status = 'review' then 'die Endlesung da ist' else 'er zu und gelesen ist' end);
end $$;

-- ── 2. Die Plan-Funktion ruft nur noch die Regel (Signatur, Rückgabe, Texte unverändert) ──────────────────────────────────────
create or replace function public.prophos_gegenrichtung_frei(p_plan uuid, p_richtung text default null)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  pl record;
begin
  select id, user_id, master_account_id, master_firm, richtung into pl from public.trade_plans where id = p_plan;
  if not found then
    return jsonb_build_object('frei', true, 'grund', 'Plan unbekannt');
  end if;
  return public.prophos_gegenrichtung_frei_konto(pl.user_id, pl.master_firm, coalesce(p_richtung, pl.richtung), pl.id, pl.master_account_id);
end $$;

-- Kontrolle (nur lesen):
-- select public.prophos_gegenrichtung_frei_konto('<user_id>', 'Tradeify', 'buy');
-- select public.prophos_gegenrichtung_frei('<plan_id>', 'sell');
