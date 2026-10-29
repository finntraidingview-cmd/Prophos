-- TSX_LIVE: RECHTE ENG (Master 29.10.2026, Auftrag TSX-LIVE-RLS; S2 zu Lücke D: „RLS von tsx_live = echoplus_live — jede eingeloggte ID darf
-- jede Zeile schreiben"). Erhoben am Code (29.10.2026):
--   SCHREIBT: nur der Prophos-PC-Tab (prophos.html tsxLiveTick → supabase.from('tsx_live').upsert, Rolle authenticated, JWT der am PC
--             eingeloggten ID), eine Zeile je PC (id = PC-Kennung). Panel und TopstepX-Auge schreiben NIE in Supabase (das Auge meldet nur
--             dem Panel 127.0.0.1:8770, der Tab holt dort /api/tsx-stand).
--   LIEST:    nur Railway (app.py fp_tick, Service-Schlüssel → RLS gilt dort nicht). Kein Frontend-Leser.
-- Neu:
--   • Spalte user_id = Besitzer der Zeile; ein Trigger setzt sie bei JEDEM Schreiben eines eingeloggten Tabs auf auth.uid() — der Tab muss
--     nichts mitschicken (alte Tabs schreiben unverändert weiter), niemand kann eine fremde ID eintragen. Service-Schreibzugriffe
--     (auth.uid() leer) lassen sie stehen.
--   • Schreiben nur in die EIGENE Zeile. Übernahme einer fremden Zeile nur, wenn sie seit 10 min tot ist (ID-Wechsel am PC: der PC-Tab
--     meldet sich mit einer anderen ID an, dieselbe PC-Kennung) oder noch keinen Besitzer hat (Zeilen von vor dieser Datei).
--   • Lesen wie mt5_live: eine ID aus fleet_privat (Emins Gruppe) sieht nur eigene Zeilen, alle anderen sehen alle Zeilen außer denen
--     von fleet_privat-IDs. Löschen nur eigene. backup_reader liest weiter alles.
-- Folge für den Richtungsschutz: keine — fp_tick liest mit dem Service-Schlüssel und braucht user_id nicht. Ein Tab kann weiterhin für
-- SEINE Zeile jedes Konto melden (das Auge sieht, was im TopstepX-Tab gewählt ist); eine Bindung Konto ↔ Besitzer wäre ein eigener Schritt.
-- echoplus_live bleibt hier bewusst unverändert: das Frontend liest dort quer über IDs (WD-Reader-Lage, Feed-Lage, Orbit-Liste) und schaltet
-- fremde Reader (epSchalten → soll_an) — eine Verschärfung bräuchte eine eigene Abstimmung.
-- Einspielen: Master nach Prüfer-OK. Idempotent. Kein Code-Push nötig.
--
-- RÜCKNAHME (zurück auf den offenen Stand von sql/2026-10-29_tsx_live.sql):
--   drop trigger if exists tsx_live_besitzer on public.tsx_live;
--   drop function if exists public.tsx_live_besitzer();
--   drop policy if exists "tsx_live read" on public.tsx_live;   create policy "tsx_live read"   on public.tsx_live for select to authenticated using (true);
--   drop policy if exists "tsx_live insert" on public.tsx_live; create policy "tsx_live insert" on public.tsx_live for insert to authenticated with check (true);
--   drop policy if exists "tsx_live update" on public.tsx_live; create policy "tsx_live update" on public.tsx_live for update to authenticated using (true) with check (true);
--   drop policy if exists "tsx_live delete" on public.tsx_live; create policy "tsx_live delete" on public.tsx_live for delete to authenticated using (true);
--   (Spalte user_id darf bleiben — stört niemanden; sonst: alter table public.tsx_live drop column if exists user_id;)

alter table public.tsx_live add column if not exists user_id uuid;

create or replace function public.tsx_live_besitzer() returns trigger
  language plpgsql security invoker set search_path = public as $$
begin
  if auth.uid() is not null then
    new.user_id := auth.uid();
  end if;
  return new;
end $$;

drop trigger if exists tsx_live_besitzer on public.tsx_live;
create trigger tsx_live_besitzer before insert or update on public.tsx_live
  for each row execute function public.tsx_live_besitzer();

alter table public.tsx_live enable row level security;

drop policy if exists "tsx_live read" on public.tsx_live;
create policy "tsx_live read" on public.tsx_live for select to authenticated using (
  case when ist_fleet_privat((auth.uid())::text) then user_id = auth.uid()
       else not ist_fleet_privat(coalesce(user_id::text, '')) end);

drop policy if exists "tsx_live insert" on public.tsx_live;
create policy "tsx_live insert" on public.tsx_live for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "tsx_live update" on public.tsx_live;
create policy "tsx_live update" on public.tsx_live for update to authenticated
  using (user_id = auth.uid() or user_id is null or updated_at < now() - interval '10 minutes')
  with check (user_id = auth.uid());

drop policy if exists "tsx_live delete" on public.tsx_live;
create policy "tsx_live delete" on public.tsx_live for delete to authenticated using (user_id = auth.uid());
