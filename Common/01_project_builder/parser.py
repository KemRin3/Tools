"""Parser for the project builder DSL."""

import os
from pathlib import PurePath, PureWindowsPath

from models import Action, ProjectItem


class ParseError(ValueError):
    """Raised when DSL text is invalid."""


def parse_dsl(text: str) -> list[ProjectItem]:
    """Parse DSL text into project items.

    Supported commands:
    - dir: RELATIVE_PATH
    - file: RELATIVE_PATH
    - write: RELATIVE_PATH
      file content
      ---
    """

    items: list[ProjectItem] = []
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()
        line_number = index + 1

        if not line:
            index += 1
            continue

        if line.startswith("dir:"):
            path = _read_path(line, "dir", line_number)
            items.append(ProjectItem(Action.DIR, path))
            index += 1
            continue

        if line.startswith("file:"):
            path = _read_path(line, "file", line_number)
            items.append(ProjectItem(Action.FILE, path))
            index += 1
            continue

        if line.startswith("write:"):
            path = _read_path(line, "write", line_number)
            content_lines: list[str] = []
            index += 1

            while index < len(lines) and lines[index].strip() != "---":
                content_lines.append(lines[index])
                index += 1

            if index >= len(lines):
                raise ParseError(f"Line {line_number}: write block is missing '---'.")

            items.append(ProjectItem(Action.WRITE, path, "\n".join(content_lines)))
            index += 1
            continue

        raise ParseError(f"Line {line_number}: unknown command: {raw_line}")

    return items


def _read_path(line: str, command: str, line_number: int) -> str:
    prefix = f"{command}:"
    path = line[len(prefix) :].strip()

    if not path:
        raise ParseError(f"Line {line_number}: {command} path is empty.")

    if _is_absolute_path(path):
        raise ParseError(f"Line {line_number}: absolute paths are not allowed: {path}")

    if _contains_parent_reference(path):
        raise ParseError(
            f"Line {line_number}: parent directory references are not allowed: {path}"
        )

    return path


def _is_absolute_path(path: str) -> bool:
    windows_path = PureWindowsPath(path)
    return os.path.isabs(path) or windows_path.is_absolute() or bool(windows_path.drive)


def _contains_parent_reference(path: str) -> bool:
    return ".." in PurePath(path).parts or ".." in PureWindowsPath(path).parts
