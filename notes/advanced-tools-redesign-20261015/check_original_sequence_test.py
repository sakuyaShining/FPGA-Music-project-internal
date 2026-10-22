"""Check whether the unrelated sequence timing failure predates UI edits."""
import json
import os
from pathlib import Path
import sys
import types
import unittest
import zipfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QPA_FONTDIR'] = 'C:/Windows/Fonts'
root = Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
sys.path[:0] = [str(root / 'tools/host'), str(root / 'tools/scripts')]
out = Path(__file__).parent
backup = Path((out / 'latest-backup.txt').read_text(encoding='utf-8'))
with zipfile.ZipFile(backup / 'before.zip') as z:
    for name in ('config_editor', 'workbench'):
        path = 'tools/host/' + name + '.py'
        module = types.ModuleType(name)
        module.__file__ = str(root / path)
        sys.modules[name] = module
        exec(compile(z.read(path), module.__file__, 'exec'), module.__dict__)
suite = unittest.defaultTestLoader.loadTestsFromName(
    'test_workbench.WorkbenchTests.test_stop_during_score_download_is_queued_instead_of_ignored')
with (out / 'original-sequence-test.txt').open('w', encoding='utf-8') as log:
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
print(json.dumps(dict(original_version='host-workbench-20261015-10',
    success=result.wasSuccessful(), failures=len(result.failures), errors=len(result.errors))))
