"""MiniDirStat entry point for the desktop app and JSON scan mode."""

from __future__ import annotations

import argparse
import json

from app import run
from scanner import result_to_dict, scan_directory


VERSION = "1.0.0"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect directory sizes with a small standard-library GUI."
    )
    parser.add_argument("--version", action="version", version=f"MiniDirStat Python {VERSION}")
    parser.add_argument("--scan", metavar="PATH", help="scan a directory without opening the GUI")
    parser.add_argument("--open", metavar="PATH", help="open the GUI and scan this directory")
    parser.add_argument("--json", action="store_true", help="emit formatted JSON with --scan")
    args = parser.parse_args()

    if args.scan:
        result = scan_directory(args.scan)
        indent = 2 if args.json else None
        print(json.dumps(result_to_dict(result), ensure_ascii=False, indent=indent))
        return 0

    run(initial_path=args.open, auto_scan=bool(args.open))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

