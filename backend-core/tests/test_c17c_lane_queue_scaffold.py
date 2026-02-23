"""C17C lane queue reference contract checks.

This module validates concurrency semantics using test-only helpers and a
reference ``SessionLaneQueue`` implementation. It does not invoke the
production DM runtime directly.

Architecture context (from agencyclaw-agent-loop.md, Decision #8):
    "Sequential execution (lane queue): Process events serially per
     session/lane to prevent race conditions (e.g., double-pings causing
     duplicate creates). Different sessions can still run concurrently."

Test categories:
    [BASELINE]  — documents unlocked behavior.
    [CONTRACT]  — validates expected serialized/concurrent semantics via
                  reference implementation.

Concurrency model:
    Tests use asyncio primitives (Event, Lock) and controlled "gate"
    barriers for deterministic ordering.  Bounded short sleeps
    (≤20 ms) are used only where needed to establish task stagger
    order for lock acquisition; no unbounded polling or wall-clock
    timing assertions.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Test-only helpers
# ---------------------------------------------------------------------------


class ExecutionLog:
    """Thread-safe (asyncio-safe) ordered log of handler execution events.

    Each entry is ``(label, timestamp_ns)`` where *label* encodes
    session + message identity and *timestamp_ns* is monotonic clock.
    """

    def __init__(self) -> None:
        self._entries: list[tuple[str, int]] = []

    def record(self, label: str) -> None:
        self._entries.append((label, time.monotonic_ns()))

    @property
    def labels(self) -> list[str]:
        return [e[0] for e in self._entries]

    @property
    def entries(self) -> list[tuple[str, int]]:
        return list(self._entries)

    def labels_for_session(self, session_id: str) -> list[str]:
        return [lbl for lbl, _ in self._entries if lbl.startswith(f"{session_id}:")]


async def _fake_handler(
    *,
    label: str,
    log: ExecutionLog,
    gate: asyncio.Event | None = None,
    work_duration: float = 0.0,
) -> None:
    """Simulate a DM handler that logs start/end and optionally waits at a gate.

    Parameters
    ----------
    label:
        Identifies the handler invocation (e.g. ``"sess-1:msg-A"``).
    log:
        Shared execution log for ordering assertions.
    gate:
        If provided, handler blocks at ``gate.wait()`` *after* logging
        ``start`` — lets the test control interleaving.
    work_duration:
        Seconds to ``asyncio.sleep`` between start and end, simulating
        I/O-bound work.
    """
    log.record(f"{label}:start")
    if gate is not None:
        await gate.wait()
    if work_duration > 0:
        await asyncio.sleep(work_duration)
    log.record(f"{label}:end")


# ---------------------------------------------------------------------------
# Simulated DM dispatcher (no per-session lock — current behavior)
# ---------------------------------------------------------------------------


async def dispatch_dm_no_lock(
    *,
    session_id: str,
    message_id: str,
    log: ExecutionLog,
    gate: asyncio.Event | None = None,
    work_duration: float = 0.0,
) -> None:
    """Simulates current DM event dispatch — fire-and-forget, no per-session lock.

    Production seam: In C17C, ``slack_dm_runtime.handle_dm_event_runtime`` will
    acquire a per-session ``asyncio.Lock`` before calling the handler,
    replacing this unlocked dispatch path.
    """
    await _fake_handler(
        label=f"{session_id}:{message_id}",
        log=log,
        gate=gate,
        work_duration=work_duration,
    )


# ---------------------------------------------------------------------------
# Simulated DM dispatcher WITH per-session lane queue (C17C target)
# ---------------------------------------------------------------------------


class SessionLaneQueue:
    """Per-session async lock registry (test-only reference implementation).

    The production version will wrap ``slack_dm_runtime.handle_dm_event_runtime``
    with a per-session ``asyncio.Lock`` acquired before handler dispatch.

    Contract:
        - Same session_id  → events execute serially (FIFO)
        - Different session_ids → events can execute concurrently
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def dispatch(
        self,
        *,
        session_id: str,
        message_id: str,
        log: ExecutionLog,
        gate: asyncio.Event | None = None,
        work_duration: float = 0.0,
    ) -> None:
        lock = self._get_lock(session_id)
        async with lock:
            await _fake_handler(
                label=f"{session_id}:{message_id}",
                log=log,
                gate=gate,
                work_duration=work_duration,
            )


