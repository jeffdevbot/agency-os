# 📘 PRD — Product Intake Tool

**Version:** 1.0
**Product Area:** Agency OS → Tools → Product Intake
**Status:** Draft for Review

## Overview
Product Intake Tool is a client-facing web form that collects comprehensive product information, compliance data, and digital assets needed to onboard new products for Amazon selling. It replaces the current Excel-based process with a guided web experience that validates data, manages file uploads, and serves as the single source of truth for product data across Agency OS tools.

### Purpose
- Provide clients with a professional, easy-to-use product submission experience
- Collect all required Amazon catalog data (UPC, dimensions, weights, compliance)
- Manage product assets (images, videos, documents) with proper storage
- Validate data at submission time to reduce back-and-forth
- Feed clean, structured data into Composer for copy generation
- Generate Amazon-ready flat file exports

### Key Outputs
- Complete product records with all catalog data
- Organized asset library (product images, lifestyle shots, videos, documents)
- Amazon flat file CSV export
- Pre-filled Composer projects (SKUs + attributes + context)

## Goals

### 1.1 Primary Goals
- Replace manual Excel workflow with validated web forms
- Enable clients to submit products independently without team guidance
- Reduce data entry errors through validation and structured inputs
- Centralize asset management (no more scattered Dropbox links)
- Provide single source of truth for product data across tools
- Integrate seamlessly with Composer for copy generation workflow

### 1.2 Secondary Goals
- Track submission status (draft → submitted → reviewed → approved)
- Support bulk product uploads via CSV import
- Generate Amazon flat files automatically
- Provide client portal for viewing submitted products
- Enable team review and editing before approval

## Non-Goals
- Copy generation (handled by Composer)
- Keyword research or SEO optimization
- A+ Content or Brand Store creation
- Competitor analysis
- Inventory management or order tracking
- Direct Amazon API integration (manual upload for now)
- Multi-language product data (English only for v1)

## User Roles
- **Client** – fills out product information, uploads assets, submits for review
- **Team Member / VA** – reviews submissions, edits data, approves products, exports to Amazon
- **PM / Account Manager** – monitors submission pipeline, communicates with clients

## High-Level Workflow

### Client Flow
1. Receive email with unique intake link
2. Fill out product form (can save draft and return)
3. Upload images, videos, documents
4. Review summary
5. Submit for team review
6. (Optional) Receive feedback, make edits, resubmit

### Team Flow
1. Receive notification of new submission
2. Review product data and assets
3. Edit/correct any issues
4. Approve product
5. Export to Amazon flat file, or
6. Import to Composer to generate copy

## Detailed Requirements

### 🟦 5.1 INTAKE LINK SYSTEM

**Link Generation**
- Team creates shareable intake link per client or per project
- Format: `tools.ecomlabs.ca/intake/{token}`
- Token-based auth (no login required for clients)
- Link can be:
  - Single-use (expires after submission)
  - Multi-product (client can submit multiple products)
  - Time-limited (expires after X days)

**Link Management (Team View)**
- Create link with settings:
  - Client name
  - Link type (single/multi/unlimited)
  - Expiration date
  - Optional welcome message
- Copy link to clipboard
- View active links, submissions per link
- Disable/revoke links

### 🟦 5.2 PRODUCT INFORMATION SECTION

**Required Fields:**
- UPC (barcode format validation)
- SKU (unique within organization)
- Brand
- Manufacturer

**Optional Fields:**
- Manufacturer Part Number
- Model Number
- Unit Count (number)
- Unit Count Type (dropdown: Count, Fl Oz, Foot, Gram, Ounce, Pound, Sq Ft)
- Number of Items
- MSRP (currency input)
- Selling Price (currency input, validate < MSRP)
- Color (text or dropdown if standardized)
- Size (text or dropdown if standardized)

**Validation:**
- UPC: 12-digit barcode format
- SKU: alphanumeric, no spaces
- MSRP/Selling Price: positive numbers, 2 decimal places
- Duplicate SKU check within organization

### 🟦 5.3 FBA LABELING SECTION

**Single Selection:**
- How will FBA inventory be labelled?
  - ( ) Amazon Barcode (FNSKU)
  - ( ) UPC Barcode

