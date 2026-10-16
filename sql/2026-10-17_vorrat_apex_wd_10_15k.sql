-- 17.10.2026 Finn am Muster-Portfolio-Tacho Apex („0/1 WD"): „Ziel bitte hier 10-15k in WD acc". Apex zählt ab jetzt wie
-- Tradeify/Topstep das Plus über der Startgröße der Winning-Days-Konten (Spanne 10.000–15.000 $) statt 1 Stück. Nachkauf-Einheit
-- 100k EOD (Finn: „in Zukunft werden nur noch 100k Accounts"). Die Art lässt sich auf der Seite nicht ändern (vorrat_ziel_pruefen),
-- darum per SQL.
update vorrat_ziele
   set art = 'plus_ueber_start', von = 10000, bis = 15000, groessen = null,
       kauf_einheit = '100k EOD', kauf_groesse = 100000, updated_at = now()
 where firma = 'Apex Trader';
-- Prüfen: select firma, art, typen, von, bis, groessen, kauf_einheit, kauf_groesse from vorrat_ziele where firma = 'Apex Trader';
