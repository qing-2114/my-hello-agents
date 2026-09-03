"""Offline tests for deterministic mock ticket availability and booking."""

from __future__ import annotations

import json
import unittest

from agent import run_agent
from tools import (
    book_ticket,
    check_ticket_availability,
    find_ticket_alternatives,
    reset_mock_ticket_inventory,
)


class TicketToolTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_mock_ticket_inventory()

    def test_sold_out_attraction_returns_structured_status(self) -> None:
        result = json.loads(
            check_ticket_availability("杭州", "灵隐寺", "2026-09-10", quantity=1)
        )
        self.assertEqual(result["status"], "SOLD_OUT")
        self.assertEqual(result["remaining"], 0)

    def test_available_attraction_can_be_booked_after_confirmation(self) -> None:
        result = json.loads(
            book_ticket(
                "杭州",
                "西溪国家湿地公园",
                "2026-09-10",
                quantity=2,
                confirmed_by_user=True,
            )
        )
        self.assertEqual(result["status"], "BOOKED")
        self.assertEqual(result["remaining"], 4)
        self.assertTrue(result["order_id"].startswith("MOCK-"))

    def test_booking_requires_explicit_confirmation(self) -> None:
        result = json.loads(
            book_ticket("杭州", "杭州宋城", "2026-09-10", quantity=1)
        )
        self.assertEqual(result["status"], "CONFIRMATION_REQUIRED")

    def test_alternatives_exclude_sold_out_and_requested_attraction(self) -> None:
        result = json.loads(
            find_ticket_alternatives(
                "杭州",
                "2026-09-10",
                quantity=2,
                exclude=["灵隐寺", "杭州宋城"],
            )
        )
        names = {item["attraction"] for item in result["alternatives"]}
        self.assertNotIn("灵隐寺", names)
        self.assertNotIn("杭州宋城", names)
        self.assertIn("西溪国家湿地公园", names)

    def test_agent_loop_recovers_from_sold_out_booking(self) -> None:
        class SoldOutFlowLLM:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def generate(self, prompt: str, system_prompt: str) -> str:
                self.calls.append(prompt)
                if len(self.calls) == 1:
                    return (
                        "Thought: 用户已确认，尝试模拟购票。\n"
                        'Action: book_ticket(city="杭州", attraction="灵隐寺", '
                        'visit_date="2026-09-10", quantity=1, confirmed_by_user=True)'
                    )
                if len(self.calls) == 2:
                    self.sold_out_observation = prompt
                    return (
                        "Thought: 已售罄，查询仍有票的备选。\n"
                        'Action: find_ticket_alternatives(city="杭州", '
                        'visit_date="2026-09-10", quantity=1, exclude=["灵隐寺"])'
                    )
                self.alternative_observation = prompt
                return (
                    "Thought: 展示备选并等待用户重新确认。\n"
                    "Action: Finish[灵隐寺已售罄。西溪国家湿地公园还有票，"
                    "是否改为预订该景点？]"
                )

        llm = SoldOutFlowLLM()
        answer = run_agent(
            "我确认购买2026-09-10的1张灵隐寺门票",
            llm=llm,
            trace_memory=False,
        )
        self.assertIn("灵隐寺已售罄", answer)
        self.assertIn('"status": "SOLD_OUT"', llm.sold_out_observation)
        self.assertIn('"status": "ALTERNATIVES_FOUND"', llm.alternative_observation)
        self.assertEqual(len(llm.calls), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
