# -*- coding: utf-8 -*-
"""foto-schuss.py — Bildschirmfoto aller Monitore als PNG, reines Python ohne pip (01.11.2026, Auftrag FOTO, Fernzugriff).

Warum Python statt PowerShell: Windows Defender/AMSI blockte am 29.10.2026 das CopyFromScreen-Skript des Puls-Fehlerfotos als
ScriptContainedMaliciousContent (0 von 5 Fotos). Seitdem fotografiert Puls in order_bot.py per GDI/ctypes — derselbe Weg hier:
BitBlt des ganzen virtuellen Bildschirms (SRCCOPY | CAPTUREBLT, DPI-bewusst) + GetDIBits, PNG aus der Standardbibliothek (zlib).
Scheitert BitBlt (UAC-/Sperr-Desktop, getrennte Sitzung), Rückfall PrintWindow auf das vordere bzw. größte sichtbare Fenster.

Gestartet von der geplanten Aufgabe „Prophos Foto“ (foto-aufgabe.ps1) per pythonw.exe in der ANGEMELDETEN Sitzung — eine
SSH-Sitzung (Session 0) sieht den Desktop nicht. Harte Regel: nur lesen. Kein Klick, keine Taste, kein Fokus, kein Fenster.

Ablage: C:\\mt5-copier\\fernzugriff\\fotos\\<JJJJMMTT-hhmmss>.png (erst .tmp, dann umbenannt — foto.ps1 sieht nur fertige
Bilder). Fehlergrund in fehler.txt daneben. Fotos älter als 7 Tage löscht jeder Schuss selbst. Python liegt auf jedem PC (Copier).
"""
import ctypes
import os
import struct
import sys
import time
import zlib

# Bilder + fehler.txt/hinweis.txt NEBEN dem Skriptordner (…\fernzugriff\fotos), nicht darin: setup-pc.ps1 löscht fernzugriff\foto\
# bei jedem erneuten Setup komplett und kopiert es neu (Betrieb 1, 01.11.2026) — Fotos dürfen dabei nicht verschwinden.
ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fotos")
FEHLER = os.path.join(ORDNER, "fehler.txt")
TAGE_BEHALTEN = 7


# ── rein rechnend ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def bgra_zu_rgb(bgra, w, h):
    """BGRA (oben→unten, 4 Byte je Punkt) → RGB-Bytes, volle Größe. Drei Slice-Zuweisungen in C statt Schleife je Punkt."""
    mv = memoryview(bgra)
    out = bytearray(w * h * 3)
    out[0::3] = mv[2::4]   # R
    out[1::3] = mv[1::4]   # G
    out[2::3] = mv[0::4]   # B
    return bytes(out)


