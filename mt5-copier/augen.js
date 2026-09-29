/* PROPHOS-AUGEN (29.09.2026, Projekt „Script-Augen", Finn: Puls soll TradingView nicht mehr per Windows-UIA erraten, sondern
 * die Seite selbst lesen — Pixel und Feldwerte aus dem DOM, geklickt wird weiter mit der ECHTEN Maus).
 *
 * Eigenständig und ohne Abhängigkeiten: dieselbe Datei läuft
 *   (A) im Userscript (Tampermonkey, Reader-Muster) und
 *   (B) per Chrome DevTools Protocol aus Python: Runtime.evaluate(expression = <Dateiinhalt> + "\nPROPHOS_AUGEN.stand()",
 *       returnByValue = true).
 * Beide Funktionen geben reines JSON zurück (keine DOM-Knoten), werfen nie und KLICKEN NIE.
 *
 * Koordinaten: rect = [x, y, w, h] in CSS-Pixeln relativ zum Viewport (x/y = linke obere Ecke); geo trägt screenX/Y, outer/inner und
 * devicePixelRatio — Puls rechnet daraus Bildschirm-Pixel (wie beim Reader-Bedienfeld seit 30.08.2026).
 *
 * Signatur-Reihenfolge je Feld (Lehre aus dem Reader 0.3–0.8): stabile data-name/id → role/aria → Text DE+EN → Geometrie.
 * CSS-Klassen nie als Anker (TradingView hasht sie bei jedem Release neu). Gewonnen hat die erste Signatur mit GENAU EINEM
 * sichtbaren Treffer; mehrdeutige werden übersprungen und in 'notiz' gemeldet.
 *
 * Live geprüft (öffentliche Chartseite, ohne Broker, 29.09.2026): keine iframes, kein Shadow DOM; Toast-Gruppen tragen
 * data-name="toast-group-expand-button-<gruppe>" (aria-expanded = Stapel offen/zu) und "toast-group-close-button-<gruppe>";
 * Dialoge sind [role=dialog][data-name=…], ihr X hat weder data-name noch aria-label (Knopf oben rechts, Text „Close menu").
 * Ticket-Anker aus Finns Panel-Dump vom 31.08.2026: [data-name=order-panel], side-control-buy/-sell, #quantity-field,
 * #Market, [data-name=place-and-modify-button]. Die Kopf-Knöpfe [data-name=buy-order-button|sell-order-button] sind
 * SCHNELLHANDEL im Chart — nie mit dem Senden-Knopf des Tickets verwechseln (sie werden hier bewusst ausgeschlossen).
 */
