# Product Requirement Document: N-PAT

**Version:** 1.0
**Product Area:** Agency OS → Tools → N-PAT
**Status:** Ready for Review
**Route:** `tools.ecomlabs.ca/npat`

**Architecture:** Stateless (upload/download workflow)

---

## 1. Executive Summary

**N-PAT (Negative-Product Attribute Targeting)** is an Amazon PPC analysis tool designed to identify ASINs (Amazon Standard Identification Numbers) consuming ad spend that should be excluded from campaigns. It complements the N-Gram tool by providing the inverse analysis: where N-Gram focuses on keywords, N-PAT focuses exclusively on products.

### Primary Goals

1. **Filter Search Term Reports to ONLY ASINs** across all campaigns
2. **Integrate Helium10 ASIN Grabber** data for product enrichment (titles, brands, prices)
3. **Generate ASIN pipe strings** for bulk Amazon search and H10 lookup
4. **Create actionable negative targeting lists** ready for Amazon Ads upload

### The Core Problem

Currently, PPC teams manually review 6,000+ row Search Term Reports looking for ASINs (10-character alphanumeric codes like `B08XYZ123`) buried among thousands of keyword queries. These ASINs represent users clicking on competitor products or irrelevant products, consuming ad spend without driving desired outcomes.

**Manual workflow pain points:**
- No quick way to filter to ONLY ASINs across campaigns
- Can't see what products these ASINs represent (blind targeting)
- Copying individual ASINs to Amazon → Running Helium10 → Copy/paste back → Repeat
- No systematic way to generate negative targeting lists

**N-PAT solves this by:**
- Automatically filtering Search Term Reports to ASINs only
- Providing a paste zone for Helium10 data enrichment
- Auto-generating ASIN pipe strings (`B08X|B09Y|B0AZ`) for bulk lookup
- Extracting marked ASINs into formatted negative targeting summaries

---

## 2. Key Differences from N-Gram

N-PAT and N-Gram are **separate tools** with **inverse filtering logic**:

| Feature | N-Gram | N-PAT |
|---------|--------|-------|
| **Input** | Search Term Report | Search Term Report (same file) |
| **Filter** | EXCLUDES ASINs (keywords only) | ONLY ASINs (excludes keywords) |
| **Analysis** | Monogram/Bigram/Trigram word combos | Per-ASIN metrics with product data |
| **Enrichment** | None (keywords are self-explanatory) | Helium10 product data required |
| **Output Structure** | 3 tables per campaign (mono/bi/tri) | 1 table per campaign (ASINs) |
| **User Marks** | NE on keywords + scratchpad n-grams | NE on ASINs after product review |
| **Mental Model** | Keyword research & negative phrases | Product targeting & competitor exclusion |
| **Primary Users** | Catalog Strategists, Brand Managers | PPC Strategists, PPC Specialists |

### Why Separate Tools (Not Integrated)

1. **Different mental models**: Words vs. Products
2. **Different workflows**: N-gram generation vs. product lookup via Helium10
3. **Different user tasks**: Keyword specialists analyze words; PPC specialists analyze products
4. **Simpler to maintain**: Each tool can evolve independently
5. **Role-based access**: Not everyone needs both tools

---

## 3. User Roles & Personas

### Primary Users
**PPC Strategists & PPC Specialists** (internal Ecomlabs team)

**Needs:**
- Quickly identify competitor ASINs consuming ad spend
- Understand what products these ASINs represent
- Mark ASINs for negative targeting
- Export formatted lists for Amazon Ads upload

**Access:** N-PAT tool via `tools.ecomlabs.ca/npat`

---

## 4. Core Workflows

### Workflow 1: Generate N-PAT Workbook

**Actor:** PPC Specialist
**Steps:**

1. Download Search Term Report from Amazon Ads (30-day report, all campaigns)
2. Navigate to `tools.ecomlabs.ca/npat`
3. Upload Search Term Report (.xlsx, .xls, or .csv)
4. System processes file:
   - Parses columns (Query, Impression, Click, Spend, Order 14d, Sales 14d, Campaign Name)
   - **Filters to ONLY ASINs** using regex: `^[A-Z0-9]{10}$` (case-insensitive; ASINs uppercased for consistency)
   - Excludes campaigns containing "Ex.", "SDI", or "SDV" in name
   - Groups ASINs by campaign
   - Calculates metrics: CTR, CPC, CVR, ACOS
   - Generates Excel workbook with:
     - Summary sheet (campaign overview)
     - Per-campaign sheets with ASIN analysis
     - ASIN pipe string formula in row 2
     - H10 paste zone (columns M-V)
     - VLOOKUP enrichment formulas (columns W-AA)
     - NE/NP marking column (column AB)
5. User downloads `filename_npat.xlsx`

**Success:** Workbook opens without errors, ASIN pipe string is visible in row 2, all campaigns have dedicated sheets

---

### Workflow 2: Helium10 Enrichment (Manual)

