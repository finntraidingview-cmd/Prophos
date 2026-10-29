-- Meta Wallet: optionaler Name/Label je Wallet (29.10.2026, Finn: „Wir wollen künftig mit mehr Wallets arbeiten … geordneter nach Person
-- sein — eine Person kann mehrere Wallets haben"). Nur eine Spalte, keine Daten werden umgeschrieben.
-- Mehrere Wallets je Person gingen schon immer: id_wallets hat nur UNIQUE (chain, address), kein Limit je Person
-- („bis zu sechs Adressen" stand nur im Text der Oberfläche). Ethereum + Arbitrum derselben Adresse = zwei Zeilen (je Chain eine),
-- das erlaubt der bestehende Schlüssel (chain, address).
-- Ohne diese Spalte läuft die Oberfläche weiter, nur das Feld „Name (optional)" wird dann nicht gespeichert (Hinweis im Formular).
alter table public.id_wallets add column if not exists label text;
