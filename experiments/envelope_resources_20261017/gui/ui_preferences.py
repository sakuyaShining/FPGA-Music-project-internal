"""界面偏好独立存储；不进入乐器配置、不发送设备命令。"""
import json
import os
from pathlib import Path
import tempfile

DEFAULTS = {"theme": "paper", "text_size": "comfortable", "font": "lolita"}


def load_preferences(path):
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        return {"theme": value["theme"] if value.get("theme") in ("paper", "night", "grove") else "paper",
                "text_size": value["text_size"] if value.get("text_size") in ("comfortable", "large") else "comfortable",
                "font": value["font"] if value.get("font") in ("system", "lolita", "lolita_mono") else "lolita"}
    except (OSError, ValueError, TypeError, AttributeError):
        return dict(DEFAULTS)


def save_preferences(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(target.parent), delete=False, suffix=".tmp", mode="w", encoding="utf-8") as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary:
            os.unlink(temporary)
