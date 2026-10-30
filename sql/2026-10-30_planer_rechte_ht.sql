-- PLANER-RECHTE HT (Finn 30.10.2026 ~08:30): in der Gruppe Hermann Technologies dürfen NUR „Finn + Pascal" und „Pascal" in Challenge Planer,
-- Funded Planer (CFD + Futures) und Winning Days etwas ändern; alle anderen HT-IDs nur ansehen (app.py _planer_schreib_gate → 403).
-- Regel = Tabelle admin_voll (dieselbe wie für Payout erhalten / Hedge-Freigabe, sql/2026-10-30_admin_voll.sql — die war live NIE
-- eingespielt, deshalb griff die Hedge-Freigabe bei Pascal nicht, Marc …7231). Diese Datei legt sie an, falls sie fehlt, und füllt sie mit
-- den Mail-Lesern („Finn + Pascal", „Pascal"). In den Planer-Routen gelten admin_voll-Logins wie ein Admin (_planer_admin_auth).
-- Lesen/Schreiben nur Service-Key (RLS an, keine Policy) — kein Login kann sich selbst eintragen. Keine E-Mail im Repo, nur user_ids.
-- Weitere Schreiber: eine Zeile mehr. Entziehen: delete from public.admin_voll where user_id = '<uuid>';  (Backend kennt es nach ≤ 60 s)
-- Idempotent.
create table if not exists public.admin_voll (
  user_id uuid primary key references auth.users(id) on delete cascade,
  seit    timestamptz not null default now()
);
alter table public.admin_voll enable row level security;
insert into public.admin_voll (user_id) select user_id from public.admin_mail_leser on conflict do nothing;

-- Probe (nur lesen): wer darf schreiben
-- select v.user_id, u.raw_user_meta_data->>'name' from public.admin_voll v join auth.users u on u.id = v.user_id;
