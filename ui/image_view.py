from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt5.QtCore import QRectF, pyqtSignal, Qt
from PyQt5.QtGui import QWheelEvent

class ImageView(QGraphicsView):

    bbox_selected = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        # 缩放相关
        self.zoom_level = 1.0
        self.setDragMode(QGraphicsView.ScrollHandDrag)  # 支持空格拖拽平移
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)  # 以鼠标位置为缩放中心

    def load_pixmap(self, pixmap):
        """加载图片（可选择是否清除场景）"""
        self.scene.clear()  # 加载新图像之前先清除场景
        pixmap_item = self.scene.addPixmap(pixmap)  # 将pixmap添加到scene中
        pixmap_item.setZValue(-1)  # 确保图片在最下层
        self.setSceneRect(QRectF(pixmap.rect()))  # 设置QGraphicsView的显示区域
        
        # 自动适应视图（图片显示在视图内，不超出）
        self.fit_to_view()
    
    def load_pixmap_only(self, pixmap):
        """只加载图片，不清除现有的BBox项"""
        # 先移除旧图片
        for item in self.scene.items():
            if item.type() == 14:  # QGraphicsPixmapItem的类型ID是14
                self.scene.removeItem(item)
                break
        
        pixmap_item = self.scene.addPixmap(pixmap)
        pixmap_item.setZValue(-1)
        self.setSceneRect(QRectF(pixmap.rect()))
        
        # 自动适应视图
        self.fit_to_view()
    
    def fit_to_view(self):
        """缩放图片以适应视图"""
        self.zoom_level = 1.0
        self.resetTransform()
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        self.zoom_level = self.transform().m11()  # 获取实际的缩放比例

    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮缩放"""
        if not self.scene.items():
            return
        
        # 获取滚轮方向
        delta = event.angleDelta().y()
        
        # 设置缩放因子
        zoom_factor = 1.1 if delta > 0 else 0.9
        
        # 限制缩放范围
        new_zoom = self.zoom_level * zoom_factor
        if new_zoom < 0.2 or new_zoom > 5.0:  # 缩放范围：0.2倍 - 5倍
            return
        
        self.zoom_level = new_zoom
        self.scale(zoom_factor, zoom_factor)
        event.accept()
    
    def reset_zoom(self):
        """重置缩放（适应视图）"""
        self.fit_to_view()

    def on_selection_changed(self):
        items = self.scene.selectedItems()
        if items:
            self.bbox_selected.emit(items[0])