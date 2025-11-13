# Product Requirement Document: Amazon Creative Brief Tool

## 1. Executive Summary
**The Creative Brief Tool** is a visual orchestration engine that generates designer-ready instructions for Amazon Product Images and A+ Content.

It solves the "Handover Problem": Instead of sending a designer a folder of random JPEGs and a Word doc of copy, this tool ingests both, uses AI to "see" the images, and outputs a structured **Web-Based Brief**. This brief dictates exactly which image to use, what text overlay to apply, and what style to follow.

## 2. User Experience (UX)

### 2.1 The Setup (Input Wizard)
**Location:** `tools.ecomlabs.ca/brief`

* **Step 1: Link to Copy**
    * User selects a **Client** and a **Listing** (from Tool #3: Amazon Composer).
    * *Benefit:* Automatically pulls the Title, Bullets, and Keywords. No re-entry needed.

* **Step 2: Asset Ingest (The "Digital Asset Manager")**
    * **Upload:** Drag-and-drop raw images (product shots, lifestyle, textures).
    * **AI Tagging:** The system scans every upload (using GPT-4o Vision) and auto-tags them:
        * *Type:* `Main`, `Infographic`, `Lifestyle`, `Packaging`.
        * *Subject:* `Front View`, `Side View`, `In-Use`, `Texture Zoom`.

* **Step 3: Strategy & Style**
    * **Target Persona:** "Busy Mom," "Tech Enthusiast," etc.
    * **Visual Style:** Select from presets (e.g., "Aesop Minimalist," "Anker Tech-Heavy," "Fisher-Price Playful").
    * **Reference URLs:** Input competitor ASINs or internal inspiration links.

### 2.2 The AI Generation
The system runs a "Mapping Agent":
1.  Reads **Bullet Point 1** (e.g., "Waterproof Construction").
2.  Scans **Assets** for tags like `water`, `rain`, `droplets`.
3.  **Output:** Creates a "Slide" combining that text with that image.

### 2.3 The Brief Editor (The Output)
**Interface:** A linear "Storyboard" view (Slide 1 to Slide 7).

* **Each Slide Contains:**
    * **Visual:** The selected raw asset (previewed inline).
    * **Copy Overlay:** The specific text the designer should place on the image.
    * **Designer Note:** "Make the water droplets pop," or "Zoom in 20%."
    * **Reference:** A snippet of a competitor image for inspiration.
* **Actions:**
    * *Swap Image:* Click to replace the raw asset from the library.
    * *Edit Text:* Tweaks the overlay copy.
    * *Reorder:* Drag Slide 3 to become Slide 2.

### 2.4 The Handoff
* **Share Link:** `tools.ecomlabs.ca/brief/share/{uuid}`.
    * Sent to the Graphic Designer.
    * Read-only view of the Storyboard.
    * **"Download Asset Kit"**: A button that zips all selected raw images for the designer.
* **Export:** PDF Generation for client approval.

---

## 3. Technical Architecture

### 3.1 Frontend (`frontend-web`)
* **Asset Grid:** A masonry layout for viewing 50+ raw uploads.
* **Storyboard UI:** A vertical list of "Cards" with drag-and-drop reordering (`dnd-kit`).
* **Image Preview:** High-performance rendering (Next.js Image optimization).

### 3.2 Backend (`backend-core`)
* **Vision Pipeline:**
    * Uses **GPT-4o (Vision)** or **Claude 3.5 Sonnet**.
    * *Prompt:* "Analyze this image. Is it on a white background? Is it lifestyle? Describe the key objects."
* **Mapping Logic:**
    * A logic layer that matches `Listing Text Segments` $\leftrightarrow$ `Image Tags`.
* **Storage:**
    * **Supabase Storage:** We need a dedicated Bucket `brief-assets`.
    * *Constraint:* Images are heavy. We must implement client-side compression or strict size limits (e.g., 5MB max per file) before upload.

---

## 4. Data Model (Supabase)

### 4.1 Briefs & Assets
```sql
create table public.briefs (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references public.listings, -- Link to Composer
  style_guide jsonb, -- { tone: 'playful', colors: ['#F00', '#000'] }
  status text default 'draft',
  created_by uuid references auth.users
);

create table public.assets (
  id uuid primary key default gen_random_uuid(),
  brief_id uuid references public.briefs,
  storage_path text not null, -- Supabase Storage path
  ai_tags text[], -- ['lifestyle', 'dog', 'outdoors']
  file_meta jsonb -- { width: 1024, height: 1024, size: 2mb }
);

### 4.2 The Storyboard (Slides)

create table public.brief_slides (
  id uuid primary key default gen_random_uuid(),
  brief_id uuid references public.briefs,
  sort_order int,
  slide_type text, -- 'main', 'lifestyle', 'infographic'
  
  -- Content
  asset_id uuid references public.assets, -- The raw image to use
  overlay_text text, -- "Waterproof up to 50m"
  designer_notes text, -- "Add a blue tint overlay"
  reference_image_url text -- Optional external inspiration
);

5. Integration Strategy
Integration with Composer (Tool #3)
The User does not type copy here. They select a listing_version_id from Composer.

If the Composer copy changes after the brief is made, the Brief Tool shows a "Sync Available" warning: "The listing bullet points have changed. Update Brief?"

Integration with ClickUp (Future)
When the Brief is marked "Ready for Design," the system can trigger a ClickUp Task creation via the ClickUp Fetcher (Tool #2), attaching the Share Link.

6. Success Criteria (MVP)
Vision Accuracy: The AI correctly identifies "White Background" vs "Lifestyle" 90% of the time.

Mapping Logic: The system creates a reasonable "First Draft" brief (7 slides) automatically from the assets + copy.

Asset Delivery: The Designer can download the exact files referenced in the brief without digging through a messy Drive folder.
