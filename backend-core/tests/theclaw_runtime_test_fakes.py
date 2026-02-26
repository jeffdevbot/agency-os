from __future__ import annotations


class FakeSlackService:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.closed = False

    async def post_message(self, *, channel: str, text: str) -> None:
        self.messages.append({"channel": channel, "text": text})

    async def aclose(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, *, session_id: str = "S1", context: dict | None = None) -> None:
        self.id = session_id
        self.context = context or {}


class FakeSessionService:
    def __init__(self, *, session: FakeSession | None = None) -> None:
        self._session = session or FakeSession()
        self.cleared_users: list[str] = []
        self.updated: list[tuple[str, dict]] = []

    def clear_active_session(self, slack_user_id: str) -> None:
        self.cleared_users.append(slack_user_id)

    def get_or_create_session(self, slack_user_id: str) -> FakeSession:
        _ = slack_user_id
        return self._session

    def update_context(self, session_id: str, context_updates: dict) -> None:
        self.updated.append((session_id, context_updates))
        self._session.context.update(context_updates)
