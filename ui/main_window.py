from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QListWidget, QMessageBox,
    QAction, QDockWidget, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout, QListWidgetItem, QSpinBox, QLabel, QDialog
)
from PyQt5.QtCore import QRectF, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont
from pathlib import Path

from ui.image_view import ImageView
from ui.bbox_item import BBoxItem
from core.label_manager import LabelManager
from core.bbox import BBox
from core.yolo_io import load_yolo_txt, save_yolo_txt
from utils.image_loader import load_image

class MainWindow(QMainWindow):

    item_selected = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLOTxtMaker")

        self.image_view = ImageView()
        self.setCentralWidget(self.image_view)

        self.label_manager = LabelManager()
        self.current_image_path = None
        self.current_folder_path = None
        self.image_list = []  # 文件夹中的图片列表
        self.current_image_index = 0
        self.save_folder_path = None  # 保存路径
        self.bbox_items = {}

        self._create_right_panel()
        self._create_menu()
        self.image_view.bbox_selected.connect(self.on_graphics_selected)
        self.item_selected.connect(self.on_list_selected)

    def _create_right_panel(self):
        dock = QDockWidget('BBoxs', self)
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 保存路径显示
        self.save_path_label = QLabel("保存路径: 未选择")
        self.save_path_label.setWordWrap(True)
        layout.addWidget(self.save_path_label)
        
        btn_set_save_path = QPushButton("设置保存路径")
        btn_set_save_path.clicked.connect(self.set_save_folder)
        layout.addWidget(btn_set_save_path)

        # 图片导航
        nav_layout = QHBoxLayout()
        btn_prev = QPushButton("上一张")
        btn_next = QPushButton("下一张")
        self.img_counter_label = QLabel("0/0")
        btn_prev.clicked.connect(self.show_prev_image)
        btn_next.clicked.connect(self.show_next_image)
        nav_layout.addWidget(btn_prev)
        nav_layout.addWidget(self.img_counter_label)
        nav_layout.addWidget(btn_next)
        layout.addLayout(nav_layout)

        # 缩放控制
        zoom_layout = QHBoxLayout()
        btn_fit_view = QPushButton("适应视图")
        btn_fit_view.clicked.connect(self.fit_image_to_view)
        zoom_layout.addWidget(btn_fit_view)
        layout.addLayout(zoom_layout)

        # BBox列表
        self.bbox_list = QListWidget()
        self.bbox_list.itemClicked.connect(self.on_list_selected)
        layout.addWidget(QLabel("BBox列表:"))
        layout.addWidget(self.bbox_list)

        # BBox操作按钮
        bbox_btn_layout = QHBoxLayout()
        btn_add = QPushButton("新添")
        btn_del = QPushButton("删除")
        btn_add.clicked.connect(self.add_bbox)
        btn_del.clicked.connect(self.delete_bbox)
        bbox_btn_layout.addWidget(btn_add)
        bbox_btn_layout.addWidget(btn_del)
        layout.addLayout(bbox_btn_layout)

        # class_id编辑
        class_layout = QHBoxLayout()
        class_layout.addWidget(QLabel("Class ID:"))
        self.class_id_spinbox = QSpinBox()
        self.class_id_spinbox.setMinimum(0)
        self.class_id_spinbox.setMaximum(999)
        self.class_id_spinbox.valueChanged.connect(self.on_class_id_changed)
        class_layout.addWidget(self.class_id_spinbox)
        layout.addLayout(class_layout)

        # 保存按钮
        btn_save = QPushButton("保存 YOLO txt")
        btn_save.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        btn_save.clicked.connect(self.save_txt)
        layout.addWidget(btn_save)

        layout.addStretch()

        dock.setWidget(panel)
        self.addDockWidget(0x2, dock)

    def _create_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("文件")

        open_img = QAction("打开单张图片", self)
        open_img.triggered.connect(self.open_image)
        file_menu.addAction(open_img)

        open_folder = QAction("打开文件夹", self)
        open_folder.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder)

    def set_save_folder(self):
        """设置保存路径"""
        folder = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if folder:
            self.save_folder_path = Path(folder)
            self.save_path_label.setText(f"保存路径: {self.save_folder_path}")

    def open_image(self):
        """打开单张图片"""
        if not self.save_folder_path:
            QMessageBox.warning(self, "警告", "请先点击右侧'设置保存路径'按钮选择保存目录！")
            return
        
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images(*.jpg *.png *.jpeg *.bmp)")
        if not path:
            return
        
        self.current_image_path = Path(path)
        self.current_folder_path = None
        self.image_list = []
        self.current_image_index = 0
        self._load_image(self.current_image_path)
        self._update_nav_label()

    def open_folder(self):
        """打开文件夹"""
        if not self.save_folder_path:
            QMessageBox.warning(self, "警告", "请先点击右侧'设置保存路径'按钮选择保存目录！")
            return
        
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder:
            return
        
        # 获取所有图片文件
        folder_path = Path(folder)
        image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        self.image_list = sorted([f for f in folder_path.iterdir() 
                                   if f.suffix.lower() in image_exts])
        
        if not self.image_list:
            QMessageBox.warning(self, "警告", "文件夹中没有图片！")
            return
        
        self.current_folder_path = folder_path
        self.current_image_index = 0
        self._load_image(self.image_list[0])
        self._update_nav_label()

    def _load_image(self, image_path: Path):
        """加载图片及其标注"""
        # 防守性检查
        if not self.save_folder_path:
            QMessageBox.critical(self, "错误", "保存路径未设置！")
            return
        
        if not image_path.exists():
            QMessageBox.warning(self, "错误", f"图片文件不存在: {image_path}")
            return
        
        try:
            self.current_image_path = image_path
            pixmap = load_image(self.current_image_path)
            self.image_view.load_pixmap(pixmap)

            # 根据保存路径加载txt
            txt_path = self.save_folder_path / image_path.with_suffix(".txt").name
            self.label_manager.bboxes = load_yolo_txt(txt_path)
            
            # 清空图形项并重新添加
            self.image_view.scene.clear()
            pixmap_item = self.image_view.scene.addPixmap(pixmap)
            pixmap_item.setZValue(-1)  # 确保图片在最下层
            self.bbox_items = {}
            
            # 图像矩形（以像素为单位）
            img_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
            
            # 重建所有BBox图形项
            for bbox in self.label_manager.bboxes:
                # 从YOLO归一化坐标转换回像素坐标
                # YOLO格式: x_center, y_center, width, height (都是0-1的相对坐标)
                pixel_x_center = bbox.x_center * img_rect.width()
                pixel_y_center = bbox.y_center * img_rect.height()
                pixel_w = bbox.width * img_rect.width()
                pixel_h = bbox.height * img_rect.height()
                
                # 计算左上角坐标
                x = pixel_x_center - pixel_w / 2
                y = pixel_y_center - pixel_h / 2
                
                # 使用正确的Qt坐标系统：rect从(0,0)开始，位置由setPos()确定
                rect = QRectF(0, 0, pixel_w, pixel_h)  # 本地坐标从(0,0)开始
                item = BBoxItem(rect, bbox)
                item.setPos(x, y)  # scene坐标中的位置
                item.set_image_rect(img_rect)
                self.image_view.scene.addItem(item)
                self.bbox_items[bbox.id] = item
            
            self.refresh_bbox_list()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片失败: {str(e)}")

    def _update_nav_label(self):
        """更新导航标签"""
        if self.image_list:
            total = len(self.image_list)
            current = self.current_image_index + 1
            self.img_counter_label.setText(f"{current}/{total}")
        else:
            self.img_counter_label.setText("0/0")

    def show_prev_image(self):
        """显示上一张图片"""
        if not self.image_list:
            QMessageBox.information(self, "提示", "请先打开文件夹")
            return
        
        # 保存当前图片
        self.save_txt()
        
        self.current_image_index = (self.current_image_index - 1) % len(self.image_list)
        self._load_image(self.image_list[self.current_image_index])
        self._update_nav_label()

    def show_next_image(self):
        """显示下一张图片"""
        if not self.image_list:
            QMessageBox.information(self, "提示", "请先打开文件夹")
            return
        
        # 保存当前图片
        self.save_txt()
        
        self.current_image_index = (self.current_image_index + 1) % len(self.image_list)
        self._load_image(self.image_list[self.current_image_index])
        self._update_nav_label()

    def save_txt(self):
        """保存YOLO txt文件"""
        if not self.current_image_path or not self.save_folder_path:
            return
        
        try:
            txt_path = self.save_folder_path / self.current_image_path.with_suffix(".txt").name
            save_yolo_txt(txt_path, self.label_manager.bboxes)
            # 显示保存成功提示
            self._show_save_success_toast()
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存txt文件失败: {str(e)}")
    
    def _show_save_success_toast(self):
        """显示保存成功的淡出提示"""
        # 创建临时提示标签
        toast = QLabel("✓ 保存成功")
        toast.setFont(QFont("Arial", 12, QFont.Bold))
        toast.setStyleSheet(
            "background-color: #4CAF50; "
            "color: white; "
            "padding: 10px 20px; "
            "border-radius: 5px; "
            "border: none;"
        )
        toast.setParent(self)
        toast.adjustSize()
        
        # 将提示放在窗口右下角
        geometry = self.geometry()
        toast.move(
            geometry.width() - toast.width() - 20,
            geometry.height() - toast.height() - 60
        )
        toast.show()
        
        # 1秒后自动删除
        def fade_out():
            toast.deleteLater()
        
        QTimer.singleShot(1000, fade_out)

    def fit_image_to_view(self):
        """将图像适应到视图"""
        self.image_view.fit_to_view()

    def refresh_bbox_list(self):
        """刷新BBox列表显示"""
        self.bbox_list.clear()
        for bbox in self.label_manager.bboxes:
            # 显示 ID、ClassID、坐标信息
            text = f"ID{bbox.id} | Class: {bbox.class_id}"
            self.bbox_list.addItem(text)



    # BBox操作
    def add_bbox(self):
        """添加新的BBox"""
        if not self.current_image_path:
            QMessageBox.warning(self, "提示", "请先打开图片")
            return
        
        # 获取当前图像的大小
        pixmap_items = [item for item in self.image_view.scene.items() 
                        if type(item).__name__ == 'QGraphicsPixmapItem']
        if pixmap_items:
            pixmap = pixmap_items[0].pixmap()
            img_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        else:
            img_rect = QRectF(0, 0, 640, 480)  # 默认尺寸
        
        # 创建新的BBox，位置在图像中心，大小为图像的20%
        img_w = img_rect.width()
        img_h = img_rect.height()
        box_w = img_w * 0.2  # 宽度为图像20%
        box_h = img_h * 0.2  # 高度为图像20%
        x = (img_w - box_w) / 2  # 水平居中
        y = (img_h - box_h) / 2  # 垂直居中
        
        bbox_id = len(self.label_manager.bboxes)
        bbox = BBox(bbox_id, 0, 0.5, 0.5, 0.2, 0.2)
        self.label_manager.add(bbox)

        # 使用正确的Qt坐标系统：rect从(0,0)开始，位置由pos()确定
        rect = QRectF(0, 0, box_w, box_h)  # 本地坐标从(0,0)开始
        item = BBoxItem(rect, bbox)
        item.setPos(x, y)  # 在scene坐标中的位置
        item.set_image_rect(img_rect)  # 重要：设置image_rect以启用坐标同步和边界检查
        self.image_view.scene.addItem(item)
        self.bbox_items[bbox_id] = item

        self.refresh_bbox_list()

    def delete_bbox(self):
        """删除选中的BBox"""
        item = self.bbox_list.currentItem()
        if not item:
            return
        
        row = self.bbox_list.row(item)
        if row < 0 or row >= len(self.label_manager.bboxes):
            return
        
        bbox = self.label_manager.bboxes[row]
        bbox_id = bbox.id
        
        # 移除图形项
        if bbox_id in self.bbox_items:
            gfx_item = self.bbox_items[bbox_id]
            self.image_view.scene.removeItem(gfx_item)
            del self.bbox_items[bbox_id]

        # 移除数据
        self.label_manager.remove(bbox_id)
        self.refresh_bbox_list()

    def on_class_id_changed(self, value):
        """Class ID被改变时"""
        item = self.bbox_list.currentItem()
        if not item:
            return
        
        row = self.bbox_list.row(item)
        if row < 0 or row >= len(self.label_manager.bboxes):
            return
        
        # 更新BBox的class_id
        self.label_manager.bboxes[row].class_id = value
        self.refresh_bbox_list()

    def on_graphics_selected(self, bbox_item):
        """图形项被选中时"""
        # 取消所有图形项的选中状态
        for gfx_item in self.bbox_items.values():
            if gfx_item != bbox_item:
                gfx_item.setSelected(False)
        
        # 更新列表选项
        for i in range(self.bbox_list.count()):
            item = self.bbox_list.item(i)
            # 找到对应的bbox_item
            bbox = self.label_manager.bboxes[i]
            is_match = self.bbox_items[bbox.id] == bbox_item
            item.setSelected(is_match)
            
            if is_match:
                # 更新class_id spinbox
                self.class_id_spinbox.blockSignals(True)
                self.class_id_spinbox.setValue(bbox.class_id)
                self.class_id_spinbox.blockSignals(False)

    def on_list_selected(self, item):
        """列表项被选中时"""
        row = self.bbox_list.row(item)
        if row < 0 or row >= len(self.label_manager.bboxes):
            return
        
        bbox = self.label_manager.bboxes[row]
        bbox_id = bbox.id
        
        if bbox_id not in self.bbox_items:
            return
        
        gfx_item = self.bbox_items[bbox_id]
        
        # 清空场景中所有其他选中项
        self.image_view.scene.clearSelection()
        
        # 选中当前bbox图形项
        gfx_item.setSelected(True)
        
        # 更新class_id spinbox
        self.class_id_spinbox.blockSignals(True)
        self.class_id_spinbox.setValue(bbox.class_id)
        self.class_id_spinbox.blockSignals(False)

