from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from ...services.theclaw.slack_http_runtime import (
    handle_slack_events_http_runtime,
    handle_slack_interactions_http_runtime,
)
from ...services.theclaw.slack_minimal_runtime import (
    handle_theclaw_minimal_interaction,
    run_theclaw_minimal_dm_turn,
)

router = APIRouter(prefix="/slack", tags=["slack"])


async def _handle_dm_event(*, slack_user_id: str, channel: str, text: str) -> None:
    await run_theclaw_minimal_dm_turn(
        slack_user_id=slack_user_id,
        channel=channel,
        text=text,
    )


async def _handle_interaction(payload: dict[str, Any]) -> None:
    await handle_theclaw_minimal_interaction(payload=payload)


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    result = await handle_slack_events_http_runtime(
        request=request,
        background_tasks=background_tasks,
        handle_dm_event_fn=_handle_dm_event,
    )
    return JSONResponse(result)


@router.post("/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    result = await handle_slack_interactions_http_runtime(
        request=request,
        background_tasks=background_tasks,
        handle_interaction_fn=_handle_interaction,
    )
    return JSONResponse(result)
