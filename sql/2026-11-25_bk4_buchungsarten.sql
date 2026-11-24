-- ============================================================================
-- Prophos: BK4 Buchungsarten Bankkonto (25.11.2026) — NICHT eingespielt, erst nach Finns Entscheid zum Block „ZUORDNUNG" unten.
--
-- Finn 25.11.2026: bei Bankkonto-Buchungen nur noch „Zahlung von HT", „Zahlung an HT", „Payout", „Account-Kauf".
-- Vorzeichen fest: Zahlung von HT +, Payout +, Zahlung an HT −, Account-Kauf − (bank_app.py setzt es bei jeder Eingabe, hier als
-- check, damit die Tabelle es nie anders hält).
--
-- Reihenfolge beim Einspielen: diese Datei, dann den Code (bank_app.py + prophos.html) pushen. Der alte Code schickt noch
-- „Einzahlung HT" — bank_app.py nimmt den alten Namen als „Zahlung von HT" an.
--
-- Bestand 25.11.2026 (478 Zeilen): Account-Kauf 374 (alle −) · Einzahlung HT 78 (alle +) · Payout 16 (alle +) · Gebühr 5 · Sonstiges 5
-- · Vergütung 0. Ohne Namen/IBAN (Repo öffentlich) — die Zeilen sind über ihre id gemeint.
-- ============================================================================
begin;

alter table public.bank_buchungen drop constraint if exists bank_buchungen_art_check;
alter table public.bank_buchungen drop constraint if exists bank_buchungen_vorzeichen_check;

-- 1) fest: Einzahlung HT → Zahlung von HT (Account-Kauf und Payout bleiben)
update public.bank_buchungen set art = 'Zahlung von HT' where art = 'Einzahlung HT';

-- 2) ZUORDNUNG (Finn entscheidet; Vorschlag nach Vorzeichen und Text — nur die rechte Spalte ändern)
--    Gebühr (5, alle −): Revolut-/Wechselgebühren auf Prop-Käufe → Vorschlag Account-Kauf
--    Sonstiges (5): Test-Überweisung −1 · „abhebung an uns (profits)" −2.896 · zwei Zeilen ohne Text +1.109 / +650 · „Abrechnung … OKX Deposit Tag" −86
update public.bank_buchungen b set art = z.art
  from (values
    ('27ed916f-766c-4c7d-8edf-b9fe199ed64e'::uuid, 'Account-Kauf'),     -- Gebühr     −8     26.09.  Kartenliefergebühr
    ('59bde620-cca0-483d-b56c-72cde8c8686f'::uuid, 'Account-Kauf'),     -- Gebühr     −160   03.11.  Gebühren + Rundung 25.09.–03.11.
    ('956d82bc-fc2d-424c-aa1d-31bd9661e584'::uuid, 'Account-Kauf'),     -- Gebühr     −77    09.11.  Wechselgebühren Prop-Zahlungen
    ('22f2ef5d-a279-4e35-af36-8d3f8156d9e9'::uuid, 'Account-Kauf'),     -- Gebühr     −65    10.11.  Korrektur Gebühren/Wechselkurs
    ('9af81f47-af0d-42ba-afda-9f03c67642fc'::uuid, 'Account-Kauf'),     -- Gebühr     −87    11.11.  Wechselgebühren Prop-Zahlungen
    ('f7149c13-ead4-4b57-868c-24113a7f331a'::uuid, 'Zahlung an HT'),    -- Sonstiges  −1     17.09.  1-€-Test
    ('e8517dd3-794d-4810-82c1-2778b8a5caf5'::uuid, 'Zahlung an HT'),    -- Sonstiges  −2896  01.10.  Abhebung an uns (profits)
    ('f7c32ced-71d6-4680-b728-05dcf23b7405'::uuid, 'Zahlung von HT'),   -- Sonstiges  +1109  05.10.  ohne Text
    ('3face59f-6c3a-4550-b960-2e1c6ab52d46'::uuid, 'Zahlung von HT'),   -- Sonstiges  +650   18.10.  ohne Text
    ('2dcf4014-e742-4623-8e35-916816c67baf'::uuid, 'Zahlung an HT')     -- Sonstiges  −86    12.11.  Abrechnung OKX-Deposit-Tag
  ) as z(id, art)
 where b.id = z.id and b.art in ('Gebühr', 'Sonstiges', 'Vergütung');

-- Riegel: nichts darf in einer alten Art übrig bleiben (sonst bricht die Transaktion hier ab statt still zu raten)
do $$ begin
  if exists (select 1 from public.bank_buchungen where art not in ('Zahlung von HT', 'Zahlung an HT', 'Payout', 'Account-Kauf')) then
    raise exception 'BK4: es gibt noch Buchungen in alten Arten — Block ZUORDNUNG ergänzen';
  end if;
  if exists (select 1 from public.bank_buchungen
              where (art in ('Zahlung von HT', 'Payout') and betrag < 0) or (art in ('Zahlung an HT', 'Account-Kauf') and betrag > 0)) then
    raise exception 'BK4: Vorzeichen passt nicht zur Art — Zuordnung prüfen';
  end if;
end $$;

alter table public.bank_buchungen alter column art set default 'Account-Kauf';
alter table public.bank_buchungen add constraint bank_buchungen_art_check
  check (art in ('Zahlung von HT', 'Zahlung an HT', 'Payout', 'Account-Kauf'));
alter table public.bank_buchungen add constraint bank_buchungen_vorzeichen_check
  check ((art in ('Zahlung von HT', 'Payout') and betrag > 0) or (art in ('Zahlung an HT', 'Account-Kauf') and betrag < 0));

commit;

-- Kontrolle: select art, count(*), sum(betrag) from public.bank_buchungen group by 1 order by 1;
