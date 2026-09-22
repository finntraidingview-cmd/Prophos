-- ============================================================================
-- Prophos: Benachrichtigungen aufs Handy — Geräte-Anmeldungen (22.09.2026)
--
-- Finn: „gehts nicht ans handy" / „prophos liegt auf meinem home bildschrim"
-- → Web Push über einen Service Worker (sw.js). Bisher gab es nur
-- `new Notification(...)` aus einem OFFENEN Tab; iOS zeigt das nicht, auch
-- nicht in der installierten Web-App, und wenn alles zu ist kam ohnehin nie
-- etwas an.
--
-- push_geraete: eine Zeile pro Gerät und Login. Der Browser vergibt beim
--   Anmelden eine endpoint-Adresse beim Push-Dienst (Apple/Google/Mozilla)
--   plus zwei Schlüssel, mit denen die Nachricht verschlüsselt wird. Nur wer
--   diese drei Werte hat, kann an das Gerät senden — deshalb sind sie
--   Geheimnisse und liegen unter Per-User-RLS wie order_signale.
--
-- Warum `endpoint` eindeutig ist: meldet sich dasselbe Gerät erneut an (nach
--   Neuinstallation, Berechtigung erneut erteilt, Schlüssel-Rotation), liefert
--   der Push-Dienst dieselbe oder eine neue endpoint-Adresse. Bei derselben
--   soll die Zeile AKTUALISIERT werden statt ein Duplikat zu erzeugen — sonst
--   bekäme Finn jede Meldung doppelt. Darum upsert on conflict (endpoint).
--
-- zuletzt_ok_at / letzter_fehler: damit in den Einstellungen sichtbar ist,
--   welches Gerät wirklich noch erreicht wird. Tote Anmeldungen (der Dienst
--   antwortet 404/410) löscht das Backend selbst — ein Handy, das Finn
--   zurücksetzt, würde sonst ewig als Empfänger mitlaufen.
--
-- Im Supabase SQL Editor einfügen und auf „Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.push_geraete (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null default auth.uid(),
  endpoint       text not null unique,
  p256dh         text not null,
  auth           text not null,
  geraet         text,                     -- „iPhone · Safari", frei beschriftbar
  erstellt_at    timestamptz not null default now(),
  zuletzt_ok_at  timestamptz,
  letzter_fehler text
);

create index if not exists push_geraete_user_idx on public.push_geraete (user_id);

alter table public.push_geraete enable row level security;
drop policy if exists "push_geraete eigene" on public.push_geraete;
create policy "push_geraete eigene" on public.push_geraete
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
