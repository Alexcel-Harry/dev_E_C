"""Pilot collection UI. Images are used only for the setup preview in memory."""
import time

READING = (
    "A small notebook can change the way a walk feels. On an ordinary morning, a person might pass the same gate, tree and bus stop without noticing anything new. With a notebook in a pocket, those familiar places become questions. How many leaves have changed colour? Which window catches the first light? Does the street sound different after rain? There is no need to answer every question. The point is simply to notice.\n\n"
    "One page might contain a quick drawing of a bench. Another might describe a conversation heard at a distance, without recording anyone's words. A third might list the colours of doors along a quiet street. None of these observations needs to become a finished story. They can remain small records of attention. Some days there may be only a date and a sentence about the weather.\n\n"
    "After several weeks, patterns begin to appear. The same delivery bicycle arrives near the corner shop at a similar time. A tree loses its leaves unevenly, starting on the side that faces the road. The park is busiest on afternoons when the clouds break before sunset. The notes are incomplete, but they make it easier to remember how a place changes. Read at your normal pace, blink naturally, and use the arrow keys for another page when you wish.",
    "A library is full of different kinds of time. Some books describe events that lasted a few seconds. Others follow a family across several generations. The reader moves between those scales simply by turning a page. A shelf can place a recent account of a city beside a map printed long before its newest roads existed.\n\n"
    "Behind the public shelves are many ordinary routines. Returned books need to be checked and placed in order. A damaged cover may need repair. A noticeboard needs new dates. Someone adjusts a chair, helps a visitor find a reference, or makes room for a small group meeting. These tasks are easy to overlook, but together they make the building useful.\n\n"
    "There is also a particular pleasure in finding something unexpected. A reader looking for a guide to local birds may notice a book about rivers on the next shelf. That book may lead to a history of bridges, and then to a collection of photographs. The original question has not disappeared; it has become part of a larger set of interests. A good afternoon does not always end with a complete answer. Sometimes it ends with a better question and a note about where to look next.",
    "Making a simple meal involves many small decisions. A cook chooses which vegetables to cut first, how much room to leave in a pan, and when to start warming a plate. An experienced cook may make these decisions without much thought. Someone learning the same recipe may pause at each step and read the instructions again. Both approaches can produce a satisfying meal.\n\n"
    "Recipes are useful because they preserve a sequence that has worked before. They are also incomplete descriptions. A tomato may contain more water than expected. A small pan may heat differently from a large one. The written time is therefore a starting point for observation. Colour, texture and smell help the cook decide what should happen next.\n\n"
    "Shared meals carry their own routines. One person sets out cups while another clears a space on the table. Conversation pauses when a hot dish arrives, then resumes in a different direction. Afterwards, the remaining food is put away and the dishes are washed. The meal itself may be brief, but the preparation and clearing form a larger pattern around it. If you have finished all three pages, return to the first and continue reading naturally until the collection interval ends."
)


