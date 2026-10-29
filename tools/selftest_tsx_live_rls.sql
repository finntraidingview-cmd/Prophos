-- SELBSTTEST (keine Migration!) zu sql/2026-10-29_tsx_live_rls.sql — spielt dieselben Regeln auf einer PROBE-KOPIE der Tabelle durch und rollt
-- sich am Ende selbst zurück (RAISE EXCEPTION mit dem Ergebnis): die echte tsx_live wird nicht angefasst, in der DB bleibt nichts zurück.
-- Ausführen als postgres (Supabase SQL-Editor / MCP execute_sql). Die drei IDs unten bei Bedarf ersetzen: a, b = zwei Hermann-Technologies-IDs,
-- p = eine ID aus fleet_privat. Erwartet (29.10.2026, S3): 1 Besitzer=A · 2 K1b · 3 K-A/A · 4 abgelehnt · 5 0 Zeilen · 6 0 Zeilen ·
-- 7 Besitzer=B (Trigger) · 8 K-B/B · 9 privat sieht 1 · 10 HT sieht 3 · 11 service_role liest 2.
do $probe$
declare
  a uuid := '00000000-0000-0000-0000-00000000000a';   -- HT-ID 1 (ersetzen)
  b uuid := '00000000-0000-0000-0000-00000000000b';   -- HT-ID 2 (ersetzen)
  p uuid := (select user_id::uuid from fleet_privat limit 1);
  r text := '';
  n int; u text;
