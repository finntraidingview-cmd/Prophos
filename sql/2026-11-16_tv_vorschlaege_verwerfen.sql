-- TV1 TV-VORSCHLÄGE VERWERFEN (16.11.2026, Finn über den Master zu „FTMO110764 · FTMO Futures · zu bestätigen · aus TV“ unter Accounts:
-- „Mach dieses ‚bestätigen' komplett weg. Wir fügen die Accounts immer alle manuell hinzu. Alles verwerfen, das nutzen wir nicht.“).
-- Das Frontend zeigt unter Accounts seit TV1 keine Vorschlags-Zeilen mehr (Mail seit MV1 11.11.2026). Diese Datei verwirft die offenen TV-Vorschläge
-- GENAU wie der Knopf „Verwerfen“ (POST /konto-verwerfen, app.py konto_verwerfen) — beide Schritte, nichts wird gelöscht:
--   1. user_settings key 'konto_verworfen' der Besitzer-ID += {EXT normiert: Zeitpunkt}
--   2. tv_konten.ignoriert_at = jetzt (nur Zeilen mit ignoriert_at is null)
-- Wirkung wie der Klick: die Zeilen verschwinden auch in Admin → Alle Accounts UND im Reiter „Konten aus Mail & TV“ (der blendet TV-Zeilen mit
-- ignoriert_at aus und Zeilen „neu“, deren Nummer in konto_verworfen steht — eine Mail-Zeile mit derselben Nummer also ebenfalls).
--
-- OFFEN = was Accounts bis TV1 als Vorschlag zeigte (tvOffen + /tv-konten/mein), bewusst eng:
--   · nur IDs der Gruppe „Hermann Technologies“ (id_gruppe_mitglied) — Emins Gruppe bleibt unberührt (zwei Unternehmen getrennt)
--   · zuletzt_at in den letzten 60 Tagen (Fenster von /tv-konten/mein), ignoriert_at is null, angelegt_account_id is null
--   · bei derselben ID KEIN Konto in accounts (archivierte eingeschlossen, das Archiv liegt in user_settings) — „schon da“ ist jede dieser Formen:
--       External ID gleich (nur A–Z/0–9) · External ID gleich in Apex-Form (tv_konto_normal: PA-APEX-685010-01 → PAAPEX6850100000001) ·
--       ein Wort des Kontonamens gleich in Apex-Form (tv_konto_in_prophos) · Nummer im Kontonamen enthalten (tvSchonDa im Frontend, weiter)
-- Stand 16.11.2026 ~16:00 Dubai (Slave 4, nur gelesen): 239 Zeilen in tv_konten, davon 232 schon als Konto da, 5 offen — 3 FTMO Futures bei einer
-- HT-ID (zuerst 16.11. 11:34 Berlin, pc-c19p2l), 2 Tradeify bei einer anderen HT-ID (zuerst 16.11. 00:17 Berlin); keiner schon verworfen.
-- VOR DEM EINSPIELEN die Vorschau unten laufen lassen (muss dieselben 5 bzw. nur neu dazugekommene HT-Zeilen zeigen). Keine IDs oder Nummern in
-- dieser Datei — die Auswahl ergibt sich aus der Regel.
-- Normierung des Schlüssels wie admin_konto_ext_norm / kontoKey: Großbuchstaben, nur A–Z und 0–9 (tv_konten.name ist schon tv_konto_normal).
-- IDEMPOTENT: vorhandene Verworfen-Zeitpunkte bleiben (bestehender Wert gewinnt); sind alle Schlüssel schon da, wird in user_settings nichts
-- geschrieben; ein zweiter Lauf findet keine offenen Zeilen mehr (ignoriert_at gesetzt). Eine Anweisung: Schritt 1 und 2 sehen denselben Stand.
-- KONTO_VERWORFEN_MAX (500, app.py) kürzt erst der nächste Klick — heute 1 Eintrag bei der betroffenen ID, harmlos.
-- Einspielen nur auf des Masters bzw. Finns Wort (execute_sql, DML).

with ht as (
  select m.user_id from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
  where g.name = 'Hermann Technologies'
), konto_keys as (   -- je Konto alle „schon da“-Schlüssel (gleich-Vergleich)
  select a.user_id, k
  from public.accounts a
  cross join lateral (
    select upper(regexp_replace(coalesce(a.external_id, ''), '[^A-Za-z0-9]', '', 'g')) as k
    union all
    select (case when w like 'PA-%' then 'PAAPEX' else 'APEX' end) || substring(w from '^(?:PA-)?APEX-([0-9]+)-') || lpad(substring(w from '-([0-9]{1,3})$'), 7, '0')
    from (select upper(trim(coalesce(a.external_id, ''))) as w
          union all
          select upper(x[1]) from regexp_matches(coalesce(a.name, ''), '[A-Za-z0-9_-]{6,}', 'g') as x) ww
    where w ~ '^(PA-)?APEX-[0-9]{5,}-[0-9]{1,3}$'
  ) s
  where a.user_id in (select user_id from ht)
), offen as (
  select t.user_id, t.name, upper(regexp_replace(t.name, '[^A-Za-z0-9]', '', 'g')) as ext
  from public.tv_konten t
  where t.user_id in (select user_id from ht)
    and t.zuletzt_at > now() - interval '60 days'
    and t.ignoriert_at is null
    and t.angelegt_account_id is null
    and length(upper(regexp_replace(t.name, '[^A-Za-z0-9]', '', 'g'))) between 6 and 64      -- wie konto_verwerfen (ext ungültig → 400)
    and not exists (select 1 from konto_keys kk where kk.user_id = t.user_id and kk.k = upper(regexp_replace(t.name, '[^A-Za-z0-9]', '', 'g')))
    and not exists (select 1 from public.accounts a where a.user_id = t.user_id
                      and upper(regexp_replace(coalesce(a.name, ''), '[^A-Za-z0-9]', '', 'g')) like '%' || upper(regexp_replace(t.name, '[^A-Za-z0-9]', '', 'g')) || '%')
), je_id as (
  select user_id,
         jsonb_object_agg(ext, to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')) as wert
  from offen group by user_id
), verworfen as (
  insert into public.user_settings (user_id, key, value, updated_at)
  select user_id, 'konto_verworfen', wert, now() from je_id
  on conflict (user_id, key) do update
    set value = excluded.value || public.user_settings.value,   -- bestehender Wert rechts = gewinnt (alte Zeitpunkte bleiben)
        updated_at = now()
    where not (public.user_settings.value ?& array(select jsonb_object_keys(excluded.value)))   -- alles schon verworfen → nichts schreiben
  returning user_id
)
update public.tv_konten t
   set ignoriert_at = now()
  from offen o
 where t.user_id = o.user_id
   and t.name = o.name
   and t.ignoriert_at is null;

-- Vorschau (vor dem Einspielen) und Kontrolle (danach → 0 Zeilen): die CTEs ht, konto_keys, offen von oben kopieren, dann
--   select left(user_id::text, 8) as id, name from offen order by 1, 2;
-- Rücknahme (eine Zeile; <EXT> = Name nur A–Z/0–9):
--   update public.tv_konten set ignoriert_at = null where user_id = '<uuid>' and name = '<NAME>';
--   update public.user_settings set value = value - '<EXT>' where user_id = '<uuid>' and key = 'konto_verworfen';
