from __future__ import annotations

from collections import Counter
from typing import Any

from openpyxl import Workbook
from supabase import Client

from .analytics import clean_query_str

SUMMARY_METADATA_COLUMN = "J"
SUMMARY_METADATA_ROWS = range(3, 8)
TERM_COLUMN = "AN"
TERM_FLAG_COLUMN = "AT"
AI_RECOMMENDATION_COLUMN = "AV"
AI_CONFIDENCE_COLUMN = "AW"
AI_REASON_COLUMN = "AX"
MONO_GRAM_COLUMN = "A"
MONO_FLAG_COLUMN = "K"
BI_GRAM_COLUMN = "N"
BI_FLAG_COLUMN = "X"
TRI_GRAM_COLUMN = "AA"
TRI_FLAG_COLUMN = "AK"


def _to_text(value: Any) -> str:
    return str(value or "").strip()


def _search_term_key(value: Any) -> str:
    return _to_text(value).casefold()


def _last_non_empty(sheet, col: str, start_row: int) -> int:
    max_row = sheet.max_row
    for row_idx in range(max_row, start_row - 1, -1):
        if sheet[f"{col}{row_idx}"].value not in (None, ""):
            return row_idx
    return start_row - 1


def _extract_summary_metadata(workbook: Workbook) -> dict[str, str | None]:
    summary = workbook["Summary"] if "Summary" in workbook.sheetnames else None
    metadata: dict[str, str | None] = {
        "preview_run_id": None,
        "model": None,
        "prompt_version": None,
        "spend_threshold": None,
    }
    if summary is None:
        return metadata

    prefixes = {
        "AI Preview Run: ": "preview_run_id",
        "AI Model: ": "model",
        "AI Prompt Version: ": "prompt_version",
        "AI Threshold: ": "spend_threshold",
    }
    for row_idx in SUMMARY_METADATA_ROWS:
        value = _to_text(summary[f"{SUMMARY_METADATA_COLUMN}{row_idx}"].value)
        for prefix, key in prefixes.items():
            if value.startswith(prefix):
                metadata[key] = value[len(prefix) :].strip() or None
                break
    return metadata


def _read_sheet_state(sheet) -> dict[str, Any]:
    exact_negatives: set[str] = set()
    reviewed_terms: dict[str, dict[str, str | None]] = {}

    last_term_row = max(
      _last_non_empty(sheet, TERM_COLUMN, 7),
      _last_non_empty(sheet, AI_RECOMMENDATION_COLUMN, 7),
    )
    for row_idx in range(7, last_term_row + 1):
        search_term = _to_text(sheet[f"{TERM_COLUMN}{row_idx}"].value)
        if not search_term:
            continue
        key = _search_term_key(search_term)
        reviewed_terms[key] = {
            "search_term": search_term,
            "final_flag": _to_text(sheet[f"{TERM_FLAG_COLUMN}{row_idx}"].value).upper() or None,
            "ai_recommendation": _to_text(sheet[f"{AI_RECOMMENDATION_COLUMN}{row_idx}"].value).upper() or None,
            "ai_confidence": _to_text(sheet[f"{AI_CONFIDENCE_COLUMN}{row_idx}"].value).upper() or None,
            "ai_reason_tag": _to_text(sheet[f"{AI_REASON_COLUMN}{row_idx}"].value) or None,
        }
        if reviewed_terms[key]["final_flag"] == "NE":
            exact_negatives.add(key)

    final_grams = {"mono": set(), "bi": set(), "tri": set()}
    gram_specs = (
        ("mono", MONO_GRAM_COLUMN, MONO_FLAG_COLUMN),
        ("bi", BI_GRAM_COLUMN, BI_FLAG_COLUMN),
        ("tri", TRI_GRAM_COLUMN, TRI_FLAG_COLUMN),
    )
    for bucket, gram_col, flag_col in gram_specs:
        last_row = _last_non_empty(sheet, flag_col, 7)
        for row_idx in range(7, last_row + 1):
            flag = _to_text(sheet[f"{flag_col}{row_idx}"].value).upper()
            gram = _to_text(sheet[f"{gram_col}{row_idx}"].value)
            if flag in {"NE", "NP"} and gram:
                final_grams[bucket].add(clean_query_str(gram))

    return {
        "exact_negatives": exact_negatives,
        "reviewed_terms": reviewed_terms,
        "final_grams": {key: sorted(values) for key, values in final_grams.items()},
    }