**Actor:** PPC Specialist
**Steps:**

1. Open downloaded N-PAT workbook
2. For each campaign sheet:
   - **Copy ASIN pipe string** from cell B2 (e.g., `b08xyz123|b09abc456|b0a1def789`)
   - **Paste into Amazon search bar** (Amazon recognizes pipe-delimited ASINs)
   - **Run Helium10 ASIN Grabber** Chrome extension on search results page
   - H10 returns spreadsheet data:
     - ASIN
     - Product Title
     - Brand
     - Price
     - Star Rating
     - Number of Reviews
     - Sales Rank
     - BSR Category
     - Image URL
     - Product URL
   - **Copy H10 data** from extension popup
   - **Paste into columns M-V** (H10 Data Paste Zone) in N-PAT workbook
3. VLOOKUP formulas in columns W-AA automatically populate with matched data
4. User reviews enriched ASINs (now has product titles and brands visible)
5. User marks ASINs as **"NE"** (Negative Exact) in column AB if they should be excluded
6. User adds notes in column AC (Comments) - e.g., "Competitor product - Anker brand"

**Success:** Enrichment columns show product titles/brands for all ASINs, user can quickly identify competitors and irrelevant products

---

### Workflow 3: Export Negatives Summary

**Actor:** PPC Specialist
**Steps:**

1. Save filled N-PAT workbook after marking all "NE" ASINs
2. Return to `tools.ecomlabs.ca/npat`
3. Upload filled workbook to **Step 2** section
4. System processes workbook:
   - Parses all campaign sheets (skips "Summary")
   - Extracts ASINs marked "NE" in column AB
   - Reads enrichment columns W-AA (Title, Brand, Price, etc.)
   - Reads original metrics (Impression, Click, Spend, Order 14d, Sales 14d, CTR, CVR, CPC, ACOS — same set as N-Gram)
   - Generates summary Excel with columns:
     - Campaign
     - ASIN
     - Product Title (from H10 enrichment)
     - Brand (from H10 enrichment)
     - Impression
     - Click
     - Spend
     - Order 14d
     - Sales 14d
     - CTR
     - CVR
     - CPC
     - ACOS
5. User downloads `filename_negatives.xlsx`
6. User uploads to Amazon Ads as negative targeting list

**Success:** Negatives summary includes all marked ASINs with product context, formatted for Amazon Ads bulk upload

---

## 5. Campaign Sheet Layout (Detailed Specification)

### Helper Rows (Top of Sheet)

