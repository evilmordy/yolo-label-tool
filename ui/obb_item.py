import math
from PyQt5.QtWidgets import QGraphicsPolygonItem, QGraphicsLineItem, QGraphicsItem
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QPolygonF, QBrush, QColor

from ui.theme_manager import get_annotation_colors
from ui.graphics_utils import select_only, select_only_parent
from ui.screen_handle import ScreenHandle, event_scene_pos

# Scene-pixel gap between the top edge and the rotate handle at view scale 1.
# Left unchanged so a Linux session whose image fits near 1:1 looks the same.
ROTATE_HANDLE_DISTANCE = 30
MIN_SIZE = 10


def _wrap_angle_delta(delta):
    """Shortest signed delta, so crossing ±180° does not spin a full turn."""
    return (delta + 180.0) % 360.0 - 180.0


class OBBHandle(ScreenHandle):
    def __init__(self, handle_type, parent):
        super().__init__(parent)
        self.handle_type = handle_type  # 'tl', 'tr', 'br', 'bl', 'rotate'
        self.parent_obb = parent
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["rotate"] if handle_type == "rotate" else colors["handle"]))
        self.setPen(QPen(QColor(colors["handle_border"]), 1))

        if handle_type == "rotate":
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def hoverEnterEvent(self, event):
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["handle_hover"]))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["rotate"] if self.handle_type == "rotate" else colors["handle"]))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.parent_obb._notify_edit_start()
        select_only_parent(self.parent_obb)
        # scenePos, not mapToScene(event.pos()): see screen_handle.py.
        self.parent_obb.start_drag(self.handle_type, event_scene_pos(event))
        event.accept()

    def mouseMoveEvent(self, event):
        self.parent_obb.do_drag(self.handle_type, event_scene_pos(event))
        event.accept()

    def mouseReleaseEvent(self, event):
        self.parent_obb.end_drag()
        event.accept()