**Helper Text:**
- Amazon Barcode: Amazon will apply FNSKU labels (recommended for new sellers)
- UPC Barcode: You'll use manufacturer barcode (requires existing UPC)

### 🟦 5.4 MARKETING INFO SECTION

**Fields:**
- Title (text, 200 char max, show counter)
- Product Description (rich text editor, 2000 char max)
- Product Category (dropdown or autocomplete from Amazon browse nodes)
- Product Benefits/Features (repeater: add/remove bullet points)
- Ingredients (textarea, optional)
- Usage Directions (textarea, optional)

**Notes:**
- Title and Description here are DRAFT/REFERENCE only
- Composer will generate optimized copy later
- But this content provides context for AI

### 🟦 5.5 IMAGE ASSETS SECTION

**Upload Categories:**

1. **Product Images** (required: min 1, max 9)
   - Requirements: Min 1000x500px, pure white background, JPEG format
   - Main image validation: exactly 1000x1000px recommended
   - Drag-and-drop upload
   - Set one as "Main Image"
   - Reorder images

2. **Nutritional Facts Chart** (optional, food/supplement products)
   - Requirements: Min 1000x500px, JPEG format
   - Single file upload

3. **Product/Marketing Videos** (optional, max 3)
   - Requirements: .mp4 or .mov, under 5 GB each
   - Upload with progress bar
   - Generate thumbnail on upload

4. **Lifestyle Images** (optional, max 6)
   - Requirements: Min 1000x500px, JPEG format
   - Show product in use/context

5. **Brand Logo** (optional)
   - Requirements: PNG with transparency preferred, min 500x500px
   - Used for brand registry and A+ content

**Asset Management:**
- All files stored in Supabase Storage under `product-assets/{org_id}/{product_id}/`
- Generate thumbnails for images
- Validate file types, dimensions, sizes on upload
- Show preview gallery with delete/replace options
- Track upload status (uploading / processing / ready / error)

**Error Handling:**
- Reject files that don't meet requirements with specific error
- Show which files failed and why
- Allow retry without re-uploading successful files

### 🟦 5.6 GENERIC ATTRIBUTES SECTION

**Product Attributes:**
- Item Type (text)
- Included Components (comma-separated list)
- Material Type (text or dropdown if standardized)
- Contains Liquid Contents? (Yes/No toggle)
  - If Yes: show "Is the liquid product double sealed?" (Yes/No)
  - If Yes: show "Liquid Volume" (number + unit dropdown: mL, L, fl oz, gal)

**Expiration:**
- Is Product Expirable? (Yes/No toggle)
  - If Yes: show "Product Expiration Type" dropdown:
    - Does Not Expire
    - Expiration Date Required
    - Expiration On Package
    - Production Date Required
  - If Yes: show "FC Shelf Life Unit in days" (number)

**Temperature:**
- Is the Item Heat Sensitive? (Yes/No toggle)

**Dimensions (Product):**
- Item Length (number + unit: inches/cm)
- Item Width (number + unit: inches/cm)
- Item Height (number + unit: inches/cm)
- Item Weight (number + unit: oz/lb/g/kg)

**Dimensions (Package):**
- Package Length (number + unit: inches/cm)
- Package Width (number + unit: inches/cm)
- Package Height (number + unit: inches/cm)
- Package Weight (number + unit: oz/lb/g/kg)

**Validation:**
- Package dimensions must be ≥ item dimensions
- Package weight must be ≥ item weight
- Positive numbers only

### 🟦 5.7 COMPLIANCE & SAFETY SECTION

