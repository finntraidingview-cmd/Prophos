-- ============================================================================
-- Prophos: fleet_privat — IDs, die Prophos eigenständig nutzen
--
-- Finns Ansage (25.08.2026): Emin nutzt Prophos alleine für sich. Er soll die
-- Flotte der anderen NICHT sehen, und die anderen sollen ihn NICHT sehen —
-- beide Richtungen, durchgesetzt per RLS (nicht nur im Frontend versteckt).
--
-- Mechanik:
--   - fleet_privat hält die user_ids der "privaten" Nutzer. RLS an, KEINE
--     Policies → Clients können die Liste weder lesen noch ändern.
--   - Die Lese-Policies von dup_live und mt5_live fragen die Liste über eine
--     SECURITY-DEFINER-Funktion ab (ist_fleet_privat). Direkt ginge nicht:
--     Policy-Subqueries laufen als anfragender User und würden an der RLS
--     von fleet_privat abprallen — exists() wäre still immer false und die
--     Trennung wäre wirkungslos.
--   - Privater Nutzer: sieht nur die eigene(n) Zeile(n) — seine Lots-Chips
--     funktionieren weiter, sein Flotten-Block bleibt leer (eigene Person
--     wird eh nicht gelistet). Alle anderen: sehen alles AUSSER den privaten.
--   - Der Wächter schreibt mit Service-Key an RLS vorbei — unverändert.
--   - mt5_live: user_id steckt im status-JSON (seit .109); Alt-Zeilen ohne
--     user_id bleiben für normale Nutzer sichtbar, für private nicht.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.fleet_privat (
  user_id text primary key,
  notiz   text not null default ''
);
alter table public.fleet_privat enable row level security;

create or replace function public.ist_fleet_privat(uid text)
returns boolean
language sql stable security definer
set search_path = public
as $$ select exists (select 1 from fleet_privat where user_id = uid) $$;

insert into public.fleet_privat (user_id, notiz)
  values ('6cceb3f3-dc78-48ee-8668-26081da3e70f', 'Emin (elominx) — nutzt Prophos eigenstaendig, 25.08.2026')
  on conflict (user_id) do nothing;

drop policy if exists "dup_live read" on public.dup_live;
create policy "dup_live read" on public.dup_live for select to authenticated using (
  case when public.ist_fleet_privat(auth.uid()::text)
    then dup_live.user_id = auth.uid()::text
    else not public.ist_fleet_privat(dup_live.user_id)
  end
);

drop policy if exists "mt5_live read" on public.mt5_live;
create policy "mt5_live read" on public.mt5_live for select to authenticated using (
  case when public.ist_fleet_privat(auth.uid()::text)
    then coalesce(mt5_live.status->>'user_id','') = auth.uid()::text
    else not public.ist_fleet_privat(coalesce(mt5_live.status->>'user_id',''))
  end
);
