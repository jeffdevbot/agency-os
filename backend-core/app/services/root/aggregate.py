"""Hierarchical aggregation and metric calculation for Root Keyword Analysis."""
from __future__ import annotations

from typing import Any

import pandas as pd
import numpy as np

from .weeks import WeekBucket, assign_week_bucket


class HierarchyNode:
    """Represents a node in the hierarchy tree."""

    def __init__(self, level: str, label: str, full_path: list[str]):
        self.level = level  # ProfileName, PortfolioName, AdType, Targeting, SubType, Variant
        self.label = label  # Display label for this node
        self.full_path = full_path  # Full path from root to this node
        self.metrics_by_week: dict[int, dict[str, float]] = {}  # week_num -> metrics

    def add_metrics(self, week_num: int, metrics: dict[str, float]):
        """Add or update metrics for a specific week."""
        if week_num not in self.metrics_by_week:
            self.metrics_by_week[week_num] = {}
        for key, value in metrics.items():
            self.metrics_by_week[week_num][key] = (
                self.metrics_by_week[week_num].get(key, 0.0) + value
            )

    def get_display_label(self) -> str:
        """Get the display label for Excel output (pipe-separated path with indent)."""
        path_str = " | ".join(self.full_path)
        indent = "  " * (len(self.full_path) - 1)
        return f"{indent}{path_str}"

    def calculate_rates(self):
        """Calculate CTR, CVR, CPC, ACoS for each week."""
        for week_num, metrics in self.metrics_by_week.items():
            impression = metrics.get("Impression", 0.0)
            click = metrics.get("Click", 0.0)
            spend = metrics.get("Spend", 0.0)
            order = metrics.get("Order14d", 0.0)
            sales = metrics.get("Sales14d", 0.0)

            # Calculate rates with division-by-zero guards
            metrics["CTR"] = (click / impression) if impression > 0 else 0.0
            metrics["CVR"] = (order / click) if click > 0 else 0.0
            metrics["CPC"] = (spend / click) if click > 0 else 0.0
            metrics["ACoS"] = (spend / sales) if sales > 0 else 0.0
            metrics["ROAS"] = (sales / spend) if spend > 0 else 0.0


def aggregate_hierarchy(df: pd.DataFrame, week_buckets: list[WeekBucket]) -> list[HierarchyNode]:
    """
    Aggregate data into hierarchical structure grouped by weeks.

    Hierarchy levels (in order):
    1. ProfileName
    2. PortfolioName
    3. AdType
    4. Targeting
    5. SubType
    6. Variant

    Args:
        df: Dataframe with parsed campaign data and week assignments
        week_buckets: List of WeekBucket objects

    Returns:
        List of HierarchyNode objects in display order (alphabetically sorted within each level)
    """
    # Assign week buckets to each row
    df = df.copy()
    df["WeekNum"] = df["Time"].apply(lambda t: assign_week_bucket(t, week_buckets))

    # Filter to rows within the 4-week window
    df = df[df["WeekNum"].notna()]

    if len(df) == 0:
        raise ValueError("No data in last 4 weeks")

    # Build hierarchical structure
    nodes: dict[tuple, HierarchyNode] = {}
    children: dict[tuple, list[tuple]] = {}

    # Hierarchy levels in order
    levels = ["ProfileName", "PortfolioName", "AdType", "Targeting", "SubType", "Variant"]

    for _, row in df.iterrows():
        week_num = int(row["WeekNum"])

        current_path: list[str] = []
        for level in levels:
            value = str(row[level]).strip()
            if not value:
                break

            current_path.append(value)
            node_key = tuple(current_path)

            if node_key not in nodes:
                nodes[node_key] = HierarchyNode(
                    level=level,
                    label=value,
                    full_path=current_path.copy(),
                )

            metrics = {
                "Impression": float(row["Impression"]),
                "Click": float(row["Click"]),
                "Spend": float(row["Spend"]),
                "Order14d": float(row["Order14d"]),
                "SaleUnits14d": float(row["SaleUnits14d"]),
                "Sales14d": float(row["Sales14d"]),
            }
            nodes[node_key].add_metrics(week_num, metrics)

    # Build parent-child relationships
    for node_key in nodes.keys():
        if len(node_key) == 1:
            continue
        parent = node_key[:-1]
        if parent in nodes:
            children.setdefault(parent, []).append(node_key)

    # Calculate rates for all nodes
    for node in nodes.values():
        node.calculate_rates()

    def dfs(node_key: tuple, acc: list[HierarchyNode]):
        acc.append(nodes[node_key])
        for child in sorted(children.get(node_key, []), key=lambda k: nodes[k].label):
            dfs(child, acc)

    ordered_nodes: list[HierarchyNode] = []
    root_keys = [k for k in nodes.keys() if len(k) == 1]
    for root in sorted(root_keys, key=lambda k: nodes[k].label):
        dfs(root, ordered_nodes)

    return ordered_nodes


def get_stats(nodes: list[HierarchyNode]) -> dict[str, int]:
    """Get statistics about the aggregated data."""
    profiles = set()
    portfolios = set()
    campaigns = 0

    for node in nodes:
        if node.level == "ProfileName":
            profiles.add(node.label)
        elif node.level == "PortfolioName":
            portfolios.add(node.label)
        elif node.level == "Variant":
            campaigns += 1

    return {
        "profiles_count": len(profiles),
        "portfolios_count": len(portfolios),
        "campaigns_parsed": campaigns,
    }
