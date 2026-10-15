-- 15.10.2026 18:45 Dubai (Finn: „bitte trades bis 20:00 Dubai zeit planen"): das eine Fenster (sql/2026-10-15_fenster_ein_tag.sql)
-- reicht jetzt bis 18:00 dt = 20:00 Dubai (Sommerzeit; ab 25.10. wäre das 21:00 Dubai → dann 17:00 dt setzen), letzter Start ebenfalls.
-- Folge: Nachplan-Fenster bis 17:45 dt = 19:45 Dubai → Mike (Pause-Ende 17:41) und Marc (seit 18:05 im Planer) werden heute noch geplant.
update auto_plan_regeln
   set zeiten = coalesce(zeiten, '{}'::jsonb)
                || jsonb_build_object('fenster', jsonb_build_array(jsonb_build_array('00:00', '18:00', 100)),
                                      'start_bis', '18:00')
 where id = 1;
