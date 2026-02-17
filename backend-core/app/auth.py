from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from supabase import Client, create_client

from .config import settings


auth_scheme = HTTPBearer(auto_error=True)
_supabase_admin_client: Client | None = None


def verify_supabase_jwt(token: str):
    if not settings.supabase_jwt_secret:
        raise RuntimeError("SUPABASE_JWT_SECRET not configured.")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
            options={"verify_iss": True},
            issuer=settings.supabase_issuer,
        )
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def require_user(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    token = creds.credentials
    return verify_supabase_jwt(token)


def _get_supabase_admin_client() -> Client:
    global _supabase_admin_client  # noqa: PLW0603
    if _supabase_admin_client:
        return _supabase_admin_client
    if not settings.supabase_url or not settings.supabase_service_role:
        raise RuntimeError("Supabase admin credentials are not configured.")
    _supabase_admin_client = create_client(settings.supabase_url, settings.supabase_service_role)
    return _supabase_admin_client


def require_admin_user(user=Depends(require_user)):
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing subject")

    try:
        db = _get_supabase_admin_client()
        response = db.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to validate admin access: {exc}") from exc

    rows = response.data if isinstance(response.data, list) else []
    if not rows or not isinstance(rows[0], dict):
        raise HTTPException(status_code=403, detail="Admin access required")

    profile = rows[0]
    is_admin = bool(profile.get("is_admin"))
    role = str(profile.get("role") or "").strip().lower()
    team_role = str(profile.get("team_role") or "").strip().lower()
    if is_admin or role == "admin" or team_role == "admin":
        return user

    raise HTTPException(status_code=403, detail="Admin access required")
