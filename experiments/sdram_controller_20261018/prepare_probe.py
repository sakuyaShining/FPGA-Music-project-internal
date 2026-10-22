from common import *
original=(R/'rtl/storage_probe.v').read_text(encoding='utf-8')
ports='''
 input wire sdram_req_valid,sdram_req_write,sdram_rsp_ready,
 input wire [21:0] sdram_req_addr,input wire [15:0] sdram_req_data,
 output wire sdram_req_ready,sdram_rsp_valid,sdram_init_done,
 output wire [15:0] sdram_rsp_data,
 output wire sd_clk,sd_cke,sd_cs_n,sd_ras_n,sd_cas_n,sd_we_n,
 output wire [10:0] sd_addr,output wire [1:0] sd_bank,
 output wire [3:0] sd_dqm,inout wire [31:0] sd_dq,
'''
text=original.replace('module storage_probe','module sdram_storage_probe',1).replace('(\n','(\n'+ports,1)
body='''
sdram_word_controller sdram(.clk(clk),.rst_n(rst_n),
 .req_valid(sdram_req_valid),.req_ready(sdram_req_ready),.req_write(sdram_req_write),
 .req_addr(sdram_req_addr),.req_data(sdram_req_data),
 .rsp_valid(sdram_rsp_valid),.rsp_ready(sdram_rsp_ready),.rsp_data(sdram_rsp_data),.init_done(sdram_init_done),
 .sd_clk(sd_clk),.sd_cke(sd_cke),.sd_cs_n(sd_cs_n),.sd_ras_n(sd_ras_n),.sd_cas_n(sd_cas_n),.sd_we_n(sd_we_n),
 .sd_addr(sd_addr),.sd_bank(sd_bank),.sd_dqm(sd_dqm),.sd_dq(sd_dq));
'''
stub='''
assign sdram_req_ready=0;assign sdram_rsp_valid=0;assign sdram_rsp_data=0;assign sdram_init_done=0;
assign sd_clk=0;assign sd_cke=0;assign sd_cs_n=1;assign sd_ras_n=1;assign sd_cas_n=1;assign sd_we_n=1;
assign sd_addr=0;assign sd_bank=0;assign sd_dqm=4'hf;assign sd_dq=32'bz;
'''
(R/'rtl/sdram_storage_probe.v').write_text(text.replace('endmodule',body+'\nendmodule'),encoding='utf-8')
(R/'reference/sdram_storage_probe.v').write_text(text.replace('endmodule',stub+'\nendmodule'),encoding='utf-8')
p=R/'synthesize.py';s=p.read_text();s=s.replace("R/'reference/storage_probe.v' if p.name=='storage_probe.v'","R/'reference/sdram_storage_probe.v' if p.name=='sdram_storage_probe.v'").replace("else 'storage_probe'","else 'sdram_storage_probe'")
p.write_text(s)
print('Prepared logical resource probes; FIFO-to-SDRAM arbitration still pending')
