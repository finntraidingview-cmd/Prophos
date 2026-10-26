-- 2026-10-26 (~16:30 Dubai): drei MT5-Konten mit gesperrtem Handel aus dem Auto-Planer nehmen, ihre hängenden Pläne entfernen.
-- Anlass: Finn „Fehlstarts von heute — alles wieder fixen". 13 Fehlstarts „F9-Dialog nicht gefunden … trade_allowed = False":
--   Jacob FundingPips …6925 (Balance 89.792,93) · Jacob FundingPips …6924 (93.473,40) · Marco FTMO …0116 (90.071,52).
-- MT5 meldet account_info.trade_allowed = False — die Firma hat den Handel gesperrt (geblowt). Die Pläne standen seit dem Morgen
-- auf 'planned' (Deckel voll), der Auto-Planer würde morgen wieder einen anlegen.
-- Nicht archiviert: Archivieren als geblowt stößt Duplikum-/Echo-Löschaufträge an — das entscheidet Finn nach dem Blick ins
-- Firmen-Dashboard. auto_planer = false ist umkehrbar. Pläne weg wie der 🗑-Knopf (nur solange 'planned'). Idempotent.

update public.accounts
   set auto_planer = false, updated_at = now()
 where id in (select master_account_id from public.trade_plans
               where id in ('007f5017-eab4-4011-be3a-6398041ac691',      -- Jacob FundingPips …6925
                            '76a62d92-96df-4f5d-8165-b085286d5eb0',      -- Jacob FundingPips …6924
                            'fd5e137f-c3aa-44cc-a5b8-a56197b98f25'));    -- Marco FTMO …0116

delete from public.trade_plans
 where id in ('007f5017-eab4-4011-be3a-6398041ac691',
              '76a62d92-96df-4f5d-8165-b085286d5eb0',
              'fd5e137f-c3aa-44cc-a5b8-a56197b98f25')
   and status = 'planned';

-- ZURÜCK (falls ein Konto doch wieder handeln darf): accounts.auto_planer = true für das Konto setzen, der Auto-Planer plant neu.
