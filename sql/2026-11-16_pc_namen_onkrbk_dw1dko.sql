-- PN1 (16.11.2026): zwei PCs ohne Eintrag in pc_namen. Zuordnung aus der DB belegt (Slave 6):
--  pc-onkrbk → Emin: alle mt5_live-Instanzen (status.user_id), 369 order_signale und 28 tv_konten tragen dieselbe
--             user_id; das ist die ID „Emin“ (auth-Name + id_gruppen „Emin“). Zweiter PC dieser ID: pc-jjlr74 (auch ohne Namen).
--  pc-dw1dko → Artur: alle 19 mt5_live-Instanzen und 56 order_signale tragen eine einzige user_id, auth-Name „Artur“.
-- Idempotent: nochmal ausführen ändert nichts außer updated_at.
insert into public.pc_namen (pc_id, name, updated_at) values
  ('pc-onkrbk', 'Emin',  now()),
  ('pc-dw1dko', 'Artur', now())
on conflict (pc_id) do update set name = excluded.name, updated_at = now();
