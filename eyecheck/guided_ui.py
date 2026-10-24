"""Fullscreen target-local instructions; no moving cursor or camera preview."""

TARGETS = {"center": (.5, .5), "left": (.15, .5), "right": (.85, .5),
           "up": (.5, .18), "down": (.5, .82)}


def target_for(name):
    return TARGETS.get(name, TARGETS["center"])


def target_rect(width, height, target):
    """Keep the instruction card on screen, in logical Qt coordinates."""
    w, h = min(280, int(width * .28)), min(220, int(height * .3))
    x = max(0, min(width - w, round(width * target[0] - w / 2)))
    y = max(0, min(height - h, round(height * target[1] - h / 2)))
    return x, y, w, h


def display_text(phase, offset):
    if phase.name in ("left", "right", "up", "down"):
        instruction = "Look HERE.\nKeep your head still."
    elif phase.name.startswith("center") or phase.name == "final_center":
        instruction = "Look HERE.\nKeep eyes naturally open."
    else:
        instruction = phase.instruction
    section = phase.window(offset)
    state = {"settling": "Get ready - samples excluded",
             "measuring": "Measuring - keep holding",
             "trailing": "Keep holding - samples excluded"}[section]
    return f"+\n{instruction}\n\n{state}\n{max(0, phase.seconds - offset):.1f}s until next cue"


def create_view(app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QFontMetrics, QShortcut, QKeySequence
    from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout

    class GuidedView(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Eyecheck - LIVE fixation validation - Escape to stop")
            self.setStyleSheet("background-color: #20242a; color: #f4f4f4;")
            self.target = TARGETS["center"]
            self.card = QWidget(self)
            layout = QVBoxLayout(self.card)
            layout.setContentsMargins(0, 0, 0, 0)
            self.prompt = QLabel()
            self.prompt.setFont(QFont("Sans Serif", 11))
            self.prompt.setAlignment(Qt.AlignCenter)
            self.prompt.setWordWrap(True)
            layout.addWidget(self.prompt)
            self.escape = QShortcut(QKeySequence("Escape"), self)
            self.escape.activated.connect(self.close)
            self.set_warmup()
            self.showFullScreen()
            app.processEvents()
            self.place()

        def place(self):
            rect = target_rect(self.width(), self.height(), self.target)
            self.card.setGeometry(*rect)
            # Fit wrapped text at smaller desktop sizes without clipping a cue.
            for size in (11, 10, 9, 8):
                font = QFont("Sans Serif", size)
                self.prompt.setFont(font)
                bounds = QFontMetrics(font).boundingRect(
                    0, 0, rect[2], rect[3], Qt.AlignCenter | Qt.TextWordWrap, self.prompt.text())
                if bounds.height() <= rect[3]:
                    break

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self.place()

        def set_warmup(self):
            self.prompt.setText("LIVE camera warmup\nFollow text as it moves.\nHold each pose until the next cue.\nClosures/face loss: count FOUR seconds, then return.\nEscape stops the test.")

        def show_phase(self, phase, offset, stale=False):
            self.target = target_for(phase.name)
            self.prompt.setText(display_text(phase, offset) +
                                ("\nCamera stale - samples unavailable" if stale else ""))
            self.place()

        def metadata(self):
            screen = self.screen()
            rect = screen.geometry()
            return {"mode": "fullscreen_target_local_text_no_preview",
                    "window_logical_size": [self.width(), self.height()],
                    "screen_name": screen.name(),
                    "screen_logical_geometry": [rect.x(), rect.y(), rect.width(), rect.height()],
                    "device_pixel_ratio": screen.devicePixelRatio(),
                    "target_centers_normalized": TARGETS,
                    "target_cards_logical": {k: target_rect(self.width(), self.height(), v)
                                             for k, v in TARGETS.items()},
                    "note": "Text occupies a small area around each target, not an exact gaze ground-truth point."}

    return GuidedView()
