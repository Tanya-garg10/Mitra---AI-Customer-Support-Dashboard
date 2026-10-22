# Mitra — AI Customer Support Dashboard

Mitra is a customer-support demo that pairs an empathetic, knowledge-grounded chat assistant with a live agent dashboard. It classifies conversation signals, summarizes cases, and suggests safe next steps for support teams.

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
- **AI:** Featherless AI through its OpenAI-compatible chat-completions API (optional)

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
