-- ============================================================================
-- Prophos: dup_live.user_id — wem gehört das Duplikium-Konto?
--
-- Nachtrag zu 2026-08-25_dup_live.sql (gleicher Abend): Finns Layout-Ansage
-- für die Flotte ist EINE Farbe pro PERSON — nicht pro Account. Der Wächter
-- kennt die Zuordnung längst (duplikum_credentials: user_id ↔ E-Mail) und
-- schreibt sie ab jetzt in jede dup_live-Zeile mit. Das Frontend gruppiert
-- damit direkt nach Person, ohne Login-Raterei über /admin/overview.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.dup_live add column if not exists user_id text not null default '';
