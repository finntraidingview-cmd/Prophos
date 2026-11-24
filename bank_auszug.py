"""Kontoauszüge je Bankkonto + KI-Abgleich — Admin → Finanzen → Bankkonto → Detail (BK6, 25.11.2026).

Finn: „Ja zum Kontoauszug-Upload". Konstrukt side-session-notes/…/2026-11-25_BK6_kontoauszug_konstrukt.md, Standardwerte (Master):
Auszüge 12 Monate aufbewahren, Erinnerung nur in der Liste, Datum ±3 Tage.

  1 Hochladen   POST /admin/bank/auszug {konto_id, name, typ pdf|csv, daten base64} → privater Bucket „kontoauszuege" + Zeile
  2 Auslesen    Hintergrund-Thread: CSV direkt (Spalten erkennen), PDF über die Claude-API (ANTHROPIC_API_KEY wie ai_advisor.py)
  3 Abgleich    rein rechnend (abgleich): ✓ passt (Betrag auf Cent, Datum ±3 Tage) · fehlt in Prophos · nur in Prophos · Saldo-Differenz
  4 Übernehmen  nie automatisch — POST /admin/bank/auszug/uebernehmen legt nur die angeklickten Zeilen an (quelle 'auszug')

Gate und Konto-Rechte wie bank_app (Kapital-Gate, Verwalter nur seine Gruppe). Inhalte (IBAN, Zeilen, Texte) nie in Logs, URLs oder
Fehlerantworten — Fehler nur als fester Text bzw. Fehlertyp.
"""
import base64
import csv
import io
import json
import os
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone

from flask import request, jsonify

import kapital_app as K

A = {}
B = None                        # bank_app (für _konto_erlaubt, VORZEICHEN, ARTEN) — gesetzt in registrieren()

BUCKET = "kontoauszuege"
MAX_BYTES = 10 * 1024 * 1024
TOLERANZ_TAGE = 3               # Master 25.11.2026
AUFBEWAHREN_TAGE = 365          # Master 25.11.2026: 12 Monate
FAELLIG_TAGE = 21               # Erinnerung „Auszug fällig" (nur in der Liste)
MODELL = os.environ.get("BANK_AUSZUG_MODEL", "claude-sonnet-5-5")
_aufgeraeumt = {"at": 0.0}

PROP_RE = re.compile(r"topstep|apex|tradeify|lucid|ftmo|funded ?next|funding ?pips|5ers|the5|blue ?guardian|alpha ?capital|"
                     r"fusion|rise|deel|payout|auszahlung", re.I)


# ── rein rechnend (Selbsttest) ────────────────────────────────────────────────────────────────────────────────────────────────────
def zahl(v):
    """„1.234,56" / „1,234.56" / „-12,50" / 12.5 → float; nichts Lesbares → None."""
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-+]", "", str(v or "").replace("−", "-"))
    if not re.search(r"\d", s):
        return None
    minus = s.startswith("-") or s.endswith("-")          # „123,45-" (Minus hinten, manche Banken)
    s = s.strip("+-")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(".") > 1 or s.count(",") > 1:              # „1.234.567" / „1,234,567" = nur Tausender
        s = s.replace(".", "").replace(",", "")
    else:
        t = "," if "," in s else "." if "." in s else ""
        if t:
            ganz, nach = s.split(t)
            # genau 3 Nachstellen und vorne keine 0 → Tausender („1.000", „1,500"); sonst Dezimal („12,50", „0,125")
            s = ganz + nach if len(nach) == 3 and ganz.lstrip("0") else ganz + "." + nach
    try:
        return -float(s) if minus else float(s)
    except ValueError:
        return None


def datum(v):
    """„2026-11-24 10:12:00" / „24.11.2026" / „24/11/2026" / „24.11.26" → „2026-11-24"; sonst None."""
    s = str(v or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"(\d{1,2})([./])(\d{1,2})[./](\d{2,4})", s)
        if not m:
            return None
        d, trenner, mo, y = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
        if trenner == "/" and mo > 12 >= d:                 # „11/24/2026" geht nur als MM/DD
            d, mo = mo, d
        y += 2000 if y < 100 else 0
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


