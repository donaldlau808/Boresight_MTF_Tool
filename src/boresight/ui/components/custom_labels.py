import os
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QApplication
from PySide6.QtGui import QPixmap, QImage, QPen, QColor, QPainter
from PySide6.QtCore import Qt, Signal, QRectF

class ResizableImageLabel(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setStyleSheet("background-color: #F0F0F0; border: 1px solid #C0C0C0;")
        self.zoom_factor = 1.0
        self.current_pixmap = None
        self.placeholder_text = ""

    def set_image(self, image_path):
        img = QImage(image_path)
        if not img.isNull():
            pixmap = QPixmap.fromImage(img)
            self.current_pixmap = pixmap
            self.pixmap_item.setPixmap(pixmap)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.zoom_factor = 1.0
            self.viewport().update()
        else:
            self.clear_image()

    def clear_image(self):
        self.current_pixmap = None
        self.pixmap_item.setPixmap(QPixmap()) 
        self.scene.setSceneRect(QRectF(0, 0, 1, 1))
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.current_pixmap is None and self.placeholder_text:
            painter = QPainter(self.viewport())
            painter.setPen(QColor("#888888"))
            font = painter.font()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, self.placeholder_text)
            painter.end()

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        
        if event.angleDelta().y() > 0:
            zoom_multiplier = zoom_in_factor
            self.zoom_factor *= zoom_in_factor
        else:
            zoom_multiplier = zoom_out_factor
            self.zoom_factor *= zoom_out_factor
            
        self.scale(zoom_multiplier, zoom_multiplier)
        event.accept()

    def resizeEvent(self, event):
        if self.current_pixmap and self.zoom_factor == 1.0:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        super().resizeEvent(event)


class ClickableLabel(ResizableImageLabel):
    coordinate_clicked = Signal(str, int, int)
    image_dropped = Signal(str, str)

    def __init__(self, channel_name, parent=None):
        super().__init__(parent)
        self.channel_name = channel_name
        self.placeholder_text = f"Drag and drop {channel_name} image"
        self.clicked_pt = None
        self.crosshair_lines = []
        self.setAcceptDrops(True)

    def set_image(self, image_path):
        super().set_image(image_path)
        self.clear_markup()

    def clear_markup(self):
        self.clicked_pt = None
        for line in self.crosshair_lines:
            self.scene.removeItem(line)
        self.crosshair_lines.clear()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
            
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            for url in urls:
                if url.isLocalFile():
                    file_path = os.path.normpath(url.toLocalFile())
                    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')):
                        event.acceptProposedAction()
                        self.image_dropped.emit(self.channel_name, file_path)
                        break 

    def mousePressEvent(self, event):
        if self.dragMode() == QGraphicsView.ScrollHandDrag and event.button() == Qt.LeftButton and QApplication.keyboardModifiers() == Qt.ControlModifier:
            scene_pos = self.mapToScene(event.pos())
            if self.current_pixmap and self.pixmap_item.contains(scene_pos):
                raw_x, raw_y = int(scene_pos.x()), int(scene_pos.y())
                self.clicked_pt = (raw_x, raw_y)
                self.coordinate_clicked.emit(self.channel_name, raw_x, raw_y)
                self.draw_markup(raw_x, raw_y)
        super().mousePressEvent(event)

    def draw_markup(self, cx, cy):
        for line in self.crosshair_lines:
            self.scene.removeItem(line)
        self.crosshair_lines.clear()
        
        pen = QPen(Qt.red, 1)
        pen.setCosmetic(True)
        w, h = self.current_pixmap.width(), self.current_pixmap.height()
        
        h_line = self.scene.addLine(0, cy, w, cy, pen)
        v_line = self.scene.addLine(cx, 0, cx, h, pen)
        circle = self.scene.addEllipse(cx - 10, cy - 10, 20, 20, pen)
        
        self.crosshair_lines.extend([h_line, v_line, circle])
