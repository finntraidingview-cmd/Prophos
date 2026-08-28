-- Rechnungen für die Abrechnungen der gemanagten IDs (28.08.2026, Finns Wunsch).
-- Eine Zeile pro erstellter Rechnung: eingefrorener Datensatz (jeder Trade,
-- jede Buchung des Zeitraums als jsonb) + fertiges PDF als base64. Eingefroren
-- deshalb, weil eine Rechnung für die Steuer den Stand ZUM ERSTELLZEITPUNKT
-- dokumentieren muss — nachträgliche Änderungen an trade_plans/transactions
-- dürfen eine bestehende Rechnung nie mehr verändern.
--
-- RECHTE (bewusst NICHT das geteilte Kasse-Muster):
--   * Lesen: jeder eingeloggte User NUR die eigenen Rechnungen (user_id = auth.uid()).
--   * Schreiben: NIEMAND per Client — keine insert/update/delete-Policies.
--     Erstellt wird ausschließlich über app.py mit dem Service-Key, und der
--     Endpoint prüft die E-Mail des Anfragenden gegen die Railway-Variable
--     ADMIN_EMAILS. Das ist die erste echte Rollen-Prüfung in Prophos
--     (vgl. Offene Punkte 245/310: „ab wann braucht Prophos Rollen?").

create table if not exists rechnungen (
  id            uuid primary key default gen_random_uuid(),
  nummer        text not null unique,          -- z.B. RG-2026-0001, fortlaufend
  user_id       uuid not null,                 -- Empfänger = die gemanagte ID
  person_name   text not null default '',
  person_mail   text not null default '',
  zeitraum_von  date not null,
  zeitraum_bis  date not null,
  absender      text not null default '',      -- Freitext-Briefkopf (später FZCO)
  notiz         text,
  anteil_pct    numeric,                       -- Anteil der ID am Saldo (wie profit_share_pct), null = kein Split auf der Rechnung
  daten         jsonb not null,                -- eingefrorene Positionen: trades[], buchungen[], summen{}
  pdf_b64       text not null,                 -- fertiges PDF, base64 (Rechnungen sind klein, kein Storage-Bucket nötig)
  created_by    text not null default '',      -- E-Mail des erstellenden Admins
  created_at    timestamptz not null default now()
);

create index if not exists rechnungen_user_idx on rechnungen (user_id, created_at desc);

alter table rechnungen enable row level security;

-- Nur die eigene Rechnung lesbar — der Admin liest über den Service-Key daran vorbei.
drop policy if exists "rechnungen_select_own" on rechnungen;
create policy "rechnungen_select_own" on rechnungen
  for select to authenticated
  using (user_id = auth.uid());
