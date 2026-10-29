# Firmen-Schema für Challenge- und Funded-Planer — Inventur, Vorschlag, Umbau-Plan

Stand 30.10.2026, S3, nur gelesen (Code origin/main .1901, DB live). Auftrag Master / Finn: „Challenge-Planer, Funded-Planer: die ganze
Logik rein, dass nur noch jeweils der Input von mir je Firma fehlt.“ Ziel: jede firmenspezifische Regel ist ein Wert je Firma, der Code liest nur.
Eine neue Firma ist dann reine Dateneingabe.

---

## 0. Kurzfassung

- **Heute gibt es sechs Quellen für Firmenregeln:** `auto_plan_regeln.regeln.firmen[]` (Challenge-Planer), `funded_plan_regeln.firmen[]`
  (Funded-Planer), `liq_regeln` (Liq/DLL/Stufen), `wd_farmer_regeln.vorplan.regeln` (WD-TP, Kontrakte, Staffel), `firm_specs` (Symbol, $/Punkt,
  Tradovate-Username) und `account_templates` (Schablonen: DD, Kaufpreis, Consistency). Dazu kommen top-level Schalter in `regeln`
  (`apex_hedge`, `tradeify_final_hedge`, `echo_hedge`, `ausgleich.waage_ohne`).
- **Das Backend liest `regeln.firmen[]` schon gut** (Ziel, SL/TP, Menge, Puffer, Boden, DD, Größen, Kette, Flex, Tagesdeckel). Hart sind vor allem:
  Firmen-Erkennung/Klasse, WD-Werte, Hedge-Wege je Firma, Topstep-Sonderwege, Vorrat und Payout.
- **Das Frontend liest `regeln.firmen[]` gar nicht.** Es hat eigene feste Tabellen: `tpFirmIstCfd`/`tpFirmIstFutures`, `TC_GOOD_DAY_MIN`,
  `tpFundedHedgeVorgabe`, `TP_VP_VORGABE`, `MINDESTTAGE_JE_FIRMA`, `ADM_APEX_DD`, `PB_FIRMEN`, `admPayoutPctDefault`.
- **Viele Werte stehen doppelt** in Backend und Frontend: Good Day (`WD_GOOD_DAY_MIN` = `TC_GOOD_DAY_MIN`), Apex-DD je Größe (`AP_APEX_DD_JE_GROESSE_USD` =
  `ADM_APEX_DD` = `je_groesse`), Futures-Liste (`WD_FUTURES_FIRMEN` ≈ `tpFirmIstFutures` ≈ `WD_FUTURES_RX`), Tradeify-CFD-Ausnahme an
  7 Stellen.
- **Vorschlag:** eine Firmen-Liste als einzige Quelle (`regeln.firmen[]`, erweitert), die das Backend über `GET /firmen-regeln` auch dem
  Frontend gibt. Funded-Planer, WD und Hedge bekommen je einen Unterblock **in derselben Firmenzeile**. `liq_regeln` bleibt für Liq/DLL-Stufen
  (dort ist es schon Daten), `firm_specs` bleibt für Symbol/Punktwert.
- **Umbau in 9 kleinen Schritten**, jeder mit „vorher = nachher“-Test gegen die heutigen Werte. Kein Schritt ändert das Verhalten bestehender
  Firmen. Neue Firmen gehen ab Schritt 3 per Eingabe.

---

## 1. Inventur — wo Firmen hart im Code stehen

Legende Spalte „Feld“: ✅ Feld existiert und wird gelesen · ⚠️ Feld existiert, wird hier aber nicht gelesen · ❌ kein Feld.

### 1.1 Firmen-Erkennung und Klasse (Grundlage für alles)

