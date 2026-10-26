from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('resource_audio_verifier', ROOT / 'verify_audio.py')
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class AudioGuardTests(unittest.TestCase):
    def test_only_target_file_is_mutated(self):
        for fault in ('early-consume', 'ignore-kill', 'early-finish', 'partial-token'):
            changed = []
            for path in (ROOT / 'rtl').glob('*.v'):
                source = path.read_text(encoding='utf-8')
                if VERIFIER.variant(path.name, source, fault) != source:
                    changed.append(path.name)
            target = 'note_audio_backend.v' if fault == 'partial-token' else 'tdm_engine_transactional.v'
            self.assertEqual(changed, [target])

    def test_changed_or_repeated_mutation_anchor_is_rejected(self):
        with self.assertRaises(ValueError):
            VERIFIER.mutant('not the original source', 'ignore-kill')
        anchor = 'wire kill_effect=TRANSACTIONAL&&consume&&kill1;'
        with self.assertRaises(ValueError):
            VERIFIER.mutant(anchor + anchor, 'ignore-kill')

    def test_compile_failure_timeout_and_wrong_failure_do_not_count(self):
        marker = 'unpublished partial consumed'
        self.assertFalse(VERIFIER.verdict('early-consume', dict(returncode=1), dict(returncode=1, text=marker)))
        self.assertFalse(VERIFIER.verdict('early-consume', dict(returncode=0), dict(returncode=124, text=marker)))
        self.assertFalse(VERIFIER.verdict('early-consume', dict(returncode=0), dict(returncode=1, text='unrelated assertion')))
        self.assertFalse(VERIFIER.verdict('early-consume', dict(returncode=0), None))

    def test_designated_failure_required_for_each_mutant(self):
        markers = {'early-consume':'unpublished partial consumed', 'ignore-kill':'retirement acknowledged before silence',
                   'early-finish':'false natural completion', 'partial-token':'stale partial response consumed'}
        for case, marker in markers.items():
            self.assertTrue(VERIFIER.verdict(case, dict(returncode=0), dict(returncode=1, text=marker)))
            self.assertFalse(VERIFIER.verdict(case, dict(returncode=0), dict(returncode=0, text=marker)))

    def test_positive_requires_clean_exit_and_pass_marker(self):
        for case, marker in [('legacy', 'PASS legacy_audio'), ('candidate', 'PASS real_audio')]:
            self.assertTrue(VERIFIER.verdict(case, dict(returncode=0), dict(returncode=0, text=marker)))
            self.assertFalse(VERIFIER.verdict(case, dict(returncode=0), dict(returncode=1, text=marker)))
            self.assertFalse(VERIFIER.verdict(case, dict(returncode=0), dict(returncode=0, text=marker + '\nFATAL: bad')))


if __name__ == '__main__':
    unittest.main()
