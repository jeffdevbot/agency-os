from typing import Any, Dict, List, Optional
from supabase import Client
from .identity_reconciliation import (
    ExistingProfile,
    SlackExternalUser,
    ClickUpExternalUser,
    reconcile_identity,
    ReconciliationResult,
)

def run_identity_sync(
    db: Client,
    *,
    slack_users: List[SlackExternalUser],
    clickup_users: List[ClickUpExternalUser],
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Orchestrates identity reconciliation against the database.
    
    1. Fetches existing profiles.
    2. Runs reconciliation for each candidate.
    3. Applies updates (auto_match) or logs events (needs_review) if dry_run=False.
    4. Returns summary stats and proposal lists.
    """
    
    # 1. Fetch Existing Profiles
    # TODO: pagination? Assuming reasonable count for now (<1000)
    response = db.table("profiles").select("id,slack_user_id,clickup_user_id,email,is_admin").execute()
    data = response.data if response.data else []
    profiles: List[ExistingProfile] = [
        ExistingProfile(
            id=d["id"],
            slack_user_id=d.get("slack_user_id"),
            clickup_user_id=d.get("clickup_user_id"),
            email=d.get("email"),
            is_admin=d.get("is_admin", False)
        )
        for d in data
    ]

    results: Dict[str, Any] = {
        "summary": {
            "auto_match": 0,
            "new_profile": 0,
            "needs_review": 0,
        },
        "actions_taken": [],
        "proposals": [], # New profile candidates
        "needs_review_items": [],
    }

    def process_result(result: ReconciliationResult, source_type: str, candidate_id: str):
        outcome = result["outcome"]
        results["summary"][outcome] += 1
        
        if outcome == "auto_match":
            action = result.get("suggested_action")
            if action and action.get("action") == "update_profile":
                pid = action["profile_id"]
                updates = action["updates"]
                
                # Only perform update if there are actual diffs
                if updates and not dry_run:
                    try:
                        db.table("profiles").update(updates).eq("id", pid).execute()
                        for profile in profiles:
                            if profile["id"] == pid:
                                profile.update(updates)
                                break
                        results["actions_taken"].append(
                            f"Updated profile {pid} with {updates}"
                        )
                    except Exception as e:
                        results["actions_taken"].append(f"Error updating profile {pid}: {e}")
                elif updates:
                     results["actions_taken"].append(f"[DRY RUN] Would update profile {pid} with {updates}")

        elif outcome == "new_profile":
            results["proposals"].append({
                "source": source_type,
                "candidate_id": candidate_id,
                "reasons": result["reasons"],
                "suggested_payload": result.get("suggested_action", {}).get("payload")
            })
            
        elif outcome == "needs_review":
            item = {
                "source": source_type,
                "candidate_id": candidate_id,
                "candidate_profiles": result["candidate_profile_ids"],
                "reasons": result["reasons"]
            }
            results["needs_review_items"].append(item)
            
            if not dry_run:
                try:
                    db.table("agent_events").insert({
                        "event_type": "identity_needs_review",
                        "payload": item,
                        # Assuming no specific client_id/employee_id context here globally
                    }).execute()
                except Exception:
                    pass

    # 2. Process Slack Candidates
    for s_user in slack_users:
        res = reconcile_identity(s_user, None, profiles)
        process_result(res, "slack", s_user["slack_user_id"])

    # 3. Process ClickUp Candidates
    for c_user in clickup_users:
        res = reconcile_identity(None, c_user, profiles)
        process_result(res, "clickup", c_user["clickup_user_id"])

    return results
