# Hackathon Submission Checklist

## Challenge feature mapping

- [x] Dual interface: customer support chat and admin monitoring
- [x] Adaptive empathetic tone based on detected sentiment
- [x] Clarifying questions and step-by-step troubleshooting
- [x] Knowledge base context retrieval with article IDs/titles
- [x] Live admin feed using WebSockets
- [x] Conversation summaries and root-cause hypotheses
- [x] Sentiment, intent, urgency, category, entities, severity score
- [x] Suggested action plan and missing-information list
- [x] Simulated escalation ticket, refund request, and discount code
- [x] Separated prompt templates for persona, classifier, summary, action plan
- [x] Basic sensitive-data redaction and explicit simulation disclaimers
- [x] Optional provider-neutral OpenAI-compatible chat-completions integration
- [x] Local fallback mode when no API key is configured
- [x] Unit tests for core analysis and retrieval

## Before submission

- [ ] Run backend tests: `python -m unittest discover -s tests -v`
- [ ] Run frontend production build: `npm run build`
- [ ] Test both chat and admin views in two browser tabs
- [ ] If using an external AI endpoint, configure secrets only in `backend/.env`
- [ ] Do not include API keys or real customer data in the ZIP/repository
- [ ] Record a short demo showing a complex issue, clarification, article grounding, live admin classification, action plan, and simulated escalation
- [ ] Review all generated responses manually; demo analysis is not a substitute for human judgment

## Known prototype limits

- Conversations and action records use in-memory storage and reset on restart.
- Knowledge articles are embedded demo text, not an uploaded-document ingestion pipeline.
- The local classifier is rule-based; the optional LLM is used for the conversational reply only.
- Refund/discount actions are simulations; no external commerce/helpdesk system is connected.
- Authentication, persistent storage, production-grade redaction, and rate limiting are not included.
