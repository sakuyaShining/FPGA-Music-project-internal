"""Bounded explicit evidence export off the UI thread, with atomic replacement."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal


class EvidenceWorker(QThread):
    result = pyqtSignal(str)

    def __init__(self, filename, data, parent=None):
        super().__init__(parent)
        self.filename, self.data = filename, data

    def run(self):
        temporary = None
        try:
            target = Path(self.filename)
            payload = json.dumps(self.data, ensure_ascii=False, indent=2).encode('utf-8')
            if shutil.disk_usage(str(target.parent)).free < len(payload) + 1048576:
                raise OSError('剩余磁盘容量不足，未覆盖已有证据')
            with tempfile.NamedTemporaryFile(dir=str(target.parent),delete=False,suffix='.tmp') as stream:
                temporary = stream.name
                stream.write(payload)
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,target);temporary=None
            self.result.emit('证据已保存：'+str(target))
        except Exception as exc:
            self.result.emit('证据保存失败：'+str(exc))
        finally:
            if temporary:
                try:os.unlink(temporary)
                except OSError:pass
