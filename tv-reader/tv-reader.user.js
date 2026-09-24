// ==UserScript==
// @name         Prophos TV-Reader
// @namespace    prophos
// @version      0.8.2
// @description  Liest offene TradingView-Positionen live aus dem DOM und schickt sie an den lokalen Prophos-Empfaenger. Seit 0.3 zusaetzlich das BEDIENFELD (Konto-Umschalter, Symbol-Suche, Order-Ticket, Kaufen/Verkaufen) mit Bildschirm-Geometrie — die Augen fuer den Puls, der mit echter Maus klickt. Seit 0.5 auch die KONTO-ZUSAMMENFASSUNG (Balance, Today's P&L …) fuer den Orbit-V2-Rundgang.
// @match        https://*.tradingview.com/*
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-start
// @updateURL    https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/tv-reader.user.js
// @downloadURL  https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/tv-reader.user.js
// ==/UserScript==

// Warum GM_xmlhttpRequest statt fetch: umgeht CORS/Mixed-Content sauber
// (HTTPS-Seite -> http://127.0.0.1). Ist die Standard-Zapfstelle fuer
// Userscripts, die mit einem lokalen Prozess reden.
//
// Seit 24.09.2026 optional (Finn: „Nein — alles ohne Tampermonkey-Script,
// wenn es geht"): Bot liest per UIA, das Script beschleunigt nur (Reader-
// Stand < 1 s statt UIA-Scan ~1–2 s). Rundgang (tvlesen) und Schliessen
// (tvclose) laufen ohne Reader vollstaendig ueber die Windows-UI-Automation;
// ist der Reader da und >= 0.5.0, bleibt er die bevorzugte Quelle. Update
// kommt ueber @updateURL/@downloadURL (GitHub-raw) von selbst.
//
// CHANGELOG (Kurzform, Details an den Stellen im Code):
//   0.8.2  25.09.2026  Serien-Zaehler nach Ursache getrennt (Moritz' PC: 'unbek 366' bei 'Serien 3' — ein
//                      Zaehler je Bar sagte nicht, WELCHE Serie): fremd (Symbol bekannt, weder NQ noch MNQ),
//                      unaufgeloest (Send gehoert, Symbol-Id noch ohne Klartext — wird nachgezogen, sobald
//                      symbol_resolved kommt) und unbekannt (kein Send, kein Rueckfall) — je Serie, nicht je Bar
//   0.8.1  25.09.2026  Kurs-ts = EMPFANGSZEIT (Moritz' PC: reader_ts hinkte 0–60 s, weil lp_time nur minuten-
//                      genau kommt → Markt-Kopf/Hedge-Waechter hielten den laufenden Feed fuer tot); lp_time
//                      bleibt als lp_time/lp_time_ms daneben. Serien-Rueckfall, wenn die Sends vor dem Wrapper
//                      liefen: genau ein aufgeloestes Symbol → Tab-Titel-Symbol → einzige qsd-Wurzel.
//   0.8.0  24.09.2026  TradingViews EIGENE WebSocket-Verbindung passiv mitgehoert (document-start, unsafeWindow):
//                      Kurse (qsd: lp/bid/ask/lp_time) und Minutenkerzen (timescale_update/du) fuer NQ + MNQ —
//                      laeuft auch im verdeckten Tab; POST /kerzen; feed-Nachweis im Bedienfeld; Legende/Titel
//                      bleiben Rueckfall; Reload nur, wenn KEIN Frame mehr kommt (auch kein Herzschlag)
//   0.7.0  24.09.2026  BEIDE Kurse NQ + MNQ aus den Legenden-Knöpfen (Sell/Buy = Bid/Ask) je Chart-Pane,
//                      Tab-Titel nur Rückfall; Stale-Wächter + Selbstheilung per Reload (kurse, stale, reload_grund)
//   0.6.0  24.09.2026  Live-Kurs aus dem Tab-Titel (kurs) im Positions-Strom — Winning-Day-Gegenhedge auf Fusion
//   0.5.2  24.09.2026  Sprache egal: Englisch wird gelesen statt gewarnt (Verbinder parst beide Zahlformate)
//   0.5.1  24.09.2026  Zusammenfassung robuster: Label/Wert in getrennten Divs
//                      derselben Elternebene (auch mit Icon dazwischen), Werte
//                      wie „−1,234.50 USD“, „-1.234,50 $“, „USD 1,234.50“,
//                      „(12.50)“. Vollumstieg „Ohne Hedge“ (Rundgang + tvclose).
//   0.5.0  24.09.2026  Konto-Zusammenfassung (summary + today_pnl_text) im
//                      Bedienfeld — Orbit-V2-Rundgang: Puls liest, ob die
//                      Position noch offen ist, und nach dem Ende „Today's P&L".
//                      Das exakte Label kennt erst der erste Live-Lauf: im
//                      Bedienfeld-Dump unter 'summary' nachsehen, wie es
//                      wirklich heisst, dann NUR TODAY_PNL_LABELS anpassen.
//   0.4.2  21.09.2026  Text-Suche auf Anforderung (treffer) — Konto-IDs im DOM.
//   0.4.1  01.09.2026  Verdeckter Tab darf nie auf „flach" wechseln.
//   0.4.0  01.09.2026  textContent statt innerText, Blind-Pruefung, Worker-Takt.
//   0.3.x  30./31.08.  Bedienfeld, Kompakt-Dump, Spaltentitel-Listen.

