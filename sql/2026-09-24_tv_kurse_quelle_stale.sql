-- 2026-09-24 (spät): tv_kurse um Quelle, Stale und Modus erweitern (Kurs-Feed 0.7.0/0.8.0).
-- Die Brücke (Session „Teste") schreibt je Wurzel eine Zeile <pc>:NQ / <pc>:MNQ und will
-- mitgeben, WOHER der Kurs stammt und ob er frisch ist — ohne die Spalten würde der ganze
-- Upsert an einer unbekannten Spalte scheitern (PostgREST lehnt die Zeile komplett ab).
--   quelle  'ws' (TradingViews Socket, auch verdeckt) | 'legende' (Sell/Buy-Knöpfe) | 'titel'
--   stale   kein neuer Wert > 45 s oder Empfang > 45 s (Userscript/reader-server-Urteil)
--   modus   'streaming' | 'delayed_streaming_600' — 'delayed' = TradingView-CME-Abo auf dem
--           PC nicht aktiv, Kurse 10 min alt mit frischem Zeitstempel (Markt-Kopf warnt)
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.tv_kurse add column if not exists quelle text not null default '';
alter table public.tv_kurse add column if not exists stale  boolean not null default false;
alter table public.tv_kurse add column if not exists modus  text;
comment on column public.tv_kurse.quelle is 'ws | legende | titel (Kurs-Feed 0.8.0)';
comment on column public.tv_kurse.stale  is 'kein neuer Wert / Empfang > 45 s';
comment on column public.tv_kurse.modus  is 'streaming | delayed_streaming_600 (delayed = kein CME-Abo)';
