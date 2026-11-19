# Blue Guardian – CFD „2 Step Nano“ vs. „2 Step Standard“ (100K)

BG1 (Finn 19.11.2026), Slave-Bericht. Teil A = Regeln (unten, ab „Stand der Recherche“). Teil B = Planer (direkt hier).

## Kurz für Prophos (Planer-Kernwerte)

| | Nano 100K | Standard 100K (heute im Planer) |
|---|---|---|
| Kauf | 167 $ ≈ **145 €** | 324 $ (Planer: 300 €) |
| Ziel P1 / P2 | 8 % / **5 %** | 8 % / 4 % |
| Daily Loss | **3 %** (3.000, 17:00 NY, höher aus Balance/Equity) | 4 % |
| Max DD | **10 % statisch** (Boden 90.000) | 8 % statisch (92.000) |
| Mindesttage | **keine** | 3 × ≥ 0,5 % je Phase |
| Funded | Consistency 50 % (sperrt nur Payout), Cap 2.000 $ / 14 Tage, 80 %, **kein** Guardian Shield | kein Cap, 85 %, Guardian Shield 2 % floating |
| Haltezeit / News funded | 2 min / ±5 min rot + FOMC | gleich |

**Kennung Nano am Konto: `accounts.max_drawdown`** (Nano 10.000 = 10 %, Standard 8.000 = 8 %) über den vorhandenen Varianten-Weg
`regel.flex` (ap_konto_flex/ap_regel_flex, gebaut für FundingPips Flex: Variante ab `ab_dd_pct` % Max DD). Begründung:
- kein neues Feld, kein Namens-Parser; alle 6 heutigen BG-Konten stehen auf 8.000 → bleiben Standard, bitgleich.
- Max DD muss am Konto ohnehin stimmen (Liq-Boden, Radar, Hedge); Nachfolger/Reset erben ihn.
- eigene Firma „Blue Guardian Nano“ verworfen: eigener Firmen-Schlüssel → Gegenrichtungs-Riegel und Firmen-Abstand trennen Nano von
  Standard (BG verbietet Hedging über Konten hinweg), dazu fehlen firm_specs/Preset (NAS100 10 $/Pkt) für den neuen Namen.
- Schwachstelle: wird ein Nano-Konto OHNE Max DD angelegt, setzt DD1 (konto_dd_ergaenzen) den Firmen-Kernwert 8.000 → Standard-Plan.
  Beim Anlegen Max DD **10.000** eintragen. Selbst dann schützt `daily_pct 3` nur Nano, nicht den Fehlfall — siehe SQL-Kopf.

**Echo-Hedge (Fusion) braucht Code:** der Kontowert-Satz (ap_kontowert_konto → eh_hedge) rechnet je Firma mit 300 € / 8 % — für Nano
0,0375 statt 0,0145 €/$ in Phase 1 (≈ 2,6× zu viel Hedge), Phase 2 0,075 statt 0,026 (≈ 2,9×). Fix: Kontowert nimmt die Variante, wenn
`flex.kauf_eur` gesetzt ist (nur BG Nano; FundingPips Flex hat keins → bitgleich).

**Finns Vorgaben 19.11.2026 (über den Master):** Challenge Nano = Lots/TP wie Standard, **SL 2.000–2.500 $** (Daily 3.000 nie treffen).
Bedingung „kein Max Loss pro Trade bei Nano“ — geprüft, erfüllt: [NANO] nennt nur Daily 3 % + DD 10 % und „Stop losses: not mandatory“, kein
Lot-/Risiko-Limit je Trade; [PROH] hat nur die 80-%-Margin-Regel; [AGB] „Prohibited Strategies“ verbietet „excessive risk … in a single
simulated-trade“ und „Boom or Bust“ OHNE Zahl (Ermessen von Blue Guardian, kein fester Wert). **Funded Nano 100k (BG2):** Payout-Ziel je
Zyklus **800–1.200 $** (Finn „750/800 bis 1.200“, Master nimmt 800–1.200).

