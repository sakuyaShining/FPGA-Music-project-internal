"""从应用资源加载用户指定字体；不修改系统字体安装。"""
from pathlib import Path
from PyQt5.QtGui import QFontDatabase
from serial_link import find_file

_loaded = None


def font_choices():
    global _loaded
    if _loaded is None:
        _loaded = {"system": ("系统字体", None)}
        for key, filename, title in (("lolita", "lolita.ttf", "Lolita"),
                                    ("lolita_mono", "LolitaMono.ttf", "Lolita Mono")):
            path = find_file("fonts/" + filename, (str(Path(__file__).parent),))
            if path:
                identity = QFontDatabase.addApplicationFont(path)
                families = QFontDatabase.applicationFontFamilies(identity) if identity >= 0 else []
                if families:
                    _loaded[key] = (title, families[0])
    return _loaded
