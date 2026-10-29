-- Puls für Topstep wieder SCHARF (Finn 29.10.2026 ~20:15 Dubai: „Der Bug, der heute Morgen bei Simon war, ist jetzt ja behoben … Schalte
-- Topstep wieder live. Sobald irgendein Bug passiert … melde dich bei mir"). Rücknahme von sql/2026-10-29_puls_topstep_aus.sql.
-- Seit .1862 live: Nova-Brackets bis zu 3 Runden + Rücklesung + brackets_fehlen 🔴, Nova-Ende nur mit Beweis (nie Schätz-Ende ohne Brackets).
-- Topstep-Challenge-Größen 2 NQ (75 %) / 3 NQ (25 %). Rücknahme: puls_topstep = 'aus'.
update public.wd_farmer_regeln set puls_topstep = 'scharf' where id = 1;
-- Nachtrag 17:00 Dubai: Beim ersten Scharfschalten (16:59) holten die PC-Tabs sofort 8 seit 14:10–15:07 liegende tsv2-Pläne (Ina ×4,
-- Marco ×3, Mike ×1) per Claim — alle mit „Startzeit um 113–169 min verpasst" abgewiesen, keine Order. Master hatte vorsichtshalber kurz
-- wieder auf 'aus' gestellt, nach Prüfung (started_at überall leer) erneut 'scharf'.
