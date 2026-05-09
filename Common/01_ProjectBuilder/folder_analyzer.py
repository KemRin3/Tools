"""Convert an existing folder tree into ProjectBuilder DSL."""

from pathlib import Path
import stat


EXCLUDED_DIR_NAMES = {"__pycache__", "logs", ".git"}


def folder_to_dsl(target_dir: str | Path) -> str:
    """Return DSL lines for the contents under target_dir.

    The target folder itself is not emitted. Hidden files/directories,
    __pycache__, logs, and .git folders are excluded.
    """

    root = Path(target_dir)
    lines: list[str] = []

    for path in _iter_visible_paths(root):
        relative_path = path.relative_to(root).as_posix()
        if path.is_dir():
            lines.append(f"dir:{relative_path}/")
        elif path.is_file():
            lines.append(f"file:{relative_path}")

    return "\n".join(lines)


def _iter_visible_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for child in sorted(root.iterdir(), key=_sort_key):
        if _is_excluded(child):
            continue
        paths.append(child)
        if child.is_dir():
            paths.extend(_iter_visible_paths(child))
    return paths


def _is_excluded(path: Path) -> bool:
    name = path.name
    if name.startswith("."):
        return True
    if _is_windows_hidden(path):
        return True
    if path.is_dir() and name.lower() in EXCLUDED_DIR_NAMES:
        return True
    return False


def _is_windows_hidden(path: Path) -> bool:
    hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0)
    if not hidden_flag:
        return False
    file_attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(file_attributes & hidden_flag)


def _sort_key(path: Path) -> tuple[int, str]:
    return (0 if path.is_dir() else 1, path.name.lower())
