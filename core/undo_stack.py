import copy
from typing import List, Optional

from core.bbox import BBox

MAX_UNDO = 50


class UndoStack:
    def __init__(self, max_size: int = MAX_UNDO):
        self._stack: List[List[BBox]] = []
        self._max_size = max_size

    def clear(self):
        self._stack.clear()

    def push_snapshot(self, bboxes: List[BBox]):
        snapshot = copy.deepcopy(bboxes)
        self._stack.append(snapshot)
        if len(self._stack) > self._max_size:
            self._stack.pop(0)

    def undo(self) -> Optional[List[BBox]]:
        if not self._stack:
            return None
        return self._stack.pop()

    def can_undo(self) -> bool:
        return bool(self._stack)
