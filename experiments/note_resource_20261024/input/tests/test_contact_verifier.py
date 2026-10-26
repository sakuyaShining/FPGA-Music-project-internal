from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_contact_contract import mutate, positive_valid, negative_valid, FAULTS


class ContactVerifierTests(unittest.TestCase):
    def test_positive_accepts_native_and_normalized_newlines(self):
        for newline in ('\n', '\r\n'):
            text = newline.join(('Ran 11 tests in 0.03s', '', 'OK', ''))
            self.assertTrue(positive_valid(0, text))
            self.assertFalse(positive_valid(1, text))
        self.assertFalse(positive_valid(0, 'Ran 10 tests\nOK\n'))
        self.assertFalse(positive_valid(0, 'Ran 11 tests\nNOT OK\n'))

    def test_negative_needs_the_designated_assertion_not_import_or_timeout(self):
        target = 'test_expected_guard'
        text = 'FAIL: '+target+' (Case)\nAssertionError\n'
        self.assertTrue(negative_valid(1, text, target))
        self.assertFalse(negative_valid(0, text, target))
        self.assertFalse(negative_valid(124, text, target))
        self.assertFalse(negative_valid(1, 'ERROR: '+target+' (Case)\nImportError', target))
        self.assertFalse(negative_valid(1, text, 'test_different_guard'))

    def test_mutations_are_exact_and_guard_source_changes(self):
        source = (ROOT/'contact_contract.py').read_text(encoding='utf-8')
        self.assertEqual(mutate(source, 'candidate'), source)
        for fault in FAULTS:
            self.assertNotEqual(mutate(source, fault), source)
            with self.assertRaises(ValueError):
                mutate('changed source', fault)