**BG2 gebaut (19.11.2026):** Der Funded-CFD-Planer kennt jetzt die Variante je Konto (app.py `fcp_regel_konto`, Kennung Max DD ≥ 10 %), ebenso
Radar-Ziel/Boden (`zw_funded_cfd`), Konto-Seite (`kz_rechnen`) und Reiter. SQL `sql/2026-11-19_bg2_blue_guardian_nano_funded.sql` (ersetzt den
auskommentierten Teil 2 der BG1-SQL): flex im blueguardian-Eintrag von funded_cfd_plan_regeln — Ziel 800–1.200, Consistency 50 % (vorhandener
Weg fcp_cons_finn wie The5ers, je Zyklus), SL 1.250–1.700, Lots 1–1,75, keine Gewinntage, Hedge 500 € / 10.000 $ = 0,05 €/$ (Finn).
Beispiel aus dem Test: Ziel 1.000 → TP ≈ 475 $, nach einem 475-$-Tag hebt der Planer das Endziel auf ≥ 950/969, damit der größte Tag ≤ 50 % bleibt.

Der folgende Absatz ist der Stand VOR BG2:

**Funded-CFD-Planer:** kennt keine Varianten je Konto. Heute gäbe es für einen Nano-Funded die Standard-Werte (Gewinntage 3 × 500,
Ziel 1.000–2.000 ≤ Cap, SL 1.250–1.600 < Daily 3.000 — regelsicher, aber Hedge 1.000 €/8.000 $ ≈ 3× zu groß, Consistency nur zufällig
eingehalten). Nano-Funded gibt es frühestens nach zwei bestandenen Phasen → eigener Schritt BG2 (Code + Finns Hedge-Satz), s. SQL Teil 2.

---

Stand der Recherche: 19.11.2026. Quellen: Help Center help.blueguardian.com (alle 35 Artikel per Download vollständig gelesen; die Help-Center-Suche liefert immer dieselbe Liste, mehr Artikel gibt es nicht), Website blueguardian.com (Plan-Daten aus dem Seiten-JSON der Startseite), AGB (/terms-and-conditions) und Refund Policy (/refund-policy). Plan-Artikel „2 Step Nano“ und „2 Step Standard“: zuletzt aktualisiert am 13.11.2026; „How payouts work“ und „Account inactivity“: 17.11.2026.

Kurzzeichen der Quellen:
- **[NANO]** https://help.blueguardian.com/en/articles/18426785-2-step-nano-rules
- **[STD]** https://help.blueguardian.com/en/articles/18426783-2-step-standard-rules
- **[PAY]** https://help.blueguardian.com/en/articles/18426605-how-payouts-work
- **[NEWS]** https://help.blueguardian.com/en/articles/18426788-cfd-news-trading-rules
- **[INACT]** https://help.blueguardian.com/en/articles/18426606-account-inactivity-rule
- **[OWN]** https://help.blueguardian.com/en/articles/18426721-account-rules-ownership-devices-and-fair-use
- **[COND]** https://help.blueguardian.com/en/articles/18426741-cfd-trading-conditions-markets-commissions-and-leverage
- **[PROH]** https://help.blueguardian.com/en/articles/18426719-prohibited-trading-strategies
- **[BREAK]** https://help.blueguardian.com/en/articles/18426723-what-happens-if-i-break-a-rule
- **[DAY]** https://help.blueguardian.com/en/articles/18426727-trading-hours-and-the-trading-day
- **[ACC]** https://help.blueguardian.com/en/articles/18426641-how-many-accounts-can-i-have
- **[BILL]** https://help.blueguardian.com/en/articles/18426640-paying-for-your-account-methods-card-rules-and-refunds
- **[KYC]** https://help.blueguardian.com/en/articles/18426598-kyc-verification-what-you-need-and-when
- **[HOW]** https://help.blueguardian.com/en/articles/18426633-how-blue-guardian-works
- **[PLAT]** https://help.blueguardian.com/en/articles/18426740-trading-platforms
- **[WEB]** https://blueguardian.com/ (Plan-Karten/Regel-Kacheln im Seiten-JSON, Plan „two_step_nano“ / „two_step_standard“, Größe 100000)
- **[AGB]** https://blueguardian.com/terms-and-conditions
- **[REF]** https://blueguardian.com/refund-policy

---

## (1) Tabelle Nano vs. Standard (100K)

### Evaluation (Phase 1 / Phase 2)

