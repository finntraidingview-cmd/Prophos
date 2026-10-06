-- Vorrat-KI über SQL statt Railway (06.10.2026)
--
-- Anlass: Die Cloud-Routine „Vorrat-KI“ kommt nicht an Railway heran (Netz-Allowlist der Claude-Cloud).
-- Sie liest und schreibt deshalb über den Supabase-Connector (execute_sql, läuft als postgres).
-- Die beiden Funktionen tun EXAKT das, was die Railway-Routen tun:
--   vorrat_ki_fakten()                         ≙ GET  /admin/vorrat/lauf  (neuester Lauf mit Ergebnis, kompakt)
--   vorrat_ki_schreiben(lauf_id, text, zeilen) ≙ POST /admin/vorrat/ki    (Prüfung wie vorrat_ki_pruefen in app.py)
-- Ändert sich vorrat_ki_pruefen oder die Speicherform in app.py, muss diese Datei mitziehen.
--
-- Kein REST-Zugriff: execute nur für den Eigentümer (postgres) und service_role (Supabase-Standardrecht,
-- der Schlüssel liegt nur auf Railway). public/anon/authenticated bekommen es ausdrücklich entzogen.
--
-- Aufrufe der Routine:
--   select public.vorrat_ki_fakten();
--   select public.vorrat_ki_schreiben(<lauf_id>, '<text>', '{"<user_id>|<firma>": {"heute": 1, "einheit": "100k", "prio": "hoch", "satz": "…"}}'::jsonb);


-- ─── 1. Fakten ──────────────────────────────────────────────────────────────
-- Neuester Lauf mit Ergebnis — sortiert nach at (dann id), wie die Route: ein nachgeholter Takt kann eine kleinere id haben.
-- Kompakt: nur die Felder, die die KI braucht. fakten_text fasst die Konten schon in Klartext zusammen; konten[] kommt
-- ohne Namen/IDs (stehen in fakten_text bzw. braucht die KI nicht) und mit gerundeten Zahlen.
create or replace function public.vorrat_ki_fakten()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  with l as (
    select id, at, ergebnis, ki_um
      from vorrat_lauf
     where ergebnis is not null
     order by at desc, id desc
     limit 1
  ), e as (
    select coalesce(parameter, '{}'::jsonb) as p from vorrat_einstellung where id = 1
  )
  select case when l.id is null then jsonb_build_object('ok', false, 'fehler', 'kein Lauf')
  else jsonb_build_object(
    'ok', true,
    'lauf_id', l.id,
    'at', l.at,
    'gerechnet_um', l.ergebnis->'gerechnet_um',
    'ki_um', l.ki_um,                                    -- schon beantwortet? (null = nein)
    'grenzen', jsonb_build_object(
        'max_tag',   coalesce(nullif((select p->>'ki_max_tag'   from e), '')::int, 30),
        'max_zelle', coalesce(nullif((select p->>'ki_max_zelle' from e), '')::int, 5)),
    -- Finns Hinweise an den KI-Bot — nur Objekte, wie _vorrat2_ki_hinweise
    'ki_hinweise', coalesce((select jsonb_agg(h) from e, jsonb_array_elements(
                     case when jsonb_typeof(e.p->'ki_hinweise') = 'array' then e.p->'ki_hinweise' else '[]'::jsonb end) h
                    where jsonb_typeof(h) = 'object'), '[]'::jsonb),
    'zellen', coalesce((
      select jsonb_agg(jsonb_build_object(
        'user_id', z->'user_id', 'user', z->'user', 'firma', z->'firma',
        'status', z->'status', 'lage', z->'lage', 'sperre', z->'sperre',
        'nur_eins_lebt', z->'nur_eins_lebt', 'bestellt', z->'bestellt',
        'fakten_text', z->'fakten_text',
        'untergrenze', z->'untergrenze',
        'luecke', round((z->>'luecke')::numeric),
        'sicherheit', round((z->>'sicherheit')::numeric, 3),
        'tagesrate', z->'tagesrate',
        'nachkauf', jsonb_build_object(
            'n', z->'nachkauf'->'n', 'heute', z->'nachkauf'->'heute', 'einheit', z->'nachkauf'->'einheit',
            'preis_eur', z->'nachkauf'->'preis_eur', 'grund', z->'nachkauf'->'grund',
            'dringlichkeit', z->'nachkauf'->'dringlichkeit'),
        'konten', coalesce((
          select jsonb_agg(jsonb_build_object(
            'typ', k->'typ', 'stufe', k->'stufe', 'groesse', k->'groesse',
            'balance', round((k->>'balance')::numeric),
            'chance', round((k->>'chance')::numeric, 3),
            'abstand_boden', round((k->>'abstand_boden')::numeric),
            'abstand_ziel', round((k->>'abstand_ziel')::numeric),
            'im_bestand', k->'im_bestand', 'eins_vor', k->'eins_vor', 'kurz_vor_blow', k->'kurz_vor_blow',
            'waiting', k->'waiting', 'unsicher', k->'unsicher', 'daten_fehlen', k->'daten_fehlen',
            'alter_tage', k->'alter_tage') order by ko)
            from jsonb_array_elements(
                   case when jsonb_typeof(z->'konten') = 'array' then z->'konten' else '[]'::jsonb end
                 ) with ordinality as kk(k, ko)), '[]'::jsonb)
      ) order by zo)
        from jsonb_array_elements(coalesce(l.ergebnis->'zellen', '[]'::jsonb)) with ordinality as zz(z, zo)
    ), '[]'::jsonb)
  ) end
  from (select 1) eins
  left join l on true;
