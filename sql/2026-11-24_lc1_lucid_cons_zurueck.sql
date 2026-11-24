-- LC1 (Master 24.11.2026): Lucid Flex 150k Evals — Consistency 40 % (Lucid-Dashboard, Finn-Foto 24.11.: Chris …0018 „42,88 %, Profit Target 9.738,
-- $656 left, ACTIVE“). Die Ziel-Wache hatte Lucid mit 50 % gerechnet (ZW_CONS_FIRMEN, Fix LC1) und das Konto am 23.11. als „Ziel erreicht“ markiert.
-- Diese Zeile nimmt die Markierung zurück → der Planer plant den Rest-Trade bis 159.737 (größter Tag 3.894,50 ÷ 0,4 = 9.736,25; Balance 159.082,
-- Rest ~655 $ + Puffer). Gesucht über ALLE IDs: markierte Lucid-Evals mit Balance < Größe + größter Tag ÷ p (150k 40 %, 50k 50 %) → 2 Treffer (Ina …0008 bleibt, s. unten),
-- beide Gruppe Hermann Technologies. Idempotent (nur, wenn noch markiert und noch Challenge). NUR DATEN, nicht eingespielt — Master nach Finns Wort.
-- ERST NACH dem Push von LC1 einspielen: mit dem alten Code (Lucid 50 %) markiert die Ziel-Wache das Konto im nächsten Lauf (≈ 5 min) wieder.
update accounts
   set ziel_erreicht_at = null, ziel_erreicht_bal = null
 where id = '15e8f4d6-bb81-4fa5-9cc3-fa8c592d542f'          -- Chris · Lucid 150k LFE15098201480018 (42,9 %)
   and account_type = 'challenge'
   and ziel_erreicht_at is not null
returning id, name, tv_balance, ziel_erreicht_at;

-- Zweiter Treffer Ina · Lucid 150k …0008 (40,4 %) bleibt markiert: Finn bestätigt 24.11., das Konto ist wirklich bestanden (Nachfolger aktiv).
