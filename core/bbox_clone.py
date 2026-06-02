import copy
from typing import List

from core.bbox import BBox


def clone_bboxes(bboxes: List[BBox]) -> List[BBox]:
    return copy.deepcopy(bboxes)
