# Shared AI Service Plan

_Created: 2026-03-19_

## Current state note (2026-03-19)

This document is still a **plan**, not an implemented shared service.

What has changed since the initial draft:

1. The Claw backend adapter now successfully runs on `gpt-5-mini-2025-08-07` in production.
2. The Claw adapter already handles several GPT-5-specific quirks:
   - `max_completion_tokens`
   - no `temperature`
   - `reasoning_effort`
   - content-part response parsing
3. The frontend/shared OpenAI paths have **not** yet been migrated into one common backend AI service.
4. The architecture problem described below still stands: provider/model quirks remain too duplicated across the codebase.
5. This plan should now be read as the **internal Agency OS AI runtime plan**, not the entire long-term AI surface strategy.
6. The complementary external-surface plan now lives in:
   - [claude_primary_surface_plan.md](/Users/jeff/code/agency-os/docs/claude_primary_surface_plan.md)

## Why this document exists

We hit GPT-5 compatibility issues in The Claw because `max_tokens` became `max_completion_tokens` and `temperature` became unsupported — but only the backend adapter knew about it. The frontend adapter (`lib/composer/ai/openai.ts`) still sends `max_tokens` unconditionally and would break on GPT-5 models today.

More broadly: every AI feature in this repo talks to OpenAI through its own copy of the same HTTP call, with its own model defaults, its own parameter handling, and its own token logging wiring. When a provider changes behavior (as GPT-5 did), we play whack-a-mole across multiple files in multiple languages.

This plan proposes a shared AI service that eliminates that duplication for
Agency OS-owned app surfaces.

---

## 1. Current-state inventory

### Active AI features and their callsites

| Feature | File(s) | Side | Provider call | Tool use | Token logging | Request type |
|---------|---------|------|---------------|----------|---------------|--------------|
| **The Claw** (skill selection) | `theclaw/slack_minimal_runtime.py` | Backend | `theclaw/openai_client.py` | No (uses `response_format`) | Yes (`ai_token_usage` via backend logger) | Sync |
| **The Claw** (skill execution + tool loop) | `theclaw/slack_minimal_runtime.py` | Backend | `theclaw/openai_client.py` | Yes (function calling, up to 6 rounds) | Yes (`ai_token_usage` via backend logger) | Sync with multi-turn loop |
| **AdScope chat** | `api/adscope/chat/route.ts` | Frontend API route | `lib/composer/ai/openai.ts` | Yes (`switch_view` tool) | Yes (`ai_token_usage` via `usageLogger.ts`) | Sync |
| **Debrief extract** | `api/debrief/.../extract/route.ts` | Frontend API route | `lib/composer/ai/openai.ts` | No | Yes (`ai_token_usage` via `usageLogger.ts`) | Sync |
| **Debrief draft email** | `api/debrief/.../draft-email/route.ts` | Frontend API route | `lib/composer/ai/openai.ts` | No | Yes (`ai_token_usage` via `usageLogger.ts`) | Sync |
| **Scribe topics** | `lib/scribe/topicsGenerator.ts` | Frontend API route | `lib/composer/ai/openai.ts` | No | Yes (`ai_token_usage` via caller) | Sync (inside job processor) |
| **Scribe copy** | `lib/scribe/copyGenerator.ts` | Frontend API route | `lib/composer/ai/openai.ts` | No | Yes (`ai_token_usage` via caller) | Sync (inside job processor) |
| **Composer grouping** | `lib/composer/ai/groupKeywords.ts` | Frontend API route | `lib/composer/ai/openai.ts` | No | Partial (`composer_usage_events` table, separate schema) | Sync |
| **OpenAI costs dashboard** | `app/actions/get-openai-costs.ts` | Frontend server action | Direct `fetch()` to OpenAI admin API | N/A | N/A | Sync |

### AI adapters (the duplication)

**Backend adapter** — `backend-core/app/services/theclaw/openai_client.py`
- Raw `httpx` POST to OpenAI
- GPT-5 aware: switches `max_tokens` → `max_completion_tokens`, drops `temperature`
- Primary/fallback model logic via env vars
- Default model: `gpt-4o-mini`
- Returns structured `ChatCompletionResult` TypedDict with token counts

