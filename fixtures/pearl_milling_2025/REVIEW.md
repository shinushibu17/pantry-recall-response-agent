# Source check and authored reference answers

This is one **development** recall and eight synthetic inventory scenarios, now version 2.
Codex read the official notice and raw enforcement record, then authored
`scope.json`, `inventory.json`, and `expected.json` before implementing the
matcher. Expectations were checked directly against the source, not populated
from program outputs. **No independent human has signed off these labels.**
The user can perform that sign-off using the table and pinned evidence below.

## Scope check

- Recall F-0553-2025, event 96134. Company announcement January 14, 2025;
  FDA publication/content date January 15, 2025. Downloaded September 12, 2026.
  This is a later snapshot for historical replay, not a claim that all API
  information was available at recall initiation. API metadata and HTTP dates
  are preserved in `sources/acquisition.json`; HTTP Last-Modified is not treated
  as the announcement's editorial date.
- The table contains **one** product row: Pearl Milling Company **Original**
  Pancake & Waffle Mix, 32 OZ (2LB) 907g, printed UPC `30000 65040`, and complete
  Code Date & Manufacturing Code `BBD SEP 13 25 P`. These conditions are ANDed. The notice does not specify a separate lot code.
  The date and trailing `P` are both necessary; this is not an all-lots recall.
- The printed UPC has ten digits. Preserve that source representation. Remove
  spaces only for comparison; do not invent a leading digit/check digit or a
  mapping to a twelve-digit scanned UPC. Unknown representations require review.
- `best_by_manufacturing_code` intentionally holds the **entire printed composite code**.
  An optional separately transcribed best-by date is a consistency check, not
  a substitute for the manufacturing code.
- The notice bounds the product scope and states that other Pearl Milling
  products are not recalled. The lookalike's identity/UPC are synthetic authored
  label evidence; its UPC and lot do not assert real catalog membership.
- Enforcement `product_description` and `code_info` agree with the table.
  Its firm is Frito-Lay, Inc. Headquarters; the notice issuer is The Quaker Oats
  Company. Both are preserved without inferring a corporate relationship.
  Company instructions are attributed to Quaker, not to FDA. The API's later
  termination status has no role in matching or pantry action completion.
- The consumer nonconsumption/discard instruction applies **if consumers have
  an allergy or sensitivity to milk**. Retain audience and trigger. It is not
  an unconditional pantry disposal instruction. Pantry holds and review rules
  are authored application policy. No disposal method is invented.
- Listed states and receipt dates are context, not exclusion tests.

## Expected outcomes (checked before coding)

| Stock group | Evidence calculation | Expected outcome |
| --- | --- | --- |
| affected | Correct identity, size, UPC, full code, all six labels checked; receipt Nov 1 precedes stated retail availability Nov 18 | AFFECTED; hold recommended; action open |
| missing_code | Correct product/UPC, complete code absent | NEEDS_EVIDENCE; inspect four boxes at A2 |
| excluded_code | Correct product; all three boxes say SEP 14, outside SEP 13 scope | Propose NOT_AFFECTED_BY_THIS_RECALL for review |
| similar_product | Buttermilk Complete is a different checked variant, even with matching lot text | Retrieved candidate; propose exclusion for review |
| mixed_codes | Only one of nine labels has an excluded code | NEEDS_EVIDENCE; inspect/split the bin |
| unrelated | Black beans have no retrieval feature | Not selected; PENDING / NOT_ASSESSED |
| ambiguous_code | Numeric date notation differs from the printed source format | NEEDS_REVIEW; never silently repair |
| contradictory_label | Full code says SEP 13, separate date says SEP 14 | NEEDS_REVIEW; preserve the conflict |

`expected.json` records each condition's true/false/unknown value, missing and
review fields, candidate inclusion, proposal, action state, and evidence IDs.
`fixture.lock.json` freezes hashes before the first agent run for version 2; version 1 was frozen before the first matcher run. Source spans
are zero-based, end-exclusive character offsets in the UTF-8-decoded
`sources/notice.txt`; this derivative is reproduced from the preserved HTML.

## Limits and source terms

No held-out recall, model evaluation, benchmark, field accuracy estimate, human
confirmation, or physical inventory action is represented here. The purpose of
these authored examples is to test deterministic behavior. Scope extraction is
manual, not an autonomous parser of arbitrary notices.

Sources: [FDA-hosted Quaker announcement](https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/quaker-issues-limited-recall-undeclared-milk-pearl-milling-company-original-pancake-waffle-mix),
[openFDA enforcement](https://open.fda.gov/apis/food/enforcement/).
Exact API request, hashes, and retrieval times are in `sources/acquisition.json`.

The preserved notice is an FDA-hosted company announcement. No separate
copyright restriction was observed on this page. FDA's
[website copying policy](https://www.fda.gov/about-fda/about-website/website-policies)
permits reuse unless otherwise noted and requests copy dates and source links.
[openFDA terms](https://open.fda.gov/terms/) identify generally public-domain/CC0
data, with exceptions for marked third-party material. Source snapshots retain
their source terms; the project's code license does not relicense them. Product
photo assets are linked in the original HTML and were not downloaded.

## Version 2 correction record

The user independently checked the notice and identified the identifier naming,
product bounding sentence, purchase-availability date, and consumer-action
audience. This is source review, not blanket approval of every synthetic label.
The complete printed code is now `best_by_manufacturing_code`; missing and
excluded cases are named `missing_code` and `excluded_code`. Stock coverage uses
`single_code_group`/`mixed_codes` rather than claiming a separately printed lot.

The existing affected scenario now has a deliberate synthetic receipt date of
2024-11-01, before the stated retail purchase-availability date 2024-11-18. Its
expected result remains AFFECTED: that prose does not specify a production or
receipt restriction. `notice.purchase_availability` preserves the exact quote.
Both exclusion proposals cite `notice.other_products` as product-scope context;
the table still supplies the specific code restriction for the excluded-code
case. The Original versus Buttermilk Complete discriminator is explicit.

All eight identification/action expectations are unchanged. This schema/source
correction was authored and frozen before the first agent run; it is not tuning
against agent answers. The original frozen fixture is preserved at
`../archive/pearl_milling_2025_v1/`. The source HTML/JSON bytes are unchanged.
Pantry hold/quarantine remains `policy.hold`, while the conditional consumer
nonconsumption/discard sentence remains `notice.consumer_instruction`.
