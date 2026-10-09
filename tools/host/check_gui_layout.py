"""离屏布局检查。可用 QT_SCALE_FACTOR 在独立进程中覆盖不同 DPI。"""
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
from dsp_gui import QApplication, MainWindow


def main():
    app = QApplication([])
    results = []
    with tempfile.TemporaryDirectory() as directory:
        window = MainWindow(str(Path(directory) / "preferences.json"))
        window.timer.stop()
        window.show()
        for size in ((1024, 768), (1280, 900), (1440, 1000)):
            for text in (0, 1):
                window.resize(*size)
                window.text_size_picker.setCurrentIndex(text)
                for font in range(window.font_picker.count()):
                    window.font_picker.setCurrentIndex(font)
                    for page in range(3):
                        window.pages.setCurrentIndex(page)
                        for _ in range(5):
                            app.processEvents()
                        horizontal = window.pages.currentWidget().horizontalScrollBar().maximum()
                        sidebar_fits = all(button.contentsRect().width()-30 >= button.fontMetrics().horizontalAdvance(button.text())
                            for button in window.nav_buttons)
                        results.append(dict(size=size, text=window.text_size_picker.currentText(), page=page,
                            font=window.font_picker.currentData(), sidebar_fits=sidebar_fits,
                            actual_size=[window.width(), window.height()], horizontal_overflow=horizontal,
                            dpr=window.devicePixelRatioF(), passed=sidebar_fits and horizontal == 0 and window.width() == size[0]))
        window.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    sys.exit(main())
