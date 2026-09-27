# MMLongBench-Doc — Dataset Inspection (CP-2.1)

Inspected 2026-09-27. Reproduce with:

```bash
python scripts/download_mmlongbench_doc.py      # -> data/raw/mmlongbench-doc/ (+ MANIFEST.json with sha256)
python scripts/inspect_mmlongbench_doc.py       # -> data/processed/mmlongbench-doc/inspection.json
```

All numbers below are facts about the dataset release, not experiment results.

## 1. Source, version, license

| Item | Value |
|---|---|
| Paper | Ma et al., *MMLongBench-Doc: Benchmarking Long-context Document Understanding with Visualizations*, NeurIPS 2024 (Datasets & Benchmarks) |
| Official repo | GitHub `mayubo2333/MMLongBench-Doc`, pinned commit `d73f0dc0be7e0a2ff6a403d5fe65fcd96461f384` (2025-09-28) |
| Hugging Face | `yubo2333/MMLongBench-Doc`, pinned revision `2ff6aa9237fc777b6627dc57a486e9225ac5fb86` (2025-11-06) |
| License | Apache-2.0 (GitHub LICENSE; also stated in the LAD-RAG paper, App. B) |
| Files used | `data/samples.json` (GitHub) = annotations; `data/documents/*.pdf` (GitHub) = 135 PDFs, 666.9 MB incl. annotations |
| Integrity | every GitHub file verified against its git blob hash; every PDF's sha256 also matches the hash listed in the HF tree (136/136 comparable files) |

### Download incident (why PDFs come from GitHub)
On 2026-09-27 the Hugging Face file endpoint (`/resolve/...`, served via the xet bridge) returned
**wrong content** for some PDFs: e.g. `mi_phone.pdf` returned 31,841,340 bytes (the bytes of
`NYU_graduate.pdf`), although the HF tree lists sha256 `c5feec13…` (24,877,442 bytes), which is exactly
the GitHub file. The HF *metadata* is consistent with GitHub; only the served bytes were wrong. PDFs are
therefore downloaded from GitHub and cross-checked against the HF-listed hashes (decision D-010).

## 2. Annotation format (`samples.json`)

A JSON list of 1,082 objects with 7 string fields:

| Field | Type | Meaning / format |
|---|---|---|
| `doc_id` | str | PDF file name, e.g. `PH_2016.06.08_Economy-Final.pdf` (= file in `documents/`) |
| `doc_type` | str | one of 7 document types (below) |
| `question` | str | question text |
| `answer` | str | gold answer; `"Not answerable"` for unanswerable questions |
| `evidence_pages` | str | **Python-list literal as a string**, e.g. `"[19, 20]"`, `"[]"`; ints |
| `evidence_sources` | str | Python-list literal, e.g. `"['Chart', 'Table']"` |
| `answer_format` | str | `Int`, `Str`, `Float`, `List`, `None` (`None` = unanswerable) |

No question ID field exists — the loader must assign stable IDs (CP-2.2). No parse errors; no
duplicate rows.

## 3. Statistics

| | Value | LAD-RAG paper (App. B) |
|---|---|---|
| Questions | 1,082 | 1,082 ✔ |
| Documents | 135 (all referenced, none missing) | 135 ✔ |
| Pages per document | mean 48.36, median 28, min 9, max 468; total 6,529 | mean 47.5 ✗ (see §6.1) |
| Multi-page questions | 360 (33.3% of all questions) | 33% ✔ |
| Single-page questions | 494 | — |
| Questions with empty `evidence_pages` | 228 | — |
| `answer == "Not answerable"` | 223 | — |

- `answer_format`: Int 299, Str 250, None 223, Float 159, List 151.
- `doc_type` (questions): Research report / Introduction 292, Academic paper 199, Guidebook 155,
  Tutorial/Workshop 138, Financial report 117, Brochure 100, Administration/Industry file 81.
- Mean pages by doc type: Financial report 87.1, Guidebook 78.4, Tutorial/Workshop 57.5,
  Research report 39.4, Academic paper 34.8, Brochure 30.3, Administration/Industry file 16.8.
- `evidence_sources` (label occurrences): Pure-text 305, Figure 304, Table 218, Chart 178,
  Generalized-text (Layout) 119.
- Number of evidence pages per question: 0: 228, 1: 494, 2: 247, 3: 40, 4: 22, 5: 14, 6: 12, 7–24: 25.

Subsets under D-009: **evidence subset 854 questions**, **no-evidence subset 228 questions**.

## 4. Evidence-page indexing: 1-based physical pages ✔

- Empirical test: for 55 single-page questions whose short answer string occurs on exactly one page of
  the PDF text layer, the answer is on the annotated page under a **1-based** reading in 46/55 cases
  and under a 0-based reading in **0/55** cases.
