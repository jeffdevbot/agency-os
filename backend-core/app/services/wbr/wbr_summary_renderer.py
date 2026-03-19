"""Render a wbr_digest_v1 into compact Slack mrkdwn text.

This is a pure, deterministic formatter — no DB calls, no LLM calls.
The Claw can use this directly or feed the digest to an LLM for
more conversational output.
"""

from __future__ import annotations

from typing import Any


def render_wbr_summary(digest: dict[str, Any]) -> str:
    """Format a wbr_digest_v1 dict as Slack-friendly mrkdwn."""
    profile = digest.get("profile") or {}
    window = digest.get("window") or {}
    s1 = (digest.get("headline_metrics") or {}).get("section1") or {}
    s2 = (digest.get("headline_metrics") or {}).get("section2") or {}
    s3 = (digest.get("headline_metrics") or {}).get("section3") or {}
    wins = digest.get("wins") or []
    concerns = digest.get("concerns") or []
    notes = digest.get("data_quality_notes") or []

    client_name = profile.get("client_name") or ""
    display_name = profile.get("display_name") or ""
    market = profile.get("marketplace_code") or ""

    # Build a readable label: prefer "ClientName MarketCode", fall back to
    # display_name (which often already contains the market code).
    if client_name:
        label = f"{client_name} {market}".strip()
    elif display_name:
        label = display_name
    else:
        label = "Unknown"

    week_ending = window.get("week_ending") or "—"
    week_count = window.get("week_count") or 0

    lines: list[str] = []

    # Header
    lines.append(f"*WBR Summary — {label}*")
    lines.append(f"Week ending {week_ending} · {week_count}-week window")
    lines.append("")

    # Key Metrics
    metrics: list[str] = []
    _add_dollar_metric(metrics, "Sales", s1.get("total_sales"), s1.get("total_sales_wow"))
    _add_int_metric(metrics, "Units", s1.get("total_unit_sales"), s1.get("total_unit_sales_wow"))
    _add_int_metric(metrics, "Page Views", s1.get("total_page_views"), s1.get("total_page_views_wow"))
    _add_dollar_metric(metrics, "Ad Spend", s2.get("total_ad_spend"), s2.get("total_ad_spend_wow"))
    _add_dollar_metric(metrics, "Ad Sales", s2.get("total_ad_sales"), s2.get("total_ad_sales_wow"))
    _add_pct_metric(metrics, "ACoS", s2.get("acos"))
    _add_pct_metric(metrics, "TACoS", s2.get("tacos"))
    _add_float_metric(metrics, "Weeks of Stock", s3.get("weeks_of_stock"))
    _add_pct_metric(metrics, "Return Rate", s3.get("return_rate"))

    if metrics:
        lines.append("*Key Metrics*")
        lines.extend(metrics)

    # Wins
    if wins:
        lines.append("")
        lines.append("*Wins*")
        for w in wins:
            lines.append(f"• {w}")

    # Concerns
    if concerns:
        lines.append("")
        lines.append("*Concerns*")
        for c in concerns:
            lines.append(f"• {c}")

    # Data Notes
    if notes:
        lines.append("")
        lines.append("*Data Notes*")
        for n in notes:
            lines.append(f"• {n}")

    # Footer
    source_run_at = digest.get("source_run_at")
    if source_run_at:
        lines.append("")
        lines.append(f"_Snapshot taken {source_run_at}_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_wow(wow: float | None) -> str:
    if wow is None:
        return ""
    sign = "+" if wow >= 0 else ""
    return f" ({sign}{wow:.0%} WoW)"


def _fmt_dollar(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _add_dollar_metric(
    lines: list[str], label: str, value: float | None, wow: float | None = None
) -> None:
    if value is None or value == 0:
        return
    lines.append(f"  {label}: {_fmt_dollar(value)}{_fmt_wow(wow)}")


def _add_int_metric(
    lines: list[str], label: str, value: int | float | None, wow: float | None = None
) -> None:
    if value is None or value == 0:
        return
    lines.append(f"  {label}: {int(value):,}{_fmt_wow(wow)}")


def _add_pct_metric(lines: list[str], label: str, value: float | None) -> None:
    if value is None:
        return
    lines.append(f"  {label}: {value:.0%}")


def _add_float_metric(lines: list[str], label: str, value: float | None) -> None:
    if value is None:
        return
    lines.append(f"  {label}: {value:.1f}")
