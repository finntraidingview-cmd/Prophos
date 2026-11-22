-- Echo-Hedge-Konto für die ID Carsten nachtragen (CH1, Konten-Check KA1-C 23.11.2026).
--
-- Warum: Carstens 6 CFD-Challenges (FundedNext ×3, FTMO, Tradeify CFD ×2, angelegt 19./20.11.) wurden nie geplant.
-- Der Auto-Planer meldete jeden Tag „kein Echo-Hedge stellbar — kein Echo-Hedge-Konto (Fusion) bei dieser ID“.
-- Das Fusion-Konto „488579 → Live“ gibt es in Carstens ID seit 17.11.,
-- aber die Einstellung user_settings.echo_hedge_account fehlt. Alle anderen aktiven HT-IDs haben sie.
-- Das Format ist dasselbe wie dort: value = {"accountId": <accounts.id des eigenen Fusion-Kontos>, "hedgeLogin": <dessen external_id>}.
-- accountId muss ein EIGENES Konto der ID sein (Riegel gp_hedge_settings_eigen, 02.11.2026).
--
-- Idempotent: Der Eintrag wird nur angelegt, wenn das Konto noch existiert, der ID gehört und nicht deaktiviert ist.
-- Ein vorhandener Eintrag wird nicht überschrieben (Unique-Schlüssel user_id + key).
-- Der Login steht nicht im Klartext hier, er kommt aus accounts.external_id.
--
-- Wirkt nur auf die Planer (Auto-Planer, Funded-CFD-Planer, Echo-Vorschau). PCs, Copier-Configs und mt5_live
-- bleiben unberührt. Damit Echo-Trades wirklich laufen, muss auf Carstens PC zusätzlich der Copier mit
-- Hedge-Terminal (hedge_expected_login) und magic_base laufen, siehe Magic-Base-Sheet vom 23.11.

insert into public.user_settings (user_id, key, value)
select a.user_id,
       'echo_hedge_account',
       jsonb_build_object('accountId', a.id::text, 'hedgeLogin', a.external_id)
from public.accounts a
where a.id = '3f7890bf-192f-4e04-b3d5-ef077440fd40'            -- Fusion Markets „… → Live“ der ID Carsten
  and a.user_id = '7fc987c0-b836-4555-ab03-254ceb150d51'       -- ID Carsten
  and a.firm ilike 'Fusion%'
  and a.deaktiviert_at is null
  and coalesce(a.external_id, '') <> ''
on conflict (user_id, key) do nothing;

-- Kontrolle (soll genau 1 Zeile liefern, hedgeLogin = external_id des Fusion-Kontos):
-- select value, updated_at from public.user_settings
--  where user_id = '7fc987c0-b836-4555-ab03-254ceb150d51' and key = 'echo_hedge_account';
