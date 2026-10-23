from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('engineering', Path(__file__).parents[1]/'scripts/engineering.py')
engineering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engineering)


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base/'repository'
        self.raw = b'golden\r\nunchanged\r\n'
        stored = gzip.compress(self.raw, mtime=0)
        self.blob = self.root/'fpga/current/golden.tsv.gz'
        self.blob.parent.mkdir(parents=True)
        self.blob.write_bytes(stored)
        self.record = dict(stored='fpga/current/golden.tsv.gz', bytes=len(self.raw),
                           sha256=hashlib.sha256(self.raw).hexdigest(),
                           stored_sha256=hashlib.sha256(stored).hexdigest(), codec='gzip')
        self.manifest = dict(captured_at='2026-10-23T15:35:23+00:00', source_branch='fixture',
                             areas=dict(fpga=dict(files={'golden.tsv':self.record})))
        self.save_manifest()

    def save_manifest(self):
        path = self.root/engineering.MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.manifest), encoding='utf8')

    def test_export_restores_exact_bytes_and_provenance(self):
        output = self.base/'export'
        result = engineering.export('fpga', output, self.root)
        self.assertEqual((output/'golden.tsv').read_bytes(), self.raw)
        self.assertEqual(result['inputs']['golden.tsv'], self.record['sha256'])
        self.assertFalse(result['validation_inherited'])
        self.assertFalse(result['product_acceptance'])

    def test_corruption_does_not_create_output(self):
        self.blob.write_bytes(b'corrupt')
        output = self.base/'export'
        with self.assertRaisesRegex(ValueError, 'Stored identity'):
            engineering.export('fpga', output, self.root)
        self.assertFalse(output.exists())

    def test_decoded_identity_is_checked_separately(self):
        self.record['sha256'] = '0'*64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'Source identity'):
            engineering.check(self.root)

    def test_unregistered_source_cannot_enter_build_glob(self):
        (self.blob.parent/'unexpected.v').write_text('module unexpected; endmodule')
        with self.assertRaisesRegex(ValueError, 'Unregistered'):
            engineering.export('fpga', self.base/'export', self.root)

    def test_existing_and_nested_outputs_are_refused(self):
        output = self.base/'existing'
        output.mkdir()
        (output/'keep').write_text('original')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            engineering.export('fpga', output, self.root)
        with self.assertRaisesRegex(ValueError, 'outside'):
            engineering.export('fpga', self.root/'new', self.root)
        self.assertEqual((output/'keep').read_text(), 'original')

    def test_unsafe_manifest_paths_are_rejected(self):
        for name in ('../escape', '/absolute', 'C:/absolute', 'folder\\escape'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                engineering.safe(name)


if __name__ == '__main__':
    unittest.main()
