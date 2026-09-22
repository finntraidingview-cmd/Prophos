-- 2026-09-23: Winning-Day-Farm-Haken je Konto (Finn: „nur bei Fundeds, wo ich bei Einstellungen oder
-- nach dem Trade einen Haken setzen kann ‚Zu WD-Farm hinzufügen' — manche Fundeds sind zwar funded,
-- stehen aber noch auf Anfangs-Balance"). Der Farmer nimmt NUR Konten mit wd_farm = true.
alter table public.accounts add column if not exists wd_farm boolean not null default false;
