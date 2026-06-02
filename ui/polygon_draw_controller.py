from PyQt5.QtCore import QObject, pyqtSignal, QPointF, Qt
from PyQt5.QtGui import QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsPathItem

CLOSE_THRESHOLD = 12.0
MIN_VERTICES = 3


class PolygonDrawController(QObject):
    finished = pyqtSignal(list)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.scene = None
        self.image_rect = None
        self.points = []
        self.preview_item = None
        self.active = False
        self._cursor_pos = None

    def start(self, scene, image_rect):
        self.cancel()
        self.scene = scene
        self.image_rect = image_rect
        self.points = []
        self.active = True
        self._cursor_pos = None
        self.preview_item = QGraphicsPathItem()
        self.preview_item.setZValue(20)
        pen = QPen(QColor("#0ea5e9"), 2, Qt.DashLine)
        self.preview_item.setPen(pen)
        self.scene.addItem(self.preview_item)

    def is_active(self):
        return self.active

    def _clamp(self, point: QPointF) -> QPointF:
        if self.image_rect is None:
            return point
        x = max(self.image_rect.left(), min(self.image_rect.right(), point.x()))
        y = max(self.image_rect.top(), min(self.image_rect.bottom(), point.y()))
        return QPointF(x, y)

    def add_point(self, scene_pos: QPointF):
        if not self.active:
            return
        self.points.append(self._clamp(scene_pos))
        self._update_preview()

    def remove_last_point(self) -> bool:
        if not self.active or not self.points:
            return False
        self.points.pop()
        self._update_preview()
        return True

    def update_cursor(self, scene_pos: QPointF):
        if not self.active:
            return
        self._cursor_pos = self._clamp(scene_pos)
        self._update_preview()

    def try_close_at(self, scene_pos: QPointF) -> bool:
        if not self.active or len(self.points) < MIN_VERTICES:
            return False
        first = self.points[0]
        dx = scene_pos.x() - first.x()
        dy = scene_pos.y() - first.y()
        if (dx * dx + dy * dy) ** 0.5 <= CLOSE_THRESHOLD:
            self.finish()
            return True
        return False

    def finish(self):
        if not self.active or len(self.points) < MIN_VERTICES:
            return
        result = list(self.points)
        self._cleanup()
        self.finished.emit(result)

    def cancel(self):
        was_active = self.active
        self._cleanup()
        if was_active:
            self.cancelled.emit()

    def _cleanup(self):
        if self.preview_item is not None and self.scene is not None:
            self.scene.removeItem(self.preview_item)
        self.preview_item = None
        self.points = []
        self._cursor_pos = None
        self.active = False

    def _update_preview(self):
        if self.preview_item is None:
            return
        path = QPainterPath()
        if not self.points:
            self.preview_item.setPath(path)
            return
        path.moveTo(self.points[0])
        for pt in self.points[1:]:
            path.lineTo(pt)
        if self._cursor_pos is not None:
            path.lineTo(self._cursor_pos)
        self.preview_item.setPath(path)