```
┌─────────────────────────────────────────────────────────────────┐
│ Row 1: Campaign:  [Brand X - Product Targeting Campaign]       │
│ Row 2: ASINs for H10:  [=TEXTJOIN("|",TRUE,B6:B5000)]  ← COPY │
│ Row 3: [Blank spacing row]                                     │
│ Row 4: [Column headers]                                        │
│ Row 5: [Blank row]                                             │
│ Row 6+: [Data rows start]                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Row 1:** Campaign name (bold, large font)
**Row 2:** ASIN pipe string generator (light blue background, thick border, monospace font)
**Row 3:** Blank spacing
**Row 4:** Column headers (blue background, white text, bold)
**Row 5:** Blank or instructions
**Row 6+:** Data rows with zebra striping

---

### Column Layout

#### Columns A-K: N-PAT Analysis (Main Data)

| Column | Field | Format | Description |
|--------|-------|--------|-------------|
| A | ASIN | Text, left-aligned | 10-character ASIN code |
| B | Impression | Number, center-aligned | Number of ad impressions |
| C | Click | Number, center-aligned | Number of clicks |
| D | Spend | Currency, 2 decimals | Ad spend in USD |
| E | Order 14d | Number, center-aligned | Orders within 14 days |
| F | Sales 14d | Currency, 2 decimals | Sales within 14 days |
| G | CTR | Percentage, 2 decimals | Click-through rate (Click/Impression) |
| H | CPC | Currency, 2 decimals | Cost per click (Spend/Click) |
| I | CVR | Percentage, 2 decimals | Conversion rate (Order/Click) |
| J | ACOS | Percentage, 2 decimals | Advertising cost of sale (Spend/Sales) |
| K | [Spacer] | Blank | Visual spacing |

---

#### Column L: Visual Separator

- Bold vertical line or gray background (#E0E0E0)
- Header label: **"← Analysis | H10 Data →"**
- Purpose: Clear visual boundary between analysis and enrichment zones

---

#### Columns M-V: H10 Data Paste Zone (User Fills Manually)

**Row 4 Header:** `PASTE HELIUM10 DATA HERE →` (bold, blue background #0066CC)
**Row 5 Instructions:** `1. Copy ASIN string from B2 → 2. Search Amazon → 3. Run H10 ASIN Grabber → 4. Paste data here`

**Expected H10 headers/order (example):** `Product Details | ASIN | URL | Image URL | Brand | Origin | Price $ | BSR | Ratings | Review Count`

| Column | Field | Description |
|--------|-------|-------------|
| M | ASIN | ASIN from H10 (for VLOOKUP matching) |
| N | Product Details | Product title/details from H10 |
| O | Brand | Brand name from H10 |
| P | Price | Current price from H10 |
| Q | Ratings | Star rating (1-5) from H10 |
| R | Review Count | Number of reviews from H10 |
| S | BSR | Best Seller Rank |
| T | Origin | Origin (if present) |
| U | Image URL | Product image URL from H10 |
| V | Product URL | Amazon product URL from H10 |

**User Action:** Paste Helium10 export directly into this zone (columns will align automatically; unused fields are ignored).

---

#### Columns W-AA: Enrichment (Auto-Populated via VLOOKUP)

These columns use formulas to match ASINs from column A with H10 data from columns M-V:

| Column | Field | Formula |
|--------|-------|---------|
| W | Title | `=IFERROR(VLOOKUP($A6,$M$6:$V$5000,2,FALSE),"")` |
| X | Brand | `=IFERROR(VLOOKUP($A6,$M$6:$V$5000,3,FALSE),"")` |
| Y | Price | `=IFERROR(VLOOKUP($A6,$M$6:$V$5000,4,FALSE),"")` |
| Z | Rating | `=IFERROR(VLOOKUP($A6,$M$6:$V$5000,5,FALSE),"")` |
| AA | Reviews | `=IFERROR(VLOOKUP($A6,$M$6:$V$5000,6,FALSE),"")` |

**Purpose:** Users see product data next to ASIN metrics without manual copying

---

#### Columns AB-AC: Action Columns

| Column | Field | Format | Description |
|--------|-------|--------|-------------|
| AB | NE/NP | Text input, center-aligned, gray header | User marks "NE" for negative exact targeting |
| AC | Comments | Text input, left-aligned, wrap text, gray header | User notes (e.g., "Competitor - Anker", "Wrong category") |

**User Action:** Mark ASINs as "NE" after reviewing enriched product data

---

### Formatting Details

**Header Row (Row 4):**
- Background: Blue (#0066CC)
- Text: White, bold, center-aligned
- Borders: All sides

**Data Rows (Row 6+):**
- Zebra striping: Alternating white and light gray (#F2F2F2)
- Borders: All cells
- Freeze panes: At row 5 (headers always visible when scrolling)

**Column Widths:**
- A (ASIN): 15
- B-F (Metrics): 12
- G-J (Calculated): 10
- K (Spacer): 3
- L (Separator): 3
- M (H10 ASIN): 15
- N (H10 Title): 60
- O (H10 Brand): 20
- P-V (H10 Data): 12
- W (Enriched Title): 60
- X (Enriched Brand): 20
- Y-AA (Enriched Data): 12
- AB (NE/NP): 10
- AC (Comments): 30

---

## 6. ASIN Pipe String Generator

### Implementation

**Location:** Cell B2 (immediately visible when opening campaign sheet)

**Formula:**
```excel
=TEXTJOIN("|",TRUE,UPPER(B6:B5000))
```

**Output Example:**
```
B08XYZ123|B09ABC456|B0A1DEF789|B07GHI012|B08MNO345|B0APQR678
```

### User Workflow

1. Open campaign sheet
2. Click cell B2 (formula result is visible, highlighted in light blue)
3. Copy value (Ctrl+C / Cmd+C)
4. Open Amazon.com
5. Paste into search bar (Amazon recognizes pipe-delimited ASINs)
6. Press Enter → Amazon shows all products in search results
7. Run **Helium10 ASIN Grabber** Chrome extension
8. Extension scrapes product data from search results
9. Copy H10 export data
10. Return to N-PAT workbook
11. Paste into columns M-V (H10 Data Paste Zone)
12. VLOOKUP formulas in columns W-AA auto-populate with matched data

### Formatting

- **Cell B2 Background:** Light blue (#E6F2FF)
- **Border:** Thick blue border (2px, #0066CC) to stand out
- **Font:** Courier New (monospace) for easy reading
- **Text Alignment:** Left
- **Wrap Text:** Disabled (single long line)
- **Cell Note/Comment:** *"Copy this string and paste into Amazon search, then run H10 ASIN Grabber"*

---

## 7. Summary Sheet

### Purpose

Provide high-level campaign overview before diving into individual sheets.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ N-PAT Summary                                                   │
│ Generated: 2025-11-21 14:30 PST                                 │
│ Version: 1.0.0                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Campaign                          │ ASINs │ Spend   │ Notes     │
├───────────────────────────────────┼───────┼─────────┼───────────┤
│ Brand X - Product Targeting       │  45   │ $1,234  │ [Link]    │
│ Brand Y - Competitor               │  23   │ $567    │ [Link]    │
│ Brand Z - Category                 │  67   │ $890    │ [Link]    │
└─────────────────────────────────────────────────────────────────┘
```