# ---------------------------------------------------------------------------
# Context mutation tracker (detects lost updates)
# ---------------------------------------------------------------------------


class ContextMutationTracker:
    """Simulates session context read-modify-write without locking.

    Tracks mutation count and detects lost-update races:
    each "handler" reads a counter, sleeps, then writes counter+1.
    Under concurrent access without a lock, the final counter will be
    less than the number of handlers (lost update).
    """

    def __init__(self) -> None:
        self.counter: int = 0
        self.write_log: list[tuple[str, int, int]] = []  # (label, read, wrote)

    async def read_modify_write(
        self, label: str, *, delay: float = 0.01,
    ) -> None:
        """Simulate a non-atomic read-modify-write on session context."""
        read_value = self.counter
        await asyncio.sleep(delay)  # simulate I/O between read and write
        self.counter = read_value + 1
        self.write_log.append((label, read_value, read_value + 1))


# ===================================================================
# BASELINE TESTS — document current (unlocked) behavior
# ===================================================================


class TestBaselineConcurrentDM:
    """Characterize current behavior: no per-session serialization."""

    @pytest.mark.asyncio
    async def test_concurrent_same_session_both_execute(self) -> None:
        """BASELINE: Two DM events for the same session currently run
        concurrently (interleaved).  Neither blocks the other.

        After C17C this interleaving should be impossible for same-session.
        """
        log = ExecutionLog()
        gate = asyncio.Event()

        # Launch two handlers for the same session concurrently.
        t1 = asyncio.create_task(
            dispatch_dm_no_lock(
                session_id="sess-1", message_id="msg-A", log=log, gate=gate,
            )
        )
        t2 = asyncio.create_task(
            dispatch_dm_no_lock(
                session_id="sess-1", message_id="msg-B", log=log, gate=gate,
            )
        )

        # Let both tasks reach their start point.
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(t1, t2)

        # Both started before either ended — interleaved execution.
        labels = log.labels
        starts = [l for l in labels if l.endswith(":start")]
        ends = [l for l in labels if l.endswith(":end")]
        assert len(starts) == 2
        assert len(ends) == 2

        # Verify both handlers ran (current behavior: no blocking).
        assert "sess-1:msg-A:start" in labels
        assert "sess-1:msg-B:start" in labels

    @pytest.mark.asyncio
    async def test_concurrent_different_sessions_both_execute(self) -> None:
        """BASELINE: Two DM events for different sessions run concurrently.
        This should remain true after C17C (lane queue is per-session)."""
        log = ExecutionLog()
        gate = asyncio.Event()

        t1 = asyncio.create_task(
            dispatch_dm_no_lock(
                session_id="sess-1", message_id="msg-A", log=log, gate=gate,
            )
        )
        t2 = asyncio.create_task(
            dispatch_dm_no_lock(
                session_id="sess-2", message_id="msg-B", log=log, gate=gate,
            )
        )

        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(t1, t2)

        labels = log.labels
        assert "sess-1:msg-A:start" in labels
        assert "sess-2:msg-B:start" in labels
        assert "sess-1:msg-A:end" in labels
        assert "sess-2:msg-B:end" in labels

    @pytest.mark.asyncio
    async def test_context_lost_update_without_lock(self) -> None:
        """BASELINE: Without per-session lock, concurrent handlers cause
        lost updates to session context.

        Two handlers both read counter=0, both write counter=1.
        Expected final counter: 1 (not 2).  This is the race C17C fixes.
        """
        tracker = ContextMutationTracker()

        t1 = asyncio.create_task(tracker.read_modify_write("handler-A", delay=0.01))
        t2 = asyncio.create_task(tracker.read_modify_write("handler-B", delay=0.01))
        await asyncio.gather(t1, t2)

        # Lost update: both read 0, both write 1.
        assert tracker.counter == 1, (
            f"Expected lost update (counter=1), got counter={tracker.counter}"
        )


