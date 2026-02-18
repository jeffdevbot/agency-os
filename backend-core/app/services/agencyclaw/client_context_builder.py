from typing import Any, Dict, List, Optional, TypedDict

class ClientContextInput(TypedDict):
    assignments: List[str]
    kpi_targets: List[str]
    active_tasks: List[str]
    completed_tasks: List[str]
    sop_slices: List[str]
    recent_events: List[str]
    freshness_context: Optional[Dict[str, Any]]

class OmittedDetail(TypedDict):
    count: int
    reason: str

class ClientContextOutput(TypedDict):
    context_text: str
    token_estimate: int
    included_sources: Dict[str, int]
    omitted_sources: Dict[str, OmittedDetail]
    freshness: Dict[str, Any]

# Budget Configuration (Tokens)
TOTAL_BUDGET = 4000
TARGET_ALLOCATIONS = {
    "assignments": 500,
    "kpi_targets": 500,
    "active_tasks": 1500,
    "sop_slices": 1000,
    "recent_events": 500,
    "completed_tasks": 500 # Implicit "mid priority" bucket, share with something? 
                           # Or just treat as "what's left"? 
                           # Providing a default 500 for safety.
}

# Simple heuristic: 1 token approx 4 chars
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(text) // 4

def _format_section(title: str, items: List[str]) -> str:
    if not items:
        return ""
    content = "\n".join(f"- {item}" for item in items)
    return f"## {title}\n{content}\n\n"

def build_client_context_pack(input_data: ClientContextInput, max_tokens: int = TOTAL_BUDGET) -> ClientContextOutput:
    """
    Builds a deterministic context pack for a client within a fixed token budget.
    
    Phases:
    1. Strict Section Caps: Enforce TARGET_ALLOCATIONS per section.
    2. Global Assembly & Truncation:
       Priority for retention when over global budget:
       1. Assignments (Highest)
       2. KPI Targets
       3. Active Tasks
       4. Completed Tasks
       5. SOP Slices
       6. Recent Events (Lowest - drop oldest first)
    """
    
    sections = {
        "assignments": list(input_data.get("assignments", [])),
        "kpi_targets": list(input_data.get("kpi_targets", [])),
        "active_tasks": list(input_data.get("active_tasks", [])),
        "completed_tasks": list(input_data.get("completed_tasks", [])),
        "sop_slices": list(input_data.get("sop_slices", [])),
        "recent_events": list(input_data.get("recent_events", [])),
    }
    
    omitted_details: Dict[str, OmittedDetail] = {
        k: {"count": 0, "reason": ""} for k in sections.keys()
    }
    omission_reasons: Dict[str, List[str]] = {k: [] for k in sections.keys()}
    
    # helper to track omission
    def record_omission(section: str, count: int, reason: str) -> None:
        current = omitted_details[section]
        current["count"] += count
        reasons = omission_reasons[section]
        if reason not in reasons:
            reasons.append(reason)
        current["reason"] = ", ".join(reasons)

    # Phase 1: Section Caps
    for section, target in TARGET_ALLOCATIONS.items():
        if section not in sections: continue
        
        # Calculate current size
        items = sections[section]
        while items:
            # Check cost. Ideally we check cost of *just this section*.
            # _format_section adds header overhead.
            text = _format_section("temp", items)
            cost = estimate_tokens(text)
            if cost <= target:
                break
            # Truncate last item (or oldest for events?)
            # For strict determinism + simple logic, we drop last item for now.
            # Events are assumed "Newest...Oldest", so dropping last drops oldest.
            items.pop()
            record_omission(section, 1, "section_cap")

    # Phase 2: Global Assembly & Truncation
    def calculate_current_tokens() -> int:
        text = ""
        text += _format_section("Team Assignments", sections["assignments"])
        text += _format_section("KPI Targets", sections["kpi_targets"])
        text += _format_section("Active Tasks", sections["active_tasks"])
        text += _format_section("Completed Tasks", sections["completed_tasks"])
        text += _format_section("Relevant SOPs", sections["sop_slices"])
        text += _format_section("Recent Events", sections["recent_events"])
        return estimate_tokens(text)

    # Priority 1: Events (Drop oldest/last)
    while calculate_current_tokens() > max_tokens and sections["recent_events"]:
        sections["recent_events"].pop()
        record_omission("recent_events", 1, "global_budget")
        
    # Priority 2: SOP Slices (Drop last)
    while calculate_current_tokens() > max_tokens and sections["sop_slices"]:
        sections["sop_slices"].pop()
        record_omission("sop_slices", 1, "global_budget")

    # Priority 3: Completed Tasks (Drop last)
    while calculate_current_tokens() > max_tokens and sections["completed_tasks"]:
        sections["completed_tasks"].pop()
        record_omission("completed_tasks", 1, "global_budget")
        
    # Priority 4: Active Tasks (Drop last)
    while calculate_current_tokens() > max_tokens and sections["active_tasks"]:
        sections["active_tasks"].pop()
        record_omission("active_tasks", 1, "global_budget")

    # Priority 5: KPIs (Drop last)
    while calculate_current_tokens() > max_tokens and sections["kpi_targets"]:
        sections["kpi_targets"].pop()
        record_omission("kpi_targets", 1, "global_budget")
        
    # Priority 6: Assignments (Drop last)
    while calculate_current_tokens() > max_tokens and sections["assignments"]:
        sections["assignments"].pop()
        record_omission("assignments", 1, "global_budget")

    # Final Assembly
    final_text = ""
    final_text += _format_section("Team Assignments", sections["assignments"])
    final_text += _format_section("KPI Targets", sections["kpi_targets"])
    final_text += _format_section("Active Tasks", sections["active_tasks"])
    final_text += _format_section("Completed Tasks", sections["completed_tasks"])
    final_text += _format_section("Relevant SOPs", sections["sop_slices"])
    final_text += _format_section("Recent Events", sections["recent_events"])
    
    included_counts = {k: len(v) for k, v in sections.items()}
    
    return {
        "context_text": final_text.strip(),
        "token_estimate": estimate_tokens(final_text),
        "included_sources": included_counts,
        "omitted_sources": omitted_details,
        "freshness": input_data.get("freshness_context", {}) or {}
    }
