// Register-pair upload endpoint. No unvalidated bytes reach the active bank.
module uart_cfg_transport #(
 parameter QUIET_CYCLES=270000, TIMEOUT_CYCLES=2700000
)(
 input wire clk,rst_n,rx_byte,wr_en,
 input wire [7:0] wr_addr,wr_data,rd_addr,
 input wire idle_allowed,
 input wire [3:0] enabled_slots,
 output reg [7:0] rd_data,
 output reg sandbox,
 output wire pair_reset,
 output wire cfg_valid,cfg_commit,
 output wire [1:0] cfg_slot,
 output wire [3:0] cfg_part,
 output wire [87:0] cfg_word,
 input wire cfg_ready,cfg_applied,cfg_error
);
 localparam IDLE=0,HEADER=1,DATA=2,CRCLO=3,CRCHI=4,END=5,
  READ=6,READWAIT=7,SEND=8,WORDWAIT=9,COMMIT=10,COMMITWAIT=11,DONE=12;
 reg [3:0] state;reg [1:0] header_index,slot;
 reg [7:0] count,read_index;reg [2:0] result;
 reg [3:0] part,byte_index;
 reg [15:0] sequence_id,crc,revision;
 reg crc_low_ok,crc_ok;
 reg [87:0] word_shift;
 reg [7:0] buffer[0:255] /* synthesis syn_ramstyle="block_ram" */;
 localparam TW=$clog2(TIMEOUT_CYCLES+2);
 localparam QW=$clog2(QUIET_CYCLES+2);
 reg [QW-1:0] quiet;
 reg [TW-1:0] age;
 assign pair_reset=(quiet==QUIET_CYCLES-1)&&!rx_byte;
 assign cfg_valid=state==SEND||state==COMMIT;
 assign cfg_commit=state==COMMIT;assign cfg_slot=slot;
 assign cfg_part=part;assign cfg_word=word_shift;
 function [15:0] crc_byte;
 input [15:0] current;input [7:0] data;reg [15:0] c;integer j;
 begin c=current^{data,8'd0};for(j=0;j<8;j=j+1)c=c[15]?(c<<1)^16'h1021:(c<<1);crc_byte=c;end
 endfunction
 always @(posedge clk)if(rst_n&&state==DATA&&wr_en&&wr_addr==8'he4&&age!=TIMEOUT_CYCLES)
  buffer[count]<=wr_data;
 // Eleven byte shifts overwrite all 88 bits before cfg_valid. Clearing this
 // register on every word adds a redundant wide data mux and is unnecessary.
 always @(posedge clk)if(state==READ)word_shift<={buffer[read_index],word_shift[87:8]};
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;sandbox<=0;quiet<=0;age<=0;header_index<=0;slot<=0;count<=0;result<=0;
   sequence_id<=0;crc<=16'hffff;crc_low_ok<=0;crc_ok<=0;revision<=0;
   read_index<=0;part<=0;byte_index<=0;
  end else begin
   if(rx_byte)quiet<=0;else if(quiet<QUIET_CYCLES)quiet<=quiet+1'b1;
   if(state==IDLE||(wr_en&&wr_addr!=8'h0f))age<=0;else if(age<TIMEOUT_CYCLES+1)age<=age+1'b1;
   if(state>=HEADER&&state<=END&&age==TIMEOUT_CYCLES)begin result<=5;state<=DONE;end
   else case(state)
    IDLE: if(wr_en&&wr_addr==8'he0)begin
     if(wr_data==8'ha5)begin
      sandbox<=1;result<=0;count<=0;crc<=crc_byte(16'hffff,8'd1);crc_low_ok<=0;crc_ok<=0;header_index<=0;
      if(idle_allowed)state<=HEADER;else begin result<=6;state<=DONE;end
     end else if(wr_data==8'hc3)sandbox<=0;
    end
    HEADER: if(wr_en&&wr_addr!=8'h0f)begin
     if(wr_addr==8'he1+{6'd0,header_index}&&(header_index!=0||wr_data<4))begin
      crc<=crc_byte(crc,wr_data);
      case(header_index)0:slot<=wr_data[1:0];1:sequence_id[7:0]<=wr_data;2:sequence_id[15:8]<=wr_data;endcase
      if(header_index==2)state<=DATA;else header_index<=header_index+1'b1;
     end else begin result<=7;state<=DONE;end
    end
    DATA: if(wr_en&&wr_addr!=8'h0f)begin
     if(wr_addr==8'he4)begin
      crc<=crc_byte(crc,wr_data);count<=count+1'b1;
      if(count==175)state<=CRCLO;
     end else begin result<=3;state<=DONE;end
    end
    CRCLO: if(wr_en&&wr_addr!=8'h0f)begin
     if(wr_addr==8'he5)begin crc_low_ok<=wr_data==crc[7:0];state<=CRCHI;end
     else begin result<=3;state<=DONE;end
    end
    CRCHI: if(wr_en&&wr_addr!=8'h0f)begin
     if(wr_addr==8'he6)begin crc_ok<=crc_low_ok&&(wr_data==crc[15:8]);state<=END;end
     else begin result<=7;state<=DONE;end
    end
    END: if(wr_en&&wr_addr!=8'h0f)begin
     if(wr_addr!=8'he7||wr_data!=8'h5a)begin result<=7;state<=DONE;end
     else if(!crc_ok)begin result<=2;state<=DONE;end
     else begin read_index<=0;part<=0;byte_index<=0;state<=READ;end
    end
    READ:state<=READWAIT;
    READWAIT:begin
     if(byte_index==10)state<=SEND;
     else begin byte_index<=byte_index+1'b1;read_index<=read_index+1'b1;state<=READ;end
    end
    SEND:if(cfg_ready)state<=WORDWAIT;
    WORDWAIT:if(cfg_error)begin result<=4;state<=DONE;end
     else if(part==15)state<=COMMIT;
     else begin part<=part+1'b1;byte_index<=0;read_index<=read_index+1'b1;state<=READ;end
    COMMIT:if(cfg_ready)state<=COMMITWAIT;
    COMMITWAIT:begin
     if(cfg_error)begin result<=4;state<=DONE;end
     else if(cfg_applied)begin revision<=revision+1'b1;result<=1;state<=DONE;end
    end
    DONE:if(quiet>=QUIET_CYCLES)state<=IDLE;
    default:state<=IDLE;
   endcase
  end
 end
 always @* begin
  rd_data=0;
  case(rd_addr)
   8'hd0:rd_data=8'h75;8'hd1:rd_data=1;8'hd2:rd_data=4;8'hd3:rd_data=16;8'hd4:rd_data=11;8'hd5:rd_data=7;
   8'hd6:rd_data=state==IDLE?0:state<=END?1:state==DONE?3:2;
   8'hd7:rd_data=result;8'hd8:rd_data=sequence_id[7:0];8'hd9:rd_data=sequence_id[15:8];
   8'hda:rd_data={6'd0,slot};8'hdb:rd_data=count;8'hdc:rd_data=crc[7:0];8'hdd:rd_data=crc[15:8];
   8'hde:rd_data=revision[7:0];8'hdf:rd_data=revision[15:8];
   8'he8:rd_data={4'd0,enabled_slots};8'he9:rd_data={6'd0,sandbox,idle_allowed};
  endcase
 end
endmodule
