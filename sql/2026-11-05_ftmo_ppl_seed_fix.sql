-- FTMO-PUNKTWERT IM SEED (FS1, Master 05.11.2026, Befund S2 HX1) — Slave 3. NICHT von Slave 3 eingespielt.
-- DEFAULT_FIRM_SPECS im Tab stand bei FTMO noch auf ppl 0,85. Der Seed für NEUE Logins legte damit seit 08.10.2026 eigene firm_specs-Zeilen
-- „FTMO · NAS100 · 0,85" an — nach sql/2026-10-08_ftmo_kernwerte.sql (dort alle Bestands-Zeilen auf 1,0). Richtig ist 1,0: MT5 US100.cash,
-- Kontraktgröße 1, USD → 1 $ je Punkt und Lot (alle FTMO-Konten USD). Folge bisher: Railway-Anzeigen (echo_hedge.lots, sl/tp_punkte,
-- delta_eur_pkt in Delta/Waage) bei diesen IDs um × 0,85 zu klein; echter SL und Hedge stimmen. Den Tab-Seed setzt FS1 auf 1,00.
--
-- Stand vor dem Einspielen (Select 05.11.2026): genau 7 Zeilen, 13 andere FTMO-Zeilen stehen schon auf 1,0:
--   23c6cfb2… user d55671f9 (angelegt 08.10. 22:41 Dubai) · 506d5274… fb42b5c3 (12.10.) · 632d0e64… 6c206a34 (14.10.) · f385ecf1… f6e166c1 (17.10.)
--   8b10536b… 6370fb87 (18.10.) · a8c81dad… 5409e926 (20.10.) · 8e2f79fc… fcd47013 (04.11.)
-- Idempotent: trifft nur FTMO + NAS100 + ppl 0,85; ein zweiter Lauf ändert nichts.

begin;

update public.firm_specs
   set ppl = 1.0
 where name = 'FTMO' and symbol = 'NAS100' and ppl = 0.85;

commit;

-- Kontrolle (nach dem Einspielen): erwartet FTMO nur noch ppl 1.0 (20 Zeilen), keine 0,85
-- select name, symbol, ppl, count(*) from public.firm_specs where name = 'FTMO' group by 1, 2, 3 order by 3;

-- Rückbau (nur falls nötig — genau die 7 Zeilen von oben zurück auf 0,85):
-- update public.firm_specs set ppl = 0.85
--  where name = 'FTMO' and ppl = 1.0 and id in ('23c6cfb2-5fda-4979-a755-3f4c8a363961', '506d5274-2e7b-4e4e-8f86-2a2bafcf3548',
--    '632d0e64-1043-42a9-b610-ab441f9e4591', 'f385ecf1-7626-440f-86db-29acf1ba2702', '8b10536b-acf5-4645-93d2-6bb9fb484417',
--    'a8c81dad-4447-47c6-bc00-071df9883c24', '8e2f79fc-6d41-40a8-86d2-15a6f449238f');
