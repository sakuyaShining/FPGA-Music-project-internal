"""Regression for the user's ordinary launch path, not a custom test window."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class NormalStartupTests(unittest.TestCase):
    def test_main_opens_the_same_workbench_as_the_delivered_preview(self):
        script=Path(__file__).parent/'dsp_gui.py'
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_FONTDIR='C:/Windows/Fonts',
                 PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,str(script.resolve()),'--startup-check'],
                cwd=directory,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr.decode('utf-8',errors='replace'))
            report=json.loads((Path(directory)/'sim_build/gui/normal-startup.json').read_text(encoding='utf-8'))
            self.assertEqual(report['ui_class'],'WorkbenchWindow')
            self.assertEqual(report['entry'],'normal main()')
            self.assertIn('全局演奏工作台',report['title'])
            self.assertNotIn('配置与设备实验',report['title'])


if __name__=='__main__':unittest.main()
