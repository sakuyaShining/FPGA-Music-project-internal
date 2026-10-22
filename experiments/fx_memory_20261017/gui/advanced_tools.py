"""Screen-bounded developer tools; closing retains the in-memory draft."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QShortcut, QSizePolicy, QVBoxLayout, QWidget)


class DeviceStatusLabel(QLabel):
    text_changed = pyqtSignal(str)

    def setText(self, text):
        super().setText(text)
        self.text_changed.emit(text)


class AdvancedToolsDialog(QDialog):
    def __init__(self, pages, editor, apply_button, preset_button, parent=None):
        super().__init__(parent)
        self.setWindowTitle('高级工具 · 测试与开发')
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint |
                            Qt.WindowMinMaxButtonsHint)
        self.setSizeGripEnabled(True)
        self.setModal(False)
        self.pages = pages
        self.editor = editor
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel('高级工具')
        title.setObjectName('Brand')
        header.addWidget(title, 1)
        self.top_close = QPushButton('关闭')
        self.top_close.clicked.connect(self.reject)
        header.addWidget(self.top_close)
        layout.addLayout(header)
        description = QLabel('保存文件仅写入电脑；设备可应用范围以下方说明为准。')
        description.setWordWrap(True)
        description.setObjectName('Hint')
        layout.addWidget(description)
        # Every tab owns its scrollable body, including the measurement page.
        for index in range(pages.count()):
            widget = pages.widget(index)
            if not isinstance(widget, QScrollArea):
                text = pages.tabText(index)
                pages.removeTab(index)
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.NoFrame)
                scroll.setWidget(widget)
                pages.insertTab(index, scroll, text)
        pages.setMinimumSize(0, 0)
        pages.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        pages.tabBar().setExpanding(False)
        pages.tabBar().setUsesScrollButtons(True)
        layout.addWidget(pages, 1)
        self.config_actions = QWidget()
        actions = QVBoxLayout(self.config_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        self.scope = QLabel('仅应用：预设、16项泛音谱。发声方式、包络、颤音和效果器仍只保存在草稿中。')
        self.scope.setWordWrap(True)
        self.scope.setObjectName('Hint')
        actions.addWidget(self.scope)
        row = QHBoxLayout()
        self.save_button = QPushButton('保存草稿文件')
        self.save_button.clicked.connect(editor.save_document)
        self.save_button.setToolTip('保存到电脑，不改变设备声音，也不写入设备的断电存储。')
        row.addWidget(self.save_button)
        self.apply_button = apply_button
        apply_button.setText('应用预设与泛音谱')
        apply_button.setObjectName('Primary')
        apply_button.setToolTip('请先松开所有音符。仅应用预设和绘制谱，在下一次起音使用；其他草稿字段不应用。')
        row.addWidget(apply_button)
        self.preset_button = preset_button
        preset_button.setText('仅用预设')
        preset_button.setToolTip('应用草稿选中的内置预设，清除附加绘制谱；其他草稿字段不应用。')
        row.addWidget(preset_button)
        row.addStretch(1)
        actions.addLayout(row)
        layout.addWidget(self.config_actions)
        self.status = QLabel('尚未应用；保存草稿文件不会改变设备声音。')
        self.status.setObjectName('Ticker')
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        self.close_hint = QLabel('关闭仅收起窗口，保留当前草稿。')
        self.close_hint.setObjectName('Hint')
        self.close_hint.setWordWrap(True)
        footer.addWidget(self.close_hint, 1)
        self.bottom_close = QPushButton('关闭 · Esc')
        self.bottom_close.clicked.connect(self.reject)
        footer.addWidget(self.bottom_close)
        layout.addLayout(footer)
        self.shortcuts = []
        for keys, action in (('Ctrl+S', editor.save_document), ('Ctrl+Shift+S', editor.save_as),
                             ('Ctrl+O', editor.open_dialog), ('Ctrl+N', editor.new_document)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(lambda fn=action: fn() if pages.currentIndex() == 0 else None)
            self.shortcuts.append(shortcut)
        pages.currentChanged.connect(lambda index: self.config_actions.setVisible(index == 0))
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.resize(1040, 680)

    def fit_to_available(self, available=None):
        screen = self.parentWidget().screen() if self.parentWidget() else QApplication.primaryScreen()
        if available is None:
            if screen is None:
                return
            available = screen.availableGeometry()
        self.ensurePolished()
        self.layout().activate()
        frame = self.frameGeometry().size() - self.size()
        width = max(1, available.width() - max(0, frame.width()) - 24)
        height = max(1, available.height() - max(0, frame.height()) - 24)
        self.setMinimumSize(min(560, width), min(320, height))
        self.resize(min(1040, width), min(680, height))
        frame_rect = self.frameGeometry()
        frame_rect.moveCenter(available.center())
        self.move(frame_rect.topLeft())

    def open_tools(self):
        self.config_actions.setVisible(self.pages.currentIndex() == 0)
        self.show()
        self.fit_to_available()
        self.raise_()
        self.activateWindow()
