"""
AI Advisor v5 — Chat + Firm Rules + Conversations + Persistent Memory

Endpoints:
    POST   /advisor/recommend       — Single-Shot
    POST   /advisor/chat            — Multi-Turn (jetzt mit Auto-Save bei conversation_id)
    GET    /advisor/knowledge       — Wissensdokument lesen
    POST   /advisor/knowledge       — Wissensdokument schreiben
    GET    /advisor/firms           — Liste aller Firms mit Regeln
    POST   /advisor/firms           — Neue Firm hinzufuegen oder bestehende updaten
    DELETE /advisor/firms/<id>      — Firm loeschen
    POST   /advisor/firms/extract   — Free-Text via Claude in strukturiertes Markdown
    GET    /advisor/conversations          — Liste aller gespeicherten Konversationen
    GET    /advisor/conversations/<id>     — Eine Konversation laden
    POST   /advisor/conversations          — Konversation speichern (neu oder update)
    DELETE /advisor/conversations/<id>     — Konversation loeschen
    POST   /advisor/conversations/<id>/extract — Memory-Bullets aus Konversation extrahieren
    GET    /advisor/memory          — Persistent Memory lesen
    POST   /advisor/memory          — Persistent Memory schreiben
    GET    /advisor/health          — Status
"""

import os
import json
import re
import datetime
import uuid
from pathlib import Path
from flask import request, jsonify

KNOWLEDGE_FILE = "knowledge_base.md"
FIRMS_FILE = "firm_rules.json"
CONVERSATIONS_FILE = "conversations.json"
MEMORY_FILE = "advisor_memory.md"
MODEL = "claude-opus-4-5"
MAX_TOKENS = 4000


# ─── File I/O ──────────────────────────────────────────────────

def _load_knowledge_base():
    try:
        path = Path(KNOWLEDGE_FILE)
        if not path.exists():
            return None, f"knowledge_base.md nicht gefunden ({path.absolute()})"
        return path.read_text(encoding="utf-8"), None
    except Exception as e:
        return None, f"Fehler beim Laden des Knowledge-Docs: {e}"


def _save_knowledge_base(content):
    try:
        path = Path(KNOWLEDGE_FILE)
        if path.exists():
            backup = path.with_suffix(".md.bak")
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(content, encoding="utf-8")
        return True, None
    except Exception as e:
        return False, str(e)


def _load_firms():
    try:
        path = Path(FIRMS_FILE)
        if not path.exists():
            return {"version": 1, "firms": []}, None
        data = json.loads(path.read_text(encoding="utf-8"))
        if "firms" not in data:
            data["firms"] = []
        return data, None
    except Exception as e:
        return None, str(e)


def _save_firms(data):
    try:
        path = Path(FIRMS_FILE)
        if path.exists():
            backup = path.with_suffix(".json.bak")
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        data["updated_at"] = datetime.datetime.utcnow().isoformat()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, None
    except Exception as e:
        return False, str(e)


def _load_conversations():
    try:
        path = Path(CONVERSATIONS_FILE)
        if not path.exists():
            return {"version": 1, "conversations": []}, None
        data = json.loads(path.read_text(encoding="utf-8"))
        if "conversations" not in data:
            data["conversations"] = []
        return data, None
    except Exception as e:
        return None, str(e)


def _save_conversations(data):
    try:
        path = Path(CONVERSATIONS_FILE)
        if path.exists():
            backup = path.with_suffix(".json.bak")
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        data["updated_at"] = datetime.datetime.utcnow().isoformat()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, None
    except Exception as e:
        return False, str(e)


