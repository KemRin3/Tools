"""Data models for the project builder DSL."""

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    """Supported filesystem actions."""

    DIR = "dir"
    FILE = "file"
    WRITE = "write"


@dataclass(frozen=True)
class ProjectItem:
    """A parsed DSL item to be created by the builder."""

    action: Action
    path: str
    content: str = ""
