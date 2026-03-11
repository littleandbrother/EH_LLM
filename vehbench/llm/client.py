from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _candidate_env_files() -> list[Path]:
    project_root = Path(__file__).resolve().parents[2]
    return [
        project_root / "pipelines" / "download" / ".env",
        project_root.parent / "EH-LLM" / "pipelines" / "download" / ".env",
    ]


def _ensure_llm_env() -> None:
    if os.getenv("ARK_API_KEY"):
        return
    for env_path in _candidate_env_files():
        _load_env_file(env_path)
        if os.getenv("ARK_API_KEY"):
            return


def get_llm_config() -> dict[str, str]:
    _ensure_llm_env()
    api_key = os.getenv("ARK_API_KEY", "")
    base_url = os.getenv("VEHBENCH_LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("VEHBENCH_LLM_MODEL", "glm-4-7-251222")
    if not api_key:
        raise RuntimeError("ARK_API_KEY is not configured for zero-shot LLM baseline")
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "timeout_s": os.getenv("VEHBENCH_LLM_TIMEOUT_S", "60"),
    }


def get_llm_client() -> tuple[OpenAI, dict[str, str]]:
    config = get_llm_config()
    client = OpenAI(
        base_url=config["base_url"],
        api_key=config["api_key"],
        timeout=float(config["timeout_s"]),
    )
    return client, config
