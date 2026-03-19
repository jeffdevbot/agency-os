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
    def __init__(
        self,
        *,
        session_id: str = "S1",
        context: dict | None = None,
        profile_id: str | None = None,
        slack_user_id: str = "U1",
        active_client_id: str | None = None,
    ) -> None:
        self.id = session_id
        self.slack_user_id = slack_user_id
        self.profile_id = profile_id
        self.active_client_id = active_client_id
        self.context = context or {}


class FakeSessionService:
    def __init__(self, *, session: FakeSession | None = None) -> None:
        self._session = session or FakeSession()
        self.cleared_users: list[str] = []
        self.updated: list[tuple[str, dict]] = []

    def clear_active_session(self, slack_user_id: str) -> None:
        self.cleared_users.append(slack_user_id)

    def get_active_session(self, slack_user_id: str) -> FakeSession | None:
        _ = slack_user_id
        return self._session

    def ensure_session_profile_link(self, session: FakeSession) -> FakeSession:
        return session

    def get_profile_id_by_slack_user_id(self, slack_user_id: str) -> str | None:
        _ = slack_user_id
        return self._session.profile_id

    def create_session(self, slack_user_id: str, profile_id: str | None) -> FakeSession:
        self._session = FakeSession(
            session_id=self._session.id,
            context=self._session.context,
            profile_id=profile_id,
            slack_user_id=slack_user_id,
            active_client_id=self._session.active_client_id,
        )
        return self._session

    def update_context(self, session_id: str, context_updates: dict) -> None:
        self.updated.append((session_id, context_updates))
        self._session.context.update(context_updates)