_SP = {
    "datum": ("completed date", "started date", "buchungsdatum", "buchungstag", "datum", "date", "valuta", "wertstellung"),
    "betrag": ("amount", "betrag (eur)", "betrag", "umsatz", "summe"),
    "gebuehr": ("fee", "gebühr", "gebuehr"),
    "text": ("description", "beschreibung", "verwendungszweck", "buchungstext", "empfänger", "empfaenger", "name", "reference"),
    "saldo": ("balance", "saldo", "kontostand"),
    "status": ("state", "status"),
    "waehrung": ("currency", "währung", "waehrung"),
}


def csv_lesen(text):
    """CSV-Auszug (Revolut u. a.) → {zeilen, von, bis, endsaldo, waehrung}. Ohne KI. Nicht abgeschlossene Revolut-Zeilen fallen weg."""
    text = text.lstrip("﻿")
    try:
        dialekt = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialekt = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialekt))
    if len(rows) < 2:
        raise ValueError("CSV ohne Zeilen")
    kopf = [str(h).strip().lower() for h in rows[0]]
    sp = {}
    for feld, namen in _SP.items():
        for n in namen:                      # Reihenfolge = Vorrang (Completed Date vor Started Date)
            if n in kopf:
                sp[feld] = kopf.index(n)
                break
    if "datum" not in sp or "betrag" not in sp:
        raise ValueError("CSV: Datum- oder Betrag-Spalte nicht gefunden")
    zeilen, saldo_je, uebersprungen = [], [], 0
    for r in rows[1:]:
        get = lambda f: r[sp[f]] if f in sp and sp[f] < len(r) else ""
        if "status" in sp and get("status").strip().upper() not in ("", "COMPLETED", "ABGESCHLOSSEN", "GEBUCHT"):
            continue
        d, b = datum(get("datum")), zahl(get("betrag"))
        if not d or b is None:
            uebersprungen += 1 if any(str(x).strip() for x in r) else 0
            continue
        b -= abs(zahl(get("gebuehr")) or 0.0)            # Revolut: Amount ohne Fee
        if round(b, 2) == 0:
            continue
        zeilen.append({"datum": d, "betrag": round(b, 2), "text": get("text").strip()[:200], "gegenseite": ""})
        s = zahl(get("saldo"))
        if s is not None:
            saldo_je.append((d, len(zeilen), s))
    if not zeilen:
        raise ValueError("CSV: keine gebuchten Zeilen")
    tage = sorted(z["datum"] for z in zeilen)
    endsaldo = None
    if saldo_je:
        # Review BK6: viele Banken exportieren die neueste Zeile OBEN → am jüngsten Tag dann die erste Zeile, sonst die letzte
        absteigend = zeilen[0]["datum"] > zeilen[-1]["datum"]
        juengst = [x for x in saldo_je if x[0] == max(x[0] for x in saldo_je)]
        endsaldo = (min(juengst, key=lambda x: x[1]) if absteigend else max(juengst, key=lambda x: x[1]))[2]
    wae = ""
    if "waehrung" in sp:
        werte = {r[sp["waehrung"]].strip().upper() for r in rows[1:] if sp["waehrung"] < len(r) and r[sp["waehrung"]].strip()}
        wae = werte.pop() if len(werte) == 1 else ""
    return {"zeilen": zeilen, "von": tage[0], "bis": tage[-1], "endsaldo": endsaldo, "waehrung": wae or None, "uebersprungen": uebersprungen}


