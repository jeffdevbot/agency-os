# Scribe — Stage B Topics (Slice Spec)

Scribe Stage B turns Stage A inputs into 8 candidate topics per SKU and lets the user pick the best 5 that will feed Stage C.

---

## 1. Goals
- Generate intelligent topic angles per SKU.
- Make it easy to skim 8 candidates and pick 5.
- Ensure every SKU has enough direction before generating copy.

## 2. Inputs (per SKU)
- SKU code, product name, variant attributes
- Brand tone, target audience
- Supplied content
- Words to avoid
- Keywords (max 10)
- Customer questions

## 3. LLM Behavior (high level)
- Question-first: primarily grounds topics in the customer questions; internally clusters questions into themes (not persisted).
- Generates up to 8 topics covering the key themes.
- Each topic: `title` + one-sentence `description`.
- Incorporates keywords and brand tone when natural; avoids forbidden words.

### Prompt & Output (standard)
```
You are an Amazon listing strategist. Generate 1–8 distinct, short, high-intent topic angles for this SKU. These will be shown to the user, who will select the best 5 for Stage C copy generation.

RULES:
1) CUSTOMER QUESTIONS are the #1 source. Prioritize them above everything else. If no questions, use supplied_content, keywords, brand tone, target audience, and variant attributes.
2) Internally group similar questions into 3–6 themes before ideation (not shown in output).
3) For each theme, propose strong topic angles that:
   - Directly address the underlying concerns in the questions.
   - Incorporate KEYWORDS naturally, never forced.
   - Respect BRAND TONE and TARGET AUDIENCE.
   - Use PRODUCT NAME, VARIANT ATTRIBUTES, and SUPPLIED CONTENT for nuance.
4) Avoid all terms listed in WORDS_TO_AVOID.
5) No safety risks, no prohibited claims.
6) Each topic must have:
   - a short “angle-style” TITLE (max ~8 words)
   - exactly three bullet sentences in DESCRIPTION (1 sentence per bullet), explaining why that angle matters; prefix each with "• " and separate with newlines.
7) No duplicates. No fluff. No generic feature lists.

INPUTS:
Product Name: {{product_name}}
SKU: {{sku_code}}
ASIN: {{asin}}
Brand Tone: {{brand_tone}}
Target Audience: {{target_audience}}
Variant Attributes: {{variant_attributes}}   # e.g., Color=Black | Capacity=10L
Supplied Content: {{supplied_content}}
Keywords: {{keywords | join(", ")}}
Customer Questions: {{questions | join(" | ")}}   # may be empty
Words to Avoid: {{words_to_avoid | join(", ")}}

OUTPUT (valid JSON only):
{
  "topics": [
    { "title": "...", "description": "• ...\n• ...\n• ..." }
  ]
}
```

## 4. Data Model Link
- Reuse `scribe_topics`; no new tables.
- 1..8 topics per SKU.
- `approved = true` → topic selected for Stage C.
- Stage C only sees `approved` topics, ordered by `topic_index`, limited to 5.

## 5. API & Job Summary
- `POST /projects/:id/generate-topics` → enqueue job, generate topics for all SKUs.
- `POST /projects/:id/skus/:skuId/regenerate-topics` → regenerate one SKU.
- `GET /projects/:id/topics?skuId=...` → list topics.
- `PATCH /projects/:id/topics/:topicId` → edit / reorder / approve topics.
- `POST /projects/:id/approve-topics` → validate and mark Stage B as approved.
- Job runner is shared with other Scribe generation jobs; only the prompt and insert target differ.
 - Regenerate behavior: delete existing topics for the SKU, generate a fresh set (selections cleared).

## 6. UI Summary (Stage B Surface)
- One Stage B screen per project.
- Per-SKU topic list: up to 8 rows; checkboxes to select (approved) topics; drag handles/arrows to reorder; selected count indicator “Selected X / 5 required”.
- Project-level status gate: Stage B approve button disabled until each SKU has 5 selected topics.

### ASCII wireframe (per SKU block)
```
┌───────────────────────────────────────────────────────────┐
│ SKU: MHCP-CHI-01   Product: Cold Plunge Chiller           │
│ Selected: 3 / 5 required      [Regenerate]                │
├───────────────────────────────────────────────────────────┤
│ [ ] Topic 1 title (draggable)        ⋮                    │
│     • Bullet 1 (why it matters)                           │
│     • Bullet 2 (why it matters)                           │
│     • Bullet 3 (why it matters)                           │
│ [x] Topic 2 title (draggable)        ⋮                    │
│     • Bullet 1 (why it matters)                           │
│     • Bullet 2 (why it matters)                           │
│     • Bullet 3 (why it matters)                           │
│ [x] Topic 3 title (draggable)        ⋮                    │
│     • Bullet 1 (why it matters)                           │
│     • Bullet 2 (why it matters)                           │
│     • Bullet 3 (why it matters)                           │
│ [ ] Topic 4 title (draggable)        ⋮                    │
│     • Bullet 1 (why it matters)                           │
│     • Bullet 2 (why it matters)                           │
│     • Bullet 3 (why it matters)                           │
│ ... up to 8 rows ...                                      │
├───────────────────────────────────────────────────────────┤
│ [Approve Stage B]  (disabled until all SKUs have 5)       │
└───────────────────────────────────────────────────────────┘
```