def _load_memory():
    try:
        path = Path(MEMORY_FILE)
        if not path.exists():
            default = (
                "# Persistent Memory — Operator-spezifische Erkenntnisse\n\n"
                "Dieses File wird bei jedem System-Prompt mitgeschickt. "
                "Hier kommen Patterns, Erkenntnisse und Operator-Status rein, "
                "die der Advisor across Konversationen behalten soll.\n\n"
                "## Operator-Status\n\n"
                "_Noch leer. Editier hier oder lass den Advisor extrahieren._\n\n"
                "## Trading-Patterns\n\n"
                "_Noch leer._\n\n"
                "## Wichtige Erkenntnisse\n\n"
                "_Noch leer._\n"
            )
            path.write_text(default, encoding="utf-8")
            return default, None
        return path.read_text(encoding="utf-8"), None
    except Exception as e:
        return None, f"Fehler beim Laden des Memory-Docs: {e}"


def _save_memory(content):
    try:
        path = Path(MEMORY_FILE)
        if path.exists():
            backup = path.with_suffix(".md.bak")
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(content, encoding="utf-8")
        return True, None
    except Exception as e:
        return False, str(e)


def _slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "firm"


def _generate_conv_id():
    return f"conv-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _auto_title(messages):
    for m in messages:
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                line = content.strip().split("\n")[0]
                if len(line) > 60:
                    line = line[:57] + "..."
                return line or "Neue Konversation"
    return "Neue Konversation"


# ─── Anthropic Client ──────────────────────────────────────────

def _get_anthropic_client():
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic SDK nicht installiert"
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY environment variable nicht gesetzt"
    return Anthropic(api_key=api_key), None


# ─── Prompt Building ───────────────────────────────────────────

def _build_firms_section():
    data, err = _load_firms()
    if err or not data.get("firms"):
        return ""
    parts = ["\n=== PROP FIRM REGELN ===\n"]
    for firm in data["firms"]:
        rules = firm.get("rules_markdown", "").strip()
        if rules and "_Noch nicht ausgefuellt" not in rules and "_Noch nicht ausgefüllt" not in rules:
            parts.append(rules)
            parts.append("")
    parts.append("=== ENDE PROP FIRM REGELN ===\n")
    return "\n".join(parts)


def _build_memory_section():
    memory, err = _load_memory()
    if err or not memory:
        return ""
    return f"\n=== PERSISTENT MEMORY (Operator-Erkenntnisse aus alten Konversationen) ===\n\n{memory}\n\n=== ENDE PERSISTENT MEMORY ===\n"


def _build_system_prompt(knowledge):
    firms_section = _build_firms_section()
    memory_section = _build_memory_section()
    return (
        "Du bist der AI-Advisor fuer Prophos, das Prop-Firm-Hedging-Tool des Operators. "
        "Du hast Zugriff auf das Strategie-Wissensdokument, eine Datenbank mit "
        "Firm-spezifischen Regeln, und ein Persistent Memory mit Operator-Erkenntnissen "
        "aus frueheren Konversationen.\n\n"
        "Verhaltensregeln:\n"
        "- Empfehle NIE Markt-Direction (Long/Short) — der Operator ist immer marktneutral\n"
        "- Halluziniere KEINE Zahlen — wenn dir was fehlt, sag es\n"
        "- Wenn der Account-Pool keine sinnvolle Empfehlung erlaubt, sag das ehrlich\n"
        "- Sei konkret: nenn Account-Namen, Euro-Werte, konkrete Risk-Allokationen\n"
        "- Flagge Hektik-Risk-Indikatoren proaktiv\n"
        "- Pruefe IMMER die Firm-Regeln gegen jeden Empfehlungs-Vorschlag\n"
        "- Falls Firm-Regeln zu einer involvierten Firma fehlen, weise darauf hin\n"
        "- Beziehe dich aktiv auf das Persistent Memory wenn relevant\n"
        "- Nutze Markdown: Tabellen fuer Vergleiche, Listen fuer Optionen, Bold fuer Empfehlungen\n"
        "- Antworte auf Deutsch\n"
        "- Im Chat-Modus: knappe Antworten ausser explizit nach Tiefe gefragt\n\n"
        "=== STRATEGIE-WISSENSDOKUMENT ===\n\n"
        f"{knowledge}\n\n"
        "=== ENDE WISSENSDOKUMENT ===\n"
        f"{firms_section}\n"
        f"{memory_section}\n"
        "Folge dem Wissensdokument, den Firm-Regeln und dem Persistent Memory als verbindlicher Grundlage."
    )


