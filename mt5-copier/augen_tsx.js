/* PROPHOS-AUGEN FÜR TOPSTEPX (30.09.2026, Topstep-Komplett-Paket K1 — Finn: „eine Lösung für alles, immer nur so": Topstep wie
 * Orbit über das eigene Puls-Chrome per CDP, augen = Auge, Windows-Maus = Hand). Eigene Datei neben augen.js (TradingView/
 * Tradovate bleibt unberührt); T3 lädt sie wie augen.js commit-genau und legt sie per Runtime.evaluate als INHALT in den
 * topstepx.com-Tab.
 *
 * Vertrag (wie augen.js): globalThis.prophosAugen = { v, stand(), inventar() } — reines JSON, wirft nie, KLICKT NIE.
 * Rechtecke [x, y, w, h] in CSS-Pixeln relativ zum Viewport; geo trägt screenX/Y, outer/inner, devicePixelRatio.
 * stand() nutzt nur die Schlüssel, die die Route puls_augen durchlässt (app.py puls_augen_saeubern): v, ts, url, titel, geo,
 * sichtbar, fokus, popups, konto, ticket, kauf_knopf, positionen, orders, toasts, konto_summary, fehler — ≤ 60 KB je Zeile.
 *
 * STAND 0.1 (vor dem K0-Inventar): Grundgerüst + Toast-Lesung. Die Toasts sind durch Finns Bilder belegt (tsx-fill-toast.png,
 * tsx-bracket-toasts.webp, 30.09.2026): unten links, je Meldung Haken-Symbol, Titel „Order Filled" / „Order Placed", darunter
 * „+1 MNQZ26 Market" + „Execute Price: 30,592.25" bzw. „-1 MNQZ26 Stop Market @ 30,586.25" (SL) / „-1 MNQZ26 Limit @ 30,597.75"
 * (TP), X oben rechts. Gelesen wird deshalb NUR über diese Texte und die Geometrie (kein Klassen-/data-Anker geraten).
 * Konto-Auslöser, BAL/MLL, Manage brackets, Risk/Profit, Contract, Kauf-Knopf und Reiter kommen erst mit dem K0-Inventar
 * (puls_augen 'inventar_tsx_*') — bis dahin bleiben konto/ticket/kauf_knopf/konto_summary null, positionen/orders leer.
 */
var PROPHOS_AUGEN_TSX = (function () {
  'use strict';
  var VERSION = 'tsx-0.1.0';

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
  function txt(el) { return String((el && el.textContent) || '').replace(/\s+/g, ' ').trim(); }
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
      meldungen.forEach(function (m) { var s = [m.art, m.status, m.seite, m.menge, m.symbol, m.typ, m.preis].join('|'); if (!merk[s]) merk[s] = jetzt; m.erst_gesehen = merk[s]; });
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

  // ── Öffentliche Funktionen ─────────────────────────────────────────────────
  var STAND_MAX = 48000;
  function stand(opts) {
    opts = opts || {};
    var fehler = [];
    var g = geo(); g.lang = document.documentElement.lang || '';
    var o = { v: VERSION, ts: Date.now(), url: location.href, titel: document.title, geo: g, sichtbar: document.visibilityState, fokus: fokus(),
              popups: [], konto: null, ticket: null, kauf_knopf: null, positionen: [], orders: [], toasts: null, konto_summary: null };
    try { o.toasts = toasts(); } catch (e) { fehler.push('toasts: ' + e); }
    try { o.popups = dialoge(); } catch (e) { fehler.push('popups: ' + e); }
    try {
      if (JSON.stringify(o).length > STAND_MAX) {
        if (o.toasts) { o.toasts.gruppen = (o.toasts.gruppen || []).slice(0, 6); o.toasts.meldungen = (o.toasts.meldungen || []).slice(0, 10); }
        o.popups = (o.popups || []).slice(0, 4);
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
    function klasse(e) { var c = typeof e.className === 'string' ? e.className : (e.className && e.className.baseVal) || ''; return c.replace(/\s+/g, ' ').trim().slice(0, 80); }
    var sel = 'button,a[href],[role],input,select,textarea,[data-testid],[data-test],[data-cy],[aria-label],[id],[name],[title],th,label';
    var els = alle(sel).filter(sichtbar), liste = [];
    for (var i = 0; i < els.length && liste.length < 450; i++) {
      var e = els[i], t = txt(e);
      if (t.length > 120 && !attr(e, 'role') && !testid(e)) continue;   // Hüllen mit viel Text sind Rauschen
      liste.push(kurz(e, { zone: zone(e), cls: klasse(e) || undefined, name: attr(e, 'name') || undefined, title: attr(e, 'title') || undefined,
                           ph: attr(e, 'placeholder') || undefined, zu: zustand(e) }));
    }
    // Blatt-Texte: sichtbare Elemente ohne Element-Kinder mit kurzem Text (Kopfzahlen, Symbole, Reiter-Namen)
    var blatt = [];
    alle('body *').forEach(function (e) {
      if (blatt.length >= 320 || e.children.length || !sichtbar(e)) return;
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
              anzahl: els.length, elemente: liste, blatt: blatt, kaestchen: kaestchen };
    try { o.stand = stand(opts); } catch (e2) { o.stand = { fehler: String(e2) }; }
    // Größen-Riegel: erst Blatt-Texte, dann Elemente von hinten kürzen — nie den Kopf
    try {
      var n = 0;
      while (JSON.stringify(o).length > INVENTAR_MAX && n++ < 40) {
        if (o.blatt.length > 60) o.blatt = o.blatt.slice(0, Math.floor(o.blatt.length * 0.8));
        else if (o.elemente.length > 80) o.elemente = o.elemente.slice(0, Math.floor(o.elemente.length * 0.85));
        else if (o.kaestchen.length > 10) o.kaestchen = o.kaestchen.slice(0, 10);
        else break;
        o.gekappt = true;
      }
    } catch (_) {}
    return o;
  }

  return { v: VERSION, version: VERSION, plattform: 'topstepx', stand: stand, inventar: inventar,
           _meldungAus: meldungAus };   // _meldungAus: nur für Tests (reine Textregel)
})();
// Vertrag T3: globalThis.prophosAugen = { v, stand(), inventar() } — wie augen.js; im TopstepX-Tab gilt diese Datei.
globalThis.prophosAugen = PROPHOS_AUGEN_TSX;
