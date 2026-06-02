from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class BBox:
    id: int
    class_id: int
    type: str = 'rect'  # 'rect', 'obb', or 'polygon'
    # For rect
    x_center: float = 0.0
    y_center: float = 0.0
    width: float = 0.0
    height: float = 0.0
    # For obb / polygon (normalized coordinates)
    points: Optional[List[Tuple[float, float]]] = None
