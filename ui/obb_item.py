import math
from PyQt5.QtWidgets import QGraphicsPolygonItem, QGraphicsEllipseItem, QGraphicsLineItem
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QPolygonF, QBrush

HANDLE_SIZE = 8

class OBBHandle(QGraphicsEllipseItem):
    def __init__(self, handle_type, parent):
        super().__init__(-HANDLE_SIZE/2, -HANDLE_SIZE/2, HANDLE_SIZE, HANDLE_SIZE, parent)
        self.handle_type = handle_type # 'tl', 'tr', 'br', 'bl', 'rotate'
        self.parent_obb = parent
        self.setBrush(Qt.white)
        self.setPen(QPen(Qt.black, 1))
        self.setZValue(10)
        self.setAcceptHoverEvents(True)
        
        if handle_type == 'rotate':
            self.setBrush(Qt.green)
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def hoverEnterEvent(self, event):
        self.setBrush(Qt.yellow)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(Qt.green if self.handle_type == 'rotate' else Qt.white)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self._drag_start_pos = self.mapToScene(event.pos())
        self.parent_obb.start_drag(self.handle_type, self._drag_start_pos)
        event.accept()

    def mouseMoveEvent(self, event):
        current_pos = self.mapToScene(event.pos())
        self.parent_obb.do_drag(self.handle_type, current_pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.parent_obb.end_drag()
        event.accept()

class OBBItem(QGraphicsPolygonItem):
    def __init__(self, center: QPointF, width: float, height: float, angle: float, bbox_data):
        super().__init__()
        self.bbox_data = bbox_data
        self.image_rect = None
        
        self.cx = center.x()
        self.cy = center.y()
        self.w = width
        self.h = height
        self.angle = angle # degrees
        
        self.setFlags(QGraphicsPolygonItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        
        self._update_color(selected=False)
        
        self.handles = {}
        for ht in ['tl', 'tr', 'br', 'bl', 'rotate']:
            self.handles[ht] = OBBHandle(ht, self)
            
        self.rotate_line = QGraphicsLineItem(self)
        self.rotate_line.setPen(QPen(Qt.green, 1, Qt.DashLine))
        
        self._is_dragging = False
        self._update_geometry()

    def _update_color(self, selected: bool):
        color = Qt.magenta if selected else Qt.green
        self.setPen(QPen(color, 2))
        self.setBrush(QBrush(Qt.transparent))

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
            QPointF(-hw, -hh), # tl
            QPointF(hw, -hh),  # tr
            QPointF(hw, hh),   # br
            QPointF(-hw, hh)   # bl
        ]
        
        self.corners = []
        for p in lc:
            rx = p.x() * cos_a - p.y() * sin_a
            ry = p.x() * sin_a + p.y() * cos_a
            self.corners.append(QPointF(self.cx + rx, self.cy + ry))
            
        poly = QPolygonF(self.corners)
        self.setPolygon(poly)
        
        # Update handles
        self.handles['tl'].setPos(self.corners[0])
        self.handles['tr'].setPos(self.corners[1])
        self.handles['br'].setPos(self.corners[2])
        self.handles['bl'].setPos(self.corners[3])
        
        # Rotate handle (above top edge)
        top_center_x = (self.corners[0].x() + self.corners[1].x()) / 2
        top_center_y = (self.corners[0].y() + self.corners[1].y()) / 2
        
        rot_dist = 30
        rot_x = top_center_x + sin_a * rot_dist
        rot_y = top_center_y - cos_a * rot_dist
        rot_pos = QPointF(rot_x, rot_y)
        
        self.handles['rotate'].setPos(rot_pos)
        self.rotate_line.setLine(QLineF(QPointF(top_center_x, top_center_y), rot_pos))
        
        self._sync_to_yolo()

    def start_drag(self, handle_type, pos):
        self._drag_start_cx = self.cx
        self._drag_start_cy = self.cy
        self._drag_start_w = self.w
        self._drag_start_h = self.h
        self._drag_start_angle = self.angle
        self._drag_start_pos = pos

    def do_drag(self, handle_type, pos):
        if handle_type == 'rotate':
            dx = pos.x() - self.cx
            dy = pos.y() - self.cy
            angle_rad = math.atan2(dy, dx)
            self.angle = math.degrees(angle_rad) + 90
        else:
            # Resizing from corners
            rad = math.radians(-self.angle)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            
            dx = pos.x() - self._drag_start_cx
            dy = pos.y() - self._drag_start_cy
            
            local_x = dx * cos_a - dy * sin_a
            local_y = dx * sin_a + dy * cos_a
            
            MIN_SIZE = 10
            
            w0 = self._drag_start_w
            h0 = self._drag_start_h
            
            if handle_type == 'br':
                lx = max(-w0/2 + MIN_SIZE, local_x)
                ly = max(-h0/2 + MIN_SIZE, local_y)
                new_w = lx + w0/2
                new_h = ly + h0/2
                shift_local_x = (-w0/2 + lx) / 2
                shift_local_y = (-h0/2 + ly) / 2
            elif handle_type == 'tl':
                lx = min(w0/2 - MIN_SIZE, local_x)
                ly = min(h0/2 - MIN_SIZE, local_y)
                new_w = w0/2 - lx
                new_h = h0/2 - ly
                shift_local_x = (lx + w0/2) / 2
                shift_local_y = (ly + h0/2) / 2
            elif handle_type == 'tr':
                lx = max(-w0/2 + MIN_SIZE, local_x)
                ly = min(h0/2 - MIN_SIZE, local_y)
                new_w = lx + w0/2
                new_h = h0/2 - ly
                shift_local_x = (-w0/2 + lx) / 2
                shift_local_y = (ly + h0/2) / 2
            elif handle_type == 'bl':
                lx = min(w0/2 - MIN_SIZE, local_x)
                ly = max(-h0/2 + MIN_SIZE, local_y)
                new_w = w0/2 - lx
                new_h = ly + h0/2
                shift_local_x = (lx + w0/2) / 2
                shift_local_y = (-h0/2 + ly) / 2
                
            self.w = new_w
            self.h = new_h
            
            rad_f = math.radians(self.angle)
            cos_f = math.cos(rad_f)
            sin_f = math.sin(rad_f)
            
            shift_x = shift_local_x * cos_f - shift_local_y * sin_f
            shift_y = shift_local_x * sin_f + shift_local_y * cos_f
            
            self.cx = self._drag_start_cx + shift_x
            self.cy = self._drag_start_cy + shift_y
            
        self._update_geometry()

    def end_drag(self):
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = self.mapToScene(event.pos())
            self._drag_start_cx = self.cx
            self._drag_start_cy = self.cy
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            current_pos = self.mapToScene(event.pos())
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
        
        pts = []
        for p in self.corners:
            nx = (p.x() - img.left()) / iw
            ny = (p.y() - img.top()) / ih
            pts.append((nx, ny))
        self.bbox_data.points = pts

    def set_image_rect(self, image_rect):
        self.image_rect = image_rect
        self._sync_to_yolo()
