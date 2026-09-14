# Dataset attribution and license

**SemEval 2025 Task 9: The Food Hazard Detection Challenge**

Source and attribution: the [task organizers and contributors](https://food-hazard-detection-semeval-2025.github.io/).
The task page credits food science / food technology expert annotations to
Agroknow and identifies the dataset license as Creative Commons Attribution-
NonCommercial-ShareAlike 4.0 International (**CC BY-NC-SA 4.0**).

- [License summary](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- [Legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)
- [Original data repository](https://github.com/food-hazard-detection-semeval-2025/food-hazard-detection-semeval-2025.github.io/tree/main/data)

The project's Apache-2.0 license does not relicense this dataset or its derived
label vocabulary. Preserve attribution, the noncommercial restriction and
applicable share-alike terms with dataset-derived materials. No organizer
endorsement is implied.

The acquired CSV bytes are unchanged and stored locally under ignored
`outputs/semeval-st1/sources/`. The protocol extracts unique training category
labels and test row IDs. Inference JSON-wraps the original full text without
truncation, then adds model-generated predictions. These transformations are
disclosed in the protocol and evaluation README. The published scoring function
is attributed at its implementation in `tools/semeval_eval.py`.
