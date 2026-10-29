"""KAPITAL IM SYSTEM je Gruppe (29.10.2026, Finn: 50 % an der Emin-Gruppe, legt demnächst weitere 5.000 $ nach und will eine Zahl, die
zeigt, ob Geld abgezweigt wird). EIGENES MODUL wie polar_app/support_app: app.py bekommt nur `kapital_app.registrieren(app, globals())`.

Finns Logik: jedes Prop-Konto ist auf Fusion gegengehedgt, also bleibt das Kapital im System nahezu gleich. Ein Konto zählt mit seinen
Gesamtkosten = Kauf + bisherige Hedge-Verluste (Finns Beispiel: Kauf 500 €, Blow → die 500 € kommen über den Hedge zurück; Bestehen →
Phase 2, im Konto stecken 1.000 € = 500 Kauf + 500 Hedge-Verlust, der auf Fusion fehlt). Die Summe sinkt nur durch Reibung; fällt sie
deutlich stärker, fehlt Geld.

ALLES IN EUR (Finn 29.10.2026, Nachtrag über die Vertrags-Session — ersetzt die erste Antwort „US-Dollar"): Wallets (USDT/USDC ≈ USD) zum
EZB-Tageskurs (frankfurter.dev, 6 h gemerkt; Rückfall Prophos-Kurs user_settings fx_usd_eur, sichtbar markiert), Fusion ist EUR,
Geschäftskonto in EUR. Account-Käufe zählen mit dem in Prophos gebuchten €-Betrag; dass on-chain in USDT bezahlt wurde, liegt als Kurs- und
CoinPayments-Abweichung in der Toleranz.

  Seit 29.10.2026 (Finn 06:45): Kontowerte = Kauf + Hedge-Verluste je laufender Kette ohne Payout-Abzug, Soll mit Payouts laufender Ketten
  statt Gewinnen im Plus (Abweichung unverändert) — Details in bilanz_rechnen. Die Zeilen unten beschreiben den Stand davor.
  Ist („insgesamt geparkt") = Wallets der Gruppe (letzter wallet_snapshots-Tag je Wallet, inkl. Kasse 0xc27c…)
         + Fusion (live aus mt5_live: Equity, je hedge_login nur einmal, Zeile ≤ 1 h alt; sonst Hand-Eingabe kapital_fusion)
         + Geschäftskonto (Σ kapital_gk_buchungen)
         + Σ Gesamtkosten der laufenden Ketten, Boden 0 (= Accounts-Kachel „Gesamtwert", sql kapital_ketten)
         + offene Payouts (pending_payouts pending — kapital_ketten zieht sie schon vom Konto ab, sonst doppelt)
  Soll = Σ Einlagen − Reibung (beendete Ketten, deren Kosten der Hedge nicht zurückgeholt hat — u. a. CFD-Blows, deren Hedge die Gebühr nur
         zu 64–88 % deckt) + Gewinne (Ketten im Plus) − Gebühren/Swap-Saldo − Ausschüttungen (wallet_tx Profit Split …)
         + Geschäftskonto-Buchungen außer „Umbuchung Krypto" (Kundenzahlung +, PC-Kauf/Ausgabe/Entnahme −)
  Abweichung = Ist − Soll, Toleranz max(250 €, 3 % der Account-Käufe). Reine Finanzübersicht — keine Regel-, Compliance- oder Risiko-Prüfung.

  GET    /admin/kapital?gruppe=<id>     Zahl, Aufschlüsselung, Fusion-Report, Geschäftskonto, Verlauf, Abflüsse/Zuflüsse ohne Erklärung
  POST   /admin/kapital/einlage         {gruppe, betrag, waehrung EUR|USD, datum, ziel_wallet?, notiz?, quelle_tx?}  · DELETE {id}
  POST   /admin/kapital/fusion          {gruppe, betrag, waehrung, stand_am?, notiz?}  (Rückfall, wenn mt5_live nicht frisch)
  POST   /admin/kapital/gk              {gruppe, datum, betrag (± ), waehrung, kategorie, text}  · DELETE {id}

Rechte (_gate, Stand 29.10.2026 nach Prüfer): alle Gruppen nur für ADMIN_EMAILS oder admin_mail_leser („Finn + Pascal"), nie für jede
uneingeschränkte HT-ID (Kunden). VERWALTER (Finn 04:30: „Bei Emin
soll es auch gehen — es geht ja vor allem um die IDs von Emin") = nur die Gruppe, deren Verwalter er ist (Lesen, Buchen, Löschen; nie
HT-Daten), nur mit ?ansicht=admin wie alle Admin-Reiter. Mitglied / „nur eigene“ bekommen 403. Bis dahin _lq_gate (ADMIN_EMAILS): „Finn + Pascal“ steht nicht in ADMIN_EMAILS und sah nur „Nur für Voll-Admins.“
Tageswerte: jeder GET schreibt den
heutigen Stand, dazu auf Railway ein Stunden-Takt."""
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import request, jsonify, g

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

A = {}                         # Namensraum von app.py — gefüllt in registrieren()

STABLES = {"USDT", "USDC", "USDT0", "USDC.E"}      # nur echte Stable-Contracts landen so in wallet_tx (Kasse-Reiter blendet fremde Token aus)
MIN_BETRAG = 1.0                                    # darunter: Null-/Staub-Transfers (Address-Poisoning schickt 0-Beträge)
# Kategorien aus wallet_tx_kategorien, die einen Abfluss erklären (Finn: „Account-Kauf, Fusion, Gebühr oder interner Transfer"). „Interner
# Transfer auf Bank" ist seit dem Geschäftskonto intern (Gegenbuchung dort „Umbuchung Krypto").
ERKLAERT_RAUS = {"Account Kauf", "Account-Kauf", "Fusion Deposit", "Gebühr", "Gebühren / Gas", "Swap", "Umbuchung intern",
                 "Interner Transfer (Krypto)", "Interner Transfer auf Bank"}
# Geld, das die Gruppe bewusst verlässt (verteilt) — erklärt, aber auf der Soll-Seite abgezogen und eigens gezeigt
AUSSCHUETTUNG = {"Profit Split", "Kunden-Payout → Bank", "Auszahlung an Person", "Privat"}
ERKLAERT_REIN = {"Payout", "Payout Prop-Firm", "Swap", "Fusion Deposit", "Interner Transfer (Krypto)", "Interner Transfer auf Bank",
                 "Umbuchung intern", "Account Kauf", "Account-Kauf"}
# Geschäftskonto ↔ Wallets: Tasche wechselt, Soll bleibt. „Konto-Kauf (in Prophos)": Konto-Käufe aus Emins Sheet stehen schon als
# purchase_cost in Prophos und damit in den Kontowerten — im Soll noch einmal abgezogen, zählten sie doppelt (Befund 29.10.2026, 4.323,78 €)
GK_KONTO_KAUF = "Konto-Kauf (in Prophos)"
GK_NEUTRAL = {"Umbuchung Krypto", GK_KONTO_KAUF}
GK_KATEGORIEN = ["Anfangsstand", "Kundenzahlung", "PC-Kauf", "Ausgabe", "Einlage", "Entnahme", "Umbuchung Krypto", "Sonstiges"]
# „Weitere Posten" (29.10.2026, Finn: „Geschäftskonto und andere Werte will ich ohne Google Sheet einfach in einer Liste von Hand
# eintragen"): je Zeile in kapital_gk_buchungen ein Stand (Name = text, Betrag = aktueller Wert). Kategorie „Geschäftskonto" oder
# „Sonstiges"; „Sonstiges" steht im Ist als eigener Teil (Chart-Quelle), alle übrigen Kategorien zählen als Geschäftskonto.
GK_POSTEN_KATEGORIEN = ["Geschäftskonto", "Sonstiges"]
GK_SONSTIGES = "Sonstiges"
TOLERANZ_MIN = 250.0
TOLERANZ_ANTEIL = 0.03         # Kurs-/CoinPayments-Aufschläge auf die Account-Käufe
FUSION_FRISCH_S = 3600         # mt5_live-Zeile älter → Hand-Eingabe
KURS_MERKEN_S = 6 * 3600
TAKT_S = 3600
TZ_TAG = "Asia/Dubai"          # Tageswert nach Finns Tag

