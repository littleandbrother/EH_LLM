from __future__ import annotations

from dataclasses import dataclass, field

from .bootstrap import ensure_autora_core_path

ensure_autora_core_path()

from autora.state import StandardState


@dataclass(frozen=True)
class VehBenchState(StandardState):
    task: dict = field(default_factory=dict, metadata={"delta": "replace"})
    traces: list[dict] = field(default_factory=list, metadata={"delta": "extend"})
    cycle_summaries: list[dict] = field(default_factory=list, metadata={"delta": "extend"})