def _build_term_ngrams(search_term: str) -> dict[str, set[str]]:
    tokens = [token for token in clean_query_str(search_term).split(" ") if token]
    out: dict[str, set[str]] = {"mono": set(), "bi": set(), "tri": set()}
    for n, key in ((1, "mono"), (2, "bi"), (3, "tri")):
        if len(tokens) < n:
            continue
        out[key] = {" ".join(tokens[idx : idx + n]) for idx in range(len(tokens) - n + 1)}
    return out


def _build_override_payload(workbook: Workbook, preview_run: dict[str, Any]) -> dict[str, Any] | None:
    metadata = _extract_summary_metadata(workbook)
    preview_payload = preview_run.get("preview_payload")
    if not isinstance(preview_payload, dict):
        return None
    campaigns = preview_payload.get("campaigns")
    if not isinstance(campaigns, list):
        return None

    sheet_states = {
        _to_text(sheet["B1"].value or sheet.title): _read_sheet_state(sheet)
        for sheet in workbook.worksheets
        if sheet.title not in {"Summary", "NE Summary"}
    }

    term_status_counts: Counter[str] = Counter()
    gram_status_counts: Counter[str] = Counter()
    campaign_payloads: list[dict[str, Any]] = []

    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue
        campaign_name = _to_text(campaign.get("campaignName"))
        if not campaign_name:
            continue
        sheet_state = sheet_states.get(campaign_name)
        if not sheet_state:
            continue

        final_grams = {
            key: set(values)
            for key, values in (sheet_state.get("final_grams") or {}).items()
            if isinstance(values, list)
        }
        ai_prefills_raw = campaign.get("synthesizedPrefills") if isinstance(campaign.get("synthesizedPrefills"), dict) else {}
        ai_prefills = {
            "mono": sorted(
                clean_query_str(_to_text(item.get("gram")))
                for item in ai_prefills_raw.get("mono", [])
                if isinstance(item, dict) and _to_text(item.get("gram"))
            ),
            "bi": sorted(
                clean_query_str(_to_text(item.get("gram")))
                for item in ai_prefills_raw.get("bi", [])
                if isinstance(item, dict) and _to_text(item.get("gram"))
            ),
            "tri": sorted(
                clean_query_str(_to_text(item.get("gram")))
                for item in ai_prefills_raw.get("tri", [])
                if isinstance(item, dict) and _to_text(item.get("gram"))
            ),
        }

        term_diffs: list[dict[str, Any]] = []
        reviewed_terms = sheet_state.get("reviewed_terms") or {}
        exact_negatives = sheet_state.get("exact_negatives") or set()

        for evaluation in campaign.get("evaluations", []):
            if not isinstance(evaluation, dict):
                continue
            search_term = _to_text(evaluation.get("search_term"))
            if not search_term:
                continue
            search_term_key = _search_term_key(search_term)
            term_ngrams = _build_term_ngrams(search_term)
            matched_grams = {
                key: sorted(term_ngrams[key].intersection(final_grams.get(key, set())))
                for key in ("mono", "bi", "tri")
            }
            gram_matches_flat = [gram for grams in matched_grams.values() for gram in grams]
            analyst_source = (
                "exact"
                if search_term_key in exact_negatives
                else "gram"
                if gram_matches_flat
                else "none"
            )
            analyst_outcome = "negated" if analyst_source != "none" else "not_negated"
            ai_recommendation = _to_text(evaluation.get("recommendation")).upper()
            ai_outcome = "negated" if ai_recommendation == "NEGATE" else "not_negated"
            decision_status = "matched" if ai_outcome == analyst_outcome else "overridden"
            if ai_recommendation == "NEGATE" and analyst_outcome == "negated":
                term_status = "ai_negate_accepted"
            elif ai_recommendation == "NEGATE" and analyst_outcome == "not_negated":
                term_status = "ai_negate_rejected"
            elif ai_recommendation in {"KEEP", "REVIEW"} and analyst_outcome == "negated":
                term_status = "analyst_added_negative"
            else:
                term_status = "unchanged_non_negative"
            term_status_counts[term_status] += 1

            workbook_review = reviewed_terms.get(search_term_key, {})
            term_diffs.append(
                {
                    "search_term": search_term,
                    "ai_recommendation": ai_recommendation,
                    "ai_confidence": _to_text(evaluation.get("confidence")).upper() or workbook_review.get("ai_confidence"),
                    "ai_reason_tag": _to_text(evaluation.get("reason_tag")) or workbook_review.get("ai_reason_tag"),
                    "analyst_outcome": analyst_outcome,
                    "analyst_source": analyst_source,
                    "decision_status": decision_status,
                    "term_status": term_status,
                    "matched_grams": matched_grams,
                }
            )

        gram_diffs: dict[str, list[dict[str, Any]]] = {"mono": [], "bi": [], "tri": []}
        for bucket in ("mono", "bi", "tri"):
            ai_values = set(ai_prefills[bucket])
            final_values = final_grams.get(bucket, set())
            for gram in sorted(ai_values.union(final_values)):
                ai_present = gram in ai_values
                analyst_present = gram in final_values
                if ai_present and analyst_present:
                    status = "matched"
                elif ai_present and not analyst_present:
                    status = "removed_by_analyst"
                else:
                    status = "added_by_analyst"
                gram_status_counts[status] += 1
                gram_diffs[bucket].append(
                    {
                        "gram": gram,
                        "ai_present": ai_present,
                        "analyst_present": analyst_present,
                        "status": status,
                    }
                )

        campaign_payloads.append(
            {
                "campaign_name": campaign_name,
                "term_diffs": term_diffs,
                "gram_diffs": gram_diffs,
                "final_grams": {key: sorted(values) for key, values in final_grams.items()},
            }
        )

    if not campaign_payloads:
        return None

    return {
        "preview_run_id": _to_text(preview_run.get("id")) or metadata.get("preview_run_id"),
        "profile_id": _to_text(preview_run.get("profile_id")) or None,
        "model": _to_text(preview_run.get("model")) or metadata.get("model"),
        "prompt_version": _to_text(preview_run.get("prompt_version")) or metadata.get("prompt_version"),
        "workbook_metadata": metadata,
        "campaigns": campaign_payloads,
        "summary": {
            "campaigns_logged": len(campaign_payloads),
            "term_status_counts": dict(term_status_counts),
            "gram_status_counts": dict(gram_status_counts),
        },
    }


