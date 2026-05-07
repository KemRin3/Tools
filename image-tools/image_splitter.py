"""Desktop GUI tool for cutting image sheets into normalized PNG cells.

External dependency: Pillow
"""

from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

from PIL import Image, ImageChops, ImageTk, UnidentifiedImageError

SUPPORTED_FILETYPES = (
    ("Image files", "*.png *.jpg *.jpeg *.webp"),
    ("PNG files", "*.png"),
    ("JPEG files", "*.jpg *.jpeg"),
    ("WEBP files", "*.webp"),
    ("All files", "*.*"),
)
PREVIEW_MAX_SIZE = (520, 420)
SNAP_UNITS = ("1", "8", "16", "32", "64")


class ImageSplitterApp:
    """Main tkinter application for cutting image sheets into PNG cells."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Generic Image Cutter")
        self.root.minsize(980, 720)

        self.image_path: Optional[Path] = None
        self.output_dir: Optional[Path] = None
        self.loaded_image: Optional[Image.Image] = None
        self.preview_photo_source: Optional[ImageTk.PhotoImage] = None
        self.preview_photo_output: Optional[ImageTk.PhotoImage] = None

        self.rows_var = tk.StringVar(value="2")
        self.cols_var = tk.StringVar(value="2")
        self.output_width_var = tk.StringVar(value="256")
        self.output_height_var = tk.StringVar(value="256")
        self.image_path_var = tk.StringVar(value="画像が選択されていません")
        self.output_dir_var = tk.StringVar(value="出力フォルダが選択されていません")

        self.cut_edit_var = tk.BooleanVar(value=False)
        self.snap_var = tk.BooleanVar(value=True)
        self.snap_unit_var = tk.StringVar(value="8")
        self.min_cell_size_var = tk.StringVar(value="128")
        self.selected_line_var = tk.StringVar(value="選択中の線: なし")

        self.cell_centering_var = tk.BooleanVar(value=True)
        self.detection_mode_var = tk.StringVar(value="auto")
        self.threshold_var = tk.StringVar(value="15")
        self.alpha_threshold_var = tk.StringVar(value="10")
        self.padding_var = tk.StringVar(value="0")
        self.min_area_var = tk.StringVar(value="100")

        self.vertical_cut_lines: list[int] = []
        self.horizontal_cut_lines: list[int] = []
        self.cut_grid_signature: Optional[tuple[int, int, int, int]] = None
        self.dragging_cut_line: Optional[tuple[str, int]] = None
        self.source_preview_scale = 1.0
        self.source_preview_offset = (0, 0)
        self.source_preview_size = (0, 0)

        self._build_ui()
        self._bind_events()

    def _build_ui(self) -> None:
        """Create widgets and layout."""
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        controls_canvas = tk.Canvas(self.root, borderwidth=0, highlightthickness=0, width=340)
        controls_canvas.grid(row=0, column=0, sticky="nsw")
        controls_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=controls_canvas.yview)
        controls_scrollbar.grid(row=0, column=0, sticky="nse")
        controls_canvas.configure(yscrollcommand=controls_scrollbar.set)
        controls = ttk.Frame(controls_canvas, padding=12)
        controls_window = controls_canvas.create_window((0, 0), window=controls, anchor="nw")
        controls.bind("<Configure>", lambda _event: controls_canvas.configure(scrollregion=controls_canvas.bbox("all")))
        controls_canvas.bind("<Configure>", lambda event: controls_canvas.itemconfigure(controls_window, width=event.width))

        preview_and_log = ttk.Frame(self.root, padding=(0, 12, 12, 12))
        preview_and_log.grid(row=0, column=1, sticky="nsew")
        preview_and_log.columnconfigure(0, weight=1)
        preview_and_log.rowconfigure(0, weight=1)
        preview_and_log.rowconfigure(1, weight=0)

        self._build_controls(controls)
        self._build_preview(preview_and_log)
        self._build_log(preview_and_log)

    def _build_controls(self, parent: ttk.Frame) -> None:
        """Create the left-side control panel with only the generic cutter options."""
        parent.columnconfigure(0, weight=1)

        image_frame = ttk.LabelFrame(parent, text="入力画像", padding=10)
        image_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        image_frame.columnconfigure(0, weight=1)
        ttk.Button(image_frame, text="画像ファイルを選択", command=self.select_image).grid(row=0, column=0, sticky="ew")
        ttk.Label(image_frame, textvariable=self.image_path_var, wraplength=260).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        split_frame = ttk.LabelFrame(parent, text="分割設定", padding=10)
        split_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        split_frame.columnconfigure(1, weight=1)
        ttk.Label(split_frame, text="rows").grid(row=0, column=0, sticky="w")
        ttk.Entry(split_frame, textvariable=self.rows_var, width=10).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(split_frame, text="cols").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(split_frame, textvariable=self.cols_var, width=10).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(split_frame, text="output width").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(split_frame, textvariable=self.output_width_var, width=10).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(split_frame, text="output height").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(split_frame, textvariable=self.output_height_var, width=10).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        cut_frame = ttk.LabelFrame(parent, text="カット線編集", padding=10)
        cut_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        cut_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            cut_frame,
            text="カット線編集モード",
            variable=self.cut_edit_var,
            command=self._on_cut_edit_changed,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(cut_frame, text="スナップ", variable=self.snap_var).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            cut_frame,
            textvariable=self.snap_unit_var,
            values=SNAP_UNITS,
            state="readonly",
            width=8,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cut_frame, text="min_cell_size").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cut_frame, textvariable=self.min_cell_size_var, width=10).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(cut_frame, text="均等割り付けに戻す", command=self.reset_cut_lines).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        ttk.Button(cut_frame, text="カット線JSON保存", command=self.save_cut_lines_json).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        ttk.Button(cut_frame, text="カット線JSON読み込み", command=self.load_cut_lines_json).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        ttk.Label(cut_frame, textvariable=self.selected_line_var, wraplength=260).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        cell_frame = ttk.LabelFrame(parent, text="セル個別余白除去・センタリング", padding=10)
        cell_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        cell_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            cell_frame,
            text="セル個別余白除去・センタリング",
            variable=self.cell_centering_var,
            command=self.update_preview,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(cell_frame, text="detection mode").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            cell_frame,
            textvariable=self.detection_mode_var,
            values=("auto", "alpha", "brightness"),
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="brightness threshold").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.threshold_var, width=10).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="alpha threshold").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.alpha_threshold_var, width=10).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="padding").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.padding_var, width=10).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="min_area").grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.min_area_var, width=10).grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        output_frame = ttk.LabelFrame(parent, text="出力フォルダ", padding=10)
        output_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        ttk.Button(output_frame, text="出力フォルダを選択", command=self.select_output_dir).grid(row=0, column=0, sticky="ew")
        ttk.Label(output_frame, textvariable=self.output_dir_var, wraplength=260).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(parent, text="分割実行", command=self.split_image).grid(row=5, column=0, sticky="ew", ipady=6)

    def _build_preview(self, parent: ttk.Frame) -> None:
        """Create the preview area."""
        preview_frame = ttk.LabelFrame(parent, text="プレビュー", padding=10)
        preview_frame.grid(row=0, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        ttk.Label(preview_frame, text="入力 / カット線").grid(row=0, column=0, sticky="ew")
        ttk.Label(preview_frame, text="出力プレビュー").grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.source_canvas = tk.Canvas(
            preview_frame,
            width=PREVIEW_MAX_SIZE[0],
            height=PREVIEW_MAX_SIZE[1],
            background="#222222",
            highlightthickness=0,
        )
        self.source_canvas.grid(row=1, column=0, sticky="nsew")
        self.output_canvas = tk.Canvas(
            preview_frame,
            width=PREVIEW_MAX_SIZE[0],
            height=PREVIEW_MAX_SIZE[1],
            background="#222222",
            highlightthickness=0,
        )
        self.output_canvas.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        self.source_canvas.bind("<ButtonPress-1>", self._on_cut_line_press)
        self.source_canvas.bind("<B1-Motion>", self._on_cut_line_drag)
        self.source_canvas.bind("<ButtonRelease-1>", self._on_cut_line_release)

    def _build_log(self, parent: ttk.Frame) -> None:
        """Create the execution log area."""
        log_frame = ttk.LabelFrame(parent, text="ログ", padding=10)
        log_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="ew")

    def _bind_events(self) -> None:
        """Refresh preview when settings change."""
        for variable in (
            self.rows_var,
            self.cols_var,
            self.output_width_var,
            self.output_height_var,
            self.cut_edit_var,
            self.snap_var,
            self.snap_unit_var,
            self.min_cell_size_var,
            self.cell_centering_var,
            self.detection_mode_var,
            self.threshold_var,
            self.alpha_threshold_var,
            self.padding_var,
            self.min_area_var,
        ):
            variable.trace_add("write", lambda *_: self.update_preview())

    def select_image(self) -> None:
        """Open a file dialog and load an image."""
        file_name = filedialog.askopenfilename(title="画像ファイルを選択", filetypes=SUPPORTED_FILETYPES)
        if not file_name:
            return

        path = Path(file_name)
        try:
            image = Image.open(path)
            image.load()
        except (OSError, UnidentifiedImageError) as exc:
            self._show_error("画像読み込み失敗", f"画像を読み込めませんでした。\n{exc}")
            return

        self.image_path = path
        self.loaded_image = image
        self.cut_grid_signature = None
        self.vertical_cut_lines = []
        self.horizontal_cut_lines = []
        self.image_path_var.set(str(path))
        self._update_selected_line_label()
        self.log(f"読み込み成功: {path}")
        self.update_preview()

    def select_output_dir(self) -> None:
        """Open a folder dialog for the output destination."""
        directory = filedialog.askdirectory(title="出力フォルダを選択")
        if not directory:
            return

        self.output_dir = Path(directory)
        self.output_dir_var.set(str(self.output_dir))
        self.log(f"出力フォルダ選択: {self.output_dir}")

    def update_preview(self) -> None:
        """Draw source grid/cut-line preview and processed output preview."""
        if self.loaded_image is None:
            return

        rows = self._safe_positive_int(self.rows_var.get())
        cols = self._safe_positive_int(self.cols_var.get())
        source = self.loaded_image.convert("RGBA")
        if rows and cols and self.cut_edit_var.get():
            self._ensure_cut_lines(rows, cols, source.size)
        self._set_preview_image(source, self.source_canvas, "source")
        if rows and cols:
            self._draw_cut_lines_on_canvas(editable=self.cut_edit_var.get(), rows=rows, cols=cols)

        try:
            output_preview = self._build_output_preview(rows, cols) if rows and cols else source.copy()
        except ValueError:
            output_preview = source.copy()
        self._set_preview_image(output_preview, self.output_canvas, "output")

    def split_image(self) -> None:
        """Validate settings, cut the image, and save normalized PNG files."""
        if self.loaded_image is None or self.image_path is None:
            self._show_error("画像未選択", "画像ファイルを選択してください。")
            return
        if self.output_dir is None:
            self._show_error("出力フォルダ未選択", "出力フォルダを選択してください。")
            return

        rows = self._validate_positive_int(self.rows_var.get(), "rows")
        cols = self._validate_positive_int(self.cols_var.get(), "cols")
        if rows is None or cols is None:
            return

        try:
            settings = self._processing_settings(preview=False)
            if self.cut_edit_var.get():
                self._validate_cut_line_settings(rows, cols, self.loaded_image.size)
        except ValueError as exc:
            self._show_error("設定が不正", str(exc))
            return

        base_name = self.image_path.stem
        total = rows * cols
        digits = max(2, int(math.log10(total)) + 1 if total > 0 else 2)
        source = self.loaded_image.convert("RGBA")

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for row, col, tile in self._iter_tiles(source, rows, cols):
                index = row * cols + col + 1
                processed = self._process_tile(tile, settings, index=index)
                processed.save(self.output_dir / f"{base_name}_{index:0{digits}d}.png", "PNG")
        except OSError as exc:
            self._show_error("書き出し失敗", f"PNGの保存に失敗しました。\n{exc}")
            return

        self.log(f"出力完了: {total} ファイルを保存しました ({self.output_dir})")
        messagebox.showinfo("出力完了", f"{total} ファイルを保存しました。")

    def _processing_settings(self, preview: bool = False) -> dict[str, object]:
        """Validate and collect processing settings."""
        return {
            "output_width": self._validate_positive_field(self.output_width_var.get(), "output width", preview, 256),
            "output_height": self._validate_positive_field(self.output_height_var.get(), "output height", preview, 256),
            "cell_centering": self.cell_centering_var.get(),
            "detection_mode": self.detection_mode_var.get(),
            "threshold": self._validate_threshold_value(self.threshold_var.get(), "brightness threshold", preview, 15),
            "alpha_threshold": self._validate_threshold_value(self.alpha_threshold_var.get(), "alpha threshold", preview, 10),
            "padding": self._validate_padding_value(self.padding_var.get(), preview),
            "min_area": self._validate_non_negative_int(self.min_area_var.get(), "min_area", preview, 100),
        }

    def _build_output_preview(self, rows: int, cols: int) -> Image.Image:
        """Build a composite preview of the final normalized PNG cells."""
        settings = self._processing_settings(preview=True)
        source = self.loaded_image.convert("RGBA")
        output_width = int(settings["output_width"])
        output_height = int(settings["output_height"])
        preview = Image.new("RGBA", (output_width * cols, output_height * rows), (0, 0, 0, 0))
        for row, col, tile in self._iter_tiles(source, rows, cols):
            processed = self._process_tile(tile, settings)
            preview.paste(processed, (col * output_width, row * output_height))
        return preview

    def _iter_tiles(self, source: Image.Image, rows: int, cols: int):
        """Yield cells from edited cut lines only when edit mode is enabled; otherwise use equal grid."""
        if self.cut_edit_var.get():
            self._ensure_cut_lines(rows, cols, source.size)
            vertical_lines = self.vertical_cut_lines
            horizontal_lines = self.horizontal_cut_lines
        else:
            vertical_lines, horizontal_lines = self._equal_cut_lines(rows, cols, source.size)
        for row in range(rows):
            upper = horizontal_lines[row]
            lower = horizontal_lines[row + 1]
            for col in range(cols):
                left = vertical_lines[col]
                right = vertical_lines[col + 1]
                yield row, col, source.crop((left, upper, right, lower))

    def _process_tile(self, tile: Image.Image, settings: dict[str, object], index: Optional[int] = None) -> Image.Image:
        """Optionally remove per-cell margins, then contain-fit and center on the output canvas."""
        source = tile.convert("RGBA")
        if settings["cell_centering"]:
            centered = self._remove_cell_margins(
                source,
                str(settings["detection_mode"]),
                int(settings["threshold"]),
                int(settings["padding"]),
                int(settings["min_area"]),
                int(settings["alpha_threshold"]),
            )
            if centered is None:
                if index is not None:
                    self.log(f"警告: セル {index} で有効ピクセルが検出できませんでした。")
                source = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            else:
                source = centered
        return self._contain_center_on_canvas(source, int(settings["output_width"]), int(settings["output_height"]))

    def _remove_cell_margins(
        self,
        tile: Image.Image,
        detection_mode: str,
        threshold: int,
        padding: int,
        min_area: int,
        alpha_threshold: int,
    ) -> Optional[Image.Image]:
        """Detect a cell bbox, crop it, and add transparent padding."""
        mode = self._resolve_detection_mode(tile, detection_mode, alpha_threshold)
        bbox = self._find_content_bbox(tile, mode, threshold, min_area, alpha_threshold)
        if bbox is None:
            return None
        left, top, right, bottom = bbox
        return self._crop_with_padding(tile, (left - padding, top - padding, right + padding, bottom + padding))

    def _contain_center_on_canvas(self, image: Image.Image, output_width: int, output_height: int) -> Image.Image:
        """Fit an image with aspect-ratio-preserving contain and place it at canvas center."""
        canvas = Image.new("RGBA", (output_width, output_height), (0, 0, 0, 0))
        scale = min(output_width / image.width, output_height / image.height)
        resized_width = max(1, round(image.width * scale))
        resized_height = max(1, round(image.height * scale))
        resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
        x = round((output_width - resized_width) / 2)
        y = round((output_height - resized_height) / 2)
        canvas.alpha_composite(resized, (x, y))
        return canvas

    def _resolve_detection_mode(self, image: Image.Image, selected: str, alpha_threshold: int) -> str:
        """Resolve alpha/brightness/auto detection for a cell."""
        if selected in {"alpha", "brightness"}:
            return selected
        return "alpha" if image.getchannel("A").getextrema()[0] <= alpha_threshold else "brightness"

    def _find_content_bbox(
        self, image: Image.Image, mode: str, threshold: int, min_area: int, alpha_threshold: int
    ) -> Optional[tuple[int, int, int, int]]:
        """Return the bbox of connected valid-pixel components that are large enough."""
        mask = self._content_mask(image, mode, threshold, alpha_threshold)
        return self._connected_components_bbox(mask, min_area)

    def _content_mask(self, image: Image.Image, mode: str, threshold: int, alpha_threshold: int) -> Image.Image:
        """Build an L-mode mask for alpha or brightness content detection."""
        alpha = image.getchannel("A")
        alpha_mask = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
        if mode == "alpha":
            return alpha_mask

        rgb = image.convert("RGB")
        brightness = rgb.convert("L", matrix=(0.299, 0.587, 0.114, 0))
        bright_mask = brightness.point(lambda value: 255 if value >= threshold else 0)
        return ImageChops.multiply(bright_mask, alpha_mask)

    def _connected_components_bbox(self, mask: Image.Image, min_area: int) -> Optional[tuple[int, int, int, int]]:
        """Compute bbox from connected components at or above min_area, ignoring isolated noise."""
        width, height = mask.size
        pixels = mask.load()
        visited: set[tuple[int, int]] = set()
        kept_bbox: Optional[tuple[int, int, int, int]] = None

        for y in range(height):
            for x in range(width):
                if (x, y) in visited or pixels[x, y] == 0:
                    continue

                stack = [(x, y)]
                visited.add((x, y))
                area = 0
                left = right = x
                top = bottom = y

                while stack:
                    current_x, current_y = stack.pop()
                    area += 1
                    left = min(left, current_x)
                    right = max(right, current_x)
                    top = min(top, current_y)
                    bottom = max(bottom, current_y)

                    for next_x, next_y in (
                        (current_x - 1, current_y),
                        (current_x + 1, current_y),
                        (current_x, current_y - 1),
                        (current_x, current_y + 1),
                    ):
                        if not (0 <= next_x < width and 0 <= next_y < height):
                            continue
                        if (next_x, next_y) in visited or pixels[next_x, next_y] == 0:
                            continue
                        visited.add((next_x, next_y))
                        stack.append((next_x, next_y))

                if area < min_area:
                    continue
                component_bbox = (left, top, right + 1, bottom + 1)
                kept_bbox = self._union_bbox(kept_bbox, component_bbox)

        return kept_bbox

    @staticmethod
    def _union_bbox(
        bbox: Optional[tuple[int, int, int, int]], component_bbox: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int]:
        """Return the union of an existing bbox and a component bbox."""
        if bbox is None:
            return component_bbox
        return (
            min(bbox[0], component_bbox[0]),
            min(bbox[1], component_bbox[1]),
            max(bbox[2], component_bbox[2]),
            max(bbox[3], component_bbox[3]),
        )

    def _crop_with_padding(self, image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
        """Crop an RGBA image, padding outside source bounds with transparency."""
        left, top, right, bottom = box
        width = max(1, right - left)
        height = max(1, bottom - top)
        result = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        source_left = max(0, left)
        source_top = max(0, top)
        source_right = min(image.width, right)
        source_bottom = min(image.height, bottom)
        if source_left >= source_right or source_top >= source_bottom:
            return result

        cropped = image.crop((source_left, source_top, source_right, source_bottom))
        result.alpha_composite(cropped, (source_left - left, source_top - top))
        return result

    def _ensure_cut_lines(self, rows: int, cols: int, image_size: tuple[int, int], force: bool = False) -> None:
        """Initialize cut lines from rows/cols, preserving edits while the signature matches."""
        width, height = image_size
        signature = (width, height, rows, cols)
        if not force and self.cut_grid_signature == signature and self._cut_lines_match(rows, cols, image_size):
            return

        self.vertical_cut_lines, self.horizontal_cut_lines = self._equal_cut_lines(rows, cols, image_size)
        self.cut_grid_signature = signature
        self._update_selected_line_label()

    @staticmethod
    def _equal_cut_lines(rows: int, cols: int, image_size: tuple[int, int]) -> tuple[list[int], list[int]]:
        """Return rows x cols equal-grid cut lines for an image size."""
        width, height = image_size
        vertical_lines = [round(width * col / cols) for col in range(cols + 1)]
        horizontal_lines = [round(height * row / rows) for row in range(rows + 1)]
        vertical_lines[0] = 0
        vertical_lines[-1] = width
        horizontal_lines[0] = 0
        horizontal_lines[-1] = height
        return vertical_lines, horizontal_lines

    def _cut_lines_match(self, rows: int, cols: int, image_size: tuple[int, int]) -> bool:
        """Return True when current cut lines fit the current image and grid settings."""
        width, height = image_size
        return (
            len(self.vertical_cut_lines) == cols + 1
            and len(self.horizontal_cut_lines) == rows + 1
            and self.vertical_cut_lines[0] == 0
            and self.horizontal_cut_lines[0] == 0
            and self.vertical_cut_lines[-1] == width
            and self.horizontal_cut_lines[-1] == height
            and all(a < b for a, b in zip(self.vertical_cut_lines, self.vertical_cut_lines[1:]))
            and all(a < b for a, b in zip(self.horizontal_cut_lines, self.horizontal_cut_lines[1:]))
        )

    def _validate_cut_line_settings(self, rows: int, cols: int, image_size: tuple[int, int]) -> None:
        """Validate min cell size and current cut-line coordinates before export."""
        min_cell_size = self._validate_min_cell_size(preview=False)
        width, height = image_size
        if min_cell_size * cols > width or min_cell_size * rows > height:
            raise ValueError("min_cell_sizeが画像サイズとrows/colsに対して大きすぎます。")
        self._ensure_cut_lines(rows, cols, image_size)
        for left, right in zip(self.vertical_cut_lines, self.vertical_cut_lines[1:]):
            if right - left < min_cell_size:
                raise ValueError("縦カット線の間隔がmin_cell_size未満です。")
        for top, bottom in zip(self.horizontal_cut_lines, self.horizontal_cut_lines[1:]):
            if bottom - top < min_cell_size:
                raise ValueError("横カット線の間隔がmin_cell_size未満です。")

    def reset_cut_lines(self) -> None:
        """Reset cut lines back to an even rows x cols grid."""
        if self.loaded_image is None:
            self._show_error("画像未選択", "画像ファイルを選択してください。")
            return
        rows = self._validate_positive_int(self.rows_var.get(), "rows")
        cols = self._validate_positive_int(self.cols_var.get(), "cols")
        if rows is None or cols is None:
            return
        self._ensure_cut_lines(rows, cols, self.loaded_image.size, force=True)
        self.log("カット線を均等割り付けに戻しました。")
        self.update_preview()

    def save_cut_lines_json(self) -> None:
        """Save current cut lines to a JSON preset."""
        if self.loaded_image is None:
            self._show_error("画像未選択", "画像ファイルを選択してください。")
            return
        rows = self._validate_positive_int(self.rows_var.get(), "rows")
        cols = self._validate_positive_int(self.cols_var.get(), "cols")
        if rows is None or cols is None:
            return
        self._ensure_cut_lines(rows, cols, self.loaded_image.size)
        file_name = filedialog.asksaveasfilename(
            title="カット線JSON保存",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not file_name:
            return
        data = {
            "image_width": self.loaded_image.width,
            "image_height": self.loaded_image.height,
            "rows": rows,
            "cols": cols,
            "vertical_lines": self.vertical_cut_lines,
            "horizontal_lines": self.horizontal_cut_lines,
        }
        try:
            Path(file_name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self._show_error("JSON保存失敗", f"カット線JSONを保存できませんでした。\n{exc}")
            return
        self.log(f"カット線JSON保存: {file_name}")

    def load_cut_lines_json(self) -> None:
        """Load cut lines from a JSON preset."""
        if self.loaded_image is None:
            self._show_error("画像未選択", "画像ファイルを選択してください。")
            return
        rows = self._validate_positive_int(self.rows_var.get(), "rows")
        cols = self._validate_positive_int(self.cols_var.get(), "cols")
        if rows is None or cols is None:
            return
        file_name = filedialog.askopenfilename(
            title="カット線JSON読み込み",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not file_name:
            return
        try:
            data = json.loads(Path(file_name).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("JSONのルートはオブジェクトである必要があります。")
            vertical_lines = [int(value) for value in data["vertical_lines"]]
            horizontal_lines = [int(value) for value in data["horizontal_lines"]]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            self._show_error("JSON読み込み失敗", f"カット線JSONを読み込めませんでした。\n{exc}")
            return

        if (
            data.get("image_width") != self.loaded_image.width
            or data.get("image_height") != self.loaded_image.height
            or data.get("rows") != rows
            or data.get("cols") != cols
        ):
            self._show_error("JSON内容不一致", "JSONの画像サイズ・rows・colsが現在の設定と一致しません。")
            return
        if len(vertical_lines) != cols + 1 or len(horizontal_lines) != rows + 1:
            self._show_error("JSON内容不一致", "JSON内のカット線数がrows/colsと一致しません。")
            return
        if not self._are_valid_cut_lines(vertical_lines, self.loaded_image.width) or not self._are_valid_cut_lines(
            horizontal_lines, self.loaded_image.height
        ):
            self._show_error("JSON内容不一致", "JSON内のカット線座標が不正です。")
            return

        self.vertical_cut_lines = vertical_lines
        self.horizontal_cut_lines = horizontal_lines
        self.cut_grid_signature = (self.loaded_image.width, self.loaded_image.height, rows, cols)
        self._update_selected_line_label()
        self.log(f"カット線JSON読み込み: {file_name}")
        self.update_preview()

    @staticmethod
    def _are_valid_cut_lines(lines: list[int], size: int) -> bool:
        """Return True when cut lines are sorted, bounded, and include fixed outer edges."""
        return bool(lines) and lines[0] == 0 and lines[-1] == size and all(a < b for a, b in zip(lines, lines[1:]))

    def _on_cut_edit_changed(self) -> None:
        """Initialize cut lines when edit mode is enabled and refresh the preview."""
        if self.loaded_image is not None and self.cut_edit_var.get():
            rows = self._safe_positive_int(self.rows_var.get())
            cols = self._safe_positive_int(self.cols_var.get())
            if rows and cols:
                self._ensure_cut_lines(rows, cols, self.loaded_image.size)
        self.update_preview()

    def _on_cut_line_press(self, event: tk.Event) -> None:
        """Select an inner cut line near the pointer."""
        if not self.cut_edit_var.get() or self.loaded_image is None:
            return
        hit = self._nearest_cut_line(event.x, event.y)
        self.dragging_cut_line = hit
        self._update_selected_line_label(hit)
        self._draw_cut_lines_on_canvas(editable=True)

    def _on_cut_line_drag(self, event: tk.Event) -> None:
        """Move the selected cut line, clamped to adjacent lines and optional snapping."""
        if not self.dragging_cut_line or self.loaded_image is None:
            return
        rows = self._safe_positive_int(self.rows_var.get())
        cols = self._safe_positive_int(self.cols_var.get())
        if not rows or not cols:
            return
        self._ensure_cut_lines(rows, cols, self.loaded_image.size)
        kind, index = self.dragging_cut_line
        image_x, image_y = self._canvas_to_image_coords(event.x, event.y)
        min_cell_size = self._effective_min_cell_size(self.loaded_image.size, rows, cols)
        if kind == "vertical":
            value = self._snap_coordinate(round(image_x))
            value = max(self.vertical_cut_lines[index - 1] + min_cell_size, value)
            value = min(self.vertical_cut_lines[index + 1] - min_cell_size, value)
            self.vertical_cut_lines[index] = value
        else:
            value = self._snap_coordinate(round(image_y))
            value = max(self.horizontal_cut_lines[index - 1] + min_cell_size, value)
            value = min(self.horizontal_cut_lines[index + 1] - min_cell_size, value)
            self.horizontal_cut_lines[index] = value
        self._update_selected_line_label(self.dragging_cut_line)
        self._draw_cut_lines_on_canvas(editable=True)

    def _on_cut_line_release(self, _event: tk.Event) -> None:
        """Finish dragging and update processed preview."""
        if self.dragging_cut_line is not None:
            self.dragging_cut_line = None
            self.update_preview()

    def _nearest_cut_line(self, canvas_x: int, canvas_y: int) -> Optional[tuple[str, int]]:
        """Return the nearest movable cut line under the pointer."""
        if not self.vertical_cut_lines or not self.horizontal_cut_lines:
            return None
        hit_distance = 8
        best: Optional[tuple[str, int]] = None
        best_distance = hit_distance + 1
        for index, line_x in enumerate(self.vertical_cut_lines[1:-1], start=1):
            preview_x = self.source_preview_offset[0] + line_x * self.source_preview_scale
            distance = abs(canvas_x - preview_x)
            if distance <= hit_distance and distance < best_distance:
                best = ("vertical", index)
                best_distance = distance
        for index, line_y in enumerate(self.horizontal_cut_lines[1:-1], start=1):
            preview_y = self.source_preview_offset[1] + line_y * self.source_preview_scale
            distance = abs(canvas_y - preview_y)
            if distance <= hit_distance and distance < best_distance:
                best = ("horizontal", index)
                best_distance = distance
        return best

    def _canvas_to_image_coords(self, canvas_x: int, canvas_y: int) -> tuple[float, float]:
        """Convert preview canvas coordinates to original image coordinates."""
        offset_x, offset_y = self.source_preview_offset
        if self.source_preview_scale <= 0:
            return 0, 0
        image_x = (canvas_x - offset_x) / self.source_preview_scale
        image_y = (canvas_y - offset_y) / self.source_preview_scale
        return image_x, image_y

    def _draw_cut_lines_on_canvas(self, editable: bool, rows: Optional[int] = None, cols: Optional[int] = None) -> None:
        """Overlay current cut lines and coordinates on the source preview canvas."""
        if not self.loaded_image:
            return
        if editable:
            vertical_lines = self.vertical_cut_lines
            horizontal_lines = self.horizontal_cut_lines
        elif rows and cols:
            vertical_lines, horizontal_lines = self._equal_cut_lines(rows, cols, self.loaded_image.size)
        else:
            vertical_lines = self.vertical_cut_lines
            horizontal_lines = self.horizontal_cut_lines

        canvas = self.source_canvas
        canvas.delete("cut_line")
        offset_x, offset_y = self.source_preview_offset
        preview_width, preview_height = self.source_preview_size
        right = offset_x + preview_width
        bottom = offset_y + preview_height
        canvas.create_rectangle(offset_x, offset_y, right, bottom, outline="#ffffff", width=2, tags="cut_line")
        selected = self.dragging_cut_line
        normal_color = "#ffcc00" if editable else "#ff0000"
        for index, line_x in enumerate(vertical_lines[1:-1], start=1):
            x = offset_x + line_x * self.source_preview_scale
            color = "#00ffff" if selected == ("vertical", index) else normal_color
            width = 4 if selected == ("vertical", index) else 2
            canvas.create_line(x, offset_y, x, bottom, fill=color, width=width, tags="cut_line")
            if editable:
                canvas.create_text(x + 4, offset_y + 12, text=str(line_x), fill=color, anchor="nw", tags="cut_line")
        for index, line_y in enumerate(horizontal_lines[1:-1], start=1):
            y = offset_y + line_y * self.source_preview_scale
            color = "#00ffff" if selected == ("horizontal", index) else normal_color
            width = 4 if selected == ("horizontal", index) else 2
            canvas.create_line(offset_x, y, right, y, fill=color, width=width, tags="cut_line")
            if editable:
                canvas.create_text(offset_x + 4, y + 4, text=str(line_y), fill=color, anchor="nw", tags="cut_line")

    def _update_selected_line_label(self, selected: Optional[tuple[str, int]] = None) -> None:
        """Show selected line coordinates and all current cut line positions."""
        if selected is None:
            selected_text = "選択中の線: なし"
        else:
            kind, index = selected
            if kind == "vertical" and index < len(self.vertical_cut_lines):
                selected_text = f"選択中の線: 縦 {index} = {self.vertical_cut_lines[index]}px"
            elif kind == "horizontal" and index < len(self.horizontal_cut_lines):
                selected_text = f"選択中の線: 横 {index} = {self.horizontal_cut_lines[index]}px"
            else:
                selected_text = "選択中の線: なし"
        self.selected_line_var.set(f"{selected_text}\n縦: {self.vertical_cut_lines}\n横: {self.horizontal_cut_lines}")

    def _snap_coordinate(self, value: int) -> int:
        """Snap a coordinate to the selected unit while dragging."""
        if not self.snap_var.get():
            return value
        unit = self._safe_positive_int(self.snap_unit_var.get()) or 1
        return round(value / unit) * unit

    def _effective_min_cell_size(self, image_size: tuple[int, int], rows: int, cols: int) -> int:
        """Return a min cell size that keeps dragging possible when requested value is too large."""
        requested = self._validate_min_cell_size(preview=True)
        max_possible = max(1, min(image_size[0] // cols, image_size[1] // rows))
        return min(requested, max_possible)

    def _validate_min_cell_size(self, preview: bool = False) -> int:
        """Validate minimum cell size."""
        result = self._safe_positive_int(self.min_cell_size_var.get())
        if result is None:
            if preview:
                return 128
            raise ValueError("min_cell_sizeには1以上の整数を入力してください。")
        return result

    def _set_preview_image(self, image: Image.Image, canvas: tk.Canvas, slot: str) -> None:
        """Scale a preview image onto a canvas."""
        preview = image.copy()
        preview.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
        canvas_width, canvas_height = PREVIEW_MAX_SIZE
        offset_x = (canvas_width - preview.width) // 2
        offset_y = (canvas_height - preview.height) // 2

        photo = ImageTk.PhotoImage(preview)
        if slot == "source":
            self.preview_photo_source = photo
            self.source_preview_scale = preview.width / image.width if image.width else 1.0
            self.source_preview_offset = (offset_x, offset_y)
            self.source_preview_size = preview.size
        else:
            self.preview_photo_output = photo

        canvas.configure(width=canvas_width, height=canvas_height)
        canvas.delete("all")
        canvas.create_image(offset_x, offset_y, image=photo, anchor="nw")

    def _validate_positive_int(self, value: str, field_name: str) -> Optional[int]:
        """Validate a positive integer field and show an error if invalid."""
        result = self._safe_positive_int(value)
        if result is None:
            self._show_error(f"{field_name}が不正", f"{field_name}には1以上の整数を入力してください。")
        return result

    def _validate_positive_field(self, value: str, field_name: str, preview: bool, fallback: int) -> int:
        """Validate a positive integer field with a preview fallback."""
        result = self._safe_positive_int(value)
        if result is None:
            if preview:
                return fallback
            raise ValueError(f"{field_name}には1以上の整数を入力してください。")
        return result

    def _validate_non_negative_int(self, value: str, field_name: str, preview: bool, fallback: int) -> int:
        """Validate a non-negative integer field with a preview fallback."""
        try:
            result = int(value)
        except ValueError as exc:
            if preview:
                return fallback
            raise ValueError(f"{field_name}には0以上の整数を入力してください。") from exc
        if result < 0:
            if preview:
                return fallback
            raise ValueError(f"{field_name}には0以上の整数を入力してください。")
        return result

    def _validate_threshold_value(
        self, value: str, field_name: str = "threshold", preview: bool = False, fallback: int = 15
    ) -> int:
        """Validate a 0-255 threshold value."""
        try:
            threshold = int(value)
        except ValueError as exc:
            if preview:
                return fallback
            raise ValueError(f"{field_name}には0〜255の整数を入力してください。") from exc
        if not 0 <= threshold <= 255:
            if preview:
                return fallback
            raise ValueError(f"{field_name}には0〜255の整数を入力してください。")
        return threshold

    def _validate_padding_value(self, value: str, preview: bool = False) -> int:
        """Validate a padding value."""
        try:
            padding = int(value)
        except ValueError as exc:
            if preview:
                return 0
            raise ValueError("paddingには0以上の整数を入力してください。") from exc
        if padding < 0:
            if preview:
                return 0
            raise ValueError("paddingには0以上の整数を入力してください。")
        return padding

    @staticmethod
    def _safe_positive_int(value: str) -> Optional[int]:
        """Parse a string as a positive integer."""
        try:
            result = int(value)
        except ValueError:
            return None
        return result if result > 0 else None

    def _show_error(self, title: str, message: str) -> None:
        """Show an error dialog and write it to the log."""
        self.log(f"エラー: {title} - {message}")
        messagebox.showerror(title, message)

    def log(self, message: str) -> None:
        """Append a message to the read-only log box."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def main() -> None:
    """Start the application."""
    root = tk.Tk()
    ImageSplitterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