def _build_account_context(payload):
    parts = []
    accounts = payload.get("accounts", [])
    if accounts:
        parts.append("## Aktueller Account-Pool")
        parts.append("```json")
        parts.append(json.dumps(accounts, indent=2, ensure_ascii=False, default=str))
        parts.append("```")
    trade_plans = payload.get("trade_plans", [])
    if trade_plans:
        parts.append("\n## Letzte Trade-Plans")
        parts.append("```json")
        parts.append(json.dumps(trade_plans[-10:], indent=2, ensure_ascii=False, default=str))
        parts.append("```")
    mode = payload.get("mode")
    if mode and mode != "auto":
        parts.append(f"\n**Operations-Modus:** {mode}")
    return "\n".join(parts) if parts else ""


# ─── Claude Call mit Caching ──────────────────────────────────

def _call_claude(client, system_prompt, messages, max_tokens=None):
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens or MAX_TOKENS,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=messages,
    )
    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    text = "\n".join(text_blocks)
    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cost = (
        (input_tokens / 1_000_000 * 15)
        + (output_tokens / 1_000_000 * 75)
        + (cache_creation / 1_000_000 * 18.75)
        + (cache_read / 1_000_000 * 1.50)
    )
    return {
        "text": text,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "cache_creation": cache_creation,
            "cache_read": cache_read,
        },
        "cost_usd": round(cost, 4),
        "model": MODEL,
    }


# ─── Endpoints: Recommend / Chat ───────────────────────────────

