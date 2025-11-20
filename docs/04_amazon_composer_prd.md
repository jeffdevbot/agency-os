# 📘 PRD — Composer (Amazon Listing Content Generator)

**Version:** 1.6 — Updated with Multi-Product Mode  
**Product Area:** Agency OS → Tools → Composer  
**Status:** Ready for Engineering

## Overview
Composer is a guided, AI-powered workflow for generating Amazon listing content across any number of SKUs.

### Outputs
- Title
- Bullet Points
- Description
- Backend Keywords
- Optional multilingual listings

### Supported Structures
- Single products
- Traditional variation families
- Complex listings where distinct products share a parent ASIN

Composer automates repetitive tasks but preserves key checkpoints for accuracy, compliance, and approval.

## Goals

### 1.1 Primary Goals
- Replace manual template-building and multi-prompt workflows
- Support both simple and complex product structures
- Prevent data loss via autosave/versioning
- Produce Amazon-compliant content
- Allow multi-language generation
- Centralize product info, keywords, themes, and outputs in one tool

### 1.2 Secondary Goals
- Standardize VA workflow
- Reduce cognitive load
- Improve accuracy and speed
- Simplify client review

## Non-Goals
- Scraping Amazon URLs
- Competitor research automation
- A+ Content / Brand Store
- Amazon Ads or PackView API integration (manual import for now)
- AI image generation

## User Roles
- Team Member / VA – primary operator
- PM/Editor – reviewer/approver
- Client – optional viewing of finished content

## High-Level Workflow
1. Create Project
2. Product Info
3. Choose Content Strategy
4. Keyword Upload
5. Keyword Cleaning (Approval)
6. Keyword Grouping Plan (Approval)
7. Themes (5 Topics) per Product/Group (Approval)
8. Sample Generation (Approval)
9. Bulk Generation per SKU
10. Backend Keywords (Approval)
11. Multilingual Output (Optional)
12. Client Review
13. Export → Amazon

## Detailed Requirements

### 🟦 5.1 PROJECT SYSTEM (Autosave + Versioning)
**Autosave**
- Every change → debounced 500–1000ms save to DB
- LocalStorage backup in case network fails
- Persistent across refresh and devices

**Versioning**
- Save versions at major milestones:
  - Keywords cleaned
  - Keyword grouping set
  - Themes chosen
  - Sample approved
  - Bulk generated
  - Backend keywords generated

**Project Dashboard**
- “Resume Project” view showing:
  - Project Name
  - Last edited
  - Current step
  - Status badges

### 🟦 5.2 PRODUCT INFO STEP
**Required:**
- Project Name
- Client / Brand
- Marketplace(s): US, CA, UK, DE, FR, IT, ES, NL, PL, SE
- Product Category (Browse Node) – dropdown
- SKU Input

**Users can:**
- Upload CSV
- Paste spreadsheet data
- Enter manually

**CSV Template (columns optional)**
- sku (required)
- asin (required)
- parent_sku
- color
- size
- age_range
- material
- scent
- flavor
- character
- pattern
- ingredients
- weight
- dimensions
- pack_size
- custom_1 / custom_2 etc.

Composer treats every column beyond sku + asin as a dynamic attribute.

### 🟦 5.3 CONTENT STRATEGY SELECTION (IMPORTANT)
After SKUs are processed, user MUST choose:

**Choose Content Strategy:**
- ( ● ) Treat all SKUs as variations of ONE product
  - Shared keyword pool
  - Shared themes
  - Shared sample
  - Bulk generation per SKU
  - Per-SKU titles, backend keywords
- ( ○ ) Treat SKUs as DISTINCT products
  - Separate keyword pools per SKU or SKU group
  - Separate theme selection per SKU/group
  - Separate sample per SKU/group
  - Completely independent content workflows

**Distinct Products Mode**
- User can create SKU Groups, e.g.:
  - [ Group A: Main System ]
  - [ Group B: Accessory 1 ]
  - [ Group C: Rings ]
  - [ Group D: Bundle ]
- Each group goes through all subsequent steps independently.

**Key Attribute Highlights (all strategies)**
- Composer shows the detected attribute keys (from Product Info) in a table with four columns: Title, Bullets, Description, Backend Keywords.
- Users tick the surfaces where each attribute must be mentioned (e.g., color in Title + Backend, material only in Bullets).
- Selections persist on the project (`highlight_attributes` JSON) and flow into downstream generators even in Variation mode so attributes are only forced where requested.
- UI lives below the strategy toggle so users can make the decision before progressing.

### 🟦 5.4 OPTIONAL PRODUCT-LEVEL INFO
**Brand-Level**
- Brand tone / guidelines
- Words to highlight
- What NOT to say (blacklist words/phrases)

**Product-Level**
- Target audience
- Use cases
- Differentiators
- Safety/compliance notes
- Certifications