_takt = {"at": 0.0, "fehler": "", "laeuft": False}
_kurs = {"bis": 0.0, "wert": None}
_google = {"creds": None}

# ── GESCHÄFTSKONTO AUS EMINS SHEET (29.10.2026, Finn: „Bring genau den Gesamtbetrag mit rein", Entscheidung: automatisch) ──────────────
# Railway liest täglich Buchungen!A2:G (+ Stand-Zeile Übersicht!A2, „Zeitraum ab" Übersicht!B3) per Google-Service-Konto — nur lesen,
# nie zurückschreiben — und spiegelt jede Zeile nach kapital_gk_buchungen (quelle 'sheet'): das Sheet ist die Wahrheit, verschwundene
# Zeilen gehen raus, neue kommen rein. Ohne Railway-Variable GOOGLE_SERVICE_ACCOUNT_JSON (komplette JSON-Schlüsseldatei des Kontos)
# steht in kapital_gk_quellen.fehler „Service-Konto fehlt" und der Reiter rechnet mit den Hand-Buchungen weiter.
GK_SHEET_SA_VAR = "GOOGLE_SERVICE_ACCOUNT_JSON"
GK_SHEET_BEREICHE = ["Buchungen!A2:G", "Übersicht!A2", "Übersicht!B3"]
GK_SHEET_TAKT_S = 24 * 3600       # „täglich"; nach einem Fehler beim nächsten Stunden-Takt erneut


def _sb(methode, tabelle, params=None, body=None, prefer=None, timeout=15):
    r = A["_sb_anfrage"](methode, f"{A['SUPABASE_URL']}/rest/v1/{tabelle}", params=params or {}, json=body,
                         headers=A["_sb_headers"](prefer), timeout=timeout)
    A["_sb_pruefen"](r)
    try:
        return r.json()
    except ValueError:
        return None


def _heute():
    if ZoneInfo:
        return datetime.now(ZoneInfo(TZ_TAG)).date()
    return (datetime.now(timezone.utc) + timedelta(hours=4)).date()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _in(menge):
    return "in.(" + ",".join(sorted(str(u) for u in menge)) + ")"


def _uuid(s):
    s = str(s or "").strip()
    return s if re.fullmatch(r"[0-9a-fA-F-]{36}", s) else ""


def _ts(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _lookalike(a, b):
    """REIN RECHNEND: sieht Adresse a wie b aus, ohne b zu sein? Address-Poisoning kopiert Anfang + Ende (0x1B94…26e1)."""
    a, b = str(a or "").lower(), str(b or "").lower()
    return bool(a and b and a != b and len(a) > 12 and a[:6] == b[:6] and a[-4:] == b[-4:])


def tageskurs():
    """{fx: € je $, quelle, stand} — EZB-Referenzkurs über frankfurter.dev (keyless, früher .app), 6 h gemerkt. Rückfall: Prophos-Kurs (Hand-Eingabe in
    den Einstellungen) mit Quelle „Prophos-Einstellung", damit die Karte zeigt, dass es kein Tageskurs ist."""
    jetzt = time.time()
    if _kurs["wert"] and _kurs["bis"] > jetzt:
        return _kurs["wert"]
    try:
        r = requests.get("https://api.frankfurter.dev/v1/latest", params={"from": "USD", "to": "EUR"}, timeout=6)
        r.raise_for_status()
        j = r.json()
        fx = float(j["rates"]["EUR"])
        if 0.5 < fx < 1.5:
            _kurs.update(bis=jetzt + KURS_MERKEN_S, wert={"fx": fx, "quelle": "EZB-Referenzkurs (frankfurter.dev)", "stand": j.get("date")})
            return _kurs["wert"]
    except Exception as e:
        print(f"[kapital] ⚠️ Tageskurs: {type(e).__name__}: {e}", flush=True)
    w = {"fx": A["_lq_fx"](), "quelle": "Prophos-Einstellung (kein Tageskurs erreichbar)", "stand": None}
    _kurs.update(bis=jetzt + 600, wert=w)                # Rückfall nur 10 min merken, dann wieder EZB versuchen
    return w


def fusion_live_waehlen(zeilen, logins, jetzt=None):
    """REIN RECHNEND: aus mt5_live-Zeilen je hedge_login die frischeste (mehrere PC-Instanzen schreiben dasselbe Konto), Equity vor Balance
    (offene Hedges stecken sonst doppelt drin oder fehlen), nur ≤ FUSION_FRISCH_S alt. → {eur_roh: {login: (betrag, waehrung)}, stand, logins}
    oder None, wenn kein Login frisch ist."""
    jetzt = jetzt or datetime.now(timezone.utc)
    best = {}
    for z in zeilen or []:
        lg = str(z.get("hedge_login") or "").strip()
        st = z.get("status") if isinstance(z.get("status"), dict) else {}
        t = _ts(z.get("updated_at"))
        if lg not in logins or t is None:
            continue
        wert = st.get("hedge_equity") if st.get("hedge_equity") not in (None, "") else st.get("hedge_balance")
        if wert in (None, ""):
            continue
        if lg not in best or t > best[lg][0]:
            best[lg] = (t, _num(wert), str(st.get("hedge_currency") or "EUR").upper(), st.get("hedge_equity") not in (None, ""))
    frisch = {lg: v for lg, v in best.items() if (jetzt - v[0]).total_seconds() <= FUSION_FRISCH_S}
    if not frisch:
        return None
    return {"konten": {lg: {"betrag": v[1], "waehrung": v[2], "equity": v[3], "stand": v[0].isoformat()} for lg, v in frisch.items()},
            "stand": min(v[0] for v in frisch.values()).isoformat()}


def _de_zahl(v):
    """REIN RECHNEND: „3.476,14 €" / „-10,18" / 3476.14 → float oder None."""
    if isinstance(v, (int, float)):
        return float(v)
    t = re.sub(r"[^\d,.\-−]", "", str(v or "")).replace("−", "-")
    if not t or t in ("-", ",", "."):
        return None
    t = t.replace(".", "").replace(",", ".") if "," in t else t
    try:
        return float(t)
    except ValueError:
        return None


def _de_datum(v):
    """REIN RECHNEND: „25.09.2026" → „2026-09-25" (auch ISO durchreichen), sonst None."""
    t = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return t if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t) else None


