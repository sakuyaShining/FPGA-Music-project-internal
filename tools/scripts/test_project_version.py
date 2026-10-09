"""Reject incomplete manifests, source drift and substituted build artifacts."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import project_version as pv


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        for name,data in {'src/rtl/top.v':'module top; endmodule',
            'src/constr/top.cst':'pin', 'src/gowin/tdm_synth/table.hex':'00',
            'src/gowin/tdm_synth/tdm_synth.gprj':'<Project><File path="../../rtl/top.v"/><File path="../../constr/top.cst"/></Project>',
            'tools/host/gui.py':'pass'}.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
        current=pv.files(self.root)
        self.record=dict(schema=1,scope=list(pv.SCOPE),files=current,
                         tree_sha256=pv.sha(json.dumps(current,sort_keys=True).encode()))
        self.manifest=self.root/'manifest.json';self.save(self.record)

    def save(self,record):self.manifest.write_text(json.dumps(record))
    def tearDown(self):self.tmp.cleanup()
    def test_complete_manifest(self):self.assertEqual(pv.check(self.root,self.manifest)[1],[])
    def test_empty_manifest_rejected(self):
        self.save(dict(self.record,files={}))
        with self.assertRaises(ValueError):pv.check(self.root,self.manifest)
    def test_omitted_constraint_rejected_even_with_recomputed_digest(self):
        record=copy.deepcopy(self.record);del record['files']['src/constr/top.cst']
        record['tree_sha256']=pv.sha(json.dumps(record['files'],sort_keys=True).encode());self.save(record)
        self.assertTrue(any('missing build dependency' in e for e in pv.check(self.root,self.manifest)[1]))
    def test_gui_and_table_drift_detected(self):
        for n in ['tools/host/gui.py','src/gowin/tdm_synth/table.hex']:(self.root/n).write_text('changed')
        self.assertEqual(len(pv.check(self.root,self.manifest)[1]),2)
    def test_added_source_detected(self):
        (self.root/'src/rtl/extra.v').write_text('module extra;endmodule')
        self.assertTrue(pv.check(self.root,self.manifest)[1])
    def test_build_substitution_rejected(self):
        bit=self.root/'output.fs';bit.write_bytes(b'original')
        log=self.root/'build.txt';log.write_text('build log')
        bound=self.root/'build.json'
        bound.write_text(json.dumps(dict(schema=1,source_manifest=str(self.manifest),source_tree_sha256=self.record['tree_sha256'],
            bitstream=str(bit),bitstream_sha256=pv.sha(bit.read_bytes()),log=str(log),log_sha256=pv.sha(log.read_bytes()))))
        cmd=['python',str(Path(pv.__file__)),'--root',str(self.root),'check-build',str(bound)]
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        bit.write_bytes(b'replacement')
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,1)
    def test_old_build_cannot_be_bound_to_new_source_capture(self):
        bit=self.root/'old.fs';bit.write_bytes(b'old output')
        log=self.root/'old.txt';log.write_text('old log')
        self.record['captured_at']='2099-01-01T00:00:00+00:00';self.save(self.record)
        command=['python',str(Path(pv.__file__)),'--root',str(self.root),'bind-build',str(self.manifest),
                 '--bitstream',str(bit),'--log',str(log),'--command','test','--configuration','test',
                 '--output',str(self.root/'bound.json')]
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,1)
        self.assertFalse((self.root/'bound.json').exists())
        self.record['captured_at']='2000-01-01T00:00:00+00:00';self.save(self.record)
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)


if __name__=='__main__':unittest.main()