| Stelle | Regel | Werte | Feld | Nötiges Feld |
|---|---|---|---|---|
| app.py:5895–6024 `_FIRM_RULES`/`_firm_norm` | Schreibweisen → Firma | 14 Firmen | ⚠️ `namen` | `namen` (Quelle für `_firm_norm`) |
| app.py:5904 `_ist_tradeify_cfd` + 7 Ausnahmen (11609, 12107, 13606, 14178, 24265, 25883, 26749); prophos.html:14693 `istTradeifyCfd` | „tradeify“+„cfd“ = eigene CFD-Firma | – | ❌ | `namen` je Firma (Tradeify CFD = eigene Zeile, die schon existiert) + Treffer „längster Name gewinnt“ |
| app.py:11499 `WD_FUTURES_FIRMEN`, 12097 `WD_BALANCE_FUTURES`, 26739 `ap_klasse`; prophos.html:50642/50652 `tpFirmIstCfd/Futures`, 27404, 65132 `WD_FUTURES_RX` | Futures oder CFD (Balance-Weg, Waage-Klasse, WD-Weg) | 6–8 Firmen | ⚠️ `route` | `klasse: "futures" \| "cfd"` |
| prophos.html:25106 `firmNormRichtung`, 64615 `tpVorplanFirmaKey`, 46632 Preset-Key | Firma → interner Schlüssel | – | ❌ | `key` (kurz, eindeutig) |
| app.py:19817 `AP_STILL_FIRMEN` | Fusion nie planen | fusionmarkets | ❌ | `planen: false` (Feld gibt es, nur nicht für Fusion) |
| app.py:12336 `ist_topstep_express`; prophos.html:64735 `kontoIstTopstepExpress` | Topstep Express/XFA: kein Plan, kein Boden, Balance zählt nicht | Name/Typ | ❌ | `express: {muster: ["EXPRESS","XFA"], typen: ["funded","winning_days"], planen: false, boden: "tsx"}` |

### 1.2 Challenge-Planer (`ap_*`)

| Stelle | Regel | Werte | Feld | Nötiges Feld |
|---|---|---|---|---|
| app.py:21150 `AP_APEX_DD_JE_GROESSE_USD` | DD je Größe (Rückfall) | 25k 1.500 … 300k 7.500 | ✅ `je_groesse.dd_usd` (gewinnt) | – (Konstante kann weg, sobald DB vollständig) |
| app.py:20393 | Futures-Puffer überschreibt `puffer` | 20 $/Kt, Gebühr 6 | ⚠️ `puffer_je_menge` | `gebuehr_je_kt_usd`, Puffer nur aus Regel |
| app.py:20430 `AP_FUT_DECKEL_PLUS_USD` | letzter Trade darf `tp_max` + 100 | 100 | ❌ | `tp_max_toleranz_usd` |
| app.py:20448 | Tagesgrenze nur CFD, Futures ignoriert `daily_usd` | – | ⚠️ `daily_usd`, `soft` | `daily_kappt: bool` |
| app.py:20353 `AP_REST_MIN(_CFD)` | Rest darunter → von Hand | 100 / 1 | ❌ | `rest_min_usd` |
| app.py:20151 `ap_tage_mini` | Mini-Trade Mindesttage: MNQ, 3–5 Pkt | MNQ, 2 $/Pkt | ⚠️ `klein_symbol` | `mindesttage: {anzahl, symbol, pkt:[3,5]}` |
| app.py:20164 | Topstep (tsv2): keine Mini-Trades | – | ✅ `route` | `mindesttage.mini: false` |
| prophos.html:50630 `MINDESTTAGE_JE_FIRMA` | FundedNext 5 Tage | 5 | ❌ | `mindesttage.anzahl` |
| prophos.html:50631 `GEWINNTAGE_JE_FIRMA` | Blue Guardian 3 × 500 $ | 3 / 500 | ⚠️ `gewinntage.tp` | `gewinntage: {anzahl, min_usd, tp}` |
| app.py:19890 `AP_KETTE_STANDARD`; 30321 `ap_kette_abhaken` | Topstep-Kette, Abhaken liest Standard statt `kette` | DD 4.500, Rand +1.500, Grenze 4.700 | ⚠️ `kette` | `kette.abhaken_rand_usd`, `kette.verlust_grenze_usd` |
| app.py:24256 `ap_tradeify_final_halten` | finaler Tradeify nur mit Hedge | – | ❌ (top-level) | `final.halten_ohne_hedge` |
| prophos.html:41221 `accConsSichtbar` | Consistency nur Tradeify | 40 %/50 % | ❌ (Schablone) | `consistency: {pct, addon_pct}` |
| prophos.html:77913 `PB_FIRMEN`, 77960 `pbStart` | Prop-Baum: Stufen, Ziel-%, 150k fest | – | ⚠️ `ziel_pct`, `groessen` | lesen aus `ziel_pct`/`groessen` |