def png_bauen(rgb, w, h):
    """PNG (8 Bit RGB, Zeilenfilter 0) aus RGB-Bytes — wie fehlerfoto_png in order_bot.py, ohne Palette."""
    def stueck(typ, inhalt):
        return struct.pack(">I", len(inhalt)) + typ + inhalt + struct.pack(">I", zlib.crc32(typ + inhalt) & 0xFFFFFFFF)
    if len(rgb) != w * h * 3:
        raise ValueError("Datenlänge passt nicht zu Breite × Höhe")
    roh = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))
    kopf = stueck(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    return b"\x89PNG\r\n\x1a\n" + kopf + stueck(b"IDAT", zlib.compress(roh, 6)) + stueck(b"IEND", b"")


def fenster_wahl(fenster):
    """Ziel für den PrintWindow-Rückfall (wie fehlerfoto_fenster_wahl): vorn, sonst MetaTrader, sonst das größte sichtbare."""
    gut = [f for f in fenster if f["sichtbar"] and not f["minimiert"] and f["w"] >= 300 and f["h"] >= 200]
    vorne = [f for f in gut if f["vorne"]]
    if vorne:
        return vorne[0]["hwnd"]
    mt5 = [f for f in gut if f["klasse"] == "MetaQuotes::MetaTrader::5.00"]
    for liste in (mt5, gut):
        if liste:
            return max(liste, key=lambda f: f["w"] * f["h"])["hwnd"]
    return None


# ── Windows (GDI per ctypes) ────────────────────────────────────────────────────────────────────────────────────────────────
def _gdi():
    from ctypes import wintypes as wt
    u32, g32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    for f, arg, res in ((u32.GetSystemMetrics, [ctypes.c_int], ctypes.c_int), (u32.GetDC, [wt.HWND], wt.HDC),
                        (u32.ReleaseDC, [wt.HWND, wt.HDC], ctypes.c_int), (u32.GetForegroundWindow, [], wt.HWND),
                        (u32.IsWindowVisible, [wt.HWND], wt.BOOL), (u32.IsIconic, [wt.HWND], wt.BOOL),
                        (u32.GetWindowRect, [wt.HWND, ctypes.POINTER(wt.RECT)], wt.BOOL),
                        (u32.GetClassNameW, [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int),
                        (u32.GetWindowTextW, [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int),
                        (u32.PrintWindow, [wt.HWND, wt.HDC, wt.UINT], wt.BOOL),
                        (g32.CreateCompatibleDC, [wt.HDC], wt.HDC),
                        (g32.CreateCompatibleBitmap, [wt.HDC, ctypes.c_int, ctypes.c_int], wt.HBITMAP),
                        (g32.SelectObject, [wt.HDC, wt.HGDIOBJ], wt.HGDIOBJ), (g32.DeleteObject, [wt.HGDIOBJ], wt.BOOL),
                        (g32.DeleteDC, [wt.HDC], wt.BOOL),
                        (g32.BitBlt, [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD], wt.BOOL),
                        (g32.GetDIBits, [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT], ctypes.c_int)):
        f.argtypes, f.restype = arg, res
    return u32, g32


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


def _abgreifen(u32, g32, w, h, malen, name):
    """Gemeinsamer Teil von BitBlt und PrintWindow: Speicher-DC + Bitmap, malen(mdc) → True, GetDIBits oben→unten. -> bgra"""
    hdc = u32.GetDC(None)
    if not hdc:
        raise RuntimeError("GetDC gescheitert (keine Desktop-Sitzung?)")
    mdc, bmp = g32.CreateCompatibleDC(hdc), g32.CreateCompatibleBitmap(hdc, w, h)
    try:
        if not mdc or not bmp:
            raise RuntimeError("GDI-Speicher nicht angelegt")
        alt = g32.SelectObject(mdc, bmp)
        ok = malen(mdc, hdc)
        g32.SelectObject(mdc, alt)                     # GetDIBits nur mit nicht ausgewählter Bitmap
        if not ok:
            raise RuntimeError("%s gescheitert" % name)
        bi = _BIH(ctypes.sizeof(_BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)   # negative Höhe = oben→unten, BI_RGB
        puf = ctypes.create_string_buffer(w * h * 4)
        if g32.GetDIBits(mdc, bmp, 0, h, puf, ctypes.byref(bi), 0) != h:
            raise RuntimeError("GetDIBits las nicht alle Zeilen")
        return puf.raw
    finally:
        if bmp:
            g32.DeleteObject(bmp)
        if mdc:
            g32.DeleteDC(mdc)
        u32.ReleaseDC(None, hdc)


def bildschirm():
    """Ganzer virtueller Bildschirm (alle Monitore) per BitBlt. -> (bgra, w, h)"""
    u32, g32 = _gdi()
    try:
        ctypes.WinDLL("user32").SetProcessDPIAware()   # System-DPI-aware (S11-Hinweis: bei 2 Monitoren mit verschiedener Skalierung
    except Exception:                                   # fehlt ein Teil — die PCs haben einen Dummy-Stecker, also egal)
        pass
    x, y, w, h = (u32.GetSystemMetrics(i) for i in (76, 77, 78, 79))   # SM_X/Y/CX/CYVIRTUALSCREEN
    if w <= 0 or h <= 0:
        raise RuntimeError("Bildschirmgröße unbekannt (%d×%d)" % (w, h))
    bgra = _abgreifen(u32, g32, w, h, lambda mdc, hdc: g32.BitBlt(mdc, 0, 0, w, h, hdc, x, y, 0x00CC0020 | 0x40000000), "BitBlt")  # SRCCOPY|CAPTUREBLT
    return bgra, w, h


def fenster():
    """Rückfall: ein Fenster per PrintWindow (PW_RENDERFULLCONTENT). -> (bgra, w, h, titel)"""
    from ctypes import wintypes as wt
    u32, g32 = _gdi()
    vorn = u32.GetForegroundWindow()
    liste = []
    ENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def _je(hwnd, _l):
        r, k = wt.RECT(), ctypes.create_unicode_buffer(128)
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        u32.GetClassNameW(hwnd, k, 128)
        liste.append({"hwnd": hwnd, "sichtbar": bool(u32.IsWindowVisible(hwnd)), "minimiert": bool(u32.IsIconic(hwnd)),
                      "w": r.right - r.left, "h": r.bottom - r.top, "klasse": k.value, "vorne": bool(vorn) and hwnd == vorn})
        return True
    u32.EnumWindows(ENUM(_je), 0)
    hwnd = fenster_wahl(liste)
    if not hwnd:
        raise RuntimeError("kein sichtbares Fenster für PrintWindow")
    f = next(x for x in liste if x["hwnd"] == hwnd)
    w, h = f["w"], f["h"]
    t = ctypes.create_unicode_buffer(120)
    u32.GetWindowTextW(hwnd, t, 120)
    bgra = _abgreifen(u32, g32, w, h, lambda mdc, hdc: u32.PrintWindow(hwnd, mdc, 2), "PrintWindow")   # PW_RENDERFULLCONTENT
    return bgra, w, h, t.value


def desktop_diag():
    """Warum der Bildschirm nicht lesbar ist (Eingabe-Desktop), für fehler.txt. Nie ein Fehler."""
    try:
        from ctypes import wintypes as wt
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        u32.OpenInputDesktop.argtypes, u32.OpenInputDesktop.restype = [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE
        u32.GetUserObjectInformationW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
        u32.CloseDesktop.argtypes = [wt.HANDLE]
        hd = u32.OpenInputDesktop(0, False, 0x0001)   # DESKTOP_READOBJECTS
        if not hd:
            return "Eingabe-Desktop nicht lesbar (Fehler %d) — UAC/Sperrbildschirm?" % ctypes.get_last_error()
        puf, n = ctypes.create_unicode_buffer(64), wt.DWORD(0)
        name = puf.value if u32.GetUserObjectInformationW(hd, 2, puf, ctypes.sizeof(puf), ctypes.byref(n)) else "?"   # UOI_NAME
        u32.CloseDesktop(hd)
        return "Eingabe-Desktop %s" % (name or "?")
    except Exception as e:
        return "Desktop unbekannt (%s)" % type(e).__name__


# ── Ablauf ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _schreiben(pfad, text):
    """Textdatei atomar (erst .tmp, dann os.replace), damit foto.ps1 nie eine halb geschriebene Datei liest."""
    with open(pfad + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(pfad + ".tmp", pfad)


def aufraeumen():
    grenze = time.time() - TAGE_BEHALTEN * 86400
    for name in os.listdir(ORDNER):
        p = os.path.join(ORDNER, name)
        try:
            if name.endswith(".png") and os.path.getmtime(p) < grenze:
                os.remove(p)
            elif name.endswith(".tmp") and os.path.getmtime(p) < time.time() - 300:   # Reste abgebrochener Schüsse
                os.remove(p)
        except OSError:
            pass


def main():
    os.makedirs(ORDNER, exist_ok=True)
    try:
        hinweis = ""
        try:
            bgra, w, h = bildschirm()
        except Exception as e:
            diag = desktop_diag()
            try:
                bgra, w, h, titel = fenster()
            except Exception as e2:
                raise RuntimeError("%s · Rückfall PrintWindow: %s · %s" % (e, e2, diag))
            hinweis = "Rückfall PrintWindow (%s) · %s" % ((titel or "?")[:40], diag)
        png = png_bauen(bgra_zu_rgb(bgra, w, h), w, h)
        name = time.strftime("%Y%m%d-%H%M%S")
        tmp, ziel = os.path.join(ORDNER, name + ".tmp"), os.path.join(ORDNER, name + ".png")
        with open(tmp, "wb") as f:
            f.write(png)
        # hinweis.txt VOR dem Umbenennen setzen/löschen: foto.ps1 liest sie sofort, wenn das PNG auftaucht (Review 01.11.2026).
        hinweis_pfad = os.path.join(ORDNER, "hinweis.txt")
        if hinweis:   # Bild da, aber nur ein Fenster: Grund dazu, foto.ps1 gibt trotzdem den Pfad aus
            _schreiben(hinweis_pfad, hinweis)
        elif os.path.exists(hinweis_pfad):
            os.remove(hinweis_pfad)
        if os.path.exists(FEHLER):
            os.remove(FEHLER)
        os.replace(tmp, ziel)
        aufraeumen()
        return 0
    except Exception as e:
        try:
            _schreiben(FEHLER, "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), e))
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
