// ==UserScript==
// @name         Prophos TV-Reader
// @namespace    prophos
// @version      0.3.1
// @description  Liest offene TradingView-Positionen live aus dem DOM und schickt sie an den lokalen Prophos-Empfaenger. Seit 0.3 zusaetzlich das BEDIENFELD (Konto-Umschalter, Symbol-Suche, Order-Ticket, Kaufen/Verkaufen) mit Bildschirm-Geometrie — die Augen fuer den Puls, der mit echter Maus klickt.
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
  const BEDIENFELD = 'http://127.0.0.1:8790/bedienfeld';
  const INTERVALMS = 250;    // wie oft gelesen + gesendet wird (0,25 s — niedrige Hedge-Latenz)
  const BF_JEDER   = 2;      // Bedienfeld nur jeden n-ten Tick (500 ms) — die
                             // Steuerelement-Suche geht durchs halbe DOM, das
                             // muss nicht im Hedge-Takt laufen. Puls wartet
                             // ohnehin auf einen Stand, der JUENGER ist als
                             // sein letzter Klick (Beweis statt Vermutung).

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

  /* ═════════════════════════════════════════════════════════════════════════
   * BEDIENFELD (0.3.0, 30.08.2026 — Orbit-Puls Schritt 2 „Order platzieren")
   *
   * Arbeitsteilung, bewusst so geschnitten:
   *   Userscript = AUGEN — findet die Steuerelemente im DOM und meldet ihre
   *                Rechtecke + den sichtbaren Text. Es klickt NICHTS.
   *   Puls       = HAENDE + KOPF — entscheidet (passt das Konto? das Symbol?)
   *                und klickt mit echter Maus (_klick_absolut).
   *
   * Warum nicht das Userscript selbst klicken lassen: ein element.click()
   * traegt isTrusted=false und ist damit als Automat markierbar. Die ganze
   * Puls-Doktrin (15.08.2026) ist „muss wie ein Handklick aussehen" — auf der
   * MT5-Seite wegen der Expert-Markierung, hier aus demselben Reflex. Der
   * Umweg ueber Bildschirm-Koordinaten kostet die Kalibrierung unten, kauft
   * dafuer echte Maus-Events.
   *
   * Rechtecke sind [x, y, breite, hoehe] in CSS-Pixeln RELATIV ZUM VIEWPORT.
   * Die Umrechnung in Bildschirm-Pixel macht Puls (tv_bildschirm_punkt) aus
   * geo{} + dem Fenster-Rechteck, das er selbst per UIA misst — der Browser
   * kennt seine eigene Fensterdekoration nicht zuverlaessig genug.
   * ═════════════════════════════════════════════════════════════════════════ */

  function sichtbar(el) {
    if (!el || !el.getBoundingClientRect) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 3 || r.height < 3) return false;
    // Ausserhalb des Viewports = fuer einen Maus-Klick nicht erreichbar
    if (r.bottom < 0 || r.right < 0 ||
        r.top > window.innerHeight || r.left > window.innerWidth) return false;
    const st = window.getComputedStyle(el);
    return st.visibility !== 'hidden' && st.display !== 'none' && st.opacity !== '0';
  }

  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  }

  function txt(el) {
    return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, ' ').trim();
  }

  function wert(el) {
    // Bei Eingabefeldern ist der INHALT der value, nicht der Text (gleiche
    // Lehre wie _feld_lesen im order_bot: window_text liefert dort das Label).
    if (!el) return '';
    if (typeof el.value === 'string') return el.value.trim();
    return txt(el);
  }

  /* Ein Steuerelement ueber MEHRERE unabhaengige Signaturen suchen — nie ueber
   * einen einzelnen String-Treffer (Lehre 18.08.2026, EA-Dialog-Fehlgriff).
   * Gewonnen hat die ERSTE Signatur, die GENAU EIN sichtbares Element liefert.
   * Mehrdeutige Signaturen werden uebersprungen, aber gemeldet — daran sieht
   * die Ferndiagnose, ob TV umgebaut wurde oder ob nur der Filter zu weit war. */
  function suche(sigs, wurzel) {
    const basis = wurzel || document;
    const notiz = [];
    for (const s of sigs) {
      let els;
      try {
        els = [...basis.querySelectorAll(s.sel)];
      } catch (_) { continue; }          // ungueltiger Selektor killt nie den Tick
      els = els.filter(sichtbar);
      if (s.text) els = els.filter((e) => s.text.test(txt(e)));
      if (s.nicht) els = els.filter((e) => !s.nicht.test(txt(e)));
      if (els.length === 1) {
        return { rect: rectOf(els[0]), text: txt(els[0]).slice(0, 80),
                 wert: wert(els[0]).slice(0, 40), quelle: s.q, notiz };
      }
      if (els.length > 1) notiz.push(`${s.q}: ${els.length} Treffer`);
    }
    return notiz.length ? { fehlt: true, notiz } : null;
  }

  /* Sammelsuche fuer Listen (Konto-Auswahl im offenen Dropdown): hier ist
   * MEHR als ein Treffer der Normalfall — Puls sucht sich den Eintrag mit der
   * External ID heraus. */
  function sucheAlle(sigs, wurzel) {
    const basis = wurzel || document;
    for (const s of sigs) {
      let els;
      try {
        els = [...basis.querySelectorAll(s.sel)];
      } catch (_) { continue; }
      els = els.filter(sichtbar).filter((e) => txt(e));
      if (els.length) {
        return els.slice(0, 40).map((e) => ({ rect: rectOf(e), text: txt(e).slice(0, 80), quelle: s.q }));
      }
    }
    return [];
  }

  // --- Signatur-Tabellen -----------------------------------------------------
  // Reihenfolge = Vertrauensreihenfolge: erst stabile data-name/id-Anker, dann
  // aria-Label, dann Text. Beim Haerten nach dem ersten PC-Lauf wird hier eine
  // Zeile ergaenzt — nichts anderes muss sich aendern.

  const SIG_SYMBOL_KNOPF = [
    { q: 'id:header-toolbar-symbol-search', sel: '#header-toolbar-symbol-search' },
    { q: 'data-name:symbol-search',         sel: '[data-name="symbol-search"]' },
    { q: 'aria:Symbol-Suche',               sel: 'button[aria-label*="ymbol"]' },
  ];
  const SIG_SUCHFELD = [
    { q: 'data-role:search',        sel: 'input[data-role="search"]' },
    { q: 'dialog>input',            sel: '[data-name="symbol-search-items-dialog"] input' },
    { q: 'aria:Suche',              sel: 'input[aria-label*="uch"], input[placeholder*="uch"]' },
  ];
  const SIG_KONTO_SCHALTER = [
    { q: 'data-name:account-select', sel: '[data-name="account-manager-account-select"]' },
    { q: 'data-name*account',        sel: '[data-name*="account"][role="button"], [data-name*="account"] button' },
    { q: 'class*accountSelect',      sel: '[class*="accountSelect"] button, button[class*="accountSelect"]' },
  ];
  const SIG_KONTO_EINTRAEGE = [
    { q: 'role:option',   sel: '[role="listbox"] [role="option"], [data-name="menu-inner"] [role="option"]' },
    { q: 'role:menuitem', sel: '[data-name="popup-menu-container"] [role="menuitem"]' },
    { q: 'menu-item',     sel: '[data-name="popup-menu-container"] [data-name="menu-item"]' },
  ];
  const SIG_TICKET = [
    { q: 'data-name:order-ticket', sel: '[data-name="order-ticket"]' },
    { q: 'dialog-name*order',      sel: '[data-dialog-name*="rder"]' },
    { q: 'role:dialog+Order',      sel: '[role="dialog"]', text: /order|kaufen|verkaufen|buy|sell/i },
  ];
  const SIG_PANEL_KAUFEN = [
    { q: 'data-name:buy-button', sel: '[data-name="buy-button"]' },
    { q: 'text:Kaufen',          sel: 'button, [role="button"]', text: /^(kaufen|buy)\b/i },
  ];
  const SIG_PANEL_VERKAUFEN = [
    { q: 'data-name:sell-button', sel: '[data-name="sell-button"]' },
    { q: 'text:Verkaufen',        sel: 'button, [role="button"]', text: /^(verkaufen|sell)\b/i },
  ];
  // Felder INNERHALB des Order-Tickets (Wurzel = Ticket-Element, deshalb duerfen
  // die Selektoren hier grob sein — der Kontext macht sie eindeutig).
  const SIG_MENGE = [
    { q: 'data-name:quantity', sel: '[data-name="quantity"] input, input[data-name="quantity"]' },
    { q: 'aria:Menge',         sel: 'input[aria-label*="eng"], input[aria-label*="uantit"], input[aria-label*="Qty"]' },
    { q: 'erstes input',       sel: 'input[type="text"], input[inputmode="numeric"]' },
  ];
  const SIG_TP_FELD = [
    { q: 'data-name:take-profit', sel: '[data-name*="take-profit"] input, [data-name*="takeProfit"] input' },
    { q: 'aria:TakeProfit',       sel: 'input[aria-label*="ake"], input[aria-label*="Gewinn"]' },
  ];
  const SIG_SL_FELD = [
    { q: 'data-name:stop-loss', sel: '[data-name*="stop-loss"] input, [data-name*="stopLoss"] input' },
    { q: 'aria:StopLoss',       sel: 'input[aria-label*="top"], input[aria-label*="erlust"]' },
  ];
  // Einheiten-Umschalter der Bracket-Felder (Ticks / Preis / % / Geld). Finn
  // gibt TP/SL in $ an — steht die Einheit auf Ticks, waere derselbe getippte
  // Wert eine voellig andere Distanz. Deshalb wird die Einheit MITGELESEN und
  // Puls bricht ab, wenn sie nicht auf Geld steht (statt still danebenzuliegen).
  const SIG_TP_EINHEIT = [
    { q: 'data-name:tp-unit', sel: '[data-name*="take-profit"] [role="button"], [data-name*="takeProfit"] [role="button"]' },
  ];
  const SIG_SL_EINHEIT = [
    { q: 'data-name:sl-unit', sel: '[data-name*="stop-loss"] [role="button"], [data-name*="stopLoss"] [role="button"]' },
  ];
  const SIG_TICKET_SENDEN = [
    { q: 'data-name:place-order', sel: '[data-name="place-order"], [data-name*="submit"]' },
    { q: 'text:Kaufen/Verkaufen', sel: 'button, [role="button"]', text: /^(kaufen|verkaufen|buy|sell)\b/i },
  ];

  /* Kandidaten-Dump fuer die Ferndiagnose — NUR auf Anforderung (der Server
   * antwortet dump:true, wenn Puls einen Fehlversuch hatte). Grund: der Dump
   * laeuft durchs ganze DOM und waere im 500-ms-Takt reine Verschwendung.
   * Zweck ist derselbe wie modus_inspect beim MT5-Puls: „Dump an Claude
   * schicken, daraus wird die Zuordnung gebaut" — nur eben fuer eine Webseite. */
  function dumpKandidaten() {
    const out = [];
    const sel = 'button,[role="button"],[role="option"],[role="menuitem"],input,[data-name],[data-dialog-name]';
    let els;
    try { els = [...document.querySelectorAll(sel)]; } catch (_) { return out; }
    for (const e of els) {
      if (out.length >= 150) break;
      if (!sichtbar(e)) continue;
      const t = txt(e).slice(0, 60);
      const dn = e.getAttribute('data-name') || e.getAttribute('data-dialog-name') || '';
      const al = e.getAttribute('aria-label') || '';
      if (!t && !dn && !al && e.tagName !== 'INPUT') continue;
      out.push({ tag: e.tagName.toLowerCase(), dn, al, rolle: e.getAttribute('role') || '',
                 text: t, wert: wert(e).slice(0, 30), rect: rectOf(e) });
    }
    return out;
  }

  let dumpAn = false;   // vom Server gesetzt (Antwort auf /bedienfeld)

  function liesBedienfeld() {
    const ticketTreffer = suche(SIG_TICKET);
    // Wurzel fuer die Ticket-Felder: das gefundene Ticket-Element selbst.
    // Ohne diese Einengung wuerden 'erstes input'-Signaturen irgendwo auf der
    // Seite zuschnappen — der Kontext IST hier die halbe Signatur.
    let ticketEl = null;
    if (ticketTreffer && ticketTreffer.rect) {
      for (const s of SIG_TICKET) {
        let c;
        try { c = [...document.querySelectorAll(s.sel)].filter(sichtbar); } catch (_) { continue; }
        if (s.text) c = c.filter((e) => s.text.test(txt(e)));
        if (c.length === 1) { ticketEl = c[0]; break; }
      }
    }

    const symbolKnopf = suche(SIG_SYMBOL_KNOPF);
    const kontoSchalter = suche(SIG_KONTO_SCHALTER);

    return {
      ts: Date.now(),
      // Seitentitel + Adresse (0.3.1, 30.08.2026): der Puls sucht den
      // TradingView-Tab in der Chrome-Tableiste. Bis .192 suchte er nach dem
      // Wort "tradingview" — an Finns PC steht im Tab aber nur
      // "NQU2026 29.491,75 ▼ −0,69 %", und er fand nichts. Statt zu raten,
      // sagt die Seite jetzt selbst, wie sie heisst; Puls nimmt daraus den
      // stabilen Teil (das erste Wort, also das Symbol) als Suchbegriff —
      // der Preis im Titel tickt sekuendlich, ein Volltext-Vergleich waere
      // also praktisch nie ein Treffer.
      titel: document.title || '',
      url: location.href || '',
      // Selbst-Kalibrierung: Puls rechnet CSS-Pixel in Bildschirm-Pixel um.
      // devicePixelRatio traegt in Chrome BEIDES — Windows-Skalierung und
      // Seiten-Zoom —, deshalb ist es der einzige noetige Faktor; die
      // Plausibilitaet prueft Puls gegen das gemessene Fenster-Rechteck.
      geo: {
        innerWidth: window.innerWidth, innerHeight: window.innerHeight,
        outerWidth: window.outerWidth, outerHeight: window.outerHeight,
        screenX: window.screenX, screenY: window.screenY,
        dpr: window.devicePixelRatio || 1,
      },
      sprache_fremd: spracheFremd,
      konto: {
        aktiv: kontoSchalter && kontoSchalter.text ? kontoSchalter.text : '',
        schalter: kontoSchalter,
        eintraege: sucheAlle(SIG_KONTO_EINTRAEGE),
      },
      symbol: {
        aktiv: symbolKnopf && symbolKnopf.text ? symbolKnopf.text : '',
        knopf: symbolKnopf,
        suchfeld: suche(SIG_SUCHFELD),
      },
      panel: {
        kaufen: suche(SIG_PANEL_KAUFEN),
        verkaufen: suche(SIG_PANEL_VERKAUFEN),
      },
      ticket: {
        offen: !!ticketEl,
        menge: ticketEl ? suche(SIG_MENGE, ticketEl) : null,
        tp: ticketEl ? suche(SIG_TP_FELD, ticketEl) : null,
        sl: ticketEl ? suche(SIG_SL_FELD, ticketEl) : null,
        tp_einheit: ticketEl ? suche(SIG_TP_EINHEIT, ticketEl) : null,
        sl_einheit: ticketEl ? suche(SIG_SL_EINHEIT, ticketEl) : null,
        senden: ticketEl ? suche(SIG_TICKET_SENDEN, ticketEl) : null,
      },
      dump: dumpAn ? dumpKandidaten() : null,
    };
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
  let tickNr = 0;

  function sendeBedienfeld() {
    let bf;
    try {
      bf = liesBedienfeld();
    } catch (e) {
      // Die Steuerelement-Suche darf den Positions-Reader NIE mitreissen —
      // der Hedge haengt am Positions-Strom, das Bedienfeld nur am Puls.
      bf = { ts: Date.now(), fehler: String((e && e.message) || e) };
    }
    GM_xmlhttpRequest({
      method: 'POST', url: BEDIENFELD,
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify(bf), timeout: 2500,
      onload: (r) => {
        try { dumpAn = JSON.parse(r.responseText).dump === true; } catch (_) { dumpAn = false; }
      },
      onerror: () => {},      // alter reader-server ohne /bedienfeld: still ignorieren
      ontimeout: () => {},
    });
  }

  function tick() {
    const positionen = lesePositionen();
    const payload = JSON.stringify({ ts: Date.now(), positionen });

    if ((tickNr++ % BF_JEDER) === 0) sendeBedienfeld();

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
