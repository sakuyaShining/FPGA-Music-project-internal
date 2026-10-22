// Volatile synthetic SDRAM stream bench. Audio outputs muted; no Flash/TF.
module sdram_board_top #(parameter FIFO_AW=10,RING_AW=17,
 NORMAL_SAMPLES=(1<<(RING_AW+1))+4096,RECOVERY_SAMPLES=4096,PREFILL=4096,HOLD_TICKS=4096,
 SAMPLE_DIV=512,FAST_DIV=32,HEARTBEAT=2700000,UART_BAUD=115200,WATCHDOG=810000000)(
 input wire clk,reset_button,
 output wire uart_tx_pin,output wire [5:0] led,
 output wire dac_din,dac_ws,dac_bck,pa_en,
 output wire O_sdram_clk,O_sdram_cke,O_sdram_cs_n,
 output wire O_sdram_ras_n,O_sdram_cas_n,O_sdram_wen_n,
 output wire [10:0] O_sdram_addr,output wire [1:0] O_sdram_ba,
 output wire [3:0] O_sdram_dqm,inout wire [31:0] IO_sdram_dq
);
 wire logic_clk,clock_locked;
`ifdef TIMING_RTL_SIM
 // Only for functional protocol simulation; not a model of PLL jitter/lock.
 assign logic_clk=clk;
 assign clock_locked=1'b1;
`else
 rPLL clocking(.CLKOUT(logic_clk),.LOCK(clock_locked),.CLKOUTP(),.CLKOUTD(),.CLKOUTD3(),
 .RESET(1'b0),.RESET_P(1'b0),.CLKIN(clk),.CLKFB(1'b0),
 .FBDSEL(6'd0),.IDSEL(6'd0),.ODSEL(6'd0),.PSDA(4'd0),.DUTYDA(4'd0),.FDLY(4'd0));
 defparam clocking.FCLKIN="27",clocking.DYN_IDIV_SEL="false",clocking.IDIV_SEL=0,
 clocking.DYN_FBDIV_SEL="false",clocking.FBDIV_SEL=0,clocking.DYN_ODIV_SEL="false",clocking.ODIV_SEL=32,
 clocking.PSDA_SEL="0000",clocking.DYN_DA_EN="true",clocking.DUTYDA_SEL="1000",
 clocking.CLKOUT_FT_DIR=1'b1,clocking.CLKOUTP_FT_DIR=1'b1,clocking.CLKOUT_DLY_STEP=0,
 clocking.CLKOUTP_DLY_STEP=0,clocking.CLKFB_SEL="internal",clocking.CLKOUT_BYPASS="false",
 clocking.CLKOUTP_BYPASS="false",clocking.CLKOUTD_BYPASS="false",clocking.DYN_SDIV_SEL=2,
 clocking.CLKOUTD_SRC="CLKOUT",clocking.CLKOUTD3_SRC="CLKOUT",clocking.DEVICE="GW2AR-18C";
`endif
 wire reset_assert=reset_button || !clock_locked;
 reg [1:0] reset_release=0;
 always @(posedge logic_clk or posedge reset_assert)
  if(reset_assert)reset_release<=0;else reset_release<={reset_release[0],1'b1};
 wire rst_n=reset_release[1];
 // Synthetic data integrity bench only; no TF/Flash or audio engine.
 localparam BOOT=0,PRIME=1,RUN=2,NORMAL_DONE=3,H_INJECT=4,H_REQ=5,H_WAIT=6,H_DONE=7,
 I_INJECT=8,I_REQ=9,I_WAIT=10,I_DONE=11,OVF=12,OV_DRAIN=13,MISS=14,R_REQ=15,R_WAIT=16,R_DONE=17,PASS=18,FAIL=19,FINAL_CHECK=20,FINAL_VERIFY=21;
 localparam [31:0] PREFIX=(32'd1<<RING_AW)+(32'd1<<FIFO_AW)+32'd1;
 reg [4:0] state;
 reg [1:0] epoch,clear_sent,clear_seen;
 reg [5:0] tests;
 reg [31:0] cycles,rec_count,rec_read,feed_count,played,normal_ticks,after_stop,prefix_count,misses,clear_count,hold_count,inflight_clears,requests;
 reg [31:0] failure_index;reg [15:0] observed,expected;reg [7:0] error_code;
 reg held_rec;reg [38:0] held_command;
 reg [3:0] prefix_mismatch;
 reg [$clog2(SAMPLE_DIV)-1:0] sample_div;
 reg [$clog2(FAST_DIV)-1:0] fast_div;
 wire normal_tick=sample_div==0,fast_tick=fast_div==0;
 wire [31:0] target=epoch==2?RECOVERY_SAMPLES:NORMAL_SAMPLES;
 wire clear_phase=state==H_REQ||state==H_WAIT||state==I_REQ||state==I_WAIT||state==R_REQ||state==R_WAIT;
 wire clear_request=state==H_REQ||state==I_REQ||state==R_REQ;
 wire rc=clear_request&&!clear_sent[0],pc=clear_request&&!clear_sent[1];
 wire rcr,pcr,rcd,pcd,rcb,pcb,rv,fr,pv,overflow,underflow,miss,mem_busy;
 wire [15:0] rec_data,play_data;
 wire [FIFO_AW:0] rec_fifo_level,play_fifo_level;
 wire [RING_AW:0] rec_ring_level,play_ring_level;
 wire normal=state==RUN;
 wire inject=state==H_INJECT||state==I_INJECT;
 wire rec_enable=(normal&&rec_count<target)||inject||state==OVF;
 wire pcm_tick=normal?normal_tick:fast_tick;
 wire play_enable=(normal&&played<target)||state==MISS;
 wire play_tick=normal?normal_tick:fast_tick;
 wire rec_ready=(normal&&!(normal_ticks>=target-HOLD_TICKS&&normal_ticks<target+HOLD_TICKS))||state==OV_DRAIN;
 wire feed_valid=((state==PRIME||normal)&&feed_count<target&&!(normal&&normal_ticks>=PREFILL&&normal_ticks<PREFILL+HOLD_TICKS))||inject;
 function [15:0] pattern;input[31:0] n;input[15:0] salt;
  begin pattern=n[15:0]^n[31:16]^salt;end
 endfunction
 wire [15:0] rec_salt=16'h1357^{14'd0,epoch};
 wire [15:0] play_salt=16'h9bdf^{14'd0,epoch};
 wire mv,mr,mw,sv,sr,controller_ready,initialized;wire [21:0] ma;wire [15:0] md,sd;
 wire memory_grant=!(state==H_INJECT||state==H_REQ||state==H_WAIT)||hold_count>=32;
 assign mr=controller_ready&&memory_grant;
 pcm_sdram_stream #(.FIFO_AW(FIFO_AW),.RING_AW(RING_AW)) stream(.clk(logic_clk),.rst_n(rst_n),
 .rec_clear(rc),.play_clear(pc),.rec_clear_ready(rcr),.play_clear_ready(pcr),.rec_clear_done(rcd),.play_clear_done(pcd),.rec_clearing(rcb),.play_clearing(pcb),
 .rec_enable(rec_enable),.pcm_valid(pcm_tick),.pcm_data(pattern(rec_count,rec_salt)^16'h1),
 .rec_valid(rv),.rec_ready(rec_ready),.rec_data(rec_data),.rec_level(rec_fifo_level),.play_level(play_fifo_level),
 .rec_ring_level(rec_ring_level),.play_ring_level(play_ring_level),.rec_overflow(overflow),
 .play_enable(play_enable),.sample_tick(play_tick),.feed_valid(feed_valid),.feed_ready(fr),.feed_data(pattern(feed_count,play_salt)),
 .play_valid(pv),.play_data(play_data),.play_underflow(underflow),.play_miss(miss),
 .mem_req_valid(mv),.mem_req_ready(mr),.mem_req_write(mw),.mem_req_addr(ma),.mem_req_data(md),
 .mem_rsp_valid(sv),.mem_rsp_ready(sr),.mem_rsp_data(sd),.mem_busy(mem_busy));
 sdram_word_controller ram(.clk(logic_clk),.rst_n(rst_n),.req_valid(mv&&memory_grant),.req_ready(controller_ready),.req_write(mw),.req_addr(ma),.req_data(md),
 .rsp_valid(sv),.rsp_ready(sr),.rsp_data(sd),.init_done(initialized),
 .sd_clk(O_sdram_clk),.sd_cke(O_sdram_cke),.sd_cs_n(O_sdram_cs_n),.sd_ras_n(O_sdram_ras_n),.sd_cas_n(O_sdram_cas_n),.sd_we_n(O_sdram_wen_n),
 .sd_addr(O_sdram_addr),.sd_bank(O_sdram_ba),.sd_dqm(O_sdram_dqm),.sd_dq(IO_sdram_dq));
 assign dac_din=0;assign dac_ws=0;assign dac_bck=0;assign pa_en=0;
 assign led=~{state==FAIL,state==PASS,tests[3],initialized,rst_n,mem_busy};
 // Pure combinational error selection; state/error registers have ONE writer.
 reg [7:0] pending_error;
 reg [31:0] pending_index;
 reg [15:0] pending_observed,pending_expected;
 always @*begin
  pending_error=0;pending_index=0;pending_observed=0;pending_expected=0;
  if(cycles>=WATCHDOG)begin pending_error=4;pending_index=cycles;end
  else if(rv&&rec_ready&&rec_data!==pattern(rec_read,rec_salt))begin
   pending_error=1;pending_index=rec_read;pending_observed=rec_data;pending_expected=pattern(rec_read,rec_salt);
  end else if(pv&&play_data!==pattern(played,play_salt))begin
   pending_error=2;pending_index=played;pending_observed=play_data;pending_expected=pattern(played,play_salt);
  end else if(normal&&(overflow||underflow||miss))begin
   pending_error=3;pending_index=normal_ticks;pending_observed={13'd0,overflow,underflow,miss};
  end else if((state==H_REQ||state==H_WAIT)&&hold_count<32&&((held_rec&&rcd)||(!held_rec&&pcd)))begin
   pending_error=5;pending_index=hold_count;
  end else if((state==H_REQ||state==H_WAIT)&&hold_count<32&&(!mv||{mw,ma,md}!==held_command))begin
   pending_error=6;pending_index=hold_count;pending_observed=md;pending_expected=held_command[15:0];
  end else if(state==OV_DRAIN&&rec_read>PREFIX)begin pending_error=7;pending_index=rec_read;end
  else if(state==MISS&&(pv||!overflow))begin pending_error=8;pending_index=misses;end
  else if((state==H_DONE||state==I_DONE||state==R_DONE)&&(overflow||underflow))begin
   pending_error=9;pending_index=clear_count;pending_observed={14'd0,overflow,underflow};
  end else if(state==I_DONE&&inflight_clears==0)pending_error=10;
  else if(state==FINAL_VERIFY)begin
   if(tests!=6'h1f)begin pending_error=11;pending_observed={10'd0,tests};pending_expected=16'h1f;end
   else if(prefix_mismatch!=0)begin pending_error=12;pending_index={28'd0,prefix_mismatch};pending_observed=prefix_count[15:0];pending_expected=PREFIX[15:0];end
   else if(clear_count!=6)begin pending_error=13;pending_index=clear_count;pending_observed=clear_count[15:0];pending_expected=6;end
   else if(after_stop==0)begin pending_error=14;pending_expected=1;end
  end
 end
 task reset_counts;
  begin rec_count<=0;rec_read<=0;feed_count<=0;played<=0;normal_ticks<=0;end
 endtask
 always @(posedge logic_clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=BOOT;epoch<=0;tests<=0;clear_sent<=0;clear_seen<=0;cycles<=0;
   rec_count<=0;rec_read<=0;feed_count<=0;played<=0;normal_ticks<=0;after_stop<=0;
   prefix_count<=0;misses<=0;clear_count<=0;hold_count<=0;inflight_clears<=0;requests<=0;
   failure_index<=0;observed<=0;expected<=0;error_code<=0;held_rec<=0;held_command<=0;sample_div<=0;fast_div<=0;prefix_mismatch<=0;
  end else begin
   if(state!=PASS&&state!=FAIL)cycles<=cycles+1'b1;
   if(sample_div==SAMPLE_DIV-1)sample_div<=0;else sample_div<=sample_div+1'b1;
   if(fast_div==FAST_DIV-1)fast_div<=0;else fast_div<=fast_div+1'b1;
   if(rec_enable&&pcm_tick&&!rcb&&!overflow)rec_count<=rec_count+1'b1;
   if(rv&&rec_ready)begin
    rec_read<=rec_read+1'b1;
    if(normal&&rec_count>=target)after_stop<=after_stop+1'b1;
   end
   if(feed_valid&&fr)feed_count<=feed_count+1'b1;
   if(pv)played<=played+1'b1;
   if(normal&&normal_tick)normal_ticks<=normal_ticks+1'b1;
   if(mv&&mr)requests<=requests+1'b1;
   if(rcd||pcd)clear_count<=clear_count+{31'd0,rcd}+{31'd0,pcd};
   if(clear_phase)begin
    if(rc&&rcr)clear_sent[0]<=1;
    if(pc&&pcr)clear_sent[1]<=1;
    if(rcd)clear_seen[0]<=1;
    if(pcd)clear_seen[1]<=1;
   end
   if((state==H_REQ||state==H_WAIT)&&hold_count<32)hold_count<=hold_count+1'b1;
   if(state==I_REQ&&mem_busy&&!mv&&((rc&&rcr)||(pc&&pcr)))inflight_clears<=inflight_clears+1'b1;
   case(state)
    BOOT:if(initialized)state<=PRIME;
    PRIME:if(feed_count>=PREFILL)begin state<=RUN;normal_ticks<=0;end
    RUN:if(rec_read==target&&played==target&&feed_count==target&&rec_count==target&&
     rec_fifo_level==0&&rec_ring_level==0&&play_fifo_level==0&&play_ring_level==0&&!mem_busy&&!rv)state<=NORMAL_DONE;
    NORMAL_DONE:if(epoch==0)begin
     tests[0]<=1;state<=H_INJECT;epoch<=1;reset_counts();clear_sent<=0;clear_seen<=0;
    end else state<=FINAL_CHECK;
    H_INJECT:if(mv)begin held_rec<=!ma[RING_AW];held_command<={mw,ma,md};state<=H_REQ;end
    H_REQ:if(clear_sent==3)state<=H_WAIT;
    H_WAIT:if(clear_seen==3)state<=H_DONE;
    H_DONE:begin tests[1]<=1;state<=I_INJECT;reset_counts();clear_sent<=0;clear_seen<=0;end
    I_INJECT:if(mem_busy&&!mv)state<=I_REQ;
    I_REQ:if(clear_sent==3)state<=I_WAIT;
    I_WAIT:if(clear_seen==3)state<=I_DONE;
    I_DONE:begin tests[2]<=1;state<=OVF;epoch<=3;reset_counts();end
    OVF:if(overflow)state<=OV_DRAIN;
    OV_DRAIN:if(rec_read==PREFIX&&rec_fifo_level==0&&rec_ring_level==0&&!rv&&!mem_busy)begin
     tests[3]<=1;prefix_count<=rec_read;state<=MISS;
    end
    MISS:if(miss)begin
     misses<=misses+1'b1;
     if(misses==7)begin tests[4]<=1;state<=R_REQ;clear_sent<=0;clear_seen<=0;end
    end
    R_REQ:if(clear_sent==3)state<=R_WAIT;
    R_WAIT:if(clear_seen==3)state<=R_DONE;
    R_DONE:begin state<=PRIME;epoch<=2;reset_counts();end
    FINAL_CHECK:begin
     prefix_mismatch[0]<=|(prefix_count[7:0]^PREFIX[7:0]);
     prefix_mismatch[1]<=|(prefix_count[15:8]^PREFIX[15:8]);
     prefix_mismatch[2]<=|(prefix_count[23:16]^PREFIX[23:16]);
     prefix_mismatch[3]<=|(prefix_count[31:24]^PREFIX[31:24]);
     state<=FINAL_VERIFY;
    end
    FINAL_VERIFY:if(pending_error==0)begin tests[5]<=1;state<=PASS;end
    default:;
   endcase
   if(state!=PASS&&state!=FAIL&&pending_error!=0)begin
    state<=FAIL;error_code<=pending_error;failure_index<=pending_index;
    observed<=pending_observed;expected<=pending_expected;
   end
  end
 end
 // Atomic 64-byte UART snapshot, 115200 8N1. XOR covers bytes0..62.
 reg [$clog2(HEARTBEAT+1)-1:0] heartbeat;
 reg [511:0] frame,snapshot;reg [6:0] byte_index;reg transmitting,start;
 wire tx_done,tx_busy;reg [7:0] tx_byte,checksum;integer k;
 always @*begin
  snapshot=0;snapshot[0+:8]=8'ha5;snapshot[8+:8]=8'h83;snapshot[16+:8]=1;snapshot[24+:8]={3'd0,state};
  snapshot[32+:8]={1'b0,mem_busy,clock_locked,underflow,overflow,initialized,state==FAIL,state==PASS};
  snapshot[40+:8]={2'd0,tests};snapshot[48+:32]=cycles;
  snapshot[80+:32]=rec_count;snapshot[112+:32]=rec_read;snapshot[144+:32]=feed_count;snapshot[176+:32]=played;
  snapshot[208+:32]=after_stop;snapshot[240+:32]=prefix_count;snapshot[272+:32]=misses;
  snapshot[304+:32]=clear_count;snapshot[336+:32]=hold_count;snapshot[368+:32]=inflight_clears;
  snapshot[400+:32]=failure_index;snapshot[432+:16]=observed;snapshot[448+:16]=expected;snapshot[464+:8]=error_code;
  snapshot[472+:32]=requests;checksum=0;
  for(k=0;k<63;k=k+1)checksum=checksum^snapshot[k*8+:8];snapshot[504+:8]=checksum;
 end
 uart_tx #(.CLK_HZ(27000000),.BAUD(UART_BAUD)) serial(.clk(logic_clk),.rst_n(rst_n),.tx_data(tx_byte),.tx_start(start),.tx(uart_tx_pin),.busy(tx_busy),.done(tx_done));
 always @(posedge logic_clk or negedge rst_n)begin
  if(!rst_n)begin heartbeat<=0;frame<=0;byte_index<=0;transmitting<=0;start<=0;tx_byte<=0;end
  else begin
   start<=0;if(heartbeat==HEARTBEAT-1)heartbeat<=0;else heartbeat<=heartbeat+1'b1;
   if(!transmitting&&heartbeat==0)begin frame<=snapshot;byte_index<=0;transmitting<=1;end
   else if(transmitting&&!tx_busy&&!start)begin
    if(byte_index<64)begin tx_byte<=frame[byte_index*8+:8];start<=1;byte_index<=byte_index+1'b1;end
    else transmitting<=0;
   end
  end
 end
endmodule
