"""Exhaustive original-vs-candidate background pixels, including 9-bit offscreen inputs."""
from common import *
import sys
if '--finalize-existing' in sys.argv:
    # The first run completed both simulations, then failed only when storing
    # this script's relative path. Verify the captured compiler input identities
    # before repairing metadata; do not rerun or relabel failed RTL.
    original=json.loads((E/'compile-renderer-inputs.json').read_text())
    assert original['returncode']==0
    assert all(sha(Path(p))==h for p,h in original['inputs'].items())
    log=(E/'run-renderer.log').read_text()
    negative=(E/'bad-renderer.log').read_text()
    assert 'PASS exhaustive renderer 8388608 pixels' in log
    assert 'FATAL:' in negative and 'pixel mismatch' in negative
    (E/'renderer-equivalence.json').write_text(json.dumps(dict(status='PASS',comparisons=8388608,log=log,negative=negative,
        metadata_repair='Original simulation passed; relative __file__ serialization failed. Verified captured input hashes before recording.',
        inputs=original['inputs'],checker_sha256=sha(Path(__file__).resolve())),indent=2),encoding='utf-8')
    print('PASS finalized existing exhaustive and negative evidence; input hashes verified')
    sys.exit(0)
tb = r'''`timescale 1ns/1ps
module tb_renderer;
mv_renderer_before gold(.clk(1'b0),.rst_n(1'b1));
mv_renderer dut(.clk(1'b0),.rst_n(1'b1));
integer bank,seen,x,y,n=0;
reg [15:0] a,b;
initial begin
 for(bank=0;bank<16;bank=bank+1)for(seen=0;seen<2;seen=seen+1) begin
  gold.frame_layers=bank;dut.frame_layers=bank;
  gold.frame_seen=seen;dut.frame_seen=seen;
  for(y=0;y<512;y=y+1)for(x=0;x<512;x=x+1)begin
   a=gold.background(x[8:0],y[8:0]);b=dut.background(x[8:0],y[8:0]);
   if(a!==b)$fatal(1,"pixel mismatch x=%0d y=%0d bank=%0d seen=%0d old=%h new=%h",x,y,bank,seen,a,b);
   n=n+1;
  end
 end
 $display("PASS exhaustive renderer %0d pixels, all x/y/layers/seen",n);$finish;
end
endmodule
'''
p=R/'tb/tb_renderer.v';p.write_text(tb,encoding='utf-8')
files=[R/'reference/mv_renderer_before.v',R/'engine/src/mv_renderer.v',R/'engine/src/mv_panel_driver.v',R/'engine/src/mv_spi_byte.v',p]
run([IV,'-g2012','-I',str(R/'engine/src'),'-s','tb_renderer','-o',str(E/'renderer.vvp'),*map(str,files)],'compile-renderer')
log=run([VVP,str(E/'renderer.vvp')],'run-renderer',timeout=300)
bad=E/'bad_renderer.v'
source=(R/'engine/src/mv_renderer.v').read_text()
assert source.count('x>=26&&x<40')==1
bad.write_text(source.replace('x>=26&&x<40','x>=27&&x<40'),encoding='utf-8')
run([IV,'-g2012','-I',str(R/'engine/src'),'-s','tb_renderer','-o',str(E/'bad-renderer.vvp'),*[str(bad if f.name=='mv_renderer.v' else f) for f in files]],'compile-bad-renderer')
out=subprocess.run([VVP,str(E/'bad-renderer.vvp')],capture_output=True,text=True,timeout=30)
(E/'bad-renderer.log').write_text(out.stdout+out.stderr,encoding='utf-8')
assert out.returncode!=0 and 'pixel mismatch' in out.stdout,out.stdout+out.stderr
(E/'renderer-equivalence.json').write_text(json.dumps(dict(status='PASS',comparisons=8388608,log=log,negative=out.stdout,inputs={str(f.relative_to(R)):sha(f) for f in files+[R/'engine/src/mv_font.vh',Path(__file__).resolve()]}),indent=2),encoding='utf-8')
print('PASS one-pixel boundary mutation rejected')
