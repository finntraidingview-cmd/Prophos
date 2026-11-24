-- LC1b (Finn 24.11.2026 über den Master): „Es gibt 50ks mit 40 % und 50ks mit 50 % Consistency. Alle, die gerade im Planer sind, haben 50. Die 150er
-- haben wir immer 40 — kann unterschiedlich sein, wird beim Account-Hinzufügen in der Schablone eingegeben.“
-- Stand der Lesung 24.11. ~21:30 Dubai: Code nimmt schon den Konto-Wert zuerst (accounts.consistency_pct → ap_konten_stand_zeile cons_quelle „konto“ →
-- zw_cons_ziel / ap_cons_regel; ap_regel_konto setzt damit auch tp_max), erst ohne Konto-Wert die Vorgabe ZW_CONS_FIRMEN (seit LC1 150k 40 / 50k 50).
-- Die Schablone (bulk_vorlagen.consistency_pct) wird beim Anlegen ins Konto übernommen (prophos.html Bulk/Popup). Lücke nur in den DATEN:
--   „Lucid 50k Flex“ = 50 ✓ (alle 38 Lucid-50k-Challenges tragen 50) · „Lucid 150k Challenge“ = leer, alle aktiven 150k-Challenges leer.
-- Diese Datei: Schablone 150k auf 40 und die noch offenen Lucid-150k-Challenges (nicht markiert, nicht deaktiviert) mit leerem Wert auf 40 — damit
-- steht der Wert sichtbar am Konto (Chip „40 %“) und eine 150k-Ausnahme mit 50 % kann am Konto geändert werden. Wirkung auf Ziel/Planer: keine
-- Änderung gegenüber LC1 (Vorgabe 150k ist schon 40; tp_max 40 % × 9.000 = 3.600 wie die Regel). Markierte/bestandene Konten bleiben unberührt.
-- Idempotent (nur wo leer). NUR DATEN, nicht eingespielt — Master nach Finns Wort, nach dem Push von LC1.
update bulk_vorlagen
   set consistency_pct = 40, updated_at = now()
 where firm ilike 'lucid%' and account_type = 'challenge' and account_size = 150000 and consistency_pct is null
returning id, name, consistency_pct;

update accounts
   set consistency_pct = 40
 where firm ilike 'lucid%'
   and account_type = 'challenge'
   and consistency_pct is null
   and deaktiviert_at is null
   and ziel_erreicht_at is null
   and (account_size = 150000 or starting_balance = 150000 or name ~* '^150k\M')
returning id, name, consistency_pct;     -- Lesung 24.11.: 84 Konten (alle Hermann Technologies); „100k Lucid“ ohne Größe bleibt bewusst leer
