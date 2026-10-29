-- Topstep-Trades von heute nachholen (Finn 29.10.2026 ~17:00 Dubai: „die Topstep-Orders für heute sollen noch durchlaufen … in der nächsten
-- 1 Stunde sollen alle starten"). Puls-Topstep war 14:05–16:59 AUS (Vorfall Simon). 7 Pläne hat der Nachholen-Weg selbst auf 17:02–17:20
-- gelegt (Ina ×4, Marco ×3). Übrig 4 ohne neuen Start: Simon …88012649, Marc …16884818 / …79770038, Mike WD …57131691 (16:59 als
-- „verpasst" abgewiesen, keine Order). Neu gestreut in die nächste Stunde (Jitter-Regel), Claim/Abweisung zurückgesetzt. Richtungsschutz
-- bleibt: Marcs Buy wartet, solange sein Sell auf Topstep läuft.
update public.trade_plans
   set start_um = now() + make_interval(mins => v.min) + make_interval(secs => floor(random() * 90)),
       start_um_gestartet_at = null,
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) - 'start_fehler' - 'start_sperre',
       updated_at = now()
  from (values ('7b782bdf-bade-4ec8-9d40-8205555994eb'::uuid, 22),
               ('c5162814-20fe-4145-b45e-fcbd1971e62e'::uuid, 26),
               ('c34d0b5e-8930-4d28-9944-654ca894a8ce'::uuid, 31),
               ('e9cf8722-5582-4399-a8d6-d8621bcacaca'::uuid, 48)) v(id, min)
 where trade_plans.id = v.id and trade_plans.status = 'planned' and trade_plans.started_at is null and trade_plans.route = 'tsv2';
