"""Tkinter desktop interface for MiniDirStat."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from models import ScanNode, ScanResult
from scanner import scan_directory
from treemap import TreemapCanvas, format_size


class MiniDirStatApp(tk.Tk):
    def __init__(self, initial_path: str | None = None, auto_scan: bool = False) -> None:
        super().__init__()
        self.title("MiniDirStat Python")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self.option_add("*Font", ("Segoe UI", 9))

        self._messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel_event: threading.Event | None = None
        self._scan_result: ScanResult | None = None
        self._current_node: ScanNode | None = None
        self._tree_nodes: dict[str, ScanNode] = {}
        self._item_nodes: dict[str, ScanNode] = {}
        self._next_id = 0

        self._path = tk.StringVar(value=initial_path or str(Path.home()))
        self._status = tk.StringVar(value="Choose a folder and scan.")
        self._build_interface()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll_messages)
        if auto_scan:
            self.after(250, self.start_scan)

    def _build_interface(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        toolbar = ttk.Frame(self, padding=(8, 7))
        toolbar.pack(side="top", fill="x")
        ttk.Label(toolbar, text="Folder").pack(side="left", padx=(0, 6))
        self.path_entry = ttk.Entry(toolbar, textvariable=self._path)
        self.path_entry.pack(side="left", fill="x", expand=True)
        self.path_entry.bind("<Return>", lambda _event: self.start_scan())
        self.browse_button = ttk.Button(toolbar, text="Browse", command=self._browse)
        self.browse_button.pack(side="left", padx=(7, 0))
        self.scan_button = ttk.Button(toolbar, text="Scan", command=self.start_scan)
        self.scan_button.pack(side="left", padx=(7, 0))
        self.stop_button = ttk.Button(toolbar, text="Stop", command=self._cancel_scan)
        self.stop_button.pack(side="left", padx=(4, 0))
        self.up_button = ttk.Button(toolbar, text="Up", command=self._show_parent)
        self.up_button.pack(side="left", padx=(12, 0))
        self.explore_button = ttk.Button(toolbar, text="Explore", command=self._explore_current)
        self.explore_button.pack(side="left", padx=(4, 0))

        self.main_pane = ttk.Panedwindow(self, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=8)

        tree_frame = ttk.Frame(self.main_pane, width=320)
        self.directory_tree = ttk.Treeview(tree_frame, show="tree")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.directory_tree.yview)
        self.directory_tree.configure(yscrollcommand=tree_scroll.set)
        self.directory_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.directory_tree.bind("<<TreeviewOpen>>", self._expand_tree_node)
        self.directory_tree.bind("<<TreeviewSelect>>", self._select_tree_node)
        self.main_pane.add(tree_frame, weight=0)

        right_pane = ttk.Panedwindow(self.main_pane, orient="vertical")
        self.main_pane.add(right_pane, weight=3)

        item_frame = ttk.Frame(right_pane)
        columns = ("type", "size", "percent", "modified")
        self.item_table = ttk.Treeview(item_frame, columns=columns, show="tree headings")
        self.item_table.heading("#0", text="Name")
        self.item_table.heading("type", text="Type")
        self.item_table.heading("size", text="Size")
        self.item_table.heading("percent", text="Percent")
        self.item_table.heading("modified", text="Modified")
        self.item_table.column("#0", width=330, minwidth=160)
        self.item_table.column("type", width=100, minwidth=75)
        self.item_table.column("size", width=110, minwidth=90, anchor="e")
        self.item_table.column("percent", width=85, minwidth=70, anchor="e")
        self.item_table.column("modified", width=150, minwidth=120)
        item_scroll = ttk.Scrollbar(item_frame, orient="vertical", command=self.item_table.yview)
        self.item_table.configure(yscrollcommand=item_scroll.set)
        self.item_table.pack(side="left", fill="both", expand=True)
        item_scroll.pack(side="right", fill="y")
        self.item_table.bind("<Double-Button-1>", self._activate_table_item)
        right_pane.add(item_frame, weight=1)

        notebook = ttk.Notebook(right_pane)
        treemap_page = ttk.Frame(notebook)
        extension_page = ttk.Frame(notebook)
        notebook.add(treemap_page, text="Treemap")
        notebook.add(extension_page, text="Extensions")
        right_pane.add(notebook, weight=1)

        self.treemap = TreemapCanvas(treemap_page, self._activate_node)
        self.treemap.pack(fill="both", expand=True)

        extension_columns = ("files", "size", "percent")
        self.extension_table = ttk.Treeview(
            extension_page, columns=extension_columns, show="tree headings"
        )
        self.extension_table.heading("#0", text="Extension")
        self.extension_table.heading("files", text="Files")
        self.extension_table.heading("size", text="Size")
        self.extension_table.heading("percent", text="Percent")
        self.extension_table.column("#0", width=180)
        self.extension_table.column("files", width=90, anchor="e")
        self.extension_table.column("size", width=130, anchor="e")
        self.extension_table.column("percent", width=90, anchor="e")
        extension_scroll = ttk.Scrollbar(
            extension_page, orient="vertical", command=self.extension_table.yview
        )
        self.extension_table.configure(yscrollcommand=extension_scroll.set)
        self.extension_table.pack(side="left", fill="both", expand=True)
        extension_scroll.pack(side="right", fill="y")

        status_frame = ttk.Frame(self, padding=(8, 5))
        status_frame.pack(side="bottom", fill="x")
        ttk.Label(status_frame, textvariable=self._status).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=150)
        self.progress.pack(side="right")

        self._set_scanning(False)
        self.after(400, self._set_initial_sashes)

    def _set_initial_sashes(self) -> None:
        try:
            self.update_idletasks()
            if self.main_pane.winfo_width() >= 700:
                self.main_pane.sashpos(0, 320)
        except tk.TclError:
            pass

    def _browse(self) -> None:
        selected = filedialog.askdirectory(initialdir=self._path.get() or str(Path.home()))
        if selected:
            self._path.set(selected)

    def start_scan(self) -> None:
        raw_path = self._path.get().strip()
        if not Path(raw_path).expanduser().is_dir():
            messagebox.showwarning("MiniDirStat", "The selected folder does not exist.")
            return

        self._clear_results()
        self._cancel_event = threading.Event()
        self._set_scanning(True)
        self._status.set(f"Scanning {raw_path}")

        def progress(files: int, directories: int, size: int, current: str) -> None:
            self._messages.put(("progress", (files, directories, size, current)))

        def worker() -> None:
            try:
                result = scan_directory(raw_path, self._cancel_event, progress)
                self._messages.put(("done", result))
            except Exception as error:  # The UI reports filesystem failures cleanly.
                self._messages.put(("error", error))

        threading.Thread(target=worker, name="directory-scan", daemon=True).start()

    def _cancel_scan(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self._status.set("Cancelling after the current filesystem operation...")

    def _poll_messages(self) -> None:
        try:
            while True:
                kind, payload = self._messages.get_nowait()
                if kind == "progress":
                    files, directories, size, current = payload  # type: ignore[misc]
                    self._status.set(
                        f"{files:,} files, {directories:,} folders, "
                        f"{format_size(size)} - {current}"
                    )
                elif kind == "done":
                    self._apply_result(payload)  # type: ignore[arg-type]
                elif kind == "error":
                    self._set_scanning(False)
                    self._status.set("Scan failed.")
                    messagebox.showerror("MiniDirStat", str(payload))
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_messages)

    def _apply_result(self, result: ScanResult) -> None:
        self._scan_result = result
        self._set_scanning(False)
        root_id = self._insert_tree_node("", result.root)
        self.directory_tree.item(root_id, open=True)
        self.directory_tree.selection_set(root_id)
        self._show_node(result.root)
        self._populate_extensions(result)
        prefix = "Cancelled - partial result: " if result.cancelled else ""
        self._status.set(
            f"{prefix}{result.file_count:,} files, {result.directory_count:,} folders, "
            f"{format_size(result.root.size)}, {result.error_count:,} unreadable entries, "
            f"{result.elapsed_seconds:.1f}s"
        )

    def _clear_results(self) -> None:
        for table in (self.directory_tree, self.item_table, self.extension_table):
            table.delete(*table.get_children())
        self._tree_nodes.clear()
        self._item_nodes.clear()
        self._current_node = None
        self._scan_result = None
        self.treemap.show_node(None)

    def _new_id(self, prefix: str) -> str:
        self._next_id += 1
        return f"{prefix}-{self._next_id}"

    def _insert_tree_node(self, parent_id: str, node: ScanNode) -> str:
        item_id = self._new_id("dir")
        label = f"{node.name}  [{format_size(node.size)}]"
        self.directory_tree.insert(parent_id, "end", iid=item_id, text=label)
        self._tree_nodes[item_id] = node
        if any(child.is_directory for child in node.children):
            self.directory_tree.insert(item_id, "end", iid=self._new_id("placeholder"), text="")
        return item_id

    def _expand_tree_node(self, _event: tk.Event[tk.Misc]) -> None:
        selected = self.directory_tree.focus()
        node = self._tree_nodes.get(selected)
        if node is None:
            return
        children = self.directory_tree.get_children(selected)
        if len(children) == 1 and children[0] not in self._tree_nodes:
            self.directory_tree.delete(children[0])
            for child in node.children:
                if child.is_directory:
                    self._insert_tree_node(selected, child)

    def _select_tree_node(self, _event: tk.Event[tk.Misc]) -> None:
        selected = self.directory_tree.selection()
        if selected:
            node = self._tree_nodes.get(selected[0])
            if node is not None:
                self._show_node(node)

    def _show_node(self, node: ScanNode) -> None:
        self._current_node = node
        self.item_table.delete(*self.item_table.get_children())
        self._item_nodes.clear()
        for child in node.children:
            item_id = self._new_id("item")
            percent = child.size / node.size * 100 if node.size else 0
            item_type = (
                "Folder (unreadable)"
                if child.is_directory and child.access_denied
                else "Folder"
                if child.is_directory
                else child.extension
            )
            modified = child.modified.strftime("%Y-%m-%d %H:%M") if child.modified else ""
            self.item_table.insert(
                "",
                "end",
                iid=item_id,
                text=child.name,
                values=(item_type, format_size(child.size), f"{percent:.1f}%", modified),
            )
            self._item_nodes[item_id] = child
        self.treemap.show_node(node)
        self.up_button.configure(state="normal" if node.parent else "disabled")
        self.explore_button.configure(state="normal")

    def _populate_extensions(self, result: ScanResult) -> None:
        self.extension_table.delete(*self.extension_table.get_children())
        for item in sorted(result.extensions.values(), key=lambda value: value.size, reverse=True):
            percent = item.size / result.root.size * 100 if result.root.size else 0
            self.extension_table.insert(
                "",
                "end",
                text=item.extension,
                values=(f"{item.count:,}", format_size(item.size), f"{percent:.1f}%"),
            )

    def _activate_table_item(self, _event: tk.Event[tk.Misc]) -> None:
        selected = self.item_table.selection()
        if selected:
            node = self._item_nodes.get(selected[0])
            if node is not None:
                self._activate_node(node)

    def _activate_node(self, node: ScanNode) -> None:
        if node.is_directory:
            self._show_node(node)
        else:
            self._reveal(node.path)

    def _show_parent(self) -> None:
        if self._current_node is not None and self._current_node.parent is not None:
            self._show_node(self._current_node.parent)

    def _explore_current(self) -> None:
        if self._current_node is not None:
            self._reveal(self._current_node.path)

    def _reveal(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                if path.is_dir():
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["explorer.exe", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                target = path if path.is_dir() else path.parent
                subprocess.Popen(["xdg-open", str(target)])
        except OSError as error:
            messagebox.showerror("MiniDirStat", str(error))

    def _set_scanning(self, scanning: bool) -> None:
        state = "disabled" if scanning else "normal"
        self.path_entry.configure(state=state)
        self.browse_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.stop_button.configure(state="normal" if scanning else "disabled")
        if scanning:
            self.progress.start(12)
        else:
            self.progress.stop()
            self._cancel_event = None
        if self._current_node is None:
            self.up_button.configure(state="disabled")
            self.explore_button.configure(state="disabled")

    def _close(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
        self.destroy()


def run(initial_path: str | None = None, auto_scan: bool = False) -> None:
    MiniDirStatApp(initial_path=initial_path, auto_scan=auto_scan).mainloop()

