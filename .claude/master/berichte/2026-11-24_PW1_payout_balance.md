# PW1 — Balance nach dem Payout, Waiting for Payout bleibt hängen (24.11.2026, Slave 3)

Finns Frage: „Wann wird aktuell die Balance in Bezug auf Payout-Anfragen neu geladen?“ — plus Marc · FundedNext 100k …7821 · HT steht auf
„Waiting for Payout“ mit „Payout jetzt“, obwohl der Payout längst ausgezahlt ist.

## 1) Wann wird die Balance rund um einen Payout heute gelesen? (Stand origin/main 28b9ae28)

| Moment | Weg | Datei:Zeile | Schwäche |
|---|---|---|---|
| Payout **anfragen** (Finanzen) | `finBalanceNachPayout` → `accBalanceLesen`: sofort, nach 5 und 30 min | prophos.html:84621, Funktion 84529 | nur solange dieser Tab offen ist; die Firma zieht oft erst Stunden später ab |
| Payout **direkt buchen** (Finanzen) | dasselbe | prophos.html:84665 | wie oben |
| Payout **als erhalten abhaken** (Finanzen) | **gar nicht** — `finReceiveConfirm` liest nicht und leert kein Waiting | prophos.html:~84070–84115 | Lücke |
| Payout **als erhalten abhaken** (Admin → Payouts) | `admBalanceAnstossen` → POST `/admin/konto-balance-lesen`: sofort, 5 und 30 min; Waiting nur mit Option „waitingLeeren“ | prophos.html:~20500–20535, app.py:25677 | nur solange der Admin-Tab offen ist; nach dem ersten Fehlschlag still; scheitert sofort, wenn der PC der ID gerade nicht lebt (`_mt5_ort_fehler` → 409) |
| **Balance-Takt** (Railway, rund um die Uhr) Fall (E) | `ap_bal_auto_funded` liest Funded-Konten, deren Lesung älter als der letzte Trade oder der Payout ist (WP3) | app.py:46347, Takt 46551 | (a) überspringt Konten mit **Waiting for Payout** ganz, (b) zählt `accounts.tv_balance_at` als Lesung |
| **Flotten-Takt** am PC-Tab (alle 5 s, gedrosselt 5 min) | schreibt die Master-Balance aus dem Echo-Snapshot nach `tv_balance` + frisches `tv_balance_at` (Quelle `mt5`) | prophos.html:30769 / 30789 | schreibt einen **eingefrorenen** Stand (Terminal im Standby) mit frischem Zeitstempel, sobald die Panel-Notiz kurz fehlt |
| Planer **WP2** (Waiting nur mit Lesung nach dem Payout) | `fcp_payout_lesung_fehlt` vergleicht `tv_balance_at` mit Anfrage/Auszahlung | app.py:53370, Aufruf in `fcp_planen` | durch den Flotten-Takt ausgehebelt |

## 2) Was ist bei Marc …7821 passiert?

- 18.11. 14:35 letzter Trade (Balance danach 104.915,95). 18.11. 22:37 Payout angefragt (3.428,78 €), 19.11. 13:14 ausgezahlt / erhalten (Rise, Mail „disbursed“).
- Danach **nie ein abgeschlossener Lese-Auftrag** (`order_signale konto:27f94392…` seit 17.11. leer). Das Echo-Terminal steht im Standby, `mt5_live`-Notiz
  „Snapshot eingefroren“ (pc-7ftp5l, PC von Marc).
- 23.11. 03:26 UTC setzte der Planer wieder **Waiting for Payout** (Ziel 104.901 mit 104.915,95 „erreicht“); `tv_balance_at` stand auf 23.11. 19:31, Quelle `mt5`
  — der Flotten-Takt hat den eingefrorenen Stand mit frischem Zeitstempel geschrieben. Deshalb „Payout jetzt“ (payout_ready_at 23.11.).
- **Der Payout ist ausgezahlt** (pending_payouts status received, Buchung 70fdb0e1 über 3.428,78 €). Die echte Balance bei FundedNext ist sehr
  wahrscheinlich wieder ~100.000 — Prophos hat sie nie gelesen.

**Heute gleich (HT):** Mike · FundedNext 50k …7055 und Mike · FundedNext 100k …7057 — Waiting seit 19.11., Payout am 20.11. bestätigt, seitdem keine echte
Lesung (`tv_balance_at` 23.11. vom Flotten-Takt). Chris · FundedNext 50k …5614: Payout heute 15:48 bestätigt, noch nicht gelesen (normal, jetzt vom Takt erfasst).

