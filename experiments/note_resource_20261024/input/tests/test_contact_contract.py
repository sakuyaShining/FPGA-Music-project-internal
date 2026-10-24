from dataclasses import FrozenInstanceError
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contact_contract import ContactLedger, ContactCancellation

specification = importlib.util.spec_from_file_location('resource_contract_reference', ROOT.parent/'reference.py')
resource_reference = importlib.util.module_from_spec(specification)
specification.loader.exec_module(resource_reference)
ResourceModel = resource_reference.ResourceModel


def drive(ledger, resource, event, observers=(), cancel=0):
    command = dict(kind=0 if event.on else 1, token=event.token, layers=event.layers, groups=0, cancel=cancel)
    result = resource.apply(command)
    for operation, ticket, token, groups, layers, mapping in result['works']:
        if operation == 1:
            for observer in (ledger,)+tuple(observers):
                observer.retire(token)
    code, token, groups, layers, mapping = result['response']
    ledger.complete(token, code, groups, layers, mapping)
    return result


class ContactContractTests(unittest.TestCase):
    def press(self, ledger, contact=0, generation=1, layers=15):
        return ledger.press(contact, generation, 60, 127, -81, layers)

    def test_payload_is_immutable_and_off_keeps_exact_identity(self):
        ledger = ContactLedger()
        resource = ResourceModel()
        event = self.press(ledger)
        with self.assertRaises(FrozenInstanceError):
            event.note = 72
        drive(ledger, resource, event)
        release = ledger.release(event.token)
        self.assertEqual((release.token, release.contact, release.generation), (event.token, 0, 1))
        drive(ledger, resource, release)
        self.assertEqual(resource.used(), 15)
        self.assertIsNone(ledger.move(event.token, 70))

    def test_same_pitch_two_sources_are_independent_complete_notes(self):
        live, score, resource = ContactLedger(), ContactLedger(source=1), ResourceModel()
        first, second = self.press(live), self.press(score)
        self.assertEqual(first.token ^ second.token, 1 << 31)
        drive(live, resource, first)
        drive(score, resource, second)
        self.assertEqual(len(resource.notes), 2)
        self.assertEqual(resource.used(), 255)

    def test_all_four_layers_move_together_without_new_identity(self):
        ledger, resource = ContactLedger(), ResourceModel()
        event = self.press(ledger)
        drive(ledger, resource, event)
        before = ledger.issued
        for position in (0, 100, 511, 250):
            movement = ledger.move(event.token, position)
            self.assertEqual((movement['token'], movement['groups'], movement['layers']), (event.token, 15, 15))
        self.assertEqual(ledger.issued, before)

    def test_stolen_held_contact_does_not_retrigger_or_move_new_owner(self):
        live, score, resource = ContactLedger(), ContactLedger(source=1), ResourceModel()
        old = self.press(live)
        drive(live, resource, old)
        for contact in range(8):
            drive(score, resource, self.press(score, contact), observers=(live,))
        self.assertNotIn(old.token, resource.notes)
        self.assertIsNone(live.move(old.token, 300))
        with self.assertRaises(RuntimeError):
            self.press(live, generation=2)
        before = resource.snapshot()
        stale = drive(live, resource, live.release(old.token))
        self.assertEqual(stale['response'][0], 3)
        self.assertEqual(resource.snapshot(), before)
        fresh = self.press(live, generation=2)
        self.assertNotEqual(fresh.token, old.token)
        drive(live, resource, fresh, observers=(score,))

    def test_late_off_and_move_survive_legacy_generation_wrap_without_alias(self):
        ledger, resource = ContactLedger(), ResourceModel()
        first = self.press(ledger, generation=0, layers=1)
        drive(ledger, resource, first)
        delayed_off = ledger.release(first.token)
        drive(ledger, resource, delayed_off)
        for generation in range(1, 257):
            fresh = self.press(ledger, generation=generation % 256, layers=1)
            drive(ledger, resource, fresh)
            if generation != 256:
                drive(ledger, resource, ledger.release(fresh.token))
        self.assertEqual((fresh.contact, fresh.generation), (first.contact, first.generation))
        self.assertNotEqual(fresh.token, first.token)
        before = resource.snapshot()
        result = resource.apply(dict(kind=1, token=delayed_off.token, layers=0, groups=0))
        self.assertEqual(result['response'][0], 3)
        self.assertEqual(resource.snapshot(), before)
        self.assertIsNone(ledger.move(first.token, 511))
        self.assertIsNone(ledger.release(first.token))

    def test_cancelled_pending_admission_cannot_bind_an_allocated_reply(self):
        ledger, resource = ContactLedger(), ResourceModel()
        event = self.press(ledger)
        self.assertIsInstance(ledger.release(event.token), ContactCancellation)
        with self.assertRaises(ValueError):
            ledger.complete(event.token, 0, 15, 15, 3 << 15 | 2 << 10 | 1 << 5)
        result = drive(ledger, resource, event, cancel=4)
        self.assertEqual(result['response'][0], 6)
        self.assertEqual(resource.used(), 0)
        self.assertIsNone(ledger.move(event.token, 10))

    def test_wrong_reply_and_incomplete_layer_maps_leave_pending_unchanged(self):
        ledger = ContactLedger()
        event = self.press(ledger)
        for token, groups, layers, mapping in ((event.token ^ (1 << 31), 15, 15, 0),
                                               (event.token, 1, 1, 0), (event.token, 15, 15, 0),
                                               (event.token, 31, 15, 3 << 15 | 2 << 10 | 1 << 5)):
            with self.assertRaises(ValueError):
                ledger.complete(token, 0, groups, layers, mapping)
            self.assertIs(ledger.pending, event)
            self.assertEqual(ledger.rows[0]['groups'], 0)

    def test_natural_partial_finish_differs_from_whole_note_retirement(self):
        ledger, resource = ContactLedger(), ResourceModel()
        event = self.press(ledger)
        drive(ledger, resource, event)
        ledger.natural_end(event.token, 2)
        self.assertEqual(ledger.move(event.token, 200)['groups'], 13)
        self.assertEqual(ledger.rows[0]['layers'], 13)
        ledger.retire(event.token)
        self.assertTrue(ledger.rows[0]['held'])
        self.assertIsNone(ledger.move(event.token, 201))

    def test_serial_wrap_is_ordered_and_full_epoch_cannot_reuse_tokens(self):
        ledger, resource = ContactLedger(initial_serial=0x7ffffffe), ResourceModel()
        tokens = []
        for generation in range(3):
            event = self.press(ledger, generation=generation, layers=1)
            tokens.append(event.token)
            self.assertEqual(drive(ledger, resource, event)['response'][0], 0)
            drive(ledger, resource, ledger.release(event.token))
        self.assertEqual(tokens, [0x7ffffffe, 0x7fffffff, 0])
        narrow = ContactLedger(serial_bits=2, initial_serial=3)
        issued = []
        for generation in range(4):
            event = self.press(narrow, generation=generation, layers=1)
            issued.append(event.token)
            narrow.complete(event.token, 4)
            release = narrow.release(event.token)
            narrow.complete(release.token, 3)
        self.assertEqual(len(set(issued)), 4)
        with self.assertRaises(RuntimeError):
            self.press(narrow, generation=4, layers=1)

    def test_reset_flushes_pending_and_requires_shared_backend_fence(self):
        ledger = ContactLedger()
        event = self.press(ledger)
        ledger.reset()
        with self.assertRaises(ValueError):
            ledger.complete(event.token, 6)
        self.assertEqual((ledger.rows, ledger.pending, ledger.issued), ({}, None, 0))

    def test_invalid_payload_and_concurrent_transaction_are_not_accepted(self):
        for values in ((26, 1, 60, 127, 0, 15), (0, 256, 60, 127, 0, 15),
                       (0, 1, 128, 127, 0, 15), (0, 1, 60, 256, 0, 15),
                       (0, 1, 60, 127, 1 << 17, 15), (0, 1, 60, 127, 0, 0)):
            with self.assertRaises(ValueError):
                ContactLedger().press(*values)
        ledger = ContactLedger()
        self.press(ledger)
        with self.assertRaises(RuntimeError):
            self.press(ledger, contact=1)