### 1.3 Funded-Planer (`fdp_*`)

| Stelle | Regel | Werte | Feld | Nötiges Feld |
|---|---|---|---|---|
| app.py:33611 `FDP_FIRMEN_STANDARD` | Seed: Apex an, Rest aus; Ziel, max_trade, Kosten, DD, Kontrakte | Apex 150k 15.000/7.500/550 €/4.000 | eigene Tabelle `funded_plan_regeln.firmen[]` | → `firmen[].funded{}` |
| app.py:34053 `FDP_NQ_PPL`, „NQ“ fest | Symbol/Punktwert | NQ, 20 | ⚠️ `symbol` (FDP-Seed, nicht gelesen) | `symbol` lesen |
| app.py fdp_planen (~29728 laut Memory) | Route hart „tvv2“ → Topstep (Nova/tsv2) nicht planbar | tvv2 | ⚠️ `route` | `funded.route` |
| app.py:33603 `FDP_SL_MIN_USD` | kein Trade unter SL 100 | 100 | ❌ | `funded.sl_min_usd` |
| app.py:34046 | Richtung zufällig, keine Waage | – | ❌ | `funded.waage: false` |
| prophos.html:64091 `tpFundedHedgeVorgabe` | fester Gegenhedge € je Max-DD | Topstep 900/4.500 · Tradeify 1.000/4.500 · FN 1.000/10.000 · FP 1.500/12.000 · Apex 550/4.000 · 5ers 500/10.000 | ❌ | `funded.hedge_eur_je_dd: {eur, dd_usd}` |
| prophos.html:62106, 64273 | Topstep-Funded → Nova (tsv2) | – | ❌ | `funded.route: "tsv2"` |
| app.py:8800 `VORRAT2_STD.funded_wege` | Weg Funded → WD: Tradeify trades/14.500, Topstep 4.500/14.500, Apex Siege 2.500/7.500/15.000 | – | ❌ (nur vorrat_einstellung) | `funded.weg_zu_wd: {art, tps, …}` |
| prophos.html:77922 `PB_WD_PUFFER` | ab 4.500 Puffer = WD | 4.500 | ❌ | `funded.wd_ab_puffer_usd` |

### 1.4 Winning Days / Farmer

| Stelle | Regel | Werte | Feld | Nötiges Feld |
|---|---|---|---|---|
| app.py:13598 `WD_GOOD_DAY_MIN` = prophos.html:68749 `TC_GOOD_DAY_MIN` (doppelt) | Good-Day-Schwelle | Tradeify/Lucid/FNF 250 · Topstep 150 · Apex 100k 300 / 150k 350 · Tradeify CFD keine | ❌ | `wd.good_day_usd` (+ `je_groesse`) |
| prophos.html:64587 `TP_VP_VORGABE`, 64595 `TP_VP_FIRMEN`, 64596 `tpVpLucidWieTradeify` | WD/Funded-TP-Spanne, Kontrakte, Staffel; Lucid kopiert Tradeify | Funded 270–290, Apex 370–390, Apex100 320–340, Topstep 220–240 | ⚠️ `wd_farmer_regeln.vorplan` (Schlüssel hart) | `wd.tp`, `wd.kontrakte`, `wd.staffel`; „wie Tradeify“ = `erbt: "tradeify"` |
| app.py:11602 `_wd_v2_route`; prophos.html:65963 `wdPlanAufV2` | WD-Route: Topstep tsv2, Futures tvv2, sonst mt5v2 | – | ⚠️ `route` | `wd.route` (Rückfall `route`) |
| app.py:12333 `LT_WD_BLOW_PLUS`, prophos.html:28630 | WD-Liq = Größe + 100 | 100 | `liq_regeln` (Tradeify/Lucid) | bleibt `liq_regeln`, Konstante weg |
| app.py:8805 `wd_boden_ueber_start_usd` | Vorrat: WD-Boden über Start, Tradeify/FNF/Lucid | 100 | ❌ | aus `liq_regeln` lesen |
| prophos.html:61644, 64271 | Topstep-Funded gilt als WD-fähig, WD auf Topstep = tsv2 | – | ❌ | `wd.aus_funded: true`, `wd.route` |

