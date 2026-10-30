-- NOTIZ JE KONTO IN RADAR → BESTANDEN → REVIEW (Finn 30.10.2026: „Bei Review noch Notizen schreiben können, zum Beispiel bei Marc: ‚OK, warten auf KYC'").
-- Eigene Spalte statt accounts.notes: dort schreibt der Winning-Days-Übergang („Winning Days seit …") und der Konto-Dialog speichert das Feld mit.
-- Nur Anzeige im Radar, kein Planer, kein Abhaken. Ohne Spalte läuft der Radar weiter, nur „Notiz speichern“ meldet 409. Wiederholbar.
alter table public.accounts add column if not exists review_notiz text;
comment on column public.accounts.review_notiz is 'Kurze Notiz im Radar unter Bestanden → Review, nur Anzeige (30.10.2026)';
