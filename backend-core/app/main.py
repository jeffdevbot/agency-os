from typing import Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .routers import ngram, npat, root, adscope, clickup
from .auth import verify_supabase_jwt
from .error_logging import error_logger

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ngram.router)
app.include_router(npat.router)
app.include_router(root.router)
app.include_router(adscope.router)
app.include_router(clickup.router)


def _infer_tool_from_path(path: str) -> Optional[str]:
    if path.startswith("/ngram"):
        return "ngram"
    if path.startswith("/npat"):
        return "npat"
    if path.startswith("/root"):
        return "root"
    if path.startswith("/adscope"):
        return "adscope"
    if path.startswith("/clickup"):
        return "clickup"
    return None


def _try_get_user_from_request(request: Request) -> Tuple[Optional[str], Optional[str]]:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        return None, None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, None
    try:
        payload = verify_supabase_jwt(parts[1])
        return payload.get("sub"), payload.get("email")
    except Exception:  # noqa: BLE001
        return None, None


@app.exception_handler(StarletteHTTPException)
async def _http_exception_with_logging(request: Request, exc: StarletteHTTPException):
    status_code = getattr(exc, "status_code", 500)

    # Log 4xx/5xx except auth/forbidden/not-found (too noisy).
    if status_code >= 400 and status_code not in {401, 403, 404}:
        user_id, user_email = _try_get_user_from_request(request)
        tool = _infer_tool_from_path(request.url.path)
        detail = getattr(exc, "detail", None)
        message = str(detail) if detail else f"HTTP {status_code}"

        error_logger.log(
            {
                "tool": tool,
                "severity": "warn" if status_code < 500 else "error",
                "message": message,
                "route": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "request_id": request.headers.get("x-request-id"),
                "user_id": user_id,
                "user_email": user_email,
                "meta": {
                    "type": "http_exception",
                },
            }
        )

    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def _unhandled_exception_with_logging(request: Request, exc: Exception):
    user_id, user_email = _try_get_user_from_request(request)
    tool = _infer_tool_from_path(request.url.path)
    error_logger.log(
        {
            "tool": tool,
            "severity": "error",
            "message": str(exc),
            "route": request.url.path,
            "method": request.method,
            "status_code": 500,
            "request_id": request.headers.get("x-request-id"),
            "user_id": user_id,
            "user_email": user_email,
            "meta": {"type": "unhandled_exception"},
        }
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": settings.app_version}
