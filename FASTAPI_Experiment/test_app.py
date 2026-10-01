"""Offline HTTP tests for the FastAPI travel-Agent boundary."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app import create_app


class StubLLM:
    """Deterministic model substitute; not a real API validation."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return "Thought: 测试直接完成。\nAction: Finish[这是离线测试答复]"


class FastAPIExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.llm = StubLLM()
        self.client = TestClient(create_app(llm=self.llm))

    def test_health_and_session_creation(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active_sessions"], 0)

        response = self.client.post("/sessions", json={"user_id": "student-1"})
        self.assertEqual(response.status_code, 201)
        self.session_id = response.json()["session_id"]

        summary = self.client.get(f"/sessions/{self.session_id}")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["user_id"], "student-1")
        self.assertEqual(summary.json()["message_count"], 0)

    def test_turn_reuses_existing_agent_and_returns_json(self) -> None:
        created = self.client.post("/sessions", json={}).json()
        session_id = created["session_id"]

        response = self.client.post(
            f"/sessions/{session_id}/turns",
            json={"message": "查询杭州天气"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "这是离线测试答复")
        self.assertEqual(response.json()["feedback_type"], "none")
        self.assertEqual(len(self.llm.calls), 1)

        summary = self.client.get(f"/sessions/{session_id}").json()
        self.assertEqual(summary["message_count"], 2)
        self.assertTrue(summary["has_last_recommendation"])

    def test_validation_and_session_errors_are_explicit(self) -> None:
        created = self.client.post("/sessions", json={}).json()
        session_id = created["session_id"]

        empty_message = self.client.post(
            f"/sessions/{session_id}/turns",
            json={"message": ""},
        )
        self.assertEqual(empty_message.status_code, 422)

        missing = self.client.post(
            "/sessions/not-found/turns",
            json={"message": "你好"},
        )
        self.assertEqual(missing.status_code, 404)

        invalid_feedback = self.client.post(
            f"/sessions/{session_id}/turns",
            json={"message": "你好", "feedback_type": "maybe"},
        )
        self.assertEqual(invalid_feedback.status_code, 422)

    def test_reject_before_first_recommendation_returns_bad_request(self) -> None:
        session_id = self.client.post("/sessions", json={}).json()["session_id"]
        response = self.client.post(
            f"/sessions/{session_id}/turns",
            json={"message": "我不喜欢这个", "feedback_type": "reject"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

