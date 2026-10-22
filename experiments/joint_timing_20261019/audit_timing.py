"""Static probe qualification only; this harness has no board programming gate."""
from common import *
import html,re,xml.etree.ElementTree as ET
def rows(s):
    return [[html.unescape(re.sub('<[^>]*>','',v)).strip() for v in re.findall(r'<td\b[^>]*>(.*?)</td>',r,re.S|re.I)] for r in re.findall(r'<tr\b[^>]*>(.*?)</tr>',s,re.S|re.I)]
def timing(text):
    slacks={};paths={}
    for kind in ('Setup','Hold','Recovery','Removal'):
        m=re.search(r'name="'+kind+r'_Slack_Table"(.*?)(?=<a name=|\Z)',text,re.S);assert m,kind
        paths[kind]=[v for v in rows(m[1]) if len(v)>=9 and v[0].isdigit()];assert paths[kind],kind
        slacks[kind]=min(float(v[1]) for v in paths[kind])
    return dict(slack_ns=slacks,worst_paths={k:min(v,key=lambda r:float(r[1])) for k,v in paths.items()})
def constraints(text):
    assert 'create_generated_clock -name sdram_forward' in text
    assert 'get_pins {clocking/CLKOUT}' in text and 'create_generated_clock -name core_clk' in text
    for command in ('set_input_delay','set_output_delay'):
        for mode in ('-max','-min'):
            lines=[l for l in text.splitlines() if l.startswith(command) and mode in l]
            assert len(lines)==1 and 'IO_sdram_dq[*]' in lines[0],(command,mode)
    for token in ('O_sdram_addr[*]','O_sdram_ba[*]','O_sdram_dqm[*]','O_sdram_ras_n','O_sdram_cas_n','O_sdram_wen_n'):
        assert all(token in l for l in text.splitlines() if l.startswith('set_output_delay')),token
    for l in text.splitlines():
        if l.startswith(('set_false_path','set_clock_groups','set_multicycle_path')):
            assert l in ('set_false_path -from [get_ports {reset_button}]','set_false_path -to [get_ports {led[*] probe_out}]','set_false_path -from [get_ports {scan_in}]'),l
    assert 'set_clock_uncertainty -setup' in text and 'set_clock_uncertainty -hold' in text
def accepted(r):return all(v>=0 for v in r['slack_ns'].values())
def audit(folder,mode):
    D=R/folder;d=json.loads((D/'run.json').read_text(encoding='utf-8'))
    assert d['returncode']==0 and d['status'].startswith('build completed')
    for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256'],(folder,name)
    assert sha(D/'board.gprj')==d['project_sha256'] and sha(D/'build.tcl')==d['tcl_sha256']
    constraints((D/('sdram_board.sdc' if mode=='nominal' else 'stress.sdc')).read_text())
    Q=D/'impl/pnr';result=timing((Q/'board_tr_content.html').read_text(encoding='utf-8'))
    pins=rows((Q/'board.pin.html').read_text(encoding='utf-8'))
    sip=[v for v in pins if len(v)>7 and (v[0].startswith('O_sdram') or v[0].startswith('IO_sdram'))]
    assert len(sip)==55 and all(v[2].startswith('p') and v[7]=='LVTTL33' for v in sip)
    external={v[0]:int(v[2].split('/')[0]) for v in pins if len(v)>7 and '/' in v[2] and not v[2].startswith('p') and v[4] in ('in','out','io')}
    expected={'clk':4,'reset_button':87,'scan_in':70,'probe_out':69,'pa_en':51,'dac_din':54,'dac_ws':55,'dac_bck':56,**{'led[%d]'%i:15+i for i in range(6)}}
    assert external==expected,external
    report=(Q/'board.rpt.txt').read_text();metrics={}
    for key in ('Logic','Register','BSRAM','I/O Port'):
        m=re.search(r'^\s*'+re.escape(key)+r'\s*\|\s*(\d+)',report,re.M);assert m,key;metrics[key]=int(m[1])
    assert 'logic_clk' in report and 'PRIMARY' in report and 'rPLL' in report
    log=(D/'console.log').read_text();assert not re.search(r'\bERROR\s*\(',log) and 'Bitstream generation completed' in log
    root=ET.parse(D/'impl/gwsynthesis/board_syn_rsc.xml').getroot();hierarchy={}
    def walk(n,p=''):
        p+=('/' if p else '')+n.get('name');hierarchy[p]=n.attrib
        for c in n:walk(c,p)
    walk(root)
    required=('music/layers','music/bridge','music/control','music/core/u_tdm/u_pmod','music/core/u_fx',
        'visualizer/u_fft','visualizer/u_renderer','sensor/scanner','sensor/store','sensor/positions',
        'transport/arbiter','transport/buffers/recording','transport/buffers/playback','sdram')
    for p in required:assert 'joint_timing_top/system/'+p in hierarchy,p
    result.update(resource=metrics,logic_spare=20736-metrics['Logic'],bitstream_sha256=sha(Q/'board.fs'),
        sip_ports={v[0]:v[2] for v in sip},external_pins=external,hierarchy=hierarchy,
        warnings=[v for v in log.splitlines() if 'WARN' in v],static_pass=accepted(result),bench_gate=False)
    return result