### Columns

1. **Campaign** (clickable link to campaign sheet) - Campaign name with internal link
2. **ASINs** (number, center-aligned) - Count of unique ASINs in campaign
3. **Total Spend** (currency, right-aligned) - Sum of ad spend across all ASINs
4. **Link** (internal) - Jumps to campaign sheet

### Functionality

- **Freeze panes:** On header row (row 1)
- **Autofilter:** All columns
- **Sorting:** By any column (default: Campaign name A-Z)
- **Color-coding:** Category colors (reuse N-Gram category detection logic)
- **Links:** Clicking campaign name navigates to that sheet

---

## 8. Technical Architecture

### Frontend

**Location:** `frontend-web/src/app/npat/page.tsx`
**Framework:** Next.js 14 (App Router) + React + TypeScript
**UI Library:** ShadcnUI components (match N-Gram styling)

**Features:**
- **2-step interface:**
  - Step 1: Generate N-PAT Workbook
  - Step 2: Upload Filled Workbook → Download Negatives Summary
- **Drag-and-drop file upload** (reuse N-Gram component)
- **Fun loading states** with rotating phrases (reuse N-Gram phrases):
  - "Reticulating splines"
  - "Calibrating flux capacitors"
  - "Engaging hyperdrive motivator"
  - etc. (15 total phrases rotating every 4.2 seconds)
- **Toast notifications** for success/error
- **Authentication** via Supabase (require login)
- **Header/CTA styling:** Reuse N-Gram header and button styles (typography, spacing, hover/disabled states) for consistency.

**State Management:**
- `selectedFile`: File | null (Step 1 upload)
- `selectedFilledFile`: File | null (Step 2 upload)
- `uploading`: boolean (Step 1 processing state)
- `collecting`: boolean (Step 2 processing state)
- `error`: string | null (Step 1 error message)
- `collectError`: string | null (Step 2 error message)
- `toast`: string | null (Success notification)

---

### Backend

**Location:** `backend-core/app/routers/npat.py`
**Framework:** Python FastAPI
**Dependencies:**
- `pandas` >= 2.2.2 (data processing)
- `numpy` >= 1.26.4 (calculations)
- `openpyxl` >= 3.1.2 (read Excel)
- `xlsxwriter` >= 3.2.0 (write Excel with formulas)
- `python-multipart` == 0.0.9 (file uploads)

**Endpoints:**

1. `GET /npat/healthz` - Health check
2. `POST /npat/process` - Generate N-PAT workbook
3. `POST /npat/collect` - Extract negatives summary

---

### Shared Services

#### Parser Service

**Location:** `backend-core/app/services/npat/parser.py`

**Functions:**
- `read_backview_path(path, original_name)` - Parse Search Term Report
- `_normalize_columns(df)` - Map column names to standard format
- `clean_numeric(col)` - Clean currency/number formats

**Key Difference from N-Gram:**
```python
# N-Gram filters OUT ASINs:
df = df[df["Query"].str.strip().str.lower().str.match(ASIN_RE) == False]

# N-PAT filters to ONLY ASINs:
ASIN_RE = re.compile(r"^[a-z0-9]{10}$", re.I)
df = df[df["Query"].str.strip().str.lower().str.match(ASIN_RE) == True]
```

---

#### Analytics Service

**Location:** `backend-core/app/services/npat/analytics.py`

**Functions:**
- `calculate_metrics(df)` - Calculate CTR, CPC, CVR, ACOS
- `derive_category(campaign_name)` - Detect category from campaign name (reuse N-Gram logic)

---

#### Workbook Service

**Location:** `backend-core/app/services/npat/workbook.py`

**Functions:**
- `build_npat_workbook(campaign_items, app_version)` - Main workbook generator
- `_write_summary_sheet(book, campaign_items)` - Create Summary sheet
- `_write_campaign_sheet(book, campaign_item)` - Create per-campaign sheet with:
  - Helper rows (campaign name + ASIN pipe string formula)
  - Main data table (columns A-K)
  - H10 paste zone (columns M-V)
  - VLOOKUP enrichment formulas (columns W-AA)
  - Action columns (AB-AC)
  - Formatting (zebra stripes, borders, freeze panes)

---

### Database

**No new tables needed** (stateless tool like N-Gram)

**Usage Logging:**
Uses existing `usage_logger` service:

```python
usage_logger.log({
    "user_id": user.get("sub"),
    "user_email": user.get("email"),
    "file_name": file.filename,
    "file_size_bytes": total,
    "rows_processed": int(df.shape[0]),
    "campaigns": len(campaign_items),
    "total_asins": sum([len(item["asins"]) for item in campaign_items]),
    "status": "success",
    "duration_ms": int((time.time() - started) * 1000),
    "app_version": settings.app_version,
})
```

---

## 9. API Surface

### Base Route: `/npat`

---

### `GET /npat/healthz`

