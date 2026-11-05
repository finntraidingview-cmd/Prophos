-- RÜCKBAU UNT0 (sql/2026-11-05_unt0_ohne_unternehmen.sql): die Live-Fassungen vom 05.11.2026 vor dem Einspielen (pg_get_functiondef / pg_get_viewdef
-- / pg_get_triggerdef, gelesen von S4). Danach landet eine neue ID wieder automatisch in „Hermann Technologies".
-- IDs, die inzwischen OHNE Zeile registriert wurden, bleiben ohne Zeile — sie zählen nach dem Rückbau wieder als HT (alte Logik). Wer sie lieber
-- ausdrücklich in HT haben will: insert into public.id_gruppe_mitglied (user_id, gruppe_id) select u.id, g.id from auth.users u, public.id_gruppen g
--   where g.verwalter_user_id is null and not exists (select 1 from public.id_gruppe_mitglied m where m.user_id = u.id)
--     and not exists (select 1 from public.id_gruppen v where v.verwalter_user_id = u.id);

begin;

CREATE OR REPLACE FUNCTION public.admin_nur_eigene()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select exists (select 1 from public.admin_zugang z where z.user_id = auth.uid() and z.nur_eigene)
      or exists (select 1 from public.id_gruppen g where g.verwalter_user_id = auth.uid())
      or exists (select 1 from public.id_gruppe_mitglied m
                   join public.id_gruppen g on g.id = m.gruppe_id
                  where m.user_id = auth.uid() and g.verwalter_user_id is not null);
$function$;

create or replace view public.id_gruppen_uebersicht as
 SELECT COALESCE(g.name, 'Hermann Technologies (ohne Zeile)'::text) AS gruppe,
        CASE
            WHEN g.verwalter_user_id IS NULL THEN NULL::text
            ELSE COALESCE(NULLIF(v.raw_user_meta_data ->> 'name'::text, ''::text), "left"(v.id::text, 8))
        END AS verwalter,
    COALESCE(NULLIF(u.raw_user_meta_data ->> 'name'::text, ''::text), "left"(u.id::text, 8)) AS mitglied,
    u.id AS user_id,
    m.seit,
    m.notiz
   FROM auth.users u
     LEFT JOIN id_gruppe_mitglied m ON m.user_id = u.id
     LEFT JOIN id_gruppen g ON g.id = m.gruppe_id
     LEFT JOIN auth.users v ON v.id = g.verwalter_user_id
  ORDER BY (g.verwalter_user_id IS NOT NULL), (COALESCE(g.name, 'Hermann Technologies (ohne Zeile)'::text)), (COALESCE(NULLIF(u.raw_user_meta_data ->> 'name'::text, ''::text), "left"(u.id::text, 8)));

-- Funktion id_gruppe_neu_ht() ist unverändert geblieben (md5 ebfab840dc6e1a439c07e19736cd3265) — nur der Trigger wird wieder angelegt
drop trigger if exists id_gruppe_neu_ht on auth.users;
CREATE TRIGGER id_gruppe_neu_ht AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.id_gruppe_neu_ht();

commit;
