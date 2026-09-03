from __future__ import annotations
from dataclasses import dataclass

LEVELS = ["PASS", "INFO", "WARN", "FAIL"]


@dataclass
class Finding:
    check_id: str
    level: str
    summary: str
    table: str | None = None

    def __post_init__(self):
        if self.level not in LEVELS:
            raise ValueError(f"bad level {self.level!r}")
