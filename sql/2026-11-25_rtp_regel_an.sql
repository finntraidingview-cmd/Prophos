-- Finn 25.11.2026 („wo kann man das Add-on anmachen“): RTP-Regel global an, damit der Schalter am Topstep-Tacho je ID sofort wirkt.
-- Ohne addon_firma-Zeile einer ID ändert sich nichts (heute keine). Rückweg: aktiv false. Idempotent.
update public.rtp_regeln set aktiv = true, updated_at = now() where id = 1 and not aktiv;
