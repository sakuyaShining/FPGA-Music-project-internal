from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reference import render, generate
from verify_renderer import mutate, compare


class RendererTests(unittest.TestCase):
    def context(self):
        return dict(note=60,velocity=255,scale=256,tilt=0x70,pad=0,spectrum=[0]*16,replace=0,
                    artic=0,artic_mask=0,strike_m=3,strike_k=12,curve=0,sustain=0,glide=-100)

    def payload(self, context, weight, partial=3, custom=False, envelope=0):
        definition=(envelope<<48)|(256<<32)|(200<<24)|(20000<<7)|(3<<5)|12
        return render(context,1,partial,definition,custom,[65536]*128,[256]*256,[weight]*1024)

    def test_high_scale_cannot_wrap_quiet_weight_into_bright_output(self):
        context=self.context();context['scale']=511
        self.assertEqual(self.payload(context,0)[1],0)
        self.assertEqual(self.payload(context,511)[1],254)

    def test_unity_off_default_scaling_and_protected_partials(self):
        context=self.context();context['scale']=0
        self.assertEqual(self.payload(context,0)[1],199)
        context['scale']=256
        self.assertEqual(self.payload(context,128)[1],99)
        self.assertEqual(self.payload(context,0,partial=0)[1],49)

    def test_zero_velocity_nyquist_and_glide_identity(self):
        context=self.context();context['velocity']=0
        self.assertEqual(self.payload(context,256)[1],0)
        context['velocity']=255
        definition=(65535<<32)|(200<<24)
        payload=render(context,0,7,definition,False,[0x7fffff]*128,[256]*256,[256]*1024)
        self.assertEqual(payload[1],0)
        self.assertEqual(payload[4],(-100)&0x3ffff)

    def test_custom_definition_bypasses_legacy_spectrum(self):
        context=self.context();context.update(pad=65535,replace=1)
        self.assertEqual(self.payload(context,256,custom=True)[1],199)
        self.assertEqual(self.payload(context,256,custom=False)[1],254)

    def test_strike_curve_and_independent_envelope_fields(self):
        context=self.context();context.update(artic=1,artic_mask=65535,strike_k=12,curve=8,sustain=3)
        envelope=(1<<35)|(11<<11)|77
        payload=self.payload(context,256,partial=3,custom=True,envelope=envelope)
        self.assertEqual(payload[2],((3<<11)<<7)|(3<<5)|11)
        self.assertEqual(payload[3],envelope&~(15<<11))
        self.assertEqual(self.payload(context,256,partial=15,custom=True)[2],(3<<5)|5)

    def test_generation_is_deterministic_and_covers_four_slots(self):
        tables=([65536]*128,[(256<<32)|(200<<24)]*64,[256]*256,[256]*1024)
        commands,expected,coverage=generate(*tables,count=4)
        self.assertEqual((commands,expected,coverage),generate(*tables,count=4))
        self.assertEqual(len(expected),256)
        self.assertEqual({row[3] for row in expected},{0,1,2,3})

    def test_mutation_routing_and_trace_comparison_guards(self):
        original=(ROOT/'rtl/vel_shape_scaled.v').read_text(encoding='utf-8')
        self.assertNotEqual(mutate(original,'legacy-width','vel_shape_scaled.v'),original)
        self.assertEqual(mutate(original,'live-tilt','vel_shape_scaled.v'),original)
        with self.assertRaises(ValueError):
            mutate('wrong source','legacy-width','vel_shape_scaled.v')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.tsv';path.write_text('R 0 00000001 00 0 0 000100 10 000000 0000000000 00000\n')
            expected=[[0,1,0,0,0,256,17,0,0,0]]
            self.assertEqual(compare(expected,path)['field'],'amp')
            path.write_text('bad trace\n')
            self.assertEqual(compare(expected,path)['field'],'malformed-trace')


if __name__=='__main__':
    unittest.main()
