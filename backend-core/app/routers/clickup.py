from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import require_user
from ..services.clickup import (
    ClickUpAPIError,
    ClickUpConfigurationError,
    ClickUpError,
    ClickUpRateLimitError,
    ClickUpService,
    get_clickup_service,
)


router = APIRouter(prefix="/clickup", tags=["clickup"])


class CreateTaskRequest(BaseModel):
    list_id: str | None = Field(default=None)
    space_id: str | None = Field(default=None)
    override_list_id: str | None = Field(default=None)
    name: str = Field(min_length=1)
    description_md: str | None = Field(default=None)
    assignee_ids: list[str] | None = Field(default=None)


class CreateTaskResponse(BaseModel):
    id: str
    url: str | None = None


@router.get("/healthz")
def health():
    return {"ok": True}


@router.post("/tasks", response_model=CreateTaskResponse)
async def create_task(
    payload: CreateTaskRequest,
    _user=Depends(require_user),
):
    service: ClickUpService | None = None
    try:
        service = get_clickup_service()

        if payload.list_id:
            task = await service.create_task_in_list(
                list_id=payload.list_id,
                name=payload.name,
                description_md=payload.description_md,
                assignee_ids=payload.assignee_ids,
            )
        elif payload.space_id:
            task = await service.create_task_in_space(
                space_id=payload.space_id,
                override_list_id=payload.override_list_id,
                name=payload.name,
                description_md=payload.description_md,
                assignee_ids=payload.assignee_ids,
            )
        else:
            raise HTTPException(status_code=400, detail="Provide either list_id or space_id")

        return CreateTaskResponse(id=task.id, url=task.url)
    except ClickUpRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ClickUpConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ClickUpAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ClickUpError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if service:
            await service.aclose()

