from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt5.QtCore import QRectF, pyqtSignal, Qt
from PyQt5.QtGui import QWheelEvent, QColor, QBrush

from ui.graphics_utils import pick_preferred_bbox_root


class ImageView(QGraphicsView):

    bbox_selected = pyqtSignal(object)  # BBox gfx item or None

    def __init__(self):
        super().__init__()
        self.setObjectName("canvasView")
        self.setBackgroundBrush(QBrush(QColor("#2d2d2d")))
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.selectionChanged.connect(self.on_selection_changed)

        self.zoom_level = 1.0
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self.drawing_mode = False
        self._draw_controller = None

    def set_draw_controller(self, controller):
        self._draw_controller = controller

    def set_drawing_mode(self, enabled: bool):
        self.drawing_mode = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setFocus()
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)

    def set_canvas_color(self, color_hex: str):
        self.setBackgroundBrush(QBrush(QColor(color_hex)))

    def load_pixmap(self, pixmap):
        """加载图片（可选择是否清除场景）"""
        self.scene.clear()
        pixmap_item = self.scene.addPixmap(pixmap)
        pixmap_item.setZValue(-1)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fit_to_view()

    def load_pixmap_only(self, pixmap):
        """只加载图片，不清除现有的BBox项"""
        for item in self.scene.items():
            if item.type() == 14:
                self.scene.removeItem(item)
                break

        pixmap_item = self.scene.addPixmap(pixmap)
        pixmap_item.setZValue(-1)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fit_to_view()

    def fit_to_view(self):
        """缩放图片以适应视图"""
        self.zoom_level = 1.0
        self.resetTransform()
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        self.zoom_level = self.transform().m11()

    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮缩放"""
        if not self.scene.items():
            return

        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9

        new_zoom = self.zoom_level * zoom_factor
        if new_zoom < 0.2 or new_zoom > 5.0:
            return

        self.zoom_level = new_zoom
        self.scale(zoom_factor, zoom_factor)
        event.accept()

    def reset_zoom(self):
        """重置缩放（适应视图）"""
        self.fit_to_view()

    def mousePressEvent(self, event):
        if self.drawing_mode and self._draw_controller and event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self._draw_controller.add_point(scene_pos)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_mode and self._draw_controller:
            scene_pos = self.mapToScene(event.pos())
            self._draw_controller.update_cursor(scene_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.drawing_mode and self._draw_controller and event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            if self._draw_controller.try_close_at(scene_pos):
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def on_selection_changed(self):
        items = self.scene.selectedItems()
        if not items:
            self.bbox_selected.emit(None)
            return
        root = pick_preferred_bbox_root(items)
        self.bbox_selected.emit(root)
