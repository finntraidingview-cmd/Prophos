-- IDF1 ID „Finn“ stilllegen, NUR Konten archivieren (11.11.2026, Finn ~21:10 Dubai: „Nur Konten archivieren“ — vorher „lösch ID Finn
-- einfach“, nach dem Befund berichte/2026-11-11_IDF1_id_finn_befund.md bewusst NICHT hart gelöscht: an der ID hängen 548 Trades (+112.724 $),
-- 258 Buchungen und Payouts — ein delete auf auth.users kaskadiert und ändert Finanzen/Kapital/Gesamtkosten rückwirkend).
-- ID „Finn“ = b55d7ab4-5246-4101-abca-f729c71d17ec (seit 21.10.2026 archiviert, Arbeit nur noch über „Finn + Pascal“).
-- Was passiert: die 10 noch nicht archivierten Konten der ID werden archiviert (Format wie das Frontend) und deaktiviert → kein Planer, keine
-- Wache, kein Radar fasst sie mehr an. Login, HT-Gruppe und alle Geschichte bleiben unverändert. Idempotent (nur nicht archivierte / nicht
-- deaktivierte Konten). Rücknahme: Konten unter Accounts → Archivierte anzeigen wiederherstellen und am Stift aktivieren.

begin;

-- 1) Archivieren: nur Konten, die in der archive-Liste der ID noch nicht archiviert sind
with offen as (
  select a.id
    from public.accounts a
    left join public.user_settings us on us.user_id = a.user_id and us.key = 'archive'
   where a.user_id = 'b55d7ab4-5246-4101-abca-f729c71d17ec'
     and not coalesce((us.value->a.id::text->>'archived')::boolean, false)
)
update public.user_settings us
   set value = us.value || (select jsonb_object_agg(o.id::text, jsonb_build_object(
                              'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                              'reason', 'ID Finn stillgelegt (IDF1)', 'archived', true)) from offen o),
       updated_at = now()
 where us.user_id = 'b55d7ab4-5246-4101-abca-f729c71d17ec' and us.key = 'archive'
   and exists (select 1 from offen);

-- 2) Deaktivieren: nur die eben archivierten (Grund IDF1) und noch nicht deaktivierten Konten
update public.accounts a
   set deaktiviert_at = now()
 where a.user_id = 'b55d7ab4-5246-4101-abca-f729c71d17ec'
   and a.deaktiviert_at is null
   and exists (select 1 from public.user_settings us
                where us.user_id = a.user_id and us.key = 'archive'
                  and us.value->a.id::text->>'reason' = 'ID Finn stillgelegt (IDF1)');

commit;

-- Kontrolle (erwartet: nicht_archiviert 0, idf1 10):
-- select count(*) filter (where not coalesce((us.value->a.id::text->>'archived')::boolean, false)) nicht_archiviert,
--        count(*) filter (where us.value->a.id::text->>'reason' = 'ID Finn stillgelegt (IDF1)') idf1
--   from accounts a left join user_settings us on us.user_id = a.user_id and us.key = 'archive'
--  where a.user_id = 'b55d7ab4-5246-4101-abca-f729c71d17ec';
