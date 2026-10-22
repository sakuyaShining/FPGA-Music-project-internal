// Independent command/timing monitor and data store. Subset model, not a
// vendor die model: BL1/CAS3, explicit precharge, no power-down/self-refresh.
`timescale 1ns/1ps
module sdram_timing_model(
 input wire clk,cke,cs_n,ras_n,cas_n,we_n,
 input wire [10:0] addr,input wire [1:0] ba,input wire [3:0] dqm,
 inout wire [31:0] dq,input wire operational,
 output integer refreshes=0,reads=0,writes=0,max_refresh_gap=0
);
 reg [31:0] memory[0:2097151];
 reg [10:0] rows[0:3];reg [3:0] opened=0;
 integer active_at[0:3],pre_at[0:3],write_at[0:3];
 integer cycle=0,refresh_at=-10000,deadline_at=-10000,mode_at=-10000,pending=0,index,i,j,gap,init_refs=0;
 reg mode_set=0,driving=0;reg [31:0] drive_data,pending_data;
 reg was_operational=0;
 assign dq=driving?drive_data:32'bz;
 initial for(i=0;i<4;i=i+1)begin active_at[i]=-10000;pre_at[i]=-10000;write_at[i]=-10000;end
 always @(posedge clk)begin
  cycle=cycle+1;driving<=#3 0;
  if(pending>0)begin
   pending=pending-1;
   if(pending==0)begin drive_data<=#3 pending_data;driving<=#3 1;end
  end
  if(operational && !was_operational)deadline_at=cycle;
  was_operational=operational;
  if(operational)begin
   gap=cycle-deadline_at;if(gap>max_refresh_gap)max_refresh_gap=gap;
   if(gap>421)$fatal(1,"refresh deadline cycle=%0d gap=%0d",cycle,gap);
  end
  if(cke && !cs_n && {ras_n,cas_n,we_n}!=3'b111)begin
   if(cycle-refresh_at<9)$fatal(1,"tRFC");
   if(cycle-mode_at<3)$fatal(1,"tMRD");
   case({ras_n,cas_n,we_n})
    3'b010:begin
     if(cycle<5400)$fatal(1,"power up wait");
     for(j=0;j<4;j=j+1)if(addr[10]||ba==j)begin
      if(opened[j]&&cycle-active_at[j]<6)$fatal(1,"tRAS");
      if(cycle-write_at[j]<3)$fatal(1,"tWR");
      opened[j]=0;pre_at[j]=cycle;
     end
    end
    3'b001:begin
     if(opened!=0)$fatal(1,"refresh with open row");
     for(j=0;j<4;j=j+1)if(cycle-pre_at[j]<3)$fatal(1,"refresh tRP");
     refreshes=refreshes+1;refresh_at=cycle;deadline_at=cycle;init_refs=init_refs+1;
    end
    3'b000:begin
     if(opened!=0||init_refs<2||addr!==11'h030||ba!=0)$fatal(1,"mode/init sequence");
     mode_set=1;mode_at=cycle;init_refs=0;
    end
    3'b011:begin
     if(!mode_set||opened[ba]||cycle-pre_at[ba]<3)$fatal(1,"ACT mode/open/tRP");
     rows[ba]=addr;opened[ba]=1;active_at[ba]=cycle;
    end
    3'b100,3'b101:begin
     if(!opened[ba]||cycle-active_at[ba]<3||addr[10:8]!=0)$fatal(1,"column/tRCD");
     index={ba,rows[ba],addr[7:0]};
     if(!we_n)begin
      if(driving)$fatal(1,"DQ contention");
      for(j=0;j<4;j=j+1)if(!dqm[j])begin
       if((^dq[j*8+:8])===1'bx)$fatal(1,"write unknown/Z");
       memory[index][j*8+:8]=dq[j*8+:8];
      end
      write_at[ba]=cycle;writes=writes+1;
     end else begin
      if(pending!=0||dqm!=0)$fatal(1,"read overlap/mask");
      pending=3;pending_data=memory[index];reads=reads+1;
     end
    end
    default:$fatal(1,"unsupported command");
   endcase
  end
 end
endmodule
