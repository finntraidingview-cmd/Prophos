-- ============================================================================
-- Prophos: GESCHÄFTSKONTO AUS EMINS SHEET für „Kapital" (29.10.2026)
--
-- Finn (04:45, über den Master): „Das ist ein Google Sheet von Emins Buchhaltung, weil er noch ein Geschäftskonto hat — davon gehört mir
-- auch die Hälfte. Bring genau den Gesamtbetrag mit rein." Entscheidung danach: automatisch. Railway liest täglich Buchungen!A2:G per
-- Google-Service-Konto (nur lesen, nie zurückschreiben) und spiegelt jede Zeile nach kapital_gk_buchungen (quelle 'sheet'). Das Sheet führt
-- keinen Kontostand, nur Buchungen ab „Zeitraum ab" (Übersicht!B3) — der Anfangsstand an dem Tag ist eine eigene Hand-Buchung „Anfangsstand".
--
--  kapital_gk_buchungen.quelle            'hand' (im Reiter gebucht) | 'sheet' (gespiegelt; das Sheet ist die Wahrheit, Prophos löscht und
--                                         legt diese Zeilen beim Abgleich neu an, ändert sie nie von Hand)
--  kapital_gk_buchungen.zeilen_schluessel Inhalts-Schlüssel der Sheet-Zeile (Datum|Art|Betrag|Zweck|Kategorie + laufende Nummer bei exakt
--                                         gleichen Zeilen) — Zeilennummern taugen nicht, im Sheet stehen Nachträge mitten drin
--  kapital_gk_quellen                     je Gruppe ein Sheet + Stand des letzten Abrufs (Stand-Zeile Übersicht!A2, Fehler, Zeilenzahl)
--
-- Lesen/Schreiben nur über app.py (Service-Key) — RLS ohne Policy. Idempotent.
-- ============================================================================

alter table public.kapital_gk_buchungen add column if not exists quelle text not null default 'hand';
alter table public.kapital_gk_buchungen add column if not exists zeilen_schluessel text;
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'kapital_gk_buchungen_quelle_chk') then
    alter table public.kapital_gk_buchungen add constraint kapital_gk_buchungen_quelle_chk check (quelle in ('hand','sheet'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'kapital_gk_buchungen_zeile_uq') then
    -- NULL (Hand-Buchungen) zählt nie als gleich → nur Sheet-Zeilen sind je Gruppe eindeutig
    alter table public.kapital_gk_buchungen add constraint kapital_gk_buchungen_zeile_uq unique (gruppe_id, zeilen_schluessel);
  end if;
end $$;

create table if not exists public.kapital_gk_quellen (
  gruppe_id      uuid primary key references public.id_gruppen(id) on delete cascade,
  sheet_id       text not null,
  titel          text,
  anteil_hinweis text,                 -- reine Anzeige, z. B. „50 % Finn" (der Reiter rechnet keinen Anteil)
  abruf_at       timestamptz,
  stand_text     text,                 -- Übersicht!A2 wörtlich („Letzte Buchung am …, Stand …")
  zeitraum_ab    date,                 -- Übersicht!B3 — Datum des Anfangsstands
  zeilen         int,
  fehler         text
);
alter table public.kapital_gk_quellen enable row level security;

-- Emin-Gruppe: Sheet „Buchhaltung 2026" (Besitzer obuyel1@gmail.com), Hälfte gehört Finn
insert into public.kapital_gk_quellen (gruppe_id, sheet_id, titel, anteil_hinweis)
values ('90c616f3-3ec1-49cb-b3ba-8a267d0a43df', '1FovCPMmEujv_SoZ6TWlT9D2UduUvEZMgJ3C4ubQnWdE', 'Buchhaltung 2026', '50 % Finn')
on conflict (gruppe_id) do nothing;