### 1.5 Hedge / Final-Trade

| Stelle | Regel | Werte | Feld | Nötiges Feld |
|---|---|---|---|---|
| app.py:26112 `AH_FIRMA`, `ah_tick`; prophos.html:56180 | Apex-Challenge immer mit Fusion-Hedge, WD-Weg | top-level `regeln.apex_hedge` | ❌ je Firma | `challenge_hedge: {an, weg: "wd", groesse: "kauf_durch_dd", …}` |
| app.py:25879 `tfh_tick`, 25701 `TFH_STANDARD`; prophos.html:28450/28457/28617 | Tradeify-Final-Trade = Orbit V3 + Hedge, Liq = Start − (Risk − 100) | top-level `regeln.tradeify_final_hedge` | ❌ je Firma | `final_hedge: {an, groesse: "kontowert_durch_polster", liq_minus_usd: 100, …}` |
| app.py:26007 `HEDGE_ARTEN` | erlaubte hedge_art | apex, tradeify_final | ❌ | aus Firmen ableiten (`<key>_final`, `<key>_challenge`) |
| app.py:26130, 25841 | $/Punkt MNQ 2 / NQ 20 | – | `firm_specs.ppl` | aus `firm_specs` |
| prophos.html:56253 `efFrei` + DB `prophos_ein_finaler_frei` | nur 1 finaler Trade je ID (Tradeify) | 1 | DB-Schalter | `final.max_gleichzeitig_je_id` |
| app.py:12422 `ah_dll_balance` | Apex-Hedge Liq = max(Boden, Tagesstart − DLL) | Kontofeld | ⚠️ `daily_usd` | `daily_usd` lesen |

### 1.6 Waage, Paare, Abstände

| Stelle | Regel | Werte | Feld | Nötiges Feld |
|---|---|---|---|---|
| app.py:29163 `AP_WAAGE_OHNE_FIRMEN` | Apex in keiner Waage | ("apex",) | top-level `ausgleich.waage_ohne` | `waage: false` |
| app.py `ap_paare_legen` (Memory) | Apex ohne Paare, Topstep nur Trade 1 als Partner | – | ❌ | `paare: false \| "nur_t1"` |
| prophos.html:65209 `WD_FIRMA_ABSTAND_MIN` | 1 min Firmen-Abstand (alle gleich) | 1 | ❌ | `abstand_min` (Standard 1) |
| `funded_plan_regeln.zeiten.firma_abstand_min` | 15 min je Firma (Funded) | 15 | ✅ global | ggf. `funded.abstand_min` |

### 1.7 Boden, Liq, Größe

| Stelle | Regel | Werte | Feld | Nötiges Feld |
|---|---|---|---|---|
| app.py:12694 `liq_konto_groesse`; prophos.html:64748 `tpKontoGroesseAusName` | Größe aus Name (TDFYSL…150, KTC …) | Regex | ⚠️ `groessen` | `groesse_aus_name: regex` |
| app.py:8463 `vorrat_groesse`; prophos.html:77940 | CFD-Größe aus Balance <75k/125k | – | ⚠️ `groessen` | aus `groessen` (nächste) |
| prophos.html:64798 `tpTopstepMll` | Topstep-DD je Größe ohne Kontofeld | 50k 2.000 · 100k 3.000 · 150k 4.500 | ⚠️ `je_groesse` | `je_groesse.dd_usd` |
| prophos.html:17166 `ADM_APEX_DD` | Apex-DD je Größe (Payout-Puffer) | wie oben | ⚠️ `je_groesse` | `je_groesse.dd_usd` |
| app.py:12447 `_lt_liq_balance` | Nicht-WD-Liq aus `accounts.max_drawdown` | Kontofeld | ⚠️ `dd_usd` | Rückfall `dd_usd` |

