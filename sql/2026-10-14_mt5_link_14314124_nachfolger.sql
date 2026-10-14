-- 14.10.2026: Ina, FundedNext 14314124 — „Kein Master-Terminal auf diesem PC"
-- Am 08.10. wurde das alte Konto „100k funded next 14314124" als bestanden
-- archiviert, Nachfolger ist „100k 14314124 → Phase 1" (gleicher MT5-Login).
-- Der Echo-Nachzügler hat das Terminal auf pc-xc5c52 neu eingerichtet
-- (Instanz 100k14314124Phase1, lebt), aber mt5_links zeigt für den Login
-- weiter auf das ARCHIVIERTE Konto → Start-Wächter findet für den neuen
-- Plan keine Route, zwei Mini-Trades (13.10. 16:50, 14.10. 12:40) starteten nie.
update mt5_links
   set account_id = 'fcfc93d1-4e56-4a73-b62a-8c7953603d99',   -- 100k 14314124 → Phase 1 (neu)
       updated_at = now()
 where mt5_login::text = '14314124'
   and account_id = '1e0903e6-36d1-4af0-b1d1-03474aa19e3e';   -- 100k funded next 14314124 (archiviert)