if __name__=='__main__':
    builds={'nominal':'build_nominal_v5','stress':'build_stress_v5'};selected={};build_inputs=[]
    for mode,folder in builds.items():
        D=R/folder
        if not (D/'run.json').exists():
            selected[mode]=dict(status='NOT RUN / not completed',static_pass=False,slack_ns=None);continue
        d=json.loads((D/'run.json').read_text(encoding='utf-8'));build_inputs.append(D/'run.json')
        if d['returncode']!=0 or not d['status'].startswith('build completed'):
            for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256'],(folder,name)
            log=(D/'console.log').read_text(encoding='utf-8',errors='replace');build_inputs.append(D/'console.log')
            errors=[l for l in log.splitlines() if re.search(r'\bERROR\s*\(',l)]
            selected[mode]=dict(status='FAIL build: no routed timing result',errors=errors,static_pass=False,slack_ns=None)
        else:
            selected[mode]=audit(folder,mode)
            build_inputs += [D/'impl/pnr/board_tr_content.html',D/'impl/pnr/board.pin.html',D/'impl/pnr/board.rpt.txt',D/'impl/gwsynthesis/board_syn_rsc.xml']
    for name in ('joint-model','delta-model','sensor-model','native-model','pitch-model','engine-compatibility'):
        d=json.loads((E/(name+'.json')).read_text(encoding='utf-8'));assert d['status'].startswith('PASS')
        for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
    source=(R/'rtl/joint_timing_top.v').read_text()
    assert source.count('scan_in;')==1 and 'scan_meta<=scan_in;scan_sync<=scan_meta' in source
    # Demonstrate that missing I/O timing and a negative hold path cannot pass.
    text=(R/'constraints/sdram_board.sdc').read_text();detected=[]
    for needle in ('set_input_delay -clock sdram_forward -min','set_output_delay -clock sdram_forward -max'):
        damaged='\n'.join(l for l in text.splitlines() if not l.startswith(needle))
        try:constraints(damaged)
        except AssertionError:detected.append(needle)
        else:raise AssertionError('missing constraint accepted')
    synthetic=dict(slack_ns=dict(Setup=1.0,Hold=-.001,Recovery=1.,Removal=1.))
    assert not accepted(synthetic);detected.append('negative hold despite any summary TNS')
    up=json.loads((R/'upstream.json').read_text(encoding='utf-8'));changed=[]
    for rel,h in up['files'].items():
        if Path(rel).parts[0] in ('engine','rtl') and sha(R/rel)!=h:changed.append(rel)
    assert set(changed)=={'engine/src/rc_delta_store.v','engine/src/pitch_mod.v'},changed
    assert (R/'engine/src/pitch_native_store.v').is_file()
    status='PASS declared-envelope structural joint static timing' if all(v['static_pass'] for v in selected.values()) else 'FAIL declared-envelope structural joint static timing'
    inputs=[Path(__file__).resolve(),R/'common.py',R/'upstream.json',R/'project/scan-map.json',*sources(),
        R/'constraints/sdram_board.cst',R/'constraints/sdram_board.sdc',R/'reference/stress.sdc',
        *[E/(n+'.json') for n in ('joint-model','delta-model','sensor-model','native-model','pitch-model','engine-compatibility')]]
    inputs+=build_inputs
    record=dict(status=status,selected=selected,builds=builds,changed_upstream=changed,detected_false_green_cases=detected,
        bench_gate=False,production_qualified=False,hardware_programmed=False,
        limitations=['structural scan input is not musical command protocol','integration simulation forces controls; no real scan event delivery',
            'parity observation adds load and can cancel some correlated signals','exact die/package/temperature delays unbound',
            'no physical display/touch/DAC timing qualification','worst25 paths per category','raw PLL clock warning retained'],
        inputs={p.relative_to(R).as_posix():sha(p) for p in inputs})
    (E/'timing-audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=status,bench_gate=False,nominal=selected['nominal']['slack_ns'],stress=selected['stress']['slack_ns'],resources=selected['nominal'].get('resource'))))
