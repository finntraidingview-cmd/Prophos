-- TW4 WÜRFEL-AUSNAHME JE ID × FIRMA × TAG (Finn 16.11.2026 ~03:30 Dubai über den Master: „mach Simon mal rein für heute" — gemeint sind Simons Lucid-Challenges,
-- die heute auf „Pause-Tag Firma (Firmen-Würfel 85 %)" standen). Bisher ging das nur global (Wert hochsetzen = alle Firmen-Pausen aufgefüllt) oder je Konto
-- (TW2 „heute rein", Marke tw_hand in user_settings).
-- Code (Commit TW4, app.py tw_ausnahmen / tw_ausnahme_hat / tw_pause_grund): Gibt es eine Zeile für ID × Firma (Vergleich nach _ap_norm) × Plan-Tag, greifen
-- Firmen-Würfel (TW3) UND Konto-Würfel (TW1) für diese ID × Firma an dem Tag nicht. Alle anderen Regeln bleiben (Waage, Tagesdeckel, Liq-Abstand, Zeitfenster,
-- Grenzen je ID/Firma, Richtung). firma NULL = alle Firmen der ID. tag = Plan-Tag (Dubai-Datum, wie der Würfel ihn sieht); der nächste Tag ist wieder gewürfelt.
-- Nachtlauf, Nachplan-Takt (5 min), Knopf, Funded-Takt und WD-POST lesen dieselbe Tabelle (20 s gemerkt). Ohne Tabelle/Zeile alles wie vor TW4.
-- Nachtrag Master 16.11.2026: optional konto_id — gesetzt = die Zeile gilt NUR für dieses eine Konto (beide Würfel aus), firma wird dann ignoriert.
-- Lesen/Schreiben nur über Railway (Service-Rolle) — RLS an, keine Policies. Idempotent. Reihenfolge egal (der alte Code liest die Tabelle nicht).

create table if not exists public.planer_wuerfel_ausnahme (
  id           bigserial primary key,
  user_id      uuid not null,
  firma        text,                                   -- NULL = alle Firmen der ID; sonst der Firmenname wie accounts.firm (Vergleich im Code nach _ap_norm)
  konto_id     uuid,                                   -- gesetzt = nur dieses Konto (accounts.id); dann zählt firma nicht
  tag          date not null,                          -- Plan-Tag (Dubai-Datum)
  angelegt_von text,                                   -- wer (ID oder „Master SQL")
  created_at   timestamptz not null default now()
);
alter table public.planer_wuerfel_ausnahme add column if not exists konto_id uuid;   -- falls die Tabelle schon ohne die Spalte angelegt wurde
drop index if exists public.planer_wuerfel_ausnahme_eindeutig;
create unique index if not exists planer_wuerfel_ausnahme_eindeutig2
  on public.planer_wuerfel_ausnahme (user_id, coalesce(lower(firma), '*'), coalesce(konto_id::text, '*'), tag);
create index if not exists planer_wuerfel_ausnahme_tag on public.planer_wuerfel_ausnahme (tag);
alter table public.planer_wuerfel_ausnahme enable row level security;
comment on table public.planer_wuerfel_ausnahme is
  'TW4: ID × Firma (NULL = alle) bzw. ein Konto (konto_id) × Tag ohne Handels-Würfel (Firma TW3 + Konto TW1). Andere Planer-Regeln bleiben. Ohne Zeile wie vor TW4.';

-- Beispiel (Finn 16.11.2026 „Simon für heute rein", Lucid) — user_id von Simon einsetzen:
--   insert into public.planer_wuerfel_ausnahme (user_id, firma, tag, angelegt_von)
--   values ('<simon-user-id>', 'Lucid Trading', '2026-11-16', 'Master SQL (Finn 16.11.)')
--   on conflict do nothing;
-- Nur ein einzelnes Konto (z. B. ein Pause-Tag-Konto, die übrigen Konten der Firma bleiben gewürfelt):
--   insert into public.planer_wuerfel_ausnahme (user_id, konto_id, tag, angelegt_von)
--   select a.user_id, a.id, '2026-11-16', 'Master SQL' from public.accounts a where a.id = '<konto-id>'
--   on conflict do nothing;
-- tag = der Tag, für den der Planer würfelt: Challenge = Dubai-Datum; Funded-Planer = Plan-Tag (CME-/nächster Handelstag, fd_plan_tag); WD = planned_for.
-- Meist dasselbe Datum — plant ein Funded-Planer schon für den nächsten Handelstag, die Zeile für DIESEN Tag anlegen.
-- Danach rechnet der Nachplan-Takt die Konten binnen ~5 min neu („Pause-Tag" ist kein fester Grund).
-- Prüfen:   select * from public.planer_wuerfel_ausnahme order by tag desc, created_at desc;
-- Zurück:   delete from public.planer_wuerfel_ausnahme where tag = '2026-11-16';   -- oder drop table (Code: ohne Tabelle = wie vor TW4)
