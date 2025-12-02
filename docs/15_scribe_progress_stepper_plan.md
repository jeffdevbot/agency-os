# Scribe Progress Stepper — Implementation Plan

**Version:** 1.0
**Created:** 2025-11-26
**Purpose:** Add a visual progress stepper header to the Scribe project page showing workflow progression through Stages A → B → C.

---

## 1. Overview

Add a project-level header band with a horizontal stepper that shows users where they are in the 3-stage Scribe workflow. The stepper communicates progress, unlocks stages sequentially, and uses benefit-focused microcopy to "sell" the value of each stage.

**Key Goals:**
- Clear visual feedback on current stage and completion status
- Sequential unlock pattern (complete A to unlock B, etc.)
- Benefit-focused messaging that highlights Scribe's value
- Future-proof design for when Stages B/C are enabled

---

## 2. Placement & Layout

### 2.1 Header Band (Top Section)

Place a **project-level header band** at the very top of the Scribe project page, above all Stage A/B/C content.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Project Name]                      [Status: Draft] [Last updated: ...] │
│  "Turn messy briefs into Amazon-ready copy in 3 quick steps."           │
└─────────────────────────────────────────────────────────────────────────┘
```

**Left side:**
- Project name (large, bold)
- Tagline (small, muted text — see §6 for options)

**Right side:**
- Project status pill (e.g., "Draft", "Stage A Approved", "Archived")
- Last updated timestamp (optional, small muted text)

---

### 2.2 Stepper Band (Below Header)

Directly under the header, render a **3-step horizontal stepper**.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  ● Stage A — Product Data     ○ Stage B — Topics     ○ Stage C — Copy   │
│  Add product details           Shape the angles      Generate titles     │
└─────────────────────────────────────────────────────────────────────────┘
```

**Structure:**
- Three equally-spaced steps spanning the width
- Each step shows: icon/dot, stage label, sublabel (one line)
- Connected by a subtle horizontal line/progress bar (optional)

---

## 3. Stepper Structure

### 3.1 Three Steps (Always Visible)

1. **Stage A — Product Data**
2. **Stage B — Topic Ideas**
3. **Stage C — Listing Copy**

### 3.2 Per-Step Components

Each step has:

**Icon/Dot:**
- Filled circle for current/completed stages
- Outlined circle for locked/future stages
- Checkmark inside circle for completed stages

**Stage Label:**
- "Stage A" / "Stage B" / "Stage C" (bold, uppercase or small-caps)

**Sublabel (one line, ~30 chars max):**
- **Stage A:** "Add product details & guidance"
- **Stage B:** "Shape the angles we'll write to"
- **Stage C:** "Generate optimized titles & bullets"

**No "Coming soon" text** — stages are simply locked/grayed until unlocked.

---

## 4. Visual States per Stage

Use the project's `status` field to determine visual states for each stage.

### 4.1 Status: `draft`

- **Stage A:** Active (accent color, bold, filled dot)
- **Stage B:** Locked (gray dot + label, muted)
- **Stage C:** Locked (gray dot + label, muted)

**Locked stage hover tooltip:** "Unlock after Stage A."

---

### 4.2 Status: `stage_a_approved`

- **Stage A:** Completed (checkmark in dot, success color)
- **Stage B:** Active (accent color, bold, filled dot)
- **Stage C:** Locked (gray dot + label, muted)

**Locked stage hover tooltip:** "Unlock after Stage B."

---

### 4.3 Status: `stage_b_approved` (future)

- **Stage A:** Completed (checkmark)
- **Stage B:** Completed (checkmark)
- **Stage C:** Active (accent color, bold)

---

### 4.4 Status: `stage_c_approved` (future)

- **Stage A:** Completed (checkmark)
- **Stage B:** Completed (checkmark)
- **Stage C:** Completed (checkmark)

---

### 4.5 Status: `archived`

- All three steps: Muted/grayed out
- Project status pill shows "Archived"
- No interaction allowed

---

### 4.6 Visual Design Tokens

**Colors:**
- **Active:** `#0a6fd6` (primary blue) or accent color
- **Completed:** `#10b981` (emerald/success green)
- **Locked:** `#94a3b8` (slate-400, muted gray)
- **Archived:** `#64748b` (slate-500, darker muted gray)

**Dot/Icon Styles:**
- Active: Filled circle with accent color
- Completed: Filled circle with checkmark icon inside
- Locked: Outlined circle (border only), gray

**Typography:**
- Stage label: Bold, 12–14px, uppercase or small-caps
- Sublabel: Regular, 11–12px, muted color

---

## 5. Interaction Behavior

### 5.1 Clicking a Step

**If stage is unlocked:**
- Navigate to that stage's view:
  - Stage A: `/scribe/:projectId/stage-a` (or current `/scribe/:projectId` if Stage A is default)
  - Stage B: `/scribe/:projectId/stage-b` (future)
  - Stage C: `/scribe/:projectId/stage-c` (future)

**If stage is locked:**
- No navigation
- Show tooltip on hover: "Finish Stage A first" or "Finish Stage B first"

**If project is archived:**
- No interaction allowed
- Optional tooltip: "Archived projects are read-only"

---

### 5.2 Approve Button Animation

When the user clicks "Approve Stage A":
1. Update project status to `stage_a_approved`
2. Animate the stepper:
   - Stage A dot: transition to completed (checkmark appears)
   - Stage B dot: glow/pulse effect for 1–2 seconds to draw the eye
3. Show success toast (optional): "Stage A approved! Ready for Stage B."

**Implementation Notes:**
- Use CSS transitions for smooth state changes
- Add a subtle glow/pulse animation to the newly unlocked stage
- Consider a micro-celebration animation (e.g., confetti, subtle checkmark bounce)