def ki_antwort_lesen(txt):
    """Antwort der Claude-API → geprüftes Ergebnis wie csv_lesen (+ vorschlag). Ungültige Zeilen fallen weg."""
    a, e = txt.find("{"), txt.rfind("}")
    if a < 0 or e <= a:
        raise ValueError("KI-Antwort ohne JSON")
    d = json.loads(txt[a:e + 1])
    zeilen = []
    for z in (d.get("zeilen") or [])[:3000]:
        dt, b = datum(z.get("datum")), zahl(z.get("betrag"))
        if dt and b is not None and round(b, 2) != 0:
            zeilen.append({"datum": dt, "betrag": round(b, 2), "text": str(z.get("text") or "").strip()[:200],
                           "gegenseite": str(z.get("gegenseite") or "").strip()[:120]})
    if not zeilen:
        raise ValueError("KI: keine Buchungszeilen erkannt")
    tage = sorted(z["datum"] for z in zeilen)
    v = d.get("vorschlag") if isinstance(d.get("vorschlag"), dict) else {}
    vorschlag = {k: str(v.get(k) or "").strip()[:120] or None for k in ("bank", "inhaber", "iban")}
    if vorschlag.get("iban") is not None:
        vorschlag["iban"] = (B.iban_normal(vorschlag["iban"]) or None) if B else vorschlag["iban"]   # ungültige Prüfziffer → kein Vorschlag
    es = zahl(d.get("endsaldo"))
    return {"zeilen": zeilen, "von": datum(d.get("von")) or tage[0], "bis": datum(d.get("bis")) or tage[-1],
            "endsaldo": round(es, 2) if es is not None else None, "waehrung": (str(d.get("waehrung") or "").upper()[:3] or None),
            "vorschlag": vorschlag if any(vorschlag.values()) else None}


def art_vorschlag(betrag, text):
    """Art für eine Zeile, die nur im Auszug steht (BK4-Arten): + Prop-Firma/Payout → Payout, + sonst → Zahlung von HT,
    − Prop-Firma/Gebühr → Account-Kauf, − sonst → Zahlung an HT. Nur Vorschlag — Finn ändert ihn im Dropdown."""
    t = str(text or "")
    if betrag > 0:
        return "Payout" if PROP_RE.search(t) else "Zahlung von HT"
    return "Account-Kauf" if PROP_RE.search(t) or re.search(r"geb(ü|ue)hr|fee", t, re.I) else "Zahlung an HT"


def _tag(s):
    return date.fromisoformat(str(s)[:10])


