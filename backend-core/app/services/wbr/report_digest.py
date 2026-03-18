"""Build canonical wbr_digest_v1 from WBR section report payloads.

The digest is a compact, prompt-friendly JSON structure designed for:
- Claw summaries and email drafting
- Snapshot persistence and reproducibility
- Stable AI prompt contracts

It is deliberately opinionated and compact — it does not attempt to
preserve the full raw report payload.
"""

from __future__ import annotations

from typing import Any

DIGEST_VERSION = "wbr_digest_v1"


def build_digest(
    *,
    section1: dict[str, Any],
    section2: dict[str, Any],
    section3: dict[str, Any],
) -> dict[str, Any]:
    """Build a wbr_digest_v1 from three section report payloads."""
    profile = section1.get("profile") or {}
    weeks = section1.get("weeks") or []

    window = _build_window(weeks)
    s1_headline = _section1_headline(section1)
    s2_headline = _section2_headline(section2)
    s3_headline = _section3_headline(section3)

    wins, concerns = _derive_movers(section1, section2, section3)
    data_quality_notes = _derive_data_quality_notes(section1, section2, section3)

    return {
        "digest_version": DIGEST_VERSION,
        "profile": {
            "profile_id": str(profile.get("id") or ""),
            "client_name": str(profile.get("client_name") or profile.get("display_name") or ""),
            "marketplace_code": str(profile.get("marketplace_code") or ""),
            "display_name": str(profile.get("display_name") or ""),
        },
        "window": window,
        "headline_metrics": {
            "section1": s1_headline,
            "section2": s2_headline,
            "section3": s3_headline,
        },
        "wins": wins,
        "concerns": concerns,
        "data_quality_notes": data_quality_notes,
        "section_summaries": {
            "section1": _section_row_summaries(section1),
            "section2": _section_row_summaries(section2),
            "section3": _section3_row_summaries(section3),
        },
    }


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------


def _build_window(weeks: list[dict[str, Any]]) -> dict[str, Any]:
    if not weeks:
        return {
            "week_count": 0,
            "window_start": None,
            "window_end": None,
            "week_labels": [],
            "week_ending": None,
        }

    return {
        "week_count": len(weeks),
        "window_start": weeks[0].get("start"),
        "window_end": weeks[-1].get("end"),
        "week_labels": [w.get("label", "") for w in weeks],
        "week_ending": weeks[-1].get("end"),
    }


# ---------------------------------------------------------------------------
# Headline metrics
# ---------------------------------------------------------------------------


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sum_top_rows_metric(report: dict[str, Any], metric: str) -> list[float]:
    """Sum a metric across top-level (parent) rows for each week."""
    rows = report.get("rows") or []
    top_rows = [r for r in rows if not r.get("parent_row_id")]
    week_count = len(report.get("weeks") or [])
    totals = [0.0] * week_count
    for row in top_rows:
        row_weeks = row.get("weeks") or []
        for i, w in enumerate(row_weeks):
            if i < week_count:
                totals[i] += _safe_float(w.get(metric, 0))
    return totals


def _latest_and_prev(values: list[float]) -> tuple[float, float | None]:
    """Return (latest_week_value, previous_week_value_or_None)."""
    if not values:
        return 0.0, None
    latest = values[-1]
    prev = values[-2] if len(values) >= 2 else None
    return latest, prev


def _wow_pct(current: float, previous: float | None) -> float | None:
    if previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous), 4)


def _section1_headline(report: dict[str, Any]) -> dict[str, Any]:
    sales = _sum_top_rows_metric(report, "sales")
    units = _sum_top_rows_metric(report, "unit_sales")
    page_views = _sum_top_rows_metric(report, "page_views")

    latest_sales, prev_sales = _latest_and_prev(sales)
    latest_units, prev_units = _latest_and_prev(units)
    latest_pv, prev_pv = _latest_and_prev(page_views)

    return {
        "total_sales": round(latest_sales, 2),
        "total_sales_wow": _wow_pct(latest_sales, prev_sales),
        "total_unit_sales": round(latest_units),
        "total_unit_sales_wow": _wow_pct(latest_units, prev_units),
        "total_page_views": round(latest_pv),
        "total_page_views_wow": _wow_pct(latest_pv, prev_pv),
    }


def _section2_headline(report: dict[str, Any]) -> dict[str, Any]:
    spend = _sum_top_rows_metric(report, "ad_spend")
    ad_sales = _sum_top_rows_metric(report, "ad_sales")
    impressions = _sum_top_rows_metric(report, "impressions")
    clicks = _sum_top_rows_metric(report, "clicks")
    ad_orders = _sum_top_rows_metric(report, "ad_orders")

    latest_spend, prev_spend = _latest_and_prev(spend)
    latest_ad_sales, prev_ad_sales = _latest_and_prev(ad_sales)
    latest_impressions, _ = _latest_and_prev(impressions)
    latest_clicks, _ = _latest_and_prev(clicks)
    latest_orders, _ = _latest_and_prev(ad_orders)

    acos = round(latest_spend / latest_ad_sales, 4) if latest_ad_sales else None
    ctr = round(latest_clicks / latest_impressions, 4) if latest_impressions else None
    cvr = round(latest_orders / latest_clicks, 4) if latest_clicks else None

    # TACoS requires Section 1 business sales — check availability
    rows = report.get("rows") or []
    top_rows = [r for r in rows if not r.get("parent_row_id")]
    tacos = None
    if top_rows:
        last_week_data = (top_rows[0].get("weeks") or [{}])[-1] if top_rows[0].get("weeks") else {}
        if last_week_data.get("tacos_available") and last_week_data.get("tacos_pct") is not None:
            # Recalculate across all top rows
            biz_sales = _sum_top_rows_metric(report, "business_sales")
            latest_biz, _ = _latest_and_prev(biz_sales)
            tacos = round(latest_spend / latest_biz, 4) if latest_biz else None

    return {
        "total_ad_spend": round(latest_spend, 2),
        "total_ad_spend_wow": _wow_pct(latest_spend, prev_spend),
        "total_ad_sales": round(latest_ad_sales, 2),
        "total_ad_sales_wow": _wow_pct(latest_ad_sales, prev_ad_sales),
        "acos": acos,
        "tacos": tacos,
        "ctr": ctr,
        "cvr": cvr,
        "total_impressions": round(latest_impressions),
        "total_clicks": round(latest_clicks),
        "total_ad_orders": round(latest_orders),
    }


