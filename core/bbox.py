from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class BBox:
    id: int
    class_id: int
    type: str = 'rect'  # 'rect' or 'obb'
    # For rect
    x_center: float = 0.0
    y_center: float = 0.0
    width: float = 0.0
    height: float = 0.0
    # For obb (4 vertices, normalized)
    points: Optional[List[Tuple[float, float]]] = None