begin
  create table public.tsx_live_probe_rls (like public.tsx_live including defaults including constraints);
  alter table public.tsx_live_probe_rls add primary key (id);
  alter table public.tsx_live_probe_rls add column if not exists user_id uuid;
  create function public.tsx_live_probe_besitzer() returns trigger language plpgsql security invoker set search_path = public as $f$
  begin if auth.uid() is not null then new.user_id := auth.uid(); end if; return new; end $f$;
  create trigger b before insert or update on public.tsx_live_probe_rls for each row execute function public.tsx_live_probe_besitzer();
  alter table public.tsx_live_probe_rls enable row level security;
  create policy rd on public.tsx_live_probe_rls for select to authenticated using (
    case when ist_fleet_privat((auth.uid())::text) then user_id = auth.uid() else not ist_fleet_privat(coalesce(user_id::text, '')) end);
  create policy ins on public.tsx_live_probe_rls for insert to authenticated with check (user_id = auth.uid());
  create policy upd on public.tsx_live_probe_rls for update to authenticated
    using (user_id = auth.uid() or user_id is null or updated_at < now() - interval '10 minutes') with check (user_id = auth.uid());
  create policy del on public.tsx_live_probe_rls for delete to authenticated using (user_id = auth.uid());
  grant select, insert, update, delete on public.tsx_live_probe_rls to authenticated;
  insert into public.tsx_live_probe_rls (id, konto, positionen_ok) values ('pc-alt', 'K-ALT', false);

  perform set_config('request.jwt.claims', json_build_object('sub', a, 'role', 'authenticated')::text, true);
  perform set_config('role', 'authenticated', true);
  insert into public.tsx_live_probe_rls (id, konto, positionen_ok, vollstaendig, flach, updated_at) values ('pc-a', 'K1', true, true, true, now())
    on conflict (id) do update set konto = excluded.konto, positionen_ok = excluded.positionen_ok, updated_at = excluded.updated_at;
  select user_id::text into u from public.tsx_live_probe_rls where id = 'pc-a';
  r := r || '1 A legt an, Besitzer=' || coalesce(case when u = a::text then 'A' else u end, 'NULL') || E'\n';
  insert into public.tsx_live_probe_rls (id, konto, positionen_ok, updated_at) values ('pc-a', 'K1b', true, now())
    on conflict (id) do update set konto = excluded.konto, updated_at = excluded.updated_at;
  r := r || '2 A schreibt erneut: ' || (select konto from public.tsx_live_probe_rls where id = 'pc-a') || E'\n';
  insert into public.tsx_live_probe_rls (id, konto, positionen_ok, updated_at) values ('pc-alt', 'K-A', true, now())
    on conflict (id) do update set konto = excluded.konto, updated_at = excluded.updated_at;
  r := r || '3 A übernimmt besitzerlose Altzeile: ' || (select konto || '/' || (case when user_id = a then 'A' else '?' end) from public.tsx_live_probe_rls where id = 'pc-alt') || E'\n';

  perform set_config('request.jwt.claims', json_build_object('sub', b, 'role', 'authenticated')::text, true);
  begin
    insert into public.tsx_live_probe_rls (id, konto, positionen_ok, updated_at) values ('pc-a', 'K-FREMD', true, now())
      on conflict (id) do update set konto = excluded.konto, updated_at = excluded.updated_at;
    r := r || '4 B überschreibt A (FALSCH, ging durch)' || E'\n';
  exception when others then r := r || '4 B überschreibt A frisch → abgelehnt (' || left(sqlerrm, 60) || ')' || E'\n';
  end;
  update public.tsx_live_probe_rls set konto = 'K-FREMD2' where id = 'pc-a';
  get diagnostics n = row_count;
  r := r || '5 B UPDATE direkt auf A: ' || n || ' Zeilen' || E'\n';
  delete from public.tsx_live_probe_rls where id = 'pc-a';
  get diagnostics n = row_count;
  r := r || '6 B DELETE auf A: ' || n || ' Zeilen' || E'\n';
  begin
    insert into public.tsx_live_probe_rls (id, konto, user_id, updated_at) values ('pc-b', 'K2', a, now());
    r := r || '7 B legt Zeile an und trägt A als Besitzer ein → Besitzer=' || (select case when user_id = b then 'B (Trigger)' when user_id = a then 'A (FALSCH)' else '?' end from public.tsx_live_probe_rls where id = 'pc-b') || E'\n';
  exception when others then r := r || '7 B mit fremder user_id → ' || left(sqlerrm, 60) || E'\n';
  end;

  perform set_config('role', 'postgres', true);
  update public.tsx_live_probe_rls set updated_at = now() - interval '11 minutes' where id = 'pc-a';
  perform set_config('role', 'authenticated', true);
  insert into public.tsx_live_probe_rls (id, konto, positionen_ok, updated_at) values ('pc-a', 'K-B', true, now())
    on conflict (id) do update set konto = excluded.konto, updated_at = excluded.updated_at;
  r := r || '8 B übernimmt tote Zeile: ' || (select konto || '/' || (case when user_id = b then 'B' else '?' end) from public.tsx_live_probe_rls where id = 'pc-a') || E'\n';

  perform set_config('request.jwt.claims', json_build_object('sub', p, 'role', 'authenticated')::text, true);
  insert into public.tsx_live_probe_rls (id, konto, positionen_ok, updated_at) values ('pc-p', 'K-P', true, now());
  select count(*) into n from public.tsx_live_probe_rls;
  r := r || '9 privat-ID sieht ' || n || ' Zeile(n) (nur eigene)' || E'\n';
  perform set_config('request.jwt.claims', json_build_object('sub', b, 'role', 'authenticated')::text, true);
  select count(*) into n from public.tsx_live_probe_rls;
  r := r || '10 HT-ID sieht ' || n || ' Zeile(n) (alle außer privat)' || E'\n';

  perform set_config('role', 'service_role', true);
  select count(*) into n from public.tsx_live_probe_rls where positionen_ok is true;
  r := r || '11 service_role liest ' || n || ' Zeile(n) mit positionen_ok (alle)' || E'\n';
  perform set_config('role', 'postgres', true);
  raise exception E'PROBE-ERGEBNIS (alles zurückgerollt):\n%', r;
end $probe$;
