"""Regression for off-screen close/apply controls, without opening serial ports."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QPA_FONTDIR', 'C:/Windows/Fonts')
import tempfile
import unittest
from unittest.mock import patch
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QScrollArea
from serial_link import SimLink
from workbench import WorkbenchWindow


class AdvancedToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.w = WorkbenchWindow(self.temp.name + '/preferences.json')
        self.w.show()
        self.w.timer.stop()
        self.w._open_advanced()
        self.app.processEvents()
        self.dialog = self.w.advanced_dialog

    def tearDown(self):
        self.dialog.close()
        self.w.editor._saved = self.w.editor.document()
        self.w.editor_panel.saved = self.w.editor_panel.document()
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def assert_control_visible(self, control):
        self.assertTrue(control.isVisible())
        rect = QRect(control.mapTo(self.dialog, QPoint()), control.size())
        self.assertTrue(self.dialog.rect().contains(rect), (control.text(), rect, self.dialog.size()))

    def test_small_screens_and_large_text_keep_close_and_apply_visible(self):
        for text_size in ('comfortable', 'large'):
            self.w.text_size_picker.setCurrentIndex(self.w.text_size_picker.findData(text_size))
            for width, height in ((1366, 728), (1280, 680), (1024, 728), (800, 560), (640, 440)):
                with self.subTest(text_size=text_size, size=(width, height)):
                    available = QRect(40, 30, width, height)
                    self.dialog.fit_to_available(available)
                    self.app.processEvents()
                    self.assertTrue(available.contains(self.dialog.frameGeometry()), self.dialog.frameGeometry())
                    for button in (self.dialog.top_close, self.dialog.bottom_close,
                                   self.dialog.save_button, self.dialog.apply_button, self.dialog.preset_button):
                        self.assert_control_visible(button)
                    scroll = self.w.pages.widget(0)
                    self.assertGreater(scroll.viewport().height(), 40)
                    for value in (scroll.verticalScrollBar().minimum(), scroll.verticalScrollBar().maximum()):
                        scroll.verticalScrollBar().setValue(value)
                        self.app.processEvents()
                        self.assert_control_visible(self.dialog.bottom_close)
                        self.assert_control_visible(self.dialog.apply_button)

    def test_both_close_buttons_and_escape_retain_unsaved_draft_and_send_nothing(self):
        self.w.editor.name.setText('保留这份未保存草稿')
        before = self.w.editor.document()
        self.w.link = SimLink()
        self.w.journal = []
        for close in (lambda: self.dialog.top_close.click(), lambda: self.dialog.bottom_close.click(),
                      lambda: QTest.keyClick(self.dialog, Qt.Key_Escape), lambda: self.dialog.close()):
            close()
            self.app.processEvents()
            self.assertFalse(self.dialog.isVisible())
            self.assertTrue(self.w.isVisible())
            self.assertTrue(self.w.editor.dirty)
            self.assertEqual(self.w.editor.document(), before)
            self.assertFalse(self.w.journal)
            self.w._open_advanced()
            self.app.processEvents()
            self.assertTrue(self.dialog.isVisible())

    def test_all_tabs_have_close_and_logs_do_not_take_parameter_space(self):
        for index in range(self.w.pages.count()):
            self.w.pages.setCurrentIndex(index)
            self.app.processEvents()
            self.assert_control_visible(self.dialog.top_close)
            self.assert_control_visible(self.dialog.bottom_close)
            self.assertEqual(self.dialog.config_actions.isVisible(), index == 0)
        self.assertEqual(self.w.pages.tabText(4), '操作日志')
        self.assertIs(self.w.logbox.parentWidget(), self.w.pages.widget(4))
        self.assertIsInstance(self.w.pages.widget(3), QScrollArea)

    def test_errors_and_partial_application_are_visible_inside_dialog(self):
        self.w.apply_draft()
        self.assertIn('连接设备', self.dialog.status.text())
        self.w.link = SimLink()
        self.w.link.regs[0x7f] = 0x11
        self.w.editor.spectrum.set_values([200, 80] + [0] * 14)
        self.dialog.apply_button.click()
        self.w.apply_worker.wait(1500)
        self.app.processEvents()
        self.assertEqual(self.w.device_record['status'], 'PARTIAL_PARAMETER_CONFIRMED')
        self.assertIn('模拟流程', self.dialog.status.text())
        self.assertIn('其他草稿字段未应用', self.dialog.status.text())
        self.assertEqual([d for a, d, _ in self.w.device_record['writes'] if a == 0x59], [200, 80] + [0] * 14)
        self.assertNotIn(0x63, [a for a, _, _ in self.w.device_record['writes']])

    def test_save_shortcut_is_scoped_to_config_and_does_not_apply(self):
        with patch.object(self.w.editor, 'save_to') as save:
            self.w.editor.path = self.temp.name + '/instrument.json'
            self.w.editor.name.setFocus()
            QTest.keyClick(self.w.editor.name, Qt.Key_S, Qt.ControlModifier)
            self.app.processEvents()
            save.assert_called_once()
        self.assertIsNone(self.w.device_record)

    def test_enter_never_implicitly_applies_or_closes_dialog(self):
        self.w.editor.name.setFocus()
        QTest.keyClick(self.w.editor.name, Qt.Key_Return)
        self.app.processEvents()
        self.assertTrue(self.dialog.isVisible())
        self.assertIsNone(self.w.apply_worker)


if __name__ == '__main__':
    unittest.main()
