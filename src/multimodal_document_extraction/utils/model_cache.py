"""Permanent, content-addressed cache for model replies (method-agnostic; LAD-RAG† R16).

Key = sha256 over (model identifier, task, prompt text, image hashes, generation parameters).
One JSON file per key under ``<root>/<key[:2]>/<key>.json``, written atomically, so interrupted runs
never leave partial entries and re-runs reuse every completed call for free.
"""

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def cache_key(
    model_id: str,
    task: str,
    prompt: str,
    image_hashes: Sequence[str],
    params: Mapping[str, Any],
) -> str:
    payload = json.dumps(
        {
            "model_id": model_id,
            "task": task,
            "prompt": prompt,
            "images": list(image_hashes),
            "params": dict(params),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ModelCache:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, entry: Mapping[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)

    def __contains__(self, key: str) -> bool:
        return self._path(key).exists()
