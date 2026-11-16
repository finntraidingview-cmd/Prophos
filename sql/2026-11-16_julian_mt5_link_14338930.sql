-- Julian, FundedNext 100k 14338930 → Phase 1: Trade-Start-Check „MT5-Verlinkung: Keine Copier-Instanz passt zu Master – → Hedge –“
-- (Finn 16.11.2026, Screenshot). Ursache: Das Konto gibt es zweimal — 93db16ea (angelegt 18.10., archiviert) trägt den mt5_links-Eintrag,
-- der aktive Plan 9d789c66 hängt am neu angelegten 9d231861 (15.11.) ohne Link. Copier-Instanz „100k14338930Phase1“ auf pc-6qnjpu läuft (Hedge 430095).
-- Fix wie „Verknüpfung korrigieren“: den Link des archivierten Vorgängers auf das aktive Konto umhängen. Idempotent.
update public.mt5_links set account_id = '9d231861-61b9-429e-a3c1-4597f9d29520', updated_at = now()
where user_id = 'f6e166c1-d77c-45b0-8d0a-52dd22290112' and mt5_login = '14338930'
  and account_id = '93db16ea-b12c-4434-aa97-f28ad9747fcc';