def persist_ai_override_capture(
    db: Client,
    workbook: Workbook,
    *,
    collected_by_auth_user_id: str | None,
    source_filename: str | None,
) -> dict[str, Any] | None:
    metadata = _extract_summary_metadata(workbook)
    preview_run_id = _to_text(metadata.get("preview_run_id"))
    if not preview_run_id:
        return None

    preview_response = (
        db.table("ngram_ai_preview_runs")
        .select("id,profile_id,model,prompt_version,preview_payload")
        .eq("id", preview_run_id)
        .limit(1)
        .execute()
    )
    preview_rows = preview_response.data if isinstance(preview_response.data, list) else []
    if not preview_rows or not isinstance(preview_rows[0], dict):
        return None

    payload = _build_override_payload(workbook, preview_rows[0])
    if not payload:
        return None

    insert_response = (
        db.table("ngram_ai_override_runs")
        .insert(
            {
                "preview_run_id": preview_rows[0]["id"],
                "profile_id": preview_rows[0]["profile_id"],
                "collected_by_auth_user_id": collected_by_auth_user_id,
                "source_filename": _to_text(source_filename) or None,
                "model": payload.get("model"),
                "prompt_version": payload.get("prompt_version"),
                "override_payload": payload,
            }
        )
        .select("id,created_at")
        .single()
        .execute()
    )
    data = insert_response.data if isinstance(insert_response.data, dict) else {}
    return {
        "id": data.get("id"),
        "created_at": data.get("created_at"),
        "preview_run_id": preview_run_id,
    }