## 3) Fix nach Finns Zielbild (Commit im Worktree, Planer → Prüfer S2)

Zielbild: „Payout anfragen → bei CFD direkt wieder Funded CFD, weitere Trades planen; Balance 1–12 h nach der Anfrage neu lesen; sobald der Profit
abgebucht ist, ganz normal im Trade-Planer.“

- **Anfrage = zurück auf Funded CFD:** Liegt die jüngste Anfrage (`pending_payouts.created_at`) nach `waiting_payout_since`, stellt der Funded-CFD-Planer
  Waiting zurück — auch für Anfragen aus Admin/anderen Logins (das Frontend tat es bisher nur beim eigenen Login). Ebenso, wenn Waiting **nach** der Anfrage
  auf alter Balance gesetzt wurde (Fall Marc). Nur HT-IDs, Update mit Guard, geplant wird nur, wenn das Update durchging; Gruppen: nur angezeigt.
- **In der Zwischenzeit (eine Zeile):** Bis die neue Balance gelesen ist, plant der Planer weiter mit **Balance − (Balance vor der Anfrage − Kontogröße)** —
  der angefragte Gewinn gilt schon als abgezogen, Gewinn des neuen Zyklus = was seit der Anfrage dazukam; kein „Ziel erreicht → Waiting“ und kein
  festgeschriebenes Zyklus-Ziel, bis die Abbuchung gelesen ist.
- **„Balance vor der Anfrage“** = End-Balance des letzten Trades vor der Anfrage (`final.master_balance`, bei Funded CFD immer gesetzt; Marc 104.915,95).
  Ohne Trade davor oder ohne Gewinn davor: normal rechnen. Anfragen älter als 30 Tage: normal.
- **Beobachtung nach der Anfrage** = abgeschlossener Lese-Auftrag (`order_signale` konto:<id>, `mt5_balance`/`konto_balance`, fertig, ok + Wert) ODER
  End-Balance eines danach beendeten Trades — nie `tv_balance_at` allein (Flotten-Takt). **Abgebucht** = jüngste Beobachtung liegt mindestens
  ½ × Vor-Gewinn (höchstens 500 $, mindestens 50 $) unter Vor-Balance + Trades seit der Anfrage (Teil-Payouts On Demand zählen mit). Dann ist sie die
  Balance (bis zur nächsten Beobachtung) und der Planer rechnet normal (Zyklus-Ziel wird festgeschrieben, WP2 nutzt dieselbe Lesung). Nach einem Trade
  zeigt seine End-Balance, ob abgebucht ist — kein doppelter Abzug.
- **Nachlesen:** neue Quelle (F) im Balance-Takt (HT und Gruppen) für Funded CFD, auch bei Waiting; nicht vor 1 h, 1–12 h nach der Anfrage im Abstand des
  Takts (3/Tag, 90 min), danach — solange nicht abgebucht — höchstens alle 12 h (bucht die Firma später ab, wird es trotzdem erkannt).
- **Waiting von Hand** bleibt: zurückgestellt wird nur, wenn die Anfrage nach dem Waiting liegt oder Waiting gesetzt wurde, ohne dass seit der Anfrage
  etwas beobachtet ist (Fall Marc).

**Wirkung nach dem Push:** der nächste Planer-Lauf stellt Marc …7821 und Mike …7055/…7057 auf Funded CFD zurück und plant sie mit Balance − angefragtem Gewinn
(Marc: 104.915,95 − 4.915,95 = 100.000); der Balance-Takt liest die drei (seit der Anfrage nie gelesen), danach rechnet der Planer mit der echten Balance.
Kein Daten-SQL nötig.

**Offen:** Zieht die Firma nie ab (Payout abgelehnt), plant der Planer weiter so, als wäre der Gewinn weg (konservativ: Ziel liegt höher als nötig) — bei
Bedarf eine Meldung „12 h nach der Anfrage nicht abgebucht“ als eigener Auftrag.

**Offen (nicht Teil des Fixes), weiter:** Flotten-Takt am PC-Tab (prophos.html:30769) schreibt eingefrorene Snapshots mit frischem Zeitstempel weiter — für die
Planer-Entscheidung nach Payouts zählt er jetzt nicht mehr; als eigener Auftrag: Snapshot-Alter aus dem Panel mitliefern und nur frische Stände schreiben.
Finanzen „als erhalten abhaken“ stößt weiter keine Lesung an — der Railway-Takt übernimmt das jetzt.
