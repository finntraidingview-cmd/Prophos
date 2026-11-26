-- Hans (bd98f522): der Planer ließ am 26.11.2026 alle 7 CFD-Challenges aus („kein Echo-Hedge stellbar — kein Echo-Hedge-Konto (Fusion) bei dieser
-- ID“, Finn ~03:25 Dubai: „Was ist bei Hans los, warum Echo nicht?“). Alles andere stand: Fusion-Konto „430095 → Live“ (304f6786, angelegt 25.11.),
-- mt5_links 430095 → dieses Konto, 7 Copier auf dem PC von Hans (pc-czv8js) mit hedge_login 430095. Es fehlte nur die Wahl im Echo-Popup
-- (user_settings echo_hedge_account), aus der app.py das Hedge-Konto je ID liest (GP_HEDGE_KEY). Gleiche Form wie bei Jona. Idempotent.
insert into public.user_settings (user_id, key, value)
values ('bd98f522-fba6-4285-bf0c-3f1c2b76d362', 'echo_hedge_account',
        '{"accountId": "304f6786-ec9f-4b37-a8d7-d56e5b3e6cb6", "hedgeLogin": "430095"}'::jsonb)
on conflict (user_id, key) do nothing;
