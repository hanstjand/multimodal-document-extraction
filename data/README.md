# Data

Nothing in `raw/`, `processed/`, or `technical/` is committed (see `.gitignore`).
Every dataset added here must be documented below: source URL, version / revision,
download date, license, checksum, and the checkpoint that introduced it.

| Directory | Contents |
|---|---|
| `raw/` | Original downloads, never modified in place |
| `processed/` | Derived artifacts (inspection reports, rendered pages, extracted elements, graphs, indices) — reproducible from `raw/` + code |
| `technical/` | Technical documents / datasheets for the domain-shift study (Phase 5) |

## Datasets

### MMLongBench-Doc — `raw/mmlongbench-doc/` (CP-2.1)

| Item | Value |
|---|---|
| Download | `python scripts/download_mmlongbench_doc.py` |
| Annotations | GitHub `mayubo2333/MMLongBench-Doc` @ `d73f0dc0…f384`, `data/samples.json` (1,082 questions) |
| PDFs | same GitHub commit, `data/documents/*.pdf` (135 files) |
| Also stored | HF `yubo2333/MMLongBench-Doc` @ `2ff6aa92…fb86`, `hf/train-00000-of-00001.parquet` (1,091 rows, later revision; not used) |
| License | Apache-2.0 |
| Downloaded | 2026-09-27 |
| Checksums | `raw/mmlongbench-doc/MANIFEST.json` (sha256 per file) |
| Size | 666.9 MB |
| Notes | see `docs/studies/ladrag/MMLONGBENCH_DOC.md` (format, indexing, known data-quality issues) |

Layout:

```
raw/mmlongbench-doc/
  MANIFEST.json
  github/samples.json, github/README.md
  hf/train-00000-of-00001.parquet
  documents/*.pdf
processed/mmlongbench-doc/
  inspection.json        # python scripts/inspect_mmlongbench_doc.py
splits/mmlongbench-doc/  # COMMITTED (small, versioned subset definitions)
  pilot-v1.json          # python scripts/make_mmlongbench_pilot.py (D-013)
  calib-v1.json
```

`data/splits/` is the only data directory under version control: subset files contain IDs and
selection metadata only, never document content.
