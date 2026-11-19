-- Pascal Tradeify 150k TDFYSL150941101560 (accounts 1730fcd8, Challenge, Ziel erreicht 05.11.2026) stand im Radar unter Bestanden → Review mit der
-- Notiz „ACC IST WEG WEGEN LIVE, FINN PLS LÖSCHEN ODER SO“. Finn 19.11.2026: „bitte den Trade hier weg machen“.
-- Grund: Tradeify schließt beim Wechsel auf Elite Live alle Sim- und Evaluation-Konten; das Konto gibt es nicht mehr.
-- Weg: Archiv des Besitzers wie archiveAccount() im Frontend, reason 'passed' (bestanden, danach durch den Live-Wechsel geschlossen).
-- Keine offenen Pläne am Konto. Kein Echo-Löschauftrag (Tradovate, kein MT5-Link). Nur, wenn noch nicht archiviert.
insert into public.user_settings (user_id, key, value, updated_at)
select '728b4d23-ff5c-45f9-b6de-9b75c1f9a78a', 'archive', '{}'::jsonb, now()
where not exists (select 1 from public.user_settings where user_id = '728b4d23-ff5c-45f9-b6de-9b75c1f9a78a' and key = 'archive');

update public.user_settings s
set value = coalesce(s.value, '{}'::jsonb) || jsonb_build_object('1730fcd8-7c56-432a-b6c6-710cdc917d26',
              jsonb_build_object('archived', true, 'reason', 'passed', 'at', now())),
    updated_at = now()
where s.user_id = '728b4d23-ff5c-45f9-b6de-9b75c1f9a78a' and s.key = 'archive'
  and not coalesce((s.value->'1730fcd8-7c56-432a-b6c6-710cdc917d26'->>'archived')::boolean, false);
