from __future__ import annotations

import pytest

import app.services.clickup as clickup_module
from app.services.clickup import ClickUpService


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def request(self, method: str, path: str, *, json=None, params=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "json": json,
                "params": params,
            }
        )
        return _FakeResponse(status_code=200, payload={"ok": True, "tasks": []})

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_request_passes_params_to_http_client():
    service = ClickUpService(api_token="token", team_id="team", rate_limit_per_minute=0)
    fake_client = _FakeClient()
    service._client = fake_client  # type: ignore[assignment]

    result = await service._request("GET", "/list/L1/task", params={"page": "2", "include_closed": "true"})

    assert result["ok"] is True
    assert fake_client.calls == [
        {
            "method": "GET",
            "path": "/list/L1/task",
            "json": None,
            "params": {"page": "2", "include_closed": "true"},
        }
    ]


@pytest.mark.asyncio
async def test_get_tasks_in_list_uses_params_not_manual_query():
    service = ClickUpService(api_token="token", team_id="team", rate_limit_per_minute=0)
    captured: dict[str, object] = {}

    async def _fake_request(method: str, path: str, *, json=None, params=None):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json
        captured["params"] = params
        return {"tasks": []}

    service._request = _fake_request  # type: ignore[method-assign]

    await service.get_tasks_in_list(
        "L1",
        date_updated_gt=1700000000000,
        date_updated_lt=1700000000999,
        page=3,
        include_closed=True,
        subtasks=True,
    )

    assert captured["method"] == "GET"
    assert captured["path"] == "/list/L1/task"
    assert captured["json"] is None
    assert captured["params"] == {
        "page": "3",
        "subtasks": "true",
        "include_closed": "true",
        "date_updated_gt": "1700000000000",
        "date_updated_lt": "1700000000999",
    }


@pytest.mark.asyncio
async def test_request_enforces_rate_limit_sleep(monkeypatch):
    service = ClickUpService(api_token="token", team_id="team", rate_limit_per_minute=60)
    fake_client = _FakeClient()
    service._client = fake_client  # type: ignore[assignment]

    sleeps: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monotonic_values = iter([100.0, 100.0, 100.0, 100.0])

    def _fake_monotonic() -> float:
        return next(monotonic_values)

    monkeypatch.setattr(clickup_module.asyncio, "sleep", _fake_sleep)
    service._clock = _fake_monotonic

    await service._request("GET", "/team/T1/space")
    await service._request("GET", "/team/T1/space")

    assert len(fake_client.calls) == 2
    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(1.0, abs=0.0001)


@pytest.mark.asyncio
async def test_request_with_zero_rate_limit_does_not_sleep(monkeypatch):
    service = ClickUpService(api_token="token", team_id="team", rate_limit_per_minute=0)
    fake_client = _FakeClient()
    service._client = fake_client  # type: ignore[assignment]

    sleeps: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(clickup_module.asyncio, "sleep", _fake_sleep)

    await service._request("GET", "/team/T1/space")
    await service._request("GET", "/team/T1/space")

    assert len(fake_client.calls) == 2
    assert sleeps == []