### 1.8 Payout / Kauf (Randbereich, nicht Planer — nur der Vollständigkeit halber)

prophos.html:17095 `admPayoutPctDefault` (Split je Firma), 17121 (FundedNext Refund × 1,5), 17145 `ADM_ANFRAGBAR_REGELN`, 17167 `ADM_APEX_MAX`,
prophos.html:80276 (Topstep-Einheit „150k Combine“). Vorschlag: eigener Block `payout{}` je Firma, aber **nicht Teil dieses Umbaus**.

### 1.9 Schon generisch (nichts zu tun)

`ap_konto_rechnen` (bis auf die Klassen-Konstanten), `ap_regel_flex`, `ap_consistency_etappe`, `ap_tagesdeckel` (`max_konten_tag`), `_ap_boden`,
`ap_kontowert`, `zw_tick`, Echo-Hedge (`eh_*`, nur Route), `liq_regel_waehlen` (Daten in `liq_regeln`).

---

## 2. Vorschlag: Firmen-Schema

Eine Zeile je Firma in `auto_plan_regeln.regeln.firmen[]`. Bestehende Felder bleiben **unverändert** (Spalte „neu?“ = nein). Neue Blöcke sind
optional; fehlt ein Feld, gilt der Standardwert — und der Standardwert ist genau das heutige Verhalten.

```jsonc
{
  // ── Kennung & Klasse ─────────────────────────────────────────────── neu?
  "key": "tradeify",                 // kurz, eindeutig (Vorplan-, Good-Day-, Hedge-Schlüssel)     ja
  "name": "Tradeify",                // Anzeige                                                      ja
  "namen": ["tradeify"],             // Schreibweisen; längster Treffer gewinnt (Tradeify CFD!)      nein
  "klasse": "futures",               // futures | cfd                                                 ja
  "route": "tvv2",                   // Challenge-Weg: tvv2 | tsv2 | mt5v2                           nein
  "planen": true,                    // false = nie planen (Fusion)                                  nein
  "symbol": "NQ", "klein_symbol": "MNQ",                                                            // nein
  "groessen": [150000], "standard_groessen": [...], "wert_groessen": [...],                          // nein
  "groesse_aus_name": "(?:TDFYSL|FTDFYSLX)(\\d{2,3})",   // Regex, Gruppe 1 = k                     ja
  "express": null,                   // Topstep: {"muster":["EXPRESS","XFA"],"typen":["funded","winning_days"],"planen":false,"boden":"tsx"}  ja

  // ── Konto-Regeln (Challenge) ─────────────────────────────────────── (heute alles da)
  "boden": "nachziehend", "dd_usd": 4500, "dd_pct": null, "daily_usd": null, "daily_pct": null, "soft": false,
  "lock_bei_start": false, "skaliert": false, "kauf_eur": 215, "ziel_pct": {"challenge": 6},
  "phasen": { "challenge": { "sl": null, "tp": [3450,3550], "tp_max": 3600, "menge": [2,2.8], "menge_schritt": 1,
              "puffer_je_menge": {...}, "ziel_pct": 6, "dd_usd": 4500 } },
  "je_groesse": { "150000": { "dd_usd": 4500, "phasen": {...} } },
  "max_konten_tag": null, "kette": null, "flex": null,

  // ── Planer-Feinheiten, heute Konstanten ──────────────────────────── ja (alle mit Standard = heute)
  "daily_kappt": false,              // Futures: Tagesgrenze kappt TP nicht (heute: nur CFD kappt)
  "tp_max_toleranz_usd": 100,        // letzter Trade darf tp_max um so viel überschreiten (Futures)
  "rest_min_usd": 100,               // darunter von Hand (CFD 1)
  "gebuehr_je_kt_usd": 6, "puffer_je_kt_usd": 20,
  "waage": true,                     // Apex: false
  "paare": true,                     // Apex: false · Topstep: "nur_t1"
  "abstand_min": 1,
  "mindesttage": null,               // FundedNext CFD: {"anzahl": 5, "mini": true, "symbol": "MNQ", "pkt": [3,5]}
  "gewinntage": null,                // Blue Guardian: {"anzahl": 3, "min_usd": 500, "tp": [1000,1100]}
  "consistency": null,               // Tradeify: {"pct": 40, "addon_pct": 50}

  // ── Hedge in der Challenge ───────────────────────────────────────── ja
  "challenge_hedge": null,           // Apex: {"an": true, "weg": "wd", "groesse": "kauf_durch_dd", "netto_faktor": 1.0,
                                     //        "min_lot": 0.01, "vorlauf_min": 20, "nachlauf_min": 30, "liq": "boden_oder_dll"}
  "final_hedge": null,               // Tradeify: {"an": true, "halten_ohne_hedge": true, "groesse": "kontowert_durch_polster",
                                     //   "netto_faktor": 1.0, "max_lots": 100, "liq_minus_usd": 100, "max_gleichzeitig_je_id": 1,
                                     //   "route": "tvv2", "orbit": "v3"}

  // ── Funded (Big Trades) ──────────────────────────────────────────── ja (heute funded_plan_regeln.firmen[])
  "funded": null,                    // Apex: {"an": true, "route": "tvv2", "lock_usd": 100, "sl_min_usd": 100, "waage": false,
                                     //   "hedge_eur_je_dd": {"eur": 550, "dd_usd": 4000},
                                     //   "je_groesse": {"150000": {"ziel_gewinn": 15000, "max_trade": 7500, "kosten_eur": 550,
                                     //                              "dd": 4000, "kontrakte": {"2": 0.9, "3": 0.1}}, ...},
                                     //   "weg_zu_wd": {"art": "siege", "tages": 2500, "tp_tag": 7500, "ziel": 15000, "verlusttage_max": 2},
                                     //   "wd_ab_puffer_usd": 4500}
                                     // Topstep: {"route": "tsv2", ...}  ·  CFD: {"route": "mt5v2", ...}

  // ── Winning Days ─────────────────────────────────────────────────── ja (heute wd_farmer_regeln.vorplan + Konstanten)
  "wd": null                         // Tradeify: {"route": "tvv2", "good_day_usd": 250, "tp": [268,280], "kontrakte": [2,3],
                                     //   "staffel": [...], "aus_funded": false}
                                     // Lucid: {"erbt": "tradeify"}   Apex: {"good_day_usd": {"100000": 300, "150000": 350}, ...}
}
```

