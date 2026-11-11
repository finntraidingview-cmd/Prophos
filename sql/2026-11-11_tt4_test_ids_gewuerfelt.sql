-- TT4 (11.11.2026, Finn ~21:15 Dubai): „Ich will ja gerade testen, dass für so und so viel Prozent eben so viele Trades gemacht werden.“
-- Bei den Test-IDs (Marco, Simon) stand der Würfel fest auf 3 Trades je Echo-Konto (test_n 3). Jetzt test_n null = gewürfelt wie später für alle
-- (65/21/10/4 je Konto × Tag). Nur dieser eine Schlüssel, idempotent. Rücknahme: test_n auf 1–4 setzen (Karte „Trades pro Tag“ → Anzahl bei Test-IDs).
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{tagesteilung,test_n}', 'null'::jsonb), updated_at = now()
 where id = 1 and regeln->'tagesteilung'->'test_n' is distinct from 'null'::jsonb;
