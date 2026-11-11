-- RV1 RANGE-WÜRFEL (11.11.2026, Finn 07:35 über den Master: „75 % der Trades bleiben gleich, und nur bei 25 % der Trades wird's angepasst … Stop Loss,
-- Take Profit und Lotanzahl, alles drei … für alle drei wird einzeln gewürfelt“). Konstrukt: side-session-notes 2026-11-11_RV1_range_wuerfel_konstrukt.md.
-- Je Planer × Unternehmen: pct = Anteil der Haupt-Trades, die „klein“ werden; von/bis = Spanne der drei Faktoren (TP, SL, Lots je eigener Wurf) in %.
-- Gewürfelt wird in app.py je Konto × Tag fest (Hash, rv_faktoren) — kein Speicher je Tag nötig. Nur Challenge-Planer CFD (Echo), nur die Etappe.
--   planer: challenge_cfd (weitere Planer erst auf Finns Wort — Funded CFD fragt der Master separat)
--   gruppe: '' = Standard = Hermann Technologies; sonst die gruppe_id eines Unternehmens (Text). Ohne Zeile = aus (0 %); ein Unternehmen erbt den HT-Wert NICHT.
-- Lesen/Schreiben nur über Railway (Service-Rolle, GET/POST /admin/range-wuerfel) — RLS an, keine Policies (wie planer_handel_wuerfel).
-- REIHENFOLGE: erst den Code pushen, dann einspielen (der alte Code liest die Tabelle nicht — harmlos). Teil 2 schaltet HT auf 25 % — damit wirkt es ab dem
-- nächsten Planer-Lauf (Nachtlauf / Nachplanen). Einspielen nur auf Finns bzw. des Masters Wort.

create table if not exists public.planer_range_wuerfel (
  planer      text not null check (planer in ('challenge_cfd')),
  gruppe      text not null default '',
  pct         numeric(5, 2) not null check (pct >= 0 and pct <= 100),
  von         numeric(5, 2) not null default 10 check (von >= 1 and von <= 100),
  bis         numeric(5, 2) not null default 100 check (bis >= 1 and bis <= 100),
  updated_at  timestamptz not null default now(),
  updated_von uuid,
  primary key (planer, gruppe),
  check (von <= bis)
);
alter table public.planer_range_wuerfel enable row level security;
comment on table public.planer_range_wuerfel is
  'RV1 Range-Würfel: Anteil „klein“ (pct) und Faktor-Spanne von–bis (%) je Planer × Unternehmen (gruppe '''' = HT-Standard). Ohne Zeile aus.';

-- Teil 2: Hermann Technologies (Standard) — Challenge-Planer CFD 25 % klein, Faktoren 10–100 %
insert into public.planer_range_wuerfel (planer, gruppe, pct, von, bis) values ('challenge_cfd', '', 25, 10, 100)
on conflict (planer, gruppe) do nothing;   -- erneut eingespielt: in der Karte geänderte Werte bleiben stehen

-- Kontrolle: select * from public.planer_range_wuerfel;
-- Aus (wie vor RV1):  delete from public.planer_range_wuerfel;
