# Justage-Statistik — Anleitung für Claude

Seit 26.10.2026 (Finn): Das Nachziehen von TP/SL am echten Fill plus der robuste Ändern-Klick heißt **„Justage“**. Finn will
sehen, wann genau die Justage gegriffen hat und ob sie funktioniert hat. Nur Auswertung: keine Regel- oder Risiko-Prüfung daraus
bauen. Es geht nur darum, ob die Technik greift.

## Was die Justage ist

| Weg | Code | Wann sie greift | Ergebnis steht in |
|---|---|---|---|
| Echo V2 (`mt5v2`) | `order_bot._sltp_nachziehen` → `_sltp_klicken` | `final` pass (TP), blow (SL), beide; ab .1751 für jeden Trade mit SL: echter Verlust bis SL ab Fill > Plan + 15 % (ausloeser `plan`) oder > `tages_grenze_usd` (ausloeser `tagesgrenze`, SL auf min(Plan-SL, Grenze)) | `trade_plans.mt5_baseline.puls_spur` (msg + trail) |
| Orbit (`tvv2`) — **seit .1749 raus** | `order_bot._cdp_nachziehen` (Revert) | bis .1748: Marken `@final=pass` (TP schießt übers Ziel) / `@tages_grenze_usd=` (SL kostet mehr als die Grenze) | `order_signale.ergebnis.trail` (params.aktion = orbit), Zeile „Nachziehen am Fill: …“ |
| Polar | `polar_bot` Slave → `_sltp_klicken` | immer nach dem Fill: Airbag aus beiden Fills, sonst Plan-Abstände | `polar_lauf.slave.level` + `slave.schritte` |

Schwellen (order_bot.py): `NACHZIEHEN_AB_USD` 3 $ (kleiner = „nicht_noetig“), `NACHZIEHEN_VERSUCHE` 2, Ändern-Frist
`AENDERN_FRIST_S` 20 s (Echo) bzw. `TV_NZ_FRIST_S` 25 s (Orbit).

Achtung: Das Objekt `nachzug` (Echo) und `pruefung.nachziehen` (Orbit) kommen nicht als eigenes Feld in der DB an. Alles steht als Text
in der Spur, die Views lesen es per Regex. Wird ein Spurtext im Bot geändert, muss `sql/2026-10-26_justage_view.sql` mitziehen.

## Views

SQL: `sql/2026-10-26_justage_view.sql` (create or replace, security_invoker, Rückbau am Dateiende).

- `justage_ereignisse`: eine Zeile je Fall. Spalten: at (Dubai), tag, wer, gruppe, plan_id, route echo|orbit|polar,
  ausloeser ziel|blow|tagesgrenze|plan (kombiniert mit `+`, Polar airbag|plan|notfall), seite tp|sl|beide,
  ergebnis nachgezogen|abgebrochen|nicht_noetig|unklar, grund, dauer_s (+ dauer_ca), abweichung_vorher/nachher_usd,
  levels_vorher/nachher, aendern_dialoge, aendern_punkte, versuche, frist_erreicht, pc, quelle_id.
- `justage_statistik`: je Dubai-Tag × Route × Ergebnis, nur Gruppe „Hermann Technologies“. Spalten: anzahl, trefferquote_pct, Ø/max Dauer,
  Ø Abweichung vorher, Ändern-Dialoge, Frist erreicht, Auslöser.

## Abfragen

Letzte 7 Tage im Überblick:

```sql
select tag, route, ergebnis, anzahl, trefferquote_pct, dauer_s_avg, dauer_s_max, abweichung_vorher_usd_avg, frist_erreicht, ausloeser
from justage_statistik where tag >= (now() at time zone 'Asia/Dubai')::date - 6 order by tag desc, route, ergebnis;
```

Alle Fälle eines Tages (nur HT):

```sql
select at, wer, route, ausloeser, seite, ergebnis, grund, dauer_s, dauer_ca, abweichung_vorher_usd, levels_vorher, levels_nachher,
       aendern_dialoge, versuche, pc
from justage_ereignisse where gruppe = 'Hermann Technologies' and tag = (now() at time zone 'Asia/Dubai')::date order by at;
```

Nur die Fehlschläge mit Grund:

```sql
select at, wer, route, ausloeser, grund, dauer_s, pc, quelle_id from justage_ereignisse
where gruppe = 'Hermann Technologies' and ergebnis in ('abgebrochen', 'unklar') order by at desc limit 30;
```

Einzelfall nachlesen: Echo `select mt5_baseline->'puls_spur' from trade_plans where id = '<plan_id>'`, Orbit
`select ergebnis->>'trail' from order_signale where id = '<quelle_id>'`, Polar `select slave from polar_lauf where id = '<quelle_id>'`.

## Bewertungsregel

1. **Gegriffen** = es gibt eine Zeile. Echo: Final pass/blow/beide, SL > Plan + 15 % oder Tagesgrenze überschritten (Spur „SL: Verlust bis SL …
   → am Fill“). „SL ok (…)“ ist kein Fall. Orbit: nur bis .1748. Polar: jeder Slave-Fill.
2. **Funktioniert** = `nachgezogen` (Level per API bzw. Order-Zeile bestätigt). `nicht_noetig` ist auch in Ordnung: die groben Level lagen
   < 3 $ daneben bzw. das Ziel bzw. die Grenze hält schon. Die Trefferquote zählt nur nachgezogen ÷ (nachgezogen + abgebrochen).
3. **Ziel**: Trefferquote ≥ 95 % je Route über 7 Tage. Darunter die `grund`-Spalte bündeln. Ein Grund, der ≥ 3× in 7 Tagen oder an
   ≥ 2 PCs auftritt, ist ein Fehler-Muster → an der Ursache fixen, wie in `.claude/fehler-analyse.md`.
4. **Dauer**: Echo-Justage unter 30 s ist normal. Über 60 s heißt fast immer: Der Ändern-Dialog ging erst im zweiten Versuch auf
   (`versuche` 2, `aendern_dialoge` 2). Liegen solche Fälle gehäuft an einem PC, ist es Einrichtung (Terminal-Layout, Anker) statt Code.
   `dauer_ca` = Spur gekürzt, dann reicht die Dauer bis zum Lauf-Ende.
5. **unklar** = die Spur zeigt weder Erfolg noch Grund (meist abgeschnitten). Einzeln im Rohtext nachsehen, bevor gezählt wird.
6. `frist_erreicht` > 0 → der Dialog ging in der Frist nicht auf. Die groben F9-Level bleiben an der Position. Das ist kein Risiko, aber
   die Justage fehlte. Bei Häufung den Scan-Punkt (`aendern_punkte`, ab .1746) mit der PC-Kennung melden.

Stand 26.10.2026 (Probe gegen die Live-DB, nur gelesen): Echo 11 Fälle seit 23.10. (10× Ziel/TP, 1× Blow/SL), alle nachgezogen,
vorher 11–595 $ daneben. 3 davon brauchten den zweiten Ändern-Versuch (85–270 s, Spur gekürzt → dauer_ca). Polar 21.10.: 6 von 8 bestätigt. Orbit: noch kein
Fall (Justage erst seit .1747), die Erkennung ist mit nachgebauten Spuren geprüft.
