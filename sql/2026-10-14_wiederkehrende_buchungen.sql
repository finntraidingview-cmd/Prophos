-- 2026-10-14: Wiederkehrende Buchungen in den Finanzen je ID (Finn: „unter Finanzen manuell einbuchen und recurring auswählen —
-- jeden Monat am 2. zieht Finanzen 500 € ab, das geht vom Gesamt-P&L runter; so sehe ich, wann ich dem Kunden Geld schicken muss").
-- Eine Zeile je Dauerbuchung: user_id (die ID, in deren Finanzen gebucht wird), Betrag mit Vorzeichen, Tag im Monat, nächste Fälligkeit.
-- Railway bucht fällige Zeilen täglich als transactions (auto_generated, kind wie hinterlegt) und schiebt naechste_am einen Monat weiter;
-- die Admin-Karte „Monatszahlungen an Kunden" (Rechnungen-Reiter) liest dieselben Zeilen. Ersetzt kunden_zahlungen vom selben Tag (nie live).
-- Zahltage laut Finn 14.10.2026: Chris 16., Mike 21., Ina 2. — erste Zahlungen sind in den Finanzen der IDs schon von Hand gebucht,
-- die drei Startzeilen wurden direkt in der DB angelegt (keine Personendaten im Repo).

drop table if exists public.kunden_zahlungen;

create table if not exists public.wiederkehrende_buchungen (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null,
  kind          text not null default 'manual',
  amount        numeric(12,2) not null,
  currency      text not null default 'EUR',
  notes         text,
  tag_im_monat  smallint not null check (tag_im_monat between 1 and 31),
  naechste_am   date not null,
  letzte_am     date,
  aktiv         boolean not null default true,
  created_at    timestamptz not null default now()
);

create index if not exists wiederkehrende_buchungen_faellig on public.wiederkehrende_buchungen (naechste_am) where aktiv;

alter table public.wiederkehrende_buchungen enable row level security;

-- Jede ID sieht und pflegt nur ihre eigenen Dauerbuchungen (wie transactions); Railway bucht über den Service-Key.
create policy "wb eigene lesen"   on public.wiederkehrende_buchungen for select using (auth.uid() = user_id);
create policy "wb eigene anlegen" on public.wiederkehrende_buchungen for insert with check (auth.uid() = user_id);
create policy "wb eigene aendern" on public.wiederkehrende_buchungen for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "wb eigene loeschen" on public.wiederkehrende_buchungen for delete using (auth.uid() = user_id);
