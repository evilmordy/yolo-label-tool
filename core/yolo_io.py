from pathlib import Path
from core.bbox import BBox

STATUS_UNLABELED = "unlabeled"
STATUS_BACKGROUND = "background"
STATUS_LABELED = "labeled"


def read_label_file_status(txt_path: Path) -> str:
    """labeled = non-empty txt, background = empty txt, unlabeled = no txt."""
    try:
        if not txt_path.is_file():
            return STATUS_UNLABELED
        if txt_path.stat().st_size > 0:
            return STATUS_LABELED
    except OSError:
        return STATUS_UNLABELED
    return STATUS_BACKGROUND


def annotation_signature(bboxes) -> tuple:
    """Immutable snapshot of annotation content, ignoring bbox ids."""
    rows = []
    for bbox in bboxes:
        if bbox.type == "rect":
            rows.append((
                "rect",
                int(bbox.class_id),
                float(bbox.x_center),
                float(bbox.y_center),
                float(bbox.width),
                float(bbox.height),
            ))
        else:
            points = tuple(
                (float(px), float(py)) for px, py in (bbox.points or [])
            )
            rows.append((bbox.type, int(bbox.class_id), points))
    return tuple(rows)


def _is_polygon_row(num_parts: int) -> bool:
    return num_parts >= 7 and (num_parts - 1) % 2 == 0 and num_parts != 9


def load_yolo_txt(txt_path: Path):
    bboxes = []

    if not txt_path.exists():
        return bboxes

    with open(txt_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            parts = line.strip().split()
            if not parts:
                continue
            if len(parts) == 5:
                class_id, x, y, w, h = parts
                bboxes.append(
                    BBox(
                        id=idx,
                        class_id=int(class_id),
                        type='rect',
                        x_center=float(x),
                        y_center=float(y),
                        width=float(w),
                        height=float(h),
                    )
                )
            elif len(parts) == 9:
                class_id = int(parts[0])
                points = [(float(parts[i]), float(parts[i + 1])) for i in range(1, 9, 2)]
                bboxes.append(
                    BBox(
                        id=idx,
                        class_id=class_id,
                        type='obb',
                        points=points,
                    )
                )
            elif _is_polygon_row(len(parts)):
                class_id = int(parts[0])
                points = [(float(parts[i]), float(parts[i + 1])) for i in range(1, len(parts), 2)]
                bboxes.append(
                    BBox(
                        id=idx,
                        class_id=class_id,
                        type='polygon',
                        points=points,
                    )
                )

    return bboxes


def save_yolo_txt(txt_path: Path, bboxes):
    with open(txt_path, "w", encoding='utf-8') as f:
        for bbox in bboxes:
            if bbox.type == 'rect':
                x = max(0.0, min(1.0, bbox.x_center))
                y = max(0.0, min(1.0, bbox.y_center))
                w = max(0.0, min(1.0, bbox.width))
                h = max(0.0, min(1.0, bbox.height))
                line = f"{bbox.class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n"
                f.write(line)
            elif bbox.type == 'obb':
                pts = []
                for px, py in bbox.points:
                    pts.append(f"{max(0.0, min(1.0, px)):.6f} {max(0.0, min(1.0, py)):.6f}")
                line = f"{bbox.class_id} {' '.join(pts)}\n"
                f.write(line)
            elif bbox.type == 'polygon':
                pts = []
                for px, py in bbox.points:
                    pts.append(f"{max(0.0, min(1.0, px)):.6f} {max(0.0, min(1.0, py)):.6f}")
                line = f"{bbox.class_id} {' '.join(pts)}\n"
                f.write(line)
