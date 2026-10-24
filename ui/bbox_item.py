from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QColor

from ui.theme_manager import get_annotation_colors
from ui.graphics_utils import select_only, select_only_parent
from ui.screen_handle import ScreenHandle, event_scene_pos


class ResizeHandle(ScreenHandle):
    """
    拉伸控制点 - PPT级别的独立拖拽逻辑
    
    核心思想：
    - 完全自主处理拖拽，不依赖父项的复杂状态
    - 直接在scene坐标中计算和约束
    - 所有边界检查都在这里完成
    - 鼠标位置用 event.scenePos()。手柄忽略视图变换，mapToScene(event.pos())
      在 Windows 缩放 / 视图 fit 之后会对不上光标。
    """
    def __init__(self, position: str, parent_bbox):
        super().__init__(parent_bbox)
        self.position = position
        self.parent_bbox = parent_bbox
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["handle"]))
        self.setPen(QPen(QColor(colors["handle_border"]), 1))
        self.setCursor(self._cursor())

    def _cursor(self):
        """根据控制点位置返回相应的鼠标光标"""
        cursors = {
            "tl": Qt.SizeFDiagCursor,
            "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor,
            "bl": Qt.SizeBDiagCursor,
            "l": Qt.SizeHorCursor,
            "r": Qt.SizeHorCursor,
            "t": Qt.SizeVerCursor,
            "b": Qt.SizeVerCursor,
        }
        return cursors.get(self.position, Qt.ArrowCursor)
    
    def hoverEnterEvent(self, event):
        """鼠标进入时高亮"""
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["handle_hover"]))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """鼠标离开时恢复"""
        colors = get_annotation_colors()
        self.setBrush(QColor(colors["handle"]))
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """记录拖拽起始位置"""
        self.parent_bbox._notify_edit_start()
        select_only_parent(self.parent_bbox)
        self._press_scene = event_scene_pos(event)
        self._original_rect = self.parent_bbox.scene_box_rect()
        event.accept()
    
    def mouseMoveEvent(self, event):
        """拖拽时实时计算新矩形并约束"""
        self._apply_resize(event_scene_pos(event))
        event.accept()
    
    def mouseReleaseEvent(self, event):
        """释放鼠标"""
        event.accept()
    
    def _apply_resize(self, target_pos: QPointF):
        """
        应用拉伸操作，完全处理约束
        
        PPT逻辑：
        - 被拖拽的边/角才移动
        - 其他边保持固定
        - 所有坐标都限制在图像范围内
        - 最小尺寸为10像素
        """
        # 获取原始矩形的四条边
        orig_rect = self._original_rect
        x1 = orig_rect.left()
        y1 = orig_rect.top()
        x2 = orig_rect.right()
        y2 = orig_rect.bottom()
        
        # 用相对按下点的位移，而不是把边直接吸到光标上。
        # 命中区域比圆点大，点在圆点旁边时不能在第一下就把边跳过去。
        dx = target_pos.x() - self._press_scene.x()
        dy = target_pos.y() - self._press_scene.y()
        
        # 获取图像边界
        img = self.parent_bbox.image_rect
        if img is not None:
            img_x1 = img.left()
            img_y1 = img.top()
            img_x2 = img.right()
            img_y2 = img.bottom()
        else:
            img_x1 = img_y1 = float('-inf')
            img_x2 = img_y2 = float('inf')
        
        MIN_SIZE = 10
        
        # 根据handle位置计算新的四条边
        if self.position == "r":
            # 右边：只改x2
            x2 = orig_rect.right() + dx
            x2 = max(x2, x1 + MIN_SIZE)      # 最小宽度
            x2 = min(x2, img_x2)              # 图像右边界
            
        elif self.position == "l":
            # 左边：只改x1
            x1 = orig_rect.left() + dx
            x1 = max(x1, img_x1)              # 图像左边界
            x1 = min(x1, x2 - MIN_SIZE)       # 最小宽度
            
        elif self.position == "b":
            # 底边：只改y2
            y2 = orig_rect.bottom() + dy
            y2 = max(y2, y1 + MIN_SIZE)      # 最小高度
            y2 = min(y2, img_y2)              # 图像底边界
            
        elif self.position == "t":
            # 顶边：只改y1
            y1 = orig_rect.top() + dy
            y1 = max(y1, img_y1)              # 图像顶边界
            y1 = min(y1, y2 - MIN_SIZE)       # 最小高度
            
        elif self.position == "br":
            # 右下角：改x2和y2
            x2 = orig_rect.right() + dx
            y2 = orig_rect.bottom() + dy
            x2 = max(x2, x1 + MIN_SIZE)
            x2 = min(x2, img_x2)
            y2 = max(y2, y1 + MIN_SIZE)
            y2 = min(y2, img_y2)
            
        elif self.position == "bl":
            # 左下角：改x1和y2
            x1 = orig_rect.left() + dx
            y2 = orig_rect.bottom() + dy
            x1 = max(x1, img_x1)
            x1 = min(x1, x2 - MIN_SIZE)
            y2 = max(y2, y1 + MIN_SIZE)
            y2 = min(y2, img_y2)
            
        elif self.position == "tr":
            # 右上角：改x2和y1
            x2 = orig_rect.right() + dx
            y1 = orig_rect.top() + dy
            x2 = max(x2, x1 + MIN_SIZE)
            x2 = min(x2, img_x2)
            y1 = max(y1, img_y1)
            y1 = min(y1, y2 - MIN_SIZE)
            
        elif self.position == "tl":
            # 左上角：改x1和y1
            x1 = orig_rect.left() + dx
            y1 = orig_rect.top() + dy
            x1 = max(x1, img_x1)
            x1 = min(x1, x2 - MIN_SIZE)
            y1 = max(y1, img_y1)
            y1 = min(y1, y2 - MIN_SIZE)
        
        # 构造新矩形（scene坐标）
        new_scene_rect = QRectF(x1, y1, x2 - x1, y2 - y1)
        
        # 更新BBoxItem
        self.parent_bbox.setPos(new_scene_rect.left(), new_scene_rect.top())
        self.parent_bbox.setRect(0, 0, new_scene_rect.width(), new_scene_rect.height())
        self.parent_bbox._update_handles()
        self.parent_bbox._sync_to_yolo()


