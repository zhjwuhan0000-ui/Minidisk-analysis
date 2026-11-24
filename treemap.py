"""A compact, dependency-free treemap widget built on tkinter.Canvas."""

from __future__ import annotations

import colorsys
import hashlib
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Iterable

from models import ScanNode


@dataclass(frozen=True)
class Tile:
    node: ScanNode
    x: float
    y: float
    width: float
    height: float

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


def layout_treemap(
    nodes: Iterable[ScanNode], width: float, height: float, padding: float = 3
) -> list[Tile]:
    """Lay out positive-sized nodes using an iterative binary partition."""

    candidates = [node for node in nodes if node.size > 0]
    if not candidates or width <= padding * 2 or height <= padding * 2:
        return []

    tiles: list[Tile] = []
    pending: list[tuple[list[ScanNode], float, float, float, float]] = [
        (candidates, padding, padding, width - padding * 2, height - padding * 2)
    ]
    while pending:
        items, x, y, item_width, item_height = pending.pop()
        if not items or item_width < 1 or item_height < 1:
            continue
        if len(items) == 1:
            tiles.append(Tile(items[0], x, y, item_width, item_height))
            continue

        total = sum(item.size for item in items)
        running = 0
        split = 1
        best_difference = total
        for index in range(1, len(items)):
            running += items[index - 1].size
            difference = abs(total - running * 2)
            if difference < best_difference:
                best_difference = difference
                split = index

        first = items[:split]
        second = items[split:]
        first_size = sum(item.size for item in first)
        ratio = first_size / total if total else 0.5
        if item_width >= item_height:
            first_width = max(1.0, min(item_width - 1.0, item_width * ratio))
            pending.append((second, x + first_width, y, item_width - first_width, item_height))
            pending.append((first, x, y, first_width, item_height))
        else:
            first_height = max(1.0, min(item_height - 1.0, item_height * ratio))
            pending.append((second, x, y + first_height, item_width, item_height - first_height))
            pending.append((first, x, y, item_width, first_height))
    return tiles


class TreemapCanvas(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        on_activate: Callable[[ScanNode], None],
        **kwargs: object,
    ) -> None:
        super().__init__(
            master,
            background="#f3f5f7",
            highlightthickness=0,
            **kwargs,
        )
        self._node: ScanNode | None = None
        self._tiles: list[Tile] = []
        self._on_activate = on_activate
        self._tooltip: tk.Toplevel | None = None
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _event: self._hide_tooltip())
        self.bind("<Double-Button-1>", self._on_double_click)

    def show_node(self, node: ScanNode | None) -> None:
        self._node = node
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        self._tiles = []
        if self._node is None:
            return
        self._tiles = layout_treemap(
            self._node.children, self.winfo_width(), self.winfo_height()
        )
        for tile in self._tiles:
            x2 = tile.x + tile.width
            y2 = tile.y + tile.height
            self.create_rectangle(
                tile.x + 1,
                tile.y + 1,
                x2 - 1,
                y2 - 1,
                fill=_color_for(tile.node),
                outline="#ffffff",
                width=1,
            )
            if tile.width >= 90 and tile.height >= 38:
                label = f"{tile.node.name}\n{format_size(tile.node.size)}"
                self.create_text(
                    tile.x + 7,
                    tile.y + 6,
                    anchor="nw",
                    text=label,
                    fill="#ffffff",
                    font=("Segoe UI", 9),
                    width=max(20, tile.width - 14),
                )

    def _tile_at(self, x: float, y: float) -> Tile | None:
        return next((tile for tile in self._tiles if tile.contains(x, y)), None)

    def _on_motion(self, event: tk.Event[tk.Misc]) -> None:
        tile = self._tile_at(event.x, event.y)
        if tile is None:
            self._hide_tooltip()
            return
        self.configure(cursor="hand2")
        self._show_tooltip(tile.node, event.x_root + 12, event.y_root + 12)

    def _on_double_click(self, event: tk.Event[tk.Misc]) -> None:
        tile = self._tile_at(event.x, event.y)
        if tile is not None:
            self._on_activate(tile.node)

    def _show_tooltip(self, node: ScanNode, x: int, y: int) -> None:
        self._hide_tooltip()
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            popup,
            text=f"{node.path}\n{format_size(node.size)}",
            background="#20252b",
            foreground="#ffffff",
            relief="solid",
            borderwidth=1,
            padx=7,
            pady=5,
            justify="left",
        )
        label.pack()
        self._tooltip = popup

    def _hide_tooltip(self) -> None:
        self.configure(cursor="")
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None


def format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    return f"{size} B" if unit == 0 else f"{value:.2f} {units[unit]}"


def _color_for(node: ScanNode) -> str:
    key = node.name if node.is_directory else node.extension or node.name
    digest = hashlib.sha256(key.casefold().encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65535
    saturation = 0.58 if node.is_directory else 0.67
    value = 0.72 if node.is_directory else 0.78
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"

