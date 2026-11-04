// Selbsttest ENDLESUNG ÜBER DIE DEALS, Tab-Seite (N2, 04.11.2026) — im Browser auf prophos.html (Konsole oder javascript_tool) ausführen:
// window._deUrteil (Entscheidung Deal / nicht gelaufen / unklar) und window._sfVorOrderBeleg (Beleg „nicht platziert" nur im Kopf der Puls-Antwort).
(() => {
  const U = window._deUrteil, B = window._sfVorOrderBeleg, f = []
  const ok = (c, n) => f.push((c ? '✓ ' : '✗ ') + n)
  let r = U({ ok: true, lesbar: true, balance: 98000, positionen: 0, treffer: [7], offen: false, pl: -817.5 }, 98984.38); ok(r.art === 'deals' && r.pl === -817.5, 'Deal → P&L')
  r = U({ ok: true, lesbar: true, balance: 98984.38, positionen: 0, treffer: [], offen: false, pl: null }, 98984.38); ok(r.art === 'nicht_gelaufen' && r.pl === 0, 'kein Deal + Balance gleich → nicht gelaufen')
  r = U({ ok: true, lesbar: true, balance: 98500, positionen: 0, treffer: [] }, 98984.38); ok(r.art === 'unklar' && /Balance/.test(r.grund), 'kein Deal + Balance anders → unklar mit Grund')
  r = U({ ok: true, lesbar: true, balance: 98984.38, positionen: 0, treffer: [] }, null); ok(r.art === 'unklar' && /Vergleichs/.test(r.grund), 'ohne Vergleichs-Balance → unklar')
  r = U({ ok: true, lesbar: true, balance: 98984.38, positionen: 1, treffer: [] }, 98984.38); ok(r.art === 'unklar', 'offene fremde Position → unklar')
  r = U({ ok: false, lesbar: false, grund: 'Terminal nicht angemeldet (kein Konto)' }, 98984.38); ok(r.art === 'unklar' && /angemeldet/.test(r.grund), 'Terminal nicht lesbar → unklar mit Grund')
  r = U({ ok: true, lesbar: true, balance: 1, positionen: 1, treffer: [9], offen: true }, 1); ok(r.art === 'offen', 'Position offen → warten')
  ok(B('Kein MT5-Fenster mit Konto 14353615 gefunden. Evtl. steht am PC eine Windows-Abfrage offen'), 'Beleg: kein MT5-Fenster')
  ok(B("Terminal-Verbindung fehlgeschlagen: (-6, 'Terminal: Authorization failed') — Terminal läuft"), 'Beleg: Authorization failed')
  ok(B('F9-Dialog nicht gefunden — Abbruch, nichts gesendet. [0.0s·Hand…]'), 'Beleg: F9')
  ok(B('Abbruch VOR dem Order-Knopf (nichts platziert): Volumen-Feld uebernimmt 26 nicht'), 'Beleg: Volumen')
  ok(B('KEINE Bestaetigung binnen 12 s — Grund: Markt geschlossen (Server: Market closed) — Kontostand 97 119.63 (Journal: [Market closed]) → … Spur: [x]'), 'Beleg: Market closed')
  ok(!B('KEINE Bestaetigung binnen 12 s — Position nicht am Konto, Dialog geschlossen. Spur: [… Volumen-Feld leert nicht …]'), 'kein Beleg: Bestätigung fehlt ohne Grund')
  ok(!B('Order-Bot Timeout (300s) — im Terminal pruefen, ob die Order platziert wurde'), 'kein Beleg: Timeout')
  ok(!B('Verbindung zum Panel brach nach 17 s mitten in der Order ab — nichts gesendet?'), 'kein Beleg: Verbindungsabriss')
  ok(!B('Fuer diese Instanz laeuft gerade schon eine Order — warten'), 'kein Beleg: andere Order läuft')
  ok(!B("ok [0.0s·Hand → Volumen-Feld leert nicht ('0.00') — nichts platziert]"), 'Spur-Text zählt nicht (nur Kopf)')
  r = U({ ok: true, lesbar: true, balance: 1, positionen: 0, treffer: [1, 2], mehrdeutig: true }, 1); ok(r.art === 'unklar' && /eindeutig/.test(r.grund), 'zwei Treffer → unklar')
  ok(!B('KEINE Bestaetigung binnen 12 s — Grund: zu wenig freie Marge für dieses Volumen (API: nötig 45 969.94, frei 23 007.24) — Kontostand'), 'kein Beleg: Marge nur aus der API')
  ok(B('KEINE Bestaetigung binnen 12 s — Grund: Handel gesperrt (Server: trading disabled) — Kontostand 1'), 'Beleg: Server lehnt ab')
  r = U({ ok: true, lesbar: true, balance: 98984.38, positionen: 0, orders: 1, treffer: [] }, 98984.38); ok(r.art === 'unklar' && /schwebende/.test(r.grund), 'schwebende Order → unklar')
  // Vergleichs-Balance (Prüfer-Stopp N2): nie aus dem Plan selbst, nur Lesungen vor dem Claim
  const V = window._deVergleichsBalance, claim = '2026-11-03T03:52:06Z'
  ok(V('p1', claim, [{ id: 'p1', ended_at: '2026-11-03T03:52:00Z', mt5_baseline: { bal_nach: { ok: true, balance: 5, at: '2026-11-03T03:00:00Z' } } }]) === null, 'eigener Plan zählt nie')
  ok(V('p1', claim, [{ id: 'p0', ended_at: '2026-11-02T10:00:00Z', mt5_baseline: { bal_nach: { ok: true, balance: 98984.38, at: '2026-11-02T10:05:00Z' } } }]) === 98984.38, 'Lesung eines früheren Plans vor dem Claim')
  ok(V('p1', claim, [{ id: 'p0', ended_at: '2026-11-02T10:00:00Z', mt5_baseline: { bal_nach: { ok: true, balance: 1, at: '2026-11-03T05:00:00Z' } } }]) === null, 'Lesung nach dem Claim zählt nicht')
  ok(V('p1', claim, [{ id: 'p0', ended_at: '2026-11-02T10:00:00Z', mt5_baseline: { final: { balance_end: 98000 } } }]) === 98000, 'Rückfall final.balance_end vor dem Claim')
  return f
})()