- Bounds: 30 evidence pages equal the document's page count (valid only if 1-based).
- Conclusion: `evidence_pages` are **1-based physical page positions**, matching our convention
  (D-007). No conversion needed, except for the invalid values below.

## 5. Unanswerable vs. empty evidence

"Not answerable" and "empty evidence" are **not the same set**:

| | Empty evidence | Non-empty evidence |
|---|---|---|
| Not answerable (223) | 216 | **7** (e.g. "what is the color of the stamp in the 6th page?" → `[6]`) |
| Answerable (859) | **12** (e.g. counting absent objects → `"0"`, whole-document questions) | 847 |

D-009 subsets are defined by evidence emptiness (as intended), not by answerability.

## 6. Data-quality issues

### 6.1 Wrong PDF shipped for `dr-vorapptchapter1emissionsources-…_95.pdf` (10 questions)
The file is **byte-identical** to `digitalmeasurementframework22feb2011v6novideo-…_95.pdf`
(same sha256, 196 pages) in both GitHub and HF. Rendered page 1 reads *"Making Sense of Data: Creating a
Structured Digital Measurement … Framework"*, while its 10 questions ask about vehicle emissions and
climate change. These 10 questions (evidence pages up to 75) cannot be answered from the shipped PDF.
Plausible but unverified: the paper-era file was a different ~80-page PDF; replacing 196 by ~80 pages
would reproduce the paper's mean of 47.5 pages (6,529 − 116 ≈ 47.5 × 135).

### 6.2 Invalid evidence page numbers (9 questions)
| Document | Annotated | Pages in PDF | Likely cause |
|---|---|---|---|
| `edb88a99…pdf`, `2303.08559v2.pdf`, `f86d073b…pdf` | `[0]` | 20 / 30 / 20 | 0 is outside 1-based range |
| `PS_2018.01.09_STEM_FINAL.pdf` | `[115, 116]` | 105 | printed page labels? |
| `san-francisco-11-contents.pdf` (4 questions) | 288–318 | 40 | printed page labels of a book excerpt |
| `f1f5242528411b262be447e61e2eb10f.pdf` | `[…, 1418, 20]` | 20 | typo (one value) |

Our data models reject these values (D-007); how to handle them is decided in CP-2.2.

### 6.3 Identical PDFs under two names (not an error for the questions)
`SAO-StudentSupport_Guidebook-Content.pdf` and `StudentSupport_Guidebook.pdf` are byte-identical
(5 + 6 questions). Both are legitimately the same guidebook; questions are distinct.

### 6.4 No text layer (28 of 135 PDFs)
28 PDFs (mostly SlideShare decks `*_95.pdf`, plus `NUS-FASS-Graduate-Guidebook-2021-small.pdf`) have no
extractable text: PyMuPDF returns empty text for every page. Text-based retrieval over raw PDF text
(e.g. BM25 on page text, Phase 3) is impossible for them without OCR or LVLM extraction — the LAD-RAG
baselines operate over LVLM-generated element summaries instead. This must be decided before CP-3.1.

### 6.5 Minor
PyMuPDF prints non-fatal "could not parse color space" warnings while reading at least one PDF
(source file not identified); the inspection completed and no PDF failed to open.

## 7. GitHub vs. Hugging Face annotations

| | Rows |
|---|---|
| GitHub `samples.json` | 1,082 (= paper) |
| HF `train` split (dataset viewer rows API) | 1,091 |
| Rows only in HF | 37 = 26 new questions + 11 edited versions of GitHub questions |
| Rows only in GitHub | 28 = 11 pre-edit versions + 17 not present in HF |

Edits change answer / answer_format / evidence_sources (10 each) and evidence_pages (8). The HF split is a
later revision; the **GitHub `samples.json` (1,082) matches the LAD-RAG paper** and is used (D-010).

## 8. Loader policy (resolved in CP-2.2, D-012)

Loader: `multimodal_document_extraction.datasets.mmlongbench_doc.load_mmlongbench_doc()`.

1. Question IDs: `mmlb-<index:04d>-<sha1(doc_id + "\n" + question)[:8]>`.
2. Invalid evidence pages (§6.2): dropped, original kept in `metadata.raw_evidence_pages`,
   flag `invalid_evidence_pages`.
3. Wrong `dr-vorapp` PDF (§6.1): flag `wrong_document`.
4. `evidence_pages` / `evidence_sources` parsed with `ast.literal_eval` and type-checked.
5. `doc_type`, `evidence_sources`, `answer_format` kept for per-category analysis (paper Tables 3, 5).

| Set | Questions | Evidence subset | No-evidence subset |
|---|---|---|---|
| Full (paper-comparable count) | 1,082 | 846 | 236 |
| Clean (no flags; primary) | 1,063 | 837 | 226 |

The full set's evidence subset is 846, not the 854 of §3, because 8 invalid-page questions lose all
their evidence pages when out-of-range values are dropped.
