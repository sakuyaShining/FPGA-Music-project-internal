from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reference import Router, INPUT_FIELDS, OUTPUT_FIELDS, generate, pack, unpack
from verify import compare, mutate
from build import slacks


class InputRouterTests(unittest.TestCase):
    def inputs(self):
        values={name:0 for name,width in INPUT_FIELDS}
        values.update(rst_n=1,live_valid=1,score_valid=1,live_serial=7,score_serial=7,
                      live_note=60,score_note=72,live_layers=15,score_layers=5)
        return values

    def test_source_token_tag_and_complete_payload(self):
        model=Router();values=self.inputs()
        outputs=model.outputs(values);model.advance(values,outputs)
        self.assertEqual(model.payload['token'],7)
        self.assertEqual(model.payload['layers'],15)
        self.assertEqual(model.phase,'present')

    def test_rotation_only_after_accepted_request(self):
        model=Router();values=self.inputs()
        model.advance(values,model.outputs(values))
        self.assertEqual(model.turn,1)
        for cycle in range(8):
            model.advance(values,model.outputs(values))
            self.assertEqual(model.turn,1)
        values['event_ready']=1;model.advance(values,model.outputs(values))
        values.update(response_valid=1,response_token=7,live_response_ready=1)
        model.advance(values,model.outputs(values))
        self.assertEqual(model.outputs(values)['score_ready'],1)

    def test_wrong_response_cannot_complete_or_leak(self):
        model=Router();values=self.inputs();model.advance(values,model.outputs(values))
        values['event_ready']=1;model.advance(values,model.outputs(values))
        values.update(response_valid=1,response_token=0x80000007,live_response_ready=1,score_response_ready=1)
        outputs=model.outputs(values)
        self.assertEqual((outputs['response_ready'],outputs['live_response_valid'],outputs['score_response_valid']),(0,0,0))
        model.advance(values,outputs)
        self.assertEqual((model.phase,model.error),('reply',1))

    def test_reset_clears_transaction_and_arbitration(self):
        model=Router();values=self.inputs();model.advance(values,model.outputs(values))
        values['rst_n']=0;outputs=model.outputs(values)
        self.assertEqual((outputs['event_valid'],outputs['live_ready'],outputs['score_ready']),(0,0,0))
        self.assertEqual((model.phase,model.turn),('choose',0))

    def test_vector_roundtrip_and_deterministic_coverage(self):
        inputs,expected,coverage=generate(cycles=1500)
        self.assertEqual((inputs,expected,coverage),generate(cycles=1500))
        self.assertTrue(all(count>20 for count in coverage['accepted']))
        self.assertTrue(all(count==1 for count in coverage['serial_wraps']))
        self.assertEqual(pack(INPUT_FIELDS,unpack(INPUT_FIELDS,inputs[100])),inputs[100])
        self.assertEqual(sum(width for name,width in OUTPUT_FIELDS),168)

    def test_mutation_anchor_and_exact_trace_rejection(self):
        original=(ROOT/'rtl/note_event_router.v').read_text(encoding='utf-8')
        for fault in ('fixed-source','ignore-token','wrong-payload'):
            self.assertNotEqual(mutate(original,fault),original)
            with self.assertRaises(ValueError):
                mutate('wrong source',fault)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.tsv';path.write_text('0 xyz\n')
            self.assertEqual(compare(path,[0])['field'],'unknown')

    def test_sta_missing_section_is_not_pass(self):
        self.assertEqual(slacks('missing report'),dict(Setup=None,Hold=None,Recovery=None,Removal=None))

    def test_sta_keeps_negative_and_all_check_types(self):
        text=''.join('<a name="'+kind+'_Slack_Table"><tr><td>1</td><td>'+str(value)+'</td>'+''.join('<td>x</td>' for column in range(7))+'</tr>'
            for kind,value in [('Setup',5.0),('Hold',-0.1),('Recovery',2.0),('Removal',1.0)])
        self.assertEqual(slacks(text),dict(Setup=5.0,Hold=-0.1,Recovery=2.0,Removal=1.0))


if __name__=='__main__':
    unittest.main()
