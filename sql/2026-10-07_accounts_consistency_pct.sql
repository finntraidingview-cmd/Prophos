-- Consistency je Konto (Finn 07.10.2026): accounts.consistency_pct (Prozent, null = Firmen-Standard aus den Kernwerten).
-- Der Auto-Planer nimmt bei Futures-Challenges den größten Tag = consistency_pct × Ziel-$ (Tradeify 150k, Ziel 9.000:
-- Standard 40 % → 3.600, mit Addon 50 % → 4.500; TP-Spanne rückt mit, z. B. [4.350, 4.450]); Kontowert und Vorrat-Chance
-- rechnen mit derselben Etappe. Das Eingabefeld im Konto-Formular baut das Frontend (Feldname genau consistency_pct).
-- Der Code liest die Spalte nur, wenn es sie gibt — vor dem Einspielen läuft alles wie bisher.

alter table public.accounts add column if not exists consistency_pct numeric;

do $$ begin
  alter table public.accounts add constraint accounts_consistency_pct_bereich
    check (consistency_pct is null or (consistency_pct > 0 and consistency_pct <= 100));
exception when duplicate_object then null; end $$;

-- Tradeify-Konten mit gebuchtem 50-%-Addon tragen „50%" im Namen (z. B. „(50% consistensy)") → 50. Nur per Name-Muster,
-- keine IDs oder Kontonummern in dieser Datei (Repo ist öffentlich).
update public.accounts
set consistency_pct = 50
where firm ilike '%tradeify%'
  and name ~* '50\s*%'
  and consistency_pct is null;

-- Prüfen:
-- select firm, name, account_type, consistency_pct from public.accounts where consistency_pct is not null;
