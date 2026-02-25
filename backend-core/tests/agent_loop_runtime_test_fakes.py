from __future__ import annotations


class FakeSlack:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def post_message(self, *, channel: str, text: str, blocks=None) -> None:
        self.messages.append({"channel": channel, "text": text})


class FakeSession:
    def __init__(self, session_id: str = "sess-1", context: dict | None = None) -> None:
        self.id = session_id
        self.context = context or {}


class FakeSessionService:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def update_context(self, session_id: str, context: dict) -> None:
        assert session_id == self._session.id
        self._session.context.update(context)

