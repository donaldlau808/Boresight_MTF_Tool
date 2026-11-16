from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QApplication
from PySide6.QtGui import QPixmap, QImage, QPen, QColor, QPainter
from PySide6.QtCore import Qt, Signal, QRectF

class ResizableImageLabel(QGraphicsView):
    """Upgraded image viewer supporting Ctrl+Scroll zoom and drag panning."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #555;")
        self.zoom_factor = 1.0
        self.current_pixmap = None

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
        """Safely clears the image and aggressively forces the viewport to redraw as blank."""
        self.current_pixmap = None
        self.pixmap_item.setPixmap(QPixmap()) 
        self.scene.setSceneRect(QRectF(0, 0, 1, 1))
        self.viewport().update()

    def wheelEvent(self, event):
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor
            
            if event.angleDelta().y() > 0:
                zoom_multiplier = zoom_in_factor
                self.zoom_factor *= zoom_in_factor
            else:
                zoom_multiplier = zoom_out_factor
                self.zoom_factor *= zoom_out_factor
                
            self.scale(zoom_multiplier, zoom_multiplier)
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event):
        if self.current_pixmap and self.zoom_factor == 1.0:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        super().resizeEvent(event)


class ClickableLabel(ResizableImageLabel):
    """Upgraded interactive viewer with markup, coordinate extraction, and drag-and-drop."""
    coordinate_clicked = Signal(str, int, int)
    image_dropped = Signal(str, str) # Emits: channel_name, file_path

    def __init__(self, channel_name, parent=None):
        super().__init__(parent)
        self.channel_name = channel_name
        self.clicked_pt = None
        self.crosshair_lines = []
        
        # Enable Drag and Drop
        self.setAcceptDrops(True)

    def set_image(self, image_path):
        super().set_image(image_path)
        self.clear_markup()

    def clear_markup(self):
        self.clicked_pt = None
        for line in self.crosshair_lines:
            self.scene.removeItem(line)
        self.crosshair_lines.clear()

    # --- DRAG AND DROP EVENTS ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)
            
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    # Verify it is an image file
                    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')):
                        self.image_dropped.emit(self.channel_name, file_path)
                        break # Only process the first image if they drag multiple

    # --- MOUSE EVENTS ---
    def mousePressEvent(self, event):
        if self.dragMode() == QGraphicsView.ScrollHandDrag and event.button() == Qt.LeftButton and QApplication.keyboardModifiers() != Qt.ControlModifier:
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
        
        pen = QPen(Qt.red, max(1, int(2 / self.zoom_factor)))
        w, h = self.current_pixmap.width(), self.current_pixmap.height()
        
        h_line = self.scene.addLine(0, cy, w, cy, pen)
        v_line = self.scene.addLine(cx, 0, cx, h, pen)
        circle = self.scene.addEllipse(cx - 10, cy - 10, 20, 20, pen)
        
        self.crosshair_lines.extend([h_line, v_line, circle])