"""Desktop GUI tool for splitting one image into a rows x columns grid.

External dependency: Pillow
"""

from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

from PIL import Image, ImageChops, ImageDraw, ImageTk, UnidentifiedImageError

SUPPORTED_FILETYPES = (
    ("Image files", "*.png *.jpg *.jpeg *.webp"),
    ("PNG files", "*.png"),
    ("JPEG files", "*.jpg *.jpeg"),
    ("WEBP files", "*.webp"),
    ("All files", "*.*"),
)
PREVIEW_MAX_SIZE = (520, 420)


class ImageSplitterApp:
    """Main tkinter application for image splitting."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Splitter")
        self.root.minsize(980, 720)

        self.image_path: Optional[Path] = None
        self.output_dir: Optional[Path] = None
        self.loaded_image: Optional[Image.Image] = None
        self.preview_photo_before: Optional[ImageTk.PhotoImage] = None
        self.preview_photo_after: Optional[ImageTk.PhotoImage] = None

        self.rows_var = tk.StringVar(value="2")
        self.cols_var = tk.StringVar(value="2")
        self.resize_var = tk.BooleanVar(value=True)
        self.width_var = tk.StringVar(value="1024")
        self.height_var = tk.StringVar(value="1024")
        self.image_path_var = tk.StringVar(value="画像が選択されていません")
        self.output_dir_var = tk.StringVar(value="出力フォルダが選択されていません")
        self.auto_margin_var = tk.BooleanVar(value=True)
        self.detection_mode_var = tk.StringVar(value="auto")
        self.threshold_var = tk.StringVar(value="15")
        self.padding_var = tk.StringVar(value="0")
        self.square_var = tk.BooleanVar(value=False)
        self.center_var = tk.BooleanVar(value=True)
        self.show_grid_var = tk.BooleanVar(value=True)
        self.post_split_resize_var = tk.BooleanVar(value=False)
        self.output_cell_width_var = tk.StringVar(value="256")
        self.output_cell_height_var = tk.StringVar(value="256")
        self.fit_mode_var = tk.StringVar(value="contain")
        self.alignment_var = tk.StringVar(value="center")
        self.background_var = tk.StringVar(value="transparent")
        self.cell_centering_var = tk.BooleanVar(value=False)
        self.cell_detection_mode_var = tk.StringVar(value="auto")
        self.cell_background_var = tk.StringVar(value="transparent")
        self.cell_threshold_var = tk.StringVar(value="15")
        self.cell_padding_var = tk.StringVar(value="0")
        self.scale_limit_var = tk.StringVar(value="2.0")
        self.min_area_var = tk.StringVar(value="1")
        self.cut_edit_var = tk.BooleanVar(value=False)
        self.snap_var = tk.BooleanVar(value=True)
        self.snap_unit_var = tk.StringVar(value="8")
        self.min_cell_size_var = tk.StringVar(value="128")
        self.selected_line_var = tk.StringVar(value="選択中の線: なし")

        self.vertical_cut_lines: list[int] = []
        self.horizontal_cut_lines: list[int] = []
        self.cut_grid_signature: Optional[tuple[int, int, int, int]] = None
        self.dragging_cut_line: Optional[tuple[str, int]] = None
        self.before_preview_scale = 1.0
        self.before_preview_offset = (0, 0)
        self.before_preview_size = (0, 0)

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
        controls.bind(
            "<Configure>",
            lambda event: controls_canvas.configure(scrollregion=controls_canvas.bbox("all")),
        )
        controls_canvas.bind(
            "<Configure>",
            lambda event: controls_canvas.itemconfigure(controls_window, width=event.width),
        )

        preview_and_log = ttk.Frame(self.root, padding=(0, 12, 12, 12))
        preview_and_log.grid(row=0, column=1, sticky="nsew")
        preview_and_log.columnconfigure(0, weight=1)
        preview_and_log.rowconfigure(0, weight=1)
        preview_and_log.rowconfigure(1, weight=0)

        self._build_controls(controls)
        self._build_preview(preview_and_log)
        self._build_log(preview_and_log)

    def _build_controls(self, parent: ttk.Frame) -> None:
        """Create the left-side control panel."""
        parent.columnconfigure(0, weight=1)

        image_frame = ttk.LabelFrame(parent, text="入力画像", padding=10)
        image_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        image_frame.columnconfigure(0, weight=1)
        ttk.Button(image_frame, text="画像ファイルを選択", command=self.select_image).grid(row=0, column=0, sticky="ew")
        ttk.Label(image_frame, textvariable=self.image_path_var, wraplength=260).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        split_frame = ttk.LabelFrame(parent, text="分割設定", padding=10)
        split_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(split_frame, text="rows").grid(row=0, column=0, sticky="w")
        ttk.Entry(split_frame, textvariable=self.rows_var, width=10).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(split_frame, text="cols").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(split_frame, textvariable=self.cols_var, width=10).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        resize_frame = ttk.LabelFrame(parent, text="出力サイズ設定", padding=10)
        resize_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        resize_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            resize_frame,
            text="指定サイズにリサイズしてから分割",
            variable=self.resize_var,
            command=self._on_resize_mode_changed,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(resize_frame, text="width").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.width_entry = ttk.Entry(resize_frame, textvariable=self.width_var, width=10)
        self.width_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(resize_frame, text="height").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.height_entry = ttk.Entry(resize_frame, textvariable=self.height_var, width=10)
        self.height_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        margin_frame = ttk.LabelFrame(parent, text="自動余白調整", padding=10)
        margin_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        margin_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            margin_frame,
            text="分割前に余白を自動調整",
            variable=self.auto_margin_var,
            command=self.update_preview,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(margin_frame, text="判定モード").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            margin_frame,
            textvariable=self.detection_mode_var,
            values=("auto", "alpha", "brightness"),
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(margin_frame, text="threshold").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(margin_frame, textvariable=self.threshold_var, width=10).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(margin_frame, text="padding").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(margin_frame, textvariable=self.padding_var, width=10).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Checkbutton(margin_frame, text="正方形化", variable=self.square_var, command=self.update_preview).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(margin_frame, text="中央寄せ", variable=self.center_var, command=self.update_preview).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(margin_frame, text="分割グリッド表示", variable=self.show_grid_var, command=self.update_preview).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        post_frame = ttk.LabelFrame(parent, text="分割後リサイズ", padding=10)
        post_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        post_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            post_frame,
            text="分割後リサイズモード",
            variable=self.post_split_resize_var,
            command=self.update_preview,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(post_frame, text="cell width").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(post_frame, textvariable=self.output_cell_width_var, width=10).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(post_frame, text="cell height").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(post_frame, textvariable=self.output_cell_height_var, width=10).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(post_frame, text="fit mode").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            post_frame, textvariable=self.fit_mode_var, values=("contain", "cover", "stretch"), state="readonly", width=12
        ).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(post_frame, text="alignment").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            post_frame, textvariable=self.alignment_var, values=("center", "top", "bottom"), state="readonly", width=12
        ).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(post_frame, text="background").grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            post_frame, textvariable=self.background_var, values=("transparent", "black"), state="readonly", width=12
        ).grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        cell_frame = ttk.LabelFrame(parent, text="セル個別センタリング", padding=10)
        cell_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        cell_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            cell_frame,
            text="セル個別センタリング ON",
            variable=self.cell_centering_var,
            command=self.update_preview,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(cell_frame, text="detection").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            cell_frame, textvariable=self.cell_detection_mode_var, values=("auto", "alpha", "brightness"), state="readonly", width=12
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="background").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            cell_frame, textvariable=self.cell_background_var, values=("transparent", "black"), state="readonly", width=12
        ).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="threshold").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.cell_threshold_var, width=10).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="padding").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.cell_padding_var, width=10).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="scale limit").grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.scale_limit_var, width=10).grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(cell_frame, text="min_area").grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cell_frame, textvariable=self.min_area_var, width=10).grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        cut_frame = ttk.LabelFrame(parent, text="カット線編集", padding=10)
        cut_frame.grid(row=6, column=0, sticky="ew", pady=(0, 10))
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
            values=("1", "8", "16", "32", "64"),
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

        output_frame = ttk.LabelFrame(parent, text="出力フォルダ", padding=10)
        output_frame.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        ttk.Button(output_frame, text="出力フォルダを選択", command=self.select_output_dir).grid(row=0, column=0, sticky="ew")
        ttk.Label(output_frame, textvariable=self.output_dir_var, wraplength=260).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(parent, text="分割実行", command=self.split_image).grid(row=8, column=0, sticky="ew", ipady=6)

    def _build_preview(self, parent: ttk.Frame) -> None:
        """Create the preview area."""
        preview_frame = ttk.LabelFrame(parent, text="プレビュー", padding=10)
        preview_frame.grid(row=0, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        ttk.Label(preview_frame, text="処理前 / カット線編集").grid(row=0, column=0, sticky="ew")
        ttk.Label(preview_frame, text="処理後").grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.preview_before_label = tk.Canvas(
            preview_frame,
            width=PREVIEW_MAX_SIZE[0],
            height=PREVIEW_MAX_SIZE[1],
            background="#222222",
            highlightthickness=0,
        )
        self.preview_before_label.grid(row=1, column=0, sticky="nsew")
        self.preview_after_label = tk.Canvas(
            preview_frame,
            width=PREVIEW_MAX_SIZE[0],
            height=PREVIEW_MAX_SIZE[1],
            background="#222222",
            highlightthickness=0,
        )
        self.preview_after_label.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        self.preview_before_label.bind("<ButtonPress-1>", self._on_cut_line_press)
        self.preview_before_label.bind("<B1-Motion>", self._on_cut_line_drag)
        self.preview_before_label.bind("<ButtonRelease-1>", self._on_cut_line_release)

    def _build_log(self, parent: ttk.Frame) -> None:
        """Create the execution log area."""
        log_frame = ttk.LabelFrame(parent, text="ログ", padding=10)
        log_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="ew")

    def _bind_events(self) -> None:
        """Refresh preview when grid settings change."""
        for variable in (
            self.rows_var,
            self.cols_var,
            self.detection_mode_var,
            self.threshold_var,
            self.padding_var,
            self.auto_margin_var,
            self.square_var,
            self.center_var,
            self.show_grid_var,
            self.post_split_resize_var,
            self.output_cell_width_var,
            self.output_cell_height_var,
            self.fit_mode_var,
            self.alignment_var,
            self.background_var,
            self.cell_centering_var,
            self.cell_detection_mode_var,
            self.cell_background_var,
            self.cell_threshold_var,
            self.cell_padding_var,
            self.scale_limit_var,
            self.min_area_var,
            self.cut_edit_var,
            self.snap_var,
            self.snap_unit_var,
            self.min_cell_size_var,
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
        self.image_path_var.set(str(path))
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
        """Draw a scaled image preview with grid lines."""
        if self.loaded_image is None:
            return

        rows = self._safe_positive_int(self.rows_var.get())
        cols = self._safe_positive_int(self.cols_var.get())

        before = self.loaded_image.convert("RGBA").copy()
        if rows and cols and self.cut_edit_var.get():
            self._ensure_cut_lines(rows, cols, before.size)
        before_rows = rows if not self.cut_edit_var.get() else None
        before_cols = cols if not self.cut_edit_var.get() else None
        self._set_preview_image(before, self.preview_before_label, "before", before_rows, before_cols)
        if rows and cols and self.cut_edit_var.get():
            self._draw_cut_lines_on_canvas()

        try:
            if rows and cols and self.cut_edit_var.get():
                after = self._build_cut_line_preview(rows, cols)
            elif rows and cols and self._uses_cell_pipeline():
                after = self._build_cell_pipeline_preview(rows, cols)
            elif rows and cols:
                after = self._prepare_source_image(rows=rows, cols=cols, preview=True)
            else:
                after = before.copy()
        except (ValueError, OSError):
            after = before.copy()
        preview_rows = rows if not self._uses_cell_pipeline() and not self.cut_edit_var.get() else None
        preview_cols = cols if not self._uses_cell_pipeline() and not self.cut_edit_var.get() else None
        self._set_preview_image(after, self.preview_after_label, "after", preview_rows, preview_cols)

    def split_image(self) -> None:
        """Validate settings, split the image, and save PNG files."""
        if self.loaded_image is None or self.image_path is None:
            self._show_error("画像未選択", "画像ファイルを選択してください。")
            return

        if self.output_dir is None:
            self._show_error("出力フォルダ未選択", "出力フォルダを選択してください。")
            return

        rows = self._validate_positive_int(self.rows_var.get(), "rows")
        if rows is None:
            return
        cols = self._validate_positive_int(self.cols_var.get(), "cols")
        if cols is None:
            return

        base_name = self.image_path.stem
        total = rows * cols
        digits = max(2, int(math.log10(total)) + 1 if total > 0 else 2)

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if self.cut_edit_var.get():
                self._save_cut_line_tiles(rows, cols, base_name, digits)
            elif self._uses_cell_pipeline():
                self._save_cell_pipeline_tiles(rows, cols, base_name, digits)
            else:
                self._save_whole_image_tiles(rows, cols, base_name, digits)
        except ValueError as exc:
            self._show_error("設定が不正", str(exc))
            return
        except OSError as exc:
            self._show_error("出力エラー", f"PNGの保存に失敗しました。\n{exc}")
            return

        self.log(f"出力完了: {total} ファイルを保存しました ({self.output_dir})")
        messagebox.showinfo("出力完了", f"{total} ファイルを保存しました。")

    def _save_cut_line_tiles(self, rows: int, cols: int, base_name: str, digits: int) -> None:
        """Save tiles using the editable cut-line boundaries."""
        if self.loaded_image is None:
            raise OSError("画像が読み込まれていません。")

        source = self.loaded_image.convert("RGBA")
        self._validate_cut_line_settings(rows, cols, source.size)
        self._ensure_cut_lines(rows, cols, source.size)
        settings = self._cell_pipeline_settings(preview=False)
        settings["fit_mode"] = str(settings["fit_mode"] or "contain")
        settings["alignment"] = str(settings["alignment"] or "center")

        for row, col, tile in self._iter_cut_line_tiles(source):
            index = row * cols + col + 1
            processed = self._process_cell_tile(tile, settings)
            processed.save(self.output_dir / f"{base_name}_{index:0{digits}d}.png", "PNG")

    def _build_cut_line_preview(self, rows: int, cols: int) -> Image.Image:
        """Build a processed preview using the editable cut-line grid."""
        if self.loaded_image is None:
            raise OSError("画像が読み込まれていません。")

        source = self.loaded_image.convert("RGBA")
        self._ensure_cut_lines(rows, cols, source.size)
        settings = self._cell_pipeline_settings(preview=True)
        preview = Image.new(
            "RGBA",
            (int(settings["output_width"]) * cols, int(settings["output_height"]) * rows),
            self._background_fill(str(settings["background"])),
        )
        for row, col, tile in self._iter_cut_line_tiles(source):
            processed = self._process_cell_tile(tile, settings)
            preview.paste(processed, (col * int(settings["output_width"]), row * int(settings["output_height"])))
        return preview

    def _iter_cut_line_tiles(self, source: Image.Image):
        """Yield tiles from the current editable cut-line coordinates."""
        for row in range(len(self.horizontal_cut_lines) - 1):
            upper = self.horizontal_cut_lines[row]
            lower = self.horizontal_cut_lines[row + 1]
            for col in range(len(self.vertical_cut_lines) - 1):
                left = self.vertical_cut_lines[col]
                right = self.vertical_cut_lines[col + 1]
                yield row, col, source.crop((left, upper, right, lower))

    def _ensure_cut_lines(self, rows: int, cols: int, image_size: tuple[int, int], force: bool = False) -> None:
        """Initialize editable cut lines from rows/cols, preserving them while the signature matches."""
        width, height = image_size
        signature = (width, height, rows, cols)
        if not force and self.cut_grid_signature == signature and self._cut_lines_match(rows, cols, image_size):
            return

        self.vertical_cut_lines = [round(width * col / cols) for col in range(cols + 1)]
        self.horizontal_cut_lines = [round(height * row / rows) for row in range(rows + 1)]
        self.vertical_cut_lines[0] = 0
        self.vertical_cut_lines[-1] = width
        self.horizontal_cut_lines[0] = 0
        self.horizontal_cut_lines[-1] = height
        self.cut_grid_signature = signature
        self._update_selected_line_label()

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
        """Reset editable cut lines back to an even rows x cols grid."""
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
        """Save current editable cut lines to a JSON preset."""
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
        """Load editable cut lines from a JSON preset."""
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
            self._show_error("JSON不一致", "JSONの画像サイズ・rows・colsが現在の設定と一致しません。")
            return
        if len(vertical_lines) != cols + 1 or len(horizontal_lines) != rows + 1:
            self._show_error("JSON不一致", "JSON内のカット線数がrows/colsと一致しません。")
            return
        if not self._are_valid_cut_lines(vertical_lines, self.loaded_image.width) or not self._are_valid_cut_lines(
            horizontal_lines, self.loaded_image.height
        ):
            self._show_error("JSON不一致", "JSON内のカット線座標が不正です。")
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
        self._draw_cut_lines_on_canvas()

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
        self._draw_cut_lines_on_canvas()

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
            preview_x = self.before_preview_offset[0] + line_x * self.before_preview_scale
            distance = abs(canvas_x - preview_x)
            if distance <= hit_distance and distance < best_distance:
                best = ("vertical", index)
                best_distance = distance
        for index, line_y in enumerate(self.horizontal_cut_lines[1:-1], start=1):
            preview_y = self.before_preview_offset[1] + line_y * self.before_preview_scale
            distance = abs(canvas_y - preview_y)
            if distance <= hit_distance and distance < best_distance:
                best = ("horizontal", index)
                best_distance = distance
        return best

    def _canvas_to_image_coords(self, canvas_x: int, canvas_y: int) -> tuple[float, float]:
        """Convert preview canvas coordinates to original image coordinates."""
        offset_x, offset_y = self.before_preview_offset
        if self.before_preview_scale <= 0:
            return 0, 0
        image_x = (canvas_x - offset_x) / self.before_preview_scale
        image_y = (canvas_y - offset_y) / self.before_preview_scale
        return image_x, image_y

    def _draw_cut_lines_on_canvas(self) -> None:
        """Overlay editable cut lines and coordinates on the before-preview canvas."""
        if not isinstance(self.preview_before_label, tk.Canvas) or not self.loaded_image:
            return
        canvas = self.preview_before_label
        canvas.delete("cut_line")
        offset_x, offset_y = self.before_preview_offset
        preview_width, preview_height = self.before_preview_size
        right = offset_x + preview_width
        bottom = offset_y + preview_height
        canvas.create_rectangle(offset_x, offset_y, right, bottom, outline="#ffffff", width=2, tags="cut_line")
        selected = self.dragging_cut_line
        for index, line_x in enumerate(self.vertical_cut_lines[1:-1], start=1):
            x = offset_x + line_x * self.before_preview_scale
            color = "#00ffff" if selected == ("vertical", index) else "#ffcc00"
            width = 4 if selected == ("vertical", index) else 2
            canvas.create_line(x, offset_y, x, bottom, fill=color, width=width, tags="cut_line")
            canvas.create_text(x + 4, offset_y + 12, text=str(line_x), fill=color, anchor="nw", tags="cut_line")
        for index, line_y in enumerate(self.horizontal_cut_lines[1:-1], start=1):
            y = offset_y + line_y * self.before_preview_scale
            color = "#00ffff" if selected == ("horizontal", index) else "#ffcc00"
            width = 4 if selected == ("horizontal", index) else 2
            canvas.create_line(offset_x, y, right, y, fill=color, width=width, tags="cut_line")
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
        self.selected_line_var.set(
            f"{selected_text}\n縦: {self.vertical_cut_lines}\n横: {self.horizontal_cut_lines}"
        )

    def _snap_coordinate(self, value: int) -> int:
        """Snap a coordinate to the selected unit while dragging."""
        if not self.snap_var.get():
            return value
        unit = self._safe_positive_int(self.snap_unit_var.get()) or 1
        return round(value / unit) * unit

    def _effective_min_cell_size(self, image_size: tuple[int, int], rows: int, cols: int) -> int:
        """Return a min cell size that keeps dragging possible even when the requested value is too large."""
        requested = self._validate_min_cell_size(preview=True)
        max_possible = max(1, min(image_size[0] // cols, image_size[1] // rows))
        return min(requested, max_possible)

    def _validate_min_cell_size(self, preview: bool = False) -> int:
        """Validate the editable cut-line minimum cell size."""
        result = self._safe_positive_int(self.min_cell_size_var.get())
        if result is None:
            if preview:
                return 128
            raise ValueError("min_cell_sizeには1以上の整数を入力してください。")
        return result

    def _uses_cell_pipeline(self) -> bool:
        """Return True when tiles should be processed after the initial split."""
        return self.post_split_resize_var.get() or self.cell_centering_var.get()

    def _save_whole_image_tiles(self, rows: int, cols: int, base_name: str, digits: int) -> None:
        """Save tiles using the traditional whole-image preprocessing pipeline."""
        source = self._prepare_source_image(rows=rows, cols=cols)
        tile_width = source.width // cols
        tile_height = source.height // rows
        if tile_width <= 0 or tile_height <= 0:
            raise ValueError("rows/colsが画像サイズに対して大きすぎます。")

        for row in range(rows):
            for col in range(cols):
                index = row * cols + col + 1
                left = col * tile_width
                upper = row * tile_height
                right = left + tile_width
                lower = upper + tile_height
                tile = source.crop((left, upper, right, lower))
                tile.save(self.output_dir / f"{base_name}_{index:0{digits}d}.png", "PNG")

    def _save_cell_pipeline_tiles(self, rows: int, cols: int, base_name: str, digits: int) -> None:
        """Split the original image first, process each cell, and save PNG tiles."""
        if self.loaded_image is None:
            raise OSError("画像が読み込まれていません。")

        settings = self._cell_pipeline_settings(preview=False)
        source = self.loaded_image.convert("RGBA")
        for row, col, tile in self._iter_original_grid_tiles(source, rows, cols):
            index = row * cols + col + 1
            processed = self._process_cell_tile(tile, settings)
            processed.save(self.output_dir / f"{base_name}_{index:0{digits}d}.png", "PNG")

    def _build_cell_pipeline_preview(self, rows: int, cols: int) -> Image.Image:
        """Build a composite preview of post-split cell processing results."""
        if self.loaded_image is None:
            raise OSError("画像が読み込まれていません。")

        settings = self._cell_pipeline_settings(preview=True)
        source = self.loaded_image.convert("RGBA")
        preview = Image.new(
            "RGBA",
            (settings["output_width"] * cols, settings["output_height"] * rows),
            self._background_fill(settings["background"]),
        )
        for row, col, tile in self._iter_original_grid_tiles(source, rows, cols):
            processed = self._process_cell_tile(tile, settings)
            preview.paste(processed, (col * settings["output_width"], row * settings["output_height"]))
        return preview

    def _iter_original_grid_tiles(self, source: Image.Image, rows: int, cols: int):
        """Yield cells from the original image using proportional boundaries so all pixels are included."""
        for row in range(rows):
            upper = round(source.height * row / rows)
            lower = round(source.height * (row + 1) / rows)
            for col in range(cols):
                left = round(source.width * col / cols)
                right = round(source.width * (col + 1) / cols)
                yield row, col, source.crop((left, upper, right, lower))

    def _cell_pipeline_settings(self, preview: bool = False) -> dict[str, object]:
        """Validate and collect settings for post-split tile processing."""
        output_width = self._validate_positive_field(self.output_cell_width_var.get(), "output cell width", preview, 256)
        output_height = self._validate_positive_field(self.output_cell_height_var.get(), "output cell height", preview, 256)
        cell_threshold = self._validate_threshold_value(self.cell_threshold_var.get(), preview)
        cell_padding = self._validate_padding_value(self.cell_padding_var.get(), preview)
        scale_limit = self._validate_positive_float(self.scale_limit_var.get(), "scale limit", preview, 2.0)
        min_area = self._validate_non_negative_int(self.min_area_var.get(), "min_area", preview, 1)
        background = self.background_var.get() if self.post_split_resize_var.get() or self.cut_edit_var.get() else self.cell_background_var.get()
        cell_background = self.cell_background_var.get()
        if background not in {"transparent", "black"}:
            background = "transparent"
        if cell_background not in {"transparent", "black"}:
            cell_background = "transparent"

        return {
            "output_width": output_width,
            "output_height": output_height,
            "fit_mode": self.fit_mode_var.get(),
            "alignment": self.alignment_var.get(),
            "background": background,
            "cell_background": cell_background,
            "cell_centering": self.cell_centering_var.get(),
            "detection_mode": self.cell_detection_mode_var.get(),
            "threshold": cell_threshold,
            "padding": cell_padding,
            "scale_limit": scale_limit,
            "min_area": min_area,
        }

    def _process_cell_tile(self, tile: Image.Image, settings: dict[str, object]) -> Image.Image:
        """Apply optional per-cell centering, fit mode, background, and alignment."""
        source = tile.convert("RGBA")
        if settings["cell_centering"]:
            source = self._center_cell_content(
                source,
                str(settings["detection_mode"]),
                int(settings["threshold"]),
                int(settings["padding"]),
                int(settings["min_area"]),
                str(settings["cell_background"]),
            )
        return self._fit_tile_to_canvas(
            source,
            int(settings["output_width"]),
            int(settings["output_height"]),
            str(settings["fit_mode"]),
            str(settings["alignment"]),
            str(settings["background"]),
            float(settings["scale_limit"]) if settings["cell_centering"] else None,
        )

    def _center_cell_content(
        self,
        tile: Image.Image,
        detection_mode: str,
        threshold: int,
        padding: int,
        min_area: int,
        background: str,
    ) -> Image.Image:
        """Crop a cell to its detected content bbox and add padding before final fitting."""
        mode = self._resolve_detection_mode_for_image(tile, detection_mode)
        bbox = self._find_content_bbox_with_min_area(tile, mode, threshold, min_area)
        if bbox is None:
            return Image.new("RGBA", (1, 1), self._background_fill(background))

        left, top, right, bottom = bbox
        padded_box = (left - padding, top - padding, right + padding, bottom + padding)
        return self._crop_with_padding(tile, padded_box, self._background_fill(background))

    def _fit_tile_to_canvas(
        self,
        tile: Image.Image,
        output_width: int,
        output_height: int,
        fit_mode: str,
        alignment: str,
        background: str,
        scale_limit: Optional[float] = None,
    ) -> Image.Image:
        """Resize a tile according to fit mode and place it on the requested canvas."""
        fill = self._background_fill(background)
        canvas = Image.new("RGBA", (output_width, output_height), fill)
        fit_mode = fit_mode if fit_mode in {"contain", "cover", "stretch"} else "contain"
        alignment = alignment if alignment in {"center", "top", "bottom"} else "center"

        if fit_mode == "stretch":
            resized = tile.resize((output_width, output_height), Image.Resampling.LANCZOS)
            self._paste_centered(canvas, resized, "center")
            return canvas

        width_scale = output_width / tile.width
        height_scale = output_height / tile.height
        scale = min(width_scale, height_scale) if fit_mode == "contain" else max(width_scale, height_scale)
        if scale_limit is not None:
            scale = min(scale, scale_limit)
        resized_width = max(1, round(tile.width * scale))
        resized_height = max(1, round(tile.height * scale))
        resized = tile.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
        self._paste_centered(canvas, resized, alignment)
        return canvas

    def _paste_centered(self, canvas: Image.Image, image: Image.Image, alignment: str) -> None:
        """Paste an image horizontally centered and vertically aligned, cropping overflow."""
        x = round((canvas.width - image.width) / 2)
        if alignment == "top":
            y = 0
        elif alignment == "bottom":
            y = canvas.height - image.height
        else:
            y = round((canvas.height - image.height) / 2)
        self._paste_with_crop(canvas, image, x, y)

    @staticmethod
    def _paste_with_crop(canvas: Image.Image, image: Image.Image, x: int, y: int) -> None:
        """Paste with alpha while safely cropping source areas outside the canvas."""
        dest_left = max(0, x)
        dest_top = max(0, y)
        dest_right = min(canvas.width, x + image.width)
        dest_bottom = min(canvas.height, y + image.height)
        if dest_left >= dest_right or dest_top >= dest_bottom:
            return

        source_left = dest_left - x
        source_top = dest_top - y
        source_right = source_left + (dest_right - dest_left)
        source_bottom = source_top + (dest_bottom - dest_top)
        cropped = image.crop((source_left, source_top, source_right, source_bottom))
        canvas.alpha_composite(cropped, (dest_left, dest_top))

    def _find_content_bbox_with_min_area(
        self, image: Image.Image, mode: str, threshold: int, min_area: int
    ) -> Optional[tuple[int, int, int, int]]:
        """Find content bbox and ignore tiny detections below min_area."""
        mask = self._content_mask(image, mode, threshold)
        active_pixels = sum(count for value, count in enumerate(mask.histogram()) if value > 0)
        if active_pixels < min_area:
            return None
        return mask.getbbox()

    def _content_mask(self, image: Image.Image, mode: str, threshold: int) -> Image.Image:
        """Build an L-mode mask for alpha or brightness content detection."""
        if mode == "alpha":
            return image.getchannel("A").point(lambda alpha: 255 if alpha > 0 else 0)

        rgb = image.convert("RGB")
        alpha = image.getchannel("A")
        brightness = rgb.convert("L", matrix=(0.299, 0.587, 0.114, 0))
        bright_mask = brightness.point(lambda value: 255 if value >= threshold else 0)
        alpha_mask = alpha.point(lambda value: 255 if value > 0 else 0)
        return ImageChops.multiply(bright_mask, alpha_mask)

    def _resolve_detection_mode_for_image(self, image: Image.Image, selected: str) -> str:
        """Resolve auto detection mode for an arbitrary image or cell."""
        if selected in {"alpha", "brightness"}:
            return selected
        return "alpha" if image.getchannel("A").getextrema()[0] < 255 else "brightness"

    @staticmethod
    def _background_fill(background: str) -> tuple[int, int, int, int]:
        """Return the RGBA fill color for generated canvases."""
        return (0, 0, 0, 255) if background == "black" else (0, 0, 0, 0)

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

    def _validate_positive_float(self, value: str, field_name: str, preview: bool, fallback: float) -> float:
        """Validate a positive float field with a preview fallback."""
        try:
            result = float(value)
        except ValueError as exc:
            if preview:
                return fallback
            raise ValueError(f"{field_name}には0より大きい数値を入力してください。") from exc
        if result <= 0:
            if preview:
                return fallback
            raise ValueError(f"{field_name}には0より大きい数値を入力してください。")
        return result

    def _validate_threshold_value(self, value: str, preview: bool = False) -> int:
        """Validate a brightness threshold value independent from a specific Tk variable."""
        try:
            threshold = int(value)
        except ValueError as exc:
            if preview:
                return 15
            raise ValueError("thresholdには0〜255の整数を入力してください。") from exc
        if not 0 <= threshold <= 255:
            if preview:
                return 15
            raise ValueError("thresholdには0〜255の整数を入力してください。")
        return threshold

    def _validate_padding_value(self, value: str, preview: bool = False) -> int:
        """Validate a padding value independent from a specific Tk variable."""
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

    def _prepare_source_image(
        self, rows: int, cols: int, preview: bool = False
    ) -> Image.Image:
        """Return the RGBA image to split after resize, margin adjustment, and grid-safe trimming."""
        if self.loaded_image is None:
            raise OSError("画像が読み込まれていません。")

        source = self.loaded_image.convert("RGBA")
        if self.resize_var.get():
            width = self._safe_positive_int(self.width_var.get())
            height = self._safe_positive_int(self.height_var.get())
            if width is None or height is None:
                raise ValueError("widthとheightには1以上の整数を入力してください。")
            source = source.resize((width, height), Image.Resampling.LANCZOS)
        else:
            source = source.copy()

        if self.auto_margin_var.get():
            threshold = self._validate_threshold(preview=preview)
            padding = self._validate_padding(preview=preview)
            source = self._auto_adjust_margins(source, rows, cols, threshold, padding, preview=preview)
        else:
            source = self._trim_to_grid(source, rows, cols, keep_square=self.square_var.get())

        return source

    def _set_preview_image(
        self,
        image: Image.Image,
        widget: tk.Canvas,
        slot: str,
        rows: Optional[int],
        cols: Optional[int],
    ) -> None:
        """Scale a preview image onto a canvas and optionally overlay the split grid."""
        preview = image.copy()
        preview.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
        canvas_width, canvas_height = PREVIEW_MAX_SIZE
        offset_x = (canvas_width - preview.width) // 2
        offset_y = (canvas_height - preview.height) // 2

        photo = ImageTk.PhotoImage(preview)
        if slot == "before":
            self.preview_photo_before = photo
            self.before_preview_scale = preview.width / image.width if image.width else 1.0
            self.before_preview_offset = (offset_x, offset_y)
            self.before_preview_size = preview.size
        else:
            self.preview_photo_after = photo

        widget.configure(width=canvas_width, height=canvas_height)
        widget.delete("all")
        widget.create_image(offset_x, offset_y, image=photo, anchor="nw")

        if self.show_grid_var.get() and rows and cols:
            self._draw_grid_on_canvas(widget, (offset_x, offset_y), preview.size, rows, cols)

    def _draw_grid_on_canvas(
        self, canvas: tk.Canvas, offset: tuple[int, int], size: tuple[int, int], rows: int, cols: int
    ) -> None:
        """Draw a non-editable red grid over a preview canvas."""
        offset_x, offset_y = offset
        width, height = size
        right = offset_x + width
        bottom = offset_y + height
        line_color = "#ff0000"
        for col in range(1, cols):
            x = offset_x + round(width * col / cols)
            canvas.create_line(x, offset_y, x, bottom, fill=line_color, width=2)
        for row in range(1, rows):
            y = offset_y + round(height * row / rows)
            canvas.create_line(offset_x, y, right, y, fill=line_color, width=2)

    def _auto_adjust_margins(
        self,
        image: Image.Image,
        rows: int,
        cols: int,
        threshold: int,
        padding: int,
        preview: bool = False,
    ) -> Image.Image:
        """Detect content bounds, rebuild an even-margin canvas, and make it grid-safe."""
        mode = self._resolve_detection_mode(image)
        bbox = self._find_content_bbox(image, mode, threshold)
        if bbox is None:
            if not preview:
                self.log("有効ピクセルが見つからないため、余白調整をスキップしました。")
            return self._trim_to_grid(image, rows, cols, keep_square=self.square_var.get())

        left, top, right, bottom = bbox
        content_width = right - left
        content_height = bottom - top
        target_width = content_width + padding * 2
        target_height = content_height + padding * 2

        if self.square_var.get():
            side = max(target_width, target_height)
            target_width = side
            target_height = side

        if self.center_var.get():
            center_x = (left + right) / 2
            center_y = (top + bottom) / 2
            crop_left = round(center_x - target_width / 2)
            crop_top = round(center_y - target_height / 2)
        else:
            crop_left = left - padding
            crop_top = top - padding

        crop_box = (crop_left, crop_top, crop_left + target_width, crop_top + target_height)
        adjusted = self._crop_with_padding(image, crop_box, self._padding_fill(image, mode))
        return self._trim_to_grid(adjusted, rows, cols, keep_square=self.square_var.get())

    def _resolve_detection_mode(self, image: Image.Image) -> str:
        """Choose alpha or brightness content detection according to the selected mode."""
        selected = self.detection_mode_var.get()
        if selected in {"alpha", "brightness"}:
            return selected

        alpha = image.getchannel("A")
        extrema = alpha.getextrema()
        return "alpha" if extrema[0] < 255 else "brightness"

    def _find_content_bbox(self, image: Image.Image, mode: str, threshold: int) -> Optional[tuple[int, int, int, int]]:
        """Return the bounding box of pixels considered content."""
        if mode == "alpha":
            mask = image.getchannel("A").point(lambda alpha: 255 if alpha > 0 else 0)
            return mask.getbbox()

        rgb = image.convert("RGB")
        alpha = image.getchannel("A")
        brightness = rgb.convert("L", matrix=(0.299, 0.587, 0.114, 0))
        bright_mask = brightness.point(lambda value: 255 if value >= threshold else 0)
        alpha_mask = alpha.point(lambda value: 255 if value > 0 else 0)
        return ImageChops.multiply(bright_mask, alpha_mask).getbbox()

    def _crop_with_padding(
        self, image: Image.Image, box: tuple[int, int, int, int], fill: tuple[int, int, int, int]
    ) -> Image.Image:
        """Crop an RGBA image, padding areas outside the source rectangle with the requested fill."""
        left, top, right, bottom = box
        width = right - left
        height = bottom - top
        result = Image.new("RGBA", (width, height), fill)

        source_left = max(0, left)
        source_top = max(0, top)
        source_right = min(image.width, right)
        source_bottom = min(image.height, bottom)
        if source_left >= source_right or source_top >= source_bottom:
            return result

        cropped = image.crop((source_left, source_top, source_right, source_bottom))
        result.paste(cropped, (source_left - left, source_top - top))
        return result

    def _padding_fill(self, image: Image.Image, mode: str) -> tuple[int, int, int, int]:
        """Use transparent padding for alpha assets and black padding for opaque brightness-mode assets."""
        alpha_extrema = image.getchannel("A").getextrema()
        if mode == "brightness" and alpha_extrema == (255, 255):
            return (0, 0, 0, 255)
        return (0, 0, 0, 0)

    def _trim_to_grid(self, image: Image.Image, rows: int, cols: int, keep_square: bool = False) -> Image.Image:
        """Centrally trim or minimally pad the image so dimensions divide by rows and columns."""
        if keep_square:
            side = max(image.width, image.height)
            multiple = math.lcm(rows, cols)
            target_side = self._largest_divisible_size(side, multiple)
            if target_side < min(image.width, image.height):
                target_side = self._smallest_divisible_size(side, multiple)
            squared = self._center_crop_or_pad(image, target_side, target_side, self._edge_fill(image))
            return squared

        target_width = self._largest_divisible_size(image.width, cols)
        target_height = self._largest_divisible_size(image.height, rows)
        return self._center_crop_or_pad(image, target_width, target_height, self._edge_fill(image))

    def _center_crop_or_pad(
        self, image: Image.Image, target_width: int, target_height: int, fill: tuple[int, int, int, int]
    ) -> Image.Image:
        """Return a centered crop or padded canvas of the requested size."""
        left = round((image.width - target_width) / 2)
        top = round((image.height - target_height) / 2)
        return self._crop_with_padding(image, (left, top, left + target_width, top + target_height), fill)

    @staticmethod
    def _largest_divisible_size(size: int, divisor: int) -> int:
        """Return the largest positive size not greater than size that is divisible by divisor."""
        trimmed = size - (size % divisor)
        return trimmed if trimmed > 0 else divisor

    @staticmethod
    def _smallest_divisible_size(size: int, divisor: int) -> int:
        """Return the smallest size not less than size that is divisible by divisor."""
        return ((size + divisor - 1) // divisor) * divisor

    @staticmethod
    def _edge_fill(image: Image.Image) -> tuple[int, int, int, int]:
        """Pick a safe padding fill that preserves transparent PNGs and opaque black-background assets."""
        alpha_extrema = image.getchannel("A").getextrema()
        return (0, 0, 0, 0) if alpha_extrema[0] < 255 else (0, 0, 0, 255)

    def _validate_threshold(self, preview: bool = False) -> int:
        """Validate brightness threshold; preview falls back to the default while typing."""
        try:
            threshold = int(self.threshold_var.get())
        except ValueError as exc:
            if preview:
                return 15
            raise ValueError("thresholdには0〜255の整数を入力してください。") from exc
        if not 0 <= threshold <= 255:
            if preview:
                return 15
            raise ValueError("thresholdには0〜255の整数を入力してください。")
        return threshold

    def _validate_padding(self, preview: bool = False) -> int:
        """Validate padding; preview falls back to zero while typing."""
        try:
            padding = int(self.padding_var.get())
        except ValueError as exc:
            if preview:
                return 0
            raise ValueError("paddingには0以上の整数を入力してください。") from exc
        if padding < 0:
            if preview:
                return 0
            raise ValueError("paddingには0以上の整数を入力してください。")
        return padding

    def _on_resize_mode_changed(self) -> None:
        """Enable or disable resize entries to match the selected mode."""
        state = "normal" if self.resize_var.get() else "disabled"
        self.width_entry.configure(state=state)
        self.height_entry.configure(state=state)
        self.update_preview()

    def _draw_grid(self, draw: ImageDraw.ImageDraw, size: tuple[int, int], rows: int, cols: int) -> None:
        """Draw red grid lines over the preview image."""
        width, height = size
        line_color = (255, 0, 0, 220)
        line_width = 2

        for col in range(1, cols):
            x = round(width * col / cols)
            draw.line((x, 0, x, height), fill=line_color, width=line_width)
        for row in range(1, rows):
            y = round(height * row / rows)
            draw.line((0, y, width, y), fill=line_color, width=line_width)

    def _validate_positive_int(self, value: str, field_name: str) -> Optional[int]:
        """Validate a positive integer field and show an error if invalid."""
        result = self._safe_positive_int(value)
        if result is None:
            self._show_error(f"{field_name}が不正", f"{field_name}には1以上の整数を入力してください。")
        return result

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
    app = ImageSplitterApp(root)
    app._on_resize_mode_changed()
    root.mainloop()


if __name__ == "__main__":
    main()
