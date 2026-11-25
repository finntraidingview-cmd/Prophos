-- KP6c als Daten statt Code (Prüfer S2, Master 25.11.2026): Die ID Emin stand seit 06.10. in vorrat_einstellung.ohne_ids (damals: Emin nicht in
-- der HT-Vorrat-Sicht). Seit KP6 trennt der Lauf HT und Emin selbst — die HT-Standard-Sicht blendet Emin über _admin_standard_aus weiter aus.
-- Emin raus aus ohne_ids, damit seine Zeilen im Emin-Abschnitt (KP6b) und in seiner Verwalter-Sicht erscheinen. Die zwei HT-IDs bleiben drin.
-- Rückweg: array_append(ohne_ids, '6cceb3f3-dc78-48ee-8668-26081da3e70f'). Idempotent.
update public.vorrat_einstellung
   set ohne_ids = array_remove(ohne_ids, '6cceb3f3-dc78-48ee-8668-26081da3e70f'::uuid), updated_at = now()
 where id = 1 and '6cceb3f3-dc78-48ee-8668-26081da3e70f'::uuid = any(ohne_ids);
