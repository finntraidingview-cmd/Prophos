-- RC4 zwei Recovery-WD (Ausgleich) freigeben und neu einplanen (Finn 12.11.2026 ~21:00 Dubai zum Funded Planer „Braucht dich“: „Warum haben die nicht
-- gestartet? Kannst du die neu planen?“). Ursache (S5, Bericht 2026-11-12_RC4_recovery_nicht_gestartet.md): Ausgleichs-Trades (wd_ausgleich) brauchen seit
-- 03.11. eine Einzel-Bestätigung (hedge_freigabe_at). Die ⚪-Meldung kam bei keinem Gerät an, und „Zu bestätigen“ war wegen 403 leer → niemand hat
-- bestätigt, der Tab startete bewusst nicht. Finns „neu planen“ = Bestätigung beider Pläne.
-- Weg wie Memory „Nachplanen per Supabase“: Freigabe + start_um gestreut in die Zukunft (Jitter), Guard: nur geplant, nie geclaimt, nie gestartet.
-- Mike Tradeify …3058 (1 × NQ, TP 2.904) in 3–6 min, Finn + Pascal Lucid …0001 (7 × MNQ, TP 1.650) in 9–14 min.

update public.trade_plans
   set hedge_freigabe_at = now(), hedge_freigabe_von = 'master-sql RC4 (Finn: neu planen)',
       start_um = now() + make_interval(secs => 180 + floor(random() * 180)::int), updated_at = now()
 where id = 'c892a4d0-8778-4029-9637-b50163684f76'
   and status = 'planned' and start_um_gestartet_at is null and started_at is null and hedge_freigabe_at is null;

update public.trade_plans
   set hedge_freigabe_at = now(), hedge_freigabe_von = 'master-sql RC4 (Finn: neu planen)',
       start_um = now() + make_interval(secs => 540 + floor(random() * 300)::int), updated_at = now()
 where id = '814ef28f-99dd-494b-998e-53260c95c33f'
   and status = 'planned' and start_um_gestartet_at is null and started_at is null and hedge_freigabe_at is null;