| Regel | 2 Step Nano | 2 Step Standard | Quelle |
|---|---|---|---|
| Preis 100K | **167 $** (Listenpreis 239 $; Website zeigt Code GUARD30 „30 % sparen“) | **324 $** (Listenpreis 463 $) | [WEB] |
| Gewinnziel Phase 1 | 8 % = 8.000 $ | 8 % = 8.000 $ | [NANO] [STD] [WEB] |
| Gewinnziel Phase 2 | 5 % = 5.000 $ | 4 % = 4.000 $ | [NANO] [STD] [WEB] |
| Max Daily Loss | 3 % vom Startkapital = 3.000 $ | 4 % vom Startkapital = 4.000 $ | [NANO] [STD] |
| Daily-Loss-Bezug | Höherer Wert aus Balance oder Equity beim Reset 17:00 New York; ohne offene Trades: geschlossene Balance minus 3 % | dito, minus 4 % | [NANO] [STD] [DAY] |
| Beispiel Daily Loss (100K) | 2.000 $ Floating-Gewinn beim Reset → Equity darf am Folgetag nicht unter 99.000 $; 2.000 $ Floating-Verlust → Grenze 97.000 $ | analog → 98.000 $ bzw. 96.000 $ | [NANO] [STD] |
| Max Drawdown | 10 % **statisch** vom Startkapital, Equity inkl. offener Trades nie unter 90.000 $ | 8 % **statisch**, Equity nie unter 92.000 $ | [NANO] [STD] |
| Mindest-Handelstage | **keine** | **3 Tage mit je ≥ 0,5 % Gewinn**, nicht aufeinanderfolgend nötig | [NANO] [STD] |
| Max. Handelstage | unbegrenzt | unbegrenzt | [WEB] |
| Consistency | keine | keine | [WEB] (Nano-Kachel „None“; Standard ohne Kachel) |
| News | erlaubt | erlaubt | [NANO] [STD] [NEWS] |
| Mindest-Haltezeit | 2 min je Trade („tick scalping“) | 2 min | [NANO] [STD] |
| Overnight / Wochenende | erlaubt | erlaubt | [NANO] [STD] [WEB] |
| EAs | erlaubt, wenn eigenes Setup | dito | [NANO] [STD] |
| Trade Copier | „Yes“ (Website) – laut Help Center nur zwischen eigenen Konten | dito | [WEB] [NANO] [STD] |
| Hebel | FX 1:50, Indizes + Rohstoffe **1:10**, Krypto 1:2 | dito | [NANO] [STD] [COND] |
| Kommission | FX + Rohstoffe 5 $/Lot, Indizes + Krypto 0 $ | dito | [COND] |
| Stop-out | Margin Level 100 % → unprofitabelster Trade wird geschlossen | dito | [COND] |
| Stop-Loss Pflicht | nein (Regelhaltung trotzdem eigene Verantwortung) | nein | [NANO] [STD] |
| Start der Evaluation | mit dem ersten Trade (Inaktivitäts-Uhr aber ab Kontoerstellung) | dito | [HOW] [INACT] |
| Nach Phase 2 | „final review“, dann Funded; Login + Trader Agreement + Zertifikat in 6–12 Geschäftsstunden | dito | [NANO] [STD] [HOW] |
| Phase-1- vs. Phase-2-Unterschied | nur Gewinnziel (8 % → 5 %); alle anderen Regeln gleich | nur Gewinnziel (8 % → 4 %); Mindesttage gelten je Phase („each over at least 3 trading days“) | [NANO] [STD] |

### Funded

