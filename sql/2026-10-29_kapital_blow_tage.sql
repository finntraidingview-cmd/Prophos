-- ============================================================================
-- Prophos: KAPITAL — BLOW-TAG JE BEENDETER KETTE (29.10.2026)
--
-- Finn 29.10.2026 („geblowte Konten sind bei uns dicke Minus", „ok mach" auf die Kachel „Verlust beendete Konten"): die Kachel im Admin-Reiter
-- Kapital rechnet Σ (Kauf + Hedge − Payouts) der beendeten Ketten aus kapital_ketten (archiviert = true) und folgt den Zeitraum-Chips über
-- den Blow-Tag. kapital_ketten liefert den Tag nicht (Rückgabetyp bleibt unverändert) — diese Funktion liefert ihn je Kopf nach.
--   kopf_id  = Kopf der Kette (wie kapital_ketten.kopf_id)
--   arch_tag = Dubai-Tag von archive.at des Kopfes (wie kapital_ereignisse / kapital_rueckblick_tag); NULL, wenn ohne Datum archiviert
--              (zählt dann nur bei „Alles")
-- Archiv-Eintrag je Konto wie kapital_ketten: Profil des Besitzers zuerst, sonst der jüngste. Nur lesend, nur Service-Key.
-- Rücknahme: drop function public.kapital_blow_tage(uuid);
-- ============================================================================

create or replace function public.kapital_blow_tage(p_gruppe uuid)
returns table(kopf_id uuid, arch_tag date)
language sql stable
set search_path to 'public'
as $function$
  with
  mit as (select m.user_id from id_gruppe_mitglied m where m.gruppe_id = p_gruppe),
  acc as materialized (select a.id, a.user_id from accounts a where a.user_id in (select user_id from mit)),
  arch as (
    select distinct on (e.key) e.key acc_id,
           coalesce((e.value->>'archived')::boolean, false) archiviert,
           case when coalesce(e.value->>'at', '') ~ '^\d{4}-\d{2}-\d{2}' then ((e.value->>'at')::timestamptz at time zone 'Asia/Dubai')::date end arch_tag
    from user_settings s
    cross join lateral jsonb_each(case when jsonb_typeof(s.value) = 'object' then s.value else '{}'::jsonb end) e
    join acc on acc.id::text = e.key
    where s.key = 'archive' and jsonb_typeof(e.value) = 'object'
    order by e.key, (s.user_id = acc.user_id) desc, s.updated_at desc
  )
  select a.id, r.arch_tag from arch r join acc a on a.id::text = r.acc_id where r.archiviert
$function$;
revoke all on function public.kapital_blow_tage(uuid) from public, anon, authenticated;
grant execute on function public.kapital_blow_tage(uuid) to service_role;   -- Prüfer S7 29.10.2026 (wie kapital_ketten)
