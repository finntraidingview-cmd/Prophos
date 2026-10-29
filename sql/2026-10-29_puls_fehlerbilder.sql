-- PULS-FEHLERFOTO (29.10.2026, Finn: „Wenn Fehler kommt, immer mit Screenshots arbeiten, ist eine gute Idee. Kannst einfach direkt
-- schon bauen."). Slave 7, nach Prüfer-OK spielt der Master ein. Wiederholbar.
--
-- Weg: Endet ein Puls-Lauf mit ok false, fotografiert der Bot entkoppelt den ganzen Bildschirm (+ den Puls-Chrome-Tab) und lädt über
-- Railway POST /puls-fehlerbild/<pc> hoch (der Bot hat keinen Supabase-Schlüssel; app.py lädt mit dem Service-Key). Ablage:
--   puls-fehlerbilder/<pc>/<JJJJ-MM-TT>/<id>-bildschirm.jpg   und   …/<id>-tab.jpg
-- Den Präfix <pc>/<JJJJ-MM-TT>/<id> gibt der Bot als „fehlerbild" zurück: er landet in order_signale.ergebnis (PC-Tab-Rückmeldung) und
-- als bild_pfad in puls_fehlstarts (sfMelden). Ansehen: GET /admin/puls-fehlerbild?pfad=<präfix>&art=bildschirm|tab (5-min-Link) oder
-- Supabase-Storage, siehe .claude/fehler-analyse.md.

-- 1) Privater Bucket, nur JPEG, ≤ 400 KB. KEINE Policies auf storage.objects für diesen Bucket: anon/authenticated dürfen nichts
--    (RLS ist auf storage.objects an), nur der Service-Key von Railway lädt hoch (x-upsert false = nie überschreiben) und signiert
--    Lese-Links. Kein Löschen, kein Auto-Löschen.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('puls-fehlerbilder', 'puls-fehlerbilder', false, 409600, array['image/jpeg'])
on conflict (id) do nothing;

-- 2) Spalte an puls_fehlstarts (bestehende RLS: insert/select nur eigene Zeilen — gilt unverändert auch für bild_pfad).
alter table public.puls_fehlstarts add column if not exists bild_pfad text;
alter table public.puls_fehlstarts drop constraint if exists puls_fehlstarts_bild_pfad_form;
alter table public.puls_fehlstarts add constraint puls_fehlstarts_bild_pfad_form
  check (bild_pfad is null or bild_pfad ~ '^pc-[a-z0-9]{4,12}/[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$');

-- 3) Views: Ereignisse tragen das Bild (Fehlstart: bild_pfad, Signal: ergebnis.fehlerbild), das Muster das jüngste Bild.
--    Neue Spalten nur hinten angehängt → create or replace reicht, security_invoker wie bisher (RLS des Lesers).
create or replace view public.puls_fehler_ereignisse with (security_invoker = true) as
  select f.at, f.user_id, f.plan_id, f.route, f.pc, f.schritt, f.msg, f.unklar, 'start_um'::text as quelle, f.bild_pfad
    from public.puls_fehlstarts f
  union all
  select s.created_at, s.user_id, s.plan_id, null, s.pc,
         coalesce(s.ergebnis->>'schritt', s.ergebnis->>'code', s.params->>'aktion', 'signal'), s.ergebnis->>'msg',
         coalesce((s.ergebnis->>'unklar')::boolean, false), 'signal',
         case when s.ergebnis->>'fehlerbild' ~ '^pc-[a-z0-9]{4,12}/[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$'
              then s.ergebnis->>'fehlerbild' end
    from public.order_signale s where s.status = 'fehler';

create or replace view public.puls_fehler_muster with (security_invoker = true) as
  select public.puls_fehler_muster_text(e.schritt, e.msg) as muster,
         count(*) filter (where e.at > now() - interval '24 hours') as n_24h,
         count(*) filter (where e.at > now() - interval '7 days') as n_7d,
         count(*) filter (where e.at > now() - interval '30 days') as n_30d,
         count(*) filter (where e.unklar) as n_unklar,
         array_agg(distinct e.pc) filter (where e.pc is not null) as pcs,
         count(distinct e.user_id) as ids,
         max(e.at) as zuletzt,
         (array_agg(e.msg order by e.at desc))[1] as beispiel,
         (array_agg(e.bild_pfad order by e.at desc) filter (where e.bild_pfad is not null))[1] as bild
    from public.puls_fehler_ereignisse e
   group by 1;

-- Kontrolle:
-- select id, public, file_size_limit, allowed_mime_types from storage.buckets where id = 'puls-fehlerbilder';
-- select count(*) from pg_policies where schemaname = 'storage' and tablename = 'objects' and qual ilike '%puls-fehlerbilder%';   -- 0
-- select muster, n_24h, zuletzt, bild from public.puls_fehler_muster order by zuletzt desc limit 10;
-- select name, created_at, metadata->>'size' from storage.objects where bucket_id = 'puls-fehlerbilder' order by created_at desc limit 20;
