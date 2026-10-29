-- Puls für Topstep wieder AUS (Master 29.10.2026 18:07 Dubai). Vorfall: Marc (pc-7ftp5l) Plan e9cf8722, Topstep 150k …79770038, BUY 2 NQ
-- 17:51 — mt5_baseline.tv.warnung „Brackets in TopstepX prüfen: Risk 1208 $ nicht gesetzt (Risk-Zelle verdeckt, gesperrt …)", Plan open OHNE
-- brackets_fehlen → der Bracket-Fix vom Vormittag (Retry + 🔴) hat nicht gegriffen. Finn hatte ab ~14:05 festgelegt: kein weiterer Topstep-Trade,
-- bevor der Fehler nicht mehr auftritt. Laufende Trades bleiben unberührt. Rücknahme: puls_topstep = 'scharf' (erst nach Fix + Finns Wort).
update public.wd_farmer_regeln set puls_topstep = 'aus' where id = 1;