def gk_sheet_zeilen(werte):
    """REIN RECHNEND: Zeilen aus Buchungen!A2:G (Datum, Art, Betrag €, Zweck, Kategorie, Beleg, Dateiname) → Buchungen für
    kapital_gk_buchungen. Ausgabe = negativ. Kategorien: „Challenge / Evaluation" → Konto-Kauf (in Prophos) = neutral (schon in den
    Kontowerten), Zweck „Auszahlung …" → Entnahme, sonst die Kategorie des Sheets (Payout, Hardware, Software & Abos …). Schlüssel aus dem
    Inhalt + laufende Nummer bei exakt gleichen Zeilen (Zeilennummern wandern, im Sheet stehen Nachträge mitten drin). Leer-/Kopfzeilen
    und Zeilen ohne lesbares Datum/Betrag fallen raus."""
    aus, gesehen = [], {}
    for z in werte or []:
        z = list(z) + [""] * (7 - len(z))
        datum, art, betrag = _de_datum(z[0]), str(z[1] or "").strip(), _de_zahl(z[2])
        zweck, kat = str(z[3] or "").strip(), str(z[4] or "").strip()
        if not datum or betrag is None or betrag == 0:
            continue
        b = -abs(betrag) if art.lower().startswith("ausgabe") else abs(betrag)
        if kat.lower().startswith("challenge"):
            kategorie = GK_KONTO_KAUF
        elif re.match(r"auszahlung\b", zweck, re.I):
            kategorie = "Entnahme"
        else:
            kategorie = kat or ("Einnahme" if b > 0 else "Ausgabe")
        roh = "|".join([datum, art, f"{abs(betrag):.2f}", zweck, kat])
        gesehen[roh] = gesehen.get(roh, 0) + 1
        aus.append({"datum": datum, "betrag": round(b, 2), "waehrung": "EUR", "kategorie": kategorie[:40],
                    "text": (zweck or kat)[:300], "zeilen_schluessel": f"{roh}#{gesehen[roh]}"[:400]})
    return aus


def gk_abgleich(sheet_zeilen, db_zeilen):
    """REIN RECHNEND: (neu, weg_ids) — Sheet-Zeilen, die in der DB fehlen, und DB-Zeilen (quelle sheet), die das Sheet nicht mehr hat."""
    im_sheet = {z["zeilen_schluessel"] for z in sheet_zeilen}
    in_db = {str(d.get("zeilen_schluessel")): d for d in db_zeilen if d.get("zeilen_schluessel")}
    neu = [z for z in sheet_zeilen if z["zeilen_schluessel"] not in in_db]
    weg = [str(d["id"]) for k, d in in_db.items() if k not in im_sheet]
    return neu, weg


def bilanz_rechnen(ketten, snaps, fusion_live, fusion_hand, einlagen, tx, labels, gruppen_adressen, fx, offene=None, gk=None):
    """REIN RECHNEND (ohne DB, Selbsttest-fähig): alle Teile der Zahl in EUR.
    ketten: kapital_ketten-Zeilen (gk_eur, hedge_eur, archiviert, kauf_eur …) · snaps: {wallet_id: {usd, tag}} · fusion_live: Ergebnis von
    fusion_live_waehlen oder None · fusion_hand: jüngste kapital_fusion-Zeile oder None · einlagen: kapital_einlagen · tx: wallet_tx der
    Gruppen-Wallets · labels: {adresse_klein: kind} · gruppen_adressen: set der eigenen Adressen (klein) · fx: € je $ ·
    offene: pending_payouts (amount, currency) · gk: kapital_gk_buchungen (betrag, waehrung, kategorie)."""
    fx = fx if fx and 0.5 < fx < 1.5 else 0.85
    eur = lambda betrag, waehrung="USD": _num(betrag) * (fx if str(waehrung or "USD").upper() == "USD" else 1.0)
    r2 = lambda v: round(v, 2)

    # ── Konten (Ketten) ──
    lauf = [k for k in ketten if not k.get("archiviert")]
    ende = [k for k in ketten if k.get("archiviert")]
    # KONTOWERT NEU (29.10.2026, Finn 06:45: „Ein Emin-Konto, das schon 2,5k Payout gebracht hat, fällt dadurch auf 0 und verschwindet aus dem
    # Unternehmenswert, obwohl das Konto noch da ist und Geld bringt"): je laufender Kette Kauf + bisherige Hedge-Verluste (kauf_eur + hedge_eur,
    # = calcReingesteckdEur mit WD-Hedge, aber ohne netPayouts), OHNE Payout-Abzug und ohne 0-Kappung — die Payouts stecken schon als Geld in
    # Wallets/Geschäftskonto/Weiteren Posten bzw. als offene Payouts. Geblowte (archivierte) Ketten zählen 0. Bis 28.10.: Σ max(0, gk_eur).
    konten = sum(_num(k.get("kauf_eur")) + _num(k.get("hedge_eur")) for k in lauf)
    konten_netto_alt = sum(max(0.0, _num(k.get("gk_eur"))) for k in lauf)          # alte Regel, nur zum Vergleich in der Antwort
    po_lauf = sum(_num(k.get("payouts_eur")) for k in lauf)
    reibung = sum(max(0.0, _num(k.get("gk_eur"))) for k in ende)
    gewinn_ende = sum(max(0.0, -_num(k.get("gk_eur"))) for k in ende)
    kauf = sum(_num(k.get("kauf_eur")) for k in ketten)
    hedge_ergebnis = -sum(_num(k.get("hedge_eur")) for k in ketten)      # + = Fusion hat gewonnen

    # ── Wallets (USD-Stables + Coins in USDT bewertet) ──
    wallets_usd = sum(_num(s.get("usd")) for s in snaps.values())
    wallets_tag = max((s.get("tag") or "" for s in snaps.values()), default="") or None

    # ── Fusion: live vor Hand ──
    if fusion_live:
        fus_eur = sum(eur(v["betrag"], v["waehrung"]) for v in fusion_live["konten"].values())
        fus = {"eur": r2(fus_eur), "quelle": "live", "stand": fusion_live["stand"], "logins": sorted(fusion_live["konten"]),
               "equity": all(v.get("equity") for v in fusion_live["konten"].values())}
    elif fusion_hand:
        fus = {"eur": r2(eur(fusion_hand.get("betrag"), fusion_hand.get("waehrung") or "EUR")), "quelle": "hand",
               "stand": fusion_hand.get("stand_am"), "logins": [], "notiz": fusion_hand.get("notiz") or ""}
    else:
        fus = None

    # ── Offene Payouts (beantragt, noch nicht da) ──
    offen = sum(eur(o.get("amount"), o.get("currency") or "EUR") for o in (offene or []))

    # ── Geschäftskonto ──
    gk = gk or []
    gk_saldo = sum(eur(b.get("betrag"), b.get("waehrung") or "EUR") for b in gk)
    sonstiges = sum(eur(b.get("betrag"), b.get("waehrung") or "EUR") for b in gk if (b.get("kategorie") or "") == GK_SONSTIGES)
    gk_soll = sum(eur(b.get("betrag"), b.get("waehrung") or "EUR") for b in gk if (b.get("kategorie") or "") not in GK_NEUTRAL)
    gk_rein = sum(eur(b.get("betrag"), b.get("waehrung") or "EUR") for b in gk
                  if (b.get("kategorie") or "") not in GK_NEUTRAL and _num(b.get("betrag")) > 0)

    # ── Wallet-Transfers: Gebühren, Swaps, Ausschüttungen, Fusion-Flüsse, Abflüsse/Zuflüsse ohne Erklärung (Beträge in USD) ──
    gebuehren = swap_raus = swap_rein = ausschuett = fus_ein = fus_aus = 0.0
    abfl, zufl = [], []
    gef = {"null": 0, "fake": 0, "poisoning": 0}
    bekannte = set(gruppen_adressen)
    for t in tx:
        if (t.get("kategorie") or "") in (ERKLAERT_RAUS | ERKLAERT_REIN | AUSSCHUETTUNG):
            bekannte.add(str(t.get("other") or "").lower())
    eingebucht = {str(e.get("quelle_tx")) for e in einlagen if e.get("quelle_tx")}
    for t in tx:
        sym = str(t.get("sym") or "").upper()
        betrag = _num(t.get("amount"))
        other = str(t.get("other") or "").lower()
        kat = t.get("kategorie") or ""
        if sym not in STABLES:
            gef["fake"] += 1
            continue
        if betrag < MIN_BETRAG:
            gef["null"] += 1
            continue
        if other not in bekannte and any(_lookalike(other, b) for b in bekannte):
            gef["poisoning"] += 1
            continue
        if other in gruppen_adressen:
            continue                                  # innerhalb der Gruppe (Emin → Kasse usw.) — bleibt im System
        raus = t.get("dir") == "raus"
        if kat in ("Gebühr", "Gebühren / Gas"):
            gebuehren += betrag if raus else -betrag
            continue
        if kat == "Swap":
            if raus:
                swap_raus += betrag
            else:
                swap_rein += betrag
            continue
        if kat == "Fusion Deposit":
            if raus:
                fus_ein += betrag
            else:
                fus_aus += betrag
            continue
        if kat in AUSSCHUETTUNG and raus:
            ausschuett += betrag
            continue
        zeile = {"key": t.get("tx_key"), "ts": t.get("ts"), "betrag": r2(betrag), "betrag_eur": r2(eur(betrag)), "sym": sym,
                 "an": t.get("other"), "person": t.get("person_name"), "chain": t.get("chain"), "hash": t.get("hash"), "kategorie": kat,
                 "label": labels.get(other) or "", "kommentar": t.get("kommentar") or ""}
        if raus:
            if kat in ERKLAERT_RAUS or labels.get(other) == "coinpayments_deposit":
                continue
            abfl.append(zeile)
        else:
            if kat in ERKLAERT_REIN or labels.get(other) == "coinpayments_hot" or t.get("tx_key") in eingebucht:
                continue
            zufl.append(zeile)
    abfl.sort(key=lambda z: -z["betrag"])
    zufl.sort(key=lambda z: -z["betrag"])
    krypto_reibung = eur(gebuehren + max(0.0, swap_raus - swap_rein))

    # ── Summen ──
    einlagen_eur = sum(eur(e.get("betrag"), e.get("waehrung") or "EUR") for e in einlagen)
    wallets = eur(wallets_usd)
    ist = wallets + (fus["eur"] if fus else 0.0) + gk_saldo + konten + offen
    # Soll passend zum neuen Kontowert: statt „Gewinne der laufenden Ketten im Plus" die Payouts der laufenden Ketten (inkl. beantragter) —
    # die Abweichung bleibt rechnerisch dieselbe wie mit der alten Konten-Regel (je Kette: Ist kauf+hedge, Soll +payouts).
    soll = einlagen_eur - reibung + gewinn_ende + po_lauf - krypto_reibung - eur(ausschuett) + gk_soll
    abw = ist - soll
    toleranz = max(TOLERANZ_MIN, TOLERANZ_ANTEIL * kauf)
    return {
        "ist": {"summe": r2(ist), "wallets": r2(wallets), "wallets_usd": r2(wallets_usd), "wallets_tag": wallets_tag,
                "wallets_n": len(snaps), "fusion": fus, "geschaeftskonto": r2(gk_saldo), "gk_n": len(gk),
                "gk_konto": r2(gk_saldo - sonstiges), "sonstiges": r2(sonstiges),
                "konten": r2(konten), "konten_n": len(lauf), "konten_plus_n": sum(1 for k in lauf if _num(k.get("gk_eur")) < 0),
                "konten_regel": "kauf_plus_hedge", "konten_netto_alt": r2(konten_netto_alt),
                "payouts_offen": r2(offen), "payouts_offen_n": len(offene or [])},
        "soll": {"summe": r2(soll), "einlagen": r2(einlagen_eur), "einlagen_n": len(einlagen),
                 "reibung": r2(reibung), "beendet_n": len(ende), "gewinne": r2(gewinn_ende), "payouts_lauf": r2(po_lauf),
                 "krypto_reibung": r2(krypto_reibung), "gebuehren": r2(eur(gebuehren)), "swap_saldo": r2(eur(swap_raus - swap_rein)),
                 "ausschuettungen": r2(eur(ausschuett)), "geschaeftskonto": r2(gk_soll), "gk_einnahmen": r2(gk_rein),
                 "gk_ausgaben": r2(gk_rein - gk_soll)},
        "fusion_report": {"kapital": fus, "einzahlungen": r2(eur(fus_ein)), "auszahlungen": r2(eur(fus_aus)),
                          "hedge_ergebnis": r2(hedge_ergebnis)},
        "abweichung": r2(abw), "toleranz": r2(toleranz), "auffaellig": abs(abw) > toleranz, "kauf": r2(kauf),
        "abfluesse": abfl[:200], "abfluesse_summe": r2(sum(z["betrag_eur"] for z in abfl)), "abfluesse_n": len(abfl),
        "zufluesse": zufl[:200], "zufluesse_summe": r2(sum(z["betrag_eur"] for z in zufl)), "zufluesse_n": len(zufl),
        "gefiltert": gef,
    }


