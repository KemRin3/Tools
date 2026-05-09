"""Preset file helpers for the project builder GUI."""

from pathlib import Path
import sys


PRESET_EXTENSION = ".txt"


class PresetError(ValueError):
    """Raised when a preset name or path is invalid."""


def get_presets_dir() -> Path:
    """Return the writable presets directory next to the app or executable."""

    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent
    return app_dir / "presets"


def ensure_presets_dir(presets_dir: Path | None = None) -> Path:
    """Create and return the presets directory if it does not exist."""

    target_dir = presets_dir or get_presets_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def list_presets(presets_dir: Path | None = None) -> list[Path]:
    """Return UTF-8 DSL preset candidates from the presets directory."""

    target_dir = ensure_presets_dir(presets_dir)
    return sorted(path for path in target_dir.glob("*.txt") if path.is_file())


def load_preset(path: Path) -> str:
    """Load a preset file as UTF-8 text."""

    return path.read_text(encoding="utf-8")


def make_preset_path(name: str, presets_dir: Path | None = None) -> Path:
    """Convert a GUI preset name into a safe .txt file path."""

    clean_name = name.strip()
    if not clean_name:
        raise PresetError("Preset name is empty.")

    candidate = Path(clean_name)
    if candidate.name != clean_name or candidate.name in {".", ".."}:
        raise PresetError("Preset name must not include folders.")

    if candidate.suffix == "":
        candidate = candidate.with_suffix(PRESET_EXTENSION)

    if candidate.suffix.lower() != PRESET_EXTENSION:
        raise PresetError("Preset file extension must be .txt.")

    return ensure_presets_dir(presets_dir) / candidate.name


def save_preset(path: Path, content: str) -> None:
    """Save preset content as UTF-8 text."""

    path.write_text(content, encoding="utf-8", newline="\n")
