"""真实 Qt 控件的配置闭环和设备隔离测试；无板、无音频模拟。"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox
from dsp_gui import MainWindow, SimLink, SerialLink
from instrument_config import default_config, load_config, ConfigError


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.preferences_temp = tempfile.TemporaryDirectory()
        self.preferences_path = str(Path(self.preferences_temp.name) / "display.json")
        self.window = MainWindow(self.preferences_path)
        self.window.timer.stop()
        self.window.link = SimLink()
        self.window.link.open()
        self.editor = self.window.editor
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.editor.set_document(default_config())
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.preferences_temp.cleanup()

    def test_full_document_survives_widgets_and_file_all_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ("sustain", "strike", "hybrid"):
                with self.subTest(mode=mode):
                    cfg = default_config("完整配置 Ω", mode)
                    cfg.update(preset=3, spectrum_mode="add", spectrum=[i*13 for i in range(16)])
                    cfg["articulation"].update(attack_ms=60000, decay_ms=997, release_ms=0, sustain_level=0,
                        hybrid_parts=["strike", "sustain"] * 8)
                    cfg["vibrato"].update(enabled=True, rate_millihz=12345, depth_cents=199)
                    cfg["effects"]["dry_enabled"] = False
                    cfg["effects"]["delay"].update(enabled=True, time_ms=2000, feedback_q8=254)
                    cfg["effects"]["chorus"].update(enabled=True, rate_millihz=19999, depth_ms=99)
                    cfg["effects"]["reverb"].update(enabled=True, feedback_q8=253, damping=7)
                    self.editor.set_document(cfg)
                    self.assertEqual(self.editor.document(), cfg)
                    self.editor.name.setText("已编辑 " + mode)
                    cfg["name"] = "已编辑 " + mode
                    self.assertTrue(self.editor.dirty)
                    path = Path(directory) / (mode + ".json")
                    self.editor.save_to(path)
                    self.assertFalse(self.editor.dirty)
                    self.assertEqual(load_config(path), cfg)
                    self.editor.set_document(default_config())
                    self.editor.load_from(path)
                    self.assertEqual(self.editor.document(), cfg)
                    self.assertFalse(self.editor.dirty)

    def test_all_editor_controls_import_save_send_no_frames(self):
        with patch.object(self.window.link, "send", wraps=self.window.link.send) as send:
            self.editor.name.setText("无副作用")
            self.editor.spectrum.set_values([12] * 16)
            self.editor.preset.setCurrentIndex(2)
            self.editor.spectrum_mode.setCurrentIndex(1)
            self.editor.mode.setCurrentIndex(2)
            for widget in self.editor.fields.values():
                if hasattr(widget, "setChecked"):
                    widget.setChecked(not widget.isChecked())
                else:
                    widget.setValue(widget.maximum())
            for box in self.editor.parts:
                box.setChecked(not box.isChecked())
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "draft.json"
                self.editor.save_to(path)
                self.editor.load_from(path)
            QTest.mouseClick(self.editor.apply_button, Qt.LeftButton)
            send.assert_not_called()
            self.assertFalse(self.editor.apply_button.isEnabled())
            self.assertEqual(self.window.journal, [])

    def test_invalid_import_and_failed_save_preserve_dirty_draft(self):
        self.editor.name.setText("必须保留的草稿")
        before = self.editor.document()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"schema_version":99}', encoding="utf-8")
            with self.assertRaises(ConfigError):
                self.editor.load_from(path)
            self.assertEqual(self.editor.document(), before)
            original = path.read_bytes()
            with patch("instrument_config.os.replace", side_effect=OSError("保存失败")):
                with self.assertRaises(OSError):
                    self.editor.save_to(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(self.editor.document(), before)
            self.assertIsNone(self.editor.path)
            self.assertTrue(self.editor.dirty)

    def test_unsaved_cancel_discard_and_save_failure(self):
        self.editor.name.setText("未保存")
        with patch("config_editor.QMessageBox.question", return_value=QMessageBox.Cancel):
            self.editor.new_document()
            self.assertEqual(self.editor.name.text(), "未保存")
            self.assertFalse(self.window.close())
        with patch("config_editor.QMessageBox.question", return_value=QMessageBox.Save), \
             patch.object(self.editor, "save_document", return_value=False):
            self.assertFalse(self.editor.confirm_discard())
        with patch("config_editor.QMessageBox.question", return_value=QMessageBox.Discard):
            self.editor.new_document()
        self.assertFalse(self.editor.dirty)

    def test_dialog_load_and_save_success_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "配置.json")
            self.editor.name.setText("对话框保存")
            with patch("config_editor.QFileDialog.getSaveFileName", return_value=(path, "")):
                self.assertTrue(self.editor.save_as())
            with patch("config_editor.QFileDialog.getSaveFileName", return_value=("", "")):
                self.assertFalse(self.editor.save_as())
            self.editor.new_document()
            with patch("config_editor.QFileDialog.getOpenFileName", return_value=(path, "")):
                self.editor.open_dialog()
            self.assertEqual(self.editor.name.text(), "对话框保存")

    def test_keyboard_scope_and_tab_switch_release_held_notes(self):
        with patch.object(self.window.link, "send", wraps=self.window.link.send) as send:
            self.editor.name.setFocus()
            QTest.keyClicks(self.editor.name, "zxcm")
            send.assert_not_called()
            self.window.pages.setCurrentIndex(1)
            self.window.ed_score.setFocus()
            QTest.keyClicks(self.window.ed_score, "c")
            send.assert_not_called()
            self.window.setFocus()
            QTest.keyPress(self.window, Qt.Key_Z)
            self.assertEqual(self.window.held, {0: 60})
            self.window.pages.setCurrentIndex(0)
            self.assertEqual(self.window.held, {})
            self.assertEqual(send.call_count, 2)

    def test_legacy_spectrum_is_blocked_for_real_serial(self):
        self.window.link = SerialLink("unused-test-port")
        with patch.object(self.window.link, "send") as send:
            self.window.send_spectrum()
            send.assert_not_called()
        self.assertIn("设备未确认协议 v1.1", self.window.logbox.toPlainText())

    def test_theme_switch_preserves_draft_and_sends_nothing(self):
        self.editor.name.setText("保留所有修改")
        self.editor.spectrum.set_values(list(range(16)))
        before = self.editor.document()
        with patch.object(self.window.link, "send") as send:
            for index, key in enumerate(("paper", "night", "grove", "paper")):
                self.window.theme_picker.setCurrentIndex(index % 3)
                self.app.processEvents()
                self.assertEqual(self.window.property("studioTheme"), key)
                self.assertEqual(self.editor.document(), before)
                self.assertTrue(self.editor.dirty)
                self.assertNotIn("@accent@", self.window.styleSheet())
            send.assert_not_called()

    def test_mode_and_navigation_buttons_remain_selected(self):
        for index in range(3):
            button = self.editor.mode_buttons[index]
            QTest.mouseClick(button, Qt.LeftButton)
            QTest.mouseClick(button, Qt.LeftButton)
            self.assertEqual(self.editor.mode.currentIndex(), index)
            self.assertEqual(sum(b.isChecked() for b in self.editor.mode_buttons), 1)
        for index in (1, 2, 0):
            button = self.window.nav_buttons[index]
            QTest.mouseClick(button, Qt.LeftButton)
            QTest.mouseClick(button, Qt.LeftButton)
            self.assertEqual(self.window.pages.currentIndex(), index)
            self.assertEqual(sum(b.isChecked() for b in self.window.nav_buttons), 1)

    def test_precise_spectrum_input_and_keyboard_are_isolated(self):
        before = self.editor.spectrum.values()
        self.editor.part_selector.setCurrentIndex(5)
        self.editor.amplitude.setValue(117)
        expected = list(before)
        expected[5] = 117
        self.assertEqual(self.editor.spectrum.values(), expected)
        self.editor.spectrum.setFocus()
        QTest.keyClick(self.editor.spectrum, Qt.Key_Up, Qt.ShiftModifier)
        self.assertEqual(self.editor.amplitude.value(), 127)
        QTest.keyClick(self.editor.spectrum, Qt.Key_Right)
        self.assertEqual(self.editor.part_selector.currentIndex(), 6)
        QTest.keyClick(self.editor.spectrum, Qt.Key_End)
        self.assertEqual(self.editor.spectrum.values()[6], 255)
        self.assertEqual(self.window.journal, [])

    def test_display_size_persists_separately_from_instrument(self):
        before = self.editor.document()
        self.window.text_size_picker.setCurrentIndex(1)
        self.window.theme_picker.setCurrentIndex(2)
        self.assertEqual(self.editor.document(), before)
        self.assertEqual(self.window.journal, [])
        other = MainWindow(self.preferences_path)
        other.timer.stop()
        self.assertEqual(other.text_size_picker.currentData(), "large")
        self.assertEqual(other.theme_picker.currentData(), "grove")
        other.close()
        other.deleteLater()

    def test_document_actions_remain_visible_while_scrolling(self):
        self.window.resize(1024, 768)
        self.app.processEvents()
        scroll = self.window.pages.currentWidget()
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        self.assertTrue(self.editor.document_header.isVisibleTo(self.window))
        self.window.pages.setCurrentIndex(1)
        self.assertFalse(self.editor.document_header.isVisibleTo(self.window))

    def test_lolita_font_selection_persists_without_device_changes(self):
        self.assertIn("lolita", self.window.available_fonts)
        self.assertIn("lolita_mono", self.window.available_fonts)
        before = self.editor.document()
        self.window.font_picker.setCurrentIndex(self.window.font_picker.findData("lolita_mono"))
        self.app.processEvents()
        self.assertEqual(self.editor.document(), before)
        self.assertEqual(self.window.journal, [])
        other = MainWindow(self.preferences_path)
        other.timer.stop()
        self.assertEqual(other.font_picker.currentData(), "lolita_mono")
        other.close()
        other.deleteLater()

    def test_sidebar_fits_navigation_and_explicit_description_lines(self):
        for font_key in ("system", "lolita", "lolita_mono"):
            self.window.font_picker.setCurrentIndex(self.window.font_picker.findData(font_key))
            for text_size in (0, 1):
                self.window.text_size_picker.setCurrentIndex(text_size)
                for page in range(3):
                    self.window.pages.setCurrentIndex(page)
                    self.app.processEvents()
                    for button in self.window.nav_buttons:
                        self.assertGreaterEqual(button.contentsRect().width()-30,
                            button.fontMetrics().horizontalAdvance(button.text()))
                    label = self.window.page_description
                    for line in label.text().splitlines():
                        self.assertGreaterEqual(label.width(), label.fontMetrics().horizontalAdvance(line))

    def test_scan_records_all_channels_and_restores_selected_channel(self):
        self.window.cmb_ch.setCurrentIndex(3)
        self.window.journal = []
        self.window.scan_all()
        self.window.scan_timer.stop()
        for _ in range(16):
            self.window._scan_step()
        self.assertEqual(set(self.window.ele), set(range(16)))
        for channel in range(16):
            self.assertEqual(self.window.ele[channel], (24+(channel*7)%40,)*2)
        self.assertEqual(self.window.link.sel, 3)
        self.assertEqual(self.window.scan_i, -1)

    def test_disconnect_stops_manual_scan_and_ignores_pending_tick(self):
        self.window.scan_all()
        self.assertTrue(self.window.scan_timer.isActive())
        self.window._toggle_conn()
        self.assertFalse(self.window.scan_timer.isActive())
        self.assertIsNone(self.window.link)
        self.window._scan_step()
        self.assertEqual(self.window.scan_i, -1)

    def test_bad_score_is_rejected_and_length_boundary_is_preserved(self):
        with patch("dsp_gui.QMessageBox.warning") as warning:
            for text in ("64:1:extra", ",".join(["64:1"]*64)):
                self.window.ed_score.setText(text)
                self.assertIsNone(self.window._parse_score())
            self.assertEqual(warning.call_count, 2)
        self.window.ed_score.setText(",".join(["64:1"]*63))
        self.assertEqual(len(self.window._parse_score()), 63)

    def test_failed_send_is_not_reported_as_success_or_held_note(self):
        with patch.object(self.window.link, "send", side_effect=OSError("断线")):
            self.window.note_on(0)
        self.assertEqual(self.window.held, {})
        self.assertEqual(self.window.journal, [])
        self.assertIn("生效状态未知", self.window.logbox.toPlainText())
        with patch.object(self.window.link, "send", return_value=1):
            self.assertFalse(self.window.send_frames(__import__('dsp_host').cmd_note('on:60:12'), '短写'))
        self.assertEqual(self.window.journal, [])

    def test_bpm_status_and_real_sequence_guard(self):
        self.window.spin_bpm.setValue(80)
        first = self.window.lab_seq.text()
        self.window.spin_bpm.setValue(180)
        self.assertNotEqual(self.window.lab_seq.text(), first)
        self.window.link = SerialLink("unused-test-port")
        with patch.object(self.window.link, "send") as send:
            self.window.seq_download()
            self.window.seq_play()
            send.assert_not_called()

    def test_export_preserves_device_identity_after_disconnect(self):
        self.window.note_on(0)
        self.window.note_off(0)
        self.window._toggle_conn()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "frames.txt")
            with patch("dsp_gui.QFileDialog.getSaveFileName", return_value=(path, "")):
                self.window._export()
            self.assertIn("设备类型：模拟设备", Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
