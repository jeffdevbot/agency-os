# Product Requirement Document: Amazon Composer

## 1. Executive Summary
**Amazon Composer** is a specialized content generation and approval tool. It replaces the "Word Doc + Email" workflow with a streamlined web application that:
1.  **Ingests** product data (SKUs, dimensions, raw features).
2.  **Generates** optimized Amazon listings (Title, Bullets, Search Terms) using AI.
3.  **Facilitates** client approval via a secure, public "Secret Link."
4.  **Exports** the final approved content directly into an Amazon-ready Flat File (CSV).

## 2. User Experience (UX)

### 2.1 The Internal Workflow (Agency Side)
**Location:** `tools.ecomlabs.ca/composer`

* **Step 1: The Input Wizard**
    * User selects a **Client** (from the Agency OS dropdown).
    * **Data Entry:** User inputs core product data:
        * *Identity:* Parent SKU, Child SKUs, Brand Name.
        * *Specs:* Dims, Weights, Material, Country of Origin.
        * *Marketing:* Target Keywords (paste from Helium10/Ngram), Key Features, Target Audience.
    * **Language:** Select Target Language (e.g., "English (US)", "French (CA)", "Spanish (MX)").

* **Step 2: The AI Draft**
    * System generates a "Draft V1" of the listing.
    * **The Editor:** A rich-text editor that mimics the Amazon PDP (Product Detail Page) layout.
        * *Validation:* Real-time character counters (e.g., "Title: 185/200 bytes").
        * *Keyword Highlighting:* Highlights used target keywords in green, missing in red.

* **Step 3: The Review Request**
    * User clicks "Generate Review Link."
    * System creates a unique URL (e.g., `tools.ecomlabs.ca/review/7283-x9z2`).

### 2.2 The External Workflow (Client Side)
**Location:** `tools.ecomlabs.ca/review/{uuid}` (Public Route)

* **The View:** A clean, branded "Read-Only" view of the listing. It looks like a mock Amazon page.
* **Actions:**
    * **"Request Changes":** Opens a comment box for specific feedback.
    * **"Approve Listing":** Locks the version in the database.
* **Security:** No login required, but the link expires after 30 days (or upon approval).

### 2.3 The Output
* Once "Approved," the **"Download Flat File"** button unlocks for the Agency Admin.
* **Formats:**
    * **Inventory Loader (CSV):** Standard Amazon Flat File.
    * **PDF:** A pretty version for the client's records.

---

## 3. Technical Architecture

### 3.1 Frontend (`frontend-web`)
* **Forms:** `react-hook-form` for the massive Input Wizard.
* **Public Route:** A specific Next.js layout for the `/review` route that strips the Admin Sidebar/Nav (distraction-free).
* **Editor:** A lightweight rich-text editor (e.g., TipTap) customized with "Byte Counter" logic (since Amazon counts bytes, not just chars).

### 3.2 Backend (`backend-core`)
* **AI Logic:** Chained Prompting.
    1.  *Analyzer:* Reads inputs, identifies the "Hook."
    2.  *Writer:* Generates Title (SEO heavy) and Bullets (Benefit heavy).
    3.  *Translator:* (Optional) If Multi-language is selected.
* **Flat File Engine:**
    * Uses `pandas` to map our Database Fields $\to$ Amazon's specific Column Headers (e.g., `item_name`, `bullet_point1`, `generic_keywords`).
    * *Maintenance:* We store "Template Mappings" in the code so we can update them when Amazon changes their template format.

---

## 4. Data Model (Supabase)

### 4.1 Listings & Versions
```sql
create table public.listings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references public.clients,
  product_name text, -- Internal name
  parent_sku text,
  target_keywords text[],
  status text default 'draft', -- draft, in_review, approved, exported
  created_at timestamptz default now()
);

create table public.listing_versions (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references public.listings,
  version_number int,
  
  -- The Content
  title text,
  bullets text[], -- Array of 5 strings
  description text,
  search_terms text,
  
  -- The Specs (for flat file)
  specs jsonb, -- { weight: 1.2, unit: 'lbs', ... }
  
  is_approved boolean default false,
  created_by uuid references auth.users
);
4.2 The Secret LinkSQLcreate table public.review_links (
  id uuid primary key default gen_random_uuid(), -- The secure token
  version_id uuid references public.listing_versions,
  expires_at timestamptz,
  is_active boolean default true
);
5. API InterfaceAgency Endpoints (Private)POST /api/composer/generate: Inputs $\to$ AI Draft (Streaming Text).POST /api/composer/save: Saves current editor state as a Version.POST /api/composer/share: Creates a review_link.GET /api/composer/export/{version_id}: Returns the CSV/Excel Flat File.Client Endpoints (Public)GET /api/public/listing/{token}: Fetches the listing content for the Review Page.POST /api/public/feedback: Client submits comments.POST /api/public/approve: Client marks version as approved.6. AI Prompt Strategy (Specifics)The "Byte Limit" Constraint:Amazon Titles have a hard 200-byte limit. The AI often ignores this.Solution: We ask the AI for 3 variations: Short, Medium, Long. The Frontend validates the byte count. If the AI overshoots, the human editor trims it.Keyword Stuffer:Input: List of 10 "Must Have" keywords.System Prompt: "Ensure the following phrases appear exactly once across the Title and Bullets. Prioritize placing 'Main Keyword' in the first 80 characters of the Title."

7. Success Criteria (MVP)
End-to-End Flow: Can create a listing, generate AI copy, save it, share it, approve it, and download a valid CSV.

Client Experience: The "Review Link" loads instantly on mobile/desktop and requires zero friction (no signup).

Flat File Accuracy: The exported CSV can be uploaded to Seller Central without "Header Error."
