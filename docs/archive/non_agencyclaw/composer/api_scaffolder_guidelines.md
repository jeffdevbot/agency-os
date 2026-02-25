# API Scaffolder Guidelines

These guidelines should be used by the API Scaffolder agent when creating new Composer API routes.

## Mandatory Template

All new Composer API routes MUST follow this template:

```typescript
import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireOrganizationId, isUuid } from "@/lib/composer/serverUtils";

// Define TypeScript interface for database row
interface [ResourceName]Row {
  id: string;
  organization_id: string;
  // ... all other fields from database table
  created_at: string;
  updated_at: string;
}

/**
 * [METHOD] /api/composer/[resource]/[param]
 * [Description of what this endpoint does]
 * 
 * Requirements:
 * - [List any status or validation requirements]
 * 
 * Returns:
 * - Success: { [resourceName]: [ResourceName]Row }
 * - Error: { error: string }
 */
export async function [METHOD](
  request: NextRequest,
  context: { params: Promise<{ [paramName]?: string }> }
): Promise<NextResponse> {
  // 1. PARAMETER VALIDATION
  const { [paramName] } = await context.params;

  if (![paramName] || !isUuid([paramName])) {
    return NextResponse.json(
      { error: "Invalid [resource] ID" },
      { status: 400 }
    );
  }

  // 2. AUTHENTICATION (REQUIRED - DO NOT SKIP!)
  const supabase = await createSupabaseRouteClient();
  const result = await requireOrganizationId(supabase);
  
  if (result.error) return result.error;
  
  const organizationId = result.organizationId;

  // 3. REQUEST BODY PARSING (if POST/PUT/PATCH)
  let body: { /* define expected shape */ };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 }
    );
  }

  // 4. FETCH EXISTING DATA (if needed)
  const { data: existing, error: fetchError } = await supabase
    .from("[table_name]")
    .select("*")
    .eq("id", [paramName])
    .eq("organization_id", organizationId)
    .single<[ResourceName]Row>();

  if (fetchError || !existing) {
    return NextResponse.json(
      { error: "[Resource] not found or access denied" },
      { status: 404 }
    );
  }

  // 5. BUSINESS LOGIC VALIDATION
  if (existing.status !== "expected_status") {
    return NextResponse.json(
      {
        error: "Cannot perform this operation with current status",
        currentStatus: existing.status,
        requiredStatus: "expected_status",
      },
      { status: 400 }
    );
  }

  // 6. PERFORM DATABASE OPERATION
  const { data: updated, error: updateError } = await supabase
    .from("[table_name]")
    .update({
      // ... fields to update
      updated_at: new Date().toISOString(),
    })
    .eq("id", [paramName])
    .eq("organization_id", organizationId)
    .select("*")
    .single<[ResourceName]Row>();

  if (updateError || !updated) {
    return NextResponse.json(
      { error: "Failed to update [resource]" },
      { status: 500 }
    );
  }

  // 7. RETURN SUCCESS RESPONSE
  return NextResponse.json({ [resourceName]: updated });
}
```

## Critical Requirements

### 1. ALWAYS Use Authentication Helper

**✅ CORRECT:**
```typescript
const supabase = await createSupabaseRouteClient();
const result = await requireOrganizationId(supabase);

if (result.error) return result.error;

const organizationId = result.organizationId; // Type is string, not string | null
```

**❌ WRONG (causes TypeScript errors):**
```typescript
const organizationId = resolveComposerOrgIdFromSession(session);
// Missing null check - will fail TypeScript compilation!
```

**❌ ALSO WRONG (missing helper import):**
```typescript
const organizationId = resolveComposerOrgIdFromSession(session);

if (!organizationId) {
  return NextResponse.json({ error: "Organization not found" }, { status: 401 });
}
// This works but requireOrganizationId() is preferred for consistency
```

### 2. ALWAYS Define Type Interfaces

```typescript
✅ CORRECT:
interface KeywordPoolRow {
  id: string;
  organization_id: string;
  project_id: string;
  pool_type: string;
  status: string;
  raw_keywords: string[];
  created_at: string;
  updated_at: string;
}

const { data } = await supabase
  .from("composer_keyword_pools")
  .select("*")
  .single<KeywordPoolRow>();  // Explicit type
```

