-- 2026-09-23: Winning-Day-Farm-Haken je Konto (Finn: „nur bei Fundeds, wo ich bei Einstellungen oder
-- nach dem Trade einen Haken setzen kann ‚Zu WD-Farm hinzufügen' — manche Fundeds sind zwar funded,
-- stehen aber noch auf Anfangs-Balance"). Der Farmer nimmt NUR Konten mit wd_farm = true.
alter table public.accounts add column if not exists wd_farm boolean not null default false;

-- Nachtrag 23.09.2026 01:4x (Finn: „standardmäßig soll jede einzelne ID drin sein und auch jeder einzelne
-- Account; ich nehme dann per Klick raus, und was gespeichert ist, gilt am nächsten Tag weiter"):
-- Vorgabe TRUE, und alle bestehenden Funded/Live-Konten bei Futures-Firmen sind ab jetzt drin.
alter table public.accounts alter column wd_farm set default true;
update public.accounts set wd_farm = true
 where account_type in ('funded', 'live')
   and firm ~* 'tradeify|apex|topstep|futur|mffu|lucid';
