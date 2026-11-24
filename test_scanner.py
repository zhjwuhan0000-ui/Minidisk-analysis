"""Standard-library tests for scanning and treemap layout."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from models import ScanNode
from scanner import scan_directory
from treemap import layout_treemap


class ScannerTests(unittest.TestCase):
    def test_scan_totals_extensions_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "small.txt").write_bytes(b"abc")
            (root / "large.bin").write_bytes(b"x" * 12)
            nested = root / "nested"
            nested.mkdir()
            (nested / "note.txt").write_bytes(b"hello")

            result = scan_directory(root)

            self.assertEqual(result.file_count, 3)
            self.assertEqual(result.directory_count, 2)
            self.assertEqual(result.error_count, 0)
            self.assertEqual(result.root.size, 20)
            self.assertEqual(result.extensions[".txt"].count, 2)
            self.assertEqual(result.extensions[".txt"].size, 8)
            self.assertEqual(result.root.children[0].name, "large.bin")

    def test_pre_cancelled_scan_returns_partial_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cancel = threading.Event()
            cancel.set()
            result = scan_directory(temporary, cancel)
            self.assertTrue(result.cancelled)
            self.assertEqual(result.file_count, 0)


class TreemapTests(unittest.TestCase):
    def test_layout_keeps_tiles_inside_bounds(self) -> None:
        nodes = [
            ScanNode("a", Path("a"), False, size=60),
            ScanNode("b", Path("b"), False, size=30),
            ScanNode("c", Path("c"), False, size=10),
        ]
        tiles = layout_treemap(nodes, 600, 300)
        self.assertEqual(len(tiles), 3)
        for tile in tiles:
            self.assertGreater(tile.width, 0)
            self.assertGreater(tile.height, 0)
            self.assertGreaterEqual(tile.x, 0)
            self.assertGreaterEqual(tile.y, 0)
            self.assertLessEqual(tile.x + tile.width, 600)
            self.assertLessEqual(tile.y + tile.height, 300)


if __name__ == "__main__":
    unittest.main()