def create_view(app, protocol, settings, action):
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
    from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QComboBox

    class CollectionView(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Eyecheck collection — Escape stops")
            self.setStyleSheet("background: #20242a; color: #f4f4f4; font-size: 16px;")
            self.page = 0
            self.protocol = protocol
            self.ready = False
            self.notice = "Opening camera and local landmark model…"
            self.panel = QWidget(self)
            layout = QVBoxLayout(self.panel)
            self.heading = QLabel()
            self.heading.setWordWrap(True)
            layout.addWidget(self.heading)
            self.preview = QLabel()
            self.preview.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.preview)
            self.choice = QComboBox()
            layout.addWidget(self.choice)
            self.continue_button = QPushButton("Continue / Space")
            self.continue_button.clicked.connect(self.advance)
            layout.addWidget(self.continue_button)
            self.repeat_button = QPushButton("Repeat this item / R")
            self.repeat_button.clicked.connect(self.repeat)
            layout.addWidget(self.repeat_button)
            self.stop_button = QPushButton("Stop and save incomplete / Escape")
            self.stop_button.clicked.connect(self.close)
            layout.addWidget(self.stop_button)
            self.shortcuts = []
            for key, callback in (("Escape", self.close), ("Space", self.advance),
                                  ("P", lambda: self.control("pause")), ("R", self.repeat),
                                  ("Right", lambda: self.turn_page(1)), ("Left", lambda: self.turn_page(-1))):
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.activated.connect(callback)
                self.shortcuts.append(shortcut)
            self.last_version = -1
            self.showFullScreen()

        def advance(self):
            if protocol.state == "complete":
                self.close()
            elif protocol.state != "setup" or self.ready:
                self.control("advance", self.choice.currentData() if self.choice.isVisible() else None)

        def control(self, kind, value=None):
            action(kind, value)
            self.refresh()  # hide menu before a newly requested target can receive a paint ack

        def repeat(self):
            self.control("repeat", self.choice.currentData() if self.choice.isVisible() else None)

        def turn_page(self, delta):
            if protocol.step.role == "negative_reading" and protocol.state == "measure":
                self.page = (self.page + delta) % len(READING)
                protocol.event("reading_page", time.monotonic(), page=self.page)
                self.update()

        def set_preview(self, rgb, ready, notice):
            self.ready, self.notice = ready, notice
            if protocol.state == "setup":
                height, width = rgb.shape[:2]
                image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()
                self.preview.setPixmap(QPixmap.fromImage(image).scaled(560, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        def refresh(self):
            menu = protocol.state not in ("prepare", "measure")
            if menu:
                self.unsetCursor()
            else:
                self.setCursor(Qt.BlankCursor)
            self.panel.setVisible(menu)
            self.preview.setVisible(protocol.state == "setup")
            if protocol.state != "setup":
                self.preview.clear()
            needs_confirmation = protocol.state == "review" and protocol.step.role in ("gesture_trial", "gesture_reference", "negative_reading")
            self.choice.setVisible(needs_confirmation)
            if self.last_version != protocol.version:
                self.choice.clear()
                self.choice.addItem("Select what you actually did…", None)
                if needs_confirmation:
                    options = (["S", "SS", "SSS", "L", "SL", "LL", "uncertain", "failed"] if protocol.step.role == "gesture_trial"
                               else ["open", "closed", "uncertain", "failed"] if protocol.step.role == "gesture_reference"
                               else ["no_command", "commands_present", "uncertain"])
                    for value in options:
                        self.choice.addItem(value.replace("_", " "), value)
                self.last_version = protocol.version
            if protocol.state == "setup":
                self.heading.setText("PILOT — numeric observations only; no mouse input or image saving.\n"
                    f"Lighting: {settings['lighting']} | distance: {settings['distance_cm']} cm\n"
                    f"Glasses/setup: {settings['notes']}\n"
                    "Check face and both eyes in the preview. Keep this setup for the session.\n"
                    "First: top-left → top-right → bottom-right → bottom-left; then center and gaze targets.\n"
                    "Every item begins with 2 seconds preparation. P pauses; Escape stops.\n" + self.notice)
                self.continue_button.setEnabled(self.ready)
            else:
                self.heading.setText("Session collection finished. No model training or mouse control was run." if protocol.completed else protocol.message)
                self.continue_button.setEnabled(True)
            self.continue_button.setText("Close" if protocol.completed else "Continue / Space")
            self.repeat_button.setVisible(protocol.state in ("review", "retry"))
            self.stop_button.setVisible(not protocol.completed)
            width = min(700, self.width() - 60)
            self.panel.setFixedWidth(width)
            self.panel.adjustSize()
            self.panel.move((self.width() - width)//2, max(10, (self.height()-self.panel.height())//2))
            self.update()

        def metadata(self):
            screen = self.screen()
            rect = screen.geometry()
            x, y = protocol.step.target
            return {"window_logical_size": [self.width(), self.height()], "screen_name": screen.name(),
                    "screen_logical_geometry": [rect.x(), rect.y(), rect.width(), rect.height()],
                    "device_pixel_ratio": screen.devicePixelRatio(),
                    "target_window_logical": [x*self.width(), y*self.height()],
                    "target_screen_logical": [rect.x()+x*self.width(), rect.y()+y*self.height()],
                    "coordinate_note": "Qt logical coordinates, normalized by fullscreen window; no DPR multiplier applied."}

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#20242a"))
            if protocol.state in ("prepare", "measure"):
                step = protocol.step
                elapsed = 0 if protocol.phase_start is None else time.monotonic()-protocol.phase_start
                duration = 2 if protocol.state == "prepare" else (4 if step.role == "calibration_anchor" else step.seconds)
                if step.role == "negative_reading" and protocol.state == "measure":
                    painter.setPen(QColor("#f4f4f4"))
                    painter.setFont(QFont("Sans Serif", 15))
                    painter.drawText(QRectF(70, 45, self.width()-140, 55), Qt.AlignLeft,
                                     f"Read normally — no intentional commands. ← / → page {self.page+1}/3. P pauses; Escape stops.")
                    painter.drawText(QRectF(70, 120, self.width()-140, self.height()-150), Qt.TextWordWrap, READING[self.page])
                else:
                    x, y = step.target[0]*self.width(), step.target[1]*self.height()
                    colour = QColor("#f6bd60" if protocol.state == "prepare" else "#7bdcb5")
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setPen(QPen(colour, 3))
                    painter.drawArc(QRectF(x-24, y-24, 48, 48), 90*16, -int(360*16*max(0, 1-elapsed/duration)))
                    painter.setBrush(colour)
                    painter.drawEllipse(QRectF(x-3, y-3, 6, 6))
                    instruction = "Focus on the small dot"
                    if step.role == "gesture_trial":
                        instruction = f"{step.label}: short ≈ 0.5s, long ≈ 1.5s.\nBlinks separated by comfortable reopening; finish eyes open."
                    elif step.role == "gesture_reference":
                        instruction = "Keep eyes naturally open" if step.label == "open" else "Close both eyes comfortably during RECORD, then reopen"
                    elif step.role == "negative_reading":
                        instruction = "Prepare to read naturally; no intentional commands"
                    state = "GET READY" if protocol.state == "prepare" else "RECORD"
                    controls = "P pause · " + ("R repeat · " if step.role == "gaze_target" else "") + "Esc stop"
                    text = f"{state} · {max(0, duration-elapsed):.1f}s\n{instruction}\n{protocol.index+1} / {len(protocol.steps)} · {controls}"
                    w, h = min(410, self.width()-30), 125
                    left = max(15, min(self.width()-w-15, x-w/2))
                    top = y+33 if y < self.height()/2 else y-h-33
                    painter.setFont(QFont("Sans Serif", 11))
                    painter.drawText(QRectF(left, max(5, top), w, h), Qt.AlignCenter | Qt.TextWordWrap, text)
            painter.end()
            if not self.panel.isVisible():
                start_record = protocol.pending_paint and protocol.state == "measure"
                protocol.painted(protocol.version, time.monotonic(), self.metadata())
                if start_record:
                    app.beep()

    return CollectionView()
