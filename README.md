# Mitra | Customer Care Studio

Mitra is a calmer, context-aware customer care studio that turns complex conversations into grounded answers and clear next steps. The full-stack workspace pairs an empathetic customer chat with a live agent dashboard, support guide ingestion, structured conversation analytics, and safe simulated actions.

## Included features

- Dual interface: end-user support chat + admin monitoring dashboard
- Adaptive empathetic response style based on detected sentiment
- Clarifying questions and safe troubleshooting steps
- Demo knowledge base with context retrieval and article references
- Upload approved `.txt` and `.md` support guides (up to 20 KB) for live context retrieval
- Structured sentiment, intent, category, key entities, urgency, and severity score
- Conversation summaries, missing-information list, and suggested action plan
- One-click action-plan generation from the full conversation, with an optional configured LLM and local fallback
- WebSocket updates from the chat flow to the admin monitor
- Simulated escalation ticket, refund request, and discount-code actions
- Dedicated escalation ticket queue linked back to the source conversation
- Separated prompt strategy templates: chatbot persona, classifier, summary/ticket generator, and action planner
- Basic redaction for email-like strings, long payment-card-like numbers, and password/OTP patterns
- Responsive React + Vite + Tailwind CSS interface with Lucide icons
- FastAPI endpoints and interactive API docs

## Tech stack

- Frontend: React, Vite, Tailwind CSS, Lucide React
- Backend: FastAPI, Pydantic, WebSockets
- Default analysis: deterministic local rules; optional OpenAI-compatible LLM endpoint via backend environment variables

## Project structure

```text
Mitra_Customer_Care_Studio/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css
│   │   ├── styles.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── .gitignore
└── README.md
```

## Run on Windows 10/11

### 1. Backend

Open PowerShell in the extracted project folder:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# Add your Featherless API key to AI_API_KEY in backend/.env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation, run the venv executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend

Open a second terminal at the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally <http://localhost:5173>.

### 3. Verify

- Health: <http://127.0.0.1:8000/api/health>
- Knowledge articles: <http://127.0.0.1:8000/api/knowledge>
- Interactive backend docs: <http://127.0.0.1:8000/docs>
- Admin WebSocket: `ws://127.0.0.1:8000/ws/admin`

Start a chat in **Support chat**. The conversation should then appear in **Live monitor** and the overview feed.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service metadata |
| GET | `/api/health` | Health check |
| GET | `/api/knowledge` | Built-in and uploaded knowledge articles |
| POST | `/api/knowledge` | Add a redacted text/Markdown knowledge article |
| DELETE | `/api/knowledge/{article_id}` | Remove an uploaded article |
| GET | `/api/sessions` | Conversation analytics and transcript |
| POST | `/api/sessions/{session_id}/action-plan` | Generate a suggested plan from the full conversation |
| POST | `/api/chat` | Add a user message and generate a grounded reply |
| POST | `/api/actions` | Simulate a ticket, refund request, or discount |
| GET | `/api/tickets` | List demo escalation tickets |
| GET | `/api/actions` | List simulated actions |
| WebSocket | `/ws/admin` | Live conversation/action events |

## Prompt engineering strategy

The backend exposes four separated prompt templates to demonstrate the intended architecture:

1. **Chatbot Persona Prompt** — empathy, clarification, knowledge grounding, safe step-by-step guidance.
2. **Sentiment & Intent Classifier Prompt** — structured labels, urgency, entities, and uncertainty handling.
3. **Summary & Ticket Generator Prompt** — root-cause hypothesis, confirmed facts, missing information, and escalation reason.
4. **Action Plan Prompt** — safe next steps, prerequisites, and human verification.

This ZIP works out of the box with a deterministic local engine. To enable Featherless AI, add your Featherless API key to `AI_API_KEY` in `backend/.env`. The example configuration uses `https://api.featherless.ai/v1` and `meta-llama/Meta-Llama-3.1-8B-Instruct`; select a model available to your Featherless account by changing `AI_MODEL` if needed. The key is only read by the backend and must never be added to frontend code. Chat replies use the persona, classifier, and grounding instructions. Suggested plans use the separated summary and action-plan prompts when Featherless is configured, with a local context-aware plan as fallback. Review recommendations and verify account-specific facts before taking real-world action.

## Privacy and safety notes

- The demo redacts common email strings, long card-like number sequences, and simple password/OTP patterns from user text before storing the chat message.
- Redaction is a basic prototype safeguard, not comprehensive DLP. Do not enter real sensitive customer data.
- Knowledge articles are simulated examples. Uploaded TXT/Markdown guidance is redacted and stored in memory for retrieval; account-specific, payment, refund, and order details must be verified by an authorized human/system.
- Refunds and discount codes are simulations only. No money is moved, no code is applied, and no external system is contacted.
- The demo uses in-memory storage. Conversations and uploaded knowledge reset when the backend restarts.
- No authentication, authorization, persistent database, rate limiting, or production-grade audit logging is included.

## Automated tests

From the `backend` folder, install dependencies and run:

```powershell
python -m unittest discover -s tests -v
```

## Suggested next steps

- Add an actual LLM provider adapter and run prompt-injection / hallucination evaluations.
- Add authenticated agent roles and durable database storage.
- Ingest approved PDFs/FAQs and evaluate retrieval quality.
- Expand evaluation coverage, audit logging, rate limits, deployment configuration, and production-grade privacy controls.