def je_id_rechnen(ketten, snaps, offene, fx, mit=None):
    """REIN RECHNEND: die Teile, die einer ID gehören, je ID (29.10.2026, Finn 09:35: „auch nach IDs filtern") — Kontowerte (Kette = ID des
    Kopfes, Regel wie bilanz_rechnen: kauf + hedge der laufenden Ketten), Wallets (id_wallets.person_uid) und offene Payouts (user_id).
    Fusion, Geschäftskonto und Weitere Posten sind gruppenweit und fehlen hier. Σ über alle IDs = die Gruppensumme dieser drei Teile.
    snaps: {wallet_id: {usd, uid}} · offene: pending_payouts mit user_id · mit: alle Mitglieder (auch ohne Werte). Ohne Namen — die stehen
    nur in der Antwort (b.ids), nicht im gespeicherten Tageswert (Gegenprüfung 29.10.2026)."""
    fx = fx if fx and 0.5 < fx < 1.5 else 0.85
    eur = lambda betrag, waehrung="USD": _num(betrag) * (fx if str(waehrung or "USD").upper() == "USD" else 1.0)
    je = {}
    leer = lambda: {"konten": 0.0, "konten_n": 0, "wallets": 0.0, "wallets_usd": 0.0, "wallets_n": 0, "payouts_offen": 0.0}
    for uid in mit or []:
        je[str(uid)] = leer()
    for k in ketten:
        if k.get("archiviert") or not k.get("user_id"):
            continue
        z = je.setdefault(str(k["user_id"]), leer())
        z["konten"] += _num(k.get("kauf_eur")) + _num(k.get("hedge_eur"))
        z["konten_n"] += 1
    for s in snaps.values():
        if not s.get("uid"):
            continue
        z = je.setdefault(str(s["uid"]), leer())
        z["wallets_usd"] += _num(s.get("usd"))
        z["wallets_n"] += 1
    for o in offene or []:
        if not o.get("user_id"):
            continue
        je.setdefault(str(o["user_id"]), leer())["payouts_offen"] += eur(o.get("amount"), o.get("currency") or "EUR")
    for uid, z in je.items():
        z["wallets"] = eur(z["wallets_usd"])
        for f in ("konten", "wallets", "wallets_usd", "payouts_offen"):
            z[f] = round(z[f], 2)
    return je