**Was NICHT in `firmen[]` wandert** (dort ist es schon Daten und richtig aufgehoben):
- `liq_regeln` — Liq-Art, DLL-Stufen je Balance (Apex PA), WD-Boden Größe + 100. Code-Konstanten wie `LT_WD_BLOW_PLUS` lesen künftig nur dort.
- `firm_specs` — Symbol, Einheit, $/Punkt, Tradovate-Username je ID. Hedge-Lots-Rechnung liest den Punktwert dort statt MNQ 2 / NQ 20 hart.
- `account_templates` — Konto-Anlage (Kaufpreis, DD, Consistency je Größe). Planer-Standard aus `firmen[]`, Konto-Wert aus der Schablone gewinnt.

**Standardwerte je Klasse** (gelten, wenn das Feld fehlt; = heutiges Verhalten):

| Feld | futures | cfd |
|---|---|---|
| `daily_kappt` | false | true |
| `rest_min_usd` | 100 | 1 |
| `tp_max_toleranz_usd` | 100 | 0 |
| `puffer_je_kt_usd` / `gebuehr_je_kt_usd` | 20 / 6 | aus `phasen.puffer` |
| `waage` / `paare` | true / true | true / false |
| `wd.route` | `route` | mt5v2 |
| Balance-Weg | Tradovate/TopstepX | MT5 |

---

## 3. Input von Finn je Firma (was heute fehlt)

Nur, was der Code heute nicht weiß oder nur als Konstante kennt. „=“ heißt: heutiger Wert, nur bestätigen.