**Supplied Info**
- Paste product copy
- Upload files (PDF/spec)
- Notes textarea

**Manual FAQ (Rufus questions)**
- User manually enters common customer questions.

### 🟦 5.5 KEYWORD INGESTION
- Two keyword pools:
  - Description & Bullets
  - Titles
- User can:
  - Upload CSV
  - Paste
  - Manually add terms
  - Preview raw merged list.
- If in Distinct Product Mode, keyword upload appears per SKU group.

### 🟦 5.6 KEYWORD CLEANING (APPROVAL)
**System removes:**
- Duplicates
- Competitor brands
- Own brand name
- Banned terms
- Optional: colors / sizes
- Normalizes casing

**User can:**
- Review removed keywords
- Restore any
- Remove more manually
- Approval required.

If in Distinct Product Mode → treat each group independently.

### 🟦 5.7 KEYWORD GROUPING PLAN (APPROVAL)
**System analyzes:**
- Distinct attribute values
- Number of SKUs
- Variation structure

**Then suggests grouping:**
- Default:
  - Description/Bullets → grouped by best attribute (e.g., color) or single group
  - Titles → per SKU

**User can override to:**
- Single group
- Per SKU
- Per attribute
- Custom # of groups

- Preview grouping count + labels.
- Optional manual overrides: drag keywords between groups, add/delete groups, or remove phrases entirely. Overrides are logged (with before/after) and can be reset to the AI suggestion.
- Approval required.
- For Distinct Product Mode, each group has its own grouping plan.

### 🟦 5.8 THEMES (5 TOPICS)
**AI proposes 6–12 themes based on:**
- Cleaned keywords
- Supplied info
- FAQ
- Category

- User selects exactly 5 + edits explanations.
- Approval required.
- In Distinct Product Mode, each product group selects its own 5 themes.

### 🟦 5.9 SAMPLE CONTENT (APPROVAL)
**AI generates:**
- Description
- Bullets
- Title

**For:**
- Variation mode: one representative SKU
- Distinct mode: one sample per group

- User edits or regenerates → then approves.

### 🟦 5.10 BULK GENERATION
**AI generates content for:**
- Every SKU in variation mode
- Every SKU inside each group in distinct mode

**System flags:**
- Length violations
- Duplicate content
- Missing important keywords
- Banned words

**User can:**
- Edit per SKU
- Regenerate per SKU or per group
- Approve entire set

### 🟦 5.11 BACKEND KEYWORDS (APPROVAL)
For each SKU:
- Build backend keyword string using unused cleaned keywords
- Remove any terms already used in visible copy
- Enforce character/byte limits
- Remove banned words
- Trim/compress intelligently

- User can edit/regenerate.
- Approval required.

### 🟦 5.12 MULTILINGUAL OUTPUT (OPTIONAL)
- Supported languages: EN-UK, DE, FR, IT, ES, NL, PL, SE
- Modes:
  - Translate from English master (default)
  - Generate fresh local-SEO content (advanced)
- System enforces locale rules:
  - Byte limits
  - Punctuation restrictions (FR)
  - Cultural phrasing
  - Metric vs imperial
- User approves per language.

### 🟦 5.13 CLIENT REVIEW
- Generate client-facing page:
  - Clean design
  - Variant selector
  - Title + bullets + description
  - Backend keywords
  - Multilingual tabs
  - Comment thread
  - Approve/Reject

### 🟦 5.14 EXPORT
- Formats:
  - Amazon Flat File CSV
  - Master CSV (all SKUs)
  - Copy buttons (title/bullets/desc/backend)
  - PDF export for client
  - JSON export for internal use

## Technical Requirements

### 6.1 Data Storage (Supabase)
Tables:
- projects
- project_versions
- sku_variants
- sku_groups
- product_attributes
- keyword_pools
- cleaned_keywords
- keyword_groups
- topics
- generated_content
- backend_keywords
- locales
- client_reviews

### 6.2 Autosave
- Debounced writes
- LocalStorage fallback

### 6.3 AI Models
- GPT-5.1 (content)
- GPT-4.1-mini-high (keyword grouping)
- GPT-5.1 (translations)

### 6.4 Error Handling
- Retry queue
- Local backup
- Undo/rollback via versioning

## Open Issues / Future Enhancements
- Optional SKU attribute autodetection (parsing SKU codes)
- EU keyword ingestion
- Category-specific compliance templates
- Marketplace rulesets (DE byte weirdness, FR phrasing)
- A/B test mode

## Appendix — Screens to Build
- New Project
- Resume Project
- Product Info
- Content Strategy Selection
- Keyword Upload
- Keyword Cleanup
- Grouping Plan
- Grouping Preview
- Themes
- Sample Editor
- Bulk Editor
- Backend Keywords
- Multilingual Output
- Client Review
- Export