def abgleich(zeilen, buchungen, start_saldo=0.0, von=None, bis=None, endsaldo=None, tol=TOLERANZ_TAGE, auszug_id=None):
    """Auszug ↔ Buchungen eines Kontos. passt = gleicher Betrag (auf Cent) und Datum ±tol Tage, je Buchung höchstens einmal (nächstes
    Datum gewinnt). fehlt = Auszug-Zeilen ohne Partner (mit Art-Vorschlag), nur = Buchungen im Zeitraum von..bis ohne Partner,
    differenz = Endsaldo − Saldo Prophos am Tag „bis". → dict"""
    tage = sorted(z["datum"] for z in zeilen) if zeilen else []
    von = von or (tage[0] if tage else None)
    bis = bis or (tage[-1] if tage else None)
    frei = [b for b in buchungen if b.get("datum")]
    # 1) aus GENAU diesem Auszug übernommene Buchungen gehören fest zu ihrer Zeile (Review BK6: sonst nach Vorzeichen-/Datumsänderung
    #    wieder „fehlt" → Doppelbuchung)
    fest = {}
    for b in frei:
        if auszug_id and str(b.get("auszug_id") or "") == str(auszug_id) and b.get("auszug_zeile") is not None:
            fest.setdefault(int(b["auszug_zeile"]), b["id"])
    # 2) übrige: größtmögliche Zuordnung (Kuhn) — je Zeile die Kandidaten nach Abstand sortiert, damit bei gleicher Anzahl der nähere gewinnt
    benutzt = set(fest.values())
    kand = {}
    for i, z in enumerate(zeilen):
        if i in fest:
            continue
        zt, zb = _tag(z["datum"]), round(float(z["betrag"]), 2)
        c = [((abs((_tag(b["datum"]) - zt).days), str(b["datum"])), b["id"]) for b in frei
             if b["id"] not in benutzt and abs(round(float(b["betrag"]), 2) - zb) < 0.005 and abs((_tag(b["datum"]) - zt).days) <= tol]
        kand[i] = [bid for _, bid in sorted(c)]
    partner = {}                                       # buchung_id → zeile

    def _versuch(i, gesehen):
        for bid in kand.get(i, []):
            if bid in gesehen:
                continue
            gesehen.add(bid)
            if bid not in partner or _versuch(partner[bid], gesehen):
                partner[bid] = i
                return True
        return False
    for i in sorted(kand, key=lambda i: (zeilen[i]["datum"], i)):
        _versuch(i, set())
    zu = {i: bid for bid, i in partner.items()}
    zu.update(fest)
    benutzt |= set(partner)
    passt, fehlt = [], []
    for i, z in enumerate(zeilen):
        if i in zu:
            passt.append({"i": i, "buchung_id": zu[i]})
        else:
            zb = round(float(z["betrag"]), 2)
            fehlt.append({"i": i, "art": art_vorschlag(zb, (z.get("text") or "") + " " + (z.get("gegenseite") or ""))})
    nur = [b["id"] for b in frei if b["id"] not in benutzt and von and bis and von <= str(b["datum"])[:10] <= bis]
    saldo_prophos = round(float(start_saldo or 0) + sum(float(b["betrag"]) for b in frei if not bis or str(b["datum"])[:10] <= bis), 2)
    differenz = round(float(endsaldo) - saldo_prophos, 2) if endsaldo is not None else None
    return {"passt": passt, "fehlt": fehlt, "nur": nur, "von": von, "bis": bis, "saldo_prophos": saldo_prophos, "differenz": differenz}


def faellig(letzter, heute=None):
    """Tage seit dem letzten Auszug (Ende des Zeitraums, sonst Upload-Tag); fällig ab FAELLIG_TAGE. Kein Auszug → None (keine Erinnerung)."""
    if not letzter:
        return None
    heute = heute or datetime.now(timezone.utc).date()
    tage = (heute - _tag(letzter)).days
    return tage if tage >= FAELLIG_TAGE else None


# ── Speicher + KI ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _storage(methode, pfad, **kw):
    h = {"apikey": A["SUPABASE_SERVICE_KEY"], "Authorization": f"Bearer {A['SUPABASE_SERVICE_KEY']}"}
    h.update(kw.pop("headers", {}))
    return A["_SB_SESSION"].request(methode, f"{A['SUPABASE_URL']}/storage/v1/{pfad}", headers=h, timeout=kw.pop("timeout", 30), **kw)


def _pdf_lesen(roh):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt auf Railway — PDF nicht lesbar (CSV geht ohne)")
    from anthropic import Anthropic
    anweisung = (
        "Das ist ein Kontoauszug. Gib NUR JSON zurück, ohne Text davor oder danach:\n"
        '{"von":"JJJJ-MM-TT","bis":"JJJJ-MM-TT","endsaldo":Zahl,"waehrung":"EUR",'
        '"vorschlag":{"bank":"…","inhaber":"…","iban":"…"},'
        '"zeilen":[{"datum":"JJJJ-MM-TT","betrag":Zahl,"text":"…","gegenseite":"…"}]}\n'
        "Regeln: jede gebuchte Umsatzzeile genau einmal; betrag mit Vorzeichen (Eingang +, Ausgang −) inklusive Gebühren dieser Zeile; "
        "ausstehende/stornierte Zeilen weglassen; endsaldo = Kontostand am Ende des Zeitraums; vorschlag = Bank, Inhaber und IBAN DIESES "
        "Kontos aus dem Kopf (falls lesbar). Nie Kartennummern, nie IBANs der Gegenseite (gegenseite nur der Name).")
    # Streaming (Review BK6): lange Auszüge brauchen viele Ausgabe-Tokens; ohne Stream bricht das SDK bei großem max_tokens ab
    with Anthropic(api_key=key, timeout=600).messages.stream(
            model=MODELL, max_tokens=48000,
            messages=[{"role": "user", "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(roh).decode()}},
                {"type": "text", "text": anweisung}]}]) as st:
        msg = st.get_final_message()
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("Auszug zu lang für das Auslesen — bitte als CSV exportieren oder kürzeren Zeitraum hochladen")
    if msg.stop_reason == "refusal":
        raise RuntimeError("Die KI hat das Auslesen abgelehnt — bitte als CSV hochladen")
    txt = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
    return ki_antwort_lesen(txt)


