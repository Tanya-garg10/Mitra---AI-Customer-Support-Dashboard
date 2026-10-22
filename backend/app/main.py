import asyncio
import logging
import os
import re
import uuid
import json
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexora")

APP_NAME = "Mitra | Customer Care Studio"
APP_VERSION = "1.3.0"
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
AI_PROVIDER = os.getenv("AI_PROVIDER", "featherless").strip().lower()
AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", "").rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")
app = FastAPI(title=APP_NAME, version=APP_VERSION)

origins = [x.strip() for x in os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# Demo knowledge base. In production, load approved articles from a database/vector store.
KNOWLEDGE_BASE = [
    {
        "id": "KB-001",
        "title": "Password reset troubleshooting",
        "content": "Use the newest password-reset email only. Reset links can expire after 30 minutes. Check spam, confirm the account email, and request a new link. Support agents must never ask customers to share their password or one-time verification code.",
        "keywords": ["password", "reset", "login", "sign in", "account", "link"]
    },
    {
        "id": "KB-002",
        "title": "Order tracking and delivery",
        "content": "Customers can check shipment status from Orders > Order details. Tracking updates may take up to 24 hours after dispatch. If there is no update after 48 hours, create a support ticket for the fulfilment team. Do not promise a delivery date unless it is shown in the order system.",
        "keywords": ["order", "delivery", "shipping", "shipment", "tracking", "package"]
    },
    {
        "id": "KB-003",
        "title": "Refund eligibility",
        "content": "Refund eligibility depends on order status and the applicable return policy. The demo refund action only simulates a request; it does not move money. Confirm the order and policy before approving a real refund. Never claim that a refund has been completed by this demo.",
        "keywords": ["refund", "return", "money back", "charged", "payment", "billing"]
    },
    {
        "id": "KB-004",
        "title": "Export and technical issues",
        "content": "For export problems, confirm the selected date range and filters, retry once, and capture the error message. If records remain missing, create a technical support ticket with the affected report name and approximate time. Do not request passwords or payment secrets.",
        "keywords": ["export", "csv", "report", "error", "bug", "crash", "missing", "technical"]
    },
    {
        "id": "KB-005",
        "title": "Subscription and discount offers",
        "content": "Plan renewal dates should be checked in account billing settings. Discount codes shown in this demo are illustrative and may not be valid in a real store. Do not guarantee eligibility or claim that an offer has been applied unless the connected billing system confirms it.",
        "keywords": ["subscription", "renew", "plan", "discount", "coupon", "price"]
    }
]

# These separated prompt templates document the intended LLM strategy. The default
# implementation is deterministic and local so the project works without an API key.
PROMPT_TEMPLATES = {
    "chatbot_persona": """PERSONA PROMPT: You are Mitra, an empathetic, context-aware support assistant.
Use only the approved knowledge-base context and conversation history. Ask one concise
clarifying question when key facts are missing. Give numbered, safe troubleshooting steps.
Match the detected sentiment and the customer’s technical fluency: reassure frustrated users,
stay concise for neutral users, and use precise technical language when it is appropriate.
Never ask for passwords, one-time codes, full payment card details, or secrets. Never claim
an action succeeded unless a connected system confirms it. Escalate complex or high-risk cases.""",
    "sentiment_classifier": """CLASSIFIER PROMPT: Return structured labels for sentiment, urgency, user intent,
category, and key entities. Use only evidence in the conversation. If uncertain, label it
unknown rather than inventing details. Do not reproduce sensitive personal data.""",
    "summary_ticket_generator": """SUMMARY PROMPT: Produce a concise root-cause hypothesis, facts confirmed,
steps already tried, missing information, and escalation reason. Clearly distinguish confirmed
facts from hypotheses. Never expose secrets or invent order/account facts.""",
    "action_plan": """ACTION PLAN PROMPT: Recommend safe next steps based on the full conversation and
approved knowledge context. State prerequisites and what a human must verify. Refunds,
discounts, and ticket actions in this demo are simulations only."""
}

sessions: dict[str, dict[str, Any]] = {}
tickets: list[dict[str, Any]] = []
actions_log: list[dict[str, Any]] = []
uploaded_knowledge: list[dict[str, Any]] = []
manager_sockets: set[WebSocket] = set()


class ChatMessage(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)


class ActionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    action: str
    details: dict[str, Any] = Field(default_factory=dict)


class TicketRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    customer_name: str = Field(default="Guest", max_length=100)
    subject: str = Field(min_length=3, max_length=200)


class KnowledgeArticleRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    content: str = Field(min_length=40, max_length=20000)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_sensitive(text: str) -> str:
    """Redact common secrets before storing/displaying text."""
    patterns = [
        (r'\b(?:\d[ -]*?){13,19}\b', "[REDACTED PAYMENT NUMBER]"),
        (r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', "[EMAIL REDACTED]"),
        (r'(?i)\b(password|passcode|one[- ]time code|otp)\s*[:=]\s*\S+', r'\1: [REDACTED]'),
    ]
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    return result


def classify(text: str) -> dict[str, Any]:
    t = text.lower()
    if any(w in t for w in ["refund", "charged", "payment", "billing", "subscription", "discount"]):
        category, intent = "Billing & orders", "billing_or_refund"
    elif any(w in t for w in ["password", "login", "sign in", "account", "reset"]):
        category, intent = "Account access", "account_recovery"
    elif any(w in t for w in ["bug", "error", "crash", "export", "missing", "not working", "failed", "sync", "connector", "integration", "queue", "timeout", "connection", "slow", "stuck"]):
        category, intent = "Technical issue", "troubleshooting"
    elif any(w in t for w in ["delivery", "shipping", "tracking", "package", "order"]):
        category, intent = "Order & delivery", "order_tracking"
    else:
        category, intent = "General support", "general_question"

    if any(w in t for w in ["urgent", "immediately", "can't work", "cannot work", "locked out", "charged twice", "fraud", "security", "unsafe"]):
        urgency = "High"
    elif any(w in t for w in ["not working", "missing", "failed", "broken", "frustrated", "still", "again", "problem", "delayed", "stuck", "slow"]):
        urgency = "Medium"
    else:
        urgency = "Low"

    if any(w in t for w in ["furious", "angry", "unacceptable", "terrible", "frustrated", "fed up"]):
        sentiment = "Frustrated"
    elif any(w in t for w in ["worried", "concerned", "anxious", "scared"]):
        sentiment = "Concerned"
    elif any(w in t for w in ["thanks", "thank you", "great", "appreciate", "excellent"]):
        sentiment = "Positive"
    else:
        sentiment = "Neutral"

    entities = []
    for word in ["order", "refund", "password", "subscription", "export", "delivery", "account", "sync", "connector", "integration"]:
        if word in t and word not in entities:
            entities.append(word)
    return {
        "category": category, "intent": intent, "urgency": urgency,
        "sentiment": sentiment, "entities": entities or ["support request"],
        "severity_score": {"Low": 24, "Medium": 58, "High": 88}[urgency]
    }


def retrieve_context(text: str) -> list[dict[str, str]]:
    t = text.lower()
    scored = []
    for article in [*KNOWLEDGE_BASE, *uploaded_knowledge]:
        score = sum(1 for keyword in article["keywords"] if keyword in t)
        if score:
            scored.append((score, article))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {"id": a["id"], "title": a["title"], "content": a["content"]}
        for _, a in scored[:3]
    ]



def make_llm_messages(message: str, context: list[dict[str, str]], history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Build separated prompt-chain messages for an OpenAI-compatible chat-completions endpoint."""
    context_text = "\n\n".join(f"[{a['id']}] {a['title']}: {a['content']}" for a in context) or "No matching knowledge articles found."
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])
    persona = PROMPT_TEMPLATES["chatbot_persona"]
    grounding = (
        "KNOWLEDGE-BASE GROUNDING: Use only the provided knowledge context for product policy. "
        "If the context does not answer the question, say so and ask a clarifying question or recommend human escalation. "
        "Do not invent order status, eligibility, dates, refunds, account facts, or policy."
    )
    user_payload = f"""APPROVED KNOWLEDGE CONTEXT:
{context_text}

RECENT CONVERSATION:
{transcript}

LATEST USER MESSAGE:
{message}

Return only JSON with keys reply (string), steps (array of strings), needs_clarification (boolean).
Keep the reply empathetic and specific. Never request passwords, one-time codes, full card numbers, or secrets.
Do not state that a simulated refund, discount, or ticket action has succeeded in an external system."""
    return [
        {"role": "system", "content": persona + "\n\n" + grounding},
        {"role": "system", "content": PROMPT_TEMPLATES["sentiment_classifier"]},
        {"role": "user", "content": user_payload},
    ]


async def try_llm_reply(message: str, context: list[dict[str, str]], history: list[dict[str, str]]) -> dict[str, Any] | None:
    """Optional OpenAI-compatible provider. Without configured env vars, local mode is used."""
    if not (AI_API_BASE_URL and AI_API_KEY and AI_MODEL):
        return None
    endpoint = AI_API_BASE_URL
    if not endpoint.endswith("/chat/completions"):
        endpoint = endpoint + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODEL,
                    "temperature": 0.25,
                    "response_format": {"type": "json_object"},
                    "messages": make_llm_messages(message, context, history),
                },
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            reply = str(parsed.get("reply", "")).strip()
            if not reply:
                return None
            steps = parsed.get("steps", [])
            if not isinstance(steps, list):
                steps = []
            return {
                "reply": reply,
                "steps": [str(x)[:500] for x in steps[:8]],
                "needs_clarification": bool(parsed.get("needs_clarification", False)),
                "provider": AI_PROVIDER,
            }
    except Exception as exc:
        logger.warning("Configured AI provider failed; using local engine: %s", exc)
        return None


def build_local_reply(message: str, context: list[dict[str, str]], labels: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
    if labels["sentiment"] in {"Frustrated", "Concerned"}:
        opening = "I’m sorry this has been stressful. I’ll help you work through it."
    else:
        opening = "Thanks for explaining the issue. I’ll help you with the next steps."

    if not context:
        answer = opening + " I want to avoid guessing. Could you share what you were trying to do and the exact message or result you saw? Please do not include passwords, one-time codes, or payment details."
        steps = ["Describe the action you attempted.", "Share the exact error text, if any.", "Tell me what you have already tried."]
        needs_clarification = True
    else:
        article = context[0]
        answer = opening + f"\n\nBased on our support guide, {article['title']}:\n{article['content']}"
        steps = [s.strip() for s in re.split(r'(?<=[.!?])\s+', article["content"]) if s.strip()][:4]
        needs_clarification = labels["urgency"] == "High" or len(history) < 2
        if needs_clarification:
            answer += "\n\nTo narrow this down, can you tell me when this first happened and whether you see an error message?"
    if labels["urgency"] == "High":
        answer += "\n\nI’m flagging this for human review. The dashboard can create an escalation ticket, but no external system is contacted by this demo."
    return {"reply": answer, "steps": steps, "needs_clarification": needs_clarification, "provider": "local-rules"}


async def build_reply(message: str, context: list[dict[str, str]], labels: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
    result = await try_llm_reply(message, context, history)
    if result is None:
        result = build_local_reply(message, context, labels, history)
    result["context_articles"] = [{"id": x["id"], "title": x["title"]} for x in context]
    result["guardrail_note"] = "Guidance is grounded in the listed demo knowledge articles; verify account-specific facts with a human agent."
    return result


def analyze_conversation(session: dict[str, Any]) -> dict[str, Any]:
    transcript = " ".join(m["content"] for m in session["messages"] if m["role"] == "user")
    labels = classify(transcript)
    facts = [m["content"] for m in session["messages"] if m["role"] == "user"]
    summary = (
        f"{labels['category']} case with {labels['sentiment'].lower()} sentiment and "
        f"{labels['urgency'].lower()} urgency. Customer messages: {len(facts)}. "
        f"Root-cause hypothesis: {labels['intent'].replace('_', ' ')}; confirm details before taking action."
    )
    missing = []
    if labels["category"] in {"Billing & orders", "Order & delivery"}:
        missing.append("Order reference and current order status (verify in the real system)")
    if labels["category"] == "Technical issue":
        missing.append("Exact error text, affected feature, and steps to reproduce")
    if labels["category"] == "Account access":
        missing.append("Account email verified through approved process; never request a password or OTP")
    context = retrieve_context(transcript)
    if context:
        grounding_step = "Use the relevant support guide(s): " + ", ".join(article["title"] for article in context) + "."
    else:
        grounding_step = "No approved article matches yet; ask one clarifying question before suggesting product-specific steps."
    plan = [
        f"Acknowledge the customer’s impact and confirm the {labels['category'].lower()} issue.",
        grounding_step,
    ]
    if missing:
        plan.append("Collect the missing, non-sensitive details: " + "; ".join(missing) + ".")
    else:
        plan.append("Confirm which safe troubleshooting steps the customer has already tried.")
    if labels["urgency"] == "High":
        plan.append("Prioritize human review now and verify any account-specific facts in the authorized system.")
    else:
        plan.append("If the issue persists, create an escalation ticket for a human agent.")
    plan.append("Confirm the outcome only after the relevant system or agent verifies it.")
    return {
        "summary": summary,
        "root_cause_hypothesis": labels["intent"].replace("_", " "),
        "sentiment": labels["sentiment"],
        "urgency": labels["urgency"],
        "severity_score": labels["severity_score"],
        "category": labels["category"],
        "intent": labels["intent"],
        "entities": labels["entities"],
        "missing_information": missing,
        "action_plan": plan,
    }


async def generate_action_plan(session: dict[str, Any]) -> dict[str, Any]:
    analysis = analyze_conversation(session)
    analysis["plan_provider"] = "local-rules"
    if not (AI_API_BASE_URL and AI_API_KEY and AI_MODEL):
        return analysis

    user_messages = [message for message in session["messages"] if message["role"] == "user"]
    context = retrieve_context(" ".join(message["content"] for message in user_messages))
    context_text = "\n\n".join(f"[{article['id']}] {article['title']}: {article['content']}" for article in context)
    transcript = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in session["messages"][-20:]
    )
    prompt = f"""APPROVED KNOWLEDGE CONTEXT:
{context_text or "No matching help articles were found."}

FULL CONVERSATION:
{transcript}

Return JSON with action_plan (an array of up to 8 concise, safe steps) and
root_cause_hypothesis (a short string). Distinguish confirmed facts from hypotheses.
Never invent account/order facts or request secrets. Clearly identify what a human must verify.
All ticket, refund, and discount actions are simulations."""
    endpoint = AI_API_BASE_URL
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODEL,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": PROMPT_TEMPLATES["summary_ticket_generator"]},
                        {"role": "system", "content": PROMPT_TEMPLATES["action_plan"]},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            generated = json.loads(content)
            plan = generated.get("action_plan")
            if isinstance(plan, list) and all(isinstance(step, str) for step in plan):
                clean_plan = [step.strip()[:500] for step in plan[:8] if step.strip()]
                if clean_plan:
                    analysis["action_plan"] = clean_plan
                    analysis["root_cause_hypothesis"] = str(
                        generated.get("root_cause_hypothesis", analysis["root_cause_hypothesis"])
                    )[:300]
                    analysis["plan_provider"] = AI_PROVIDER
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Configured AI action planner failed; using the local plan: %s", exc)
    return analysis


async def broadcast(event: dict[str, Any]):
    stale = []
    for ws in list(manager_sockets):
        try:
            await ws.send_json(event)
        except Exception:
            stale.append(ws)
    for ws in stale:
        manager_sockets.discard(ws)


@app.get("/")
async def root():
    return {"name": APP_NAME, "status": "online", "version": APP_VERSION}


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "configured_provider": AI_PROVIDER,
        "analysis_engine": AI_PROVIDER if (AI_API_BASE_URL and AI_API_KEY and AI_MODEL) else "local-rules",
        "external_ai_configured": bool(AI_API_BASE_URL and AI_API_KEY and AI_MODEL),
        "knowledge_articles": len(KNOWLEDGE_BASE) + len(uploaded_knowledge),
    }


@app.get("/api/knowledge")
async def knowledge():
    return [
        {"id": a["id"], "title": a["title"], "content": a["content"], "custom": a.get("custom", False)}
        for a in [*KNOWLEDGE_BASE, *uploaded_knowledge]
    ]


@app.post("/api/knowledge", status_code=201)
async def add_knowledge_article(payload: KnowledgeArticleRequest):
    content = redact_sensitive(payload.content.strip())
    title = payload.title.strip()
    if len(content) < 40:
        raise HTTPException(
            status_code=422,
            detail="Article content must contain at least 40 non-sensitive characters",
        )
    if len(title) < 3:
        raise HTTPException(status_code=422, detail="Article title must contain at least three characters")
    stop_words = {
        "about", "after", "again", "also", "and", "are", "can", "from", "have",
        "into", "more", "that", "the", "their", "then", "there", "these", "this",
        "through", "with", "your",
    }
    keywords = {
        word
        for word in re.findall(r"[a-z0-9]+", f"{title} {content}".lower())
        if len(word) > 2 and word not in stop_words
    }
    article = {
        "id": f"KB-U-{uuid.uuid4().hex[:7].upper()}",
        "title": title,
        "content": content,
        "keywords": sorted(keywords),
        "custom": True,
    }
    uploaded_knowledge.append(article)
    return {key: article[key] for key in ("id", "title", "content", "custom")}


@app.delete("/api/knowledge/{article_id}")
async def delete_knowledge_article(article_id: str):
    for index, article in enumerate(uploaded_knowledge):
        if article["id"] == article_id:
            del uploaded_knowledge[index]
            return {"deleted": article_id}
    raise HTTPException(status_code=404, detail="Uploaded knowledge article not found")


@app.get("/api/sessions")
async def list_sessions():
    results = []
    for session in sessions.values():
        results.append({**analyze_conversation(session), "session_id": session["id"],
                        "customer_name": session["customer_name"], "updated_at": session["updated_at"],
                        "messages": session["messages"]})
    return sorted(results, key=lambda x: x["updated_at"], reverse=True)


@app.post("/api/sessions/{session_id}/action-plan")
async def create_action_plan(session_id: str):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"session_id": session_id, **await generate_action_plan(session)}


@app.post("/api/chat")
async def chat(payload: ChatMessage):
    sid = payload.session_id
    if sid not in sessions:
        sessions[sid] = {
            "id": sid, "customer_name": "Guest customer",
            "messages": [], "created_at": now_iso(), "updated_at": now_iso()
        }
    session = sessions[sid]
    safe_message = redact_sensitive(payload.message.strip())
    session["messages"].append({"role": "user", "content": safe_message, "timestamp": now_iso()})
    labels = classify(" ".join(m["content"] for m in session["messages"] if m["role"] == "user"))
    context = retrieve_context(" ".join(m["content"] for m in session["messages"] if m["role"] == "user"))
    result = await build_reply(safe_message, context, labels, session["messages"])
    session["messages"].append({"role": "assistant", "content": result["reply"], "timestamp": now_iso()})
    session["updated_at"] = now_iso()
    analytics = analyze_conversation(session)
    response = {"session_id": sid, **result, "analytics": analytics}
    await broadcast({"type": "conversation_updated", "session": {
        **analytics, "session_id": sid, "customer_name": session["customer_name"],
        "updated_at": session["updated_at"], "messages": session["messages"]
    }})
    return response


@app.post("/api/actions")
async def run_action(payload: ActionRequest):
    if payload.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Conversation not found")
    allowed = {"create_ticket", "simulate_refund", "offer_discount"}
    if payload.action not in allowed:
        raise HTTPException(status_code=422, detail="Unsupported demo action")
    session = sessions[payload.session_id]
    if payload.action == "create_ticket":
        ticket = {
            "id": f"NXR-{uuid.uuid4().hex[:7].upper()}",
            "session_id": payload.session_id,
            "subject": str(payload.details.get("subject", "Escalated support issue"))[:200],
            "status": "Open", "created_at": now_iso(),
            "summary": analyze_conversation(session)["summary"]
        }
        tickets.append(ticket)
        result = {"message": f"Demo support ticket {ticket['id']} created for human review.", "ticket": ticket, "simulated": True}
    elif payload.action == "simulate_refund":
        result = {"message": "Refund request simulation recorded. No money was moved and no refund was issued.", "simulated": True}
    else:
        code = "MITRA-" + uuid.uuid4().hex[:6].upper()
        result = {"message": f"Illustrative discount code generated: {code}. It has not been applied to any account.", "code": code, "simulated": True}
    log = {"id": uuid.uuid4().hex[:8], "session_id": payload.session_id, "action": payload.action,
           "result": result["message"], "created_at": now_iso()}
    actions_log.append(log)
    await broadcast({"type": "action_created", "action": log})
    return result


@app.get("/api/tickets")
async def list_tickets():
    return list(reversed(tickets))


@app.get("/api/actions")
async def list_actions():
    return list(reversed(actions_log))


@app.websocket("/ws/admin")
async def admin_socket(websocket: WebSocket):
    await websocket.accept()
    manager_sockets.add(websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "Mitra live monitoring connected"})
        while True:
            text = await websocket.receive_text()
            if text == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager_sockets.discard(websocket)
    except Exception:
        manager_sockets.discard(websocket)
        logger.exception("Admin WebSocket ended")
