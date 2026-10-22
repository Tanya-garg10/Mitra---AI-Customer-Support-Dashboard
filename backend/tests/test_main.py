
import os
import sys
import unittest
import asyncio
import httpx
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import (
    PROMPT_TEMPLATES,
    add_knowledge_article,
    app,
    classify,
    generate_action_plan,
    health,
    make_llm_messages,
    parse_json_object,
    redact_sensitive,
    retrieve_chat_context,
    retrieve_context,
    try_llm_reply,
    uploaded_knowledge,
    KnowledgeArticleRequest,
)


class NEXORATests(unittest.TestCase):
    def test_high_urgency_and_frustration(self):
        result = classify("I am furious, urgent, and locked out of my account")
        self.assertEqual(result["urgency"], "High")
        self.assertEqual(result["sentiment"], "Frustrated")
        self.assertGreaterEqual(result["severity_score"], 80)

    def test_technical_queue_issue_is_classified(self):
        result = classify("The warehouse sync queue is stuck")
        self.assertEqual(result["category"], "Technical issue")
        self.assertEqual(result["urgency"], "Medium")
        self.assertIn("sync", result["entities"])

    def test_knowledge_retrieval(self):
        result = retrieve_context("password reset link expired")
        self.assertTrue(result)
        self.assertEqual(result[0]["id"], "KB-001")

    def test_chat_context_prefers_current_question_and_uses_history_for_followups(self):
        history = [
            {"role": "user", "content": "My password reset link expired."},
            {"role": "assistant", "content": "Request a new password reset link."},
        ]
        current_issue = retrieve_chat_context("The CSV export fails.", history)
        self.assertEqual([article["id"] for article in current_issue], ["KB-004"])

        follow_up = retrieve_chat_context("It is still broken.", history + [
            {"role": "user", "content": "The CSV export fails."},
        ])
        self.assertEqual([article["id"] for article in follow_up], ["KB-004"])

    def test_json_parser_accepts_markdown_fenced_object(self):
        parsed = parse_json_object('```json\n{"reply":"Try again."}\n```')
        self.assertEqual(parsed, {"reply": "Try again."})

    def test_sensitive_text_redaction(self):
        result = redact_sensitive("Email me at test@example.com; password: abc123")
        self.assertNotIn("test@example.com", result)
        self.assertIn("[REDACTED]", result)

    def test_prompt_strategy_separated(self):
        self.assertIn("chatbot_persona", PROMPT_TEMPLATES)
        self.assertIn("sentiment_classifier", PROMPT_TEMPLATES)
        self.assertIn("summary_ticket_generator", PROMPT_TEMPLATES)
        self.assertIn("action_plan", PROMPT_TEMPLATES)
        self.assertIn("customer’s technical fluency", PROMPT_TEMPLATES["chatbot_persona"])

    def test_provider_prompt_has_grounding(self):
        messages = make_llm_messages("my order is late", retrieve_context("order delivery"), [])
        combined = " ".join(m["content"] for m in messages)
        self.assertIn("KNOWLEDGE-BASE GROUNDING", combined)
        self.assertIn("Return only JSON", combined)

    def test_featherless_chat_completion_configuration(self):
        captured = {}

        class MockResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": '{"reply":"I can help with that.","steps":[],"needs_clarification":false}'
                        }
                    }]
                }

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, endpoint, **kwargs):
                captured["endpoint"] = endpoint
                captured["headers"] = kwargs["headers"]
                captured["model"] = kwargs["json"]["model"]
                captured["json_mode"] = "response_format" in kwargs["json"]
                return MockResponse()

        with (
            patch("app.main.AI_API_BASE_URL", "https://api.featherless.ai/v1"),
            patch("app.main.AI_API_KEY", "test-key"),
            patch("app.main.AI_MODEL", "test/model"),
            patch("app.main.AI_PROVIDER", "featherless"),
            patch("app.main.httpx.AsyncClient", return_value=MockAsyncClient()),
        ):
            result = asyncio.run(try_llm_reply("Need help", [], []))

        self.assertEqual(captured["endpoint"], "https://api.featherless.ai/v1/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["model"], "test/model")
        self.assertFalse(captured["json_mode"])
        self.assertEqual(result["provider"], "featherless")

    def test_featherless_plain_text_response_is_used(self):
        class MockResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "Try exporting again after clearing the filters."}}]}

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *_args, **_kwargs):
                return MockResponse()

        with (
            patch("app.main.AI_API_BASE_URL", "https://api.featherless.ai/v1"),
            patch("app.main.AI_API_KEY", "test-key"),
            patch("app.main.AI_MODEL", "test/model"),
            patch("app.main.AI_PROVIDER", "featherless"),
            patch("app.main.httpx.AsyncClient", return_value=MockAsyncClient()),
        ):
            result = asyncio.run(try_llm_reply("Export fails", [], []))

        self.assertEqual(
            result["reply"],
            "Try exporting again after clearing the filters.",
        )
        self.assertEqual(result["provider"], "featherless")

    def test_featherless_error_is_reported_in_health(self):
        class MockResponse:
            def raise_for_status(self):
                request = httpx.Request("POST", "https://api.featherless.ai/v1/chat/completions")
                response = httpx.Response(401, request=request)
                raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *_args, **_kwargs):
                return MockResponse()

        with (
            patch("app.main.AI_API_BASE_URL", "https://api.featherless.ai/v1"),
            patch("app.main.AI_API_KEY", "test-key"),
            patch("app.main.AI_MODEL", "test/model"),
            patch("app.main.AI_PROVIDER", "featherless"),
            patch("app.main.AI_LAST_ERROR", None),
            patch("app.main.httpx.AsyncClient", return_value=MockAsyncClient()),
        ):
            result = asyncio.run(try_llm_reply("Need help", [], []))
            health_result = asyncio.run(health())

        self.assertIsNone(result)
        self.assertEqual(health_result["external_ai_last_error"], "Featherless returned HTTP 401")

    def test_health_reports_featherless_when_configured(self):
        with (
            patch("app.main.AI_API_BASE_URL", "https://api.featherless.ai/v1"),
            patch("app.main.AI_API_KEY", "test-key"),
            patch("app.main.AI_MODEL", "test/model"),
            patch("app.main.AI_PROVIDER", "featherless"),
        ):
            result = asyncio.run(health())

        self.assertEqual(result["analysis_engine"], "featherless")
        self.assertTrue(result["external_ai_configured"])

    def test_health_reports_missing_featherless_credentials(self):
        with (
            patch("app.main.AI_API_BASE_URL", "https://api.featherless.ai/v1"),
            patch("app.main.AI_API_KEY", ""),
            patch("app.main.AI_MODEL", "test/model"),
            patch("app.main.AI_PROVIDER", "featherless"),
        ):
            result = asyncio.run(health())

        self.assertEqual(result["configured_provider"], "featherless")
        self.assertEqual(result["analysis_engine"], "local-rules")
        self.assertFalse(result["external_ai_configured"])

    def test_deployed_vercel_origin_passes_cors_preflight(self):
        async def send_preflight():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                responses = []
                for origin in (
                    "https://mitra-ai-customer-support-dashboard.vercel.app",
                    "https://mitra-ai-customer-support-dashboard-git-main-tanya-382b.vercel.app",
                ):
                    responses.append(await client.options(
                        "/api/chat",
                        headers={
                            "Origin": origin,
                            "Access-Control-Request-Method": "POST",
                            "Access-Control-Request-Headers": "content-type",
                        },
                    ))
                return responses

        responses = asyncio.run(send_preflight())
        for response in responses:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers["access-control-allow-origin"],
                response.request.headers["origin"],
            )

    def test_unrelated_vercel_origin_is_not_allowed(self):
        async def send_preflight():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.options(
                    "/api/chat",
                    headers={
                        "Origin": "https://some-other-project.vercel.app",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )

        response = asyncio.run(send_preflight())
        self.assertEqual(response.status_code, 400)

    def test_uploaded_knowledge_is_retrievable(self):
        article = {
            "id": "KB-U-TEST",
            "title": "Smart thermostat setup",
            "content": "Check thermostat pairing and reconnect the home hub.",
            "keywords": ["thermostat", "pairing", "home"],
            "custom": True,
        }
        uploaded_knowledge.append(article)
        try:
            result = retrieve_context("thermostat pairing issue")
            self.assertEqual(result[0]["id"], article["id"])
        finally:
            uploaded_knowledge.remove(article)

    def test_uploaded_articles_redact_sensitive_content(self):
        request = KnowledgeArticleRequest(
            title="Support guide",
            content="Use this approved support process and never expose password: sample-secret to customers.",
        )
        article = asyncio.run(add_knowledge_article(request))
        try:
            self.assertIn("[REDACTED]", article["content"])
            self.assertNotIn("sample-secret", article["content"])
        finally:
            uploaded_knowledge[:] = [item for item in uploaded_knowledge if item["id"] != article["id"]]

    def test_action_plan_uses_full_conversation_context(self):
        session = {
            "messages": [
                {"role": "user", "content": "I am worried about my billing."},
                {"role": "assistant", "content": "What happened with the charge?"},
                {"role": "user", "content": "I was charged twice for the same order."},
            ]
        }
        with patch("app.main.AI_API_BASE_URL", ""), patch("app.main.AI_API_KEY", ""), patch("app.main.AI_MODEL", ""):
            result = asyncio.run(generate_action_plan(session))
        self.assertEqual(result["category"], "Billing & orders")
        self.assertEqual(result["urgency"], "High")
        self.assertEqual(result["plan_provider"], "local-rules")
        self.assertTrue(result["action_plan"])
        self.assertTrue(any("Refund eligibility" in step for step in result["action_plan"]))
        self.assertTrue(any("Prioritize human review" in step for step in result["action_plan"]))


if __name__ == "__main__":
    unittest.main()
