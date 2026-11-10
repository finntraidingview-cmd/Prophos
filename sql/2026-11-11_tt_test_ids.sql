-- TT1 „Trades pro Tag“ mit Test-IDs statt Testkonten (Finn 11.11.2026: „Nein, ich will keine Testkonten mehr. Ich will jetzt Test-IDs … Okay, Marco
-- und Simon werden das Ganze heute testen.“). Setzt regeln.tagesteilung.test_ids = [Marco, Simon] und leert nur_konten (Testkonten vom 10.11. raus).
-- Wirkung (app.py tt_gilt): angehakte Test-IDs → NUR ihre Echo-Konten (Challenge CFD, Firma in tagesteilung.firmen) werden beim nächsten Planlauf
-- geteilt, alle anderen IDs bleiben bei 1 Trade. an / firmen / test_n und die Rechenwerte bleiben, wie sie sind (Finn: bestehende Einstellung bleibt).
-- IDs werden per Name aufgelöst (auth.users.raw_user_meta_data->>'name', erstes Wort, ohne Groß/klein) und NUR unter den HT-Planer-IDs
-- (auto_plan_regeln.user_ids, id 1) gesucht — keine IDs im Repo. Bricht ab, wenn ein Name nicht genau EINE Planer-ID trifft. Idempotent.
-- REIHENFOLGE: ERST den TT1-Code pushen, DANN diese Datei einspielen (Gegenprüfung 11.11.2026). Der alte Code kennt test_ids nicht — mit an = true
-- und geleertem nur_konten teilte er bis zum Push ALLE Konten der angehakten Firmen. Der neue Code wertet den alten nur_konten-Eintrag ohne Test-IDs
-- als Sperre (nichts geteilt), die Zwischenzeit ist also sicher. Steht an = false, passiert nach dem Einspielen nichts (an setzt diese Datei nicht).
-- Lage vorher/nachher:  select regeln->'tagesteilung' from public.auto_plan_regeln where id = 1;
do $$
declare
  ids uuid[];
  n_marco int;
  n_simon int;
begin
  select count(*) filter (where lower(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1)) = 'marco'),
         count(*) filter (where lower(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1)) = 'simon')
    into n_marco, n_simon
    from public.auto_plan_regeln r
    join auth.users u on u.id = any(r.user_ids)
   where r.id = 1;
  if n_marco <> 1 or n_simon <> 1 then
    raise exception 'TT1: Marco % Treffer, Simon % Treffer unter den HT-Planer-IDs — erwartet je 1, nichts geändert', n_marco, n_simon;
  end if;
  select array_agg(u.id order by lower(u.raw_user_meta_data->>'name'))
    into ids
    from public.auto_plan_regeln r
    join auth.users u on u.id = any(r.user_ids)
   where r.id = 1
     and lower(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1)) in ('marco', 'simon');
  update public.auto_plan_regeln
     set regeln = jsonb_set(jsonb_set(regeln, '{tagesteilung,test_ids}', to_jsonb(array(select x::text from unnest(ids) x))),
                            '{tagesteilung,nur_konten}', '[]'::jsonb),
         updated_at = now()
   where id = 1 and regeln ? 'tagesteilung';
end $$;

select regeln->'tagesteilung'->'an' an, regeln->'tagesteilung'->'test_ids' test_ids, regeln->'tagesteilung'->'nur_konten' nur_konten,
       regeln->'tagesteilung'->'firmen' firmen, regeln->'tagesteilung'->'test_n' test_n
  from public.auto_plan_regeln where id = 1;