class OBBItem(QGraphicsPolygonItem):
    def __init__(self, center: QPointF, width: float, height: float, angle: float, bbox_data):
        super().__init__()
        self.bbox_data = bbox_data
        self.image_rect = None
        self.on_edit_start = None

        self.cx = center.x()
        self.cy = center.y()
        self.w = width
        self.h = height
        self.angle = angle  # degrees

        self.setFlags(QGraphicsPolygonItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self._update_color(selected=False)

        self.handles = {}
        for ht in ["tl", "tr", "br", "bl", "rotate"]:
            self.handles[ht] = OBBHandle(ht, self)

        self.rotate_line = QGraphicsLineItem(self)
        colors = get_annotation_colors()
        self.rotate_line.setPen(QPen(QColor(colors["rotate"]), 1, Qt.DashLine))
        self.rotate_line.setFlag(QGraphicsItem.ItemIsSelectable, False)

        self._is_dragging = False
        self._update_geometry()

    def _update_color(self, selected: bool):
        colors = get_annotation_colors()
        color = QColor(colors["selected"] if selected else colors["unselected"])
        self.setPen(QPen(color, 2))
        self.setBrush(QBrush(Qt.transparent))

    def refresh_theme_colors(self):
        selected = self.isSelected()
        self._update_color(selected)
        colors = get_annotation_colors()
        self.rotate_line.setPen(QPen(QColor(colors["rotate"]), 1, Qt.DashLine))
        for handle in self.handles.values():
            handle.setBrush(QColor(colors["rotate"] if handle.handle_type == "rotate" else colors["handle"]))
            handle.setPen(QPen(QColor(colors["handle_border"]), 1))

    def setSelected(self, selected: bool):
        super().setSelected(selected)
        self._update_color(selected)

    def _update_geometry(self):
        rad = math.radians(self.angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        hw = self.w / 2
        hh = self.h / 2

        # Local corners
        lc = [
            QPointF(-hw, -hh),  # tl
            QPointF(hw, -hh),  # tr
            QPointF(hw, hh),  # br
            QPointF(-hw, hh),  # bl
        ]

        self.corners = []
        for p in lc:
            rx = p.x() * cos_a - p.y() * sin_a
            ry = p.x() * sin_a + p.y() * cos_a
            self.corners.append(QPointF(self.cx + rx, self.cy + ry))

        poly = QPolygonF(self.corners)
        self.setPolygon(poly)

        self.handles["tl"].setPos(self.corners[0])
        self.handles["tr"].setPos(self.corners[1])
        self.handles["br"].setPos(self.corners[2])
        self.handles["bl"].setPos(self.corners[3])

        # Rotate handle (above top edge)
        top_center_x = (self.corners[0].x() + self.corners[1].x()) / 2
        top_center_y = (self.corners[0].y() + self.corners[1].y()) / 2

        rot_dist = ROTATE_HANDLE_DISTANCE
        rot_x = top_center_x + sin_a * rot_dist
        rot_y = top_center_y - cos_a * rot_dist
        rot_pos = QPointF(rot_x, rot_y)

        self.handles["rotate"].setPos(rot_pos)
        self.rotate_line.setLine(QLineF(QPointF(top_center_x, top_center_y), rot_pos))

        self._sync_to_yolo()

    def start_drag(self, handle_type, pos):
        self._drag_start_cx = self.cx
        self._drag_start_cy = self.cy
        self._drag_start_w = self.w
        self._drag_start_h = self.h
        self._drag_start_angle = self.angle
        self._drag_start_pos = QPointF(pos)

    def _local_of(self, pos):
        """Scene point -> box-local coordinates around the drag-start center."""
        rad = math.radians(-self._drag_start_angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        dx = pos.x() - self._drag_start_cx
        dy = pos.y() - self._drag_start_cy
        return dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a

    def do_drag(self, handle_type, pos):
        if handle_type == "rotate":
            # Delta around the center, not "point the top edge at the cursor".
            # An off-center grab (the hit pad is larger than the dot) must not
            # snap the angle on the first move.
            a0 = math.degrees(math.atan2(
                self._drag_start_pos.y() - self._drag_start_cy,
                self._drag_start_pos.x() - self._drag_start_cx,
            ))
            a1 = math.degrees(math.atan2(
                pos.y() - self._drag_start_cy,
                pos.x() - self._drag_start_cx,
            ))
            self.angle = self._drag_start_angle + _wrap_angle_delta(a1 - a0)
        else:
            lx0, ly0 = self._local_of(self._drag_start_pos)
            lx1, ly1 = self._local_of(pos)
            dlx = lx1 - lx0
            dly = ly1 - ly0
            w0 = self._drag_start_w
            h0 = self._drag_start_h

            if handle_type == "br":
                dlx = max(dlx, MIN_SIZE - w0)
                dly = max(dly, MIN_SIZE - h0)
                new_w = w0 + dlx
                new_h = h0 + dly
            elif handle_type == "tl":
                dlx = min(dlx, w0 - MIN_SIZE)
                dly = min(dly, h0 - MIN_SIZE)
                new_w = w0 - dlx
                new_h = h0 - dly
            elif handle_type == "tr":
                dlx = max(dlx, MIN_SIZE - w0)
                dly = min(dly, h0 - MIN_SIZE)
                new_w = w0 + dlx
                new_h = h0 - dly
            elif handle_type == "bl":
                dlx = min(dlx, w0 - MIN_SIZE)
                dly = max(dly, MIN_SIZE - h0)
                new_w = w0 - dlx
                new_h = h0 + dly
            else:
                return

            self.w = new_w
            self.h = new_h
            self.angle = self._drag_start_angle

            shift_local_x = dlx / 2
            shift_local_y = dly / 2
            rad_f = math.radians(self._drag_start_angle)
            cos_f = math.cos(rad_f)
            sin_f = math.sin(rad_f)
            self.cx = self._drag_start_cx + shift_local_x * cos_f - shift_local_y * sin_f
            self.cy = self._drag_start_cy + shift_local_x * sin_f + shift_local_y * cos_f

        self._update_geometry()

    def end_drag(self):
        pass

    def _notify_edit_start(self):
        if self.on_edit_start:
            self.on_edit_start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._notify_edit_start()
            select_only(self)
            self._is_dragging = True
            self._drag_start_pos = event_scene_pos(event)
            self._drag_start_cx = self.cx
            self._drag_start_cy = self.cy
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            current_pos = event_scene_pos(event)
            dx = current_pos.x() - self._drag_start_pos.x()
            dy = current_pos.y() - self._drag_start_pos.y()

            self.cx = self._drag_start_cx + dx
            self.cy = self._drag_start_cy + dy

            if self.image_rect is not None:
                self.cx = max(self.image_rect.left(), min(self.image_rect.right(), self.cx))
                self.cy = max(self.image_rect.top(), min(self.image_rect.bottom(), self.cy))

            self._update_geometry()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            self._is_dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _sync_to_yolo(self):
        if self.image_rect is None:
            return
        img = self.image_rect
        iw, ih = img.width(), img.height()
        if iw <= 0 or ih <= 0:
            return

        pts = []
        for p in self.corners:
            nx = (p.x() - img.left()) / iw
            ny = (p.y() - img.top()) / ih
            pts.append((nx, ny))
        self.bbox_data.points = pts

    def set_image_rect(self, image_rect):
        self.image_rect = image_rect