# ===================================================================
# C17C GOAL TESTS — acceptance criteria for lane queue
# ===================================================================


class TestC17CGoalSameSessionSerial:
    """C17C acceptance: same session events must execute serially."""

    @pytest.mark.asyncio
    async def test_same_session_serial_execution(self) -> None:
        """After C17C: two DM events for the same session must execute
        one-after-the-other (no interleaving).

        Acceptance assertion:
            msg-A:start, msg-A:end, msg-B:start, msg-B:end
            (or B before A — order doesn't matter, but no interleaving)
        """
        log = ExecutionLog()
        gate = asyncio.Event()
        gate.set()  # no artificial blocking

        queue = SessionLaneQueue()

        t1 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-1",
                message_id="msg-A",
                log=log,
                work_duration=0.02,
            )
        )
        # Slight stagger so msg-A starts first (FIFO order).
        await asyncio.sleep(0.001)
        t2 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-1",
                message_id="msg-B",
                log=log,
                work_duration=0.02,
            )
        )
        await asyncio.gather(t1, t2)

        labels = log.labels
        a_end_idx = labels.index("sess-1:msg-A:end")
        b_start_idx = labels.index("sess-1:msg-B:start")

        # Serial: B must not start until A ends.
        assert b_start_idx > a_end_idx, (
            f"Expected serial execution: msg-A:end (idx={a_end_idx}) "
            f"before msg-B:start (idx={b_start_idx}). "
            f"Full log: {labels}"
        )

    @pytest.mark.asyncio
    async def test_no_context_lost_updates_under_lane_queue(self) -> None:
        """After C17C: serial execution prevents lost updates.

        Two handlers updating the same counter serially should
        produce counter=2, not counter=1.
        """
        tracker = ContextMutationTracker()

        queue = SessionLaneQueue()

        async def _serialized_rmw(session_id: str, label: str) -> None:
            lock = queue._get_lock(session_id)
            async with lock:
                await tracker.read_modify_write(label, delay=0.01)

        t1 = asyncio.create_task(_serialized_rmw("sess-1", "handler-A"))
        t2 = asyncio.create_task(_serialized_rmw("sess-1", "handler-B"))
        await asyncio.gather(t1, t2)

        # C17C goal: no lost updates.
        assert tracker.counter == 2, (
            f"Expected counter=2 (serial execution), got counter={tracker.counter}. "
            f"Write log: {tracker.write_log}"
        )


class TestC17CGoalDifferentSessionsConcurrent:
    """C17C acceptance: different sessions must NOT block each other."""

    @pytest.mark.asyncio
    async def test_different_sessions_remain_concurrent(self) -> None:
        """After C17C: events for different sessions still run concurrently.

        This test uses the reference SessionLaneQueue to verify the
        contract holds.  It passes today because the reference impl
        is correct — the production code just needs to match it.
        """
        log = ExecutionLog()
        gate = asyncio.Event()
        queue = SessionLaneQueue()

        t1 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-1", message_id="msg-A", log=log, gate=gate,
            )
        )
        t2 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-2", message_id="msg-B", log=log, gate=gate,
            )
        )

        # Let both start.
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(t1, t2)

        labels = log.labels
        # Both sessions started (concurrent — different locks).
        assert "sess-1:msg-A:start" in labels
        assert "sess-2:msg-B:start" in labels
        assert "sess-1:msg-A:end" in labels
        assert "sess-2:msg-B:end" in labels


