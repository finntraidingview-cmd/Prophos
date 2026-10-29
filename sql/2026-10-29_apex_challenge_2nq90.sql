-- Apex im Challenge-Planer: 90 % 2 NQ, 10 % 3 NQ (Finn 29.10.2026 ~14:50 Dubai: „Mit einem NQ werden wir keine 11k im Profit machen.
-- Mach einfach immer zu 90 % 2 NQs und zu 10 % 3 NQs.") Anlass: Auswertung S7 — Apex 3 NQ ohne SL, faktischer Stop = Tagesverlust ÷ 3 NQ
-- ≈ 26 Pkt (kleiner als eine normale 15-min-Kerze, Ø 49 Pkt), Trefferquote 12 % statt nötiger 19 %. Mit 2 NQ liegt der Stop bei ~38–50 Pkt.
-- Vorher menge [3,3] (oben und je_groesse 100000/150000). Der Planer würfelt gleichverteilt aus [von, bis] und rundet (_ap_spanne +
-- _ap_runden): [2, 2.5556] ergibt 3 nur bei 2 + 0,5556·u > 2,5 → u > 0,9 → 10 % 3 NQ. Rücknahme: alle drei wieder [3,3].
update public.auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(
               case when f->'namen' ? 'apex' then
                 jsonb_set(jsonb_set(jsonb_set(f,
                   '{phasen,challenge,menge}', '[2,2.5556]'::jsonb),
                   '{je_groesse,100000,phasen,challenge,menge}', '[2,2.5556]'::jsonb),
                   '{je_groesse,150000,phasen,challenge,menge}', '[2,2.5556]'::jsonb)
               else f end order by i)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality t(f, i))),
    updated_at = now()
where r.id = 1;
