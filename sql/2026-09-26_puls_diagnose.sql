-- 2026-09-26: Puls-Diagnose je PC (Auftrag Koordination B6 „Fenster-Treue", Finn: „Puls muss immer im bestehenden
-- Chrome-Fenster bleiben … nur Tabs hinzufügen, keine Fenster"). Puls (mt5-copier/order_bot.py) schreibt bei jedem Lauf
-- über POST https://web-production-bec81.up.railway.app/puls-diagnose/<pc_id>: welches Handels-Fenster gemerkt ist
-- (puls_fenster.json: hwnd, pid, Profil, Titel), Ergebnis der Fenstersuche (gemerkt | neu | unklar | kein_chrome), die
-- Chrome-Profile des PCs (Ordner + Anzeigename) und alle gesehenen Browser-Fenster mit Profil + Ausschlussgrund.
-- Damit ist ohne PC-Zugriff sichtbar, ob die Erkennung unter Windows greift. Eine Zeile je PC, immer der letzte Lauf.
-- Nur der Service-Key (app.py) schreibt: RLS an, keine Policy. Lesen: SQL Editor / MCP.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
create table if not exists public.puls_diagnose (
  pc_id      text primary key check (pc_id ~ '^pc-[a-z0-9]{4,12}$'),
  diagnose   jsonb not null,
  at         timestamptz not null default now()
);
alter table public.puls_diagnose enable row level security;