class BBoxItem(QGraphicsRectItem):
    """
    YOLO标注框 - 简化设计
    
    职责：
    - 存储bbox数据和图像范围
    - 管理8个控制点
    - 处理整体拖拽（可选）
    - 同步到YOLO格式
    
    关键：所有复杂的拉伸逻辑都在ResizeHandle中
    """

    def __init__(self, rect: QRectF, bbox_data):
        super().__init__(rect)
        
        self.bbox_data = bbox_data
        self.image_rect = None  # scene中图片的rect
        self.on_edit_start = None

        # 只允许选择，不使用内置拖拽
        self.setFlags(QGraphicsRectItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        
        # 颜色
        self._update_color(selected=False)
        
        # 创建8个控制点
        self.handles = {}
        self._create_handles()
        self._update_handles()
        
        # 整体拖拽状态
        self._is_dragging = False

    # ======================= 颜色 =======================

    def _update_color(self, selected: bool):
        colors = get_annotation_colors()
        color = QColor(colors["selected"] if selected else colors["unselected"])
        self.setPen(QPen(color, 2))

    def refresh_theme_colors(self):
        selected = self.isSelected()
        self._update_color(selected)
        for handle in self.handles.values():
            colors = get_annotation_colors()
            handle.setBrush(QColor(colors["handle"]))
            handle.setPen(QPen(QColor(colors["handle_border"]), 1))

    def setSelected(self, selected: bool):
        """重写选中"""
        super().setSelected(selected)
        self._update_color(selected)

    # ======================= 控制点 =======================

    def _create_handles(self):
        """创建8个控制点"""
        for pos in ("tl", "t", "tr", "r", "br", "b", "bl", "l"):
            self.handles[pos] = ResizeHandle(pos, self)

    def _update_handles(self):
        """更新控制点位置"""
        r = self.rect()
        cx, cy = r.center().x(), r.center().y()
        
        positions = {
            "tl": r.topLeft(),
            "t": QPointF(cx, r.top()),
            "tr": r.topRight(),
            "r": QPointF(r.right(), cy),
            "br": r.bottomRight(),
            "b": QPointF(cx, r.bottom()),
            "bl": r.bottomLeft(),
            "l": QPointF(r.left(), cy),
        }
        
        for k, p in positions.items():
            self.handles[k].setPos(p)

    # ======================= 整体拖拽（可选） =======================

    def _notify_edit_start(self):
        if self.on_edit_start:
            self.on_edit_start()

    def mousePressEvent(self, event):
        """按下鼠标开始拖拽"""
        if event.button() == Qt.LeftButton:
            self._notify_edit_start()
            select_only(self)
            self._is_dragging = True
            self._drag_start_pos = event_scene_pos(event)
            self._drag_start_rect = self.scene_box_rect()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """拖拽时移动整体bbox"""
        if self._is_dragging:
            current_pos = event_scene_pos(event)
            dx = current_pos.x() - self._drag_start_pos.x()
            dy = current_pos.y() - self._drag_start_pos.y()
            
            # 计算新位置
            new_x = self._drag_start_rect.left() + dx
            new_y = self._drag_start_rect.top() + dy
            
            # 约束到图像范围
            if self.image_rect is not None:
                img = self.image_rect
                w = self._drag_start_rect.width()
                h = self._drag_start_rect.height()
                
                # 左边界
                new_x = max(new_x, img.left())
                # 右边界
                new_x = min(new_x, img.right() - w)
                # 上边界
                new_y = max(new_y, img.top())
                # 下边界
                new_y = min(new_y, img.bottom() - h)
            
            # 更新位置
            self.setPos(new_x, new_y)
            self._update_handles()
            self._sync_to_yolo()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """释放鼠标"""
        if self._is_dragging:
            self._is_dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ======================= YOLO同步 =======================

    def scene_box_rect(self) -> QRectF:
        """框本身在 scene 中的矩形，不含控制点。"""
        return self.mapRectToScene(self.rect())

    def _sync_to_yolo(self):
        """同步到YOLO归一化坐标"""
        if self.image_rect is None:
            return

        scene_rect = self.scene_box_rect()
        img = self.image_rect
        iw, ih = img.width(), img.height()
        if iw <= 0 or ih <= 0:
            return

        # YOLO格式：中心点 + 宽高（归一化）
        self.bbox_data.x_center = (scene_rect.center().x() - img.left()) / iw
        self.bbox_data.y_center = (scene_rect.center().y() - img.top()) / ih
        self.bbox_data.width = scene_rect.width() / iw
        self.bbox_data.height = scene_rect.height() / ih

    # ======================= 外部接口 =======================

    def set_image_rect(self, image_rect: QRectF):
        """设置图像范围。只记录坐标系，不回写 YOLO（避免把控制点尺寸写进标注）。"""
        self.image_rect = image_rect
