-- ============================================================================
-- Prophos: order_signale — Remote-Trade-Signale (Handy/Mac → PC → Puls)
--
-- Finns Feature (28.08.2026): Trade am Handy oder Mac planen, dann „Trade
-- automatisch starten" — der Knopf schreibt EINE Zeile hierher. Der Prophos-
-- Tab auf dem PC (pollt eh alle 5s) sieht sie, prüft ob der Plan zu einer
-- SEINER Copier-Instanzen gehört, claimt race-sicher (Update nur solange
-- status='wartet') und startet denselben Trade-Start-Check wie der lokale
-- Klick — bei Grün platziert Puls (der Order-Bot) die Order im Terminal.
-- Das IP-Bild bleibt unverändert: das Handy redet nie mit der Prop-Firma,
-- der PC holt sich das Signal AUSGEHEND aus der Cloud (Muster mirror_control
-- „Stufe 2", die 29.07.2026 bewusst nie gebaut wurde — das hier ist sie).
--
-- BEWUSST MIT Per-User-RLS — anders als mt5_live/dup_live (geteilte Sicht):
-- ein Order-AUSLÖSE-Kanal, den jedes eingeloggte Profil beschreiben könnte,
-- wäre die schärfste Ausprägung der offenen Rollen-Frage (Offene Punkte
-- 227/245/310/320). So kann nur das eigene Profil Signale anlegen, und der
-- PC führt nur Signale des dort eingeloggten Profils aus.
--
-- Status-Kette:  wartet → laeuft → fertig | fehler
--                wartet → verworfen  (Absender bricht ab, solange kein Claim)
--                wartet → verfallen  (Frische-Gate: älter 3 min wird NIE
--                                     ausgeführt — ein PC, der Stunden später
--                                     aufwacht, darf keine alte Order feuern)
-- ergebnis trägt die Puls-Antwort (Preis/Ticket/SL/TP bzw. Fehlertext) —
-- damit die „SL/TP von Hand nachtragen!"-Warnung auch am Handy ankommt.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.order_signale (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid(),
  plan_id    text not null,                            -- trade_plans.id (als Text, wie überall im Frontend)
  params     jsonb not null,                           -- {symbol, richtung, volumen, sl_usd, tp_usd}
  status     text not null default 'wartet',           -- wartet|laeuft|fertig|fehler|verworfen|verfallen
  ergebnis   jsonb,                                    -- Rückmeldung des PCs (Puls-Antwort / Fehlertext)
  pc         text,                                     -- prophos_pc_id des PCs, der geclaimt hat
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Der Empfänger-Tick fragt nur offene Signale ab.
create index if not exists order_signale_status_idx on public.order_signale (status, created_at);

alter table public.order_signale enable row level security;

drop policy if exists "order_signale eigene" on public.order_signale;

-- Nur die EIGENEN Signale — lesen, anlegen, updaten, löschen. Kein fremdes
-- Profil kann auf diesem Kanal eine Order auslösen oder mitlesen.
create policy "order_signale eigene" on public.order_signale
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());
