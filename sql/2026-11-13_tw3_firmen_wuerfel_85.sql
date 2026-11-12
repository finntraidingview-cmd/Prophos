-- Firmen-Würfel (TW3) für Hermann Technologies von 75 % auf 85 % (Finn 13.11.2026 ~03:30 Dubai: „Auf 85 %“). Anlass: erster Lauf 13.11. — ein Wurf nahm bei
-- Simon Lucid 10 Konten auf einmal raus (5 davon am Vortag gekauft); Challenge-Planer 40 geplant / 24 Firmen-Pause / 18 Konto-Pause. Mit 85 % Firma × 75 % Konto
-- handeln im Schnitt ~64 % statt ~56 % der Konten je Tag. Konto-Würfel (TW1, 75 %) unverändert. Zurück: pct = 75.
update public.planer_handel_wuerfel set pct = 85
 where planer = 'firma_je_id' and gruppe = '';