var PROPHOS_AUGEN = (function () {
  'use strict';
  var VERSION = '0.7.1';   // 0.7.1 (29.09.2026, K2 für T3): kauf_knopf.disabled, tp/sl.einheit/wert/neben, summary_reiter   // 0.7.0 (29.09.2026, Aufnahme 00:52): Kontoliste ohne Rollen, Meldungs-Status, Watchlist, Dialog-Knöpfe   // 0.6.1 (29.09.2026): aufnahme_letzte() als Rettungskopie, T3-Banner 'prophos-aufnahme' ausgeblendet   // 0.6.0 (29.09.2026, Aufnahme 00:36 leer): window-capture, roh-Zähler, tab_id, Sichtbarkeit   // 0.5.3 (29.09.2026, Lesung 00:22:50): Konto-Anker Kontonummer zuerst, Summary Total P/L = today   // 0.5.2 (29.09.2026, Lesung 00:22): Panel 'Collapse panel'/Manager-Knopf, Konto entdoppelt + kontonr   // 0.5.1 (29.09.2026, Lesung 00:17 pc-usq1i6): Schalter-Rechteck, ticket.seite/bereit, Legende, veraltete Zeilen   // 0.5.0 (29.09.2026): Aufnahme-Modus (Finn klickt den Ablauf einmal selbst, jede Aktion wird mitgeschrieben)   // 0.4.0 (29.09.2026, K1–K4 für T3): positionen, orders, konto_summary, symbolsuche, toasts.meldungen   // 0.3.0 (29.09.2026, erste echte Lesung pc-usq1i6): TP/SL-Zustand, Konto-Leiste, Toast-Rückfall   // 0.2.0 (29.09.2026): Vertrag mit T3 — globalThis.prophosAugen, Schlüssel-Whitelist, popups, kauf_knopf

  // ── Grundwerkzeuge ─────────────────────────────────────────────────────────
  function sichtbar(el) {
    try {
      if (!el || !el.getBoundingClientRect || eigen(el)) return false;
      var r = el.getBoundingClientRect();
      if (r.width < 3 || r.height < 3) return false;
      if (r.bottom < 0 || r.right < 0 || r.top > window.innerHeight || r.left > window.innerWidth) return false;
      var st = window.getComputedStyle(el);
      return st.visibility !== 'hidden' && st.display !== 'none' && st.opacity !== '0';
    } catch (_) { return false; }
  }
  // T3s Aufnahme-Banner/-Rahmen (data-name="prophos-aufnahme", pointer-events none) gehören nicht zu TradingView
  function eigen(el) { try { return !!(el && el.closest && el.closest('[data-name="prophos-aufnahme"]')); } catch (_) { return false; } }
  function rect(el) {
    var r = el.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  }
  // textContent statt innerText: innerText braucht Layout und liefert in einem verdeckten Tab Leeres (Reader-Fund 01.09.2026)
  function txt(el) { return String((el && el.textContent) || '').replace(/\s+/g, ' ').trim(); }
  function wert(el) {
    if (!el) return '';
    if (typeof el.value === 'string') return el.value.trim();
    return txt(el);
  }
  function attr(el, n) { try { return el.getAttribute(n) || ''; } catch (_) { return ''; } }
  function alle(sel, wurzel) {
    try { return Array.prototype.slice.call((wurzel || document).querySelectorAll(sel)); } catch (_) { return []; }
  }
  function kurz(el, extra) {
    var o = { tag: el.tagName.toLowerCase(), dn: attr(el, 'data-name'), role: attr(el, 'role'), aria: attr(el, 'aria-label'),
              id: el.id || '', text: txt(el).slice(0, 60), rect: rect(el) };
    if (typeof el.value === 'string') o.wert = el.value.slice(0, 30);
    var zust = ['aria-expanded', 'aria-selected', 'aria-checked', 'aria-pressed', 'aria-disabled', 'disabled', 'checked'];
    for (var i = 0; i < zust.length; i++) { var v = attr(el, zust[i]); if (v !== '') o[zust[i]] = v; }
    if (el.type === 'checkbox' || el.type === 'radio') o.checked = !!el.checked;
    if (extra) for (var k in extra) o[k] = extra[k];
    return o;
  }
  // erste Signatur mit GENAU EINEM sichtbaren Treffer; sigs = [{q, sel, text?, nicht?, wurzel?}]
  function suche(sigs, wurzel) {
    var notiz = [];
    for (var i = 0; i < sigs.length; i++) {
      var s = sigs[i];
      var els = alle(s.sel, s.wurzel || wurzel).filter(sichtbar);
      if (s.text) els = els.filter(function (e) { return s.text.test(txt(e) + ' ' + attr(e, 'aria-label')); });
      if (s.nicht) els = els.filter(function (e) { return !s.nicht.test(txt(e) + ' ' + attr(e, 'data-name')); });
      if (s.filter) els = els.filter(s.filter);
      if (els.length === 1) return { el: els[0], quelle: s.q, notiz: notiz };
      if (els.length > 1) notiz.push(s.q + ': ' + els.length + ' Treffer');
    }
    return { el: null, quelle: null, notiz: notiz };
  }
  function geo() {
    return { innerWidth: window.innerWidth, innerHeight: window.innerHeight, outerWidth: window.outerWidth,
             outerHeight: window.outerHeight, screenX: window.screenX, screenY: window.screenY, dpr: window.devicePixelRatio || 1,
             scrollX: Math.round(window.scrollX || 0), scrollY: Math.round(window.scrollY || 0) };
  }
  // Nächstes Eingabefeld zu einer Beschriftung: gleiche Zeile rechts daneben oder direkt darunter (≤ 60 px), sonst das nächste
  // Eingabefeld danach in der Dokument-Reihenfolge innerhalb der Wurzel
  function feldZu(label, wurzel) {
    if (!label) return null;
    var lr = label.getBoundingClientRect();
    // nie der Haken/Schalter selbst (Test 29.09.2026: 'Take-Profit, $' trägt seine Checkbox im label) — nur Wertfelder
    var kand = alle('input,[role="spinbutton"],[contenteditable="true"]', wurzel).filter(sichtbar).filter(function (e) {
      return !/^(checkbox|radio|hidden|button|submit)$/i.test(e.type || '') && !label.contains(e);
    });
    var best = null, bestD = 1e9;
    for (var i = 0; i < kand.length; i++) {
      var r = kand[i].getBoundingClientRect();
      var dy = r.top - lr.top, dx = r.left - lr.right;
      var gleicheZeile = Math.abs((r.top + r.height / 2) - (lr.top + lr.height / 2)) <= 14 && dx >= -4 && dx <= 400;
      var darunter = dy >= 0 && dy <= 60 && r.right > lr.left - 20 && r.left < lr.right + 300;
      if (!gleicheZeile && !darunter) continue;
      var d = gleicheZeile ? dx : 1000 + dy;
      if (d < bestD) { bestD = d; best = kand[i]; }
    }
    if (best) return best;
    for (var j = 0; j < kand.length; j++) {
      if (label.compareDocumentPosition(kand[j]) & Node.DOCUMENT_POSITION_FOLLOWING) return kand[j];
    }
    return null;
  }
  /* TP/SL-SCHALTER (erste echte Lesung pc-usq1i6 29.09.2026 00:05 UTC): 'Take profit, $' ist ein <button> mit Symbol-Span, der
   * eigentliche Haken ist ein UNSICHTBARES Kästchen (opacity 0) — sichtbar() filtert es weg, tp.an/sl.an blieben null. Deshalb hier
   * OHNE Sichtbarkeits-Filter: Kästchen/Schalter in derselben Zeile (±16 px) nahe der Beschriftung. Rückfall: deaktiviertes/
   * ausgegrautes Wertfeld = aus. -> {an: true|false|null, quelle} */
  function schalterNahe(label, feld, wurzel) {
    try {
      var lr = label.getBoundingClientRect(), mitte = lr.top + lr.height / 2;
      var kand = alle('input[type="checkbox"],[role="switch"],[role="checkbox"],[aria-checked]', wurzel).filter(function (e) {
        var r = e.getBoundingClientRect();
        if (!r.width && !r.height) { var p = e.parentElement; if (p) r = p.getBoundingClientRect(); }
        return Math.abs((r.top + r.height / 2) - mitte) <= 16 && r.left >= lr.left - 60 && r.left <= lr.right + 320;
      });
      if (kand.length === 1 || (kand.length > 1 && kand.every(function (k) { return schalterZustand(k) === schalterZustand(kand[0]); }))) {
        var z = schalterZustand(kand[0]);
        if (z !== null) return { an: z, quelle: 'kaestchen:' + (attr(kand[0], 'role') || kand[0].type || kand[0].tagName.toLowerCase()), schalter: kurz(kand[0]) };
      }
      var inner = label.querySelector && label.querySelector('input[type="checkbox"],[role="switch"],[role="checkbox"],[aria-checked]');
      if (inner && schalterZustand(inner) !== null) return { an: schalterZustand(inner), quelle: 'kaestchen:innen' };
      var ap = attr(label, 'aria-pressed') || attr(label, 'aria-checked');
      if (ap === 'true' || ap === 'false') return { an: ap === 'true', quelle: 'beschriftung:aria' };
      if (feld) {
        if (feld.disabled || feld.readOnly || attr(feld, 'aria-disabled') === 'true') return { an: false, quelle: 'feld:deaktiviert' };
        var op = 1, x = feld;
        for (var i = 0; i < 4 && x; i++) { op *= parseFloat(window.getComputedStyle(x).opacity || '1'); x = x.parentElement; }
        if (op < 0.75) return { an: false, quelle: 'feld:grau(' + op.toFixed(2) + ')' };
        return { an: null, quelle: 'unklar (Feld aktiv, kein Kästchen gefunden)', kandidaten: kand.length };
      }
    } catch (_) {}
    return { an: null, quelle: 'unklar' };
  }
  // 'ABCABC' → 'ABC', 'X Y X Y' → 'X Y' (TradingView legt manche Texte doppelt ins DOM: sichtbar + Mess-/Tooltip-Kopie)
  function entdoppeln(t) {
    t = String(t || '');
    var m = t.match(/^(.+?)\s*\1$/);
    if (m) return m[1];
    var m2 = t.match(/^(.{6,}?)\1(.*)$/);           // 'NR NR USD' als 'NRNRUSD' (versteckte Kopie mitten im Knopf)
    return m2 ? m2[1] + m2[2] : t;
  }
  function schalterZustand(el) {
    if (!el) return null;
    var cb = el.matches && el.matches('input[type="checkbox"]') ? el : (el.querySelector && el.querySelector('input[type="checkbox"]'));
    if (cb) return !!cb.checked;
    var a = attr(el, 'aria-checked') || attr(el, 'aria-pressed');
    if (a === 'true') return true;
    if (a === 'false') return false;
    return null;   // unlesbar — Puls entscheidet dann über den Wert im Feld
  }

  // ── Texte DE + EN ──────────────────────────────────────────────────────────
  var RX_MENGE = /^(units|einheiten|menge|quantity|qty|kontrakte|contracts|anzahl)\b/i;
  var RX_TP = /take[\s-]*profit|gewinnmitnahme/i;
  var RX_SL = /stop[\s-]*loss|verlustbegrenzung/i;
  var RX_SENDEN = /^(buy|sell|kauf(en)?|verkauf(en)?)\s+[\d.,]+\s+\S+\s+(market|markt|limit|stop|stop[\s-]*limit)\b/i;
  var RX_SCHLIESSEN = /close|schlie(ß|ss)en|^[×✕✖]$|dismiss|ausblenden/i;
  var RX_KONTO = /[A-Z]{3,}[A-Z0-9]*\d{6,}/;

  // ── Ticket (Order-Panel des Brokers) ───────────────────────────────────────
  function ticket() {
    var p = suche([{ q: 'data-name:order-panel', sel: '[data-name="order-panel"]' }]);
    var out = { da: !!p.el, quelle: p.quelle, notiz: p.notiz.slice() };
    if (!p.el) return out;
    var w = p.el;
    out.rect = rect(w);
    var kauf = suche([{ q: 'dn:side-control-buy', sel: '[data-name="side-control-buy"]' },
                      { q: 'text:Kaufen', sel: 'button,[role="button"],[role="radio"],[role="tab"]', text: /^(buy|kauf(en)?)\b/i, wurzel: w }], w);
    var verk = suche([{ q: 'dn:side-control-sell', sel: '[data-name="side-control-sell"]' },
                      { q: 'text:Verkaufen', sel: 'button,[role="button"],[role="radio"],[role="tab"]', text: /^(sell|verkauf(en)?)\b/i, wurzel: w }], w);
    out.kaufen = kauf.el ? kurz(kauf.el, { quelle: kauf.quelle }) : null;
    out.verkaufen = verk.el ? kurz(verk.el, { quelle: verk.quelle }) : null;
    var typen = alle('[role="tab"]', w).filter(sichtbar);
    out.typen = typen.map(function (t) { return kurz(t); });
    var aktiv = typen.filter(function (t) { return attr(t, 'aria-selected') === 'true'; })[0];
    out.typ = aktiv ? txt(aktiv) : null;
    var mengeLabel = alle('*', w).filter(function (e) { return e.children.length === 0 && sichtbar(e) && RX_MENGE.test(txt(e)); })[0] || null;
    var menge = suche([{ q: 'id:quantity-field', sel: '#quantity-field' },
                       { q: 'aria:Menge', sel: 'input[aria-label]', text: /menge|quantit|units|einheit/i, wurzel: w },
                       { q: 'label:Menge', sel: '*', filter: function (e) { return e === feldZu(mengeLabel, w); }, wurzel: w }], w);
    out.menge = menge.el ? kurz(menge.el, { quelle: menge.quelle }) : null;
    function klammer(rx, name) {
      var sch = alle('button,[role="button"],[role="switch"],[role="checkbox"],label,span,div', w).filter(function (e) {
        return sichtbar(e) && e.children.length <= 3 && rx.test(txt(e)) && txt(e).length <= 40;
      });
      // innerstes Element mit dem Text
      sch = sch.filter(function (e) { return !sch.some(function (f) { return f !== e && e.contains(f); }); });
      if (sch.length !== 1) return { da: false, notiz: name + ': ' + sch.length + ' Beschriftungen' };
      var feld = feldZu(sch[0], w);
      var z = schalterNahe(sch[0], feld, w);
      // schalter = das (unsichtbare) input[role=switch] rechts in der Zeile — Lesung 00:17: [1196,397,38,20] (TP) / [1196,481,38,20] (SL)
      // Einheit aus der Beschriftung ('Take profit, $' → '$'; 'ticks'/'%'/'Punkte' falls umgestellt); daneben der Umrechnungs-Knopf
      // (#dropdownId, Lesung 00:05: '30651.50price' bzw. '124ticks') — zeigt denselben Abstand in der anderen Einheit
      var bt = txt(sch[0]), em = bt.match(/,\s*(.+)$/);
      var neben = null;
      if (feld) {
        var fr = feld.getBoundingClientRect();
        var nb = alle('button,[role="button"]', w).filter(function (b) {
          var r = b.getBoundingClientRect();
          return sichtbar(b) && Math.abs(r.top - fr.top) <= 6 && r.left > fr.right + 20 && r.left - fr.right < 200 && txt(b);
        })[0];
        if (nb) { var nt = txt(nb), nm = nt.match(/^([\d.,\-]+)\s*([A-Za-zäöü%$]+)$/); neben = { text: nt, wert: nm ? zahl(nm[1]) : null, einheit: nm ? nm[2] : null, rect: rect(nb) }; }
      }
      return { da: true, beschriftung: kurz(sch[0]), an: z.an, an_quelle: z.quelle, schalter: z.schalter || null, feld: feld ? kurz(feld) : null,
               einheit: em ? em[1].trim() : null, wert: feld ? zahl(feld.value) : null, neben: neben };
    }
    out.tp = klammer(RX_TP, 'TP');
    out.sl = klammer(RX_SL, 'SL');
    var sd = suche([{ q: 'dn:place-and-modify-button', sel: '[data-name="place-and-modify-button"]' },
                    { q: 'text:Senden', sel: 'button,[role="button"]', text: RX_SENDEN, wurzel: w,
                      nicht: /buy-order-button|sell-order-button/ }], w);
    if (sd.el) {
      var t = txt(sd.el), m = t.match(/^(buy|sell|kauf(?:en)?|verkauf(?:en)?)\s+([\d.,]+)\s+(\S+)\s+(\S+)/i);
      out.senden = kurz(sd.el, { quelle: sd.quelle, disabled: !!(sd.el.disabled || attr(sd.el, 'aria-disabled') === 'true' || sd.el.closest('[aria-disabled="true"],[disabled]')),
                                 seite: m ? (/^(buy|kauf)/i.test(m[1]) ? 'buy' : 'sell') : null,
                                 menge: m ? m[2] : null, symbol: m ? m[3] : null, typ: m ? m[4] : null });
    } else out.senden = null;
    out.seite = out.senden && out.senden.seite ? out.senden.seite : null;
    out.bereit = !!(out.senden && out.senden.seite && out.senden.menge);   // Lesung 00:17: nach der Order 'Start creating order' = keine Seite gewählt
    out.notiz = out.notiz.concat(kauf.notiz, verk.notiz, menge.notiz, sd.notiz);
    return out;
  }

  // ── Toasts (Meldungs-Stapel unten) ─────────────────────────────────────────
  function toasts() {
    var gruppen = [];
    alle('[data-name^="toast-group-expand-button-"]').forEach(function (b) {
      var name = attr(b, 'data-name').replace('toast-group-expand-button-', '');
      var zu = document.querySelector('[data-name="toast-group-close-button-' + name + '"]');
      // Gruppe = der höchste Vorfahr (≤ 6 Ebenen), der KEINE andere Toast-Gruppe enthält (Live 29.09.2026: ohne diese Grenze lief
      // die Suche bis zur gemeinsamen Toast-Liste hoch, und jede Gruppe meldete die Texte aller anderen)
      var g = b, i = 0;
      while (g.parentElement && i < 3 && !/^(BODY|HTML|SECTION)$/.test(g.parentElement.tagName)) {   // TV: Knopf → Steuerleiste → toastGroup
        var hoeher = g.parentElement;
        var fremd = alle('[data-name^="toast-group-expand-button-"]', hoeher).some(function (x) { return x !== b; });
        if (fremd) break;
        g = hoeher; i++;
      }
      if (g === b) g = b.parentElement;
      var texte = [];
      if (g) {
        var lauf = document.createTreeWalker(g, NodeFilter.SHOW_TEXT);
        var k;
        while ((k = lauf.nextNode()) && texte.length < 30) {
          var s = String(k.nodeValue || '').replace(/\s+/g, ' ').trim();
          var el = k.parentElement;
          if (!s || !el || b.contains(el) || (zu && zu.contains(el)) || !sichtbar(el)) continue;
          texte.push({ text: s.slice(0, 80), rect: rect(el) });
        }
      }
      if (!sichtbar(b) && !texte.length) return;   // leere Gruppe ohne Knopf im Bild
      gruppen.push({ gruppe: name, offen: attr(b, 'aria-expanded') === 'true', mehr: sichtbar(b) ? kurz(b) : null,
                     zu: zu && sichtbar(zu) ? kurz(zu) : null, rect: g && sichtbar(g) ? rect(g) : null, texte: texte });
    });
    // Rückfall ohne Gruppen-Knopf (erste echte Lesung: laut Spur 2 Toasts, gruppen leer): Container, deren Klasse mit 'toastGroup-'
    // beginnt (gehasht nur hinten), sichtbare Blatt-Texte einsammeln
    if (!gruppen.some(function (gr) { return gr.texte.length; })) {
      alle('[class*="toastGroup-"],[class*="toastListInner-"]').filter(sichtbar).slice(0, 6).forEach(function (c) {
        if (gruppen.some(function (gr) { return gr._el && (gr._el.contains(c) || c.contains(gr._el)); })) return;
        var texte = [], lauf = document.createTreeWalker(c, NodeFilter.SHOW_TEXT), k;
        while ((k = lauf.nextNode()) && texte.length < 20) {
          var t = String(k.nodeValue || '').replace(/\s+/g, ' ').trim(), el = k.parentElement;
          if (t && el && sichtbar(el)) texte.push({ text: t.slice(0, 80), rect: rect(el) });
        }
        if (texte.length) gruppen.push({ gruppe: 'unbekannt', offen: null, mehr: null, zu: xIn(c), rect: rect(c), texte: texte, quelle: 'klasse:toastGroup' });
      });
    }
    var log = alle('[role="log"]').map(function (l) { return { text: txt(l).slice(0, 400), live: attr(l, 'aria-live') }; })
      .filter(function (l) { return l.text; });
    return { gruppen: gruppen, log: log };
  }

  // ── Dialoge / Popups / Overlays mit ihrem X ────────────────────────────────
  function xIn(box) {
    var r = box.getBoundingClientRect();
    var kand = alle('button,[role="button"],[data-name*="close"],[aria-label]', box).filter(sichtbar).filter(function (e) {
      var q = e.getBoundingClientRect();
      var eck = (r.right - q.right) <= 70 && (q.top - r.top) <= 70 && q.width <= 60 && q.height <= 60;
      var wort = RX_SCHLIESSEN.test(txt(e) + ' ' + attr(e, 'aria-label') + ' ' + attr(e, 'data-name') + ' ' + attr(e, 'title'));
      return eck && (wort || /close/i.test(attr(e, 'data-name')));
    });
    kand = kand.filter(function (e) { return !kand.some(function (f) { return f !== e && e.contains(f); }); });
    return kand.length === 1 ? kurz(kand[0]) : (kand.length ? { mehrdeutig: kand.length } : null);
  }
  function dialoge() {
    var gesehen = [];
    var out = [];
    alle('[role="dialog"],[role="alertdialog"],[data-dialog-name],[aria-modal="true"]').filter(sichtbar).forEach(function (d) {
      if (gesehen.some(function (g) { return g.contains(d); })) return;
      gesehen.push(d);
      // Knöpfe mit data-name (Aufnahme 00:52: „Close position"-Dialog → [data-name=submit-button]); submit extra für den Bestätigungs-Klick
      var kn = alle('button[data-name],[role="button"][data-name]', d).filter(sichtbar).slice(0, 8).map(function (b) { return kurz(b); });
      var sub = kn.filter(function (b) { return /submit|confirm|ok|apply/i.test(b.dn); })[0] || null;
      out.push({ dn: attr(d, 'data-name'), name: attr(d, 'data-dialog-name'), role: attr(d, 'role'), rect: rect(d),
                 titel: txt(d.querySelector('h1,h2,h3,[class*="title"]')).slice(0, 60), text: txt(d).slice(0, 120), x: xIn(d), knoepfe: kn, submit: sub });
    });
    // Overlays ohne Dialog-Rolle (Werbung, Broker-Hinweise): fest positioniert, groß, weit oben im Stapel — nur mit X gemeldet
    alle('body > div, body > section, body > aside').forEach(function (e) {
      if (out.length >= 12 || gesehen.some(function (g) { return g.contains(e) || e.contains(g); }) || !sichtbar(e)) return;
      var st = window.getComputedStyle(e), r = e.getBoundingClientRect();
      if (!(st.position === 'fixed' || st.position === 'absolute') || (parseInt(st.zIndex, 10) || 0) < 100 || r.width * r.height < 40000) return;
      if (e.querySelector('[data-name^="toast-group-"]')) return;
      var x = xIn(e);
      if (x) out.push({ dn: attr(e, 'data-name'), name: '', role: 'overlay', rect: rect(e), titel: '', text: txt(e).slice(0, 120), x: x });
    });
    return out;
  }

  // ── Konto (Account-Manager) ────────────────────────────────────────────────
  /* KONTO-DROPDOWN (Aufnahme 00:52 pc-usq1i6, T3): Tradovate rendert die Liste OHNE role — Zeilen sind div ~228×32 im 32-px-Raster
   * ([78,600|632|664|696,228,32]), darin ein span mit der Kontonummer; Gruppen-Köpfe (z. B. „Apex") stehen in derselben Spalte ohne
   * Nummer. Direkt nach dem Öffnen kommt ein focusin auf einen gleich breiten Container weiter oben ([6,30,228,32]) — bei gleicher
   * Nummer gewinnt deshalb die Zeile, die dem Umschalter am nächsten liegt. -> {zeilen:[{text, kontonr, rect, aktiv}], gruppen:[{text, rect}]} */
  function kontoZeilen(schalterEl) {
    var sr = schalterEl ? schalterEl.getBoundingClientRect() : null;
    var kand = [];
    alle('div,li,button,a,[tabindex]').forEach(function (e) {
      if (!sichtbar(e) || (schalterEl && (e === schalterEl || schalterEl.contains(e) || e.contains(schalterEl)))) return;
      if (e.closest('table,[data-name="order-panel"],#footer-chart-panel,[data-name="symbol-list-wrap"],[data-name="tree"],[data-name^="toast-group-"]')) return;
      var r = e.getBoundingClientRect();
      if (sr && Math.abs(r.left - sr.left) > 320) return;           // Liste klappt am Umschalter auf, nicht irgendwo im Chart
      if (r.height < 24 || r.height > 44 || r.width < 150 || r.width > 340) return;
      var t = entdoppeln(txt(e)); if (!RX_KONTO.test(t) || t.length > 60) return;
      if (/[A-Z]\d{4}\d*[.,]\d/.test(t.replace(/\s/g, ''))) return;    // Symbol + Kurs ohne Leerzeichen ('NQZ202630,500.75') ist kein Konto
      kand.push({ el: e, t: t, r: r });
    });
    // innerste passende Zeile (nicht die Liste, die mehrere Zeilen umschließt — die ist höher und fiele ohnehin raus)
    kand = kand.filter(function (k) { return !kand.some(function (m) { return m !== k && k.el.contains(m.el); }); });
    var jeNr = {};
    kand.forEach(function (k) {
      var nr = (k.t.match(/[A-Z]{2,}[A-Z0-9_-]*?\d{5,}/) || [k.t])[0];
      var d = sr ? Math.abs(k.r.top - sr.top) : 0;
      if (!jeNr[nr] || d < jeNr[nr].d) jeNr[nr] = { k: k, d: d, nr: nr };
    });
    var zeilen = Object.keys(jeNr).map(function (nr) { var k = jeNr[nr].k;
      return { text: k.t, kontonr: nr, rect: rect(k.el), aktiv: attr(k.el, 'aria-selected') === 'true' || attr(k.el, 'aria-checked') === 'true' || null }; })
      .sort(function (a, b) { return a.rect[1] - b.rect[1]; });
    var gruppen = [];
    if (zeilen.length) {
      var x0 = zeilen[0].rect[0], y0 = zeilen[0].rect[1] - 120, y1 = zeilen[zeilen.length - 1].rect[1] + 40;
      alle('div,span').forEach(function (e) {
        if (gruppen.length >= 10 || e.children.length > 2 || !sichtbar(e)) return;
        var r = e.getBoundingClientRect(), t = entdoppeln(txt(e));
        if (Math.abs(r.left - x0) > 14 || r.top < y0 || r.top > y1 || r.height < 14 || r.height > 40 || !t || t.length > 30 || RX_KONTO.test(t) || /\d{4,}/.test(t)) return;
        if (gruppen.some(function (g) { return g.text === t; })) return;
        gruppen.push({ text: t, rect: rect(e) });
      });
    }
    return { zeilen: zeilen.slice(0, 40), gruppen: gruppen };
  }
  function konto(texte) {
    // Lesung 00:22:50: '[data-name*=account] button' traf 'Column setup' in der Account-Manager-Tabelle — jetzt zuerst die KONTONUMMER
    // als Text (unser eigener Anker, z. B. 'PAAPEX6416990000009USD' [72,510]), data-name-Wege nur noch mit Kontonummer im Text
    var s = suche([{ q: 'text:Kontonummer', sel: 'button,[role="button"]', text: RX_KONTO,
                     filter: function (e) { return e.getBoundingClientRect().top > window.innerHeight * 0.3 && !e.closest('[data-name="order-panel"]'); } },
                   { q: 'dn:account-manager-account-select', sel: '[data-name="account-manager-account-select"]' },
                   { q: 'dn*account button', sel: '[data-name*="account"][role="button"], [data-name*="account"] button', text: RX_KONTO }]);
    var eintraege = alle('[role="listbox"] [role="option"],[role="menu"] [role="menuitem"],[data-name="menu-inner"] [role="option"],[data-name="popup-menu-container"] [role="menuitem"]')
      .filter(sichtbar).slice(0, 40).map(function (e) { return kurz(e); });
    var gruppen = [];
    if (!eintraege.length) { var kl = kontoZeilen(s.el); eintraege = kl.zeilen; gruppen = kl.gruppen; }
    // External IDs als Text suchen (Reader-Lehre 21.09.2026: eine 17-stellige Kontonummer kann TradingView nicht umbenennen)
    var treffer = [];
    var nadeln = (texte || []).map(function (x) { return String(x || '').replace(/[^a-z0-9]/gi, '').toUpperCase(); })
      .filter(function (n) { return n.length >= 3; });
    if (nadeln.length && document.body) {
      var lauf = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), k, gesehen = [];
      while ((k = lauf.nextNode()) && treffer.length < 40) {
        var norm = String(k.nodeValue || '').replace(/[^a-z0-9]/gi, '').toUpperCase();
        if (norm.length < 3 || !nadeln.some(function (n) { return norm.indexOf(n) >= 0; })) continue;
        var el = k.parentElement;
        if (!el || gesehen.indexOf(el) >= 0 || !sichtbar(el)) continue;
        gesehen.push(el);
        treffer.push(kurz(el, { liste: !!el.closest('[role="listbox"],[role="menu"],[data-name="menu-inner"],[data-name="popup-menu-container"]') }));
      }
    }
    // Broker-Leiste unten (erste echte Lesung 29.09.2026): #footer-chart-panel mit Knopf aria 'Open account manager' (Text = Broker,
    // z. B. 'Tradovate') und [data-name=toggle-visibility-button] 'Open panel'/'Close panel'. Ist das Panel zu, steht die Kontonummer
    // NICHT auf dem Schirm — dann ehrlich 'panel_zu' statt eines leeren Kontos.
    var leiste = document.getElementById('footer-chart-panel');
    var mgr = suche([{ q: 'aria:account manager', sel: '#footer-chart-panel button[aria-label], button[aria-label]', text: /account\s*manager|konto(-|\s*)?manager|kontoverwaltung/i }]);
    var tog = document.querySelector('#footer-chart-panel [data-name="toggle-visibility-button"], [data-name="toggle-visibility-button"]');
    var togA = tog ? (attr(tog, 'aria-label') || attr(tog, 'title')) : '';
    // Lesung 00:22: offen heißt der Knopf 'Collapse panel' (zu: 'Open panel'), der Manager-Knopf 'Close account manager' / 'Open account manager'
    var ZU_RX = /open|öffnen|oeffnen|einblenden|show|expand|aufklappen|ausklappen|maximi/i, OFFEN_RX = /close|schlie|ausblenden|hide|minim|collapse|einklappen|zuklappen/i;
    var panel = tog ? (OFFEN_RX.test(togA) ? 'offen' : ZU_RX.test(togA) ? 'zu' : null) : null;
    var mgrA = mgr.el ? attr(mgr.el, 'aria-label') : '';
    if (!panel && mgrA) panel = /^(close|schlie)/i.test(mgrA) ? 'offen' : /^(open|öffnen|oeffnen)/i.test(mgrA) ? 'zu' : null;
    if (!panel) panel = tog || mgr.el ? 'unklar' : null;
    var schalter = s.el ? kurz(s.el, { quelle: s.quelle }) : null;
    // Lesung 00:22: textContent las 'PAAPEX6416990000009USDPAAPEX6416990000009USD' (versteckter Doppel-Text) — entdoppeln, Nummer extra
    var aktivText = s.el ? entdoppeln(txt(s.el)).slice(0, 60) : '';
    var kontonrM = aktivText.match(/[A-Z]{2,}[A-Z0-9_-]*?\d{5,}/);
    eintraege.forEach(function (e) { e.text = entdoppeln(e.text); });
    eintraege.forEach(function (e) {
      var n1 = String(e.text || '').replace(/[^a-z0-9]/gi, '').toUpperCase(), n2 = aktivText.replace(/[^a-z0-9]/gi, '').toUpperCase();
      e.aktiv = e['aria-selected'] === 'true' || e['aria-checked'] === 'true' || (!!n1 && !!n2 && (n1.indexOf(n2) >= 0 || n2.indexOf(n1) >= 0));
    });
    if (schalter) schalter.text = entdoppeln(schalter.text);
    // offen = mindestens zwei Zeilen oder eine, die nicht das aktive Konto ist (nur die aktive Nummer irgendwo reicht nicht)
    var offenListe = eintraege.length >= 2 || (eintraege.length === 1 && !eintraege[0].aktiv);
    return { schalter: schalter, aktiv: aktivText, kontonr: kontonrM ? kontonrM[0] : null, gruppen: gruppen, liste_offen: offenListe, eintraege: eintraege, treffer: treffer, notiz: s.notiz,
             broker: mgr.el ? txt(mgr.el).slice(0, 30) : (leiste ? txt(leiste).slice(0, 30) : ''), manager_knopf: mgr.el ? kurz(mgr.el) : null,
             panel: panel, panel_knopf: tog && sichtbar(tog) ? kurz(tog) : null,
             hinweis: (!s.el && !treffer.length && panel === 'zu') ? 'Broker-Panel zu — Kontonummer nicht sichtbar (panel_knopf öffnet es)' : null };
  }


  // ── Zahlen DE/EN (wie zahlAusText im Reader / tv_zahl_lesen im Bot) ─────────
  function zahl(t) {
    var z = String(t == null ? '' : t).replace(/−/g, '-').replace(/[^\d.,\-]/g, '');
    if (!/\d/.test(z)) return null;
    if (z.indexOf(',') >= 0 && z.indexOf('.') >= 0) {
      var dez = z.lastIndexOf(',') > z.lastIndexOf('.') ? ',' : '.';
      z = z.split(dez === ',' ? '.' : ',').join('').replace(dez, '.');
    } else if (/^-?\d{1,3}([.,]\d{3})+$/.test(z)) z = z.replace(/[.,]/g, '');
    else z = z.replace(',', '.');
    var n = Number(z);
    return isFinite(n) ? n : null;
  }
  function seiteNorm(t) {
    var u = String(t || '').trim().toLowerCase();
    if (/^(buy|kauf|long)/.test(u)) return 'buy';
    if (/^(sell|verkauf|short)/.test(u)) return 'sell';
    return null;
  }

  // ── Tabellen: Positionen + Orders (td[data-label], Spaltennamen wie im Reader) ─
  var SP = {
    symbol: ['Symbol'], seite: ['Seite', 'Side'], menge: ['Menge', 'Anz.', 'Anzahl', 'Qty', 'Quantity'],
    avg: ['Durchschn. Ausführungspreis', 'Durchschnittlicher Erfüllungspreis', 'Ø Ausführungspreis', 'Avg Fill Price', 'Avg. Fill Price'],
    pnl: ['Unrealisierter G&V', 'Profit', 'Unrealized P&L', 'P&L', 'G&V'],
    typ: ['Typ', 'Type', 'Auftragsart', 'Order Type'], status: ['Status'],
    preis: ['Limitpreis', 'Limit-Preis', 'Limit Price', 'Preis', 'Price', 'Stopp-Preis', 'Stop Price'],
    id: ['Order-ID', 'Order ID', 'Auftrags-ID', 'Auftragsnummer', 'Order Id']
  };
  function sp(z, namen) { for (var i = 0; i < namen.length; i++) { var v = z[namen[i]]; if (v != null && String(v).trim() !== '') return String(v).trim(); } return null; }
  var RX_ZU = /close|schlie(ß|ss)en|flatten|glattstellen|cancel|stornieren|abbrechen|^[×✕✖]$/i;
  function zeilenKnopf(tr, rx) {
    var k = alle('button,[role="button"],[data-name],[aria-label],[title]', tr).filter(function (e) {
      return rx.test(attr(e, 'aria-label') + ' ' + attr(e, 'title') + ' ' + attr(e, 'data-name') + ' ' + txt(e));
    });
    k = k.filter(function (e) { return !k.some(function (f) { return f !== e && e.contains(f); }); });
    var sicht = k.filter(sichtbar);
    return sicht.length === 1 ? kurz(sicht[0]) : sicht.length ? { mehrdeutig: sicht.length } : (k.length ? { versteckt: k.length } : null);
  }
  function tabellen() {
    var zeilen = [];
    var map = new Map();
    alle('td[data-label]').forEach(function (td) {
      var tr = td.closest('tr'); if (!tr) return;
      if (!map.has(tr)) { map.set(tr, {}); zeilen.push(tr); }
      map.get(tr)[attr(td, 'data-label')] = txt(td);
    });
    var pos = [], ord = [];
    zeilen.forEach(function (tr) {
      var z = map.get(tr), symbol = sp(z, SP.symbol);
      if (!symbol) return;
      var istOrder = !!(sp(z, SP.status) || sp(z, SP.id) || (sp(z, SP.typ) && !sp(z, SP.pnl)));
      // Unsichtbare Zeile (Panel zu) = womöglich VERALTET: Lesung 00:17 zeigte versteckt Avg 30556.75, der echte Fill war 30543.75
      var sb = sichtbar(tr);
      var basis = { symbol: symbol, seite: seiteNorm(sp(z, SP.seite)), menge: zahl(sp(z, SP.menge)), zeile_rect: sb ? rect(tr) : null,
                    sichtbar: sb, veraltet_moeglich: !sb, spalten: z };
      if (istOrder) {
        basis.typ = sp(z, SP.typ); basis.preis = zahl(sp(z, SP.preis)); basis.status = sp(z, SP.status);
        basis.cancel = zeilenKnopf(tr, /cancel|stornieren|abbrechen|^[×✕✖]$/i);
        ord.push(basis);
      } else {
        basis.avg = zahl(sp(z, SP.avg)); basis.pl_text = sp(z, SP.pnl);
        basis.close = zeilenKnopf(tr, RX_ZU);
        pos.push(basis);
      }
    });
    // „keine Position" vs „nicht lesbar" (T3 29.09.2026): ist ein Tabellenkopf der Art überhaupt sichtbar?
    var koepfe = alle('th,[role="columnheader"]').filter(sichtbar).map(function (h) { return txt(h); });
    function kopfHat(namen) { return koepfe.some(function (k) { return namen.some(function (n) { return k.indexOf(n) === 0; }); }); }
    var posSicht = pos.some(function (z) { return z.sichtbar; }) || kopfHat(SP.avg.concat(['Unrealized', 'Unrealisiert', 'Avg']));
    var ordSicht = ord.some(function (z) { return z.sichtbar; }) || kopfHat(SP.status.concat(SP.id, ['Limit Price', 'Limitpreis', 'Stop Price']));
    return { positionen: pos.slice(0, 20), orders: ord.slice(0, 20), positionen_sichtbar: posSicht, orders_sichtbar: ordSicht };
  }

  // ── Konto-Zusammenfassung (Label → Wert im Account Manager; Reader liesZusammenfassung) ─
  var RX_WERT = /^\(?\s*[+\-−–]?\s*(?:[$€£]|USD|EUR|GBP|CHF)?\s*[+\-−–]?\d[\d.,\s ']*\s*(?:%|USD|EUR|GBP|CHF|\$|€|£)?\s*\)?$/;
  function istWert(t) { return t.length >= 1 && t.length <= 24 && /\d/.test(t) && RX_WERT.test(t); }
  function istLabel(t) { return t.length >= 2 && t.length <= 40 && /[A-Za-zÄÖÜäöüß]/.test(t) && !/\d{4,}/.test(t); }
  function geldZahl(t) {
    var s0 = String(t || '').trim(), neg = /^\(.*\)$/.test(s0) || /^[\-−–]/.test(s0.replace(/^[\s($€£A-Z]+/, ''));
    var n = zahl(s0.replace(/[()]/g, ''));
    return n == null ? null : (neg && n > 0 ? -n : n);
  }
  function zusammenfassung() {
    var paare = {}, n = 0;
    function setze(l, v) { l = String(l || '').replace(/[:\s]+$/, '').trim(); v = String(v || '').trim(); if (!l || !v || paare[l] !== undefined || n >= 40) return; paare[l] = v; n++; }
    var zmap = new Map();
    alle('td[data-label]').forEach(function (td) { var tr = td.closest('tr'); if (!tr) return; if (!zmap.has(tr)) zmap.set(tr, []); zmap.get(tr).push([attr(td, 'data-label'), txt(td)]); });
    zmap.forEach(function (zellen) {
      if (zellen.some(function (c) { return SP.symbol.indexOf(c[0]) >= 0 || SP.seite.indexOf(c[0]) >= 0; })) return;
      zellen.forEach(function (c) { if (istLabel(c[0]) && istWert(c[1])) setze(c[0], c[1]); });
    });
    // Panel zu: dann nur die Fußleiste (#footer-chart-panel) — stehen dort Balance/Equity, kommen sie mit, sonst null (T3 29.09.2026)
    var wurzel = document.querySelector('[data-name="account-manager"],[data-name^="account-manager"],[class*="accountManager"]') || document.getElementById('footer-chart-panel');
    if (wurzel) {
      var w = wurzel, st = 0;
      while (w.parentElement && w !== document.body && st < 12) { var r = w.getBoundingClientRect(); if (r.height >= 120 && r.width >= window.innerWidth * 0.4) break; w = w.parentElement; st++; }
      alle('*', w).slice(0, 6000).forEach(function (el) {
        if (n >= 40 || el.children.length || el.closest('table,script,style,input,textarea')) return;
        var t = txt(el); if (!t || t.length > 70) return;
        var m = t.match(/^([^:\d]{2,40}):\s*(.+)$/);
        if (m && istLabel(m[1].trim()) && istWert(m[2].trim())) { setze(m[1], m[2]); return; }
        if (!istLabel(t)) return;
        var p = el.parentElement, kand = [el.nextElementSibling, el.previousElementSibling];
        if (p) { for (var i = 0; i < p.children.length; i++) if (p.children[i] !== el && kand.indexOf(p.children[i]) < 0) kand.push(p.children[i]); kand.push(p.nextElementSibling, p.previousElementSibling); }
        for (var j = 0; j < kand.length; j++) { var k = kand[j]; if (!k || k === el) continue; var v = txt(k); if (!v || v.length > 40) continue; if (istWert(v)) { setze(t, v); break; } if (istLabel(v) && k.parentElement === p) break; }
      });
    }
    if (!n) return null;
    // Welcher Reiter des Account Managers ist aktiv (T3 29.09.2026): 'Total P/L' (= heute) steht NUR im Reiter #summary; im Reiter
    // #positions zeigt die Kopfzeile nur Account Balance · Equity · Profit (Profit = offene Positionen, NICHT heute)
    var reiter = null;
    try { var rt = document.querySelector('#id_account-manager-tabs [role="tab"][aria-selected="true"]'); reiter = rt ? (rt.id || txt(rt)) : null; } catch (_) {}
    function nimm(rx, nicht) { for (var l in paare) { if (rx.test(l) && !(nicht && nicht.test(l))) return { label: l, text: paare[l], wert: geldZahl(paare[l]) }; } return null; }
    var UNREAL = /unreal|nicht\s*real|offen|open/i;
    // Tradovate 'Account summary' (Lesung 00:22:50): Account Balance · Equity · Net Liq · Open P/L · Total P/L · Profit · Margins.
    // Finn: 'Total P/L' ist das P&L von heute (ein Trade pro Tag) → today_pnl; 'Open P/L' = unrealisiert; 'Profit' eigenes Feld.
    return { balance: nimm(/^(account\s*)?balance$|kontostand|saldo|guthaben|^balance/i), equity: nimm(/equity|eigenkapital|net\s*liq|netto-?liquid/i),
             realisiert: nimm(/realized|realisiert/i, UNREAL), unrealisiert: nimm(/unrealized|unrealisiert|nicht\s*realisiert|open\s*p/i),
             today_pnl: nimm(/today|heutig|tages|^total\s*p\/?l|gesamt\s*g(&|u)v/i, UNREAL), profit: nimm(/^profit$|^gewinn$/i),
             net_liq: nimm(/net\s*liq|netto-?liquid/i), reiter: reiter, texte: paare };
  }

  // ── Symbolsuche (Kopfleiste + Such-Dialog) ─────────────────────────────────
  function symbolsuche() {
    var k = suche([{ q: 'id:header-toolbar-symbol-search', sel: '#header-toolbar-symbol-search' }, { q: 'aria:Symbol', sel: 'button[aria-label^="Symbol"]' }]);
    var dlg = document.querySelector('[data-name="symbol-search-items-dialog"]');
    var f = suche([{ q: 'data-role:search', sel: 'input[data-role="search"]' }, { q: 'dialog>input', sel: '[data-name="symbol-search-items-dialog"] input' },
                   { q: 'aria/placeholder:Suche', sel: 'input[aria-label*="uch"], input[placeholder*="uch"], input[aria-label*="earch"], input[placeholder*="earch"]' }]);
    var treffer = [];
    if (dlg && sichtbar(dlg)) {
      var gesehen = [];
      alle('*', dlg).forEach(function (e) {
        if (treffer.length >= 20 || e.children.length || !sichtbar(e)) return;
        var t = txt(e);
        if (!/^[A-Z][A-Z0-9!.]{1,11}$/.test(t)) return;          // Symbol-artiger Text (MNQZ2026, NQ1!, MNQ)
        var zeile = e.closest('[role="row"],[role="option"],[data-role="list-item"],a,[tabindex]') || e.parentElement;
        if (!zeile || gesehen.indexOf(zeile) >= 0) return;
        gesehen.push(zeile);
        treffer.push({ symbol: t, text: txt(zeile).slice(0, 80), rect: rect(zeile) });
      });
    }
    var leg = suche([{ q: 'aria:Change symbol', sel: 'button[aria-label]', text: /change symbol|symbol (ä|ae)ndern/i }]);
    // Watchlist rechts (Aufnahme 00:52: Finn wechselte NQ↔MNQ per Klick in [data-name=symbol-list-wrap] / [data-name=tree], Zeile ~80×27)
    var watch = [];
    var wl = document.querySelector('[data-name="symbol-list-wrap"]') || document.querySelector('[data-name="tree"]');
    if (wl && sichtbar(wl)) {
      var gs = [];
      alle('*', wl).forEach(function (e) {
        if (watch.length >= 30 || e.children.length || !sichtbar(e)) return;
        var t = txt(e); if (!/^[A-Z][A-Z0-9]{0,5}([FGHJKMNQUVXZ]\d{2,4}|\d!)$/.test(t)) return;
        var z = e, i = 0;
        while (z.parentElement && z.parentElement !== wl && i < 5) { var rr = z.getBoundingClientRect(); if (rr.width >= 150 && rr.height >= 18 && rr.height <= 44) break; z = z.parentElement; i++; }
        if (gs.indexOf(z) >= 0) return; gs.push(z);
        watch.push({ symbol: t, rect: rect(z), text_rect: rect(e) });
      });
    }
    return { knopf: k.el ? kurz(k.el, { quelle: k.quelle }) : null, legende: leg.el ? kurz(leg.el) : null, watchlist: watch, dialog: dlg && sichtbar(dlg) ? { rect: rect(dlg), x: xIn(dlg) } : null,
             feld: f.el ? kurz(f.el, { quelle: f.quelle }) : null, treffer: treffer, notiz: k.notiz.concat(f.notiz) };
  }

  // ── Order-Meldungen aus Toast-Texten (EN + DE, Regeln wie tv_meldung_preise im Bot) ─
  var RX_M_TP = /take[\s-]*profit|gewinnmitnahme/i, RX_M_SL = /stop[\s-]*loss|verlustbegrenzung|stop[\s-]*order/i;
  var RX_M_FILL = /executed|filled|position opened|ausgef(ü|ue)hrt|gef(ü|ue)llt/i;
  // Status aus dem Titel (Aufnahme 00:52: Close position → „Take Profit/Stop Loss order CANCELLED … Buy 1 at …" — das sind die
  // stornierten Bracket-Beine eines Shorts, keine neuen TP/SL; ohne Status sah das wie ein falsch zugeordnetes TP/SL aus)
  var RX_M_STORNO = /cancel+ed|canceled|storniert|abgebrochen|gel(ö|oe)scht/i, RX_M_ABGELEHNT = /reject|abgelehnt/i;
  var RX_M_GEAENDERT = /modified|ge(ä|ae)ndert/i, RX_M_PLATZIERT = /placed|platziert|submitted|aufgegeben/i;
  var RX_M_TITEL = /\border\b|auftrag|position opened|marktorder|limitorder|stop-?order/i;
  var RX_D_EN = /\b(buy|sell|kauf(?:en)?|verkauf(?:en)?)\s+([\d.,]+)\s*(?:@|\bat\b|\bzu\b|\bbei\b)\s*(\d[\d.,]*)/i;
  var RX_D_DE = /(?:(?:^|\s)(\d+)\s+)?\b(?:zu|bei|@)\s*(\d[\d.,]*)\s+(verkaufen|kaufen|verkauf|kauf)\b/i;
  function meldungenAus(texte) {
    var out = [], art = null, status = null;
    for (var i = 0; i < texte.length; i++) {
      var t = texte[i].text, r = texte[i].rect;
      // Jeder Titel setzt Art UND Status neu — die Preis-Zeile darunter gehört zu genau diesem Toast
      if (RX_M_TITEL.test(t) || RX_M_TP.test(t) || RX_M_SL.test(t)) {
        art = RX_M_TP.test(t) ? 'tp' : RX_M_SL.test(t) ? 'sl' : RX_M_FILL.test(t) ? 'fill' : 'order';
        status = RX_M_STORNO.test(t) ? 'storniert' : RX_M_ABGELEHNT.test(t) ? 'abgelehnt' : RX_M_FILL.test(t) ? 'ausgefuehrt'
               : RX_M_GEAENDERT.test(t) ? 'geaendert' : RX_M_PLATZIERT.test(t) ? 'platziert' : null;
        if (status === 'ausgefuehrt' && art !== 'fill') art = 'fill';
      }
      var m = t.match(RX_D_EN), seite = null, menge = null, preis = null;
      if (!m && i + 1 < texte.length && /^(buy|sell|kauf(en)?|verkauf(en)?)\s+[\d.,]+$/i.test(t) && /^(@|at|zu|bei)\s*\d/i.test(texte[i + 1].text)) {
        m = (t + ' ' + texte[i + 1].text).match(RX_D_EN); if (m) i++;               // 'Buy 4' + 'at 30,594.25' als zwei Knoten
      }
      if (m) { seite = seiteNorm(m[1]); menge = zahl(m[2]); preis = zahl(m[3]); }
      else { var d = t.match(RX_D_DE); if (d) { seite = /^verkauf/i.test(d[3]) ? 'sell' : 'buy'; menge = d[1] ? zahl(d[1]) : null; preis = zahl(d[2]); } }
      // aktiv = zählt als laufendes TP/SL bzw. echter Fill; stornierte/abgelehnte Meldungen bleiben zur Nachvollziehbarkeit stehen
      if (preis != null && preis > 0) out.push({ art: art, status: status, aktiv: status !== 'storniert' && status !== 'abgelehnt',
                                                seite: seite, menge: menge, preis: preis, text: t.slice(0, 80), rect: r });
    }
    return out;
  }


  /* ── AUFNAHME-MODUS (29.09.2026, Finns Idee): Finn klickt den Order-Ablauf im Puls-Chrome einmal selbst bis VOR den Kauf-Knopf,
   * jede Aktion wird mit Ziel + 3 Vorfahren + Zone mitgeschrieben — daraus werden die Signaturen gebaut. Capture-Listener auf
   * document (sehen jedes Ereignis zuerst, ändern nichts: kein preventDefault, kein stopPropagation). Zustand in
   * window.__prophosAufnahme, damit ein erneutes Evaluate derselben Datei die Listener weder doppelt setzt noch verliert.
   * Datenschutz: Passwort-/Kreditkartenfelder nie mit Wert, von der Tastatur nur Enter/Tab/Esc (kein Mitschnitt von Tipperei). */
  var AUFNAHME_MAX = 300;
  var AUFNAHME_TYPEN = ['pointerdown', 'mousedown', 'click', 'input', 'change', 'keydown', 'focusin'];
  function zoneVon(e) {
    try {
      if (e.closest('[data-name="order-panel"]')) return 'ticket';
      if (e.closest('[role="dialog"],[role="alertdialog"],[data-dialog-name]')) return 'dialog';
      if (e.closest('[data-name^="toast-group-"],[class*="toastGroup-"]')) return 'toast';
      if (e.closest('[role="listbox"],[role="menu"],[data-name="menu-inner"],[data-name="popup-menu-container"]')) return 'menu';
      if (e.closest('[data-name*="account"],#footer-chart-panel,[class*="accountManager"]')) return 'konto';
      if (e.closest('table,[role="table"],[role="grid"]')) return 'tabelle';
      var r = e.getBoundingClientRect();
      return r.top < 70 ? 'kopf' : r.left > window.innerWidth * 0.6 ? 'rechts' : r.top > window.innerHeight * 0.6 ? 'unten' : 'mitte';
    } catch (_) { return '?'; }
  }
  function geheim(el) {
    try {
      var t = String(el.type || '').toLowerCase(), ac = attr(el, 'autocomplete').toLowerCase();
      if (t === 'password' || /password|cc-|one-time-code/.test(ac) || /passw|kennwort|pin\b|cvc|cvv/i.test(attr(el, 'name') + ' ' + attr(el, 'aria-label') + ' ' + attr(el, 'placeholder'))) return true;
      // Login-Formulare/-Dialoge (Tradovate/TradingView-Anmeldung, T3 29.09.2026): JEDES Feld dort verborgen, auch Benutzername
      var f = el.closest('form'); if (f && f.querySelector('input[type="password"]')) return true;
      var d = el.closest('[role="dialog"],[role="alertdialog"],[data-dialog-name],[aria-modal="true"]');
      if (d && (d.querySelector('input[type="password"]') || /sign\s*in|log\s*in|anmeld|einloggen|login|passwort|password/i.test(txt(d).slice(0, 300)))) return true;
      return false;
    } catch (_) { return true; }
  }
  function aufnahmeKnoten(el) {
    if (!el || !el.tagName) return null;
    var o = { tag: el.tagName.toLowerCase(), dn: attr(el, 'data-name'), role: attr(el, 'role'), aria: attr(el, 'aria-label'), id: el.id || '',
              text: txt(el).slice(0, 60), rect: el.getBoundingClientRect ? rect(el) : null };
    if (typeof el.value === 'string') o.wert = geheim(el) ? '[verborgen]' : el.value.slice(0, 60);
    var zust = ['aria-expanded', 'aria-selected', 'aria-checked', 'aria-pressed', 'data-dialog-name', 'title', 'placeholder', 'type'];
    for (var i = 0; i < zust.length; i++) { var v = attr(el, zust[i]); if (v !== '') o[zust[i]] = v.slice(0, 60); }
    if (el.type === 'checkbox' || el.type === 'radio') o.checked = !!el.checked;
    return o;
  }
  // Tab-Kennung (sessionStorage): zeigt beim Stopp, ob Start und Stopp im selben Tab liefen (Aufnahme 00:36: 0 Ereignisse, Tab 'hidden')
  function tabId() {
    try { var id = sessionStorage.getItem('prophos_augen_tab'); if (!id) { id = 'a' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); sessionStorage.setItem('prophos_augen_tab', id); } return id; }
    catch (_) { return window.__prophosAugenTab || (window.__prophosAugenTab = 'w' + Math.random().toString(36).slice(2, 9)); }
  }
  function fokus() { try { return document.hasFocus(); } catch (_) { return null; } }
  function aufnahmeEintrag(ev) {
    var A = window.__prophosAufnahme; if (!A || !A.an) return;
    try {
      var typ = ev.type;
      A.roh = (A.roh || 0) + 1;                       // JEDES Ereignis vor den Filtern — 0 heißt: in diesem Tab kam gar nichts an
      if (typ === 'visibilitychange') { if (A.liste.length < AUFNAHME_MAX) A.liste.push({ n: A.liste.length + 1, t: Date.now() - A.t0, typ: 'sichtbarkeit', zone: '-', ziel: null, vorfahren: [], maus: null, wert: document.visibilityState }); return; }
      // mousedown nur, wenn kein pointerdown auf dasselbe Ziel direkt davor (sonst jeder Klick doppelt)
      if (typ === 'mousedown' && A.letztPd && A.letztPd.el === ev.target && Date.now() - A.letztPd.t < 150) return;
      if (typ === 'pointerdown') A.letztPd = { el: ev.target, t: Date.now() };
      if (typ === 'keydown' && !/^(Enter|Tab|Escape)$/.test(ev.key)) return;
      var ziel = ev.target && ev.target.nodeType === 1 ? ev.target : (ev.target && ev.target.parentElement);
      if (!ziel || eigen(ziel)) return;
      // input: pro Feld nur der letzte Stand (sonst 300 Einträge nach ein paar Tastendrücken)
      if (typ === 'input' && A.liste.length) {
        var letzt = A.liste[A.liste.length - 1];
        if (letzt.typ === 'input' && letzt._el === ziel) { letzt.wert = geheim(ziel) ? '[verborgen]' : String(ziel.value || '').slice(0, 60); letzt.t_ende = Date.now() - A.t0; return; }
      }
      if (A.liste.length >= AUFNAHME_MAX) { A.voll = true; return; }
      var vorfahren = [], p = ziel.parentElement;
      for (var i = 0; i < 3 && p && p !== document.body; i++) { vorfahren.push(aufnahmeKnoten(p)); p = p.parentElement; }
      var e = { n: A.liste.length + 1, t: Date.now() - A.t0, typ: typ, zone: zoneVon(ziel), ziel: aufnahmeKnoten(ziel), vorfahren: vorfahren,
                maus: (typeof ev.clientX === 'number' && typ !== 'keydown') ? [Math.round(ev.clientX), Math.round(ev.clientY)] : null };
      if (typ === 'keydown') e.taste = ev.key;
      if (typ === 'input' || typ === 'change') e.wert = geheim(ziel) ? '[verborgen]' : String(ziel.value == null ? '' : ziel.value).slice(0, 60);
      Object.defineProperty(e, '_el', { value: ziel, enumerable: false });   // nur für das Zusammenfassen, nie im JSON
      A.liste.push(e);
    } catch (_) {}
  }
  function aufnahme_start() {
    var A = window.__prophosAufnahme;
    if (A && A.an) return { ok: true, laeuft: true, eintraege: A.liste.length, roh: A.roh || 0, tab_id: A.tab_id, seit_ms: Date.now() - A.t0 };
    // WINDOW + capture: sieht jedes Ereignis als Allererstes, noch vor einem stopImmediatePropagation der Seite auf document/window
    A = window.__prophosAufnahme = { an: true, t0: Date.now(), liste: [], voll: false, lst: aufnahmeEintrag, url: location.href, roh: 0,
                                     tab_id: tabId(), sichtbar_start: document.visibilityState, fokus_start: fokus() };
    AUFNAHME_TYPEN.forEach(function (t) { window.addEventListener(t, A.lst, true); });
    document.addEventListener('visibilitychange', A.lst, true);
    return { ok: true, gestartet: true, t0: A.t0, tab_id: A.tab_id, sichtbar: A.sichtbar_start, fokus: A.fokus_start, url: location.href };
  }
  function aufnahme_stopp() {
    var A = window.__prophosAufnahme;
    if (!A) return { ok: true, verloren: true, ereignisse: [], hinweis: 'kein Aufnahme-Puffer (Seite neu geladen oder nie gestartet)' };
    AUFNAHME_TYPEN.forEach(function (t) { try { window.removeEventListener(t, A.lst, true); } catch (_) {} try { document.removeEventListener(t, A.lst, true); } catch (_) {} });
    try { document.removeEventListener('visibilitychange', A.lst, true); } catch (_) {}
    A.an = false;
    var liste = JSON.parse(JSON.stringify(A.liste));   // _el fällt raus (nicht aufzählbar)
    var o = { ok: true, verloren: false, v: VERSION, t0: A.t0, dauer_ms: Date.now() - A.t0, url: A.url, url_jetzt: location.href, voll: A.voll,
              anzahl: liste.length, roh: A.roh || 0, tab_id: A.tab_id, sichtbar_start: A.sichtbar_start, fokus_start: A.fokus_start,
              sichtbar_stopp: document.visibilityState, fokus_stopp: fokus(), geo: geo(), ereignisse: liste };
    window.__prophosAufnahme = null;
    // Rettungskopie (T3 29.09.2026: 119 Ereignisse verloren, weil der Upload scheiterte und der Puffer schon null war) — bleibt bis
    // zur nächsten Aufnahme bzw. bis die Seite neu lädt; aufnahme_letzte() liefert sie für „augen aufnahme senden"
    try { window.__prophosAufnahmeLetzte = o; } catch (_) {}
    return o;
  }
  function aufnahme_letzte() {
    var L = window.__prophosAufnahmeLetzte;
    return L ? L : null;
  }
  function aufnahme_stand() {
    var A = window.__prophosAufnahme;
    return A ? { ok: true, laeuft: !!A.an, eintraege: A.liste.length, roh: A.roh || 0, voll: A.voll, tab_id: A.tab_id, sichtbar: document.visibilityState, fokus: fokus(), seit_ms: Date.now() - A.t0 }
             : { ok: true, laeuft: false, tab_id: tabId() };
  }

  // ── Öffentliche Funktionen ─────────────────────────────────────────────────
  /* Stand für Puls: alles, was er vor und nach einem Klick braucht. opts.kontoTexte = External IDs (Suche als Text). */
  /* VERTRAG MIT T3 (29.09.2026, Route im Augen-Prozess): nur diese Schlüssel kommen durch — v, ts, url, titel, geo, sichtbar,
   * fokus, popups, konto, ticket, kauf_knopf, positionen, orders, toasts, konto_summary (+ fehler). Rechtecke [x, y, w, h] in
   * CSS-Pixeln. positionen/orders/konto_summary bleiben leer bzw. null, bis das Inventar die Selektoren liefert. ≤ ~50 KB. */
  var STAND_MAX = 48000;
  function stand(opts) {
    opts = opts || {};
    var fehler = [];
    var g = geo(); g.lang = document.documentElement.lang || '';
    var o = { v: VERSION, ts: Date.now(), url: location.href, titel: document.title, geo: g,
              sichtbar: document.visibilityState, fokus: (function () { try { return document.hasFocus(); } catch (_) { return null; } })(),
              popups: [], konto: null, ticket: null, kauf_knopf: null, positionen: [], orders: [], toasts: null, konto_summary: null };
    try { o.ticket = ticket(); o.kauf_knopf = (o.ticket && o.ticket.senden) || null; } catch (e) { fehler.push('ticket: ' + e); }
    try { o.toasts = toasts(); } catch (e) { fehler.push('toasts: ' + e); }
    try { o.popups = dialoge(); } catch (e) { fehler.push('popups: ' + e); }
    try { o.konto = konto(opts.kontoTexte); } catch (e) { fehler.push('konto: ' + e); }
    // Sichtbarkeit der Tabellen unter konto (Master 29.09.2026: KEINE neuen Top-Schlüssel — die Route in app.py bleibt unverändert,
    // sonst Backend-Neustart auf allen PCs): konto.positionen_sichtbar / konto.orders_sichtbar
    var ps = false, os_ = false;
    try { var tb = tabellen(); o.positionen = tb.positionen; o.orders = tb.orders; ps = tb.positionen_sichtbar; os_ = tb.orders_sichtbar; }
    catch (e) { fehler.push('tabellen: ' + e); }
    if (!o.konto) o.konto = {};
    o.konto.positionen_sichtbar = ps; o.konto.orders_sichtbar = os_;
    try { o.konto_summary = zusammenfassung(); } catch (e) { fehler.push('konto_summary: ' + e); }
    try { if (o.ticket) o.ticket.symbolsuche = symbolsuche(); } catch (e) { fehler.push('symbolsuche: ' + e); }
    try {
      if (o.toasts) {
        var ms = [];
        (o.toasts.gruppen || []).forEach(function (gr) { meldungenAus(gr.texte || []).forEach(function (m) { m.gruppe = gr.gruppe; ms.push(m); }); });
        (o.toasts.log || []).forEach(function (l) { meldungenAus([{ text: l.text, rect: null }]).forEach(function (m) { m.gruppe = 'log'; ms.push(m); }); });
        // erst_gesehen je Meldung (T3): Merker überlebt mehrfaches Evaluate im selben Tab (globalThis), neu geladen = neu
        var merk = globalThis.__prophosAugenGesehen = globalThis.__prophosAugenGesehen || {};
        var jetzt = Date.now();
        ms.forEach(function (m) { var k = (m.art || '') + '|' + m.seite + '|' + m.menge + '|' + m.preis + '|' + m.text; if (!merk[k]) merk[k] = jetzt; m.erst_gesehen = merk[k]; });
        o.toasts.meldungen = ms.slice(0, 20);
      }
    } catch (e) { fehler.push('meldungen: ' + e); }
    // Größen-Riegel: erst die langen Listen kürzen, nie die Knöpfe/Rechtecke
    try {
      if (JSON.stringify(o).length > STAND_MAX) {
        if (o.konto) { o.konto.treffer = (o.konto.treffer || []).slice(0, 10); o.konto.eintraege = (o.konto.eintraege || []).slice(0, 15); }
        if (o.toasts && o.toasts.gruppen) o.toasts.gruppen.forEach(function (gr) { gr.texte = (gr.texte || []).slice(0, 8); });
        if (o.toasts && o.toasts.log) o.toasts.log = o.toasts.log.slice(0, 3);
        if (o.ticket && o.ticket.typen) o.ticket.typen = o.ticket.typen.slice(0, 6);
        (o.positionen || []).concat(o.orders || []).forEach(function (z) { delete z.spalten; });
        if (o.konto_summary) delete o.konto_summary.texte;
        if (JSON.stringify(o).length > STAND_MAX) fehler.push('stand über ' + STAND_MAX + ' Zeichen');
      }
    } catch (e) { fehler.push('groesse: ' + e); }
    if (fehler.length) o.fehler = fehler;
    return o;
  }

  /* Inventar (Etappe 0): der relevante DOM EINMAL als JSON — daraus werden die Signaturen für Ticket/Konto/Toasts gebaut.
   * Alles Sichtbare mit data-name / role / aria-label / id / data-dialog-name, dazu Eingaben und Knöpfe, mit Zone. Gekappt. */
  function inventar(opts) {
    opts = opts || {};
    var max = opts.max || 600;
    var zonen = [
      ['ticket', '[data-name="order-panel"]'], ['dialog', '[role="dialog"],[role="alertdialog"],[data-dialog-name]'],
      ['toast', 'section,[data-name^="toast-group-"]'], ['menu', '[role="listbox"],[role="menu"],[data-name="menu-inner"],[data-name="popup-menu-container"]'],
      ['konto', '[data-name*="account"]'], ['tabelle', 'table,[role="table"],[role="grid"]']
    ];
    function zone(e) {
      for (var i = 0; i < zonen.length; i++) { try { var z = e.closest(zonen[i][1]); if (z && (i !== 2 || z.querySelector('[data-name^="toast-group-"]') || /^toast-group-/.test(attr(z, 'data-name')))) return zonen[i][0]; } catch (_) {} }
      var r = e.getBoundingClientRect();
      return r.top < 70 ? 'kopf' : r.left > window.innerWidth * 0.6 ? 'rechts' : r.top > window.innerHeight * 0.6 ? 'unten' : 'mitte';
    }
    var sel = 'button,[role],input,select,textarea,[data-name],[aria-label],[data-dialog-name],[id],th,td[data-label],label';
    var els = alle(sel).filter(sichtbar);
    var liste = [];
    for (var i = 0; i < els.length && liste.length < max; i++) {
      var e = els[i];
      var t = txt(e);
      var dn = attr(e, 'data-name'), ro = attr(e, 'role'), al = attr(e, 'aria-label');
      // Hüllen ohne eigene Merkmale mit viel Text sind Rauschen
      if (!dn && !ro && !al && !e.id && !/^(button|input|select|textarea|th|td|label)$/i.test(e.tagName)) continue;
      if (t.length > 120 && !dn && !ro) continue;
      var z = kurz(e, { zone: zone(e), ddn: attr(e, 'data-dialog-name') || undefined, dlabel: attr(e, 'data-label') || undefined,
                        title: attr(e, 'title') || undefined, ph: attr(e, 'placeholder') || undefined });
      liste.push(z);
    }
    // unsichtbare Kästchen/Schalter (TP/SL-Haken, 29.09.2026) — sichtbar() filtert sie, für die Signaturen brauchen wir sie trotzdem
    var kaestchen = alle('input[type="checkbox"],input[type="radio"],[role="switch"],[role="checkbox"]').slice(0, 60).map(function (e) {
      var r = e.getBoundingClientRect(), st = window.getComputedStyle(e);
      return kurz(e, { zone: zone(e), opacity: st.opacity, display: st.display, sichtbar: sichtbar(e),
                       eltern: e.parentElement ? (e.parentElement.tagName.toLowerCase() + ':' + txt(e.parentElement).slice(0, 30)) : '' });
    });
    var o = { ok: true, art: 'augen_inventar', v: VERSION, kaestchen: kaestchen, ts: Date.now(), url: location.href, titel: document.title,
              lang: document.documentElement.lang || '', sichtbar: document.visibilityState, geo: geo(),
              iframes: alle('iframe').map(function (f) { return { src: String(f.src || '').slice(0, 120), rect: sichtbar(f) ? rect(f) : null }; }),
              shadow: alle('*').filter(function (x) { return !!x.shadowRoot; }).slice(0, 20).map(function (x) { return x.tagName.toLowerCase(); }),
              anzahl: els.length, gekappt: els.length > liste.length, elemente: liste };
    try { o.stand = stand(opts); } catch (e2) { o.stand = { fehler: String(e2) }; }
    return o;
  }

  return { v: VERSION, version: VERSION, stand: stand, inventar: inventar,
           aufnahme_start: aufnahme_start, aufnahme_stopp: aufnahme_stopp, aufnahme_stand: aufnahme_stand, aufnahme_letzte: aufnahme_letzte };
})();
// Vertrag T3: globalThis.prophosAugen = { v, stand(), inventar() } — mehrfaches Ausführen setzt es einfach neu (idempotent).
// PROPHOS_AUGEN / augenStand / augenInventar bleiben als Alias.
globalThis.prophosAugen = PROPHOS_AUGEN;
function augenStand(opts) { return PROPHOS_AUGEN.stand(opts); }
function augenInventar(opts) { return PROPHOS_AUGEN.inventar(opts); }