| Firma | Fehlt / bestätigen |
|---|---|
| **Apex Trader** | = Challenge-Hedge an, Kauf ÷ DD. **Funded-Kontrakte**: DB sagt 2:90 % / 3:10 %, Code-Seed 75/25 bzw. 50/50 → welcher gilt? = Good Day 300/350. **Größen 25k/50k/75k/250k/300k**: nur DD bekannt, kein Kaufpreis/Ziel — planen ja/nein? |
| **Tradeify** | = Final-Hedge. **Funded-Planer**: aus — Ziel, Max-Trade, Kosten je Größe, Kontrakte fehlen, falls er an soll. = Consistency 40 % / 50 %. |
| **Tradeify CFD** | **Funded-Hedge-Satz** fehlt (heute keiner). **Good Day** fehlt (heute keiner). Phase 1 Ziel 5 %, Phase 2 10 % — Reihenfolge so richtig? |
| **Topstep** | **Funded/Nova**: Ziel, Max-Trade, Kontrakte je Größe; Route tsv2. **Final-Hedge** („wenn es so weit ist“): an/aus, Polster. DD je Größe 50k 2.000 / 100k 3.000 / 150k 4.500 bestätigen. Express: nie planen = richtig? |
| **Lucid** | **Final-Hedge** (wie Tradeify?): an/aus. **Funded-Hedge-Satz** fehlt. **Funded-Planer**-Werte fehlen. „erbt Tradeify“ für WD bestätigen. |
| **FundedNext Futures (FNF)** | **Funded-Planer**-Werte fehlen. Final-Hedge an/aus. Funded-Hedge-Satz = 1.000 € / 4.000 $ (laut Memory geplant) bestätigen. |
| **FTMO Futures** | **Funded-Planer**-Werte, Good Day, Funded-Hedge-Satz fehlen. Final-Hedge an/aus. |
| **FTMO (CFD)** | Funded-Hedge-Satz = 1.000 € / 10.000 $ (Memory „in Bau“) bestätigen. Mindesttage? |
| **FundedNext (CFD)** | = Mindesttage 5. = Funded-Hedge 1.000 € / 10.000 $. Phase-2-Ziel 5 % bestätigen. |
| **FundingPips** | = Funded-Hedge 1.500 € / 12.000 $. Mindesttage? |
| **The5%ers** | = Funded-Hedge 500 € / 10.000 $ (100k), 200k 1.000 €. |
| **Blue Guardian** | = Gewinntage 3 × ≥ 500 $. **Funded-Hedge-Satz** fehlt. |
| **Alle Futures** | Waage/Paare je Firma bestätigen (heute: Apex aus, Rest an, Topstep nur Trade 1). Firmen-Abstand 1 min (Challenge/WD) und 15 min (Funded) bestätigen. |

---

## 4. Umbau-Plan (je Schritt klein, testbar, ohne Verhaltensänderung)

Grundregel jedes Schritts: **Golden-Test vorher = nachher.** Vor dem Schritt einmal je Firma × Größe × Phase die heutigen Ergebnisse
(Planwerte, Klasse, Route, Good Day, Hedge-Satz, Boden) als JSON festhalten (`tools/selftest_firmen_golden.py` + Fixture mit Platzhalter-Konten);
nach dem Schritt muss dasselbe herauskommen. SQL nur als Datei, Einspielen durch den Master.

1. **Golden-Fixture bauen** (nur Tests, kein Code). Rechnet heute über `ap_konto_rechnen`, `_wd_v2_route`, `_wd_good_day`, `ap_klasse`,
   `liq_konto_boden`, `fdp_konto_rechnen` und im Frontend (`jsc`) über `tpFirmIstFutures`, `TC_GOOD_DAY_MIN`, `tpFundedHedgeVorgabe`,
   `tpVorplanFirmaKey`. Ergebnis: eine Tabelle „Firma → alle heutigen Werte“.
2. **Eine Firmen-Auflösung im Backend:** `firma_regel(name) -> (regel, key)` aus `regeln.firmen[]` (längster `namen`-Treffer, Tradeify CFD
   vor Tradeify), Rückfall `_firm_norm`. Noch kein Aufrufer umgestellt. SQL: `key`, `name`, `klasse` je bestehender Firma ergänzen (Werte =
   heutige Listen).