(function () {
  'use strict';

  // Version doppelt: einmal im @version-Kopf fuer Tampermonkey, einmal hier
  // fuer die Ferndiagnose. Klingt redundant, ist es nicht -- an Finns PC wurde
  // dreimal ein Update vermutet, das gar nicht aktiv war (31.08.2026), und von
  // aussen war das nur an FEHLENDEN Feldern zu erraten. Ab jetzt sagt jeder
  // Bedienfeld-Abruf, welcher Stand wirklich laeuft.
  const VERSION    = '0.8.2';
  const ENDPOINT   = 'http://127.0.0.1:8790/positions';
  const BEDIENFELD = 'http://127.0.0.1:8790/bedienfeld';
  const KERZEN     = 'http://127.0.0.1:8790/kerzen';       // 0.8.0: Bars aus dem Socket, gebuendelt
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
  // Sprache egal (0.5.2, 24.09.2026, Finn: „stell ein, dass es egal ist, ob es auf Deutsch ist"):
  // die Spaltentitel stehen deutsch UND englisch in SPALTEN, und der Verbinder
  // (tv_snapshot.parse_de_zahl) wie der Puls (tv_zahl_lesen) lesen beide
  // Zahlformate ('29.618,25' und '29,618.25'). Englisch wird weiter ERKANNT
  // (spracheFremd, fuer die Ferndiagnose im Payload), aber nicht mehr gewarnt.
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

  /* Text-Suche auf Anforderung (0.4.2, 21.09.2026 — Futures-Puls Schritt 2).
   * Der Puls nennt ueber den Server Texte (die External IDs der Konten), hier
   * werden sie im GANZEN DOM gesucht und mit Rechteck zurueckgemeldet.
   * Warum: Finns erster Lauf am 21.09. — der Konto-Umschalter stand sichtbar
   * im Panel, beide data-name-Signaturen hatten null Treffer (TradingView hat
   * umbenannt), und die Aufklappliste haengt am ENDE des DOM, hinter der
   * 130er-Kappung von dumpKompakt. Eine 17-stellige Kontonummer ist dagegen
   * ein Anker, der UNS gehoert: TradingView kann ihn nicht umbenennen.
   * Verglichen wird nur-alphanumerisch (wie _nur_alnum im Puls), gesucht ueber
   * TEXTKNOTEN — das liefert von selbst das innerste Element statt aller
   * Huellen. Nur solange der Server Texte mitschickt (90 s), nie im
   * Dauerbetrieb. Geklickt wird auch hier NIE — das bleibt die echte Maus. */
  let suchTexte = [];
  const nurAlnum = (x) => String(x == null ? '' : x).replace(/[^a-z0-9]/gi, '').toUpperCase();

  function sucheTexte() {
    const nadeln = suchTexte.map(nurAlnum).filter((n) => n.length >= 3);
    const out = [];
    if (!nadeln.length || !document.body) return out;
    const gesehen = new Set();
    const lauf = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let knoten;
    while ((knoten = lauf.nextNode()) && out.length < 40) {
      const roh = knoten.nodeValue;
      if (!roh || roh.length < 3) continue;
      const norm = nurAlnum(roh);
      if (norm.length < 3 || !nadeln.some((n) => norm.includes(n))) continue;
      const el = knoten.parentElement;
      if (!el || gesehen.has(el) || !sichtbar(el)) continue;
      if (el.closest('script,style,noscript')) continue;
      gesehen.add(el);
      const rolle = el.closest('[role]');
      out.push({
        rect: rectOf(el), text: txt(el).slice(0, 80),
        rolle: rolle ? (rolle.getAttribute('role') || '') : '',
        // Liegt der Treffer in einer Aufklappliste? Der Puls unterscheidet
        // daran nicht hart (die Rollen koennen sich aendern wie die
        // data-names), aber die Ferndiagnose sieht es sofort.
        liste: !!el.closest('[role="listbox"],[role="menu"],[data-name="menu-inner"],[data-name="popup-menu-container"]'),
      });
    }
    return out;
  }

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

  /* ═════════════════════════════════════════════════════════════════════════
   * KONTO-ZUSAMMENFASSUNG (0.5.0, 24.09.2026 — Orbit-V2-Rundgang)
   *
   * Finn: „Der Bot geht sich in einem gewissen Intervall automatisch in das
   * Konto bei Tradovate auf TradingView, genauso wie man einen Trade startet.
   * Er liest, ob die Position noch offen ist oder schon beendet. Ist sie
   * beendet, kann man bei Today's P&L sehen, wie viel sich bewegt hat, weil
   * man immer nur eine Position pro Tag macht."
   *
   * Der exakte DOM der Zusammenfassung (die Leiste bzw. der Reiter im Account
   * Manager mit Balance / Realized P&L / Unrealized P&L …) ist beim Bau NICHT
   * bekannt — Tradovate-in-TradingView war auf keinem Mac zu sehen. Deshalb
   * bewusst GENERISCH, wie beim Spaltentitel-Fund vom 31.08.2026: alle
   * Label→Wert-Paare im Bereich des Account Managers einsammeln, deutsch wie
   * englisch, und als 'summary' mitschicken. Zwei Wege, beide ueber
   * textContent (nie innerText — der Tabwechsel-Fund vom 01.09.2026 gilt hier
   * genauso, der Rundgang laeuft ja gerade, WEIL der Tab oft hinten liegt):
   *   (a) ka-table-Zeilen OHNE Symbol-/Seite-Spalte: so sieht der Reiter
   *       „Account Summary" aus, wenn er offen ist (td[data-label] wie die
   *       Positionstabelle, nur ohne Positionen);
   *   (b) Blatt-Elemente mit Text-Label und einem BENACHBARTEN Zahlen-Text
   *       (naechstes/vorheriges Geschwister, Geschwister des Elternteils) im
   *       Account-Manager-Panel — so sehen die kleinen Kacheln in der Leiste
   *       aus. Plus „Label: Wert" in einem Element.
   * Gekappt auf SUMMARY_MAX Paare, erster Treffer je Label gewinnt.
   *
   * 'today_pnl_text' ist der Wert des ERSTEN Labels aus TODAY_PNL_LABELS, das
   * als Teilstring (ohne Gross/Klein) in einem Summary-Label steckt. Riegel:
   * Labels mit „unreal…"/„nicht real…" zaehlen nie — „Unrealized P&L" enthaelt
   * „Realized P&L" als Teilstring, und der offene G&V ist genau NICHT das
   * Tagesergebnis. Nach dem ersten Live-Lauf steht im Dump, wie das Label bei
   * Tradovate wirklich heisst — dann nur die Liste anpassen, sonst nichts.
   * ═════════════════════════════════════════════════════════════════════════ */
  const TODAY_PNL_LABELS = ["Today's P&L", "Today's Realized P&L", "Realized P&L",
                            "Heutiger G&V", "Heutiger realisierter G&V", "Realisierter G&V",
                            "Tages-G&V", "Realisiert"];
  const RX_NICHT_TODAY = /unreal|nicht\s*real|offen/i;     // offener/unrealisierter G&V ist nie das Tagesergebnis
  const SUMMARY_MAX = 40;
  // Zahlen-Text: Vorzeichen (auch U+2212 „−" wie im TV-Titel), Waehrung vorn
  // oder hinten, Tausender-/Dezimalzeichen deutsch wie englisch, Prozent.
  // 0.5.1: zusaetzlich Waehrungswort VORN („USD 1,234.50“, „USD -12.50“) und Buchhalter-
  // Klammern („(12.50)“, „(1.234,50 $)“) — Tradovates Kopfzeile „Balance · Realized P&L ·
  // Unrealized P&L“ schreibt je nach Einstellung so. Das Vorzeichen bleibt im Text; der
  // Puls liest es (tv_geld_lesen: U+2212, Gedankenstrich, Klammer-Minus).
  const RX_WERT  = /^\(?\s*[+\-−–]?\s*(?:[$€£]|USD|EUR|GBP|CHF)?\s*[+\-−–]?\d[\d.,\s\u00a0']*\s*(?:%|USD|EUR|GBP|CHF|\$|€|£)?\s*\)?$/;
  const RX_LABEL = /[A-Za-zÄÖÜäöüß]/;

  function textKurz(el) {
    return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
  }
  function istWert(t) {
    return t.length >= 1 && t.length <= 24 && /\d/.test(t) && RX_WERT.test(t);
  }
  function istLabel(t) {
    // Kein Konto-/Ordernummern-Text (4+ Ziffern), kein Satz, kein Leerstring
    return t.length >= 2 && t.length <= 40 && RX_LABEL.test(t) && !/\d{4,}/.test(t);
  }

  /* Wurzel des Account Managers: vom stabilsten Anker aus hochklettern, bis
   * ein Vorfahr breit und hoch genug ist, um das ganze Panel zu sein. Ohne
   * Layout (verdeckter Tab -> alle Rechtecke 0) fuenf Stufen blind hoch — das
   * Panel ist nie der Anker selbst, und textContent liest auch ohne Layout. */
  function kontoManagerWurzel() {
    const anker = [
      '[data-name="account-manager"]',
      '[data-name="account-manager-account-select"]',
      '[data-name^="account-manager"]',
      '[class*="accountManager"]',
      'td[data-label]',
    ];
    let el = null;
    for (const s of anker) {
      try { el = document.querySelector(s); } catch (_) { el = null; }
      if (el) break;
    }
    if (!el) return null;
    const r0 = el.getBoundingClientRect();
    let w = el, stufen = 0;
    if (!r0.width && !r0.height) {
      while (w.parentElement && w.parentElement !== document.body && stufen < 5) { w = w.parentElement; stufen++; }
      return w;
    }
    while (w && w !== document.body && stufen < 12) {
      const r = w.getBoundingClientRect();
      if (r.height >= 120 && r.width >= window.innerWidth * 0.4) return w;
      w = w.parentElement; stufen++;
    }
    return el.parentElement || el;
  }

  function liesZusammenfassung() {
    const paare = {};
    let n = 0;
    const setze = (label, wert) => {
      label = String(label || '').replace(/[:\s]+$/, '').trim();
      wert = String(wert || '').trim();
      if (!label || !wert || paare[label] !== undefined || n >= SUMMARY_MAX) return;
      paare[label] = wert;
      n++;
    };

    // (a) Tabellenzeilen ohne Symbol/Seite = Konto-Zusammenfassung als ka-table
    const zeilen = new Map();
    document.querySelectorAll('td[data-label]').forEach((td) => {
      const tr = td.closest('tr');
      if (!tr) return;
      if (!zeilen.has(tr)) zeilen.set(tr, []);
      zeilen.get(tr).push([td.getAttribute('data-label') || '', zellText(td)]);
    });
    for (const zellen of zeilen.values()) {
      if (zellen.some(([l]) => SPALTEN.symbol.includes(l) || SPALTEN.seite.includes(l))) continue;
      for (const [l, v] of zellen) if (istLabel(l) && istWert(v)) setze(l, v);
    }

    // (b) Label + benachbarter Zahlen-Text im Account-Manager-Panel
    const wurzel = kontoManagerWurzel();
    if (wurzel) {
      // (c) schlichte Tabelle ohne data-label: <th>Label</th><td>Wert</td>
      try {
        wurzel.querySelectorAll('th').forEach((th) => {
          const td = th.nextElementSibling;
          const l = textKurz(th), v = td ? textKurz(td) : '';
          if (istLabel(l) && istWert(v)) setze(l, v);
        });
      } catch (_) {}
      let els;
      try { els = wurzel.querySelectorAll('*'); } catch (_) { els = []; }
      let geprueft = 0;
      for (const el of els) {
        if (n >= SUMMARY_MAX || ++geprueft > 6000) break;
        if (el.children.length) continue;                      // nur Blaetter als Label
        if (el.closest('table,script,style,input,textarea')) continue;
        const t = textKurz(el);
        if (!t || t.length > 70) continue;
        // „Label: 1.234,00" in EINEM Element
        const m = t.match(/^([^:\d]{2,40}):\s*(.+)$/);
        if (m && istLabel(m[1].trim()) && istWert(m[2].trim())) { setze(m[1], m[2]); continue; }
        if (!istLabel(t)) continue;
        // 0.5.1 (Vollumstieg „Ohne Hedge“ — Rundgang und tvclose lesen Today's P&L hieraus):
        // Tradovates Kopfzeile im Reiter „Positionen“ stellt Label und Wert oft als
        // getrennte Divs unter EINEM Elternteil — mit einem Info-Icon oder Trenner
        // dazwischen. Deshalb nicht nur die direkten Nachbarn, sondern ALLE Geschwister
        // des Labels (naechster zuerst, dann die uebrigen), danach die Geschwister des
        // Elternteils. Erster Treffer, der wie ein Wert aussieht, gewinnt; ein Geschwister
        // derselben Ebene, das selbst wie ein Label aussieht, beendet die Suche (sonst
        // naehme „Balance“ den Wert von „Equity“ daneben).
        const p = el.parentElement;
        const gp = p && p.parentElement;
        const kand = [el.nextElementSibling, el.previousElementSibling];
        if (p) for (const g of p.children) if (g !== el && kand.indexOf(g) < 0) kand.push(g);
        if (p) kand.push(p.nextElementSibling, p.previousElementSibling);
        if (gp && p) for (const g of gp.children) if (g !== p && kand.indexOf(g) < 0) kand.push(g);
        let gefunden = false;
        for (const k of kand) {
          if (!k || k === el) continue;
          const v = textKurz(k);
          if (!v || v.length > 40) continue;
          if (istWert(v)) { setze(t, v); gefunden = true; break; }
          if (istLabel(v) && k.parentElement === p) break;
        }
        if (gefunden) continue;
      }
    }

    // Tages-G&V: erstes Label aus der Liste, das in einem Summary-Label steckt
    let todayLabel = null, todayText = null;
    const keys = Object.keys(paare).filter((k) => !RX_NICHT_TODAY.test(k));
    for (const such of TODAY_PNL_LABELS) {
      const sl = such.toLowerCase();
      const k = keys.find((x) => x.toLowerCase().includes(sl));
      if (k) { todayLabel = k; todayText = paare[k]; break; }
    }
    return { summary: paare, today_pnl_text: todayText, today_label: todayLabel };
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
    // Konto-Zusammenfassung (0.5.0) — darf das Bedienfeld nie mitreissen:
    // ein Fehler hier wird gemeldet, alles andere geht trotzdem raus.
    let zus;
    try {
      zus = liesZusammenfassung();
    } catch (e) {
      zus = { summary: null, today_pnl_text: null, today_label: null,
              summary_fehler: String((e && e.message) || e) };
    }

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
      // Konto-Zusammenfassung (0.5.0, Orbit-V2-Rundgang): alle Label→Wert-Paare
      // des Account Managers + der Tages-G&V nach TODAY_PNL_LABELS. null =
      // nicht lesbar (Fehler steht in summary_fehler), {} = nichts gefunden.
      summary: zus.summary,
      today_pnl_text: zus.today_pnl_text,
      today_label: zus.today_label,
      summary_fehler: zus.summary_fehler || null,
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
      // Text-Treffer (0.4.2): null = es wurde nichts gesucht, [] = gesucht und
      // nichts gefunden. Der Unterschied zaehlt — "nicht gesucht" darf beim
      // Puls nie als "steht nicht da" ankommen.
      treffer: suchTexte.length ? sucheTexte() : null,
      // 0.8.0: Nachweis, was der Socket liefert — auch im verdeckten Tab (Frames/Minute je Quelle, Modus, Serien)
      feed: pxFeedStand(),
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
        try {
          const a = JSON.parse(r.responseText);
          dumpAn = a.dump === true;
          suchTexte = Array.isArray(a.suche) ? a.suche.slice(0, 60) : [];
        } catch (_) { dumpAn = false; suchTexte = []; }
      },
      onerror: () => {},      // alter reader-server ohne /bedienfeld: still ignorieren
      ontimeout: () => {},
    });
  }

  /* Blind-Pruefung (0.4.0, 01.09.2026; verschaerft 0.4.1 am selben Abend).
   * Gibt den GRUND zurueck, warum dieser Lesevorgang nicht als Aussage
   * taugt — oder null, wenn er es tut.
   *
   * Die Regel dahinter ist dieselbe wie ueberall in Prophos ("Beweis oder
   * leer"), nur an der einen Stelle, an der sie bisher fehlte: der Reader
   * durfte "0 Positionen" sagen, ohne zu wissen, ob er die Tabelle ueberhaupt
   * gesehen hat. Der Server nimmt einen blinden Stand nicht an, der Stand
   * friert ein, und die Frische-Doktrin des Verbinders haelt den Hedge —
   * stale != flat. Ein blinder Reader schliesst nie einen Hedge.
   *
   * 0.4.1, warum die 0.4.0-Pruefung NICHT gereicht hat (Finns Lauf vom
   * selben Abend, Flattern trotz Fix): sie kannte nur "Zeilen da, Zellen
   * leer". Nimmt TradingView die Zeilen im verdeckten Tab aber KOMPLETT aus
   * dem DOM (Virtualisierung/Unmount), ist der Befund "Anker da, 0 Zeilen" —
   * und das fiel als "Tabelle da, wirklich flach" durch. textContent liest
   * dann auch nichts mehr, weil es nichts zu lesen GIBT. Deshalb jetzt die
   * haertere Invariante: EIN VERDECKTER TAB DARF NIE EINEN WECHSEL AUF
   * "FLACH" BEHAUPTEN. Massstab ist die letzte SICHTBARE Lesung: waren da
   * Positionen offen, ist ein leerer Befund im verdeckten Tab Unwissen —
   * egal, welchen DOM-Trick Chrome oder TradingView diesmal spielt.
   *
   * WICHTIG, beide Richtungen bleiben offen: Positionen gehen IMMER durch
   * (auch im verdeckten Tab — Zeilen im DOM sind Beweis genug), und ein
   * SICHTBARER Tab mit vorhandener Tabelle darf weiter flach melden (echte
   * Closes muessen den Hedge zumachen). War die letzte sichtbare Lesung
   * schon flach, darf auch der verdeckte Tab flach bleiben. */
  let sichtbarePosZahl = null;   // Positionszahl der letzten SICHTBAREN, nicht blinden Lesung

  function blindGrund(positionen) {
    if (positionen.length) return null;                  // Positionen = Beweis genug
    if (!leseBefund.tabelle) return 'Positionstabelle nicht auffindbar (Panel zu?)';
    if (leseBefund.zeilen && !leseBefund.zellen) return 'Tabellenzellen kamen leer zurueck';
    if (document.visibilityState !== 'visible') {
      if (sichtbarePosZahl === null)
        return 'Tab verdeckt, noch keine sichtbare Lesung als Massstab';
      if (sichtbarePosZahl > 0)
        return 'Tab verdeckt — zuletzt sichtbar waren ' + sichtbarePosZahl +
               ' Position(en) offen, ein leerer Befund beweist hier nichts';
    }
    return null;                                          // Tabelle da, wirklich flach
  }

  // Tab-Titel „NQZ2026 30,448.25 ▼ −1.03% Unnamed" (auch „(2) NQ1! 30,510.50 ▼ −0.83% …"
  // bei ungelesenen Meldungen, und ohne Pfeil bei genau 0 %). Dieselbe Signatur wie
  // TV_RX_CHART_TITEL im Puls (order_bot.py), nur mit Fanggruppen fuer Symbol + Kurs.
  const RX_TITEL_KURS = /^(?:\(\d+\)\s*)?([A-Za-z][A-Za-z0-9!:._-]{1,24})\s+([\d.,]+)\s+(?:[▲▼]\s*)?[−\-+]?[\d.,]+\s*%/;
  function liesKursAusTitel() {
    const m = RX_TITEL_KURS.exec(String(document.title || '').trim());
    if (!m) return null;
    return { symbol: m[1], text: m[2], ts: Date.now() };
  }

  /* 0.7.0 (24.09.2026, Finn: „ich muss das zu 100 % sicher haben: die MNQ- und NQ-Live-Daten
   * in Prophos, mit einem Script, das die ganze Zeit liest, auf einem PC, der 24/7 an ist —
   * genau von dem NQ und MNQ, wo auch die Order platziert ist"):
   * BEIDE Symbole gleichzeitig, aus einem TradingView-Layout mit zwei Chart-Panes (NQ1! oben,
   * MNQ1! unten). Quelle je Pane: die Sell/Buy-Knoepfe in der Chart-Legende
   * ([data-name="sell-order-button"] / [data-name="buy-order-button"]) — sie tragen Bid und
   * Ask als Text ('30,738.50Sell' / '30,739.00Buy', deutsch 'Verkaufen'/'Kaufen') und haengen
   * an data-name-Ankern, nicht an gehashten Klassen. Welches Symbol das Pane zeigt, steht in
   * der Legende daneben: entweder als Symbol ('CME_MINI:NQ1!') oder als Beschreibung
   * ('NASDAQ 100 E-mini Futures' / 'Micro E-mini Nasdaq-100') — beides wird erkannt.
   * Rueckfall: der Tab-Titel (nur das aktive Chart-Symbol) wie in 0.6.0.
   * Am Mac ohne Login geprueft (24.09.2026): Knoepfe + Legende so vorhanden; das 2-Pane-Layout
   * und das Ticken im VERDECKTEN Tab kann nur der PC beweisen — deshalb meldet der Payload
   * ehrlich sichtbar/stale je Symbol. */
  // Kein \b am Ende: nach '1!' gibt es keine Wortgrenze (Browser-Test 24.09.2026: 'NQ1!' fiel durch) — stattdessen
  // „danach kein Buchstabe/keine Ziffer", damit 'NQZ2026' nicht als 'NQ' + Rest gelesen wird.
  const RX_KURS_SYMBOL = /\b(M?NQ)(?:\d*!|[FGHJKMNQUVXZ]\d{1,4})?(?![A-Z0-9])/;
  // \d+ zuerst (Browser-Test: '30739Buy' wurde als '307' gelesen, weil die Dreiergruppen-Form zuerst griff)
  const RX_KURS_ZAHL = /\d+(?:[.,]\d{3})*(?:[.,]\d+)?/;
  function kursWurzelAusText(t) {
    const s = String(t || '');
    const m = RX_KURS_SYMBOL.exec(s.toUpperCase());
    if (m) return m[1];
    if (/micro/i.test(s) && /nasdaq|nq/i.test(s)) return 'MNQ';
    if (/nasdaq\s*-?\s*100|e-mini nasdaq/i.test(s)) return 'NQ';
    return '';
  }
  function kursZahlText(t) {
    const m = RX_KURS_ZAHL.exec(String(t || '').replace(/\u2212/g, '-'));
    return m ? m[0] : '';
  }
  // Legenden-Knoepfe je Pane lesen → { NQ: {bid, ask, text, symbol_text, quelle}, MNQ: {...} }
  function liesKurseAusLegenden() {
    const out = {};
    let knoepfe;
    try { knoepfe = document.querySelectorAll('[data-name="buy-sell-buttons"]'); } catch (_) { return out; }
    for (const k of knoepfe) {
      let leg = k.parentElement;
      while (leg && !/legend/i.test(String(leg.className))) leg = leg.parentElement;
      const legText = leg ? (leg.textContent || '').replace(/\s+/g, ' ') : '';
      const wurzel = kursWurzelAusText(legText);
      if (!wurzel || out[wurzel]) continue;               // unbekanntes Pane oder Doppel (erstes gewinnt)
      const sell = k.querySelector('[data-name="sell-order-button"]');
      const buy = k.querySelector('[data-name="buy-order-button"]');
      const bid = kursZahlText(sell && sell.textContent), ask = kursZahlText(buy && buy.textContent);
      if (!bid && !ask) continue;
      out[wurzel] = { bid: bid || null, ask: ask || null, text: bid || ask, symbol_text: legText.slice(0, 60), quelle: 'legende' };
    }
    return out;
  }
  /* ═══ 0.8.0 (24.09.2026 spaet): TradingViews EIGENE WebSocket-Verbindung passiv mithoeren ═══
   * Finn: „Ich muss das zu 100 % sicher haben: die MNQ- und NQ-Live-Daten in Prophos … auf einem
   * PC, der 24/7 an ist — genau von dem NQ und MNQ, wo auch die Order platziert ist." Spec:
   * Vault „Prophos - Live-Chart NQ MNQ ueber TV-Reader" (Session „Live-Daten fuer NQ und MNQ").
   * Kein eigener Socket, keine eigene Anfrage: das Script haengt sich an die Verbindung, die
   * TradingView selbst oeffnet, und liest mit, was ohnehin ankommt. WebSocket-message-Events
   * werden im verdeckten Tab NICHT gedrosselt — deshalb liefert dieser Weg auch, wenn Prophos
   * vorn liegt (der Tab-Titel friert dort ein). Dafuer @run-at document-start (der Socket ist
   * bei document-idle laengst offen) und @grant unsafeWindow (mit @grant laeuft das Script in
   * der Sandbox, das Seiten-Objekt WebSocket erreicht man nur ueber unsafeWindow).
   * Am 24.09.2026 im Browser-Pane am echten TradingView mitgelesen (MessageEvent-Getter, 8 s):
   *   Frame  = '~m~<len>~m~<json>' (mehrere je Frame), '~m~<len>~m~~h~<n>' = Herzschlag
   *   qsd    → p[1] = {n:'CME_MINI:NQ1!' ODER n:'={"symbol":"CME_MINI:NQ1!",…}', s:'ok',
   *                    v:{bid, ask, lp, lp_time, ch, chp, volume, …}}  (Teil-Updates: nur die
   *                    Felder, die sich geaendert haben — deshalb wird gemerged, nie ersetzt)
   *   du / timescale_update → p[1] = {'sds_1': {s:[{i, v:[t, o, h, l, c, vol]}], lbs:{…}},
   *                    'st1': {st:[…]} (Studien — fallen durch die 5–6-Zahlen-Regel)}
   *   Serie → Symbol/Aufloesung nur ueber die SENDS: resolve_symbol (p[1]=Symbol-Id,
   *   p[2]='={"symbol":…}') und create_series/modify_series (p[1]=Serien-Id, p[3]=Symbol-Id,
   *   p[4]=Aufloesung, z. B. '1'). Serien-Id nie hart verdrahten.
   * Alles hier ist gegen Fehler abgeschottet: ein Fehler im Mithoeren darf TradingView nie
   * stoeren (wir reichen jedes Event unveraendert weiter) und den Positions-Reader nie mitreissen. */
  const feed = {
    sockets: 0, frames: [], qsd: [], du: [], titel: [],   // Zeitstempel (ms) der letzten 60 s
    letzter_frame_ms: 0, letzter_ws_ms: 0,                // irgendein Frame (auch ~h~) / Kurs- oder Bar-Frame
    serien: {},          // serienId -> { symbol, wurzel, aufloesung }
    symbole: {},         // symbolId (sds_sym_1) -> symbol
    kurse: {},           // wurzel -> { lp, bid, ask, lp_time, symbol, ts, geaendert_ms }
    bars: [],            // wartende Bars fuer POST /kerzen
    erstladung: false,
    unbekannte_serien: 0, fehler: 0, aufloesung_warnung: null,
    // 0.8.2: je Serien-Id statt je Bar — sid -> Bars, damit die Live-Zeile sagt, welche Serie es ist
    unbekannt: {},       // kein create_series-Send gehoert UND kein Rueckfall (pxSerieRaten) moeglich
    unaufgeloest: {},    // Send gehoert, aber die Symbol-Id hat noch keinen Klartext (resolve_symbol lief vor dem Wrapper)
    fremd: {},           // Symbol bekannt, Wurzel weder NQ noch MNQ (ES, Vergleichssymbol, …) -> keine Bars, kein Fehler
    modus: null, delay_s: null,   // update_mode aus qsd/series_completed ('streaming' | 'delayed_streaming_600'), delay aus symbol_resolved
    info: {},            // symbolId -> { symbol, root, front_contract, pointvalue, tick } aus symbol_resolved (eingehend)
    bevorzugt: {},       // wurzel -> Symbol der Chart-Serie (NQ1! und NQZ2026 liefern dieselben qsd — nur eine Quelle je Wurzel)
  };
  const feedZaehl = (liste, jetzt) => { liste.push(jetzt); while (liste.length && liste[0] < jetzt - 60000) liste.shift(); };
  // Framing als reine Funktion (testbar): Text -> [{m, p} | {h: n}]
  function pxFramesParsen(text) {
    const out = [];
    const s = String(text || '');
    let i = 0;
    while (i < s.length) {
      const m = /^~m~(\d+)~m~/.exec(s.slice(i, i + 24));
      if (!m) break;
      const len = Number(m[1]);
      const body = s.substr(i + m[0].length, len);
      i += m[0].length + len;
      if (body.startsWith('~h~')) { out.push({ h: Number(body.slice(3)) || 0 }); continue; }
      try { const j = JSON.parse(body); if (j && typeof j === 'object') out.push(j); } catch (_) { out.push({ fehler: body.slice(0, 40) }); }
    }
    return out;
  }
  // 'CME_MINI:NQ1!' | '={"symbol":"CME_MINI:NQ1!",…}' -> 'CME_MINI:NQ1!'
  function pxSymbolAusN(n) {
    let s = String(n || '');
    if (s.startsWith('=')) { try { s = JSON.parse(s.slice(1)).symbol || ''; } catch (_) { const m = /"symbol"\s*:\s*"([^"]+)"/.exec(s); s = m ? m[1] : ''; } }
    return s;
  }
  function pxSendMerken(text) {
    for (const msg of pxFramesParsen(text)) {
      if (!msg || !msg.m || !Array.isArray(msg.p)) continue;
      if (msg.m === 'resolve_symbol' && msg.p.length >= 3) {
        const sym = pxSymbolAusN(msg.p[2]);
        if (sym) feed.symbole[String(msg.p[1])] = sym;
      } else if ((msg.m === 'create_series' || msg.m === 'modify_series') && msg.p.length >= 5) {
        const sym = feed.symbole[String(msg.p[3])] || '';
        const info = feed.info[String(msg.p[3])];
        const wurzel = (info && info.root) || kursWurzelAusText(sym);
        // symbol_id merken (0.8.2): ist der Klartext noch unbekannt, zieht pxSerienNachziehen ihn nach,
        // sobald symbol_resolved fuer diese Id eintrifft — statt jede Bar als 'unbekannt' zu zaehlen.
        feed.serien[String(msg.p[1])] = { symbol: sym, wurzel, aufloesung: String(msg.p[4]), symbol_id: String(msg.p[3]) };
        if (wurzel && sym) feed.bevorzugt[wurzel] = sym;
      }
    }
  }
  // 0.8.1: Serie ohne mitgehoerten create_series-Send (Wrapper kam nach den Sends — Tampermonkey-Update
  // ohne F5, oder Chart schon aufgebaut) — drei Rueckfaelle, jeder als 'geraten' markiert, damit das
  // Reader-Fenster sagt, worauf die Zuordnung beruht: (1) genau EIN aufgeloestes Symbol (symbol_resolved
  // kommt eingehend, braucht keinen Send) → das; (2) Tab-Titel „MNQZ2026 30,448.25 ▼ …" = Symbol des
  // aktiven Charts; (3) genau EINE Wurzel im qsd-Strom. Aufloesung bleibt '1' als Annahme — der
  // reader-server prueft die Kerzenabstaende nicht, aber die Bars sind ohnehin nur brauchbar, wenn der
  // Chart auf 1 min steht (Finns Screenshot 24.09.: „1m"). Mehrdeutig → unbekannte_serien zaehlt hoch.
  function pxSerieRaten(sid) {
    let symbol = '', grund = '';
    const ids = Object.keys(feed.info);
    if (ids.length === 1) { symbol = feed.info[ids[0]].symbol; grund = 'einziges aufgeloestes Symbol'; }
    if (!symbol) { const t = liesKursAusTitel(); if (t && t.symbol) { symbol = t.symbol; grund = 'Tab-Titel'; } }
    if (!symbol) { const ws = Object.keys(feed.kurse); if (ws.length === 1) { symbol = feed.kurse[ws[0]].symbol || ws[0]; grund = 'einzige qsd-Wurzel'; } }
    const wurzel = symbol ? kursWurzelAusText(symbol) : '';
    if (!wurzel) return null;
    return (feed.serien[sid] = { symbol, wurzel, aufloesung: '1', geraten: true, grund });
  }
  // 0.8.2: Serien, deren Send gehoert wurde, deren Symbol-Id aber noch keinen Klartext hatte, bekommen
  // ihn nach — feed.symbole/feed.info fuellen sich durch symbol_resolved (eingehend) auch dann, wenn
  // das resolve_symbol selbst vor dem Wrapper lief.
  function pxSerienNachziehen() {
    for (const sid of Object.keys(feed.serien)) {
      const se = feed.serien[sid];
      if (!se || se.wurzel || !se.symbol_id) continue;
      const sym = feed.symbole[se.symbol_id] || '';
      const info = feed.info[se.symbol_id];
      if (!sym && !info) continue;
      se.symbol = sym || (info && info.symbol) || '';
      se.wurzel = (info && info.root) || kursWurzelAusText(se.symbol);
      if (se.wurzel && se.symbol) feed.bevorzugt[se.wurzel] = se.symbol;
      if (se.wurzel) { delete feed.unaufgeloest[sid]; feed.unbekannte_serien = Object.keys(feed.unbekannt).length + Object.keys(feed.unaufgeloest).length; }
    }
  }
  const WURZELN = ['NQ', 'MNQ'];   // nur dafuer gibt es Bars — alles andere (ES, Vergleichssymbol) ist 'fremd', kein Fehler
  const zaehl = (obj, sid) => { obj[sid] = (obj[sid] || 0) + 1; };
  function pxBarsAusUpdate(p1, erstladung) {
    if (!p1 || typeof p1 !== 'object') return 0;
    let n = 0;
    for (const sid of Object.keys(p1)) {
      const eintrag = p1[sid];
      const s = eintrag && Array.isArray(eintrag.s) ? eintrag.s : null;
      if (!s || !s.length) continue;
      let serie = feed.serien[sid];
      if (serie && !serie.wurzel && serie.symbol_id) { pxSerienNachziehen(); serie = feed.serien[sid]; }
      if (!serie) serie = pxSerieRaten(sid);
      for (const b of s) {
        const v = b && Array.isArray(b.v) ? b.v : null;
        if (!v || v.length < 5 || v.length > 6 || !v.every(x => typeof x === 'number')) continue;
        if (!serie || !serie.wurzel || WURZELN.indexOf(serie.wurzel) < 0) {
          // Ursache getrennt zaehlen (0.8.2), je Serie: fremd / unaufgeloest / unbekannt
          if (serie && serie.symbol) { const f = feed.fremd[sid] || (feed.fremd[sid] = { symbol: serie.symbol, bars: 0 }); f.bars++; }
          else if (serie && serie.symbol_id) zaehl(feed.unaufgeloest, sid);
          else zaehl(feed.unbekannt, sid);
          feed.unbekannte_serien = Object.keys(feed.unbekannt).length + Object.keys(feed.unaufgeloest).length;
          continue;
        }
        feed.bars.push({ wurzel: serie.wurzel, symbol: serie.symbol, aufloesung: serie.aufloesung,
                         minute: Math.floor(v[0]), o: v[1], h: v[2], l: v[3], c: v[4], vol: v[5] == null ? null : v[5] });
        n++;
      }
    }
    if (n && erstladung) { feed.erstladung = true; feed.erstladung_erwartet = null; }
    if (feed.bars.length > 2000) feed.bars = feed.bars.slice(-2000);   // Erstladung ist begrenzt, du-Updates sind klein
    return n;
  }
  function pxModus(m) {
    if (typeof m !== 'string' || !m) return;
    feed.modus = m;
    const d = /delayed[^0-9]*(\d+)/.exec(m);
    if (d) feed.delay_s = Number(d[1]);
    else if (m === 'streaming') feed.delay_s = 0;
  }
  function pxNachricht(msg, jetzt) {
    if (!msg || !msg.m || !Array.isArray(msg.p)) return;   // Begruessung ohne m, Herzschlag: nichts zu tun
    if (msg.m === 'symbol_resolved' && msg.p.length >= 3 && msg.p[2] && typeof msg.p[2] === 'object') {
      // eingehend: Symbol-Id -> Klartext + Wurzel + Frontkontrakt + Punktwert (kein Regex noetig)
      const i = msg.p[2], sym = String(i.pro_name || i.full_name || i.name || '');
      const root = String(i.root || '') || kursWurzelAusText(sym);
      feed.info[String(msg.p[1])] = { symbol: sym, root, front_contract: i.front_contract || null, pointvalue: i.pointvalue || null,
                                      tick: (i.minmov && i.pricescale) ? i.minmov / i.pricescale : null };
      if (sym) feed.symbole[String(msg.p[1])] = sym;
      if (typeof i.delay === 'number') feed.delay_s = i.delay;
      pxSerienNachziehen();   // 0.8.2: wartende Serien mit dieser Symbol-Id bekommen jetzt Klartext + Wurzel
      return;
    }
    if (msg.m === 'series_completed' && msg.p.length >= 3) { pxModus(msg.p[2]); return; }
    if (msg.m === 'series_loading' && msg.p.length >= 2) {
      // Serie wird neu geladen (Symbol-/Aufloesungswechsel): das naechste timescale_update ersetzt den Ring
      feed.erstladung_erwartet = String(msg.p[1]);
      return;
    }
    if (msg.m === 'qsd') {
      const p1 = msg.p[1];
      if (!p1 || typeof p1 !== 'object' || !p1.v) return;
      const sym = pxSymbolAusN(p1.n), wurzel = kursWurzelAusText(sym);
      if (!wurzel) return;
      if (p1.v.update_mode) pxModus(p1.v.update_mode);
      // Nur EINE Quelle je Wurzel (NQ1! und NQZ2026 senden identische qsd): die Chart-Serie hat Vorrang,
      // sonst das zuerst gesehene Symbol; ein anderes Symbol darf erst uebernehmen, wenn die Quelle > 10 s still ist.
      const bev = feed.bevorzugt[wurzel];
      const k0 = feed.kurse[wurzel];
      if (k0 && k0.symbol && k0.symbol !== sym) {
        const quelleAktiv = (jetzt - (k0.empf_ms || 0)) < 10000;
        if (quelleAktiv && (bev ? k0.symbol === bev : true) && sym !== bev) return;
      }
      const k = feed.kurse[wurzel] || (feed.kurse[wurzel] = { lp: null, bid: null, ask: null, lp_time: null, symbol: sym, ts: 0, geaendert_ms: 0, empf_ms: 0 });
      const v = p1.v;
      let neu = false;
      for (const f of ['lp', 'bid', 'ask', 'lp_time']) {
        if (typeof v[f] === 'number' && isFinite(v[f])) { if (k[f] !== v[f]) neu = true; k[f] = v[f]; }
      }
      if (sym) k.symbol = sym;
      k.empf_ms = jetzt;
      // 0.8.1: ts ist die EMPFANGSZEIT. Vorher lp_time×1000 — TradingView liefert lp_time aber nur
      // minutengenau/sporadisch (Mitschnitt 24.09.: lp-Updates ohne lp_time, lp_time = Minutengrenze).
      // Moritz' PC 24.09. 21:40: reader_ts = 17:40:00,000 exakt, 46 s alt bei 5 s altem updated_at —
      // jeder Leser mit 30-s-Grenze (hedgeKursLesen, Markt-Kopf, Farmer-Zeile) hielt den Feed fuer tot.
      k.ts = jetzt;
      if (neu) k.geaendert_ms = jetzt;
      feedZaehl(feed.qsd, jetzt); feed.letzter_ws_ms = jetzt;
    } else if (msg.m === 'du' || msg.m === 'timescale_update') {
      if (pxBarsAusUpdate(msg.p[1], msg.m === 'timescale_update')) { feedZaehl(feed.du, jetzt); feed.letzter_ws_ms = jetzt; }
    }
  }
  function pxFrameVerarbeiten(data) {
    if (typeof data !== 'string' || data.indexOf('~m~') !== 0) return;
    const jetzt = Date.now();
    feedZaehl(feed.frames, jetzt); feed.letzter_frame_ms = jetzt;
    for (const msg of pxFramesParsen(data)) { try { pxNachricht(msg, jetzt); } catch (_) { feed.fehler++; } }
  }
  function pxSocketHaken(ws) {
    feed.sockets++;
    try { ws.addEventListener('message', ev => { try { pxFrameVerarbeiten(ev.data); } catch (_) { feed.fehler++; } }); } catch (_) {}
    try {
      const origSend = ws.send;
      ws.send = function (d) { try { if (typeof d === 'string') pxSendMerken(d); } catch (_) { feed.fehler++; } return origSend.apply(this, arguments); };
    } catch (_) {}
  }
  (function pxWebSocketWrappen() {
    const W = (typeof unsafeWindow !== 'undefined' && unsafeWindow) ? unsafeWindow : window;
    const Orig = W.WebSocket;
    if (!Orig || Orig.__prophos) return;
    function PxWebSocket(url, protocols) {
      const ws = (protocols === undefined) ? new Orig(url) : new Orig(url, protocols);
      try { pxSocketHaken(ws); } catch (_) { feed.fehler++; }
      return ws;
    }
    PxWebSocket.prototype = Orig.prototype;
    for (const k of ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED']) { try { PxWebSocket[k] = Orig[k]; } catch (_) {} }
    PxWebSocket.__prophos = true;
    try { W.WebSocket = PxWebSocket; } catch (_) { feed.fehler++; }
  })();
  // Kurse aus dem Socket in der Payload-Form (Vorrang vor Legende/Titel): preis = lp, sonst Mitte bid/ask
  function pxKurse() {
    const out = {};
    for (const w of Object.keys(feed.kurse)) {
      const k = feed.kurse[w];
      const preis = (typeof k.lp === 'number') ? k.lp : (typeof k.bid === 'number' && typeof k.ask === 'number') ? Math.round((k.bid + k.ask) * 100 / 2) / 100 : null;
      if (!(preis > 0)) continue;
      out[w] = { bid: k.bid, ask: k.ask, lp: k.lp, lp_time: k.lp_time,
                 lp_time_ms: (typeof k.lp_time === 'number' && k.lp_time > 1e9) ? k.lp_time * 1000 : null,   // 0.8.1: Handelszeit getrennt vom ts
                 text: String(preis), symbol_text: k.symbol, quelle: 'ws', ts: k.ts,
                 modus: feed.modus, delay_s: feed.delay_s };
    }
    return out;
  }
  // Nachweis fuers Bedienfeld: was liefert der Socket gerade — auch im verdeckten Tab?
  function pxFeedStand() {
    return {
      ws_frames_min: feed.frames.length, qsd_min: feed.qsd.length, du_min: feed.du.length, titel_min: feed.titel.length,
      letzter_frame_ms: feed.letzter_frame_ms, letzter_ws_ms: feed.letzter_ws_ms, sockets: feed.sockets,
      serien: feed.serien, symbole: Object.keys(feed.symbole).length, unbekannte_serien: feed.unbekannte_serien,
      unbekannt: feed.unbekannt, unaufgeloest: feed.unaufgeloest, fremd: feed.fremd,   // 0.8.2: je Serie, mit Bars
      fehler: feed.fehler, aufloesung_warnung: feed.aufloesung_warnung, sichtbar: document.visibilityState === 'visible',
      bars_wartend: feed.bars.length, modus: feed.modus, delay_s: feed.delay_s,
      info: Object.values(feed.info).map(i => ({ symbol: i.symbol, root: i.root, front_contract: i.front_contract, pointvalue: i.pointvalue, tick: i.tick })),
      bevorzugt: feed.bevorzugt,
    };
  }
  // Bars gebuendelt an den Empfaenger (POST /kerzen), hoechstens alle 2 s, nur wenn welche warten
  let pxKerzenZuletzt = 0;
  function pxKerzenSenden() {
    const jetzt = Date.now();
    if (!feed.bars.length || jetzt - pxKerzenZuletzt < 2000) return;
    pxKerzenZuletzt = jetzt;
    const bars = feed.bars; feed.bars = [];
    const erst = feed.erstladung; feed.erstladung = false;
    const andere = bars.filter(b => b.aufloesung !== '1');
    feed.aufloesung_warnung = andere.length ? ('Chart-Aufloesung ' + andere[0].aufloesung + ' statt 1 — keine Minutenkerzen') : null;
    GM_xmlhttpRequest({
      method: 'POST', url: KERZEN, headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify({ ts: jetzt, version: VERSION, quelle: 'ws', erstladung: erst, modus: feed.modus, delay_s: feed.delay_s, bars }), timeout: 4000,
      onerror: () => {}, ontimeout: () => {},
    });
  }

  // Stale-Waechter (0.7.0): je Wurzel den letzten Text und wann er sich ZULETZT geaendert hat.
  // Kein neuer Wert > 45 s → stale:true im Payload (der Chart ist eingefroren oder der Markt
  // steht — beides darf nie als „live" durchgehen). > 90 s ohne jeden Tick → einmal
  // location.reload() (hoechstens 1x je 10 min, Grund landet nach dem Reload im Payload),
  // damit ein eingefrorener Chart sich selbst heilt. Der Reload-Stempel liegt in
  // localStorage (ueberlebt den Reload), der Grund in sessionStorage (nur dieser Tab).
  const STALE_S = 45, RELOAD_S = 90, RELOAD_SPERRE_MS = 10 * 60 * 1000;
  const kursMerk = {};   // wurzel -> { text, geaendert_ms }
  let reloadGrund = null;
  try { reloadGrund = sessionStorage.getItem('prophos_reader_reload_grund') || null; sessionStorage.removeItem('prophos_reader_reload_grund'); } catch (_) {}
  function staleUndReload(kurse) {
    const jetzt = Date.now();
    let juengste = 0;
    for (const w of Object.keys(kurse)) {
      const m = kursMerk[w] || (kursMerk[w] = { text: null, geaendert_ms: jetzt });
      if (kurse[w].text !== m.text) { m.text = kurse[w].text; m.geaendert_ms = jetzt; }
      const alter = (jetzt - m.geaendert_ms) / 1000;
      kurse[w].stale = alter > STALE_S;
      kurse[w].unveraendert_s = Math.round(alter);
      if (m.geaendert_ms > juengste) juengste = m.geaendert_ms;
    }
    // Reload-Kriterium (Koordination 24.09.2026 spaet): nur wenn KEIN WebSocket-Frame mehr kommt (auch kein
    // Herzschlag — am Wochenende/in der CME-Pause laeuft der Herzschlag weiter, die Verbindung ist gesund) UND
    // kein Titel-/Legenden-Wert sich > RELOAD_S geaendert hat — und nicht oefter als alle 10 min. Ohne jemals
    // einen Frame (kein Chart-Tab) kein Reload.
    const socketTot = feed.letzter_frame_ms > 0 && (jetzt - feed.letzter_frame_ms) / 1000 > RELOAD_S;
    if (socketTot && juengste && (jetzt - juengste) / 1000 > RELOAD_S) {
      let letzter = 0;
      try { letzter = Number(localStorage.getItem('prophos_reader_reload_ms')) || 0; } catch (_) {}
      if (jetzt - letzter > RELOAD_SPERRE_MS) {
        try {
          localStorage.setItem('prophos_reader_reload_ms', String(jetzt));
          sessionStorage.setItem('prophos_reader_reload_grund', 'kein WebSocket-Frame seit ' + Math.round((jetzt - feed.letzter_frame_ms) / 1000) + ' s, kein neuer Kurs seit ' + Math.round((jetzt - juengste) / 1000) + ' s');
        } catch (_) {}
        setTimeout(() => location.reload(), 500);
        return true;
      }
    }
    return false;
  }
  // Gesamtbild fuer den Payload: Legenden zuerst, Tab-Titel als Rueckfall fuer die Wurzel des aktiven Charts
  function liesKurse() {
    // 0.8.0: Socket zuerst (laeuft auch verdeckt), dann Legende (0.7.0), dann Tab-Titel (0.6.0)
    const kurse = pxKurse();
    const leg = liesKurseAusLegenden();
    for (const w of Object.keys(leg)) if (!kurse[w]) kurse[w] = leg[w];
    const t = liesKursAusTitel();
    if (t) {
      feedZaehl(feed.titel, Date.now());
      const w = kursWurzelAusText(t.symbol);
      if (w && !kurse[w]) kurse[w] = { bid: null, ask: null, text: t.text, symbol_text: t.symbol, quelle: 'titel' };
    }
    const ts = Date.now();
    for (const w of Object.keys(kurse)) if (!kurse[w].ts) kurse[w].ts = ts;
    staleUndReload(kurse);
    return kurse;
  }

  function tick() {
    const positionen = lesePositionen();
    const blind = blindGrund(positionen);
    // Massstab fuer die Verdeckt-Regel nachfuehren: NUR sichtbare, nicht
    // blinde Lesungen zaehlen. Eine Lesung im verdeckten Tab veraendert den
    // Massstab nie — sonst wuerde ein einzelner leerer Befund sich selbst
    // zum neuen "Normal" erklaeren und die Regel aushebeln.
    if (!blind && document.visibilityState === 'visible')
      sichtbarePosZahl = positionen.length;
    // Auch blind wird GESENDET — der Server soll den Grund kennen (und die
    // Orbit-Karte spaeter auch). Er uebernimmt den Stand dann nur nicht.
    const payload = JSON.stringify({
      ts: Date.now(), positionen, version: VERSION,
      blind: !!blind, blind_grund: blind || '',
      sichtbar: document.visibilityState === 'visible',
      // 0.6.0 (24.09.2026, Winning-Day-Gegenhedge auf Fusion — Finn: „auf einem PC,
      // der 24/7 laeuft, per Reader immer in Echtzeit die aktuellen NQ-/MNQ-Punkte
      // haben"): der Kurs aus dem TAB-TITEL. Bewusst nicht aus der Watchlist oder
      // der Chart-Legende — deren Anker gehoeren TradingView und wurden schon
      // zweimal umbenannt (31.08., 21.09.); der Titel tickt seit Monaten in
      // derselben Form. Nur Roh-Text, gedeutet wird im Prophos-Tab (Zahlformat
      // deutsch/englisch, gleiche Regel wie tv_snapshot.parse_de_zahl). null =
      // Titel nicht lesbar (kein Chart-Tab) — nie ein stilles 0.
      kurs: liesKursAusTitel(),
      // 0.7.0: beide Symbole aus den Legenden (kurse.NQ / kurse.MNQ mit bid/ask/text/ts/quelle/stale),
      // Rueckfall Tab-Titel; reload_grund nur im ersten Tick nach einer Selbstheilung.
      kurse: liesKurse(),
      reload_grund: reloadGrund,
    });
    reloadGrund = null;

    if ((tickNr++ % BF_JEDER) === 0) sendeBedienfeld();
    try { pxKerzenSenden(); } catch (_) { feed.fehler++; }   // 0.8.0: wartende Bars gebuendelt an /kerzen

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
        // 0.5.2: Englisch ist kein Warnfall mehr — Spalten und Zahlen werden in beiden Sprachen gelesen
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

  // document-start (0.8.0): der Socket-Wrapper oben muss vor TradingViews erstem WebSocket stehen —
  // der DOM-Reader (Positionen, Bedienfeld, Badge) laeuft wie bisher erst, wenn die Seite da ist.
  const start = () => { starteTakt(); tick(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
