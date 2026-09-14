# Clarification of inherited protocol metadata

The frozen v6 protocols inherit configuration fields from v5. This note corrects
descriptive metadata without changing the frozen code, requests, predictions,
selection rule or original protocol files.

- `retrieval.exclusions` ends with the inherited sentence “No label-based
  retrieval or global test filtering.” The first part of that sentence is stale
  for `pro-balanced-retrieval`: v6 deliberately stratifies additional examples
  by **training hazard labels**, as specified before inference in `plan.json`
  and implemented in `BalancedRetriever`. It does not use target annotations.
  Exact normalized target-body exclusion, per-query duplicate-body exclusion
  and original-training-order tie-breaking still apply. There is no global
  test filtering.
- For `svm-*` protocols, `model_id`, `system_prompt`, `retrieval`, `tool_config`
  and `inference_config` describe the inherited v5 Bedrock component. They are
  not instructions to make new Bedrock calls. `variant` selects the supervised
  combination; `plan.json` freezes its training/features/model parameters and
  inherited prediction hashes. The supervised runner records zero new model
  attempts, the parent record hash and the SVM decision-trace hash per row.
- `retrieval.neighbors=4` is the product-neighbor count. The balanced-retrieval
  variant adds up to one further distinct example for each training hazard
  category, with its separate 900-character limit. The code and frozen plan
  define this addition.

These metadata defects do not change the completed inference. They are retained
here so that consumers do not mistake a shared protocol template for the full
method description. See [the frozen plan](plan.json),
[implementation](../../tools/semeval_hybrid.py), and
[record reconstruction](verification.json).