def recommend_handler():
    if request.method == "OPTIONS":
        return "", 200
    knowledge, kb_err = _load_knowledge_base()
    if kb_err:
        return jsonify({"error": kb_err}), 500
    client, client_err = _get_anthropic_client()
    if client_err:
        return jsonify({"error": client_err}), 500

    payload = request.get_json(silent=True) or {}
    parts = []
    ctx = _build_account_context(payload)
    if ctx:
        parts.append(ctx)
    parts.append("\n## Operator-Frage")
    question = payload.get("question", "").strip()
    parts.append(question or "Schau auf den Pool und gib eine konkrete Empfehlung.")
    user_message = "\n".join(parts)

    try:
        result = _call_claude(client, _build_system_prompt(knowledge),
                              [{"role": "user", "content": user_message}])
        return jsonify({
            "recommendation": result["text"],
            "tokens": result["tokens"],
            "cost_usd": result["cost_usd"],
            "model": result["model"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def chat_handler():
    if request.method == "OPTIONS":
        return "", 200
    knowledge, kb_err = _load_knowledge_base()
    if kb_err:
        return jsonify({"error": kb_err}), 500
    client, client_err = _get_anthropic_client()
    if client_err:
        return jsonify({"error": client_err}), 500

    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages required"}), 400

    conversation_id = payload.get("conversation_id")  # optional, fuer Auto-Save

    ctx = _build_account_context(payload)
    api_messages = list(messages)
    if ctx and api_messages and api_messages[-1].get("role") == "user":
        last = api_messages[-1]
        api_messages = api_messages[:-1] + [{
            "role": "user",
            "content": f"{ctx}\n\n---\n\n{last.get('content', '')}" if last.get("content") else ctx,
        }]

    try:
        result = _call_claude(client, _build_system_prompt(knowledge), api_messages)
        assistant_message = {"role": "assistant", "content": result["text"]}

        # Auto-Save: wenn conversation_id mitgegeben, Konversation persistieren
        saved_conv_id = None
        if conversation_id:
            full_messages = list(messages) + [assistant_message]
            saved_conv_id, _ = _upsert_conversation(
                conversation_id, full_messages, payload.get("title")
            )

        return jsonify({
            "message": assistant_message,
            "tokens": result["tokens"],
            "cost_usd": result["cost_usd"],
            "model": result["model"],
            "conversation_id": saved_conv_id or conversation_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Endpoints: Knowledge ──────────────────────────────────────

def get_knowledge_handler():
    knowledge, err = _load_knowledge_base()
    if err:
        return jsonify({"error": err}), 404
    return jsonify({"knowledge": knowledge, "length_chars": len(knowledge), "file": KNOWLEDGE_FILE})


def save_knowledge_handler():
    if request.method == "OPTIONS":
        return "", 200
    payload = request.get_json(silent=True) or {}
    content = payload.get("knowledge", "")
    if not content or len(content) < 100:
        return jsonify({"error": "Zu kurz"}), 400
    if len(content) > 200_000:
        return jsonify({"error": "Zu gross"}), 400
    ok, err = _save_knowledge_base(content)
    if not ok:
        return jsonify({"error": err}), 500
    return jsonify({"saved": True, "length_chars": len(content)})


# ─── Endpoints: Firms ──────────────────────────────────────────

def list_firms_handler():
    data, err = _load_firms()
    if err:
        return jsonify({"error": err}), 500
    for firm in data.get("firms", []):
        rules = firm.get("rules_markdown", "")
        firm["is_filled"] = bool(
            rules and len(rules) > 100
            and "Noch nicht ausgefuellt" not in rules
            and "Noch nicht ausgefüllt" not in rules
        )
    return jsonify(data)


def upsert_firm_handler():
    if request.method == "OPTIONS":
        return "", 200
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    firm_id = (payload.get("id") or "").strip() or _slugify(name)
    rules_markdown = payload.get("rules_markdown", "").strip()
    raw_source = payload.get("raw_source", "")
    category = payload.get("category", "")

    data, err = _load_firms()
    if err:
        return jsonify({"error": err}), 500

    now = datetime.datetime.utcnow().isoformat()
    existing = next((f for f in data["firms"] if f["id"] == firm_id), None)

    if existing:
        existing["name"] = name
        existing["category"] = category or existing.get("category", "")
        existing["rules_markdown"] = rules_markdown or existing.get("rules_markdown", "")
        if raw_source:
            existing["raw_source"] = raw_source
        existing["updated_at"] = now
    else:
        data["firms"].append({
            "id": firm_id,
            "name": name,
            "category": category,
            "rules_markdown": rules_markdown,
            "raw_source": raw_source,
            "updated_at": now,
        })

    ok, err = _save_firms(data)
    if not ok:
        return jsonify({"error": err}), 500
    return jsonify({"saved": True, "id": firm_id})


def delete_firm_handler(firm_id):
    if request.method == "OPTIONS":
        return "", 200
    data, err = _load_firms()
    if err:
        return jsonify({"error": err}), 500
    before = len(data["firms"])
    data["firms"] = [f for f in data["firms"] if f["id"] != firm_id]
    if len(data["firms"]) == before:
        return jsonify({"error": "Firm nicht gefunden"}), 404
    ok, err = _save_firms(data)
    if not ok:
        return jsonify({"error": err}), 500
    return jsonify({"deleted": True})


def extract_firm_handler():
    if request.method == "OPTIONS":
        return "", 200
    client, client_err = _get_anthropic_client()
    if client_err:
        return jsonify({"error": client_err}), 500

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip() or "Unbenannte Firm"
    raw_text = (payload.get("raw_text") or "").strip()
    if len(raw_text) < 50:
        return jsonify({"error": "raw_text zu kurz (min 50 Zeichen)"}), 400
    if len(raw_text) > 50_000:
        return jsonify({"error": "raw_text zu gross (max 50K)"}), 400

    extraction_system_prompt = (
        "Du bist ein Datenextraktions-Assistent für Prop-Firm-Regeln. "
        "Der Operator gibt dir einen Free-Text mit Regeln einer Prop-Firm. "
        "Extrahier alle relevanten Trading-Regeln in ein strukturiertes Markdown.\n\n"
        "Beachte:\n"
        "- Nutze IMMER dieses Format mit den Sektionen unten\n"
        "- Wenn eine Info im Text fehlt: 'unbekannt' eintragen, NICHT raten\n"
        "- Werte exakt uebernehmen wie im Original (Prozente, Dollarbetraege, Tage)\n"
        "- Bei mehreren Account-Sizes / Phasen: alle auflisten\n"
        "- Antworte AUSSCHLIESSLICH mit dem Markdown-Block, kein Vorwort, kein Nachwort\n\n"
        "Ziel-Format:\n\n"
        "```\n"
        "## [FIRM NAME]\n\n"
        "**Kategorie:** futures / cfd / mixed\n"
        "**Account-Sizes:** [...]\n"
        "**Phasen-Struktur:** 1-step / 2-step / 3-step / Combine\n\n"
        "### Drawdown\n- **Daily Loss Limit:** [...]\n- **Max Drawdown:** [...]\n\n"
        "### Profit-Targets pro Phase\n- Phase 1: [...]\n- Phase 2: [...]\n\n"
        "### Consistency-Regeln\n- Variante: [...]\n- Schwelle: [X%]\n\n"
        "### Time-Rules\n- Min Trading Days: [...]\n- Weekend Holding: erlaubt / verboten\n- News Trading: erlaubt / restricted / verboten\n\n"
        "### Hedging-Regeln\n- Internal Hedging: erlaubt / verboten\n- Cross-Account Same Symbol: [...]\n\n"
        "### Payout\n- Profit Split: [X%]\n- First Payout After: [Tage]\n\n"
        "### Sonstiges\n- [...]\n"
        "```\n"
    )

    user_message = (
        f"Firm: {name}\n\n"
        f"Free-Text (Original-Quelle):\n\n{raw_text}\n\n"
        "Bitte extrahier alle Trading-Regeln in das vorgegebene Markdown-Format."
    )

    try:
        result = _call_claude(client, extraction_system_prompt,
                              [{"role": "user", "content": user_message}],
                              max_tokens=2000)
        text = result["text"].strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)
        return jsonify({
            "rules_markdown": text,
            "tokens": result["tokens"],
            "cost_usd": result["cost_usd"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Endpoints: Conversations ──────────────────────────────────

def _upsert_conversation(conv_id, messages, title=None):
    data, err = _load_conversations()
    if err:
        return None, err
    now = datetime.datetime.utcnow().isoformat()
    existing = next((c for c in data["conversations"] if c["id"] == conv_id), None)
    if existing:
        existing["messages"] = messages
        existing["updated_at"] = now
        if title:
            existing["title"] = title
    else:
        data["conversations"].append({
            "id": conv_id,
            "title": title or _auto_title(messages),
            "messages": messages,
            "created_at": now,
            "updated_at": now,
        })
    ok, save_err = _save_conversations(data)
    if not ok:
        return None, save_err
    return conv_id, None


def list_conversations_handler():
    data, err = _load_conversations()
    if err:
        return jsonify({"error": err}), 500
    summary = []
    for c in data.get("conversations", []):
        summary.append({
            "id": c["id"],
            "title": c.get("title", "Konversation"),
            "created_at": c.get("created_at"),
            "updated_at": c.get("updated_at"),
            "message_count": len(c.get("messages", [])),
        })
    summary.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return jsonify({"conversations": summary})


def get_conversation_handler(conv_id):
    data, err = _load_conversations()
    if err:
        return jsonify({"error": err}), 500
    conv = next((c for c in data.get("conversations", []) if c["id"] == conv_id), None)
    if not conv:
        return jsonify({"error": "Konversation nicht gefunden"}), 404
    return jsonify(conv)


def save_conversation_handler():
    if request.method == "OPTIONS":
        return "", 200
    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    if not messages:
        return jsonify({"error": "messages required"}), 400
    conv_id = payload.get("id") or _generate_conv_id()
    title = payload.get("title")
    saved_id, err = _upsert_conversation(conv_id, messages, title)
    if err:
        return jsonify({"error": err}), 500
    return jsonify({"saved": True, "id": saved_id})


def delete_conversation_handler(conv_id):
    if request.method == "OPTIONS":
        return "", 200
    data, err = _load_conversations()
    if err:
        return jsonify({"error": err}), 500
    before = len(data["conversations"])
    data["conversations"] = [c for c in data["conversations"] if c["id"] != conv_id]
    if len(data["conversations"]) == before:
        return jsonify({"error": "Konversation nicht gefunden"}), 404
    ok, err = _save_conversations(data)
    if not ok:
        return jsonify({"error": err}), 500
    return jsonify({"deleted": True})


def extract_memory_from_conversation_handler(conv_id):
    if request.method == "OPTIONS":
        return "", 200
    client, client_err = _get_anthropic_client()
    if client_err:
        return jsonify({"error": client_err}), 500
    data, err = _load_conversations()
    if err:
        return jsonify({"error": err}), 500
    conv = next((c for c in data.get("conversations", []) if c["id"] == conv_id), None)
    if not conv:
        return jsonify({"error": "Konversation nicht gefunden"}), 404

    transcript_parts = []
    for m in conv.get("messages", []):
        role = "OPERATOR" if m.get("role") == "user" else "ADVISOR"
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join([c.get("text", "") for c in content if isinstance(c, dict)])
        transcript_parts.append(f"[{role}]\n{content}\n")
    transcript = "\n".join(transcript_parts)

    extraction_prompt = (
        "Du analysierst eine Konversation zwischen einem Prop-Firm-Trader (Operator) "
        "und einem AI-Advisor. Extrahier WICHTIGE OPERATOR-ERKENNTNISSE als persistent Memory.\n\n"
        "Was rein soll:\n"
        "- Operator-Status-Updates (z.B. 'Account X ist jetzt geflagged')\n"
        "- Trading-Patterns die der Operator etabliert hat\n"
        "- Wichtige Erkenntnisse oder Entscheidungen\n"
        "- Praeferenzen, Constraints, Restrictions\n"
        "- Korrigierte Annahmen\n\n"
        "Was NICHT rein soll:\n"
        "- Allgemeine Informationen die schon im Wissensdokument oder Firm-Regeln stehen\n"
        "- Triviale Konversations-Stuecke\n"
        "- Hypothetische Ueberlegungen ohne Entscheidung\n\n"
        "Format: pure Markdown-Bullet-Liste, kategorisiert nach Sektionen wie "
        "'## Operator-Status', '## Trading-Patterns', '## Wichtige Erkenntnisse'. "
        "Wenn nichts Memory-wuerdiges drin ist: '_Keine neuen Erkenntnisse._'\n\n"
        "Antworte AUSSCHLIESSLICH mit dem Markdown."
    )

    try:
        result = _call_claude(client, extraction_prompt,
                              [{"role": "user", "content": f"Konversation:\n\n{transcript}"}],
                              max_tokens=2000)
        text = result["text"].strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)
        return jsonify({
            "extracted_memory": text,
            "tokens": result["tokens"],
            "cost_usd": result["cost_usd"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Endpoints: Memory ─────────────────────────────────────────

def get_memory_handler():
    memory, err = _load_memory()
    if err:
        return jsonify({"error": err}), 500
    return jsonify({"memory": memory, "length_chars": len(memory), "file": MEMORY_FILE})


def save_memory_handler():
    if request.method == "OPTIONS":
        return "", 200
    payload = request.get_json(silent=True) or {}
    content = payload.get("memory", "")
    if len(content) > 100_000:
        return jsonify({"error": "Zu gross (max 100K)"}), 400
    ok, err = _save_memory(content)
    if not ok:
        return jsonify({"error": err}), 500
    return jsonify({"saved": True, "length_chars": len(content)})


# ─── Health ────────────────────────────────────────────────────

def health_handler():
    knowledge, kb_err = _load_knowledge_base()
    client, client_err = _get_anthropic_client()
    firms_data, firms_err = _load_firms()
    convs_data, convs_err = _load_conversations()
    memory, mem_err = _load_memory()

    filled_count = 0
    if firms_data and not firms_err:
        for firm in firms_data.get("firms", []):
            rules = firm.get("rules_markdown", "")
            if (rules and len(rules) > 100
                    and "Noch nicht ausgefuellt" not in rules
                    and "Noch nicht ausgefüllt" not in rules):
                filled_count += 1

    return jsonify({
        "knowledge_base": {
            "ok": kb_err is None,
            "error": kb_err,
            "length_chars": len(knowledge) if knowledge else 0,
        },
        "anthropic_client": {
            "ok": client_err is None,
            "error": client_err,
            "model": MODEL,
        },
        "firms": {
            "ok": firms_err is None,
            "error": firms_err,
            "total": len(firms_data.get("firms", [])) if firms_data else 0,
            "filled": filled_count,
        },
        "conversations": {
            "ok": convs_err is None,
            "error": convs_err,
            "total": len(convs_data.get("conversations", [])) if convs_data else 0,
        },
        "memory": {
            "ok": mem_err is None,
            "error": mem_err,
            "length_chars": len(memory) if memory else 0,
        },
        "ready": kb_err is None and client_err is None,
    })


# ─── Registration ─────────────────────────────────────────────

def register_advisor_routes(app):
    app.add_url_rule("/advisor/recommend", view_func=recommend_handler, methods=["POST", "OPTIONS"])
    app.add_url_rule("/advisor/chat", view_func=chat_handler, methods=["POST", "OPTIONS"])
    app.add_url_rule("/advisor/knowledge", view_func=get_knowledge_handler,
                     methods=["GET"], endpoint="advisor_get_knowledge")
    app.add_url_rule("/advisor/knowledge", view_func=save_knowledge_handler,
                     methods=["POST", "OPTIONS"], endpoint="advisor_save_knowledge")
    app.add_url_rule("/advisor/firms", view_func=list_firms_handler,
                     methods=["GET"], endpoint="advisor_list_firms")
    app.add_url_rule("/advisor/firms", view_func=upsert_firm_handler,
                     methods=["POST", "OPTIONS"], endpoint="advisor_upsert_firm")
    app.add_url_rule("/advisor/firms/<firm_id>", view_func=delete_firm_handler,
                     methods=["DELETE", "OPTIONS"], endpoint="advisor_delete_firm")
    app.add_url_rule("/advisor/firms/extract", view_func=extract_firm_handler,
                     methods=["POST", "OPTIONS"], endpoint="advisor_extract_firm")
    # NEU v5: Conversations
    app.add_url_rule("/advisor/conversations", view_func=list_conversations_handler,
                     methods=["GET"], endpoint="advisor_list_convs")
    app.add_url_rule("/advisor/conversations", view_func=save_conversation_handler,
                     methods=["POST", "OPTIONS"], endpoint="advisor_save_conv")
    app.add_url_rule("/advisor/conversations/<conv_id>", view_func=get_conversation_handler,
                     methods=["GET"], endpoint="advisor_get_conv")
    app.add_url_rule("/advisor/conversations/<conv_id>", view_func=delete_conversation_handler,
                     methods=["DELETE", "OPTIONS"], endpoint="advisor_delete_conv")
    app.add_url_rule("/advisor/conversations/<conv_id>/extract",
                     view_func=extract_memory_from_conversation_handler,
                     methods=["POST", "OPTIONS"], endpoint="advisor_extract_memory")
    # NEU v5: Memory
    app.add_url_rule("/advisor/memory", view_func=get_memory_handler,
                     methods=["GET"], endpoint="advisor_get_memory")
    app.add_url_rule("/advisor/memory", view_func=save_memory_handler,
                     methods=["POST", "OPTIONS"], endpoint="advisor_save_memory")
    app.add_url_rule("/advisor/health", view_func=health_handler, methods=["GET"])
