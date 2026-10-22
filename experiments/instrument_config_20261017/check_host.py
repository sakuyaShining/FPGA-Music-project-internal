from common import *
import sys,copy,unittest,io,random
sys.path.insert(0,str(R/'host'))
from instrument_config import default_config
from config_adapter import encode,decode,compile_document,fit_attack,fit_exp,exp_steps
class Checks(unittest.TestCase):
    def test_roundtrip(self):
        words,report=compile_document(default_config());self.assertEqual(encode(decode(words)),words);self.assertEqual(len(words),16)
    def test_modes(self):
        for mode in ('sustain','strike','hybrid'):
            doc=default_config(mode=mode);parts=decode(compile_document(doc)[0]);expected=[0 if (mode=='strike' or mode=='hybrid' and i>=8) else round(192*32768/255) for i in range(16)];self.assertEqual([p['sustain_q15'] for p in parts],expected)
    def test_add_saturates(self):
        d=default_config();d['spectrum_mode']='add';d['spectrum']=[255]*16;self.assertEqual([p['amplitude'] for p in decode(compile_document(d)[0])],[255]*16)
    def test_preset_ratios(self):
        rom=[int(x,16) for x in (R/'src/preset_part.hex').read_text().split()]
        for i in range(4):
            d=default_config();d['preset']=i;self.assertEqual([p['ratio_q8'] for p in decode(compile_document(d)[0])],[(x>>32)&65535 for x in rom[i*16:(i+1)*16]])
    def test_unsupported(self):
        for name in ('vibrato','delay','chorus','reverb','dry'):
            d=default_config()
            if name=='vibrato':d['vibrato']['enabled']=True
            elif name=='dry':d['effects']['dry_enabled']=False
            else:d['effects'][name]['enabled']=True
            with self.assertRaisesRegex(ValueError,'not applied'):compile_document(d)
    def test_input_unchanged(self):
        d=default_config();before=copy.deepcopy(d);compile_document(d);self.assertEqual(d,before)
    def test_width_reserved(self):
        words,_=compile_document(default_config())
        for bit in (23,84,87,88):
            bad=words[:];bad[2]|=1<<bit
            with self.assertRaises(ValueError):decode(bad)
    def test_field_validation(self):
        parts=decode(compile_document(default_config())[0])
        for field,value in [('attack_inc',0),('attack_shift',16),('release_m',0),('decay_shift',True),('sustain_q15',32769),('ratio_q8',0)]:
            bad=copy.deepcopy(parts);bad[0][field]=value
            with self.assertRaises(ValueError):encode(bad)
    def test_unknown_schema(self):
        d=default_config();d['new_field']=1
        with self.assertRaises(ValueError):compile_document(d)
    def test_timing_quantized(self):
        for ms in (0,1,5,12,200,600,2000,60000):
            a=fit_attack(ms);self.assertLessEqual(abs(a['nominal_ms']-ms),max(1.,ms*.02));self.assertLessEqual(a['phase_jitter_bound_ms'],max(1.,ms*.01))
            r=fit_exp(ms,100);self.assertLessEqual(abs(r['nominal_ms']-ms),max(1.,ms*.02))
    def test_random_encodings(self):
        rng=random.Random(538);base=decode(compile_document(default_config())[0])
        for _ in range(100):
            p=copy.deepcopy(base);i=rng.randrange(16);p[i].update(attack_inc=rng.randrange(1,32769),attack_shift=rng.randrange(16),release_shift=rng.randrange(16),decay_shift=rng.randrange(16));self.assertEqual(decode(encode(p)),p)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks);stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(E/'host-tests.log').write_text(stream.getvalue(),encoding='utf-8');assert result.wasSuccessful(),stream.getvalue()
fixtures=[]
for name,mode,attack,release,decay,sustain,spectrum in [('fast','sustain',1,2,0,255,[80]+[0]*15),('slow','sustain',12,40,0,255,[70]+[0]*15),('hybrid','hybrid',1,10,1,160,[100,40]+[0]*14),('strike','strike',0,5,2,0,[90]+[0]*15)]:
    d=default_config(name,mode);d['articulation'].update(attack_ms=attack,release_ms=release,decay_ms=decay,sustain_level=sustain,hybrid_parts=['sustain','strike']+['strike']*14);d['spectrum']=spectrum
    words,report=compile_document(d);(R/('config-'+name+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');(R/('config-'+name+'.hex')).write_text(''.join('%022x\n'%w for w in words),encoding='ascii');fixtures.append(dict(name=name,report=report))
inputs=[Path(__file__).resolve(),R/'common.py',R/'host/config_adapter.py',R/'host/instrument_config.py',R/'src/preset_part.hex']
(E/'host-validation.json').write_text(json.dumps(dict(status='PASS compiler checks only; no UART application',tests=result.testsRun,fixtures=fixtures,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs}),indent=2),encoding='utf-8');print('PASS compiler checks',result.testsRun)
