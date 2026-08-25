-- ============================================================================
-- Prophos: dup_live — Duplikium-Live-Spiegel des Railway-Wächters
--
-- Finns Architektur-Ansage (25.08.2026 abends): "die ganzen Sachen in der
-- Datenbank speichern … über Railway, sodass die Daten da reinkommen und dann
-- an die anderen Usern ausgespuckt werden." Hintergrund: alle Duplikium-
-- Anzeigen im Browser (Flotte, Live-Lots-Chips) hingen am localStorage-Token —
-- lief der ab (401 → dupLogout), war auf der Origin alles leer, bis jemand die
-- Creds neu eintippte (Fund 25.08.: Chips um 19:02 da, 19:52 weg).
--
-- Der Wächter pollt getOpenPositions ohnehin alle ~30s pro Duplikium-Konto —
-- diese Tabelle ist sein Spiegel: EINE Zeile pro Duplikium-Konto (E-Mail),
-- rohe Positionsliste + schlanke Account-Liste (Name/Login) für die Personen-
-- Zuordnung. Kein Browser braucht mehr einen Duplikium-Token zum LESEN.
--
-- Bewusst NICHT nach user_id getrennt (Muster kasse_entries/mt5_live): die
-- Flotte ist EINE Operation, jeder eingeloggte User sieht alles.
-- Schreiben darf NUR der Service-Key (Wächter) — keine Insert/Update-Policies
-- für Clients, anders als mt5_live (dort pushen die lokalen PCs selbst).
--
-- Frische-Beweis: updated_at. Wächter-Takt 30s → Frontend zeigt älter ~75s
-- ausgegraut, älter 10min gar nicht — nie alte Daten als live.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.dup_live (
  id         text primary key,                        -- Duplikium-Login-E-Mail (ein Konto = eine Zeile)
  positions  jsonb not null default '[]'::jsonb,      -- rohes getOpenPositions-data (account_id, symbol, side, amountLot, id_master, ticket, openTime, …)
  accounts   jsonb not null default '[]'::jsonb,      -- schlank: [{account_id, name, login}] aus getAccounts (stündlich)
  updated_at timestamptz not null default now()
);

alter table public.dup_live enable row level security;

drop policy if exists "dup_live read" on public.dup_live;

-- Lesen: alle authentifizierten Prophos-User (geteilte Sicht, profilübergreifend).
create policy "dup_live read" on public.dup_live for select to authenticated using (true);

-- KEINE insert/update/delete-Policies: Clients können nicht schreiben,
-- der Wächter schreibt mit dem Service-Key an RLS vorbei.
