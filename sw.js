/* ============================================================
   PROPHOS — Service Worker fuer Handy-Benachrichtigungen
   22.09.2026, Finn: "gehts nicht ans handy" / "prophos liegt auf
   meinem home bildschirm".

   WARUM ES DIESE DATEI GEBEN MUSS — und warum sie die Single-File-
   Doktrin NICHT bricht:
   iOS zeigt Web-Benachrichtigungen ausschliesslich ueber einen
   Service Worker. Den `new Notification(...)`-Weg, den prophos.html
   bisher benutzt hat (News-Alerts, Auto-Close), kennt iOS nicht —
   auch nicht in der auf dem Home-Bildschirm installierten Web-App.
   Die Erlaubnis-Abfrage erscheint, und danach passiert nichts.
   Ein Service Worker MUSS eine eigene Datei mit eigenem Scope sein;
   inline im HTML geht es prinzipiell nicht.

   Das ist trotzdem kein Bruch der Regel "prophos.html bleibt EINE
   Datei": Cloudflare Pages liefert die Nachbardateien aus dem Repo
   ohnehin aus (die App-Icons aus dem Manifest kommen genau so, mit
   200). Diese Datei liegt also unter https://prophos.pages.dev/sw.js
   ohne jedes Zutun. Gefaehrlich waere nur, prophos.html in js/css zu
   zerlegen — DAS wuerde auf den lokalen PCs gegen localhost:5000
   aufloesen. Fuer genau diesen Fall proxyt app.py /sw.js von
   pages.dev nach (siehe dort), damit die PC-Tabs dieselbe Datei
   bekommen und nicht in ein 404 laufen.

   Der Worker ist BEWUSST duemmlich gehalten: anzeigen und oeffnen,
   sonst nichts. Alles, was Zustand braucht (An-/Abmelden, Schluessel,
   Geraeteliste), macht die Seite — ein Worker, der sich selbst
   neu anmeldet, muesste den VAPID-Schluessel kennen und ueber
   Origin-Grenzen hinweg beim Backend nachfragen. Die Seite kann das
   bei jedem Laden billiger und sichtbarer.
============================================================ */

const PROPHOS_URL  = 'https://prophos.pages.dev/prophos'
const PROPHOS_ICON = 'https://prophos.pages.dev/prophos-icon-192.png'

/* Sofort uebernehmen statt auf das Schliessen aller Tabs zu warten.
   Finns stehende Regel (17.09.2026): Updates kommen ueberall von
   selbst an, "starte X neu" ist kein Handgriff, den er machen soll.
   Ohne skipWaiting/claim liefe nach einem Deploy noch tagelang der
   alte Worker — und ein Fehler darin waere unreparierbar. */
self.addEventListener('install',  () => self.skipWaiting())
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()))

self.addEventListener('push', event => {
  // Ohne Nutzdaten trotzdem etwas zeigen: eine Push, die nichts
  // anzeigt, wertet der Browser als Missbrauch und kann die
  // Berechtigung entziehen.
  let d = {}
  try { d = event.data ? event.data.json() : {} } catch (_) { d = {} }

  const titel = d.titel || 'Prophos'
  const text  = d.text  || ''
  const opts  = {
    body: text,
    icon: PROPHOS_ICON,
    badge: PROPHOS_ICON,
    // tag faltet Nachfolger zusammen: zehn Ticks "Copier eingefroren"
    // sollen EINE Meldung sein, nicht zehn Zeilen im Sperrbildschirm.
    tag: d.tag || 'prophos',
    renotify: !!d.renotify,
    data: { url: d.url || PROPHOS_URL },
    timestamp: Date.now(),
  }
  event.waitUntil(self.registration.showNotification(titel, opts))
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  const ziel = (event.notification.data && event.notification.data.url) || PROPHOS_URL
  event.waitUntil((async () => {
    const liste = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    // Schon offen? Dann dorthin, statt ein zweites Fenster aufzumachen.
    // Der Vergleich geht ueber den Ursprung, nicht ueber die ganze
    // Adresse — der Hash (#trades) unterscheidet sich ja gerade.
    for (const c of liste) {
      try {
        if (new URL(c.url).origin === new URL(ziel).origin) {
          await c.focus()
          if ('navigate' in c) { try { await c.navigate(ziel) } catch (_) {} }
          return
        }
      } catch (_) {}
    }
    await self.clients.openWindow(ziel)
  })())
})