---

## 6. Microcopy & Messaging

### 6.1 Header Tagline (Pick One)

**Option 1:** "Turn messy briefs into Amazon-ready copy in 3 quick steps."
**Option 2:** "From product spreadsheet to polished Amazon copy in three simple stages."
**Option 3:** "Your team's fast lane from product details to ready-to-paste Amazon copy."

**Recommendation:** Option 1 (shortest, most casual, benefit-focused)

---

### 6.2 Per-Stage Sublabels

**Stage A:** "Add product details & guidance"
**Stage B:** "Shape the angles we'll write to"
**Stage C:** "Generate optimized titles & bullets"

**Tone:** Benefit-focused, action-oriented, concise (under 40 chars).

---

### 6.3 Status Pill Text

- `draft` → "Draft"
- `stage_a_approved` → "Stage A Approved"
- `stage_b_approved` → "Stage B Approved" (future)
- `stage_c_approved` → "Approved" (future)
- `archived` → "Archived"

---

## 7. Implementation Tasks

### 7.1 Frontend Component

**File:** `frontend-web/src/app/scribe/[projectId]/components/ProgressStepper.tsx` (new)

**Props:**
```tsx
interface ProgressStepperProps {
  projectStatus: ScribeProjectStatus;
  projectName: string;
  lastUpdated?: string;
}
```

**Responsibilities:**
- Render header band with project name, tagline, status pill, last updated
- Render 3-step stepper with dots, labels, sublabels
- Apply visual states based on `projectStatus`
- Handle click interactions (navigation or locked tooltip)
- Animate transitions when status changes

---

### 7.2 Integration into Scribe Page

**File:** `frontend-web/src/app/scribe/[projectId]/page.tsx`

**Changes:**
1. Import `ProgressStepper` component
2. Place `<ProgressStepper />` at the top of the page, before the "Stage A" header
3. Pass `project.status`, `project.name`, and `project.updated_at` as props

---

### 7.3 Routing (Future-Proofing)

For now, all stages render on the same page (`/scribe/:projectId`). When Stages B/C are enabled:

**Option A:** Use tabs/panels on the same page (simpler, no routing changes)
**Option B:** Create separate routes:
- `/scribe/:projectId/stage-a`
- `/scribe/:projectId/stage-b`
- `/scribe/:projectId/stage-c`

**Recommendation:** Option A (tabs/panels) for simplicity; defer routing until Stage B/C UX is finalized.

---

### 7.4 Testing

**Manual Testing:**
1. Create a new project (status: `draft`) → verify Stage A is active, B/C are locked
2. Approve Stage A → verify Stage A shows checkmark, Stage B becomes active
3. Try clicking locked stages → verify tooltip appears, no navigation
4. Archive project → verify all stages are muted, status pill shows "Archived"

**Automated Testing (Optional):**
- Unit test `ProgressStepper` component with different `projectStatus` values
- Verify correct visual states for each status
- Verify click handlers fire correct navigation or tooltips

---

### 7.5 Accessibility

- Use semantic HTML: `<nav>` for stepper, `<button>` or `<a>` for clickable steps
- Add `aria-label` to each step: "Stage A: Product Data (active)", "Stage B: Topics (locked)", etc.
- Ensure keyboard navigation works (Tab to each step, Enter to activate)
- Add `aria-disabled="true"` to locked steps
- Ensure color contrast meets WCAG AA standards (text vs. background)

---

## 8. Future Enhancements

**When Stages B/C are enabled:**
1. Update stepper to show active/completed states for B/C
2. Add navigation to `/scribe/:projectId/stage-b` and `/stage-c` routes (or tabs)
3. Add "Approve Stage B" and "Approve Stage C" buttons to respective views
4. Animate transitions between stages (glow effect on newly unlocked stage)

**Optional Polish:**
- Add a subtle progress bar connecting the dots (fills as stages complete)
- Add micro-animations (e.g., checkmark bounce, confetti on approval)
- Add "Undo approval" button in stepper for quick rollback (if unapprove is common)

---

## 9. Visual Mockup (ASCII)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  MiHIGH Cold Plunge Project                     [Draft] [Last updated: 2 hrs]  │
│  Turn messy briefs into Amazon-ready copy in 3 quick steps.                    │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ●━━━━━━━━━━━━━━━━○━━━━━━━━━━━━━━━○                                          │
│   Stage A           Stage B          Stage C                                   │
│   Product Data      Topics           Listing Copy                              │
│   Add details       Shape angles     Generate titles                           │
│   (Active)          (Locked)         (Locked)                                  │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘

After approving Stage A:

┌────────────────────────────────────────────────────────────────────────────────┐
│  MiHIGH Cold Plunge Project                     [Stage A Approved] [2 hrs ago] │
│  Turn messy briefs into Amazon-ready copy in 3 quick steps.                    │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ✓━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━○                                          │
│   Stage A           Stage B          Stage C                                   │
│   Product Data      Topics           Listing Copy                              │
│   Add details       Shape angles     Generate titles                           │
│   (Complete)        (Active)         (Locked)                                  │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Design Notes

**Keep it lightweight:**
- Use existing Agency OS design tokens (colors, spacing, typography)
- Match the CTA button style (rounded-2xl, blue, shadowed hover)
- Use the same status pill style as the project list page

**Benefit-focused messaging:**
- Avoid technical jargon ("SKUs", "RLS", "API")
- Focus on outcomes ("Amazon-ready copy", "high-converting listings")
- Use action verbs ("Add", "Shape", "Generate")

**Progressive disclosure:**
- Don't show "Coming soon" or "Disabled" text — just gray out locked stages
- Use tooltips to explain why a stage is locked (only on hover)
- Keep the UI clean and uncluttered

---

**End of Plan**
