-- NA1 (05.11.2026, Finn: „Es wurden gerade eben drei Accounts, die auf Review waren, zum Nachfolger hinzugefügt … die Accounts, die für
-- die Challenges waren, die bestanden waren, wurden nicht archiviert"). NICHT automatisch einspielen — Master nach Prüfer-OK.
--
-- Ursache: Seit AC3 (.2065, 892ee549, 05.11.2026 06:12 Dubai) lädt der localStorage-Hook vom Archiv nur noch den UNTERSCHIED zum vorherigen
-- lokalen Stand hoch. archivSchreibenAbgeglichen schrieb den neuen Eintrag aber vorher schon am Hook vorbei lokal hin → kein Unterschied,
-- kein Upload. Der Nachfolger-Assistent setzte parents (Cloud ✓) und rief archiveAccount(Vorgänger, 'passed', Nachfolger) (Cloud ✗).
-- Code-Fix im selben Commit (prophos.html archivSchreibenAbgeglichen → archivCloudMerge). Diese Datei holt den Bestand nach.
--
-- Was der normale Weg geschrieben hätte: user_settings(key 'archive')[Vorgänger] = {archived: true, reason: 'passed', at, successorId: Nachfolger}.
-- Die Review-Pläne der drei Vorgänger sind schon 'completed' (02.–04.11.) — an trade_plans ist nichts zu tun.
-- Auswahl: jede Kette aus user_settings 'parents', deren Nachfolger seit .2065 (05.11.2026 02:12 UTC) angelegt wurde und deren Vorgänger im
-- Cloud-Archiv NICHT archived ist. Live am 05.11.2026 ~18:30 Dubai genau 3 Zeilen, alle ID Jacob (Apex 100k …0017 → PA…0003, …0020 → PA…0004,
-- …0019 → PA…0005). Ein schon archivierter Vorgänger wird nie angefasst (auch kein anderer reason) → idempotent.
--
-- Kontrolle vorher (muss die 3 Zeilen zeigen) / nachher (muss leer sein):
--   with par as (select s.user_id, e.key kind, e.value #>> '{}' eltern from user_settings s, jsonb_each(s.value) e
--                where s.key = 'parents' and jsonb_typeof(s.value) = 'object')
--   select p.user_id, p.eltern, p.kind from par p join accounts ka on ka.id::text = p.kind
--   join user_settings ar on ar.user_id = p.user_id and ar.key = 'archive' and jsonb_typeof(ar.value) = 'object'
--   where ka.created_at > '2026-11-05 02:12+00' and coalesce((ar.value -> p.eltern ->> 'archived')::boolean, false) = false;
--
-- Rückbau (nur diese Einträge, erkennbar an "quelle": "NA1"):
--   update user_settings s set value = s.value - array(select k from jsonb_each(s.value) e(k, v) where v ->> 'quelle' = 'NA1'),
--          updated_at = now()
--   where s.key = 'archive' and jsonb_typeof(s.value) = 'object'
--     and exists (select 1 from jsonb_each(s.value) e(k, v) where v ->> 'quelle' = 'NA1');
--
-- Nur Archive, die ein jsonb-Objekt sind: ein als String/kaputt gespeicherter Wert wird nie angefasst (der Tab überschreibt ihn auch nicht,
-- archivCloudMergeLauf), und seine Ketten gelten NICHT als „nicht archiviert" (Gegenprüfung NA1). Vorher die Kontrolle lesen (genau 3 Zeilen,
-- alle Jacob) — ein seit 02:12 UTC absichtlich entarchivierter Vorgänger würde sonst wieder archiviert.

begin;

with par as (
  select s.user_id, e.key as kind, e.value #>> '{}' as eltern
  from user_settings s, jsonb_each(s.value) e
  where s.key = 'parents' and jsonb_typeof(s.value) = 'object'
), offen as (
  select p.user_id, p.eltern, p.kind, ka.created_at
  from par p
  join accounts ka on ka.id::text = p.kind
  join accounts ea on ea.id::text = p.eltern
  join user_settings ar on ar.user_id = p.user_id and ar.key = 'archive' and jsonb_typeof(ar.value) = 'object'
  where ka.created_at > '2026-11-05 02:12+00'
    and coalesce((ar.value -> p.eltern ->> 'archived')::boolean, false) = false
), je_id as (
  select user_id,
         jsonb_object_agg(eltern, jsonb_build_object(
           'archived', true, 'reason', 'passed',
           'at', to_char(created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
           'successorId', kind, 'quelle', 'NA1')) as eintraege
  from offen group by user_id
)
update user_settings s
set value = s.value || j.eintraege,
    updated_at = now()   -- Tab-Wächter (archivCloudMerge) und Radar-Abgleich (archivCloudAbgleich) sehen die Änderung
from je_id j
where s.user_id = j.user_id and s.key = 'archive' and jsonb_typeof(s.value) = 'object';

-- ID ohne archive-Zeile (live keine): Zeile anlegen
with par as (
  select s.user_id, e.key as kind, e.value #>> '{}' as eltern
  from user_settings s, jsonb_each(s.value) e
  where s.key = 'parents' and jsonb_typeof(s.value) = 'object'
)
insert into user_settings (user_id, key, value, updated_at)
select p.user_id, 'archive',
       jsonb_object_agg(p.eltern, jsonb_build_object('archived', true, 'reason', 'passed',
         'at', to_char(ka.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'), 'successorId', p.kind, 'quelle', 'NA1')),
       now()
from par p
join accounts ka on ka.id::text = p.kind
join accounts ea on ea.id::text = p.eltern
where ka.created_at > '2026-11-05 02:12+00'
  and not exists (select 1 from user_settings ar where ar.user_id = p.user_id and ar.key = 'archive')
group by p.user_id
on conflict (user_id, key) do nothing;

commit;
