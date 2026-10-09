/* PROPHOS-AUGEN FÜR TOPSTEPX (30.09.2026, Topstep-Komplett-Paket K1 — Finn: „eine Lösung für alles, immer nur so": Topstep wie
 * Orbit über das eigene Puls-Chrome per CDP, augen = Auge, Windows-Maus = Hand). Eigene Datei neben augen.js (TradingView/
 * Tradovate bleibt unberührt); T3 lädt sie wie augen.js commit-genau und legt sie per Runtime.evaluate als INHALT in den
 * topstepx.com-Tab.
 *
 * Vertrag (wie augen.js): globalThis.prophosAugen = { v, stand(), inventar() } — reines JSON, wirft nie, KLICKT NIE.
 * Rechtecke [x, y, w, h] in CSS-Pixeln relativ zum Viewport; geo trägt screenX/Y, outer/inner, devicePixelRatio.
 * Die Route puls_augen lässt nur bekannte Oberschlüssel durch (app.py puls_augen_saeubern): v, ts, url, titel, geo, sichtbar,
 * fokus, popups, konto, ticket, kauf_knopf, positionen, orders, toasts, konto_summary, fehler, seit 30.09.2026 auch die K1-Felder
 * kopf, positionen_sichtbar, flach (Vertrag T3, Whitelist von T1) — ≤ 60 KB je Zeile.
 *
 * STAND 0.1 (vor dem K0-Inventar): Grundgerüst + Toast-Lesung. Die Toasts sind durch Finns Bilder belegt (tsx-fill-toast.png,
 * tsx-bracket-toasts.webp, 30.09.2026): unten links, je Meldung Haken-Symbol, Titel „Order Filled" / „Order Placed", darunter
 * „+1 MNQZ26 Market" + „Execute Price: 30,592.25" bzw. „-1 MNQZ26 Stop Market @ 30,586.25" (SL) / „-1 MNQZ26 Limit @ 30,597.75"
 * (TP), X oben rechts. Gelesen wird deshalb NUR über diese Texte und die Geometrie (kein Klassen-/data-Anker geraten).
 * Konto-Auslöser, BAL/MLL, Manage brackets, Risk/Profit, Contract, Kauf-Knopf und Reiter kommen erst mit dem K0-Inventar
 * (puls_augen 'inventar_tsx_*') — bis dahin bleiben konto/ticket/kauf_knopf/konto_summary null, positionen/orders leer.
 * STAND 0.2 (30.09.2026, K1-Vertrag von T3): Gerüst für konto/kopf/positionen/positionen_sichtbar/flach — Felder da, Werte null,
 * bis die Anker aus dem K0-Inventar des ersten Topstep-PCs stehen (Abschnitt „K1 Lesen").
 * STAND 0.4 (01.10.2026, TSX-CHART-SONDE): chart_sonde() — nur lesend: Library-API im Chart-iframe, Preisbereich/Modus der
 * Haupt-Preisskala, Pane-Geometrie, Preis → Host-y (mit Gegenprobe), Order-/Positionslinien aus dem Chart-Modell; auch in inventar().
 * Dazu ticket.bracket (Bracket-Dialog lesen, Form mit T3 abgestimmt).
 * STAND 0.3 (30.09.2026, TSX-ANKER-K1): echte Anker aus dem K0-Inventar (puls_augen, 30.09.2026) für Konto-Auslöser, Kopfzeile,
 * „No Active Position" und die Konto-Liste (konto.liste für K2); ticket.anzeigen als Rohtext. Die Anzeige einer OFFENEN Position
 * ist noch nicht belegt (Inventar war flach). inventar(): Overlays (Liste/Dialog) zuerst, SVG-Innereien raus.
 * STAND 0.6 (05.10.2026, K4 — Finn: „unten auf Position gehen, Doppelklick auf Risk und da eine Zahl eingeben; das ist so viel
 * einfacher"): SL/TP NICHT mehr über das Ziehen im Chart, sondern über die Positions-Tabelle unten. Neu, nur lesend: ticket.reiter
 * (Reiter „Positions"), ticket.gitter (Tabelle mit Symbol, Position, Entry Price, Risk, To Make samt Bearbeiten-Zustand der Zellen),
 * ticket.k4 = Vertrag da; positionen liest jetzt eine OFFENE Position (Tabelle, sonst die Zeile „-6 @ 31,339.50" der Order-Karte).
 */
