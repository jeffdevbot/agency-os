"""Root Keyword Analysis service modules."""

from .parser import read_campaign_report, read_campaign_report_path, parse_campaign_name
from .weeks import calculate_week_buckets, assign_week_bucket, WeekBucket
from .aggregate import aggregate_hierarchy, get_stats, HierarchyNode
from .workbook import build_root_workbook

__all__ = [
    "read_campaign_report",
    "read_campaign_report_path",
    "parse_campaign_name",
    "calculate_week_buckets",
    "assign_week_bucket",
    "WeekBucket",
    "aggregate_hierarchy",
    "get_stats",
    "HierarchyNode",
    "build_root_workbook",
]