def _id_namen(uids):
    """Anzeigenamen der IDs wie in den übrigen Admin-Reitern (app.py _wd_personen / Übersicht): user_metadata.name, sonst das Kürzel vor
    dem @ der Login-Mail, sonst die ersten 8 Zeichen — nie die ganze Mail (29.10.2026: Chip „46ce0409“ in Finns HT-Screenshot).
    Lesefehler → nur Kürzel (die Zahlen hängen nicht daran)."""
    try:
        r = A["_auth_liste_anfrage"]()
        users = (r.json() or {}).get("users") or [] if r.status_code == 200 else []
    except Exception:
        users = []
    namen = {}
    for u in users:
        mail = str(u.get("email") or "")
        namen[str(u.get("id"))] = str(((u.get("user_metadata") or {}).get("name")) or "").strip() or (mail.split("@")[0] if "@" in mail else "")
    return {str(u): namen.get(str(u)) or str(u)[:8] for u in uids}


# Kein eigener ID-Chip im Kapital-Reiter (29.10.2026, Master nach Finns HT-Screenshot): der Test-Login nie; „Finn" ist seit 21.10.2026
# archiviert (nur noch „Finn + Pascal") — seine laufenden Konten bleiben in der Gruppensumme, nur der Chip entfällt, bis Finn anders entscheidet.
KAPITAL_OHNE_CHIP = {"eeeeeeee-0000-4000-a000-000000000001", "b55d7ab4-5246-4101-abca-f729c71d17ec"}


def _daten_lesen(gid):
    """Alle Zeilen für bilanz_rechnen. Fehler fliegen durch (Aufrufer antwortet 502)."""
    kurs = tageskurs()
    fx = kurs["fx"]
    mit = [str(r["user_id"]) for r in (_sb("GET", "id_gruppe_mitglied", {"select": "user_id", "gruppe_id": f"eq.{gid}"}) or [])]
    r = A["_sb_anfrage"]("POST", f"{A['SUPABASE_URL']}/rest/v1/rpc/kapital_ketten", headers=A["_sb_headers"](), timeout=(5, 30),
                         json={"p_gruppe": gid, "p_fx": fx})
    A["_sb_pruefen"](r)
    ketten = r.json() or []
    wallets = A["_sb_all"]("id_wallets", {"select": "id,person_name,person_uid,chain,address", "person_uid": _in(mit)}) if mit else []
    uid_von = {w["id"]: str(w.get("person_uid") or "") for w in wallets}
    wids = [w["id"] for w in wallets]
    snaps = {}
    if wids:
        ab = (_heute() - timedelta(days=30)).isoformat()
        for s in A["_sb_all"]("wallet_snapshots", {"select": "id,wallet_id,day,usdt,coin_usdt", "wallet_id": _in(wids),
                                                    "day": f"gte.{ab}", "order": "day.desc,id.asc"}):
            if s["wallet_id"] not in snaps:            # jüngster Tag je Wallet
                snaps[s["wallet_id"]] = {"usd": _num(s.get("usdt")) + _num(s.get("coin_usdt")), "tag": s.get("day"), "uid": uid_von.get(s["wallet_id"])}
    # Fusion live: Hedge-Logins = external_id der Live-Konten der Gruppe (Emin-Gruppe: alle fünf IDs auf 430095 → einmal zählen)
    logins = {str(a.get("external_id") or "").strip() for a in
              (A["_sb_all"]("accounts", {"select": "id,external_id", "account_type": "eq.live", "user_id": _in(mit)}) if mit else [])}
    logins.discard("")
    fus_live = None
    if logins:
        zeilen = _sb("GET", "mt5_live", {"select": "hedge_login,updated_at,status", "hedge_login": _in(logins),
                                         "order": "updated_at.desc", "limit": "50"}) or []
        fus_live = fusion_live_waehlen(zeilen, logins)
    offene = (_sb("GET", "pending_payouts", {"select": "amount,currency,user_id", "status": "eq.pending", "user_id": _in(mit)}) or []) if mit else []
    fus = _sb("GET", "kapital_fusion", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "created_at.desc", "limit": "1"}) or []
    einl = A["_sb_all"]("kapital_einlagen", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "datum.asc,id.asc"})
    gk = A["_sb_all"]("kapital_gk_buchungen", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "datum.asc,id.asc"})
    tx = A["_sb_all"]("wallet_tx", {"select": "tx_key,wallet_id,chain,person_name,hash,ts,dir,amount,sym,other,kategorie,kommentar",
                                    "wallet_id": _in(wids), "order": "ts.desc,id.asc"}) if wids else []
    adressen = {str(w["address"]).lower() for w in wallets}
    others = sorted({str(t.get("other") or "").lower() for t in tx if t.get("other")})
    labels = {}
    for i in range(0, len(others), 150):               # URL-Länge: in Häppchen; wallet_labels speichert die Adresse klein
        for l in _sb("GET", "wallet_labels", {"select": "address,kind", "address": _in(others[i:i + 150])}) or []:
            labels[str(l["address"]).lower()] = l.get("kind") or ""
    return {"kurs": kurs, "ketten": ketten, "snaps": snaps, "fusion_live": fus_live, "fusion_hand": fus[0] if fus else None,
            "einlagen": einl, "gk": gk, "tx": tx, "labels": labels, "adressen": adressen, "wallets_n": len(wallets), "offene": offene,
            "mit": mit}


def verlauf_quellen(ist):
    """REIN RECHNEND: Teile eines gespeicherten Tageswerts (teile.ist) je Chart-Quelle (29.10.2026, Finn: „ein Chart, auf dem ich sehe, wie
    viel auf Wallets, auf Fusion, auf Geschäftskonto, in Kontowerten und sonstigen Sachen steckt"). Tage vor dem Split kennen kein
    gk_konto/sonstiges → Geschäftskonto = geschaeftskonto, Sonstiges = 0. Fusion kann fehlen (kein Stand) → 0."""
    fus = ist.get("fusion") if isinstance(ist.get("fusion"), dict) else None
    gk = _num(ist.get("geschaeftskonto"))
    sonst = _num(ist.get("sonstiges")) if "sonstiges" in ist else 0.0
    return {"wallets": round(_num(ist.get("wallets")), 2), "fusion": round(_num(fus.get("eur")) if fus else 0.0, 2),
            "geschaeftskonto": round(_num(ist.get("gk_konto")) if "gk_konto" in ist else gk - sonst, 2),
            "konten": round(_num(ist.get("konten")), 2), "payouts_offen": round(_num(ist.get("payouts_offen")), 2), "sonstiges": round(sonst, 2)}


def _als_dict(v):
    return v if isinstance(v, dict) else {}


def verlauf_zeile(r):
    """REIN RECHNEND: eine kapital_tageswerte-Zeile → Verlauf-Punkt. Rückblick-Zeilen (sql/2026-10-29_kapital_rueckblick.sql, teile.quelle
    'rueckblick': nur Wallets + Kontowerte nachgerechnet, Fusion/GK/offene Payouts erst ab 29.10.) tragen rueckblick=True und kein Soll —
    gelesen aus teile, damit es auch ohne die neue Spalte quelle geht."""
    teile = _als_dict(r.get("teile"))
    rueck = teile.get("quelle") == "rueckblick"
    return {"tag": r["tag"], "ist": _num(r["ist_eur"]), "rueckblick": rueck,
            "soll": None if rueck or r.get("soll_eur") is None else _num(r["soll_eur"]),
            "abw": None if rueck or r.get("abweichung_eur") is None else _num(r["abweichung_eur"]),
            "quellen": verlauf_quellen(teile.get("ist") or {}),
            # je ID (ab 29.10.2026 im Tageswert, Rückblick-Tage per sql/2026-10-29_kapital_rueckblick_je_id.sql) — fehlt bei älteren Zeilen
            "je_id": {uid: {"wallets": round(_num(z.get("wallets")), 2), "konten": round(_num(z.get("konten")), 2),
                            "payouts_offen": round(_num(z.get("payouts_offen")), 2)}
                      for uid, z in _als_dict((teile.get("ist") or {}).get("je_id")).items() if isinstance(z, dict)} or None}


