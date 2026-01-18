from dataclasses import dataclass

@dataclass
class BBox:
    id:int
    class_id:int
    x_center: float
    y_center: float
    width: float
    height: float