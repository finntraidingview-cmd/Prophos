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
  var VERSION = '0.3.0';   // 0.3.0 (29.09.2026, erste echte Lesung pc-usq1i6): TP/SL-Zustand, Konto-Leiste, Toast-Rückfall   // 0.2.0 (29.09.2026): Vertrag mit T3 — globalThis.prophosAugen, Schlüssel-Whitelist, popups, kauf_knopf

  // ── Grundwerkzeuge ─────────────────────────────────────────────────────────
  function sichtbar(el) {
    try {
      if (!el || !el.getBoundingClientRect) return false;
      var r = el.getBoundingClientRect();
      if (r.width < 3 || r.height < 3) return false;
      if (r.bottom < 0 || r.right < 0 || r.top > window.innerHeight || r.left > window.innerWidth) return false;
      var st = window.getComputedStyle(el);
      return st.visibility !== 'hidden' && st.display !== 'none' && st.opacity !== '0';
    } catch (_) { return false; }
  }
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
        if (z !== null) return { an: z, quelle: 'kaestchen:' + (kand[0].type || attr(kand[0], 'role') || kand[0].tagName.toLowerCase()) };
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
      return { da: true, beschriftung: kurz(sch[0]), an: z.an, an_quelle: z.quelle, feld: feld ? kurz(feld) : null };
    }
    out.tp = klammer(RX_TP, 'TP');
    out.sl = klammer(RX_SL, 'SL');
    var sd = suche([{ q: 'dn:place-and-modify-button', sel: '[data-name="place-and-modify-button"]' },
                    { q: 'text:Senden', sel: 'button,[role="button"]', text: RX_SENDEN, wurzel: w,
                      nicht: /buy-order-button|sell-order-button/ }], w);
    if (sd.el) {
      var t = txt(sd.el), m = t.match(/^(buy|sell|kauf(?:en)?|verkauf(?:en)?)\s+([\d.,]+)\s+(\S+)\s+(\S+)/i);
      out.senden = kurz(sd.el, { quelle: sd.quelle, seite: m ? (/^(buy|kauf)/i.test(m[1]) ? 'buy' : 'sell') : null,
                                 menge: m ? m[2] : null, symbol: m ? m[3] : null, typ: m ? m[4] : null });
    } else out.senden = null;
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
      out.push({ dn: attr(d, 'data-name'), name: attr(d, 'data-dialog-name'), role: attr(d, 'role'), rect: rect(d),
                 titel: txt(d.querySelector('h1,h2,h3,[class*="title"]')).slice(0, 60), text: txt(d).slice(0, 120), x: xIn(d) });
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
  function konto(texte) {
    var s = suche([{ q: 'dn:account-manager-account-select', sel: '[data-name="account-manager-account-select"]' },
                   { q: 'dn*account button', sel: '[data-name*="account"][role="button"],[data-name*="account"] button' },
                   { q: 'text:Kontonummer', sel: 'button,[role="button"]', text: RX_KONTO,
                     filter: function (e) { return e.getBoundingClientRect().top > window.innerHeight * 0.4; } }]);
    var eintraege = alle('[role="listbox"] [role="option"],[role="menu"] [role="menuitem"],[data-name="menu-inner"] [role="option"],[data-name="popup-menu-container"] [role="menuitem"]')
      .filter(sichtbar).slice(0, 40).map(function (e) { return kurz(e); });
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
    var panel = tog ? (/open|öffnen|oeffnen|einblenden|show/i.test(togA) ? 'zu' : /close|schlie|ausblenden|hide|minim/i.test(togA) ? 'offen' : 'unklar') : null;
    var schalter = s.el ? kurz(s.el, { quelle: s.quelle }) : null;
    return { schalter: schalter, aktiv: s.el ? txt(s.el).slice(0, 60) : '', eintraege: eintraege, treffer: treffer, notiz: s.notiz,
             broker: mgr.el ? txt(mgr.el).slice(0, 30) : (leiste ? txt(leiste).slice(0, 30) : ''), manager_knopf: mgr.el ? kurz(mgr.el) : null,
             panel: panel, panel_knopf: tog && sichtbar(tog) ? kurz(tog) : null,
             hinweis: (!s.el && !treffer.length && panel === 'zu') ? 'Broker-Panel zu — Kontonummer nicht sichtbar (panel_knopf öffnet es)' : null };
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
    // Größen-Riegel: erst die langen Listen kürzen, nie die Knöpfe/Rechtecke
    try {
      if (JSON.stringify(o).length > STAND_MAX) {
        if (o.konto) { o.konto.treffer = (o.konto.treffer || []).slice(0, 10); o.konto.eintraege = (o.konto.eintraege || []).slice(0, 15); }
        if (o.toasts && o.toasts.gruppen) o.toasts.gruppen.forEach(function (gr) { gr.texte = (gr.texte || []).slice(0, 8); });
        if (o.toasts && o.toasts.log) o.toasts.log = o.toasts.log.slice(0, 3);
        if (o.ticket && o.ticket.typen) o.ticket.typen = o.ticket.typen.slice(0, 6);
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

  return { v: VERSION, version: VERSION, stand: stand, inventar: inventar };
})();
// Vertrag T3: globalThis.prophosAugen = { v, stand(), inventar() } — mehrfaches Ausführen setzt es einfach neu (idempotent).
// PROPHOS_AUGEN / augenStand / augenInventar bleiben als Alias.
globalThis.prophosAugen = PROPHOS_AUGEN;
function augenStand(opts) { return PROPHOS_AUGEN.stand(opts); }
function augenInventar(opts) { return PROPHOS_AUGEN.inventar(opts); }
