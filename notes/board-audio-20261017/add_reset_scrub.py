from pathlib import Path
import shutil
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017';S=R/'src';ref=R/'reference';ref.mkdir(exist_ok=True)
p=S/'tdm_top_owned.v';s=p.read_text(encoding='utf-8')
if 'parameter integer BOARD_BOOT_SCRUB' not in s:
    shutil.copyfile(p,ref/'tdm_top_before_scrub.v')
    shutil.copyfile(R/'evidence/run-tb_board_audio.log',R/'evidence/pre-scrub-reset-failure.log')
    def once(a,b):
        global s
        assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
    once('parameter integer DIAG_FINGER=1,','parameter integer BOARD_BOOT_SCRUB=0, parameter integer DIAG_FINGER=1,')
    once('    wire select_owned=','''    // First pass releases every slot. After pending writes settle, a second
    // gate-off pass replaces stale amplitudes (release-only preserves them).
    // Ordinary note loading resumes only after the quiet fence completes.
    reg [12:0] boot_scrub_count;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)boot_scrub_count<=0;
        else if(boot_scrub_count<13'd4096)boot_scrub_count<=boot_scrub_count+1'b1;
    wire boot_scrub_busy=BOARD_BOOT_SCRUB&&boot_scrub_count<13'd4096;
    wire boot_scrub_write=BOARD_BOOT_SCRUB&&((boot_scrub_count<13'd512)||
        (boot_scrub_count>=13'd2048&&boot_scrub_count<13'd2560));
    wire select_owned=''')
    once('&& !spec_commit_pending;', '&& !spec_commit_pending && !boot_scrub_busy;')
    for name,width in [('load_en',''),('load_slot',''),('load_inc',''),('load_amp',''),('load_gate',''),('load_epar',''),('load_gq','')]:
        # Preserve the declared widths/signedness and original mode expression.
        import re
        pattern=r'(wire\s+(?:signed\s+)?(?:\[[^\]]+\]\s+)?'+name+r'\s*=\s*)([^;]+);'
        m=re.search(pattern,s);assert m,(name,'declaration missing')
        value={'load_en':"1'b1",'load_slot':'boot_scrub_count[8:0]','load_inc':"24'd0",'load_amp':"8'd0",'load_gate':"1'b0",'load_epar':"23'd0",'load_gq':"18'sd0"}[name]
        s=s[:m.start(2)]+'boot_scrub_write ? '+value+' : ('+m.group(2)+')'+s[m.end(2):]
    once('.load_start_tag(test_mode_eff ? 8\'d0 : nm_load_start_tag)',".load_start_tag(boot_scrub_write ? 8'd0 : (test_mode_eff ? 8'd0 : nm_load_start_tag))")
    p.write_text(s,encoding='utf-8')
p=S/'left_layer_music_probe.v';s=p.read_text(encoding='utf-8')
if 'BOARD_BOOT_SCRUB' not in s:
    s=s.replace('DIAG_CAPTURE_SAMPLES=2048)(', 'DIAG_CAPTURE_SAMPLES=2048,BOARD_BOOT_SCRUB=0)(').replace('.DIAG_FINGER(0)', '.DIAG_FINGER(0),.BOARD_BOOT_SCRUB(BOARD_BOOT_SCRUB)');p.write_text(s,encoding='utf-8')
p=R/'rtl/board_audio_top.v';s=p.read_text(encoding='utf-8').replace('.BOARD_DIAG(1),.UART_BAUD', '.BOARD_DIAG(1),.BOARD_BOOT_SCRUB(1),.UART_BAUD');p.write_text(s,encoding='utf-8')
print('Prepared board-only two-pass slot quiet fence, legacy default disabled')
