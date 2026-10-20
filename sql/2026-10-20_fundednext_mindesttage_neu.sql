-- MINDESTTAGE FÜR NEUE FUNDEDNEXT-PHASEN (Finn 20.10.2026 17:30 Dubai, Screenshot Accounts „100k …8074 Phase 1 → Phase 2, Tage-Spalte „–":
-- „Bei mehreren neuen FundedNext-Konten werden die Tage nicht angezeigt und nicht gesammelt — bei den alten Konten hat es endlich
-- funktioniert, bei den neuen nicht. Auch bei Marco einer.")
-- Befund 20.10.2026 (Slave 1): alle 93 FundedNext-CFD-Phasen bis 11.10. tragen goal_kind trading_days (sql/2026-10-12_fundednext_mindesttage.sql),
-- alle 15 danach angelegten (7× Phase 1 vom 14.–16.10., 8× Phase 2 vom 14.–20.10.) nicht: Hand-Formular „＋ Account" ließ das Ziel-Feld leer,
-- der Nachfolger-Assistent trug gar keine Ziel-Felder, nur die zentralen Bulk-Vorlagen setzten es. Code-Fix im selben Commit (prophos.html
-- kontoMindesttage: EINE Firmenregel für Bulk, Formular, Assistent) — dieses Skript holt die liegen gebliebenen Konten nach.
-- Regel wie 12.10.: goal_kind trading_days, goal_target 5. goal_since = Anlegetag (Berlin) des Kontos, goal_done_offset 0 — vor dem Anlegen
-- gibt es keine Pläne auf dem Konto (anders als 2026-10-13_mindesttage_rueckwirkend.sql, wo Alt-Tage vor goal_since lagen); die Tage seit dem
-- Anlegen zählen zielFortschritt (Frontend, alle Pläne) und ap_tage_ist (app.py, letzte 30 Tage) selbst aus trade_plans.started_at.
-- Nur FundedNext CFD (nicht „FundedNext Futures"), nur phase1/phase2, nur ohne goal_kind, nur nicht archivierte (Archiv = user_settings
-- key 'archive', JSON-Objekt je Konto-ID). Idempotent: beim zweiten Lauf trifft es nichts mehr (goal_kind ist dann gesetzt).
-- Nicht eingespielt — Finn/Master entscheidet. Kontrolle unten.

update accounts a
   set goal_kind = 'trading_days',
       goal_target = coalesce(a.goal_target, 5),
       goal_since = coalesce(a.goal_since, (a.created_at at time zone 'Europe/Berlin')::date),
       goal_done_offset = coalesce(a.goal_done_offset, 0),
       goal_manual = false
 where a.firm ilike 'fundednext%'
   and a.firm not ilike '%futures%'
   and a.account_type in ('phase1', 'phase2')
   and a.goal_kind is null
   and not exists (select 1 from user_settings s
                    where s.user_id = a.user_id and s.key = 'archive'
                      and jsonb_typeof(s.value) = 'object' and s.value ? a.id::text);

-- Kontrolle: Stand je Konto (Tage seit goal_since + Offset gegen das Ziel)
-- select right(coalesce(a.external_id, a.name), 4) as ende4, a.account_type, a.goal_since, a.goal_done_offset,
--        (select count(distinct (p.started_at at time zone 'Europe/Berlin')::date) from trade_plans p
--          where p.master_account_id = a.id and p.started_at is not null
--            and (p.started_at at time zone 'Europe/Berlin')::date >= a.goal_since) as tage_seit, a.goal_target
--   from accounts a where a.firm ilike 'fundednext%' and a.firm not ilike '%futures%' and a.account_type in ('phase1','phase2')
--    and a.created_at > '2026-10-11' order by a.created_at;
