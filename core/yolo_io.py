from pathlib import Path
from core.bbox import BBox

def load_yolo_txt(txt_path: Path):
    bboxes = []

    if not txt_path.exists():
        return bboxes
    
    with open(txt_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            parts = line.strip().split()
            if len(parts) == 5:
                class_id, x, y, w, h = parts
                bboxes.append(
                    BBox(
                        id=idx,
                        class_id=int(class_id),
                        type='rect',
                        x_center=float(x),    # 中心X坐标（0-1）
                        y_center=float(y),    # 中心Y坐标（0-1）
                        width=float(w),       # 宽度（0-1）
                        height=float(h),      # 高度（0-1）
                    )
                )
            elif len(parts) == 9:
                class_id = int(parts[0])
                points = [(float(parts[i]), float(parts[i+1])) for i in range(1, 9, 2)]
                bboxes.append(
                    BBox(
                        id=idx,
                        class_id=class_id,
                        type='obb',
                        points=points
                    )
                )
    
    return bboxes

def save_yolo_txt(txt_path: Path, bboxes):
    with open(txt_path, "w", encoding='utf-8') as f:
        for bbox in bboxes:
            if bbox.type == 'rect':
                # 确保坐标严格在0-1范围内（禁止超出图像）
                x = max(0.0, min(1.0, bbox.x_center))
                y = max(0.0, min(1.0, bbox.y_center))
                w = max(0.0, min(1.0, bbox.width))
                h = max(0.0, min(1.0, bbox.height))
                
                # 写入YOLO格式：class_id x_center y_center width height
                line = f"{bbox.class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n"
                f.write(line)
            elif bbox.type == 'obb':
                pts = []
                for px, py in bbox.points:
                    pts.append(f"{max(0.0, min(1.0, px)):.6f} {max(0.0, min(1.0, py)):.6f}")
                line = f"{bbox.class_id} {' '.join(pts)}\n"
                f.write(line)
