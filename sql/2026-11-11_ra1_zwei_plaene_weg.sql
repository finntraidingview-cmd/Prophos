-- RA1 (Finn 11.11.2026 ~02:10 Dubai: „Ja“ zum Löschen). Zwei Echo-Pläne vom 10.11. (Funded CFD The5%ers 100k …2352 Moritz, …5860 Marc)
-- hingen im Radar „Erledigt → Abhaken“ mit „unklar: Plan von 2026-11-10 nie fertig“. Befund berichte/2026-11-11_RA1_radar_abhaken.md:
-- Server lehnte die Order ab („Only position closing is allowed“), Position nie am Konto, kein Hedge, started_at null, kein P&L.
-- Der Tages-Reset hat sie nach review geschoben; sie sperrten den Funded-Planer für beide Konten. Löschen wie NG1 es täte.
-- Enge Bedingung: nur diese zwei IDs, nur review, nie gestartet, ohne P&L, ohne Hedge. Idempotent (zweiter Lauf löscht nichts).
delete from trade_plans
 where id in ('4f4e4eca-1569-4382-846d-ea8bb7f41ccb', '52e184db-f114-4862-a37c-6fb4098fc383')
   and status = 'review'
   and started_at is null
   and master_pl is null
   and not (coalesce(mt5_baseline, '{}'::jsonb) ? 'hedge');