def _lesen(auszug_id, roh, typ):
    """Hintergrund: Datei auslesen und Ergebnis in die Zeile schreiben. Fehler nur als Text ohne Inhalt."""
    try:
        A["sb_update"]("bank_auszuege", {"id": f"eq.{auszug_id}"}, {"status": "liest"})
        if typ == "csv":
            try:
                text = roh.decode("utf-8")
            except UnicodeDecodeError:
                text = roh.decode("latin-1")
            erg = csv_lesen(text)
        else:
            erg = _pdf_lesen(roh)
        A["sb_update"]("bank_auszuege", {"id": f"eq.{auszug_id}"}, {
            "status": "gelesen", "fehler": None, "zeilen": erg["zeilen"], "von": erg["von"], "bis": erg["bis"],
            "endsaldo": erg["endsaldo"], "waehrung": erg.get("waehrung"), "vorschlag": erg.get("vorschlag"),
            "uebersprungen": int(erg.get("uebersprungen") or 0),
            "gelesen_at": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        # nur eigene, feste Texte; JSON-Fehler tragen Auszugsinhalt in der Meldung → nur der Typ
        eigen = isinstance(e, (ValueError, RuntimeError)) and not isinstance(e, json.JSONDecodeError)
        grund = str(e) if eigen else f"Auslesen fehlgeschlagen ({type(e).__name__})"
        print(f"[bank-auszug] ⚠️ lesen: {type(e).__name__}", flush=True)
        try:
            A["sb_update"]("bank_auszuege", {"id": f"eq.{auszug_id}"}, {"status": "fehler", "fehler": grund[:200]})
        except Exception:
            pass


def aufraeumen(jetzt=None):
    """12 Monate aufbewahren (Master 25.11.2026): ältere Auszüge → Datei aus dem Bucket und Zeile löschen. Höchstens alle 6 h."""
    jetzt = jetzt or time.time()
    if jetzt - _aufgeraeumt["at"] < 6 * 3600:
        return 0
    _aufgeraeumt["at"] = jetzt
    grenze = (datetime.now(timezone.utc) - timedelta(days=AUFBEWAHREN_TAGE)).isoformat()
    alt = K._sb("GET", "bank_auszuege", {"select": "id,datei_pfad", "created_at": f"lt.{grenze}"}) or []
    for a in alt:
        if a.get("datei_pfad") and not datei_loeschen([a["datei_pfad"]]):
            continue                         # Datei bleibt → Zeile auch (nächster Lauf)
        K._sb("DELETE", "bank_auszuege", {"id": f"eq.{a['id']}"})
    return len(alt)


def datei_loeschen(pfade):
    """Dateien aus dem Bucket löschen → True nur bei Erfolg (Review BK6: requests wirft bei 4xx/5xx nicht)."""
    pfade = [p for p in pfade if p]
    if not pfade:
        return True
    try:
        return _storage("DELETE", f"object/{BUCKET}", json={"prefixes": pfade}).status_code < 300
    except Exception:
        return False


def konto_dateien_loeschen(konto_id):
    """Vor dem Löschen eines Bankkontos (bank_app): seine Auszug-Dateien aus dem Bucket (die Zeilen gehen per cascade). → True/False."""
    try:
        rows = K._sb("GET", "bank_auszuege", {"select": "datei_pfad", "konto_id": f"eq.{konto_id}"}) or []
    except Exception:
        return True                          # Tabelle fehlt (SQL nicht eingespielt) → nichts zu löschen
    return datei_loeschen([r.get("datei_pfad") for r in rows])


def letzte_je_konto(konto_ids):
    """Für die ID-Liste (bank_app GET): je Konto letzter Auszug {bis, status, faellig_tage}. Tabelle fehlt (SQL nicht eingespielt) → {}."""
    if not konto_ids:
        return {}
    try:
        try:
            aufraeumen()
        except Exception:
            pass
        rows = A["_sb_all"]("bank_auszuege", {"select": "id,konto_id,status,bis,created_at", "konto_id": K._in(konto_ids),
                                              "status": "eq.gelesen", "order": "created_at.desc,id.asc"}) or []   # nur gelesene zählen
    except Exception:
        return {}
    out = {}
    for r in rows:
        k = str(r["konto_id"])
        if k in out:
            continue
        stand = r.get("bis") or str(r.get("created_at") or "")[:10]
        out[k] = {"id": r["id"], "status": r["status"], "bis": r.get("bis"), "faellig_tage": faellig(stand)}
    return out


def _fehler(wo, e):
    print(f"[bank-auszug] ⚠️ {wo}: {type(e).__name__}", flush=True)
    return jsonify({"ok": False, "error": f"Kontoauszug: fehlgeschlagen ({type(e).__name__})"}), 502


def _auszug_erlaubt(auszug_id, erlaubt):
    rows = K._sb("GET", "bank_auszuege", {"select": "*", "id": f"eq.{auszug_id}"}) or []
    if not rows or not B._konto_erlaubt(rows[0]["konto_id"], erlaubt):
        return None
    return rows[0]


HAENGT_MIN = 15                 # Review BK6: „hochgeladen/liest" länger als 15 min (Neustart, Fehler vor dem Thread) → als fehler melden


def _haengt(a):
    if a.get("status") not in ("hochgeladen", "liest"):
        return False
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(str(a.get("created_at")).replace("Z", "+00:00")) > timedelta(minutes=HAENGT_MIN)
    except ValueError:
        return False


def _abgleich_fuer(a):
    konto = (K._sb("GET", "bank_konten", {"select": "id,start_saldo,waehrung", "id": f"eq.{a['konto_id']}"}) or [{}])[0]
    buch = A["_sb_all"]("bank_buchungen", {"select": "id,datum,betrag,text,art,auszug_id,auszug_zeile", "konto_id": f"eq.{a['konto_id']}",
                                           "order": "datum.asc,created_at.asc,id.asc"}) or []
    if a.get("status") != "gelesen":
        return None, buch
    erg = abgleich(a.get("zeilen") or [], buch, K._num(konto.get("start_saldo")), a.get("von"), a.get("bis"),
                   K._num(a["endsaldo"]) if a.get("endsaldo") is not None else None, auszug_id=a.get("id"))
    w_konto, w_auszug = str(konto.get("waehrung") or "EUR").upper(), str(a.get("waehrung") or "").upper()
    erg["waehrung_passt"] = not w_auszug or w_auszug == w_konto
    erg["waehrung_auszug"] = w_auszug or None
    return erg, buch


def registrieren(app, ns, bank_app):
    global B
    A.update(ns)
    B = bank_app

    @app.route("/admin/bank/auszug", methods=["GET", "POST", "DELETE", "OPTIONS"])
    def admin_bank_auszug():
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = K._gate()
        if err:
            return err
        try:
            if request.method == "GET":
                kid = K._uuid(request.args.get("konto"))
                if not kid or not B._konto_erlaubt(kid, erlaubt):
                    return jsonify({"ok": False, "error": "Konto nicht gefunden"}), 404
                liste = K._sb("GET", "bank_auszuege", {"select": "id,status,fehler,von,bis,endsaldo,waehrung,datei_name,datei_typ,created_at",
                                                       "konto_id": f"eq.{kid}", "order": "created_at.desc", "limit": "24"}) or []
                wahl = K._uuid(request.args.get("id")) or (liste[0]["id"] if liste else "")
                if not wahl:
                    return jsonify({"ok": True, "auszuege": [], "aktuell": None, "abgleich": None})
                a = _auszug_erlaubt(wahl, erlaubt)
                if not a or str(a["konto_id"]) != kid:
                    return jsonify({"ok": False, "error": "Auszug nicht gefunden"}), 404
                if _haengt(a):
                    a["status"], a["fehler"] = "fehler", "Auslesen nicht fertig geworden — bitte nochmal hochladen"
                    A["sb_update"]("bank_auszuege", {"id": f"eq.{a['id']}"}, {"status": "fehler", "fehler": a["fehler"]})
                erg, _ = _abgleich_fuer(a)
                aktuell = {k: a.get(k) for k in ("id", "status", "fehler", "von", "bis", "endsaldo", "waehrung", "datei_name",
                                                 "datei_typ", "created_at", "zeilen", "vorschlag", "uebersprungen")}
                return jsonify({"ok": True, "auszuege": liste, "aktuell": aktuell, "abgleich": erg})

            body = request.get_json(silent=True) or {}
            if request.method == "DELETE":
                a = _auszug_erlaubt(K._uuid(body.get("id")), erlaubt)
                if not a:
                    return jsonify({"ok": False, "error": "Auszug nicht gefunden"}), 404
                if not datei_loeschen([a.get("datei_pfad")]):
                    return jsonify({"ok": False, "error": "Datei nicht löschbar — nochmal versuchen"}), 502
                K._sb("DELETE", "bank_auszuege", {"id": f"eq.{a['id']}"})
                return jsonify({"ok": True})

            # POST: hochladen
            kid = K._uuid(body.get("konto_id"))
            if not kid or not B._konto_erlaubt(kid, erlaubt):
                return jsonify({"ok": False, "error": "Konto nicht gefunden"}), 404
            typ = str(body.get("typ") or "").lower()
            if typ not in ("pdf", "csv"):
                return jsonify({"ok": False, "error": "Nur PDF oder CSV"}), 400
            try:
                roh = base64.b64decode(str(body.get("daten") or ""), validate=True)
            except Exception:
                return jsonify({"ok": False, "error": "Datei nicht lesbar"}), 400
            if not roh or len(roh) > MAX_BYTES:
                return jsonify({"ok": False, "error": "Datei leer oder größer als 10 MB"}), 400
            if typ == "pdf" and not roh.startswith(b"%PDF"):
                return jsonify({"ok": False, "error": "Das ist kein PDF"}), 400
            neu = A["sb_insert"]("bank_auszuege", {"konto_id": kid, "datei_typ": typ, "status": "hochgeladen",
                                                    "datei_name": B._txt(body.get("name"), 120),
                                                    "hochgeladen_von": K._admin_uid() or None})
            pfad = f"{kid}/{neu['id']}.{typ}"
            try:
                r = _storage("POST", f"object/{BUCKET}/{pfad}", data=roh,
                             headers={"Content-Type": "application/pdf" if typ == "pdf" else "text/csv", "x-upsert": "false"})
                if r.status_code >= 300:
                    raise RuntimeError(f"HTTP {r.status_code}")
                A["sb_update"]("bank_auszuege", {"id": f"eq.{neu['id']}"}, {"datei_pfad": pfad})
            except Exception as e:
                datei_loeschen([pfad])
                K._sb("DELETE", "bank_auszuege", {"id": f"eq.{neu['id']}"})   # Review BK6: keine Zeile ohne Datei, die ewig „hochgeladen" steht
                return jsonify({"ok": False, "error": f"Speichern fehlgeschlagen ({e if isinstance(e, RuntimeError) else type(e).__name__})"}), 502
            threading.Thread(target=_lesen, args=(neu["id"], roh, typ), name="bank-auszug", daemon=True).start()
            return jsonify({"ok": True, "id": neu["id"]})
        except Exception as e:
            return _fehler("auszug " + request.method, e)

    @app.route("/admin/bank/auszug/datei", methods=["POST", "OPTIONS"])
    def admin_bank_auszug_datei():
        """5-Minuten-Link zum Ansehen (Bucket privat). id im Body, nie in der URL."""
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = K._gate()
        if err:
            return err
        try:
            a = _auszug_erlaubt(K._uuid((request.get_json(silent=True) or {}).get("id")), erlaubt)
            if not a or not a.get("datei_pfad"):
                return jsonify({"ok": False, "error": "Datei nicht (mehr) da"}), 404
            r = _storage("POST", f"object/sign/{BUCKET}/{a['datei_pfad']}", json={"expiresIn": 300}, timeout=10)
            d = r.json() if r.status_code == 200 else {}
            teil = d.get("signedURL") or d.get("signedUrl")
            if not teil:
                return jsonify({"ok": False, "error": "Link nicht erstellbar"}), 502
            return jsonify({"ok": True, "url": f"{A['SUPABASE_URL']}/storage/v1{teil}"})
        except Exception as e:
            return _fehler("datei", e)

    @app.route("/admin/bank/auszug/uebernehmen", methods=["POST", "OPTIONS"])
    def admin_bank_auszug_uebernehmen():
        """{auszug_id, zeilen:[{i, art}]} → Buchungen nur für Zeilen, die laut Abgleich fehlen (nie doppelt), Vorzeichen folgt der Art."""
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = K._gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            a = _auszug_erlaubt(K._uuid(body.get("auszug_id")), erlaubt)
            if not a:
                return jsonify({"ok": False, "error": "Auszug nicht gefunden"}), 404
            erg, _ = _abgleich_fuer(a)
            if not erg:
                return jsonify({"ok": False, "error": "Auszug noch nicht gelesen"}), 409
            if not erg.get("waehrung_passt", True):
                return jsonify({"ok": False, "error": f"Auszug ist in {erg.get('waehrung_auszug')}, das Konto nicht — bitte das richtige Konto wählen"}), 409
            fehlt = {f["i"] for f in erg["fehlt"]}
            neue = []
            for w in (body.get("zeilen") or [])[:500]:
                try:
                    i = int(w.get("i"))
                except (TypeError, ValueError):
                    continue
                art = str(w.get("art") or "")
                if i not in fehlt or art not in B.ARTEN:
                    continue
                z = a["zeilen"][i]
                if (float(z["betrag"]) > 0) != (B.VORZEICHEN[art] > 0):   # Review BK6: Art mit falschem Vorzeichen würde ewig „fehlt" bleiben
                    return jsonify({"ok": False, "error": f"„{art}“ passt nicht zum Vorzeichen der Zeile vom {z['datum']}"}), 400
                text = " · ".join(x for x in (z.get("text"), z.get("gegenseite")) if x)[:300] or None
                neue.append({"konto_id": a["konto_id"], "datum": z["datum"], "betrag": abs(round(float(z["betrag"]), 2)) * B.VORZEICHEN[art],
                             "text": text, "art": art, "quelle": "auszug", "auszug_id": a["id"], "auszug_zeile": i,
                             "angelegt_von": K._admin_uid() or None})
                fehlt.discard(i)
            if not neue:
                return jsonify({"ok": False, "error": "Nichts zu übernehmen (schon gebucht?)"}), 400
            try:
                A["sb_insert"]("bank_buchungen", neue)
            except Exception as e:
                txt = str(getattr(getattr(e, "response", None), "text", "") or "")
                if "23505" in txt or "duplicate key" in txt:   # unique (auszug_id, auszug_zeile): schon übernommen (zwei Klicks/Tabs)
                    return jsonify({"ok": False, "error": "Schon übernommen — Seite neu laden"}), 409
                raise
            return jsonify({"ok": True, "anzahl": len(neue)})
        except Exception as e:
            return _fehler("uebernehmen", e)