**Frontend adapter** — `frontend-web/src/lib/composer/ai/openai.ts`
- Raw `fetch()` POST to OpenAI
- **Not GPT-5 aware**: always sends `max_tokens` and `temperature` — will break on GPT-5
- Primary/fallback model logic via env vars
- Default model: `gpt-5.1-nano` (updated recently but parameter handling wasn't)
- Returns structured `ChatCompletionResult` with token counts
- Lives under `lib/composer/` despite being used by Scribe, Debrief, and AdScope

### Token logging (the fragmentation)

Three separate logging paths write to two different tables:

| Logger | Location | Target table | Used by |
|--------|----------|-------------|---------|
| `logUsage()` | `frontend-web/src/lib/ai/usageLogger.ts` | `ai_token_usage` | Debrief, AdScope, Scribe |
| `logUsageEvent()` | `frontend-web/src/lib/composer/ai/usageLogger.ts` | `composer_usage_events` | Composer (only) |
| `log_ai_token_usage()` | `backend-core/app/services/ai_token_usage_logger.py` | `ai_token_usage` | The Claw |

The Composer logger is a legacy artifact writing to a separate table. The other two write to the same table but with different schemas and field conventions.

---

## 2. Problems with the current setup

### P1: Provider parameter whack-a-mole
The frontend adapter still sends `max_tokens` unconditionally. GPT-5 rejects this — you must send `max_completion_tokens` instead. The backend adapter already handles this; the frontend doesn't. Every future provider quirk (Gemini's `maxOutputTokens`, Claude's `max_tokens` meaning something different) will require touching every adapter.

### P2: "Composer" is dead, its adapter isn't
`lib/composer/ai/openai.ts` is imported by 5 active features (Scribe, Debrief, AdScope, Composer grouping). Composer the product is deprecated. New engineers will not know to look inside `lib/composer/` for the AI utility that Debrief uses.

### P3: Frontend API routes talk directly to OpenAI
Debrief, AdScope, and Scribe all call OpenAI from Next.js API routes using `fetch()`. This means:
- The OpenAI API key is loaded in the frontend runtime (server-side only, but still)
- Each route does its own error handling, retry logic, and token logging
- We can't add cross-cutting concerns (rate limiting, cost controls, request logging) without touching every route

### P4: Two usage logging tables
Composer logs to `composer_usage_events`. Everything else logs to `ai_token_usage`. The Command Center tokens page reads from `ai_token_usage` only, so Composer usage is invisible in cost reporting.

### P5: No path to multi-provider
Every callsite is hardcoded to `api.openai.com`. Adding Gemini or Claude means either duplicating the adapter again or retrofitting every callsite.

### P6: One model for all workloads
Backend defaults to `gpt-4o-mini`. Frontend defaults to `gpt-5.1-nano`. Both read `OPENAI_MODEL_PRIMARY` but have different fallback defaults. Scribe copy generation, Claw routing, and Debrief JSON extraction all have fundamentally different model requirements (prose quality vs speed/cost vs schema adherence vs tool-calling) but share one blunt env var. There's no way for a feature to declare what kind of model it needs — it gets whatever the global default says.

---

## 3. Recommended target architecture

### Name: `ai-service` (backend module: `app/services/ai/`)

A single backend Python module that owns all LLM communication. Frontend features call it through a thin internal API endpoint rather than talking to providers directly.

### Scope clarification

This service should be the shared AI runtime for:

1. The Claw
2. Scribe
3. Debrief
4. AdScope
5. other Agency OS-owned app surfaces

It should **not** be treated as the only top-level abstraction for the
company's future AI strategy.

There is now a second complementary layer to plan for:

1. a private `agency-os` MCP / integration layer for Claude.ai first
2. potentially other LLM-native web surfaces later

That external integration layer should sit beside this internal AI service, not
replace it.

### What belongs in the AI service

| Responsibility | Why centralized |
|---------------|-----------------|
| Provider HTTP calls | One place to handle `max_tokens` vs `max_completion_tokens`, auth, timeouts, retries |
| Model routing | "Give me a fast model" vs "give me a capable model" — resolved centrally based on env config |
| Parameter normalization | Temperature, token limits, response format — validated and adapted per provider/model |
| Token usage logging | Every call automatically logged to `ai_token_usage` — callers don't wire it |
| Primary/fallback logic | Retry on different model if primary fails |
| Provider abstraction | OpenAI today, Gemini/Claude later — callers don't know or care |
| Cost controls | Future: per-user rate limits, spend caps, circuit breakers |

### What stays feature-specific

| Responsibility | Why not centralized |
|---------------|---------------------|
| Prompt construction | Each feature owns its prompts, system messages, and context assembly |
| Tool definitions | Features define their own function-calling tools |
| Response parsing | Each feature interprets the LLM output its own way |
| Orchestration logic | Multi-turn loops, skill selection, job processing — all feature-level |
| Business logic | What to do with the AI response is not the AI service's job |

### Core interface (Python)

```python
# app/services/ai/completions.py

class CompletionRequest:
    messages: list[ChatMessage]
    lane: Literal["fast", "writing", "extraction", "agent"] = "fast"
    model: str | None = None              # override — skips lane resolution
    temperature: float | None = None      # None = provider/lane default
    max_output_tokens: int | None = None
    tools: list[dict] | None = None
    response_format: dict | None = None
    # Logging context
    tool: str                             # "theclaw", "adscope", "scribe", etc.
    user_id: str | None = None
    meta: dict | None = None

class CompletionResult:
    content: str
    tool_calls: list[dict] | None
    tokens_in: int
    tokens_out: int
    tokens_total: int
    model: str
    duration_ms: int

async def complete(request: CompletionRequest) -> CompletionResult:
    """Single entry point for all LLM calls. Handles provider quirks,
    model resolution, fallback, and usage logging internally."""
```

### Provider normalization (the GPT-5 problem, solved once)

```python
# app/services/ai/providers/openai.py

def _build_payload(request: CompletionRequest, model: str) -> dict:
    payload = {"model": model, "messages": request.messages}

    # Temperature: GPT-5 doesn't support it
    if request.temperature is not None and _supports_temperature(model):
        payload["temperature"] = request.temperature

    # Token limit: GPT-5 uses max_completion_tokens
    if request.max_output_tokens is not None:
        key = "max_completion_tokens" if _uses_max_completion_tokens(model) else "max_tokens"
        payload[key] = request.max_output_tokens

    # ... tools, response_format, etc.
    return payload
```

New providers (Gemini, Claude) get their own file in `providers/` with the same normalization pattern. The `complete()` function dispatches based on which provider owns the resolved model.

Important: this provider abstraction is still valuable even if Claude.ai
becomes the main analyst-facing surface, because Agency OS will still have
owned surfaces and internal workflows that need direct model access.

### Model lanes instead of one global default

The current `OPENAI_MODEL_PRIMARY` / `OPENAI_MODEL_FALLBACK` setup pretends one model fits every workload. It doesn't. Scribe needs a model that writes well. Claw routing needs a model that's fast and cheap. Debrief extraction needs a model that follows JSON schemas reliably. The Claw agent loop needs a model that handles tool calling well.

Model **lanes** map workload characteristics to model choices:

| Lane | Env var | Default | Workload characteristics | Used by |
|------|---------|---------|------------------------|---------|
| `fast` | `AI_MODEL_FAST` | `gpt-4o-mini` | Cheap, low-latency, adequate reasoning. Routing, summaries, lightweight chat. | Claw skill selection, AdScope chat |
| `writing` | `AI_MODEL_WRITING` | `gpt-5.1-nano` | Strong prose quality, creative range, good at following style guidelines. | Scribe copy/topics, Debrief draft email |
| `extraction` | `AI_MODEL_EXTRACTION` | `gpt-4o-mini` | Reliable structured/JSON output, follows schemas tightly, low cost. | Debrief task extraction, any future structured parsing |
| `agent` | `AI_MODEL_AGENT` | `gpt-5.1-nano` | Strong tool-calling, multi-step reasoning, handles complex instructions. | Claw skill execution + tool loop |

```python
# app/services/ai/config.py

ModelLane = Literal["fast", "writing", "extraction", "agent"]

_LANE_DEFAULTS: dict[ModelLane, str] = {
    "fast": "gpt-4o-mini",
    "writing": "gpt-5.1-nano",
    "extraction": "gpt-4o-mini",
    "agent": "gpt-5.1-nano",
}

_LANE_ENV_VARS: dict[ModelLane, str] = {
    "fast": "AI_MODEL_FAST",
    "writing": "AI_MODEL_WRITING",
    "extraction": "AI_MODEL_EXTRACTION",
    "agent": "AI_MODEL_AGENT",
}

def resolve_model(lane: ModelLane, override: str | None = None) -> str:
    """Resolve the model for a given lane. Explicit override wins."""
    if override:
        return override
    env_var = _LANE_ENV_VARS[lane]
    return os.environ.get(env_var, "").strip() or _LANE_DEFAULTS[lane]
```

Each lane can also have its own fallback (`AI_MODEL_FAST_FALLBACK`, etc.) but we don't need to wire that until a lane actually needs it.

**Key property:** all four lanes can point to the same model today (`gpt-4o-mini` everywhere) and be tuned independently later. No feature code changes when you want to move Scribe to Claude and keep The Claw on OpenAI — you just change `AI_MODEL_WRITING=claude-sonnet-4-6`.

**Backward compatibility:** during migration, `OPENAI_MODEL_PRIMARY` is read as a fallback for any lane that doesn't have its own env var set. This avoids a flag day where all env groups need updating at once.

### Frontend → backend routing

Frontend API routes stop calling OpenAI directly. Instead:

```
[Next.js API route] → [backend-core /internal/ai/complete] → [AI service] → [OpenAI]
```

The `/internal/ai/complete` endpoint is an internal-only backend route (no public access, authenticated by service-to-service token or the existing user auth). This means:
- OpenAI key only lives in backend-core
- Frontend API routes become thin orchestrators: build prompt, call backend, parse response
- Token logging happens automatically in one place
- Provider changes never touch frontend code

**For The Claw:** no change — it already calls through `backend-core`.

**For worker-sync:** if it needs AI in the future, it imports `app.services.ai` directly (same Python process or via the same internal endpoint).

---

## 4. Deployment/location decisions

| Question | Recommendation | Rationale |
|----------|---------------|-----------|
| Where does the service live? | `backend-core/app/services/ai/` | Python module, co-located with The Claw and future backend AI consumers |
| Should frontend routes call backend AI endpoints? | **Yes.** New internal endpoint `/internal/ai/complete` | Eliminates key duplication, centralizes logging and provider quirks |
| Should worker-sync use it? | **Yes.** Direct Python import (same venv) or HTTP call | Workers are the most likely place for Gemini/Claude experiments |
| What about browser/client code? | **Never.** All AI calls are server-side today and should stay that way | API keys must never reach the browser |

## 4.1 Relationship to the LLM-native head plan

Agency OS should now be thought of as having **two complementary AI layers**.

### Layer A: Shared internal AI runtime

This document covers:

1. model/provider/runtime normalization
2. centralized logging
3. lane-based model selection
4. owned application surfaces

Examples:

1. The Claw in Slack
2. Scribe
3. Debrief
4. AdScope

### Layer B: Private `agency-os` integration / MCP layer

This is covered in:

1. [claude_primary_surface_plan.md](/Users/jeff/code/agency-os/docs/claude_primary_surface_plan.md)

This layer covers:

1. tool exposure to Claude.ai first
2. a future ChatGPT or other compatible "head" later
3. user-scoped access to Agency OS data and workflows
4. durable tool/resource descriptions that do not depend on one specific web chat product

### Practical architecture split

The split should be:

1. backend business/data services remain the source of truth
2. shared AI runtime powers Agency OS-owned AI features
3. `agency-os` MCP server exposes tools/resources to external LLM-native surfaces
4. project instructions in Claude/ChatGPT stay thin and portable

This means:

1. do not move all intelligence into Claude-specific project instructions
2. do not assume the MCP layer removes the need for the internal AI runtime
3. do make the tool/data layer durable enough that the "head" can change over time

---

## 5. Migration plan

### Phase 0: Fix the immediate GPT-5 bug (do now)

**Risk: Low. Effort: 30 min.**

Port the GPT-5 parameter handling from `theclaw/openai_client.py` into `lib/composer/ai/openai.ts`. This is a band-aid, not architecture — but it unblocks anyone hitting GPT-5 on the frontend today.

- Add `_usesMaxCompletionTokens(model)` and `_supportsTemperature(model)` checks
- Apply them in `callOpenAIHttp()`
- This fix gets thrown away when Phase 2 lands, but it prevents breakage now

### Phase 1: Create the backend AI service module (foundation)

**Risk: Low. Effort: 1-2 sessions.**

Create `backend-core/app/services/ai/` with:
- `completions.py` — `CompletionRequest`, `CompletionResult`, `complete()`
- `providers/openai.py` — OpenAI-specific HTTP call with all parameter normalization
- `config.py` — model lane resolution, env var reading, backward-compat `OPENAI_MODEL_PRIMARY` fallback
- `__init__.py` — public API surface

Migrate The Claw first:
- Replace `theclaw/openai_client.py` imports with `app.services.ai.complete()`
- Skill selection uses `lane="fast"`, skill execution uses `lane="agent"`
- Delete `theclaw/openai_client.py`
- The Claw's usage logging moves inside `complete()` — remove manual `_log_theclaw_usage()` calls

**Why The Claw first:** it's already backend-side, it already has GPT-5 handling, and it's the most actively developed feature. Low risk because we can run existing tests against the new service.

This phase remains valid even with the Claude-primary-surface direction,
because The Claw and other owned surfaces still benefit from a shared runtime.

### Phase 2: Add internal AI endpoint and migrate frontend features

**Risk: Medium. Effort: 2-3 sessions.**

Add `POST /internal/ai/complete` to `backend-core/app/routers/`:
- Accepts `CompletionRequest` as JSON body
- Returns `CompletionResult`
- Authenticated via existing user auth (request comes from Next.js API routes, which already have the user's session)

Migrate frontend features in this order:

1. **Debrief extract** (`lane="extraction"`) + **draft email** (`lane="writing"`) — simplest callsites, no tool use, easy to verify. Change the API routes to POST to backend instead of calling OpenAI directly.
2. **AdScope chat** (`lane="fast"`) — has tool use, but single-round. Moderate complexity.
3. **Scribe topics + copy** (`lane="writing"`) — higher volume, runs inside job processor. Test with a full generate cycle.
4. **Composer grouping** (`lane="fast"`) — lowest priority (Composer is deprecated). Migrate if easy, otherwise leave.

After migration:
- Delete `frontend-web/src/lib/composer/ai/openai.ts`
- Delete `frontend-web/src/lib/composer/ai/usageLogger.ts`
- Consolidate `frontend-web/src/lib/ai/usageLogger.ts` — may no longer be needed if all logging is backend-side

### Phase 3: Retire the Composer usage table

**Risk: Low. Effort: 30 min.**

- Composer grouping (if still alive) switches to `ai_token_usage`
- Drop or archive `composer_usage_events` table
- Command Center tokens page now sees all AI usage in one place

### Phase 4: Multi-provider support (when needed, not before)

**Risk: Low if Phase 1-2 are done. Effort: 1 session per provider.**

When we want Gemini or Claude:
- Add `providers/gemini.py` or `providers/anthropic.py`
- Model tier config resolves to provider-specific model IDs
- `complete()` dispatches based on model prefix or explicit provider field
- No feature code changes — callers still say `model_tier="capable"` and get whatever provider is configured

This is separate from exposing Agency OS tools to Claude.ai or ChatGPT via MCP.
The MCP/tool layer is a surface integration problem; this phase is an internal
runtime/provider problem.

---

## 6. Anti-patterns to stop

| Anti-pattern | What to do instead |
|-------------|-------------------|
| Frontend API routes calling OpenAI directly | Route through backend AI service |
| Importing from `lib/composer/ai/` for non-Composer features | Move to `lib/ai/` or (better) move to backend |
| Hardcoding `max_tokens` / `temperature` without model checks | AI service normalizes per model |
| Manual token logging at every callsite | AI service logs automatically |
| Two usage tables (`ai_token_usage` + `composer_usage_events`) | Single table, single logger |
| One global model env var for all workloads | Named lanes (`fast`, `writing`, `extraction`, `agent`) with independent env vars |
| Feature code knowing about provider URLs, auth headers, response shapes | AI service owns the provider boundary |

---

## 7. What this plan does NOT cover

- **Streaming responses.** No feature uses streaming today. When one does, add a `stream()` method to the AI service. Don't pre-build it.
- **Embeddings.** No feature uses embeddings today. Same approach — add when needed.
- **Image generation.** Not on the roadmap.
- **Prompt management / versioning.** Prompts stay in feature code. No prompt registry.
- **LLM evaluation / testing harness.** Out of scope for this plan.
- **Claude.ai / ChatGPT project setup.** Covered in the external-surface planning doc, not here.
- **Agency OS MCP server design.** Complementary plan, not part of this document's implementation scope.

---

## 8. File layout after Phase 2

```
backend-core/app/services/ai/
├── __init__.py              # Public API: complete()
├── completions.py           # CompletionRequest, CompletionResult, complete()
├── config.py                # Model tiers, env vars, provider selection
├── usage_logger.py          # Moved from ai_token_usage_logger.py
└── providers/
    ├── __init__.py
    └── openai.py            # OpenAI HTTP call, parameter normalization

backend-core/app/routers/
└── ai.py                    # POST /internal/ai/complete (internal endpoint)
```

The Claw's `theclaw/openai_client.py` is deleted. Frontend `lib/composer/ai/openai.ts` is deleted. Both usage loggers are consolidated into `ai/usage_logger.py`.
