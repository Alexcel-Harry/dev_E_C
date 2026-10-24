"""Static chart for manual native-pointer coordinate verification."""
from .pointer import POINTS, pause


def markers(width, height):
    names = ["1 / 6: CENTER", "2: UPPER LEFT", "3: UPPER RIGHT",
             "4: LOWER RIGHT", "5: LOWER LEFT"]
    return [{"label": label, "normalized": [x, y],
             "logical_xy": [round(x * (width - 1)), round(y * (height - 1))]}
            for label, (x, y) in zip(names, POINTS[:5])]


def run(args):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainter, QColor, QPen, QFont, QShortcut, QKeySequence
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])
    result = {"schema": 1, "kind": "pointer-targets", "status": "recorded",
              "manual_coordinate_verification": "REQUIRED", "pointer_input_sent": False}

    class Chart(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Eyecheck pointer targets - Escape requests pause and closes")
            self.setCursor(Qt.ArrowCursor)
            self.shortcut = QShortcut(QKeySequence("Escape"), self)
            self.shortcut.activated.connect(self.close)

        def paintEvent(self, event):
            p = QPainter(self)
            p.fillRect(self.rect(), QColor("#20242a"))
            p.setFont(QFont("Sans Serif", 12))
            p.setPen(QPen(QColor("#7cdbff"), 2))
            for marker in markers(self.width(), self.height()):
                x, y = marker["logical_xy"]
                p.drawEllipse(x - 10, y - 10, 20, 20)
                p.drawLine(x - 16, y, x + 16, y)
                p.drawLine(x, y - 16, x, y + 16)
                p.drawText(x - 90, y + 24, 180, 45, Qt.AlignHCenter, marker["label"])
            p.setPen(QColor("#f4f4f4"))
            p.drawText(30, self.height() // 2 + 90, self.width() - 60, 130, Qt.AlignHCenter,
                       "STATIC TARGET CHART - start the pointer probe in another terminal.\n"
                       "Observe the real cursor at 1, 2, 3, 4, 5, 6. Do not move the mouse during the sequence.\n"
                       "Global pause: your configured shortcut. Escape here requests pause and closes the chart.\n"
                       "This window does not move the pointer, click, or measure cursor accuracy.")
            p.end()

        def closeEvent(self, event):
            screen = self.screen()
            rect = screen.geometry()
            result.update(window_logical_size=[self.width(), self.height()],
                          screen_name=screen.name(), device_pixel_ratio=screen.devicePixelRatio(),
                          screen_logical_geometry=[rect.x(), rect.y(), rect.width(), rect.height()],
                          markers=markers(self.width(), self.height()))
            try:
                pause()
                result["pause_requested_on_close"] = True
            except Exception as exc:
                result.update(status="error", error=str(exc), pause_requested_on_close=False)
            event.accept()

    window = Chart()
    window.showFullScreen()
    print("Static targets opened. Use another terminal to start motion; Escape here requests pause and exits.", flush=True)
    app.exec()
    return result
