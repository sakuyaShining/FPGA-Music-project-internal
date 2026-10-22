import json
import tempfile
import unittest
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from dsp_gui import SpectrumBars, PRESETS
from tone_panel import TonePanel, compile_tone, validate_tone


class ToneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def tone(self):
        return dict(tone_schema=1,name='明亮声音',kind='drawn',preset=2,amplitudes=[255,120]+[0]*14)

    def test_drawn_sound_uses_integer_harmonics_and_replaces_builtin(self):
        config,preset_only=compile_tone(self.tone())
        self.assertFalse(preset_only)
        self.assertEqual(config['preset'],0)
        self.assertEqual(config['spectrum_mode'],'replace')
        self.assertEqual(config['spectrum'],self.tone()['amplitudes'])

    def test_builtin_discards_hidden_drawing(self):
        tone=self.tone();tone['kind']='built_in'
        config,preset_only=compile_tone(tone)
        self.assertTrue(preset_only)
        self.assertEqual(config['preset'],2)
        self.assertEqual(config['spectrum'],[0]*16)

    def test_invalid_documents_are_rejected_without_mutating_editor(self):
        panel=TonePanel(SpectrumBars,PRESETS);before=panel.document()
        for field,value in [('tone_schema',True),('preset',4),('amplitudes',[1]*15),('name','')]:
            tone=self.tone();tone[field]=value
            with self.assertRaises(ValueError):validate_tone(tone)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json';path.write_text('{}')
            with self.assertRaises(ValueError):panel.load_from(path)
        self.assertEqual(panel.document(),before)
        panel.deleteLater()

    def test_edit_and_file_roundtrip_require_explicit_apply(self):
        panel=TonePanel(SpectrumBars,PRESETS);requests=[]
        panel.apply_requested.connect(requests.append)
        panel.kind.setCurrentIndex(1);panel.preset.setCurrentIndex(2)
        panel.name.setText('明亮声音');panel.bars.set_values(self.tone()['amplitudes'])
        self.assertTrue(panel.dirty)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sound.json';panel.save_to(path)
            self.assertFalse(panel.dirty)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),self.tone())
            panel.name.setText('改变');panel.load_from(path)
        self.assertEqual(requests,[])
        panel.use.click()
        self.assertEqual(requests,[self.tone()])
        panel.deleteLater()
