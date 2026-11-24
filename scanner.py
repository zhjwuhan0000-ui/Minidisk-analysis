"""Read-only directory scanning for MiniDirStat."""

from __future__ import annotations

import os
import stat
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from models import ExtensionStat, ScanNode, ScanResult


ProgressCallback = Callable[[int, int, int, str], None]


def scan_directory(
    root_path: str | os.PathLike[str],
    cancel_event: threading.Event | None = None,
    progress: ProgressCallback | None = None,
) -> ScanResult:
    """Scan a directory without following symlinks or Windows reparse points."""

    path = Path(root_path).expanduser().resolve()
    if not path.is_dir():
        raise NotADirectoryError(f"Directory not found: {path}")

    started = time.perf_counter()
    root = ScanNode(
        name=path.name or str(path),
        path=path,
        is_directory=True,
        modified=_safe_modified(path),
    )
    result = ScanResult(root=root)
    pending = [root]
    last_progress = 0.0

    while pending:
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
            break

        directory = pending.pop()
        try:
            with os.scandir(directory.path) as entries:
                for entry in entries:
                    if cancel_event is not None and cancel_event.is_set():
                        result.cancelled = True
                        break

                    try:
                        entry_stat = entry.stat(follow_symlinks=False)
                        if _is_link_or_reparse(entry, entry_stat):
                            continue

                        modified = datetime.fromtimestamp(entry_stat.st_mtime)
                        entry_path = Path(entry.path)
                        if stat.S_ISDIR(entry_stat.st_mode):
                            child = ScanNode(
                                name=entry.name,
                                path=entry_path,
                                is_directory=True,
                                modified=modified,
                                parent=directory,
                            )
                            directory.children.append(child)
                            pending.append(child)
                            result.directory_count += 1
                            continue

                        if not stat.S_ISREG(entry_stat.st_mode):
                            continue

                        extension = entry_path.suffix.lower() or "<none>"
                        child = ScanNode(
                            name=entry.name,
                            path=entry_path,
                            is_directory=False,
                            size=entry_stat.st_size,
                            modified=modified,
                            extension=extension,
                            parent=directory,
                        )
                        directory.children.append(child)
                        result.file_count += 1
                        _add_size_to_ancestors(directory, child.size)

                        extension_stat = result.extensions.setdefault(
                            extension, ExtensionStat(extension=extension)
                        )
                        extension_stat.count += 1
                        extension_stat.size += child.size

                        now = time.monotonic()
                        if progress is not None and (
                            result.file_count % 128 == 0 or now - last_progress >= 0.25
                        ):
                            progress(
                                result.file_count,
                                result.directory_count,
                                result.root.size,
                                str(directory.path),
                            )
                            last_progress = now
                    except OSError:
                        result.error_count += 1
        except OSError:
            directory.access_denied = True
            result.error_count += 1

    _sort_tree(root)
    result.elapsed_seconds = time.perf_counter() - started
    if progress is not None:
        progress(
            result.file_count,
            result.directory_count,
            result.root.size,
            str(result.root.path),
        )
    return result


def result_to_dict(result: ScanResult, limit: int = 20) -> dict[str, object]:
    """Return a JSON-ready summary for scripts and automated verification."""

    return {
        "path": str(result.root.path),
        "bytes": result.root.size,
        "files": result.file_count,
        "directories": result.directory_count,
        "errors": result.error_count,
        "cancelled": result.cancelled,
        "elapsed_ms": round(result.elapsed_seconds * 1000),
        "largest": [
            {
                "name": node.name,
                "path": str(node.path),
                "directory": node.is_directory,
                "bytes": node.size,
            }
            for node in result.root.children[:limit]
        ],
        "extensions": [
            {
                "extension": item.extension,
                "files": item.count,
                "bytes": item.size,
            }
            for item in sorted(
                result.extensions.values(), key=lambda item: item.size, reverse=True
            )[:limit]
        ],
    }


def _safe_modified(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def _is_link_or_reparse(entry: os.DirEntry[str], entry_stat: os.stat_result) -> bool:
    if entry.is_symlink():
        return True
    file_attributes = getattr(entry_stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(file_attributes & reparse_flag)


def _add_size_to_ancestors(node: ScanNode | None, size: int) -> None:
    while node is not None:
        node.size += size
        node = node.parent


def _sort_tree(root: ScanNode) -> None:
    pending = [root]
    while pending:
        node = pending.pop()
        node.children.sort(key=lambda child: (-child.size, child.name.casefold()))
        pending.extend(child for child in node.children if child.is_directory)

