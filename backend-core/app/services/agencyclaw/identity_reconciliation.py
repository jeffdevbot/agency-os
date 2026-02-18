from typing import List, Optional, TypedDict, Any

class SlackExternalUser(TypedDict):
    slack_user_id: str
    email: Optional[str]
    real_name: Optional[str]

class ClickUpExternalUser(TypedDict):
    clickup_user_id: str
    email: Optional[str]
    username: Optional[str]

class ExistingProfile(TypedDict):
    id: str
    slack_user_id: Optional[str]
    clickup_user_id: Optional[str]
    email: Optional[str]
    is_admin: bool

class ReconciliationResult(TypedDict):
    outcome: str  # "auto_match", "new_profile", "needs_review"
    candidate_profile_ids: List[str]
    reasons: List[str]
    suggested_action: Optional[dict[str, Any]]

def normalize_email(email: Optional[str]) -> Optional[str]:
    return email.strip().lower() if email else None

def reconcile_identity(
    slack_user: Optional[SlackExternalUser],
    clickup_user: Optional[ClickUpExternalUser],
    existing_profiles: List[ExistingProfile]
) -> ReconciliationResult:
    reasons: List[str] = []
    candidates: List[str] = []
    
    # 1. Normalize Inputs
    s_email = normalize_email(slack_user.get("email")) if slack_user else None
    s_id = slack_user.get("slack_user_id") if slack_user else None
    
    c_email = normalize_email(clickup_user.get("email")) if clickup_user else None
    c_id = clickup_user.get("clickup_user_id") if clickup_user else None

    # 2. Find Matches (Precedence: Email > Slack ID > ClickUp ID)
    matches: dict[str, List[str]] = {} # profile_id -> reasons

    for profile in existing_profiles:
        p_id = profile["id"]
        p_email = normalize_email(profile.get("email"))
        p_slack = profile.get("slack_user_id")
        p_clickup = profile.get("clickup_user_id")
        
        # Check Exact Email Match
        if p_email and (p_email == s_email or p_email == c_email):
             matches.setdefault(p_id, []).append("email_match")
        
        # Check Exact Slack ID Match
        if p_slack and s_id and p_slack == s_id:
            matches.setdefault(p_id, []).append("slack_id_match")
            
        # Check Exact ClickUp ID Match
        if p_clickup and c_id and p_clickup == c_id:
            matches.setdefault(p_id, []).append("clickup_id_match")

    candidates = list(matches.keys())

    # 3. Determine Outcome
    
    # Scenario A: No Matches -> New Profile
    if not candidates:
        return {
            "outcome": "new_profile",
            "candidate_profile_ids": [],
            "reasons": ["no_existing_match_found"],
            "suggested_action": {
                "action": "create_profile",
                "payload": {
                    "slack_user_id": s_id,
                    "clickup_user_id": c_id,
                    "email": s_email or c_email, # Prefer slack email?
                    "full_name": slack_user.get("real_name") if slack_user else (clickup_user.get("username") if clickup_user else "")
                }
            }
        }

    # Scenario B: Multiple Matches -> Needs Review
    if len(candidates) > 1:
        return {
            "outcome": "needs_review",
            "candidate_profile_ids": candidates,
            "reasons": ["multiple_candidates_found"] + [f"{pid}: {','.join(reasons)}" for pid, reasons in matches.items()],
            "suggested_action": None
        }

    # Scenario C: Single Match
    match_id = candidates[0]
    match_reasons = matches[match_id]
    profile = next(p for p in existing_profiles if p["id"] == match_id)
    
    # Check for ID Conflicts
    # If the profile has a DIFFERENT Slack ID than the incoming one, it's a conflict (unless incoming is None)
    if s_id and profile.get("slack_user_id") and profile.get("slack_user_id") != s_id:
         return {
            "outcome": "needs_review",
            "candidate_profile_ids": [match_id],
            "reasons": ["conflicting_slack_id"],
            "suggested_action": None
        }

    # If the profile has a DIFFERENT ClickUp ID than the incoming one
    if c_id and profile.get("clickup_user_id") and profile.get("clickup_user_id") != c_id:
         return {
            "outcome": "needs_review",
            "candidate_profile_ids": [match_id],
            "reasons": ["conflicting_clickup_id"],
            "suggested_action": None
        }
        
    # Auto Match Success
    updates: dict[str, str] = {}
    if s_id and not profile.get("slack_user_id"):
        updates["slack_user_id"] = s_id
    if c_id and not profile.get("clickup_user_id"):
        updates["clickup_user_id"] = c_id

    return {
        "outcome": "auto_match",
        "candidate_profile_ids": [match_id],
        "reasons": match_reasons,
        "suggested_action": {
            "action": "update_profile",
            "profile_id": match_id,
            "updates": updates,
        }
    }