| Regel | 2 Step Nano | 2 Step Standard | Quelle |
|---|---|---|---|
| Max Daily Loss | 3 % (3.000 $) | 4 % (4.000 $) | [WEB] (Funded-Kacheln) |
| Max Drawdown | 10 % statisch | 8 % statisch | [WEB] |
| Consistency | **50 %**: bester Tag muss im Payout-Zeitraum **unter** 50 % des Gesamtgewinns liegen; sperrt nur den Payout, kein Breach (Beispiel: bester Tag 1.000 $ → mehr als 2.000 $ Gesamtgewinn nötig) | **keine** | [NANO] [PAY] [WEB] |
| Guardian Shield | **gilt nicht** | **2 % kombinierter Floating-Verlust** aller offenen Trades → GS schließt „meist“ alle offenen Trades; 1. Mal: Split dauerhaft 50 %; 2. Mal: Konto dauerhaft breached; weitertraden sofort möglich | [NANO] [STD] |
| Payout-Rhythmus | alle 14 Tage, keine Mindest-Handelstage | erst nach erfüllten Mindest-Handelstagen **und** 14 Tagen seit dem ersten Trade, danach alle 14 Tage ab letzter Anfrage; mit Add-on alle 7 Tage | [NANO] [STD] [PAY] |
| Payout-Cap | **2 % vom Startkapital je Zyklus = 2.000 $**; Mehrgewinn bleibt im Konto | **kein Cap** (in keiner Quelle genannt; Cap-Liste in [PAY] nennt nur Instant + Nano) | [NANO] [PAY] [WEB] |
| Profit Split | 80 %, mit Add-on 100 % | 85 %, mit Add-on 90 % | [NANO] [STD] [PAY] |
| Add-ons beim Kauf (Website) | **keine** im Checkout-JSON (addOns leer), Kachel zeigt aber „Up to 100%“ | „90% Profit Split“ und „**First Payout in 7 days**“ | [WEB] |
| Payout-Bedingungen | Balance über Startkapital, Consistency erfüllt, keine Regelverstöße, alle Positionen **und Orders** geschlossen | Balance über Startkapital, keine Verstöße, alles geschlossen | [NANO] [STD] [PAY] |
| Mindestbetrag | 100 $ Krypto / 500 $ Rise | dito | [PAY] |
| Max je Anfrage | Krypto max. 1.000 $; über 1.000 $ nur über Rise | dito | [PAY] |
| Gebühr | 3 % Bearbeitungsgebühr auf jeden Payout | dito | [PAY] |
| Bearbeitung | innerhalb 24 Geschäftsstunden; Konto ist während der Prüfung **read-only** | dito | [PAY] |
| Voraussetzung 1. Payout | KYC (einmal je Person, nur ein verifiziertes Profil), Rise vorab einrichten | dito | [PAY] [KYC] |
| News | **±5 min** um High-Impact (rote) News auf betroffenen Instrumenten kein Öffnen/Schließen; FOMC **jeder** Stufe (auch gelb/orange); Gewinn im Fenster oder stark news-getrieben wird entfernt, **kein Breach** | dito | [NANO] [STD] [NEWS] |
| Hebel | 1:50 max (Website); Tabelle [COND] nennt für Funded nur „1 Step und 2 Step Standard“ (FX 1:50 / Indizes 1:10 / Rohstoffe 1:10 / Krypto 1:2), Nano-Funded fehlt dort | FX 1:50, Indizes 1:10, Rohstoffe 1:10, Krypto 1:2 | [WEB] [COND] |
| Withdrawal-Buffer 1 % | nicht genannt (gibt es nur bei Plänen mit Trailing-DD) | nicht genannt | [NANO] [STD] |
| Gebühren-Rückerstattung | Eval-Gebühr wird nach dem **4. Payout** voll erstattet (Konten ab 21.01.2026); nicht bei Hard-Breach vor dem 4. Payout | dito | [BILL] |
| Max. Kapital je Person | 400.000 $ aktive Funded-Balance gesamt (alle Funded + Instant); darüber Warteschlange | dito | [ACC] |
| Scaling | CFD allgemein: 12 % Gewinn in 3 Monaten regelkonform → +30 % der Anfangsbalance, bis 4.000.000 $ (nicht planspezifisch ausgewiesen) | dito | [ACC] |
| Inaktivität | ≥ 1 Trade je 30 Tage, Uhr läuft ab Kontoerstellung; sonst Breach | dito | [INACT] [ACC] |

---

## (2) Versteckte Regeln für den Copier-/Hedge-Betrieb

Betrieb: MT5-Master → Copier auf mehrere Konten (auch anderer Personen/Kunden), Gegen-Hedge auf anderem Konto/anderer Firma, große TP/SL (Ziel in 1–2 Trades), mehrere Konten je Person, VPS/gleiche IP.