**CPSIA Warning** (dropdown, required for children's products):
- No Warning Applicable (default)
- Choking Hazard - Contains A Marble
- Choking Hazard - Is A Small Ball
- Choking Hazard - Is A Marble
- Choking Hazard - Contains Small Ball
- Choking Hazard - Small Parts
- Choking Hazard - Balloon
- Contains Small Magnets

**Dangerous Goods Regulations** (dropdown):
- Not Applicable (default)
- GHS
- Transportation
- Storage
- Waste
- Unknown
- Other

**Safety Data Sheet (SDS/MSDS)** (file upload, PDF only, optional)
- For hazardous materials
- Store with product assets

**GHS Class** (multi-select checkboxes, if applicable):
- Explosive
- Flammable
- Oxidizing
- Compressed Gas
- Corrosive
- Toxic
- Irritant
- Health Hazard
- Environmentally Damaging
- Amazon Specific No Label With Warning

**California Proposition 65 Warning Type** (dropdown, if applicable):
- Not Applicable (default)
- Alcoholic Beverage
- Chemical
- Diesel Engines
- Food
- Furniture
- On Product Cancer
- On Product Combined Cancer Reproductive
- On Product Reproductive
- Passenger or Off Road Vehicle
- Raw Wood
- Recreational Vessel

**Origin:**
- Country/Region of Origin (dropdown: all countries, searchable)

**Warranty:**
- Manufacturer Warranty Description (textarea, optional)

### 🟦 5.8 FORM UX & VALIDATION

**Multi-Step Form:**
- Step 1: Product Information
- Step 2: FBA Labeling
- Step 3: Marketing Info
- Step 4: Image Assets
- Step 5: Generic Attributes
- Step 6: Compliance & Safety
- Step 7: Review & Submit

**Progress Indicator:**
- Show current step, completed steps, remaining steps
- Allow jumping to completed steps
- Block jumping to incomplete steps

**Autosave:**
- Save draft every 30 seconds (or on blur of each field)
- Show "Saving..." / "Saved" indicator
- LocalStorage backup in case network fails

**Validation:**
- Inline validation on blur (field-level errors)
- Summary validation on step navigation (show all errors)
- Final validation on submit (server-side)
- Clear error messages with suggestions

**Required Field Indicators:**
- Asterisk (*) on required field labels
- Summary at top: "3 required fields, 12 optional fields"

### 🟦 5.9 REVIEW & SUBMIT SCREEN

**Summary View:**
- Read-only view of all entered data
- Thumbnails of uploaded assets
- "Edit Section" buttons to jump back
- Terms/agreement checkbox (optional)
- Submit button

**Post-Submit:**
- Success message with submission ID
- "Submit Another Product" button (if multi-product link)
- Email confirmation to client with summary

### 🟦 5.10 TEAM DASHBOARD (INTERNAL)

**Product Submissions List:**
- Columns:
  - Submission Date
  - Client Name
  - Product SKU
  - Brand
  - Status (Draft, Submitted, In Review, Approved, Rejected)
  - Assets (count of images/videos)
  - Actions (View, Edit, Approve, Export, Import to Composer)
- Filters: Status, Client, Date range
- Search: SKU, Brand, UPC
- Sort: Date, Status, Client

**Submission Detail View:**
- All product data in organized sections
- Asset gallery with download links
- Edit mode (team can fix errors)
- Status change controls:
  - Mark as "In Review"
  - "Request Changes" (send note to client)
  - "Approve" (mark ready for use)
  - "Reject" (with reason)
- Activity log (submissions, edits, status changes)

**Bulk Actions:**
- Select multiple products
- Bulk approve
- Bulk export to CSV
- Bulk import to Composer

### 🟦 5.11 INTEGRATION WITH COMPOSER

**Import Flow:**
- From Product Intake dashboard: "Import to Composer" button
- Opens Composer wizard with Product Info pre-filled:

**Mapping:**
```
Product Intake                → Composer Product Info
────────────────────────────────────────────────────────
SKU, Brand, UPC              → SKU table (sku, asin=UPC)
Color, Size, Material Type   → Dynamic attributes
Product Category             → Category field
Ingredients, Usage           → Supplied info
Product Benefits             → Product brief (use cases)
Product Description (draft)  → Supplied info (reference)
Item dimensions/weight       → Attributes (for filters)
```

**What Doesn't Import:**
- MSRP, Selling Price (pricing not needed for copy)
- FBA labeling (operational, not copy-related)
- Compliance data (catalog data, not copy)
- Assets (Composer doesn't manage images)

**Link Products:**
- `composer_projects` table gets `product_intake_id` FK (nullable)
- Can view source product data from Composer
- Changes in Product Intake don't auto-update Composer (one-way import)

### 🟦 5.12 EXPORT TO AMAZON FLAT FILE

**Export Options:**
- Single product: "Export to Amazon CSV" button
- Bulk export: select multiple, "Export Selected to CSV"

**Flat File Format:**
- Standard Amazon template based on category
- Map Product Intake fields to Amazon columns
- Include all required catalog data
- Exclude draft marketing copy (will be replaced by Composer output)
- Generate compliant file name: `{brand}_{sku}_{date}.csv`

**Download:**
- CSV file download
- Optional: email to user
- Log export in activity history

### 🟦 5.13 CLIENT PORTAL (OPTIONAL - V2)

**Client View of Submissions:**
- List of products they've submitted
- Status badges
- View product details (read-only)
- Download their assets
- See team feedback/notes
- Edit and resubmit if changes requested

**Access:**
- Same token link or separate login
- Scoped to their submissions only

## Technical Requirements

### 6.1 Data Storage (Supabase)

**Tables:**

**`product_intake_links`**
- `id`, `organization_id`, `token`, `client_name`, `link_type`, `expires_at`, `max_submissions`, `submission_count`, `welcome_message`, `enabled`, `created_by`, `created_at`

**`product_submissions`**
- `id`, `organization_id`, `intake_link_id`, `status`
- Product Info: `sku`, `upc`, `brand`, `manufacturer`, `manufacturer_part_number`, `model_number`, `unit_count`, `unit_count_type`, `number_of_items`, `msrp`, `selling_price`, `color`, `size`
- FBA: `fba_label_type`
- Marketing: `title`, `description`, `category`, `benefits` (JSONB array), `ingredients`, `usage_directions`
- Attributes: `item_type`, `included_components`, `material_type`, `contains_liquid`, `liquid_sealed`, `liquid_volume`, `is_expirable`, `expiration_type`, `fc_shelf_life_days`, `is_heat_sensitive`, `dimensions` (JSONB), `weights` (JSONB)
- Compliance: `cpsia_warning`, `dangerous_goods_reg`, `ghs_classes` (array), `prop65_warning`, `country_of_origin`, `warranty_description`
- Metadata: `submitted_at`, `reviewed_at`, `approved_at`, `rejected_at`, `rejection_reason`, `created_at`, `updated_at`

**`product_assets`**
- `id`, `organization_id`, `product_submission_id`, `asset_type` (product_image / nutritional_chart / video / lifestyle_image / brand_logo / sds_document), `file_name`, `storage_path`, `file_size`, `mime_type`, `width`, `height` (for images), `duration` (for videos), `thumbnail_path`, `is_main` (for product images), `sort_order`, `upload_status`, `created_at`

**`product_activity_log`**
- `id`, `organization_id`, `product_submission_id`, `actor_id`, `actor_type` (client/team), `action` (created / edited / submitted / reviewed / approved / rejected / exported), `metadata` (JSONB), `created_at`

**Foreign Keys:**
- Link → Organization
- Submission → Organization, Link
- Asset → Organization, Submission
- Activity → Organization, Submission
- Optional: `composer_projects.product_intake_id` → Submission

### 6.2 File Storage (Supabase Storage)

**Bucket Structure:**
```
product-assets/
  {organization_id}/
    {product_submission_id}/
      product-images/
        main.jpg
        alt-1.jpg
        alt-2.jpg
      lifestyle-images/
        lifestyle-1.jpg
      videos/
        demo.mp4
        demo-thumb.jpg
      documents/
        nutritional-facts.jpg
        sds.pdf
      brand/
        logo.png
```

**Storage Policies:**
- Clients (via token): upload to their submission folder only
- Team: read/write all under their organization
- Max file sizes: Images 10MB, Videos 5GB, Documents 25MB
- Allowed types: JPEG/PNG for images, MP4/MOV for videos, PDF for documents

### 6.3 Validation Rules

**Client-Side (React):**
- Field format validation (UPC, SKU, email)
- Required field checks
- File type/size/dimension checks before upload
- Dimension logic (package ≥ item)

**Server-Side (API):**
- Re-validate all client checks
- Duplicate SKU within organization
- Image dimension verification (ImageMagick or sharp)
- Virus scan on file uploads (optional)
- Rate limiting on submissions

### 6.4 APIs

**Client-Facing:**
- `GET /api/intake/:token` - validate token, get link settings
- `GET /api/intake/:token/draft` - load saved draft
- `POST /api/intake/:token/draft` - save draft (autosave)
- `POST /api/intake/:token/submit` - final submission
- `POST /api/intake/:token/assets/upload` - chunked file upload

**Team-Facing:**
- `GET /api/intake/links` - list links
- `POST /api/intake/links` - create link
- `PATCH /api/intake/links/:id` - update/disable link
- `GET /api/intake/submissions` - list submissions (filters, pagination)
- `GET /api/intake/submissions/:id` - get submission detail
- `PATCH /api/intake/submissions/:id` - update submission (team edits)
- `POST /api/intake/submissions/:id/approve` - approve
- `POST /api/intake/submissions/:id/reject` - reject with reason
- `POST /api/intake/submissions/:id/request-changes` - send back to client
- `GET /api/intake/submissions/:id/export` - generate flat file CSV
- `POST /api/intake/submissions/:id/import-to-composer` - create Composer project

### 6.5 Notifications

**Email Triggers:**
- Client submits product → notify team
- Team approves/rejects → notify client
- Team requests changes → notify client with details
- Link expires soon (24h warning) → notify client

**Email Templates:**
- Welcome email with intake link
- Submission confirmation
- Changes requested
- Approved/Rejected
- Link expiration warning

## Implementation Phasing

### Phase 1 - MVP (Core Intake)
- Token-based intake links (single/multi use)
- All form sections (Product Info → Compliance)
- File uploads to Supabase Storage
- Draft autosave
- Submit workflow
- Team dashboard (list, view, edit, approve)
- Basic export to CSV

### Phase 2 - Integration & Polish
- Import to Composer integration
- Bulk CSV import (team uploads multiple products)
- Enhanced validation (image dimensions, virus scan)
- Activity logs
- Email notifications
- Asset thumbnail generation

### Phase 3 - Advanced Features
- Client portal (view submissions)
- Resubmit after changes requested
- Bulk actions (approve/export multiple)
- Advanced Amazon flat file templates per category
- Analytics (submission funnel, time-to-approve)
- Link analytics (views vs submissions)

## Open Questions / Decisions Needed

1. **Asset Management Strategy:**
   - Do clients upload to Dropbox/Drive then paste links? Or direct upload to our storage?
   - **Decision:** Direct upload to Supabase Storage for better control and validation

2. **Pricing Fields:**
   - Is MSRP/Selling Price needed in Product Intake, or only in Amazon Seller Central?
   - **Decision:** Include for completeness, but optional

3. **Category Taxonomy:**
   - Use Amazon's browse node hierarchy, or simplified categories?
   - **Decision:** Start with free text, add dropdown with common categories in Phase 2

4. **Multi-Variant Products:**
   - How to handle variation families (parent + children)?
   - **Decision:** V1 treats each SKU independently; V2 adds parent/child relationships

5. **Client Self-Service:**
   - Can clients edit after submission, or only team?
   - **Decision:** V1 team only; V2 adds "Request Changes" flow for client edits

## Success Metrics

**Adoption:**
- % of clients using web form vs. Excel
- Time from link sent to submission
- Submission completion rate (started vs finished)

**Quality:**
- % of submissions requiring team edits
- Average time team spends reviewing/fixing
- Rejection rate

**Efficiency:**
- Time saved per product vs. manual Excel process
- Reduction in client back-and-forth

**Integration:**
- % of submissions imported to Composer
- Time from intake to copy generation start

## Appendix — Screens to Build

### Client-Facing
1. Intake Landing Page (token validation)
2. Form Step 1 - Product Information
3. Form Step 2 - FBA Labeling
4. Form Step 3 - Marketing Info
5. Form Step 4 - Image Assets (upload interface)
6. Form Step 5 - Generic Attributes
7. Form Step 6 - Compliance & Safety
8. Form Step 7 - Review & Submit
9. Success / Confirmation Page

### Team-Facing
10. Link Management (create/list/disable)
11. Submissions Dashboard (list with filters)
12. Submission Detail View (read-only)
13. Submission Edit View (team edits)
14. Approval/Rejection Flow
15. Export Options (CSV, Composer import)

### Shared/Modals
16. File Upload Component (drag-drop, progress)
17. Asset Gallery (view/download/delete)
18. Validation Error Summary

---

**Next Steps:**
1. Review and approve PRD
2. Create implementation plan (similar to Composer's staged approach)
3. Design schema and migrations
4. Build Phase 1 MVP
5. Test with pilot client
6. Iterate based on feedback