3. **Klasse aus Daten:** `ap_klasse`, `WD_FUTURES_FIRMEN`, `WD_BALANCE_FUTURES`, `_ist_tradeify_cfd`-Ausnahmen lesen `klasse`; Konstanten
   bleiben nur als Rückfall. **Ab hier ist eine neue Futures-/CFD-Firma per Eingabe planbar.**
4. **`GET /firmen-regeln` fürs Frontend** (gecacht, Gate eingeloggt): `tpFirmIstCfd/Futures`, `istTradeifyCfd`, `tpVorplanFirmaKey`, `WD_FUTURES_RX`
   lesen daraus, harte Liste bleibt Rückfall, falls die Route nicht antwortet.
5. **Planer-Konstanten als Felder:** `daily_kappt`, `tp_max_toleranz_usd`, `rest_min_usd`, `puffer_je_kt_usd`, `gebuehr_je_kt_usd`, `waage`, `paare`,
   `abstand_min`, `mindesttage`, `gewinntage`, `consistency`, `express`, `planen` (Fusion). Je Feld Standard = heutige Konstante.
   `ap_kette_abhaken` liest `kette` statt `AP_KETTE_STANDARD`.
6. **WD-Block:** `wd.good_day_usd`, `wd.route`, `wd.tp/kontrakte/staffel`, `wd.erbt`. Backend und Frontend lesen dieselbe Quelle →
   `WD_GOOD_DAY_MIN`/`TC_GOOD_DAY_MIN` doppelt weg. `wd_farmer_regeln.vorplan` bleibt Eingabe im Admin, schreibt aber in `firmen[].wd`
   (oder wird beim Lesen dort gemischt — Entscheidung im Schritt).
7. **Funded-Block:** `funded_plan_regeln.firmen[]` → `firmen[].funded` (gelesen über eine Hülle, die beide Quellen kennt, bis die alte
   Tabelle leer ist). `fdp_planen` liest `funded.route` (Topstep/Nova wird möglich), `symbol`, `sl_min_usd`, `waage`.
   `tpFundedHedgeVorgabe` liest `funded.hedge_eur_je_dd`.
8. **Hedge-Blöcke je Firma:** `challenge_hedge` (heute `regeln.apex_hedge` + `AH_FIRMA`) und `final_hedge` (heute `regeln.tradeify_final_hedge`
   + `tfh_tick` Tradeify-Filter). `ah_tick`/`tfh_tick` laufen über alle Firmen mit `an`. `HEDGE_ARTEN` aus den Firmen. DB-Trigger
   (`trade_plans_a1_apex_hedge`, `prophos_ein_finaler_frei`, `trade_plans_kontoart_weg`) bekommen die Firma über `hedge_art`, nicht den Namen —
   **eine** gemeinsame SQL-Datei (Memory-Falle: nie zwei Dateien mit je nur ihrem Block). **Ab hier ist der Lucid-/Topstep-Final-Trade reine
   Eingabe.** Prüfer-Pfad S2, weil Order-/Hedge-Logik.
9. **Admin-Maske „Firmen“:** eine Karte je Firma, Felder gruppiert (Konto · Challenge · Funded · WD · Hedge), leere Pflichtfelder rot
   („Input von Finn fehlt“). Alte Konstanten löschen, sobald der Golden-Test eine Woche ohne Rückfall-Treffer lief (Rückfall-Zähler im Log).

**Reihenfolge-Risiko:** Schritte 1–4 ändern nur die Quelle der Klasse, nicht die Rechnung. Schritte 5–7 fassen Planwerte an — je Schritt ein
Nachtlauf-Vergleich (`ap_planen` trocken gegen Live-Konten, Diff = 0). Schritt 8 ist Order-Pfad → S2 + Freigabe Finn.

**Aufwand grob:** 1–4 je ½ Tag, 5 ein Tag, 6–7 je ein Tag, 8 zwei Tage inkl. Prüfung, 9 ein Tag.
