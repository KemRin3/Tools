"""Desktop GUI tool for splitting one image into a rows x columns grid.

External dependency: Pillow
"""

from __future__ import annotations

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
        self.root.minsize(860, 620)

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

        ttk.Label(preview_frame, text="処理前").grid(row=0, column=0, sticky="ew")
        ttk.Label(preview_frame, text="処理後").grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.preview_before_label = ttk.Label(preview_frame, text="画像を選択すると表示します", anchor="center")
        self.preview_before_label.grid(row=1, column=0, sticky="nsew")
        self.preview_after_label = ttk.Label(preview_frame, text="画像を選択すると表示します", anchor="center")
        self.preview_after_label.grid(row=1, column=1, sticky="nsew", padx=(8, 0))

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
        self._set_preview_image(before, self.preview_before_label, "before", rows, cols)

        try:
            after = self._prepare_source_image(rows=rows, cols=cols, preview=True) if rows and cols else before.copy()
        except (ValueError, OSError):
            after = before.copy()
        self._set_preview_image(after, self.preview_after_label, "after", rows, cols)

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
            source = self._prepare_source_image(rows=rows, cols=cols)
        except ValueError as exc:
            self._show_error("設定が不正", str(exc))
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
        label: ttk.Label,
        slot: str,
        rows: Optional[int],
        cols: Optional[int],
    ) -> None:
        """Scale a preview image and optionally overlay the split grid."""
        preview = image.copy()
        preview.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
        if self.show_grid_var.get() and rows and cols:
            draw = ImageDraw.Draw(preview)
            self._draw_grid(draw, preview.size, rows, cols)

        photo = ImageTk.PhotoImage(preview)
        if slot == "before":
            self.preview_photo_before = photo
        else:
            self.preview_photo_after = photo
        label.configure(image=photo, text="")

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
