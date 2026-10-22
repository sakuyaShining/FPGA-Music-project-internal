"""Two-octave chromatic piano, with stable note IDs for the existing session."""
from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtWidgets import QWidget, QPushButton

# The first eight IDs remain compatible with existing tests and diagnostics.
OFFSETS = (0, 2, 4, 7, 9, 12, 14, 16)
OFFSETS += tuple(n for n in range(25) if n not in OFFSETS)
INDEX = {offset: index for index, offset in enumerate(OFFSETS)}
BLACK = {1, 3, 6, 8, 10}
NAMES = ('C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B')
LOWER = 'ZSXDCVGBHNJM,L.;/'
UPPER = 'Q2W3ER5T6Y7UI'
BINDINGS = {ord(key): INDEX[offset] for offset, key in enumerate(LOWER)}
BINDINGS.update({ord(key): INDEX[offset+12] for offset, key in enumerate(UPPER)})
LABELS = {INDEX[offset]: key for offset, key in enumerate(LOWER)}
LABELS.update({INDEX[offset+12]: key for offset, key in enumerate(UPPER)})


def note_name(midi):
    return NAMES[midi % 12] + str(midi // 12 - 1)


class PianoKeyboard(QWidget):
    note_pressed = pyqtSignal(int)
    note_released = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.setMaximumHeight(135)
        self.base = 60
        self.mouse_note = None
        self.buttons = []
        for index, offset in enumerate(OFFSETS):
            button = QPushButton(self)
            button.setFocusPolicy(Qt.NoFocus)
            button.setMouseTracking(True)
            button.installEventFilter(self)
            black = offset % 12 in BLACK
            button.setStyleSheet(
                'QPushButton {background:#202b38;color:#fff;border:1px solid #111a24;'
                'border-radius:0px;border-bottom-left-radius:4px;border-bottom-right-radius:4px;padding:0px;font-size:10pt;}'
                'QPushButton:pressed {background:#b63e26;color:#fff;}' if black else
                'QPushButton {background:#fffdf7;color:#222;border:1px solid #b7b0a5;'
                'border-radius:0px;border-bottom-left-radius:4px;border-bottom-right-radius:4px;padding:0px;padding-top:50px;font-size:10pt;}'
                'QPushButton:pressed {background:#f1a184;color:#222;}')
            self.buttons.append(button)
        self.set_base(60)

    def set_base(self, midi):
        self.base = midi
        for index, offset in enumerate(OFFSETS):
            button = self.buttons[index]
            aliases = [chr(key) for key, value in BINDINGS.items() if value == index]
            button.setText('%s\n%s' % (LABELS[index], note_name(midi+offset)))
            button.setToolTip('%s · MIDI %d · 电脑键 %s' % (note_name(midi+offset), midi+offset, ' / '.join(aliases)))

    def resizeEvent(self, event):
        white_offsets = [n for n in range(25) if n % 12 not in BLACK]
        unit = self.width() / len(white_offsets)
        for column, offset in enumerate(white_offsets):
            self.buttons[INDEX[offset]].setGeometry(round(column*unit), 0,
                round((column+1)*unit)-round(column*unit), self.height())
        width = max(10, round(unit*.62))
        for offset in range(25):
            if offset % 12 not in BLACK:
                continue
            boundary = sum(n < offset for n in white_offsets) * unit
            button = self.buttons[INDEX[offset]]
            button.setGeometry(round(boundary-width/2), 0, width, round(self.height()*.60))
            button.raise_()

    def _mouse_target(self, position):
        child = self.childAt(position)
        return self.buttons.index(child) if child in self.buttons else None

    def _move_mouse(self, index):
        if index == self.mouse_note:
            return
        old = self.mouse_note
        self.mouse_note = index
        if old is not None:
            self.note_released.emit(old)
        if index is not None:
            self.note_pressed.emit(index)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._move_mouse(self.buttons.index(watched))
            return True
        if kind == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
            self._move_mouse(self._mouse_target(self.mapFromGlobal(event.globalPos())))
            return True
        if kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._move_mouse(None)
            return True
        return super().eventFilter(watched, event)

    def clear_mouse(self):
        self.mouse_note = None