| # | Regel (sinngemäß) | Betrifft | Quelle | Bedeutung für den Betrieb |
|---|---|---|---|---|
| 1 | **Copy Trading nur zwischen Konten, die man rechtlich selbst besitzt** (inkl. eigener Eval → eigenes Funded). Website-Kachel „Trade Copier: Yes“ meint nur das. | beide | [NANO] [STD] [OWN] [WEB] | Master eines Betreibers → Konten von Kunden/anderen Personen = **verboten**. Innerhalb einer Person erlaubt. |
| 2 | Kopieren anderer Trader, Signalgeber oder Trade-Gruppen ist nicht erlaubt (ausdrücklich im Futures-Teil); bei CFD: VPN/VPS dürfen nicht genutzt werden, um **Copy-Trading-, Gruppen- oder Signal-Regeln** zu umgehen. | beide | [PROH] [NANO] [STD] | Ein zentraler Master, der viele Personen bedient, fällt unter „group trading/signal“. |
| 3 | **Hedging zwischen getrennten Konten verboten** – egal ob eigene oder fremde Konten. Innerhalb **eines** CFD-Kontos ist Hedging erlaubt. | beide | [PROH] | Gegen-Hedge auf einem anderen Blue-Guardian-Konto = verboten. |
| 4 | AGB: Verboten ist der Versuch, ein Challenge-Konto mit einem anderen Konto **bei Blue Guardian oder bei einer dritten Firma** zu „arbitragen“ (Entscheidung im alleinigen Ermessen von BG). Dazu kommen das Verbot von „hedge arbitrage“, Reverse- und Latency-Arbitrage (CFD) sowie das Verbot von „offsetting positions“ und Hedging über Konten im Abschnitt zu mehreren Accounts. | beide (AGB nennt ausdrücklich Challenge) | [AGB] [PROH] | **Gegen-Hedge bei einer anderen Prop-Firma ist ausdrücklich erfasst.** |
| 5 | **Koordiniertes Trading mit anderen Personen** verboten, z. B. **gleiche oder entgegengesetzte Trades** über verschiedene Konten. | beide | [PROH] [AGB] („coordinated activity“) | Identische Copier-Trades auf Konten verschiedener Personen = Musterfall. |
| 6 | **Nur der Kontoinhaber selbst darf traden**; niemand darf für einen Trades platzieren/verwalten; Login-Daten nicht teilen. Wird Fremd-Trading erkannt → sofortige Kündigung. | beide | [OWN] [PROH] | Betreiber, der Kundenkonten bedient = verboten (Kunde müsste selbst traden). |
| 7 | **CID-Geräteregel**: jedes Login-Gerät hat eine Kennung (CID). Ein Gerät darf nie für das Konto **eines anderen Traders** genutzt worden sein. Ausdrücklich eingeschlossen: Geräte von Freunden/Familie/Kollegen/Communities/Signalgebern/**Account Managern**, geteilte Rechner und **VPS-Dienste**. Folge eines Treffers: Konten gelten als verknüpft, meist bei der **Payout-Prüfung** geprüft → Payout-Ablehnung, Gewinn-Entfernung, Sperre/Schließung. Entscheidungen des Risk Teams sind endgültig. | beide | [OWN] | Mehrere Personen auf einem VPS/PC = CID-Treffer. **Eine Person mit mehreren Konten auf einem Gerät ist laut Text nicht verboten** (Regel betrifft nur „anderer Trader“). |
| 8 | Zur IP: Im Help Center gibt es für CFD **keine eigene IP-Regel** (nur beim Monatswettbewerb „ein Konto je E-Mail und IP“). KYC muss auf eigenem Gerät/eigener Verbindung laufen – **ohne VM, Remote Desktop oder Proxy**. | KYC/Payout | [KYC] | Gleiche IP ist nicht ausdrücklich geregelt; erkannt wird über CID. Für die KYC kein Parsec/RDP/VPS nutzen. |
| 9 | **Gambling-Regel (CFD): mehr als 80 % der Margin in offenen Trades** = „all or nothing“ → Payout-Ablehnung, Gewinn-Entfernung oder Kündigung. | beide (Payout-Prüfung) | [PROH] | Große Lots für „Ziel in 1–2 Trades“: Margin-Auslastung unter 80 % halten. |
| 10 | AGB-Risikomanagement: BG kann bei **übermäßigem Risiko je Einzeltrade**, übermäßigem kumulierten Risiko in überlappenden Trades und „**Boom or Bust**“ (Erfolg hängt an einem Trade oder an einer News-Serie) Konten kündigen bzw. Auszahlungen verweigern; Risk Review „in jeder Phase“ möglich. | beide | [AGB] | **Ziel in 1–2 Trades mit großem TP/SL** passt genau in dieses Muster, auch ohne festen %-Wert. |
| 11 | AGB: Verboten sind eine **andere Strategie im Funded als in der Prüfung** sowie **Strategien von Dritten bzw. fertig gekaufte „Pass“-Strategien**. | Übergang Challenge → Funded | [AGB] | Groß-TP zum Bestehen, danach anderes Muster im Funded = angreifbar; ein fremder Master gilt als „third-party strategy“. |
| 12 | AGB: **Front-Running von anderswo platzierten Trades** ist verboten. | beide | [AGB] | Ein zeitversetzter Copier von einem externen Master kann so gedeutet werden. |
| 13 | AGB: **Ein aktives Konto je Challenge-Stufe**, außer mit vorheriger schriftlicher Zustimmung. | Challenge | [AGB] | **Widerspruch** zu [ACC] („so viele Evaluations wie man will“). Mehrere gleichzeitige 2-Step-100K-Konten je Person sind laut AGB nicht gedeckt. |
| 14 | AGB: keine mehreren Profile, keine Konten über **Dritte/Strohleute (nominees)**, kein Umgehen der **maximalen Kapitalzuteilung**; alle eigenen Profile müssen gemeldet werden. Help Center: Mehrfach-Konten zum Ausnutzen von Promo-Codes, Resets oder Payout-Bedingungen → alle verknüpften Konten schließen, Gewinne nichtig, Sperre. | beide | [AGB] [OWN] [KYC] | Kunden als Konto-Halter, um über 400.000 $ je Betreiber zu kommen = ausdrücklich erfasst. |
| 15 | Kauf nur mit **eigenem Zahlungsmittel**: Kontoname = Karteninhaber = Rechnungsadresse; Karten Dritter werden nie akzeptiert. AGB: kein Kauf **für Dritte**, kein Kauf **durch Dritte**. | Kauf | [BILL] [AGB] | Betreiber kauft für Kunden oder Kunde bezahlt mit Betreiber-Karte = Verstoß. |
| 16 | Payout geht nur an den Kontoinhaber (Name = Empfänger). | Funded | [OWN] | — |
| 17 | **MT5-Passwort darf nicht geändert werden** (es muss das von BG vergebene sein). | beide | [OWN] | Copier/Investor-Setup ohne Passwortwechsel. |
| 18 | **Guardian Shield (nur Standard Funded)**: 2 % Floating-Verlust aller offenen Trades zusammen (= 2.000 $ auf 100K) → Schließung; 1. Mal Split dauerhaft 50 %, 2. Mal Breach. | Standard Funded | [STD] | Großer SL > 2 % ist im Standard-Funded faktisch unmöglich; schon ein Trade mit 2 % offenem Minus löst aus. Nano Funded hat kein GS. |
| 19 | **Nano Funded Consistency 50 % + Cap 2 %**: der beste Tag muss unter 50 % des Zyklusgewinns liegen; ausbezahlt werden höchstens 2.000 $ je 14 Tage. | Nano Funded | [NANO] [PAY] | Ein einzelner Gewinntag reicht nie für einen Payout; man braucht mindestens 2 Gewinntage im Zyklus. |
| 20 | Mindest-Haltezeit **2 min** je Trade; HFT, Tick-Scalping, Arbitrage-Bots und **Trade-Emulatoren** verboten. | beide | [NANO] [STD] [PROH] | Copier-Teilschließungen/Justagen innerhalb von 2 min vermeiden. |
| 21 | EAs nur, wenn es das **eigene Setup** ist; VPN/VPS erlaubt, aber nicht zur Umgehung der Copy-/Gruppen-/Signal-Regeln. | beide | [NANO] [STD] | — |
| 22 | News funded: ±5 min (rote News + FOMC jeder Stufe) auf betroffenen Instrumenten; Gewinn wird entfernt, auch bei Umgehungsversuchen; kein Breach. USD-News betreffen auch XAUUSD, NDX100, SPX500, US30, BTC, ETH. | Funded | [NEWS] | Copier muss Funded-Konten in den Fenstern sperren. |
| 23 | AGB: Equity-CFD kurz vor Handelsschluss eröffnen, um auf die Eröffnungslücke zu setzen = verboten (Ermessen). | beide | [AGB] | — |
| 24 | **Jede bestandene Evaluation wird vor dem Funding geprüft** (auch durch den Broker). Bei Verstoß: kein Funded, evtl. keine Erstattung. Verstöße werden oft erst **manuell bei Payout/Compliance-Check** gefunden, auch rückwirkend; Maßnahmen auch gegen **verknüpfte Konten**. | beide | [BREAK] [AGB] | Ein Muster, das das System nicht automatisch erkennt, ist damit nicht sicher. |
| 25 | Wer Inhaber/Beteiligter einer **konkurrierenden Prop-Firma** ist, darf nicht bei BG traden. | beide | [AGB] | Nur relevant, wenn ein Unternehmen selbst Konten an Dritte vergibt. |
| 26 | Martingale ist bei CFD **nicht** verboten (80-%-Margin-Regel gilt aber weiter). | beide | [PROH] | — |
| 27 | Plattform wechseln geht nur, solange noch kein Trade platziert wurde (auch beim Phasenwechsel vor dem ersten Trade). | beide | [PLAT] | Plattform vor dem ersten Trade auf MT5 festlegen. |
| 28 | Inaktivität: CFD ≥ 1 Trade je 30 Tage, gezählt **ab Kontoerstellung**. Konten in der Funded-Warteschlange: 0,01 Lot je 30 Tage. | beide | [INACT] [ACC] | Vorrats-Konten nicht länger als 30 Tage liegen lassen. |
| 29 | Payout-Prüfung: Konto ist **read-only**, bis der Payout freigegeben ist. | Funded | [PAY] | Copier darf in der Zeit nicht auf das Konto kopieren (Fehlorders). |
| 30 | Alle CFD-Konten inkl. Funded sind **Demo/Simulation**; Funded erst nach unterschriebenem Trader Agreement. | beide | [HOW] | — |

---

## (3) Nicht gefunden / unklar

1. **Max. Lot / Max. Position** für CFD: im Help Center **keine Grenze** genannt. Grenzen sind nur Hebel, Margin, die 80-%-Gambling-Regel und der Stop-out bei 100 %. (Nur beim Monatswettbewerb steht ausdrücklich „kein Lot-Limit“.)
2. **Fester Prozentwert für Risiko je Trade**: nicht vorhanden; AGB sprechen nur allgemein von „excessive risk“ und „Boom or Bust“ (Ermessen).
3. **Daily Loss erreicht → Hard oder Soft Breach bei CFD?** Die CFD-Plan-Artikel sagen nichts dazu. Die Grafik in [DAY] beschreibt allgemein ein Tages-Sperren ohne Fehlschlag, [BREAK] nennt als Soft-Breach-Beispiel aber nur die optionale DLL bei Futures Reserve. Für CFD vermutlich Hard Breach, aber **nicht ausdrücklich belegt**.
4. **Nano-Payout: erster Payout wann?** „Every 14 days“ – ob die Frist ab Funding, ab dem ersten Funded-Trade oder ab Kauf zählt, steht nicht da (bei Standard: ab dem ersten Trade).
5. **Standard Funded: Mindest-Handelstage vor dem Payout** – „once you've met the minimum trading days“: ob im Funded erneut 3 Tage ≥ 0,5 % nötig sind oder die Tage aus der Evaluation gemeint sind, ist nicht eindeutig.
6. **Standard 7-Tage-Add-on**: Help Center sagt „alle 7 Tage“, die Website-Checkout-Bezeichnung lautet „First Payout in 7 days“ (nur der erste?). Widerspruch.
7. **Nano 100-%-Add-on**: Help Center und Website-Kachel („Up to 100%“) nennen es, im Checkout-JSON hat Nano aber **keine Add-ons**. Unklar, wie bzw. ob es kaufbar ist.
8. **Copier von einem externen eigenen Konto** (z. B. eigenes Konto bei einer anderen Firma als Master): Bei Instant Standard steht ausdrücklich „inkl. eigener externer Konten“, bei 2 Step nur „eigene Eval- und Funded-Konten“. Für 2 Step nicht ausdrücklich erlaubt; die AGB-Regeln zu Arbitrage mit Drittfirmen und zum Front-Running sprechen dagegen.
9. **IP-Regel** (gleiche IP/VPS für Konten derselben Person): im Help Center nicht geregelt, nur die CID-Geräteregel (gegen andere Trader). Gleiche IP verschiedener Personen ist nicht als eigene Regel genannt, dürfte über CID/VPS aber erfasst sein.
10. **AGB „ein aktives Konto je Challenge-Stufe“** gegen das Help Center „unbegrenzte Evaluations“: Widerspruch, welcher Text gilt, ist offen. Vor dem Kauf mehrerer gleicher Konten beim Support schriftlich klären.
11. **Refund Policy „keine Erstattung, alle Verkäufe endgültig“** gegen [BILL] „Gebühr wird nach dem 4. Payout erstattet“: Die Erstattung nach dem 4. Payout ist eine Leistung im Funded und kein Rücktritt; trotzdem widersprechen sich die Texte.
12. **Reset-Option (Kauf eines Resets)** für CFD 2 Step: kein Artikel, kein Preis. Resets werden nur beim Missbrauchsverbot erwähnt.
13. **Scaling für Nano**: Der Scaling-Plan gilt allgemein für CFD, ob Nano (mit Cap 2 %) teilnimmt, ist nicht gesagt.
14. **Guardian Shield „usually“**: Wann GS ausnahmsweise nicht schließt, ist nicht erklärt; ob geschlossene Verluste oder nur Floating zählen: laut Text nur der kombinierte Floating-Verlust offener Trades.
15. **Hebel Nano Funded** fehlt in der Tabelle [COND] (dort steht nur „1 Step und 2 Step Standard“ für Funded); Website sagt „1:50 Max“, der Nano-Artikel nennt FX 1:50 / Indizes 1:10.
16. **Wochenend-Halten bei Krypto/Gaps**: erlaubt; Gap-Regel nur für Equity-CFDs in den AGB.
17. **Wie lange die Payout-Prüfung read-only dauert**: nur „innerhalb 24 Geschäftsstunden bearbeitet“.

---

## Kurzfazit: Abweichungen vom „Bekannt“-Stand

- **Nano**: alle bekannten Werte bestätigt (8/5 %, 3 % Daily ab höherem Wert aus Balance/Equity um 17:00 NY, 10 % statisch, keine Mindesttage, keine Consistency in der Challenge, News in der Challenge erlaubt, funded 50 % Consistency nur als Payout-Sperre, Cap 2 % = 2.000 $, alle 14 Tage, 80/100 %, kein Guardian Shield, News ±5 min, 2 min Haltezeit, **167 $** bestätigt, Listenpreis 239 $). Neu: Das 100-%-Add-on ist im Checkout nicht als Add-on sichtbar.
- **Standard**: Werte bestätigt (8/4 %, 4 % Daily, 8 % statisch, 3 Tage ≥ 0,5 %, 85/90 %, kein Cap, GS 2 % → 50 % → Breach). Genauer: Der erste Payout kommt **nach den Mindesttagen und 14 Tagen ab dem ersten Trade**; das Add-on heißt auf der Website „First Payout in 7 days“. **Preis 100K: 324 $** (Listenpreis 463 $).
- **Zusätzlich gilt für beide**: 3 % Payout-Gebühr, Krypto max. 1.000 $ je Anfrage, Indizes nur 1:10, 80-%-Margin-Gambling-Regel, max. 400.000 $ Funded je Person, Gebühr zurück nach dem 4. Payout, 30-Tage-Inaktivität ab Kontoerstellung, MT5-Passwort darf nicht geändert werden.
- **Kritisch für das Betriebsmodell**: Copy nur zwischen eigenen Konten. Hedging über Konten hinweg ist verboten, und die AGB nennen ausdrücklich auch Arbitrage gegen Konten **anderer Firmen**. Koordinierte gleiche oder Gegen-Trades verschiedener Personen sind verboten, ebenso ein gemeinsamer VPS mehrerer Personen (CID-Regel) und Strohleute, um über das Kapitallimit zu kommen. „Boom or Bust“ und ein Strategiewechsel zwischen Challenge und Funded sind verboten. Laut AGB ist nur **ein aktives Konto je Challenge-Stufe** erlaubt (Widerspruch zum Help Center). Geprüft wird vor allem manuell bei der Payout-Prüfung, auch rückwirkend.
