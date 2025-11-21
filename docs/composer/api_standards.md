# Composer API Standards

This document defines the required patterns and best practices for all Composer API routes.

## Table of Contents

1. [Organization ID Validation](#organization-id-validation)
2. [Helper Functions](#helper-functions)
3. [Type Safety](#type-safety)
4. [Error Responses](#error-responses)
5. [Examples](#examples)

---

## Organization ID Validation

### Problem

The `resolveComposerOrgIdFromSession(session)` function returns `string | null`, but database queries require `string`. Using it directly causes TypeScript compilation errors:

```typescript
❌ WRONG - Causes TypeScript Error:
const organizationId = resolveComposerOrgIdFromSession(session);
// Error: Type 'string | null' is not assignable to type 'string'
await supabase.from("table").select().eq("organization_id", organizationId);
```

### Required Pattern (Manual Approach)

Every API route MUST include this exact pattern after session check:

```typescript
✅ CORRECT:
const organizationId = resolveComposerOrgIdFromSession(session);

if (!organizationId) {
  return NextResponse.json({ error: "Organization not found" }, { status: 401 });
}

// Now TypeScript knows organizationId is string, not string | null
await supabase.from("table").select().eq("organization_id", organizationId);
```

### Recommended Pattern (Helper Function)

**Preferred approach:** Use the `requireOrganizationId` helper function to eliminate boilerplate:

```typescript
import { requireOrganizationId } from "@/lib/composer/serverUtils";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

export async function POST(request: NextRequest) {
  const supabase = await createSupabaseRouteClient();
  const result = await requireOrganizationId(supabase);
  
  if (result.error) return result.error;
  
  const organizationId = result.organizationId; // TypeScript knows this is string!
  
  // ... rest of route logic
}
```

**Benefits:**
- ✅ No manual null checks needed
- ✅ Automatic TypeScript type narrowing
- ✅ Consistent error responses
- ✅ Fewer lines of code

---

## Helper Functions

### `requireOrganizationId(supabase)`

Validates session and organization ID, returning either:
- Success: `{ organizationId: string, error: null }`
- Failure: `{ organizationId: null, error: NextResponse }`

**Location:** `/home/user/agency-os/frontend-web/src/lib/composer/serverUtils.ts`

**Usage Example:**

```typescript
export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id?: string }> }
) {
  const { id } = await context.params;
  
  if (!id || !isUuid(id)) {
    return NextResponse.json({ error: "Invalid ID" }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const result = await requireOrganizationId(supabase);
  
  if (result.error) return result.error;
  
  const organizationId = result.organizationId;
  
  // Fetch data
  const { data, error } = await supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("id", id)
    .eq("organization_id", organizationId)
    .single();
  
  if (error || !data) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  
  return NextResponse.json({ pool: data });
}
```

---

## Type Safety

### Always Define Return Types

```typescript
✅ CORRECT:
export async function GET(): Promise<NextResponse> {
  // ...
}

❌ WRONG:
export async function GET() {
  // No return type - harder to catch errors
}
```

### Use Explicit Type Annotations for Database Rows

```typescript
✅ CORRECT:
interface KeywordPoolRow {
  id: string;
  organization_id: string;
  project_id: string;
  // ... all fields
}

const { data } = await supabase
  .from("composer_keyword_pools")
  .select("*")
  .single<KeywordPoolRow>();

❌ WRONG:
const { data } = await supabase
  .from("composer_keyword_pools")
  .select("*")
  .single(); // Type is 'any' - no type safety
```

---

## Error Responses

### Standard Error Format

All error responses should follow this format:

```typescript
return NextResponse.json(
  { 
    error: "Human-readable error message",
    code?: "OPTIONAL_ERROR_CODE",  // For programmatic handling
    details?: { /* additional context */ }
  },
  { status: 400 | 401 | 403 | 404 | 409 | 500 }
);
```

### HTTP Status Codes

- `400` - Bad Request (invalid input, validation errors)
- `401` - Unauthorized (no session or organization)
- `403` - Forbidden (has auth but not allowed)
- `404` - Not Found (resource doesn't exist)
- `409` - Conflict (concurrent modification, optimistic locking failure)
- `500` - Internal Server Error (unexpected failures)

### Example Error Responses

```typescript
// Invalid input
return NextResponse.json(
  { error: "Invalid pool ID format" },
  { status: 400 }
);

// Missing authentication
return NextResponse.json(
  { error: "Unauthorized" },
  { status: 401 }
);

// Resource not found
return NextResponse.json(
  { error: "Pool not found or access denied" },
  { status: 404 }
);

// Status validation failure
return NextResponse.json(
  {
    error: "Cannot approve grouping until grouping plan is generated",
    currentStatus: pool.status,
    requiredStatus: "grouped",
  },
  { status: 400 }
);

// Optimistic locking conflict
return NextResponse.json(
  {
    error: "Concurrent update detected. Please refresh and try again.",
    code: "CONCURRENT_MODIFICATION"
  },
  { status: 409 }
);
```

---

## Examples

### Complete Route Template

```typescript
import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireOrganizationId, isUuid } from "@/lib/composer/serverUtils";

interface PoolRow {
  id: string;
  organization_id: string;
  project_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

/**
 * POST /api/composer/keyword-pools/:id/action
 * Description of what this endpoint does
 */
export async function POST(
  request: NextRequest,
  context: { params: Promise<{ poolId?: string }> }
): Promise<NextResponse> {
  const { poolId } = await context.params;

  // 1. Validate route parameters
  if (!poolId || !isUuid(poolId)) {
    return NextResponse.json(
      { error: "Invalid pool ID" },
      { status: 400 }
    );
  }

  // 2. Authenticate and get organization ID
  const supabase = await createSupabaseRouteClient();
  const result = await requireOrganizationId(supabase);
  
  if (result.error) return result.error;
  
  const organizationId = result.organizationId;

  // 3. Parse request body (if needed)
  let body: { someField: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 }
    );
  }

  // 4. Fetch existing data
  const { data: pool, error: fetchError } = await supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single<PoolRow>();

  if (fetchError || !pool) {
    return NextResponse.json(
      { error: "Pool not found or access denied" },
      { status: 404 }
    );
  }

  // 5. Validate business logic
  if (pool.status !== "expected_status") {
    return NextResponse.json(
      {
        error: "Invalid pool status for this operation",
        currentStatus: pool.status,
        requiredStatus: "expected_status",
      },
      { status: 400 }
    );
  }

  // 6. Perform operation
  const { data: updated, error: updateError } = await supabase
    .from("composer_keyword_pools")
    .update({
      status: "new_status",
      updated_at: new Date().toISOString(),
    })
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .select("*")
    .single<PoolRow>();

  if (updateError || !updated) {
    return NextResponse.json(
      { error: "Failed to update pool" },
      { status: 500 }
    );
  }

  // 7. Return success response
  return NextResponse.json({ pool: updated });
}
```

---

## Pre-Commit Hook

To catch TypeScript errors before deployment, enable the pre-commit hook:

```bash
# Hook location: .claude/hooks/pre-commit.sh
# Automatically runs TypeScript type checking before each commit
# Prevents type errors from reaching Render deployment
```

**The hook will:**
- ✅ Run `tsc --noEmit` to check for type errors
- ✅ Block commits if errors are found
- ✅ Display errors with file locations for easy fixing

---

## Checklist for New Routes

Before submitting a PR with new API routes:

- [ ] Uses `requireOrganizationId()` helper OR manual null check
- [ ] Has explicit return type annotation
- [ ] Defines TypeScript interfaces for database rows
- [ ] Validates route parameters (UUIDs, etc.)
- [ ] Includes business logic validation (status checks, etc.)
- [ ] Returns appropriate HTTP status codes
- [ ] Has JSDoc comment describing endpoint purpose
- [ ] Pre-commit hook passes (no TypeScript errors)

---

## Migration Guide

### Converting Existing Routes

**Before:**
```typescript
const organizationId = resolveComposerOrgIdFromSession(session);

// Missing null check - TypeScript error!
await supabase.from("table").eq("organization_id", organizationId);
```

**After (Option 1 - Helper Function):**
```typescript
const result = await requireOrganizationId(supabase);
if (result.error) return result.error;

const organizationId = result.organizationId;
await supabase.from("table").eq("organization_id", organizationId);
```

**After (Option 2 - Manual Check):**
```typescript
const organizationId = resolveComposerOrgIdFromSession(session);

if (!organizationId) {
  return NextResponse.json({ error: "Organization not found" }, { status: 401 });
}

await supabase.from("table").eq("organization_id", organizationId);
```
