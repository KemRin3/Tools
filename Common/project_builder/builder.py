"""Filesystem builder for parsed project DSL items."""

from pathlib import Path

from models import Action, ProjectItem


class ProjectBuilder:
    """Create directories and files from parsed project items."""

    def __init__(self) -> None:
        self.logs: list[str] = []

    def build(self, items: list[ProjectItem]) -> list[str]:
        """Build all items and return creation logs."""

        self.logs = []
        for item in items:
            self._build_item(item)
        return self.logs

    def _build_item(self, item: ProjectItem) -> None:
        path = Path(item.path)

        if path.exists():
            self._log(f"SKIP exists: {path}")
            return

        if item.action == Action.DIR:
            path.mkdir(parents=True, exist_ok=False)
            self._log(f"CREATE dir: {path}")
            return

        if item.action == Action.FILE:
            self._create_parent(path)
            path.touch(exist_ok=False)
            self._log(f"CREATE file: {path}")
            return

        if item.action == Action.WRITE:
            self._create_parent(path)
            path.write_text(item.content, encoding="utf-8", newline="\n")
            self._log(f"WRITE file: {path}")
            return

        self._log(f"SKIP unknown action: {item.action} {path}")

    def _create_parent(self, path: Path) -> None:
        parent = path.parent
        if parent.exists():
            return
        parent.mkdir(parents=True, exist_ok=False)
        self._log(f"CREATE dir: {parent}")

    def _log(self, message: str) -> None:
        self.logs.append(message)
