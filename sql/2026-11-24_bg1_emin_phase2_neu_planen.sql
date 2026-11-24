-- BG1 (Finn/Master 24.11.2026, Vorschlag A): Emin Blue Guardian 100k Phase 2 — drei heutige Pläne mit 5,0 / 5,2 / 4,4 Lot ohne Marge-Deckel
-- (636678 / 636175 / 636193; 636175 und 636193 scheiterten in der Vorprüfung „zu wenig freie Marge, nötig 135.8xx / 115.1xx, frei 100.000“).
-- Ursache: der MG3-Firmen-Rückfall nahm nur Konten derselben Kontoart — Phase 2 hatte noch keinen Lernwert, Phase 1 (Deckel 3,4 Lot) schon.
-- Code-Fix BG1: mg3_vergleich_art behandelt Phase 1 = Phase 2 = Challenge als eine Klasse. Diese Datei löscht die drei Pläne, damit der Planer
-- sie MIT Deckel neu plant (heute ist Emins Startfenster 07:00–15:15 dt. Zeit vorbei → der Nachtlauf plant sie für morgen).
-- NUR DATEI, vom Master einzuspielen, ERST NACH dem Push von BG1 (sonst plant der Nachtlauf wieder ohne Deckel). Eine Transaktion:
--   1) Sicherung in bg1_emin_plaene_20261124 (bricht ab, falls die Tabelle schon existiert = Datei lief schon), RLS an.
--   2) Lernwerte „Marge je Lot“ der zwei gescheiterten Pläne in user_settings marge_je_lot sichern (wie MG3) — sonst wären sie mit dem Plan weg.
--   3) Löschen — nur, solange noch nicht gestartet/gesendet; ein Claim zählt nur, wenn er belegt in der Vorprüfung endete („… nichts gesendet“).

begin;

create temp table bg1_ziel on commit drop as
select p.id
from trade_plans p
where p.id in ('54787d28-2f5d-4fd7-a2f2-6dd4051fe9e0',   -- 100k 636678 → Phase 2 · 5,0 Lot · nie geclaimt
               'f5e9e014-deeb-4a20-b77d-7724e8429ee5',   -- 100k 636175 → Phase 2 · 5,2 Lot · Vorprüfung Marge
               '86bbd17e-2801-48c7-98fe-2c61c6c51ffe')   -- 100k 636193 → Phase 2 · 4,4 Lot · Vorprüfung Marge
  and p.planned_for = '2026-11-24'
  and p.status = 'planned'
  and p.started_at is null
  and p.orbit_gesendet_at is null
  and p.hand_werte_at is null
  and (p.start_um_gestartet_at is null
       or (p.mt5_baseline->'start_fehler'->>'msg' ilike '%Vorprüfung%zu wenig freie Marge%'
           and (p.mt5_baseline->'start_fehler'->>'at')::timestamptz >= p.start_um_gestartet_at));   -- nur, wenn DIESER Claim in der Vorprüfung endete

-- 1) Sicherung
create table bg1_emin_plaene_20261124 as
select p.*, now() as gesichert_at from trade_plans p where p.id in (select id from bg1_ziel);
alter table public.bg1_emin_plaene_20261124 enable row level security;

-- 2) Lernwerte je Konto (Marge je Lot = „Vorprüfung: nötig X“ ÷ Plan-Lots), bestehende Einträge der ID bleiben
insert into user_settings (user_id, key, value)
select l.user_id, 'marge_je_lot',
       jsonb_object_agg(l.master_account_id::text, jsonb_build_object('mpl', l.mpl, 'firma', l.master_firm, 'at', l.fehler_at, 'quelle', 'BG1 Vorprüfung'))
from (select s.user_id, s.master_account_id, s.master_firm, s.mt5_baseline->'start_fehler'->>'at' as fehler_at,
             round(regexp_replace(substring(s.mt5_baseline->'start_fehler'->>'msg' from 'Vorprüfung: nötig ([0-9][0-9   .]*?), frei'),
                                  '[   ]', '', 'g')::numeric / nullif(s.master_contracts, 0), 2) as mpl
      from bg1_emin_plaene_20261124 s
      where s.mt5_baseline->'start_fehler'->>'msg' ilike '%Vorprüfung: nötig%') l
where l.mpl > 0
group by l.user_id
on conflict (user_id, key) do update set value = user_settings.value || excluded.value, updated_at = now();

-- 3) Löschen (gleiche Bedingungen, gegen ein Rennen mit dem PC-Tab)
delete from trade_plans p
where p.id in (select id from bg1_ziel)
  and p.status = 'planned'
  and p.started_at is null
  and p.orbit_gesendet_at is null
  and p.hand_werte_at is null
  and (p.start_um_gestartet_at is null
       or (p.mt5_baseline->'start_fehler'->>'msg' ilike '%Vorprüfung%zu wenig freie Marge%'
           and (p.mt5_baseline->'start_fehler'->>'at')::timestamptz >= p.start_um_gestartet_at));

-- Kontrolle vor dem commit: gesichert = 3 (bzw. weniger, falls inzwischen gestartet), noch_da 0
select (select count(*) from bg1_emin_plaene_20261124) as gesichert,
       (select count(*) from trade_plans where id in (select id from bg1_ziel)) as noch_da;

commit;

-- Rückweg (nur VOR dem Neuplanen): insert into trade_plans (<Spaltenliste>) select <Spaltenliste> from bg1_emin_plaene_20261124 on conflict (id) do nothing;
