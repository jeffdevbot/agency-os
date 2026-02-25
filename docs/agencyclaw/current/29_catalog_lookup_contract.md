# Catalog Lookup Skill Contract (C12C Prep)

Last updated: 2026-02-20

## 1. Purpose And Scope
`catalog_lookup` provides deterministic ASIN/SKU disambiguation support for mutation workflows that require product-level precision.

Scope for C12C:
- define the request/response contract,
- define deterministic matching/ranking semantics,
- define clarify/fail-closed safety behavior.

Out of scope for C12C prep:
- Slack runtime wiring,
- DB query implementation details,
- command routing or policy-gate changes.

## 2. Skill Inputs
Required:
- `client_id` (UUID)
- `query` (string; user-provided product hint, ASIN, SKU, or title fragment)

Optional:
- `brand_id` (UUID; narrows candidate set within client)
- `limit` (integer; default `10`, max recommended `25`)

Input contract:
```json
{
  "client_id": "uuid",
  "brand_id": "uuid | null",
  "query": "string",
  "limit": 10
}
```

## 3. Output Schema
`catalog_lookup` returns ranked candidates and a deterministic resolution state.

```json
{
  "candidates": [
    {
      "asin": "string | null",
      "sku": "string | null",
      "title": "string",
      "confidence": 0.0,
      "match_reason": "exact_asin | exact_sku | prefix_asin | prefix_sku | token_contains_title"
    }
  ],
  "resolution_status": "exact | ambiguous | none"
}
```

Field notes:
- `confidence` is normalized `0.0` to `1.0`.
- `candidates` is sorted by descending confidence, then deterministic tie-breaker.
- `resolution_status` semantics:
  - `exact`: one unambiguous exact identifier match.
  - `ambiguous`: one or more candidates exist but no single unambiguous exact match.
  - `none`: no candidates found.

## 4. Matching Strategy
Priority order:
1. Exact ASIN/SKU match.
2. Prefix ASIN/SKU match.
3. Token-contains title match.

Ranking rules:
- Higher-priority match families always rank above lower-priority families.
- Within family, rank by confidence then deterministic stable tiebreakers.
- Exact tier should usually produce high confidence (`>= 0.95`).

## 5. Safety Rules
- Never auto-pick a candidate when `resolution_status = "ambiguous"`.
- When `resolution_status = "none"`, mutation flow must block and ask for:
  - explicit ASIN/SKU from user, or
  - explicit user confirmation to proceed with identifier pending.
- Runtime must never silently invent ASIN/SKU values.
- If user proceeds with pending identifiers, downstream draft must include unresolved identifier fields and explicit follow-up action.

## 6. Performance Expectations
Targets:
- P50 response time under 250 ms for warm-cache, indexed lookup.
- P95 response time under 800 ms for bounded limit (`<= 25`).
- Candidate cap enforces bounded payload and deterministic response size.

Future index recommendations:
- composite index on `(client_id, brand_id, asin)`,
- composite index on `(client_id, brand_id, sku)`,
- optional trigram/text index for normalized title token matching.

## 7. Telemetry Requirements
Catalog lookup calls should write best-effort telemetry to `ai_token_usage` / runtime logs using:
- `tool='agencyclaw'`
- `skill_id='catalog_lookup'`

Suggested stage labels:
- `catalog_lookup_request`
- `catalog_lookup_match`
- `catalog_lookup_resolution`

Recommended metadata:
- `client_id`, `brand_id`, `query_length`, `limit`,
- `candidate_count`, `resolution_status`,
- latency metrics and trace `run_id` when available.