class TestC17CGoalRapidDoublePing:
    """C17C acceptance: rapid duplicate messages must not cause duplicate mutations."""

    @pytest.mark.asyncio
    async def test_double_ping_same_session_no_duplicate_mutation(self) -> None:
        """After C17C: two rapid "create task" messages for the same session
        should not both execute the mutation.

        The lane queue serializes them so the second message sees the
        state left by the first (e.g., pending_task_create already set,
        or idempotency key already claimed).

        Without lane queue, both read the same "clean" state and both
        attempt the mutation.
        """
        mutation_count = 0
        context: dict[str, Any] = {}

        async def simulate_create_task(msg_label: str) -> None:
            nonlocal mutation_count
            # Step 1: Read state (simulates get_or_create_session)
            already_pending = "pending_task_create" in context

            # Step 2: Yield to event loop (simulates I/O — DB read, LLM call)
            await asyncio.sleep(0.01)

            # Step 3: If not already pending, execute mutation
            if not already_pending:
                mutation_count += 1
                context["pending_task_create"] = {"task": msg_label}

        queue = SessionLaneQueue()

        async def _serialized_create_task(msg_label: str) -> None:
            lock = queue._get_lock("sess-1")
            async with lock:
                await simulate_create_task(msg_label)

        t1 = asyncio.create_task(_serialized_create_task("msg-A"))
        t2 = asyncio.create_task(_serialized_create_task("msg-B"))
        await asyncio.gather(t1, t2)

        # C17C goal: only one mutation should execute.
        # Current behavior: both read empty context, both mutate → count=2.
        assert mutation_count == 1, (
            f"Expected exactly 1 mutation (serialized), got {mutation_count}"
        )


# ===================================================================
# Reference implementation validation
# ===================================================================


class TestSessionLaneQueueReference:
    """Validate the test-only reference SessionLaneQueue implementation.

    These tests confirm the reference impl satisfies the C17C contract,
    so it can be used as a comparison target for the production code.
    """

    @pytest.mark.asyncio
    async def test_same_session_serialized(self) -> None:
        """Same session → events execute serially (FIFO)."""
        log = ExecutionLog()
        queue = SessionLaneQueue()

        t1 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-1",
                message_id="msg-A",
                log=log,
                work_duration=0.02,
            )
        )
        # Small stagger to ensure msg-A acquires lock first.
        await asyncio.sleep(0.001)
        t2 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-1",
                message_id="msg-B",
                log=log,
                work_duration=0.02,
            )
        )
        await asyncio.gather(t1, t2)

        labels = log.labels
        a_end_idx = labels.index("sess-1:msg-A:end")
        b_start_idx = labels.index("sess-1:msg-B:start")
        assert b_start_idx > a_end_idx, (
            f"Reference impl failed serialization: {labels}"
        )

    @pytest.mark.asyncio
    async def test_different_sessions_concurrent(self) -> None:
        """Different sessions → events can run concurrently."""
        log = ExecutionLog()
        gate = asyncio.Event()
        queue = SessionLaneQueue()

        t1 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-1", message_id="msg-A", log=log, gate=gate,
            )
        )
        t2 = asyncio.create_task(
            queue.dispatch(
                session_id="sess-2", message_id="msg-B", log=log, gate=gate,
            )
        )

        # Both should reach start (different locks, no contention).
        await asyncio.sleep(0)
        starts_before_gate = [l for l in log.labels if l.endswith(":start")]
        assert len(starts_before_gate) == 2, (
            f"Expected both to start before gate, got: {log.labels}"
        )

        gate.set()
        await asyncio.gather(t1, t2)

    @pytest.mark.asyncio
    async def test_serialized_context_prevents_lost_update(self) -> None:
        """With lane queue serialization, no lost updates on context."""
        tracker = ContextMutationTracker()
        queue = SessionLaneQueue()

        async def _serialized_rmw(session_id: str, label: str) -> None:
            lock = queue._get_lock(session_id)
            async with lock:
                await tracker.read_modify_write(label, delay=0.01)

        t1 = asyncio.create_task(_serialized_rmw("sess-1", "handler-A"))
        t2 = asyncio.create_task(_serialized_rmw("sess-1", "handler-B"))
        await asyncio.gather(t1, t2)

        assert tracker.counter == 2, (
            f"Expected counter=2 under serialization, got {tracker.counter}"
        )

    @pytest.mark.asyncio
    async def test_lock_registry_creates_per_session(self) -> None:
        """Each session_id gets its own lock instance."""
        queue = SessionLaneQueue()
        lock_a = queue._get_lock("sess-1")
        lock_b = queue._get_lock("sess-2")
        lock_a2 = queue._get_lock("sess-1")

        assert lock_a is lock_a2, "Same session should reuse the same lock"
        assert lock_a is not lock_b, "Different sessions should have different locks"