var PROPHOS_AUGEN_TSX = (function () {
  'use strict';
  var VERSION = 'tsx-0.6.1';

  // ── Grundwerkzeuge (wie augen.js) ──────────────────────────────────────────
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
  // T3s Aufnahme-Banner/-Rahmen gehören nicht zur Seite
  function eigen(el) { try { return !!(el && el.closest && el.closest('[data-name="prophos-aufnahme"]')); } catch (_) { return false; } }
  function rect(el) {
    var r = el.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  }
  // textContent statt innerText: innerText braucht Layout und liefert in einem verdeckten Tab Leeres (Reader-Fund 01.09.2026)
  // Null-Breite-Zeichen raus: MUI-Selects tragen ein „\u200b" in einem Hilfs-Span (K0-Inventar 30.09.2026: der Hüll-Text des Auslösers endet darauf)
  function txt(el) { return String((el && el.textContent) || '').replace(/[\u200b-\u200d\ufeff]/g, '').replace(/\s+/g, ' ').trim(); }
  function klasse(e) { var c = typeof e.className === 'string' ? e.className : (e.className && e.className.baseVal) || ''; return c.replace(/\s+/g, ' ').trim().slice(0, 80); }
  function hatKlasse(e, k) { try { return !!(e.classList && e.classList.contains(k)); } catch (_) { return false; } }
  function attr(el, n) { try { return el.getAttribute(n) || ''; } catch (_) { return ''; } }
  function alle(sel, wurzel) {
    try { return Array.prototype.slice.call((wurzel || document).querySelectorAll(sel)); } catch (_) { return []; }
  }
  // Geheime Felder nie mit Wert (wie augen.js 0.7.3): Passwortfeld oder jedes Feld in einem Login-Formular/-Dialog —
  // TopstepX hat eine eigene Anmeldeseite (/login, „PLATFORM LOGIN"), deren Felder nie nach puls_augen gehen dürfen
  function geheim(el) {
    try {
      var t = String(el.type || '').toLowerCase(), ac = attr(el, 'autocomplete').toLowerCase();
      if (t === 'password' || /password|cc-|one-time-code/.test(ac) || /passw|kennwort|pin\b|cvc|cvv/i.test(attr(el, 'name') + ' ' + attr(el, 'aria-label') + ' ' + attr(el, 'placeholder'))) return true;
      var f = el.closest('form'); if (f && f.querySelector('input[type="password"]')) return true;
      if (/\/login\b/i.test(location.pathname) && document.querySelector('input[type="password"]')) return true;
      var d = el.closest('[role="dialog"],[role="alertdialog"],[aria-modal="true"]');
      if (d && (d.querySelector('input[type="password"]') || /sign\s*in|log\s*in|anmeld|einloggen|login|passwort|password/i.test(txt(d).slice(0, 300)))) return true;
      return false;
    } catch (_) { return true; }
  }
  // Test-Anker, die TopstepX evtl. setzt — nur zum MITSCHREIBEN im Inventar/kurz(), nicht zum Suchen (Anker erst nach K0)
  function testid(el) { return attr(el, 'data-testid') || attr(el, 'data-test') || attr(el, 'data-cy') || attr(el, 'data-qa'); }
  function kurz(el, extra) {
    var o = { tag: el.tagName.toLowerCase(), role: attr(el, 'role'), aria: attr(el, 'aria-label'), id: el.id || '',
              text: txt(el).slice(0, 60), rect: rect(el) };
    var ti = testid(el); if (ti) o.testid = ti.slice(0, 60);
    if (typeof el.value === 'string') o.wert = geheim(el) ? (el.value ? '[verborgen]' : '') : el.value.slice(0, 30);
    var zust = ['aria-expanded', 'aria-selected', 'aria-checked', 'aria-pressed', 'aria-disabled', 'disabled', 'readonly', 'checked'];
    for (var i = 0; i < zust.length; i++) { var v = attr(el, zust[i]); if (v !== '') o[zust[i]] = v; }
    if (el.type === 'checkbox' || el.type === 'radio') o.checked = !!el.checked;
    if (extra) for (var k in extra) o[k] = extra[k];
    return o;
  }
  function geo() {
    return { innerWidth: window.innerWidth, innerHeight: window.innerHeight, outerWidth: window.outerWidth,
             outerHeight: window.outerHeight, screenX: window.screenX, screenY: window.screenY, dpr: window.devicePixelRatio || 1,
             scrollX: Math.round(window.scrollX || 0), scrollY: Math.round(window.scrollY || 0) };
  }
  function fokus() { try { return document.hasFocus(); } catch (_) { return null; } }
  /* Klick-Tauglichkeit eines Elements (für die Hand in Python, Regeln .826/.836: :hover allein ist kein Beweis — auch prüfen, WAS
   * am Zielpunkt oben liegt): disabled/readonly/aria-disabled und Verdeckung am Mittelpunkt per elementFromPoint.
   * verdeckt = das oberste Element am Mittelpunkt ist weder das Ziel noch sein Nachfahr/Vorfahr; oben = kurz() davon. */
  function zustand(el) {
    var o = { disabled: false, readonly: false, verdeckt: null, oben: null };
    try {
      o.disabled = !!el.disabled || attr(el, 'aria-disabled') === 'true' || (!!el.closest && !!el.closest('fieldset[disabled]'));
      o.readonly = !!el.readOnly || attr(el, 'aria-readonly') === 'true';
      var r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) { o.verdeckt = true; o.oben = 'ausserhalb'; return o; }
      var top = document.elementFromPoint(x, y);
      o.verdeckt = !(top && (top === el || el.contains(top) || top.contains(el)));
      if (o.verdeckt && top) o.oben = { tag: top.tagName.toLowerCase(), role: attr(top, 'role'), text: txt(top).slice(0, 40), rect: rect(top) };
    } catch (_) {}
    return o;
  }

  // ── Zahlen (TopstepX zeigt EN: „30,592.25"; DE-Schreibweise trotzdem erkannt, wie augen.js zahl) ─────────────
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

  // ── Toasts (Meldungen unten links) ─────────────────────────────────────────
  /* Titel = eigener Text genau „Order <Status>". Container = höchster Vorfahr (≤ 6 Ebenen, ≤ 720×300 px), der keinen ANDEREN Titel
   * enthält — so bekommt jede Meldung ihre eigenen Zeilen, auch wenn drei übereinander stehen. X = kleines klickbares Element oben
   * rechts im Container (Bild: X rechts oben, Titel links daneben). */
  var RX_TITEL = /^order\s+(filled|partially\s+filled|placed|rejected|cancel+ed|canceled|modified|updated|expired)$/i;
  var RX_ZEILE = /^([+\-−])\s*(\d+(?:[.,]\d+)?)\s+([A-Z][A-Z0-9.]*)\s+(stop\s+market|stop\s+limit|trailing\s+stop|market|limit|stop)(?:\s*@\s*([\d.,]+))?\s*$/i;
  var RX_PREIS = /(?:execute(?:d)?\s+price|fill(?:ed)?\s+price|avg\.?\s+price|price)\s*:?\s*([\d.,]+)/i;
  var RX_SCHLIESSEN = /close|schlie(ß|ss)en|dismiss|^[×✕✖x]$/i;
  function titelKnoten() {
    var out = [], lauf = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT), k;
    while ((k = lauf.nextNode()) && out.length < 40) {
      var s = String(k.nodeValue || '').replace(/\s+/g, ' ').trim(), el = k.parentElement;
      if (!s || !el || !RX_TITEL.test(s) || !sichtbar(el) || eigen(el)) continue;
      if (out.indexOf(el) < 0) out.push(el);
    }
    return out;
  }
  function containerZu(titel, alleTitel) {
    var best = null, g = titel, i = 0;
    while (g.parentElement && i < 6) {
      var hoeher = g.parentElement;
      if (/^(BODY|HTML)$/.test(hoeher.tagName)) break;
      var fremd = alleTitel.some(function (t) { return t !== titel && hoeher.contains(t); });
      if (fremd) break;
      var r = hoeher.getBoundingClientRect();
      if (r.width > 720 || r.height > 300) break;
      g = hoeher; i++;
      if (sichtbar(g)) best = g;
    }
    return best || titel.parentElement || titel;
  }
  function xInToast(box) {
    var r = box.getBoundingClientRect();
    var kand = alle('button,[role="button"],svg,[aria-label],[title],span,i,div', box).filter(sichtbar).filter(function (e) {
      var q = e.getBoundingClientRect();
      if (q.width > 44 || q.height > 44) return false;
      if ((r.right - q.right) > 60 || (q.top - r.top) > 50) return false;          // oben rechts in der Meldung
      var t = txt(e);
      var wort = RX_SCHLIESSEN.test(attr(e, 'aria-label') + ' ' + attr(e, 'title') + ' ' + testid(e)) || /^[×✕✖]$/.test(t);
      var knopf = /^(button)$/i.test(e.tagName) || attr(e, 'role') === 'button' || e.tagName.toLowerCase() === 'svg';
      var zeiger = (function () { try { return window.getComputedStyle(e).cursor === 'pointer'; } catch (_) { return false; } })();
      return (wort || knopf || zeiger) && t.length <= 2;
    });
    // SVG/Symbol → nächster klickbarer Vorfahr innerhalb der Meldung; Verschachtelte: nur den äußersten behalten
    kand = kand.map(function (e) {
      var k = e.closest && e.closest('button,[role="button"]');
      return (k && box.contains(k) && k !== box) ? k : e;
    });
    kand = kand.filter(function (e, i) { return kand.indexOf(e) === i; });
    kand = kand.filter(function (e) { return !kand.some(function (f) { return f !== e && f.contains(e); }); });
    if (!kand.length) return null;
    // mehrere: das der rechten oberen Ecke nächste
    kand.sort(function (a, b) {
      var qa = a.getBoundingClientRect(), qb = b.getBoundingClientRect();
      return ((r.right - qa.right) + (qa.top - r.top)) - ((r.right - qb.right) + (qb.top - r.top));
    });
    var x = kand[0];
    return kurz(x, { zustand: zustand(x), kandidaten: kand.length });
  }
  function status(titel) {
    var t = String(titel || '').toLowerCase();
    return /partially/.test(t) ? 'teilweise' : /filled/.test(t) ? 'ausgefuehrt' : /placed/.test(t) ? 'platziert' : /reject/.test(t) ? 'abgelehnt'
         : /cancel/.test(t) ? 'storniert' : /modified|updated/.test(t) ? 'geaendert' : /expired/.test(t) ? 'abgelaufen' : null;
  }
  /* Eine Meldung aus Titel + Zeilen. -> {art, status, aktiv, seite, menge, symbol, typ, preis, titel, text} | null
   * art: 'fill' (Order Filled, Preis aus „Execute Price") · 'stop' / 'limit' (Order Placed … @ Preis) · 'order' (sonst) */
  function meldungAus(titel, zeilen) {
    var st = status(titel), m = null, preis = null;
    for (var i = 0; i < zeilen.length; i++) {
      var z = zeilen[i];
      if (!m) { var mm = z.match(RX_ZEILE); if (mm) m = mm; }
      if (preis == null) { var pm = z.match(RX_PREIS); if (pm) preis = zahl(pm[1]); }
    }
    if (!m && preis == null) return null;
    var typ = m ? m[4].replace(/\s+/g, ' ').toLowerCase() : null;
    var seite = m ? (m[1] === '+' ? 'buy' : 'sell') : null;
    var p = (m && m[5]) ? zahl(m[5]) : preis;
    var art = st === 'ausgefuehrt' || st === 'teilweise' ? 'fill' : typ && /stop/.test(typ) ? 'stop' : typ === 'limit' ? 'limit' : 'order';
    return { art: art, status: st, aktiv: st !== 'storniert' && st !== 'abgelehnt' && st !== 'abgelaufen',
             seite: seite, menge: m ? zahl(m[2]) : null, symbol: m ? m[3].toUpperCase() : null, typ: typ,
             preis: p, titel: String(titel).slice(0, 40), text: zeilen.join(' | ').slice(0, 120) };
  }
  function toasts() {
    var titel = titelKnoten(), gruppen = [], meldungen = [];
    titel.forEach(function (t) {
      var box = containerZu(t, titel);
      if (gruppen.some(function (g) { return g._box === box; })) return;
      var zeilen = [], lauf = document.createTreeWalker(box, NodeFilter.SHOW_TEXT), k;
      while ((k = lauf.nextNode()) && zeilen.length < 12) {
        var s = String(k.nodeValue || '').replace(/\s+/g, ' ').trim(), el = k.parentElement;
        if (!s || !el || !sichtbar(el) || el === t || t.contains(el)) continue;
        zeilen.push(s.slice(0, 80));
      }
      var tt = txt(t), me = meldungAus(tt, zeilen), x = xInToast(box);
      gruppen.push({ _box: box, gruppe: 'tsx', titel: tt.slice(0, 40), rect: rect(box), zu: x, texte: zeilen.slice(0, 8) });
      if (me) { me.rect = rect(box); me.zu = x ? x.rect : null; meldungen.push(me); }
    });
    gruppen.forEach(function (g) { delete g._box; });
    // erst_gesehen je Meldung (wie augen.js): Merker überlebt mehrfaches Evaluate im selben Tab, neu geladen = neu
    try {
      var merk = globalThis.__prophosAugenTsxGesehen = globalThis.__prophosAugenTsxGesehen || {}, jetzt = Date.now();
      // 0.6.1 (Prüfer 06.10.2026): je Schlüssel {erst, zuletzt}; stand die Meldung > 15 s in keinem Blick, gilt sie beim Wiederkommen
      // als neu (gleich lautende Ablehnung oder Fill im nächsten Lauf desselben Tabs zählte sonst nie mehr). Zahlen-Einträge von tsx-0.5/0.6.0 werden ersetzt.
      meldungen.forEach(function (m) {
        var s = [m.art, m.status, m.seite, m.menge, m.symbol, m.typ, m.preis].join('|'), e = merk[s];
        if (!e || typeof e !== 'object' || jetzt - e.zuletzt > 15000) e = merk[s] = { erst: jetzt, zuletzt: jetzt };
        e.zuletzt = jetzt; m.erst_gesehen = e.erst;
      });
    } catch (_) {}
    return { gruppen: gruppen, meldungen: meldungen.slice(0, 20), bracket: bracketAus(meldungen) };
  }
  /* Bracket zur jüngsten Ausführung: TP = aktives Limit, SL = aktiver Stop — beide Gegenseite zum Fill und dasselbe Symbol
   * (Bild: Fill „+1 MNQZ26", SL „-1 MNQZ26 Stop Market @", TP „-1 MNQZ26 Limit @"). Ohne Fill: nur die Meldungen. */
  function bracketAus(ms) {
    var fills = ms.filter(function (m) { return m.art === 'fill' && m.aktiv; });
    if (!fills.length) return null;
    fills.sort(function (a, b) { return (b.erst_gesehen || 0) - (a.erst_gesehen || 0); });
    var f = fills[0], gegen = f.seite === 'buy' ? 'sell' : f.seite === 'sell' ? 'buy' : null;
    var bein = function (art) {
      var k = ms.filter(function (m) { return m.art === art && m.aktiv && m.seite === gegen && (!f.symbol || m.symbol === f.symbol); });
      k.sort(function (a, b) { return (b.erst_gesehen || 0) - (a.erst_gesehen || 0); });
      return k.length ? { preis: k[0].preis, menge: k[0].menge, typ: k[0].typ, rect: k[0].rect } : null;
    };
    return { fill: { preis: f.preis, menge: f.menge, seite: f.seite, symbol: f.symbol, typ: f.typ, rect: f.rect }, tp: bein('limit'), sl: bein('stop') };
  }

  // ── Dialoge / Popups (ARIA-Rollen, keine Seiten-Anker) ─────────────────────
  function dialoge() {
    var out = [];
    alle('[role="dialog"],[role="alertdialog"],[aria-modal="true"]').filter(sichtbar).forEach(function (d) {
      if (out.some(function (o) { return o._el.contains(d); })) return;
      var kn = alle('button,[role="button"]', d).filter(sichtbar).slice(0, 10).map(function (b) { return kurz(b); });
      out.push({ _el: d, role: attr(d, 'role'), rect: rect(d), titel: txt(d.querySelector('h1,h2,h3,h4')).slice(0, 60), text: txt(d).slice(0, 160), knoepfe: kn });
    });
    out.forEach(function (o) { delete o._el; });
    return out;
  }

  // ── K1 Lesen: Konto, Kopfzeile, Positionen (Vertrag T3, 30.09.2026) ────────
  /* Danach richtet sich der Bot:
   *   konto {aktiv: Text des Konto-Auslösers, kontonr: volle ID oder sichtbare Kennung, abgekuerzt: bool}
   *   kopf {balance|mll|rpl|upl: {text, wert}}   (Kopfzeile BAL / MLL / RP&L / UP&L) + kopf.balance_relativ (true|false|null)
   *   positionen [{symbol, seite: 'buy'|'sell', menge, avg, pl_text}]
   *   positionen_sichtbar: true, wenn der Positions-Bereich zu sehen ist (Zeilen oder „No Active Position")
   *   flach: true | false | null
   * Geraten wird nichts: ein falscher Anker hieße, der Bot hält ein fremdes Konto für das richtige oder ein offenes Konto für
   * flach. K1_ANKER false = Gerüst (alles null), true seit 0.3 (Anker belegt, s. „ANKER" unten). Die TEXTREGELN sind aus dem
   * UIA-Inventar belegt (B18/B22 in order_bot.py) und hier nachgebaut, damit JS und Python dieselben Texte gleich lesen. */
  var K1_ANKER = true;
  var KOPF_LABELS = { 'BAL': 'balance', 'MLL': 'mll', 'RP&L': 'rpl', 'UP&L': 'upl' };
  var RX_KOPF = /^(BAL|MLL|RP&L|UP&L)\s*:?\s*(.*)$/i;
  var RX_VORSATZ = /^[-−(]?\s*\$?\s*[-−]?$/;   // Knoten nur aus Vorzeichen/Klammer/„$" (Teil eines zerlegten Werts)
  var RX_AUSLOESER = /(?:\$\s*\d+(?:[.,]\d+)?\s*K\b|\d+(?:[.,]\d+)?\s*K\s+[A-Z])[^|]*\|\s*([A-Z0-9][A-Z0-9-]*)\s*(…|\.\.\.)?/i;
  var RX_OHNE_ID = /^\s*((?:\$\s*\d+(?:[.,]\d+)?\s*K\b|\d+(?:[.,]\d+)?\s*K\s+[A-Z])[^|$]*?)\s*\|?\s*(…|\.\.\.)?\s*$/i;
  var RX_KEINE_POS = /no active position|keine aktive position|no open position|no positions?\b/i;   // Varianten (09.10.2026)

  // US-Geldformat wie tsx_geld: '$11,079.66', '-$1,234.50', '$-7.00', '($12.50)' → Zahl | null. Komma ist hier IMMER Tausender
  // (nicht zahl(): die liest „12,5" deutsch — TopstepX schreibt US). Minus zählt überall VOR der ersten Ziffer („$" · „-7.00"
  // zusammengesetzt = „$-7.00" wäre sonst +7; an T3 für tsx_geld, 30.09.2026)
  function geld(t) {
    t = String(t == null ? '' : t).trim().replace(/−/g, '-');
    var neg = /^[^\d]*-/.test(t) || (t.charAt(0) === '(' && t.charAt(t.length - 1) === ')');
    var m = /\d[\d,]*(?:\.\d+)?/.exec(t);
    if (!m) return null;
    var v = Number(m[0].replace(/,/g, ''));
    return isFinite(v) ? (neg ? -v : v) : null;
  }

  // Kopfzeile wie tsx_kopf_werte: Texte in Lesereihenfolge → {balance, mll, rpl, upl}, je {text, wert} oder null.
  // Form 1 „BAL: $11,079.66" in einem Knoten; Form 2 Label und Wert im nächsten Knoten; B22 (UIA-Inventar): „BAL:" · „$" ·
  // „154,504.88" als DREI Knoten. Bei negativen Werten zerlegt TopstepX womöglich noch feiner: „RP&L:" · „-" · „$" · „50.00" oder
  // „(" · „$" · „12.50" · „)" (Master 30.09.2026, gleiche Regel an T3 für tsx_kopf_werte) — bis zu drei Vorsatz-Knoten (auch ein
  // Rest im Label-Knoten wie „RP&L: -") vor die Zahl setzen, eine schließende Klammer als eigenen Knoten anhängen. Ein Label
  // ohne lesbaren Wert darf ein späteres gleiches Label noch füllen (wie im Bot).
  function kopfAusTexten(namen) {
    var out = { balance: null, mll: null, rpl: null, upl: null };
    namen = (namen || []).map(function (n) { return String(n == null ? '' : n).trim(); });
    for (var i = 0; i < namen.length; i++) {
      var m = RX_KOPF.exec(namen[i]);
      if (!m) continue;
      var key = KOPF_LABELS[m[1].toUpperCase()];
      if (out[key] && out[key].wert !== null) continue;
      var text = m[2] || '', wert = text ? geld(text) : null;
      if (wert === null && i + 1 < namen.length) {
        var vor = RX_VORSATZ.test(text) ? text : '', j = i + 1;
        while (j < namen.length - 1 && j - i <= 3 && RX_VORSATZ.test(namen[j])) vor += namen[j++];
        text = RX_KOPF.test(namen[j]) ? vor : vor + namen[j];   // nie das nächste Label („MLL:") als Wert schlucken
        if (text.charAt(0) === '(' && text.charAt(text.length - 1) !== ')' && namen[j + 1] === ')') text += ')';
        wert = geld(text);
      }
      out[key] = { text: text || null, wert: wert };
    }
    return out;
  }

  // Konto-Auslöser wie tsx_konto_sichtbar / tsx_ist_ausloeser_text (B18/B22):
  //   „$150K EXPRESS | EXPRESS-V2-000000-00000000"  → volle Kennung, abgekuerzt false
  //   „$150K EXPRESS | EXPRESS-…"                    → sichtbare Kennung ohne Rest-Striche, abgekuerzt true (volle ID erst in der Liste)
  //   „$150K TRADING COMBINE |"                      → TopstepX lässt die Kennung bei langen Namen ganz weg (UIA-Inventar 11:24 UTC):
  //                                                    kontonr null, abgekuerzt true — auch hier beweist erst die Liste das Konto
  function kontoAusText(t) {
    t = String(t == null ? '' : t).replace(/\s+/g, ' ').trim();
    var m = RX_AUSLOESER.exec(t);
    if (m) { var k = m[1].toUpperCase(); return { aktiv: t, kontonr: m[2] ? k.replace(/-+$/, '') : k, abgekuerzt: !!m[2] }; }
    if (RX_OHNE_ID.test(t)) return { aktiv: t, kontonr: null, abgekuerzt: true };
    return { aktiv: t || null, kontonr: null, abgekuerzt: null };
  }

  // Sichtbare Blatt-Texte eines Bereichs in DOM-Reihenfolge (für die Kopfzeile: „BAL:" · „$" · „154,504.88")
  function blattTexte(w, max) {
    var out = [];
    try {
      var lauf = document.createTreeWalker(w, NodeFilter.SHOW_TEXT), k;
      while ((k = lauf.nextNode()) && out.length < (max || 120)) {
        var s = String(k.nodeValue || '').replace(/\s+/g, ' ').trim();
        if (s && sichtbar(k.parentElement)) out.push(s);
      }
    } catch (_) {}
    return out;
  }

  /* ANKER — belegt durch das K0-Inventar vom 30.09.2026 (puls_augen: inventar_tsx_grund, inventar_tsx_konto, stand_tsx; ein
   * Express-Konto, flach — Kontonummern stehen bewusst nicht im Code). TopstepX ist eine MUI-Oberfläche mit
   * durchgehenden data-testid — gesucht wird IMMER erst über data-testid, dann role, zuletzt über den Text:
   *   Konto-Auslöser  [data-testid="account-selector-input-select-account"] → darin [role="combobox"]. Text = Label · „|" · VOLLE
   *                   Kontonummer in drei Spans (optisch abgeschnitten, im DOM vollständig → abgekuerzt false)
   *   Kopfzeile       [data-testid="balance-display-value-amount" | "max-loss-display-value-amount" |
   *                   "realized-pnl-display-value-amount" | "unrealized-pnl-display-value-amount"], je zwei Spans („BAL:" · „$0.00");
   *                   MLL steht als „$-4,500.00" (Minus HINTER dem Dollar). Rückfall: Texte in [data-testid="navbar-container"]
   *   Liste offen     aria-expanded am Auslöser („false" im Grundzustand, „true" bei offener Liste)
   *   flach           [data-testid="order-card-display-value-no-position"] mit „No Active Position" (Order-Karte rechts) UND
   *                   [data-testid="order-card-click-button-close-position"] disabled — beides zusammen (Regel T3)
   *   Konto-Liste     li[role="option"] (416×30 px, Overlay am Ende von body), Text „$150K Express|EXPRESS-V2-…" bzw.
   *                   „$150K Trading Combine|150KTC-SKU-V2-… (Ineligible)"
   * NICHT belegt (das Inventar war flach, unten lief der Reiter „Trades", die Liste fiel dem Größendeckel zum Opfer):
   *   - die Anzeige einer OFFENEN Position: positionsZeilen/positionAus bleiben leer. Ohne „No Active Position" meldet stand()
   *     positionen_sichtbar false und flach null — nie geraten „nicht flach". ticket.anzeigen schreibt dafür alle
   *     order-card-display-value-* mit: die erste stand_tsx-Zeile mit offener Position liefert den Anker.
   *   - die Markierung in der Liste: aria-selected / Mui-selected sind MUI-Standard, im Inventar aber nicht zu sehen →
   *     markiert null, wenn in der ganzen Liste keines von beiden vorkommt. */
  function tid(id) { return '[data-testid="' + id + '"]'; }
  function q1(sel, wurzel) { var a = alle(sel, wurzel).filter(sichtbar); return a.length ? a[0] : null; }
  var KOPF_TID = { balance: 'balance-display-value-amount', mll: 'max-loss-display-value-amount',
                   rpl: 'realized-pnl-display-value-amount', upl: 'unrealized-pnl-display-value-amount' };
  // „$“ optional (09.10.2026): DLL-Konten heißen „150K DLL Combine|150KTC-SKU-V2-DLL-…“ ohne „$“ — vorher 0 Listenzeilen
  var RX_LISTE = /^\s*((?:\$\s*\d+(?:[.,]\d+)?\s*K\b|\d+(?:[.,]\d+)?\s*K\s+[A-Z])[^|]*?)\s*\|\s*([A-Z0-9][A-Z0-9-]{5,})\s*(?:\(([^)]*)\))?\s*$/i;

  function ankerKonto() {                            // Konto-Auslöser oben links
    var w = q1(tid('account-selector-input-select-account')) || q1(tid('account-selector-container'));
    return w ? (q1('[role="combobox"]', w) || w) : null;
  }
  function ankerKopf() { return q1(tid('navbar-container')); }                               // Kopfzeile (Rückfall über Texte)
  function ankerPositionen() { return q1(tid('order-card-display-value-no-position')); }   // „No Active Position"
  /* POSITIONEN UNTEN (05.10.2026, K4, Finn: „unten auf diese Leiste auf Position gehen, Doppelklicken auf Risk und da eine Zahl
   * eingeben"). Belegt durch das K0-Inventar (30.09.2026): die Reiterleiste unten ist rc-dock — je Reiter div.dock-tab-btn[role=tab]
   * mit id „rc-tabs-N-tab-<name>" (accountsTab, positionTab, ordersTab, trades, quotesTab, terminalTab) und aria-selected; die Tabellen
   * sind MUI-DataGrids (role=grid, Spaltenköpfe role=columnheader mit aria-label). Belegt durch Finns Bilder (05.10.2026): die Spalten
   * Time · Symbol („/MNQ") · Position („-6") · Entry Price („31,339.50") · Risk („$21.00" + Stift) · To Make („$198.00" + Stift) · P&L ·
   * Close (Kreuz), im Bearbeiten ein Zahlenfeld in der Zelle; in der Order-Karte „-6 @ 31,339.50".
   * NICHT live gelesen sind die Zellen selbst — darum dreifach gesucht: über data-field des Spaltenkopfs, sonst aria-colindex, sonst
   * die Lage (Zellenmitte unter dem Spaltenkopf). Fehlt etwas: grund, nichts geraten. Nur lesen — geklickt und getippt wird im Bot.
   * Die Close-Zelle wird nur als Rechteck gemeldet (close_rect), damit der Bot ihr fernbleiben kann. */
  var RX_KARTE_POS = /^([+\-−]?\s*\d+)\s*@\s*([\d.,]+)/;
  function reiterLesen() {
    var t = null;
    alle('[role="tab"]').filter(sichtbar).some(function (e) { if (/-tab-positionTab$/.test(e.id || '')) { t = e; return true; } return false; });
    if (!t) {
      var k = alle('[role="tab"]').filter(sichtbar).filter(function (e) { return hatKlasse(e, 'dock-tab-btn') && /^positions?$/i.test(txt(e)); });
      if (k.length === 1) t = k[0];
    }
    return { positions: t ? { rect: rect(t), aktiv: attr(t, 'aria-selected') === 'true', text: txt(t).slice(0, 20), zu: zustand(t) } : null };
  }
  function kopfName(h) { return (attr(h, 'aria-label') || txt(h)).replace(/\s+/g, ' ').trim().toLowerCase(); }
  function gitterLesen() {
    var o = { da: false, spalten: [], zeilen: [], grund: null };
    var g = null, koepfe = null;
    alle('[role="grid"]').filter(sichtbar).some(function (x) {
      var hs = alle('[role="columnheader"]', x), namen = hs.map(kopfName);
      if (namen.indexOf('risk') >= 0 && namen.indexOf('to make') >= 0) { g = x; koepfe = hs; return true; }
      return false;
    });
    if (!g) { o.grund = 'keine Tabelle mit den Spalten Risk und To Make im Bild (Reiter Positions offen?)'; return o; }
    o.da = true; o.rect = rect(g);
    var sp = {};
    koepfe.forEach(function (h) {
      var n = kopfName(h), r = h.getBoundingClientRect();
      if (n && !sp[n]) sp[n] = { field: attr(h, 'data-field') || null, col: attr(h, 'aria-colindex') || null, x0: r.left, x1: r.right };
    });
    o.spalten = Object.keys(sp).slice(0, 14);
    function zelle(row, name) {
      var c = sp[name]; if (!c) return null;
      var zs = alle('[role="cell"],[role="gridcell"]', row), z = null;
      if (c.field) zs.some(function (e) { if (attr(e, 'data-field') === c.field) { z = e; return true; } return false; });
      if (!z && c.col) zs.some(function (e) { if (attr(e, 'aria-colindex') === c.col) { z = e; return true; } return false; });
      if (!z) zs.some(function (e) { var r = e.getBoundingClientRect(), m = r.left + r.width / 2; if (r.width > 2 && m >= c.x0 && m <= c.x1) { z = e; return true; } return false; });
      return z;
    }
    // Risk / To Make: Wert, Rechteck der Zelle und Bearbeiten-Zustand (Zahlenfeld in der Zelle, Fokus genau auf diesem Feld)
    function feld(row, name) {
      var z = zelle(row, name); if (!z || !sichtbar(z)) return null;
      var inp = alle('input', z).filter(function (i) { var t = String(i.type || '').toLowerCase(); return t !== 'checkbox' && t !== 'radio' && t !== 'hidden'; })[0] || null;
      var t = txt(z);
      return { text: t.slice(0, 30), wert: inp ? null : geld(t), rect: rect(z), zu: zustand(z),
               edit: inp ? { offen: true, wert: String(inp.value == null ? '' : inp.value).slice(0, 20), rect: rect(inp), fokus: aktivIst(inp), typ: String(inp.type || '').slice(0, 12) }
                         : { offen: false } };
    }
    alle('[role="row"]', g).filter(sichtbar).forEach(function (row) {
      if (o.zeilen.length >= 12 || row.querySelector('[role="columnheader"]')) return;
      var zs = zelle(row, 'symbol'), zp = zelle(row, 'position');
      if (!zs || !zp) return;
      var sym = txt(zs).replace(/^\//, '').toUpperCase(), m = zahl(txt(zp));
      if (!sym || m === null) return;
      var ze = zelle(row, 'entry price'), zl = zelle(row, 'p&l'), zc = zelle(row, 'close');
      o.zeilen.push({ symbol: sym.slice(0, 16), menge: m, seite: m > 0 ? 'buy' : m < 0 ? 'sell' : null, avg: ze ? zahl(txt(ze)) : null,
                      pl_text: zl ? txt(zl).slice(0, 20) : null, risk: feld(row, 'risk'), to_make: feld(row, 'to make'),
                      close_rect: zc && sichtbar(zc) ? rect(zc) : null, rect: rect(row) });
    });
    return o;
  }
  // Offene Position(en) für den K1-Vertrag: erst die Tabelle unten, sonst die Zeile der Order-Karte („-6 @ 31,339.50", Symbol =
  // das Contract-Feld). Menge positiv, die Richtung steht in seite. Ohne beides: [] (dann bleibt flach null — nie geraten).
  function positionsZeilen() {
    var g = gitterLesen();
    if (g.da && g.zeilen.length) return g.zeilen.map(function (z) { return { symbol: z.symbol, seite: z.seite, menge: Math.abs(z.menge), avg: z.avg, pl_text: z.pl_text, quelle: 'tabelle' }; });
    var out = [];
    alle('[data-testid^="order-card-display-value-"]').filter(sichtbar).some(function (e) {
      var m = RX_KARTE_POS.exec(txt(e)); if (!m) return false;
      var n = zahl(m[1].replace(/\s/g, '')), c = contractLesen();
      if (n === null || n === 0) return false;
      out.push({ symbol: c && c.wert ? String(c.wert).toUpperCase().slice(0, 16) : null, seite: n > 0 ? 'buy' : 'sell', menge: Math.abs(n), avg: zahl(m[2]), pl_text: null, quelle: 'order_karte' });
      return true;
    });
    return out;
  }
  function positionAus(zeile) { return zeile && zeile.seite && typeof zeile.menge === 'number' ? zeile : null; }

  var KONTO_LEER = function () { return { aktiv: null, kontonr: null, abgekuerzt: null }; };
  var KOPF_LEER = function () { return { balance: null, mll: null, rpl: null, upl: null }; };

  // Offene Konto-Liste (für K2): nur Einträge, die wie ein Konto aussehen (Label|Kennung) — die Order-Typ-/Contract-Listen
  // sind auch role=option. rect = ganze Zeile (Klickziel), zu = verdeckt/disabled, hinweis = Klammer-Zusatz („Ineligible").
  function kontoListe() {
    var out = [], belegt = false;
    alle('[role="listbox"] [role="option"],li[role="option"]').filter(sichtbar).slice(0, 40).forEach(function (li) {
      var t = txt(li), m = RX_LISTE.exec(t);
      if (!m) return;
      var sel = attr(li, 'aria-selected'), hinweis = m[3] ? m[3].trim() : null;
      var mark = sel ? sel === 'true' : (hatKlasse(li, 'Mui-selected') ? true : null);
      if (mark !== null) belegt = true;
      out.push({ text: t, label: m[1].replace(/\s+/g, ' ').trim(), id: m[2].toUpperCase(), markiert: mark, ineligible: /ineligible/i.test(hinweis || ''),
                 hinweis: hinweis, aus: attr(li, 'aria-disabled') === 'true' || hatKlasse(li, 'Mui-disabled'), rect: rect(li), zu: zustand(li) });
    });
    if (belegt) out.forEach(function (o) { if (o.markiert === null) o.markiert = false; });
    return out;
  }

  // -> {aktiv, kontonr, abgekuerzt, rect, zu, liste_offen, liste}; rect/zu = Auslöser (Klickziel für K2, zu.verdeckt bei offener Liste)
  function kontoLesen() {
    var k = KONTO_LEER();
    if (!K1_ANKER) return k;
    var el = ankerKonto();
    if (el) { k = kontoAusText(txt(el)); k.rect = rect(el); k.zu = zustand(el); }
    k.liste = kontoListe();
    var offen = el ? attr(el, 'aria-expanded') : '';      // belegt: „false"/„true" am Auslöser; fehlt es, zählen die Zeilen
    k.liste_offen = offen === 'true' ? true : (offen === 'false' ? false : k.liste.length > 0);
    return k;
  }
  // Je Feld sein eigener data-testid; es zählt nur das EIGENE Label (ein BAL-Feld mit „MLL:"-Text bleibt null). Fehlen alle vier
  // Felder (TopstepX benennt um), lesen die Textregeln die Kopfzeile als Ganzes.
  function kopfLesen() {
    var out = KOPF_LEER(), da = 0;
    if (!K1_ANKER) return out;
    Object.keys(KOPF_TID).forEach(function (k) {
      var el = q1(tid(KOPF_TID[k]));
      if (!el) return;
      da++;
      out[k] = kopfAusTexten(blattTexte(el, 8))[k] || kopfAusTexten([txt(el)])[k];
    });
    if (!da) { var nav = ankerKopf(); if (nav) out = kopfAusTexten(blattTexte(nav, 60)); }
    return out;
  }
  // -> {sichtbar, zeilen, flach}. Gerüst: alles null. „No Active Position" zu sehen = sichtbar true; flach true NUR, wenn dazu
  // „Close Position" disabled ist (belegt: bei flachem Konto disabled) — widersprechen sich die beiden oder fehlt der Knopf, bleibt
  // flach null. Sonst (Position offen ODER Order-Karte nicht zu sehen): sichtbar/flach false nur mit gelesenen Zeilen, sonst null.
  // „No Active Position" auch ohne data-testid (09.10.2026, Ina DLL-Konto: weder Anker noch Zeile gefunden): ein sichtbares Element der
  // Order-Karte (data-testid^=order-card) bzw. ein kurzer Blatt-Text, der GANZ „No Active Position" (o. Ä.) ist
  function keinePosPerText() {
    var kand = alle('[data-testid^="order-card"]').filter(sichtbar).filter(function (e) { return RX_KEINE_POS.test(txt(e)) && txt(e).length <= 40; });
    if (kand.length) return kand[0];
    var treffer = null;
    alle('span,div,p').some(function (e) {
      if (e.children.length || !sichtbar(e)) return false;
      var t = txt(e);
      if (t.length <= 30 && /^(no active position|no open position|no positions?)$/i.test(t)) { treffer = e; return true; }
      return false;
    });
    return treffer;
  }
  function positionenLesen() {
    if (!K1_ANKER) return { sichtbar: null, zeilen: [], flach: null };
    var keine = ankerPositionen() || keinePosPerText();
    if (keine && RX_KEINE_POS.test(txt(keine))) {
      var zu = q1(tid('order-card-click-button-close-position'));
      return { sichtbar: true, zeilen: [], flach: zu && zustand(zu).disabled ? true : null };
    }
    var zeilen = [];
    positionsZeilen().forEach(function (z) { var p = positionAus(z); if (p) zeilen.push(p); });
    if (!zeilen.length) {
      // Positions-Grid offen, mit Kopfzeile (Risk/To Make), OHNE Zeile UND „Close Position" gesperrt = flach (zwei Belege wie Regel T3)
      var g = gitterLesen(), zuK = q1(tid('order-card-click-button-close-position'));
      if (g.da && !g.zeilen.length && zuK && zustand(zuK).disabled) return { sichtbar: true, zeilen: [], flach: true };
    }
    return { sichtbar: zeilen.length > 0, zeilen: zeilen, flach: zeilen.length ? false : null };
  }
  // Express-Konten zeigen die Balance RELATIV (K0 30.09.2026: „$150K Express" mit BAL $0.00 und MLL $-4,500.00), Combine-Konten
  // absolut (UIA-Inventar B22: BAL $154,504.88). Der Rohwert bleibt, wie er ist — hier nur das Merkmal: true = relativ,
  // false = absolut, null = nicht erkennbar. Erkennbar an einem negativen MLL (ein absolutes MLL ist ein Kontostand) oder daran,
  // dass die Balance unter der halben Kontogröße aus dem Label („$150K") liegt: so tief steht kein absoluter Stand, das Konto
  // wäre längst am MLL.
  function balanceRelativ(aktiv, kopf) {
    var bal = kopf && kopf.balance ? kopf.balance.wert : null, mll = kopf && kopf.mll ? kopf.mll.wert : null;
    if (typeof mll === 'number' && mll < 0) return true;
    var m = /\$\s*(\d+(?:[.,]\d+)?)\s*K\b/i.exec(String(aktiv || ''));
    var gr = m ? Number(m[1].replace(',', '.')) * 1000 : null;
    if (typeof bal !== 'number' || !gr) return null;
    return bal < gr * 0.5;
  }
  /* K3 (01.10.2026, Finn: „bei Contracts reinklicken, MNQ oder NQ auswählen; bei Number of Contracts reinklicken, die Zahl weg,
   * die eigentliche Zahl angeben; Buy bzw. Sell"). NUR LESEN — geklickt und getippt wird im Bot (Windows-Maus/-Tastatur).
   * Anker belegt im K0-Inventar 30.09.2026 (puls_augen inventar_tsx_grund):
   *   Contract   [data-testid="contract-selector-input-select-contract"] → input[role="combobox"] (Wert „MNQZ26")
   *   Order-Typ  [data-testid="order-card-click-select-order-type"] (Text „Market")
   *   Menge      [data-testid="order-card-input-field-contracts"] → input (Wert „3")
   *   Knöpfe     [data-testid="order-card-click-button-buy"] „Buy +3 @ Market", […-sell] „Sell -3 @ Market"
   * NICHT im Inventar (die Liste war zu): die Vorschlagsliste des Contract-Felds (MUI-Autocomplete, Bild Finn 01.10.2026:
   * „MNQZ26 · Micro Nasdaq (Dec 2026)", links ein Stern = Favorit). Gelesen wird die Liste, die das Feld per aria-controls nennt,
   * sonst eine sichtbare [role=listbox] direkt unter dem Feld; es zählen nur Zeilen mit einer Textzeile, die GANZ ein Kontrakt-Code ist.
   * Klickziel ist der Code-Text selbst (code_rect), nie die ganze Zeile — der Stern links darf nie getroffen werden. */
  var RX_CODE = /^[A-Z]{1,5}[FGHJKMNQUVXZ]\d{1,2}$/;
  function aktivIst(el) { try { return !!el && document.activeElement === el; } catch (_) { return false; } }
  function feldIn(id) {
    var w = q1(tid(id));
    return { w: w, i: w ? q1('input', w) : null };
  }
  function contractLesen() {
    var f = feldIn('contract-selector-input-select-contract');
    if (!f.i) { var c = q1(tid('contract-selector-container')); if (c) f = { w: c, i: q1('input', c) }; }
    if (!f.i) return null;
    return { wert: String(f.i.value || '').trim().slice(0, 30), rect: rect(f.i), feld_rect: f.w ? rect(f.w) : null,
             offen: attr(f.i, 'aria-expanded') === 'true', fokus: aktivIst(f.i), zu: zustand(f.i), liste_id: attr(f.i, 'aria-controls') || null };
  }
  function contractVorschlaege(c) {
    var boxen = [], fr = c && (c.feld_rect || c.rect);
    var eigen_ = c && c.liste_id ? document.getElementById(c.liste_id) : null;
    if (eigen_ && sichtbar(eigen_)) boxen.push(eigen_);
    if (!boxen.length && fr) {
      alle('[role="listbox"]').filter(sichtbar).forEach(function (b) {
        var r = b.getBoundingClientRect();
        var unter = r.top >= fr[1] + fr[3] - 12 && r.top <= fr[1] + fr[3] + 60, quer = r.left < fr[0] + fr[2] && r.right > fr[0];
        if (unter && quer) boxen.push(b);
      });
    }
    var out = [];
    boxen.forEach(function (b) {
      alle('[role="option"]', b).filter(sichtbar).slice(0, 30).forEach(function (li) {
        var zeilen = String(li.innerText || li.textContent || '').split('\n').map(function (z) { return z.replace(/\s+/g, ' ').trim(); })
          .filter(Boolean);
        // Code = die erste Textzeile, die GANZ ein Kontrakt-Code ist — davor stehen Markierungen („■", Stern), dahinter der Name
        var code = (zeilen.map(function (z) { return z.toUpperCase(); }).filter(function (z) { return RX_CODE.test(z); })[0]) || '';
        if (!code) return;
        var blatt = null;
        alle('*', li).some(function (e) {
          if (e.children.length === 0 && sichtbar(e) && txt(e).toUpperCase() === code) { blatt = e; return true; }
          return false;
        });
        out.push({ code: code, text: zeilen.join(' · ').slice(0, 80), rect: rect(li), code_rect: blatt ? rect(blatt) : null,
                   markiert: attr(li, 'aria-selected') === 'true', zu: zustand(blatt || li) });
      });
    });
    return out;
  }
  function mengeLesen() {
    var f = feldIn('order-card-input-field-contracts');
    return f.i ? { wert: String(f.i.value || '').trim().slice(0, 12), rect: rect(f.i), fokus: aktivIst(f.i), zu: zustand(f.i) } : null;
  }
  function knopfLesen(id) {
    var b = q1(tid(id));
    return b ? { testid: id, text: txt(b).slice(0, 40), rect: rect(b), zu: zustand(b) } : null;
  }
  // Order-Karte rechts ([data-testid="order-card-container"]): Anzeige-Felder order-card-display-value-* (bid, last-price, ask,
  // no-position …) als Rohtext, Bracket-Auswahl, dazu seit tsx-0.5.0 (K3) Contract, Vorschläge, Menge, Order-Typ, Buy/Sell.
  // k3 = true: dieser Vertrag ist da (ein Bot mit K3 weist eine ältere augen_tsx.js ohne diese Felder ab).
  function ticketLesen() {
    if (!K1_ANKER || !q1(tid('order-card-container'))) return null;
    var t = { k3: true, anzeigen: alle('[data-testid^="order-card-display-value-"]').filter(sichtbar).slice(0, 12).map(function (e) {
      return { testid: testid(e), text: txt(e).slice(0, 80), rect: rect(e) };
    }) };
    try { t.bracket = bracketLesen(); } catch (e) { t.bracket = { fehler: String(e).slice(0, 80) }; }
    try { var c = contractLesen(); t.contract = c; t.vorschlaege = c ? contractVorschlaege(c) : []; }
    catch (e) { t.contract = null; t.vorschlaege = []; t.k3_fehler = 'contract: ' + String(e).slice(0, 60); }
    try { t.menge = mengeLesen(); } catch (e) { t.menge = null; t.k3_fehler = 'menge: ' + String(e).slice(0, 60); }
    try {
      var ot = q1(tid('order-card-click-select-order-type'));
      t.ordertyp = ot ? { text: txt(ot).slice(0, 30), rect: rect(ot) } : null;
      t.kauf = knopfLesen('order-card-click-button-buy');
      t.verkauf = knopfLesen('order-card-click-button-sell');
    } catch (e) { t.k3_fehler = 'knoepfe: ' + String(e).slice(0, 60); }
    return t;
  }

  /* BRACKET — nur LESEN (K3/K4 setzen SL/TP per Ziehen im Chart, nicht über den Dialog, Entscheidung vom 30.09.2026). Gebraucht wird der Zustand:
   * legt TopstepX nach einem Fill selbst SL/TP an („Automatically apply …")? Belegt durch inventar_tsx_bracket (30.09.2026 20:48 UTC,
   * Dialog offen, Konto flach):
   *   Order-Karte  [data-testid="oco-bracket-selector-container"] → [role="combobox"] „Enabled" (Mui-disabled); Zahnrad
   *                [data-testid="oco-bracket-selector-click-button-settings"] (aria „Manage brackets")
   *   Dialog       [role="dialog"], Titel h2 „Position Brackets", X = button[aria-label="close"]
   *                [data-testid="auto-oco-brackets-click-button-switch-mode"] „Switch to Auto OCO Brackets" (aria „Account must be fully
   *                flattened before switching") → aktiv ist „Position Brackets"; die Gegenrichtung („Switch to Position …") ist unbelegt
   *                [data-testid="auto-oco-brackets-input-field-risk" | "-profit"] → input (beide leer)
   *                [data-testid="auto-oco-brackets-toggle-switch-auto-apply"] → input[type=checkbox] (opacity 0, darum ohne sichtbar()-Filter;
   *                checked false = „Automatically apply Risk / Profit bracket to new Positions" AUS)
   * Form wie mit T3 abgestimmt (30.09.2026): flach unter ticket.bracket (ticket steht auf der Route-Whitelist, ein eigener Oberschlüssel
   * nicht) — dialog_offen, modus 'position'|'auto_oco'|null, auto_apply bool|null, risk/profit {text, wert}|null; ohne offenen Dialog
   * bleiben modus/auto_apply/risk/profit null. Dazu auswahl/zahnrad aus der Order-Karte und titel/x/umschalten aus dem Dialog. */
  function bracketFeld(id) {
    var f = q1(tid(id)), i = f ? f.querySelector('input') : null;
    return i ? { text: String(i.value || ''), wert: geld(i.value), rect: rect(i), zu: zustand(i) } : null;
  }
  function bracketLesen() {
    var o = { dialog_offen: false, modus: null, auto_apply: null, risk: null, profit: null,
              auswahl: null, auswahl_aus: null, zahnrad: null, titel: null, x: null, umschalten: null, rect: null };
    var sel = q1(tid('oco-bracket-selector-container')), cb = sel ? q1('[role="combobox"]', sel) : null;
    if (cb) { o.auswahl = txt(cb) || null; o.auswahl_aus = hatKlasse(cb, 'Mui-disabled') || attr(cb, 'aria-disabled') === 'true'; }
    var z = q1(tid('oco-bracket-selector-click-button-settings'));
    if (z) o.zahnrad = { rect: rect(z), zu: zustand(z) };
    var sw = q1(tid('auto-oco-brackets-click-button-switch-mode')), dlg = sw && sw.closest ? sw.closest('[role="dialog"]') : null;
    if (!dlg) return o;
    var t = txt(sw), x = q1('button[aria-label="close"]', dlg), h = q1('h2', dlg);
    var hk = q1(tid('auto-oco-brackets-toggle-switch-auto-apply')), kb = hk ? hk.querySelector('input[type="checkbox"]') : null;
    o.dialog_offen = true; o.titel = h ? txt(h) : null; o.rect = rect(dlg);
    o.modus = /switch to auto\s*oco/i.test(t) ? 'position' : (/switch to position/i.test(t) ? 'auto_oco' : null);
    o.umschalten = { text: t || null, hinweis: attr(sw, 'aria-label') || null, zu: zustand(sw) };
    o.risk = bracketFeld('auto-oco-brackets-input-field-risk'); o.profit = bracketFeld('auto-oco-brackets-input-field-profit');
    o.auto_apply = kb ? !!kb.checked : (hk && hatKlasse(hk, 'Mui-checked') ? true : null);
    o.x = x ? { rect: rect(x), zu: zustand(x) } : null;
    return o;
  }

  // ── Chart-Sonde (TSX-CHART-SONDE, 01.10.2026) ──────────────────────────────
  /* Entscheidung vom 30.09.2026: Puls setzt SL/TP auf TopstepX NICHT über den Bracket-Dialog, sondern zieht sie per echter Maus aus der
   * Positionslinie im Chart. Dafür braucht der Bot Preis → Bildschirm-y. Die Linien sind Canvas (K0: keine DOM-Knoten), der Chart ist
   * die TradingView-Library im iframe#tradingview_… (blob:, gleiche Herkunft → contentWindow lesbar).
   * Belegt durch die Recherche (Workflow wf_2c5d535c, Quellen: Library-Doku, öffentliche d.ts, Library-Bundles v31/v32, TopstepX-Bundle):
   *   - TopstepX lädt „TT v31.1.0" (iframe-Attribut version, TradingView.version()); ein globales Widget gibt es in Produktion nicht
   *     (__tvWidget nur mit Feature-Flag). Der Weg: iframe.contentWindow.tradingViewApi — dasselbe Objekt wie widget._innerAPI().
   *   - Aktiver Chart über tradingViewApi._activeChartWidgetWV.value() (schon gecacht). activeChart()/chart(i) ruft die Sonde NICHT
   *     auf: beim ersten Aufruf legt die Library einen Wrapper an, der intern Abos anmeldet.
   *   - Preis → y (pane-lokal, CSS-px, y = 0 oben): priceToCoordinate gibt es erst ab v32.2 (auf TopstepX fehlt es). Öffentlicher
   *     Ersatz, so rechnet TopstepX selbst: y = (to − p)/(to − from)·(h − 1), h = pane.getHeight(), {from, to} = getVisiblePriceRange()
   *     (Ränder schon enthalten), nur im Modus Normal (0); Log (1) in log10. Gegenprobe mit coordinateToPrice(y) (ab v28).
   *     Host-y = iframe.top + Pane-Canvas.top + y.
   *   - Order-/Positionslinien: öffentlich NICHT aufzählbar (getAllShapes filtert LineToolOrder heraus). TopstepX zeichnet Position,
   *     SL und TP mit createOrderLine; die Positionslinie trägt den Cancel-Tooltip „Close position" (das Kreuz SCHLIESST die Position —
   *     nie dorthin ziehen/klicken). Lesbar nur intern: model().model().dataSources() mit toolname 'LineToolOrder', adapter().getPrice()
   *     usw.; das zuletzt gezeichnete Label-Rechteck liegt als Feld in _paneViews.get(undefined)[0]._orderRenderer._cache
   *     ({left, right, bodyRight, quantityRight, top, bottom}); ziehbar ist der Body [left, bodyRight) — nur mit hasMoveCallback und
   *     ohne getBlocked(); ist die Linie ausgewählt, zusätzlich ein Punkt bei x = Pane-Breite − 5 auf Linienhöhe (Radius 6 px).
   *   - Gegenprüfung (Prüfer im Workflow): TopstepX legt über createOrderLine AUCH Preisalarme („Delete alert"/„Edit alert") und eine
   *     unsichtbare Hilfslinie an (Text = 3000 Leerzeichen, setLineLength(0, "pixel"), Body über die ganze Pane-Breite). Darum die
   *     Positionslinie NUR über den Cancel-Tooltip „Close position" erkennen, nie über toolname allein; eine Alarm-/Hilfslinie nahe
   *     am Positionspreis kann Treffer abfangen.
   * STRIKT LESEN: Aufgerufen werden nur Getter aus GETTER (s. ruf()); nie Setter, subscribe, create*, remove, Callbacks, Klicks, Events.
   * getVisiblePriceRange/coordinateToPrice ziehen höchstens die Autoscale-Rechnung vor, die der nächste Frame ohnehin macht (TopstepX
   * ruft sie selbst für seine Hover-Linien). TopstepX speichert Chart-Änderungen nach ~1 s auf dem Server — darum nichts anfassen.
   * Fehlt etwas: null + grund, nichts geraten. */
  var SONDE_MAX = 16000;
  var GETTER = {
    version: 1, chartsCount: 1, activeChartIndex: 1, value: 1, symbol: 1, resolution: 1, symbolExt: 1, chartType: 1, getPanes: 1,
    getHeight: 1, paneIndex: 1, hasMainSeries: 1, isCollapsed: 1, isMaximized: 1, getMainSourcePriceScale: 1, getMode: 1, isInverted: 1,
    isAutoScale: 1, isLocked: 1, getVisiblePriceRange: 1, coordinateToPrice: 1, priceToCoordinate: 1, hasModel: 1, model: 1,
    dataSources: 1, name: 1, adapter: 1, getPrice: 1, getText: 1, getQuantity: 1, getLineStyle: 1, getLineColor: 1, getBodyTextColor: 1,
    getBodyBackgroundColor: 1, getQuantityBackgroundColor: 1, getCancelTooltip: 1, getTooltip: 1, getEditable: 1, getCancellable: 1,
    getLineLength: 1, getLineLengthUnit: 1, getExtendLeft: 1, hasMoveCallback: 1, isOnCancelCallbackPresent: 1, getBlocked: 1, getVisible: 1, panes: 1,
    mainSeries: 1, paneForSource: 1, paneByState: 1, canvasElement: 1
  };
  // Einziger Weg, eine Library-Methode aufzurufen: nur Namen aus GETTER, sonst Fehler (Programmier-Riegel, nie still)
  function ruf(obj, name, args) {
    if (!GETTER[name]) throw new Error('Sonde: ' + name + ' ist nicht als Getter freigegeben');
    if (!obj || typeof obj[name] !== 'function') return undefined;
    return obj[name].apply(obj, args || []);
  }
  // Nur einfache Werte ins Ergebnis (Prüfer 01.10.2026): liefert ein Getter ein Library-Objekt mit Rückverweisen, scheitern
  // JSON.stringify und CDP returnByValue — dann wären Stand UND Inventar des Zustands verloren
  function prim(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === 'string') return v.slice(0, 120);
    if (typeof v === 'number') return isFinite(v) ? v : null;
    if (typeof v === 'boolean') return v;
    return '[' + typeof v + ']';
  }
  function versuch(fn, fehler, was) { try { return fn(); } catch (e) { if (fehler) fehler.push(was + ': ' + String(e && e.message || e).slice(0, 90)); return null; } }
  // Methodennamen eines Objekts (eigene + Prototyp-Kette) — nur Namen, nichts aufrufen
  function methoden(obj, max) {
    var out = [], seen = {}, p = obj, n = 0;
    try {
      while (p && p !== Object.prototype && n++ < 6) {
        Object.getOwnPropertyNames(p).forEach(function (k) {
          if (seen[k] || k === 'constructor') return; seen[k] = 1;
          var d = Object.getOwnPropertyDescriptor(p, k);
          if (d && typeof d.value === 'function') out.push(k);
        });
        p = Object.getPrototypeOf(p);
      }
    } catch (_) {}
    out.sort();
    return out.slice(0, max || 80);
  }
  function rechteckIn(r, off) { return r ? [r[0] + (off ? off[0] : 0), r[1] + (off ? off[1] : 0), r[2], r[3]] : null; }

  // Canvas im iframe einordnen: Haupt-Pane = breitestes Canvas (bei Gleichstand das oberste, wie TopstepX), Preisachse = rechts
  // daneben mit gleicher Höhe, Zeitachse = darunter mit gleicher Breite. aria-label „Chart for …" markiert die Pane-Canvas (v32-Demo).
  function canvasEinordnen(doc) {
    var cs = [];
    Array.prototype.slice.call(doc.querySelectorAll('canvas')).forEach(function (c) {
      var r = c.getBoundingClientRect();
      if (r.width >= 3 && r.height >= 3) cs.push({ el: c, rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], aria: attr(c, 'aria-label').slice(0, 80) });
    });
    var pane = null;
    cs.forEach(function (c) { if (!pane || c.rect[2] > pane.rect[2] || (c.rect[2] === pane.rect[2] && c.rect[1] < pane.rect[1])) pane = c; });
    cs.forEach(function (c) {
      c.rolle = !pane ? null : (c.rect[0] === pane.rect[0] && c.rect[1] === pane.rect[1] && c.rect[2] === pane.rect[2] && c.rect[3] === pane.rect[3]) ? 'pane'
        : (Math.abs(c.rect[1] - pane.rect[1]) <= 1 && Math.abs(c.rect[3] - pane.rect[3]) <= 1 && c.rect[0] >= pane.rect[0] + pane.rect[2] - 1) ? 'preisachse'
        : (Math.abs(c.rect[0] - pane.rect[0]) <= 1 && Math.abs(c.rect[2] - pane.rect[2]) <= 1 && c.rect[1] >= pane.rect[1] + pane.rect[3] - 1) ? 'zeitachse' : 'sonst';
    });
    return { liste: cs, pane: pane };
  }

  function chartSonde(opts) {
    opts = opts || {};
    var f = [], o = { v: VERSION, ts: Date.now(), dpr: window.devicePixelRatio || 1, geo: geo(), iframes: [], version: null, host: null, api: null,
                      chart: null, panes: null, skala: null, geometrie: null, umrechnung: null, linien: null, legende: null, overlays: null, fehler: f };
    // 1. iframe(s) — bei jedem Aufruf neu suchen (TopstepX tauscht das iframe zur Laufzeit aus)
    var ifs = alle('iframe[id^="tradingview_"]'), ifr = null;
    ifs.slice(0, 4).forEach(function (i) {
      var gh = false; try { gh = !!(i.contentDocument && i.contentWindow && i.contentWindow.document); } catch (_) {}
      var e = { id: i.id, titel: attr(i, 'title'), version: attr(i, 'version') || null, rect: rect(i), sichtbar: sichtbar(i), gleiche_herkunft: gh };
      o.iframes.push(e);
      if (!ifr && gh && e.sichtbar) ifr = i;
    });
    if (!ifr) { o.grund = ifs.length ? 'Chart-iframe nicht sichtbar oder nicht gleiche Herkunft' : 'kein iframe[id^="tradingview_"]'; return sondeDeckeln(o); }
    var W = ifr.contentWindow, D = ifr.contentDocument, ir = rect(ifr);
    o.version = { iframe: attr(ifr, 'version') || null, tv: prim(versuch(function () { return window.TradingView ? ruf(window.TradingView, 'version') : null; }, f, 'TradingView.version')) };
    // 2. Hauptfenster: Globals nur auf Existenz prüfen (nichts aufrufen außer version()); Widget-Optionen window[iframe.id] nur Schlüssel
    o.host = versuch(function () {
      var h = { TradingView: !!window.TradingView, tvWidget: !!window.tvWidget, __tvWidget: !!window.__tvWidget, __tvChartLines: !!window.__tvChartLines,
                optionen: null, widget_kandidaten: [] };
      var op = window[ifr.id];
      if (op && typeof op === 'object') h.optionen = { schluessel: Object.keys(op).slice(0, 40), broker: !!(op.brokerFactory || op.broker_factory) };
      Object.keys(window).slice(0, 600).forEach(function (k) {
        if (h.widget_kandidaten.length >= 6 || /^(webkit|on)/.test(k)) return;
        try { var d = Object.getOwnPropertyDescriptor(window, k), v = d && 'value' in d ? d.value : null; if (v && typeof v === 'object' && (typeof v.activeChart === 'function' || typeof v.chart === 'function' && typeof v.chartsCount === 'function')) h.widget_kandidaten.push(k); } catch (_) {}
      });
      return h;
    }, f, 'host');
    // 3. Library-API im iframe
    var api = null;
    try { api = W.tradingViewApi || null; } catch (_) {}
    o.api = { da: !!api, iframe_globals: versuch(function () {
                return ['tradingViewApi', 'TradingViewApi', 'chartWidgetCollection', 'ChartApiInstance', 'chartWidget', 'widgetReady', 'TradingView']
                  .filter(function (k) { try { return W[k] != null; } catch (_) { return false; } });
              }, f, 'iframe_globals') };
    if (!api) { o.api.grund = 'iframe.contentWindow.tradingViewApi fehlt (Chart noch nicht bereit?)'; }
    else {
      o.api.methoden = methoden(api, 70);
      o.api.charts = prim(versuch(function () { return ruf(api, 'chartsCount'); }, f, 'chartsCount'));
      o.api.aktiv = prim(versuch(function () { return ruf(api, 'activeChartIndex'); }, f, 'activeChartIndex'));
    }
    var ch = api ? versuch(function () { var wv = api._activeChartWidgetWV; return wv ? ruf(wv, 'value') : null; }, f, '_activeChartWidgetWV') : null;
    if (api && !ch) o.api.grund = 'kein _activeChartWidgetWV (activeChart() wird bewusst nicht aufgerufen)';
    // 4. Chart: Symbol, Auflösung, Tick, Panes, Haupt-Preisskala
    var skala = null, hMain = null, paneApi = null;
    if (ch) {
      o.chart = { methoden: methoden(ch, 80), symbol: prim(versuch(function () { return ruf(ch, 'symbol'); }, f, 'symbol')),
                  aufloesung: prim(versuch(function () { return ruf(ch, 'resolution'); }, f, 'resolution')),
                  typ: prim(versuch(function () { return ruf(ch, 'chartType'); }, f, 'chartType')) };
      var se = versuch(function () { return ruf(ch, 'symbolExt'); }, f, 'symbolExt');
      if (se && typeof se === 'object') {
        var ps = Number(se.pricescale), mm = Number(se.minmov);
        o.chart.symbol_info = { name: prim(se.name), full_name: prim(se.full_name), pricescale: isFinite(ps) ? ps : null, minmov: isFinite(mm) ? mm : null,
                                tick: isFinite(ps) && ps > 0 && isFinite(mm) ? mm / ps : null };
      }
      var panes = versuch(function () { return ruf(ch, 'getPanes'); }, f, 'getPanes') || [];
      o.panes = [];
      panes.slice(0, 6).forEach(function (p, i) {
        var e = { i: i, index: prim(versuch(function () { return ruf(p, 'paneIndex'); }, f, 'paneIndex')), hoehe: prim(versuch(function () { return ruf(p, 'getHeight'); }, f, 'getHeight')),
                  haupt: prim(versuch(function () { return ruf(p, 'hasMainSeries'); }, f, 'hasMainSeries')),
                  eingeklappt: prim(versuch(function () { return ruf(p, 'isCollapsed'); }, null, '')), maximiert: prim(versuch(function () { return ruf(p, 'isMaximized'); }, null, '')) };
        o.panes.push(e);
        if (e.haupt && !paneApi) { paneApi = p; hMain = e.hoehe; }
      });
      if (!paneApi && panes.length) { paneApi = panes[0]; hMain = o.panes[0].hoehe; o.chart.haupt_pane_hinweis = 'keine Pane mit hasMainSeries — Pane 0 genommen'; }
      skala = paneApi ? versuch(function () { return ruf(paneApi, 'getMainSourcePriceScale'); }, f, 'getMainSourcePriceScale') : null;
      if (skala) {
        var vr = versuch(function () { return ruf(skala, 'getVisiblePriceRange'); }, f, 'getVisiblePriceRange');
        var md = prim(versuch(function () { return ruf(skala, 'getMode'); }, f, 'getMode'));
        o.skala = { von: vr && typeof vr.from === 'number' && isFinite(vr.from) ? vr.from : null, bis: vr && typeof vr.to === 'number' && isFinite(vr.to) ? vr.to : null, modus: md,
                    modus_name: md === 0 ? 'normal' : md === 1 ? 'log' : md === 2 ? 'prozent' : md === 3 ? 'indexed100' : null,
                    invertiert: prim(versuch(function () { return ruf(skala, 'isInverted'); }, f, 'isInverted')),
                    auto: prim(versuch(function () { return ruf(skala, 'isAutoScale'); }, null, '')), gesperrt: prim(versuch(function () { return ruf(skala, 'isLocked'); }, null, '')),
                    price_to_coordinate: typeof skala.priceToCoordinate === 'function', coordinate_to_price: typeof skala.coordinateToPrice === 'function',
                    methoden: methoden(skala, 40) };
      } else if (ch) o.skala = { grund: 'keine Haupt-Preisskala (No Scale/Overlay?)' };
    }
    // 5. Geometrie: Pane-Canvas im iframe → Host-Koordinaten. Erst intern (paneByState(pane).canvasElement()), sonst Heuristik.
    var ce = canvasEinordnen(D), paneEl = null, quelle = null;
    var cw = ch ? versuch(function () { return ch._chartWidget || null; }, f, '_chartWidget') : null;
    var M = cw ? versuch(function () { return ruf(cw, 'hasModel') ? ruf(ruf(cw, 'model'), 'model') : null; }, f, 'model') : null;
    if (cw && M) paneEl = versuch(function () {
      var mp = ruf(M, 'paneForSource', [ruf(M, 'mainSeries')]);
      var w = mp ? ruf(cw, 'paneByState', [mp]) : null, el = w ? ruf(w, 'canvasElement') : null;
      return el && el.getBoundingClientRect ? el : null;
    }, f, 'paneWidget');
    if (paneEl) quelle = 'intern'; else if (ce.pane) { paneEl = ce.pane.el; quelle = 'breitestes_canvas'; }
    var pr = paneEl ? (function () { var r = paneEl.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; })() : null;
    var pExakt = paneEl ? paneEl.getBoundingClientRect() : null;
    o.geometrie = { iframe: ir, iframe_dpr: versuch(function () { return W.devicePixelRatio; }, null, ''), pane_quelle: quelle,
                    pane_iframe: pr, pane_host: rechteckIn(pr, ir),
                    preisachse_host: (function () { var a = ce.liste.filter(function (c) { return c.rolle === 'preisachse'; })[0]; return a ? rechteckIn(a.rect, ir) : null; })(),
                    zeitachse_host: (function () { var a = ce.liste.filter(function (c) { return c.rolle === 'zeitachse'; })[0]; return a ? rechteckIn(a.rect, ir) : null; })(),
                    canvas: ce.liste.slice(0, 10).map(function (c) { return { rect: c.rect, rolle: c.rolle, aria: c.aria || undefined }; }),
                    hoehe_passt: pExakt && typeof hMain === 'number' ? Math.abs(pExakt.height - hMain) < 1.5 : null };
    if (opts.kompakt) { delete o.geometrie.canvas; }
    // 6. Umrechnung Preis → y (+ Gegenprobe über coordinateToPrice)
    o.umrechnung = umrechnen(o, skala, hMain, ifr, paneEl, opts.preise, f);
    // 7. Linien (intern, nur Felder/Getter) — Position/SL/TP/Orders/Alarme als LineToolOrder
    o.linien = M ? versuch(function () { return linienLesen(M, ifr, paneEl, f); }, f, 'linien') : { grund: 'kein Chart-Modell (intern)' };
    // 8. Legende, DOM-Overlays über der Pane, Tooltips (nur Texte/Rechtecke)
    // Legende: je Quelle ein Eintrag (Demo v31.1/v32.2: data-qa-id legend-series-item = Hauptserie, legend-source-item = Studien)
    o.legende = versuch(function () {
      return Array.prototype.slice.call(D.querySelectorAll('[data-qa-id="legend-series-item"],[data-qa-id="legend-source-item"]')).slice(0, 8).map(function (e) {
        return { art: attr(e, 'data-qa-id') === 'legend-series-item' ? 'serie' : 'quelle', text: txt(e).slice(0, 100) };
      });
    }, f, 'legende');
    o.overlays = pExakt ? versuch(function () {
      var pts = [[0.5, 0.5], [0.97, 0.5], [0.5, 0.05], [0.5, 0.95]], seen = [], out = [];
      pts.forEach(function (p) {
        (D.elementsFromPoint(pExakt.left + pExakt.width * p[0], pExakt.top + pExakt.height * p[1]) || []).forEach(function (e) {
          if (out.length >= 12 || seen.indexOf(e) >= 0 || e.tagName === 'CANVAS' || e === D.body || e === D.documentElement) return;
          seen.push(e);
          var c = typeof e.className === 'string' ? e.className : ((e.className && e.className.baseVal) || '');
          out.push({ tag: e.tagName.toLowerCase(), cls: c.replace(/\s+/g, ' ').slice(0, 60), rect: rechteckIn(rect(e), ir), text: txt(e).slice(0, 40) || undefined });
        });
      });
      return out;
    }, f, 'overlays') : null;
    // offene Tooltips: nur role=tooltip — Klassen mit „tooltip" tragen in der Library auch Knöpfe und Watchlist-Zeilen (Demo v31.1/v32.2)
    o.tooltips = versuch(function () {
      return Array.prototype.slice.call(D.querySelectorAll('[role="tooltip"]')).filter(function (e) {
        var r = e.getBoundingClientRect(); return r.width > 3 && r.height > 3 && txt(e);
      })
        .slice(0, 4).map(function (e) { return { text: txt(e).slice(0, 80), rect: rechteckIn(rect(e), ir) }; });
    }, f, 'tooltips');
    if (opts.kompakt) {   // für inventar(): ohne Methodenlisten/Overlays/Optionsschlüssel — die Anker-Elemente brauchen den Platz
      if (o.api) delete o.api.methoden; if (o.chart) delete o.chart.methoden; if (o.skala) delete o.skala.methoden;
      if (o.linien) delete o.linien.adapter_methoden; delete o.overlays; if (o.host && o.host.optionen) delete o.host.optionen.schluessel;
    }
    if (!f.length) delete o.fehler;
    return sondeDeckeln(o);
  }

  // Preis → y. Modus 0 (normal) linear, 1 (log) in log10, 2/3 (prozent/indexed) wie linear (laut Library-Code affin, live unbelegt).
  // y_pane zählt ab Pane-Oberkante (CSS-px), y_host = iframe.top + pane.top + y_pane (Viewport des Hauptfensters, wie rect()).
  function umrechnen(o, skala, h, ifr, paneEl, preise, f) {
    var s = o.skala || {}, u = { ok: false, formel: null, von: s.von, bis: s.bis, hoehe: h, pane_top_host: null, pane_left_host: null, pane_breite: null, punkte: [] };
    if (!skala || !isFinite(s.von) || !isFinite(s.bis) || !(h > 1) || !paneEl) { u.grund = 'Preisbereich, Pane-Höhe oder Pane-Canvas fehlt'; return u; }
    if (s.bis === s.von) { u.grund = 'Preisbereich ohne Spanne'; return u; }
    var ifrR = ifr.getBoundingClientRect(), pR = paneEl.getBoundingClientRect();
    u.pane_top_host = Math.round((ifrR.top + pR.top) * 100) / 100; u.pane_left_host = Math.round((ifrR.left + pR.left) * 100) / 100; u.pane_breite = Math.round(pR.width);
    var log = s.modus === 1;
    if (log && !(s.von > 0 && s.bis > 0)) { u.grund = 'Log-Skala mit Preis ≤ 0'; return u; }
    u.formel = log ? 'log10' : 'linear';
    if (s.modus !== 0 && s.modus !== 1) u.hinweis = 'Modus ' + s.modus + ' (' + s.modus_name + '): laut Library-Code affin im Preis (Prüfer bestätigt), live unbelegt';
    function yVon(p) {
      var a = log ? Math.log(s.bis) / Math.LN10 : s.bis, b = log ? Math.log(s.von) / Math.LN10 : s.von, x = log ? Math.log(p) / Math.LN10 : p;
      return (a - x) / (a - b) * (h - 1);
    }
    var liste = (Array.isArray(preise) && preise.length ? preise : [s.bis, (s.bis + s.von) / 2, s.von]).slice(0, 8);
    liste.forEach(function (p) {
      p = Number(p);
      if (!isFinite(p) || (log && p <= 0)) { u.punkte.push({ preis: p, y_pane: null, grund: 'Preis ungültig' }); return; }
      var y = yVon(p), e = { preis: p, y_pane: Math.round(y * 100) / 100, y_host: Math.round((u.pane_top_host + y) * 100) / 100, im_bild: y >= 0 && y <= h - 1 };
      if (s.price_to_coordinate) e.y_library = prim(versuch(function () { return ruf(skala, 'priceToCoordinate', [p]); }, f, 'priceToCoordinate'));
      if (s.coordinate_to_price && e.im_bild) {
        var zp = versuch(function () { return ruf(skala, 'coordinateToPrice', [y]); }, f, 'coordinateToPrice');
        if (typeof zp === 'number' && isFinite(zp)) { e.gegenprobe = Math.round(zp * 1e6) / 1e6; e.abweichung = Math.round(Math.abs(zp - p) * 1e6) / 1e6; }
      }
      u.punkte.push(e);
    });
    var tick = o.chart && o.chart.symbol_info ? o.chart.symbol_info.tick : null;
    var abw = u.punkte.filter(function (e) { return typeof e.abweichung === 'number'; }).map(function (e) { return e.abweichung; });
    u.gegenprobe = abw.length ? { max_abweichung: Math.max.apply(null, abw), tick: tick, passt: tick ? Math.max.apply(null, abw) <= tick / 2 : null } : null;
    // ok nur, wenn die Pane sicher die der Hauptserie ist (intern bestimmt oder Höhe = getHeight) und die Gegenprobe nicht widerspricht —
    // die Gegenprobe prüft nur pane-lokal, ein falscher Host-Versatz (Rückfall „breitestes Canvas", Indikator-Pane darüber) fiele ihr nicht auf
    var g = o.geometrie || {};
    if (!(g.pane_quelle === 'intern' || g.hoehe_passt === true)) u.grund = 'Pane-Zuordnung unsicher (' + g.pane_quelle + ', Höhe passt ' + g.hoehe_passt + ')';
    else if (u.gegenprobe && u.gegenprobe.passt === false) u.grund = 'Gegenprobe über coordinateToPrice weicht um mehr als einen halben Tick ab';
    else u.ok = true;
    return u;
  }

  // Linien aus dem Chart-Modell: toolname 'LineToolOrder' (auch 'LineToolPosition'/'LineToolExecution'). Nur Getter + Felder.
  function linienLesen(M, ifr, paneEl, f) {
    var srcs = ruf(M, 'dataSources') || [], out = { quelle: 'intern', anzahl: 0, liste: [] };
    var ifrR = ifr.getBoundingClientRect(), pR = paneEl ? paneEl.getBoundingClientRect() : null;
    var offX = pR ? ifrR.left + pR.left : null, offY = pR ? ifrR.top + pR.top : null;
    var alle_ = [];
    srcs.forEach(function (s) {
      var tn = null; try { tn = s && s.toolname; } catch (_) {}
      if (!/^LineTool(Order|Position|Execution)$/.test(String(tn || ''))) return;
      out.anzahl++;
      if (alle_.length >= 60) return;
      var a = versuch(function () { return ruf(s, 'adapter') || s._adapter || null; }, f, 'adapter');
      var g = function (n) { return a ? prim(versuch(function () { return ruf(a, n); }, null, '')) : null; };
      var tx = a ? versuch(function () { return ruf(a, 'getText'); }, null, '') : null, txs = typeof tx === 'string' ? tx : null;
      var e = { toolname: tn, name: prim(versuch(function () { return ruf(s, 'name'); }, null, '')), preis: g('getPrice'),
                text: txs === null ? prim(tx) : txs.replace(/\s+/g, ' ').trim().slice(0, 80), text_laenge: txs === null ? null : txs.length, menge: g('getQuantity'),
                stil: g('getLineStyle'), farbe: g('getLineColor'), body_farbe: g('getBodyBackgroundColor'), cancel_tooltip: g('getCancelTooltip'), tooltip: g('getTooltip'),
                editierbar: g('getEditable'), ziehbar: g('hasMoveCallback'), kreuz: g('isOnCancelCallbackPresent'), laenge: g('getLineLength'),
                laenge_einheit: g('getLineLengthUnit'), links_verlaengert: g('getExtendLeft'), gesperrt: g('getBlocked'), sichtbar: g('getVisible') };
      if (!out.adapter_methoden && a) out.adapter_methoden = methoden(a, 60);
      // Rolle nur aus belegten TopstepX-Konstanten: Positionslinie = Cancel-Tooltip „Close position", Alarm = „Delete alert"
      var hilfe = (txs !== null && txs.length >= 100 && !txs.trim()) || (e.laenge === 0 && e.laenge_einheit === 'pixel');
      e.rolle = /^close position$/i.test(String(e.cancel_tooltip || '')) ? 'position'
        : /alert/i.test(String(e.cancel_tooltip || '') + ' ' + String(e.tooltip || '')) ? 'alarm' : hilfe ? 'hilfe' : null;
      // Label-Rechteck des letzten Zeichnens (pane-lokal, CSS-px) — reiner Feldzugriff, nie renderer() aufrufen
      var c = versuch(function () {
        var pv = s._paneViews, v = pv && typeof pv.get === 'function' ? pv.get(undefined) : null, r = v && v[0] && v[0]._orderRenderer;
        return r && r._cache ? r._cache : null;
      }, null, '');
      if (c && typeof c.left === 'number' && typeof c.top === 'number' && isFinite(c.left) && isFinite(c.top)) {
        e.label_pane = { left: c.left, right: c.right, body_right: c.bodyRight, menge_right: c.quantityRight, top: c.top, bottom: c.bottom };
        if (offX !== null) e.label_host = { body: [Math.round((offX + c.left) * 10) / 10, Math.round((offY + c.top) * 10) / 10, Math.round((c.bodyRight - c.left) * 10) / 10, Math.round((c.bottom - c.top) * 10) / 10],
                                            menge: isFinite(c.quantityRight) ? [Math.round((offX + c.bodyRight) * 10) / 10, Math.round((offY + c.top) * 10) / 10, Math.round((c.quantityRight - c.bodyRight) * 10) / 10, Math.round((c.bottom - c.top) * 10) / 10] : null,
                                            kreuz: isFinite(c.right) && isFinite(c.quantityRight) && c.right > c.quantityRight ? [Math.round((offX + c.quantityRight) * 10) / 10, Math.round((offY + c.top) * 10) / 10, Math.round((c.right - c.quantityRight) * 10) / 10, Math.round((c.bottom - c.top) * 10) / 10] : null };
      } else e.label_grund = 'kein gezeichnetes Label-Rechteck (_orderRenderer._cache fehlt)';
      alle_.push(e);
    });
    // Positionslinie zuerst, dann Linien ohne Rolle (SL/TP/Orders), dann Alarme und Hilfslinien — erst DANN kürzen (Prüfer: TopstepX legt
    // Alarme und die Hilfslinie beim Laden an, also vor der Position; sonst fiele die Position aus der Liste)
    var rang = { position: 0, alarm: 2, hilfe: 3 };
    alle_.sort(function (x, y) { return (x.rolle in rang ? rang[x.rolle] : 1) - (y.rolle in rang ? rang[y.rolle] : 1); });
    out.liste = alle_.slice(0, 12);
    if (alle_.length > 12) out.weggelassen = alle_.length - 12;
    if (!out.anzahl) out.grund = 'keine LineToolOrder/-Position im Modell (keine offene Position/Order oder anderer Pfad)';
    return out;
  }

  // Größen-Riegel: erst Methodenlisten kürzen, dann Overlays/Canvas — die Umrechnung und die Linien bleiben
  function sondeDeckeln(o) {
    try {
      var n = 0;
      while (JSON.stringify(o).length > SONDE_MAX && n++ < 12) {
        if (o.api && o.api.methoden && o.api.methoden.length > 20) o.api.methoden = o.api.methoden.slice(0, 20);
        else if (o.chart && o.chart.methoden && o.chart.methoden.length > 20) o.chart.methoden = o.chart.methoden.slice(0, 20);
        else if (o.skala && o.skala.methoden) delete o.skala.methoden;
        else if (o.linien && o.linien.adapter_methoden) delete o.linien.adapter_methoden;
        else if (o.overlays && o.overlays.length > 4) o.overlays = o.overlays.slice(0, 4);
        else if (o.geometrie && o.geometrie.canvas) delete o.geometrie.canvas;
        else if (o.legende || o.tooltips) { delete o.legende; delete o.tooltips; }
        else if (o.linien && o.linien.liste && o.linien.liste.length > 4) o.linien.liste = o.linien.liste.slice(0, 4);
        else if (o.host && o.host.optionen) delete o.host.optionen;
        else break;
        o.gekappt = true;
      }
    } catch (_) {}
    return o;
  }

  // ── Öffentliche Funktionen ─────────────────────────────────────────────────
  var STAND_MAX = 48000;
  function stand(opts) {
    opts = opts || {};
    var fehler = [];
    var g = geo(); g.lang = document.documentElement.lang || '';
    var o = { v: VERSION, ts: Date.now(), url: location.href, titel: document.title, geo: g, sichtbar: document.visibilityState, fokus: fokus(),
              popups: [], konto: null, kopf: null, ticket: null, kauf_knopf: null, positionen: [], positionen_sichtbar: null, flach: null,
              orders: [], toasts: null, konto_summary: null };
    // K1 (Vertrag T3): jeder Teil für sich — ein Fehler im einen lässt die anderen stehen, das Feld bleibt dann null
    try { o.konto = kontoLesen(); } catch (e) { o.konto = KONTO_LEER(); fehler.push('konto: ' + e); }
    try { o.kopf = kopfLesen(); } catch (e) { o.kopf = KOPF_LEER(); fehler.push('kopf: ' + e); }
    try { var pl = positionenLesen(); o.positionen = pl.zeilen; o.positionen_sichtbar = pl.sichtbar; o.flach = pl.flach; }
    catch (e) { fehler.push('positionen: ' + e); }
    try { o.kopf.balance_relativ = K1_ANKER ? balanceRelativ(o.konto.aktiv, o.kopf) : null; } catch (e) { o.kopf.balance_relativ = null; }
    try { o.ticket = ticketLesen(); } catch (e) { fehler.push('ticket: ' + e); }
    // K4 (05.10.2026): Reiter und Positions-Tabelle unten — unter ticket, weil die Route puls_augen nur bekannte Oberschlüssel durchlässt
    try { if (o.ticket) { o.ticket.reiter = reiterLesen(); o.ticket.gitter = gitterLesen(); o.ticket.k4 = true; } } catch (e) { fehler.push('gitter: ' + e); }
    try { o.toasts = toasts(); } catch (e) { fehler.push('toasts: ' + e); }
    try { o.popups = dialoge(); } catch (e) { fehler.push('popups: ' + e); }
    try {
      if (JSON.stringify(o).length > STAND_MAX) {
        if (o.toasts) { o.toasts.gruppen = (o.toasts.gruppen || []).slice(0, 6); o.toasts.meldungen = (o.toasts.meldungen || []).slice(0, 10); }
        o.popups = (o.popups || []).slice(0, 4);
        o.positionen = (o.positionen || []).slice(0, 20);
        if (JSON.stringify(o).length > STAND_MAX) fehler.push('stand über ' + STAND_MAX + ' Zeichen');
      }
    } catch (e) { fehler.push('groesse: ' + e); }
    if (fehler.length) o.fehler = fehler;
    return o;
  }

  /* Inventar (K0): der DOM des TopstepX-Tabs EINMAL als JSON — daraus baut T2 die Anker für Konto, BAL/MLL, Brackets, Contract,
   * Kauf-Knopf und Reiter. Plattformneutral: Merkmale (role/aria/id/data-testid/name/title/placeholder, Klasse gekürzt), dazu
   * kurze Blatt-Texte („BAL", „$150,000.00", „MNQZ26" …) mit Rechteck. Unter 52 KB, damit Inventar + Stand in eine puls_augen-Zeile
   * (60 KB) passen; gekürzt wird von hinten, der Kopf bleibt vollständig. */
  var INVENTAR_MAX = 52000;
  function inventar(opts) {
    opts = opts || {};
    var zonen = [['dialog', '[role="dialog"],[role="alertdialog"],[aria-modal="true"]'], ['menu', '[role="listbox"],[role="menu"],[role="menuitem"],[role="option"]'],
                 ['tabelle', 'table,[role="table"],[role="grid"],[role="row"]'], ['reiter', '[role="tablist"],[role="tab"]']];
    var toastBoxen = [];
    try { var tk = titelKnoten(); toastBoxen = tk.map(function (t) { return containerZu(t, tk); }); } catch (_) {}
    function zone(e) {
      if (toastBoxen.some(function (b) { return b.contains(e); })) return 'toast';
      for (var i = 0; i < zonen.length; i++) { try { if (e.closest(zonen[i][1])) return zonen[i][0]; } catch (_) {} }
      var r = e.getBoundingClientRect();
      return r.top < 90 ? 'kopf' : r.left > window.innerWidth * 0.66 ? 'rechts' : r.top > window.innerHeight * 0.6 ? 'unten' : r.left < window.innerWidth * 0.2 ? 'links' : 'mitte';
    }
    var sel = 'button,a[href],[role],input,select,textarea,[data-testid],[data-test],[data-cy],[aria-label],[id],[name],[title],th,label';
    // Rauschen raus (K0 30.09.2026: 209 Elemente, davon ~60 SVG-Innereien „Group_160"/„Path_101" und DataGrid-Hüllen) — und
    // Overlays ZUERST: Konto-Liste und Dialoge hängen am Ende von body und fielen dem Größendeckel (Kürzen von hinten) zum Opfer
    var SVG_INNEN = /^(g|path|rect|circle|ellipse|line|polyline|polygon|use|defs|clippath|mask|lineargradient|stop|title|desc)$/;
    var UEBER = '[role="dialog"],[role="alertdialog"],[aria-modal="true"],[role="listbox"],[role="menu"],.MuiModal-root,.MuiPopover-root,.MuiPopper-root';
    function ueber(e) { try { return !!e.closest(UEBER); } catch (_) { return false; } }
    function vornan(a) { return a.filter(ueber).concat(a.filter(function (e) { return !ueber(e); })); }
    var els = vornan(alle(sel).filter(sichtbar).filter(function (e) {
      if (testid(e) || attr(e, 'aria-label')) return true;
      if (SVG_INNEN.test(e.tagName.toLowerCase())) return false;
      return !(attr(e, 'role') === 'presentation' && e.closest('[role="grid"]'));
    })), liste = [];
    for (var i = 0; i < els.length && liste.length < 450; i++) {
      var e = els[i], t = txt(e);
      if (t.length > 120 && !attr(e, 'role') && !testid(e)) continue;   // Hüllen mit viel Text sind Rauschen
      liste.push(kurz(e, { zone: zone(e), cls: klasse(e) || undefined, name: attr(e, 'name') || undefined, title: attr(e, 'title') || undefined,
                           ph: attr(e, 'placeholder') || undefined, zu: zustand(e) }));
    }
    // Blatt-Texte: sichtbare Elemente ohne Element-Kinder mit kurzem Text (Kopfzahlen, Symbole, Reiter-Namen)
    var blatt = [];
    vornan(alle('body *').filter(function (e) { return !e.children.length && sichtbar(e); })).forEach(function (e) {
      if (blatt.length >= 320) return;
      var t = txt(e); if (!t || t.length > 40) return;
      blatt.push({ tag: e.tagName.toLowerCase(), text: t, rect: rect(e), zone: zone(e), cls: klasse(e).slice(0, 40) || undefined });
    });
    // unsichtbare Kästchen/Schalter (Haken wie „Automatically apply", TP/SL-Schalter) — sichtbar() filtert sie weg
    var kaestchen = alle('input[type="checkbox"],input[type="radio"],[role="switch"],[role="checkbox"]').slice(0, 40).map(function (e) {
      var st = window.getComputedStyle(e);
      return kurz(e, { zone: zone(e), opacity: st.opacity, display: st.display, sichtbar: sichtbar(e),
                       eltern: e.parentElement ? (e.parentElement.tagName.toLowerCase() + ':' + txt(e.parentElement).slice(0, 30)) : '' });
    });
    var o = { ok: true, art: 'augen_inventar_tsx', v: VERSION, ts: Date.now(), url: location.href, titel: document.title,
              lang: document.documentElement.lang || '', sichtbar: document.visibilityState, geo: geo(),
              iframes: alle('iframe').map(function (f) { return { src: String(f.src || '').slice(0, 120), rect: sichtbar(f) ? rect(f) : null }; }),
              shadow: alle('*').filter(function (x) { return !!x.shadowRoot; }).slice(0, 20).map(function (x) { return x.tagName.toLowerCase(); }),
              canvas: alle('canvas').filter(sichtbar).length,
              anzahl: els.length, ueber: els.filter(ueber).length, elemente: liste, blatt: blatt, kaestchen: kaestchen };
    try { o.stand = stand(opts); } catch (e2) { o.stand = { fehler: String(e2) }; }
    // Chart-Sonde (nur lesen) — eigener Schlüssel: inv.chart überschreibt der Bot mit seinem eigenen Chart-Blick
    try { o.chart_sonde = chartSonde({ kompakt: true }); } catch (e3) { o.chart_sonde = { fehler: String(e3).slice(0, 120) }; }
    // Größen-Riegel: erst Blatt-Texte, dann Elemente von hinten kürzen — Overlays stehen vorn und bleiben
    try {
      var n = 0;
      while (JSON.stringify(o).length > INVENTAR_MAX && n++ < 40) {
        // die Chart-Sonde zuerst eindampfen (Prüfer 01.10.2026: sonst gehen die Anker-Elemente für sie drauf), ganz zuletzt ganz raus
        if (o.chart_sonde && !o.chart_sonde.eingedampft) o.chart_sonde = { eingedampft: true, version: o.chart_sonde.version, grund: o.chart_sonde.grund,
          skala: o.chart_sonde.skala, geometrie: o.chart_sonde.geometrie && { pane_host: o.chart_sonde.geometrie.pane_host, pane_quelle: o.chart_sonde.geometrie.pane_quelle, hoehe_passt: o.chart_sonde.geometrie.hoehe_passt },
          umrechnung: o.chart_sonde.umrechnung && { ok: o.chart_sonde.umrechnung.ok, grund: o.chart_sonde.umrechnung.grund, gegenprobe: o.chart_sonde.umrechnung.gegenprobe },
          linien: o.chart_sonde.linien && { anzahl: o.chart_sonde.linien.anzahl, liste: (o.chart_sonde.linien.liste || []).slice(0, 3) } };
        else if (o.blatt.length > 60) o.blatt = o.blatt.slice(0, Math.floor(o.blatt.length * 0.8));
        else if (o.elemente.length > 80) o.elemente = o.elemente.slice(0, Math.floor(o.elemente.length * 0.85));
        else if (o.kaestchen.length > 10) o.kaestchen = o.kaestchen.slice(0, 10);
        else if (o.chart_sonde) delete o.chart_sonde;
        else break;
        o.gekappt = true;
      }
    } catch (_) {}
    return o;
  }

  return { v: VERSION, version: VERSION, plattform: 'topstepx', stand: stand, inventar: inventar, chart_sonde: chartSonde,
           _meldungAus: meldungAus, _geld: geld, _kopfAusTexten: kopfAusTexten, _kontoAusText: kontoAusText, _balanceRelativ: balanceRelativ };   // _…: nur für Tests (reine Textregeln)
})();
// Vertrag T3: globalThis.prophosAugen = { v, stand(), inventar() } — wie augen.js; im TopstepX-Tab gilt diese Datei.
globalThis.prophosAugen = PROPHOS_AUGEN_TSX;