**Purpose:** Health check endpoint

**Response:**
```json
{
  "ok": true
}
```

---

### `POST /npat/process`

**Purpose:** Generate N-PAT workbook from Search Term Report

**Request:**
- **Content-Type:** `multipart/form-data`
- **Body:** `file` (Search Term Report .xlsx, .xls, or .csv)
- **Auth:** `Authorization: Bearer {supabase_jwt}`

**Response:**
- **Content-Type:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **Body:** Excel file (binary)
- **Filename:** `{original_name}_npat.xlsx`

**Processing Steps:**
1. Parse uploaded file (Excel or CSV, header on row 9 for Excel)
2. Normalize column names
3. Clean numeric columns (remove commas, parentheses for negatives)
4. **Filter to ONLY ASINs** (10-character alphanumeric codes)
5. Exclude campaigns containing "Ex.", "SDI", or "SDV"
6. Group ASINs by campaign
7. Calculate derived metrics (CTR, CPC, CVR, ACOS)
8. Detect campaign categories (reuse N-Gram logic)
9. Generate Excel workbook with:
   - Summary sheet
   - Per-campaign sheets with H10 integration
   - ASIN pipe string formula in row 2
   - VLOOKUP enrichment formulas
   - NE/NP marking column
10. Log usage event
11. Enforce max upload size (40MB, aligned with N-Gram)
12. Return file as download

**Error Cases:**
- `400` - File parse error (invalid format, missing required columns)
- `413` - File too large (>40MB)
- `400` - No ASINs found in file
- `400` - No eligible campaigns (all filtered out)
- `500` - Workbook generation error

**Example Error Response:**
```json
{
  "detail": "No ASINs found in uploaded file. N-PAT requires ASIN data (10-character alphanumeric codes like B08XYZ123)."
}
```

---

### `POST /npat/collect`

**Purpose:** Extract negatives summary from filled N-PAT workbook

**Request:**
- **Content-Type:** `multipart/form-data`
- **Body:** `file` (Filled N-PAT workbook .xlsx)
- **Auth:** `Authorization: Bearer {supabase_jwt}`

**Response:**
- **Content-Type:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **Body:** Excel file (binary)
- **Filename:** `{original_name}_negatives.xlsx`

**Processing Steps:**
1. Parse uploaded workbook with `openpyxl` (data_only=True for formula values)
2. For each worksheet (skip "Summary"):
   - Read campaign name from cell B1
   - Find last non-empty row in column AB (NE/NP column)
   - Extract ASINs where column AB = "NE"
   - Read ASIN from column A
   - Read enrichment data from columns W-AA (Title, Brand, Price, Rating, Reviews)
   - Read original metrics from columns D and F (Spend, Sales 14d)
3. Generate summary Excel with columns:
   - Campaign (text)
   - ASIN (text)
   - Product Title (from column W)
   - Brand (from column X)
   - Spend (currency)
   - Sales 14d (currency)
