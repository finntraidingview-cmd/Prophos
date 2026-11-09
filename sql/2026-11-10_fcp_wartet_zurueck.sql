-- 2026-11-10 — WP3-Merker „Waiting for Payout zurück" (Master, Finn 10.11.2026 ~01:40: „Wenn das Ziel erreicht ist, dann ab zu Waiting for Payout"; seitdem
-- stellt der Funded-CFD-Planer am echten Ziel ohne Schalter um). Setzt Finn ein Konto im Funded Planer → CFD zurück (POST /admin/funded-cfd-plan/waiting-zurueck),
-- merkt sich der Planer das hier: {at, von, balance}. balance trägt der nächste Planer-Lauf aus seiner eigenen Lesung ein; solange die Balance gleich bleibt
-- (bis nach dem nächsten Trade), stellt er das Konto nicht wieder automatisch um, danach löscht er den Merker (app.py fcp_merker_urteil).
-- Ohne diese Spalte läuft alles weiter, nur ohne Merker (der Knopf meldet merker: false).
-- Idempotent. Rückbau: alter table public.accounts drop column if exists fcp_wartet_zurueck;

alter table public.accounts add column if not exists fcp_wartet_zurueck jsonb;

comment on column public.accounts.fcp_wartet_zurueck is
  'WP3 10.11.2026: Merker „Waiting for Payout von Hand zurückgesetzt“ {at, von, balance} — Funded-CFD-Planer stellt erst nach einer Balance-Änderung wieder um';

-- Kontrolle: select id, name, fcp_wartet_zurueck from public.accounts where fcp_wartet_zurueck is not null;
