
import os
import sys
import unittest
import asyncio
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import (
    PROMPT_TEMPLATES,
    add_knowledge_article,
    classify,
    generate_action_plan,
    health,
    make_llm_messages,
    redact_sensitive,
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
        self.assertEqual(result["provider"], "featherless")

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
