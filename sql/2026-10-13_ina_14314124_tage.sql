-- Ina, FundedNext 100k 14314124 Phase 1 (13.10.2026, Finn: „beide haben 3 von 5"):
-- Das Konto wurde am 08.10.2026 neu angelegt (fcfc93d1); die bisherigen Trades hängen am alten Datensatz
-- „100k funded next 14314124" (1e0903e6). Deshalb zählte zielFortschritt 0/5. Stand 3 als Offset festschreiben
-- und den von Hand angehängten Zusatz „· Trading tage sammeln" aus dem Namen nehmen — das zeigt jetzt der Typ.
update accounts
   set goal_done_offset = 3,
       name = '100k 14314124 → Phase 1'
 where id = 'fcfc93d1-4e56-4a73-b62a-8c7953603d99';
