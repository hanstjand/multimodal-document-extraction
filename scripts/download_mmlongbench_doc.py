"""Download MMLongBench-Doc (annotations + PDFs) at pinned revisions and write a checksum manifest.

Sources (both Apache-2.0):
  - GitHub mayubo2333/MMLongBench-Doc @ GITHUB_COMMIT -> data/samples.json, README.md, all PDFs
  - Hugging Face yubo2333/MMLongBench-Doc @ HF_REVISION -> data/train-00000-of-00001.parquet

PDFs are taken from GitHub, not Hugging Face: on 2026-09-27 the HF file endpoint served the wrong
content for some PDFs (e.g. ``mi_phone.pdf`` returned the bytes of ``NYU_graduate.pdf``); see
docs/studies/ladrag/MMLONGBENCH_DOC.md. Every GitHub file is verified against its git blob hash,
and every PDF is additionally compared with the HF LFS sha256 (mismatches are recorded, not fatal).

Usage:
  python scripts/download_mmlongbench_doc.py [--out data/raw/mmlongbench-doc] [--skip-pdfs]

Idempotent: files already present and matching their git blob hash are not downloaded again.
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

GITHUB_REPO = "mayubo2333/MMLongBench-Doc"
GITHUB_COMMIT = "d73f0dc0be7e0a2ff6a403d5fe65fcd96461f384"  # main @ 2025-09-28
HF_REPO = "yubo2333/MMLongBench-Doc"
HF_REVISION = "2ff6aa9237fc777b6627dc57a486e9225ac5fb86"  # lastModified 2025-11-06

GITHUB_FILES = {"data/samples.json": "github/samples.json", "README.md": "github/README.md"}
GITHUB_PDF_DIR = "data/documents/"
HF_PARQUET = "data/train-00000-of-00001.parquet"


def _fetch(url: str, retries: int = 3) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                return response.read()
        except OSError as exc:
            if attempt == retries:
                raise
            print(f"  retry {attempt}/{retries - 1} after error: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _download(url: str, dest: Path, git_blob_sha: str | None = None) -> dict:
    """Download ``url`` to ``dest``; if ``git_blob_sha`` is given, the content must match it."""
    if (
        dest.exists()
        and git_blob_sha is not None
        and _git_blob_sha1(dest.read_bytes()) == git_blob_sha
    ):
        print(f"  exists  {dest.name}")
        data = dest.read_bytes()
    else:
        print(f"  fetch   {dest.name}")
        data = _fetch(url)
        if git_blob_sha is not None and _git_blob_sha1(data) != git_blob_sha:
            raise RuntimeError(f"{url}: content does not match git blob {git_blob_sha}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
    return {"url": url, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _github_tree() -> dict[str, str]:
    """Path -> git blob sha for every file at GITHUB_COMMIT."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{GITHUB_COMMIT}?recursive=1"
    tree = json.loads(_fetch(url))
    if tree.get("truncated"):
        raise RuntimeError("GitHub tree listing is truncated")
    return {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}


def _hf_hashes(path: str) -> dict[str, tuple[str, str]]:
    """File name -> ("sha256", LFS oid) for LFS files, ("git", blob sha) for small git files."""
    url = f"https://huggingface.co/api/datasets/{HF_REPO}/tree/{HF_REVISION}/{path}"
    entries = [e for e in json.loads(_fetch(url)) if e["type"] == "file"]
    return {
        e["path"].rsplit("/", 1)[1]: ("sha256", e["lfs"]["oid"])
        if e.get("lfs")
        else ("git", e["oid"])
        for e in entries
    }


def _hf_compare(entry: dict, data_path: Path, hf_hash: tuple[str, str] | None) -> None:
    """Record whether our file matches the hash HF lists for it (``None`` if HF lacks the file)."""
    if hf_hash is None:
        entry["hf_hash"], entry["hf_match"] = None, None
        return
    kind, value = hf_hash
    ours = entry["sha256"] if kind == "sha256" else _git_blob_sha1(data_path.read_bytes())
    entry["hf_hash"], entry["hf_match"] = f"{kind}:{value}", ours == value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("data/raw/mmlongbench-doc"))
    parser.add_argument("--skip-pdfs", action="store_true")
    args = parser.parse_args()
    out: Path = args.out
    files: dict[str, dict] = {}
    gh_tree = _github_tree()

    print("GitHub annotation files")
    for src, rel in GITHUB_FILES.items():
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_COMMIT}/{src}"
        files[rel] = _download(url, out / rel, gh_tree[src])

    print("Hugging Face parquet")
    url = f"https://huggingface.co/datasets/{HF_REPO}/resolve/{HF_REVISION}/{HF_PARQUET}"
    entry = _download(url, out / "hf/train-00000-of-00001.parquet")
    parquet_name = HF_PARQUET.rsplit("/", 1)[1]
    _hf_compare(entry, out / "hf" / parquet_name, _hf_hashes("data").get(parquet_name))
    files["hf/train-00000-of-00001.parquet"] = entry

    if not args.skip_pdfs:
        hf_hashes = _hf_hashes("documents")
        pdfs = sorted(p for p in gh_tree if p.startswith(GITHUB_PDF_DIR) and p.endswith(".pdf"))
        print(f"GitHub documents ({len(pdfs)} PDFs; HF lists {len(hf_hashes)})")
        for path in pdfs:
            name = path[len(GITHUB_PDF_DIR) :]
            url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_COMMIT}/{path}"
            entry = _download(url, out / "documents" / name, gh_tree[path])
            _hf_compare(entry, out / "documents" / name, hf_hashes.get(name))
            if not entry["hf_match"]:
                print(f"  WARNING {name}: differs from HF-listed hash {entry['hf_hash']}")
            files[f"documents/{name}"] = entry

    manifest = {
        "dataset": "MMLongBench-Doc",
        "license": "Apache-2.0",
        "github": {"repo": GITHUB_REPO, "commit": GITHUB_COMMIT},
        "huggingface": {"repo": HF_REPO, "revision": HF_REVISION},
        "pdf_source": "github",
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": dict(sorted(files.items())),
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total_mb = sum(f["size"] for f in files.values()) / 1e6
    print(f"Done: {len(files)} files, {total_mb:.1f} MB -> {out / 'MANIFEST.json'}")


if __name__ == "__main__":
    main()
