# Monthly P&L Windsor Reconciliation

_Last updated: 2026-03-18 (ET)_

## Goal

Use Windsor settlement data to eventually produce the same or very similar
Monthly P&L output as the current CSV/manual-upload path.

For now, Windsor is being used as a compare/reconciliation source, not as the
active P&L source of truth.

## Current compare context

Initial live investigation snapshot from the Render-deployed compare flow:

1. Scope: `Amazon.com only`
2. Source month: the currently selected compare month in the P&L UI
3. Baseline: active CSV-backed Monthly P&L import month
4. Windsor account: resolved from the matching WBR profile

## Bucket catalog checklist

Use this while reviewing one scope on screen. For each bucket, record:

1. Whether Windsor shows any rows
2. The Windsor amount
3. The CSV amount
4. The delta
5. The top Windsor combo(s), if any

### Revenue buckets

1. `product_sales` — `Seen`
2. `shipping_credits` — `Seen`
3. `gift_wrap_credits` — `No Windsor rows seen`
4. `promotional_rebate_refunds` — `Seen`
5. `fba_liquidation_proceeds` — `TBD`

### Refund buckets

1. `refunds` — `Seen`
2. `fba_inventory_credit` — `Seen as missing in Windsor`
3. `shipping_credit_refunds` — `Seen`
4. `gift_wrap_credit_refunds` — `No Windsor rows seen`
5. `promotional_rebates` — `Seen`
6. `a_to_z_guarantee_claims` — `No Windsor rows seen`
7. `chargebacks` — `No Windsor rows seen`

### Expense buckets

1. `referral_fees` — `Seen`
2. `fba_fees` — `Seen`
3. `other_transaction_fees` — `Seen`
4. `fba_monthly_storage_fees` — `Seen as missing in Windsor`
5. `fba_long_term_storage_fees` — `Seen as missing in Windsor`
6. `fba_removal_order_fees` — `Seen as missing in Windsor`
7. `subscription_fees` — `No Windsor rows seen`
8. `inbound_placement_and_defect_fees` — `TBD`
9. `inbound_shipping_and_duties` — `TBD`
10. `liquidation_fees` — `No Windsor rows seen`
11. `promotions_fees` — `Seen`
12. `advertising` — `Seen as missing in Windsor`
13. `service_fee` — `TBD`

### Non-P&L compare bucket

1. `non_pnl_transfer` — `Seen as missing in Windsor`

## What already looks good

These buckets appear directionally aligned already and likely need either no
work or only small follow-up tuning:

1. `product_sales`
   - CSV: `283,416`
   - Windsor: `290,518`
   - Delta: `+7,102`
   - Observed Windsor combo: `Order / ItemPrice / Principal`
2. `fba_fees`
   - CSV: `(77,189)`
   - Windsor: `(73,764)`
   - Delta: `+3,425`
   - Observed Windsor combo: `Order / ItemFees / FBAPerUnitFulfillmentFee`
3. `referral_fees`
   - CSV: `(41,680)`
   - Windsor: `(42,596)`
   - Delta: `(916)`
   - Observed Windsor combos:
     - `Order / ItemFees / Commission`
     - `Refund / ItemFees / Commission`
4. `marketplace_withheld_tax`
   - CSV: `(20,130)`
   - Windsor: `(20,492)`
   - Delta: `(362)`
   - Observed Windsor combos are the expected marketplace facilitator tax rows
5. `refunds`
   - CSV: `(4,345)`
   - Windsor: `(4,459)`
   - Delta: `(114)`
6. `shipping_credits`
   - Windsor drilldown: `Order / ItemPrice / Shipping`
   - Observed Windsor amount: `9,154`
7. `shipping_credit_refunds`
   - Windsor drilldown: `Refund / ItemPrice / Shipping`
   - Observed Windsor amount: `(274)`
8. `promotional_rebates`
   - Windsor drilldowns:
     - `Order / Promotion / Shipping`
     - `Order / Promotion / Principal`
   - Observed Windsor amount: `(8,103)`
9. `promotional_rebate_refunds`
   - Windsor drilldowns:
     - `Refund / Promotion / Shipping`
     - `Refund / Promotion / Principal`
   - Observed Windsor amount: `130`
10. `promotions_fees`
   - Windsor drilldowns:
     - `AmazonFees / Coupon Participation Fee / Base fee`
     - `AmazonFees / Coupon Performance Based Fee / Base fee`
   - Observed Windsor amount: `(15)`

These are not perfect yet, but they are close enough that the current compare
work should focus first on the clearly missing buckets.

## Buckets that may legitimately be zero

Absence is not automatically a bug. Some buckets are sparse by nature and may
simply be absent for a given product/month/account.