```typescript
❌ WRONG:
const { data } = await supabase
  .from("composer_keyword_pools")
  .select("*")
  .single();  // Type is 'any' - no safety!
```

### 3. ALWAYS Validate Parameters

```typescript
✅ CORRECT:
if (!poolId || !isUuid(poolId)) {
  return NextResponse.json(
    { error: "Invalid pool ID" },
    { status: 400 }
  );
}
```

```typescript
❌ WRONG:
// Skipping validation - route will crash on invalid input
```

### 4. ALWAYS Include JSDoc Comments

```typescript
✅ CORRECT:
/**
 * POST /api/composer/keyword-pools/:id/approve-grouping
 * Approves the keyword grouping plan, allowing progression to next step
 * 
 * Requirements:
 * - Pool must have status 'grouped' (cannot skip cleanup approval)
 * - Updates pool status and sets approved_at timestamp
 * 
 * Returns:
 * - Success: { pool: ComposerKeywordPool }
 * - Error: { error: string, currentStatus?: string, requiredStatus?: string }
 */
export async function POST(...) {
```

## Common Patterns

### Status Validation

```typescript
// Validate pool has correct status before operation
if (pool.status !== "cleaned") {
  return NextResponse.json(
    {
      error: "Cannot generate grouping plan until cleanup is approved",
      currentStatus: pool.status,
      requiredStatus: "cleaned",
    },
    { status: 400 }
  );
}
```

### Optimistic Locking (Recommended for Update Operations)

```typescript
const { data: updated, error: updateError } = await supabase
  .from("composer_keyword_pools")
  .update({
    status: "new_status",
    updated_at: new Date().toISOString(),
  })
  .eq("id", poolId)
  .eq("organization_id", organizationId)
  .eq("updated_at", existing.updated_at)  // Optimistic lock
  .select("*")
  .single<PoolRow>();

// Check if update succeeded (no rows = concurrent modification)
if (!updated) {
  return NextResponse.json(
    {
      error: "Concurrent update detected. Please refresh and try again.",
      code: "CONCURRENT_MODIFICATION"
    },
    { status: 409 }
  );
}
```

### Bulk Inserts

```typescript
const groups = [...]; // Array of records to insert

const { error: insertError } = await supabase
  .from("composer_keyword_groups")
  .insert(groups);

if (insertError) {
  return NextResponse.json(
    { error: "Failed to create keyword groups", details: insertError.message },
    { status: 500 }
  );
}
```

## File Structure

New routes should follow Next.js App Router conventions:

```
frontend-web/src/app/api/composer/
├── keyword-pools/
│   ├── [poolId]/
│   │   ├── route.ts              # GET, PUT, DELETE for single pool
│   │   ├── grouping-plan/
│   │   │   └── route.ts          # POST - generate grouping
│   │   ├── groups/
│   │   │   └── route.ts          # GET - fetch groups
│   │   ├── group-overrides/
│   │   │   └── route.ts          # POST, DELETE - manage overrides
│   │   └── approve-grouping/
│   │       └── route.ts          # POST, DELETE - approve/unapprove
│   └── route.ts                  # GET (list), POST (create)
```

## Testing Checklist

Before submitting new routes:

- [ ] TypeScript compiles without errors (`npx tsc --noEmit`)
- [ ] Route has JSDoc comment describing purpose
- [ ] Uses `requireOrganizationId()` helper for auth
- [ ] Validates all route parameters (UUIDs, etc.)
- [ ] Defines TypeScript interface for database rows
- [ ] Includes business logic validation (status checks, etc.)
- [ ] Returns appropriate HTTP status codes
- [ ] Handles errors gracefully with descriptive messages
- [ ] Pre-commit hook passes

## References

- [Composer API Standards](/docs/composer/api_standards.md) - Comprehensive guide
- [Server Utils](/frontend-web/src/lib/composer/serverUtils.ts) - Helper functions
- [Next.js Route Handlers](https://nextjs.org/docs/app/building-your-application/routing/route-handlers) - Official docs
