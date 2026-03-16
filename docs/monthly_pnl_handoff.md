# Monthly P&L Handoff

_Last updated: 2026-03-16 (ET)_

This is the fast restart point after the December 2025 validation run was
finished live.

## Current live state

1. December 2025 is now materially complete for the validation profile and the
   report matches the agency manual P&L at report level.
2. Validation profile:
   - `c8e854cf-b989-4e3f-8cf4-58a43507c67a`
3. Active December import is now the older source file that the manual workbook
   was based on:
   - import `c84cade9-6633-427f-b4b0-2371d0aca344`
   - source filename `dec2025data-olderfile.csv`
   - created `2026-03-16 15:34:59+00`
   - finished `2026-03-16 15:35:41+00`
4. Active December import month:
   - import month `b862b4c2-fe8f-48be-8607-7b353ebc5b91`
   - `entry_month = 2025-12-01`
   - `is_active = true`
   - `unmapped_amount = 0.00`
5. The stale bad `Jan 2026` carryover remains gone.
6. The UI unmapped warning is now gone for December 2025.
7. The `/reports` frontend now treats WBR and Monthly P&L as separate sibling
   report surfaces at the marketplace level. The shared header exposes a WBR /
   Monthly P&L switcher, and the client hub shows each surface independently.
8. The Monthly P&L page now shows active import provenance in-product:
   filename, timestamps, import ID, and active months for the current view.

## What was confirmed

### 1. The report page does not re-parse uploaded CSVs

Uploads parse once during `POST /transaction-upload` and persist:

1. raw rows into `monthly_pnl_raw_rows`
2. normalized facts into `monthly_pnl_ledger_entries`
3. month activation in `monthly_pnl_import_months`

The report path reads persisted ledger/import tables only.

### 2. The remaining December mismatch was mostly source drift

The newer download `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`
and the older download used by the manual workbook do not represent the same
December settlement coverage.

Important consequence:

1. The newer file can be internally correct but still disagree with the manual
   workbook by about `~1100` because Amazon shifted settlement-period inclusion
   between download dates.
2. Importing the older source file immediately moved the system totals onto the
   manual workbook numbers.

### 3. The final live report failure was a database performance problem

The first RPC version fixed the Python paging problem, but the SQL function was
still slow because it scanned all historical ledger rows for the profile.

Observed live facts on 2026-03-16:

1. profile had `532,202` ledger rows across multiple historical imports
2. only one active month slice actually mattered for the December report
3. old RPC path still took roughly `10s` to `40s` in Postgres and could hit
   statement timeouts

Root cause:

1. `pnl_report_bucket_totals` joined active import months after filtering
   ledger rows by `profile_id` and date
2. there was no usable index on `import_month_id`
3. Postgres chose a parallel sequential scan over the whole ledger table

Fix:

1. add index on `monthly_pnl_ledger_entries(import_month_id, entry_month, ledger_bucket)`
2. rewrite the RPC to resolve active month IDs first, then join ledger rows by
   `import_month_id`

After that change:

1. the same RPC dropped to about `87ms` at the function boundary
2. the underlying aggregate query dropped to about `506ms`

## December 2025 final numbers

These are the current live December totals after the older-file import and the
final mapping cleanup.

### Core report totals

1. `total_gross_revenue = 339,770.20`
2. `total_refunds = -11,314.14`
3. `total_net_revenue = 328,456.06`
4. `total_expenses = -173,735.13`

These match the manual workbook target values to rounding/penny level:

1. manual gross revenue `339,770.2`
2. manual refunds `-11,314.1`
3. manual net revenue `328,456.1`
4. manual total expenses `-173,735.1`

### Key live line items

1. `product_sales = 332,515.76`
2. `shipping_credits = 7,087.47`
3. `gift_wrap_credits = 35.91`
4. `promotional_rebate_refunds = 131.06`
5. `refunds = -4,889.93`
6. `fba_inventory_credit = 386.22`
7. `shipping_credit_refunds = -128.82`
8. `promotional_rebates = -6,681.61`
9. `referral_fees = -48,954.01`
10. `fba_fees = -95,183.80`
11. `other_transaction_fees = 0.08`
12. `fba_monthly_storage_fees = -4,125.33`
13. `fba_long_term_storage_fees = -44.21`
14. `fba_removal_order_fees = -112.31`
15. `subscription_fees = -16.87`
16. `inbound_placement_and_defect_fees = -3,451.86`
17. `promotions_fees = -645.00`
18. `advertising = -21,201.82`

### Still intentionally outside report expenses

