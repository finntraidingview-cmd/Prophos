-- Blue Guardian: Duplikum-Symbol wie bei den anderen CFD-Firmen setzen (Feld „Duplikum-Symbol(e)
-- (Master)" in den Einstellungen). Broker-Symbol laut MT5 = NAS100 (Finn 04.10.2026).
update firm_specs set dup_symbol = 'NAS100' where name = 'Blue Guardian' and dup_symbol is null;
