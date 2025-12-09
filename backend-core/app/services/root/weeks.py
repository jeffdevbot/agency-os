"""Week bucketing utilities for Root Keyword Analysis."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import NamedTuple


class WeekBucket(NamedTuple):
    """Represents a single week bucket with start/end dates and labels."""
    week_num: int  # 1 = most recent, 4 = oldest
    start: datetime  # Sunday 00:00:00 UTC
    end: datetime    # Saturday 23:59:59.999999 UTC
    start_label: str  # e.g., "Aug 10"
    end_label: str    # e.g., "Aug 16"


def calculate_week_buckets(max_date: datetime) -> list[WeekBucket]:
    """
    Calculate 4 full Sunday-Saturday week buckets anchored to max_date.

    Algorithm (per PRD):
    1. Find the Saturday at or before max_date (this is week 1 end)
    2. Week 1 start = that Saturday - 6 days
    3. Weeks 2-4 back up in 7-day blocks

    Args:
        max_date: Latest date in the dataset (UTC)

    Returns:
        List of 4 WeekBucket objects, ordered from most recent (week 1) to oldest (week 4)
    """
    # Ensure max_date is UTC
    if max_date.tzinfo is None:
        max_date = max_date.replace(tzinfo=timezone.utc)

    # Find the Saturday at or before max_date
    # weekday(): Monday=0, Sunday=6
    days_since_saturday = (max_date.weekday() + 2) % 7
    if days_since_saturday == 0 and max_date.hour == 0 and max_date.minute == 0:
        # max_date is exactly a Saturday at midnight, use it
        week1_end_date = max_date.date()
    else:
        week1_end_date = (max_date - timedelta(days=days_since_saturday)).date()

    # Build week 1 end at Saturday 23:59:59.999999
    week1_end = datetime.combine(
        week1_end_date,
        datetime.max.time()
    ).replace(tzinfo=timezone.utc)

    # Week 1 start = Saturday - 6 days (Sunday 00:00:00)
    week1_start = datetime.combine(
        week1_end_date - timedelta(days=6),
        datetime.min.time()
    ).replace(tzinfo=timezone.utc)

    buckets = []
    for i in range(4):
        week_num = i + 1
        # Calculate start and end for this week
        start = week1_start - timedelta(days=7 * i)
        end = week1_end - timedelta(days=7 * i)

        # Format labels (e.g., "Aug 10")
        start_label = start.strftime("%b %d")
        end_label = end.strftime("%b %d")

        buckets.append(WeekBucket(
            week_num=week_num,
            start=start,
            end=end,
            start_label=start_label,
            end_label=end_label,
        ))

    return buckets


def assign_week_bucket(row_time: datetime, buckets: list[WeekBucket]) -> int | None:
    """
    Assign a row to a week bucket based on its timestamp.

    Args:
        row_time: Timestamp from the row (UTC)
        buckets: List of WeekBucket objects from calculate_week_buckets

    Returns:
        Week number (1-4) if row falls within a bucket, None otherwise
    """
    if row_time is None or row_time != row_time:  # Check for NaT
        return None

    # Ensure UTC
    if row_time.tzinfo is None:
        row_time = row_time.replace(tzinfo=timezone.utc)

    for bucket in buckets:
        if bucket.start <= row_time <= bucket.end:
            return bucket.week_num

    return None
