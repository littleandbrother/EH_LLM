from __future__ import annotations

import sys
from pathlib import Path


def ensure_autora_core_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    autora_core_src = repo_root.parent / "third_party" / "autora-core" / "src"
    if not autora_core_src.exists():
        raise FileNotFoundError(f"AutoRA core source not found: {autora_core_src}")
    autora_core_src_str = str(autora_core_src)
    if autora_core_src_str not in sys.path:
        sys.path.insert(0, autora_core_src_str)
    return autora_core_src
