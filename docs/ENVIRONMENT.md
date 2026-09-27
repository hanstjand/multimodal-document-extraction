# Environment

Recorded in CP-0.1 on 2026-09-27 (read-only inspection; nothing installed or changed).
Re-record if hardware or drivers change; experiments reference this file for `hardware`.

## System

| Item | Value |
|---|---|
| OS | Microsoft Windows 10 Pro 10.0.19045 (build 19045), 64-bit |
| CPU | Intel Core i7-10700 @ 2.90 GHz — 8 cores / 16 threads |
| RAM | 31.8 GB total (12.8 GB free at inspection time) |
| Disk | C: 930 GB total, 168 GB free |
| Shells | PowerShell 5.1, Git Bash |

## GPU

| Item | Value |
|---|---|
| NVIDIA GPU | Quadro RTX 4000 (Turing, compute capability 7.5) |
| VRAM | 8192 MiB (2 MiB used at idle) |
| NVIDIA driver | 595.97 (Windows driver string 32.0.15.9597), WDDM mode |
| CUDA version reported by driver | 13.2 (max supported by driver, not an installed toolkit) |
| Other display adapters | Intel UHD Graphics 630 (iGPU); Parsec Virtual Display Adapter |
| Process on GPU | `parsecd.exe` (Parsec remote desktop) |

`nvidia-smi` output (2026-09-27 13:11):

```
NVIDIA-SMI 595.97   Driver Version: 595.97   CUDA Version: 13.2
GPU 0  Quadro RTX 4000  WDDM  | 00000000:01:00.0 | 30% 36C P8 2W/125W | 2MiB / 8192MiB | 0% Default
```

## Software

| Item | Value |
|---|---|
| Default `python` | 3.13.12 — `C:\Users\Hanz\miniconda3\python.exe` (conda **base**) |
| Other Pythons | 3.8 (`C:\Users\Hanz\AppData\Local\Programs\Python\Python38`, via `py` launcher) |
| conda | 26.1.1; envs: `base`, `bigdata` (unrelated to this project) |
| PyTorch in conda base | 2.12.0+cu126, `torch.cuda.is_available() == True` |
| PyMuPDF in conda base | 1.27.2.3 (also has pypdf, pdfplumber, pdfminer) |
| Git | 2.53.0.windows.2 |
| poppler (`pdftoppm`) | not installed |

## Project environment (CP-0.3, D-006)

| Item | Value |
|---|---|
| conda env | `mmde` — `C:\Users\Hanz\miniconda3\envs\mmde` (from `environment.yml`, conda-forge) |
| Python | 3.11.16 |
| Project install | `multimodal-document-extraction 0.0.1`, editable (`pip install -e .[dev]`) |
| Runtime dependencies | PyMuPDF 1.28.2 (`pymupdf>=1.24`, added CP-2.1); bm25s 0.3.11 (`bm25s>=0.2`, MIT, added CP-3.1) with numpy 2.4.6; networkx 3.6.1 (`networkx>=3.2`, BSD-3-Clause, explicit since CP-4.2) |
| Dense extra (`.[dense]`, CP-3.3) | torch 2.14.0+cu126 (CUDA available, Quadro RTX 4000), sentence-transformers 6.1.0, transformers 5.17.0 |
| Model cache (Hugging Face) | e5-large-v2 @ f169b11e, bge-large-en @ abe7d9d8 (~1.3 GB each); Windows symlink warning (no Developer Mode) → files copied, harmless |
| Dev dependencies | pytest 9.1.1, ruff 0.16.9 (+ colorama 0.4.6, iniconfig 2.3.0, pluggy 1.6.0, Pygments 2.21.0, packaging 26.3) |

Recreate: `conda env create -f environment.yml` then `conda activate mmde`.

## Implications (observations, not decisions)

- **8 GB VRAM, Turing:** fine for BM25, E5-large-v2 / BGE-large embeddings (~335M params).
  ColPali (~3B) is likely feasible in fp16 but tight. 7–12B LVLMs (InternVL2-8B, Pixtral-12B)
  would need 4-bit quantization or remote compute. The paper used 4× A100.
- Turing has no native bf16 and no FlashAttention-2 support; fp16 would be needed locally.
- vLLM (used by the paper) does not officially support native Windows; local serving of open models
  would need WSL2/Linux or another runtime. GPT-4o (paper's ingestion + agent model) is API-based.
- The conda **base** env should not be used for the project; a dedicated env is decided in CP-0.3.
- Paper environment for comparison: Python 3.10.12, PyTorch 2.7.0+cu126, vLLM 0.9.2, 4× A100.
