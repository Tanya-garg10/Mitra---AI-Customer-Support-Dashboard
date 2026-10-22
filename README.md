# Mitra — AI Customer Support Dashboard

Mitra is an AI-powered customer support and troubleshooting dashboard that turns complex customer conversations into grounded answers and actionable agent insights. Customers get empathetic, step-by-step help informed by approved support guides, while agents can monitor live conversations, assess sentiment and urgency, review case summaries, and prepare safe escalations.

**Project description:** Mitra combines a context-aware AI support assistant with a real-time agent workspace. It uses knowledge-grounded chat, conversation classification, severity scoring, live monitoring, and suggested resolution plans to help support teams resolve issues faster—while keeping refunds and other operational actions safely simulated.

> **Demo status:** Chats, tickets, uploaded guides, and actions are stored in memory and reset when the backend restarts. Refunds and discounts are simulations only.

## Features

- Customer-facing support chat and live agent monitoring dashboard
- Knowledge-grounded troubleshooting using built-in support articles and uploaded `.txt`/`.md` guides
- Conversation classification for sentiment, intent, category, urgency, key entities, and severity
- Case summaries, missing-information indicators, and suggested action plans
- Optional Featherless AI integration for chat responses and generated action plans; local rules are used when no API key is configured
- Live dashboard updates over WebSockets
- Demo ticket queue and simulated ticket, refund-request, and discount actions
- Basic redaction of common email, payment-card-like, password, and OTP patterns
- Responsive React interface

## Tech stack

- **Frontend:** React, Vite, CSS, Lucide React
- **Backend:** Python, FastAPI, Pydantic, HTTPX, WebSockets
- **AI inference:** Featherless AI API using the OpenAI-compatible chat-completions interface and a configurable hosted language model (default: `meta-llama/Meta-Llama-3.1-8B-Instruct`)
- **Prompt engineering:** Separate assistant-persona, safety and knowledge-grounding, sentiment/intent classification, case-summary, and action-planning instructions

## AI tools and prompt-engineering approach

- **Featherless AI API** sends grounded chat and action-plan requests to the configured hosted model. The API key remains on the backend.
- **FastAPI and HTTPX** connect the dashboard backend to the model API; no LangChain or frontend AI SDK is required.
- **Local rules fallback** keeps the demo usable when the API is not configured. If a configured Featherless request fails, the API health response and chat notice report that the response fell back to local rules.
- **Persona prompt:** guides Mitra to be empathetic, concise, and clear, and to ask a clarifying question when needed.
- **Grounding prompt:** supplies retrieved approved support articles and recent conversation context; instructs the model not to invent account, order, delivery, refund, or policy facts.
- **Classifier prompt:** asks for evidence-based sentiment, intent, urgency, category, and entities for the agent dashboard.
- **Summary and action-plan prompts:** distinguish confirmed information from hypotheses, surface missing details, and recommend safe next steps with human verification.
- **Safety instructions:** prohibit asking for passwords, one-time codes, or full payment-card data, and state that demo refunds, tickets, and discounts are simulations.

The prompts are maintained in the backend and are not exposed through a public prompt-inspection endpoint.

## Requirements

- Python 3.10 or later
- Node.js 18 or later and npm
- Optional: a Featherless API key to enable external AI responses

## Run locally

Clone the repository and open two PowerShell terminals at the project root.

### 1. Start the backend

In the first terminal:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend starts in local-rules mode until you add a Featherless API key. To enable Featherless, stop the backend, open `backend/.env`, and set `AI_API_KEY` to your key. Restart the backend after changing environment settings.

If PowerShell blocks virtual-environment activation, use its Python executable directly:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then add your key to `backend/.env` and restart Uvicorn to enable Featherless.

### 2. Start the frontend

In the second terminal, from the project root:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>.

## Featherless configuration

The example configuration in `backend/.env.example` sets:

```dotenv
AI_PROVIDER=featherless
AI_API_BASE_URL=https://api.featherless.ai/v1
AI_API_KEY=
AI_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

Copy this file to `backend/.env` and add your API key to `AI_API_KEY`. Choose a model available to your Featherless account by changing `AI_MODEL` if needed. Keep the key in the backend environment only; never put it in frontend code or commit the `.env` file. The `.env` file is ignored by Git.

Check the backend health endpoint at <http://127.0.0.1:8000/api/health>. It reports the configured provider and whether external AI credentials are present. If Featherless is unavailable or not configured, the application falls back to its local rules.

## Deployment environment variables

For the deployed Vercel frontend, configure these variables in the Vercel project settings, replacing the hostname if your Render service uses another URL:

```dotenv
VITE_API_BASE=https://mitra-ai-customer-support-dashboard.onrender.com
VITE_WS_URL=wss://mitra-ai-customer-support-dashboard.onrender.com/ws/admin
```

Do not add a trailing slash to `VITE_API_BASE`. The frontend also removes trailing slashes automatically to avoid malformed `//api/...` requests.

In Render, set `FRONTEND_ORIGINS` to include the exact deployed Vercel origin:

```dotenv
FRONTEND_ORIGINS=https://mitra-ai-customer-support-dashboard.vercel.app
```

The project production domain and its Vercel preview deployment URLs are allowed by the backend. Add any custom Vercel domain you use to `FRONTEND_ORIGINS` as well. Redeploy the frontend after changing Vercel variables and restart/redeploy the backend after changing Render variables.

## API

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service name and status |
| GET | `/api/health` | Health and AI configuration status |
| GET | `/api/knowledge` | List built-in and uploaded support articles |
| POST | `/api/knowledge` | Add a support article |
| DELETE | `/api/knowledge/{article_id}` | Remove an uploaded article |
| GET | `/api/sessions` | List conversation summaries and transcripts |
| POST | `/api/chat` | Send a chat message and receive a support response |
| POST | `/api/sessions/{session_id}/action-plan` | Generate or refresh an action plan |
| POST | `/api/actions` | Simulate a ticket, refund request, or discount |
| GET | `/api/tickets` | List demo tickets |
| GET | `/api/actions` | List simulated actions |
| WebSocket | `/ws/admin` | Receive live dashboard events |

Prompt templates are maintained inside the backend and are not exposed through a public prompt-inspection endpoint.

## Run backend tests

From the `backend` directory with its virtual environment activated:

```powershell
python -m unittest discover -s tests -v
```

## Privacy and limitations

- This is a prototype, not a production customer-support system. Do not enter real customer secrets or sensitive payment data.
- Redaction uses basic patterns and is not comprehensive data-loss prevention.
- Conversations, tickets, actions, and uploaded knowledge are held in memory and are lost when the backend restarts.
- No authentication, authorization, persistent database, rate limiting, or production audit logging is included.
- Demo actions do not move money, apply discounts, or contact external systems. A human must verify account-specific facts and any suggested action.

## Project structure

```text
├── backend/
│   ├── app/
│   │   └── main.py
│   ├── tests/
│   │   └── test_main.py
│   ├── .env.example
│   └── requirements.txt
├── docs/
│   └── HACKATHON_CHECKLIST.md
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── theme.css
│   │   └── ...
│   ├── index.html
│   └── package.json
└── README.md
```