def _section3_headline(report: dict[str, Any]) -> dict[str, Any]:
    totals = report.get("totals") or {}
    return {
        "weeks_of_stock": totals.get("weeks_of_stock"),
        "return_rate": totals.get("return_rate"),
    }


# ---------------------------------------------------------------------------
# Wins / Concerns
# ---------------------------------------------------------------------------


def _derive_movers(
    section1: dict[str, Any],
    section2: dict[str, Any],
    section3: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Identify compact wins and concerns from WoW changes."""
    wins: list[str] = []
    concerns: list[str] = []

    # Section 1 — sales WoW
    s1 = _section1_headline(section1)
    wow_sales = s1.get("total_sales_wow")
    if wow_sales is not None:
        if wow_sales >= 0.05:
            wins.append(f"Sales up {wow_sales:+.0%} WoW")
        elif wow_sales <= -0.05:
            concerns.append(f"Sales down {wow_sales:+.0%} WoW")

    wow_units = s1.get("total_unit_sales_wow")
    if wow_units is not None:
        if wow_units >= 0.05:
            wins.append(f"Unit sales up {wow_units:+.0%} WoW")
        elif wow_units <= -0.05:
            concerns.append(f"Unit sales down {wow_units:+.0%} WoW")

    # Section 2 — spend efficiency
    s2 = _section2_headline(section2)
    wow_spend = s2.get("total_ad_spend_wow")
    if wow_spend is not None and wow_spend <= -0.10:
        wins.append(f"Ad spend reduced {wow_spend:+.0%} WoW")

    acos = s2.get("acos")
    if acos is not None and acos > 0.40:
        concerns.append(f"ACoS at {acos:.0%}")

    # Section 3 — inventory / returns
    s3 = _section3_headline(section3)
    wos = s3.get("weeks_of_stock")
    if wos is not None:
        if wos < 3.0:
            concerns.append(f"Low stock: {wos:.1f} weeks of stock")
        elif wos > 12.0:
            wins.append(f"Well-stocked: {wos:.1f} weeks of stock")

    rr = s3.get("return_rate")
    if rr is not None and rr > 0.05:
        concerns.append(f"Return rate elevated: {rr:.1%}")

    return wins, concerns


# ---------------------------------------------------------------------------
# Data quality notes
# ---------------------------------------------------------------------------


def _derive_data_quality_notes(
    section1: dict[str, Any],
    section2: dict[str, Any],
    section3: dict[str, Any],
) -> list[str]:
    notes: list[str] = []

    qa1 = section1.get("qa") or {}
    if qa1.get("unmapped_asin_count", 0) > 0:
        notes.append(
            f"Section 1: {qa1['unmapped_asin_count']} unmapped ASIN(s), "
            f"{qa1.get('unmapped_fact_rows', 0)} fact rows excluded"
        )

    qa2 = section2.get("qa") or {}
    if qa2.get("unmapped_campaign_count", 0) > 0:
        notes.append(
            f"Section 2: {qa2['unmapped_campaign_count']} unmapped campaign(s)"
        )

    qa3 = section3.get("qa") or {}
    if qa3.get("unmapped_inventory_asin_count", 0) > 0:
        notes.append(
            f"Section 3: {qa3['unmapped_inventory_asin_count']} unmapped inventory ASIN(s)"
        )

    return notes


# ---------------------------------------------------------------------------
# Section row summaries
# ---------------------------------------------------------------------------


def _section_row_summaries(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact summary for Section 1 / Section 2: top-level rows with latest week."""
    rows = report.get("rows") or []
    weeks = report.get("weeks") or []
    top_rows = [r for r in rows if not r.get("parent_row_id")]

    summaries: list[dict[str, Any]] = []
    for row in top_rows:
        row_weeks = row.get("weeks") or []
        latest = row_weeks[-1] if row_weeks else {}
        summary: dict[str, Any] = {
            "label": row.get("row_label", ""),
            "latest_week": latest,
        }
        if len(row_weeks) >= 2:
            summary["prev_week"] = row_weeks[-2]
        summaries.append(summary)

    return summaries


def _section3_row_summaries(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact summary for Section 3: top-level rows with inventory + returns."""
    rows = report.get("rows") or []
    top_rows = [r for r in rows if not r.get("parent_row_id")]

    summaries: list[dict[str, Any]] = []
    for row in top_rows:
        summaries.append({
            "label": row.get("row_label", ""),
            "instock": row.get("instock", 0),
            "weeks_of_stock": row.get("weeks_of_stock"),
            "returns_week_1": row.get("returns_week_1", 0),
            "returns_week_2": row.get("returns_week_2", 0),
            "return_rate": row.get("return_rate"),
        })

    return summaries
