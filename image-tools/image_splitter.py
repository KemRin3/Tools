"""Desktop GUI tool for splitting one image into a rows x columns grid.

External dependency: Pillow
"""

from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

from PIL import Image, ImageDraw, ImageTk, UnidentifiedImageError

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
        self.root.minsize(860, 620)

        self.image_path: Optional[Path] = None
        self.output_dir: Optional[Path] = None
        self.loaded_image: Optional[Image.Image] = None
        self.preview_photo: Optional[ImageTk.PhotoImage] = None

        self.rows_var = tk.StringVar(value="2")
        self.cols_var = tk.StringVar(value="2")
        self.resize_var = tk.BooleanVar(value=True)
        self.width_var = tk.StringVar(value="1024")
        self.height_var = tk.StringVar(value="1024")
        self.image_path_var = tk.StringVar(value="画像が選択されていません")
        self.output_dir_var = tk.StringVar(value="出力フォルダが選択されていません")

        self._build_ui()
        self._bind_events()

    def _build_ui(self) -> None:
        """Create widgets and layout."""
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        controls = ttk.Frame(self.root, padding=12)
        controls.grid(row=0, column=0, sticky="nsw")

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

        output_frame = ttk.LabelFrame(parent, text="出力フォルダ", padding=10)
        output_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        ttk.Button(output_frame, text="出力フォルダを選択", command=self.select_output_dir).grid(row=0, column=0, sticky="ew")
        ttk.Label(output_frame, textvariable=self.output_dir_var, wraplength=260).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(parent, text="分割実行", command=self.split_image).grid(row=4, column=0, sticky="ew", ipady=6)

    def _build_preview(self, parent: ttk.Frame) -> None:
        """Create the preview area."""
        preview_frame = ttk.LabelFrame(parent, text="プレビュー", padding=10)
        preview_frame.grid(row=0, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_label = ttk.Label(preview_frame, text="画像を選択するとプレビューを表示します", anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew")

    def _build_log(self, parent: ttk.Frame) -> None:
        """Create the execution log area."""
        log_frame = ttk.LabelFrame(parent, text="ログ", padding=10)
        log_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="ew")

    def _bind_events(self) -> None:
        """Refresh preview when grid settings change."""
        for variable in (self.rows_var, self.cols_var):
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

        preview = self.loaded_image.convert("RGBA").copy()
        preview.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(preview)

        rows = self._safe_positive_int(self.rows_var.get())
        cols = self._safe_positive_int(self.cols_var.get())
        if rows and cols:
            self._draw_grid(draw, preview.size, rows, cols)

        self.preview_photo = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=self.preview_photo, text="")

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

        try:
            source = self._prepare_source_image()
        except ValueError as exc:
            self._show_error("width/heightが不正", str(exc))
            return
        except OSError as exc:
            self._show_error("画像読み込み失敗", f"画像を処理できませんでした。\n{exc}")
            return

        tile_width = source.width // cols
        tile_height = source.height // rows
        if tile_width <= 0 or tile_height <= 0:
            self._show_error("分割サイズが不正", "rows/colsが画像サイズに対して大きすぎます。")
            return

        base_name = self.image_path.stem
        total = rows * cols
        digits = max(2, int(math.log10(total)) + 1 if total > 0 else 2)

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for row in range(rows):
                for col in range(cols):
                    index = row * cols + col + 1
                    left = col * tile_width
                    upper = row * tile_height
                    right = left + tile_width
                    lower = upper + tile_height
                    tile = source.crop((left, upper, right, lower))
                    tile.save(self.output_dir / f"{base_name}_{index:0{digits}d}.png", "PNG")
        except OSError as exc:
            self._show_error("出力エラー", f"PNGの保存に失敗しました。\n{exc}")
            return

        self.log(f"出力完了: {total} ファイルを保存しました ({self.output_dir})")
        messagebox.showinfo("出力完了", f"{total} ファイルを保存しました。")

    def _prepare_source_image(self) -> Image.Image:
        """Return the image to split, optionally resized."""
        if self.loaded_image is None:
            raise OSError("画像が読み込まれていません。")

        source = self.loaded_image.convert("RGBA")
        if not self.resize_var.get():
            return source.copy()

        width = self._safe_positive_int(self.width_var.get())
        height = self._safe_positive_int(self.height_var.get())
        if width is None or height is None:
            raise ValueError("widthとheightには1以上の整数を入力してください。")

        return source.resize((width, height), Image.Resampling.LANCZOS)

    def _on_resize_mode_changed(self) -> None:
        """Enable or disable resize entries to match the selected mode."""
        state = "normal" if self.resize_var.get() else "disabled"
        self.width_entry.configure(state=state)
        self.height_entry.configure(state=state)

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
