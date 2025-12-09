# AdScope File Schema Reference (Amazon Exports)

Use this as the canonical reference for the raw Amazon export structures we’ve seen. The PRD should link here so we don’t lose track of tab names and headers.

---

## 1) Sponsored Products Search Term Report (30-day example)

- **Tabs:** Single tab.
- **Columns (as seen):**  
  Start Date, End Date, Portfolio name, Currency, Campaign Name, Ad Group Name, Retailer, Country, Targeting, Match Type, Customer Search Term, Impressions, Clicks, Click-Thru Rate (CTR), Cost Per Click (CPC), Spend, 7 Day Total Sales, Total Advertising Cost of Sales (ACOS), Total Return on Advertising Spend (ROAS), 7 Day Total Orders (#), 7 Day Total Units (#), 7 Day Conversion Rate, 7 Day Advertised SKU Units (#), 7 Day Other SKU Units (#), 7 Day Advertised SKU Sales, 7 Day Other SKU Sales.

Notes: Last 30 days; serves as STR input (waste bin, branded vs generic, n-grams).

---

## 2) Bulk Operations File (multi-tab example)

Tabs observed:

### Tab: Portfolios
Columns: Product, Entity, Operation, Portfolio ID, Portfolio Name, Budget Amount, Budget Currency Code, Budget Policy, Budget Start Date, Budget End Date, State (Informational only), In Budget (Informational only).

### Tab: Sponsored Products Campaigns
Columns: Product, Entity, Operation, Campaign ID, Ad Group ID, Portfolio ID, Ad ID, Keyword ID, Product Targeting ID, Campaign Name, Ad Group Name, Campaign Name (Informational only), Ad Group Name (Informational only), Portfolio Name (Informational only), Start Date, End Date, Targeting Type, State, Campaign State (Informational only), Ad Group State (Informational only), Daily Budget, SKU, ASIN (Informational only), Eligibility Status (Informational only), Reason for Ineligibility (Informational only), Ad Group Default Bid, Ad Group Default Bid (Informational only), Bid, Keyword Text, Native Language Keyword, Native Language Locale, Match Type, Bidding Strategy, Placement, Percentage, Product Targeting Expression, Resolved Product Targeting Expression (Informational only), Audience ID, Shopper Cohort Percentage, Shopper Cohort Type, Segment Name, Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS.

### Tab: Sponsored Brands Campaigns
Columns: Product, Entity, Operation, Campaign ID, Draft Campaign ID, Portfolio ID, Ad Group ID, Keyword ID, Product Targeting ID, Campaign Name, Campaign Name (Informational only), Portfolio Name (Informational only), Start Date, End Date, State, Campaign State (Informational only), Campaign Serving Status (Informational only), Budget Type, Budget, Bid Optimization, Bid Multiplier, Bid, Keyword Text, Match Type, Product Targeting Expression, Resolved Product Targeting Expression (Informational only), Ad Format, Ad Format (Informational only), Landing Page URL, Landing Page ASINs, Landing Page Type (Informational only), Brand Entity ID, Brand Name, Brand Logo Asset ID, Brand Logo URL (Informational only), Custom Image Asset ID, Creative Headline, Creative ASINs, Video Media IDs, Creative Type, Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS.

### Tab: SB Multi Ad Group Campaigns
Columns: Product, Entity, Operation, Campaign ID, Portfolio ID, Ad Group ID, Ad ID, Keyword ID, Product Targeting ID, Campaign Name, Ad Group Name, Ad Name, Campaign Name (Informational only), Ad Group Name (Informational only), Portfolio Name (Informational only), Start Date, End Date, State, Brand Entity ID, Campaign State (Informational only), Campaign Serving Status (Informational only), Campaign Serving Status Details (Informational only), Rule Based Budget Is Processing (Informational only), Rule Based Budget Name (Informational only), Rule Based Budget Value (Informational only), Rule Based Budget ID (Informational only), Ad Group Serving Status (Informational only), Ad Group Serving Status Details (Informational only), Budget Type, Budget, Bid Optimization, Product Location, Bid, Placement, Percentage, Keyword Text, Match Type, Native Language Keyword, Native Language Locale, Product Targeting Expression, Resolved Product Targeting Expression (Informational only), Ad Serving Status (Informational only), Ad Serving Status Details (Informational only), Landing Page URL, Landing Page ASINs, Landing Page Type, Brand Name, Consent To Translate, Brand Logo Asset ID, Brand Logo URL (Informational only), Brand Logo Crop, Custom Images, Creative Headline, Creative ASINs, Video Asset IDs, Original Video Asset IDs (Informational only), Subpages, Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS.

### Tab: Sponsored Display Campaigns
Columns: Product, Entity, Operation, Campaign ID, Portfolio ID, Ad Group ID, Ad ID, Targeting ID, Campaign Name, Ad Group Name, Campaign Name (Informational only), Ad Group Name (Informational only), Portfolio Name (Informational only), Start Date, End Date, State, Campaign State (Informational only), Ad Group State (Informational only), Tactic, Budget Type, Budget, SKU, ASIN (Informational only), Ad Group Default Bid, Ad Group Default Bid (Informational only), Bid, Bid Optimization, Cost Type, Targeting Expression, Resolved Targeting Expression (Informational only), Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS, Viewable Impressions, Sales (Views & Clicks), Orders (Views & Clicks), Units (Views & Clicks), ACOS (Views & Clicks), ROAS (Views & Clicks).

### Tab: SP Search Term Report
Columns: Product, Campaign ID, Ad Group ID, Keyword ID, Product Targeting ID, Campaign Name (Informational only), Ad Group Name (Informational only), Portfolio Name (Informational only), State, Campaign State (Informational only), Bid, Keyword Text, Match Type, Product Targeting Expression, Resolved Product Targeting Expression (Informational only), Customer Search Term, Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS.

### Tab: SB Search Term Report
Columns: Product, Campaign ID, Ad Group ID, Keyword ID, Product Targeting ID, Campaign Name (Informational only), Ad Group Name (Informational only), State, Campaign State (Informational only), Bid, Keyword Text, Match Type, Product Targeting Expression, Customer Search Term, Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS.

### Tab: RAS Campaigns
Columns: Product, Entity, Operation, Campaign ID, Ad Group ID, Target ID, Product Ad ID, Portfolio ID, Retailer, Retailer ID, Retailer Offer ID, Name, State, Start Date, End Date, Targeting Type, Target Type, Target Level, Budget, Budget Type, SKU, Ad Group Default Bid, Negative, Product Targeting Expression, Bid, Currency Code, Keyword Text, Keyword Match Type, Auto Match Type, Bidding Strategy, Bidding Adjustment Placement, Bidding Adjustment Percentage, Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS.

### Tab: RAS Search Term Report
Columns: Product, Campaign ID, Ad Group ID, Target ID, Retailer, Retailer ID, Retailer Offer ID, Campaign Name, Ad Group Name, State, Negative, Target Level, Bid, Currency Code, Keyword, Match Type, Resolved Product Targeting Expression, Customer Search Term, Impressions, Clicks, Click-through Rate, Spend, Sales, Orders, Units, Conversion Rate, ACOS, CPC, ROAS.

Notes:
- AdScope v0 prioritizes the Sponsored Products Campaigns tab for core metrics and the main STR file; other tabs are available for future use or extended views.
- Fuzzy matching will map required columns based on these observed headers.