def _tageswert_schreiben(gid, b):
    A["sb_upsert"]("kapital_tageswerte", {
        "gruppe_id": gid, "tag": _heute().isoformat(), "ist_eur": b["ist"]["summe"], "soll_eur": b["soll"]["summe"],
        "abweichung_eur": b["abweichung"], "updated_at": datetime.now(timezone.utc).isoformat(),
        "teile": {"ist": b["ist"], "soll": b["soll"], "fusion_report": b["fusion_report"], "toleranz": b["toleranz"],
                  "abfluesse_summe": b["abfluesse_summe"], "abfluesse_n": b["abfluesse_n"], "kurs": b["kurs"]}})


def ereignisse_lesen(gid, fx, ab=None):
    """Käufe, Blows und Hedge-Ergebnis je Tag und ID (sql/2026-10-29_kapital_ereignisse.sql) für die Marken im Verlauf-Grafen (Finn 29.10.2026:
    „warum der Chart manchmal so dumm um so 3–4k [springt]"). Je Tag gilt Δ Kontowerte = gekauft_eur + hedge_eur − geblowt_eur. Fehlt die
    Funktion oder schlägt sie fehl → [] (der Graf bleibt dann ohne Marken, alles andere unverändert)."""
    try:
        r = A["_sb_anfrage"]("POST", f"{A['SUPABASE_URL']}/rest/v1/rpc/kapital_ereignisse", headers=A["_sb_headers"](), timeout=(5, 20),
                             json={"p_gruppe": gid, "p_fx": fx})
        if r.status_code != 200:
            print(f"[kapital] Ereignisse HTTP {r.status_code}", flush=True)
            return []
        zeilen = r.json() or []
    except Exception as e:
        print(f"[kapital] ⚠️ Ereignisse: {type(e).__name__}: {e}", flush=True)
        return []
    return [{"tag": str(z.get("tag"))[:10], "id": str(z.get("user_id") or ""), "gekauft_n": int(_num(z.get("gekauft_n"))),
             "gekauft_eur": round(_num(z.get("gekauft_eur")), 2), "geblowt_n": int(_num(z.get("geblowt_n"))),
             "geblowt_eur": round(_num(z.get("geblowt_eur")), 2), "hedge_eur": round(_num(z.get("hedge_eur")), 2)}
            for z in zeilen if z.get("tag") and (not ab or str(z.get("tag"))[:10] >= ab)]


def kapital_fuer(gid, schreiben=True):
    d = _daten_lesen(gid)
    b = bilanz_rechnen(d["ketten"], d["snaps"], d["fusion_live"], d["fusion_hand"], d["einlagen"], d["tx"], d["labels"], d["adressen"],
                       d["kurs"]["fx"], d["offene"], d["gk"])
    b["kurs"] = d["kurs"]
    b["ist"]["wallets_gesamt_n"] = d["wallets_n"]
    namen = _id_namen(d["mit"])
    b["ist"]["je_id"] = je_id_rechnen(d["ketten"], d["snaps"], d["offene"], d["kurs"]["fx"], d["mit"])
    b["ids"] = sorted(({"id": u, "name": namen.get(u) or u[:8]} for u in b["ist"]["je_id"] if u not in KAPITAL_OHNE_CHIP), key=lambda x: x["name"].lower())
    if schreiben:
        try:
            _tageswert_schreiben(gid, b)
        except Exception as e:
            print(f"[kapital] ⚠️ Tageswert: {type(e).__name__}: {e}", flush=True)
    fx = d["kurs"]["fx"]
    b["einlagen"] = [{"id": e["id"], "betrag": _num(e["betrag"]), "waehrung": e.get("waehrung") or "EUR",
                      "betrag_eur": round(_num(e["betrag"]) * (fx if (e.get("waehrung") or "EUR") == "USD" else 1), 2),
                      "datum": e.get("datum"), "ziel_wallet": e.get("ziel_wallet") or "", "notiz": e.get("notiz") or "",
                      "quelle_tx": e.get("quelle_tx") or ""} for e in d["einlagen"]]
    b["gk_buchungen"] = [{"id": g["id"], "datum": g.get("datum"), "betrag": _num(g["betrag"]), "waehrung": g.get("waehrung") or "EUR",
                          "kategorie": g.get("kategorie") or "", "text": g.get("text") or "", "quelle": g.get("quelle") or "hand"}
                         for g in sorted(d["gk"], key=lambda x: (str(x.get("datum") or ""), str(x.get("created_at") or "")), reverse=True)]
    q = gk_quelle_lesen(gid)
    b["gk_quelle"] = None if not q else {
        "titel": q.get("titel") or "", "anteil_hinweis": q.get("anteil_hinweis") or "", "abruf_at": q.get("abruf_at"),
        "stand_text": q.get("stand_text") or "", "zeitraum_ab": q.get("zeitraum_ab"), "zeilen": q.get("zeilen"), "fehler": q.get("fehler") or "",
        "eingerichtet": bool((os.environ.get(GK_SHEET_SA_VAR) or "").strip())}
    b["gk_kategorien"] = GK_KATEGORIEN
    b["gk_posten_kategorien"] = GK_POSTEN_KATEGORIEN
    b["verlauf"] = [verlauf_zeile(r) for r in A["_sb_all"]("kapital_tageswerte", {"select": "tag,ist_eur,soll_eur,abweichung_eur,teile",
                                                                                  "gruppe_id": f"eq.{gid}", "order": "tag.asc"})]
    b["ereignisse"] = ereignisse_lesen(gid, fx, str(b["verlauf"][0]["tag"])[:10] if b["verlauf"] else None)
    return b


