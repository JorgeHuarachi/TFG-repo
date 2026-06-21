"""Snapshot based undo/redo for authoring operations."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class HistoryEntry(Generic[T]):
    label: str
    state: T


class SnapshotHistory(Generic[T]):
    """Small transactional history using ``copy.deepcopy`` snapshots."""

    def __init__(self, initial_state: T | None = None, max_entries: int = 100):
        self.max_entries = max(1, int(max_entries))
        self.undo_stack: list[HistoryEntry[T]] = []
        self.redo_stack: list[HistoryEntry[T]] = []
        if initial_state is not None:
            self.checkpoint("initial", initial_state)
            self.undo_stack.clear()

    def checkpoint(self, label: str, state: T) -> None:
        self.undo_stack.append(HistoryEntry(label=label, state=copy.deepcopy(state)))
        if len(self.undo_stack) > self.max_entries:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, current_state: T) -> T | None:
        if not self.undo_stack:
            return None
        entry = self.undo_stack.pop()
        self.redo_stack.append(HistoryEntry(label=entry.label, state=copy.deepcopy(current_state)))
        return copy.deepcopy(entry.state)

    def redo(self, current_state: T) -> T | None:
        if not self.redo_stack:
            return None
        entry = self.redo_stack.pop()
        self.undo_stack.append(HistoryEntry(label=entry.label, state=copy.deepcopy(current_state)))
        return copy.deepcopy(entry.state)

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