1. `marketplace_withheld_tax = -23,300.36`
2. `non_pnl_transfer = -142,262.94`

## Root causes that were fixed

### 1. Blank-type promo rows were being skipped

The real December file contained:

1. `raw_type = null`
2. `raw_description = "Price Discount - ..."`
3. `other transaction fees = -245.00`

Old importer behavior skipped rows with blank `type`.

Fixed behavior:

1. keep rows when either `type` or `description` exists
2. match `description starts_with "Price Discount"` to `promotions_fees`

### 2. Manual-model special rows were broader than the first importer pass

Added coverage for manual workbook mappings including:

1. `Amazon Fees` / `Vine Enrollment Fee`
2. `Coupon Redemption Fee`
3. `Deal`
4. `Price Discount`
5. `Refund for Advertiser`
6. `FBA Transaction fees`
7. `Fee Adjustment`
8. `A-to-z Guarantee Claim`
9. `Chargeback Refund`
10. `FBA Removal Order*`
11. `FBA Amazon-Partnered Carrier Shipment Fee`
12. `FBA International Freight Shipping Charge`
13. `FBA International Freight Duties and Taxes Charge`

### 3. `Order / other` and `Refund / other` did not match the workbook

Manual workbook behavior:

1. `Order / other` belongs in `Other transaction fees`
2. `Refund / other` belongs in `Refunds`

The importer now mirrors that behavior for future imports.

### 4. `FBA Removal Order: Disposal Fee` missed the seeded rule

The workbook treats:

1. `FBA Inventory Fee / FBA Removal Order: Disposal Fee`

as:

1. `FBA removal order fees`

The first rule matched only exact description `FBA Removal Order`. This was
changed to a `starts_with` rule.

## Live migrations now applied

These Monthly P&L migrations are now live in Supabase:

1. `20260315200000_monthly_pnl_phase1_foundation.sql`
2. `20260316173000_allow_monthly_pnl_reimport_same_sha.sql`
3. `20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
4. `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
5. `20260316203000_add_monthly_pnl_manual_model_rules.sql`
6. `20260316194500_optimize_monthly_pnl_report_rpc_active_months.sql`
7. `20260316195500_fix_monthly_pnl_removal_and_refund_other_mapping.sql`

## Relevant commits now on `main`

1. `280b3af` - deploy backend report fix and earlier P&L report updates
2. `fcd0f9e` - align Monthly P&L with manual workbook mappings
3. `676851d` - optimize Monthly P&L report RPC for active months
4. `586c5a9` - map remaining Monthly P&L workbook edge cases

## Important note about the active December data

The currently active older-file December import was uploaded before the final
edge-case importer changes were pushed. To avoid forcing another manual upload,
the live active import was corrected in-place on 2026-03-16 for two residual
items:

1. `FBA Removal Order: Disposal Fee` moved from `unmapped` to
   `fba_removal_order_fees`
2. one `Refund / other = 3.60` was folded into the existing `refunds` ledger row

That means:

1. the live active December data is correct now
2. future imports should produce the same result automatically once the latest
   backend deploy is serving commit `586c5a9`

## What is next

December 2025 debugging is no longer the main blocker. The next tranche should
move from one-month debugging to productizing the workflow.

### Highest-value next steps

1. `COGS pipeline`
   - build/upload the Monthly P&L COGS source so `gross_profit` and
     `net_earnings` can reconcile fully, not just revenue/expense sections
2. `Source drift handling`
   - expand the lightweight UI guidance into explicit operator messaging and, if
     needed, a dedicated warning state when workbook reconciliation depends on
     matching the original Amazon export date
3. `Broader validation`
   - validate another month and/or another client profile using the same manual
     mapping logic
4. `Deploy verification`
   - before any future re-import testing, confirm Render is serving the latest
     backend commits (`676851d`, `586c5a9`) so the import path itself matches
     the now-correct live DB state

### What not to do casually

1. Do not replace the active December import on the validation profile unless
   the user explicitly wants to change the validated source basis.
2. The newer file `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`
   is still useful for engineering/debugging, but it is not the right artifact
   if the goal is to reproduce the existing manual December workbook exactly.

## Where the code lives

1. [transaction_import.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/transaction_import.py)
2. [report.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/report.py)
3. [pnl.py](/Users/jeff/code/agency-os/backend-core/app/routers/pnl.py)
4. [test_pnl_transaction_import.py](/Users/jeff/code/agency-os/backend-core/tests/test_pnl_transaction_import.py)
5. [test_pnl_report.py](/Users/jeff/code/agency-os/backend-core/tests/test_pnl_report.py)
