
import pytest
from app.services.agencyclaw.client_context_builder import build_client_context_pack, ClientContextInput

class TestClientContextBuilder:
    def test_empty_input(self):
        input_data: ClientContextInput = {}
        result = build_client_context_pack(input_data)
        assert result["context_text"] == ""
        assert result["token_estimate"] == 0
        assert result["included_sources"]["active_tasks"] == 0
        assert result["omitted_sources"]["active_tasks"]["count"] == 0

    def test_fits_within_budget(self):
        input_data: ClientContextInput = {
            "assignments": ["Role 1: Person A"],
            "kpi_targets": ["Target 1: 100%"],
            "active_tasks": ["Task 1", "Task 2"],
            "sop_slices": ["SOP Content..."],
            "recent_events": ["Event 1", "Event 2"]
        }
        result = build_client_context_pack(input_data, max_tokens=4000)
        
        assert result["included_sources"]["assignments"] == 1
        assert result["included_sources"]["active_tasks"] == 2
        assert result["omitted_sources"]["recent_events"]["count"] == 0
        assert "## Team Assignments" in result["context_text"]
        
    def test_truncation_priority(self):
        # Budget is very small to force global truncation
        long_string = "a" * 40 # 10 tokens per item
        
        input_data: ClientContextInput = {
            "assignments": [long_string],   
            "kpi_targets": [long_string],   
            "active_tasks": [long_string],  
            "completed_tasks": [long_string], 
            "sop_slices": [long_string],    
            "recent_events": [long_string]  
        }
        
        # Max tokens to allow ~4 items (keep Assignments, KPI, Active, Completed)
        # Drop Events, SOPs (Low priority)
        result = build_client_context_pack(input_data, max_tokens=70)
        
        # 1. Events dropped first (Lowest) - Global Budget
        assert result["included_sources"]["recent_events"] == 0
        assert result["omitted_sources"]["recent_events"]["count"] == 1
        assert "global_budget" in result["omitted_sources"]["recent_events"]["reason"]
        
        # 2. SOPs dropped next
        assert result["included_sources"]["sop_slices"] == 0
        assert result["omitted_sources"]["sop_slices"]["count"] == 1
        assert "global_budget" in result["omitted_sources"]["sop_slices"]["reason"]
        
        # 3. Completed Tasks KEPT
        assert result["included_sources"]["completed_tasks"] == 1
        
    def test_section_caps(self):
        # Force a section cap violation regardless of global budget
        # "recent_events" limit is 500 tokens. 
        # Create events that exceed 500 tokens.
        
        # 1 token = 4 chars. 500 tokens = 2000 chars.
        # Create 10 events of 300 chars (75 tokens) each -> 750 tokens total.
        long_event = "e" * 300
        events = [long_event] * 10 
        
        input_data: ClientContextInput = {
            "recent_events": events
        }
        
        # Even with global max 4000, section cap should trigger.
        result = build_client_context_pack(input_data, max_tokens=4000)
        
        # Should truncate to ~500 tokens. 
        # 750 (10 items) -> 500 (approx 6-7 items).
        included = result["included_sources"]["recent_events"]
        assert included < 10
        assert included > 0
        
        omitted = result["omitted_sources"]["recent_events"]
        assert omitted["count"] > 0
        assert "section_cap" in omitted["reason"]
        
    def test_determinism(self):
        input_data: ClientContextInput = {
            "active_tasks": ["Task B", "Task A"],
            "recent_events": ["Event 2", "Event 1"]
        }
        
        res1 = build_client_context_pack(input_data)
        res2 = build_client_context_pack(input_data)
        
        assert res1 == res2
        
    def test_freshness_metadata(self):
        freshness = {"last_event": "2023-01-01", "oldest_task": "2022-01-01"}
        input_data: ClientContextInput = {
            "freshness_context": freshness
        }
        
        result = build_client_context_pack(input_data)
        assert result["freshness"] == freshness

    def test_omission_reasons_are_deduplicated(self):
        # Force repeated section-cap omissions in a single section.
        input_data: ClientContextInput = {
            "recent_events": ["e" * 300] * 10
        }

        result = build_client_context_pack(input_data, max_tokens=4000)
        reasons = result["omitted_sources"]["recent_events"]["reason"]
        assert reasons == "section_cap"
