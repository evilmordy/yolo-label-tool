from typing import List

from PyQt5.QtWidgets import QGraphicsPolygonItem, QGraphicsEllipseItem, QGraphicsItem
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QPolygonF, QBrush, QColor

from ui.theme_manager import get_annotation_colors
from ui.graphics_utils import select_only, select_only_parent

HANDLE_SIZE = 8


class PolygonVertexHandle(QGraphicsEllipseItem):
    def __init__(self, vertex_index: int, parent):
        super().__init__(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, parent)
        self.vertex_index = vertex_index
        self.parent_polygon = parent
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["handle"]))
        self.setPen(QPen(QColor(colors["handle_border"]), 1))
        self.setZValue(10)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    def hoverEnterEvent(self, event):
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["handle_hover"]))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["handle"]))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.parent_polygon._notify_edit_start()
        select_only_parent(self.parent_polygon)
        event.accept()

    def mouseMoveEvent(self, event):
        current_pos = self.parent_polygon._clamp_point(self.mapToScene(event.pos()))
        self.parent_polygon._set_vertex(self.vertex_index, current_pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


class PolygonItem(QGraphicsPolygonItem):
    def __init__(self, scene_points: List[QPointF], bbox_data):
        super().__init__()
        self.bbox_data = bbox_data
        self.image_rect = None
        self.on_edit_start = None
        self.vertices = [QPointF(p) for p in scene_points]
        self.handles = []

        self.setFlags(QGraphicsPolygonItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self._is_dragging = False
        self._update_color(selected=False)
        self._rebuild_geometry()
        self._create_handles()

    def _update_color(self, selected: bool):
        colors = get_annotation_colors()
        color = QColor(colors["selected"] if selected else colors["unselected"])
        self.setPen(QPen(color, 2))
        alpha = 64 if selected else 38
        fill = QColor(color)
        fill.setAlpha(alpha)
        self.setBrush(QBrush(fill))

    def refresh_theme_colors(self):
        selected = self.isSelected()
        self._update_color(selected)
        for handle in self.handles:
            colors = get_annotation_colors()
            handle.setBrush(QColor(colors["handle"]))
            handle.setPen(QPen(QColor(colors["handle_border"]), 1))

    def setSelected(self, selected: bool):
        super().setSelected(selected)
        self._update_color(selected)

    def set_image_rect(self, image_rect):
        self.image_rect = image_rect
        self._sync_to_yolo()

    def _clamp_point(self, point: QPointF) -> QPointF:
        if self.image_rect is None:
            return point
        x = max(self.image_rect.left(), min(self.image_rect.right(), point.x()))
        y = max(self.image_rect.top(), min(self.image_rect.bottom(), point.y()))
        return QPointF(x, y)

    def _set_vertex(self, index: int, point: QPointF):
        self.vertices[index] = self._clamp_point(point)
        self._rebuild_geometry()
        self._update_handles()

    def _rebuild_geometry(self):
        self.setPolygon(QPolygonF(self.vertices))
        self._sync_to_yolo()

    def _update_handles(self):
        for i, handle in enumerate(self.handles):
            handle.setPos(self.vertices[i])

    def _create_handles(self):
        for handle in self.handles:
            handle.setParentItem(None)
            if handle.scene():
                handle.scene().removeItem(handle)
        self.handles = []
        for i in range(len(self.vertices)):
            handle = PolygonVertexHandle(i, self)
            self.handles.append(handle)
        self._update_handles()

    def _sync_to_yolo(self):
        if self.image_rect is None:
            return
        img = self.image_rect
        iw, ih = img.width(), img.height()
        if iw <= 0 or ih <= 0:
            return
        pts = []
        for p in self.vertices:
            nx = (p.x() - img.left()) / iw
            ny = (p.y() - img.top()) / ih
            pts.append((nx, ny))
        self.bbox_data.points = pts

    def _notify_edit_start(self):
        if self.on_edit_start:
            self.on_edit_start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._notify_edit_start()
            select_only(self)
            self._is_dragging = True
            self._drag_start_pos = self.mapToScene(event.pos())
            self._drag_start_vertices = [QPointF(v) for v in self.vertices]
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            current_pos = self.mapToScene(event.pos())
            dx = current_pos.x() - self._drag_start_pos.x()
            dy = current_pos.y() - self._drag_start_pos.y()
            new_vertices = []
            for v in self._drag_start_vertices:
                new_vertices.append(self._clamp_point(QPointF(v.x() + dx, v.y() + dy)))
            self.vertices = new_vertices
            self._rebuild_geometry()
            self._update_handles()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            self._is_dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    @staticmethod
    def from_bbox(bbox_data, img_rect) -> "PolygonItem":
        img_w = img_rect.width()
        img_h = img_rect.height()
        scene_points = [
            QPointF(p[0] * img_w + img_rect.left(), p[1] * img_h + img_rect.top())
            for p in bbox_data.points
        ]
        item = PolygonItem(scene_points, bbox_data)
        item.set_image_rect(img_rect)
        return item