4. Format with:
   - Blue header row (#0066CC background, white text, bold)
   - Zebra striping (alternating gray #F2F2F2)
   - Borders on all cells
   - Freeze panes on header row
   - Column widths optimized
5. Log usage event
6. Return file as download

**Error Cases:**
- `400` - Unable to read workbook (corrupt file, not .xlsx format)
- `400` - No NE markings found (no ASINs marked in column AB)
- `500` - Summary generation error

**Example Error Response:**
```json
{
  "detail": "No NE markings found. Please mark ASINs as 'NE' in column AB before uploading."
}
```

---

## 10. Environment Variables

### Backend (`backend-core`)

- `SUPABASE_URL` - Supabase project URL (auth validation)
- `SUPABASE_JWT_SECRET` - JWT verification key (auth validation)
- `MAX_UPLOAD_MB` - Max file size in MB (default: 40)
- `APP_VERSION` - Version string for workbook metadata (e.g., "1.0.0")

### Frontend (`frontend-web`)

- `NEXT_PUBLIC_SUPABASE_URL` - Supabase project URL (client-side auth)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Supabase anon key (client-side auth)
- `NEXT_PUBLIC_BACKEND_URL` - Backend API base URL (e.g., `https://api.ecomlabs.ca` in production, `http://localhost:8000` in dev)

---

## 11. Testing Strategy

### Unit Tests

**Backend (`backend-core/app/services/npat/`):**

1. **ASIN Regex Filter** (`parser.py`)
   - Test valid ASINs: `B08XYZ123`, `b09abc456` (case-insensitive)
   - Test invalid: `B08XYZ12` (too short), `B08XYZ1234` (too long), `B08-XYZ123` (hyphen)
   - Test edge cases: Empty string, null, numbers only, letters only

2. **Metric Calculations** (`analytics.py`)
   - CTR = Click / Impression (handle division by zero)
   - CPC = Spend / Click (handle division by zero)
   - CVR = Order / Click (handle division by zero)
   - ACOS = Spend / Sales (handle division by zero)

3. **VLOOKUP Formula Generation** (`workbook.py`)
   - Verify formula string format: `=IFERROR(VLOOKUP($A6,$M$6:$V$5000,2,FALSE),"")`
   - Test with different row numbers (6, 100, 5000)

4. **TEXTJOIN Pipe String Formula** (`workbook.py`)
   - Verify formula string: `=TEXTJOIN("|",TRUE,B6:B5000)`
   - Test with different ASIN counts (1, 10, 100)

---

### Integration Tests

**Full Workflow Tests:**

1. **Upload → Process → Download Flow**
   - Upload test Search Term Report with 500 rows (mix of ASINs and keywords)
   - Verify only ASINs are included in output (keywords filtered out)
   - Verify campaigns with "Ex.", "SDI", "SDV" are excluded
   - Verify workbook opens without errors
   - Verify ASIN pipe string formula works

2. **Upload Filled → Collect → Download Flow**
   - Create filled workbook with marked NE ASINs
   - Upload to collect endpoint
   - Verify negatives summary includes only marked ASINs
   - Verify enrichment columns are present (Title, Brand)

3. **Multi-Campaign Workbook Generation**
   - Upload report with 5+ campaigns
   - Verify each campaign gets dedicated sheet
   - Verify Summary sheet lists all campaigns
   - Verify links work (clicking campaign in Summary → navigates to sheet)

4. **H10 Paste Zone VLOOKUP Accuracy**
   - Generate workbook with 10 ASINs
   - Manually paste mock H10 data into columns M-V
   - Verify VLOOKUP formulas in columns W-AA populate correctly
   - Test with mismatched ASINs (some in paste zone don't match main data)

---

### Manual Testing Checklist

**Pre-Implementation (Design Validation):**
- [ ] Review this PRD with team
- [ ] Confirm H10 ASIN Grabber output format matches expected columns M-V
- [ ] Test ASIN pipe string in real Amazon search (does pipe delimiter work?)
- [ ] Validate VLOOKUP formula logic with sample data

**Post-Implementation (Functional Testing):**
1. [ ] Upload test Search Term Report with mix of ASINs and keywords
2. [ ] Verify only ASINs are included in generated workbook
3. [ ] Verify campaigns with "Ex.", "SDI", "SDV" are excluded
4. [ ] Open generated workbook (should open without repair dialog)
5. [ ] Verify ASIN pipe string in row 2 contains only ASINs (no keywords)
6. [ ] Copy ASIN pipe string from B2
7. [ ] Paste into Amazon search bar
8. [ ] Run Helium10 ASIN Grabber extension
9. [ ] Copy H10 data
10. [ ] Paste H10 data into columns M-V (H10 paste zone)
11. [ ] Verify VLOOKUP formulas populate columns W-AA correctly
12. [ ] Mark 5 ASINs as "NE" in column AB
13. [ ] Add notes in column AC for marked ASINs
14. [ ] Upload filled workbook to collect endpoint
15. [ ] Verify negatives summary includes exactly 5 marked ASINs
16. [ ] Verify enrichment columns (Title, Brand) are present in summary
17. [ ] Verify summary is formatted correctly (zebra stripes, borders, headers)
18. [ ] Test with multiple campaigns (2-3 campaigns)
19. [ ] Test with large file (6,000+ rows, 40MB)
20. [ ] Test error cases: empty file, missing columns, corrupt workbook

---

## 12. Success Criteria

### Functional Requirements

**✅ Must Have (MVP):**
- [ ] Tool correctly filters Search Term Reports to ONLY ASINs (10-character alphanumeric)
- [ ] ASINs are grouped by campaign with accurate metrics (CTR, CPC, CVR, ACOS)
- [ ] ASIN pipe string generator works in row 2 of each campaign sheet
- [ ] H10 paste zone (columns M-V) accepts pasted data
- [ ] VLOOKUP formulas (columns W-AA) correctly enrich ASIN data
- [ ] Collect endpoint extracts all ASINs marked "NE" in column AB
- [ ] Negatives summary includes enrichment columns (Title, Brand)
- [ ] Negatives summary is formatted and ready for Amazon Ads upload

**⭐ Nice to Have (Future):**
- [ ] Auto-detect duplicate ASINs across campaigns
- [ ] Flag high-spend ASINs (>$100 spend)
- [ ] Suggest negative targeting strategies based on ACOS
- [ ] Direct Helium10 API integration (eliminate manual paste)

---

### Performance Requirements

**Must Meet:**
- [ ] Process endpoint completes in <180 seconds for 40MB files (6,000+ rows) and enforces the MAX_UPLOAD_MB limit (match N-Gram behavior; consider a frontend check too)
- [ ] Collect endpoint completes in <30 seconds for filled workbook
- [ ] Workbook opens in Excel/Google Sheets without errors or repair dialogs
- [ ] VLOOKUP formulas calculate instantly when H10 data is pasted
- [ ] TEXTJOIN formula (ASIN pipe string) evaluates without errors
- [ ] Summary sheet loads and navigates to campaign sheets without lag

---

### User Experience Requirements

**Must Achieve:**
- [ ] UI matches N-Gram styling and color scheme (blue gradient background, white cards)
- [ ] Loading states are fun and reassuring (rotating sci-fi phrases)
- [ ] Error messages are clear and actionable (e.g., "No ASINs found. N-PAT requires...")
- [ ] File naming is intuitive (`_npat.xlsx` for generated, `_negatives.xlsx` for summary)
- [ ] ASIN pipe string in row 2 is immediately visible and easy to copy
- [ ] H10 paste zone instructions are clear and visible (row 5)
- [ ] Enrichment columns populate automatically without user action
- [ ] Negatives summary is ready for Amazon upload (no reformatting needed)

---

## 13. Future Enhancements (Post-MVP)

### Phase 2: Auto-H10 Integration

**Goal:** Eliminate manual Helium10 paste workflow

**Features:**
- Integrate Helium10 API directly (if available)
- Auto-fetch product data server-side for all ASINs
- Return fully enriched workbook (no manual paste needed)

**Benefits:**
- Faster workflow (no manual copy/paste)
- No Chrome extension dependency
- Always up-to-date product data

**Blockers:**
- Helium10 API access required (check if available)
- API rate limits and costs

---

### Phase 3: ASIN Analysis & Insights

**Goal:** Provide intelligent recommendations

**Features:**
- Detect duplicate ASINs across campaigns
- Flag high-spend ASINs (>$100 spend, <1% CVR)
- Identify competitor patterns (same brand appearing in multiple campaigns)
- Suggest negative targeting strategies based on ACOS thresholds

**Benefits:**
- Faster decision-making
- Proactive recommendations
- Pattern detection humans might miss

---

### Phase 4: Combined N-Gram + N-PAT Export

**Goal:** Unified negative targeting workflow

**Features:**
- Upload filled N-Gram workbook + filled N-PAT workbook
- Generate single negatives summary with both keywords and ASINs
- Format for Amazon Ads bulk upload (single file)

**Benefits:**
- Streamlined workflow (one upload instead of two)
- Comprehensive negative targeting list

---

### Phase 5: Historical Tracking & Analytics

**Goal:** Measure impact of negative targeting

**Features:**
- Store ASIN negative targeting decisions in database
- Track spend saved by excluding ASINs (before/after analysis)
- Analytics dashboard showing:
  - Top excluded competitors
  - Spend saved per campaign
  - Negative targeting coverage (% of ASINs reviewed)

**Benefits:**
- ROI measurement
- Historical trends
- Executive reporting

---

## 14. Open Questions (Require Product Decision)

1. **H10 Data Columns**
   - Should we include all H10 fields (10 columns), or focus on essentials (Title, Brand, Price, Rating, Reviews = 5 columns)?
   - **Recommendation:** Start with essentials (5 columns) to reduce workbook width, add more in Phase 2 if needed

2. **ASIN URL Generation**
   - Should we include Amazon product URLs (e.g., `https://amazon.com/dp/{ASIN}`) in workbook for quick access?
   - **Recommendation:** Yes, add in column V (Product URL) - low effort, high value for quick product review

3. **Category Detection**
   - Should we reuse N-Gram category logic (detect "Brand", "Catalog", "PPC" from campaign name), or ASINs don't need categories?
   - **Recommendation:** Reuse N-Gram logic for visual consistency (color-coded tabs), but make it optional

4. **Multiple H10 Runs**
   - If user re-pastes H10 data (e.g., prices changed), should VLOOKUP formulas update automatically, or warn about overwriting?
   - **Recommendation:** Update automatically (Excel default behavior), no warning needed - users expect formulas to recalculate

5. **Negatives Summary Format**
   - Should it match Amazon Ads bulk upload format exactly (specific column order/names), or be human-readable first?
   - **Recommendation:** Human-readable first (MVP), add Amazon Ads export format in Phase 2 (one-click conversion)

---

## 15. Out of Scope (Explicitly NOT in MVP)

**❌ Not Included:**
- Real-time Helium10 API integration (manual paste workflow only)
- Historical tracking of ASIN decisions (stateless tool)
- Competitor analysis dashboard (future analytics phase)
- Multi-user collaboration (workbook sharing/comments)
- Mobile app (desktop web only)
- Combined N-Gram + N-PAT export (separate tools for MVP)
- Amazon Ads bulk upload format conversion (human-readable export only)
- ASIN deduplication across campaigns (future phase)
- Automated negative targeting suggestions (future AI phase)

---

## 16. Technical Stack Summary

**Frontend:**
- Next.js 14 (App Router)
- React + TypeScript
- ShadcnUI components
- Supabase Auth (client SDK)

**Backend:**
- Python 3.11+
- FastAPI
- pandas, numpy, openpyxl, xlsxwriter
- Supabase Auth (JWT validation)

**Infrastructure:**
- Render (hosting for both frontend and backend)
- Supabase (authentication only, no database tables)

**External Dependencies:**
- Helium10 ASIN Grabber (Chrome extension, user-installed)
- Amazon.com (for ASIN search with pipe-delimited strings)

---

## 17. Migration & Rollout Plan

### Pre-Launch Checklist

**Week 1: Development**
- [ ] Backend router implementation (`app/routers/npat.py`)
- [ ] Parser service with ASIN filter (`app/services/npat/parser.py`)
- [ ] Analytics service with metric calculations (`app/services/npat/analytics.py`)
- [ ] Workbook generator with H10 integration (`app/services/npat/workbook.py`)
- [ ] Frontend page implementation (`app/npat/page.tsx`)

**Week 2: Testing**
- [ ] Unit tests for ASIN regex, metrics, formulas
- [ ] Integration tests for upload/download flows
- [ ] Manual testing with real Search Term Reports
- [ ] H10 paste workflow validation with team

**Week 3: Documentation & Training**
- [ ] User guide (screenshots + workflow steps)
- [ ] Video tutorial (5-minute walkthrough)
- [ ] Internal team training session

**Week 4: Soft Launch**
- [ ] Deploy to production (Render)
- [ ] Add route to frontend navigation (`tools.ecomlabs.ca/npat`)
- [ ] Grant access to 2-3 PPC specialists (beta testers)
- [ ] Collect feedback

**Week 5: Full Launch**
- [ ] Announce to full team
- [ ] Monitor usage logs
- [ ] Iterate based on feedback

---

## 18. Dependencies

**Completed (Ready):**
- ✅ N-Gram tool (provides patterns to replicate)
- ✅ Agency OS architecture (frontend + backend + auth)
- ✅ Supabase authentication
- ✅ Usage logging service
- ✅ Excel generation with xlsxwriter

**In Progress:**
- ⏳ Helium10 ASIN Grabber validation (confirm output format)

**Blocked On:**
- ❌ None (MVP can proceed)

---

## 19. Risks & Mitigations

### Risk 1: Helium10 Output Format Changes

**Impact:** High (breaks paste workflow)
**Probability:** Low (H10 is stable tool)
**Mitigation:**
- Document expected H10 format in user guide
- Add validation in collect endpoint (check if enrichment columns exist)
- Graceful degradation (if no H10 data, negatives summary still works with just ASINs)

### Risk 2: Amazon Blocks Pipe-Delimited ASIN Search

**Impact:** High (breaks ASIN lookup workflow)
**Probability:** Very Low (pipe delimiter is documented Amazon feature)
**Mitigation:**
- Test with real Amazon search before launch
- Fallback: Provide ASINs as line-separated list (copy/paste into Helium10 directly)

### Risk 3: Large Files Cause Timeouts

**Impact:** Medium (user frustration)
**Probability:** Low (40MB limit, gunicorn timeout already fixed for N-Gram)
**Mitigation:**
- Set gunicorn timeout to 180 seconds (already configured for N-Gram)
- Add file size validation before processing
- Show progress indicator during upload

### Risk 4: VLOOKUP Formulas Break in Google Sheets

**Impact:** Low (most users use Excel)
**Probability:** Low (VLOOKUP is standard across Excel and Sheets)
**Mitigation:**
- Test workbook in Google Sheets before launch
- Use IFERROR wrapper (compatible with both platforms)
- Document compatibility in user guide

---

## 20. Appendix: Mockups & Examples

### Example 1: Campaign Sheet (First 3 Columns)

```
Row 1: Campaign: Brand X - Product Targeting Campaign
Row 2: ASINs for H10: b08xyz123|b09abc456|b0a1def789

Row 4 Headers:
| ASIN       | Impression | Click | Spend   | ... |
|------------|------------|-------|---------|-----|
| B08XYZ123  | 1,234      | 56    | $45.67  | ... |
| B09ABC456  | 890        | 23    | $18.90  | ... |
| B0A1DEF789 | 567        | 12    | $9.87   | ... |
```

### Example 2: Negatives Summary Output

```
| Campaign                          | ASIN       | Title                          | Brand  | Spend   |
|-----------------------------------|------------|--------------------------------|--------|---------|
| Brand X - Product Targeting       | B08XYZ123  | Competitor Widget - Blue       | Anker  | $45.67  |
| Brand X - Product Targeting       | B09ABC456  | Generic Gadget - Red           | AmazonBasics | $18.90 |
| Brand Y - Competitor Campaign     | B0A1DEF789 | Off-Brand Tool - Green         | Unknown| $9.87   |
```

---

**End of PRD**

---

**Approval Signatures:**

_Product Owner:_ _____________________ Date: _______
_Engineering Lead:_ __________________ Date: _______
_PPC Team Lead:_ _____________________ Date: _______
