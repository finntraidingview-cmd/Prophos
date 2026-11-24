-- AG2 Daten (Master 24.11.2026): offene Ausgleich-Pläne mit falschem Fehlbetrag geprüft — KEINER (kein planned/open Plan mit mt5_baseline.wd_ausgleich, alle IDs).
-- Gegenprobe Balance ↔ Trade-Summe über alle Tradeify-/Lucid-WD-Konten mit Payout-Anfrage (Stand ~20:00 Dubai):
--   * Mike Tradeify …5297: Balance +29,96 / Trades +4.529,96 (Abbuchung 4.500 $ nach dem ersten Zyklus-Trade) — nicht korrigierbar (kein Trade), bis zum nächsten
--     Payout „unbekannt“: kein Ausgleich, beide im Plus → Payout nicht gesperrt. Nichts zu tun.
--   * Finn + Pascal Lucid …0001: Balance −1.680 / Trades +907,50 — Trade ec83e13a (23.11., Recovery) steht mit master_pl −180,50 (TV „Total P/L“), die Balance fiel
--     156.844 → 154.076 = −2.768,00 $ (Befund BS1, Fix .2294 wirkt nur für neue Nachlesungen). Nach AG2 bliebe das Konto deshalb „unbekannt“ (kein Ausgleich, ⚪)
--     → hier der P&L auf die Balance-Differenz (BS1-Regel: die Balance-Differenz ist der Master-P&L). Danach Balance = Trades = −1.680 → Ausgleich wieder automatisch.
--   * Aurel …2766, Chris …4657/…0729, Mike …3058: Abweichungen 1.300–5.400 $, Konten stehen an der WD-Liq (~150.000) — kein WD mehr, nichts zu tun.
--   * Emin …8522 (Gruppe Emin): −557,82 $ — Emins Unternehmen, nicht angefasst.
-- Idempotent (Guard auf den alten Wert), Sicherung des alten Werts im result_notes-Anhang. Prüfer-Pflicht: DB-Schreiblogik → erst nach OK.

update public.trade_plans p
set master_pl = -2768.00,
    result_notes = coalesce(p.result_notes || E'\n', '') || 'AG2 24.11.2026: master_pl −180,50 → −2.768,00 (Balance 156.844 → 154.076; TV „Total P/L“ las falsch, BS1)',
    updated_at = now()
where p.id = 'ec83e13a-fd74-4fbe-8c70-3a4ea874d4e9'
  and p.master_pl = -180.50
  and p.status = 'completed'
  and (p.mt5_baseline->'tv'->>'balance_start')::numeric = 156844
returning left(p.id::text, 8) id, p.master_pl;
