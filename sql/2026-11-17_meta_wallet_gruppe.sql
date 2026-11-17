-- MW1 Meta Wallet: Unternehmen je Wallet ohne ID (17.11.2026, Finn ~05:15 Dubai mit Screenshot: Admin → „Emin" → Meta Wallet zeigte
-- „Marco Ziegler", „Marc Fischer", „Simon_OKX", „Ina_OKX", „Pascal_OKX", „Mike_OKX" — „Hermann-Technologies-IDs sind bei Emin drin.
-- War schon mal so.").
--
-- BEFUND: 13 Zeilen in id_wallets haben person_uid = null (Name frei eingetippt, keine ID dahinter). Der Gruppenfilter im Frontend
-- schließt nur die person_uid der fremden Gruppe aus (excluded_uids) — eine leere person_uid steht nie in dieser Liste, deshalb
-- erschienen diese Wallets in JEDER Gruppe (bei Emin: 16 eigene + 13 = „29 Wallets · 13 Personen"). Der Kapital-Reiter
-- (kapital_app.py, id_wallets.person_uid in Mitgliedern der Gruppe) zählt sie dagegen in KEINER Gruppe mit.
--
-- LÖSUNG: dauerhafte Zuordnung über eine Spalte, nicht über den Namen geraten.
--   Gruppe einer Wallet = Gruppe ihrer person_uid (id_gruppe_mitglied) — sonst gruppe_id — sonst „ohne Zuordnung"
--   (zählt nirgends mit, steht beim HT-Admin als eigene Box mit Auswahl „Unternehmen" + „Zuweisen").
-- Neue Wallets ohne ID bekommen beim Eintragen die Gruppe, die oben im Admin gewählt ist (prophos.html walAdd).
-- Ohne diese Datei läuft die Oberfläche weiter: alle 13 stehen dann in „Ohne Zuordnung", Zuweisen meldet „SQL fehlt".

alter table public.id_wallets add column if not exists gruppe_id uuid references public.id_gruppen(id) on delete set null;

-- „Zuweisen" schreibt per UPDATE (bisher gab es auf id_wallets nur SELECT/INSERT/DELETE-Policies → jedes UPDATE traf 0 Zeilen).
-- Gleiche Weite wie die bestehenden Policies „wallets insert"/„wallets delete" (authenticated, true); die RESTRICTIVE-Policy
-- nur_eigene_wallets gilt weiter, ein eingeschränkter Login (Emin) kann also nur Zeilen seiner sichtbaren IDs ändern.
do $$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'id_wallets' and policyname = 'wallets update') then
    create policy "wallets update" on public.id_wallets for update to authenticated using (true) with check (true);
  end if;
end $$;
-- Enger als die Policy (Gegenprüfung 17.11.2026): angemeldete Nutzer dürfen per UPDATE NUR gruppe_id ändern — Adresse, person_uid,
-- Name bleiben unveränderbar (Frontend schreibt id_wallets sonst nur per insert/delete; Backend nutzt service_role, eigene Rechte).
revoke update on public.id_wallets from authenticated, anon;
grant update (gruppe_id) on public.id_wallets to authenticated;

-- VORSCHLAG ZUR ZUORDNUNG DER BESTEHENDEN ZEILEN (nicht automatisch — erst nach Finns OK einspielen oder in der Box „Ohne Zuordnung"
-- von Hand zuweisen). Alle 13 sind laut Finn HT-Leute; Hermann Technologies = 7ad374a1-c470-4b13-bf6b-24722f82739a.
-- Stand 17.11.2026, letzter Snapshot-Wert in USDT:
--   Marco Ziegler  arbitrum  4faae557-8f50-4de3-8dac-2ff728602b79   2.046,22
--   Marc Fischer   arbitrum  fcafbfb9-2c10-40b4-8692-ca641787b799     895,27
--   Marc Fischer   ethereum  70c7c1ed-70c1-4bd8-936a-324d14985831     187,99
--   Chris_OKX      arbitrum  402823f4-d38e-4ade-acdd-61d1c5ba38dd       0,00
--   Chris_OKX      ethereum  28124f28-c953-4206-9b9c-7c752b474da6       0,00
--   Ina_OKX        arbitrum  2810b657-1eb9-4b72-9dde-7c3ee62632f9       0,00
--   Ina_OKX        ethereum  1109f042-db5e-4c90-9418-e7931809adde       0,00
--   Mike_OKX       arbitrum  d6fb851d-47e9-4feb-8fca-31a9cc9d2f31       0,00
--   Mike_OKX       ethereum  09114e13-7cf7-44d0-afcf-10577dbd0654       0,00
--   Pascal_OKX     arbitrum  561aea16-c60e-423f-bfc3-8ce85d60651d       0,00
--   Pascal_OKX     ethereum  50c2ac5d-adc9-4557-95b1-cf0be0e4f961       0,00
--   Simon_OKX      arbitrum  2fefd106-d0d4-41d7-9acb-781014593e01       0,00
--   Simon_OKX      ethereum  1774772e-0579-4b0c-8e81-0eb626d41d4e       0,00
--
-- update public.id_wallets set gruppe_id = '7ad374a1-c470-4b13-bf6b-24722f82739a'
--  where person_uid is null and gruppe_id is null and id in (
--    '4faae557-8f50-4de3-8dac-2ff728602b79','fcafbfb9-2c10-40b4-8692-ca641787b799','70c7c1ed-70c1-4bd8-936a-324d14985831',
--    '402823f4-d38e-4ade-acdd-61d1c5ba38dd','28124f28-c953-4206-9b9c-7c752b474da6','2810b657-1eb9-4b72-9dde-7c3ee62632f9',
--    '1109f042-db5e-4c90-9418-e7931809adde','d6fb851d-47e9-4feb-8fca-31a9cc9d2f31','09114e13-7cf7-44d0-afcf-10577dbd0654',
--    '561aea16-c60e-423f-bfc3-8ce85d60651d','50c2ac5d-adc9-4557-95b1-cf0be0e4f961','2fefd106-d0d4-41d7-9acb-781014593e01',
--    '1774772e-0579-4b0c-8e81-0eb626d41d4e');
--
-- OFFEN (nicht Teil dieser Datei): kapital_app.py _daten_lesen liest Wallets nur über person_uid ∈ Mitglieder — Wallets mit
-- gruppe_id (ohne ID) fehlen dort weiter in der Gruppensumme. Ebenso sieht ein eingeschränkter Login (nur_eigene_wallets prüft
-- person_uid) Wallets mit nur gruppe_id nicht; betrifft heute niemanden, weil alle 13 zu HT gehören.
