-- MV1 MAIL-VORSCHLÄGE VERWERFEN (11.11.2026, Finn 19:24 über den Master zu „14389…· FundedNext · zu bestätigen · aus Mail“ unter Accounts bei Chris:
-- „Ja, einfach verwerfen. Das habe ich nie genutzt, wegmachen.“). Das Frontend zeigt unter Accounts seit MV1 keine Mail-Vorschläge mehr; diese Datei
-- verwirft die heute offenen GENAU wie der Knopf „Verwerfen“ (POST /konto-verwerfen, app.py konto_verwerfen): user_settings key 'konto_verworfen' =
-- {EXT normiert: Zeitpunkt} der Besitzer-ID. Nichts wird gelöscht — damit verschwinden sie auch in Admin → Alle Accounts; der Reiter „Konten aus Mail & TV“
-- zeigt Mails weiter (er zeigt ohnehin alles).
-- Stand 11.11.2026 ~19:40 Dubai (Slave 2, gleiche Erkennung wie mailOffen: KONTO_MAIL_MUSTER, Stichtag 28.10., 14 Tage, nicht schon in accounts, nicht
-- verworfen): 4 offene, keiner bei einer gesperrten Firma (vorrat_matrix):
--   Chris  FundedNext   14389609                          („ready for activation“, 10.11.)
--   Mike   FundedNext   14390020                          („ready for activation“, 10.11.)
--   Moritz FundingPips  21255811                          („[21255811] [2 Step Flex] Master account details“, 10.11.)
--   Marc   Topstep      150KTCSKUV2DLL69733920719220      („Your Trading Combine has been reset“)
-- EXT normiert wie admin_konto_ext_norm / kontoKey: Großbuchstaben, nur A–Z und 0–9.
-- IDEMPOTENT: vorhandene Einträge behalten ihren Zeitpunkt (bestehender Wert gewinnt beim Zusammenführen); sind schon alle Schlüssel da, wird nichts
-- geschrieben. Enge Auswahl: nur diese vier (user_id, EXT)-Paare, nur der Schlüssel 'konto_verworfen'.
-- Einspielen nur auf des Masters bzw. Finns Wort (execute_sql, DML).

with neu (user_id, ext) as (values
  ('7b1bc9a3-94d3-4603-a232-c10fc2df3262'::uuid, '14389609'),                       -- Chris
  ('32b854d1-866f-4e7e-ba0b-9bf63df2d993'::uuid, '14390020'),                       -- Mike
  ('aff98e60-e9a0-4821-9d1d-31634571a2f4'::uuid, '21255811'),                       -- Moritz
  ('6c206a34-c4a7-4352-8097-bb17366bcea1'::uuid, '150KTCSKUV2DLL69733920719220')    -- Marc
), je_id as (
  select user_id,
         jsonb_object_agg(ext, to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')) as wert
  from neu group by user_id
)
insert into public.user_settings (user_id, key, value, updated_at)
select user_id, 'konto_verworfen', wert, now() from je_id
on conflict (user_id, key) do update
  set value = excluded.value || public.user_settings.value,   -- bestehender Wert rechts = gewinnt (alte Zeitpunkte bleiben)
      updated_at = now()
  where not (public.user_settings.value ?& array(select jsonb_object_keys(excluded.value)));   -- alles schon verworfen → nichts schreiben

-- Kontrolle (alle vier → true):
-- select n.user_id, n.ext, coalesce((s.value ? n.ext), false) as verworfen
--   from (values ('7b1bc9a3-94d3-4603-a232-c10fc2df3262'::uuid, '14389609'), ('32b854d1-866f-4e7e-ba0b-9bf63df2d993'::uuid, '14390020'),
--               ('aff98e60-e9a0-4821-9d1d-31634571a2f4'::uuid, '21255811'), ('6c206a34-c4a7-4352-8097-bb17366bcea1'::uuid, '150KTCSKUV2DLL69733920719220')) n (user_id, ext)
--   left join public.user_settings s on s.user_id = n.user_id and s.key = 'konto_verworfen';
-- Rücknahme (nur diese vier Schlüssel wieder raus):
-- update public.user_settings set value = value - '14389609' where user_id = '7b1bc9a3-94d3-4603-a232-c10fc2df3262' and key = 'konto_verworfen';  -- usw. je Paar
