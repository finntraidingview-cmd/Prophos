// ==UserScript==
// @name         Prophos TV-Reader
// @namespace    prophos
// @version      0.2.1
// @description  Liest offene TradingView-Positionen live aus dem DOM und schickt sie an den lokalen Prophos-Empfaenger. Kein NinjaTrader, kein zweiter Tradovate-Login, keine zusaetzliche Session.
// @match        https://*.tradingview.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// @updateURL    https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/tv-reader.user.js
// @downloadURL  https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/tv-reader.user.js
// ==/UserScript==

// Warum GM_xmlhttpRequest statt fetch: umgeht CORS/Mixed-Content sauber
// (HTTPS-Seite -> http://127.0.0.1). Ist die Standard-Zapfstelle fuer
// Userscripts, die mit einem lokalen Prozess reden.

(function () {
  'use strict';

  const ENDPOINT   = 'http://127.0.0.1:8790/positions';
  const INTERVALMS = 250;    // wie oft gelesen + gesendet wird (0,25 s — niedrige Hedge-Latenz)

  // --- Auslese-Kern (das am 28.08.2026 live bewiesene Snippet, als Funktion) ---
  // Die TradingView-Positionstabelle ist eine ka-table: jede Zelle traegt ein
  // stabiles data-label (Spaltentitel). Daran haengt der Reader auf, NICHT an
  // den gehashten CSS-Klassen (die aendern sich bei TV-Updates).
  // TV MUSS auf Deutsch laufen: nicht nur die data-labels sind lokalisiert,
  // auch das ZAHLENFORMAT haengt an der Sprache — der Verbinder parst
  // deutsche Zahlen (parse_de_zahl: "29.618,25"). Englisch wuerde also still
  // 0 Positionen liefern und spaeter falsche Preise. Deshalb wird die
  // englische Positionstabelle ERKANNT und als Warnung gemeldet statt
  // mitgelesen (Fund 28.08.2026, PC 1: TV lief auf Englisch, Reader stumm
  // bei offener Position).
  let spracheFremd = false;

  function lesePositionen() {
    const rows = new Map();
    const labels = new Set();
    document.querySelectorAll('td[data-label]').forEach((td) => {
      const tr = td.closest('tr');
      if (!tr) return;
      if (!rows.has(tr)) rows.set(tr, {});
      const label = td.getAttribute('data-label');
      labels.add(label);
      // \s+ -> ' ': TradingView bricht manche Zellen um ("+190,00\nUSD") — Zeilenumbrueche raus
      rows.get(tr)[label] = td.innerText.replace(/\s+/g, ' ').trim();
    });
    spracheFremd = labels.has('Unrealized P&L') && !labels.has('Unrealisierter G&V');
    // Nur echte OFFENE Positionen: die tragen 'Unrealisierter G&V'.
    // Order-Verlauf-Zeilen (mit 'Order-ID'/'Status') fallen so raus.
    return [...rows.values()]
      .filter((r) => r['Unrealisierter G&V'] && r['Symbol'])
      .map((p) => ({
        symbol:   p['Symbol'],
        seite:    p['Seite'],                          // Long / Short
        menge:    p['Menge'],
        einstieg: p['Durchschn. Ausführungspreis'],
        sl:       p['Stop Loss']   || null,
        tp:       p['Take Profit'] || null,
        pnl:      p['Unrealisierter G&V'],
      }));
  }

  // --- On-Screen-Status (damit man ohne offene Console sieht, dass es laeuft) ---
  const badge = document.createElement('div');
  badge.style.cssText =
    'position:fixed;z-index:2147483647;bottom:12px;right:12px;' +
    'background:#0b0b0b;color:#38d66b;font:12px/1.4 ui-monospace,monospace;' +
    'padding:6px 10px;border-radius:8px;opacity:.9;pointer-events:none;' +
    'box-shadow:0 2px 8px rgba(0,0,0,.4)';
  badge.textContent = '● Prophos-Reader startet …';
  const mount = () => { if (document.body) document.body.appendChild(badge); else setTimeout(mount, 300); };
  mount();

  // farbe: 'ok' gruen, 'warn' orange, 'pause' grau (Reader per Prophos pausiert)
  function setBadge(text, farbe) {
    badge.textContent = text;
    badge.style.color = { ok: '#38d66b', warn: '#f0a020', pause: '#9aa4b2' }[farbe] || '#f0a020';
  }

  // --- Tick: lesen + senden ---
  // Auch pausiert wird weiter gesendet (billig, rein lokal) — der Server friert
  // den Stand ein und antwortet an:false; Wiedereinschalten greift so sofort.
  function tick() {
    const positionen = lesePositionen();
    const payload = JSON.stringify({ ts: Date.now(), positionen });

    GM_xmlhttpRequest({
      method: 'POST',
      url: ENDPOINT,
      headers: { 'Content-Type': 'application/json' },
      data: payload,
      timeout: 2500,
      onload: (r) => {
        let an = true;
        try { an = JSON.parse(r.responseText).an !== false; } catch (_) {}
        if (!an)             setBadge(`⏸ Reader pausiert (via Prophos)`, 'pause');
        else if (spracheFremd) setBadge('⚠ TradingView ist nicht auf Deutsch — Reader liest die deutschen Spalten. Profilmenü → Sprache → Deutsch, dann F5', 'warn');
        else                 setBadge(`● Reader · ${positionen.length} Pos · Copier ok`, 'ok');
      },
      onerror:   () => setBadge(`● Reader · ${positionen.length} Pos · Copier OFFLINE`, 'warn'),
      ontimeout: () => setBadge(`● Reader · ${positionen.length} Pos · Timeout`, 'warn'),
    });
  }

  setInterval(tick, INTERVALMS);
  tick();
})();
