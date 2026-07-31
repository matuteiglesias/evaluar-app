# Legacy educational content inventory

## Reproducible result

Run the repository-only validator with:

```bash
python scripts/content_inventory.py --check
```

This is the documented CI command. It rebuilds all three artifacts in memory and
fails if any committed byte differs. To intentionally regenerate after a reviewed
content change, omit `--check`. `--fail-on-issues` is available for a future
zero-warning policy; existing, explicitly recorded conflicts mean it is not the
baseline CI command.

The v1 inventory is rooted at content Git commit
`393efdf9dc13c2e3f6fd3eb823b2d4c074761b72` and contains no wall-clock timestamp.
The validator records canonical relative paths, canonical index-row hashes,
content and referenced-asset hashes, metadata, global keys, validation outcomes,
and that content source commit in `artifacts/legacy/content-manifest.v1.json`.

## Corpus outcome

| Area | Outcome |
|---|---|
| Course directories | 2: `demo_course`, `tda` |
| Course indexes | 2 present and parseable with all required columns |
| Indexed exercises | 110 (`demo_course`: 4; `tda`: 106) |
| `.tex` files | 110; every file has exactly an indexed path in this corpus |
| Missing/empty/invalid UTF-8 exercise files | 0 detected |
| Content images | 7 in `tikzpics/`; all 7 referenced through `% FIGURA` |
| Documentation images | 2 in `docs/assets/`; recorded as generated/non-authoritative and not canonical exercise assets |
| Missing/orphan content images | 0 detected |
| Root-level legacy CSV/text/TeX files | 0 found |
| Generated documentation | 1 generated `docs/` tree, 18 HTML files; non-authoritative |
| Validation findings | 13 warnings, 0 errors |

The four numeric IDs `101`, `102`, `201`, and `202` occur in both courses. They
remain distinct as `demo_course:<id>` and `tda:<id>`; the validator does not
normalize or merge them. Five duplicate-content hash groups are recorded: the
four cross-course pairs and the within-course pair `tda:502`/`tda:504`.

Four exercise entries contain raw table HTML (`demo_course:102`, `tda:102`,
`tda:408`, and `tda:415`) whose `table`, `tr`, and `td` elements are outside the
current renderer allowlist. No suspicious LaTeX command from the validator's
renderer-focused denylist was found. These are warnings requiring authority and
rendering review, not automatic corrections.

## Coverage and interpretation

The command inventories every immediate directory beneath `exercises/`, every
`index.csv` and `.tex` there, root-level legacy `.csv`/`.txt`/`.tex`, images in
known content asset directories and `docs/assets`, and generated HTML trees. It
extracts `% FIGURA`, HTML `<img src>`, and LaTeX `\includegraphics` references.

It detects missing indexes, strict CSV parse errors, missing columns, duplicate
IDs/files, repeated cross-course IDs, missing/orphan content files, missing/orphan
images, path escapes and absolute paths, invalid UTF-8, empty files, duplicate
hashes, unsupported embedded HTML, suspicious LaTeX, unsafe course slugs, and
filename/metadata-ID mismatch. Findings remain in
`artifacts/legacy/content-issues.csv`; no content is silently corrected.

The manifest is an immutable description of the inspected Git content, not a
claim that pedagogical text is correct. Binary hashes establish byte identity,
not authorship, safety, or quality.
