"""Data models shared by the scanner and user interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ScanNode:
    name: str
    path: Path
    is_directory: bool
    size: int = 0
    modified: datetime | None = None
    extension: str = ""
    access_denied: bool = False
    parent: ScanNode | None = field(default=None, repr=False)
    children: list[ScanNode] = field(default_factory=list, repr=False)


@dataclass
class ExtensionStat:
    extension: str
    size: int = 0
    count: int = 0


@dataclass
class ScanResult:
    root: ScanNode
    file_count: int = 0
    directory_count: int = 1
    error_count: int = 0
    cancelled: bool = False
    elapsed_seconds: float = 0.0
    extensions: dict[str, ExtensionStat] = field(default_factory=dict)