$$;


-- ─── 2. Schreiben ───────────────────────────────────────────────────────────
-- Prüfung 1:1 wie vorrat_ki_pruefen (app.py, VORRAT STUFE 2), Fehlertexte wörtlich gleich. Bei Fehler wird NICHTS geschrieben.
-- Speicherform wie die Route: ki_text (≤ 4000, leer = null), ki_zeilen {"uid|firma": {heute, einheit, prio, satz}},
-- ki_um sekundengenau (wie _wt_now_iso) — GET /admin/vorrat erkennt die KI an ki_um + nicht-leerem ki_zeilen.
create or replace function public.vorrat_ki_schreiben(p_lauf_id bigint, p_text text, p_zeilen jsonb)
returns jsonb
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
  v_zellen  jsonb;
  v_param   jsonb;
  v_max_tag int;
  v_max_z   int;
  v_zeilen  jsonb := p_zeilen;
  v_idx     jsonb := '{}'::jsonb;
  v_sauber  jsonb := '{}'::jsonb;
  v_summe   int := 0;
  v_k       text;
  v_v       jsonb;
  v_z       jsonb;
  v_q       text;
  v_n       int;
  v_h       jsonb;
  v_prio    text;
  v_einheit text;
  v_satz    text;
begin
  if p_lauf_id is null then
    return jsonb_build_object('ok', false, 'fehler', 'lauf_id fehlt');
  end if;
  select ergebnis->'zellen' into v_zellen from vorrat_lauf where id = p_lauf_id;
  if v_zellen is null or jsonb_typeof(v_zellen) <> 'array' or jsonb_array_length(v_zellen) = 0 then
    return jsonb_build_object('ok', false, 'fehler', 'Lauf nicht gefunden oder ohne Ergebnis');
  end if;

  select coalesce(parameter, '{}'::jsonb) into v_param from vorrat_einstellung where id = 1;
  -- int(prm.get(...) or 30): fehlt oder 0 → Standard
  v_max_tag := coalesce(nullif(nullif(v_param->>'ki_max_tag', '')::int, 0), 30);
  v_max_z   := coalesce(nullif(nullif(v_param->>'ki_max_zelle', '')::int, 0), 5);

  -- body.get("zeilen") or {}: null und leere Werte gelten als {}
  if v_zeilen is null or v_zeilen in ('null'::jsonb, '[]'::jsonb, '""'::jsonb, 'false'::jsonb, '0'::jsonb) then
    v_zeilen := '{}'::jsonb;
  end if;
  if jsonb_typeof(v_zeilen) <> 'object' or (select count(*) from jsonb_object_keys(v_zeilen)) > 300 then
    return jsonb_build_object('ok', false, 'fehler', 'zeilen muss ein Objekt {"user_id|firma": {heute, einheit, prio, satz}} sein');
  end if;

  select coalesce(jsonb_object_agg(coalesce(z->>'user_id', 'None') || '|' || coalesce(z->>'firma', 'None'), z), '{}'::jsonb)
    into v_idx from jsonb_array_elements(v_zellen) z;

  for v_k, v_v in select key, value from jsonb_each(v_zeilen) loop
    v_q := '''' || left(v_k, 60) || '''';
    v_z := v_idx->v_k;
    if v_z is null then
      return jsonb_build_object('ok', false, 'fehler', 'Zelle ' || v_q || ' gibt es in diesem Lauf nicht');
    end if;
    if coalesce(v_z->>'status', 'frei') <> 'frei' then
      return jsonb_build_object('ok', false, 'fehler', 'Zelle ' || v_q || ' ist ' || (v_z->>'status') || ' — keine Empfehlung');
    end if;
    if jsonb_typeof(v_v) <> 'object' then
      return jsonb_build_object('ok', false, 'fehler', 'Zeile ' || v_q || ': erwartet {heute, einheit, prio, satz}');
    end if;
    -- heute: fehlt → 0; sonst ganze Zahl (kein 2.0, kein true, kein "2") 0–max_zelle
    v_h := coalesce(v_v->'heute', '0'::jsonb);
    if jsonb_typeof(v_h) <> 'number' or v_h::text !~ '^[0-9]{1,3}$' or v_h::text::int > v_max_z then
      return jsonb_build_object('ok', false, 'fehler', 'Zeile ' || v_q || ': heute muss eine ganze Zahl 0–' || v_max_z || ' sein');
    end if;
    v_n := v_h::text::int;
    if v_n > 0 and coalesce(v_z->'sperre', 'null'::jsonb) not in ('null'::jsonb, 'false'::jsonb, '""'::jsonb, '0'::jsonb) then
      return jsonb_build_object('ok', false, 'fehler', 'Zeile ' || v_q || ': ohne aktuelle Lesung kein Kauf (heute muss 0 sein)');
    end if;
    if v_n > 0 and coalesce(v_z->'nur_eins_lebt', 'false'::jsonb) not in ('null'::jsonb, 'false'::jsonb, '""'::jsonb, '0'::jsonb) then
      return jsonb_build_object('ok', false, 'fehler', 'Zeile ' || v_q || ': es lebt noch ein Konto — bei dieser Firma heute nichts kaufen (heute muss 0 sein)');
    end if;
    -- prio: leer/fehlt → mittel, sonst hoch|mittel|niedrig
    if coalesce(v_v->'prio', 'null'::jsonb) in ('null'::jsonb, '""'::jsonb, 'false'::jsonb, '0'::jsonb, '[]'::jsonb, '{}'::jsonb) then
      v_prio := 'mittel';
    elsif jsonb_typeof(v_v->'prio') = 'string' and (v_v->>'prio') in ('hoch', 'mittel', 'niedrig') then
      v_prio := v_v->>'prio';
    else
      return jsonb_build_object('ok', false, 'fehler', 'Zeile ' || v_q || ': prio muss hoch, mittel oder niedrig sein');
    end if;
    -- einheit ≤ 80, satz ≤ 300 Zeichen, getrimmt, leer = null
    v_einheit := case when coalesce(v_v->'einheit', 'null'::jsonb) in ('null'::jsonb, '""'::jsonb, 'false'::jsonb, '0'::jsonb) then ''
                      when jsonb_typeof(v_v->'einheit') = 'string' then v_v->>'einheit' else (v_v->'einheit')::text end;
    v_satz    := case when coalesce(v_v->'satz', 'null'::jsonb) in ('null'::jsonb, '""'::jsonb, 'false'::jsonb, '0'::jsonb) then ''
                      when jsonb_typeof(v_v->'satz') = 'string' then v_v->>'satz' else (v_v->'satz')::text end;
    v_einheit := nullif(left(btrim(v_einheit, E' \t\n\r\f\v'), 80), '');
    v_satz    := nullif(left(btrim(v_satz,    E' \t\n\r\f\v'), 300), '');
    v_summe := v_summe + v_n;
    v_sauber := v_sauber || jsonb_build_object(v_k,
                  jsonb_build_object('heute', v_n, 'einheit', v_einheit, 'prio', v_prio, 'satz', v_satz));
  end loop;

  if v_summe > v_max_tag then
    return jsonb_build_object('ok', false, 'fehler', 'zusammen ' || v_summe || ' Käufe — höchstens ' || v_max_tag || ' am Tag');
  end if;

  update vorrat_lauf
     set ki_text   = nullif(left(coalesce(p_text, ''), 4000), ''),
         ki_zeilen = v_sauber,
         ki_um     = date_trunc('second', now())
   where id = p_lauf_id;
  if not found then
    return jsonb_build_object('ok', false, 'fehler', 'Lauf nicht gefunden');
  end if;

  return jsonb_build_object('ok', true, 'lauf_id', p_lauf_id,
                            'zeilen', (select count(*) from jsonb_object_keys(v_sauber)),
                            'summe', v_summe, 'heute', v_summe);
end;
$$;


-- ─── 3. Rechte: kein REST ───────────────────────────────────────────────────
revoke execute on function public.vorrat_ki_fakten() from public, anon, authenticated;
revoke execute on function public.vorrat_ki_schreiben(bigint, text, jsonb) from public, anon, authenticated;