def _google_token():
    """Zugriffstoken für die Sheets-API (nur lesen) aus der Railway-Variable GOOGLE_SERVICE_ACCOUNT_JSON. → (token, None) / (None, fehler)."""
    roh = (os.environ.get(GK_SHEET_SA_VAR) or "").strip()
    if not roh:
        return None, f"Service-Konto fehlt (Railway-Variable {GK_SHEET_SA_VAR})"
    try:
        import json as _json
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as _GReq
        if _google["creds"] is None:
            _google["creds"] = service_account.Credentials.from_service_account_info(
                _json.loads(roh), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        c = _google["creds"]
        if not c.valid:
            c.refresh(_GReq())
        return c.token, None
    except Exception as e:
        _google["creds"] = None
        return None, f"Service-Konto nicht nutzbar: {type(e).__name__}: {str(e)[:160]}"


def gk_quelle_lesen(gid):
    """kapital_gk_quellen-Zeile der Gruppe oder None (auch wenn die Tabelle noch fehlt — sql/2026-10-29_kapital_gk_sheet.sql)."""
    try:
        rows = _sb("GET", "kapital_gk_quellen", {"select": "*", "gruppe_id": f"eq.{gid}"}) or []
        return rows[0] if rows else None
    except Exception:
        return None


def gk_sheet_abgleichen(gid, quelle):
    """Sheet lesen und kapital_gk_buchungen (quelle sheet) darauf abgleichen. Schreibt Stand/Fehler in kapital_gk_quellen. → Kurzbericht."""
    jetzt = datetime.now(timezone.utc).isoformat()
    token, fehler = _google_token()
    stand = {"abruf_at": jetzt, "fehler": fehler}
    bericht = {"ok": False, "fehler": fehler, "neu": 0, "weg": 0}
    if token:
        try:
            r = requests.get(f"https://sheets.googleapis.com/v4/spreadsheets/{quelle['sheet_id']}/values:batchGet",
                             params=[("ranges", b) for b in GK_SHEET_BEREICHE] + [("valueRenderOption", "FORMATTED_VALUE")],
                             headers={"Authorization": f"Bearer {token}"}, timeout=(5, 20))
            if r.status_code in (403, 404):
                raise RuntimeError(f"HTTP {r.status_code} — Sheet nicht mit dem Service-Konto geteilt?")
            r.raise_for_status()
            vr = (r.json() or {}).get("valueRanges") or []
            werte = (vr[0].get("values") if len(vr) > 0 else None) or []
            stand_text = (((vr[1].get("values") or [[""]])[0] or [""])[0] if len(vr) > 1 else "") or None
            ab = _de_datum((((vr[2].get("values") or [[""]])[0] or [""])[0]) if len(vr) > 2 else "")
            soll = gk_sheet_zeilen(werte)
            db = A["_sb_all"]("kapital_gk_buchungen", {"select": "id,zeilen_schluessel", "gruppe_id": f"eq.{gid}", "quelle": "eq.sheet"})
            neu, weg = gk_abgleich(soll, db)
            for i in range(0, len(weg), 100):
                _sb("DELETE", "kapital_gk_buchungen", {"id": _in(weg[i:i + 100]), "quelle": "eq.sheet"})
            if neu:
                _sb("POST", "kapital_gk_buchungen", body=[dict(z, gruppe_id=gid, quelle="sheet", angelegt_von="sheet") for z in neu],
                    prefer="return=minimal")
            stand.update(fehler=None, stand_text=stand_text, zeitraum_ab=ab, zeilen=len(soll))
            bericht = {"ok": True, "fehler": None, "neu": len(neu), "weg": len(weg), "zeilen": len(soll)}
        except Exception as e:
            stand["fehler"] = f"{type(e).__name__}: {str(e)[:200]}"
            bericht["fehler"] = stand["fehler"]
    try:
        _sb("PATCH", "kapital_gk_quellen", {"gruppe_id": f"eq.{gid}"}, body=stand, prefer="return=minimal")
    except Exception as e:
        print(f"[kapital] ⚠️ gk-quelle Stand: {type(e).__name__}: {e}", flush=True)
    if bericht["fehler"]:
        print(f"[kapital] ⚠️ Sheet {str(quelle.get('sheet_id'))[:6]}…: {bericht['fehler']}", flush=True)
    return bericht


def _gk_sheet_faellig(q):
    if not q:
        return False
    t = _ts(q.get("abruf_at"))
    return t is None or bool(q.get("fehler")) or (datetime.now(timezone.utc) - t).total_seconds() >= GK_SHEET_TAKT_S


def _takt_gruppen():
    """Gruppen mit Verwalter (heute Emin) — Hermann Technologies erst, wenn Finn es will."""
    return [str(g["id"]) for g in (_sb("GET", "id_gruppen", {"select": "id", "verwalter_user_id": "not.is.null"}) or [])]


def _takt_schleife():
    time.sleep(90)                                     # Start des Backends nicht belasten
    while True:
        _takt["laeuft"] = True
        try:
            for gid in _takt_gruppen():
                q = gk_quelle_lesen(gid)
                if _gk_sheet_faellig(q):
                    gk_sheet_abgleichen(gid, q)        # erst das Sheet, dann rechnen — der Tageswert enthält den frischen Stand
                kapital_fuer(gid, schreiben=True)
            _takt["fehler"] = ""
        except Exception as e:
            _takt["fehler"] = f"{type(e).__name__}: {e}"
            print(f"[kapital] ⚠️ Takt: {_takt['fehler']}", flush=True)
        _takt["at"] = time.time()
        _takt["laeuft"] = False
        time.sleep(TAKT_S)


def _admin_uid():
    return str(getattr(g, "kapital_uid", "") or request.environ.get("prophos.admin_uid") or "")


def _gate():
    """→ (erlaubt, None) oder (None, (Antwort, Status)); erlaubt = None (alle Gruppen) oder set der Gruppen-IDs. ENG wie _admin_mail_auth
    (Prüfer 29.10.2026: „im Admin uneingeschränkt" heißt nur „keine admin_zugang-Zeile" — das sind alle 15 HT-IDs, auch jeder Kunde):
      1. _wd_login (eingeloggt; setzt g.admin_sicht für eingeschränkte Logins, Verwalter nur mit ?ansicht=admin)
      2. Verwalter (g.admin_verwalter) → genau die Gruppen mit verwalter_user_id = er (Finn 04:30: Emin soll seine Gruppe sehen)
      3. sonst eingeschränkt (Mitglied, „nur eigene") → 403
      4. uneingeschränkt nur mit ADMIN_EMAILS (_admin_auth frei) ODER Eintrag in admin_mail_leser (heute „Finn + Pascal" — dieselbe
         Freigabe wie Admin → Mail, bewusst mitbenutzt statt einer zweiten Liste) → alle Gruppen; jeder andere Login → 403."""
    uid, err = A["_wd_login"]()
    if err:
        return None, err
    g.kapital_uid = uid
    nein = (jsonify({"ok": False, "error": "Nur für Admins oder den Verwalter der Gruppe"}), 403)
    if getattr(g, "admin_sicht", None) is not None:
        if getattr(g, "admin_verwalter", False):
            eigene = {str(x["id"]) for x in (_sb("GET", "id_gruppen", {"select": "id", "verwalter_user_id": f"eq.{uid}"}) or [])}
            if eigene:
                return eigene, None
        return None, nein
    _mail, err = A["_admin_auth"]()
    if err is None:
        return None, None
    if err[1] != 403:
        return None, err
    try:
        if str(uid) in A["admin_mail_leser_uids"]():
            return None, None
    except Exception:
        return None, (jsonify({"ok": False, "error": "Anmeldung nicht prüfbar"}), 502)
    return None, nein


def _darf(erlaubt, gid):
    return erlaubt is None or gid in erlaubt


def _datum(v):
    v = str(v or "").strip() or _heute().isoformat()
    return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else ""


def _loeschen(tabelle, body, erlaubt):
    eid = _uuid(body.get("id"))
    if not eid:
        return jsonify({"ok": False, "error": "id nötig"}), 400
    filt = {"id": f"eq.{eid}"}
    if erlaubt is not None:
        filt["gruppe_id"] = _in(erlaubt)               # Verwalter löscht nur Zeilen seiner Gruppe
    weg = _sb("DELETE", tabelle, filt, prefer="return=representation") or []
    return jsonify({"ok": True}) if weg else (jsonify({"ok": False, "error": "nicht gefunden"}), 404)


def _gk_aendern(body, erlaubt):
    """Posten inline bearbeiten (29.10.2026, „Weitere Posten"): {id, betrag?, kategorie?, text?, datum?} — nur Felder, die mitkommen; Zeile nur
    in einer erlaubten Gruppe (Verwalter: seine), Betrag ≠ 0 wie beim Anlegen (Wert „0" = Zeile löschen)."""
    eid = _uuid(body.get("id"))
    if not eid:
        return jsonify({"ok": False, "error": "id nötig"}), 400
    neu = {}
    if "betrag" in body:
        betrag = _num(body.get("betrag"))
        if betrag == 0:
            return jsonify({"ok": False, "error": "betrag ≠ 0 nötig (0 = Posten löschen)"}), 400
        neu["betrag"] = round(betrag, 2)
    if "kategorie" in body:
        neu["kategorie"] = str(body.get("kategorie") or "Sonstiges").strip()[:40] or "Sonstiges"
    if "text" in body:
        neu["text"] = str(body.get("text") or "").strip()[:300] or None
    if "datum" in body:
        datum = _datum(body.get("datum"))
        if not datum:
            return jsonify({"ok": False, "error": "datum JJJJ-MM-TT nötig"}), 400
        neu["datum"] = datum
    if not neu:
        return jsonify({"ok": False, "error": "nichts zu ändern"}), 400
    filt = {"id": f"eq.{eid}"}
    if erlaubt is not None:
        filt["gruppe_id"] = _in(erlaubt)               # Verwalter ändert nur Zeilen seiner Gruppe
    geaendert = A["sb_update"]("kapital_gk_buchungen", filt, neu) or []
    return jsonify({"ok": True, "buchung": geaendert[0]}) if geaendert else (jsonify({"ok": False, "error": "nicht gefunden"}), 404)


def registrieren(app, ns):
    """Routen an die Flask-App hängen; auf Railway den Stunden-Takt starten (auf den PCs ist PROPHOS_FRONTEND gesetzt — dort nie)."""
    A.update(ns)

    @app.route("/admin/kapital", methods=["GET", "OPTIONS"])
    def admin_kapital():
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = _gate()
        if err:
            return err
        try:
            gruppen = [{"id": str(x["id"]), "name": x.get("name") or "", "ht": not x.get("verwalter_user_id")}
                       for x in (_sb("GET", "id_gruppen", {"select": "id,name,verwalter_user_id", "order": "name.asc"}) or [])
                       if _darf(erlaubt, str(x["id"]))]
            gid = _uuid(request.args.get("gruppe"))
            if not gid or not any(x["id"] == gid for x in gruppen):   # Standard (auch bei fremder/alter Wahl): erste Gruppe mit Verwalter
                gid = next((x["id"] for x in gruppen if not x["ht"]), gruppen[0]["id"] if gruppen else "")
            grp = next((x for x in gruppen if x["id"] == gid), None)
            if not grp:
                return jsonify({"ok": False, "error": "Gruppe nicht gefunden", "gruppen": gruppen}), 404
            b = kapital_fuer(gid, schreiben=True)
        except Exception as e:
            print(f"[kapital] ⚠️ GET: {type(e).__name__}: {e}", flush=True)
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502
        return jsonify(dict(b, ok=True, gruppe=grp, gruppen=gruppen, takt={"fehler": _takt["fehler"]},
                            generated=datetime.now(timezone.utc).isoformat()))

    @app.route("/admin/kapital/einlage", methods=["POST", "DELETE", "OPTIONS"])
    def admin_kapital_einlage():
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = _gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            if request.method == "DELETE":
                return _loeschen("kapital_einlagen", body, erlaubt)
            gid, betrag, datum = _uuid(body.get("gruppe")), _num(body.get("betrag")), _datum(body.get("datum"))
            w = str(body.get("waehrung") or "EUR").upper()
            if not _darf(erlaubt, gid):
                return jsonify({"ok": False, "error": "Gruppe nicht freigegeben"}), 403
            if not gid or not (betrag > 0) or not datum or w not in ("EUR", "USD"):
                return jsonify({"ok": False, "error": "gruppe, betrag > 0, waehrung EUR/USD und datum (JJJJ-MM-TT) nötig"}), 400
            neu = A["sb_insert"]("kapital_einlagen", {
                "gruppe_id": gid, "betrag": round(betrag, 2), "waehrung": w, "datum": datum,
                "ziel_wallet": str(body.get("ziel_wallet") or "").strip()[:120] or None,
                "notiz": str(body.get("notiz") or "").strip()[:300] or None,
                "quelle_tx": str(body.get("quelle_tx") or "").strip()[:200] or None, "angelegt_von": _admin_uid() or None})
            return jsonify({"ok": True, "einlage": neu})
        except requests.exceptions.HTTPError as e:
            txt = str(getattr(e.response, "text", "") or "")
            if "duplicate key" in txt or "23505" in txt:
                return jsonify({"ok": False, "error": "Dieser Zufluss ist schon als Einlage gebucht"}), 409
            return jsonify({"ok": False, "error": f"HTTPError: {txt[:200]}"}), 502
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502

    @app.route("/admin/kapital/fusion", methods=["POST", "OPTIONS"])
    def admin_kapital_fusion():
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = _gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        gid, betrag, stand = _uuid(body.get("gruppe")), _num(body.get("betrag")), _datum(body.get("stand_am"))
        w = str(body.get("waehrung") or "EUR").upper()
        if not _darf(erlaubt, gid):
            return jsonify({"ok": False, "error": "Gruppe nicht freigegeben"}), 403
        if not gid or betrag < 0 or w not in ("EUR", "USD") or not stand:
            return jsonify({"ok": False, "error": "gruppe, betrag ≥ 0, waehrung EUR/USD und stand_am nötig"}), 400
        try:
            neu = A["sb_insert"]("kapital_fusion", {"gruppe_id": gid, "betrag": round(betrag, 2), "waehrung": w, "stand_am": stand,
                                                    "notiz": str(body.get("notiz") or "").strip()[:300] or None,
                                                    "angelegt_von": _admin_uid() or None})
            return jsonify({"ok": True, "fusion": neu})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502

    @app.route("/admin/kapital/gk", methods=["POST", "PATCH", "DELETE", "OPTIONS"])
    def admin_kapital_gk():
        """Geschäftskonto-Buchung (Finn 29.10.2026: „wie in so einem Google-Sheet … Kunden bezahlen oder PCs kaufen")."""
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = _gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            if request.method == "DELETE":
                return _loeschen("kapital_gk_buchungen", body, erlaubt)
            if request.method == "PATCH":
                return _gk_aendern(body, erlaubt)
            gid, betrag, datum = _uuid(body.get("gruppe")), _num(body.get("betrag")), _datum(body.get("datum"))
            w = str(body.get("waehrung") or "EUR").upper()
            kat = str(body.get("kategorie") or "Sonstiges").strip()[:40] or "Sonstiges"
            if not _darf(erlaubt, gid):
                return jsonify({"ok": False, "error": "Gruppe nicht freigegeben"}), 403
            if not gid or betrag == 0 or not datum or w not in ("EUR", "USD"):
                return jsonify({"ok": False, "error": "gruppe, betrag ≠ 0 (+ Eingang / − Ausgang), waehrung und datum nötig"}), 400
            neu = A["sb_insert"]("kapital_gk_buchungen", {
                "gruppe_id": gid, "datum": datum, "betrag": round(betrag, 2), "waehrung": w, "kategorie": kat,
                "text": str(body.get("text") or "").strip()[:300] or None, "angelegt_von": _admin_uid() or None})
            return jsonify({"ok": True, "buchung": neu})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502

    @app.route("/admin/kapital/gk/sheet", methods=["POST", "OPTIONS"])
    def admin_kapital_gk_sheet():
        """Knopf „Sheet jetzt lesen" im Geschäftskonto (sonst täglich im Takt)."""
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = _gate()
        if err:
            return err
        gid = _uuid((request.get_json(silent=True) or {}).get("gruppe"))
        if not gid or not _darf(erlaubt, gid):
            return jsonify({"ok": False, "error": "Gruppe nicht freigegeben"}), 403
        q = gk_quelle_lesen(gid)
        if not q:
            return jsonify({"ok": False, "error": "Für diese Gruppe ist kein Sheet hinterlegt (kapital_gk_quellen)"}), 404
        return jsonify(gk_sheet_abgleichen(gid, q))

    if (os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "").strip() \
            and not os.environ.get("PROPHOS_FRONTEND"):
        threading.Thread(target=_takt_schleife, name="kapital-takt", daemon=True).start()