Current examples from the `Amazon.com only` screenshots:

1. `gift_wrap_credits`
2. `gift_wrap_credit_refunds`
3. `a_to_z_guarantee_claims`
4. `chargebacks`
5. `liquidation_fees`
6. `subscription_fees`

Interpretation:

1. `gift_wrap_*` may truly be zero if the product is not gift-wrapped or does
   not generate gift-wrap events in the selected month.
2. `a_to_z_guarantee_claims` and `chargebacks` are event-driven and often
   legitimately absent.
3. `liquidation_fees` may be absent if there were no liquidation events.
4. `subscription_fees` can also be absent in Windsor compare if the monthly
   subscription fee does not land inside the selected scoped subset or date
   window.

Action:

Treat these as `not suspicious yet` unless the CSV baseline for the same month
shows a non-zero value.

## Good signs from the current compare

1. `Top unmapped combos` is empty in the current `Amazon.com only` compare.
2. The dominant ignored Windsor rows are tax variants such as:
   - `Order / ItemPrice / Tax`
   - `Refund / ItemPrice / Tax`
   - `Order / ItemPrice / ShippingTax`
3. That is broadly consistent with the current P&L model, which does not roll
   those ItemPrice tax fields into the visible P&L buckets.

## Current high-priority mismatches

### 1. `advertising` is missing entirely in scoped compare

Observed:

1. CSV: `(33,349)`
2. Windsor: `0`
3. Delta: `+33,349`
4. Bucket drilldown shows no Windsor rows for `Amazon.com only`

Likely causes:

1. The current marketplace-scope filter may be dropping `Cost of Advertising`
   rows because Windsor does not populate `marketplace_name` on some
   service-fee rows.
2. Windsor may use a variant outside the currently coded exact match:
   - current rule expects `transaction_type = ServiceFee`
   - current rule expects `amount_type = Cost of Advertising`
3. CSV-side manual mapping also includes `Refund for Advertiser`; Windsor-side
   compare currently only maps `Cost of Advertising / TransactionTotalAmount`.

Status:

`Needs verification from All-marketplaces compare and/or raw combo evidence.`

### 2. `non_pnl_transfer` is missing entirely in scoped compare

Observed:

1. CSV: `(121,966)`
2. Windsor: `0`
3. Delta: `+121,966`

Likely causes:

1. Same scoped-filter issue as advertising: transfer/disbursement rows may not
   carry `marketplace_name = Amazon.com` even when they belong to the same
   account window.
2. The compare logic currently only maps:
   - `transaction_type = transfer`
   - `other-transaction` descriptions containing `transfer` or
     `to your account`
3. Windsor may use additional payout/disbursement descriptions not yet covered.

Status:

`High-priority investigation item.`

### 3. `fba_inventory_credit` is missing entirely in scoped compare

Observed:

1. CSV: `1,178`
2. Windsor: `0`
3. Delta: `(1,178)`

Likely causes:

1. Windsor reimbursement rows may be absent in the selected scope because of
   blank or non-Amazon marketplace labels.
2. Windsor may use additional reimbursement amount-type labels beyond:
   - `fba inventory reimbursement`
   - `mcf inventory reimbursement`

Status:

`Open.`

### 4. `fba_monthly_storage_fees` is missing entirely in scoped compare

Observed:

1. CSV: `(761)`
2. Windsor: `0`
3. Delta: `+761`

Likely causes:

1. Windsor storage-fee rows may be filtered out by the current
   `marketplace_name` scope logic.
2. Windsor may use variants beyond the current exact description:
   - current rule expects `other-transaction / Storage Fee`
3. The CSV/manual path also maps `Capacity Reservation Fee`, which may not come
   through Windsor under the currently handled description set.

Status:

`Open.`

### 5. `fba_long_term_storage_fees` is missing entirely in scoped compare

Observed:

1. CSV: `(130)`
2. Windsor: `0`
3. Delta: `+130`

Likely causes:

1. Windsor may use a different description than the currently coded
   `StorageRenewalBilling`.
2. Same marketplace-scope issue is still possible.

Status:

`Open.`

### 6. `fba_removal_order_fees` is missing entirely in scoped compare

Observed:

1. CSV: `(94)`
2. Windsor: `0`
3. Delta: `+94`

Likely causes:

1. The selected month may simply have no Windsor `RemovalComplete` or
   `DisposalComplete` rows inside the scoped subset.
2. Windsor may use additional description variants.
3. Same marketplace-scope issue is possible for non-order operational fees.

Status:

`Open.`

### 7. `other_transaction_fees` exists in Windsor but not in the CSV baseline

Observed:

1. CSV: `0`
2. Windsor: `(2,862)`
3. Delta: `(2,862)`
4. Observed Windsor combos:
   - `Order / ItemFees / ShippingChargeback`
   - `Refund / ItemFees / ShippingChargeback`
   - `Refund / ItemFees / RefundCommission`

Interpretation:

1. This is probably a real source-model difference, not just a missing Windsor
   mapping.
2. The implementation plan explicitly says these Windsor combos belong in
   `other_transaction_fees`, so the compare service is likely doing the right
   thing here.
3. The CSV/manual-upload path may not expose the same economics in the same
   column/bucket, or the current month’s active CSV import may truly have `0`
   in `other_transaction_fees`.

Status:

`Needs raw CSV/source validation before changing Windsor mapping.`

## Working hypothesis: scoped marketplace filtering is currently too strict

This is the strongest current hypothesis from the screenshots.

Evidence:

1. Buckets tied to order-level rows still show healthy `Amazon.com` totals:
   - `product_sales`
   - `fba_fees`
   - `referral_fees`
   - `marketplace_withheld_tax`
2. Several buckets that often come from service-fee, reimbursement, storage, or
   transfer-style rows disappear completely in `Amazon.com only`:
   - `advertising`
   - `non_pnl_transfer`
   - `fba_inventory_credit`
   - `fba_monthly_storage_fees`
   - `fba_long_term_storage_fees`
   - `fba_removal_order_fees`
3. The current scope filter only keeps rows whose Windsor
   `marketplace_name` exactly matches allowed marketplace labels.

Why this matters:

If Windsor leaves `marketplace_name` blank or non-standard on account-level fee
rows, the compare flow will undercount those buckets in `Amazon.com only` even
though the economics may still belong to the US side of the account.

This does not prove the scoped filter is wrong yet. It only means it is the
first thing to verify.

## Immediate next checks

1. Re-run the same month with `All Windsor marketplaces`.
   - If missing buckets suddenly appear, scope filtering is the main problem.
2. Re-run the same month with `Amazon.com + Amazon.ca`.
   - If missing buckets still only appear in `All`, then the issue is likely
     blank/non-standard marketplace labels rather than just Canada leakage.
3. Capture the bucket delta table for all three scopes:
   - `all`
   - `amazon_com_only`
   - `amazon_com_and_ca`
4. For any bucket still at `0` in `all`, inspect raw combo variants and extend
   Windsor mapping if the implementation plan says that bucket should exist.
5. Do not change `other_transaction_fees` mapping yet.
   - First confirm whether the CSV baseline truly has `0` in the raw import
     source or whether the source economics are represented elsewhere.

## Likely implementation follow-ups

These are candidates, not approved fixes yet:

1. Add better scoped-filter diagnostics:
   - count/amount of Windsor rows excluded by marketplace scope
   - count/amount of rows with blank marketplace labels
2. Add a reconciliation note to the compare payload for blank-marketplace rows.
3. Expand Windsor mapping coverage for service-fee and reimbursement variants if
   raw evidence shows label drift.
4. If the data supports it, revise scoped compare behavior so blank marketplace
   rows are not silently dropped without explanation.

## Decision log

### 2026-03-18

1. Started a dedicated Windsor reconciliation log instead of scattering
   findings across chat history.
2. Based on the first `Amazon.com only` screenshots, the current top suspicion
   is not “lots of unmapped Windsor data”; it is “scoped marketplace filtering
   is hiding several expected non-order buckets.”
3. Verified that suspicion directly from the exported Windsor CSV
   (`/Users/jeff/Downloads/data (13).csv`):
   - `ServiceFee / Cost of Advertising / TransactionTotalAmount`
     - `79` rows
     - `-40,714.18`
     - marketplace label is blank on all rows
   - `other-transaction / FBA Inventory Reimbursement / *`
     - `187` rows
     - `1,343.57`
     - marketplace label is blank on all rows
   - `other-transaction / other-transaction / Storage Fee`
     - `1` row
     - `-761.34`
     - marketplace label is blank
   - `other-transaction / other-transaction / StorageRenewalBilling`
     - `2` rows
     - `-136.02`
     - marketplace label is blank
   - `other-transaction / other-transaction / DisposalComplete|RemovalComplete`
     - `65` rows
     - `-96.11`
     - marketplace label is blank on all rows
   - `other-transaction / other-transaction / Subscription Fee`
     - `1` row
     - `-16.65`
     - marketplace label is blank
4. Added compare-flow scope diagnostics in code so the UI can now show:
   - excluded row count and amount
   - blank-marketplace excluded row count and amount
   - excluded mapped buckets
   - top blank-marketplace combos
