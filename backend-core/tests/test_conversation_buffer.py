"""Tests for C10B.5: Bounded conversation history buffer."""

from __future__ import annotations

import pytest

from app.services.agencyclaw.conversation_buffer import (
    Exchange,
    MAX_EXCHANGES,
    MAX_TOKENS,
    append_exchange,
    compact_exchanges,
    estimate_tokens,
    exchanges_to_chat_messages,
)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_basic_heuristic(self):
        # "hello world" = 11 chars → 11 // 4 = 2
        assert estimate_tokens("hello world") == 2

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string_minimum(self):
        # "hi" = 2 chars → 2 // 4 = 0 → clamped to 1
        assert estimate_tokens("hi") == 1

    def test_longer_string(self):
        text = "a" * 400
        assert estimate_tokens(text) == 100


# ---------------------------------------------------------------------------
# append_exchange
# ---------------------------------------------------------------------------


class TestAppendExchange:
    def test_append_to_empty(self):
        result = append_exchange([], "hello", "hi there")
        assert len(result) == 1
        assert result[0] == {"user": "hello", "assistant": "hi there"}

    def test_append_preserves_order(self):
        existing = [Exchange(user="first", assistant="response1")]
        result = append_exchange(existing, "second", "response2")
        assert len(result) == 2
        assert result[0]["user"] == "first"
        assert result[1]["user"] == "second"

    def test_append_does_not_mutate_original(self):
        existing = [Exchange(user="first", assistant="response1")]
        result = append_exchange(existing, "second", "response2")
        assert len(existing) == 1  # original unchanged
        assert len(result) == 2


# ---------------------------------------------------------------------------
# compact_exchanges
# ---------------------------------------------------------------------------


class TestCompactExchanges:
    def test_under_limits_unchanged(self):
        exchanges = [Exchange(user="hi", assistant="hello")]
        result = compact_exchanges(exchanges)
        assert result == exchanges

    def test_empty_buffer(self):
        assert compact_exchanges([]) == []

    def test_enforce_max_exchanges(self):
        exchanges = [
            Exchange(user=f"msg{i}", assistant=f"resp{i}")
            for i in range(8)
        ]
        result = compact_exchanges(exchanges, max_exchanges=5, max_tokens=999_999)
        assert len(result) == 5
        # Should keep the 5 most recent (oldest dropped)
        assert result[0]["user"] == "msg3"
        assert result[4]["user"] == "msg7"

    def test_enforce_max_tokens(self):
        # Each exchange ≈ 500 chars → 125 tokens per exchange,
        # so 3 exchanges = 375 tokens > threshold if we set max_tokens=300
        big = "x" * 500
        exchanges = [
            Exchange(user=big, assistant=big)
            for _ in range(3)
        ]
        result = compact_exchanges(exchanges, max_exchanges=99, max_tokens=300)
        assert len(result) < 3
        # With 250 tokens per exchange and 300 cap, only 1 should fit
        assert len(result) == 1

    def test_evicts_oldest_first(self):
        exchanges = [
            Exchange(user=f"msg{i}", assistant=f"resp{i}")
            for i in range(7)
        ]
        result = compact_exchanges(exchanges, max_exchanges=5)
        # Oldest two (msg0, msg1) should be evicted
        assert result[0]["user"] == "msg2"

    def test_both_limits_enforced(self):
        # 6 exchanges (over count) with moderate tokens
        exchanges = [
            Exchange(user=f"message number {i} " * 10, assistant=f"reply {i} " * 10)
            for i in range(6)
        ]
        result = compact_exchanges(exchanges, max_exchanges=5, max_tokens=MAX_TOKENS)
        assert len(result) <= 5
        # Verify token budget
        total = sum(
            estimate_tokens(ex["user"]) + estimate_tokens(ex["assistant"])
            for ex in result
        )
        assert total <= MAX_TOKENS

    def test_default_limits_match_constants(self):
        # Verify the defaults are 5 exchanges and 1500 tokens
        assert MAX_EXCHANGES == 5
        assert MAX_TOKENS == 1500


# ---------------------------------------------------------------------------
# exchanges_to_chat_messages
# ---------------------------------------------------------------------------


class TestExchangesToChatMessages:
    def test_converts_to_alternating_messages(self):
        exchanges = [
            Exchange(user="hello", assistant="hi"),
            Exchange(user="how are you", assistant="good"),
        ]
        result = exchanges_to_chat_messages(exchanges)
        assert len(result) == 4
        assert result[0] == {"role": "user", "content": "hello"}
        assert result[1] == {"role": "assistant", "content": "hi"}
        assert result[2] == {"role": "user", "content": "how are you"}
        assert result[3] == {"role": "assistant", "content": "good"}

    def test_empty_exchanges(self):
        assert exchanges_to_chat_messages([]) == []
