-- PULS-FEHLERFOTO: Bildschirmfoto als PNG (29.10.2026, Slave 7). Wiederholbar. Master spielt nach Prüfer-OK ein.
--
-- Anlass (Live-Befund .1853): 0/5 Bildschirmfotos — Windows Defender/AMSI blockte das PowerShell-Skript (CopyFromScreen) als
-- ScriptContainedMaliciousContent; die Tab-Fotos (CDP, JPEG) liefen 5/5. Der Bot nimmt den Bildschirm jetzt per GDI (Python ctypes) auf
-- und kodiert ohne pip als PNG (zlib). Der Bucket nahm bisher nur image/jpeg an → PNG dazu. Größe (400 KB), privat, keine Policies: unverändert.
update storage.buckets
   set allowed_mime_types = array['image/jpeg', 'image/png']
 where id = 'puls-fehlerbilder';

-- Kontrolle:
-- select id, public, file_size_limit, allowed_mime_types from storage.buckets where id = 'puls-fehlerbilder';   -- {image/jpeg,image/png}
