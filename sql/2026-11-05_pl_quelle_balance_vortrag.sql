-- AB3b (05.11.2026, Master nach AB3, Fall Blue Guardian 100k …7770, Hand-Nachtrade 7869ea6c): neue P&L-Herkunft 'balance_vortrag'.
-- Ein von Hand gestarteter Echo-Trade ohne Start-Balance (Master-Terminal im Standby) bekommt im Abhak-Dialog jetzt den P&L
-- „Endbalance − Endbalance des letzten Trades desselben Kontos“ vorbelegt (app.py echo_vortrag, prophos.html ab3Vortrag). Wird er
-- unverändert übernommen, steht am Plan pl_quelle = 'balance_vortrag' statt 'hand' (Finn soll sehen, woher der Wert kam).
-- Der Check erlaubte bisher nur echo/tv/duplikum/hand. Idempotent. VOR dem Frontend-/Backend-Push einspielen — ohne diese Datei
-- speichert das Trades-Popup ohne pl_quelle (Rückfall bei Fehlertext „pl_quelle“), der Radar-Weg (Railway) scheitert am Check.

alter table public.trade_plans drop constraint if exists trade_plans_pl_quelle_check;
alter table public.trade_plans add constraint trade_plans_pl_quelle_check
  check (pl_quelle is null or pl_quelle = any (array['echo'::text, 'tv'::text, 'duplikum'::text, 'hand'::text, 'balance_vortrag'::text]));

-- Kontrolle:
-- select pg_get_constraintdef(oid) from pg_constraint where conname = 'trade_plans_pl_quelle_check';

-- RÜCKBAU (vorher alle Zeilen mit 'balance_vortrag' auf 'hand' setzen):
-- update public.trade_plans set pl_quelle = 'hand' where pl_quelle = 'balance_vortrag';
-- alter table public.trade_plans drop constraint if exists trade_plans_pl_quelle_check;
-- alter table public.trade_plans add constraint trade_plans_pl_quelle_check
--   check (pl_quelle is null or pl_quelle = any (array['echo'::text, 'tv'::text, 'duplikum'::text, 'hand'::text]));
