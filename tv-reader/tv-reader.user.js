// ==UserScript==
// @name         Prophos TV-Reader
// @namespace    prophos
// @version      0.4.0
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

  // Version doppelt: einmal im @version-Kopf fuer Tampermonkey, einmal hier
  // fuer die Ferndiagnose. Klingt redundant, ist es nicht -- an Finns PC wurde
  // dreimal ein Update vermutet, das gar nicht aktiv war (31.08.2026), und von
  // aussen war das nur an FEHLENDEN Feldern zu erraten. Ab jetzt sagt jeder
  // Bedienfeld-Abruf, welcher Stand wirklich laeuft.
  const VERSION    = '0.4.0';
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
  let spaltenGesehen = [];      // fuer die Ferndiagnose: was die Tabelle WIRKLICH anbietet
  // Was der letzte Lesevorgang WIRKLICH vorgefunden hat (0.4.0) — Grundlage
  // fuer die Blind-Entscheidung in tick(). zeilen/zellen/tabelle statt eines
  // blossen "0 Positionen".
  let leseBefund = { zeilen: 0, zellen: 0, tabelle: false };

  /* Spaltentitel sind NICHT stabil (Fund 31.08.2026 an Finns PC): die Tabelle
   * hiess auf Deutsch mal "Menge / Durchschn. Ausfuehrungspreis /
   * Unrealisierter G&V" und heisst jetzt "Anz. / Durchschnittlicher
   * Erfuellungspreis / Profit". Der Reader hat deshalb 0 Positionen gemeldet,
   * waehrend 3 Kontrakte short offen waren -- und "0 Positionen" ist die
   * gefaehrlichste Falschaussage, die dieser Reader treffen kann.
   *
   * Deshalb ab 0.3.4: pro Feld eine LISTE moeglicher Titel, erster Treffer
   * gewinnt. Neue Schreibweisen kosten hier eine Zeile statt eines Ausfalls.
   * Englisch steht bewusst mit drin -- lieber lesen wir die Position auch auf
   * Englisch, als sie zu uebersehen; die Sprachwarnung bleibt trotzdem, weil
   * der Verbinder deutsche ZAHLEN parst. */
  const SPALTEN = {
    symbol:   ['Symbol'],
    seite:    ['Seite', 'Side'],
    menge:    ['Menge', 'Anz.', 'Anzahl', 'Qty', 'Quantity'],
    einstieg: ['Durchschn. Ausführungspreis', 'Durchschnittlicher Erfüllungspreis',
               'Ø Ausführungspreis', 'Avg Fill Price'],
    pnl:      ['Unrealisierter G&V', 'Profit', 'Unrealized P&L', 'P&L'],
    sl:       ['Stop Loss', 'Stop-Loss'],
    tp:       ['Take Profit', 'Take-Profit'],
  };

  function feld(zeile, namen) {
    for (const n of namen) {
      const v = zeile[n];
      if (v !== undefined && v !== null && String(v).trim() !== '') return String(v).trim();
    }
    return null;
  }

  /* Zellen-Text OHNE Layout (0.4.0, 01.09.2026 — der Tabwechsel-Fund).
   * Bis 0.3.7 stand hier td.innerText. innerText ist der GERENDERTE Text: er
   * braucht ein aktuelles Layout und liefert fuer uebersprungene Teilbaeume
   * (content-visibility) einen LEEREN String. Genau das passiert, sobald der
   * TradingView-Tab in den Hintergrund geht — Chrome haelt Rendering und
   * Layout des verdeckten Tabs an. Die Zeilen standen also weiter im DOM,
   * aber jede Zelle kam leer zurueck, der Filter unten warf sie raus, und der
   * Reader meldete mit FRISCHEM Zeitstempel "0 Positionen". Ein frisches
   * "flat" ist fuer die ganze Kette ein Beweis: der Verbinder friert nicht
   * ein (die Daten sind ja frisch!), und der Copier schliesst den Hedge.
   * Beim naechsten Tick war die Zelle wieder lesbar -> Hedge wieder auf.
   * Das war Finns Sekundentakt-Flattern vom 01.09.2026.
   * textContent haengt an keinem Layout und liest im verdeckten Tab genauso
   * wie im sichtbaren. Die Umbruch-Normalisierung unten macht ohnehin schon
   * das, wofuer innerText hier ueberhaupt gebraucht wurde. */
  function zellText(td) {
    return (td.textContent || '').replace(/\s+/g, ' ').trim();
  }

  /* Beweis, dass die Positionstabelle ueberhaupt DA ist (0.4.0).
   * Wichtig, weil "keine Zeilen" zwei voellig verschiedene Dinge heissen kann:
   *   · Konto ist flach          -> echte Aussage, Hedge MUSS zugehen
   *   · Panel weg/zugeklappt/leer -> Unwissen, Hedge MUSS stehenbleiben
   * Ohne diesen Anker kann der Reader die beiden nicht auseinanderhalten —
   * und "0 Positionen" ist die gefaehrlichste Falschaussage, die er treffen
   * kann. Anker ist das Broker-Panel (der Konto-Umschalter aus Finns Dump
   * vom 31.08.2026 lebt darin); zusaetzlich zaehlen sichtbare Datenzeilen
   * selbst als Beweis. */
  function tabelleDa() {
    const anker = [
      '[data-name="account-manager-account-select"]',
      '[data-name^="account-manager"]',
      '[class*="accountManager"]',
    ];
    for (const s of anker) {
      try { if (document.querySelector(s)) return true; } catch (_) {}
    }
    return document.querySelector('td[data-label]') !== null;
  }

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
      rows.get(tr)[label] = zellText(td);
    });
    spaltenGesehen = [...labels];
    // Englisch erkennen an einem Titel, den es auf Deutsch NICHT gibt. "Profit"
    // taugt dafuer nicht — das Wort steht in beiden Sprachen so da.
    spracheFremd = labels.has('Unrealized P&L') || labels.has('Avg Fill Price');
    // Zeilen da, aber ALLE Zellen leer = gelesen, nichts verstanden (0.4.0).
    // Das ist Unwissen, keine Flachstellung — siehe zellText().
    let zellen = 0;
    for (const r of rows.values()) {
      for (const k in r) if (r[k]) zellen++;
    }
    leseBefund = { zeilen: rows.size, zellen: zellen, tabelle: tabelleDa() };
    // Eine Zeile ist eine offene Position, wenn sie Symbol UND einen G&V-Wert
    // traegt. Order-Verlauf-Zeilen (mit 'Order-ID'/'Status') fallen so raus.
    return [...rows.values()]
      .map((r) => ({
        symbol:   feld(r, SPALTEN.symbol),
        seite:    feld(r, SPALTEN.seite),
        menge:    feld(r, SPALTEN.menge),
        einstieg: feld(r, SPALTEN.einstieg),
        sl:       feld(r, SPALTEN.sl),
        tp:       feld(r, SPALTEN.tp),
        pnl:      feld(r, SPALTEN.pnl),
      }))
      .filter((p) => p.symbol && p.pnl !== null);
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

  /* ECHTE Anker, aus Finns Panel-Dump vom 31.08.2026 gelesen -- bis 0.3.4
   * standen hier Vermutungen. Die geratenen Signaturen bleiben als zweite
   * Reihe stehen: faellt TradingView eine Umbenennung ein, greift der Text-Weg
   * weiter, und der Dump sagt, was sich geaendert hat. */
  const SIG_SYMBOL_KNOPF = [
    { q: 'id:header-toolbar-symbol-search', sel: '#header-toolbar-symbol-search' },
    { q: 'aria:Symbol aendern',             sel: 'button[aria-label^="Symbol"]' },
  ];
  const SIG_SUCHFELD = [
    { q: 'data-role:search',        sel: 'input[data-role="search"]' },
    { q: 'dialog>input',            sel: '[data-name="symbol-search-items-dialog"] input' },
    { q: 'aria/placeholder:Suche',  sel: 'input[aria-label*="uch"], input[placeholder*="uch"]' },
  ];
  const SIG_KONTO_SCHALTER = [
    { q: 'data-name:account-select', sel: '[data-name="account-manager-account-select"]' },
    { q: 'data-name*account',        sel: '[data-name*="account"][role="button"], [data-name*="account"] button' },
  ];
  const SIG_KONTO_EINTRAEGE = [
    { q: 'role:option',   sel: '[role="listbox"] [role="option"], [data-name="menu-inner"] [role="option"]' },
    { q: 'role:menuitem', sel: '[data-name="popup-menu-container"] [role="menuitem"]' },
  ];
  // Das "Ticket" ist bei TradingView kein Dialog, sondern das fest angedockte
  // Handelspanel rechts. Ist der Trade-Bereich zugeklappt, gibt es das Element
  // nicht -- dann meldet Puls genau das, statt irgendwo hinzuklicken.
  const SIG_TICKET = [
    { q: 'data-name:order-panel', sel: '[data-name="order-panel"]' },
  ];
  const SIG_PANEL_KAUFEN = [
    { q: 'data-name:side-control-buy',  sel: '[data-name="side-control-buy"]' },
  ];
  const SIG_PANEL_VERKAUFEN = [
    { q: 'data-name:side-control-sell', sel: '[data-name="side-control-sell"]' },
  ];
  const SIG_MARKT_REITER = [
    { q: 'id:Market', sel: '#Market' },
    { q: 'tab:Markt', sel: '[role="tab"]', text: /^(markt|market)$/i },
  ];
  const SIG_MENGE = [
    { q: 'id:quantity-field', sel: '#quantity-field' },
    { q: 'aria:Menge',        sel: 'input[aria-label*="eng"], input[aria-label*="uantit"]' },
  ];
  // Der Senden-Knopf traegt Richtung, Menge, Symbol und Orderart IM TEXT
  // ("Kauf 3 NQU6 MARKT"). Das ist die beste Ruecklese-Probe im ganzen Ablauf:
  // Puls prueft den Text, bevor er den unumkehrbaren Klick macht.
  const SIG_TICKET_SENDEN = [
    { q: 'data-name:place-and-modify-button', sel: '[data-name="place-and-modify-button"]' },
  ];
  // TP/SL: die Schalter tragen den Text "Take Profit, $" / "Stop-Loss, $", die
  // Wertfelder daneben haben WEDER id NOCH data-name -- sie sind nur ueber
  // ihre Lage im Panel zu finden. Deshalb bleibt SL/TP eine eigene Stufe;
  // gemeldet wird hier nur, ob die Schalter da sind.
  const SIG_TP_SCHALTER = [
    { q: 'text:TakeProfit', sel: '[data-name="order-panel"] button', text: /take\s*profit/i },
  ];
  const SIG_SL_SCHALTER = [
    { q: 'text:StopLoss',   sel: '[data-name="order-panel"] button', text: /stop[-\s]?loss/i },
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
      out.push({ tag: e.tagName.toLowerCase(), id: e.id || '', dn, al,
                 rolle: e.getAttribute('role') || '',
                 text: t, wert: wert(e).slice(0, 30), rect: rectOf(e) });
    }
    return out;
  }

  let dumpAn = false;   // vom Server gesetzt (Antwort auf /bedienfeld) -> VOLLER Dump

  /* Kompakt-Dump, IMMER dabei (0.3.2, 31.08.2026). Vorher gab es den Dump nur
   * auf Anforderung: Server setzt ein Flag, das Userscript liefert beim
   * UEBERNAECHSTEN Tick. Genau daran ist Finn zweimal gescheitert -- ist der
   * TradingView-Tab verdeckt, drosselt Chrome auf einen Lauf pro Minute, und
   * der Hin- und Rueckweg dauert dann Minuten statt Sekunden. Jetzt liegt der
   * Dump immer schon beim Server, auch wenn der Tab seit einer Weile
   * eingefroren ist -- ein Abruf genuegt, ohne Timing und ohne Tabwechsel.
   * Begrenzt auf die zwei Zonen, um die es geht: obere Werkzeugleiste
   * (Symbol-Suche), rechte Spalte (Order-Panel) und unterer Bereich
   * (Broker-Panel mit Konto-Umschalter und Positionstabelle).
   * Seit 0.3.3 auch die element-id: bei TradingView ist sie der stabilste
   * Anker (header-toolbar-symbol-search &c.), und mehrere Knoepfe der
   * Werkzeugleiste tragen ueberhaupt kein data-name. */
  function dumpKompakt() {
    const out = [];
    const grenzeX = window.innerWidth * 0.6;
    // Unterer Bereich = das Broker-Panel (Tradovate) mit dem KONTO-Umschalter.
    // Fehlte bis 0.3.5 und war damit der tote Winkel, der Puls am Konto-Schritt
    // scheitern liess: er meldete "Konto steht auf '?'" -- nicht weil das Konto
    // falsch war, sondern weil er es nicht LESEN konnte (Finns Lauf 31.08.2026).
    const grenzeY = window.innerHeight * 0.6;
    let els;
    try {
      els = [...document.querySelectorAll(
        'button,[role="button"],[role="option"],[role="tab"],input,select,[data-name]')];
    } catch (_) { return out; }
    for (const e of els) {
      if (out.length >= 130) break;
      if (!sichtbar(e)) continue;
      const r = e.getBoundingClientRect();
      if (!(r.top < 70 || r.left > grenzeX || r.top > grenzeY)) continue;
      const t = txt(e).slice(0, 45);
      const dn = e.getAttribute('data-name') || '';
      const al = e.getAttribute('aria-label') || '';
      if (!t && !dn && !al && e.tagName !== 'INPUT') continue;
      out.push({ tag: e.tagName.toLowerCase(), id: e.id || '', dn, al,
                 rolle: e.getAttribute('role') || '',
                 text: t, wert: wert(e).slice(0, 24), rect: rectOf(e) });
    }
    return out;
  }

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
      version: VERSION,
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
      // Was die Positionstabelle WIRKLICH an Spalten anbietet. Genau diese
      // Liste haette den Blind-Fall vom 31.08.2026 sofort erklaert.
      spalten: spaltenGesehen,
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
        markt: ticketEl ? suche(SIG_MARKT_REITER) : null,   // Reiter liegt ausserhalb des Panels
        menge: ticketEl ? suche(SIG_MENGE, ticketEl) : null,
        senden: ticketEl ? suche(SIG_TICKET_SENDEN, ticketEl) : null,
        tp_schalter: ticketEl ? suche(SIG_TP_SCHALTER) : null,
        sl_schalter: ticketEl ? suche(SIG_SL_SCHALTER) : null,
      },
      dump: dumpAn ? dumpKandidaten() : null,   // voll, nur auf Anforderung
      panel: dumpKompakt(),                     // Werkzeugleiste + rechte Spalte, immer
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

  /* Blind-Pruefung (0.4.0, 01.09.2026). Gibt den GRUND zurueck, warum dieser
   * Lesevorgang nicht als Aussage taugt — oder null, wenn er es tut.
   *
   * Die Regel dahinter ist dieselbe wie ueberall in Prophos ("Beweis oder
   * leer"), nur an der einen Stelle, an der sie bisher fehlte: der Reader
   * durfte "0 Positionen" sagen, ohne zu wissen, ob er die Tabelle ueberhaupt
   * gesehen hat. Der Server nimmt einen blinden Stand nicht an, der Stand
   * friert ein, und die Frische-Doktrin des Verbinders haelt den Hedge —
   * stale != flat. Ein blinder Reader schliesst nie einen Hedge.
   *
   * WICHTIG: nur der LEERE Fall wird blockiert. Sieht der Reader Positionen,
   * gehen sie durch — auch bei zugeklapptem Panel. Und ist die Tabelle
   * nachweislich da und wirklich leer, ist das eine echte Flachstellung und
   * der Hedge geht zu wie bisher. */
  function blindGrund(positionen) {
    if (positionen.length) return null;                  // Positionen = Beweis genug
    if (!leseBefund.tabelle) return 'Positionstabelle nicht auffindbar (Panel zu?)';
    if (leseBefund.zeilen && !leseBefund.zellen) return 'Tabellenzellen kamen leer zurueck';
    return null;                                          // Tabelle da, wirklich flach
  }

  function tick() {
    const positionen = lesePositionen();
    const blind = blindGrund(positionen);
    // Auch blind wird GESENDET — der Server soll den Grund kennen (und die
    // Orbit-Karte spaeter auch). Er uebernimmt den Stand dann nur nicht.
    const payload = JSON.stringify({
      ts: Date.now(), positionen, version: VERSION,
      blind: !!blind, blind_grund: blind || '',
      sichtbar: document.visibilityState === 'visible',
    });

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
        else if (blind)      setBadge(`⚠ Reader blind: ${blind} — Stand eingefroren, Hedge bleibt stehen`, 'warn');
        else if (spracheFremd) setBadge('⚠ TradingView ist nicht auf Deutsch — Reader liest die deutschen Spalten. Profilmenü → Sprache → Deutsch, dann F5', 'warn');
        else                 setBadge(`● Reader · ${positionen.length} Pos · Copier ok`, 'ok');
      },
      onerror:   () => setBadge(`● Reader · ${positionen.length} Pos · Copier OFFLINE`, 'warn'),
      ontimeout: () => setBadge(`● Reader · ${positionen.length} Pos · Timeout`, 'warn'),
    });
  }

  /* Takt aus einem Web Worker (0.4.0, 01.09.2026 — zweite Haelfte des
   * Tabwechsel-Funds). setInterval im Seiten-Kontext wird von Chrome gedrosselt,
   * sobald der Tab verdeckt ist: erst auf 1 Lauf/Sekunde, nach 5 Minuten auf
   * 1 Lauf/MINUTE. Mit dem 10-s-Frischefenster des Verbinders heisst das:
   * Orbit steht 50 von 60 Sekunden eingefroren, nur weil Finn in Prophos
   * schaut. Timer in einem eigenen Worker unterliegen dieser Drosselung nicht;
   * der Worker schickt nur einen Weckruf, gelesen und gesendet wird weiter im
   * Seiten-Kontext (GM_xmlhttpRequest gibt es nur dort).
   *
   * Faellt der Worker aus (TradingView-CSP verbietet blob:-Worker), bleibt es
   * beim gedrosselten setInterval — langsamer, aber durch die Blind-/Frische-
   * Regeln oben weiterhin sicher. Deshalb Fallback statt Abbruch. */
  function starteTakt() {
    try {
      const quelle = `let id=null;onmessage=e=>{if(id)clearInterval(id);` +
                     `id=setInterval(()=>postMessage(0),e.data)}`;
      const w = new Worker(URL.createObjectURL(new Blob([quelle], { type: 'text/javascript' })));
      w.onmessage = tick;
      w.postMessage(INTERVALMS);
      return 'worker';
    } catch (_) {
      setInterval(tick, INTERVALMS);
      return 'interval';
    }
  }

  starteTakt();
  tick();
})();
